`timescale 1ns/1ps
// ---------------------------------------------------------------------------
// tb_pkg_konstanta.sv -- constant parity of rtl/afib_lite_pkg.sv against the Fase 0
// golden manifest.
//
// Plan of record: vault doc 38, Fase 1 deliverable 2 and its gate. The testbench reads
// the Fase 0 manifest at run time, never at compile time, and compares two sets:
//   A. every package constant that the manifest can witness (the six measured node
//      extents in columns.*, the record rate, the divider, and the stream layout), and
//   B. every package constant that the manifest cannot witness, against the identity
//      that ties it to another package constant (the typedef family against the width
//      family, the saturation identities, and the encodings frozen by D2, D5, D8, D12).
//
// House rule: no measured result is typed into this file. Every expected value comes
// from the manifest or from afib_lite_pkg. The literals that remain are the zero bases
// and steps of the enumerations and the frozen reset values, because those are owner
// decisions with no numeric witness in any artifact; each one carries D2, D5, D8, D12
// or a doc 36 section in its source tag.
//
// Output contract:
//   one CHECK, BOUND or REVIEW line per constant, then a final line
//   `bit differences: N`. N counts, over every CHECK and BOUND line, the number of
//   differing bits of got XOR want. A BOUND line contributes the popcount of the excess
//   when the bound is violated, so a clean run prints exactly `bit differences: 0` and
//   any violation makes it nonzero. REVIEW lines are printed and deliberately kept out
//   of the count because they record places where the plan's own numbers do not close,
//   which is an owner question, not a testbench failure.
//   A missing manifest prints `FATAL manifest missing path=...` and then
//   `bit differences: 1`, so a missing golden file can never read as a pass.
//
// Portability, measured in this environment: Icarus 12 accepts `afib_lite_pkg::NAME`
// in an elaboration context (parameter and localparam defaults) but not inside a
// procedural statement, and it does not accept `import afib_lite_pkg::*;` at all, so
// this testbench aliases every constant it uses in a localparam at module scope and
// only ever touches the aliases below. The package must be listed before the testbench
// on the iverilog command line, which run_sim.sh now enforces.
//
// Tool: iverilog 12.0 and vvp from rtl-synthesis/debroot, through run_sim.sh.
// ---------------------------------------------------------------------------
module tb_pkg_konstanta;

    // ----------------------------------------------------------------- package side
    // Bit widths, plan 3.4 group 1. Manifest column order is [0] masukan16 [1] lp
    // [2] hp [3] turunan [4] kuadrat [5] jendela.
    localparam int unsigned W_IN        = afib_lite_pkg::W_IN;
    localparam int unsigned W_LP        = afib_lite_pkg::W_LP;
    localparam int unsigned W_HP        = afib_lite_pkg::W_HP;
    localparam int unsigned W_DER       = afib_lite_pkg::W_DER;
    localparam int unsigned W_DER_WORST = afib_lite_pkg::W_DER_WORST;
    localparam int unsigned W_SQ        = afib_lite_pkg::W_SQ;
    localparam int unsigned W_WIN       = afib_lite_pkg::W_WIN;
    localparam int unsigned W_WIN_WORST = afib_lite_pkg::W_WIN_WORST;
    localparam int unsigned W_THR       = afib_lite_pkg::W_THR;
    localparam int unsigned W_TW        = afib_lite_pkg::W_TW;
    localparam int unsigned W_RR_MS     = afib_lite_pkg::W_RR_MS;
    localparam int unsigned W_RR_SMP    = afib_lite_pkg::W_RR_SMP;
    localparam int unsigned W_CONF      = afib_lite_pkg::W_CONF;
    localparam int unsigned W_F_RATIO   = afib_lite_pkg::W_F_RATIO;
    localparam int unsigned W_F_ENT     = afib_lite_pkg::W_F_ENT;
    localparam int unsigned W_F_MEANQ   = afib_lite_pkg::W_F_MEANQ;
    localparam int unsigned W_F_RMSSD   = afib_lite_pkg::W_F_RMSSD;
    localparam int unsigned W_IDX       = afib_lite_pkg::W_IDX;
    localparam int unsigned W_RATE_DIV  = afib_lite_pkg::W_RATE_DIV;
    localparam int unsigned W_TUSER     = afib_lite_pkg::W_TUSER;

    // Saturation points, group 2.
    localparam logic [63:0] CLAMP_COUNT   = afib_lite_pkg::CLAMP_COUNT;
    localparam logic [63:0] SHIFT_IN      = afib_lite_pkg::SHIFT_IN;
    localparam logic [63:0] CLAMP_WORD    = afib_lite_pkg::CLAMP_WORD;
    localparam logic [63:0] SQ_LIMIT      = afib_lite_pkg::SQ_LIMIT;
    localparam logic [63:0] SHIFT_DER     = afib_lite_pkg::SHIFT_DER;
    localparam logic [63:0] THRESH_SCALE  = afib_lite_pkg::THRESH_SCALE;
    localparam logic [63:0] N_WIN         = afib_lite_pkg::N_WIN;
    localparam logic [63:0] N_WIN_ALT     = afib_lite_pkg::N_WIN_ALT;
    localparam logic [63:0] RR_LONG_MS    = afib_lite_pkg::RR_LONG_MS;
    localparam logic [63:0] RR_MAX_MS     = afib_lite_pkg::RR_MAX_MS;
    localparam logic [63:0] GAP_RECOVERY  = afib_lite_pkg::GAP_RECOVERY;

    // Reset operating point, group 5.
    localparam logic [63:0] RATE_DIV_RST       = afib_lite_pkg::RATE_DIV_RST;
    localparam logic [63:0] CLK_HZ             = afib_lite_pkg::CLK_HZ;
    localparam logic [63:0] RATIO_THRESH_RST   = afib_lite_pkg::RATIO_THRESH_RST;
    localparam logic [63:0] ENTROPY_THRESH_RST = afib_lite_pkg::ENTROPY_THRESH_RST;
    localparam logic [63:0] ARM_SELECT_RST     = afib_lite_pkg::ARM_SELECT_RST;
    localparam logic [63:0] WINDOW_BEATS_RST   = afib_lite_pkg::WINDOW_BEATS_RST;
    localparam logic [63:0] WINDOW_STEP_RST    = afib_lite_pkg::WINDOW_STEP_RST;
    localparam logic [63:0] CONF_FULL_SCALE    = afib_lite_pkg::CONF_FULL_SCALE;
    localparam logic [63:0] SEARCH_BACK_DEPTH  = afib_lite_pkg::SEARCH_BACK_DEPTH;
    localparam logic [63:0] DECISION_DEPTH     = afib_lite_pkg::DECISION_DEPTH;

    // Types and enums, group 4. $bits of a package type resolves in Icarus during
    // elaboration, which is where these aliases live.
    localparam int unsigned BITS_WORD_IN = $bits(afib_lite_pkg::word_in_t);
    localparam int unsigned BITS_LP      = $bits(afib_lite_pkg::lp_t);
    localparam int unsigned BITS_HP      = $bits(afib_lite_pkg::hp_t);
    localparam int unsigned BITS_DER     = $bits(afib_lite_pkg::der_t);
    localparam int unsigned BITS_SQ      = $bits(afib_lite_pkg::sq_t);
    localparam int unsigned BITS_WIN     = $bits(afib_lite_pkg::win_t);
    localparam int unsigned BITS_THR     = $bits(afib_lite_pkg::thr_t);
    localparam int unsigned BITS_RR_MS   = $bits(afib_lite_pkg::rr_ms_t);
    localparam int unsigned BITS_IDX     = $bits(afib_lite_pkg::idx_t);
    localparam int unsigned BITS_TUSER   = $bits(afib_lite_pkg::tuser_t);
    localparam int unsigned BITS_CONF    = $bits(afib_lite_pkg::conf_t);

    localparam logic [63:0] KELAS_UNDECIDED = afib_lite_pkg::KELAS_UNDECIDED;
    localparam logic [63:0] KELAS_NORMAL    = afib_lite_pkg::KELAS_NORMAL;
    localparam logic [63:0] KELAS_REVIEW    = afib_lite_pkg::KELAS_REVIEW;
    localparam logic [63:0] EV_NONE         = afib_lite_pkg::EV_NONE;
    localparam logic [63:0] EV_QRS          = afib_lite_pkg::EV_QRS;
    localparam logic [63:0] EV_RR           = afib_lite_pkg::EV_RR;
    localparam logic [63:0] EV_WINDOW       = afib_lite_pkg::EV_WINDOW;
    localparam logic [63:0] RND_TIES_EVEN   = afib_lite_pkg::RND_TIES_EVEN;
    localparam logic [63:0] RR_MARK_KEEP    = afib_lite_pkg::RR_MARK_KEEP;
    localparam logic [63:0] RR_MARK_DROP    = afib_lite_pkg::RR_MARK_DROP;
    localparam logic [63:0] RR_MARK_GAP     = afib_lite_pkg::RR_MARK_GAP;

    // ----------------------------------------------------------------- manifest side
    localparam logic [8*272-1:0] MANIFEST_DEFAULT =
        "/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0/04015.manifest.json";

    reg   [8*272-1:0]  man_path;
    reg   [8*1024-1:0] line;
    integer            fh, lines_read;
    reg   [63:0]       c_min   [6];
    reg   [63:0]       c_max   [6];
    reg   [8*16-1:0]   c_name  [6];
    integer            n_min, n_max, n_above;
    reg   [63:0]       man_rate, man_frames, man_hex_digits, man_bytes_per_word;
    reg   [63:0]       man_words_per_line, man_total_words, man_columns;
    reg   [63:0]       man_words_per_column, man_mismatches, man_fixture_words;
    reg   [63:0]       man_above;
    reg   [63:0]       v64;

    integer bit_diffs, checks;

    // ----------------------------------------------------------------- helpers
    function automatic integer pop64(input logic [63:0] v);
        integer i, s;
        begin
            s = 0;
            for (i = 0; i < 64; i = i + 1) s = s + ((v[i] == 1'b1) ? 1 : 0);
            pop64 = s;
        end
    endfunction

    function automatic logic [63:0] abs64(input logic [63:0] v);
        reg signed [63:0] sv;
        begin
            sv = $signed(v);
            abs64 = (sv < 0) ? (-sv) : v;
        end
    endfunction

    // Magnitude bits of the most negative extent: 0 for min = 0.
    function automatic integer neg_bits(input logic [63:0] v);
        begin
            if (abs64(v) == 64'd0) neg_bits = 0;
            else neg_bits = $clog2(abs64(v));
        end
    endfunction

    function automatic integer pos_bits(input logic [63:0] v);
        begin
            if (v == 64'd0) pos_bits = 0;
            else pos_bits = $clog2(v + 64'd1);
        end
    endfunction

    // Bits needed to hold both extents as a two's complement number. This is doc 36
    // section 2.2 column "Lebar dua komplemen", the column the package widths follow.
    function automatic integer sig_width(input logic [63:0] mn, input logic [63:0] mx);
        integer a, b;
        begin
            a = pos_bits(mx);
            b = neg_bits(mn);
            sig_width = ((a > b) ? a : b) + 1;
        end
    endfunction

    // The top of a signed field of w bits: 2**(w-1) - 1.
    function automatic logic [63:0] signed_top(input integer w);
        begin signed_top = (64'd1 << (w - 1)) - 64'd1; end
    endfunction

    // The magnitude of the most negative value of a signed field of w bits: 2**(w-1).
    function automatic logic [63:0] signed_bottom(input integer w);
        begin signed_bottom = (64'd1 << (w - 1)); end
    endfunction

    task automatic check(input logic [8*48-1:0] name, input logic [63:0] got,
                         input logic [63:0] want, input logic [8*72-1:0] src);
        reg [63:0] d;
        integer    pc;
        begin
            checks = checks + 1;
            d  = got ^ want;
            pc = pop64(d);
            bit_diffs = bit_diffs + pc;
            $display("CHECK %-26s got=%-12d want=%-12d diffs=%-2d %-4s src=%0s",
                     name, got, want, pc, (pc == 0) ? "PASS" : "FAIL", src);
        end
    endtask

    task automatic bound_le(input logic [8*48-1:0] name, input logic [63:0] got,
                            input logic [63:0] lim, input logic [8*72-1:0] src);
        reg [63:0] excess;
        integer    pc;
        begin
            checks = checks + 1;
            excess = (got > lim) ? (got - lim) : 64'd0;
            pc = pop64(excess);
            bit_diffs = bit_diffs + pc;
            $display("BOUND %-26s got=%-12d <= lim=%-12d excess=%-2d %-4s src=%0s",
                     name, got, lim, pc, (pc == 0) ? "PASS" : "FAIL", src);
        end
    endtask

    task automatic review(input logic [8*48-1:0] name, input logic [63:0] got,
                          input logic [63:0] other, input logic [8*72-1:0] src);
        begin
            $display("REVIEW %-25s got=%-12d other=%-12d not counted src=%0s",
                     name, got, other, src);
        end
    endtask

    // ----------------------------------------------------------------- read manifest
    integer i;

    initial begin
        bit_diffs  = 0;
        checks     = 0;
        lines_read = 0;
        n_min      = 0;
        n_max      = 0;
        n_above    = 0;
        man_above  = 64'd0;
        for (i = 0; i < 6; i = i + 1) begin
            c_min[i]  = 64'd0;
            c_max[i]  = 64'd0;
            c_name[i] = "unset";
        end

        man_path = MANIFEST_DEFAULT;
        if ($value$plusargs("MANIFEST=%s", man_path))
            $display("INFO  manifest path taken from the +MANIFEST plusarg");
        $display("INFO  manifest path [%0s]", man_path);

        fh = $fopen(man_path, "r");
        if (fh == 0) begin
            $display("FATAL manifest missing path=%0s", man_path);
            $display("FATAL no constant could be checked, the golden side is absent");
            $display("bit differences: 1");
            $finish;
        end

        while ($fgets(line, fh) != 0) begin
            lines_read = lines_read + 1;

            if ($sscanf(line, "  \"min\": %d,", v64) == 1) begin
                if (n_min < 6) c_min[n_min] = v64;
                n_min = n_min + 1;
            end
            if ($sscanf(line, "  \"max\": %d,", v64) == 1) begin
                if (n_max < 6) c_max[n_max] = v64;
                n_max = n_max + 1;
            end
            if ($sscanf(line, "   \"words_above_2p31\": %d,", v64) == 1) begin
                n_above = n_above + 1;
                if (v64 > man_above) man_above = v64;
            end
            if ($sscanf(line, " \"rate_hz\": %d", v64) == 1) man_rate = v64;
            if ($sscanf(line, " \"frames\": %d,", v64) == 1) man_frames = v64;
            if ($sscanf(line, "  \"hex_digits\": %d,", v64) == 1) man_hex_digits = v64;
            if ($sscanf(line, "  \"bytes_per_word\": %d,", v64) == 1) man_bytes_per_word = v64;
            if ($sscanf(line, "  \"words_per_line\": %d,", v64) == 1) man_words_per_line = v64;
            if ($sscanf(line, "  \"total_words\": %d,", v64) == 1) man_total_words = v64;
            if ($sscanf(line, "  \"columns\": %d,", v64) == 1) man_columns = v64;
            if ($sscanf(line, "  \"words_per_column\": %d,", v64) == 1) man_words_per_column = v64;
            if ($sscanf(line, "  \"mismatches\": %d,", v64) == 1) man_mismatches = v64;
            if ($sscanf(line, "  \"fixture_masukan16_words\": %d,", v64) == 1) man_fixture_words = v64;
        end
        $fclose(fh);

        c_name[0] = "masukan16";
        c_name[1] = "lp";
        c_name[2] = "hp";
        c_name[3] = "turunan";
        c_name[4] = "kuadrat";
        c_name[5] = "jendela";

        $display("INFO  manifest lines read %0d", lines_read);
        $display("INFO  columns parsed min=%0d max=%0d words_above_2p31=%0d", n_min, n_max, n_above);
        for (i = 0; i < 6; i = i + 1)
            $display("INFO  column[%0d] %-9s min=%-11d max=%-11d signed_width=%0d",
                     i, c_name[i], $signed(c_min[i]), c_max[i], sig_width(c_min[i], c_max[i]));

        // =================================================================== section A
        // A1. The measured extent of each node against the declared width. This is the
        // check that fails if a package width is one bit short or one bit too wide.
        check("width.masukan16", sig_width(c_min[0], c_max[0]), W_IN,  "doc36 2.2 columns.masukan16");
        check("width.lp",        sig_width(c_min[1], c_max[1]), W_LP,  "doc36 2.2 columns.lp");
        check("width.hp",        sig_width(c_min[2], c_max[2]), W_HP,  "doc36 2.2 columns.hp");
        check("width.turunan",   sig_width(c_min[3], c_max[3]), W_DER, "doc36 2.2 columns.turunan");
        check("width.kuadrat",   sig_width(c_min[4], c_max[4]), W_SQ,  "doc36 2.2 columns.kuadrat");
        check("width.jendela",   sig_width(c_min[5], c_max[5]), W_WIN, "doc36 2.2 columns.jendela");

        // A2. Both extents must fit the declared signed field.
        bound_le("fit.masukan16.max", c_max[0], signed_top(W_IN), "W_IN top");
        bound_le("fit.masukan16.min", abs64(c_min[0]), signed_bottom(W_IN), "W_IN bottom");
        bound_le("fit.lp.max",    c_max[1], signed_top(W_LP), "W_LP top");
        bound_le("fit.lp.min",    abs64(c_min[1]), signed_bottom(W_LP), "W_LP bottom");
        bound_le("fit.hp.max",    c_max[2], signed_top(W_HP), "W_HP top");
        bound_le("fit.hp.min",    abs64(c_min[2]), signed_bottom(W_HP), "W_HP bottom");
        bound_le("fit.turunan.max", c_max[3], signed_top(W_DER), "W_DER top");
        bound_le("fit.turunan.min", abs64(c_min[3]), signed_bottom(W_DER), "W_DER bottom");
        bound_le("fit.kuadrat.max", c_max[4], signed_top(W_SQ), "W_SQ top");
        bound_le("fit.jendela.max", c_max[5], signed_top(W_WIN), "W_WIN top");

        // A3. The clamp pair. The largest input word of the record must be exactly the
        // declared CLAMP_WORD, and the most negative sample must sit inside the clamp.
        check("clamp.word.max", c_max[0], CLAMP_WORD, "CLAMP_WORD vs columns.masukan16.max");
        bound_le("clamp.min.inside", abs64(c_min[0]), CLAMP_WORD,
                 "columns.masukan16.min inside CLAMP_WORD");

        // A4. The square node pins two rules at once. kuadrat.max must equal the square
        // of the arithmetic (floor) shift of the most negative derivative, which pins
        // the floor rule RND_FLOOR and the shift-before-square order together.
        // Truncation toward zero would give 18719 squared, and this check rejects it.
        begin : sq_check
            reg signed [63:0] dmin_s, shifted_s;
            dmin_s    = $signed(c_min[3]);
            shifted_s = dmin_s >>> SHIFT_DER;
            check("square.from.derivative", shifted_s * shifted_s, c_max[4],
                  "kuadrat.max vs (turunan.min >>> SHIFT_DER)**2");
            bound_le("square.limit", abs64(shifted_s), SQ_LIMIT,
                     "shifted derivative inside SQ_LIMIT");
        end

        // A5. The window node is a running sum of squares: bounded above by N_WIN
        // squares, below by any single square, and worst case by the doc 36 2.4 number.
        bound_le("window.sum.upper", c_max[5], N_WIN * c_max[4], "N_WIN * kuadrat.max");
        bound_le("window.sum.lower", c_max[4], c_max[5], "kuadrat.max");
        bound_le("window.worst.case", c_max[5], N_WIN * SQ_LIMIT * SQ_LIMIT,
                 "N_WIN * SQ_LIMIT**2, doc 36 2.4");

        // A6. The divider and the record rate. CLK_HZ is the one system parameter this
        // package carries for the check, see its comment in the package.
        check("rate.divider", RATE_DIV_RST + 64'd1, CLK_HZ / man_rate,
              "RATE_DIV_RST vs manifest rate_hz");
        check("rate.divider.width", sig_width(64'd0, RATE_DIV_RST), W_RATE_DIV,
              "D12: 399999 needs 19 bit, the field is declared 20");
        check("window.above_2p31", (man_above > 64'd0) ? 64'd1 : 64'd0, 64'd1,
              "jendela holds words at or above 2**31, doc 36 2.2 unsigned column");

        // A7. Stream layout facts the manifest states about itself, kept here because a
        // wrong layout would invalidate every extent above.
        check("stream.total_words", man_total_words, man_frames * man_columns, "gate.total_words");
        check("stream.words_per_column", man_words_per_column, man_frames, "gate.words_per_column");
        check("stream.bytes_per_word", man_bytes_per_word,
              man_hex_digits + man_words_per_line, "format.bytes_per_word");
        check("stream.column_count", n_min, man_columns, "count of parsed min lines");
        check("stream.min_max_pairs", n_max, n_min, "count of parsed max lines");
        check("stream.above_2p31_fields", n_above, n_min, "count of words_above_2p31 fields");
        check("adapter.mismatches", man_mismatches, 64'd0, "adapter_check.mismatches");
        check("adapter.fixture_words", man_fixture_words, man_frames,
              "adapter_check.fixture_masukan16_words");

        // =================================================================== section B
        // B1. Saturation identities that close against other package constants.
        check("clamp.word.identity", CLAMP_WORD, CLAMP_COUNT * (64'd1 << SHIFT_IN),
              "CLAMP_COUNT << SHIFT_IN");
        check("rr.max.identity", RR_MAX_MS, (64'd1 << W_RR_MS) - 64'd1, "2**W_RR_MS - 1");
        check("thresh.scale.identity", THRESH_SCALE, (64'd1 << SHIFT_DER), "2**SHIFT_DER");
        check("window.pair.identity", N_WIN, N_WIN_ALT + 64'd1, "N_WIN_ALT + 1");
        check("derivative.worst.identity", W_DER_WORST, W_DER + 1, "W_DER + 1");
        check("window.worst.identity", $clog2(N_WIN * SQ_LIMIT * SQ_LIMIT + 64'd1), W_WIN_WORST,
              "doc 36 2.4 states 121318382342 is 37 bit");
        bound_le("rr.long.inside.max", RR_LONG_MS, RR_MAX_MS, "RR_LONG_MS inside W_RR_MS");

        // B2. The typedef family must agree with the width family, bit for bit.
        check("bits.word_in_t", BITS_WORD_IN, W_IN,  "group 4 vs group 1");
        check("bits.lp_t",      BITS_LP,      W_LP,  "group 4 vs group 1");
        check("bits.hp_t",      BITS_HP,      W_HP,  "group 4 vs group 1");
        check("bits.der_t",     BITS_DER,     W_DER, "group 4 vs group 1");
        check("bits.sq_t",      BITS_SQ,      W_SQ,  "group 4 vs group 1");
        check("bits.win_t",     BITS_WIN,     W_WIN, "group 4 vs group 1");
        check("bits.thr_t",     BITS_THR,     W_THR, "group 4 vs group 1");
        check("bits.rr_ms_t",   BITS_RR_MS,   W_RR_MS, "group 4 vs group 1");
        check("bits.idx_t",     BITS_IDX,     W_IDX, "group 4 vs group 1");
        check("bits.tuser_t",   BITS_TUSER,   W_TUSER, "group 4 vs group 1");
        check("bits.conf_t",    BITS_CONF,    W_CONF, "group 4 vs group 1");

        // B3. Encodings frozen by the owner decisions. The base and the step are the
        // decision itself, so they are the only literals in this testbench body.
        check("enum.kelas.base", KELAS_UNDECIDED, 64'd0, "D2 reset value 0");
        check("enum.kelas.step1", KELAS_NORMAL - KELAS_UNDECIDED, 64'd1, "D2");
        check("enum.kelas.step2", KELAS_REVIEW - KELAS_NORMAL, 64'd1, "D2");
        check("enum.event.base", EV_NONE, 64'd0, "plan 3.2 m_ev_kind");
        check("enum.event.qrs", EV_QRS - EV_NONE, 64'd1, "plan 3.2 m_ev_kind");
        check("enum.event.window", EV_WINDOW - EV_RR, 64'd1, "plan 3.2 m_ev_kind");
        check("enum.rnd.base", RND_TIES_EVEN, 64'd0, "plan 3.4 group 3 order");
        check("enum.mark.base", RR_MARK_KEEP, 64'd0, "doc 36 2.7 four marks");
        check("enum.mark.gap.last", RR_MARK_GAP - RR_MARK_DROP, 64'd1, "doc 36 2.7 four marks");

        // B4. Reset operating point: the arm mask must light the four arms the D8 lock
        // names, the window pair must be the D5 lock, the confidence scale the D2b scale,
        // and the gap recovery must close against the doc 36 3.6 chain of stage delays.
        check("rst.arm.four.lit", ((ARM_SELECT_RST & 64'h0F) == 64'h0F) ? 64'd1 : 64'd0, 64'd1,
              "D8 four arms lit after reset");
        check("rst.window.beats", WINDOW_BEATS_RST, 64'd32, "D5 lock");
        check("rst.window.step", WINDOW_STEP_RST, 64'd4, "D5 lock");
        check("rst.ratio.thresh", RATIO_THRESH_RST, 64'd33, "D8 P1 0.165 in 1/200 units");
        check("rst.entropy.thresh", ENTROPY_THRESH_RST, 64'd63, "D8 P1 0.63 in 1/100 units");
        check("conf.full.scale", CONF_FULL_SCALE, 64'd1000, "D2b");
        check("gap.recovery", GAP_RECOVERY, 64'd12 + 64'd32 + 64'd4 + N_WIN + 64'd27 + 64'd18,
              "doc 36 3.6 chain of stage delays");

        // =================================================================== section C
        // REVIEW lines: places where the plan's own numbers do not close, or where a
        // package constant has no witness anywhere. Printed so every constant appears in
        // the output, and deliberately outside the bit count.
        review("square.bound.width", $clog2(SQ_LIMIT * SQ_LIMIT + 64'd1), W_SQ,
               "resolved: 30 bit datapath, SQ_SAT clamp at 2**30-1, overflow flag");
        review("searchback.width", W_THR, W_TW,
               "resolved: W_THR 30 covers the search back word, doc 36 2.2.1");
        review("buffer.depths", SEARCH_BACK_DEPTH, DECISION_DEPTH,
               "design choice not measured, labelled in the package");
        review("rr.samples.width", W_RR_SMP, W_RR_MS,
               "design choice not measured, TASK_BRIEF 2.1 gives 15");
        review("feature.widths.other", W_F_RATIO + W_F_ENT + W_F_MEANQ + W_F_RMSSD, W_CONF,
               "sum of the four feature widths, doc 36 5.5 binding column");

        $display("checks: %0d", checks);
        $display("review lines: 5");
        $display("bit differences: %0d", bit_diffs);
        $finish;
    end

endmodule
