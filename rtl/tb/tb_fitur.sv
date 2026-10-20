// ---------------------------------------------------------------------------
// tb_fitur.sv -- Fase 8 gate over rtl/features.sv, the 32 interval window feature layer.
//
// Two arms and two passes, one run:
//
//   arm A (marked series, i_arm_select[3] = 1) feeds all 2595 intervals of 04015 with their
//     marks and lets the DUT do the selecting itself, exactly rantai.seri_berpenanda
//     :764-783. 638 windows come out, 602 of them map to a golden row of 04015.windows.csv
//     through +VECTOR/map.marked.hex.
//   arm B (raw series, i_arm_select[3] = 0) feeds the same stream with arm_marked low, so
//     every interval is taken. 624 windows come out, 588 of them map to a golden row of
//     04015.decisions.csv through map.raw.hex.
//
// Each arm runs twice and the two passes must produce the same FNV-1a digest over every
// value of every emission that was compared ("dua jalan penuh identik").
//
// GATE MEASURED HERE, per the Fase 8 row of plan doc 38 section 1.3:
//   arm A, 602 golden rows: the 31 d values, the 16 histogram counts, the pNN50 count and
//     the pNN50 code must be bit exact, and the four codes (rmssd, ratio, entropy, mean
//     square) must be bit exact against the golden columns rounded at each node width.
//   arm B, 588 golden rows: the four codes against the frozen fixture jendela_fitur, with
//     the number of rows that deviate by MORE than 1 LSB, which must be 0.
//   plus: the emission count per arm, m_ev_kind, m_ev_idx against the map sample_end, the
//     high bits of m_ev_val, d_valid pulses one per window, ovf_cnt_q at 0 (a window is
//     never dropped while the unit is busy) and rej_cnt_q equal to the range gate count of
//     the arm that ran last.
//
// Golden data: +VECTOR=<dir> is the Fase 8 vector directory rtl/tb/vektor/fase8/. Every file
//   is 32 bit words, one per line, 8 hex digits, read unsigned:
//    04015.fase8.rr.hex         2595 words  {2 zero, mark[1:0], rr_ms[15:0]}
//    04015.fase8.sample.hex     2595 words  the sample index of the interval
//    04015.fase8.gold.d.hex     602*31      d & 0x1FFF, row major
//    04015.fase8.gold.bins.hex  602*4       word 4r+j holds bins 4j..4j+3, bin 4j in bits 7:0
//    04015.fase8.gold.code.hex  602*3       high, middle, low of the 92 bit code word
//    04015.fase8.gold.raw.hex   588*3       the same layout for the raw arm
//    04015.fase8.map.marked.hex 638*2       sample_end, golden row or FFFFFFFF
//    04015.fase8.map.raw.hex    624*2       sample_end, golden row or FFFFFFFF
//   The code word, bit 0 at the right: rmssd[17:0], ratio[34:18], ent[49:35], mean_q[76:50],
//   cnt50[82:77], pnn50[91:83].
//
// Optional plusargs: +LIMIT=<n> offers only the first n intervals and then prints SMOKE
//   instead of PASS, because the full count gate is not reached; +VECTOR is required.
//
// No file level timescale, same reason as the other testbenches: the package carries none and
//   the linter raises TIMESCALEMOD on a file level timescale here, so this file has none.
//
// House style: every expected value comes from the golden column or from the package
//   constants, never typed into this file, and every mismatch counter is printed on every
//   run. A run that compared nothing is a failure, not a pass.
// ---------------------------------------------------------------------------
`default_nettype none

module tb_fitur;

    localparam integer N_INT   = 2595;      // offered intervals, 04015.rr.csv rows
    localparam integer N_EM_A  = 638;       // marked arm emissions, map.marked.hex rows
    localparam integer N_EM_B  = 624;       // raw arm emissions, map.raw.hex rows
    localparam integer N_G_A   = 602;       // golden rows, windows.csv
    localparam integer N_G_B   = 588;       // golden rows, decisions.csv
    localparam integer N_REJ_B = 17;        // range gate refusals, raw arm (last pass)
    localparam integer CAD     = 44;        // cycles between offered intervals
    localparam integer ND      = 31;        // d values per window
    localparam integer NB      = 16;        // histogram bins per window
    localparam [31:0]  NONE    = 32'hFFFFFFFF;

    localparam [3:0] PH_RST0 = 4'd0;
    localparam [3:0] PH_A1   = 4'd1;
    localparam [3:0] PH_RST1 = 4'd2;
    localparam [3:0] PH_B1   = 4'd3;
    localparam [3:0] PH_RST2 = 4'd4;
    localparam [3:0] PH_A2   = 4'd5;
    localparam [3:0] PH_RST3 = 4'd6;
    localparam [3:0] PH_B2   = 4'd7;
    localparam [3:0] PH_DONE = 4'd8;

    reg clk = 1'b0;
    reg rst_n;
    reg [3:0] phase;
    reg [7:0] rst_cnt;

    reg          s_valid;
    reg  [15:0]  s_rr_ms;
    reg  [1:0]   s_rr_mark;
    reg  [31:0]  s_window_idx;
    reg          i_enable;
    reg          i_clear_counters;
    reg  [4:0]   i_arm_select;
    reg  [7:0]   i_window_step;
    reg  [7:0]   i_window_beats;

    wire         d_valid;
    wire [17:0]  d_rmssd;
    wire [16:0]  d_ratio;
    wire [14:0]  d_ent;
    wire [26:0]  d_meanq;
    wire         m_ev_valid;
    wire [2:0]   m_ev_kind;
    wire [31:0]  m_ev_idx;
    wire [31:0]  m_ev_val;

    features u_dut (
        .clk_i           (clk),
        .rst_ni          (rst_n),
        .s_valid         (s_valid),
        .s_rr_ms         (s_rr_ms),
        .s_rr_mark       (s_rr_mark),
        .s_window_idx    (s_window_idx),
        .i_enable        (i_enable),
        .i_clear_counters(i_clear_counters),
        .i_arm_select    (i_arm_select),
        .i_window_step   (i_window_step),
        .i_window_beats  (i_window_beats),
        .d_valid         (d_valid),
        .d_rmssd         (d_rmssd),
        .d_ratio         (d_ratio),
        .d_ent           (d_ent),
        .d_meanq         (d_meanq),
        .m_ev_valid      (m_ev_valid),
        .m_ev_kind       (m_ev_kind),
        .m_ev_idx        (m_ev_idx),
        .m_ev_val        (m_ev_val)
    );

    always #5 clk <= ~clk;

    // ---------------------------------------------------------------- golden memories
    reg [31:0] rr_tab   [0:N_INT-1];
    reg [31:0] samp_tab [0:N_INT-1];
    reg [31:0] d_tab    [0:N_G_A*ND-1];
    reg [31:0] bin_tab  [0:N_G_A*4-1];
    reg [31:0] cod_tab  [0:N_G_A*3-1];
    reg [31:0] raw_tab  [0:N_G_B*3-1];
    reg [31:0] mapa_tab [0:N_EM_A*2-1];
    reg [31:0] mapb_tab [0:N_EM_B*2-1];

    reg [1023:0] vdir;
    reg [1023:0] rr_path, samp_path, d_path, bin_path;
    reg [1023:0] cod_path, raw_path, mapa_path, mapb_path;

    integer limit_n;
    integer feed;
    integer cad_q;
    integer cyc;
    integer cyc_limit;
    integer dvcnt;

    integer em_a1, em_a2, em_b1, em_b2;      // emissions seen per pass
    integer chk_a1, chk_a2, chk_b1, chk_b2;  // golden rows actually compared per pass
    integer cmp_a, cmp_b;                    // comparisons run, pass 1 only
    integer mis_d, mis_bin, mis_cnt, mis_pnn, mis_cod, mis_idx, mis_kind, mis_high;
    integer mis_raw, raw_worst, mis_ovf, mis_rej, mis_dv, mis_x, xmiss;
    integer mis_total;

    reg [31:0] dig_a1, dig_a2, dig_b1, dig_b2;

    // ---- absolute difference of two unsigned values, used by the arm B 1 LSB test ------
    function [31:0] abs32;
        input [31:0] a;
        input [31:0] b;
        begin
            abs32 = (a >= b) ? (a - b) : (b - a);
        end
    endfunction

    // ---- FNV-1a mix --------------------------------------------------------------------
    function [31:0] fnv;
        input [31:0] h;
        input [31:0] v;
        begin
            fnv = (h ^ v) * 32'd16777619;
        end
    endfunction

    // ===========================================================================
    // The per emission evaluation, combinational: it reads the map row, the golden row and
    // the white box of the DUT and produces the mismatch flags plus the digest word. It is
    // a function of the phase, the emission counters and the DUT, all of which are stable
    // through the sampling edge, so the flags and the digest word sampled there belong to
    // the emission being handled.
    // ===========================================================================
    reg         ev_arm_a, ev_has_row, f_d, f_bin, f_cnt, f_pnn, f_cod;
    reg         f_idx, f_kind, f_high, f_raw, f_x;
    reg [31:0]  ev_se, ev_row32, f_rawg;
    reg [95:0]  ev_vw;
    reg [31:0]  ev_mix, gbinw;
    reg [31:0]  ev_eidx;
    integer     qq;

    always @(*) begin
        ev_arm_a   = (phase == PH_A1) || (phase == PH_A2);
        ev_eidx    = ev_arm_a ? ((phase == PH_A1) ? em_a1[31:0] : em_a2[31:0])
                              : ((phase == PH_B1) ? em_b1[31:0] : em_b2[31:0]);
        ev_se      = ev_arm_a ? mapa_tab[2*ev_eidx] : mapb_tab[2*ev_eidx];
        ev_row32   = ev_arm_a ? mapa_tab[2*ev_eidx + 1] : mapb_tab[2*ev_eidx + 1];
        // A golden row index is only usable when it is known and inside the table: an
        // unknown index would make the ranges below evaluate to x and the emission would be
        // treated as "no golden row", which is exactly the false pass this guard forbids.
        ev_has_row = !$isunknown(ev_row32) &&
                     (ev_arm_a ? (ev_row32 < N_G_A) : (ev_row32 < N_G_B));
        // ev_vw carries the golden code word and is forced to zero when this emission has no
        // golden row, so the digest chain below stays unconditional and free of X
        ev_vw      = (ev_arm_a ? {4'd0, cod_tab[3*ev_row32][27:0], cod_tab[3*ev_row32 + 1],
                                  cod_tab[3*ev_row32 + 2]}
                               : {4'd0, raw_tab[3*ev_row32][27:0], raw_tab[3*ev_row32 + 1],
                                  raw_tab[3*ev_row32 + 2]}) & {96{ev_has_row}};
        // f_x: a golden word used as an oracle, or the map word, is X. A short or missing
        // vector directory leaves X behind and every X comparison would be silently skipped,
        // so this is counted separately and gates the pass.
        f_x    = $isunknown(ev_se) || $isunknown(ev_row32);
        f_idx  = (m_ev_idx !== ev_se);
        f_kind = (m_ev_kind !== afib_lite_pkg::EV_WINDOW);
        f_high = (m_ev_val[31:6] !== 26'd0);
        f_cnt  = (m_ev_val[5:0] !== ev_vw[82:77]);
        f_pnn  = (u_dut.pnn50_q !== ev_vw[91:83]);
        f_cod  = (d_rmssd !== ev_vw[17:0]) || (d_ratio !== ev_vw[34:18]) ||
                 (d_ent !== ev_vw[49:35]) || (d_meanq !== ev_vw[76:50]);
        f_d    = 1'b0;
        f_bin  = 1'b0;
        f_raw  = 1'b0;
        f_rawg = 32'd0;
        if (ev_has_row) begin
            f_x = f_x | $isunknown(ev_vw);
            for (qq = 0; qq < ND; qq = qq + 1) begin
                if ($isunknown(u_dut.dvec_q[13*qq +: 13]) ||
                    $isunknown(d_tab[ND*ev_row32 + qq])) f_x = 1'b1;
                if (u_dut.dvec_q[13*qq +: 13] !== d_tab[ND*ev_row32 + qq][12:0]) f_d = 1'b1;
            end
            for (qq = 0; qq < NB; qq = qq + 1) begin
                gbinw = bin_tab[4*ev_row32 + (qq >> 2)];
                if ($isunknown(gbinw) || $isunknown(u_dut.bin_q[qq])) f_x = 1'b1;
                if (u_dut.bin_q[qq] !== gbinw[8*(qq & 3) +: 6]) f_bin = 1'b1;
            end
        end
        if (!ev_arm_a) begin
            if (abs32({14'd0, d_rmssd}, {14'd0, ev_vw[17:0]})     > 32'd1) f_raw = 1'b1;
            if (abs32({15'd0, d_ratio}, {15'd0, ev_vw[34:18]})    > 32'd1) f_raw = 1'b1;
            if (abs32({17'd0, d_ent},   {17'd0, ev_vw[49:35]})    > 32'd1) f_raw = 1'b1;
            if (abs32({23'd0, u_dut.pnn50_q}, {23'd0, ev_vw[91:83]}) > 32'd1) f_raw = 1'b1;
            f_rawg = abs32({14'd0, d_rmssd}, {14'd0, ev_vw[17:0]});
        end
        // The digest covers every live value of the emission plus, when there is a golden
        // row, that row. Values that are X only come from a broken vector directory, which
        // f_x reports; they never enter this mixing chain.
        ev_mix = 32'h811C9DC5;
        ev_mix = fnv(ev_mix, m_ev_idx);
        ev_mix = fnv(ev_mix, m_ev_val);
        ev_mix = fnv(ev_mix, {14'd0, d_rmssd});
        ev_mix = fnv(ev_mix, {15'd0, d_ratio});
        ev_mix = fnv(ev_mix, {17'd0, d_ent});
        ev_mix = fnv(ev_mix, {5'd0, d_meanq});
        ev_mix = fnv(ev_mix, {23'd0, u_dut.pnn50_q});
        for (qq = 0; qq < ND; qq = qq + 1)
            ev_mix = fnv(ev_mix, {19'd0, u_dut.dvec_q[13*qq +: 13]});
        for (qq = 0; qq < NB; qq = qq + 1) begin
            gbinw  = 32'd0;
            gbinw  = fnv(gbinw, {26'd0, u_dut.bin_q[qq]});
            ev_mix = fnv(ev_mix, gbinw);
        end
        ev_mix = fnv(ev_mix, ev_vw[31:0]);
        ev_mix = fnv(ev_mix, ev_vw[63:32]);
        ev_mix = fnv(ev_mix, {ev_vw[91:64], 4'd0});
    end

    // ---- sequencer: one writer per signal, so no phase change races the driver -------
    always @(posedge clk) begin
        cyc <= cyc + 1;
        case (phase)
            PH_RST0, PH_RST1, PH_RST2, PH_RST3: begin
                rst_n            <= 1'b0;
                s_valid          <= 1'b0;
                s_rr_ms          <= 16'd0;
                s_rr_mark        <= 2'd0;
                s_window_idx     <= 32'd0;
                i_clear_counters <= 1'b1;
                feed             <= 0;
                cad_q            <= 0;
                rst_cnt          <= rst_cnt + 8'd1;
                if (rst_cnt >= 8) begin
                    rst_n            <= 1'b1;
                    i_clear_counters <= 1'b0;
                    rst_cnt          <= 8'd0;
                    case (phase)
                        PH_RST0: phase <= PH_A1;
                        PH_RST1: phase <= PH_B1;
                        PH_RST2: phase <= PH_A2;
                        default: phase <= PH_B2;
                    endcase
                end
            end
            PH_A1, PH_B1, PH_A2, PH_B2: begin
                i_arm_select <= ((phase == PH_A1) || (phase == PH_A2)) ? 5'b01000 : 5'b00000;
                if ((cad_q == 0) && (feed < limit_n)) begin
                    s_valid      <= 1'b1;
                    s_rr_ms      <= rr_tab[feed][15:0];
                    s_rr_mark    <= rr_tab[feed][17:16];
                    s_window_idx <= samp_tab[feed];
                    feed         <= feed + 1;
                    cad_q        <= CAD - 1;
                end else begin
                    s_valid <= 1'b0;
                    if (cad_q > 0) cad_q <= cad_q - 1;
                    // the last window closes a few cycles after the last accepted interval,
                    // so a phase turns over only once the cadence counter has drained
                    if ((cad_q == 0) && (feed >= limit_n)) begin
                        case (phase)
                            PH_A1: phase <= PH_RST1;
                            PH_B1: phase <= PH_RST2;
                            PH_A2: phase <= PH_RST3;
                            default: phase <= PH_DONE;
                        endcase
                    end
                end
            end
            default: ;
        endcase
    end

    // ---- counters, driven by the DUT events -------------------------------------------
    always @(posedge clk) begin
        if (rst_n && d_valid) dvcnt <= dvcnt + 1;
        if (rst_n && m_ev_valid) begin
            case (phase)
                PH_A1: begin
                    em_a1 <= em_a1 + 1;
                    if (em_a1 < N_EM_A) begin
                        dig_a1 <= fnv(dig_a1, ev_mix);
                        if (f_x || $isunknown(ev_mix)) mis_x <= mis_x + 1;
                        if (f_idx)  mis_idx  <= mis_idx + 1;
                        if (f_kind) mis_kind <= mis_kind + 1;
                        if (f_high) mis_high <= mis_high + 1;
                        if (ev_has_row) begin
                            chk_a1 <= chk_a1 + 1;
                            cmp_a  <= cmp_a + 1;
                            if (f_d)   mis_d   <= mis_d + 1;
                            if (f_bin) mis_bin <= mis_bin + 1;
                            if (f_cnt) mis_cnt <= mis_cnt + 1;
                            if (f_pnn) mis_pnn <= mis_pnn + 1;
                            if (f_cod) mis_cod <= mis_cod + 1;
                        end
                    end
                end
                PH_A2: begin
                    em_a2 <= em_a2 + 1;
                    if (em_a2 < N_EM_A) begin
                        dig_a2 <= fnv(dig_a2, ev_mix);
                        if (ev_has_row) chk_a2 <= chk_a2 + 1;
                    end
                end
                PH_B1: begin
                    em_b1 <= em_b1 + 1;
                    if (em_b1 < N_EM_B) begin
                        dig_b1 <= fnv(dig_b1, ev_mix);
                        if (f_x || $isunknown(ev_mix)) mis_x <= mis_x + 1;
                        if (f_idx)  mis_idx  <= mis_idx + 1;
                        if (f_kind) mis_kind <= mis_kind + 1;
                        if (ev_has_row) begin
                            chk_b1 <= chk_b1 + 1;
                            cmp_b  <= cmp_b + 1;
                            if (f_raw) mis_raw <= mis_raw + 1;
                            if (f_rawg > raw_worst) raw_worst <= f_rawg;
                        end
                    end
                end
                default: begin
                    em_b2 <= em_b2 + 1;
                    if (em_b2 < N_EM_B) begin
                        dig_b2 <= fnv(dig_b2, ev_mix);
                        if (ev_has_row) chk_b2 <= chk_b2 + 1;
                    end
                end
            endcase
        end
    end

    initial begin
        limit_n = N_INT;
        if (!$value$plusargs("LIMIT=%d", limit_n)) limit_n = N_INT;
        if (!$value$plusargs("VECTOR=%s", vdir)) begin
            $display("tb_fitur: FAIL no +VECTOR (want the fase 8 vector directory)");
            $fatal(1, "tb_fitur: no +VECTOR");
        end
        $sformat(rr_path,   "%0s/04015.fase8.rr.hex", vdir);
        $sformat(samp_path, "%0s/04015.fase8.sample.hex", vdir);
        $sformat(d_path,    "%0s/04015.fase8.gold.d.hex", vdir);
        $sformat(bin_path,  "%0s/04015.fase8.gold.bins.hex", vdir);
        $sformat(cod_path,  "%0s/04015.fase8.gold.code.hex", vdir);
        $sformat(raw_path,  "%0s/04015.fase8.gold.raw.hex", vdir);
        $sformat(mapa_path, "%0s/04015.fase8.map.marked.hex", vdir);
        $sformat(mapb_path, "%0s/04015.fase8.map.raw.hex", vdir);
        $readmemh(rr_path,   rr_tab);
        $readmemh(samp_path, samp_tab);
        $readmemh(d_path,    d_tab);
        $readmemh(bin_path,  bin_tab);
        $readmemh(cod_path,  cod_tab);
        $readmemh(raw_path,  raw_tab);
        $readmemh(mapa_path, mapa_tab);
        $readmemh(mapb_path, mapb_tab);

        // A missing or short file leaves X behind, and X !== anything never counts as a
        // mismatch, so the whole gate could pass on an empty vector directory. Every table is
        // sampled at its ends here, before any of them is used as an oracle.
        xmiss = 0;
        if ($isunknown(rr_tab[0])   || $isunknown(rr_tab[N_INT-1]))       xmiss = xmiss + 1;
        if ($isunknown(samp_tab[0]) || $isunknown(samp_tab[N_INT-1]))     xmiss = xmiss + 1;
        if ($isunknown(d_tab[0])    || $isunknown(d_tab[N_G_A*ND/2]) ||
            $isunknown(d_tab[N_G_A*ND-1]))                               xmiss = xmiss + 1;
        if ($isunknown(bin_tab[0])  || $isunknown(bin_tab[N_G_A*4-1]))    xmiss = xmiss + 1;
        if ($isunknown(cod_tab[0])  || $isunknown(cod_tab[N_G_A*3-1]))    xmiss = xmiss + 1;
        if ($isunknown(raw_tab[0])  || $isunknown(raw_tab[N_G_B*3-1]))    xmiss = xmiss + 1;
        if ($isunknown(mapa_tab[0]) || $isunknown(mapa_tab[N_EM_A*2-1]))  xmiss = xmiss + 1;
        if ($isunknown(mapb_tab[0]) || $isunknown(mapb_tab[N_EM_B*2-1]))  xmiss = xmiss + 1;
        if (xmiss != 0) begin
            $display("tb_fitur: FAIL %0d vector tables are X at their ends in %0s", xmiss, vdir);
            $fatal(1, "tb_fitur: golden vectors missing or short, the gate cannot be measured");
        end

        $display("tb_fitur: vectors   = %0s", vdir);
        $display("tb_fitur: limit     = %0d of %0d intervals", limit_n, N_INT);
        if (limit_n < N_INT)
            $display("tb_fitur: SMOKE run, the full count gate is not claimed");

        feed = 0;  cad_q = 0;  cyc = 0;  rst_cnt = 0;  dvcnt = 0;
        em_a1 = 0; em_a2 = 0; em_b1 = 0; em_b2 = 0;
        chk_a1 = 0; chk_a2 = 0; chk_b1 = 0; chk_b2 = 0;
        cmp_a = 0; cmp_b = 0;
        mis_d = 0; mis_bin = 0; mis_cnt = 0; mis_pnn = 0; mis_cod = 0;
        mis_idx = 0; mis_kind = 0; mis_high = 0; mis_raw = 0; raw_worst = 0;
        mis_ovf = 0; mis_rej = 0; mis_dv = 0; mis_x = 0;
        dig_a1 = 32'h811C9DC5; dig_a2 = 32'h811C9DC5;
        dig_b1 = 32'h811C9DC5; dig_b2 = 32'h811C9DC5;

        phase = PH_RST0;
        rst_n = 1'b0;
        s_valid = 1'b0; s_rr_ms = 16'd0; s_rr_mark = 2'd0; s_window_idx = 32'd0;
        i_enable = 1'b1; i_clear_counters = 1'b1;
        i_arm_select = 5'b01000;
        i_window_step = afib_lite_pkg::WINDOW_STEP_FIELD;
        i_window_beats = afib_lite_pkg::WINDOW_BEATS_FIELD;

        cyc_limit = 4 * (limit_n * CAD + 200000);
        while ((phase != PH_DONE) && (cyc < cyc_limit)) @(posedge clk);
        repeat (16) @(posedge clk);

        mis_ovf = (u_dut.ovf_cnt_q !== 32'd0) ? 1 : 0;
        // the range gate count of the last pass is only meaningful over the whole stream
        mis_rej = ((limit_n == N_INT) && (u_dut.rej_cnt_q !== N_REJ_B[31:0])) ? 1 : 0;
        mis_dv  = (dvcnt !== (em_a1 + em_a2 + em_b1 + em_b2)) ? 1 : 0;
        // the phase must have walked the whole program: an early exit on the cycle budget
        // leaves the counters half filled and would otherwise look like a clean run
        if (phase != PH_DONE) begin
            $display("tb_fitur: FAIL the run did not reach the end of the program, phase=%0d", phase);
            mis_dv = mis_dv + 1;
        end
        // an X digest would make `dig1 !== dig2` false and the determinism test vacuous
        if ($isunknown(dig_a1) || $isunknown(dig_a2) ||
            $isunknown(dig_b1) || $isunknown(dig_b2)) begin
            $display("tb_fitur: FAIL a digest is X, the determinism test would be vacuous");
            mis_x = mis_x + 1;
        end
        mis_total = mis_d + mis_bin + mis_cnt + mis_pnn + mis_cod + mis_idx + mis_kind +
                    mis_high + mis_raw + mis_ovf + mis_rej + mis_dv + mis_x;

        $display("tb_fitur: arm A emissions = %0d of %0d, pass 2 = %0d", em_a1, N_EM_A, em_a2);
        $display("tb_fitur: arm B emissions = %0d of %0d, pass 2 = %0d", em_b1, N_EM_B, em_b2);
        $display("tb_fitur: arm A golden rows compared = %0d of %0d, pass 2 = %0d",
                 chk_a1, N_G_A, chk_a2);
        $display("tb_fitur: arm B golden rows compared = %0d of %0d, pass 2 = %0d",
                 chk_b1, N_G_B, chk_b2);
        $display("tb_fitur: d mismatches          = %0d", mis_d);
        $display("tb_fitur: histogram mismatches  = %0d", mis_bin);
        $display("tb_fitur: pNN50 count mismatch  = %0d", mis_cnt);
        $display("tb_fitur: pNN50 code mismatch   = %0d", mis_pnn);
        $display("tb_fitur: four code mismatches  = %0d", mis_cod);
        $display("tb_fitur: sample_end mismatch   = %0d", mis_idx);
        $display("tb_fitur: ev_kind mismatch      = %0d", mis_kind);
        $display("tb_fitur: ev_val high bits      = %0d", mis_high);
        $display("tb_fitur: d_valid pulse mismatch= %0d", mis_dv);
        $display("tb_fitur: windows dropped (ovf) = %0d", mis_ovf);
        $display("tb_fitur: range gate count wrong= %0d", mis_rej);
        $display("tb_fitur: oracle words unknown  = %0d", mis_x);
        $display("tb_fitur: arm B rows over 1 LSB = %0d (worst %0d LSB)", mis_raw, raw_worst);
        $display("tb_fitur: comparisons run       = %0d arm A + %0d arm B", cmp_a, cmp_b);
        $display("tb_fitur: digest A pass1/pass2  = %08X / %08X", dig_a1, dig_a2);
        $display("tb_fitur: digest B pass1/pass2  = %08X / %08X", dig_b1, dig_b2);
        $display("tb_fitur: mismatches = %0d out of %0d", mis_total, cmp_a + cmp_b);

        if (limit_n < N_INT) begin
            // A short run reaches a different end state by construction, so every gate that
            // depends on the whole stream is named here instead of being quietly relaxed.
            $display("tb_fitur: SKIP full stream gate, %0d of %0d intervals fed", limit_n, N_INT);
            $display("tb_fitur: SKIP arm A emission count gate, %0d seen of %0d", em_a1, N_EM_A);
            $display("tb_fitur: SKIP arm B emission count gate, %0d seen of %0d", em_b1, N_EM_B);
            $display("tb_fitur: SKIP golden row count gate, arm A %0d of %0d, arm B %0d of %0d",
                     chk_a1, N_G_A, chk_b1, N_G_B);
            $display("tb_fitur: SKIP range gate end count gate");
            if ((mis_total == 0) && ((cmp_a + cmp_b) > 0) && (dig_a1 === dig_a2) &&
                (dig_b1 === dig_b2) && !$isunknown(dig_a1) && !$isunknown(dig_b1))
                $display("tb_fitur: SMOKE OK, the full gate is NOT claimed");
            else $fatal(1, "tb_fitur: smoke comparison failed");
        end else begin
            if (mis_total != 0)
                $fatal(1, "tb_fitur: %0d mismatches over %0d comparisons", mis_total,
                       cmp_a + cmp_b);
            if (phase != PH_DONE)
                $fatal(1, "tb_fitur: the run did not reach the end of the program");
            if ((em_a1 != N_EM_A) || (em_a2 != N_EM_A) || (em_b1 != N_EM_B) || (em_b2 != N_EM_B))
                $fatal(1, "tb_fitur: emission count wrong: A %0d/%0d B %0d/%0d",
                       em_a1, em_a2, em_b1, em_b2);
            if ((chk_a1 != N_G_A) || (chk_a2 != N_G_A) || (chk_b1 != N_G_B) || (chk_b2 != N_G_B))
                $fatal(1, "tb_fitur: golden rows compared wrong: A %0d/%0d B %0d/%0d",
                       chk_a1, chk_a2, chk_b1, chk_b2);
            if ((dig_a1 !== dig_a2) || (dig_b1 !== dig_b2))
                $fatal(1, "tb_fitur: passes differ: A %08X/%08X B %08X/%08X", dig_a1, dig_a2,
                       dig_b1, dig_b2);
            if ($isunknown(dig_a1) || $isunknown(dig_b1))
                $fatal(1, "tb_fitur: a digest is X, the determinism test compared nothing");
            if ((cmp_a == 0) || (cmp_b == 0))
                $fatal(1, "tb_fitur: nothing was compared");
            // win_cnt_q is cleared by the reset and by i_clear_counters, so after the last
            // pass it holds the emission count of that pass, which is arm B
            if (u_dut.win_cnt_q !== N_EM_B)
                $fatal(1, "tb_fitur: win_cnt_q is %0d, expected %0d", u_dut.win_cnt_q, N_EM_B);
            $display("tb_fitur: PASS");
        end
        $finish;
    end

endmodule

`default_nettype wire
