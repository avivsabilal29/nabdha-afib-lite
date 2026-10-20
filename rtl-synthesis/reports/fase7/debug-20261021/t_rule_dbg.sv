// ---------------------------------------------------------------------------
// t_rule.sv -- T-wave discrimination rule, the CANONICAL standalone block of plan doc 38
// phase 7. Contract profile: stream stage (I1), with the documented additions listed
// under "Fase 7 additive interface" below.
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). This file is the recommended addition from plan 3.4 ("add one t_rule.sv
// file for the T-wave rule so its testbench has its own file").
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 section 2.2):
//   in   W_DER = 24   Q17.7, the derivative magnitude line this rule scans
//   out  W_TW  = 23   Q16.7, signed, 22 unsigned; measured range [12926, 3995970]
//
// ---------------------------------------------------------------------------
// WHAT THE FROZEN MODEL DOES (model/rantai-afib-lite/rantai.py, sha256 90df6e5b457307d3,
// read, never edited)
//
//   :313-315  gelombang_t_awal holds the slope series, the rule has no other state
//   :330-333  lo = max(pos - SETENGAH_JENDELA, 0); hi = pos + SETENGAH_JENDELA;
//             kem = maks_mutlak(lo, hi), the largest ABSOLUTE value over a CLOSED window
//   :137-148  maks_mutlak returns 0 for an empty window and ignores negative signs
//   :338-339  dalam_pita = aktif and delta is not None and kem_qrs is not None
//                         and (delta << 2) < BATAS_PITA_SAMPEL      (BATAS = 360, :58/:68)
//   :340      ditolak = dalam_pita and (2 * kem < kem_qrs)         exact cross form
//   :648-670  kem is measured for EVERY envelope peak candidate handed to the rule,
//             whether the rule is on or off ("The slope is measured always, because the
//             ratio pools are collected whether the rule is on or off", :325)
//   :59       SETENGAH_JENDELA = 18, so the window holds 2*18+1 = 37 samples
//   :664      delta = pos - i_qrs, in SAMPLES, and None before the first QRS
//
// Cross form discipline: 2*kem < kem_qrs is written exactly as the model writes it
// (rantai.py:340) and never as kem < (kem_qrs >> 1). The forbidden form is a DIFFERENT
// function: over the model's own 4096 x 4096 = 16777216 pair grid the shift form differs
// at 2048 pairs (every pair with kem_qrs odd and 2*kem = kem_qrs - 1), fraction 1/8192,
// measured in model/rantai-afib-lite/uji_00_teorema.py:766-777 and written down in
// model/math-equation-afib/math-equation-explanation/06 - t-wave-discrimination.md:210-227.
// On the recording 04015 the two forms agree at every one of the 112 real in band pairs,
// so the fixture alone cannot tell them apart: the synthetic grid is what closes the gate.
//
// ---------------------------------------------------------------------------
// Fase 7 additive interface (a question to the owner, not a silent contract change)
//
// delta and kem_qrs live in the peak stage, not in this stage's stream, so the frozen
// 43 row port list cannot carry them. Following the precedent of the four additive ports
// Fase 5 added to peak_detect.sv, every added name is APPENDED to the port list and none
// of the frozen names, widths or directions is changed:
//
//   i_peak_valid     one cycle pulse on the ACCEPTED WORD whose s_sample_idx is the
//                    envelope peak candidate the model hands to gelombang_t (:668).
//                    The rule is silent for every other word. i_rule_enable is captured
//                    together with the candidate, so it is read on the pulse word only.
//   i_delta          pos - i_qrs in SAMPLES (rantai.py:664). Not milliseconds.
//   i_delta_valid    0 reproduces the model's delta is None (no QRS recorded yet).
//   i_kem_qrs        the slope of the previous recorded QRS.
//   i_kem_qrs_valid  0 reproduces the model's kem_qrs is None.
//   o_peak_valid     one cycle pulse on the word whose m_sample_idx is the peak the
//                    verdict belongs to. Qualifies o_peak_idx, o_dalam_pita, o_reject.
//   o_peak_idx       the peak sample index that verdict belongs to.
//   o_dalam_pita     the model's dalam_pita.
//   o_overrun        sticky: a peak candidate arrived while the serializer was busy and
//                    was dropped. The block needs PEAK SPACING >= SCAN_CYC = 10 accepted
//                    words; the real recording measures a minimum of 30 (testbench proof).
//
// Frozen outputs, semantics defined by this body:
//   m_tdata/m_tvalid        kem of the reported peak, one cycle pulse per peak (this
//                           stage is an event stage, not a per sample forwarder)
//   m_sample_idx            the peak index (alignment proof for the caller)
//   m_tuser/m_tlast         forwarded from the accepted word that carried the peak
//   m_overflow              sticky: the window slope exceeded the W_TW report width
//                           (2**W_TW - 1) and m_tdata is saturated. The rule itself always
//                           compares the UNSATURATED magnitude, the model has no such rail.
//   o_reject                the model's ditolak, exact cross form
//   d_valid/d_tw            introspection mirror of the verdict and of kem
//
// Latency, in accepted words, measured and asserted by rtl/tb/tb_gelombang_t.sv:
//   PEAK_DEPTH (= HALF_WIN+1 = 19)  until the register line holds the closed 37 word window
//   SCAN_CYC   (= ceil(37/4) = 10)  the serializer, four magnitudes per accepted word
//   LAT_CYCLES (= 1, frozen)        the output register  -> LAT_ACCEPT = 30
// A peak needs HALF_WIN more words after it before its window exists at all, so a peak in
// the last 19 words of a stream gets no verdict and no verdict is invented for it.
//
// Structure: one clock domain, synchronous active low reset, one always block for all
// state, no latch, no vendor primitive, no index taken from a data value (the tap address
// comes from the scan counter, which is control). The 37 word window is scanned serially,
// four magnitudes per accepted word, the shape plan 4.10 recommends ("A, serial scanner of
// 37 values, 11 times cheaper than B"); shape B, the one cycle 37 wide max tree, is the
// candidate the plan rejects as 83 times too deep. Lane arithmetic, step j, lane l:
//   window element i = 4*j + l  sits at tap k = (N_TAP-1) + j - i
// so k = 36 - 3*j - l for j = 0..9, and only i < 37 is a real window element.
//
// House style: wire and reg only (D10), one clock, synchronous active low reset.
// ---------------------------------------------------------------------------
`default_nettype none

module t_rule_dbg #(
    parameter int unsigned W_DER      = afib_lite_pkg::W_DER,
    parameter int unsigned W_TW       = afib_lite_pkg::W_TW,
    parameter int unsigned W_IDX      = afib_lite_pkg::W_IDX,
    parameter int unsigned W_TUSER    = afib_lite_pkg::W_TUSER,
    parameter int unsigned LAT_CYCLES = 1
) (
    input  wire                     clk_i,
    input  wire                     rst_ni,

    // sample stream in
    input  wire [W_DER-1:0]         s_tdata,
    input  wire                     s_tvalid,
    input  wire                     s_tlast,
    input  wire [W_TUSER-1:0]       s_tuser,
    input  wire [W_IDX-1:0]         s_sample_idx,

    // configuration: b2 of i_arm_select enables this rule, carried in by the caller
    input  wire                     i_rule_enable,

    // sample stream out
    output reg  [W_TW-1:0]          m_tdata,
    output reg                      m_tvalid,
    output reg                      m_overflow,
    output reg                      m_tlast,
    output reg  [W_TUSER-1:0]       m_tuser,
    output reg  [W_IDX-1:0]         m_sample_idx,

    // stage-local T-wave rejection flag, see the header
    output reg                      o_reject,

    // introspection
    output reg                      d_valid,
    output reg  [W_TW-1:0]          d_tw,

    // ---- Fase 7 additive interface, see the header ----
    input  wire                     i_peak_valid,
    input  wire [W_IDX-1:0]         i_delta,
    input  wire                     i_delta_valid,
    input  wire [W_DER-1:0]         i_kem_qrs,
    input  wire                     i_kem_qrs_valid,

    output reg                      o_peak_valid,
    output reg  [W_IDX-1:0]         o_peak_idx,
    output reg                      o_dalam_pita,
    output reg                      o_overrun
);

    // =======================================================================
    // Constants. HALF_WIN, PITA_MS_ATAS and the shift by two are the model's own
    // numbers, and the package already carries both of them as Fase 5 additions.
    // =======================================================================
    localparam int unsigned HALF_WIN   = afib_lite_pkg::SETENGAH_JENDELA;      // 18, :59
    localparam int unsigned N_TAP      = 2 * HALF_WIN + 1;                     // 37
    localparam int unsigned PEAK_DEPTH = HALF_WIN + 1;                         // 19
    localparam int unsigned SCAN_LANES = 4;
    localparam int unsigned SCAN_CYC   = (N_TAP + SCAN_LANES - 1) / SCAN_LANES; // 10
    localparam logic [3:0]  SCAN_IDLE  = 4'd0;
    localparam logic [3:0]  SCAN_LAST  = 4'(SCAN_CYC - 1);                     // step j = 9
    localparam int unsigned N_MAG      = W_DER + 1;                            // 25
    localparam int unsigned W_DELTA    = W_IDX + 2;                            // 34
    localparam int unsigned N_CROSS    = N_MAG + 1;                            // 26
    localparam int unsigned W_LANE_A   = 6;
    localparam logic [W_LANE_A-1:0] LANE_TOP = (W_LANE_A)'(N_TAP - 1);         // 36
    localparam logic [W_LANE_A-1:0] LANE_N   = (W_LANE_A)'(N_TAP);             // 37

    // the in band ceiling of rantai.py:58/:68, used exactly as (delta << 2) < 360
    localparam logic [W_DELTA-1:0] PITA_DX = (W_DELTA)'(afib_lite_pkg::PITA_MS_ATAS);
    // the report rail of m_tdata, 2**W_TW - 1
    localparam logic [W_TW-1:0]   KEM_RAIL = {W_TW{1'b1}};

    // documented total latency in accepted words, see the header
    localparam int unsigned LAT_ACCEPT = PEAK_DEPTH + SCAN_CYC + LAT_CYCLES;    // 30

    // payload word carried beside each peak candidate through PEAK_DEPTH accepted words.
    // i_rule_enable is part of it: the model's `aktif` is read at the call (rantai.py:338),
    // so the verdict of a peak must use the switch as it stood on the peak's own word.
    localparam int unsigned PAY_W = 1 + W_IDX + W_IDX + 1 + W_DER + 1 + W_TUSER + 1 + 1;
    localparam int unsigned P_VALID  = 0;
    localparam int unsigned P_IDX    = P_VALID + 1;
    localparam int unsigned P_DELTA  = P_IDX + W_IDX;
    localparam int unsigned P_DVALID = P_DELTA + W_IDX;
    localparam int unsigned P_KEMQ   = P_DVALID + 1;
    localparam int unsigned P_KVAL   = P_KEMQ + W_DER;
    localparam int unsigned P_TUSER  = P_KVAL + 1;
    localparam int unsigned P_TLAST  = P_TUSER + W_TUSER;
    localparam int unsigned P_EN     = P_TLAST + 1;

    // =======================================================================
    // State. One always block owns all of it.
    // =======================================================================
    reg [N_TAP*W_DER-1:0]      tap_q;      // tap[0] newest, tap[N_TAP-1] oldest
    reg [PEAK_DEPTH*PAY_W-1:0] pl_q;       // payload delay, pl_q[0] newest
    reg [PAY_W-1:0]            hd_q;       // payload of the peak being serialized
    reg [3:0]                  scan_q;     // 0 idle, 1..SCAN_CYC stepping
    reg [N_MAG-1:0]            smag_q;     // running maximum magnitude of the window
    reg                        kem_v_q;    // the serializer finished, verdict next word
    reg                        ovr_q;      // sticky overrun, see the header

    integer li;
    integer tx;
    always @(posedge clk_i) if (!rst_ni) tx <= 0; else if (s_tvalid) tx <= tx + 1;

    // =======================================================================
    // Magnitude of a signed derivative word, the model's maks_mutlak inner step.
    // | -2**(W_DER-1) | = 2**(W_DER-1) needs W_DER bits, so the negation never wraps.
    // =======================================================================
    function automatic [W_DER-1:0] f_abs_der (input [W_DER-1:0] v);
        begin
            f_abs_der = v[W_DER-1] ? ({W_DER{1'b0}} - v) : v;
        end
    endfunction

    // =======================================================================
    // Serializer lanes for the step being evaluated this accepted word.
    // The start word is step j = 0, every stepping word is its own scan_q.
    // =======================================================================
    wire [3:0] j_w = (scan_q == 4'd0) ? 4'd0 : scan_q;

    reg [N_MAG-1:0]          lane_mag_w [0:SCAN_LANES-1];
    reg [W_LANE_A-1:0]       lane_i_w   [0:SCAN_LANES-1];
    reg [W_LANE_A-1:0]       lane_k_w   [0:SCAN_LANES-1];
    reg [N_MAG-1:0]          step_max_w;
    reg [N_MAG-1:0]          smag_next_w;

    always @(*) begin
        step_max_w = {N_MAG{1'b0}};
        for (li = 0; li < SCAN_LANES; li = li + 1) begin
            lane_i_w[li] = {j_w, 2'b00} + (W_LANE_A)'(li);       // 4*j_w + l, W_LANE_A bits
            lane_k_w[li] = LANE_TOP + (W_LANE_A)'(j_w) - lane_i_w[li];
            if (lane_i_w[li] < LANE_N) begin
                lane_mag_w[li] = {1'b0, f_abs_der(tap_q[lane_k_w[li]*W_DER +: W_DER])};
            end else begin
                lane_mag_w[li] = {N_MAG{1'b0}};      // past the last window element
            end
            if (lane_mag_w[li] > step_max_w) step_max_w = lane_mag_w[li];
        end
        smag_next_w = (smag_q > step_max_w) ? smag_q : step_max_w;
    end

    // =======================================================================
    // Accepted word, payload word of the candidate it carries, head of the delay line.
    // =======================================================================
    wire [PAY_W-1:0] head_w = pl_q[(PEAK_DEPTH-1)*PAY_W +: PAY_W];

    wire [PAY_W-1:0] pay_new_w = {(i_rule_enable), (s_tlast), (s_tuser), (i_kem_qrs_valid),
                                  (i_kem_qrs), (i_delta_valid), (i_delta), (s_sample_idx),
                                  (i_peak_valid)};

    // =======================================================================
    // Verdict of the peak held in hd_q against the slope in smag_q, rantai.py:338-340.
    // =======================================================================
    wire [W_IDX-1:0]   v_idx    = hd_q[P_IDX +: W_IDX];
    wire [W_IDX-1:0]   v_delta  = hd_q[P_DELTA +: W_IDX];
    wire               v_dval   = hd_q[P_DVALID];
    wire [W_DER-1:0]   v_kemq   = hd_q[P_KEMQ +: W_DER];
    wire               v_kval   = hd_q[P_KVAL];
    wire [W_TUSER-1:0] v_tuser  = hd_q[P_TUSER +: W_TUSER];
    wire               v_tlast  = hd_q[P_TLAST];
    wire               v_en     = hd_q[P_EN];

    wire [W_DELTA-1:0] v_delta4 = {v_delta, 2'b00};                     // delta << 2, exact
    wire               v_pita   = v_en & v_dval & v_kval &
                                  (v_delta4 < PITA_DX);                 // :338-339
    wire [N_CROSS-1:0] v_kem2   = {smag_q, 1'b0};                       // 2*kem, exact
    wire [N_CROSS-1:0] v_kemq_x = {{(N_CROSS-W_DER){1'b0}}, v_kemq};
    wire               v_rej    = v_pita & (v_kem2 < v_kemq_x);         // :340 cross form
    wire               v_rail   = (smag_q > {{(N_MAG-W_TW){1'b0}}, KEM_RAIL});

    // the verdict fires on the accepted word after the serializer finished, so every
    // report is aligned to the stream and its latency is countable in accepted words
    wire fire_w = s_tvalid & (scan_q == SCAN_IDLE) & kem_v_q;

    // =======================================================================
    // The single state block.
    // =======================================================================
    always @(posedge clk_i) begin
        if (!rst_ni) begin
            tap_q        <= {N_TAP*W_DER{1'b0}};
            pl_q         <= {PEAK_DEPTH*PAY_W{1'b0}};
            hd_q         <= {PAY_W{1'b0}};
            scan_q       <= 4'd0;
            smag_q       <= {N_MAG{1'b0}};
            kem_v_q      <= 1'b0;
            ovr_q        <= 1'b0;
            m_tdata      <= {W_TW{1'b0}};
            m_tvalid     <= 1'b0;
            m_overflow   <= 1'b0;
            m_tlast      <= 1'b0;
            m_tuser      <= {W_TUSER{1'b0}};
            m_sample_idx <= {W_IDX{1'b0}};
            o_reject     <= 1'b0;
            d_valid      <= 1'b0;
            d_tw         <= {W_TW{1'b0}};
            o_peak_valid <= 1'b0;
            o_peak_idx   <= {W_IDX{1'b0}};
            o_dalam_pita <= 1'b0;
            o_overrun    <= 1'b0;
        end else begin
            // the two event pulses are one clock wide, see tb_gelombang_t
            m_tvalid     <= 1'b0;
            o_peak_valid <= 1'b0;
            d_valid      <= 1'b0;
            o_overrun    <= ovr_q;      // sticky, see the header

            if (s_tvalid) begin
                // the register line holds the last N_TAP accepted derivative words
                tap_q <= {tap_q[(N_TAP-1)*W_DER-1:0], s_tdata};
                // the payload of this word travels HALF_WIN+1 words to the serializer
                pl_q  <= {pl_q[(PEAK_DEPTH-1)*PAY_W-1:0], pay_new_w};

                if (scan_q != SCAN_IDLE) begin
                    // stepping: fold in this step's four magnitudes (step j = scan_q)
                    smag_q <= smag_next_w;
                    if (head_w[P_VALID]) ovr_q <= 1'b1;      // busy, candidate dropped
                    if (scan_q == SCAN_LAST) begin
                        scan_q  <= SCAN_IDLE;
                        kem_v_q <= 1'b1;
                    end else begin
                        scan_q <= scan_q + 4'd1;
                    end
                end else if (kem_v_q) begin
                    // verdict word: register the report, then take a new candidate if one
                    // is at the head of the line
                    smag_q <= smag_next_w;
                    if (head_w[P_VALID]) begin
                        hd_q   <= head_w;
                        scan_q <= 4'd1;                       // step j = 0 of the new peak
                    end
                    kem_v_q <= head_w[P_VALID];
                end else if (head_w[P_VALID]) begin
                    $display("DBG start word=%0d idx=%0d smag=%0d", tx, head_w[P_IDX +: W_IDX], smag_next_w);
                    hd_q   <= head_w;
                    smag_q <= smag_next_w;                    // step j = 0 of the new peak
                    scan_q <= 4'd1;
                end
            end

            // report the finished peak. kem = smag_q, the model's maks_mutlak value.
            if (fire_w) begin
                $display("DBG fire  word=%0d idx=%0d kem=%0d pita=%0d rej=%0d", tx, v_idx, smag_q, v_pita, v_rej);
                m_tdata      <= v_rail ? KEM_RAIL : smag_q[W_TW-1:0];
                m_tvalid     <= 1'b1;
                m_tlast      <= v_tlast;
                m_tuser      <= v_tuser;
                m_sample_idx <= v_idx;
                o_reject     <= v_rej;
                o_dalam_pita <= v_pita;
                o_peak_valid <= 1'b1;
                o_peak_idx   <= v_idx;
                d_valid      <= 1'b1;
                d_tw         <= v_rail ? KEM_RAIL : smag_q[W_TW-1:0];
                m_overflow   <= m_overflow | v_rail;
            end
        end
    end

    // LAT_ACCEPT is the only reader of the frozen LAT_CYCLES parameter; the testbench
    // asserts the measured latency against the same number (30 accepted words).

endmodule

`default_nettype wire
