// ---------------------------------------------------------------------------
// rr_series.sv -- RR interval series, the eight-interval queue, the reseeding history,
// and the four interval marks. Contract profile: event stage (I1).
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). Consumes the QRS events of peak_detect on s_ev_* and produces m_rr_last,
// m_rr_mark and its own events on m_ev_*. Owns o_rr_long_count.
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 section 2.2):
//   rr in ms         W_RR_MS  = 16   Q16.0. Measured 12 bits on 04015, 16 on the worst
//                                    record, and Python never overflows, so a 12 bit
//                                    view would fail on the board as false missed beats.
//   rr in samples    W_RR_SMP = 15   the search-back distance accumulator, in samples.
//                                    Units are easy to mix here: the same physical gap
//                                    reads 51064 ms and 12766 samples.
//   index            W_IDX    = 32
// Saturation points: accepted RR band 250 to 2000 ms, long interval ceiling RR_LONG_MS
//   3000 ms, full field RR_MAX_MS 65535 so nothing is clamped to 13 bits, and the gap
//   recovery span GAP_RECOVERY 131 samples which is 524 ms at 250 Hz.
// Rounding rule: RND_FLOOR for the eight-term mean (rantai.py:399) and for the rational
//   mean (rantai.py:426 where the denominator is at most 8), and RND_TRUNC_ZERO for the
//   even-count median (rantai.py:372). The missed-beat test is the cross form 83/50 at
//   rantai.py:534 so no divider is needed; the band test is the cross forms
//   25*d*x >= 23*n and <= 29*n at rantai.py:359-361.
// Model lines this file mirrors: rantai.py:375-440, :443-559, :569-600, :631-642,
//   interval in milliseconds at :632, band at :359-361, ra1 at :399, ra2 at :426,
//   median at :372, marks at :529, :534, :536, :543, :544, ceiling at :496, cross form
//   at :581.
//
// Buffer lengths, not time constants: rhythm marker window 8 intervals, reseeding history
// 32 intervals, at most one reseed per eight intervals, candidate depth DECISION_DEPTH 8.
// They must be derived from the beat or sample counter, never from a fixed cycle count.
//
// Fixed latency: about 40 cycles per beat. Placeholder uses one cycle.
//
// Fase 1 status: PLACEHOLDER. The body forwards the accepted interval register and emits
// no event, so lint and a smoke simulation pass. Ports and widths are frozen.
// House style: wire and reg only (D10), one clock, synchronous active low reset.
// ---------------------------------------------------------------------------
`default_nettype none

module rr_series #(
    parameter int unsigned W_RR_MS    = afib_lite_pkg::W_RR_MS,
    parameter int unsigned W_RR_SMP   = afib_lite_pkg::W_RR_SMP,
    parameter int unsigned W_IDX      = afib_lite_pkg::W_IDX,
    parameter int unsigned W_TUSER    = afib_lite_pkg::W_TUSER,
    parameter int unsigned W_EVKIND   = afib_lite_pkg::W_EVKIND,
    parameter int unsigned LAT_CYCLES = 1
) (
    input  wire                     clk_i,
    input  wire                     rst_ni,

    // configuration
    input  wire                     i_enable,
    input  wire                     i_clear_counters,

    // sample stream passthrough: the window layer still needs the timing words
    input  wire                     s_tvalid,
    input  wire                     s_tlast,
    input  wire [W_TUSER-1:0]       s_tuser,
    input  wire [W_IDX-1:0]         s_sample_idx,

    // event sideband in: QRS beats and peak candidates from peak_detect
    input  wire                     s_ev_valid,
    input  wire [W_EVKIND-1:0]      s_ev_kind,
    input  wire [W_IDX-1:0]         s_ev_idx,
    input  wire [31:0]              s_ev_val,

    // decision group this stage owns
    output reg  [W_RR_MS-1:0]       m_rr_last,
    output reg  [1:0]               m_rr_mark,

    // event sideband out: interval closed and decision window closed
    output reg                      m_ev_valid,
    output reg  [W_EVKIND-1:0]      m_ev_kind,
    output reg  [W_IDX-1:0]         m_ev_idx,
    output reg  [31:0]              m_ev_val,

    // introspection
    output reg                      d_valid,
    output reg  [W_RR_MS-1:0]       d_rr_ms,
    output reg  [W_RR_SMP-1:0]      d_rr_smp,

    // status this stage owns
    output reg  [31:0]              o_rr_long_count
);

    reg [W_RR_MS-1:0] rr_ms_q;
    reg [1:0]         rr_mark_q;

    wire beat_now   = s_ev_valid & i_enable & s_tvalid & (s_ev_kind == afib_lite_pkg::EV_QRS);
    wire window_now = i_enable & s_tvalid & s_tlast;
    wire gap_mark   = i_enable & s_tvalid & s_tuser[afib_lite_pkg::TU_GAP];
    wire long_now   = beat_now & (s_ev_val[W_RR_MS-1:0] > afib_lite_pkg::RR_LONG_MS);

    always @(posedge clk_i) begin
        if (!rst_ni) begin
            rr_ms_q         <= {W_RR_MS{1'b0}};
            rr_mark_q       <= afib_lite_pkg::RR_MARK_KEEP;
            m_rr_last       <= {W_RR_MS{1'b0}};
            m_rr_mark       <= afib_lite_pkg::RR_MARK_KEEP;
            m_ev_valid      <= 1'b0;
            m_ev_kind       <= afib_lite_pkg::EV_NONE;
            m_ev_idx        <= {W_IDX{1'b0}};
            m_ev_val        <= 32'd0;
            d_valid         <= 1'b0;
            d_rr_ms         <= {W_RR_MS{1'b0}};
            d_rr_smp        <= {W_RR_SMP{1'b0}};
            o_rr_long_count <= 32'd0;
        end else begin
            // placeholder datapath: register the interval word of the accepted beat
            rr_ms_q   <= s_ev_val[W_RR_MS-1:0];
            rr_mark_q <= gap_mark ? afib_lite_pkg::RR_MARK_GAP : afib_lite_pkg::RR_MARK_KEEP;
            m_rr_last <= rr_ms_q;
            m_rr_mark <= rr_mark_q;

            // placeholder event: an accepted beat closes an interval, a tlast closes a window
            m_ev_valid <= beat_now | window_now;
            m_ev_kind  <= window_now ? afib_lite_pkg::EV_WINDOW
                                     : (beat_now ? afib_lite_pkg::EV_RR : afib_lite_pkg::EV_NONE);
            m_ev_idx   <= window_now ? s_sample_idx : s_ev_idx;
            m_ev_val   <= s_ev_val;

            d_valid    <= beat_now;
            d_rr_ms    <= rr_ms_q;
            d_rr_smp   <= {W_RR_SMP{1'b0}};

            if (i_clear_counters) begin
                o_rr_long_count <= 32'd0;
            end else if (long_now) begin
                o_rr_long_count <= o_rr_long_count + 32'd1;
            end
        end
    end

endmodule

`default_nettype wire
