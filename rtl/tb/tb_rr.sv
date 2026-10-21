// ---------------------------------------------------------------------------
// tb_rr.sv -- gate for rtl/rr_series.sv, plan doc 38 phase 6.
//
// Three phases, one run, every expected value read from a golden file:
//
// Phase A, the golden record. The stimulus is the QRS series of the frozen fixture, and it
//   comes from rtlplan2/fase5/04015.peaks.csv through rtl/tb/vektor/fase6/
//   siapkan_vektor_fase6.py: the qrs_sample_index column, one word per beat, in file order.
//   peak_detect is NOT instantiated here on purpose: it is being written by the Fase 5
//   worker at the same time as this file, so driving this stage from its output would make
//   both gates meaningless. Every expectation comes from the golden columns:
//     intervals   d_rr_ms and m_rr_last against 04015.rr.hex (2595 rows of rr_ms)
//                 d_rr_smp against 04015.rr.smp.hex (qrs_cur_sample - qrs_prev_sample)
//                 m_rr_mark against 04015.rr.mark.hex, and its one hot form against
//                 04015.rr.mask.hex, which is what the four columns mark_keep, mark_split,
//                 mark_drop and mark_gap of the golden CSV carry
//     steps       the per-step state of the locked stage against the 2586 rows of
//                 04015.rrstep.*.hex: ra1, ra2, the queue length, menyala, disemai, the
//                 history length, the fail counter, the pace counter and the interval that
//                 drove the step
//     counts      the totals against 04015.fase6.counts.hex, which is anchored on the
//                 manifest of Fase 5 (langkah 2586, semai 26, penanda 1202, census 2186,
//                 397, 9, 3)
//     beats       d_beat_val_q, the amplitude word this stage receives on the event
//                 sideband, against the envelope_value column of the same QRS rows
//
// Phase B, the queue length gate of the plan, "the queue length exactly 8 after step 24", on
//   a synthetic constant train: 40 beats a constant number of samples apart. The expected
//   queue length after each step is arithmetic on the package constants and the spacing, so
//   nothing here is a measured number, and the phase prints the queue length at step 24 and
//   at every step after it.
//
// Phase C, the passthrough and the counters: one cycle with the lost sample marker bit set
//   must raise exactly one EV_GAP, one cycle with s_tlast must raise exactly one EV_WINDOW,
//   and i_clear_counters must clear o_rr_long_count.
//
// Golden data: +VECTOR=<dir> is required and holds the Fase 6 hex directory. Optional
//   +LIMIT=<n> feeds only the first n beats; the expected interval and step counts are then
//   recomputed from the golden columns, so a short run is still a real gate, except for the
//   end of run counters, which are marked not checked on a short run.
//
// Introspection: the per-step state of the locked stage has no port in the frozen port list
//   of rtl/rr_series.sv, so this file reads the d_step_* registers and phase_q through a
//   hierarchical reference, the same white box read tb_kuantisasi.sv makes of dut.pre_raw. A
//   beat is only offered while the DUT is idle, so no event is ever dropped.
//
// No file level timescale, same reason as the other testbenches: the package carries none
//   and Verilator raises TIMESCALEMOD on a file level timescale here.
//
// House style: expected values come from the golden column or from the package constants,
//   never typed here. Every gate violation raises $fatal(1, ...) so the exit status can
//   never read as a pass, and a PASS with zero rows compared is a failure.
// ---------------------------------------------------------------------------
`default_nettype none

module tb_rr;

    // ------------------------------------------------------- package constants, aliased
    localparam int unsigned W_RR_MS    = afib_lite_pkg::W_RR_MS;
    localparam int unsigned W_RR_SMP   = afib_lite_pkg::W_RR_SMP;
    localparam int unsigned W_IDX      = afib_lite_pkg::W_IDX;
    localparam int unsigned W_TUSER    = afib_lite_pkg::W_TUSER;
    localparam int unsigned W_EVKIND   = afib_lite_pkg::W_EVKIND;
    localparam integer DELAPAN    = afib_lite_pkg::DELAPAN;         // 8
    localparam [31:0]  DELAPAN32   = afib_lite_pkg::DELAPAN;         // the same word, zero extended
    localparam integer SEMAI_JEDA = afib_lite_pkg::SEMAI_JEDA;      // 8
    localparam integer BAND_LO    = afib_lite_pkg::RR_BAND_MIN_MS;  // 250
    localparam integer BAND_HI    = afib_lite_pkg::RR_BAND_MAX_MS;  // 2000
    localparam integer RR_LONG_L  = {{16{1'b0}}, afib_lite_pkg::RR_LONG_MS};   // 3000
    localparam integer TU_GAP     = afib_lite_pkg::TU_GAP;
    localparam [1:0] MARK_KEEP_B  = afib_lite_pkg::RR_MARK_KEEP;
    localparam [1:0] MARK_SPLIT_B = afib_lite_pkg::RR_MARK_SPLIT;
    localparam [1:0] MARK_DROP_B  = afib_lite_pkg::RR_MARK_DROP;
    localparam [1:0] MARK_GAP_B   = afib_lite_pkg::RR_MARK_GAP;
    localparam [W_EVKIND-1:0] EV_QRS_B    = afib_lite_pkg::EV_QRS;
    localparam [W_EVKIND-1:0] EV_RR_B     = afib_lite_pkg::EV_RR;
    localparam [W_EVKIND-1:0] EV_WINDOW_B = afib_lite_pkg::EV_WINDOW;
    localparam [W_EVKIND-1:0] EV_GAP_B    = afib_lite_pkg::EV_GAP;

    // golden row counts. They are not measured results: every one of them is checked against
    // the counts column of the golden vector directory before the run uses it, so a stale
    // bound here turns into a fatal instead of a silent partial pass.
    localparam integer N_QRS  = 2596;   // QRS beats of 04015, peaks.csv qrs_sample_index
    localparam integer N_IQ   = 2595;   // raw RR intervals
    localparam integer N_STEP = 2586;   // in-band intervals, the model's langkah
    localparam integer N_CNT  = 16;     // counts words written by the vector helper

    // poll bounds, not expected values: a slot that takes longer than this is reported as a
    // mismatch instead of looping forever
    localparam integer SLOT_MAX   = 4096;
    localparam integer NOEVT_MAX  = 400;    // an out-of-band interval must commit no step
    localparam integer DRAIN_MAX  = 4096;

    // synthetic train of phase B, a stimulus choice and not a result
    localparam integer TRAIN_N     = 40;
    localparam integer SPACING_SMP = 200;                 // samples between synthetic beats
    localparam integer RR_EXP      = SPACING_SMP * 4;     // the relation of rantai.py:632
    localparam integer LONG_SMP    = 1200;                // a spacing past the gap ceiling
    localparam integer RR_LONG_EXP = LONG_SMP * 4;
    localparam integer LONG_N      = 3;                   // beats offered at that spacing

    localparam [2:0] PH_IDLE_D = 3'd0;   // the DUT phase encoding, for polling only

    reg clk = 1'b0;
    reg rst_n;
    reg i_enable;
    reg i_clear_counters;

    reg  s_tvalid;
    reg  s_tlast;
    reg  [W_TUSER-1:0] s_tuser;
    reg  [W_IDX-1:0]   s_sample_idx;

    reg  s_ev_valid;
    reg  [W_EVKIND-1:0] s_ev_kind;
    reg  [W_IDX-1:0]   s_ev_idx;
    reg  [31:0]        s_ev_val;

    wire [W_RR_MS-1:0]  m_rr_last;
    wire [1:0]          m_rr_mark;
    wire                m_ev_valid;
    wire [W_EVKIND-1:0] m_ev_kind;
    wire [W_IDX-1:0]    m_ev_idx;
    wire [31:0]         m_ev_val;
    wire                d_valid;
    wire [W_RR_MS-1:0]  d_rr_ms;
    wire [W_RR_SMP-1:0] d_rr_smp;
    wire [31:0]         o_rr_long_count;

    rr_series u_dut (
        .clk_i            (clk),
        .rst_ni           (rst_n),
        .i_enable         (i_enable),
        .i_clear_counters (i_clear_counters),
        .s_tvalid         (s_tvalid),
        .s_tlast          (s_tlast),
        .s_tuser          (s_tuser),
        .s_sample_idx     (s_sample_idx),
        .s_ev_valid       (s_ev_valid),
        .s_ev_kind        (s_ev_kind),
        .s_ev_idx         (s_ev_idx),
        .s_ev_val         (s_ev_val),
        .m_rr_last        (m_rr_last),
        .m_rr_mark        (m_rr_mark),
        .m_ev_valid       (m_ev_valid),
        .m_ev_kind        (m_ev_kind),
        .m_ev_idx         (m_ev_idx),
        .m_ev_val         (m_ev_val),
        .d_valid          (d_valid),
        .d_rr_ms          (d_rr_ms),
        .d_rr_smp         (d_rr_smp),
        .o_rr_long_count  (o_rr_long_count)
    );

    always #5 clk <= ~clk;   // 10 ns, 100 MHz, the PL clock of doc 36 3.1

    // event monitor: every published event is counted once, in the cycle it is visible, so
    // the per phase gates never depend on how long a poll loop happens to stand in a cycle
    reg     mon_en;
    integer m_ev_rr, m_ev_win, m_ev_gap, m_ev_other;

    always @(posedge clk) begin
        if (mon_en && m_ev_valid) begin
            case (m_ev_kind)
                EV_RR_B:     m_ev_rr    <= m_ev_rr + 1;
                EV_WINDOW_B: m_ev_win   <= m_ev_win + 1;
                EV_GAP_B:    m_ev_gap   <= m_ev_gap + 1;
                default:     m_ev_other <= m_ev_other + 1;
            endcase
        end
    end

    // ------------------------------------------------------- golden storage
    reg [31:0] mem_qrs  [0:N_QRS-1];
    reg [31:0] mem_qval [0:N_QRS-1];
    reg [31:0] mem_rr   [0:N_IQ-1];
    reg [31:0] mem_smp  [0:N_IQ-1];
    reg [31:0] mem_mark [0:N_IQ-1];
    reg [31:0] mem_mask [0:N_IQ-1];
    reg [31:0] mem_ra1     [0:N_STEP-1];
    reg [31:0] mem_ra2     [0:N_STEP-1];
    reg [31:0] mem_antre   [0:N_STEP-1];
    reg [31:0] mem_menyala [0:N_STEP-1];
    reg [31:0] mem_disemai [0:N_STEP-1];
    reg [31:0] mem_riwayat [0:N_STEP-1];
    reg [31:0] mem_gagal   [0:N_STEP-1];
    reg [31:0] mem_jeda    [0:N_STEP-1];
    reg [31:0] mem_stprr   [0:N_STEP-1];
    reg [31:0] mem_cnt  [0:N_CNT-1];

    reg [1023:0] vdir;
    reg [1023:0] f_tmp;

    integer limit_n;
    integer beats_fed;
    integer n_int;
    integer wcnt;
    integer step_pulse;
    integer bi, ei;
    integer poll_timeout;

    integer mism_rr, mism_last, mism_smp, mism_mark, mism_mask, mism_evkind,
            mism_evidx, mism_evval, mism_beatval, mism_stprr;
    integer mism_ra1, mism_ra2, mism_antre, mism_menyala, mism_disemai,
            mism_riwayat, mism_gagal, mism_jeda, mism_stepid, mism_deret;
    integer mism_int_total, mism_step_total, mism_total;

    integer mark_census [0:3];
    integer last_not_full;
    integer gold_q_after24_bad;
    integer steps_seen;
    integer step_rows_cmp;
    integer n_valid_pulse;
    integer ev_rr, ev_window, ev_other;   // phase A snapshots of the monitor
    integer c_gap, c_window;              // phase C snapshots of the monitor
    reg [31:0] deret_expected;
    reg [31:0] tr_len_seen;
    reg [31:0] tr_glen;
    integer golden_masked;
    integer unknown_words;

    // synthetic phase B
    integer tr_steps, tr_full_first, tr_mism, tr_q24;
    // end of run counters of phase A, latched before the later phases reset the DUT: the
    // later phases drive their own stimulus and would otherwise overwrite these totals
    integer a_step, a_semai, a_penanda, a_long;
    // synthetic phase C
    integer long_want, long_seen, pre_seen, pre_ref, pre_n;
    integer a32, b32, c32, d32, e32;
    localparam integer RR_MISS_NUM = 83;   // rantai.py:534, 83/50 of the reference median
    localparam integer RR_MISS_DEN = 50;   // rantai.py:498-499; the package carries no name
    integer tr_q_after24_bad, tr_ra1_mism, tr_menyala_mism;

    initial begin
        limit_n = N_QRS;
        mism_rr = 0; mism_last = 0; mism_smp = 0; mism_mark = 0; mism_mask = 0;
        mism_evkind = 0; mism_evidx = 0; mism_evval = 0; mism_beatval = 0; mism_stprr = 0;
        mism_ra1 = 0; mism_ra2 = 0; mism_antre = 0; mism_menyala = 0; mism_disemai = 0;
        mism_riwayat = 0; mism_gagal = 0; mism_jeda = 0; mism_stepid = 0; mism_deret = 0;
        mism_int_total = 0; mism_step_total = 0; mism_total = 0;
        beats_fed = 0; n_int = 0; poll_timeout = 0;
        n_valid_pulse = 0; ev_rr = 0; ev_window = 0; ev_other = 0;
        c_gap = 0; c_window = 0;
        mon_en = 1'b0; m_ev_rr = 0; m_ev_win = 0; m_ev_gap = 0; m_ev_other = 0;
        steps_seen = 0; step_rows_cmp = 0;
        last_not_full = 0; gold_q_after24_bad = 0; golden_masked = 0;
        tr_steps = 0; tr_glen = 0; tr_full_first = 0; tr_len_seen = 0;
        tr_mism = 0; tr_q24 = 0; tr_q_after24_bad = 0; tr_ra1_mism = 0; tr_menyala_mism = 0;
        a_step = 0; a_semai = 0; a_penanda = 0; a_long = 0; unknown_words = 0;
        long_want = 0; long_seen = 0; pre_seen = 0; pre_ref = 0; pre_n = 0;
        a32 = 0; b32 = 0; c32 = 0; d32 = 0; e32 = 0;
        for (ei = 0; ei < 4; ei = ei + 1) mark_census[ei] = 0;

        if (!$value$plusargs("VECTOR=%s", vdir))
            $fatal(1, "tb_rr: FAIL no +VECTOR (want the Fase 6 vector directory)");
        if ($value$plusargs("LIMIT=%d", limit_n)) begin
            if (limit_n > N_QRS) limit_n = N_QRS;
            if (limit_n < 2) limit_n = 2;
            $display("tb_rr: short run, +LIMIT=%0d beats", limit_n);
        end

        $sformat(f_tmp, "%0s/04015.fase6.counts.hex", vdir); $readmemh(f_tmp, mem_cnt);
        $sformat(f_tmp, "%0s/04015.qrs.hex",           vdir); $readmemh(f_tmp, mem_qrs);
        $sformat(f_tmp, "%0s/04015.qrsval.hex",        vdir); $readmemh(f_tmp, mem_qval);
        $sformat(f_tmp, "%0s/04015.rr.hex",            vdir); $readmemh(f_tmp, mem_rr);
        $sformat(f_tmp, "%0s/04015.rr.smp.hex",        vdir); $readmemh(f_tmp, mem_smp);
        $sformat(f_tmp, "%0s/04015.rr.mark.hex",       vdir); $readmemh(f_tmp, mem_mark);
        $sformat(f_tmp, "%0s/04015.rr.mask.hex",       vdir); $readmemh(f_tmp, mem_mask);
        $sformat(f_tmp, "%0s/04015.rrstep.ra1.hex",     vdir); $readmemh(f_tmp, mem_ra1);
        $sformat(f_tmp, "%0s/04015.rrstep.ra2.hex",     vdir); $readmemh(f_tmp, mem_ra2);
        $sformat(f_tmp, "%0s/04015.rrstep.antre.hex",   vdir); $readmemh(f_tmp, mem_antre);
        $sformat(f_tmp, "%0s/04015.rrstep.menyala.hex", vdir); $readmemh(f_tmp, mem_menyala);
        $sformat(f_tmp, "%0s/04015.rrstep.disemai.hex", vdir); $readmemh(f_tmp, mem_disemai);
        $sformat(f_tmp, "%0s/04015.rrstep.riwayat.hex", vdir); $readmemh(f_tmp, mem_riwayat);
        $sformat(f_tmp, "%0s/04015.rrstep.gagal.hex",   vdir); $readmemh(f_tmp, mem_gagal);
        $sformat(f_tmp, "%0s/04015.rrstep.jeda.hex",    vdir); $readmemh(f_tmp, mem_jeda);
        $sformat(f_tmp, "%0s/04015.rrstep.rr.hex",      vdir); $readmemh(f_tmp, mem_stprr);

        $display("== tb_rr, Fase 6, record 04015 ==");
        $display("tb_rr: vectors = %0s", vdir);

        // A column that could not be read is unknown, and an unknown compared with an unknown
        // is not a mismatch under the case inequality this file is required to use, so a
        // missing or truncated vector file would otherwise read as a pass with full row
        // counts. Every word of every column must be defined before it is used as the oracle.
        for (ei = 0; ei < N_QRS; ei = ei + 1) begin
            if ($isunknown(mem_qrs[ei]))  unknown_words = unknown_words + 1;
            if ($isunknown(mem_qval[ei])) unknown_words = unknown_words + 1;
        end
        for (ei = 0; ei < N_IQ; ei = ei + 1) begin
            if ($isunknown(mem_rr[ei]))   unknown_words = unknown_words + 1;
            if ($isunknown(mem_smp[ei]))  unknown_words = unknown_words + 1;
            if ($isunknown(mem_mark[ei])) unknown_words = unknown_words + 1;
            if ($isunknown(mem_mask[ei])) unknown_words = unknown_words + 1;
        end
        for (ei = 0; ei < N_STEP; ei = ei + 1) begin
            if ($isunknown(mem_ra1[ei]))     unknown_words = unknown_words + 1;
            if ($isunknown(mem_ra2[ei]))     unknown_words = unknown_words + 1;
            if ($isunknown(mem_antre[ei]))   unknown_words = unknown_words + 1;
            if ($isunknown(mem_menyala[ei])) unknown_words = unknown_words + 1;
            if ($isunknown(mem_disemai[ei])) unknown_words = unknown_words + 1;
            if ($isunknown(mem_riwayat[ei])) unknown_words = unknown_words + 1;
            if ($isunknown(mem_gagal[ei]))   unknown_words = unknown_words + 1;
            if ($isunknown(mem_jeda[ei]))    unknown_words = unknown_words + 1;
            if ($isunknown(mem_stprr[ei]))   unknown_words = unknown_words + 1;
        end
        for (ei = 0; ei < N_CNT; ei = ei + 1)
            if ($isunknown(mem_cnt[ei])) unknown_words = unknown_words + 1;
        if (unknown_words != 0)
            $fatal(1, "tb_rr: FAIL %0d golden words are unknown, the vector directory is missing, short or unreadable",
                   unknown_words);
        $display("tb_rr: every golden word is defined (%0d columns read)",
                 (2*N_QRS) + (4*N_IQ) + (9*N_STEP) + N_CNT);

        // the golden counts are the anchor: a stale array bound is a fatal here
        if ((mem_cnt[0] !== N_IQ) || (mem_cnt[6] !== N_QRS) || (mem_cnt[7] !== N_STEP))
            $fatal(1, "tb_rr: FAIL golden counts %0d/%0d/%0d do not match the bounds %0d/%0d/%0d",
                   mem_cnt[0], mem_cnt[6], mem_cnt[7], N_IQ, N_QRS, N_STEP);
        $display("tb_rr: golden intervals %0d, beats %0d, steps %0d",
                 mem_cnt[0], mem_cnt[6], mem_cnt[7]);
        $display("tb_rr: golden census keep/split/drop/gap = %0d/%0d/%0d/%0d, corrected entries %0d",
                 mem_cnt[2], mem_cnt[3], mem_cnt[4], mem_cnt[5], mem_cnt[1]);
        $display("tb_rr: golden queue not full through step %0d, queue at step 25 = %0d",
                 mem_cnt[10], mem_cnt[11]);

        // the golden columns have to agree with each other before they are used as the oracle
        for (ei = 0; ei < N_IQ; ei = ei + 1) begin
            if (mem_mask[ei] !== (32'd1 << mem_mark[ei]))
                $fatal(1, "tb_rr: FAIL the golden mask is not the one hot form of the mark at %0d", ei);
            if (mem_rr[ei] === 32'd0)
                $fatal(1, "tb_rr: FAIL golden interval %0d is zero", ei);
        end
        for (ei = 0; ei < N_STEP; ei = ei + 1) begin
            if ((mem_stprr[ei] < BAND_LO) || (mem_stprr[ei] > BAND_HI))
                $fatal(1, "tb_rr: FAIL golden step %0d carries an out of band interval %0d",
                       ei + 1, mem_stprr[ei]);
            if (mem_antre[ei] > DELAPAN)
                $fatal(1, "tb_rr: FAIL golden step %0d has a queue longer than %0d",
                       ei + 1, DELAPAN);
        end
        $display("tb_rr: golden columns consistent (mask one hot, step intervals in band)");

        // ------------------------------------------------------------------ phase A
        reset_dut(8);
        mon_reset;
        $display("tb_rr: phase A, golden QRS series, %0d beats offered", limit_n);

        for (bi = 0; bi < limit_n; bi = bi + 1) begin
            feed_beat(mem_qrs[bi][W_IDX-1:0], mem_qval[bi], (bi == (limit_n - 1)));
            beats_fed = beats_fed + 1;
            if (bi == 0) begin
                // the first beat only seeds the previous position, it closes no interval
                if (d_valid) begin
                    $display("MISM an interval was published for the very first beat");
                    mism_int_total = mism_int_total + 1;
                end
            end else begin
            wait_interval;
            if (d_valid === 1'b1) begin
                n_valid_pulse = n_valid_pulse + 1;
                if (d_rr_ms !== mem_rr[bi-1][W_RR_MS-1:0]) begin
                    mism_rr = mism_rr + 1;
                    if (mism_rr < 5)
                        $display("MISM interval=%0d d_rr_ms dut=%0d gold=%0d",
                                 bi-1, d_rr_ms, mem_rr[bi-1]);
                end
                if (m_rr_last !== mem_rr[bi-1][W_RR_MS-1:0]) begin
                    mism_last = mism_last + 1;
                    if (mism_last < 5)
                        $display("MISM interval=%0d m_rr_last dut=%0d gold=%0d",
                                 bi-1, m_rr_last, mem_rr[bi-1]);
                end
                if (d_rr_smp !== mem_smp[bi-1][W_RR_SMP-1:0]) begin
                    mism_smp = mism_smp + 1;
                    if (mism_smp < 5)
                        $display("MISM interval=%0d d_rr_smp dut=%0d gold=%0d",
                                 bi-1, d_rr_smp, mem_smp[bi-1]);
                end
                if (m_rr_mark !== mem_mark[bi-1][1:0]) begin
                    mism_mark = mism_mark + 1;
                    if (mism_mark < 5)
                        $display("MISM interval=%0d m_rr_mark dut=%0d gold=%0d",
                                 bi-1, m_rr_mark, mem_mark[bi-1]);
                end
                if (!((m_rr_mark === MARK_KEEP_B) || (m_rr_mark === MARK_SPLIT_B) ||
                      (m_rr_mark === MARK_DROP_B) || (m_rr_mark === MARK_GAP_B))) begin
                    // the golden column only ever carries those four codes
                    mism_mask = mism_mask + 1;
                end else begin
                    mark_census[m_rr_mark] = mark_census[m_rr_mark] + 1;
                end
                if (m_ev_kind !== EV_RR_B)               mism_evkind = mism_evkind + 1;
                if (m_ev_idx !== mem_qrs[bi][W_IDX-1:0]) mism_evidx  = mism_evidx + 1;
                if (m_ev_val !== mem_rr[bi-1])           mism_evval  = mism_evval + 1;
                n_int = n_int + 1;

                if ((mem_rr[bi-1] >= BAND_LO) && (mem_rr[bi-1] <= BAND_HI)) begin
                    // the locked stage runs, so a step commit must follow
                    wait_step(SLOT_MAX, step_pulse);
                    if (step_pulse == 0) begin
                        $display("MISM step commit missing for interval=%0d rr=%0d",
                                 bi-1, mem_rr[bi-1]);
                        mism_stepid = mism_stepid + 1;
                    end else begin
                        steps_seen = steps_seen + 1;
                        check_step(steps_seen - 1, mem_rr[bi-1]);
                        step_rows_cmp = step_rows_cmp + 1;
                    end
                end else begin
                    // out of band: no step may be committed, so the poll has to time out
                    wait_step(NOEVT_MAX, step_pulse);
                    if (step_pulse == 1) begin
                        $display("MISM a step commit for the out-of-band interval=%0d rr=%0d",
                                 bi-1, mem_rr[bi-1]);
                        mism_stepid = mism_stepid + 1;
                    end
                end
            end
            end
        end

        // drain: the last interval may still be committing
        wcnt = 0;
        while ((u_dut.phase_q !== PH_IDLE_D) && (wcnt < DRAIN_MAX)) begin
            @(posedge clk);
            #1;
            wcnt = wcnt + 1;
        end

        ev_rr     = m_ev_rr;
        ev_window = m_ev_win;
        ev_other  = m_ev_other;
        mon_en    = 1'b0;
        a_step    = u_dut.step_q;
        a_semai   = u_dut.semai_q;
        a_penanda = u_dut.penanda_q;
        a_long    = o_rr_long_count;

        for (ei = 0; ei < N_STEP; ei = ei + 1) begin
            if (mem_antre[ei] != DELAPAN) last_not_full = ei + 1;
            if ((ei + 1) > 24)
                if (mem_antre[ei] != DELAPAN) gold_q_after24_bad = gold_q_after24_bad + 1;
        end
        if (mem_antre[23] == DELAPAN) golden_masked = golden_masked + 1;

        mism_int_total  = mism_rr + mism_last + mism_smp + mism_mark + mism_mask +
                          mism_evkind + mism_evidx + mism_evval + mism_beatval + mism_stprr;
        mism_step_total = mism_ra1 + mism_ra2 + mism_antre + mism_menyala + mism_disemai +
                          mism_riwayat + mism_gagal + mism_jeda + mism_stepid + mism_deret;

        $display("tb_rr: beats offered = %0d", beats_fed);
        $display("tb_rr: intervals published = %0d", n_valid_pulse);
        $display("tb_rr: intervals compared = %0d", n_int);
        $display("tb_rr: interval mismatches = %0d out of %0d", mism_int_total, n_int);
        $display("tb_rr: steps committed = %0d", steps_seen);
        $display("tb_rr: step rows compared = %0d", step_rows_cmp);
        $display("tb_rr: step mismatches = %0d out of %0d", mism_step_total, step_rows_cmp);
        $display("tb_rr: rr_ms=%0d m_rr_last=%0d sample distance=%0d mismatches",
                 mism_rr, mism_last, mism_smp);
        $display("tb_rr: mark=%0d mask out of range=%0d event kind/idx/val=%0d/%0d/%0d",
                 mism_mark, mism_mask, mism_evkind, mism_evidx, mism_evval);
        $display("tb_rr: beat amplitude mismatch = %0d", mism_beatval);
        $display("tb_rr: ra1/ra2/queue/menyala/disemai mismatch = %0d/%0d/%0d/%0d/%0d",
                 mism_ra1, mism_ra2, mism_antre, mism_menyala, mism_disemai);
        $display("tb_rr: history/fail/pace/step index mismatch = %0d/%0d/%0d/%0d",
                 mism_riwayat, mism_gagal, mism_jeda, mism_stepid);
        $display("tb_rr: eight window length mismatch = %0d", mism_deret);
        $display("tb_rr: mark census dut = %0d %0d %0d %0d",
                 mark_census[0], mark_census[1], mark_census[2], mark_census[3]);
        $display("tb_rr: mark census gold = %0d %0d %0d %0d",
                 mem_cnt[2], mem_cnt[3], mem_cnt[4], mem_cnt[5]);
        $display("tb_rr: events rr=%0d window=%0d other=%0d",
                 ev_rr, ev_window, ev_other);
        $display("tb_rr: golden queue length at step 24 = %0d, at step 25 = %0d, last step not full = %0d",
                 mem_antre[23], mem_antre[24], last_not_full);
        $display("tb_rr: golden steps after 24 whose queue is not full = %0d, queue full at step 24 = %0d",
                 gold_q_after24_bad, golden_masked);
        $display("tb_rr: o_rr_long_count = %0d, golden intervals above the ceiling = %0d",
                 o_rr_long_count, mem_cnt[12]);
        $display("tb_rr: end of run counters: steps = %0d, reseeds = %0d, menyala total = %0d",
                 a_step, a_semai, a_penanda);
        $display("tb_rr: sa flags: ms sat %0d, smp sat %0d, quotient over %0d, ra1 over %0d, remainder over %0d",
                 u_dut.sat_ms_q, u_dut.sat_smp_q, u_dut.quo_over_q,
                 u_dut.d_ra1_over_q, u_dut.d_div_rem_bad_q);
        $display("tb_rr: poll timeouts = %0d", poll_timeout);

        // ------------------------------------------------------------------ phase B
        $display("tb_rr: phase B, constant train, %0d beats at %0d samples = %0d ms",
                 TRAIN_N, SPACING_SMP, RR_EXP);
        if ((RR_EXP < BAND_LO) || (RR_EXP > BAND_HI))
            $fatal(1, "tb_rr: FAIL the synthetic spacing is outside the locked band");
        reset_dut(4);
        for (bi = 0; bi < TRAIN_N; bi = bi + 1) begin
            feed_beat(bi * SPACING_SMP, 32'd0, 1'b0);
            if (bi != 0) begin
            wait_interval;
            wait_step(SLOT_MAX, step_pulse);
            if (step_pulse == 0)
                $fatal(1, "tb_rr: FAIL no step commit on the synthetic train at beat %0d", bi);
            tr_steps = tr_steps + 1;
            tr_glen = {{28{1'b0}}, u_dut.d_step_antre_q};
            // expected queue length: empty through step DELAPAN-1, then one accepted entry
            // per step, and full from step (DELAPAN-1)+DELAPAN = 15 on
            tr_len_seen = (tr_steps <= (DELAPAN - 1)) ? 0 :
                          ((tr_steps >= ((DELAPAN - 1) + DELAPAN)) ? DELAPAN
                           : (tr_steps - (DELAPAN - 1)));
            if (tr_glen !== tr_len_seen) begin
                tr_mism = tr_mism + 1;
                if (tr_mism < 5)
                    $display("MISM train queue step=%0d dut=%0d want=%0d",
                             tr_steps, tr_glen, tr_len_seen);
            end
            if ((tr_glen == DELAPAN) && (tr_full_first == 0)) tr_full_first = tr_steps;
            // ra1 and ra2 of a constant train are the interval itself, and they only exist
            // from the step that fills the eight window on
            if (tr_steps >= DELAPAN) begin
                if (u_dut.d_step_ra1_q !== RR_EXP[W_RR_MS-1:0]) tr_ra1_mism = tr_ra1_mism + 1;
                if (u_dut.d_step_ra2_q !== RR_EXP[W_RR_MS-1:0]) tr_ra1_mism = tr_ra1_mism + 1;
            end
            if (u_dut.d_step_menyala_q !== ((tr_glen === DELAPAN) ? 1'b1 : 1'b0)) begin
                tr_menyala_mism = tr_menyala_mism + 1;
                if (tr_menyala_mism < 5)
                    $display("MISM train menyala step=%0d dut=%0d queue=%0d",
                             tr_steps, u_dut.d_step_menyala_q, tr_glen);
            end
            if ({{28{1'b0}}, u_dut.d_step_deret_q} !==
                ((tr_steps >= DELAPAN) ? DELAPAN32 : tr_steps)) begin
                tr_mism = tr_mism + 1;
                if (tr_mism < 5)
                    $display("MISM train eight window step=%0d dut=%0d want=%0d",
                             tr_steps, u_dut.d_step_deret_q, tr_steps);
            end
            if (tr_steps == 24) tr_q24 = tr_glen;
            if (tr_steps > 24)
                if (tr_glen !== DELAPAN) tr_q_after24_bad = tr_q_after24_bad + 1;
            end
        end
        wcnt = 0;
        while ((u_dut.phase_q !== PH_IDLE_D) && (wcnt < DRAIN_MAX)) begin
            @(posedge clk);
            #1;
            wcnt = wcnt + 1;
        end
        $display("tb_rr: phase B steps = %0d, first step whose queue is full = %0d",
                 tr_steps, tr_full_first);
        $display("tb_rr: phase B queue length at step 24 = %0d", tr_q24);
        $display("tb_rr: phase B steps after 24 whose queue is not full = %0d", tr_q_after24_bad);
        $display("tb_rr: phase B ra1/ra2 mismatches = %0d, menyala mismatches = %0d",
                 tr_ra1_mism, tr_menyala_mism);
        $display("tb_rr: phase B mismatches = %0d out of %0d", tr_mism +
                 tr_ra1_mism + tr_menyala_mism, tr_steps);

        // ------------------------------------------------------------------ phase C
        $display("tb_rr: phase C, the gap mark, the passthrough and the counters");
        // (1) a recording gap, and the long interval counter it raises, which the
        //     configuration pulse then clears. The objective of this phase is to make the gap
        //     mark visible on a stimulus whose expected mark follows from the model rules
        //     rather than from a golden row, so the pre history is a constant train and the
        //     last interval steps well past both the missed beat boundary and the ceiling.
        //     The three conditions are checked below with variables, so they are a real gate
        //     and not a constant fold.
        pre_ref = SPACING_SMP * 4;      // the median of the equal pre history
        pre_n   = 10;                   // pre beats at SPACING_SMP, then one at LONG_SMP
        // the offered intervals are the pre_n-1 train intervals of pre_ref ms and one of
        // RR_LONG_EXP ms, so the counter of intervals past the ceiling follows from them
        long_want = 0;
        if (pre_ref > RR_LONG_L) long_want = long_want + (pre_n - 1);
        if (RR_LONG_EXP > RR_LONG_L) long_want = long_want + 1;
        a32 = RR_MISS_DEN * RR_LONG_EXP;
        b32 = RR_MISS_NUM * pre_ref;
        c32 = RR_MISS_DEN * pre_ref;
        d32 = RR_MISS_NUM * pre_ref;
        e32 = pre_ref * 2;
        if (!(a32 > b32))
            $fatal(1, "tb_rr: FAIL the long interval %0d is not past the missed beat boundary %0d",
                   RR_LONG_EXP, (b32 / RR_MISS_DEN));
        if (!(RR_LONG_EXP > RR_LONG_L))
            $fatal(1, "tb_rr: FAIL the synthetic long spacing %0d is not past the ceiling %0d",
                   RR_LONG_EXP, RR_LONG_L);
        if (c32 > d32)
            $fatal(1, "tb_rr: FAIL the pre history would already be a missed beat");
        if (e32 < pre_ref)
            $fatal(1, "tb_rr: FAIL the pre history would already be a false detection");
        reset_dut(4);
        mon_reset;
        long_seen = 0;
        pre_seen = 0;
        for (bi = 0; bi <= pre_n; bi = bi + 1) begin
            // the last beat steps past the ceiling, every earlier one keeps SPACING_SMP
            if (bi == pre_n)
                feed_beat((pre_n - 1) * SPACING_SMP + LONG_SMP, 32'd0, 1'b1);
            else
                feed_beat(bi * SPACING_SMP, 32'd0, 1'b0);
            if (bi == 0) begin
                @(posedge clk);
                #1;
            end else begin
                wait_interval;
                if (d_valid === 1'b1) begin
                    if (bi == pre_n) begin
                        long_seen = long_seen + 1;
                        if (m_rr_mark !== MARK_GAP_B) begin
                            $display("MISM a %0d ms interval carries mark %0d, the gap code is %0d",
                                     d_rr_ms, m_rr_mark, MARK_GAP_B);
                            mism_int_total = mism_int_total + 1;
                        end
                        if (d_rr_ms !== RR_LONG_EXP[W_RR_MS-1:0]) begin
                            $display("MISM a long interval reads %0d ms, the stimulus is %0d",
                                     d_rr_ms, RR_LONG_EXP);
                            mism_int_total = mism_int_total + 1;
                        end
                        if (m_ev_kind !== EV_RR_B) begin
                            $display("MISM a long interval published event kind %0d", m_ev_kind);
                            mism_int_total = mism_int_total + 1;
                        end
                    end else begin
                        pre_seen = pre_seen + 1;
                        if (m_rr_mark !== MARK_KEEP_B) begin
                            $display("MISM a %0d ms train interval carries mark %0d, not keep",
                                     d_rr_ms, m_rr_mark);
                            mism_int_total = mism_int_total + 1;
                        end
                    end
                end
            end
        end
        wcnt = 0;
        while ((u_dut.phase_q !== PH_IDLE_D) && (wcnt < DRAIN_MAX)) begin
            @(posedge clk);
            #1;
            wcnt = wcnt + 1;
        end
        $display("tb_rr: phase C train intervals = %0d, long intervals = %0d, counter = %0d, expected = %0d",
                 pre_seen, long_seen, o_rr_long_count, long_want);
        if (pre_seen != (pre_n - 1)) begin
            $display("MISM train intervals %0d against the %0d offered", pre_seen, pre_n - 1);
            mism_int_total = mism_int_total + 1;
        end
        if (long_seen != long_want) begin
            $display("MISM long intervals %0d against the %0d offered past the ceiling",
                     long_seen, long_want);
            mism_int_total = mism_int_total + 1;
        end
        if (o_rr_long_count !== long_want[31:0]) begin
            $display("MISM the long interval counter reads %0d, the stimulus asks for %0d",
                     o_rr_long_count, long_want);
            mism_int_total = mism_int_total + 1;
        end
        i_clear_counters = 1'b1;
        @(posedge clk);
        #1;
        i_clear_counters = 1'b0;
        @(posedge clk);
        #1;
        $display("tb_rr: phase C long counter after the clear pulse = %0d", o_rr_long_count);

        // (2) the two sideband markers, counted by the monitor: one cycle with the lost sample
        //     marker bit must raise exactly one EV_GAP, one cycle with tlast exactly one
        //     EV_WINDOW
        mon_reset;
        s_tvalid = 1'b1;
        s_tuser  = {W_TUSER{1'b0}};
        s_tuser[TU_GAP] = 1'b1;
        s_sample_idx = 32'd7;
        @(posedge clk);
        #1;
        s_tvalid = 1'b0;
        s_tuser  = {W_TUSER{1'b0}};
        for (ei = 0; ei < 8; ei = ei + 1) begin
            @(posedge clk);
            #1;
        end
        s_tvalid = 1'b1;
        s_tlast  = 1'b1;
        s_sample_idx = 32'd8;
        @(posedge clk);
        #1;
        s_tvalid = 1'b0;
        s_tlast  = 1'b0;
        for (ei = 0; ei < 8; ei = ei + 1) begin
            @(posedge clk);
            #1;
        end
        c_gap     = m_ev_gap;
        c_window  = m_ev_win;
        ev_other  = ev_other + m_ev_other;
        mon_en    = 1'b0;
        $display("tb_rr: phase C gap events = %0d, window events = %0d", c_gap, c_window);

        // ------------------------------------------------------------------ gate
        if (limit_n == N_QRS) begin
            if (n_int != mem_cnt[0]) begin
                $display("MISM full run intervals %0d against golden %0d", n_int, mem_cnt[0]);
                mism_int_total = mism_int_total + 1;
            end
            if (steps_seen != mem_cnt[7]) begin
                $display("MISM full run steps %0d against golden %0d", steps_seen, mem_cnt[7]);
                mism_step_total = mism_step_total + 1;
            end
            if (a_step !== mem_cnt[7]) begin
                $display("MISM step counter %0d against golden %0d", a_step, mem_cnt[7]);
                mism_step_total = mism_step_total + 1;
            end
            if (a_semai !== mem_cnt[8]) begin
                $display("MISM reseed count %0d against golden %0d", a_semai, mem_cnt[8]);
                mism_step_total = mism_step_total + 1;
            end
            if (a_penanda !== mem_cnt[9]) begin
                $display("MISM menyala total %0d against golden %0d", a_penanda, mem_cnt[9]);
                mism_step_total = mism_step_total + 1;
            end
            if (a_long !== mem_cnt[12]) begin
                $display("MISM long interval count %0d against golden %0d", a_long, mem_cnt[12]);
                mism_int_total = mism_int_total + 1;
            end
            if (last_not_full !== mem_cnt[10]) begin
                $display("MISM last step with a queue that is not full %0d against golden %0d",
                         last_not_full, mem_cnt[10]);
                mism_step_total = mism_step_total + 1;
            end
            if (gold_q_after24_bad != 0) begin
                $display("MISM golden queue rows after step 24 that are not full = %0d",
                         gold_q_after24_bad);
                mism_step_total = mism_step_total + gold_q_after24_bad;
            end
            for (ei = 0; ei < 4; ei = ei + 1) begin
                if (mark_census[ei] != mem_cnt[2+ei]) begin
                    $display("MISM census mark %0d dut=%0d gold=%0d",
                             ei, mark_census[ei], mem_cnt[2+ei]);
                    mism_int_total = mism_int_total + 1;
                end
                if (mark_census[ei] == 0) begin
                    $display("MISM mark %0d never appeared, the four marks are not all readable",
                             ei);
                    mism_int_total = mism_int_total + 1;
                end
            end
            if (ev_window != 1) begin
                $display("MISM window events on the golden run %0d against a single tlast",
                         ev_window);
                mism_int_total = mism_int_total + 1;
            end
        end else begin
            $display("tb_rr: SKIP end of run counters, this is a short run of %0d beats", limit_n);
        end

        // gates that hold on every run, short or not
        if (n_int != (limit_n - 1)) begin
            $display("MISM intervals %0d against the %0d beats fed", n_int, limit_n - 1);
            mism_int_total = mism_int_total + 1;
        end
        if (ev_rr != n_int) begin
            $display("MISM interval events %0d against %0d intervals", ev_rr, n_int);
            mism_int_total = mism_int_total + 1;
        end
        if (limit_n <= 0) mism_int_total = mism_int_total + 1;
        if (n_int == 0) begin
            $display("MISM no interval was compared at all, zero rows compared is a failure");
            mism_int_total = mism_int_total + 1;
        end
        if (step_rows_cmp != steps_seen) begin
            $display("MISM step rows compared %0d against steps committed %0d",
                     step_rows_cmp, steps_seen);
            mism_step_total = mism_step_total + 1;
        end
        if (steps_seen == 0) begin
            $display("MISM no step was committed at all, zero rows compared is a failure");
            mism_step_total = mism_step_total + 1;
        end
        if ((u_dut.sat_ms_q != 1'b0) || (u_dut.sat_smp_q != 1'b0) ||
            (u_dut.quo_over_q != 1'b0) || (u_dut.d_ra1_over_q != 1'b0) ||
            (u_dut.d_div_rem_bad_q != 1'b0)) begin
            $display("MISM a saturation or invariant flag is set");
            mism_int_total = mism_int_total + 1;
        end
        if (ev_other != 0) begin
            $display("MISM unexpected event kinds %0d", ev_other);
            mism_int_total = mism_int_total + ev_other;
        end
        if (tr_q24 != DELAPAN) begin
            $display("MISM phase B queue length at step 24 is %0d, not %0d", tr_q24, DELAPAN);
            mism_step_total = mism_step_total + 1;
        end
        if (tr_q_after24_bad != 0) begin
            $display("MISM phase B steps after 24 with a queue that is not full %0d",
                     tr_q_after24_bad);
            mism_step_total = mism_step_total + tr_q_after24_bad;
        end
        if (tr_full_first != (DELAPAN - 1 + DELAPAN)) begin
            $display("MISM phase B first step whose queue is full is %0d, not %0d",
                     tr_full_first, (DELAPAN - 1 + DELAPAN));
            mism_step_total = mism_step_total + 1;
        end
        if (c_gap != 1) begin
            $display("MISM phase C gap events %0d", c_gap);
            mism_int_total = mism_int_total + 1;
        end
        if (c_window != 1) begin
            $display("MISM phase C window events %0d", c_window);
            mism_int_total = mism_int_total + 1;
        end
        if (o_rr_long_count != 32'd0) begin
            $display("MISM the long interval counter was not cleared, it reads %0d",
                     o_rr_long_count);
            mism_int_total = mism_int_total + 1;
        end

        mism_total = mism_int_total + mism_step_total;

        $display("tb_rr: mismatches = %0d out of %0d", mism_total,
                 n_int + step_rows_cmp + tr_steps);
        $display("tb_rr: checks: intervals %0d, step rows %0d, synthetic steps %0d",
                 n_int, step_rows_cmp, tr_steps);
        if (mism_total == 0) begin
            $display("tb_rr: PASS");
            $finish;
        end else begin
            // repository convention: a gate violation has to leave a non zero exit status, so
            // the failure path raises $fatal after the same summary a passing run prints
            $fatal(1, "tb_rr: gate violation, see the counters above");
        end
    end

    // ------------------------------------------------------- tasks and helpers
    task automatic mon_reset;
        begin
            mon_en  = 1'b0;
            m_ev_rr = 0; m_ev_win = 0; m_ev_gap = 0; m_ev_other = 0;
            @(posedge clk);
            mon_en  = 1'b1;
        end
    endtask

    task automatic reset_dut(input integer cycles);
        begin
            rst_n = 1'b0;
            i_enable = 1'b0;
            i_clear_counters = 1'b1;
            s_tvalid = 1'b0;
            s_tlast = 1'b0;
            s_tuser = {W_TUSER{1'b0}};
            s_sample_idx = {W_IDX{1'b0}};
            s_ev_valid = 1'b0;
            s_ev_kind = {W_EVKIND{1'b0}};
            s_ev_idx = {W_IDX{1'b0}};
            s_ev_val = 32'd0;
            repeat (cycles) @(posedge clk);
            rst_n = 1'b1;
            i_enable = 1'b1;
            i_clear_counters = 1'b0;
            @(posedge clk);
        end
    endtask

    // offer one QRS beat, waiting for the stage to be idle so nothing is ever dropped
    task automatic feed_beat(input [W_IDX-1:0] pos, input [31:0] amp, input is_last);
        begin
            wcnt = 0;
            while ((u_dut.phase_q !== PH_IDLE_D) && (wcnt < SLOT_MAX)) begin
                @(posedge clk);
                #1;
                wcnt = wcnt + 1;
            end
            if (u_dut.phase_q !== PH_IDLE_D) poll_timeout = poll_timeout + 1;
            s_ev_valid   = 1'b1;
            s_ev_kind    = EV_QRS_B;
            s_ev_idx     = pos;
            s_ev_val     = amp;
            s_tvalid     = 1'b1;
            s_tlast      = is_last;
            s_tuser      = {W_TUSER{1'b0}};
            s_sample_idx = pos;
            @(posedge clk);
            #1;
            s_ev_valid = 1'b0;
            s_ev_val   = 32'd0;
            s_tvalid   = 1'b0;
            s_tlast    = 1'b0;
            // the amplitude word of the beat is latched with the beat
            if (u_dut.d_beat_val_q !== amp) begin
                mism_beatval = mism_beatval + 1;
                if (mism_beatval < 5)
                    $display("MISM beat amplitude beat=%0d dut=%0d gold=%0d",
                             beats_fed, u_dut.d_beat_val_q, amp);
            end
        end
    endtask

    // wait for the interval publish of the beat just offered
    task automatic wait_interval;
        begin
            step_pulse = 0;
            wcnt = 0;
            while ((step_pulse == 0) && (wcnt < SLOT_MAX)) begin
                // check the cycle we are standing in, then advance
                if (d_valid) step_pulse = 1;
                if (step_pulse == 0) begin
                    @(posedge clk);
                    #1;
                    wcnt = wcnt + 1;
                end
            end
            if (step_pulse == 0) begin
                poll_timeout = poll_timeout + 1;
                $display("MISM no interval published for beat=%0d", beats_fed - 1);
            end
        end
    endtask

    // wait for the per-step commit pulse of the locked stage
    task automatic wait_step(input integer max_cyc, output integer got_p);
        begin
            wcnt = 0;
            got_p = 0;
            while ((got_p == 0) && (wcnt < max_cyc)) begin
                // check the cycle we are standing in, then advance
                if (u_dut.d_step_valid_q) got_p = 1;
                if (got_p == 0) begin
                    @(posedge clk);
                    #1;
                    wcnt = wcnt + 1;
                end
            end
        end
    endtask

    // compare the committed step state against the golden row sr, zero based
    task automatic check_step(input integer sr, input [31:0] interval);
        begin
            if (u_dut.d_step_ra1_q !== mem_ra1[sr][W_RR_MS-1:0]) begin
                mism_ra1 = mism_ra1 + 1;
                if (mism_ra1 < 5)
                    $display("MISM ra1 step=%0d dut=%0d gold=%0d", sr + 1,
                             u_dut.d_step_ra1_q, mem_ra1[sr]);
            end
            if (u_dut.d_step_ra2_q !== mem_ra2[sr][W_RR_MS-1:0]) begin
                mism_ra2 = mism_ra2 + 1;
                if (mism_ra2 < 5)
                    $display("MISM ra2 step=%0d dut=%0d gold=%0d", sr + 1,
                             u_dut.d_step_ra2_q, mem_ra2[sr]);
            end
            if ({{28{1'b0}}, u_dut.d_step_antre_q} !== mem_antre[sr]) begin
                mism_antre = mism_antre + 1;
                if (mism_antre < 5)
                    $display("MISM queue step=%0d dut=%0d gold=%0d", sr + 1,
                             u_dut.d_step_antre_q, mem_antre[sr]);
            end
            if ({{31{1'b0}}, u_dut.d_step_menyala_q} !== mem_menyala[sr]) begin
                mism_menyala = mism_menyala + 1;
                if (mism_menyala < 5)
                    $display("MISM menyala step=%0d dut=%0d gold=%0d", sr + 1,
                             u_dut.d_step_menyala_q, mem_menyala[sr]);
            end
            if ({{31{1'b0}}, u_dut.d_step_disemai_q} !== mem_disemai[sr]) begin
                mism_disemai = mism_disemai + 1;
                if (mism_disemai < 5)
                    $display("MISM disemai step=%0d dut=%0d gold=%0d", sr + 1,
                             u_dut.d_step_disemai_q, mem_disemai[sr]);
            end
            if ({{26{1'b0}}, u_dut.d_step_riwayat_q} !== mem_riwayat[sr]) begin
                mism_riwayat = mism_riwayat + 1;
                if (mism_riwayat < 5)
                    $display("MISM history length step=%0d dut=%0d gold=%0d", sr + 1,
                             u_dut.d_step_riwayat_q, mem_riwayat[sr]);
            end
            if ({{28{1'b0}}, u_dut.d_step_gagal_q} !== mem_gagal[sr]) begin
                mism_gagal = mism_gagal + 1;
                if (mism_gagal < 5)
                    $display("MISM fail count step=%0d dut=%0d gold=%0d", sr + 1,
                             u_dut.d_step_gagal_q, mem_gagal[sr]);
            end
            if ({{16{1'b0}}, u_dut.d_step_jeda_q} !== mem_jeda[sr]) begin
                mism_jeda = mism_jeda + 1;
                if (mism_jeda < 5)
                    $display("MISM pace count step=%0d dut=%0d gold=%0d", sr + 1,
                             u_dut.d_step_jeda_q, mem_jeda[sr]);
            end
            if (u_dut.d_step_step_q !== (sr + 1)) begin
                mism_stepid = mism_stepid + 1;
                if (mism_stepid < 5)
                    $display("MISM step counter=%0d dut=%0d want=%0d",
                             sr + 1, u_dut.d_step_step_q, sr + 1);
            end
            // the step rows are the in-band rows of the interval series: the interval that
            // drove this step has to be the same word the golden column carries
            if (mem_stprr[sr] !== interval) begin
                mism_stprr = mism_stprr + 1;
                if (mism_stprr < 5)
                    $display("MISM step row %0d carries interval %0d, the driven one is %0d",
                             sr + 1, mem_stprr[sr], interval);
            end
            // the eight-interval window is full from the eighth accepted step on, which is
            // arithmetic on the package constant rather than a golden number
            deret_expected = ((sr + 1) >= DELAPAN) ? DELAPAN32 : (sr + 1);
            if ({{28{1'b0}}, u_dut.d_step_deret_q} !== deret_expected) begin
                mism_deret = mism_deret + 1;
                if (mism_deret < 5)
                    $display("MISM eight window length step=%0d dut=%0d want=%0d", sr + 1,
                             u_dut.d_step_deret_q, deret_expected);
            end
        end
    endtask

endmodule

`default_nettype wire
