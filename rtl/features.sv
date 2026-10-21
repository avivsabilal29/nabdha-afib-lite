// ---------------------------------------------------------------------------
// features.sv -- window feature layer over 32 intervals with a stride of 4 beats.
// Contract profile: apex stage (I1).
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). Ports, parameters and widths are the Fase 1 freeze and are unchanged.
// This body is Fase 8 of plan doc 38, section 12 ("Fase 8, lapisan fitur jendela 32
// interval") and section 4.11.
//
// WIDTHS, from afib_lite_pkg (plan 3.4, cross checked against doc 36 5.4 and 5.5):
//   d_rmssd  W_F_RMSSD = 18   Q10.8
//   d_ratio  W_F_RATIO = 17   Q1.16, pinned by the owner on 20 October 2026
//   d_ent    W_F_ENT   = 15   Q1.14, entropy divided by four
//   d_meanq  W_F_MEANQ = 27   Q19.8, the sum of 31 squared differences divided by 31
//   index    W_IDX     = 32
// House style: wire and reg only (D10), one clock, synchronous active low reset, no
// initial block, ASCII only.
//
// ============================ WHAT THIS BODY COMPUTES =============================
// Model lines (model/rantai-afib-lite/rantai.py, sha256 90df6e5b457307d3...):
//   :809  rr = (qrs[k+1] - qrs[k]) * 4 ms, exact, carried in on s_rr_ms
//   :816  windows of 32 intervals, stride 4
//   :818  one class per window                        -> OUTSIDE this module (no port)
//   :821  200 <= min(rr) and max(rr) <= 3000          -> S_GATE, exact comparators
//   :851  d[k] = rr[k+1] - rr[k], 31 values, exact
//   :852  rmssd = sqrt(mean(d*d))
//   :853  pnn50 = mean(|d| > 50), 31 comparators
//   :854  s = sort(rr), core = s[8:-8], 16 values
//   :856  edges = linspace(core.min, core.max, 17), last edge +1e-9
//   :858  cnt = histogram(core, edges), 16 bins, total always 16
//   :859  p = cnt[cnt>0] / 16
//   :860  h = -sum(p*log2(p)), ent4 = h/4
//   :861  ratio = rmssd / rr.mean()
//
// The mark input selects the interval series, exactly rantai.seri_berpenanda :764-783:
// with i_arm_select[3] high an interval enters the series only when its mark is
// RR_MARK_KEEP or RR_MARK_SPLIT; with it low every interval enters (SUMBER_MENTAH). The
// stride then runs over that selected series, which is why the two arms of record 04015
// have 638 and 641 stride positions and 602 and 588 golden rows.
//
// NODE FORMS. Plan section 12 steps 2..9 in order, each pinned to an exact integer form
// and measured against the golden columns of rtlplan2/fase5/04015.windows.csv in
// rtl-synthesis/reports/LAPORAN-FASE8.md, table "gerbang":
//   step 2  d and d*d    exact, 31 differences and 31 squares per window into a 29 bit
//                        accumulator. The range gate bounds |d| by max - min <= 2800, so
//                        31 * 2800**2 = 243040000 is the accumulator bound.
//   step 3  /31          plan constant verbatim, C31 = round(2**29/31) = 17318417 and
//                        q0 = (sum_d2 * C31) >> 29. C31 is rounded up by half a step of
//                        2**29, so q0 is either floor(sum_d2/31) or one more; the low six
//                        bits of the remainder sum_d2 - 31*q0 are therefore tested for the
//                        negative case (a true remainder in -31..-1) and the pair is folded
//                        back by one. The eight fraction bits come from the exact table
//                        FRAC[rem0] = round half to even of rem0*256/31; 31 is odd, so no
//                        tie is reachable. Measured: 0 of 602 mean31 codes differ from the
//                        golden column. A bare floor of the node instead ((x*C31) >> 21,
//                        the Fase 5 exporter's first form) differs on 213 of 602 windows
//                        at exactly 1 LSB.
//   step 4  root         29 step restoring digit root over rad = (sum_d2 * 31) << 24, so
//                        R = floor(sqrt(sum_d2/31) * 256 * 496) = floor(rmssd * 256 * 496)
//                        exactly, and the code is round half to even of R/496, ties to even
//                        (plan F6b). Measured: 0 of 602 rmssd codes differ, worst value
//                        error 0 LSB. Rooting the rounded Q19.8 mean instead (the plan's
//                        literal chain, which the Fase 5 exporter implements) differs on 13
//                        windows at exactly 1 LSB: inside the 1 LSB gate, outside the
//                        0.5 LSB line of the plan block.
//   step 5  pNN50        31 exact comparators on the unsigned magnitude, then the Q1.8 code
//                        table PNN[c] = round half to even of c*256/31. 0 of 602 differ.
//   step 6  sort+core    odd even transposition network of 32 phases over 32 values, all
//                        comparators combinational with elaboration time indices, core =
//                        s[8:23], the same s[8:-8] as rantai.py:854.
//   step 7  histogram    exact cross product, never a float linspace: with x = v -
//                        core_min and span = core_max - core_min the bin is the largest
//                        k <= 15 with 16*x >= k*span, so the last edge is inclusive and
//                        x = span lands in bin 15. The bins are counted as A[k] - A[k+1]
//                        with A[k] = #{v : 16*x >= k*span}, A[0] = 16 and A[16] = 0, which
//                        is exact by construction and already covers span = 0 (every value
//                        then has 16*x = 0, every A[k] = 16 and bin 15 takes all 16). On
//                        record 04015 span is never 0, so that branch is reasoned, not
//                        observed. 0 of 602 x 16 bins differ.
//   step 8  entropy      the 16 entry log2 table and the closed form of rantai.py:859-861
//                        folded into one 17 entry table of term(c) = c*(4 - log2 c)/64
//                        indexed by the bin count c, then one round half to even on the
//                        final shift. The two forms are algebraically identical and the
//                        folded form needs one lookup and one add per bin instead of a
//                        lookup and a multiplier. The log2 argument carries 24 fraction bits
//                        and the term 48, which puts the node error under 6e-5 LSB; the
//                        closest half boundary on record 04015 is 0.0024 LSB away, a 40x
//                        margin: 0 of 602 entropy codes differ. With the plan's 16 bit log2
//                        table (the first form built here) 49 of 602 differ at 1 LSB even
//                        though no golden row sits within 1e-9 of a boundary, because the
//                        16 bit table's own error reaches 0.03 LSB per term.
//   step 9  ratio        17 quotient bits of rmssd/mean_rr. Numerator R << 9, divisor
//                        31*sum_rr, one shared restoring divider that truncates toward zero,
//                        then one final round half to even stage, because the feature column
//                        rounds and does not truncate (F6b and the F4 row): truncating alone
//                        differs from the golden code on 293 of 602 windows and reaches
//                        1.0 LSB, the rounded form gives 0 differences. The saturation at
//                        2**17-1 is reachable once rmssd exceeds 2*mean_rr, which the range
//                        gate allows; on 04015 the largest code is 40070.
//   step 10 lint then simulation, in that order, and the phase report carries the raw output.
//
//   d_valid        one cycle per emitted window, 136 cycles per window against 80000000
//                  cycles of window budget at the fastest beat, 0.00017 percent. The
//                  LAT_CYCLES placeholder of the frozen parameter list is not read, exactly
//                  as the Fase 6 report records for rr_series.sv.
//   m_ev_val       the pNN50 count of the window (rantai.py:853), the "interval count" the
//                  signal table row m_ev_val allows, plus 26 zero bits.
//   m_ev_idx       the s_window_idx of the newest interval of the window, which equals the
//                  golden sample_end of that window.
//
// ============================ WHAT THIS BODY DOES NOT DO ==========================
// 1. The class filter of rantai.py:818 needs the rhythm label, which is an annotation
//    property with no port here. It runs outside this module, so this layer emits one
//    window per stride position that passes the range gate. On record 04015 the marked arm
//    emits 638 windows of which 602 are golden and the raw arm 624 of which 588 are
//    golden; every dropped row is a class drop and 0 are range drops, so the golden map
//    files of the vector directory carry the row bridges.
// 2. Two constants this layer needs are absent from afib_lite_pkg.sv and the package is
//    frozen this session: RR_MIN_MS 200 (rantai.py:821) and PNN50_MS 50 (rantai.py:853).
//    The upper edge already exists as RR_LONG_MS 3000. They are module localparams with the
//    model line cited, and moving them into the package is an open item of the phase.
// 3. The plan's resource sharing is not implemented: the sorting chain is not shared with
//    the RR median direction of rr_series.sv (the plan warns that without that sharing the
//    1.08 mm2 core target is out of reach), and the root, the two divisions and the
//    histogram are separate. Function items, not area items; reported, not claimed.
// 4. Every array in this file is indexed by an elaboration time genvar or by a loop over a
//    packed vector, never by a run time index into an unpacked array. Icarus executes a
//    dynamic index into an unpacked array as a priority chain over every slot, about 30x the
//    simulated time of the packed form here, which put the full two arm record run out of
//    budget.
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
    /* verilator lint_off UNUSEDSIGNAL */
    // bit 3 selects the marked series source. Bits 0, 1, 2 and 4 of the same word are the
    // ratio arm, the entropy arm, the T wave rule and the both-arms bit; classifier.sv and
    // afib_lite_top.sv consume them, and this stage must not let them move a window, so the
    // read is of the full word and only bit 3 acts here.
    input  wire [4:0]               i_arm_select,
    /* verilator lint_on UNUSEDSIGNAL */
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

    // ===========================================================================
    // 1. Local widths and constants. Every value below is derived from the package or from
    //    a model line; no statement in this file carries a bare magic number.
    // ===========================================================================
    localparam int unsigned W_WVAL   = afib_lite_pkg::W_RR_MS;             // 16, ms
    localparam int unsigned W_WIN    = afib_lite_pkg::WINDOW_BEATS_RST;    // 32 intervals
    localparam int unsigned W_D      = 13;      // signed d, |d| <= 2800 by the range gate
    localparam int unsigned W_D2     = 2 * W_D; // d*d, 2800**2 = 7840000
    localparam int unsigned W_SUM2   = 29;      // sum of 31 squares, 243040000
    localparam int unsigned W_MEANQ  = W_F_MEANQ;
    localparam int unsigned W_MEANX  = W_SUM2 + 9;  // 38, the unrounded mean square code
    localparam int unsigned W_MULP   = 58;      // 58 bit product of the step 3 constant
    localparam int unsigned W_Q0     = 29;      // floor(sum_d2 / 31)
    localparam int unsigned W_RAD    = 58;      // (sum_d2 * 31) << 24
    localparam int unsigned W_ROOT   = 29;      // floor(rmssd * 256 * 496)
    localparam int unsigned W_RREM   = 33;      // root remainder register
    localparam int unsigned W_RVAL   = W_RREM - 2;  // 31, the value width of that remainder
    localparam int unsigned W_DEN    = 26;      // 31 * sum_rr, 2976000 worst case
    localparam int unsigned W_NUM    = 40;      // divider numerator shift register
    localparam int unsigned W_QUO    = 40;      // divider quotient accumulator
    localparam int unsigned W_DVEC   = 31 * W_D;// the 31 d values, 403 bit
    localparam int unsigned W_RRSUM  = 16;      // sum of 32 intervals, 96000 worst case
    localparam int unsigned W_ESUM   = 52;      // sum of the 16 entropy terms
    localparam int unsigned W_BIN    = 6;       // one histogram bin, 0..16
    localparam int unsigned W_CNT50  = 6;       // 0..31
    localparam int unsigned W_FRACT  = W_D - 4; // 9, fraction table entry
    localparam int unsigned W_TERM   = 48;      // one entropy term
    localparam int unsigned W_PNNT   = W_FRACT;  // Q1.8 pNN50 code
    localparam int unsigned CNT_CORE = 16;      // the 16 middle values
    localparam int unsigned CNT_EDGE = 15;      // the 15 interior bin edges
    localparam int unsigned CNT_DIFF = 32;      // one cycle per interval slot
    localparam int unsigned ROOT_STEP = (W_RAD + 1) / 2;  // 29, two radicand bits per step
    localparam int unsigned DIV_STEP1 = W_ROOT;  // 29, R is 29 bits
    localparam int unsigned DIV_STEP2 = 38;      // R << 9 is 38 bits
    localparam int unsigned SA_ALIGN  = W_NUM - W_ROOT;   // 11, left align R
    localparam int unsigned CORE_FIRST = W_WIN / 4;              // 8, drop the low eight
    localparam int unsigned CORE_LAST  = W_WIN - W_WIN/4 - 1;    // 23, drop the top eight
    localparam int unsigned ENT_SHIFT  = 34;     // table sum >> 34 is the Q1.14 code
    localparam int unsigned LOG2_Q     = 24;     // log2 table fraction bits, derivation only
    localparam int unsigned DIV_RMSSD  = 31 * 16;                // 496, the root scale
    localparam int unsigned DIV_RMSSD_H = DIV_RMSSD / 2;         // 248
    localparam [W_DEN-1:0]  DEN1       = DIV_RMSSD[W_DEN-1:0];
    localparam [W_DEN-1:0]  DEN1_HALF  = DIV_RMSSD_H[W_DEN-1:0];
    localparam [W_Q0-1:0]   Q_ONE      = {{(W_Q0-1){1'b0}}, 1'b1};
    localparam [W_WVAL:0]   PNN50_X    = {1'b0, 16'd50};         // rantai.py:853
    // Field spacing of the d vector. The offset must be computed in a context wide enough
    // for the largest one, 30 * 13 = 390, so it is 9 bits: at 5 bits the product wrapped
    // (3 * 13 = 39 -> 7) and the d fields landed on top of each other, which tb_fitur sees
    // as a dvec_q that does not match the golden d column even though sum_d2 is right.
    localparam [8:0]        W_D9       = W_D[8:0];
    localparam [W_ESUM-1:0] ENT_HALF   = {{(W_ESUM-1){1'b0}}, 1'b1} << (ENT_SHIFT - 1);
    localparam [W_WVAL-1:0] RR_MIN_MS  = 16'd200;                // rantai.py:821
    localparam [W_WVAL-1:0] RR_MAX_MS  = afib_lite_pkg::RR_LONG_MS;  // 3000, rantai.py:821
    localparam [2:0]        ARM_MARKED_BIT = 3'd3;               // table row i_arm_select
    localparam [1:0]        MARK_KEEP  = afib_lite_pkg::RR_MARK_KEEP;
    localparam [1:0]        MARK_SPLIT = afib_lite_pkg::RR_MARK_SPLIT;
    localparam [7:0]        STEP_REQ   = afib_lite_pkg::WINDOW_STEP_FIELD;   // 4, D5
    localparam [7:0]        BEATS_REQ  = afib_lite_pkg::WINDOW_BEATS_FIELD;  // 32, D5

    // Entropy term table. term(c) = round half to even of c*(4 - log2 c)/64 in units of
    // 2**-48 of ent4, for the bin count c = 0..16; entry c sits at bits c*48 +: 48, so the
    // concatenation below lists entry 16 first. The plan's 16 entry log2 table, Q24 with
    // index 1..16, is 0, 16777216, 26591258, 33554432, 38955489, 43368474, 47099600,
    // 50331648, 53182516, 55732705, 58039632, 60145690, 62083076, 63876816, 65546747,
    // 67108864, and every entry below is that table folded through the closed form.
    localparam [17*W_TERM-1:0] TERM_FLAT = {
        48'd0,             // c = 16, log2 16 = 4 exactly
        48'd6142493982720, // c = 15
        48'd11861667872768,// c = 14
        48'd17127242203136,// c = 13
        48'd21904251420672,// c = 12
        48'd26151892287488,// c = 11
        48'd29821918248960,// c = 10
        48'd32856377131008,// c = 9
        48'd35184372088832,// c = 8, log2 8 = 3 exactly
        48'd36717159514112,// c = 7
        48'd37340404776960,// c = 6
        48'd36901191680000,// c = 5
        48'd35184372088832,// c = 4, log2 4 = 2 exactly
        48'd31864341921792,// c = 3
        48'd26388279066624,// c = 2, log2 2 = 1 exactly
        48'd17592186044416,// c = 1, log2 1 = 0 exactly
        48'd0 };           // c = 0, an empty bin contributes nothing

    // Division by 31 fraction table, FRAC[r] = round half to even of r*256/31 for r = 0..30
    // (index 31 is carried so the table stride stays 32). 31 is odd, so r*256/31 is never a
    // half integer and the table is the exact rounded quotient. Entry r sits at bits
    // r*9 +: 9, so the list runs from 31 down.
    localparam [32*W_FRACT-1:0] FRAC_FLAT = {
        9'd256, 9'd248, 9'd239, 9'd231, 9'd223, 9'd215, 9'd206, 9'd198,
        9'd190, 9'd182, 9'd173, 9'd165, 9'd157, 9'd149, 9'd140, 9'd132,
        9'd124, 9'd116, 9'd107, 9'd99,  9'd91,  9'd83,  9'd74,  9'd66,
        9'd58,  9'd50,  9'd41,  9'd33,  9'd25,  9'd17,  9'd8,   9'd0 };

    // pNN50 code table, Q1.8, the same rounded quotient as its own node width.
    localparam [32*W_FRACT-1:0] PNN_FLAT = {
        9'd256, 9'd248, 9'd239, 9'd231, 9'd223, 9'd215, 9'd206, 9'd198,
        9'd190, 9'd182, 9'd173, 9'd165, 9'd157, 9'd149, 9'd140, 9'd132,
        9'd124, 9'd116, 9'd107, 9'd99,  9'd91,  9'd83,  9'd74,  9'd66,
        9'd58,  9'd50,  9'd41,  9'd33,  9'd25,  9'd17,  9'd8,   9'd0 };

    localparam [3:0] S_IDLE = 4'd0;
    localparam [3:0] S_PREP = 4'd1;
    localparam [3:0] S_GATE = 4'd2;
    localparam [3:0] S_DIFF = 4'd3;
    localparam [3:0] S_BINS = 4'd4;
    localparam [3:0] S_MEAN = 4'd5;
    localparam [3:0] S_SQRT = 4'd6;
    localparam [3:0] S_DV1L = 4'd7;
    localparam [3:0] S_DV1S = 4'd8;
    localparam [3:0] S_DV2L = 4'd9;
    localparam [3:0] S_DV2S = 4'd10;
    localparam [3:0] S_EMIT = 4'd11;

    // ===========================================================================
    // 2. Interval collector: 32 slot shift register, stride counter, snapshot request. The
    //    window is 32 beats and the stride 4 beats, both locked by D5 and checked against
    //    the two configuration fields: a configuration that disagrees with the frozen
    //    hardware emits nothing rather than a wrong window.
    // ===========================================================================
    reg  [W_WIN*W_WVAL-1:0] win_q;      // newest interval at bits 15:0
    reg  [5:0]  fill_q;                 // 0 .. 32
    reg  [2:0]  stride_q;               // 0 .. 3
    reg         snap_req_q;             // one cycle pulse per completed stride position
    reg  [W_IDX-1:0] idx_q;             // sample index of the newest accepted interval

    wire cfg_ok     = (i_window_beats == BEATS_REQ) && (i_window_step == STEP_REQ);
    wire arm_marked = i_arm_select[ARM_MARKED_BIT];
    wire mark_keep  = (s_rr_mark == MARK_KEEP) || (s_rr_mark == MARK_SPLIT);
    wire ivl_take   = s_valid & i_enable & cfg_ok & (arm_marked ? mark_keep : 1'b1);
    wire window_full = fill_q[5];        // fill_q >= 32
    wire stride_end  = window_full && (stride_q == (i_window_step[2:0] - 3'd1));

    always @(posedge clk_i) begin
        if (!rst_ni || i_clear_counters) begin
            win_q      <= {W_WIN*W_WVAL{1'b0}};
            fill_q     <= 6'd0;
            stride_q   <= 3'd0;
            snap_req_q <= 1'b0;
            idx_q      <= {W_IDX{1'b0}};
        end else begin
            snap_req_q <= 1'b0;
            if (ivl_take) begin
                win_q <= {win_q[W_WIN*W_WVAL-1-W_WVAL:0], s_rr_ms};
                idx_q <= s_window_idx;
                if (!window_full) begin
                    fill_q <= fill_q + 6'd1;
                    if (fill_q == (W_WIN[5:0] - 6'd1)) begin
                        snap_req_q <= 1'b1;   // the 32nd interval completes a window
                        stride_q   <= 3'd0;
                    end
                end else if (stride_end) begin
                    snap_req_q <= 1'b1;
                    stride_q   <= 3'd0;
                end else begin
                    stride_q <= stride_q + 3'd1;
                end
            end
        end
    end

    // ===========================================================================
    // 3. Combinational window core: the 32 value sorting chain, the 16 middle values, the
    //    exact cross product histogram and the entropy term sum. A function of snp_q alone,
    //    so it settles once per window (and once per PREP cycle, which reads the same
    //    register). Each level of the chain is its own generate scope with a named vector,
    //    so the elaboration is an explicit acyclic graph rather than an array of wires whose
    //    element order only the tool can infer.
    // ===========================================================================
    reg  [W_WIN*W_WVAL-1:0] snp_q;      // the window under computation
    reg  [W_IDX-1:0]        snp_idx_q;

    genvar gp, gk;
    generate
        for (gp = 0; gp < W_WIN + 1; gp = gp + 1) begin : g_lvl
            wire [W_WIN*W_WVAL-1:0] v;
            if (gp == 0) begin : g_base
                assign v = snp_q;
            end else begin : g_net
                for (gk = 0; gk < W_WIN; gk = gk + 1) begin : g_slot
                    if (((gk % 2) == ((gp - 1) % 2)) && (gk < (W_WIN - 1))) begin : g_lower
                        assign v[gk*W_WVAL +: W_WVAL] =
                            (g_lvl[gp-1].v[gk*W_WVAL +: W_WVAL] >
                             g_lvl[gp-1].v[(gk+1)*W_WVAL +: W_WVAL]) ?
                            g_lvl[gp-1].v[(gk+1)*W_WVAL +: W_WVAL] :
                            g_lvl[gp-1].v[gk*W_WVAL +: W_WVAL];
                    end else if ((gk > 0) && (((gk - 1) % 2) == ((gp - 1) % 2))) begin : g_upper
                        assign v[gk*W_WVAL +: W_WVAL] =
                            (g_lvl[gp-1].v[(gk-1)*W_WVAL +: W_WVAL] >
                             g_lvl[gp-1].v[gk*W_WVAL +: W_WVAL]) ?
                            g_lvl[gp-1].v[(gk-1)*W_WVAL +: W_WVAL] :
                            g_lvl[gp-1].v[gk*W_WVAL +: W_WVAL];
                    end else begin : g_pass
                        assign v[gk*W_WVAL +: W_WVAL] =
                            g_lvl[gp-1].v[gk*W_WVAL +: W_WVAL];
                    end
                end
            end
        end
    endgenerate

    wire [W_WIN*W_WVAL-1:0] srt_w = g_lvl[W_WIN].v;
    wire [W_WVAL-1:0] core_min_w = srt_w[CORE_FIRST*W_WVAL +: W_WVAL];
    wire [W_WVAL-1:0] core_max_w = srt_w[CORE_LAST*W_WVAL +: W_WVAL];
    wire [W_WVAL-1:0] span_w     = core_max_w - core_min_w;

    localparam int unsigned W_XW   = W_WVAL + 4;     // 20, 16*x
    localparam int unsigned W_THRW = W_WVAL + 8;     // 24, k*span with room for the product
    reg  [W_XW-1:0]   x_w   [0:CNT_CORE-1];
    reg  [W_THRW-1:0] thr_w [1:CNT_EDGE];
    reg  [W_BIN-1:0]  abin_w [0:CNT_CORE];    // A[0]..A[16]: A[16] is 0, the last edge of
                                              // the plan's histogram is inclusive, so
                                              // bins_w[15] = A[15] - A[16] = A[15]
    reg  [W_BIN-1:0]  bins_w [0:CNT_CORE-1];
    reg  [W_ESUM-1:0] ent_sum_w;

    // minimum, maximum and sum of the 32 slots, the S_PREP operands
    reg  [W_WVAL-1:0] wmin_c, wmax_c;
    reg  [W_RRSUM:0]  rrsum_c;

    integer jj, kk, cc, pp;
    always @(*) begin
        for (jj = 0; jj < CNT_CORE; jj = jj + 1)
            x_w[jj] = {4'd0, (srt_w[(CORE_FIRST + jj)*W_WVAL +: W_WVAL] - core_min_w)} << 4;
        abin_w[0] = CNT_CORE[W_BIN-1:0];
        for (kk = 1; kk <= CNT_EDGE; kk = kk + 1) begin
            thr_w[kk]  = {8'd0, span_w} * kk[3:0];
            abin_w[kk] = {W_BIN{1'b0}};
            for (jj = 0; jj < CNT_CORE; jj = jj + 1)
                if ({{(W_THRW-W_XW){1'b0}}, x_w[jj]} >= thr_w[kk])
                    abin_w[kk] = abin_w[kk] + 6'd1;
        end
        // A[16] of the last edge: the count that reaches the top of the core, so that the
        // inclusive last bin falls out of the same A[k] - A[k+1] subtraction as the rest
        abin_w[CNT_CORE] = {W_BIN{1'b0}};
        for (cc = 0; cc < CNT_CORE; cc = cc + 1)
            bins_w[cc] = abin_w[cc] - abin_w[cc+1];
        ent_sum_w = {W_ESUM{1'b0}};
        for (cc = 0; cc < CNT_CORE; cc = cc + 1)
            ent_sum_w = ent_sum_w +
                        {{(W_ESUM-W_TERM){1'b0}}, TERM_FLAT[bins_w[cc]*W_TERM +: W_TERM]};
        // the S_PREP operands, through blocking temporaries so the loop accumulates
        wmin_c  = {W_WVAL{1'b1}};
        wmax_c  = {W_WVAL{1'b0}};
        rrsum_c = {(W_RRSUM+1){1'b0}};
        for (pp = 0; pp < W_WIN; pp = pp + 1) begin
            if (snp_q[pp*W_WVAL +: W_WVAL] < wmin_c)
                wmin_c = snp_q[pp*W_WVAL +: W_WVAL];
            if (snp_q[pp*W_WVAL +: W_WVAL] > wmax_c)
                wmax_c = snp_q[pp*W_WVAL +: W_WVAL];
            rrsum_c = rrsum_c + {{(W_RRSUM+1-W_WVAL){1'b0}}, snp_q[pp*W_WVAL +: W_WVAL]};
        end
    end

    // ===========================================================================
    // 4. Sequential unit: range gate, difference pass, mean square, digit root, one shared
    //    restoring divider with two passes, then the four taps and the window event.
    // ===========================================================================
    reg  [3:0]  st_q;
    reg  [5:0]  cnt_q;
    reg  [W_SUM2-1:0]   sum2_q;
    reg  [W_CNT50-1:0]  cnt50_q;
    reg  [W_WVAL-1:0]   prev_q;
    reg  [W_WIN*W_WVAL-1:0] rd_q;
    reg  [W_DVEC-1:0]   dvec_q;        // d[k] at bits k*W_D +: W_D, two's complement
    reg  [W_RRSUM:0]    rrsum_q;
    reg  [W_WVAL-1:0]   wmin_q, wmax_q;
    reg  [W_MEANQ-1:0]  meanq_q;
    reg  [W_ESUM-1:0]   ent_sum_q;
    reg  [W_ROOT-1:0]   root_q;
    reg  [W_RAD-1:0]    rad_q;
    reg  [W_RREM-1:0]   rrem_q;
    reg  [W_NUM-1:0]    dnum_q;
    reg  [W_QUO-1:0]    dquo_q;
    reg  [W_DEN-1:0]    dden_q;
    reg  [W_DEN-1:0]    drem_q;
    reg  [W_ROOT-1:0]   quo1_q;        // floor(R / 496)
    reg  [W_DEN-1:0]    rem1_q;        // R - 496*quo1

    // ---------------------------------------------------------------- white box bank
    // Written once per window and read by rtl/tb/tb_fitur.sv through a hierarchical
    // reference, the same way tb_kuantisasi.sv reads dut.pre_raw, so the gate of this phase
    // can be measured node by node and not only on the four taps. Nothing inside this module
    // reads them, so UNUSEDSIGNAL fires on these declarations and on no other signal in the
    // file; the waiver is scoped to this bank and is the only one in the logic.
    /* verilator lint_off UNUSEDSIGNAL */
    reg  [W_PNNT-1:0]   pnn50_q;       // Q1.8 pNN50 code of the window just finished
    reg  [31:0]         ovf_cnt_q;     // snapshots dropped because the unit was busy
    reg  [31:0]         rej_cnt_q;     // windows the range gate refused
    reg  [31:0]         win_cnt_q;     // windows emitted
    reg  [W_Q0-1:0]     d_mullo_q;     // low bits of the step 3 product, cross checked
    reg  [W_BIN-1:0]    bin_q [0:CNT_CORE-1];  // the 16 histogram bins of that window
    /* verilator lint_on UNUSEDSIGNAL */

    wire range_ok = (wmin_q >= RR_MIN_MS) && (wmax_q <= RR_MAX_MS);

    // ---- step 3: the /31 pair, plan constant C31, and the negative remainder fold-back
    wire [W_MULP-1:0] mul31_w = sum2_q * 58'd17318417;
    wire [W_Q0-1:0]   q0_w    = mul31_w[W_MULP-1 -: W_Q0];       // (sum_d2 * C31) >> 29
    wire [5:0]        q31lo_w = (q0_w[5:0] << 5) - q0_w[5:0];    // low six bits of 31*q0
    wire [5:0]        rem6_w  = sum2_q[5:0] - q31lo_w;
    wire              remneg_w = (rem6_w > 6'd31);
    wire [5:0]        rem0_w  = remneg_w ? (rem6_w - 6'd33) : rem6_w;
    wire [W_Q0-1:0]   qfix_w  = remneg_w ? (q0_w - Q_ONE) : q0_w;
    wire [W_FRACT-1:0] frac_w = FRAC_FLAT[rem0_w*W_FRACT +: W_FRACT];
    wire [W_MEANX-1:0] meanx_w = ({{(W_MEANX-W_Q0){1'b0}}, qfix_w} << 8) +
                                 {{(W_MEANX-W_FRACT){1'b0}}, frac_w};
    wire [W_MEANQ-1:0] meanq_w = (meanx_w > {{(W_MEANX-W_MEANQ){1'b0}}, {W_MEANQ{1'b1}}}) ?
                                 {W_MEANQ{1'b1}} : meanx_w[W_MEANQ-1:0];

    // ---- step 4: digit root operands
    wire [1:0]        pair_w   = rad_q[W_RAD-1 -: 2];
    wire [W_RREM+1:0] rnew_w   = {rrem_q, pair_w};
    wire [W_ROOT+1:0] rtrial_w = {root_q, 2'b01};
    wire [W_RREM+1:0] rtrial_x = {{(W_RREM + 2 - W_ROOT - 2){1'b0}}, rtrial_w};
    wire              rtake_w  = (rnew_w >= rtrial_x);
    wire [W_RVAL-1:0] rsub_w   = rnew_w[W_RVAL-1:0] - rtrial_x[W_RVAL-1:0];
    wire [W_RVAL-1:0] rnext_w  = rtake_w ? rsub_w : rnew_w[W_RVAL-1:0];
    wire [W_RREM-1:0] rjam_w   = {{(W_RREM - W_RVAL){1'b0}}, rnext_w};

    // ---- step 9: shared restoring divider operands and the two rounding tests. Doubling is
    //      avoided by comparing the remainder against half the divisor: 2*rem > D is
    //      rem > floor(D/2), and a tie 2*rem == D needs D even with rem == D/2.
    wire              dbit_w    = dnum_q[W_NUM-1];
    wire [W_DEN:0]    drnew_w   = {drem_q, dbit_w};
    wire              drsub_w   = (drnew_w >= {1'b0, dden_q});
    wire [W_DEN-1:0]  dden_half = dden_q >> 1;
    wire              quo1_up_w = (rem1_q > DEN1_HALF) ||
                                  ((rem1_q == DEN1_HALF) && quo1_q[0]);
    wire [W_ROOT-1:0] quo1_r    = quo1_q + (quo1_up_w ? Q_ONE : {W_ROOT{1'b0}});
    wire              quo2_up_w = (drem_q > dden_half) ||
                                  ((drem_q == dden_half) && (~dden_q[0]) && dquo_q[0]);
    wire [W_QUO:0]    quo2_r    = {1'b0, dquo_q} + (quo2_up_w ? {{W_QUO{1'b0}}, 1'b1}
                                                              : {(W_QUO+1){1'b0}});
    wire              rmssd_sat_w = |quo1_r[W_ROOT-1:W_F_RMSSD];
    wire              ratio_sat_w = |quo2_r[W_QUO:W_F_RATIO];

    // ---- step 8: the final entropy shift, round half to even
    wire [W_ESUM-1:0] ent_hi   = ent_sum_q >> ENT_SHIFT;
    wire [ENT_SHIFT-1:0] ent_lo = ent_sum_q[ENT_SHIFT-1:0];
    wire              ent_up   = ({{(W_ESUM-ENT_SHIFT){1'b0}}, ent_lo} > ENT_HALF) ? 1'b1 :
                                 (({{(W_ESUM-ENT_SHIFT){1'b0}}, ent_lo} == ENT_HALF) ?
                                  ent_hi[0] : 1'b0);
    wire [W_ESUM-1:0] ent_val  = ent_hi + {{(W_ESUM-1){1'b0}}, ent_up};
    wire [W_ESUM-1:0] ent_max  = {{(W_ESUM-W_F_ENT){1'b0}}, {W_F_ENT{1'b1}}};
    wire [W_F_ENT-1:0] ent_r   = (ent_val > ent_max) ? {W_F_ENT{1'b1}} : ent_val[W_F_ENT-1:0];

    // ---- the exact difference of the current top slot and the previous one
    wire [W_WVAL-1:0] cur_w   = rd_q[W_WIN*W_WVAL-1 -: W_WVAL];
    wire [W_D-1:0]    d_w     = cur_w[W_D-1:0] - prev_q[W_D-1:0];  // 13 bit two's comp
    // which d field the current beat writes, 9 bits wide (see W_D9); the value for cnt_q at
    // zero underflows on purpose and is never used, the write is guarded by cnt_q > 0
    wire [8:0]        doff_w  = ({3'd0, cnt_q} - 9'd1) * W_D9;
    wire signed [W_D-1:0]  ds_w = d_w;
    wire signed [W_D2-1:0] d2_s = ds_w * ds_w;
    wire [W_D2-1:0]   d2_u    = d2_s;                        // the sign bit is never set
    wire [W_WVAL:0]   dmag_w  = (cur_w >= prev_q) ? (cur_w - prev_q) : (prev_q - cur_w);

    integer ii;
    always @(posedge clk_i) begin
        if (!rst_ni) begin
            st_q      <= S_IDLE;
            cnt_q     <= 6'd0;
            snp_q     <= {W_WIN*W_WVAL{1'b0}};
            snp_idx_q <= {W_IDX{1'b0}};
            sum2_q    <= {W_SUM2{1'b0}};
            cnt50_q   <= {W_CNT50{1'b0}};
            prev_q    <= {W_WVAL{1'b0}};
            rd_q      <= {W_WIN*W_WVAL{1'b0}};
            dvec_q    <= {W_DVEC{1'b0}};
            rrsum_q   <= {(W_RRSUM+1){1'b0}};
            wmin_q    <= {W_WVAL{1'b0}};
            wmax_q    <= {W_WVAL{1'b0}};
            meanq_q   <= {W_MEANQ{1'b0}};
            ent_sum_q <= {W_ESUM{1'b0}};
            root_q    <= {W_ROOT{1'b0}};
            rad_q     <= {W_RAD{1'b0}};
            rrem_q    <= {W_RREM{1'b0}};
            dnum_q    <= {W_NUM{1'b0}};
            dquo_q    <= {W_QUO{1'b0}};
            dden_q    <= {W_DEN{1'b0}};
            drem_q    <= {W_DEN{1'b0}};
            quo1_q    <= {W_ROOT{1'b0}};
            rem1_q    <= {W_DEN{1'b0}};
            pnn50_q   <= {W_PNNT{1'b0}};
            d_mullo_q <= {W_Q0{1'b0}};
            ovf_cnt_q <= 32'd0;
            rej_cnt_q <= 32'd0;
            win_cnt_q <= 32'd0;
            d_valid   <= 1'b0;
            d_rmssd   <= {W_F_RMSSD{1'b0}};
            d_ratio   <= {W_F_RATIO{1'b0}};
            d_ent     <= {W_F_ENT{1'b0}};
            d_meanq   <= {W_F_MEANQ{1'b0}};
            m_ev_valid <= 1'b0;
            m_ev_kind  <= afib_lite_pkg::EV_NONE;
            m_ev_idx   <= {W_IDX{1'b0}};
            m_ev_val   <= 32'd0;
            for (ii = 0; ii < CNT_CORE; ii = ii + 1) bin_q[ii] <= {W_BIN{1'b0}};
        end else if (i_clear_counters) begin
            st_q      <= S_IDLE;
            cnt_q     <= 6'd0;
            ovf_cnt_q <= 32'd0;
            rej_cnt_q <= 32'd0;
            win_cnt_q <= 32'd0;
            d_valid   <= 1'b0;
            m_ev_valid <= 1'b0;
            m_ev_kind <= afib_lite_pkg::EV_NONE;
            m_ev_idx  <= {W_IDX{1'b0}};
            m_ev_val  <= 32'd0;
            d_rmssd   <= {W_F_RMSSD{1'b0}};
            d_ratio   <= {W_F_RATIO{1'b0}};
            d_ent     <= {W_F_ENT{1'b0}};
            d_meanq   <= {W_F_MEANQ{1'b0}};
            for (ii = 0; ii < CNT_CORE; ii = ii + 1) bin_q[ii] <= {W_BIN{1'b0}};
        end else begin
            d_valid    <= 1'b0;
            m_ev_valid <= 1'b0;
            if (snap_req_q && (st_q != S_IDLE)) ovf_cnt_q <= ovf_cnt_q + 32'd1;
            case (st_q)
                S_IDLE: begin
                    cnt_q <= 6'd0;
                    if (snap_req_q) begin
                        snp_q     <= win_q;
                        snp_idx_q <= idx_q;
                        st_q      <= S_PREP;
                    end
                end
                S_PREP: begin
                    wmin_q    <= wmin_c;
                    wmax_q    <= wmax_c;
                    rrsum_q   <= rrsum_c;
                    rd_q      <= snp_q;
                    dvec_q    <= {W_DVEC{1'b0}};
                    sum2_q    <= {W_SUM2{1'b0}};
                    cnt50_q   <= {W_CNT50{1'b0}};
                    cnt_q     <= 6'd0;
                    st_q      <= S_GATE;
                end
                S_GATE: begin
                    if (range_ok) begin
                        st_q <= S_DIFF;
                    end else begin
                        rej_cnt_q <= rej_cnt_q + 32'd1;
                        st_q      <= S_IDLE;
                    end
                end
                S_DIFF: begin
                    // 32 cycles: the first loads the tail value, the next 31 emit one d
                    prev_q <= cur_w;
                    rd_q   <= rd_q << W_WVAL;
                    if (cnt_q > 6'd0) begin
                        sum2_q  <= sum2_q + {{(W_SUM2 - W_D2){1'b0}}, d2_u};
                        cnt50_q <= cnt50_q + ((dmag_w > PNN50_X) ? 6'd1 : 6'd0);
                        dvec_q  <= dvec_q |
                                   ({{(W_DVEC - W_D){1'b0}}, d_w} << doff_w);
                    end
                    if (cnt_q == (CNT_DIFF[5:0] - 6'd1)) begin
                        cnt_q   <= 6'd0;
                        st_q    <= S_BINS;
                    end else begin
                        cnt_q <= cnt_q + 6'd1;
                    end
                end
                S_BINS: begin
                    for (ii = 0; ii < CNT_CORE; ii = ii + 1) bin_q[ii] <= bins_w[ii];
                    ent_sum_q <= ent_sum_w;
                    // The pNN50 code is read here and not in the last S_DIFF cycle: there
                    // cnt50_q still misses the 31st comparison (its own increment lands at
                    // the same edge), so a window whose last d was over 50 ms came out one
                    // step low. cnt50_q is final by the time S_BINS runs.
                    pnn50_q   <= PNN_FLAT[cnt50_q*W_FRACT +: W_PNNT];
                    st_q      <= S_MEAN;
                end
                S_MEAN: begin
                    meanq_q   <= meanq_w;
                    rad_q     <= (({{(W_RAD - W_SUM2){1'b0}}, sum2_q} << 5) -
                                  {{(W_RAD - W_SUM2){1'b0}}, sum2_q}) << 24;
                    root_q    <= {W_ROOT{1'b0}};
                    rrem_q    <= {W_RREM{1'b0}};
                    d_mullo_q <= mul31_w[W_Q0-1:0];
                    cnt_q     <= 6'd0;
                    st_q      <= S_SQRT;
                end
                S_SQRT: begin
                    rrem_q <= rjam_w;
                    root_q <= {root_q[W_ROOT-2:0], rtake_w};
                    rad_q  <= rad_q << 2;
                    if (cnt_q == (ROOT_STEP[5:0] - 6'd1)) begin
                        cnt_q <= 6'd0;
                        st_q  <= S_DV1L;
                    end else begin
                        cnt_q <= cnt_q + 6'd1;
                    end
                end
                S_DV1L: begin
                    // the numerator is left aligned at the top of the shift register, so the
                    // 29 steps consume exactly the 29 bits of R and the quotient is R/496
                    dnum_q <= {{(W_NUM - W_ROOT){1'b0}}, root_q} << SA_ALIGN;
                    dden_q <= DEN1;
                    dquo_q <= {W_QUO{1'b0}};
                    drem_q <= {W_DEN{1'b0}};
                    cnt_q  <= 6'd0;
                    st_q   <= S_DV1S;
                end
                S_DV1S: begin
                    dnum_q <= dnum_q << 1;
                    if (drsub_w) begin
                        drem_q <= drnew_w[W_DEN-1:0] - dden_q;
                        dquo_q <= {dquo_q[W_QUO-2:0], 1'b1};
                    end else begin
                        drem_q <= drnew_w[W_DEN-1:0];
                        dquo_q <= {dquo_q[W_QUO-2:0], 1'b0};
                    end
                    if (cnt_q == (DIV_STEP1[5:0] - 6'd1)) begin
                        cnt_q <= 6'd0;
                        st_q  <= S_DV2L;
                    end else begin
                        cnt_q <= cnt_q + 6'd1;
                    end
                end
                S_DV2L: begin
                    quo1_q <= dquo_q[W_ROOT-1:0];
                    rem1_q <= drem_q;
                    dnum_q <= {{(W_NUM - W_ROOT){1'b0}}, root_q} << SA_ALIGN;
                    dden_q <= (({{(W_DEN - W_RRSUM - 1){1'b0}}, rrsum_q} << 5) -
                               {{(W_DEN - W_RRSUM - 1){1'b0}}, rrsum_q});
                    dquo_q <= {W_QUO{1'b0}};
                    drem_q <= {W_DEN{1'b0}};
                    cnt_q  <= 6'd0;
                    st_q   <= S_DV2S;
                end
                S_DV2S: begin
                    dnum_q <= dnum_q << 1;
                    if (drsub_w) begin
                        drem_q <= drnew_w[W_DEN-1:0] - dden_q;
                        dquo_q <= {dquo_q[W_QUO-2:0], 1'b1};
                    end else begin
                        drem_q <= drnew_w[W_DEN-1:0];
                        dquo_q <= {dquo_q[W_QUO-2:0], 1'b0};
                    end
                    if (cnt_q == (DIV_STEP2[5:0] - 6'd1)) begin
                        cnt_q <= 6'd0;
                        st_q  <= S_EMIT;
                    end else begin
                        cnt_q <= cnt_q + 6'd1;
                    end
                end
                default: begin
                    // S_EMIT: the four taps and the window event, one cycle
                    d_rmssd <= rmssd_sat_w ? {W_F_RMSSD{1'b1}} : quo1_r[W_F_RMSSD-1:0];
                    d_ratio <= ratio_sat_w ? {W_F_RATIO{1'b1}} : quo2_r[W_F_RATIO-1:0];
                    d_ent   <= ent_r;
                    d_meanq <= meanq_q;
                    d_valid <= 1'b1;
                    m_ev_valid <= 1'b1;
                    m_ev_kind  <= afib_lite_pkg::EV_WINDOW;
                    m_ev_idx   <= snp_idx_q;
                    m_ev_val   <= {26'd0, cnt50_q};
                    win_cnt_q  <= win_cnt_q + 32'd1;
                    cnt_q      <= 6'd0;
                    st_q       <= S_IDLE;
                end
            endcase
        end
    end

endmodule

`default_nettype wire
