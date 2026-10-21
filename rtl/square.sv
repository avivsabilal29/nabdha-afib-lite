// ---------------------------------------------------------------------------
// square.sv -- right shift by 8 first, then square. Order matters: shifting after the
// square would change both the width and the value. Contract profile: stream stage (I1).
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). Introspection port: d_sq.
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 section 2.2):
//   in   W_DER  = 24   Q17.7
//   out  W_SQ   = 30   signed, 29 unsigned; measured range [0, 350438400]
// Saturation points: the measured square maximum is 350438400 (the exact square of the
//   largest measured shifted magnitude 18720). The design bound is 13316659200, which is
//   38 times that value, and the operator bound is SQ_LIMIT 56503 whose square is
//   3192589009. SQ_LIMIT is ceil(14464656 / 2**8) where 14464656 is the derivative
//   saturation bound: after the shift of SHIFT_DER 8 the largest magnitude is 56503.
// Rounding rule: RND_FLOOR, arithmetic right shift by SHIFT_DER 8 (rantai.py:244). The
//   shift is a FLOOR and not a truncation toward zero: the two differ on 222478 of
//   450000 samples when swapped, which is the largest parity trap in the chain.
//   Note d = int(nilai) >> 8 in the model is np.floor, never a truncation.
// Model lines this file mirrors: rantai.py:240-250, shift at :244, square at :245.
//
// Fixed latency: one cycle with a six-stage pipelined array multiplier, or 64 cycles for
// the shift-and-add fallback. Fase 4 chose the array, so LAT_CYCLES is 1: the single
// visible register stage is the multiplier output register, and the six array stages of
// plan 4.5 sit inside the shared multiplier unit that features.sv also calls.
//
// Fase 4 body, architecture from plan 4.5 (array multiplier, one cycle per sample):
//   d    = s_tdata >>> SHIFT_DER, arithmetic, floor, exactly rantai.py:244. The floor
//          shifted word fits W_DER - SHIFT_DER = 16 bits signed, so the body reads the low
//          W_DV bits of that shift directly and the value never leaves [-32768, 32767].
//   ku   = d * d, exact, computed at W_SQ_WORST = 32 bit, which holds SQ_LIMIT**2.
//   Saturate: ku > SQ_SAT (1073741823, the package constant) gives m_tdata = SQ_SAT and
//          raises m_overflow. SQ_SAT is the largest value W_SQ can carry unsigned, so the
//          output word is never truncated silently. On the frozen fixture the largest
//          square is 350438400, so the saturation never fires and m_overflow stays low.
//   d_sq and m_tdata are the same value in the same cycle, because the d_sq column is the
//          square node itself and the stage has no second pipeline register.
// House style: wire and reg only (D10), one clock, synchronous active low reset.
// ---------------------------------------------------------------------------
`default_nettype none

module square #(
    parameter int unsigned W_DER      = afib_lite_pkg::W_DER,
    parameter int unsigned W_SQ       = afib_lite_pkg::W_SQ,
    parameter int unsigned W_IDX      = afib_lite_pkg::W_IDX,
    parameter int unsigned W_TUSER    = afib_lite_pkg::W_TUSER,
    parameter int unsigned LAT_CYCLES = 1
) (
    input  wire                     clk_i,
    input  wire                     rst_ni,

    // stream in
    // The squaring stage reads only the bits at and above SHIFT_DER: the floor shift of
    // rantai.py:244 drops the SHIFT_DER sub count bits below it, on purpose, because that
    // shift is the price of keeping the square at 30 bit instead of 45. The suppression
    // sits on the port because that is where the tool reports the unused slice.
    /* verilator lint_off UNUSEDSIGNAL */
    input  wire [W_DER-1:0]         s_tdata,
    /* verilator lint_on UNUSEDSIGNAL */
    input  wire                     s_tvalid,
    input  wire                     s_tlast,
    input  wire [W_TUSER-1:0]       s_tuser,
    input  wire [W_IDX-1:0]         s_sample_idx,

    output reg  [W_SQ-1:0]          m_tdata,
    output reg                      m_tvalid,
    output reg                      m_overflow,
    output reg                      m_tlast,
    output reg  [W_TUSER-1:0]       m_tuser,
    output reg  [W_IDX-1:0]         m_sample_idx,

    output reg                      d_valid,
    output reg  [W_SQ-1:0]          d_sq
);

    // ---- widths, every one taken from the package, none typed here --------
    localparam int unsigned SHIFT_C  = afib_lite_pkg::SHIFT_DER;        // 8
    localparam int unsigned W_DV     = W_DER - SHIFT_C;                 // 16, the shifted word
    localparam int unsigned W_PROD   = afib_lite_pkg::W_SQ_WORST;       // 32, holds SQ_LIMIT**2
    localparam logic [W_PROD-1:0] SQ_SAT_U  = afib_lite_pkg::SQ_SAT;    // 2**30-1
    localparam logic [W_SQ-1:0]   SQ_SAT_SQ = afib_lite_pkg::SQ_SAT[W_SQ-1:0];

    // ---- datapath, one combinational multiply feeding one register stage --
    // d = s_tdata >>> SHIFT_DER, arithmetic floor (rantai.py:244). The low W_DV bits of
    // that shift ARE s_tdata[W_DER-1:SHIFT_C]: the sign fill lands above W_DV, and the
    // shifted value fits W_DV bits signed because |s_tdata| <= 2**23, so this select is
    // lossless and equals the floor shift bit for bit, negative inputs included. The
    // signedness that makes the multiply a two's complement multiply comes from d_w.
    wire signed [W_DV-1:0]   d_w    = s_tdata[W_DER-1:SHIFT_C];
    wire signed [W_PROD-1:0] prod_w = d_w * d_w;                        // rantai.py:245
    wire        [W_PROD-1:0] prod_u = prod_w;                           // the square is never negative
    wire                     sat_w  = (prod_u > SQ_SAT_U);
    wire        [W_SQ-1:0]   sq_w   = sat_w ? SQ_SAT_SQ : prod_u[W_SQ-1:0];

    always @(posedge clk_i) begin
        if (!rst_ni) begin
            m_tdata      <= {W_SQ{1'b0}};
            m_tvalid     <= 1'b0;
            m_overflow   <= 1'b0;
            m_tlast      <= 1'b0;
            m_tuser      <= {W_TUSER{1'b0}};
            m_sample_idx <= {W_IDX{1'b0}};
            d_valid      <= 1'b0;
            d_sq         <= {W_SQ{1'b0}};
        end else begin
            m_tdata      <= sq_w;
            m_tvalid     <= s_tvalid;
            // sticky: only an accepted word may set it, so a stale s_tdata cannot raise it
            m_overflow   <= m_overflow | (s_tvalid & sat_w);
            m_tlast      <= s_tlast;
            m_tuser      <= s_tuser;
            m_sample_idx <= s_sample_idx;
            d_valid      <= s_tvalid;
            d_sq         <= sq_w;
        end
    end

endmodule

`default_nettype wire
