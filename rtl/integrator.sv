// ---------------------------------------------------------------------------
// integrator.sv -- running window of 38 samples, alternating between 37 and 38 during
// warm-up. Contract profile: stream stage (I1).
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). Introspection port: d_win.
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 section 2.2):
//   in   W_SQ  = 30   the square node
//   out  W_WIN = 33   signed, 32 unsigned; measured range [0, 3105281786]
//   worst W_WIN_WORST = 37   N_WIN 38 times SQ_LIMIT^2 3192589009 = 121318382342
//                            (magnitude convention; a strict two's complement reading
//                             of the same value needs 38, reported, see the package)
// Saturation points: the measured window maximum is 3105281786 and the design bound is
//   13316659200, which is 38 times the measured square maximum 350438400. The
//   theoretical bound is 121318382342 and only synthetic vectors reach it.
//   The design bound 13316659200 is ABOVE the 33 bit port range (2**33 - 1 =
//   8589934591), so the output port saturates at {W_WIN{1'b1}} and raises m_overflow.
//   The internal accumulator is wider than the port on purpose, so the running sum itself
//   is never clamped and recovery after a saturated word is exact.
// Rounding rule: none. Pure summation, no rounding anywhere in the window (doc 36 2.2).
//   The delayed terms are subtracted, never shifted, so RND_FLOOR does not apply here.
// Model lines this file mirrors: rantai.py:259-280, accumulate at :270, the 38 tap
//   subtraction at :272, the alternating 37 correction at :274-275, line length at :267.
//
// The delay line must hold 39 words, not 38, so that x[i-37] and x[i-38] can be read in
// the same cycle. Reads of an index that has not arrived return zero, which is exactly
// the zero initial condition of the model, so no separate padding path is needed.
//
// Fixed latency: one cycle per sample. The plan 4.6 recommendation is 2 cycles per sample
// with one 35 bit adder used twice. That schedule is NOT implemented here, and the reason
// is what the recurrence splits into: rantai.py:270-275 makes the accumulator update a
// THREE term sum (jumlah + nilai - x[i-38]) and the output correction a ONE term
// subtraction (- x[i-37], even index only). A second pass of the reused adder would
// therefore carry a single subtraction, which does not pay for a state machine and the 39
// word buffer the plan priced for it. The body evaluates the two operations as one 37 bit,
// four operand add/subtract tree, and the accumulator register keeps the exact split.
// Reported as a deviation in rtl-synthesis/reports/LAPORAN-FASE4b.md.
//
// Fase 4 body, model form rantai.py:259-280 in registers:
//   jumlah_q is the running total over the last 38 accepted words, exact at
//   W_WIN_WORST = 37 bit: the largest possible total is 38 * (2**30 - 1) = 40802199130,
//   which is below 2**37 = 137438953472, so the accumulator can never wrap for any input
//   the W_SQ port can carry. Every value on the fixture is far below that.
//   Per accepted word i: jumlah_q <= jumlah_q + x[i] - (i >= N_WIN     ? x[i-38] : 0)
//   and the output is that value minus (i even and i >= N_WIN_ALT ? x[i-37] : 0), which
//   is the alternating 37 and 38 width of :274-275. Both taps are read from the delay line
//   before it shifts, so line_q[k] is x[i-1-k] when the word is accepted.
//   The index used for the two guards is s_sample_idx, the PL time base, never a local
//   counter, because the model counts from 0 and a local counter would drift one sample
//   after reset (TASK_BRIEF section 9).
// House style: wire and reg only (D10), one clock, synchronous active low reset.
// ---------------------------------------------------------------------------
`default_nettype none

module integrator #(
    parameter int unsigned W_SQ       = afib_lite_pkg::W_SQ,
    parameter int unsigned W_WIN      = afib_lite_pkg::W_WIN,
    parameter int unsigned W_IDX      = afib_lite_pkg::W_IDX,
    parameter int unsigned W_TUSER    = afib_lite_pkg::W_TUSER,
    parameter int unsigned N_WIN      = afib_lite_pkg::N_WIN,
    parameter int unsigned LAT_CYCLES = 1
) (
    input  wire                     clk_i,
    input  wire                     rst_ni,

    input  wire [W_SQ-1:0]          s_tdata,
    input  wire                     s_tvalid,
    input  wire                     s_tlast,
    input  wire [W_TUSER-1:0]       s_tuser,
    input  wire [W_IDX-1:0]         s_sample_idx,

    output reg  [W_WIN-1:0]         m_tdata,
    output reg                      m_tvalid,
    output reg                      m_overflow,
    output reg                      m_tlast,
    output reg  [W_TUSER-1:0]       m_tuser,
    output reg  [W_IDX-1:0]         m_sample_idx,

    output reg                      d_valid,
    output reg  [W_WIN-1:0]         d_win
);

    // ---- lengths and widths, every one taken from the package -------------
    localparam int unsigned N_A        = afib_lite_pkg::N_WIN_ALT;      // 37, even index width
    localparam int unsigned N_B        = N_WIN;                         // 38, odd index width
    localparam int unsigned LINE_WORDS = N_B + 1;                       // 39, model GarisTunda(39)
    localparam int unsigned W_ACC      = afib_lite_pkg::W_WIN_WORST;    // 37, 38 * SQ_LIMIT**2
    // the package constants are int unsigned, the same 32 bit width as W_IDX, so these
    // comparisons are exact and need no cast
    localparam logic [W_IDX-1:0] N_A_IDX = afib_lite_pkg::N_WIN_ALT;
    localparam logic [W_IDX-1:0] N_B_IDX = afib_lite_pkg::N_WIN;
    localparam logic [W_ACC-1:0] WIN_MAX = {{(W_ACC-W_WIN){1'b0}}, {W_WIN{1'b1}}};

    // ---- state -----------------------------------------------------------
    reg  [W_SQ-1:0]  line_q [0:LINE_WORDS-1];   // line_q[k] = x[i-1-k]
    reg  [W_ACC-1:0] jumlah_q;                  // running total of the last N_B words
    integer k;

    // ---- window arithmetic ----------------------------------------------
    wire [W_ACC-1:0] nilai_u = {{(W_ACC-W_SQ){1'b0}}, s_tdata};
    wire             full_w  = (s_sample_idx >= N_B_IDX);
    wire             alt_w   = (~s_sample_idx[0]) && (s_sample_idx >= N_A_IDX);
    wire [W_ACC-1:0] drop_b  = full_w ? {{(W_ACC-W_SQ){1'b0}}, line_q[N_B-1]} : {W_ACC{1'b0}};
    wire [W_ACC-1:0] drop_a  = alt_w  ? {{(W_ACC-W_SQ){1'b0}}, line_q[N_A-1]} : {W_ACC{1'b0}};
    // rantai.py:270 and :272 keep the running total and never fold the 37 tap into it;
    // that tap is subtracted on the OUTPUT only, so jumlah_q stays the 38 wide sum and the
    // even index correction does not accumulate. Splitting the two is what makes the parity
    // exact: folding drop_a into jumlah_q makes the sum fall by one term every sample.
    wire [W_ACC-1:0] acc_w   = jumlah_q + nilai_u - drop_b;
    wire [W_ACC-1:0] sel_w   = acc_w - drop_a;
    wire             over_w  = (sel_w > WIN_MAX);
    wire [W_WIN-1:0] win_w   = over_w ? {W_WIN{1'b1}} : sel_w[W_WIN-1:0];

    always @(posedge clk_i) begin
        if (!rst_ni) begin
            for (k = 0; k <= LINE_WORDS-1; k = k + 1) line_q[k] <= {W_SQ{1'b0}};
            jumlah_q     <= {W_ACC{1'b0}};
            m_tdata      <= {W_WIN{1'b0}};
            m_tvalid     <= 1'b0;
            m_overflow   <= 1'b0;
            m_tlast      <= 1'b0;
            m_tuser      <= {W_TUSER{1'b0}};
            m_sample_idx <= {W_IDX{1'b0}};
            d_valid      <= 1'b0;
            d_win        <= {W_WIN{1'b0}};
        end else begin
            m_tvalid <= s_tvalid;
            d_valid  <= s_tvalid;
            if (s_tvalid) begin
                // the line advances once per ACCEPTED word only: that is what keeps the
                // warm-up identical to the model, where reads return zero before arrival
                line_q[0] <= s_tdata;
                for (k = 1; k <= LINE_WORDS-1; k = k + 1) line_q[k] <= line_q[k-1];
                jumlah_q     <= acc_w;
                m_tdata      <= win_w;
                // sticky: only an accepted word may set it
                m_overflow   <= m_overflow | over_w;
                m_tlast      <= s_tlast;
                m_tuser      <= s_tuser;
                m_sample_idx <= s_sample_idx;
                d_win        <= win_w;
            end
        end
    end

endmodule

`default_nettype wire
