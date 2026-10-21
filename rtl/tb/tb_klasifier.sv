// ---------------------------------------------------------------------------
// tb_klasifier.sv -- Fase 9 of plan 38: the triage classifier rtl/classifier.sv against the
// golden decision files of record 04015 and the two arms of the Fase 5 manifest.
//
// Runs in one simulation, all through the same DUT instance, every expected value read from
// $VECTOR and every configuration word read from the same folder:
//
//   probe   latency and the first decision of the marked arm, measured against
//           u_dut.LAT_CYCLES and the golden class column.
//   run 1   marked arm, 602 windows. Thresholds and arm code from the counts vector, or
//           injected with +RATIO_CODE / +ENT_CODE, which is the parity path the plan asks for.
//           Gate: m_class equals the frozen gate's class column on all 602 windows and the
//           confusion census against the ground truth class equals the Fase 5 manifest.
//   run 2   raw arm, 588 windows. Gate: 0 of 588 decisions differ, the number the Fase 9 gate
//           in plan 38 section 12 names.
//   run 3   register sensitivity. Same features as run 1, thresholds written as 0 and 0. An
//           implementation that compared a constant instead of the register cannot pass run 1
//           and run 3 together: with those codes the expected class column differs on most
//           windows.
//   run 4   entropy field guard. The entropy arm is the only arm enrolled and its field carries
//           0x8000, so bit 15 of the 16 bit field stands above every reachable 15 bit feature
//           and the arm can never fire. Every window must read normal; a stage that ignored
//           bit 15 would fire on almost every window.
//   run 5   single arm. The entropy arm alone is enrolled, so the ratio comparator must not
//           reach the decision at all.
//   run 6   confidence properties, D2b. m_conf has no golden column anywhere in the frozen
//           data, so this run checks the four properties the DUT header states: inside the
//           declared range, zero exactly on the binding threshold, monotone in the gap,
//           saturating at full scale. It compares no confidence value with a stored number.
//   run 0   before all of them: out of reset, and again with the stage disabled while valid
//           features sit on the wires, the class register must read the undecided code, the
//           confidence must read zero and no decision may be raised (D2: the reset value is
//           undecided, so a class that was never decided can never read normal).
//
// Plusargs, after the `--` separator as run_sim.sh requires:
//   +VECTOR=<dir>    required. Holds every expected value of this phase, one 32 bit hex word
//                    per line, 8 digits, $readmemh form, no comments:
//                      04015.berpenanda.qr.hex    ratio feature Q1.16, 602 words
//                      04015.berpenanda.qe.hex    entropy/4 feature Q1.14, 602 words
//                      04015.berpenanda.kelas.hex expected m_class, 602 words
//                      04015.berpenanda.asli.hex  ground truth class, 602 words
//                      04015.berpenanda.wi.hex    window index, 602 words
//                      04015.mentah.*.hex         the same five for the raw arm, 588 words
//                      04015.mutasi.kelas.hex     expected class, thresholds 0 and 0
//                      04015.guard.kelas.hex      expected class, entropy field 0x8000
//                      04015.tunggal.kelas.hex    expected class, entropy arm alone
//                      04015.fase9.counts.hex     27 configuration and census words
//                    The folder is written by rtl/tb/vektor/fase9/siapkan_vektor_fase9.py, which
//                    proves there that this integer comparison at these two codes and these
//                    two feature formats reproduces the frozen float predicate on every window
//                    of both arms, and that every census number here equals the Fase 5 manifest.
//   +RATIO_CODE=<n>  optional, written into the ratio threshold register of the parity runs.
//   +ENT_CODE=<n>    optional, written into the entropy threshold register of the parity runs.
//   +LIMIT=<n>       optional smoke run: the first n windows of every run, with the record wide
//                    gates reported as SKIP. The gate reported in the phase report is the full
//                    run.
//
// Why the thresholds are injected instead of left at the reset values: RATIO_THRESH_RST is 33
// and ENTROPY_THRESH_RST is 63, the operating point in 1/200 and 1/100 units, while the
// comparison this stage makes is on the feature words Q1.16 and Q1.14, where the same operating
// point is 10813 and 10322. Plan 38 Fase 9 names that trap in its "risiko khusus" line, and the
// Fase 5 manifest calls the two codes ratio_register_q16 and entropy_register_q14. This file
// therefore writes both registers before every run and never compares against a reset value.
//
// No measured number is written into this file: every expected class, census, count, code and
// feature word arrives from $VECTOR. The only literals are array bounds, the counts word order,
// the stimulus staircase of run 6 and the left hand side of u_dut.LAT_CYCLES.
//
// No file level timescale: rtl/afib_lite_pkg.sv carries none and adding one here makes Verilator
// raise TIMESCALEMOD against the package in the lint run. The clock is event driven, so the time
// unit changes no result.
//
// Tool: iverilog 12.0 and vvp from rtl-synthesis/debroot, through run_sim.sh.
// ---------------------------------------------------------------------------
`default_nettype none

module tb_klasifier;

    // ------------------------------------------------------------------ bounds and word order
    // Row counts of the golden decision files (588 raw, 602 marked). Array bounds, not results:
    // every run checks the same numbers again out of the counts vector.
    localparam integer N_MARK = 602;
    localparam integer N_RAW  = 588;
    localparam integer CAD    = 4;      // cycles between two presented windows
    localparam integer NWORD  = 27;     // words in 04015.fase9.counts.hex

    localparam integer CW_N_MARK   = 0;
    localparam integer CW_N_RAW    = 1;
    localparam integer CW_FRD_MARK = 2;
    localparam integer CW_FRD_RAW  = 3;
    localparam integer CW_TP_MARK  = 4;
    localparam integer CW_FP_MARK  = 5;
    localparam integer CW_FN_MARK  = 6;
    localparam integer CW_TN_MARK  = 7;
    localparam integer CW_TP_RAW   = 8;
    localparam integer CW_FP_RAW   = 9;
    localparam integer CW_FN_RAW   = 10;
    localparam integer CW_TN_RAW   = 11;
    localparam integer CW_AFIB_MK  = 12;
    localparam integer CW_NORM_MK  = 13;
    localparam integer CW_AFIB_RW  = 14;
    localparam integer CW_NORM_RW  = 15;
    localparam integer CW_RATIO_CODE = 16;
    localparam integer CW_ENT_CODE   = 17;
    localparam integer CW_ARM_MARK   = 18;
    localparam integer CW_ARM_RAW    = 19;
    localparam integer CW_MUT_RATIO  = 20;
    localparam integer CW_MUT_ENT    = 21;
    localparam integer CW_GUARD_ENT  = 22;
    localparam integer CW_ARM_SINGLE = 23;
    localparam integer CW_FRD_MUT    = 24;
    localparam integer CW_FRD_SINGLE = 25;
    localparam integer CW_N_SINGLE   = 26;

    localparam integer W_F_RATIO = afib_lite_pkg::W_F_RATIO;
    localparam integer W_F_ENT   = afib_lite_pkg::W_F_ENT;
    localparam integer W_CONF    = afib_lite_pkg::W_CONF;
    // the class codes and the confidence full scale at their own widths, so no comparison in
    // this file is between two different widths
    localparam [1:0]        KELAS_UNDECIDED = afib_lite_pkg::KELAS_UNDECIDED;
    localparam [1:0]        KELAS_NORMAL    = afib_lite_pkg::KELAS_NORMAL;
    localparam [1:0]        KELAS_REVIEW    = afib_lite_pkg::KELAS_REVIEW;
    localparam [W_CONF-1:0] CONF_FS         = afib_lite_pkg::CONF_FULL_SCALE[W_CONF-1:0];
    localparam [W_CONF-1:0] CONF_ZERO       = {W_CONF{1'b0}};

    // ------------------------------------------------------------------ DUT
    reg clk   = 1'b0;
    reg rst_n = 1'b0;

    reg                   f_valid;
    reg  [W_F_RATIO-1:0]  f_ratio;
    reg  [W_F_ENT-1:0]    f_ent;
    reg  [31:0]           f_win_idx;

    reg                   i_enable;
    reg                   i_clear_counters;
    reg  [15:0]           i_ratio_thresh;
    reg  [15:0]           i_entropy_thresh;
    reg  [4:0]            i_arm_select;

    wire                  m_dvalid;
    wire [1:0]            m_class;
    wire [W_CONF-1:0]     m_conf;
    wire [31:0]           m_win_idx;
    wire [1:0]            d_class;
    wire [W_CONF-1:0]     d_conf;
    wire [31:0]           o_window_count;

    classifier u_dut (
        .clk_i           (clk),
        .rst_ni          (rst_n),
        .f_valid         (f_valid),
        .f_ratio         (f_ratio),
        .f_ent           (f_ent),
        .f_win_idx       (f_win_idx),
        .i_enable        (i_enable),
        .i_clear_counters(i_clear_counters),
        .i_ratio_thresh  (i_ratio_thresh),
        .i_entropy_thresh(i_entropy_thresh),
        .i_arm_select    (i_arm_select),
        .m_dvalid        (m_dvalid),
        .m_class         (m_class),
        .m_conf          (m_conf),
        .m_win_idx       (m_win_idx),
        .d_class         (d_class),
        .d_conf          (d_conf),
        .o_window_count  (o_window_count)
    );

    always #5 clk <= ~clk;

    // ------------------------------------------------------------------ vectors
    reg [31:0] qr_mk  [0:N_MARK-1];
    reg [31:0] qe_mk  [0:N_MARK-1];
    reg [31:0] kls_mk [0:N_MARK-1];
    reg [31:0] asl_mk [0:N_MARK-1];
    reg [31:0] wi_mk  [0:N_MARK-1];
    reg [31:0] kls_mut[0:N_MARK-1];
    reg [31:0] kls_grd[0:N_MARK-1];
    reg [31:0] kls_sgl[0:N_MARK-1];

    reg [31:0] qr_rw  [0:N_RAW-1];
    reg [31:0] qe_rw  [0:N_RAW-1];
    reg [31:0] kls_rw [0:N_RAW-1];
    reg [31:0] asl_rw [0:N_RAW-1];
    reg [31:0] wi_rw  [0:N_RAW-1];

    reg [31:0] cnt_mem [0:NWORD-1];

    reg [1023:0] vdir;
    reg [1023:0] fpath;

    // ------------------------------------------------------------------ state
    integer limit_n;
    integer n_run;
    integer k;
    integer rc;
    integer lat_cyc;
    integer lat_mism;
    // run 6 stimulus words, at the two feature widths so no comparison in this file widens
    reg [W_F_RATIO-1:0] stim_ratio;
    reg [W_F_ENT-1:0]   stim_ent;
    reg [W_CONF-1:0] conf_prev;

    integer ratio_code;
    integer ent_code;
    integer arm_mark_code;
    integer arm_raw_code;
    integer mut_ratio_code;
    integer mut_ent_code;
    integer guard_ent_code;
    integer arm_sgl_code;
    integer plus_code;

    // per run counters, reset at the start of every run
    integer mism_class;
    integer mism_wi;
    integer mism_tap;
    integer mism_dv;
    integer extra_dv;
    integer bad_fmt;
    integer conf_bad;
    integer tp;
    integer fp;
    integer fn;
    integer tn;
    integer fired;

    // per run results
    integer r1_mism; integer r1_dv; integer r1_wi; integer r1_extra; integer r1_tap;
    integer r2_mism; integer r2_dv; integer r2_wi; integer r2_extra;
    integer r3_mism; integer r4_mism; integer r5_mism;
    integer r6_bad; integer r6_zero; integer r6_mono; integer r6_sat; integer r6_thr;

    // ------------------------------------------------------------------ helpers
    function automatic integer count_lines(input [1023:0] path);
        integer f, n;
        reg [1023:0] line;
        begin
            n = 0;
            f = $fopen(path, "r");
            if (f == 0) begin
                $display("FATAL tb_klasifier: cannot open %0s", path);
                n = -1;
            end else begin
                while ($fgets(line, f) != 0)
                    if (line != 0) n = n + 1;
                $fclose(f);
            end
            count_lines = n;
        end
    endfunction

    // present one window, then sample the decision on the following edge: the DUT registers its
    // inputs on the edge and this file samples 1 ns after that edge, the convention of this repo.
    // The expected class, the ground truth class and the census switch all arrive as arguments, so
    // no run has to swap a memory around. Both class arguments are 2 bit wide, the width of the
    // columns they come from, and the vector format loop below proves those columns are 2 bit wide,
    // which makes the comparison the same one a zero extended comparison would make.
    task automatic langkah(input [W_F_RATIO-1:0] qr, input [W_F_ENT-1:0] qe, input [31:0] wi,
                           input [1:0] kls_exp, input [1:0] asli_exp,
                           input integer census_en);
        begin
            f_ratio   = qr;
            f_ent     = qe;
            f_win_idx = wi;
            f_valid   = 1'b1;
            @(posedge clk);
            #1;
            f_valid = 1'b0;
            if (m_dvalid !== 1'b1) mism_dv = mism_dv + 1;
            if (m_class !== kls_exp) mism_class = mism_class + 1;
            if (m_win_idx !== wi) mism_wi = mism_wi + 1;
            if (d_class !== m_class) mism_tap = mism_tap + 1;
            if (d_conf !== m_conf) mism_tap = mism_tap + 1;
            if (m_conf > CONF_FS) conf_bad = conf_bad + 1;
            if (census_en != 0) begin
                if (m_class == KELAS_REVIEW) begin
                    fired = fired + 1;
                    if (asli_exp == KELAS_REVIEW) tp = tp + 1; else fp = fp + 1;
                end else begin
                    if (asli_exp == KELAS_REVIEW) fn = fn + 1; else tn = tn + 1;
                end
            end
            repeat (CAD - 1) begin
                @(posedge clk);
                #1;
                if (m_dvalid !== 1'b0) extra_dv = extra_dv + 1;
            end
        end
    endtask

    task automatic zero_counters;
        begin
            mism_class = 0; mism_wi = 0; mism_tap = 0; mism_dv = 0; extra_dv = 0;
            conf_bad = 0; tp = 0; fp = 0; fn = 0; tn = 0; fired = 0;
        end
    endtask

    // ------------------------------------------------------------------ main
    initial begin
        f_valid          = 1'b0;
        f_ratio          = {W_F_RATIO{1'b0}};
        f_ent            = {W_F_ENT{1'b0}};
        f_win_idx        = 32'd0;
        i_enable         = 1'b0;
        i_clear_counters = 1'b0;
        i_ratio_thresh   = 16'd0;
        i_entropy_thresh = 16'd0;
        i_arm_select     = 5'd0;
        limit_n          = 0;
        zero_counters;

        if (!$value$plusargs("VECTOR=%s", vdir)) begin
            $display("FAIL tb_klasifier: no +VECTOR, want the vector directory");
            $fatal(1, "tb_klasifier: no +VECTOR");
        end
        if ($value$plusargs("LIMIT=%d", limit_n))
            $display("INFO tb_klasifier: +LIMIT=%0d, the record wide gates are skipped", limit_n);

        $display("== tb_klasifier, Fase 9, record 04015, vectors %0s ==", vdir);

        // -------------------------------------------------------------- read the vectors
        $sformat(fpath, "%0s/04015.berpenanda.qr.hex", vdir);    $readmemh(fpath, qr_mk);
        $sformat(fpath, "%0s/04015.berpenanda.qe.hex", vdir);    $readmemh(fpath, qe_mk);
        $sformat(fpath, "%0s/04015.berpenanda.kelas.hex", vdir); $readmemh(fpath, kls_mk);
        $sformat(fpath, "%0s/04015.berpenanda.asli.hex", vdir);  $readmemh(fpath, asl_mk);
        $sformat(fpath, "%0s/04015.berpenanda.wi.hex", vdir);    $readmemh(fpath, wi_mk);
        $sformat(fpath, "%0s/04015.mutasi.kelas.hex", vdir);     $readmemh(fpath, kls_mut);
        $sformat(fpath, "%0s/04015.guard.kelas.hex", vdir);      $readmemh(fpath, kls_grd);
        $sformat(fpath, "%0s/04015.tunggal.kelas.hex", vdir);    $readmemh(fpath, kls_sgl);
        $sformat(fpath, "%0s/04015.mentah.qr.hex", vdir);        $readmemh(fpath, qr_rw);
        $sformat(fpath, "%0s/04015.mentah.qe.hex", vdir);        $readmemh(fpath, qe_rw);
        $sformat(fpath, "%0s/04015.mentah.kelas.hex", vdir);     $readmemh(fpath, kls_rw);
        $sformat(fpath, "%0s/04015.mentah.asli.hex", vdir);      $readmemh(fpath, asl_rw);
        $sformat(fpath, "%0s/04015.mentah.wi.hex", vdir);        $readmemh(fpath, wi_rw);
        $sformat(fpath, "%0s/04015.fase9.counts.hex", vdir);     $readmemh(fpath, cnt_mem);

        // every column has to fit its declared width, and the class columns have to be 2 bit so
        // that the comparison in the task is the same comparison a zero extended one would be
        bad_fmt = 0;
        for (k = 0; k < N_MARK; k = k + 1) begin
            if (|qr_mk[k][31:W_F_RATIO]) bad_fmt = bad_fmt + 1;
            if (|qe_mk[k][31:W_F_ENT])   bad_fmt = bad_fmt + 1;
            if (|kls_mk[k][31:2])        bad_fmt = bad_fmt + 1;
            if (|asl_mk[k][31:2])        bad_fmt = bad_fmt + 1;
            if (|kls_mut[k][31:2])       bad_fmt = bad_fmt + 1;
            if (|kls_grd[k][31:2])       bad_fmt = bad_fmt + 1;
            if (|kls_sgl[k][31:2])       bad_fmt = bad_fmt + 1;
        end
        for (k = 0; k < N_RAW; k = k + 1) begin
            if (|qr_rw[k][31:W_F_RATIO]) bad_fmt = bad_fmt + 1;
            if (|qe_rw[k][31:W_F_ENT])   bad_fmt = bad_fmt + 1;
            if (|kls_rw[k][31:2])        bad_fmt = bad_fmt + 1;
            if (|asl_rw[k][31:2])        bad_fmt = bad_fmt + 1;
        end
        $display("INFO tb_klasifier: vector words above their width: %0d", bad_fmt);
        if (bad_fmt !== 0) $fatal(1, "tb_klasifier: vector format");

        $sformat(fpath, "%0s/04015.berpenanda.qr.hex", vdir);
        rc = count_lines(fpath);
        if (rc !== N_MARK) begin
            $display("FATAL tb_klasifier: marked feature file holds %0d words, want %0d", rc, N_MARK);
            $fatal(1, "tb_klasifier: marked vector length");
        end
        $sformat(fpath, "%0s/04015.mentah.qr.hex", vdir);
        rc = count_lines(fpath);
        if (rc !== N_RAW) begin
            $display("FATAL tb_klasifier: raw feature file holds %0d words, want %0d", rc, N_RAW);
            $fatal(1, "tb_klasifier: raw vector length");
        end
        if ((cnt_mem[CW_N_MARK] !== N_MARK) || (cnt_mem[CW_N_RAW] !== N_RAW)) begin
            $display("FATAL tb_klasifier: counts vector says %0d and %0d windows, files hold %0d and %0d",
                     cnt_mem[CW_N_MARK], cnt_mem[CW_N_RAW], N_MARK, N_RAW);
            $fatal(1, "tb_klasifier: counts vector disagrees with the files");
        end
        // these keep the word order of the counts vector visible in the log
        $display("INFO tb_klasifier: counts vector marked %0d raw %0d, afib %0d and normal %0d",
                 cnt_mem[CW_N_MARK], cnt_mem[CW_N_RAW], cnt_mem[CW_AFIB_MK], cnt_mem[CW_NORM_MK]);
        $display("INFO tb_klasifier: raw afib %0d normal %0d, single arm windows %0d, mutasi fired %0d",
                 cnt_mem[CW_AFIB_RW], cnt_mem[CW_NORM_RW], cnt_mem[CW_N_SINGLE], cnt_mem[CW_FRD_MUT]);

        // configuration read out of the vector folder, optionally overridden on the command line
        ratio_code     = cnt_mem[CW_RATIO_CODE];
        ent_code       = cnt_mem[CW_ENT_CODE];
        arm_mark_code  = cnt_mem[CW_ARM_MARK];
        arm_raw_code   = cnt_mem[CW_ARM_RAW];
        mut_ratio_code = cnt_mem[CW_MUT_RATIO];
        mut_ent_code   = cnt_mem[CW_MUT_ENT];
        guard_ent_code = cnt_mem[CW_GUARD_ENT];
        arm_sgl_code   = cnt_mem[CW_ARM_SINGLE];
        if ($value$plusargs("RATIO_CODE=%d", plus_code)) begin
            ratio_code = plus_code;
            $display("INFO tb_klasifier: +RATIO_CODE, parity ratio threshold injected from the command line");
        end
        if ($value$plusargs("ENT_CODE=%d", plus_code)) begin
            ent_code = plus_code;
            $display("INFO tb_klasifier: +ENT_CODE, parity entropy threshold injected from the command line");
        end
        $display("INFO tb_klasifier: parity ratio code %0d", ratio_code);
        $display("INFO tb_klasifier: parity entropy code %0d", ent_code);
        $display("INFO tb_klasifier: marked arm 0x%0h, raw arm 0x%0h, single arm 0x%0h",
                 arm_mark_code, arm_raw_code, arm_sgl_code);

        // -------------------------------------------------------------- run 0, reset and D2
        rst_n = 1'b0;
        i_enable = 1'b0;
        repeat (8) @(posedge clk);
        #1;
        if (m_dvalid !== 1'b0) begin
            $display("FATAL tb_klasifier: m_dvalid high out of reset");
            $fatal(1, "tb_klasifier: reset decision");
        end
        if (m_class !== KELAS_UNDECIDED) begin
            $display("FATAL tb_klasifier: class out of reset is %0d, want undecided %0d",
                     m_class, KELAS_UNDECIDED);
            $fatal(1, "tb_klasifier: D2 reset value");
        end
        if (m_conf !== CONF_ZERO) begin
            $display("FATAL tb_klasifier: confidence out of reset is %0d, want 0", m_conf);
            $fatal(1, "tb_klasifier: reset confidence");
        end
        if (o_window_count !== 32'd0) begin
            $display("FATAL tb_klasifier: window counter out of reset is %0d, want 0", o_window_count);
            $fatal(1, "tb_klasifier: reset counter");
        end
        rst_n = 1'b1;
        // disabled stage with valid features on the wires: still no decision, still undecided
        f_ratio = qr_mk[0][W_F_RATIO-1:0];
        f_ent   = qe_mk[0][W_F_ENT-1:0];
        f_win_idx = wi_mk[0];
        f_valid = 1'b1;
        @(posedge clk);
        #1;
        f_valid = 1'b0;
        if (m_dvalid !== 1'b0) begin
            $display("FATAL tb_klasifier: a disabled stage raised m_dvalid");
            $fatal(1, "tb_klasifier: disabled stage decision");
        end
        if (m_class !== KELAS_UNDECIDED) begin
            $display("FATAL tb_klasifier: disabled stage class is %0d, want undecided %0d",
                     m_class, KELAS_UNDECIDED);
            $fatal(1, "tb_klasifier: disabled stage class");
        end
        if (o_window_count !== 32'd0) begin
            $display("FATAL tb_klasifier: a disabled stage counted a window: %0d", o_window_count);
            $fatal(1, "tb_klasifier: disabled stage counter");
        end
        $display("OK   tb_klasifier: reset and disabled stage read undecided, no decision (D2)");

        // -------------------------------------------------------------- probe, latency
        rst_n = 1'b0;
        repeat (4) @(posedge clk);
        i_enable         = 1'b1;
        i_clear_counters = 1'b1;
        i_ratio_thresh   = ratio_code[15:0];
        i_entropy_thresh = ent_code[15:0];
        i_arm_select     = arm_mark_code[4:0];
        rst_n = 1'b1;
        @(posedge clk);
        #1;
        i_clear_counters = 1'b0;
        zero_counters;
        f_ratio   = qr_mk[0][W_F_RATIO-1:0];
        f_ent     = qe_mk[0][W_F_ENT-1:0];
        f_win_idx = wi_mk[0];
        f_valid   = 1'b1;
        lat_cyc = 0;
        while ((m_dvalid !== 1'b1) && (lat_cyc < 8)) begin
            @(posedge clk);
            #1;
            lat_cyc = lat_cyc + 1;
        end
        f_valid = 1'b0;
        lat_mism = 0;
        if (m_class !== kls_mk[0][1:0]) lat_mism = lat_mism + 1;
        if (m_win_idx !== wi_mk[0]) lat_mism = lat_mism + 1;
        if (d_class !== m_class) lat_mism = lat_mism + 1;
        $display("INFO tb_klasifier: measured latency = %0d cycles, DUT parameter = %0d",
                 lat_cyc, u_dut.LAT_CYCLES);
        if (lat_cyc !== u_dut.LAT_CYCLES) begin
            $display("FATAL tb_klasifier: latency %0d does not equal LAT_CYCLES %0d",
                     lat_cyc, u_dut.LAT_CYCLES);
            $fatal(1, "tb_klasifier: latency");
        end
        if (lat_mism !== 0) begin
            $display("FATAL tb_klasifier: probe decision: class %0d want %0d, win_idx %0d want %0d, d_class %0d",
                     m_class, kls_mk[0][1:0], m_win_idx, wi_mk[0], d_class);
            $fatal(1, "tb_klasifier: probe decision");
        end
        $display("OK   tb_klasifier: latency and first decision of the marked arm");

        // -------------------------------------------------------------- run 1, marked arm
        n_run = N_MARK;
        if ((limit_n > 0) && (limit_n < n_run)) n_run = limit_n;
        rst_n = 1'b0;
        repeat (4) @(posedge clk);
        i_enable         = 1'b1;
        i_clear_counters = 1'b1;
        i_ratio_thresh   = ratio_code[15:0];
        i_entropy_thresh = ent_code[15:0];
        i_arm_select     = arm_mark_code[4:0];
        rst_n = 1'b1;
        @(posedge clk);
        #1;
        i_clear_counters = 1'b0;
        zero_counters;
        for (k = 0; k < n_run; k = k + 1)
            langkah(qr_mk[k][W_F_RATIO-1:0], qe_mk[k][W_F_ENT-1:0], wi_mk[k],
                    kls_mk[k][1:0], asl_mk[k][1:0], 1);
        r1_mism = mism_class; r1_dv = mism_dv; r1_wi = mism_wi;
        r1_extra = extra_dv; r1_tap = mism_tap;
        if ((limit_n > 0) && (limit_n < N_MARK)) begin
            $display("SKIP tb_klasifier: marked arm census, this is a +LIMIT short run");
        end else begin
            $display("INFO tb_klasifier: marked arm fired %0d, TP=%0d FP=%0d FN=%0d TN=%0d",
                     fired, tp, fp, fn, tn);
            if ((tp !== cnt_mem[CW_TP_MARK]) || (fp !== cnt_mem[CW_FP_MARK]) ||
                (fn !== cnt_mem[CW_FN_MARK]) || (tn !== cnt_mem[CW_TN_MARK]) ||
                (fired !== cnt_mem[CW_FRD_MARK])) begin
                $display("FATAL tb_klasifier: marked census %0d/%0d/%0d/%0d fired %0d, vector says %0d/%0d/%0d/%0d fired %0d",
                         tp, fp, fn, tn, fired, cnt_mem[CW_TP_MARK], cnt_mem[CW_FP_MARK],
                         cnt_mem[CW_FN_MARK], cnt_mem[CW_TN_MARK], cnt_mem[CW_FRD_MARK]);
                $fatal(1, "tb_klasifier: marked census");
            end
            $display("OK   tb_klasifier: marked arm census equals the Fase 5 manifest");
        end
        if (o_window_count !== n_run) begin
            $display("FATAL tb_klasifier: marked window counter %0d, want %0d", o_window_count, n_run);
            $fatal(1, "tb_klasifier: marked window counter");
        end
        $display("tb_klasifier: [marked] words compared: %0d", n_run);
        $display("tb_klasifier: [marked] mismatches = %0d out of %0d", r1_mism, n_run);
        $display("tb_klasifier: [marked] window index mismatches = %0d", r1_wi);
        $display("tb_klasifier: [marked] m_dvalid missing = %0d, extra decisions = %0d",
                 r1_dv, r1_extra);
        $display("tb_klasifier: [marked] introspection tap mismatches = %0d", r1_tap);
        $display("tb_klasifier: [marked] confidence out of range = %0d", conf_bad);

        // counter clear, exercised once
        i_clear_counters = 1'b1;
        @(posedge clk);
        #1;
        i_clear_counters = 1'b0;
        if (o_window_count !== 32'd0) begin
            $display("FATAL tb_klasifier: counter did not clear: %0d", o_window_count);
            $fatal(1, "tb_klasifier: clear counters");
        end
        $display("OK   tb_klasifier: window counter cleared");

        // -------------------------------------------------------------- run 2, raw arm
        n_run = N_RAW;
        if ((limit_n > 0) && (limit_n < n_run)) n_run = limit_n;
        rst_n = 1'b0;
        repeat (4) @(posedge clk);
        i_ratio_thresh   = ratio_code[15:0];
        i_entropy_thresh = ent_code[15:0];
        i_arm_select     = arm_raw_code[4:0];
        rst_n = 1'b1;
        @(posedge clk);
        #1;
        zero_counters;
        for (k = 0; k < n_run; k = k + 1)
            langkah(qr_rw[k][W_F_RATIO-1:0], qe_rw[k][W_F_ENT-1:0], wi_rw[k],
                    kls_rw[k][1:0], asl_rw[k][1:0], 1);
        r2_mism = mism_class; r2_dv = mism_dv; r2_wi = mism_wi; r2_extra = extra_dv;
        if ((limit_n > 0) && (limit_n < N_RAW)) begin
            $display("SKIP tb_klasifier: raw arm census, this is a +LIMIT short run");
        end else begin
            $display("INFO tb_klasifier: raw arm fired %0d, TP=%0d FP=%0d FN=%0d TN=%0d",
                     fired, tp, fp, fn, tn);
            if ((tp !== cnt_mem[CW_TP_RAW]) || (fp !== cnt_mem[CW_FP_RAW]) ||
                (fn !== cnt_mem[CW_FN_RAW]) || (tn !== cnt_mem[CW_TN_RAW]) ||
                (fired !== cnt_mem[CW_FRD_RAW])) begin
                $display("FATAL tb_klasifier: raw census %0d/%0d/%0d/%0d fired %0d, vector says %0d/%0d/%0d/%0d fired %0d",
                         tp, fp, fn, tn, fired, cnt_mem[CW_TP_RAW], cnt_mem[CW_FP_RAW],
                         cnt_mem[CW_FN_RAW], cnt_mem[CW_TN_RAW], cnt_mem[CW_FRD_RAW]);
                $fatal(1, "tb_klasifier: raw census");
            end
            $display("OK   tb_klasifier: raw arm census equals the Fase 5 manifest");
        end
        if (o_window_count !== n_run) begin
            $display("FATAL tb_klasifier: raw window counter %0d, want %0d", o_window_count, n_run);
            $fatal(1, "tb_klasifier: raw window counter");
        end
        $display("tb_klasifier: [raw] words compared: %0d", n_run);
        $display("tb_klasifier: [raw] mismatches = %0d out of %0d", r2_mism, n_run);
        $display("tb_klasifier: [raw] window index mismatches = %0d", r2_wi);
        $display("tb_klasifier: [raw] m_dvalid missing = %0d, extra decisions = %0d",
                 r2_dv, r2_extra);

        // -------------------------------------------------------------- run 3, register sensitivity
        n_run = N_MARK;
        if ((limit_n > 0) && (limit_n < n_run)) n_run = limit_n;
        rst_n = 1'b0;
        repeat (4) @(posedge clk);
        i_ratio_thresh   = mut_ratio_code[15:0];
        i_entropy_thresh = mut_ent_code[15:0];
        i_arm_select     = arm_mark_code[4:0];
        rst_n = 1'b1;
        @(posedge clk);
        #1;
        zero_counters;
        for (k = 0; k < n_run; k = k + 1)
            langkah(qr_mk[k][W_F_RATIO-1:0], qe_mk[k][W_F_ENT-1:0], wi_mk[k],
                    kls_mut[k][1:0], kls_mut[k][1:0], 0);
        r3_mism = mism_class;
        if (o_window_count !== n_run) begin
            $display("FATAL tb_klasifier: mutasi window counter %0d, want %0d", o_window_count, n_run);
            $fatal(1, "tb_klasifier: mutasi window counter");
        end
        $display("tb_klasifier: [mutasi] thresholds %0d and %0d, arm 0x%0h",
                 mut_ratio_code, mut_ent_code, arm_mark_code);
        $display("tb_klasifier: [mutasi] words compared: %0d", n_run);
        $display("tb_klasifier: [mutasi] mismatches = %0d out of %0d", r3_mism, n_run);

        // -------------------------------------------------------------- run 4, entropy field guard
        n_run = N_MARK;
        if ((limit_n > 0) && (limit_n < n_run)) n_run = limit_n;
        rst_n = 1'b0;
        repeat (4) @(posedge clk);
        i_ratio_thresh   = ratio_code[15:0];
        i_entropy_thresh = guard_ent_code[15:0];
        i_arm_select     = arm_sgl_code[4:0];
        rst_n = 1'b1;
        @(posedge clk);
        #1;
        zero_counters;
        for (k = 0; k < n_run; k = k + 1)
            langkah(qr_mk[k][W_F_RATIO-1:0], qe_mk[k][W_F_ENT-1:0], wi_mk[k],
                    kls_grd[k][1:0], kls_grd[k][1:0], 0);
        r4_mism = mism_class;
        $display("tb_klasifier: [guard] entropy field %0d, arm 0x%0h",
                 guard_ent_code, arm_sgl_code);
        $display("tb_klasifier: [guard] words compared: %0d", n_run);
        $display("tb_klasifier: [guard] mismatches = %0d out of %0d", r4_mism, n_run);

        // -------------------------------------------------------------- run 5, single arm
        n_run = N_MARK;
        if ((limit_n > 0) && (limit_n < n_run)) n_run = limit_n;
        rst_n = 1'b0;
        repeat (4) @(posedge clk);
        i_ratio_thresh   = ratio_code[15:0];
        i_entropy_thresh = ent_code[15:0];
        i_arm_select     = arm_sgl_code[4:0];
        rst_n = 1'b1;
        @(posedge clk);
        #1;
        zero_counters;
        for (k = 0; k < n_run; k = k + 1)
            langkah(qr_mk[k][W_F_RATIO-1:0], qe_mk[k][W_F_ENT-1:0], wi_mk[k],
                    kls_sgl[k][1:0], kls_sgl[k][1:0], 1);
        r5_mism = mism_class;
        $display("tb_klasifier: [tunggal] arm 0x%0h, entropy arm alone", arm_sgl_code);
        $display("tb_klasifier: [tunggal] words compared: %0d", n_run);
        $display("tb_klasifier: [tunggal] mismatches = %0d out of %0d", r5_mism, n_run);
        if ((limit_n > 0) && (limit_n < N_MARK)) begin
            $display("SKIP tb_klasifier: tunggal fired count, this is a +LIMIT short run");
        end else begin
            $display("INFO tb_klasifier: tunggal fired %0d", fired);
            if (fired !== cnt_mem[CW_FRD_SINGLE]) begin
                $display("FATAL tb_klasifier: tunggal fired %0d, vector says %0d",
                         fired, cnt_mem[CW_FRD_SINGLE]);
                $fatal(1, "tb_klasifier: tunggal fired count");
            end
        end

        // -------------------------------------------------------------- run 6, confidence, D2b
        // Stimulus staircase over the two feature words: on both thresholds, one step over, a few
        // steps over, and far over. The step values are stimulus choices; the expectations are the
        // four properties the DUT header states and nothing else.
        rst_n = 1'b0;
        repeat (4) @(posedge clk);
        i_ratio_thresh   = ratio_code[15:0];
        i_entropy_thresh = ent_code[15:0];
        i_arm_select     = arm_mark_code[4:0];
        rst_n = 1'b1;
        @(posedge clk);
        #1;
        zero_counters;
        r6_mono = 0; r6_sat = 0; r6_zero = 0; r6_thr = 0; r6_bad = 0;
        conf_prev = CONF_ZERO;
        for (k = 0; k < 5; k = k + 1) begin
            // the gap of this step, in Q1.16 steps on the ratio word and a quarter of that on the
            // entropy word, because the entropy word sits two bits lower
            case (k)
                0: begin   // exactly on both thresholds
                    stim_ratio = ratio_code[W_F_RATIO-1:0];
                    stim_ent   = ent_code[W_F_ENT-1:0];
                end
                1: begin
                    stim_ratio = ratio_code[W_F_RATIO-1:0] + 17'd16;
                    stim_ent   = ent_code[W_F_ENT-1:0] + 15'd4;
                end
                2: begin
                    stim_ratio = ratio_code[W_F_RATIO-1:0] + 17'd64;
                    stim_ent   = ent_code[W_F_ENT-1:0] + 15'd16;
                end
                3: begin
                    stim_ratio = ratio_code[W_F_RATIO-1:0] + 17'd1024;
                    stim_ent   = ent_code[W_F_ENT-1:0] + 15'd256;
                end
                default: begin
                    stim_ratio = ratio_code[W_F_RATIO-1:0] + 17'd16000;
                    stim_ent   = ent_code[W_F_ENT-1:0] + 15'd4000;
                end
            endcase
            f_ratio   = stim_ratio;
            f_ent     = stim_ent;
            f_win_idx = k;
            f_valid   = 1'b1;
            @(posedge clk);
            #1;
            f_valid = 1'b0;
            if (m_dvalid !== 1'b1) mism_dv = mism_dv + 1;
            if (m_conf > CONF_FS) r6_bad = r6_bad + 1;
            if ((k == 0) && (m_conf !== CONF_ZERO)) r6_zero = r6_zero + 1;
            if ((k == 0) && (m_class !== KELAS_NORMAL)) r6_thr = r6_thr + 1;
            if (m_conf < conf_prev) r6_mono = r6_mono + 1;
            conf_prev = m_conf;
            if (k == 0) $display("INFO tb_klasifier: conf on both thresholds = %0d", m_conf);
            if (k == 4) begin
                $display("INFO tb_klasifier: conf far above both thresholds = %0d", m_conf);
                if (m_conf !== CONF_FS) r6_sat = r6_sat + 1;
            end
            repeat (CAD - 1) @(posedge clk);
        end
        $display("tb_klasifier: [conf] outside range = %0d, nonzero on the threshold = %0d",
                 r6_bad, r6_zero);
        $display("tb_klasifier: [conf] not monotone = %0d, not saturating = %0d, fired on the threshold = %0d",
                 r6_mono, r6_sat, r6_thr);
        $display("tb_klasifier: [conf] words compared: %0d, missing decisions = %0d", 5, mism_dv);

        // -------------------------------------------------------------- summary
        $display("tb_klasifier: gate totals, marked %0d raw %0d mutasi %0d guard %0d tunggal %0d conf %0d",
                 r1_mism, r2_mism, r3_mism, r4_mism, r5_mism, r6_bad + r6_zero + r6_mono + r6_sat + r6_thr);
        if ((r1_mism == 0) && (r2_mism == 0) && (r3_mism == 0) && (r4_mism == 0) &&
            (r5_mism == 0) && (r1_dv == 0) && (r2_dv == 0) && (mism_dv == 0) &&
            (r1_wi == 0) && (r2_wi == 0) && (r1_extra == 0) && (r2_extra == 0) &&
            (r1_tap == 0) && (lat_mism == 0) && (bad_fmt == 0) && (r6_bad == 0) &&
            (r6_zero == 0) && (r6_mono == 0) && (r6_sat == 0) && (r6_thr == 0)) begin
            $display("tb_klasifier: PASS");
            $finish;
        end else begin
            $display("tb_klasifier: FAIL");
            $fatal(1, "tb_klasifier: gate failed");
        end
    end

endmodule

`default_nettype wire
