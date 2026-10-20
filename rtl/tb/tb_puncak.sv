// ---------------------------------------------------------------------------
// tb_puncak.sv -- parity gate for rtl/peak_detect.sv, plan doc 38 phase 5.
//
// One run, one gate list, every number read from the golden data:
//
//   peaks    the 4777 peak positions of rtlplan2/fase5/04015.peaks.csv, compared one for
//            one with the positions the DUT reports on d_dbg, and with the golden values
//            of the same row: envelope value pv, filtered peak pk_f, slope kem, snapshot
//            threshold i1, the peak verdict flags and the event index.
//   qrs      the 2596 recorded beats, in order, against the qrs_sample_index column. Six
//            of the 4777 peaks are recorded by the search-back walk and two of those six
//            move the recorded index backwards, so the index is NOT the peak position and
//            this gate cannot be met by echoing the position column.
//   states   the nine ambang_state elements at the end of a full run, against the frozen
//            manifest counts.
//   stream   m_tdata, m_tvalid, m_sample_idx, m_tuser and m_tlast against the golden
//            jendela column, the same word for word check tb_integrator.sv runs.
//
// Golden data, two directories:
//   +VECTOR=<dir>  the Fase 0 columns, 32 bit words, exactly 8 hex digits, one per line:
//                    04015.jendela.hex   the window word, 33 bit signed, 32 unsigned
//                    04015.hp.hex        the high pass word, 26 bit signed, sign extended
//                    04015.turunan.hex   the slope word, 24 bit signed, sign extended
//                  The jendela column holds 27 words at or above 2**31 (largest
//                  3105281786), so this file declares the memories unsigned reg [31:0] and
//                  never reads a column as a signed 32 bit value.
//   +EXPECT=<dir>  the Fase 5 vectors derived from the golden CSVs by
//                  rtl/tb/vektor/fase5/siapkan_vektor_fase5.py. Nothing here is typed in:
//                  every expected value and every count comes from these files.
//
// Optional plusarg: +LIMIT=<n> for a short pass. The expected peak and beat counts are then
//   recomputed from the golden position column, so a short run is still a real gate, except
//   for the nine ambang_state elements, which are an end of run quantity of the full record
//   and are marked not checked on a short run.
//
// RADIUS_GOLD is the only number typed in this file that belongs to the frozen model rather
//   than to the golden data: the scanner radius, rantai.py:55. It is needed to know which
//   golden peaks a truncated run can still decide, and afib_lite_pkg carries no Fase 5
//   constant for it.
//
// No file level timescale, same reason as the other testbenches.
//
// House style: expected values come from the golden column or from the package constants,
//   never typed here.
// ---------------------------------------------------------------------------
`default_nettype none

module tb_puncak;

    localparam integer N_MAX   = 450000;
    localparam integer CAD     = 4;       // cycles between samples
    localparam integer PK_CAP  = 16384;   // array capacity, not a golden count
    localparam integer QRS_CAP = 8192;
    localparam integer RADIUS_GOLD = 27;  // rantai.py:55, the scanner radius

    // d_dbg word map, the same layout rtl/peak_detect.sv documents
    localparam integer DBG_CALON   = 0;
    localparam integer DBG_CARI    = 1;
    localparam integer DBG_DIPER   = 2;
    localparam integer DBG_DITOL   = 3;
    localparam integer DBG_TERIMA  = 4;
    localparam integer DBG_BERI    = 5;
    localparam integer DBG_SEMAI   = 6;
    localparam integer DBG_PENANDA = 7;
    localparam integer DBG_LANGKAH = 8;
    localparam integer DBG_PV      = 9;
    localparam integer DBG_KEM     = 10;
    localparam integer DBG_FLAGS   = 11;
    localparam integer DBG_POS     = 12;
    localparam integer DBG_RAILS   = 13;
    localparam integer DBG_WORDS   = 9;   // the nine ambang_state words, words 0 to 8

    localparam integer W_THR_W = afib_lite_pkg::W_THR;   // 30, the introspection width

    localparam [2:0] PH_RST  = 3'd0;
    localparam [2:0] PH_GOLD = 3'd1;
    localparam [2:0] PH_DONE = 3'd2;

    reg clk = 1'b0;
    reg rst_n;
    reg [2:0] phase;
    reg [3:0] rst_cnt;

    reg  [32:0] s_tdata;
    reg  [25:0] s_hp;
    reg  [23:0] s_besaran;
    reg         s_tvalid;
    reg         s_tlast;
    reg  [7:0]  s_tuser;
    reg  [31:0] s_sample_idx;
    reg         i_enable;
    reg         i_clear_counters;

    wire [32:0]  m_tdata;
    wire         m_tvalid;
    wire         m_overflow;
    wire         m_tlast;
    wire [7:0]   m_tuser;
    wire [31:0]  m_sample_idx;
    wire         m_ev_valid;
    wire [2:0]   m_ev_kind;
    wire [31:0]  m_ev_idx;
    wire [31:0]  m_ev_val;
    wire         d_valid;
    wire [29:0]  d_thr;
    wire [29:0]  d_pk;
    wire [31:0]  o_beat_count;
    wire [447:0] d_dbg;
    wire         d_dbg_valid;

    peak_detect u_dut (
        .clk_i            (clk),
        .rst_ni           (rst_n),
        .s_tdata          (s_tdata),
        .s_tvalid         (s_tvalid),
        .s_tlast          (s_tlast),
        .s_tuser          (s_tuser),
        .s_sample_idx     (s_sample_idx),
        .i_enable         (i_enable),
        .i_clear_counters (i_clear_counters),
        .m_tdata          (m_tdata),
        .m_tvalid         (m_tvalid),
        .m_overflow       (m_overflow),
        .m_tlast          (m_tlast),
        .m_tuser          (m_tuser),
        .m_sample_idx     (m_sample_idx),
        .m_ev_valid       (m_ev_valid),
        .m_ev_kind        (m_ev_kind),
        .m_ev_idx         (m_ev_idx),
        .m_ev_val         (m_ev_val),
        .d_valid          (d_valid),
        .d_thr            (d_thr),
        .d_pk             (d_pk),
        .o_beat_count     (o_beat_count),
        // the market corner: peak_detect.sv carries these two inputs and two introspection
        // outputs in addition to the frozen port list; see the report for the deviation
        .s_hp             (s_hp),
        .s_besaran        (s_besaran),
        .d_dbg            (d_dbg),
        .d_dbg_valid      (d_dbg_valid)
    );

    always #5 clk <= ~clk;

    reg [31:0] mem_win [0:N_MAX-1];
    reg [31:0] mem_hp  [0:N_MAX-1];
    reg [31:0] mem_bes [0:N_MAX-1];

    reg [31:0] mem_pos   [0:PK_CAP-1];
    reg [31:0] mem_pv    [0:PK_CAP-1];
    reg [31:0] mem_pkf   [0:PK_CAP-1];
    reg [31:0] mem_kem   [0:PK_CAP-1];
    reg [31:0] mem_i1    [0:PK_CAP-1];
    reg [31:0] mem_i2    [0:PK_CAP-1];
    reg [31:0] mem_flag  [0:PK_CAP-1];
    reg [31:0] mem_evidx [0:PK_CAP-1];
    reg [31:0] mem_kind  [0:PK_CAP-1];

    reg [31:0] mem_qrs  [0:QRS_CAP-1];
    reg [31:0] mem_amb  [0:15];
    reg [31:0] mem_cnt  [0:3];

    reg [1023:0] vdir;
    reg [1023:0] edir;
    reg [1023:0] f_tmp;

    integer limit_n;
    integer feed;
    integer nout;
    integer cyc;
    integer cyc_limit;
    integer cad_q;
    integer pk_max;
    integer qrs_max;
    integer amb_max;
    integer frame_max;
    integer exp_pk;
    integer exp_qrs;
    integer widx;

    integer npk;        // peaks seen on d_dbg_valid
    integer nqrs;       // QRS events seen on m_ev_valid
    integer dval_cnt;   // d_valid pulses
    integer ovf_pulse;  // cycles with m_overflow high
    integer ovf_rise;   // rising edges of m_overflow, the honest count
    reg     ovf_q;

    integer mism_pkpos;
    integer mism_pkv;
    integer mism_pkf;
    integer mism_kem;
    integer mism_i1;
    integer mism_i1_wide;
    integer mism_pkf_wide;
    integer mism_i2_data;
    integer mism_flag;
    integer mism_kind;
    integer mism_evidx;
    integer mism_evval;
    integer mism_qrs;
    integer mism_td;
    integer mism_idx;
    integer mism_user;
    integer mism_last;
    integer mism_beats;
    integer nonmono;
    integer ovf_amb;
    integer mism_total;

    integer flag_signal;
    integer flag_inband;
    integer flag_trej;
    integer flag_refit;
    integer idx_moved;    // peaks whose event index differs from the peak position
    integer amb_mism;

    reg [31:0] prev_ctr [0:DBG_WORDS-1];

    // ---- sequencer: one writer per signal -------------------------------------------
    always @(posedge clk) begin
        cyc <= cyc + 1;
        case (phase)
            PH_RST: begin
                rst_n            <= 1'b0;
                s_tvalid         <= 1'b0;
                s_tdata          <= 33'd0;
                s_hp             <= 26'd0;
                s_besaran        <= 24'd0;
                s_tlast          <= 1'b0;
                s_tuser          <= 8'd0;
                s_sample_idx     <= 32'd0;
                i_enable         <= 1'b0;
                i_clear_counters <= 1'b1;   // the clear path is exercised here, then released
                cad_q            <= 0;
                feed             <= 0;
                rst_cnt          <= rst_cnt + 4'd1;
                if (rst_cnt >= 8) begin
                    rst_n            <= 1'b1;
                    i_enable         <= 1'b1;
                    i_clear_counters <= 1'b0;
                    rst_cnt          <= 4'd0;
                    phase            <= PH_GOLD;
                end
            end
            PH_GOLD: begin
                if ((cad_q == 0) && (feed < limit_n)) begin
                    s_tvalid     <= 1'b1;
                    s_tdata      <= {1'b0, mem_win[feed][31:0]};
                    s_hp         <= mem_hp[feed][25:0];
                    s_besaran    <= mem_bes[feed][23:0];
                    s_tlast      <= (feed == (limit_n - 1));
                    s_tuser      <= feed[7:0];
                    s_sample_idx <= feed[31:0];
                    feed         <= feed + 1;
                    cad_q        <= CAD - 1;
                end else begin
                    s_tvalid <= 1'b0;
                    if (cad_q > 0) cad_q <= cad_q - 1;
                    if ((cad_q == 0) && (feed >= limit_n)) phase <= PH_DONE;
                end
            end
            default: ;   // PH_DONE: hold everything still
        endcase
    end

    // ---- stream parity --------------------------------------------------------------
    always @(posedge clk) begin
        if (rst_n && (phase == PH_GOLD) && m_tvalid) begin
            if (nout < limit_n) begin
                if (m_tdata !== {1'b0, mem_win[nout]})  mism_td   <= mism_td + 1;
                if (m_sample_idx !== nout[31:0])        mism_idx  <= mism_idx + 1;
                if (m_tuser !== nout[7:0])              mism_user <= mism_user + 1;
            end
            if (m_tlast !== (nout == (limit_n - 1)))    mism_last <= mism_last + 1;
            nout <= nout + 1;
        end
        if (rst_n && (phase == PH_GOLD)) begin
            if (m_overflow) ovf_pulse <= ovf_pulse + 1;
            if (m_overflow && !ovf_q) ovf_rise <= ovf_rise + 1;
            ovf_q <= m_overflow;
        end
        if (rst_n && (phase == PH_GOLD) && d_valid)    dval_cnt  <= dval_cnt + 1;
    end

    // ---- peak parity, one check per d_dbg_valid pulse --------------------------------
    always @(posedge clk) begin
        if (rst_n && (phase == PH_GOLD) && d_dbg_valid) begin
            if (npk < exp_pk) begin
                if (d_dbg[DBG_POS*32   +: 32] !== mem_pos[npk])     mism_pkpos <= mism_pkpos + 1;
                if (d_dbg[DBG_PV*32    +: 32] !== mem_pv[npk])      mism_pkv   <= mism_pkv + 1;
                if (d_dbg[DBG_KEM*32   +: 32] !== mem_kem[npk])     mism_kem   <= mism_kem + 1;
                if ((d_dbg[DBG_FLAGS*32 +: 32] & 32'h1F) !==
                    (mem_flag[npk] & 32'h1F))                       mism_flag  <= mism_flag + 1;
                if ({{2{1'b0}}, d_thr} !== mem_i1[npk])             mism_i1    <= mism_i1 + 1;
                if ({{2{1'b0}}, d_pk} !== mem_pkf[npk][W_THR_W-1:0]) mism_pkf  <= mism_pkf + 1;
                if (m_ev_kind !== mem_kind[npk][2:0])               mism_kind  <= mism_kind + 1;
                if (m_ev_idx !== mem_evidx[npk])                    mism_evidx <= mism_evidx + 1;
                if (m_ev_val !== mem_pv[npk])                       mism_evval <= mism_evval + 1;
                // the two frozen introspection widths cover this record; a golden word that
                // does not fit would make the comparison above vacuous
                if (mem_i1[npk] >= (32'd1 << W_THR_W))              mism_i1_wide <= mism_i1_wide + 1;
                if (mem_pkf[npk] >= (32'd1 << W_THR_W))             mism_pkf_wide <= mism_pkf_wide + 1;
                // the golden i2 column is the frozen i1 shifted down by SHIFT_I2, plan 4.4
                if ((mem_i1[npk] >> 1) !== mem_i2[npk])             mism_i2_data <= mism_i2_data + 1;
                if (mem_evidx[npk] !== mem_pos[npk])                idx_moved <= idx_moved + 1;
                if (mem_flag[npk][0]) flag_signal <= flag_signal + 1;
                if (mem_flag[npk][1]) flag_inband <= flag_inband + 1;
                if (mem_flag[npk][2]) flag_trej   <= flag_trej + 1;
                if (mem_flag[npk][3]) flag_refit  <= flag_refit + 1;
            end
            npk <= npk + 1;
        end
    end

    // ---- the QRS series, in order ---------------------------------------------------
    always @(posedge clk) begin
        if (rst_n && (phase == PH_GOLD) && d_dbg_valid &&
            (m_ev_kind == afib_lite_pkg::EV_QRS)) begin
            if (nqrs < qrs_max) begin
                if (m_ev_idx !== mem_qrs[nqrs]) mism_qrs <= mism_qrs + 1;
            end
            nqrs <= nqrs + 1;
        end
    end

    // ---- the nine ambang_state counters never move backwards -------------------------
    always @(posedge clk) begin
        if (rst_n && (phase == PH_GOLD) && d_dbg_valid) begin
            for (widx = 0; widx < DBG_WORDS; widx = widx + 1) begin
                if (d_dbg[widx*32 +: 32] < prev_ctr[widx]) nonmono <= nonmono + 1;
                prev_ctr[widx] <= d_dbg[widx*32 +: 32];
            end
        end
    end

    // ---- per sample feed -------------------------------------------------------------
    initial begin
        limit_n = N_MAX;
        if (!$value$plusargs("LIMIT=%d", limit_n)) limit_n = N_MAX;
        if (!$value$plusargs("VECTOR=%s", vdir)) begin
            $display("tb_puncak: FAIL no +VECTOR (want the Fase 0 column directory)");
            $finish;
        end
        if (!$value$plusargs("EXPECT=%s", edir)) begin
            $display("tb_puncak: FAIL no +EXPECT (want the Fase 5 vector directory)");
            $finish;
        end
        $sformat(f_tmp, "%0s/04015.jendela.hex",     vdir);   $readmemh(f_tmp, mem_win);
        $sformat(f_tmp, "%0s/04015.hp.hex",          vdir);   $readmemh(f_tmp, mem_hp);
        $sformat(f_tmp, "%0s/04015.turunan.hex",     vdir);   $readmemh(f_tmp, mem_bes);
        $sformat(f_tmp, "%0s/04015.fase5.counts.hex", edir);  $readmemh(f_tmp, mem_cnt);
        $sformat(f_tmp, "%0s/04015.ambang_state.hex", edir);  $readmemh(f_tmp, mem_amb);
        $sformat(f_tmp, "%0s/04015.qrs.hex",          edir);  $readmemh(f_tmp, mem_qrs);
        $sformat(f_tmp, "%0s/04015.puncak.pos.hex",   edir);  $readmemh(f_tmp, mem_pos);
        $sformat(f_tmp, "%0s/04015.puncak.pv.hex",    edir);  $readmemh(f_tmp, mem_pv);
        $sformat(f_tmp, "%0s/04015.puncak.pkf.hex",   edir);  $readmemh(f_tmp, mem_pkf);
        $sformat(f_tmp, "%0s/04015.puncak.kem.hex",   edir);  $readmemh(f_tmp, mem_kem);
        $sformat(f_tmp, "%0s/04015.puncak.i1.hex",    edir);  $readmemh(f_tmp, mem_i1);
        $sformat(f_tmp, "%0s/04015.puncak.i2.hex",    edir);  $readmemh(f_tmp, mem_i2);
        $sformat(f_tmp, "%0s/04015.puncak.flag.hex",  edir);  $readmemh(f_tmp, mem_flag);
        $sformat(f_tmp, "%0s/04015.puncak.evidx.hex", edir);  $readmemh(f_tmp, mem_evidx);
        $sformat(f_tmp, "%0s/04015.puncak.kind.hex",  edir);  $readmemh(f_tmp, mem_kind);

        pk_max    = mem_cnt[0];
        qrs_max   = mem_cnt[1];
        amb_max   = mem_cnt[2];
        frame_max = mem_cnt[3];

        // counts of the golden record, recomputed for this limit
        exp_pk  = 0;
        exp_qrs = 0;
        for (widx = 0; widx < pk_max; widx = widx + 1) begin
            if ((mem_pos[widx] + RADIUS_GOLD) < limit_n) begin
                exp_pk = exp_pk + 1;
                if (mem_kind[widx] == afib_lite_pkg::EV_QRS) exp_qrs = exp_qrs + 1;
            end
        end

        feed      = 0;
        nout      = 0;
        cyc       = 0;
        cad_q     = 0;
        rst_cnt   = 0;
        npk       = 0;
        nqrs      = 0;
        dval_cnt  = 0;
        ovf_pulse = 0;
        ovf_rise  = 0;
        ovf_q     = 1'b0;
        amb_mism  = 0;
        idx_moved = 0;
        nonmono   = 0;
        mism_pkpos = 0;
        mism_pkv   = 0;
        mism_pkf   = 0;
        mism_kem   = 0;
        mism_i1    = 0;
        mism_i1_wide = 0;
        mism_pkf_wide = 0;
        mism_i2_data = 0;
        mism_flag  = 0;
        mism_kind  = 0;
        mism_evidx = 0;
        mism_evval = 0;
        mism_qrs   = 0;
        mism_td    = 0;
        mism_idx   = 0;
        mism_user  = 0;
        mism_last  = 0;
        mism_beats = 0;
        flag_signal = 0;
        flag_inband = 0;
        flag_trej   = 0;
        flag_refit  = 0;
        for (widx = 0; widx < DBG_WORDS; widx = widx + 1) prev_ctr[widx] = 32'd0;

        phase   = PH_RST;
        rst_n   = 1'b0;
        s_tdata = 33'd0;
        s_hp    = 26'd0;
        s_besaran = 24'd0;
        s_tvalid = 1'b0;
        s_tlast = 1'b0;
        s_tuser = 8'd0;
        s_sample_idx = 32'd0;
        i_enable = 1'b0;
        i_clear_counters = 1'b0;

        $display("tb_puncak: vectors = %0s", vdir);
        $display("tb_puncak: expected = %0s", edir);
        $display("tb_puncak: limit   = %0d of %0d frames", limit_n, frame_max);
        $display("tb_puncak: golden peaks = %0d, qrs = %0d, ambang_state words = %0d",
                 pk_max, qrs_max, amb_max);

        if ((pk_max > PK_CAP) || (qrs_max > QRS_CAP) || (limit_n > N_MAX)) begin
            $display("tb_puncak: FAIL capacity or limit out of range (pk_cap %0d qrs_cap %0d)",
                     PK_CAP, QRS_CAP);
            $finish;
        end

        cyc_limit = (limit_n + 1) * CAD + 20000;
        while ((phase != PH_DONE) && (cyc < cyc_limit)) @(posedge clk);
        repeat (8) @(posedge clk);

        // the nine ambang_state elements are an end of run quantity of the full record
        if (limit_n == N_MAX) begin
            for (widx = 0; widx < amb_max; widx = widx + 1) begin
                if (d_dbg[widx*32 +: 32] !== mem_amb[widx]) amb_mism = amb_mism + 1;
                $display("tb_puncak: ambang_state[%0d] dut = %0d golden = %0d",
                         widx, d_dbg[widx*32 +: 32], mem_amb[widx]);
            end
        end else begin
            $display("tb_puncak: ambang_state not checked on a short run");
        end

        mism_total = mism_pkpos + mism_pkv + mism_pkf + mism_kem + mism_i1 + mism_flag +
                     mism_kind + mism_evidx + mism_evval + mism_qrs + mism_td + mism_idx +
                     mism_user + mism_last;

        $display("tb_puncak: peaks dut = %0d expected = %0d", npk, exp_pk);
        $display("tb_puncak: qrs   dut = %0d expected = %0d", nqrs, exp_qrs);
        $display("tb_puncak: beats o_beat_count = %0d", o_beat_count);
        $display("tb_puncak: words compared = %0d of %0d", nout, limit_n);
        $display("tb_puncak: peak position mismatches = %0d", mism_pkpos);
        $display("tb_puncak: peak pv mismatches       = %0d", mism_pkv);
        $display("tb_puncak: peak pk_f mismatches     = %0d", mism_pkf);
        $display("tb_puncak: peak kem mismatches      = %0d", mism_kem);
        $display("tb_puncak: peak i1 mismatches       = %0d", mism_i1);
        $display("tb_puncak: peak flag mismatches     = %0d", mism_flag);
        $display("tb_puncak: peak kind mismatches     = %0d", mism_kind);
        $display("tb_puncak: peak ev_idx mismatches   = %0d", mism_evidx);
        $display("tb_puncak: peak ev_val mismatches   = %0d", mism_evval);
        $display("tb_puncak: qrs index out of order   = %0d", mism_qrs);
        $display("tb_puncak: stream m_tdata mismatch  = %0d", mism_td);
        $display("tb_puncak: stream sample_idx        = %0d", mism_idx);
        $display("tb_puncak: stream tuser mismatch    = %0d", mism_user);
        $display("tb_puncak: stream tlast mismatch    = %0d", mism_last);
        $display("tb_puncak: golden i1 words wider than %0d bits = %0d", W_THR_W, mism_i1_wide);
        $display("tb_puncak: golden pk_f words wider than %0d bits = %0d", W_THR_W, mism_pkf_wide);
        $display("tb_puncak: golden i2 != i1 >> 1 rows = %0d", mism_i2_data);
        $display("tb_puncak: golden signal flags = %0d in_band = %0d t_rejected = %0d refit = %0d",
                 flag_signal, flag_inband, flag_trej, flag_refit);
        $display("tb_puncak: peaks whose event index moved off the peak position = %0d", idx_moved);
        $display("tb_puncak: counter decreases = %0d", nonmono);
        $display("tb_puncak: m_overflow pulses = %0d (rising edges %0d)", ovf_pulse, ovf_rise);
        $display("tb_puncak: d_valid pulses    = %0d", dval_cnt);
        $display("tb_puncak: ambang_state mismatches = %0d", amb_mism);
        $display("tb_puncak: mismatches = %0d", mism_total);

        if ((npk == exp_pk) && (exp_pk > 0) &&
            (nqrs == exp_qrs) && (exp_qrs > 0) &&
            (nout == limit_n) && (mism_total == 0) && (nonmono == 0) &&
            (ovf_rise == 0) && (o_beat_count === exp_qrs) &&
            (amb_mism == 0) && ((limit_n != N_MAX) || (npk == pk_max))) begin
            $display("tb_puncak: PASS");
        end else begin
            $display("tb_puncak: FAIL");
        end
        $finish;
    end

endmodule

`default_nettype wire
