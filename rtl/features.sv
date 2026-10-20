// ---------------------------------------------------------------------------
// features.sv -- window feature layer over 32 intervals with a stride of 4 beats.
// Contract profile: apex stage (I1).
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). This skeleton is built now because decision D11 retired the reason for
// delaying it: the marked-series arm landed on 20 October 2026, so what is left is an
// ordinary technical dependency.
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 sections 5.4 and
// 5.5, the 18 node feature table and the binding width over the three source arms):
//   d_rmssd  W_F_RMSSD = 18   Q10.8. Doc 36 5.4 measures 14 on the active arm; 5.5 pins
//                             18 on the reference arm, and the reference arm binds.
//   d_ratio  W_F_RATIO = 17   Q1.16. Pinned by the owner on 20 October 2026. 13 bits
//                             would store the value, but the threshold sweep parity
//                             needs precision 16, which is 17 bits with the sign.
//   d_ent    W_F_ENT   = 15   Q1.14, entropy divided by four. 5.4 measures 9, 5.5 pins 15.
//   d_meanq  W_F_MEANQ = 27   Q19.8, the sum of 31 squared differences divided by 31.
//   index    W_IDX     = 32
// Saturation points: sum of 31 squared differences 0 to 7052752, mean square 0 to
//   227508.13 in Q19.8, RMSSD 0 to 476.98 ms. DECISION_DEPTH 8 is the decision buffer.
// Rounding rule: four nodes are not exact and their implementation must be pinned here
//   and written in this header before Fase 8 (doc 36 5.4 and TASK_BRIEF 3):
//     integer square root, rounds DOWN;
//     log2 over a table of two 256 entry banks;
//     division by 31, RND_FLOOR;
//     bin edges by exact cross multiplication, never by a float linspace, because
//     np.linspace edges put a value exactly on an edge into the next bin.
//   Everything else is RND_FLOOR. The four inexact nodes are bounded, not equal:
//   18 bits and 15 bits are enclosures at a resolution of 2**-20, not identities.
// Model lines this file mirrors: rantai.py:754-861, :799-826, :848-861, difference at
//   :851, RMSSD at :852, pNN50 at :853, sort at :854, core at :855, edges at :856,
//   histogram at :858, probabilities at :859, entropy at :860, ratio and shift at :861.
//   The comment block at :718-761 states that this layer is fraction-free in the model.
//
// The 32 value sorting network is shared with the RR median of history in rr_series, and
// the integer root and the divider are one shared unit (plan 4.13). Without that sharing
// this layer alone would take 63 percent of the core area estimate.
//
// Fixed latency: about 600 cycles per window against 80000000 cycles of window budget.
// Placeholder uses one cycle; Fase 8 owns the schedule.
//
// Fase 1 status: PLACEHOLDER. The body registers the input words with a fixed latency and
// computes no feature, so lint and a smoke simulation pass. Ports and widths are frozen.
// House style: wire and reg only (D10), one clock, synchronous active low reset.
// ---------------------------------------------------------------------------
`default_nettype none

module features #(
    parameter int unsigned W_F_RMSSD  = afib_lite_pkg::W_F_RMSSD,
    parameter int unsigned W_F_RATIO  = afib_lite_pkg::W_F_RATIO,
    parameter int unsigned W_F_ENT    = afib_lite_pkg::W_F_ENT,
    parameter int unsigned W_F_MEANQ  = afib_lite_pkg::W_F_MEANQ,
    parameter int unsigned W_IDX      = afib_lite_pkg::W_IDX,
    parameter int unsigned LAT_CYCLES = 1
) (
    input  wire                     clk_i,
    input  wire                     rst_ni,

    // interval stream in: the accepted RR value and its mark
    input  wire                     s_valid,
    input  wire [afib_lite_pkg::W_RR_MS-1:0] s_rr_ms,
    input  wire [1:0]               s_rr_mark,
    input  wire [W_IDX-1:0]         s_window_idx,

    // configuration
    input  wire                     i_enable,
    input  wire                     i_clear_counters,
    input  wire [4:0]               i_arm_select,    // b3 selects the marked series source
    input  wire [7:0]               i_window_step,   // stride in beats
    input  wire [7:0]               i_window_beats,  // window length in beats

    // feature taps
    output reg                      d_valid,
    output reg  [W_F_RMSSD-1:0]     d_rmssd,
    output reg  [W_F_RATIO-1:0]     d_ratio,
    output reg  [W_F_ENT-1:0]       d_ent,
    output reg  [W_F_MEANQ-1:0]     d_meanq,

    // window closed event
    output reg                      m_ev_valid,
    output reg  [afib_lite_pkg::W_EVKIND-1:0] m_ev_kind,
    output reg  [W_IDX-1:0]         m_ev_idx,
    output reg  [31:0]              m_ev_val
);

    reg [7:0] beat_cnt_q;

    wire window_closed = (beat_cnt_q == i_window_beats);

    always @(posedge clk_i) begin
        if (!rst_ni) begin
            beat_cnt_q   <= 8'd0;
            d_valid      <= 1'b0;
            d_rmssd      <= {W_F_RMSSD{1'b0}};
            d_ratio      <= {W_F_RATIO{1'b0}};
            d_ent        <= {W_F_ENT{1'b0}};
            d_meanq      <= {W_F_MEANQ{1'b0}};
            m_ev_valid   <= 1'b0;
            m_ev_kind    <= afib_lite_pkg::EV_NONE;
            m_ev_idx     <= {W_IDX{1'b0}};
            m_ev_val     <= 32'd0;
        end else begin
            if (i_clear_counters) begin
                beat_cnt_q <= 8'd0;
            end else if (s_valid) begin
                beat_cnt_q <= window_closed ? i_window_step : (beat_cnt_q + 8'd1);
            end

            // placeholder feature taps: register the interval word into each tap, no arithmetic.
            // Every bit of the configuration inputs is read here so that no port is left unread.
            d_valid    <= s_valid & i_enable;
            d_rmssd    <= {{(W_F_RMSSD-afib_lite_pkg::W_RR_MS){1'b0}}, s_rr_ms};
            d_ratio    <= {{(W_F_RATIO-5){1'b0}}, i_arm_select};
            d_ent      <= {{(W_F_ENT-2){1'b0}}, s_rr_mark};
            d_meanq    <= {{(W_F_MEANQ-afib_lite_pkg::W_RR_MS){1'b0}}, s_rr_ms};

            m_ev_valid <= s_valid & i_enable & window_closed;
            m_ev_kind  <= (s_valid & i_enable & window_closed) ? afib_lite_pkg::EV_WINDOW
                                                              : afib_lite_pkg::EV_NONE;
            m_ev_idx   <= s_window_idx;
            m_ev_val   <= {31'd0, i_arm_select[3]};
        end
    end

endmodule

`default_nettype wire
