// ---------------------------------------------------------------------------
// acq_frontend.sv -- acquisition front end: 250 Hz sample enable, absolute sample
// index, gap detection, clamp counting, and the input quantiser of plan 38 section 4.1.
// Contract profile: stream stage (I1).
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). Stage ports carry the sample group plus the status group this stage
// owns; s_ready does not exist inside the datapath (decision D1, plan 13.3).
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 section 2.2):
//   in  and out word  W_IN     = 16   Q12.4, 12 significant counts shifted left four
//   rate divider      W_RATE_DIV = 20  399999 needs 19 bits, 16 is not enough (D12)
//   sample index      W_IDX    = 32
//   marker vector     W_TUSER  = 8    bits 0 to 3 used: clamp, gap, weak, undecided
// Saturation points: the count rail is CLAMP_COUNT 2047, the largest legal word is
//   CLAMP_WORD 32752 = 2047 << 4 (SHIFT_IN 4). The clamp counter is counted BEFORE
//   clamping and the marker is strict, so a count that lands exactly on 2047 is not
//   marked clamped (doc 36 3.6). Gap recovery span is GAP_RECOVERY 131 samples.
// Rounding rule: RND_TIES_EVEN on the quantiser path only, np.rint, rantai.py:163.
// Model lines this file mirrors: rantai.py:49-51, :156-165, :163, :164.
//
// Fase 2, the quantiser of plan 38 section 4.1, exact form and the reason for it:
//   pre = rint(c * CLAMP_COUNT / Q_DIVISOR)  with c the 12 bit signed record count
//   word = clip(pre, -2047, +2047) << SHIFT_IN
//   c * 2047 = (c << 11) - c, one adder and no multiplier [I2 section 1, candidate A]
//   1000 = MV_FULL_SCALE * REC_GAIN_MV, declared in the package, never typed here
// The divide by 1000 is a restoring division, one compare and subtract per cycle, on the
// magnitude of c * 2047. The quotient needs W_STEP = W_MUL - SHIFT_QUO = 23 - 10 = 13 bits,
// so it is 13 steps and not the 10 the plan's cycle budget names; the sweep over all 4095
// counts shows why: a 10 bit quotient cannot reach 4190. Rounding is half to even on the
// remainder, carried out of the last step: rint(half) adds one only when the quotient is
// odd, which is where ties to even differs from ties away from zero.
// The sign is applied after the magnitude division, which is exact because rint is an odd
// function: rint(-x) = -rint(x), and the clamp is symmetric.
//
// Structure and latency: the input word is a stream port, so the quantiser is pipelined and
// not an iterative loop: one count in per cycle, one word out per cycle, fixed latency of
// LAT_REAL cycles, no back pressure anywhere (D1). The pipeline is one register slice for
// c * 2047, W_STEP slices for the restoring division, and the last slice for rounding, the
// shift of SHIFT_IN and the clamp. LAT_CYCLES is kept because the port list is frozen; the
// real latency is LAT_REAL and rtl/tb/tb_kuantisasi.sv measures it instead of trusting it.
//
// The 250 Hz timebase is independent of the datapath: the 20 bit rate counter free runs on
// every clock, holds sample_en for one cycle every i_rate_div + 1 clocks, and the 32 bit
// index counter advances on sample_en only. sample_en is therefore the sample cadence and
// the datapath is the word flow; i_enable masks the output and the counting, it never
// stalls the pipeline.
//
// House style: wire and reg only (D10), one clock, synchronous active low reset,
// no vendor primitives, no initial blocks.
// ---------------------------------------------------------------------------
`default_nettype none

module acq_frontend #(
    parameter int unsigned W_IN       = afib_lite_pkg::W_IN,
    parameter int unsigned W_IDX      = afib_lite_pkg::W_IDX,
    parameter int unsigned W_TUSER    = afib_lite_pkg::W_TUSER,
    parameter int unsigned W_RATE_DIV = afib_lite_pkg::W_RATE_DIV,
    parameter int unsigned W_EVKIND   = afib_lite_pkg::W_EVKIND,
    parameter int unsigned LAT_CYCLES = 1
) (
    input  wire                     clk_i,
    input  wire                     rst_ni,

    // sample stream in
    // The quantiser reads the 12 significant count bits [W_IN-1:SHIFT_IN] of the sample word
    // and deliberately does not read the four sub count front end bits below them
    // (adapter.py:87-89, ATTYS_FRONT_END). The suppression sits on the port because that is
    // where the tool reports the unused slice; the reason is in the quantiser input block.
    /* verilator lint_off UNUSEDSIGNAL */
    input  wire [W_IN-1:0]          s_tdata,
    /* verilator lint_on UNUSEDSIGNAL */
    input  wire                     s_tvalid,
    input  wire                     s_tlast,
    input  wire [W_TUSER-1:0]       s_tuser,

    // configuration
    input  wire                     i_enable,
    input  wire [W_RATE_DIV-1:0]    i_rate_div,
    input  wire                     i_clear_counters,

    // sample stream out
    output reg  [W_IN-1:0]          m_tdata,
    output reg                      m_tvalid,
    output reg                      m_overflow,
    output reg                      m_tlast,
    output reg  [W_TUSER-1:0]       m_tuser,
    output reg  [W_IDX-1:0]         m_sample_idx,

    // event sideband
    output reg                      m_ev_valid,
    output reg  [W_EVKIND-1:0]      m_ev_kind,
    output reg  [W_IDX-1:0]         m_ev_idx,
    output reg  [31:0]              m_ev_val,

    // introspection
    output reg                      d_valid,
    output reg  [W_IN-1:0]          d_word,

    // status this stage owns
    output reg  [31:0]              o_sample_idx,
    output reg  [31:0]              o_gap_count,
    output reg  [31:0]              o_clamp_count
);

    // ======================================================================= widths
    // Every one of these follows from a package constant, none is a bare number.
    localparam int unsigned W_CNT     = W_IN - afib_lite_pkg::SHIFT_IN;        // 12 count bits
    localparam int unsigned SHIFT_MUL = $clog2(afib_lite_pkg::CLAMP_COUNT);    // 11, 2047 = 2**11 - 1
    localparam int unsigned W_MUL     = W_CNT + SHIFT_MUL;                     // 23
    localparam int unsigned SHIFT_QUO = $clog2(afib_lite_pkg::Q_DIVISOR);      // 10, 1000 < 2**10
    localparam int unsigned W_STEP    = W_MUL - SHIFT_QUO;                     // 13 restoring steps
    localparam int unsigned W_REM     = SHIFT_QUO + 1;                         // 11, rem < 2 * 1000
    localparam int unsigned W_QUO     = W_STEP;                                // 13, one bit per step
    localparam int unsigned W_PRE     = W_QUO + 2;                             // 15, signed, +-4191
    localparam int unsigned W_GAPSPAN = $clog2(afib_lite_pkg::GAP_RECOVERY + 1);// 8, 131 samples
    localparam int unsigned LAT_REAL  = 2 + W_STEP;                            // 15 cycles

    localparam logic [31:0]       DIV_WIDE = afib_lite_pkg::Q_DIVISOR;         // 1000
    localparam logic [W_REM-1:0]  DIV_RAIL = DIV_WIDE[W_REM-1:0];              // 1000 in rem width
    localparam logic [31:0]       HALF_WIDE = DIV_WIDE / 2;                    // 500, the tie point
    localparam logic signed [W_PRE-1:0] CLAMP_PRE = afib_lite_pkg::CLAMP_COUNT[W_PRE-1:0];
    localparam logic [W_GAPSPAN-1:0]    GAP_SPAN  = afib_lite_pkg::GAP_RECOVERY[W_GAPSPAN-1:0];

    // ======================================================================= timebase
    reg [W_RATE_DIV-1:0] rate_cnt_q;
    reg [W_IDX-1:0]      sample_idx_q;
    reg                  sample_en_q;

    // ======================================================================= side chain
    // The sample identity that travels with the arithmetic: absolute index, the gap event
    // observed at the input, the input valid, tlast, the count sign and the input marker.
    localparam int unsigned S_IDX = 0;
    localparam int unsigned S_GAP = S_IDX + W_IDX;
    localparam int unsigned S_VAL = S_GAP + 1;
    localparam int unsigned S_LST = S_VAL + 1;
    localparam int unsigned S_SGN = S_LST + 1;
    localparam int unsigned S_TU  = S_SGN + 1;
    localparam int unsigned W_SIDE = S_TU + W_TUSER;

    // ======================================================================= quantiser input
    // The sample word of the contract is Q12.4: the 12 significant counts sit in bits 15 to
    // 4 and the low SHIFT_IN bits carry the sub count front end of the acquisition ladder
    // (adapter.py:87-89, ATTYS_FRONT_END). Plan 38 section 4.1 states the quantiser input
    // as a 12 bit signed count, so the count is the field [W_IN-1:SHIFT_IN] and the low bits
    // are not read at all: they are finer than one count and the model rounds on whole
    // counts. The suppression below marks that as deliberate and is reported in the Fase 2
    // report, together with the difference between plan 4.1 and the signal table.
    /* verilator lint_off UNUSEDSIGNAL */
    wire signed [W_CNT-1:0] cnt_in = s_tdata[W_IN-1:afib_lite_pkg::SHIFT_IN];
    /* verilator lint_on UNUSEDSIGNAL */
    wire                    cnt_neg  = cnt_in[W_CNT-1];
    wire signed [W_MUL-1:0] cnt_ext  = {{(W_MUL-W_CNT){cnt_neg}}, cnt_in};
    wire signed [W_MUL-1:0] prod_s   = (cnt_ext <<< SHIFT_MUL) - cnt_ext;  // c * 2047, plan 38 4.1
    wire        [W_MUL-1:0] prod_mag = prod_s[W_MUL-1] ? (-prod_s) : prod_s;

    // gap: the input marker bit, and a sample slot that carried no word at all.
    wire gap_marker_in = s_tvalid & s_tuser[afib_lite_pkg::TU_GAP];
    wire gap_lost_in   = sample_en_q & i_enable & ~s_tvalid;
    wire gap_ev_in     = gap_marker_in | gap_lost_in;
    wire valid_in      = s_tvalid & i_enable;

    // ======================================================================= pipeline registers
    reg [W_REM-1:0]  rem_q  [0:W_STEP];
    reg [W_QUO-1:0]  quo_q  [0:W_STEP];
    reg [W_STEP-1:0] bit_q  [0:W_STEP];
    reg [W_SIDE-1:0] side_q [0:W_STEP];
    reg [W_GAPSPAN-1:0] gap_span_q;

    // Slice 0: the product and the seeding of the restoring division. The initial remainder
    // is the top SHIFT_QUO bits of the magnitude, which is below 1000 for every count in
    // range because CLAMP_COUNT * CLAMP_COUNT < 2**W_STEP * Q_DIVISOR.
    always @(posedge clk_i) begin
        if (!rst_ni) begin
            rem_q[0]  <= {W_REM{1'b0}};
            quo_q[0]  <= {W_QUO{1'b0}};
            bit_q[0]  <= {W_STEP{1'b0}};
            side_q[0] <= {W_SIDE{1'b0}};
        end else begin
            rem_q[0]  <= {{(W_REM-SHIFT_QUO){1'b0}}, prod_mag[W_MUL-1:W_STEP]};
            quo_q[0]  <= {W_QUO{1'b0}};
            bit_q[0]  <= prod_mag[W_STEP-1:0];
            side_q[0] <= {s_tuser, cnt_neg, s_tlast, valid_in, gap_ev_in, sample_idx_q};
        end
    end

    // Slices 1 to W_STEP: the restoring division, one dividend bit in and one quotient bit
    // out per slice. bits arrive most significant first, so the shift register feeds its own
    // top bit into the remainder and the quotient shifts the decision in at the bottom.
    genvar gi;
    generate
        for (gi = 0; gi < W_STEP; gi = gi + 1) begin : g_langkah
            wire [W_REM-1:0] shifted = {rem_q[gi][W_REM-2:0], bit_q[gi][W_STEP-1]};
            wire             enough  = (shifted >= DIV_RAIL);
            always @(posedge clk_i) begin
                if (!rst_ni) begin
                    rem_q[gi+1]  <= {W_REM{1'b0}};
                    quo_q[gi+1]  <= {W_QUO{1'b0}};
                    bit_q[gi+1]  <= {W_STEP{1'b0}};
                    side_q[gi+1] <= {W_SIDE{1'b0}};
                end else begin
                    rem_q[gi+1]  <= enough ? (shifted - DIV_RAIL) : shifted;
                    quo_q[gi+1]  <= {quo_q[gi][W_QUO-2:0], enough};
                    bit_q[gi+1]  <= {bit_q[gi][W_STEP-2:0], 1'b0};
                    side_q[gi+1] <= side_q[gi];
                end
            end
        end
    endgenerate

    // ======================================================================= rounding, shift, clamp
    // Last slice. Round half to even on the remainder of the magnitude: above the half it
    // goes up, below it stays, exactly on it it goes up only when the quotient is odd, so
    // the even neighbour wins. The clamp then keeps the pre clamp value inside CLAMP_COUNT,
    // counted before clamping, and the shift by SHIFT_IN builds the 16 bit Q12.4 word. The
    // shift cannot overflow the word: 2047 << 4 = 32752 fits 16 bits (doc 36 2.1).
    wire [W_QUO-1:0] quo_f   = quo_q[W_STEP];
    wire [W_REM-1:0] rem_f   = rem_q[W_STEP];
    wire [31:0]      rem_wide = {{(32-W_REM){1'b0}}, rem_f};
    wire             rnd_high = (rem_wide > HALF_WIDE);
    wire             rnd_tie  = (rem_wide == HALF_WIDE);
    wire [W_QUO-1:0] quo_rnd  = (rnd_high | (rnd_tie & quo_f[0])) ? (quo_f + 1'b1) : quo_f;
    wire             cnt_sign = side_q[W_STEP][S_SGN];
    wire signed [W_PRE-1:0] pre_pos = {{(W_PRE-W_QUO){1'b0}}, quo_rnd};
    wire signed [W_PRE-1:0] pre_raw = cnt_sign ? (-pre_pos) : pre_pos;
    wire             clipped  = (pre_raw > CLAMP_PRE) | (pre_raw < (-CLAMP_PRE));
    wire signed [W_PRE-1:0] pre_cl = clipped ? (cnt_sign ? (-CLAMP_PRE) : CLAMP_PRE) : pre_raw;
    // The shift operand is widened to the word width first, so no operand is expanded inside
    // the shift itself. The shift discards nothing that carries value: the clamp above keeps
    // |pre_cl| at or below CLAMP_COUNT, so |pre_cl << SHIFT_IN| is at most CLAMP_WORD 32752
    // and fits W_IN bits exactly (doc 36 2.1).
    wire signed [W_IN-1:0]  pre_w   = {{(W_IN-W_PRE){pre_cl[W_PRE-1]}}, pre_cl};
    wire signed [W_IN-1:0]  word_f  = pre_w <<< afib_lite_pkg::SHIFT_IN;

    wire             out_valid = side_q[W_STEP][S_VAL];
    wire             gap_out   = side_q[W_STEP][S_GAP];
    wire [W_TUSER-1:0] in_mark = side_q[W_STEP][S_TU +: W_TUSER];
    wire               gap_span_on = (gap_span_q != {W_GAPSPAN{1'b0}});
    wire [W_TUSER-1:0] clip_bit = {{(W_TUSER-1){1'b0}}, clipped} << afib_lite_pkg::TU_CLAMP;
    wire [W_TUSER-1:0] gap_bit  = {{(W_TUSER-1){1'b0}}, (gap_out | gap_span_on)}
                                  << afib_lite_pkg::TU_GAP;
    wire [W_TUSER-1:0] out_mark = in_mark | clip_bit | gap_bit;

    wire overflow_now = 1'b0;  // the word never grows here: 2047 << 4 fits 16 bits

    always @(posedge clk_i) begin
        if (!rst_ni) gap_span_q <= {W_GAPSPAN{1'b0}};
        else if (i_clear_counters) gap_span_q <= {W_GAPSPAN{1'b0}};
        else if (side_q[W_STEP][S_GAP]) gap_span_q <= GAP_SPAN;
        else if (out_valid & (gap_span_q != {W_GAPSPAN{1'b0}}))
            gap_span_q <= gap_span_q - {{(W_GAPSPAN-1){1'b0}}, 1'b1};
    end

    // ======================================================================= output register
    always @(posedge clk_i) begin
        if (!rst_ni) begin
            m_tdata       <= {W_IN{1'b0}};
            m_tvalid      <= 1'b0;
            m_overflow    <= 1'b0;
            m_tlast       <= 1'b0;
            m_tuser       <= {W_TUSER{1'b0}};
            m_sample_idx  <= {W_IDX{1'b0}};
            m_ev_valid    <= 1'b0;
            m_ev_kind     <= afib_lite_pkg::EV_NONE;
            m_ev_idx      <= {W_IDX{1'b0}};
            m_ev_val      <= 32'd0;
            d_valid       <= 1'b0;
            d_word        <= {W_IN{1'b0}};
            o_sample_idx  <= 32'd0;
            o_gap_count   <= 32'd0;
            o_clamp_count <= 32'd0;
        end else begin
            m_tdata       <= word_f;
            m_tvalid      <= out_valid;
            m_overflow    <= m_overflow | overflow_now;
            m_tlast       <= side_q[W_STEP][S_LST];
            m_tuser       <= out_mark;
            m_sample_idx  <= side_q[W_STEP][S_IDX +: W_IDX];
            m_ev_valid    <= side_q[W_STEP][S_GAP];
            m_ev_kind     <= side_q[W_STEP][S_GAP] ? afib_lite_pkg::EV_GAP
                                                   : afib_lite_pkg::EV_NONE;
            m_ev_idx      <= side_q[W_STEP][S_IDX +: W_IDX];
            m_ev_val      <= 32'd0;
            d_valid       <= out_valid;
            d_word        <= word_f;

            // status counters, cleared by i_clear_counters. The clamp counter counts the
            // word that the clamp actually moved, which is the pre clamp test and not the
            // rail value, and the gap counter counts the gap events of the input.
            if (i_clear_counters) begin
                o_sample_idx  <= 32'd0;
                o_gap_count   <= 32'd0;
                o_clamp_count <= 32'd0;
            end else begin
                o_sample_idx  <= {{(32-W_IDX){1'b0}}, sample_idx_q};
                o_gap_count   <= side_q[W_STEP][S_GAP]
                                 ? (o_gap_count + 32'd1) : o_gap_count;
                o_clamp_count <= (out_valid & clipped)
                                 ? (o_clamp_count + 32'd1) : o_clamp_count;
            end
        end
    end

    // ======================================================================= timebase logic
    // Terminal count from i_rate_div, one sample_en pulse every i_rate_div + 1 clocks:
    // RATE_DIV_RST 399999 at CLK_HZ 100 MHz is exactly 250.0 Hz (doc 36 3.1, D12). The
    // counter free runs and i_enable does not stop it, so sample_en is a clock and not a
    // consequence of the enable; i_enable gates the index and the counting.
    always @(posedge clk_i) begin
        if (!rst_ni) begin
            rate_cnt_q   <= {W_RATE_DIV{1'b0}};
            sample_idx_q <= {W_IDX{1'b0}};
            sample_en_q  <= 1'b0;
        end else begin
            if (rate_cnt_q >= i_rate_div) begin
                rate_cnt_q  <= {W_RATE_DIV{1'b0}};
                sample_en_q <= 1'b1;
            end else begin
                rate_cnt_q  <= rate_cnt_q + {{(W_RATE_DIV-1){1'b0}}, 1'b1};
                sample_en_q <= 1'b0;
            end

            if (sample_en_q && i_enable)
                sample_idx_q <= sample_idx_q + {{(W_IDX-1){1'b0}}, 1'b1};
        end
    end

endmodule

`default_nettype wire
