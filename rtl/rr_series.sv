// ---------------------------------------------------------------------------
// rr_series.sv -- RR interval series, the eight-interval queue, the reseeding history,
// and the four interval marks. Contract profile: event stage (I1).
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). Consumes the QRS events of peak_detect on s_ev_* and produces m_rr_last,
// m_rr_mark and its own events on m_ev_*. Owns o_rr_long_count.
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 section 2.2):
//   rr in ms         W_RR_MS  = 16   Q16.0. Measured 12 bits on 04015, 16 on the worst
//                                    record, and Python never overflows, so a 12 bit
//                                    view would fail on the board as false missed beats.
//   rr in samples    W_RR_SMP = 15   the search-back distance accumulator, in samples.
//                                    Units are easy to mix here: the same physical gap
//                                    reads 51064 ms and 12766 samples.
//   index            W_IDX    = 32
// Saturation points: accepted RR band 250 to 2000 ms, long interval ceiling RR_LONG_MS
//   3000 ms, full field RR_MAX_MS 65535 so nothing is clamped to 13 bits, and the gap
//   recovery span GAP_RECOVERY 131 samples which is 524 ms at 250 Hz.
// Rounding rule: RND_FLOOR for the eight-term mean (rantai.py:399) and for the rational
//   mean (rantai.py:426 where the denominator is at most 8), and RND_TRUNC_ZERO for the
//   even-count median (rantai.py:372). The missed-beat test is the cross form 83/50 at
//   rantai.py:534 so no divider is needed; the band test is the cross forms
//   25*d*x >= 23*n and <= 29*n at rantai.py:359-361.
// Model lines this file mirrors: rantai.py:375-440, :443-559, :569-600, :631-642,
//   interval in milliseconds at :632, band at :359-361, ra1 at :399, ra2 at :426,
//   median at :372, marks at :529, :534, :536, :543, :544, ceiling at :496, cross form
//   at :581.
//
// Buffer lengths, not time constants: rhythm marker window 8 intervals, reseeding history
// 32 intervals, at most one reseed per eight intervals, candidate depth DECISION_DEPTH 8.
// They must be derived from the beat or sample counter, never from a fixed cycle count.
//
// Fase 6 status: REAL BODY. What the body implements, model line by model line:
//
//   interval     rr_ms = (qrs_cur - qrs_prev) << 2, rantai.py:632. The interval is derived
//                from the QRS sample indices and never from s_ev_val, because the model
//                computes it from the two positions while s_ev_val carries the peak
//                amplitude on an event of kind EV_QRS.
//   marks        the four stage 7b marks of rantai.py:519-559, decided against the median
//                of the eight-interval rhythm window and tested in the model's own order
//                (false detection, then missed beat, then the 3000 ms ceiling).
//   queue        the eight-interval queue of rantai.py:384-423, filled only by intervals
//                inside the locked band 250 to 2000 ms (rantai.py:638), reseeded with the
//                median of the last 32 in-band intervals at most once per eight intervals
//                (rantai.py:413-419, SEMAI_JEDA).
//   averages     ra1 = sum(the eight queue observations) >> 3 (rantai.py:399) and
//                ra2 = pembilang // penyebut (rantai.py:426). Two different averages, on
//                purpose, and they must never be unified.
//
// Implementation notes, all three reported in rtl-synthesis/reports/LAPORAN-FASE6.md:
//
//   1. Both medians (the eight-interval reference and the 32-interval reseed history) come
//      from one shared rank engine: the k-th order statistic is found by a bounded 16-step
//      binary search on the value, with the count of entries at or below the trial value
//      taken over the whole window in a single cycle. Every loop bound is a compile time
//      constant (W_RR_MS steps, two ranks, 8 and 32 window slots), no loop length and no
//      buffer index comes from a data value, and the two ranks are (L-1)>>1 and L>>1,
//      which is exactly rantai.median_bulat including its truncating even-count case.
//      Plan 6 step 2 asks for the 32-value sorting network shared with the feature layer;
//      a rank engine produces the same two numbers with 32 comparators instead of a full
//      network and it is the sharing that plan 6 step 2 is after. Deviation, with the plan
//      step 5 recommendation B as the precedent (doc I2 section 3, median scan 32 cycles).
//   2. The two constants of the missed beat fraction, 83 and 50, are declared in this file
//      because afib_lite_pkg.sv carries no name for them (rantai.py:498-499 RR_MISS_NUM
//      and RR_MISS_DEN) and the package is frozen for this phase. Plan 3.4 rule 2 wants
//      every threshold in the package, so this is a deviation: the recommendation to the
//      owner is to add the two names to package group 8, the way W_SB was added in Fase 5.
//   3. The window and gap events on m_ev_* are the passthrough of s_tlast and of the
//      lost-sample marker bit, which have no datapath of their own in this stage. The four
//      interval marks never take an input marker bit into account, exactly as the model
//      does. The window event carries the interval counter in m_ev_val.
//
// Timing: the per-interval slot is bounded by 1 + 2*W_RR_MS + 1 + W_RR_SUM + 1 = 71
// cycles: 32 for the eight-interval reference median, up to 33 for a reseed median, 20 for
// the ra2 division, and one cycle each for the apply and the commit step. The fastest
// interval of the band is 200 ms, which is 50 samples or 20000000 cycles at the 250 Hz rate
// of RATE_DIV_RST, so the slot uses 0.0004 percent of the budget and this stage never needs
// back pressure (D1). LAT_CYCLES keeps its Fase 1 value of one as a parameter default, as
// the frozen port list requires; the real per-interval latency is the slot above.
//
// Introspection: d_valid pulses for the interval word (d_rr_ms, d_rr_smp), one pulse per
// raw interval. The per-step state of the locked stage (ra1, ra2, queue length, menyala,
// disemai, history length, the fail and pace counters) has no port in the frozen port list,
// so it is latched into the registers named d_step_* below and read by tb_rr.sv through a
// hierarchical reference, the same white box read tb_kuantisasi.sv makes of dut.pre_raw.
// d_step_valid_q pulses once per in-band interval, the step counter of the model.
//
// Under reset, synchronous active low, every register returns to its reset value on the
// first edge; no vendor primitive, no latch, one clock.
// House style: wire and reg only (D10), one clock, synchronous active low reset.
// ---------------------------------------------------------------------------
`default_nettype none

module rr_series #(
    parameter int unsigned W_RR_MS    = afib_lite_pkg::W_RR_MS,
    parameter int unsigned W_RR_SMP   = afib_lite_pkg::W_RR_SMP,
    parameter int unsigned W_IDX      = afib_lite_pkg::W_IDX,
    parameter int unsigned W_TUSER    = afib_lite_pkg::W_TUSER,
    parameter int unsigned W_EVKIND   = afib_lite_pkg::W_EVKIND,
    parameter int unsigned LAT_CYCLES = 1
) (
    input  wire                     clk_i,
    input  wire                     rst_ni,

    // configuration
    input  wire                     i_enable,
    input  wire                     i_clear_counters,

    // sample stream passthrough: the window layer still needs the timing words
    input  wire                     s_tvalid,
    input  wire                     s_tlast,
    input  wire [W_TUSER-1:0]       s_tuser,
    input  wire [W_IDX-1:0]         s_sample_idx,

    // event sideband in: QRS beats and peak candidates from peak_detect
    input  wire                     s_ev_valid,
    input  wire [W_EVKIND-1:0]      s_ev_kind,
    input  wire [W_IDX-1:0]         s_ev_idx,
    input  wire [31:0]              s_ev_val,

    // decision group this stage owns
    output reg  [W_RR_MS-1:0]       m_rr_last,
    output reg  [1:0]               m_rr_mark,

    // event sideband out: interval closed and decision window closed
    output reg                      m_ev_valid,
    output reg  [W_EVKIND-1:0]      m_ev_kind,
    output reg  [W_IDX-1:0]         m_ev_idx,
    output reg  [31:0]              m_ev_val,

    // introspection
    output reg                      d_valid,
    output reg  [W_RR_MS-1:0]       d_rr_ms,
    output reg  [W_RR_SMP-1:0]      d_rr_smp,

    // status this stage owns
    output reg  [31:0]              o_rr_long_count
);

    // =================================================================== package names
    // Icarus 12 accepts afib_lite_pkg::NAME in parameter and localparam defaults but not
    // inside a procedural statement, so every package constant this body reads is aliased
    // at module scope first, exactly as tb_kuantisasi.sv does.
    localparam int unsigned W_RR_SUM_L   = afib_lite_pkg::W_RR_SUM;    // 20
    localparam int unsigned W_RR_PROD_L  = afib_lite_pkg::W_RR_PROD;   // 32
    localparam [W_RR_MS-1:0] RR_LONG_L   = afib_lite_pkg::RR_LONG_MS;  // 3000
    localparam [W_RR_MS-1:0] RR_MAX_L    = afib_lite_pkg::RR_MAX_MS;   // 65535
    localparam int unsigned DELAPAN_L    = afib_lite_pkg::DELAPAN;         // 8
    localparam int unsigned SEMAI_L      = afib_lite_pkg::SEMAI_PANJANG;   // 32
    localparam int unsigned SEMAI_JEDA_L = afib_lite_pkg::SEMAI_JEDA;      // 8
    localparam int unsigned N_RR_L       = afib_lite_pkg::RR_BAND_NUM;     // 25
    localparam int unsigned N_LO_L       = afib_lite_pkg::RR_BAND_LO;      // 23
    localparam int unsigned N_HI_L       = afib_lite_pkg::RR_BAND_HI;      // 29
    localparam int unsigned BAND_MIN_L   = afib_lite_pkg::RR_BAND_MIN_MS;  // 250
    localparam int unsigned BAND_MAX_L   = afib_lite_pkg::RR_BAND_MAX_MS;  // 2000
    localparam int unsigned SHIFT_RA1_L  = afib_lite_pkg::SHIFT_RA1;       // 3
    localparam [1:0] MARK_KEEP_L  = afib_lite_pkg::RR_MARK_KEEP;   // 0
    localparam [1:0] MARK_SPLIT_L = afib_lite_pkg::RR_MARK_SPLIT;  // 1
    localparam [1:0] MARK_DROP_L  = afib_lite_pkg::RR_MARK_DROP;   // 2
    localparam [1:0] MARK_GAP_L   = afib_lite_pkg::RR_MARK_GAP;    // 3
    localparam [W_EVKIND-1:0] EV_NONE_L   = afib_lite_pkg::EV_NONE;    // 0
    localparam [W_EVKIND-1:0] EV_QRS_L    = afib_lite_pkg::EV_QRS;     // 1
    localparam [W_EVKIND-1:0] EV_RR_L     = afib_lite_pkg::EV_RR;      // 3
    localparam [W_EVKIND-1:0] EV_WINDOW_L = afib_lite_pkg::EV_WINDOW;  // 4
    localparam [W_EVKIND-1:0] EV_GAP_L    = afib_lite_pkg::EV_GAP;     // 5
    localparam int unsigned TU_GAP_L     = afib_lite_pkg::TU_GAP;      // 1

    // Deviation, reported: the stage 7b missed beat fraction 83/50 (rantai.py:498-499) has
    // no name in afib_lite_pkg.sv and that file is frozen for this phase. Declared once,
    // under the model's own names; the recommendation to the owner is package group 8.
    localparam int unsigned RR_MISS_NUM_L = 83;
    localparam int unsigned RR_MISS_DEN_L = 50;

    // =================================================================== local geometry
    localparam int unsigned HIST_SLOTS = DELAPAN_L;         // 8, rantai.py:62
    localparam int unsigned RIW_SLOTS  = SEMAI_L;           // 32, rantai.py:63
    localparam int unsigned HIST_W     = 3;                 // slot pointer, 8 slots
    localparam int unsigned RIW_W      = 5;                 // slot pointer, 32 slots
    localparam int unsigned HIST_LW    = 4;                 // length 0 to 8
    localparam int unsigned RIW_LW     = 6;                 // length 0 to 32
    localparam int unsigned DIV_BITS   = W_RR_SUM_L;        // numerator width, 20
    localparam int unsigned MED_IDX_W  = 4;                 // 0 to 15
    // The two bit indices below are sized expressions on purpose: W_RR_MS and DIV_BITS are
    // int unsigned, so an unsized `W_RR_MS - 1` is a 32 bit value assigned to a narrow
    // register and Verilator raises WIDTHTRUNC on it. The bit select keeps both operands at
    // the width of their counter, which is exact for every width plan 3.4 allows.
    localparam [MED_IDX_W:0]   MED_BIT_TOP  = W_RR_MS[MED_IDX_W:0] - 5'd1;   // 15
    localparam [MED_IDX_W:0]   MED_BIT_ZERO = {(MED_IDX_W+1){1'b0}};
    localparam [4:0]           DIV_BIT_TOP  = DIV_BITS[4:0] - 5'd1;          // 19
    localparam [DIV_BITS-2:0]  ZERO_DIV     = {(DIV_BITS-1){1'b0}};
    localparam int unsigned    DIV_REM_W    = 5;   // 2 * penyebut - 1 with penyebut <= 8, plus one
                                                   // shifted-in numerator bit (rantai.py:426)
    localparam int unsigned JEDA_W     = 16;                // the pace counter of rantai.py:411
    localparam [HIST_LW-1:0] DELAPAN_LEN = DELAPAN_L[HIST_LW-1:0];
    localparam [RIW_LW-1:0]  RIW_SLOTS_L = RIW_SLOTS[RIW_LW-1:0];
    localparam [3:0]         DELAPAN_DEN = DELAPAN_L[3:0];
    localparam [HIST_W-1:0]  ONE_SLOT    = {{(HIST_W-1){1'b0}}, 1'b1};
    localparam [HIST_W-1:0]  HIST_TWO    = {{(HIST_W-2){1'b0}}, 2'd2};
    localparam [HIST_W-1:0]  ZERO_SLOT   = {HIST_W{1'b0}};
    localparam [HIST_LW-1:0] ONE_LEN     = {{(HIST_LW-1){1'b0}}, 1'b1};
    localparam [RIW_W-1:0]   ONE_RIW     = {{(RIW_W-1){1'b0}}, 1'b1};
    localparam [RIW_LW-1:0]  ONE_RIWL    = {{(RIW_LW-1){1'b0}}, 1'b1};
    localparam [W_RR_MS-1:0] ONE_MS      = {{(W_RR_MS-1){1'b0}}, 1'b1};
    localparam [W_RR_SUM_L-1:0] ZERO_SUM = {W_RR_SUM_L{1'b0}};

    localparam [2:0] PH_IDLE   = 3'd0;   // waiting for a beat
    localparam [2:0] PH_REF    = 3'd1;   // rank engine, the two reference ranks of the marks
    localparam [2:0] PH_APPLY  = 3'd2;   // decide the mark, push, publish the interval
    localparam [2:0] PH_DIV    = 3'd3;   // ra2 = pembilang // penyebut
    localparam [2:0] PH_RES    = 3'd4;   // rank engine on the 32-interval reseed history
    localparam [2:0] PH_RES2   = 3'd5;   // reseed: fill the queue with the median
    localparam [2:0] PH_COMMIT = 3'd6;   // menyala verdict, counters, introspection latch

    // =================================================================== state
    reg [2:0]               phase_q;

    // interval engine
    reg                     qrs_seen_q;
    reg [W_IDX-1:0]         qrs_prev_q;
    reg [W_IDX-1:0]         beat_idx_q;
    reg [W_RR_MS-1:0]       x_q;            // the raw interval under test, milliseconds
    reg [W_RR_SMP-1:0]      smp_q;          // its distance in samples
    reg                     sat_ms_q;       // sticky: an interval word was saturated
    reg                     sat_smp_q;      // sticky: a sample distance was saturated
    reg                     quo_over_q;     // sticky: an ra2 quotient did not fit 16 bits
    reg [31:0]              interval_ix_q;  // raw intervals closed since reset

    // rhythm marker window, 8 intervals, circular, valid iff index < length
    reg [W_RR_MS-1:0]       hist_q [0:HIST_SLOTS-1];
    reg [HIST_W-1:0]        hist_w_q;
    reg [HIST_LW-1:0]       hist_len_q;

    // the eight-interval queue of the locked stage, in-band intervals only
    reg [W_RR_MS-1:0]       deret_q [0:HIST_SLOTS-1];
    reg [HIST_W-1:0]        deret_w_q;
    reg [HIST_LW-1:0]       deret_len_q;

    // the accepted interval queue (antre), read only through its sum and its length
    reg [W_RR_MS-1:0]       antre_q [0:HIST_SLOTS-1];
    reg [HIST_W-1:0]        antre_w_q;
    reg [HIST_LW-1:0]       antre_len_q;
    reg [W_RR_SUM_L-1:0]    pembilang_q;
    reg [3:0]               penyebut_q;
    reg [W_RR_MS-1:0]       ra1_q;
    reg [W_RR_MS-1:0]       ra2_q;
    reg [3:0]               gagal_q;        // consecutive intervals outside the band
    reg [JEDA_W-1:0]        jeda_q;         // intervals since the last reseed

    // the 32-interval reseed history, in-band intervals only
    reg [W_RR_MS-1:0]       riwayat_q [0:RIW_SLOTS-1];
    reg [RIW_W-1:0]         riwayat_w_q;
    reg [RIW_LW-1:0]        riwayat_len_q;

    // counters
    reg [31:0]              step_q;         // langkah, in-band intervals driven
    reg [31:0]              semai_q;        // reseeds since reset
    reg [31:0]              penanda_q;      // intervals whose eight window is fully in band

    // shared rank engine
    reg                     med_which_q;    // 0 rhythm window, 1 reseed history
    reg [RIW_LW-1:0]        med_len_q;      // window length the two ranks come from
    reg                     med_pass_q;     // 0 lower rank, 1 upper rank
    reg [MED_IDX_W:0]       med_bit_q;      // 15 down to 0, one bit of headroom for the top constant
    reg [W_RR_MS-1:0]       med_cand_q;
    reg [W_RR_MS-1:0]       sel_lo_q;
    reg [W_RR_MS-1:0]       sel_hi_q;
    reg                     ref_valid_q;    // a reference median exists for this interval

    // division engine, ra2
    reg [W_RR_SUM_L-1:0]    div_num_q;
    reg [3:0]               div_den_q;
    // The remainder of a restoring division is always below the denominator, so with a
    // denominator of at most eight the shifted remainder needs five bits at most
    // (2 * 8 - 1 is 15, plus the numerator bit that is shifted in). The quotient is built one
    // bit per step, one bit narrower than the numerator, and its last bit is the comparison
    // of the final step, quo_final below.
    reg [DIV_REM_W-2:0]     div_rem_q;
    reg [DIV_BITS-2:0]      div_quo_q;
    reg [4:0]               div_bit_q;

    // per-interval decisions
    reg                     in_band_q;      // the current interval is inside the locked band
    reg                     disemai_q;      // a reseed happened for the current step

    // ----------------------------------------------------------------- introspection bank
    // The port list is frozen: it carries neither a debug bus (the way peak_detect added
    // d_dbg in Fase 5) nor a per-step status word, and tb_rr.sv has to gate the three pass
    // criteria of plan Fase 6 on the state of the locked stage ("the queue length exactly 8
    // after step 24" is one of them). The bank below is written once per in-band interval and
    // read by the testbench through a hierarchical reference, exactly as tb_kuantisasi.sv
    // reads dut.pre_raw. Nothing inside this module reads it, so UNUSEDSIGNAL fires on each
    // of these declarations and on no other signal in the file: the waiver is scoped tightly
    // to this bank and it is the one lint waiver in the file. Reported in
    // rtl-synthesis/reports/LAPORAN-FASE6.md.
    /* verilator lint_off UNUSEDSIGNAL */
    reg [31:0]              d_beat_val_q;   // s_ev_val of the most recent accepted beat
    reg                     d_ra1_over_q;   // sticky: ra1 left 16 bits, unstuck by counters clear
    reg                     d_div_rem_bad_q;// sticky: the restoring remainder left four bits
    reg                     d_step_valid_q;
    reg [W_RR_MS-1:0]       d_step_ra1_q;
    reg [W_RR_MS-1:0]       d_step_ra2_q;
    reg [HIST_LW-1:0]       d_step_antre_q;
    reg [HIST_LW-1:0]       d_step_deret_q;
    reg [RIW_LW-1:0]        d_step_riwayat_q;
    reg                     d_step_menyala_q;
    reg                     d_step_disemai_q;
    reg [3:0]               d_step_gagal_q;
    reg [JEDA_W-1:0]        d_step_jeda_q;
    reg [31:0]              d_step_step_q;
    reg [W_RR_SUM_L-1:0]    d_step_pembilang_q;
    reg [3:0]               d_step_penyebut_q;
    reg                     d_step_inband_q;
    /* verilator lint_on UNUSEDSIGNAL */

    // =================================================================== input decoding
    wire beat_now = s_ev_valid & i_enable & s_tvalid & (s_ev_kind == EV_QRS_L);
    wire win_now  = i_enable & s_tvalid & s_tlast;
    wire gap_now  = i_enable & s_tvalid & s_tuser[TU_GAP_L];

    // the interval of this beat, rantai.py:632: (qrs[-1] - qrs[-2]) * 1000 // 250, and
    // 1000 / 250 is exactly 4, so the interval is a left shift by two, never a division
    wire [W_IDX-1:0]    rr_diff   = s_ev_idx - qrs_prev_q;
    wire [W_IDX+1:0]    rr_wide   = {rr_diff, 2'b00};
    wire                rr_over   = (rr_wide > {{(W_IDX+2-W_RR_MS){1'b0}}, RR_MAX_L});
    wire [W_RR_MS-1:0]  rr_word   = rr_over ? RR_MAX_L : rr_wide[W_RR_MS-1:0];
    wire                smp_over  = |rr_diff[W_IDX-1:W_RR_SMP];
    wire [W_RR_SMP-1:0] smp_word  = smp_over ? {W_RR_SMP{1'b1}} : rr_diff[W_RR_SMP-1:0];

    // =================================================================== helper functions
    // 25 * penyebut * value, rantai.py:359-361, cross multiplied so no division appears.
    // 25 * 8 * 65535 is 13107000, so 32 bits hold the left hand side with room to spare.
    function automatic [W_RR_PROD_L-1:0] band_lhs(input [W_RR_MS-1:0] v, input [3:0] den);
        begin
            band_lhs = ({{(W_RR_PROD_L-4){1'b0}}, den} * N_RR_L) *
                       {{(W_RR_PROD_L-W_RR_MS){1'b0}}, v};
        end
    endfunction

    function automatic [W_RR_PROD_L-1:0] scale_ms(input [W_RR_MS-1:0] v, input [31:0] k);
        begin
            scale_ms = {{(W_RR_PROD_L-W_RR_MS){1'b0}}, v} * k;
        end
    endfunction

    function automatic [W_RR_PROD_L-1:0] scale_num(input [W_RR_SUM_L-1:0] v, input [31:0] k);
        begin
            scale_num = {{(W_RR_PROD_L-W_RR_SUM_L){1'b0}}, v} * k;
        end
    endfunction

    // the exact band of the notebook, rantai.py:359-361: 25*penyebut*x between 23*acuan
    // and 29*acuan
    function automatic band_ok(input [W_RR_MS-1:0] v, input [W_RR_SUM_L-1:0] num,
                               input [3:0] den);
        begin
            band_ok = (band_lhs(v, den) >= scale_num(num, N_LO_L)) &&
                      (band_lhs(v, den) <= scale_num(num, N_HI_L));
        end
    endfunction

    // =================================================================== rank engine
    // the trial value of the current binary search step: cand | (1 << bit)
    wire [W_RR_MS-1:0] med_try = med_cand_q | (ONE_MS << med_bit_q);
    // the two ranks of rantai.median_bulat over med_len_q entries: (L-1)>>1 and L>>1.
    // For an odd count they are equal, for an even count they are the middle pair, and the
    // final floor of the mean of the pair is the >> 1 on ref_w below.
    wire [RIW_LW-1:0]  med_rank0 = (med_len_q - ONE_RIWL) >> 1;
    wire [RIW_LW-1:0]  med_rank1 = med_len_q >> 1;
    wire [RIW_LW-1:0]  med_rank  = med_pass_q ? med_rank1 : med_rank0;

    reg [5:0] med_cnt_c;
    integer   ci;

    always @(*) begin
        med_cnt_c = 6'd0;
        if (med_which_q == 1'b0) begin
            for (ci = 0; ci < HIST_SLOTS; ci = ci + 1)
                if ((ci[HIST_LW-1:0] < med_len_q[HIST_LW-1:0]) && (hist_q[ci] <= med_try))
                    med_cnt_c = med_cnt_c + 6'd1;
        end else begin
            for (ci = 0; ci < RIW_SLOTS; ci = ci + 1)
                if ((ci[RIW_LW-1:0] < med_len_q) && (riwayat_q[ci] <= med_try))
                    med_cnt_c = med_cnt_c + 6'd1;
        end
    end

    // The count of entries at or below the trial value is monotone in the trial value and
    // at the top of the field it is the window length, which is above either rank, so the
    // largest value whose count is at most the rank is exactly one below the rank-th
    // smallest value. Every value here is at least 4 ms (a positive sample distance
    // shifted left by two, or half of one), so the rank-th smallest value is never zero and
    // the +1 form is exact.
    wire [W_RR_MS-1:0] med_next = (med_cnt_c <= med_rank[5:0]) ? med_try : med_cand_q;
    wire [W_RR_MS-1:0] med_hit  = med_next + ONE_MS;

    // =================================================================== window sums
    reg [W_RR_SUM_L-1:0] d_sum_c;
    reg [W_RR_SUM_L-1:0] a_sum_c;
    reg [W_RR_MS-1:0]    d_over_c;   // the deret slot that a push would overwrite
    reg [W_RR_MS-1:0]    a_over_c;   // the antre slot that a push would overwrite

    always @(*) begin
        d_sum_c  = ZERO_SUM;
        for (ci = 0; ci < HIST_SLOTS; ci = ci + 1)
            if (ci[HIST_LW-1:0] < deret_len_q)
                d_sum_c = d_sum_c + {{(W_RR_SUM_L-W_RR_MS){1'b0}}, deret_q[ci]};
        d_over_c = deret_q[deret_w_q];
    end

    always @(*) begin
        a_sum_c  = ZERO_SUM;
        for (ci = 0; ci < HIST_SLOTS; ci = ci + 1)
            if (ci[HIST_LW-1:0] < antre_len_q)
                a_sum_c = a_sum_c + {{(W_RR_SUM_L-W_RR_MS){1'b0}}, antre_q[ci]};
        a_over_c = antre_q[antre_w_q];
    end

    // =================================================================== mark decision
    // rantai.py:526-559, tested in the model's own order: the false detection first, then
    // the missed beat, and the absolute ceiling only inside the missed beat branch.
    //
    // The rank pair sel_lo_q and sel_hi_q carries two different quantities at two different
    // moments, and both are needed: in PH_APPLY it is the median of the eight-interval
    // rhythm window, which is the reference of the four marks, and in PH_RES2 it is the
    // median of the 32-interval reseed history. The mark is latched into m_rr_mark in
    // PH_APPLY, before the reseed search ever starts, so the reuse is unambiguous.
    wire               ref_ok   = ref_valid_q;
    wire [W_RR_MS-1:0] med_pair_mid = (sel_lo_q + sel_hi_q) >> 1;  // rantai.py:364-372
    wire [W_RR_MS-1:0] ref_w    = med_pair_mid;
    wire [W_RR_MS:0]   drop_lhs = {1'b0, x_q} << 1;
    wire               drop_c   = ref_ok && (drop_lhs < {1'b0, ref_w});
    wire               miss_c   = ref_ok && (scale_ms(x_q, RR_MISS_DEN_L) >
                                             scale_ms(ref_w, RR_MISS_NUM_L));
    wire               gap_c    = miss_c && (x_q > RR_LONG_L);
    wire               split_c  = miss_c && !gap_c;
    wire [1:0]         mark_c   = drop_c  ? MARK_DROP_L  :
                                  (gap_c  ? MARK_GAP_L   :
                                  (split_c ? MARK_SPLIT_L : MARK_KEEP_L));

    // the rhythm window of the marks: 0 pushes for a drop and for a gap (rantai.py:531 and
    // :538 both return without a push), 1 for a keep, 2 for a split into exact halves
    wire [1:0]         hist_push_c  = (drop_c || gap_c) ? 2'd0 : (split_c ? 2'd2 : 2'd1);
    wire [W_RR_MS-1:0] split_first  = x_q >> 1;
    wire [W_RR_MS-1:0] split_second = x_q - split_first;
    wire [W_RR_MS-1:0] hist_p0      = split_c ? split_first : x_q;
    wire [W_RR_MS-1:0] hist_p1      = split_second;
    wire [HIST_W-1:0]  hist_w_n     = hist_w_q + ONE_SLOT;
    // the model pushes one entry for a keep and two for a split, and trims the window to its
    // length afterwards (rantai.py:551-558); a ring writes the two entries of a split and
    // advances the pointer twice, which leaves the pointer at the oldest entry either way
    wire [HIST_W-1:0]  hist_adv     = (hist_push_c == 2'd2) ? HIST_TWO
                                   : ((hist_push_c == 2'd1) ? ONE_SLOT : ZERO_SLOT);
    wire [HIST_W-1:0]  hist_w_next  = hist_w_q + hist_adv;
    wire [HIST_LW-1:0] hist_len_n   = (hist_push_c == 2'd0) ? hist_len_q :
                                      ((hist_push_c == 2'd1)
                                       ? ((hist_len_q == DELAPAN_LEN) ? hist_len_q
                                          : (hist_len_q + ONE_LEN))
                                       : ((hist_len_q >= (DELAPAN_LEN - ONE_LEN))
                                          ? DELAPAN_LEN : (hist_len_q + 2)));

    // =================================================================== locked band
    wire in_band_c = (x_q >= BAND_MIN_L[W_RR_MS-1:0]) && (x_q <= BAND_MAX_L[W_RR_MS-1:0]);

    wire [HIST_LW-1:0]  deret_len_n = (deret_len_q == DELAPAN_LEN) ? deret_len_q
                                      : (deret_len_q + ONE_LEN);
    wire [RIW_LW-1:0]   riw_len_n   = (riwayat_len_q == RIW_SLOTS_L) ? riwayat_len_q
                                      : (riwayat_len_q + ONE_RIWL);
    wire [W_RR_SUM_L-1:0] deret_sum_n = d_sum_c + {{(W_RR_SUM_L-W_RR_MS){1'b0}}, x_q} -
                                      ((deret_len_q == DELAPAN_LEN)
                                       ? {{(W_RR_SUM_L-W_RR_MS){1'b0}}, d_over_c} : ZERO_SUM);
    // ra1 = the sum of the eight queue entries >> 3, rantai.py:399. Eight 16 bit entries sum
    // to at most 8 * 65535 = 524280, which is below 2**19, so the mean never leaves 16 bits.
    // ra1_over_c is the guard that says so and it is checked by the testbench: it is the same
    // shape as the per stage overflow flag D1 asks for.
    wire [W_RR_SUM_L-1:0] ra1_shift  = deret_sum_n >> SHIFT_RA1_L;
    wire                  ra1_over_c = |ra1_shift[W_RR_SUM_L-1:W_RR_MS];
    wire [W_RR_MS-1:0]    ra1_new    = ra1_shift[W_RR_MS-1:0];
    wire deret_full_n = (deret_len_n == DELAPAN_LEN);

    // the band reference of the locked stage: the queue, or the eight-interval mean while
    // the queue is still empty, rantai.py:400-405
    wire                   acuan_from_ra1 = (penyebut_q == 4'd0);
    wire [W_RR_SUM_L-1:0]  acuan_num_c = acuan_from_ra1
                                       ? {{(W_RR_SUM_L-W_RR_MS){1'b0}}, ra1_new}
                                       : a_sum_c;
    wire [3:0]             acuan_den_c = acuan_from_ra1 ? 4'd1 : penyebut_q;
    wire                   lolos_c     = band_ok(x_q, acuan_num_c, acuan_den_c);
    wire [3:0]             gagal_n     = lolos_c ? 4'd0 : (gagal_q + 4'd1);
    wire [JEDA_W-1:0]      jeda_n      = jeda_q + {{(JEDA_W-1){1'b0}}, 1'b1};
    // rantai.py:413, at most one reseed per SEMAI_JEDA intervals, and both counters restart
    wire                   reseed_c    = (gagal_n >= DELAPAN_L[3:0]) &&
                                         (jeda_n >= SEMAI_JEDA_L[JEDA_W-1:0]);

    // the queue after this interval: appended when it passed and no reseed took it over,
    // rantai.py:420-423
    wire [HIST_LW-1:0]     antre_len_n = lolos_c ? ((antre_len_q == DELAPAN_LEN)
                                       ? antre_len_q : (antre_len_q + ONE_LEN))
                                       : antre_len_q;
    wire [W_RR_SUM_L-1:0]  antre_sum_n = lolos_c
        ? (a_sum_c + {{(W_RR_SUM_L-W_RR_MS){1'b0}}, x_q} -
           ((antre_len_q == DELAPAN_LEN)
            ? {{(W_RR_SUM_L-W_RR_MS){1'b0}}, a_over_c} : ZERO_SUM))
        : a_sum_c;

    // menyala: penyebut == 8 and every one of the eight queue slots inside the band of the
    // final queue sum, rantai.py:431-438
    reg menyala_c;
    integer mj;
    always @(*) begin
        menyala_c = 1'b0;
        if ((penyebut_q == DELAPAN_DEN) && (deret_len_q == DELAPAN_LEN)) begin
            menyala_c = 1'b1;
            for (mj = 0; mj < HIST_SLOTS; mj = mj + 1)
                if (!band_ok(deret_q[mj], pembilang_q, penyebut_q)) menyala_c = 1'b0;
        end
    end

    // =================================================================== ra2 division
    // restoring division over DIV_BITS steps, one quotient bit per cycle. The denominator
    // is at most eight and the numerator is the sum of at most eight intervals, so the
    // quotient is at most RR_MAX_MS and the field width of ra2 holds it; quo_over_q is the
    // sticky flag that would say otherwise, and it stays zero on every real record.
    wire [DIV_REM_W-1:0]  div_rem_sh = {div_rem_q, div_num_q[div_bit_q]};
    wire                  div_ge     = (div_rem_sh >= {{(DIV_REM_W-4){1'b0}}, div_den_q});
    wire [DIV_REM_W-1:0]  div_rem_nx = div_ge
                                     ? (div_rem_sh - {{(DIV_REM_W-4){1'b0}}, div_den_q})
                                     : div_rem_sh;
    // the top bit of the shifted remainder is set only if a remainder below the denominator
    // needed five bits, which cannot happen with a denominator of at most eight
    wire                  div_rem_bad = div_rem_nx[DIV_REM_W-1];
    wire [DIV_BITS-1:0]   quo_final  = {div_quo_q, div_ge};

    // =================================================================== sequential body
    integer si;

    always @(posedge clk_i) begin
        if (!rst_ni) begin
            phase_q         <= PH_IDLE;
            qrs_seen_q      <= 1'b0;
            qrs_prev_q      <= {W_IDX{1'b0}};
            beat_idx_q      <= {W_IDX{1'b0}};
            x_q             <= {W_RR_MS{1'b0}};
            smp_q           <= {W_RR_SMP{1'b0}};
            sat_ms_q        <= 1'b0;
            sat_smp_q       <= 1'b0;
            quo_over_q      <= 1'b0;
            interval_ix_q   <= 32'd0;
            for (si = 0; si < HIST_SLOTS; si = si + 1) begin
                hist_q[si]  <= {W_RR_MS{1'b0}};
                deret_q[si] <= {W_RR_MS{1'b0}};
                antre_q[si] <= {W_RR_MS{1'b0}};
            end
            for (si = 0; si < RIW_SLOTS; si = si + 1)
                riwayat_q[si] <= {W_RR_MS{1'b0}};
            hist_w_q        <= {HIST_W{1'b0}};
            hist_len_q      <= {HIST_LW{1'b0}};
            deret_w_q       <= {HIST_W{1'b0}};
            deret_len_q     <= {HIST_LW{1'b0}};
            antre_w_q       <= {HIST_W{1'b0}};
            antre_len_q     <= {HIST_LW{1'b0}};
            riwayat_w_q     <= {RIW_W{1'b0}};
            riwayat_len_q   <= {RIW_LW{1'b0}};
            pembilang_q     <= ZERO_SUM;
            penyebut_q      <= 4'd0;
            ra1_q           <= {W_RR_MS{1'b0}};
            ra2_q           <= {W_RR_MS{1'b0}};
            // rantai.py:353-356, the fail counter starts at zero and the pace counter at
            // SEMAI_JEDA, so the first reseed of a fresh part needs eight failures
            gagal_q         <= 4'd0;
            jeda_q          <= SEMAI_JEDA_L[JEDA_W-1:0];
            step_q          <= 32'd0;
            semai_q         <= 32'd0;
            penanda_q       <= 32'd0;
            med_which_q     <= 1'b0;
            med_len_q       <= {RIW_LW{1'b0}};
            med_pass_q      <= 1'b0;
            med_bit_q       <= MED_BIT_ZERO;
            med_cand_q      <= {W_RR_MS{1'b0}};
            sel_lo_q        <= {W_RR_MS{1'b0}};
            sel_hi_q        <= {W_RR_MS{1'b0}};
            ref_valid_q     <= 1'b0;
            div_num_q       <= ZERO_SUM;
            div_den_q       <= 4'd0;
            div_rem_q       <= {DIV_REM_W-1{1'b0}};
            div_quo_q       <= ZERO_DIV;
            div_bit_q       <= 5'd0;
            in_band_q       <= 1'b0;
            disemai_q       <= 1'b0;
            m_rr_last       <= {W_RR_MS{1'b0}};
            m_rr_mark       <= MARK_KEEP_L;
            m_ev_valid      <= 1'b0;
            m_ev_kind       <= EV_NONE_L;
            m_ev_idx        <= {W_IDX{1'b0}};
            m_ev_val        <= 32'd0;
            d_valid         <= 1'b0;
            d_rr_ms         <= {W_RR_MS{1'b0}};
            d_rr_smp        <= {W_RR_SMP{1'b0}};
            o_rr_long_count <= 32'd0;
            d_beat_val_q    <= 32'd0;
            d_ra1_over_q    <= 1'b0;
            d_div_rem_bad_q <= 1'b0;
            d_step_valid_q  <= 1'b0;
            d_step_ra1_q    <= {W_RR_MS{1'b0}};
            d_step_ra2_q    <= {W_RR_MS{1'b0}};
            d_step_antre_q  <= {HIST_LW{1'b0}};
            d_step_deret_q  <= {HIST_LW{1'b0}};
            d_step_riwayat_q<= {RIW_LW{1'b0}};
            d_step_menyala_q<= 1'b0;
            d_step_disemai_q<= 1'b0;
            d_step_gagal_q  <= 4'd0;
            d_step_jeda_q   <= {JEDA_W{1'b0}};
            d_step_step_q   <= 32'd0;
            d_step_pembilang_q <= ZERO_SUM;
            d_step_penyebut_q  <= 4'd0;
            d_step_inband_q    <= 1'b0;
        end else begin
            // one-cycle defaults for the pulse outputs
            d_valid        <= 1'b0;
            d_step_valid_q <= 1'b0;
            m_ev_valid     <= 1'b0;

            if (i_clear_counters) begin
                o_rr_long_count <= 32'd0;
                d_ra1_over_q    <= 1'b0;
                d_div_rem_bad_q <= 1'b0;
            end

            case (phase_q)
            // ------------------------------------------------------------ wait for a beat
            PH_IDLE: begin
                if (beat_now) begin
                    // s_ev_val carries the peak amplitude of an EV_QRS beat; this stage has
                    // no use for it in the datapath (the interval comes from the two sample
                    // indices) so it is kept as introspection instead of being left dangling
                    d_beat_val_q <= s_ev_val;
                    qrs_seen_q <= 1'b1;
                    qrs_prev_q <= s_ev_idx;
                    if (qrs_seen_q) begin
                        // second and later beat: this beat closes one raw interval
                        beat_idx_q    <= s_ev_idx;
                        x_q           <= rr_word;
                        smp_q         <= smp_word;
                        sat_ms_q      <= sat_ms_q | rr_over;
                        sat_smp_q     <= sat_smp_q | smp_over;
                        interval_ix_q <= interval_ix_q + 32'd1;
                        if (!i_clear_counters && (rr_word > RR_LONG_L))
                            o_rr_long_count <= o_rr_long_count + 32'd1;
                        if (hist_len_q == {HIST_LW{1'b0}}) begin
                            // no reference interval yet: rantai.py:528 gives median([]) = 0
                            ref_valid_q <= 1'b0;
                            sel_lo_q    <= {W_RR_MS{1'b0}};
                            sel_hi_q    <= {W_RR_MS{1'b0}};
                            phase_q     <= PH_APPLY;
                        end else begin
                            ref_valid_q <= 1'b1;
                            med_which_q <= 1'b0;
                            med_len_q   <= {{(RIW_LW-HIST_LW){1'b0}}, hist_len_q};
                            med_pass_q  <= 1'b0;
                            med_bit_q   <= MED_BIT_TOP;
                            med_cand_q  <= {W_RR_MS{1'b0}};
                            phase_q     <= PH_REF;
                        end
                    end
                end
            end
            // ------------------------------------------------------ reference median
            PH_REF: begin
                if (med_bit_q == MED_BIT_ZERO) begin
                    if (med_pass_q == 1'b0) begin
                        sel_lo_q   <= med_hit;
                        med_pass_q <= 1'b1;
                        med_bit_q  <= MED_BIT_TOP;
                        med_cand_q <= {W_RR_MS{1'b0}};
                    end else begin
                        sel_hi_q <= med_hit;
                        phase_q  <= PH_APPLY;
                    end
                end else begin
                    med_cand_q <= med_next;
                    med_bit_q  <= med_bit_q - 5'd1;
                end
            end
            // ------------------------------------------------------ decide and publish
            PH_APPLY: begin
                // the interval word and its mark, published together
                m_rr_last  <= x_q;
                m_rr_mark  <= mark_c;
                d_valid    <= 1'b1;
                d_rr_ms    <= x_q;
                d_rr_smp   <= smp_q;
                m_ev_valid <= 1'b1;
                m_ev_kind  <= EV_RR_L;
                m_ev_idx   <= beat_idx_q;
                m_ev_val   <= {{(32-W_RR_MS){1'b0}}, x_q};
                // the rhythm window of the marks, rantai.py:384-391 and :551-558. A push
                // writes at the pointer; the pair of a split goes to the pointer and to
                // the next slot. A window that is already full replaces its oldest entry,
                // which is the entry at the pointer, and only the multiset matters for the
                // median, so no other slot has to move.
                if (hist_push_c != 2'd0) begin
                    hist_q[hist_w_q] <= hist_p0;
                    if (hist_push_c == 2'd2) hist_q[hist_w_n] <= hist_p1;
                    hist_w_q         <= hist_w_next;
                end
                hist_len_q <= hist_len_n;
                in_band_q  <= in_band_c;
                disemai_q  <= 1'b0;
                if (in_band_c) begin
                    // the eight-interval queue and the 32-interval history, rantai.py:384-391
                    deret_q[deret_w_q]     <= x_q;
                    deret_len_q            <= deret_len_n;
                    deret_w_q              <= deret_w_q + ONE_SLOT;
                    riwayat_q[riwayat_w_q] <= x_q;
                    riwayat_len_q          <= riw_len_n;
                    riwayat_w_q            <= riwayat_w_q + ONE_RIW;
                    ra1_q                  <= deret_full_n ? ra1_new : {W_RR_MS{1'b0}};
                    if (deret_full_n) d_ra1_over_q <= d_ra1_over_q | ra1_over_c;
                    if (deret_full_n) begin
                        // rantai.py:399-413
                        gagal_q <= gagal_n;
                        jeda_q  <= jeda_n;
                        if (reseed_c) begin
                            // rantai.py:413-419: the median of the history, which already
                            // carries this interval at :388-391
                            med_which_q <= 1'b1;
                            med_len_q   <= riw_len_n;
                            med_pass_q  <= 1'b0;
                            med_bit_q   <= MED_BIT_TOP;
                            med_cand_q  <= {W_RR_MS{1'b0}};
                            phase_q     <= PH_RES;
                        end else begin
                            // rantai.py:420-426
                            pembilang_q <= antre_sum_n;
                            penyebut_q  <= antre_len_n;
                            div_num_q   <= antre_sum_n;
                            div_den_q   <= antre_len_n;
                            div_rem_q   <= {DIV_REM_W-1{1'b0}};
                            div_quo_q   <= ZERO_DIV;
                            if (lolos_c) begin
                                antre_q[antre_w_q] <= x_q;
                                antre_len_q        <= antre_len_n;
                                antre_w_q          <= antre_w_q + ONE_SLOT;
                            end
                            if (antre_len_n == {HIST_LW{1'b0}}) begin
                                // rantai.py:426, an empty queue falls back on ra1
                                ra2_q   <= ra1_new;
                                phase_q <= PH_COMMIT;
                            end else begin
                                div_bit_q <= DIV_BIT_TOP;
                                phase_q   <= PH_DIV;
                            end
                        end
                    end else begin
                        phase_q <= PH_COMMIT;
                    end
                end else begin
                    phase_q <= PH_IDLE;
                end
            end
            // ------------------------------------------------------ ra2 division
            PH_DIV: begin
                // the top bit of div_rem_nx is dropped on purpose: after the subtraction the
                // remainder is below the denominator, so it always fits the four bits left
                div_rem_q <= div_rem_nx[DIV_REM_W-2:0];
                d_div_rem_bad_q <= d_div_rem_bad_q | div_rem_bad;
                div_quo_q <= {div_quo_q[DIV_BITS-3:0], div_ge};
                if (div_bit_q == 5'd0) begin
                    // the quotient of the last step also carries the decision of that step
                    ra2_q      <= quo_final[W_RR_MS-1:0];
                    quo_over_q <= quo_over_q | (|quo_final[DIV_BITS-1:W_RR_MS]);
                    phase_q    <= PH_COMMIT;
                end else begin
                    div_bit_q <= div_bit_q - 5'd1;
                end
            end
            // ------------------------------------------------------ reseed median
            PH_RES: begin
                if (med_bit_q == MED_BIT_ZERO) begin
                    if (med_pass_q == 1'b0) begin
                        sel_lo_q   <= med_hit;
                        med_pass_q <= 1'b1;
                        med_bit_q  <= MED_BIT_TOP;
                        med_cand_q <= {W_RR_MS{1'b0}};
                    end else begin
                        sel_hi_q <= med_hit;
                        phase_q  <= PH_RES2;
                    end
                end else begin
                    med_cand_q <= med_next;
                    med_bit_q  <= med_bit_q - 5'd1;
                end
            end
            // ------------------------------------------------------ reseed fill
            PH_RES2: begin
                // rantai.py:414-419: the queue becomes the median eight times over, both
                // counters restart, and the rational mean of eight equal entries is the
                // median itself
                for (si = 0; si < HIST_SLOTS; si = si + 1)
                    antre_q[si] <= med_pair_mid;
                pembilang_q <= (med_pair_mid * DELAPAN_L[W_RR_SUM_L-1:0]);
                penyebut_q  <= DELAPAN_DEN;
                antre_len_q <= DELAPAN_LEN;
                ra2_q       <= med_pair_mid;
                semai_q     <= semai_q + 32'd1;
                gagal_q     <= 4'd0;
                jeda_q      <= {JEDA_W{1'b0}};
                disemai_q   <= 1'b1;
                phase_q     <= PH_COMMIT;
            end
            // ------------------------------------------------------ commit
            PH_COMMIT: begin
                step_q    <= step_q + 32'd1;
                penanda_q <= penanda_q + {{31{1'b0}}, menyala_c};
                d_step_valid_q     <= 1'b1;
                d_step_ra1_q       <= ra1_q;
                d_step_ra2_q       <= ra2_q;
                d_step_antre_q     <= penyebut_q;
                d_step_deret_q     <= deret_len_q;
                d_step_riwayat_q   <= riwayat_len_q;
                d_step_menyala_q   <= menyala_c;
                d_step_disemai_q   <= disemai_q;
                d_step_gagal_q     <= gagal_q;
                d_step_jeda_q      <= jeda_q;
                d_step_step_q      <= step_q + 32'd1;
                d_step_pembilang_q <= pembilang_q;
                d_step_penyebut_q  <= penyebut_q;
                d_step_inband_q    <= in_band_q;
                phase_q            <= PH_IDLE;
            end
            default: phase_q <= PH_IDLE;
            endcase

            // the window boundary and the lost-sample marker ride the event sideband on
            // the cycle they arrive; an interval event is published by PH_APPLY and that
            // cycle belongs to the interval, not to the passthrough
            if (phase_q != PH_APPLY) begin
                if (win_now) begin
                    m_ev_valid <= 1'b1;
                    m_ev_kind  <= EV_WINDOW_L;
                    m_ev_idx   <= s_sample_idx;
                    m_ev_val   <= interval_ix_q;
                end else if (gap_now) begin
                    m_ev_valid <= 1'b1;
                    m_ev_kind  <= EV_GAP_L;
                    m_ev_idx   <= s_sample_idx;
                    m_ev_val   <= 32'd0;
                end
            end
        end
    end

endmodule

`default_nettype wire
