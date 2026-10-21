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
// Saturation points: no saturation on either comparator. The confidence is the only
//   saturating quantity in this file and it saturates at CONF_FULL_SCALE, its own declared
//   range. The stage is two comparators and a subtract, the cheapest stage in the chain.
//   The two thresholds are 16 bit registers. The operating point P1 is 0.165 which is 33
//   in 1/200 units and 0.63 which is 63 in 1/100 units, and those codes live in the
//   register reset values RATIO_THRESH_RST and ENTROPY_THRESH_RST, never in this file.
//   The entropy threshold compares h/4, so its code in Q1.14 is 10322; the alternative
//   code 2580 encodes 0.63 at 12 fractional bits and would shift the threshold by two
//   bits. Plan section 13.3 item 5 and D7 lock the parity point at 0.165 and 0.63, which at
//   the feature formats of this file (ratio Q1.16 in W_F_RATIO = 17 bits, entropy/4 Q1.14
//   in W_F_ENT = 15 bits) are the register codes 10813 and 10322 that the Fase 5 manifest
//   calls ratio_register_q16 and entropy_register_q14.
// Rounding rule: none on the comparators, comparisons only. Both feature words arrive here
//   already quantised, so this stage rounds nothing. The gate is
//   p = (ratio > t1) & (entropy > t2) with the arm selection applied on top.
// Model lines this file mirrors: rantai.py:848-878, the gate at :872-878 (nilai_gerbang,
//   `p = (arr[:, 1] > t1) & (arr[:, 3] > t2)`), the old thresholds at :754-757, the feature
//   vector at :861.
//
// The arm selection register i_arm_select is 5 bit: b0 ratio, b1 entropy, b2 T-wave rule,
// b3 marked series source, b4 both arms required. Bits b2 and b3 do not enter this file:
//   b2 enables the Fase 7 T wave rule and b3 selects the interval series the features are
//   built from, and both are upstream of this stage (Fase 6 and 7, plan 3.4). The two arms
//   this stage owns combine as an AND over the arms that are enrolled, and b4 forces both of
//   them enrolled:
//       ratio required = b0 | b4      entropy required = b1 | b4
//   so the reset value 5'h0F, the model's own default arm set (rantai.py:799-801), gives
//   exactly the P1 gate above: fired = ratio_above & entropy_above. No arm enrolled never
//   fires. This reading of the four bits is this file's reading of the signal table row
//   i_arm_select; the plan names the arms and gives no combination table.
// Fixed latency: one cycle per window against 80000000 cycles of window budget.
//
// Confidence, D2b. The plan fixes the meaning (distance to the binding threshold) and the
//   scale (0 to 1000) and nothing further, so the remaining details are stated here instead
//   of hiding in the arithmetic. The binding arm is the one whose gap between the feature
//   word and its own threshold is the smaller on a common Q1.16 scale, which takes the
//   entropy gap shifted up two bits because its word is Q1.14. The confidence is that gap
//   shifted right by CONF_SHIFT and clamped to CONF_FULL_SCALE: exact agreement reads 0, the
//   value grows with the gap and stops at full scale. No golden column for m_conf exists
//   anywhere in the frozen data, so the testbench checks its properties (range, zero exactly
//   at the threshold, monotone, saturating) and never its values.
//
// Fase 9 status: IMPLEMENTED. Evidence in rtl-synthesis/reports/LAPORAN-FASE9.md: 0 of 588
// decisions differ on the raw arm and 0 of 602 on the marked arm, both thresholds read from
// the two registers, lint clean. Ports, widths and parameters are frozen from Fase 1.
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

    // D2b confidence shift: one confidence unit is worth 2**CONF_SHIFT Q1.16 steps, so full
    // scale is reached at a gap of 16000 in Q1.16. A design choice of this file, see above.
    localparam int unsigned CONF_SHIFT = 4;
    // the confidence full scale of the package at the gap width, zero extended explicitly so
    // no implicit width change happens anywhere in this file
    localparam [W_F_RATIO:0] CONF_FS_X = {{(W_F_RATIO+1-W_CONF){1'b0}},
                                          afib_lite_pkg::CONF_FULL_SCALE[W_CONF-1:0]};

    // the configuration registers, reloaded from the host side every cycle. Bits [3:2] of
    // arm_q (b2 T wave rule, b3 marked series source) are deliberately not consumed in this
    // file: both select behaviour upstream of this stage, in Fase 7 and in the window source
    // mux, and this stage must not let them move a decision. The pragma keeps the read of the
    // full configuration word honest instead of deleting the bits.
    /* verilator lint_off UNUSEDSIGNAL */
    reg [15:0] ratio_thresh_q;
    reg [15:0] entropy_thresh_q;
    reg [4:0]  arm_q;
    /* verilator lint_on UNUSEDSIGNAL */

    // ------------------------------------------------------------------ arm decode
    wire arm_ratio_req = arm_q[0] | arm_q[4];   // b0 ratio, or b4 forcing both arms
    wire arm_ent_req   = arm_q[1] | arm_q[4];   // b1 entropy, or b4 forcing both arms
    wire arm_any       = arm_ratio_req | arm_ent_req;

    // ------------------------------------------------------------------ comparator 1, ratio
    // The feature word is Q1.16 in W_F_RATIO = 17 bits and the register field is 16 bits, so
    // the field is zero extended and the comparison is exact over the whole reachable range.
    wire [W_F_RATIO-1:0] ratio_thresh_ext = {{(W_F_RATIO-16){1'b0}}, ratio_thresh_q};
    wire                 ratio_above      = (f_ratio > ratio_thresh_ext);

    // ------------------------------------------------------------------ comparator 2, entropy
    // The feature word is Q1.14 in W_F_ENT = 15 bits while the register field is 16 bits, so
    // bit 15 of the field is out of range for the comparison: when it is set the threshold
    // sits above every reachable feature value and the arm can never fire.
    wire ent_in_range = 1'b1;   // MUTANT B
    wire ent_above    = ent_in_range & (f_ent > entropy_thresh_q[W_F_ENT-1:0]);

    // ------------------------------------------------------------------ triage gate
    // AND over the arms that are enrolled. At the reset arm set this is the P1 gate
    // ratio_above & ent_above, the frozen model's own predicate.
    wire arm_satisfied = (~arm_ratio_req | ratio_above) & (~arm_ent_req | ent_above);
    wire fire          = arm_any & arm_satisfied;

    // ------------------------------------------------------------------ class, D2
    // 0 undecided, 1 normal, 2 review. A disabled stage decides nothing, and no arm enrolled
    // is no evidence, so both read undecided rather than normal: the same reason the reset
    // value is undecided, a class that was never decided must never read normal.
    wire [1:0] kelas_now = !i_enable ? afib_lite_pkg::KELAS_UNDECIDED
                         : !arm_any  ? afib_lite_pkg::KELAS_UNDECIDED
                         : fire      ? afib_lite_pkg::KELAS_REVIEW
                                     : afib_lite_pkg::KELAS_NORMAL;

    // ------------------------------------------------------------------ confidence, D2b
    // gap to the binding threshold on the common Q1.16 scale, then shifted and clamped
    wire [W_F_RATIO-1:0] ratio_gap   = (f_ratio >= ratio_thresh_ext)
                                     ? (f_ratio - ratio_thresh_ext)
                                     : (ratio_thresh_ext - f_ratio);
    wire [W_F_ENT-1:0]   ent_thr_lo  = entropy_thresh_q[W_F_ENT-1:0];
    wire [W_F_ENT-1:0]   ent_gap     = (f_ent >= ent_thr_lo) ? (f_ent - ent_thr_lo)
                                                             : (ent_thr_lo - f_ent);
    wire [W_F_RATIO:0]   ent_gap_q16 = {{1'b0, ent_gap}, 2'b00};   // Q1.14 -> Q1.16, two up
    wire [W_F_RATIO:0]   ratio_gap_x = {1'b0, ratio_gap};
    wire [W_F_RATIO:0]   gap_min     = (ratio_gap_x < ent_gap_q16) ? ratio_gap_x : ent_gap_q16;
    wire [W_F_RATIO:0]   conf_scaled = gap_min >> CONF_SHIFT;
    wire [W_CONF-1:0]    conf_now    = (conf_scaled > CONF_FS_X) ? CONF_FS_X[W_CONF-1:0]
                                                                 : conf_scaled[W_CONF-1:0];

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
            // configuration registers follow the host, the reset value is the P1 point
            ratio_thresh_q   <= i_ratio_thresh;
            entropy_thresh_q <= i_entropy_thresh;
            arm_q            <= i_arm_select;

            // the decision register, fixed latency of one cycle. The introspection tap is loaded
            // from the same source on the same edge, so d_class and d_conf are copies of the
            // decision word and never a cycle behind it
            m_dvalid  <= f_valid & i_enable;
            m_win_idx <= f_win_idx;
            if (!i_enable) begin
                m_class <= afib_lite_pkg::KELAS_UNDECIDED;   // disabled: decide nothing
                m_conf  <= {W_CONF{1'b0}};
                d_class <= afib_lite_pkg::KELAS_UNDECIDED;
                d_conf  <= {W_CONF{1'b0}};
            end else if (f_valid) begin
                m_class <= kelas_now;
                m_conf  <= conf_now;
                d_class <= kelas_now;
                d_conf  <= conf_now;
            end

            if (i_clear_counters) begin
                o_window_count <= 32'd0;
            end else if (f_valid & i_enable) begin
                o_window_count <= o_window_count + 32'd1;
            end
        end
    end

endmodule

`default_nettype wire
