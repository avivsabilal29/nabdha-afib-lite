// ---------------------------------------------------------------------------
// derivative.sv -- five-point derivative, kernel [2, 1, 0, -1, -2], then divide by 8
// truncating toward zero. Contract profile: stream stage (I1).
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). Introspection port: d_der.
//
// Equation (plan 4.4, model rantai.py:227):
//   s = 2*x[i] + x[i-1] - x[i-3] - 2*x[i-4]        zero initial state, five taps
//   y = s // 8 if s >= 0 else -((-s) // 8)         rantai.py:228, truncate toward zero
//   x[i-2] is deliberately unused: the kernel is [2, 1, 0, -1, -2].
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 section 2.2):
//   in   W_HP  = 26   Q22.4, measured range [-16974032, 19286208]
//   sum  W_ACC = 28   signed, six times the high pass bound: 6 * 19286208 = 115717248
//                     needs 28 bit signed and NO package constant carries that value,
//                     so it is written as an expression of W_HP and explained here
//   out  W_DER  = 24  Q17.7, measured range [-4792318, 3831762]
//   y    W_DER_WORST = 25 signed, the operator bound +-14464656 = (6/8) * 19286208.
//                     The measured range needs only 24 bit, the bound needs 25, which is
//                     why W_DER_WORST exists and why this stage can raise m_overflow.
// Saturation points: the sum has no hard bound either, because the high pass it consumes
//   has none (pole at z = -1). |x| <= 19286208 gives |s| <= 115717248 and |y| <= 14464656,
//   both inside W_ACC and W_DER_WORST, so the internal arithmetic never wraps. m_tdata is
//   W_DER wide and saturates at +-8388607 like bandpass.sv does, and m_overflow is raised
//   on that sample. Record 04015 never reaches it: 0 saturated words in 450000.
// Rounding rule: RND_TRUNC_ZERO, the ONLY node in the chain that truncates toward zero
//   (rantai.py:228, form s // 8 if s >= 0 else -((-s) // 8)). It keeps the kernel
//   antisymmetric; a floor shift would bias negative samples by up to 7/8 of a count.
//   Implemented in the plan's own recommended form (plan 4.4 candidate B):
//     y = (s + (s < 0 ? 7 : 0)) >> 3      with 7 = SHIFT_DER - 1 and >> 3 = the
//   arithmetic shift by log2(SHIFT_DER). The identity floor((s + 7) / 8) == ceil(s / 8)
//   == trunc(s / 8) for s < 0 is exact, so the one-sided bias replaces the sign split and
//   needs one increment instead of a negation.
//   Measured trap: the raw sum is always divisible by 8 on the frozen fixture, 0 of
//   450000 samples leave a remainder, so the fixture cannot test this rule and a
//   synthetic pulse vector with raw sums [0, 2, 1, 0, -1, -2] is required. That vector
//   lives in rtl/tb/tb_derivative.sv, and 6 of its 45 words differ under a floor shift.
// Model lines this file mirrors: rantai.py:221-233, form at :227, rounding at :228.
//
// Fase 4a body, architecture from plan 4.4 candidate B and the plan 4 preamble: ONE 9 bit
//   ripple adder, reused for every pass and every 9 bit slice. Four passes per sample,
//   each covering four slices (9 + 9 + 9 + 1 = 28 bit):
//     pass 0 = 2*x[i] + x[i-1]      the 2x terms are free left shifts, exact in W_OP
//     pass 1 = result - x[i-3]
//     pass 2 = result - 2*x[i-4]
//     pass 3 = result + (s < 0 ? 7 : 0)   the truncation bias, then y = acc >> 3 is wiring
//   One sample is in flight at a time, so the sideband (tlast, tuser, sample_idx) is held
//   in a single register set instead of a 17 deep pipeline.
//
// Fixed latency: 1 accept cycle + 4 passes * 4 slices = 17 cycles against 400000 cycles
//   available per sample at 250 Hz, no tready inside (decision D1).
//   DISAGREEMENT, reported not hidden: plan 4.4 states 4 cycles per sample for this stage
//   (three additions plus the truncation cycle). That count assumes an unsliced 24 bit
//   adder, which the same plan rejects in its own candidate A row at 42.2128 ns against
//   7.8194 ns available. With the 9 bit slice rule of the plan 4 preamble the honest count
//   is 17, and LAT_CYCLES carries it.
// Register inventory: 5 x 26 bit delay line = 130, 28 bit accumulator = 28, slice carry 1,
//   sticky overflow 1, 25 bit result, 24 bit output register, 8 + 1 + 32 bit sideband,
//   2 + 2 bit schedule counters.
// House style: wire and reg only (D10), one clock, synchronous active low reset.
// ---------------------------------------------------------------------------
`default_nettype none

module derivative #(
    parameter int unsigned W_HP       = afib_lite_pkg::W_HP,
    parameter int unsigned W_DER      = afib_lite_pkg::W_DER,
    parameter int unsigned W_IDX      = afib_lite_pkg::W_IDX,
    parameter int unsigned W_TUSER    = afib_lite_pkg::W_TUSER,
    parameter int unsigned LAT_CYCLES = 17
) (
    input  wire                     clk_i,
    input  wire                     rst_ni,

    input  wire [W_HP-1:0]          s_tdata,
    input  wire                     s_tvalid,
    input  wire                     s_tlast,
    input  wire [W_TUSER-1:0]       s_tuser,
    input  wire [W_IDX-1:0]         s_sample_idx,

    output reg  [W_DER-1:0]         m_tdata,
    output reg                      m_tvalid,
    output reg                      m_overflow,
    output reg                      m_tlast,
    output reg  [W_TUSER-1:0]       m_tuser,
    output reg  [W_IDX-1:0]         m_sample_idx,

    output reg                      d_valid,
    output reg  [W_DER-1:0]         d_der
);

    // ---- widths, every one derived from afib_lite_pkg ---------------------
    localparam int unsigned W_ACC   = afib_lite_pkg::W_HP + 2;   // 28 bit signed, 6 * max hp
    localparam int unsigned W_Y     = afib_lite_pkg::W_DER_WORST; // 25 bit signed, +-14464656
    localparam int unsigned SLICE_W = 9;                          // ripple carried per cycle
    localparam int unsigned N_SLICE = 4;                          // 9 + 9 + 9 + 1 = 28 bit
    localparam int unsigned W_OP    = SLICE_W * N_SLICE;          // 36 bit operand window
    localparam int unsigned N_PASS  = 4;                          // 3 additions + truncation
    localparam int unsigned DER_LOG2_DIV = $clog2(afib_lite_pkg::SHIFT_DER); // 3, divide by 8
    localparam int unsigned X_WORDS = 5;                          // x[i] plus x[i-1] .. x[i-4]
    // the bias 7 = SHIFT_DER - 1 of the plan 4.4 rounding form. 32 is the width of a package
    // int constant and both steps are explicit, so neither Verilator (WIDTHEXPAND) nor Icarus
    // (indefinite concatenation operand) has anything to complain about.
    localparam [31:0]       TRUNC_BIAS32 = afib_lite_pkg::SHIFT_DER - 1;
    localparam [W_OP-1:0]   TRUNC_BIAS   = {{(W_OP-32){1'b0}}, TRUNC_BIAS32};
    localparam [1:0] ST_IDLE = 2'd0;
    localparam [1:0] ST_ACC  = 2'd1;
    localparam [1:0] P_ADD0  = 2'd0;   // 2*x[i] + x[i-1]
    localparam [1:0] P_SUB3  = 2'd1;   // - x[i-3]
    localparam [1:0] P_SUB4  = 2'd2;   // - 2*x[i-4]
    localparam [1:0] P_BIAS  = 2'd3;   // + truncation bias

    // ---- state ------------------------------------------------------------
    reg  [W_HP-1:0]     x_hold_q;                       // x[i]
    reg  [W_HP-1:0]     x_hist_q [0:X_WORDS-2];         // [0] = x[i-1] .. [3] = x[i-4]
    reg  [SLICE_W-1:0]  acc_lo_q;                       // accumulator bits 8:0
    reg  [SLICE_W-1:0]  acc_mid_q;                      // accumulator bits 17:9
    reg  [SLICE_W-1:0]  acc_hi_q;                       // accumulator bits 26:18
    reg                 acc_top_q;                      // accumulator bit 27, also its sign
    reg                 acc_cy_q;                       // slice carry
    reg                 ovf_q;                          // sticky m_overflow source
    reg  [1:0]          st_q;
    reg  [1:0]          pass_q;
    reg  [1:0]          slice_q;
    reg                 last_q;
    reg  [W_TUSER-1:0]  tuser_q;
    reg  [W_IDX-1:0]    idx_q;

    integer k;

    // ---- operand window, pure bit vectors, two's complement ---------------
    wire [W_HP-1:0]   x1 = x_hist_q[0];                 // x[i-1]
    wire [W_HP-1:0]   x3 = x_hist_q[2];                 // x[i-3]
    wire [W_HP-1:0]   x4 = x_hist_q[3];                 // x[i-4]

    wire [W_OP-1:0]   acc_ext = {{(W_OP-W_ACC){acc_top_q}}, acc_top_q,
                                 acc_hi_q, acc_mid_q, acc_lo_q};
    wire [W_OP-1:0]   x1_ext  = {{(W_OP-W_HP){x1[W_HP-1]}}, x1};
    wire [W_OP-1:0]   x3_ext  = {{(W_OP-W_HP){x3[W_HP-1]}}, x3};
    // the two doubled terms are taken one bit narrower, because 2*|x| <= 2**26 still fits the
    // window and the left shift itself supplies the top bit, exactly as bandpass.sv does
    wire [W_OP-2:0]   x0_ext  = {{(W_OP-1-W_HP){x_hold_q[W_HP-1]}}, x_hold_q};
    wire [W_OP-2:0]   x4_ext  = {{(W_OP-1-W_HP){x4[W_HP-1]}}, x4};
    wire [W_OP-1:0]   x0_dbl  = {x0_ext, 1'b0};         // 2*x[i], exact in W_OP
    wire [W_OP-1:0]   x4_dbl  = {x4_ext, 1'b0};         // 2*x[i-4], exact in W_OP
    wire [W_OP-1:0]   bias_w  = acc_top_q ? TRUNC_BIAS : {W_OP{1'b0}};

    wire [W_OP-1:0]   der_add_a = (pass_q == P_ADD0) ? x0_dbl : acc_ext;
    wire [W_OP-1:0]   der_b_raw = (pass_q == P_ADD0) ? x1_ext :
                                  (pass_q == P_SUB3) ? x3_ext :
                                  (pass_q == P_SUB4) ? x4_dbl : bias_w;
    wire              der_sub   = (pass_q == P_SUB3) || (pass_q == P_SUB4);
    // subtraction is the ones complement plus the carry into slice 0: a - b == a + ~b + 1,
    // which is the form bandpass.sv uses and the only subtraction the 9 bit adder needs
    wire [W_OP-1:0]   der_add_b = der_sub ? ~der_b_raw : der_b_raw;
    wire              der_cin   = (slice_q == 2'd0) ? der_sub : acc_cy_q;

    // slice window: 9 bits of the operand pair, four windows cover 36 bit
    reg  [SLICE_W-1:0] sl_a;
    reg  [SLICE_W-1:0] sl_b;
    always @(*) begin
        case (slice_q)
            2'd0:    begin sl_a = der_add_a[SLICE_W-1:0];           sl_b = der_add_b[SLICE_W-1:0];           end
            2'd1:    begin sl_a = der_add_a[2*SLICE_W-1:SLICE_W];   sl_b = der_add_b[2*SLICE_W-1:SLICE_W];   end
            2'd2:    begin sl_a = der_add_a[3*SLICE_W-1:2*SLICE_W]; sl_b = der_add_b[3*SLICE_W-1:2*SLICE_W]; end
            default: begin sl_a = der_add_a[4*SLICE_W-1:3*SLICE_W]; sl_b = der_add_b[4*SLICE_W-1:3*SLICE_W]; end
        endcase
    end

    // one 9 bit adder, one carry register, reused for every pass and slice
    wire [SLICE_W:0]  sl_sum = {1'b0, sl_a} + {1'b0, sl_b} + {{SLICE_W{1'b0}}, der_cin};

    // the accumulator after the slice in flight, with the divide by 8 as wiring:
    // y_full = acc_new >> DER_LOG2_DIV = top bit, then the two 9 bit chunks, then acc bits 8:3
    wire [W_Y-1:0]    y_full  = {sl_sum[0], acc_hi_q, acc_mid_q,
                                 acc_lo_q[SLICE_W-1:DER_LOG2_DIV]};
    wire              y_ovf   = (y_full[W_Y-1:W_DER] != {(W_Y-W_DER){y_full[W_DER-1]}});
    wire [W_DER-1:0]  y_sat   = y_ovf ? {y_full[W_Y-1], {(W_DER-1){~y_full[W_Y-1]}}}
                                      : y_full[W_DER-1:0];

    wire              last_slice = (slice_q == 2'd3);
    wire              pad_last   = (pass_q == P_BIAS) && last_slice;

    always @(posedge clk_i) begin
        if (!rst_ni) begin
            x_hold_q     <= {W_HP{1'b0}};
            for (k = 0; k <= X_WORDS-2; k = k + 1) x_hist_q[k] <= {W_HP{1'b0}};
            acc_lo_q     <= {SLICE_W{1'b0}};
            acc_mid_q    <= {SLICE_W{1'b0}};
            acc_hi_q     <= {SLICE_W{1'b0}};
            acc_top_q    <= 1'b0;
            acc_cy_q     <= 1'b0;
            ovf_q        <= 1'b0;
            st_q         <= ST_IDLE;
            pass_q       <= P_ADD0;
            slice_q      <= 2'd0;
            last_q       <= 1'b0;
            tuser_q      <= {W_TUSER{1'b0}};
            idx_q        <= {W_IDX{1'b0}};
            m_tdata      <= {W_DER{1'b0}};
            m_tvalid     <= 1'b0;
            m_overflow   <= 1'b0;
            m_tlast      <= 1'b0;
            m_tuser      <= {W_TUSER{1'b0}};
            m_sample_idx <= {W_IDX{1'b0}};
            d_valid      <= 1'b0;
            d_der        <= {W_DER{1'b0}};
        end else begin
            m_tvalid <= 1'b0;
            d_valid  <= 1'b0;
            case (st_q)
                ST_IDLE: begin
                    if (s_tvalid) begin
                        // the input history advances once per accepted sample, so the
                        // first four outputs stay in warm-up exactly as the model does
                        x_hold_q    <= s_tdata;
                        x_hist_q[0] <= x_hold_q;
                        for (k = 1; k <= X_WORDS-2; k = k + 1) x_hist_q[k] <= x_hist_q[k-1];
                        last_q      <= s_tlast;
                        tuser_q     <= s_tuser;
                        idx_q       <= s_sample_idx;
                        acc_cy_q    <= 1'b0;
                        pass_q      <= P_ADD0;
                        slice_q     <= 2'd0;
                        st_q        <= ST_ACC;
                    end
                end
                default: begin
                    case (slice_q)
                        2'd0:    acc_lo_q  <= sl_sum[SLICE_W-1:0];
                        2'd1:    acc_mid_q <= sl_sum[SLICE_W-1:0];
                        2'd2:    acc_hi_q  <= sl_sum[SLICE_W-1:0];
                        default: acc_top_q <= sl_sum[0];
                    endcase
                    acc_cy_q <= sl_sum[SLICE_W];
                    if (last_slice) begin
                        slice_q <= 2'd0;
                        pass_q  <= pass_q + 2'd1;
                    end else begin
                        slice_q <= slice_q + 2'd1;
                    end
                    if (pad_last) begin
                        // s + bias is in the accumulator and y = s >> 3 is wiring, so the
                        // result register closes the schedule in this same cycle
                        m_tdata      <= y_sat;
                        m_tvalid     <= 1'b1;
                        m_tlast      <= last_q;
                        m_tuser      <= tuser_q;
                        m_sample_idx <= idx_q;
                        m_overflow   <= ovf_q | y_ovf;
                        d_valid      <= 1'b1;
                        d_der        <= y_sat;
                        ovf_q        <= ovf_q | y_ovf;
                        st_q         <= ST_IDLE;
                    end
                    // a word presented while this stage is busy would be lost: with no
                    // tready inside, m_overflow is the only handshake substitute (plan 3.3)
                    if (s_tvalid) begin
                        ovf_q <= 1'b1;
                    end
                end
            endcase
        end
    end

endmodule

`default_nettype wire
