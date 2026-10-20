// ---------------------------------------------------------------------------
// classifier.sv -- three class triage, both thresholds read from registers, never from
// constants. Contract profile: apex stage (I1).
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). Owns the decision group m_dvalid, m_class, m_conf, m_win_idx and the
// window counter o_window_count.
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 section 2.2 and 5.5):
//   class     2               0 undecided, 1 normal, 2 review (D2), reset value 0
//   W_CONF  = 16              confidence, 0 to CONF_FULL_SCALE 1000, distance to the
//                             binding threshold (D2b), not a standard deviation
//   W_IDX   = 32              decision window index
//   features 17 and 15 bit, two 16 bit comparators
// Saturation points: no saturation. The stage is two comparators and a subtract, the
//   cheapest stage in the whole chain (114 cells against the 1140 of a full window).
//   The two thresholds are 16 bit registers. The operating point P1 is 0.165 which is 33
//   in 1/200 units and 0.63 which is 63 in 1/100 units, and those codes live in the
//   register reset values RATIO_THRESH_RST and ENTROPY_THRESH_RST, never in this file.
//   The entropy threshold compares h/4, so its code in Q1.14 is 10322; the alternative
//   code 2580 encodes 0.63 at 12 fractional bits and would shift the threshold by two
//   bits. This is sent to the owner as a question, not decided here.
// Rounding rule: none, comparisons only. The gate is p = (ratio > t1) & (entropy > t2)
//   with the arm selection applied on top.
// Model lines this file mirrors: rantai.py:848-878, the gate at :872-878, the old
//   thresholds at :754-757, the feature vector at :861.
//
// The arm selection register i_arm_select is 5 bit: b0 ratio, b1 entropy, b2 T-wave rule,
// b3 marked series source, b4 both arms required.
//
// Fixed latency: one cycle per window against 80000000 cycles of window budget.
//
// Fase 1 status: PLACEHOLDER. The body emits class 0 (undecided) with confidence zero and
// counts windows; it performs no comparison, so lint and a smoke simulation pass.
// Ports and widths are frozen.
// House style: wire and reg only (D10), one clock, synchronous active low reset.
// ---------------------------------------------------------------------------
`default_nettype none

module classifier #(
    parameter int unsigned W_CONF     = afib_lite_pkg::W_CONF,
    parameter int unsigned W_F_RATIO  = afib_lite_pkg::W_F_RATIO,
    parameter int unsigned W_F_ENT    = afib_lite_pkg::W_F_ENT,
    parameter int unsigned W_IDX      = afib_lite_pkg::W_IDX,
    parameter int unsigned LAT_CYCLES = 1
) (
    input  wire                     clk_i,
    input  wire                     rst_ni,

    // features in
    input  wire                     f_valid,
    input  wire [W_F_RATIO-1:0]     f_ratio,
    input  wire [W_F_ENT-1:0]       f_ent,
    input  wire [W_IDX-1:0]         f_win_idx,

    // configuration
    input  wire                     i_enable,
    input  wire                     i_clear_counters,
    input  wire [15:0]              i_ratio_thresh,    // 1/200 units, register value
    input  wire [15:0]              i_entropy_thresh,  // 1/100 units, register value
    input  wire [4:0]               i_arm_select,

    // decision group
    output reg                      m_dvalid,
    output reg  [1:0]               m_class,
    output reg  [W_CONF-1:0]        m_conf,
    output reg  [W_IDX-1:0]         m_win_idx,

    // introspection
    output reg  [1:0]               d_class,
    output reg  [W_CONF-1:0]        d_conf,

    // status this stage owns
    output reg  [31:0]              o_window_count
);

    // placeholder gate. The two comparators, the two threshold registers, the arm register
    // and both feature words are read here, so that no port and no configuration register is
    // left unread, which Verilator treats as a failure. The result is exposed on the
    // introspection tap and is NOT a decision: the frozen placeholder class is
    // KELAS_UNDECIDED and no parity claim is made. Fase 9 replaces this with the real gate
    // p = (ratio > t1) & (entropy > t2) plus the arm selection.
    reg [15:0] ratio_thresh_q;
    reg [15:0] entropy_thresh_q;
    reg [4:0]  arm_q;

    wire ratio_raw   = (f_ratio > {1'b0, ratio_thresh_q});
    // the entropy field is 16 bit in the register map while the feature is 15 bit, so bit 15
    // of the field is out of range for the comparison: when it is set, the threshold sits
    // above every reachable feature value and the arm can never fire.
    wire entropy_raw = ~entropy_thresh_q[W_F_ENT] &
                       (f_ent > entropy_thresh_q[W_F_ENT-1:0]);
    wire dbg_pred    = (ratio_raw & arm_q[0]) | (entropy_raw & arm_q[1]) |
                       (arm_q[2] & arm_q[3]) | arm_q[4];

    always @(posedge clk_i) begin
        if (!rst_ni) begin
            ratio_thresh_q   <= afib_lite_pkg::RATIO_THRESH_RST;
            entropy_thresh_q <= afib_lite_pkg::ENTROPY_THRESH_RST;
            arm_q            <= afib_lite_pkg::ARM_SELECT_RST;
            m_dvalid         <= 1'b0;
            m_class          <= afib_lite_pkg::KELAS_UNDECIDED;
            m_conf           <= {W_CONF{1'b0}};
            m_win_idx        <= {W_IDX{1'b0}};
            d_class          <= afib_lite_pkg::KELAS_UNDECIDED;
            d_conf           <= {W_CONF{1'b0}};
            o_window_count   <= 32'd0;
        end else begin
            // configuration registers follow the host, the reset value is the P1 operating point
            ratio_thresh_q   <= i_ratio_thresh;
            entropy_thresh_q <= i_entropy_thresh;
            arm_q            <= i_arm_select;

            // placeholder decision: undecided, zero confidence, fixed latency of one cycle
            m_dvalid   <= f_valid & i_enable;
            m_class    <= afib_lite_pkg::KELAS_UNDECIDED;
            m_conf     <= {W_CONF{1'b0}};
            m_win_idx  <= f_win_idx;
            d_class    <= {1'b0, dbg_pred};   // placeholder predicate, see the note above
            d_conf     <= {W_CONF{1'b0}};

            if (i_clear_counters) begin
                o_window_count <= 32'd0;
            end else if (f_valid & i_enable) begin
                o_window_count <= o_window_count + 32'd1;
            end
        end
    end

endmodule

`default_nettype wire
