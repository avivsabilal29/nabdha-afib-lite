// ---------------------------------------------------------------------------
// bandpass.sv -- linear filter pair: low-pass then high-pass, one file, two nodes.
// Contract profile: stream stage (I1).
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). Introspection carries one port per node: d_lp and d_hp.
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 section 2.2):
//   in   W_IN  = 16   Q12.4
//   lp   W_LP  = 22   Q18.4, measured range [-1061200, 1179072]
//   hp   W_HP  = 26   Q22.4, measured range [-16974032, 19286208], widest filter node
// Saturation points: the low-pass has a hard bound of +-1179072, which is the DC gain
//   of 36 times the input rail 32752 (rantai.py:170). The high-pass has NO hard bound:
//   the pole at z = -1 makes the worst case grow with record length, so 26 bits is one
//   observation and not a limit, and the stage must raise m_overflow into STATUS b8.
// Rounding rule: none. Every gain in both recursions is a power of two and the
//   recurrences are pure sums, so no rounding happens at all (doc 36 2.2).
// Model lines this file mirrors: rantai.py:173-189 (form at :182) for low-pass,
//   rantai.py:197-211 (form at :204) for high-pass.
//
// Fase 3 body, architecture from plan 4.2 and 4.3 candidate B in both stages.
//
// Low-pass: y[i] = 2y[i-1] - y[i-2] + x[i] - 2x[i-6] + x[i-12], zero initial state.
//   Five terms, four additions, ONE 9 bit slice adder reused twelve times: pass 0 is
//   x[i-12] + 2y[i-1], pass 1 is -y[i-2], pass 2 is +x[i], pass 3 is -2x[i-6], and each
//   pass covers three slices (bits 8:0, 17:9, 18:26) so one sample costs 12 cycles.
//   The accumulator register is 23 bit because 2y[i-1] alone reaches 2358144, which
//   needs 23 bit signed; the registered output is 22 bit. The intermediate is never
//   clamped. Worst partial magnitudes: 2y1 2358144, 2y1-y2 1201088, 2y1-y2+x 1233840,
//   all of which fit the 23 bit accumulator exactly, so the slice truncation is exact.
// High-pass: y[i] = 32x[i-16] - (y[i-1] + x[i] - x[i-32]), zero initial state, input is
//   the low-pass output. Three passes, ONE 27 bit adder reused three times, one cycle
//   each: pass 0 is y[i-1] + x[i], pass 1 is -x[i-32], pass 2 is 32x[i-16] - accumulator.
//   The accumulator register is 27 bit because 32x[i-16] alone reaches 37730304, which
//   needs 27 bit signed; the registered output is 26 bit. m_overflow rises only when the
//   final value falls outside the 26 bit signed range, and then the output saturates.
//
// Fixed latency: LAT_CYCLES, no tready inside (decision D1). The schedule is one accept
// cycle, then 12 low-pass cycles, then 3 high-pass cycles, then the registered output,
// so the measured latency from an accepted s_tvalid to the m_tvalid pulse is 16 cycles
// against 400000 cycles available per sample at 250 Hz. One sample is in flight at a
// time, so the sideband (tlast, tuser, sample_idx) is held in a single register set
// instead of a 16 deep pipeline.
//
// Register inventory, filter state only: 13 x 16 bit input delay line = 208,
//   3 slice registers 9 + 9 + 5 = 23 for the low-pass accumulator plus 1 carry,
//   32 x 22 bit low-pass output delay line = 704 shared with the high-pass history,
//   22 bit low-pass output register, 26 bit high-pass feedback and output register,
//   27 bit high-pass accumulator.
// House style: wire and reg only (D10), one clock, synchronous active low reset.
// ---------------------------------------------------------------------------
`default_nettype none

module bandpass #(
    parameter int unsigned W_IN       = afib_lite_pkg::W_IN,
    parameter int unsigned W_LP       = afib_lite_pkg::W_LP,
    parameter int unsigned W_HP       = afib_lite_pkg::W_HP,
    parameter int unsigned W_IDX      = afib_lite_pkg::W_IDX,
    parameter int unsigned W_TUSER    = afib_lite_pkg::W_TUSER,
    parameter int unsigned LAT_CYCLES = 16
) (
    input  wire                     clk_i,
    input  wire                     rst_ni,

    input  wire [W_IN-1:0]          s_tdata,
    input  wire                     s_tvalid,
    input  wire                     s_tlast,
    input  wire [W_TUSER-1:0]       s_tuser,
    input  wire [W_IDX-1:0]         s_sample_idx,

    output reg  [W_HP-1:0]          m_tdata,
    output reg                      m_tvalid,
    output reg                      m_overflow,
    output reg                      m_tlast,
    output reg  [W_TUSER-1:0]       m_tuser,
    output reg  [W_IDX-1:0]         m_sample_idx,

    output reg                      d_valid,
    output reg  [W_LP-1:0]          d_lp,
    output reg  [W_HP-1:0]          d_hp
);

    // ---- widths, every one measured, see the header note ------------------
    localparam int unsigned W_ACC_LP = afib_lite_pkg::W_LP_ACC;  // |2*y1| = 2358144 needs 23 bit signed
    localparam int unsigned W_ACC_HP = afib_lite_pkg::W_HP_ACC;  // |32*x16| = 37730304 needs 27 bit signed
    localparam int unsigned SLICE_W  = 9;    // ripple carried per cycle
    localparam int unsigned LP_SLICES = 3;   // 9 + 9 + 5 covers the 23 bit accumulator
    localparam int unsigned W_OP     = SLICE_W * LP_SLICES;   // 27 bit operand window
    localparam int unsigned X_WORDS  = 13;   // x[i] held plus x[i-1] .. x[i-12]
    localparam int unsigned LP_WORDS = 32;   // lp[i-1] .. lp[i-32]
    localparam int unsigned HP_X16   = 15;   // index of x[i-16] in the lp history
    localparam int unsigned HP_X32   = 31;   // index of x[i-32] in the lp history
    localparam [1:0] ST_IDLE = 2'd0;
    localparam [1:0] ST_LP   = 2'd1;
    localparam [1:0] ST_HP   = 2'd2;

    // ---- state ------------------------------------------------------------
    reg  [W_IN-1:0]     x_hold_q;                        // x[i]
    reg  [W_IN-1:0]     x_hist_q [0:X_WORDS-2];          // x_hist_q[0] = x[i-1]
    reg  [W_LP-1:0]     lp_hist_q [0:LP_WORDS-1];        // lp_hist_q[k] = lp[i-1-k]
    reg  [W_LP-1:0]     lp_out_q;                        // lp[i], low-pass output node
    reg  [SLICE_W-1:0]  acc_lo_q;                        // low-pass accumulator bits 8:0
    reg  [SLICE_W-1:0]  acc_mid_q;                       // low-pass accumulator bits 17:9
    reg  [4:0]          acc_hi_q;                        // low-pass accumulator bits 22:18
    reg                 acc_cy_q;                        // slice carry
    reg  [W_HP-1:0]     hp_y_q;                          // y[i-1], also the stage output
    reg  [W_ACC_HP-1:0] acc_hp_q;                        // high-pass accumulator, 27 bit
    reg                 ovf_q;                           // sticky high-pass overflow
    reg  [1:0]          st_q;
    reg  [1:0]          lp_pass_q;
    reg  [1:0]          lp_slice_q;
    reg  [1:0]          hp_pass_q;
    reg                 last_q;
    reg  [W_TUSER-1:0]  tuser_q;
    reg  [W_IDX-1:0]    idx_q;

    integer k;

    // ---- low-pass operand window, pure bit vectors, two's complement ------
    wire [W_OP-1:0] acc_lp_ext = {{(W_OP-W_ACC_LP){acc_hi_q[4]}}, acc_hi_q, acc_mid_q, acc_lo_q};
    wire [W_OP-1:0] x_ext      = {{(W_OP-W_IN){x_hold_q[W_IN-1]}}, x_hold_q};
    wire [W_OP-2:0] x6_ext     = {{(W_OP-1-W_IN){x_hist_q[5][W_IN-1]}}, x_hist_q[5]};
    wire [W_OP-1:0] x12_ext    = {{(W_OP-W_IN){x_hist_q[X_WORDS-2][W_IN-1]}}, x_hist_q[X_WORDS-2]};
    wire [W_OP-2:0] y1_ext     = {{(W_OP-1-W_LP){lp_hist_q[0][W_LP-1]}}, lp_hist_q[0]};
    wire [W_OP-1:0] y2_ext     = {{(W_OP-W_LP){lp_hist_q[1][W_LP-1]}}, lp_hist_q[1]};
    wire [W_OP-1:0] y1_dbl     = {y1_ext, 1'b0};         // 2*y[i-1], exact
    wire [W_OP-1:0] x6_dbl     = {x6_ext, 1'b0};         // 2*x[i-6], exact

    // pass 0 = x[i-12] + 2y[i-1], 1 = -y[i-2], 2 = +x[i], 3 = -2x[i-6]
    wire [W_OP-1:0] lp_add_a = (lp_pass_q == 2'd0) ? x12_ext : acc_lp_ext;
    wire [W_OP-1:0] lp_add_b = (lp_pass_q == 2'd0) ? y1_dbl  :
                               (lp_pass_q == 2'd1) ? ~y2_ext :
                               (lp_pass_q == 2'd2) ? x_ext   : ~x6_dbl;
    wire            lp_sub   = (lp_pass_q == 2'd1) || (lp_pass_q == 2'd3);
    wire            lp_cin   = (lp_slice_q == 2'd0) ? lp_sub : acc_cy_q;

    reg  [SLICE_W-1:0] sl_a;
    reg  [SLICE_W-1:0] sl_b;
    always @(*) begin
        case (lp_slice_q)
            2'd0:    begin sl_a = lp_add_a[SLICE_W-1:0];           sl_b = lp_add_b[SLICE_W-1:0];           end
            2'd1:    begin sl_a = lp_add_a[2*SLICE_W-1:SLICE_W];   sl_b = lp_add_b[2*SLICE_W-1:SLICE_W];   end
            default: begin sl_a = lp_add_a[3*SLICE_W-1:2*SLICE_W]; sl_b = lp_add_b[3*SLICE_W-1:2*SLICE_W]; end
        endcase
    end

    // one 9 bit adder, one carry register, reused for every pass and slice
    wire [SLICE_W:0] sl_sum = {1'b0, sl_a} + {1'b0, sl_b} + {{SLICE_W{1'b0}}, lp_cin};
    // accumulator bit 21:0 after the top slice: bits 18..21 come from the slice sum
    wire [W_LP-1:0]  acc_lp_next = {sl_sum[3:0], acc_mid_q, acc_lo_q};

    // ---- high-pass operands, one 27 bit adder reused three times ----------
    wire [W_ACC_HP-1:0] hp_sext_y   = {{(W_ACC_HP-W_HP){hp_y_q[W_HP-1]}}, hp_y_q};
    wire [W_ACC_HP-1:0] hp_sext_x   = {{(W_ACC_HP-W_LP){lp_out_q[W_LP-1]}}, lp_out_q};
    wire [W_ACC_HP-1:0] hp_sext_x32 = {{(W_ACC_HP-W_LP){lp_hist_q[HP_X32][W_LP-1]}}, lp_hist_q[HP_X32]};
    wire [W_ACC_HP-1:0] hp_x16_5    = {lp_hist_q[HP_X16], 5'b00000};   // 32*x[i-16], exact
    wire [W_ACC_HP-1:0] hp_add_a = (hp_pass_q == 2'd0) ? hp_sext_y : (hp_pass_q == 2'd1) ? acc_hp_q : hp_x16_5;
    wire [W_ACC_HP-1:0] hp_add_b = (hp_pass_q == 2'd0) ? hp_sext_x : (hp_pass_q == 2'd1) ? ~hp_sext_x32 : ~acc_hp_q;
    wire [W_ACC_HP-1:0] hp_add_c = (hp_pass_q == 2'd0) ? {W_ACC_HP{1'b0}} : {{(W_ACC_HP-1){1'b0}}, 1'b1};
    wire [W_ACC_HP-1:0] hp_sum    = hp_add_a + hp_add_b + hp_add_c;
    wire                hp_ovf    = hp_sum[W_ACC_HP-1] ^ hp_sum[W_HP-1];
    wire [W_HP-1:0]     hp_sat    = hp_ovf ? {hp_sum[W_ACC_HP-1], {(W_HP-1){~hp_sum[W_ACC_HP-1]}}}
                                           : hp_sum[W_HP-1:0];

    wire lp_last = (lp_pass_q == 2'd3) && (lp_slice_q == 2'd2);

    always @(posedge clk_i) begin
        if (!rst_ni) begin
            x_hold_q  <= {W_IN{1'b0}};
            for (k = 0; k <= X_WORDS-2; k = k + 1) x_hist_q[k] <= {W_IN{1'b0}};
            for (k = 0; k <= LP_WORDS-1; k = k + 1) lp_hist_q[k] <= {W_LP{1'b0}};
            lp_out_q  <= {W_LP{1'b0}};
            acc_lo_q  <= {SLICE_W{1'b0}};
            acc_mid_q <= {SLICE_W{1'b0}};
            acc_hi_q  <= 5'd0;
            acc_cy_q  <= 1'b0;
            hp_y_q    <= {W_HP{1'b0}};
            acc_hp_q  <= {W_ACC_HP{1'b0}};
            ovf_q     <= 1'b0;
            st_q      <= ST_IDLE;
            lp_pass_q <= 2'd0;
            lp_slice_q<= 2'd0;
            hp_pass_q <= 2'd0;
            last_q    <= 1'b0;
            tuser_q   <= {W_TUSER{1'b0}};
            idx_q     <= {W_IDX{1'b0}};
            m_tdata      <= {W_HP{1'b0}};
            m_tvalid     <= 1'b0;
            m_overflow   <= 1'b0;
            m_tlast      <= 1'b0;
            m_tuser      <= {W_TUSER{1'b0}};
            m_sample_idx <= {W_IDX{1'b0}};
            d_valid      <= 1'b0;
            d_lp         <= {W_LP{1'b0}};
            d_hp         <= {W_HP{1'b0}};
        end else begin
            m_tvalid <= 1'b0;
            d_valid  <= 1'b0;
            case (st_q)
                ST_IDLE: begin
                    if (s_tvalid) begin
                        // the input history advances once per accepted sample, so the
                        // first 13 outputs stay in warm-up exactly as the model does
                        x_hold_q    <= s_tdata;
                        x_hist_q[0] <= x_hold_q;
                        for (k = 1; k <= X_WORDS-2; k = k + 1) x_hist_q[k] <= x_hist_q[k-1];
                        last_q    <= s_tlast;
                        tuser_q   <= s_tuser;
                        idx_q     <= s_sample_idx;
                        lp_pass_q <= 2'd0;
                        lp_slice_q<= 2'd0;
                        hp_pass_q <= 2'd0;
                        st_q      <= ST_LP;
                    end
                end
                ST_LP: begin
                    case (lp_slice_q)
                        2'd0:    begin acc_lo_q  <= sl_sum[SLICE_W-1:0]; acc_cy_q <= sl_sum[SLICE_W]; end
                        2'd1:    begin acc_mid_q <= sl_sum[SLICE_W-1:0]; acc_cy_q <= sl_sum[SLICE_W]; end
                        default: begin acc_hi_q  <= sl_sum[4:0];         acc_cy_q <= sl_sum[SLICE_W]; end
                    endcase
                    if (lp_last) begin
                        lp_out_q <= acc_lp_next;
                        st_q     <= ST_HP;
                    end
                    if (lp_slice_q == 2'd2) begin
                        lp_slice_q <= 2'd0;
                        lp_pass_q  <= lp_pass_q + 2'd1;
                    end else begin
                        lp_slice_q <= lp_slice_q + 2'd1;
                    end
                end
                default: begin
                    if (hp_pass_q != 2'd2) begin
                        acc_hp_q  <= hp_sum;
                        hp_pass_q <= hp_pass_q + 2'd1;
                    end else begin
                        hp_y_q <= hp_sat;
                        ovf_q  <= ovf_q | hp_ovf;
                        for (k = 1; k <= LP_WORDS-1; k = k + 1) lp_hist_q[k] <= lp_hist_q[k-1];
                        lp_hist_q[0] <= lp_out_q;
                        m_tdata      <= hp_sat;
                        m_tvalid     <= 1'b1;
                        m_overflow   <= ovf_q | hp_ovf;
                        m_tlast      <= last_q;
                        m_tuser      <= tuser_q;
                        m_sample_idx <= idx_q;
                        d_valid      <= 1'b1;
                        d_lp         <= lp_out_q;
                        d_hp         <= hp_sat;
                        st_q         <= ST_IDLE;
                    end
                end
            endcase
        end
    end

endmodule

`default_nettype wire
