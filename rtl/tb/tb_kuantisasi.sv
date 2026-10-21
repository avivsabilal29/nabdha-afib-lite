`timescale 1ns/1ps
// ---------------------------------------------------------------------------
// tb_kuantisasi.sv -- Fase 2 of plan 38: the acquisition front end and its input
// quantiser, driven against the Fase 0 golden column of record 04015.
//
// Gates of Fase 2 section 12, and how each one is closed here:
//   1. exhaustive count sweep. Every one of the 4095 counts from -CLAMP_COUNT to
//      +CLAMP_COUNT is driven through the DUT and compared with the reference quantiser
//      built from the package constants, so the run prints `count mismatches: 0`. The
//      rounding rule is half to even and it moves the pre clamp value at exactly four
//      counts, so the pre clamp node is read as well (a marked white box read of
//      dut.pre_raw) and compared count for count, and the four tie counts are printed
//      against the counter example rule, ties away from zero. At the 16 bit word output
//      the two rules cannot be told apart: the tie at 1023.5 rounds to 1024 either way,
//      and the tie at 3070.5 rounds to 3070 or 3071, both above the clamp of 2047, so both
//      words are the rail. That is why the pre node is read as well.
//   2. stream sweep. 450000 words compared against the golden column, mismatches 0, with
//      the absolute sample index checked word for word and every marker bit checked for a
//      faithful passthrough. The sweep runs at one sample per clock, because 450000 samples
//      at the real cadence of RATE_DIV_RST + 1 clocks would be 1.8e11 clocks; the datapath
//      does not read the sample enable at all, and the real cadence is the separate
//      timebase test below, which is gate 4.
//   3. status counters, index and markers against the Fase 0 manifest.
//   4. the 250 Hz timebase: sample enable spacing and pulse count, at RATE_DIV_RST.
//   5. a synthetic gap, because record 04015 carries gap 0, so the lost sample path would
//      otherwise never be exercised.
//
// Why the stimulus is the count stream of the record and not the word column:
//   The count stream cannot be recovered from the golden column at the rail. 406 words of
//   the column are exactly +-CLAMP_WORD, and only 402 of them were clipped; the other 4 are
//   counts that landed exactly on the rail (|c| = 1000), where the strict pre clamp test
//   does not fire. The column does not record which is which, so there the map from word to
//   count is 2 to 1. The testbench measures and prints both facts: 2001 distinct words over
//   4095 counts, and 1 to 1 only for |c| <= 1000, which is 2001 counts to 2001 words.
//   The primary stimulus is therefore the count column of the record, taken from the frozen
//   model adapter by rtl/tb/vektor/siapkan_vektor.py, and admitted only after that helper has
//   proved that the quantiser of every one of those counts reproduces the golden word column
//   with 0 mismatches and that the clipped count is 402. Mode B drives the column only
//   recovery instead, with +RAILC, and reports its clamp count, because the 406 against 402
//   difference is a finding of this phase and not a testbench choice.
//
// Plusargs:
//   +MANIFEST=<path>  Fase 0 manifest, the only source of every expected status number
//   +VECTOR=<path>    Fase 0 golden 16 bit word column, 450000 words
//   +STIM=<path>      stimulus column, 4 hex digits per line: marker nibble then count
//   +RAILC=<count>    mode B only: the count driven for a rail word, default 1000
//   A missing golden file stops the run with a fatal, so it can never read as a pass, the
//   same contract tb_pkg_konstanta.sv uses.
//
// Portability, measured: Icarus 12 accepts afib_lite_pkg::NAME in parameter and localparam
// defaults but not inside a procedural statement, so every package constant used here is
// aliased at module scope first. The package source has to come before this file on the
// command line, which run_sim.sh enforces.
//
// Tool: iverilog 12.0 and vvp from rtl-synthesis/debroot, through run_sim.sh.
// ---------------------------------------------------------------------------
module tb_kuantisasi;

    // ------------------------------------------------------- package constants, aliased
    localparam int unsigned W_IN       = afib_lite_pkg::W_IN;
    localparam int unsigned W_IDX      = afib_lite_pkg::W_IDX;
    localparam int unsigned W_TUSER    = afib_lite_pkg::W_TUSER;
    localparam int unsigned W_RATE_DIV = afib_lite_pkg::W_RATE_DIV;
    // the value constants are signed on purpose: every one of them takes part in signed
    // arithmetic, and an unsigned rail turns `p < -CLAMP_CNT` into a comparison that is
    // always true, which is a bug this file had and the count sweep caught
    localparam integer CLAMP_CNT  = afib_lite_pkg::CLAMP_COUNT;
    localparam integer SHIFT_IN   = afib_lite_pkg::SHIFT_IN;
    localparam integer CLAMP_WORD = afib_lite_pkg::CLAMP_WORD;
    localparam integer DIVISOR    = afib_lite_pkg::Q_DIVISOR;
    localparam integer GAP_RECOV  = afib_lite_pkg::GAP_RECOVERY;
    localparam integer CLK_HZ     = afib_lite_pkg::CLK_HZ;
    localparam integer TU_CLAMP   = afib_lite_pkg::TU_CLAMP;
    localparam integer TU_GAP     = afib_lite_pkg::TU_GAP;
    localparam integer TU_WEAK    = afib_lite_pkg::TU_WEAK;
    localparam integer TU_UNSURE  = afib_lite_pkg::TU_UNSURE;
    localparam integer N_MARK     = afib_lite_pkg::TU_UNSURE + 1;   // 4 marker bits used
    localparam [W_RATE_DIV-1:0] RATE_FIELD = afib_lite_pkg::RATE_DIV_RST;  // 20 bits
    localparam [31:0] RATE_VAL = {{(32-W_RATE_DIV){1'b0}}, RATE_FIELD};

    // the widths the DUT derives from the package, repeated here so this file knows the
    // pipeline depth it is looking at instead of trusting it
    localparam int unsigned W_CNT      = W_IN - SHIFT_IN;                    // 12
    localparam int unsigned SHIFT_MUL  = $clog2(afib_lite_pkg::CLAMP_COUNT); // 11
    localparam int unsigned W_MUL      = W_CNT + SHIFT_MUL;                  // 23
    localparam int unsigned SHIFT_QUO  = $clog2(DIVISOR);                    // 10
    localparam int unsigned W_STEP     = W_MUL - SHIFT_QUO;                  // 13
    localparam int unsigned W_QUO      = W_STEP;                             // 13
    localparam int unsigned W_PRE      = W_QUO + 2;                          // 15
    localparam int unsigned LAT_EXPECT = 2 + W_STEP;                         // 15
    // the last count that still lands on the rail instead of being clipped: pre(DIVISOR)
    // is exactly CLAMP_COUNT, and the strict test below the clamp does not fire there
    localparam integer SMALL_CNT = DIVISOR;                                  // 1000

    localparam integer N_MAX   = 450000;             // capacity, the Fase 0 frame count
    localparam integer N_COUNT = 2 * CLAMP_CNT + 1;  // 4095 counts in the sweep
    localparam [W_IN-1:0] RAIL_BITS  = CLAMP_WORD[W_IN-1:0];
    localparam integer    NRAIL_INT  = -CLAMP_WORD;
    localparam [W_IN-1:0] NRAIL_BITS = NRAIL_INT[W_IN-1:0];
    localparam [2:0] EV_GAP_BITS = afib_lite_pkg::EV_GAP;

    // ------------------------------------------------------- DUT
    reg                   clk_i;
    reg                   rst_ni;
    reg  [W_IN-1:0]       s_tdata;
    reg                   s_tvalid;
    reg                   s_tlast;
    reg  [W_TUSER-1:0]    s_tuser;
    reg                   i_enable;
    reg  [W_RATE_DIV-1:0] i_rate_div;
    reg                   i_clear_counters;
    wire [W_IN-1:0]       m_tdata;
    wire                  m_tvalid;
    wire                  m_overflow;
    wire                  m_tlast;
    wire [W_TUSER-1:0]    m_tuser;
    wire [W_IDX-1:0]      m_sample_idx;
    wire                  m_ev_valid;
    wire [2:0]            m_ev_kind;
    wire [W_IDX-1:0]      m_ev_idx;
    wire [31:0]           m_ev_val;
    wire                  d_valid;
    wire [W_IN-1:0]       d_word;
    wire [31:0]           o_sample_idx;
    wire [31:0]           o_gap_count;
    wire [31:0]           o_clamp_count;

    acq_frontend dut (
        .clk_i (clk_i), .rst_ni (rst_ni),
        .s_tdata (s_tdata), .s_tvalid (s_tvalid), .s_tlast (s_tlast), .s_tuser (s_tuser),
        .i_enable (i_enable), .i_rate_div (i_rate_div),
        .i_clear_counters (i_clear_counters),
        .m_tdata (m_tdata), .m_tvalid (m_tvalid), .m_overflow (m_overflow),
        .m_tlast (m_tlast), .m_tuser (m_tuser), .m_sample_idx (m_sample_idx),
        .m_ev_valid (m_ev_valid), .m_ev_kind (m_ev_kind), .m_ev_idx (m_ev_idx),
        .m_ev_val (m_ev_val),
        .d_valid (d_valid), .d_word (d_word),
        .o_sample_idx (o_sample_idx), .o_gap_count (o_gap_count),
        .o_clamp_count (o_clamp_count)
    );

    initial clk_i = 1'b0;
    always #5 clk_i <= ~clk_i;   // 10 ns, 100 MHz, the PL clock of doc 36 3.1

    // ------------------------------------------------------- storage
    // the golden column is stored 32 bits wide and compared on its low W_IN bits, because
    // the Fase 0 exporter writes the 32 bit pattern of a 16 bit word (8 hex digits per line)
    reg [31:0]             gold_mem [0:N_MAX-1];
    reg [W_CNT+N_MARK-1:0] stim_mem [0:N_MAX-1];
    integer                ref_pre   [0:N_COUNT-1];
    integer                ref_word  [0:N_COUNT-1];
    integer                inv_count [0:N_COUNT-1];
    reg                    seen_word [0:N_COUNT-1];

    integer i, k, c, n_gold, n_stim, n_cmp, n_valid, rc, limit_n, n_expect, mut_mode;
    integer mism_count, mism_pre, mism_stream, mism_index, mism_mark, mism_rail;
    integer mism_d, mism_ev;
    integer weak_seen, clamp_seen, unsure_seen, overflow_seen, tlast_seen;
    integer rail_words, count_at_rail, count_exact_rail, distinct_all, distinct_small;
    integer injective_small, tie_found, gap_seen, ev_seen;
    integer man_frames, man_clamp, man_gap, man_weak, man_uncertain, man_per_col;
    integer rail_c, lat_meas, checks, fails;
    reg [31:0] idx_at_last;
    reg [W_IDX-1:0] m_idx_last;
    reg signed [31:0] cnt_s;
    reg [8*128-1:0] man_path, vec_path, stim_path;

    // the white box read of the pre clamp node: pre_raw is combinational in the last
    // pipeline slice, and m_tdata is registered from it, so the node has to be sampled one
    // clock before the word it belongs to appears. This register does exactly that.
    reg signed [W_PRE-1:0] pre_dut_q;
    always @(posedge clk_i) pre_dut_q <= dut.pre_raw;

    // ------------------------------------------------------- reference quantiser
    // The integer form of rantai.py:163, verified over -4095 to 4095 in I2 section 1 item 5
    // and re-verified against np.rint by rtl/tb/vektor/siapkan_vektor.py.
    function automatic integer ref_pre_of(input integer cc);
        integer n, m, q, rem;
        begin
            n   = cc * CLAMP_CNT;
            m   = (n < 0) ? -n : n;
            q   = m / DIVISOR;                              // m is not negative, so floor
            rem = m - DIVISOR * q;
            if (rem > (DIVISOR / 2)) q = q + 1;
            else if (rem == (DIVISOR / 2)) q = q + (q % 2); // odd goes up, so even wins
            ref_pre_of = (n < 0) ? -q : q;
        end
    endfunction

    // the same quotient under the counter example rule, ties away from zero
    function automatic integer away_pre_of(input integer cc);
        integer n, m, q, rem;
        begin
            n   = cc * CLAMP_CNT;
            m   = (n < 0) ? -n : n;
            q   = m / DIVISOR;
            rem = m - DIVISOR * q;
            if (rem >= (DIVISOR / 2)) q = q + 1;
            away_pre_of = (n < 0) ? -q : q;
        end
    endfunction

    function automatic integer clip_of(input integer p);
        begin
            if (p > CLAMP_CNT) clip_of = CLAMP_CNT;
            else if (p < -(CLAMP_CNT)) clip_of = -(CLAMP_CNT);
            else clip_of = p;
        end
    endfunction

    // The three converters below deliberately drop the high bits of their integer argument,
    // which is exactly what a check needs when it compares a 16 bit word and a 15 bit pre
    // value. The suppression is on purpose, it is not an oversight.
    /* verilator lint_off UNUSEDSIGNAL */
    // the Q12.4 word of a count: the low W_CNT bits of the count shifted left SHIFT_IN
    function automatic [W_IN-1:0] word_of_count(input integer cc);
        begin
            word_of_count = {cc[W_CNT-1:0], {SHIFT_IN{1'b0}}};
        end
    endfunction

    function automatic [W_IN-1:0] word_bits(input integer v);
        begin
            word_bits = v[W_IN-1:0];
        end
    endfunction

    function automatic [W_PRE-1:0] pre_bits(input integer v);
        begin
            pre_bits = v[W_PRE-1:0];
        end
    endfunction
    /* verilator lint_on UNUSEDSIGNAL */

    // census index of a 16 bit word: word / 2**SHIFT_IN + CLAMP_COUNT, 0 to 2*CLAMP_COUNT
    function automatic integer census_index(input [W_IN-1:0] w);
        reg signed [31:0] ext;
        begin
            ext = {{(32-W_IN){w[W_IN-1]}}, w};
            census_index = (ext / (2 ** SHIFT_IN)) + CLAMP_CNT;
        end
    endfunction

    // ------------------------------------------------------- file and check helpers
    function automatic integer count_lines(input [8*128-1:0] path);
        integer f, n;
        reg [8*128-1:0] line;
        begin
            n = 0;
            f = $fopen(path, "r");
            if (f == 0) begin
                $display("FATAL cannot open %0s", path);
                $finish;
            end
            while ($fgets(line, f) != 0)
                if (line != 0) n = n + 1;
            $fclose(f);
            count_lines = n;
        end
    endfunction

    task automatic expect_equal(input [8*48-1:0] name, input integer got,
                                input integer want);
        begin
            checks = checks + 1;
            if (got != want) begin
                fails = fails + 1;
                $display("FAIL %0s got=%0d want=%0d", name, got, want);
            end else begin
                $display("OK   %0s %0d", name, got);
            end
        end
    endtask

    task automatic reset_dut(input integer cycles);
        begin
            rst_ni = 1'b0;
            s_tdata = {W_IN{1'b0}};
            s_tvalid = 1'b0;
            s_tlast = 1'b0;
            s_tuser = {W_TUSER{1'b0}};
            i_enable = 1'b0;
            i_rate_div = {W_RATE_DIV{1'b0}};
            i_clear_counters = 1'b0;
            repeat (cycles) @(posedge clk_i);
            rst_ni = 1'b1;   // released, the DUT is live from the next edge
            @(posedge clk_i);
        end
    endtask

    initial begin
        checks = 0; fails = 0;
        mism_count = 0; mism_pre = 0;
        mism_stream = 0; mism_index = 0; mism_mark = 0; mism_rail = 0;
        mism_d = 0; mism_ev = 0;
        weak_seen = 0; clamp_seen = 0; unsure_seen = 0;
        overflow_seen = 0; tlast_seen = 0; gap_seen = 0; ev_seen = 0;
        rail_words = 0; count_at_rail = 0; count_exact_rail = 0;
        distinct_all = 0; distinct_small = 0; injective_small = 0; tie_found = 0;
        n_cmp = 0; n_valid = 0; lat_meas = 0;
        idx_at_last = 32'd0; m_idx_last = {W_IDX{1'b0}}; cnt_s = 32'sd0;

        man_path  = "/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.manifest.json";
        vec_path  = "/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.masukan16.hex";
        stim_path = "vektor/04015.stimulus.hex";
        rail_c    = SMALL_CNT;
        if (!$value$plusargs("MANIFEST=%s", man_path))
            $display("INFO  no +MANIFEST, default Fase 0 path used");
        if (!$value$plusargs("VECTOR=%s", vec_path))
            $display("INFO  no +VECTOR, default Fase 0 path used");
        if (!$value$plusargs("STIM=%s", stim_path))
            $display("INFO  no +STIM, default stimulus path used");
        if ($value$plusargs("RAILC=%d", rail_c))
            $display("INFO  +RAILC taken from the command line");
        limit_n = N_MAX;
        if ($value$plusargs("LIMIT=%d", limit_n)) begin
            if (limit_n > N_MAX) limit_n = N_MAX;
            if (limit_n < 1) limit_n = 1;
            $display("INFO  short run, +LIMIT=%0d, record wide gates are skipped", limit_n);
        end
        n_expect = limit_n;
        mut_mode = 0;
        if ($value$plusargs("MUT=%d", mut_mode))
            $display("INFO  mutation mode, the timing and gap sections are skipped");

        $display("== tb_kuantisasi, Fase 2, record 04015 ==");
        $display("INFO  manifest [%0s]", man_path);
        $display("INFO  vector   [%0s]", vec_path);
        $display("INFO  stimulus [%0s]", stim_path);

        // ================================================================== golden side
        n_gold = count_lines(vec_path);
        $display("INFO  golden column lines: %0d", n_gold);
        if (n_gold != N_MAX) begin
            $display("FATAL golden column is not %0d words", N_MAX);
            fails = fails + 1;
            $display("count mismatches: 1");
            $finish;
        end

        man_frames = -1; man_clamp = -1; man_gap = -1; man_weak = -1;
        man_uncertain = -1; man_per_col = -1;
        begin : read_manifest
            integer f;
            reg [31:0] v32;
            reg [8*128-1:0] line;
            f = $fopen(man_path, "r");
            if (f == 0) begin
                $display("FATAL manifest missing path=%0s", man_path);
                fails = fails + 1;
                $display("count mismatches: 1");
                $finish;
            end
            while ($fgets(line, f) != 0) begin
                if ($sscanf(line, " \"frames\": %d,", v32) == 1) man_frames = v32;
                if ($sscanf(line, "   \"clamp\": %d,", v32) == 1) man_clamp = v32;
                if ($sscanf(line, "   \"gap\": %d,", v32) == 1) man_gap = v32;
                if ($sscanf(line, "   \"weak\": %d,", v32) == 1) man_weak = v32;
                if ($sscanf(line, "   \"uncertain\": %d,", v32) == 1) man_uncertain = v32;
                if ($sscanf(line, "  \"words_per_column\": %d,", v32) == 1)
                    man_per_col = v32;
            end
            $fclose(f);
        end
        $display("INFO  manifest frames=%0d words_per_column=%0d", man_frames, man_per_col);
        $display("INFO  manifest clamp=%0d gap=%0d", man_clamp, man_gap);
        $display("INFO  manifest weak=%0d uncertain=%0d", man_weak, man_uncertain);
        if ((man_frames != N_MAX) || (man_clamp < 0) || (man_gap < 0) || (man_weak < 0)) begin
            $display("FATAL manifest did not yield the expected fields");
            fails = fails + 1;
            $display("count mismatches: 1");
            $finish;
        end

        $readmemh(vec_path, gold_mem);

        // ================================================================== reference sweep
        for (i = 0; i < N_COUNT; i = i + 1) begin
            c = i - CLAMP_CNT;
            ref_pre[i]   = ref_pre_of(c);
            ref_word[i]  = clip_of(ref_pre[i]) * (2 ** SHIFT_IN);
            inv_count[i] = 0;
            seen_word[i] = 1'b0;
        end
        // brute force inverse over the 4095 counts, ascending, so the smallest count wins.
        // Mode B uses this table instead of dividing a word, exactly as the phase asks.
        for (i = 0; i < N_COUNT; i = i + 1) begin
            rc = census_index(word_bits(ref_word[i]));
            if (seen_word[rc] == 1'b0) begin
                seen_word[rc] = 1'b1;
                inv_count[rc] = i - CLAMP_CNT;
            end
        end
        for (i = 0; i < N_COUNT; i = i + 1) begin
            distinct_all = distinct_all + (seen_word[i] ? 1 : 0);
            c = i - CLAMP_CNT;
            if ((c <= SMALL_CNT) && (c >= -(SMALL_CNT))) distinct_small = distinct_small + 1;
            if ((ref_word[i] == CLAMP_WORD) || (ref_word[i] == -(CLAMP_WORD)))
                count_at_rail = count_at_rail + 1;
            if ((ref_pre[i] == CLAMP_CNT) || (ref_pre[i] == -(CLAMP_CNT)))
                count_exact_rail = count_exact_rail + 1;
        end
        injective_small = 1;
        for (i = (CLAMP_CNT - SMALL_CNT + 1); i <= (CLAMP_CNT + SMALL_CNT); i = i + 1)
            if (!(ref_word[i] > ref_word[i - 1])) injective_small = 0;

        $display("counts swept: %0d", N_COUNT);
        $display("distinct words over the sweep: %0d", distinct_all);
        $display("counts up to %0d: %0d", SMALL_CNT, distinct_small);
        $display("injective up to %0d: %0d", SMALL_CNT, injective_small);
        $display("counts at the rail word: %0d", count_at_rail);
        $display("counts exactly on the rail: %0d", count_exact_rail);

        // the tie counts, both rounding rules, which is where the rule can be seen
        for (i = 0; i < N_COUNT; i = i + 1) begin
            c = i - CLAMP_CNT;
            rc = c * CLAMP_CNT;
            if (rc < 0) rc = -rc;
            if ((rc % DIVISOR) == (DIVISOR / 2)) begin
                tie_found = tie_found + 1;
                $display("tie c=%0d even=%0d away=%0d word=%0d",
                         c, ref_pre[i], away_pre_of(c),
                         clip_of(ref_pre[i]) * (2 ** SHIFT_IN));
            end
        end
        $display("tie counts found: %0d", tie_found);

        // ================================================================== latency
        // Measured, not assumed: LAT_CYCLES in the port list is 1 from Fase 1 and the real
        // pipeline depth of the divider is what this counts.
        reset_dut(4);
        i_enable = 1'b1;
        i_rate_div = {W_RATE_DIV{1'b0}};
        s_tdata = word_of_count(SMALL_CNT);
        s_tvalid = 1'b1;
        @(posedge clk_i);
        s_tvalid = 1'b0;
        #1;
        while ((m_tvalid !== 1'b1) && (lat_meas < 100)) begin
            @(posedge clk_i);
            #1;
            lat_meas = lat_meas + 1;
        end
        $display("pipeline latency measured: %0d", lat_meas + 1);
        expect_equal("pipeline latency", lat_meas + 1, LAT_EXPECT);

        // ================================================================== 1. count sweep
        reset_dut(4);
        i_enable = 1'b1;
        i_rate_div = {W_RATE_DIV{1'b0}};   // one count per clock, the index is not used here
        s_tvalid = 1'b1;
        n_cmp = 0;
        for (i = 0; i < N_COUNT; i = i + 1) begin
            s_tdata = word_of_count(i - CLAMP_CNT);
            s_tuser = {W_TUSER{1'b0}};
            s_tlast = 1'b0;
            @(posedge clk_i);
            #1;
            if (m_tvalid === 1'b1) begin
                if (m_tdata !== word_bits(ref_word[n_cmp])) begin
                    mism_count = mism_count + 1;
                    if (mism_count < 5)
                        $display("MISMATCH word c=%0d got=%0d want=%0d",
                                 n_cmp - CLAMP_CNT, $signed(m_tdata), ref_word[n_cmp]);
                end
                if (pre_dut_q !== pre_bits(ref_pre[n_cmp])) begin
                    mism_pre = mism_pre + 1;
                    if (mism_pre < 5)
                        $display("MISMATCH pre c=%0d got=%0d want=%0d",
                                 n_cmp - CLAMP_CNT, $signed(pre_dut_q), ref_pre[n_cmp]);
                end
                n_cmp = n_cmp + 1;
            end
        end
        for (i = 0; i < LAT_EXPECT; i = i + 1) begin
            s_tvalid = 1'b0;
            @(posedge clk_i);
            #1;
            if (m_tvalid === 1'b1) begin
                if (m_tdata !== word_bits(ref_word[n_cmp])) mism_count = mism_count + 1;
                if (pre_dut_q !== pre_bits(ref_pre[n_cmp])) mism_pre = mism_pre + 1;
                n_cmp = n_cmp + 1;
            end
        end
        $display("counts driven: %0d", N_COUNT);
        $display("count mismatches: %0d", mism_count);
        $display("pre node mismatches: %0d", mism_pre);
        expect_equal("counts emitted", n_cmp, N_COUNT);
        expect_equal("pre node mismatches", mism_pre, 0);

        // ================================================================== 2. stream mode A
        n_stim = count_lines(stim_path);
        $display("INFO  stimulus lines: %0d", n_stim);
        if (n_stim != N_MAX) begin
            $display("FATAL stimulus column is not %0d words", N_MAX);
            fails = fails + 1;
            $display("count mismatches: 1");
            $finish;
        end
        $readmemh(stim_path, stim_mem);

        reset_dut(4);
        i_enable = 1'b1;
        i_rate_div = {W_RATE_DIV{1'b0}};   // one sample per clock, see the file header
        n_cmp = 0; n_valid = 0;
        do @(negedge clk_i); while (!((dut.sample_en_q === 1'b1) &&
                                      (dut.sample_idx_q === {W_IDX{1'b0}})));
        for (i = 0; i < limit_n + LAT_EXPECT; i = i + 1) begin
            if (i < limit_n) begin
                cnt_s = {{(32-W_CNT){stim_mem[i][W_CNT-1]}}, stim_mem[i][W_CNT-1:0]};
                s_tdata = word_of_count(cnt_s);
                s_tuser = {{(W_TUSER-N_MARK){1'b0}}, stim_mem[i][W_CNT+N_MARK-1:W_CNT]};
                s_tlast = (i == (limit_n - 1));
                s_tvalid = 1'b1;
            end else begin
                s_tdata = {W_IN{1'b0}};   // drain, no slot is ever empty, so no gap fires
                s_tuser = {W_TUSER{1'b0}};
                s_tlast = 1'b0;
                s_tvalid = 1'b1;
            end
            @(posedge clk_i);
            #1;
            if (i == (limit_n - 1)) idx_at_last = o_sample_idx;
            if (m_overflow) overflow_seen = overflow_seen + 1;
            if (m_ev_valid) begin
                ev_seen = ev_seen + 1;
                if (m_ev_kind !== EV_GAP_BITS) mism_ev = mism_ev + 1;
                if (m_ev_idx !== n_valid) mism_ev = mism_ev + 1;
                if (m_ev_val !== 32'd0) mism_ev = mism_ev + 1;
            end
            if (m_tvalid === 1'b1) begin
                if (d_valid !== 1'b1) mism_d = mism_d + 1;
                if (d_word !== m_tdata) mism_d = mism_d + 1;
                if (n_cmp < limit_n) begin
                    if (m_tdata !== gold_mem[n_cmp][W_IN-1:0]) begin
                        mism_stream = mism_stream + 1;
                        if (mism_stream < 5)
                            $display("MISMATCH stream i=%0d got=%0d want=%0d",
                                     n_cmp, $signed(m_tdata),
                                     $signed(gold_mem[n_cmp][W_IN-1:0]));
                    end
                    if (m_sample_idx !== n_cmp) begin
                        mism_index = mism_index + 1;
                        if (mism_index < 5)
                            $display("MISMATCH index i=%0d got=%0d", n_cmp, m_sample_idx);
                    end
                    if (m_tuser[TU_WEAK] !== stim_mem[n_cmp][W_CNT+TU_WEAK])
                        mism_mark = mism_mark + 1;
                    if (m_tuser[TU_CLAMP] !== stim_mem[n_cmp][W_CNT+TU_CLAMP])
                        mism_mark = mism_mark + 1;
                    if (m_tuser[TU_GAP] !== stim_mem[n_cmp][W_CNT+TU_GAP])
                        mism_mark = mism_mark + 1;
                    if (m_tuser[TU_WEAK]) weak_seen = weak_seen + 1;
                    if (m_tuser[TU_CLAMP]) clamp_seen = clamp_seen + 1;
                    if (m_tuser[TU_UNSURE]) unsure_seen = unsure_seen + 1;
                    if (m_tlast) tlast_seen = tlast_seen + 1;
                    m_idx_last = m_sample_idx;
                    n_cmp = n_cmp + 1;
                end
                n_valid = n_valid + 1;
            end
        end
        for (i = 0; i < N_MAX; i = i + 1)
            if ((gold_mem[i][W_IN-1:0] == RAIL_BITS) ||
                (gold_mem[i][W_IN-1:0] == NRAIL_BITS))
                rail_words = rail_words + 1;

        $display("words compared: %0d", n_cmp);
        $display("mismatches: %0d", mism_stream);
        $display("index mismatches: %0d", mism_index);
        $display("marker passthrough mismatches: %0d", mism_mark);
        $display("introspection mismatches: %0d", mism_d);
        $display("event sideband mismatches: %0d", mism_ev);
        $display("golden words at the rail: %0d", rail_words);
        $display("marker weak words: %0d", weak_seen);
        $display("marker clamp words: %0d", clamp_seen);
        $display("marker unsure words: %0d", unsure_seen);
        $display("overflow words: %0d", overflow_seen);
        $display("tlast words: %0d", tlast_seen);
        $display("status clamp count: %0d", o_clamp_count);
        $display("status gap count: %0d", o_gap_count);
        $display("status sample index at last word: %0d", idx_at_last);
        $display("last emitted word index: %0d", m_idx_last);
        expect_equal("words compared", n_cmp, n_expect);
        expect_equal("stream mismatches", mism_stream, 0);
        expect_equal("index mismatches", mism_index, 0);
        expect_equal("marker mismatches", mism_mark, 0);
        expect_equal("introspection mismatches", mism_d, 0);
        expect_equal("event sideband mismatches", mism_ev, 0);
        if (limit_n == N_MAX) begin
            expect_equal("clamp count vs manifest", o_clamp_count, man_clamp);
            expect_equal("gap count vs manifest", o_gap_count, man_gap);
            expect_equal("weak words vs manifest", weak_seen, man_weak);
            expect_equal("unsure words vs manifest", unsure_seen, man_uncertain);
            expect_equal("sample index vs manifest", idx_at_last, man_frames - 1);
            expect_equal("last word index", m_idx_last, man_frames - 1);
        end else begin
            expect_equal("sample index vs manifest", idx_at_last, n_expect - 1);
            expect_equal("last word index", m_idx_last, n_expect - 1);
            $display("SKIP  record wide counts, this is a +LIMIT=%0d short run", limit_n);
        end
        expect_equal("overflow words", overflow_seen, 0);
        expect_equal("tlast words", tlast_seen, 1);

        // ================================================================== 3. stream mode B
        // Column only recovery. Every word must match; the clamp count is the finding.
        reset_dut(4);
        i_enable = 1'b1;
        i_rate_div = {W_RATE_DIV{1'b0}};
        n_cmp = 0; n_valid = 0;
        do @(negedge clk_i); while (!((dut.sample_en_q === 1'b1) &&
                                      (dut.sample_idx_q === {W_IDX{1'b0}})));
        for (i = 0; i < limit_n + LAT_EXPECT; i = i + 1) begin
            if (i < limit_n) begin
                rc = inv_count[census_index(gold_mem[i][W_IN-1:0])];
                if (gold_mem[i][W_IN-1:0] == RAIL_BITS) rc = rail_c;
                if (gold_mem[i][W_IN-1:0] == NRAIL_BITS) rc = -rail_c;
                s_tdata = word_of_count(rc);
                s_tuser = {W_TUSER{1'b0}};
                s_tlast = 1'b0;
                s_tvalid = 1'b1;
            end else begin
                s_tdata = {W_IN{1'b0}};
                s_tuser = {W_TUSER{1'b0}};
                s_tlast = 1'b0;
                s_tvalid = 1'b1;
            end
            @(posedge clk_i);
            #1;
            if (m_tvalid === 1'b1) begin
                if (n_cmp < limit_n)
                    if (m_tdata !== gold_mem[n_cmp][W_IN-1:0]) begin
                        mism_rail = mism_rail + 1;
                        if (mism_rail < 5)
                            $display("MISMATCH mode B i=%0d got=%0d want=%0d",
                                     n_cmp, $signed(m_tdata),
                                     $signed(gold_mem[n_cmp][W_IN-1:0]));
                    end
                if (n_cmp < limit_n) n_cmp = n_cmp + 1;
                n_valid = n_valid + 1;
            end
        end
        $display("mode B rail count driven: %0d", rail_c);
        $display("mode B words compared: %0d", n_cmp);
        $display("mode B mismatches: %0d", mism_rail);
        $display("mode B clamp count: %0d", o_clamp_count);
        expect_equal("mode B words compared", n_cmp, n_expect);
        expect_equal("mode B mismatches", mism_rail, 0);

        if (mut_mode == 0) begin
        // ================================================================== 4. timebase
        reset_dut(4);
        i_enable = 1'b1;
        i_rate_div = RATE_FIELD;
        s_tvalid = 1'b1;
        s_tdata = {W_IN{1'b0}};
        s_tuser = {W_TUSER{1'b0}};
        begin : timebase
            integer pulses, last_cycle, spacing, spacing_ok;
            reg [31:0] prev_idx;
            pulses = 0; last_cycle = 0; spacing = 0; spacing_ok = 1;
            prev_idx = o_sample_idx;
            for (k = 0; k < 5 * (RATE_VAL + 1) + 50000; k = k + 1) begin
                @(posedge clk_i);
                #1;
                if (o_sample_idx !== prev_idx) begin
                    // the change right after the reset release is the first free running
                    // pulse and not a period, so counting starts one period in
                    if (k >= RATE_VAL) begin
                        if (pulses > 0) begin
                            if (spacing == 0) spacing = k - last_cycle;
                            else if ((k - last_cycle) != spacing) spacing_ok = 0;
                        end
                        pulses = pulses + 1;
                        last_cycle = k;
                    end
                    prev_idx = o_sample_idx;
                end
            end
            $display("sample_en spacing: %0d", spacing);
            $display("sample_en pulses: %0d", pulses);
            $display("sample_en spacing constant: %0d", spacing_ok);
            expect_equal("sample_en spacing", spacing, RATE_VAL + 1);
            expect_equal("sample_en pulses", pulses, 5);
            expect_equal("spacing constant", spacing_ok, 1);
            expect_equal("clk_hz over period", CLK_HZ / (RATE_VAL + 1), 250);
        end

        // ================================================================== 5. synthetic gap
        reset_dut(4);
        i_enable = 1'b1;
        i_rate_div = {W_RATE_DIV{1'b0}};
        gap_seen = 0; ev_seen = 0; mism_ev = 0;
        s_tdata = {W_IN{1'b0}};
        s_tuser = {W_TUSER{1'b0}};
        s_tlast = 1'b0;
        for (i = 0; i < 2 * GAP_RECOV + 40 + LAT_EXPECT; i = i + 1) begin
            s_tvalid = ~((i >= 6) && (i < 8));   // two slots with no word at all
            @(posedge clk_i);
            #1;
            if (m_ev_valid) begin
                ev_seen = ev_seen + 1;
                if (m_ev_kind !== EV_GAP_BITS) mism_ev = mism_ev + 1;
            end
            if (m_tvalid === 1'b1)
                if (m_tuser[TU_GAP]) gap_seen = gap_seen + 1;
        end
        $display("synthetic gap events: %0d", o_gap_count);
        $display("synthetic gap events on the sideband: %0d", ev_seen);
        $display("synthetic gap marked words: %0d", gap_seen);
        expect_equal("synthetic gap events", o_gap_count, 2);
        expect_equal("synthetic gap sideband events", ev_seen, 2);
        expect_equal("synthetic gap kind mismatches", mism_ev, 0);
        // A lost slot emits no word at all, so the marker has nothing to attach to on the lost
        // sample itself: the recovery span marks exactly GAP_RECOVERY words after the last lost
        // slot, which is what doc 36 3.3 asks for. A gap that arrives as an input marker bit
        // instead rides on a word and marks that word plus the span.
        expect_equal("synthetic gap marked words", gap_seen, GAP_RECOV);
        end   // mut_mode: timing and gap sections

        // ================================================================== summary
        $display("checks: %0d", checks);
        $display("failures: %0d", fails);
        if (fails != 0) $display("gate: FAIL, see the lines above");
        $finish;
    end

endmodule
