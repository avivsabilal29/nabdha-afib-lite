// ---------------------------------------------------------------------------
// peak_detect.sv -- envelope peak detection, adaptive threshold, refractory period,
// and the search-back walk. Contract profile: event stage (I1).
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). This stage owns the event sideband m_ev_* and the beat counter.
// Introspection ports: d_thr and d_pk, both at the threshold node width.
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 section 2.2):
//   in   W_WIN = 33   the running window node, signed, 32 unsigned
//   thr  W_THR = 30   adaptive threshold AND search back. Doc 36 2.2 measures 29 on
//                     04015 but 2.2.1 measures 30 on nsrdb/16265 at 128 Hz, so the
//                     binding width is 30 and this stage is built 30 bits wide.
// Saturation points: the threshold state is a floor-shifted recurrence, no clamp, and
//   the ceiling is the window rail. SEARCH_BACK_DEPTH 128 is the candidate buffer depth
//   and it is NOT proven for other records, so it needs its own overflow flag.
//   THRESH_SCALE 256 is 2**SHIFT_DER, the factor between the threshold and the shifted
//   derivative domain.
// Rounding rule: RND_FLOOR on every right shift (rantai.py:655, :656, :657, :683, :709).
//   Theorem 6 fixes this: a + ((p - a) >> 3) is identical to (7a + p) // 8, and the
//   identity breaks on 87316 of 200000 threshold pairs if truncation toward zero is
//   used instead. The refractory test is PANTUL 50 (rantai.py:57).
// Model lines this file mirrors: rantai.py:610-715, :655, :656, :657, :662, :665, :683,
//   :685, :687, :699, :700, :705-709, cross form at :581, peak scan at :983-1002,
//   batch at :289-303, RADIUS_PUNCAK 27 at :55, JENDELA_F 25 at :56, ring at :933-935.
//
// Warm-up: the adaptive threshold constants are part of the specification, not a defect.
// A new decision is only trustworthy after 23 to 32 beats (doc 36 5.1 point 3).
//
// ---------------------------------------------------------------------------
// FASE 5. Locked spec: rtl-synthesis/reports/fase5/SPEC-TERKUNCI-FASE5.md (K1 to K8).
// The placeholder body is gone. The frozen ports and parameters keep their names; two
// input ports and two introspection ports are ADDED, purely additive, and are reported as
// a deviation in rtl-synthesis/reports/LAPORAN-FASE5.md:
//
//   s_hp        W_HP = 26   the high pass stream (Fase 3), co-timed with s_tdata
//   s_besaran   W_DER = 24  the slope series ("besaran" is turunan), co-timed
//   d_dbg       12 words    additive introspection bus, layout in the DBG_* block below
//   d_dbg_valid 1           one cycle per processed peak, aligned with d_dbg
//
// The two inputs are not a convenience. The model takes pk_f from ring_hp and kem from
// ring_besaran (rantai.py:933-935, :1002, :333). s_tdata is 33 bit wide and fully used by
// the window word (04015 drives 27 words at or above 2**31), so the two streams have
// nowhere to travel inside the frozen port list. Without them pk_f, kem, the in-band flag
// and the T wave rule do not exist, and four of the nine ambang_state elements cannot be
// produced. The alternative taken elsewhere was to switch the T wave rule off; that cannot
// pass the locked phase gate, so it is not taken here.
//
// Schedule deviation: one accepted sample per cycle, and the whole per-peak datapath is
// combinational. Plan 4.7/4.8 priced 6 cycles per peak for the threshold path, a monotone
// two comparator queue for the 55 sample window and a serial 51 cycle scanner for the
// absolute maximum. Those are area and timing choices; the parity gate does not depend on
// them, and the schedule is reported rather than hidden. The three window scans are flat
// combinational maximum trees over the delay lines.
//
// Cross form discipline: 2*kem < kem_qrs is written exactly as the model writes it
// (rantai.py:340) and never as kem < (kem_qrs >> 1), which differs on 2048 of 16777216
// grid points (doc 36 2.4).
//
// House style: wire and reg only (D10), one clock, synchronous active low reset.
// ---------------------------------------------------------------------------
`default_nettype none

module peak_detect #(
    parameter int unsigned W_WIN      = afib_lite_pkg::W_WIN,
    parameter int unsigned W_THR      = afib_lite_pkg::W_THR,
    parameter int unsigned W_IDX      = afib_lite_pkg::W_IDX,
    parameter int unsigned W_TUSER    = afib_lite_pkg::W_TUSER,
    parameter int unsigned W_EVKIND   = afib_lite_pkg::W_EVKIND,
    parameter int unsigned LAT_CYCLES = 1
) (
    input  wire                     clk_i,
    input  wire                     rst_ni,

    // sample stream in
    input  wire [W_WIN-1:0]         s_tdata,
    input  wire                     s_tvalid,
    input  wire                     s_tlast,
    input  wire [W_TUSER-1:0]       s_tuser,
    input  wire [W_IDX-1:0]         s_sample_idx,

    // configuration
    input  wire                     i_enable,
    input  wire                     i_clear_counters,

    // sample stream out
    output reg  [W_WIN-1:0]         m_tdata,
    output reg                      m_tvalid,
    output reg                      m_overflow,
    output reg                      m_tlast,
    output reg  [W_TUSER-1:0]       m_tuser,
    output reg  [W_IDX-1:0]         m_sample_idx,

    // event sideband: QRS beats and peak candidates
    output reg                      m_ev_valid,
    output reg  [W_EVKIND-1:0]      m_ev_kind,
    output reg  [W_IDX-1:0]         m_ev_idx,
    output reg  [31:0]              m_ev_val,

    // introspection
    output reg                      d_valid,
    output reg  [W_THR-1:0]         d_thr,
    output reg  [W_THR-1:0]         d_pk,

    // status this stage owns
    output reg  [31:0]              o_beat_count,

    // ---- FASE 5 additive ports (reported deviation; see the header) -----------
    input  wire [afib_lite_pkg::W_HP-1:0]   s_hp,
    input  wire [afib_lite_pkg::W_DER-1:0]  s_besaran,
    output wire [14*32-1:0]                 d_dbg,
    output wire                             d_dbg_valid
);

    // =======================================================================
    // Constants of the frozen model. afib_lite_pkg predates Fase 5 and carries
    // none of them; this file may not edit the package, so each value is quoted
    // with the model line it comes from, the way the frozen header above already
    // quotes PANTUL 50 (rantai.py:57).
    // =======================================================================
    localparam int unsigned RADIUS_PUNCAK     = 27;   // rantai.py:55
    localparam int unsigned JENDELA_F         = 25;   // rantai.py:56
    localparam int unsigned PANTUL            = 50;   // rantai.py:57
    localparam int unsigned BATAS_PITA_SAMPEL = 360;  // rantai.py:58 and :68
    localparam int unsigned SETENGAH_JENDELA  = 18;   // rantai.py:59
    localparam int unsigned DELAPAN           = 8;    // rantai.py:62
    localparam int unsigned SEMAI_PANJANG     = 32;   // rantai.py:63
    localparam int unsigned SEMAI_JEDA        = 8;    // rantai.py:64
    localparam int unsigned SB_DELTA_SCALE    = 200;  // rantai.py:581, 200 = 50 * 4
    localparam int unsigned SB_AVERAGE_SCALE  = 83;   // rantai.py:581, the 83 over 50 cross form
    localparam int unsigned RR_BAND_SCALE     = 25;   // rantai.py:359
    localparam int unsigned RR_BAND_LO        = 23;   // rantai.py:359
    localparam int unsigned RR_BAND_HI        = 29;   // rantai.py:359
    localparam int unsigned RR_BAND_MIN_MS    = 250;  // rantai.py:638
    localparam int unsigned RR_BAND_MAX_MS    = 2000; // rantai.py:638
    localparam int unsigned SHIFT_I1          = 2;    // rantai.py:655, :656
    localparam int unsigned SHIFT_I2          = 1;    // rantai.py:657
    localparam int unsigned SHIFT_SPKI        = 3;    // rantai.py:683, :685, :687, :699, :700
    localparam int unsigned SHIFT_REFIT       = 2;    // rantai.py:706, :708, :709
    localparam int unsigned SHIFT_RA1         = 3;    // rantai.py:399

    // =======================================================================
    // Derived widths and lengths. Each is a function of a constant above or of a
    // node width out of the package, no free numbers.
    // =======================================================================
    localparam int unsigned W_HP_NODE  = afib_lite_pkg::W_HP;                 // 26
    localparam int unsigned W_DER_NODE = afib_lite_pkg::W_DER;                // 24
    localparam int unsigned W_STATE    = afib_lite_pkg::W_WIN;                // 33, K3: no clip
    localparam int unsigned W_ACC      = W_STATE + 1;                        // 34, signed difference
    localparam int unsigned W_CMP      = W_ACC + 1;                          // 35, unsigned against signed
    localparam int unsigned WIN_WORDS  = 2 * RADIUS_PUNCAK + 1;              // 55, the scanned window
    localparam int unsigned SEL_LINE   = WIN_WORDS - 1;                      // 54 registered taps
    localparam int unsigned HP_LINE    = JENDELA_F + RADIUS_PUNCAK;          // 52 registered taps
    localparam int unsigned BES_LINE   = RADIUS_PUNCAK + SETENGAH_JENDELA;   // 45 registered taps
    localparam int unsigned HP_IDX_LO  = RADIUS_PUNCAK - JENDELA_F - 1;      // 1
    localparam int unsigned HP_IDX_HI  = RADIUS_PUNCAK + JENDELA_F - 1;      // 51
    localparam int unsigned BES_IDX_LO = RADIUS_PUNCAK - SETENGAH_JENDELA - 1; // 8
    localparam int unsigned BES_IDX_HI = RADIUS_PUNCAK + SETENGAH_JENDELA - 1; // 44
    localparam int unsigned BUF_DEPTH  = afib_lite_pkg::SEARCH_BACK_DEPTH;   // 128, K8
    localparam int unsigned RR_LEN     = DELAPAN;                            // 8
    localparam int unsigned RIH_LEN    = SEMAI_PANJANG;                      // 32
    localparam int unsigned RR_W       = 16;                                 // interval word, W_RR_MS
    localparam int unsigned RR_SUM_W   = 20;                                 // 8 * 2000 plus headroom
    localparam int unsigned W_PV       = 32;                                 // envelope word, unsigned magnitude
    localparam int unsigned W_PKMAG    = W_HP_NODE;                          // filtered peak magnitude
    localparam int unsigned W_BPK      = W_IDX + W_PV + W_PKMAG + W_DER_NODE; // 114, one candidate entry
    localparam int unsigned W_DBG      = 14 * 32;                            // additive bus width

    // candidate entry fields, little end first: position, envelope, filtered peak, slope
    localparam int unsigned BPK_POS_L  = 0;
    localparam int unsigned BPK_PV_L   = BPK_POS_L + W_IDX;                  // 32
    localparam int unsigned BPK_PF_L   = BPK_PV_L + W_PV;                    // 64
    localparam int unsigned BPK_KM_L   = BPK_PF_L + W_PKMAG;                 // 90

    // d_dbg word map. Words 0 to 8 are the nine elements of ambang_state in the model's
    // own order (rantai.py:1051-1053). Word 9 is the envelope value, 10 the slope, 12 the
    // peak position and 11 the verdict flags, because none of those four has a frozen port.
    // Word 13 carries the internal rails and the search-back arm, which have no golden
    // column but are read back as evidence that nothing quietly saturated.
    // Flag word, bits 0 to 4 aligned one for one with the golden peaks.csv columns:
    //   b0 signal (rantai.py:679), b1 in_band domain, b2 t_rejected (rantai.py:681),
    //   b3 search_back (rantai.py:710), b4 the search-back verdict was a QRS.
    localparam int unsigned DBG_CALON_KEDUA = 0;
    localparam int unsigned DBG_CARI_MUNDUR = 1;
    localparam int unsigned DBG_DIPERIKSA   = 2;
    localparam int unsigned DBG_DITOLAK     = 3;
    localparam int unsigned DBG_DITERIMA    = 4;
    localparam int unsigned DBG_BERISIKO    = 5;
    localparam int unsigned DBG_SEMAI       = 6;
    localparam int unsigned DBG_PENANDA     = 7;
    localparam int unsigned DBG_LANGKAH     = 8;
    localparam int unsigned DBG_PV          = 9;
    localparam int unsigned DBG_KEM         = 10;
    localparam int unsigned DBG_FLAGS       = 11;
    localparam int unsigned DBG_POS         = 12;
    localparam int unsigned DBG_RAILS       = 13;

    localparam logic [31:0] DBG_F_SIGNAL   = 32'h0000_0001;
    localparam logic [31:0] DBG_F_INBAND   = 32'h0000_0002;
    localparam logic [31:0] DBG_F_TREJECT  = 32'h0000_0004;
    localparam logic [31:0] DBG_F_REFIT    = 32'h0000_0008;
    localparam logic [31:0] DBG_F_REFITQRS = 32'h0000_0010;
    localparam logic [31:0] DBG_F_SIGNAL1  = 32'h0000_0001;
    localparam logic [31:0] DBG_F_ARMED    = 32'h0000_0002;
    localparam logic [31:0] DBG_F_SBOVF    = 32'h0000_0004;
    localparam logic [31:0] DBG_F_SCANJUMP = 32'h0000_0008;
    localparam logic [31:0] DBG_F_STRAIL   = 32'h0000_0010;
    localparam logic [31:0] DBG_F_THRRAIL  = 32'h0000_0020;

    // index and sum width literals, so no expression silently changes width
    // width safe literals: a 32 bit stage first, then an explicit part select, so no
    // assignment below silently changes width
    localparam logic [31:0] N_RADIUS     = RADIUS_PUNCAK;
    localparam logic [31:0] N_PANTUL     = PANTUL;
    localparam logic [31:0] N_BUFDEPTH   = BUF_DEPTH;
    localparam logic [31:0] N_RR_MIN     = RR_BAND_MIN_MS;
    localparam logic [31:0] N_RR_MAX     = RR_BAND_MAX_MS;
    localparam logic [31:0] N_RR_LEN     = RR_LEN;
    localparam logic [31:0] N_DELAPAN    = DELAPAN;
    localparam logic [31:0] N_SEMAI_JEDA = SEMAI_JEDA;
    localparam logic [31:0] N_RR_SCALE   = RR_BAND_SCALE;
    localparam logic [31:0] N_RR_LO      = RR_BAND_LO;
    localparam logic [31:0] N_RR_HI      = RR_BAND_HI;
    localparam logic [31:0] N_SB_DELTA   = SB_DELTA_SCALE;
    localparam logic [31:0] N_SB_AVG     = SB_AVERAGE_SCALE;
    localparam logic [31:0] N_W_BPK      = W_BPK;
    localparam logic [31:0] N_BUF_MASK   = BUF_DEPTH - 1;

    localparam logic [W_IDX-1:0]  RADIUS_DX    = N_RADIUS[W_IDX-1:0];
    localparam logic [W_IDX-1:0]  PANTUL_DX    = N_PANTUL[W_IDX-1:0];
    localparam logic [W_IDX-1:0]  BUF_DEPTH_DX = N_BUFDEPTH[W_IDX-1:0];
    localparam logic [W_IDX+1:0]  RR_MIN_DX    = (W_IDX+2)'(N_RR_MIN);
    localparam logic [W_IDX+1:0]  RR_MAX_DX    = (W_IDX+2)'(N_RR_MAX);
    localparam logic [3:0]        RR_LEN_D     = N_RR_LEN[3:0];
    localparam logic [31:0]       DELAPAN_D    = N_DELAPAN[31:0];
    localparam logic [31:0]       SEMAI_JEDA_D = N_SEMAI_JEDA[31:0];
    localparam logic [31:0]       RR_SCALE_D   = N_RR_SCALE[31:0];
    localparam logic [31:0]       RR_LO_D      = N_RR_LO[31:0];
    localparam logic [31:0]       RR_HI_D      = N_RR_HI[31:0];
    localparam logic [31:0]       SB_DELTA_D   = N_SB_DELTA[31:0];
    localparam logic [31:0]       SB_AVG_D     = N_SB_AVG[31:0];
    localparam signed [W_ACC-1:0] THR_RAIL_D   = (2 ** W_THR) - 1;        // 2**30 - 1
    localparam logic [13:0]       W_BPK_D      = N_W_BPK[13:0];
    localparam logic [6:0]        BUF_MASK_D   = N_BUF_MASK[6:0];

    // =======================================================================
    // Delay lines, one packed vector per stream. Index k of a vector holds the
    // word from k+1 accepted samples back, so tap k of a stream is the live input
    // word when k is 0 and vector index k-1 otherwise. A tap that has not arrived
    // is the zero initial condition of the model's GarisTunda (rantai.py:112-113),
    // which reset gives for free.
    // =======================================================================
    reg [SEL_LINE*W_WIN-1:0]     sel_vec;
    reg [HP_LINE*W_HP_NODE-1:0]  hp_vec;
    reg [BES_LINE*W_DER_NODE-1:0] bes_vec;

    // peak candidate buffer, K8: 128 entries packed into one vector, addressed by peak
    // index modulo the depth, nothing taken from the data, overflow flagged not wrapped
    reg [BUF_DEPTH*W_BPK-1:0] bpk_vec;
    reg [W_IDX-1:0]           pk_cnt_q;    // i_puncak, the index of the peak being processed

    // =======================================================================
    // Adaptive threshold state, K3: stored at the window node width, no clip. The
    // measured ceiling is spki 717628984 on 04015, which does not fit a 29 bit signed
    // word, and the design ceiling is the window rail.
    // =======================================================================
    reg  signed [W_STATE-1:0] spki_q;
    reg  signed [W_STATE-1:0] npki_q;
    reg  signed [W_STATE-1:0] spkf_q;
    reg  signed [W_STATE-1:0] npkf_q;
    reg  [W_IDX-1:0]          i_qrs_q;
    reg                       i_qrs_v_q;
    reg  [W_IDX-1:0]          i_qrs_pk_q;
    reg                       i_qrs_pk_v_q;
    reg  [W_DER_NODE-1:0]     kem_qrs_q;
    reg                       kem_qrs_v_q;

    // =======================================================================
    // RR stage mirror, only what the nine ambang_state elements need
    // (rantai.py:375-440): the queue of eight, the accepted queue with its sum, the
    // 32 interval history, and the counters.
    // =======================================================================
    reg  [RR_W-1:0]     deret_q [0:RR_LEN-1];
    reg  [3:0]          deret_len_q;
    reg  [RR_SUM_W-1:0] deret_sum_q;
    reg  [RR_W-1:0]     antre_q [0:RR_LEN-1];
    reg  [3:0]          antre_len_q;
    reg  [RR_SUM_W-1:0] antre_sum_q;
    reg  [RR_W-1:0]     rih_q   [0:RIH_LEN-1];
    reg  [5:0]          rih_len_q;
    reg  [RR_SUM_W-1:0] ra1_q;
    reg  [RR_SUM_W-1:0] pemb_q;
    reg  [3:0]          peny_q;
    reg  [31:0]         gagal_q;
    reg  [31:0]         jeda_q;
    reg  [31:0]         semai_q;

    // =======================================================================
    // Run counters: the nine elements of ambang_state (rantai.py:1051-1053)
    // =======================================================================
    reg  [31:0] c_calon_q;
    reg  [31:0] c_cari_q;
    reg  [31:0] c_diper_q;
    reg  [31:0] c_ditol_q;
    reg  [31:0] c_terima_q;
    reg  [31:0] c_beri_q;
    reg  [31:0] c_penanda_q;
    reg  [31:0] c_langkah_q;

    // =======================================================================
    // Scanner and output state
    // =======================================================================
    reg  [W_IDX-1:0] scan_q;
    reg  [W_DBG-1:0] dbg_q;
    reg              dbg_valid_q;

    integer wi, wm, hm, bm, mi, ki;

    // =======================================================================
    // Magnitude helpers, the model's maks_mutlak (rantai.py:137-148): the largest
    // absolute value over a window, unsigned.
    // =======================================================================
    function automatic [W_HP_NODE-1:0] f_abs_hp (input [W_HP_NODE-1:0] v);
        begin
            f_abs_hp = v[W_HP_NODE-1] ? ({W_HP_NODE{1'b0}} - v) : v;
        end
    endfunction

    function automatic [W_DER_NODE-1:0] f_abs_bes (input [W_DER_NODE-1:0] v);
        begin
            f_abs_bes = v[W_DER_NODE-1] ? ({W_DER_NODE{1'b0}} - v) : v;
        end
    endfunction

    // number of entries strictly below v, the rank counting step of the history median
    function automatic [5:0] f_less_count (input [RIH_LEN*RR_W-1:0] pack,
                                           input [RR_W-1:0] v);
        integer fj;
        begin
            f_less_count = 6'd0;
            for (fj = 0; fj < RIH_LEN; fj = fj + 1) begin
                if (pack[fj*RR_W +: RR_W] < v) begin
                    f_less_count = f_less_count + 6'd1;
                end
            end
        end
    endfunction

    // =======================================================================
    // Per sample: the scanner, rantai.py:983-994.
    // The model's while loop `while scan + RADIUS_PUNCAK <= n` runs at most once per
    // sample and exactly when scan + RADIUS_PUNCAK == n: after every accepted sample the
    // scanner is at n - 2*RADIUS_PUNCAK + 1 or ahead, so the next sample makes the sum
    // equal and never smaller. K6 fixes the inclusive form.
    // =======================================================================
    wire             accept_w = s_tvalid & i_enable;
    wire [W_IDX-1:0] scan_req = scan_q + RADIUS_DX;
    wire             chk_w    = accept_w & (s_sample_idx >= scan_req);
    // a sample index that jumps over the scanner would quietly bias the window; the frozen
    // cadence never does it, and it is flagged, not ignored
    wire             scan_jump_w = accept_w & (s_sample_idx > scan_req);

    wire [W_IDX-1:0] pos_w = scan_q;
    // the window is ring_sel[scan-27 .. scan+27] = taps 0 to 54 and the item under test is
    // tap 27 (rantai.py:988-990)
    wire [W_WIN-1:0] pv_w = sel_vec[(RADIUS_PUNCAK-1)*W_WIN +: W_WIN];

    reg [W_WIN-1:0] wmax_w;
    always @(*) begin
        wmax_w = s_tdata;
        for (wm = 0; wm < SEL_LINE; wm = wm + 1) begin
            if (sel_vec[wm*W_WIN +: W_WIN] > wmax_w) begin
                wmax_w = sel_vec[wm*W_WIN +: W_WIN];
            end
        end
    end

    wire peak_w = chk_w & (pv_w != {W_WIN{1'b0}}) & (pv_w >= wmax_w);

    // =======================================================================
    // Per peak: pk_f and kem, the two absolute maxima of rantai.py:1002 and :333.
    //   pk_f = ring_hp.maks_mutlak(pos-25, pos+25)      -> hp taps 2 .. 52
    //   kem  = ring_besaran.maks_mutlak(pos-18, pos+18) -> bes taps 9 .. 45
    // max(pos-18, 0) never binds here: pos is at least RADIUS_PUNCAK at every peak.
    // =======================================================================
    reg [W_HP_NODE-1:0] pk_f_w;
    always @(*) begin
        pk_f_w = {W_HP_NODE{1'b0}};
        for (hm = HP_IDX_LO; hm <= HP_IDX_HI; hm = hm + 1) begin
            if (f_abs_hp(hp_vec[hm*W_HP_NODE +: W_HP_NODE]) > pk_f_w) begin
                pk_f_w = f_abs_hp(hp_vec[hm*W_HP_NODE +: W_HP_NODE]);
            end
        end
    end

    reg [W_DER_NODE-1:0] kem_w;
    always @(*) begin
        kem_w = {W_DER_NODE{1'b0}};
        for (bm = BES_IDX_LO; bm <= BES_IDX_HI; bm = bm + 1) begin
            if (f_abs_bes(bes_vec[bm*W_DER_NODE +: W_DER_NODE]) > kem_w) begin
                kem_w = f_abs_bes(bes_vec[bm*W_DER_NODE +: W_DER_NODE]);
            end
        end
    end

    // =======================================================================
    // Widening casts. The state words are stored unsigned 33 bit and the model
    // subtracts them, so the difference is signed 34 bit (parity trap 6).
    // =======================================================================
    wire signed [W_ACC-1:0] spki_x = $signed({{(W_ACC-W_STATE){spki_q[W_STATE-1]}}, spki_q});
    wire signed [W_ACC-1:0] npki_x = $signed({{(W_ACC-W_STATE){npki_q[W_STATE-1]}}, npki_q});
    wire signed [W_ACC-1:0] spkf_x = $signed({{(W_ACC-W_STATE){spkf_q[W_STATE-1]}}, spkf_q});
    wire signed [W_ACC-1:0] npkf_x = $signed({{(W_ACC-W_STATE){npkf_q[W_STATE-1]}}, npkf_q});
    wire signed [W_ACC-1:0] pv_e   = $signed({{(W_ACC-W_WIN){1'b0}}, pv_w});
    wire signed [W_ACC-1:0] pkf_e  = $signed({{(W_ACC-W_HP_NODE){1'b0}}, pk_f_w});

    // i1, f1 and i2, the snapshot of rantai.py:655-657. i2 comes from the snapshot i1, and
    // the snapshot is taken before any update (parity trap 1).
    wire signed [W_ACC-1:0] i1_w = npki_x + ((spki_x - npki_x) >>> SHIFT_I1);
    wire signed [W_ACC-1:0] f1_w = npkf_x + ((spkf_x - npkf_x) >>> SHIFT_I1);
    wire signed [W_ACC-1:0] i2_w = i1_w >>> SHIFT_I2;

    // a comparison against an unsigned window value needs one sign bit more
    wire signed [W_CMP-1:0] pv_c  = $signed({{(W_CMP-W_WIN){1'b0}}, pv_w});
    wire signed [W_CMP-1:0] pkf_c = $signed({{(W_CMP-W_HP_NODE){1'b0}}, pk_f_w});
    wire signed [W_CMP-1:0] i1_c  = $signed({{(W_CMP-W_ACC){i1_w[W_ACC-1]}}, i1_w});
    wire signed [W_CMP-1:0] i2_c  = $signed({{(W_CMP-W_ACC){i2_w[W_ACC-1]}}, i2_w});
    wire signed [W_CMP-1:0] f1_c  = $signed({{(W_CMP-W_ACC){f1_w[W_ACC-1]}}, f1_w});

    // =======================================================================
    // Refractory gate, T wave rule and the second candidate, rantai.py:662-681.
    // sinyal is modified in three places in order: pv > i1, then the refractory gate,
    // then the T wave rule. calon_kedua is counted after all three (parity trap 3).
    // The T wave rule switch is the model's aturan_t, which is True in the frozen run;
    // the frozen port list has no arm select for it, so it is a local constant here and
    // that is reported.
    // =======================================================================
    wire [W_IDX-1:0] delta_w  = pos_w - i_qrs_q;
    wire             delta_ok = i_qrs_v_q;
    wire             sig0_w   = (pv_c > i1_c);
    wire             sig1_w   = sig0_w & ~(delta_ok & (delta_w < PANTUL_DX));
    // pita_w (in band) and trej_w (t rejected) come from t_rule_eq, the single source of
    // the rule's equations in rtl/ (Fase 10, K6). Until phase 10 this file carried its own
    // copy of them, with the exact cross form 2*kem < kem_qrs; the module computes the
    // same expressions over the same operands, and the T wave rule switch the model reads
    // at the call (rantai.py:338) is the constant 1 here because the frozen model's
    // aturan_t is True in the frozen run, as this block already documented.
    wire             pita_w;
    wire             trej_w;
    t_rule_eq #(
        .W_IDX  (W_IDX),
        .W_KEM  (W_DER_NODE),
        .W_KEMQ (W_DER_NODE)
    ) u_rule_eq (
        .i_aktif         (1'b1),
        .i_delta         (delta_w),
        .i_delta_valid   (delta_ok),
        .i_kem           (kem_w),
        .i_kem_qrs       (kem_qrs_q),
        .i_kem_qrs_valid (kem_qrs_v_q),
        .o_dalam_pita    (pita_w),
        .o_ditolak       (trej_w)
    );
    wire             sig2_w   = sig1_w & ~trej_w;

    wire c_diper_w = sig1_w & pita_w;
    wire c_ditol_w = sig1_w & trej_w;
    wire c_terim_w = sig1_w & pita_w & ~trej_w;
    wire c_calon_w = ~sig2_w & (pv_c > i2_c);
    // rantai.py:688-694: rasio_qrs and berisiko on the signal path, in the band only
    wire c_beri_w  = sig2_w & pita_w & (kem_qrs_q != {W_DER_NODE{1'b0}}) & trej_w;

    // =======================================================================
    // Signal path updates, rantai.py:683-695
    // =======================================================================
    wire                    pkf_gt_f1_w = (pkf_c > f1_c);
    wire signed [W_ACC-1:0] spki_sig_w  = spki_x + ((pv_e - spki_x) >>> SHIFT_SPKI);
    wire signed [W_ACC-1:0] spkf_sig_w  = pkf_gt_f1_w
                                          ? (spkf_x + ((pkf_e - spkf_x) >>> SHIFT_SPKI))
                                          : spkf_x;
    wire signed [W_ACC-1:0] npkf_sig_w  = pkf_gt_f1_w
                                          ? npkf_x
                                          : (npkf_x + ((pkf_e - npkf_x) >>> SHIFT_SPKI));

    // =======================================================================
    // Noise path updates, rantai.py:699-700
    // =======================================================================
    wire signed [W_ACC-1:0] npki_nse_w = npki_x + ((pv_e - npki_x) >>> SHIFT_SPKI);
    wire signed [W_ACC-1:0] npkf_nse_w = npkf_x + ((pkf_e - npkf_x) >>> SHIFT_SPKI);

    // =======================================================================
    // Search back, rantai.py:569-600. The gate is the cross form of 83/50 of the
    // second average (:581), written so that no division appears.
    // =======================================================================
    wire [31:0]      sb_lhs_d = SB_DELTA_D * delta_w;
    wire [31:0]      sb_lhs_w = sb_lhs_d * {28'b0, peny_q};
    wire [31:0]      sb_rhs_w = SB_AVG_D * {12'b0, pemb_q};
    wire [31:0]      sb_rhs1_w = SB_AVG_D * {12'b0, ra1_q};
    wire             sb_gate_w = (peny_q != 4'd0)
                                 ? (sb_lhs_w > sb_rhs_w)
                                 : ((ra1_q != {RR_SUM_W{1'b0}}) ? (sb_lhs_d > sb_rhs1_w)
                                                                : 1'b0);
    wire [W_IDX-1:0] sb_lo_w = i_qrs_pk_q + 1'b1;
    wire [W_IDX-1:0] sb_n_w  = (pk_cnt_q >= sb_lo_w) ? ((pk_cnt_q - sb_lo_w) + 1'b1)
                                                     : {W_IDX{1'b0}};
    wire             sb_ovf_w = (sb_n_w > BUF_DEPTH_DX);
    wire             sb_arm_w = (~sig2_w) & delta_ok & i_qrs_pk_v_q & sb_gate_w;

    // The walk is over j = i_qrs_puncak+1 .. i_puncak, both inclusive (K7). It is taken
    // downward in j and a tie replaces with >=, which leaves the earliest candidate
    // standing, exactly what the model's upward walk with a strict `v > best` does.
    reg                     sb_hit_w;
    reg  [W_IDX-1:0]        sb_sp_w;
    reg  [W_IDX-1:0]        sb_j_w;
    reg  signed [W_CMP-1:0] sb_vc_w;
    reg  [W_THR-1:0]        sb_vf_w;
    reg  [W_DER_NODE-1:0]   sb_vk_w;
    reg  [W_BPK-1:0]        sb_ent_w;
    reg  [13:0]             sb_off_w;
    reg  [6:0]              sb_idx_w;
    reg  signed [W_CMP-1:0] cand_v_w;
    reg  [W_IDX-1:0]        cand_p_w;
    reg  [W_THR-1:0]        cand_f_w;
    reg  [W_DER_NODE-1:0]   cand_k_w;
    always @(*) begin
        sb_hit_w = 1'b0;
        sb_sp_w  = {W_IDX{1'b0}};
        sb_j_w   = {W_IDX{1'b0}};
        sb_vc_w  = {{W_CMP{1'b0}}};
        sb_vf_w  = {W_THR{1'b0}};
        sb_vk_w  = {W_DER_NODE{1'b0}};
        for (ki = 0; ki < BUF_DEPTH; ki = ki + 1) begin
            sb_ent_w  = {W_BPK{1'b0}};
            cand_v_w  = {{W_CMP{1'b0}}};
            cand_p_w  = {W_IDX{1'b0}};
            cand_f_w  = {W_THR{1'b0}};
            cand_k_w  = {W_DER_NODE{1'b0}};
            // The peak under test is written at slot pk_cnt[6:0], so the walk reads the entry
            // of peak (pk_cnt - ki) at that slot minus ki, taken modulo the depth. A fixed
            // base of (BUF_MASK - ki) only lines up when the peak counter happens to sit at
            // the mask, and otherwise reads an entry about a hundred peaks old.
            sb_idx_w  = (pk_cnt_q[6:0] - ki[6:0]) & BUF_MASK_D;
            sb_off_w  = sb_idx_w * W_BPK_D;
            if ((sb_arm_w & ~sb_ovf_w) & (ki < sb_n_w)) begin
                if (ki == 0) begin
                    // the peak under test is itself a candidate (K7)
                    cand_v_w = pv_c;
                    cand_p_w = pos_w;
                    cand_f_w = {{(W_THR-W_HP_NODE){1'b0}}, pk_f_w};
                    cand_k_w = kem_w;
                end else begin
                    sb_ent_w = bpk_vec[sb_off_w +: W_BPK];
                    cand_v_w = $signed({{(W_CMP-W_PV){1'b0}}, sb_ent_w[BPK_PV_L +: W_PV]});
                    cand_p_w = sb_ent_w[BPK_POS_L +: W_IDX];
                    cand_f_w = {{(W_THR-W_PKMAG){1'b0}}, sb_ent_w[BPK_PF_L +: W_PKMAG]};
                    cand_k_w = sb_ent_w[BPK_KM_L +: W_DER_NODE];
                end
                if ((cand_v_w > i2_c) && (cand_v_w <= i1_c) &&
                    (~sb_hit_w || (cand_v_w >= sb_vc_w))) begin
                    sb_hit_w = 1'b1;
                    sb_sp_w  = cand_p_w;
                    sb_j_w   = pk_cnt_q - ki;
                    sb_vc_w  = cand_v_w;
                    sb_vf_w  = cand_f_w;
                    sb_vk_w  = cand_k_w;
                end
            end
        end
    end

    wire [W_WIN-1:0] sb_v_w = sb_vc_w[W_WIN-1:0];

    // The refit updates of rantai.py:705-709. The asymmetry of parity trap 5 is kept
    // exactly: :706 uses the pre-update local spkf, :708 uses state["npkf"] AFTER :700
    // wrote it, and :709 uses the pre-update local spki.
    wire signed [W_ACC-1:0] sbv_e  = $signed({{(W_ACC-W_WIN){1'b0}}, sb_v_w});
    wire signed [W_ACC-1:0] sbvf_e = $signed({{(W_ACC-W_THR){1'b0}}, sb_vf_w});
    wire                    sbvf_gt_f1_w = (sbvf_e > f1_w);
    wire signed [W_ACC-1:0] spki_sb_w = spki_x + ((sbv_e - spki_x) >>> SHIFT_REFIT);
    wire signed [W_ACC-1:0] spkf_sb_w = sbvf_gt_f1_w
                                        ? (spkf_x + ((sbvf_e - spkf_x) >>> SHIFT_REFIT))
                                        : spkf_x;
    wire signed [W_ACC-1:0] npkf_sb_w = sbvf_gt_f1_w
                                        ? npkf_nse_w
                                        : (npkf_nse_w + ((sbvf_e - npkf_nse_w) >>> SHIFT_REFIT));

    // =======================================================================
    // Recording a QRS, rantai.py:624-642. The recorded index is the peak's own
    // sample index, except on a refit, where the model records puncak[j] of the
    // candidate and i_qrs moves backwards.
    // =======================================================================
    wire             rec_qrs_w = peak_w & (sig2_w | sb_hit_w);
    wire [W_IDX-1:0] rec_idx_w = sig2_w ? pos_w : sb_sp_w;
    wire [W_IDX-1:0] rec_pk_w  = sig2_w ? pk_cnt_q : sb_j_w;
    wire [W_IDX-1:0] rr_smp_w  = rec_idx_w - i_qrs_q;
    wire [W_IDX+1:0] rr_ms_w   = {rr_smp_w, 2'b00};   // 1000/250 is exactly 4, rantai.py:632
    wire             rr_beat_w = rec_qrs_w & i_qrs_v_q &
                                 (rr_ms_w >= RR_MIN_DX) & (rr_ms_w <= RR_MAX_DX);

    // =======================================================================
    // RR stage mirror, rantai.py:375-440, integer only, for the three elements
    // semai, penanda and langkah of ambang_state. Only in band beats reach it, which
    // is exactly the guard of rantai.py:638.
    // =======================================================================
    wire [RR_W-1:0] rr_word_w = rr_ms_w[RR_W-1:0];

    wire [3:0]          deret_len_n = (deret_len_q == RR_LEN_D) ? deret_len_q
                                                                : (deret_len_q + 4'd1);
    wire [RR_SUM_W-1:0] deret_app_n = deret_sum_q + {4'b0, rr_word_w};
    wire [RR_SUM_W-1:0] deret_drp_n = deret_sum_q + {4'b0, rr_word_w} - {4'b0, deret_q[RR_LEN-1]};
    wire [RR_SUM_W-1:0] deret_sum_n = (deret_len_q == RR_LEN_D) ? deret_drp_n : deret_app_n;
    wire [RR_SUM_W-1:0] ra1_n = deret_sum_n >>> SHIFT_RA1;

    wire [5:0] rih_len_n = (rih_len_q == 6'd32) ? rih_len_q : (rih_len_q + 6'd1);

    wire [RR_W-1:0] deret_new [0:RR_LEN-1];
    wire [RR_W-1:0] antre_new [0:RR_LEN-1];
    wire [RR_W-1:0] rih_new   [0:RIH_LEN-1];
    // shift is written as an explicit index 0 plus a loop from one, so no branch ever
    // names index -1 (a static out of bounds read, which Icarus warns about).
    assign deret_new[0] = rr_word_w;
    assign antre_new[0] = rr_word_w;
    assign rih_new[0]   = rr_word_w;
    genvar gd;
    generate
        for (gd = 1; gd < RR_LEN; gd = gd + 1) begin : g_queue_new
            assign deret_new[gd] = deret_q[gd-1];
            assign antre_new[gd] = antre_q[gd-1];
        end
    endgenerate
    genvar gr;
    generate
        for (gr = 1; gr < RIH_LEN; gr = gr + 1) begin : g_rih_new
            assign rih_new[gr] = rih_q[gr-1];
        end
    endgenerate

    // the early return of rantai.py:397-398: the queue of eight is not full yet, so the
    // model appends both queues and touches no average and no counter
    wire rr_early_w = rr_beat_w & (deret_len_n != RR_LEN_D);

    // the in band test of rantai.py:359, in the cross form 25*d*x against 23*p and 29*p
    wire [31:0] rr_ref_w  = (peny_q != 4'd0) ? {12'b0, pemb_q} : {12'b0, ra1_n};
    wire [31:0] rr_refd_w = (peny_q != 4'd0) ? {28'b0, peny_q} : 32'd1;
    wire [31:0] rr_lhs_w  = RR_SCALE_D * rr_refd_w * {16'b0, rr_word_w};
    wire [31:0] rr_lo_w   = RR_LO_D * rr_ref_w;
    wire [31:0] rr_hi_w   = RR_HI_D * rr_ref_w;
    wire        lolos_w   = (rr_lhs_w >= rr_lo_w) && (rr_lhs_w <= rr_hi_w);

    wire [31:0] gagal_n  = lolos_w ? 32'd0 : (gagal_q + 32'd1);
    wire [31:0] jeda_n   = jeda_q + 32'd1;
    wire        reseed_w = (gagal_n >= DELAPAN_D) & (jeda_n >= SEMAI_JEDA_D);

    // the median of the history, rantai.py:364-372, floor on the even count. The model
    // sorts and then reads the two middle entries. A sort network here would read and
    // write one array node inside a combinational block, which is a circular dependency
    // for a lint tool and for a real netlist, so the same two order statistics are taken
    // by rank counting instead: the value at rank r is the largest entry v with
    // #{entries < v} <= r. Nothing is written back, so the block stays acyclic.
    // History slots above the current length are padded with a word larger than any in
    // band interval. A pad cannot be selected: m entries lie below it and r is below m.
    wire [RIH_LEN*RR_W-1:0] rih_pack;
    generate
        for (gr = 0; gr < RIH_LEN; gr = gr + 1) begin : g_rih_pack
            assign rih_pack[gr*RR_W +: RR_W] = (gr < rih_len_n) ? rih_new[gr] : {RR_W{1'b1}};
        end
    endgenerate

    wire [RIH_LEN*6-1:0] lcnt_pack;
    generate
        for (gr = 0; gr < RIH_LEN; gr = gr + 1) begin : g_lcnt
            assign lcnt_pack[gr*6 +: 6] = f_less_count(rih_pack, rih_pack[gr*RR_W +: RR_W]);
        end
    endgenerate

    wire [5:0] med_hi_w = rih_len_n >> 1;
    wire [5:0] med_lo_w = (rih_len_n - 6'd1) >> 1;

    reg [RR_W-1:0] med_vlo_w;
    reg [RR_W-1:0] med_vhi_w;
    always @(*) begin
        med_vlo_w = {RR_W{1'b0}};
        med_vhi_w = {RR_W{1'b0}};
        for (mi = 0; mi < RIH_LEN; mi = mi + 1) begin
            if ((lcnt_pack[mi*6 +: 6] <= med_lo_w) &&
                (rih_pack[mi*RR_W +: RR_W] > med_vlo_w)) begin
                med_vlo_w = rih_pack[mi*RR_W +: RR_W];
            end
            if ((lcnt_pack[mi*6 +: 6] <= med_hi_w) &&
                (rih_pack[mi*RR_W +: RR_W] > med_vhi_w)) begin
                med_vhi_w = rih_pack[mi*RR_W +: RR_W];
            end
        end
    end
    wire [RR_W:0] med_sum_w = {1'b0, med_vlo_w} + {1'b0, med_vhi_w};
    wire [RR_W:0] med_w = med_sum_w >> 1;

    // the accepted queue after this beat, rantai.py:413-423
    wire [3:0]          antre_len_n   = (antre_len_q == RR_LEN_D) ? antre_len_q
                                                                  : (antre_len_q + 4'd1);
    wire [RR_SUM_W-1:0] antre_app_n   = antre_sum_q + {4'b0, rr_word_w};
    wire [RR_SUM_W-1:0] antre_drp_n   = antre_sum_q + {4'b0, rr_word_w}
                                        - {4'b0, antre_q[RR_LEN-1]};
    wire [RR_SUM_W-1:0] antre_sum_app = (antre_len_q == RR_LEN_D) ? antre_drp_n : antre_app_n;
    wire [RR_SUM_W-1:0] antre_sum_rs  = {med_w, 3'b000};         // 8 times the median
    wire [RR_SUM_W-1:0] pemb_n = reseed_w ? antre_sum_rs
                              : (lolos_w ? antre_sum_app : antre_sum_q);
    wire [3:0]          peny_n = reseed_w ? RR_LEN_D
                              : (lolos_w ? antre_len_n : antre_len_q);

    // menyala of rantai.py:431-438, on the NEW queue of eight and the NEW accepted queue.
    // All eight entries are tested because penyebut is 8, which also means the queue of
    // eight is full.
    reg mem_w;
    // The firmware lights the rhythm flag over the values the queue holds *after* this beat
    // has been absorbed (rantai.py:424-437 recomputes pembilang and penyebut before the
    // loop), so the band has to be formed from pemb_n, not from the pre update reference
    // that decides lolos.
    wire [31:0] rr_lopost_w = RR_LO_D * {12'b0, pemb_n};
    wire [31:0] rr_hipost_w = RR_HI_D * {12'b0, pemb_n};
    always @(*) begin
        mem_w = 1'b0;
        if (peny_n == RR_LEN_D) begin
            mem_w = 1'b1;
            for (mi = 0; mi < RR_LEN; mi = mi + 1) begin
                if (!(((RR_SCALE_D * {28'b0, peny_n} * {16'b0, deret_new[mi]}) >= rr_lopost_w) &&
                      ((RR_SCALE_D * {28'b0, peny_n} * {16'b0, deret_new[mi]}) <= rr_hipost_w))) begin
                    mem_w = 1'b0;
                end
            end
        end
    end

    // =======================================================================
    // Overflow sources. All of them are reported through the sticky m_overflow
    // flag, which the testbench reads back; nothing wraps and nothing is dropped in
    // silence.
    // =======================================================================
    wire thr_rail_w   = (i1_w > THR_RAIL_D) || (f1_w > THR_RAIL_D);
    // Defensive rails: every one of these bits is provably clear for any input the frozen
    // node widths can carry, because each state update is a convex combination of two 33
    // bit unsigned words and the envelope node is non negative. The last term watches the
    // envelope word's sign bit, because the candidate buffer stores the envelope at its 32
    // bit unsigned magnitude (plan 38, line 1854 budgets 112 bits per entry). Each is
    // reported through the sticky overflow flag rather than being dropped on the floor. The
    // median sum carry is deliberately NOT one of them: a median pair can legitimately
    // reach 2**17 and the carry is discarded by the shift.
    wire state_rail_w = spki_sig_w[W_ACC-1] | spkf_sig_w[W_ACC-1] | npkf_sig_w[W_ACC-1] |
                        npki_nse_w[W_ACC-1] | spki_sb_w[W_ACC-1]  | spkf_sb_w[W_ACC-1]  |
                        npkf_sb_w[W_ACC-1]  | pv_w[W_WIN-1];
    wire overflow_now = (peak_w & (thr_rail_w | sb_ovf_w | state_rail_w)) | scan_jump_w;

    // =======================================================================
    // The single sequential block: one clock, synchronous active low reset
    // =======================================================================
    always @(posedge clk_i) begin
        if (!rst_ni) begin
            m_tdata      <= {W_WIN{1'b0}};
            m_tvalid     <= 1'b0;
            m_overflow   <= 1'b0;
            m_tlast      <= 1'b0;
            m_tuser      <= {W_TUSER{1'b0}};
            m_sample_idx <= {W_IDX{1'b0}};
            m_ev_valid   <= 1'b0;
            m_ev_kind    <= afib_lite_pkg::EV_NONE;
            m_ev_idx     <= {W_IDX{1'b0}};
            m_ev_val     <= 32'd0;
            d_valid      <= 1'b0;
            d_thr        <= {W_THR{1'b0}};
            d_pk         <= {W_THR{1'b0}};
            o_beat_count <= 32'd0;
            dbg_q        <= {W_DBG{1'b0}};
            dbg_valid_q  <= 1'b0;
            scan_q       <= RADIUS_DX;
            pk_cnt_q     <= {W_IDX{1'b0}};
            spki_q       <= {W_STATE{1'b0}};
            npki_q       <= {W_STATE{1'b0}};
            spkf_q       <= {W_STATE{1'b0}};
            npkf_q       <= {W_STATE{1'b0}};
            i_qrs_q      <= {W_IDX{1'b0}};
            i_qrs_v_q    <= 1'b0;
            i_qrs_pk_q   <= {W_IDX{1'b0}};
            i_qrs_pk_v_q <= 1'b0;
            kem_qrs_q    <= {W_DER_NODE{1'b0}};
            kem_qrs_v_q  <= 1'b0;
            c_calon_q    <= 32'd0;
            c_cari_q     <= 32'd0;
            c_diper_q    <= 32'd0;
            c_ditol_q    <= 32'd0;
            c_terima_q   <= 32'd0;
            c_beri_q     <= 32'd0;
            c_penanda_q  <= 32'd0;
            c_langkah_q  <= 32'd0;
            deret_len_q  <= 4'd0;
            deret_sum_q  <= {RR_SUM_W{1'b0}};
            antre_len_q  <= 4'd0;
            antre_sum_q  <= {RR_SUM_W{1'b0}};
            rih_len_q    <= 6'd0;
            ra1_q        <= {RR_SUM_W{1'b0}};
            pemb_q       <= {RR_SUM_W{1'b0}};
            peny_q       <= 4'd0;
            gagal_q      <= 32'd0;
            jeda_q       <= SEMAI_JEDA_D;   // rantai.py:353 starts the reseed gap at 8
            semai_q      <= 32'd0;
            sel_vec      <= {SEL_LINE*W_WIN{1'b0}};
            hp_vec       <= {HP_LINE*W_HP_NODE{1'b0}};
            bes_vec      <= {BES_LINE*W_DER_NODE{1'b0}};
            bpk_vec      <= {BUF_DEPTH{{W_BPK{1'b0}}}};
            for (wi = 0; wi < RR_LEN; wi = wi + 1) begin
                deret_q[wi] <= {RR_W{1'b0}};
                antre_q[wi] <= {RR_W{1'b0}};
            end
            for (wi = 0; wi < RIH_LEN; wi = wi + 1) begin
                rih_q[wi] <= {RR_W{1'b0}};
            end
        end else begin
            // ---- frozen stream forwarding: one cycle of latency, word for word
            m_tvalid <= accept_w;
            if (accept_w) begin
                m_tdata      <= s_tdata;
                m_tlast      <= s_tlast;
                m_tuser      <= s_tuser;
                m_sample_idx <= s_sample_idx;
            end

            // ---- the three delay lines advance on an accepted word only, so the warm-up
            // is the model's own zero initial condition
            if (accept_w) begin
                sel_vec <= {sel_vec[(SEL_LINE-1)*W_WIN-1:0], s_tdata};
                hp_vec  <= {hp_vec[(HP_LINE-1)*W_HP_NODE-1:0], s_hp};
                bes_vec <= {bes_vec[(BES_LINE-1)*W_DER_NODE-1:0], s_besaran};
            end

            // ---- sticky overflow, cleared by reset or by i_clear_counters
            m_overflow <= i_clear_counters ? 1'b0 : (m_overflow | overflow_now);

            // ---- envelope peak scanner, one step per accepted sample (K6)
            if (chk_w) begin
                scan_q <= peak_w ? (scan_q + RADIUS_DX) : (scan_q + 1'b1);
            end

            // ---- per peak work
            if (peak_w) begin
                // the four parallel arrays of rantai.py:617-618, written before the
                // threshold stage reads them, and the index the model calls i_puncak
                bpk_vec[pk_cnt_q[6:0]*W_BPK_D +: W_BPK] <=
                    {kem_w, pk_f_w, pv_w[W_PV-1:0], pos_w};
                pk_cnt_q <= pk_cnt_q + 1'b1;

                // the nine ambang_state counters: :672, :677, :679, :681, :694
                if (c_diper_w) c_diper_q  <= c_diper_q  + 32'd1;
                if (c_ditol_w) c_ditol_q  <= c_ditol_q  + 32'd1;
                if (c_terim_w) c_terima_q <= c_terima_q + 32'd1;
                if (c_calon_w) c_calon_q  <= c_calon_q  + 32'd1;
                if (c_beri_w)  c_beri_q   <= c_beri_q   + 32'd1;
                if (sb_hit_w)  c_cari_q   <= c_cari_q   + 32'd1;

                // threshold state, rantai.py:683-687 on the signal path and :699-709 on
                // the noise path including the refit
                spki_q <= sig2_w ? spki_sig_w[W_STATE-1:0]
                                 : (sb_hit_w ? spki_sb_w[W_STATE-1:0] : spki_q);
                npki_q <= sig2_w ? npki_q : npki_nse_w[W_STATE-1:0];
                spkf_q <= sig2_w ? spkf_sig_w[W_STATE-1:0]
                                 : (sb_hit_w ? spkf_sb_w[W_STATE-1:0] : spkf_q);
                npkf_q <= sig2_w ? npkf_sig_w[W_STATE-1:0]
                                 : (sb_hit_w ? npkf_sb_w[W_STATE-1:0] : npkf_nse_w[W_STATE-1:0]);

                if (sig2_w) begin
                    kem_qrs_q   <= kem_w;      // rantai.py:695
                    kem_qrs_v_q <= 1'b1;
                end else if (sb_hit_w) begin
                    kem_qrs_q   <= sb_vk_w;    // rantai.py:710
                    kem_qrs_v_q <= 1'b1;
                end
            end

            // ---- recording a QRS, rantai.py:624-642
            if (rec_qrs_w) begin
                i_qrs_q      <= rec_idx_w;
                i_qrs_v_q    <= 1'b1;
                i_qrs_pk_q   <= rec_pk_w;
                i_qrs_pk_v_q <= 1'b1;
                o_beat_count <= i_clear_counters ? 32'd0 : (o_beat_count + 32'd1);
            end else if (i_clear_counters) begin
                o_beat_count <= 32'd0;
            end

            // ---- RR mirror, only in band beats reach it (rantai.py:638-642)
            if (rr_beat_w) begin
                for (wi = 0; wi < RR_LEN; wi = wi + 1) begin
                    deret_q[wi] <= deret_new[wi];
                end
                deret_len_q <= deret_len_n;
                deret_sum_q <= deret_sum_n;
                for (wi = 0; wi < RIH_LEN; wi = wi + 1) begin
                    rih_q[wi] <= rih_new[wi];
                end
                rih_len_q   <= rih_len_n;
                c_langkah_q <= c_langkah_q + 32'd1;
                c_penanda_q <= c_penanda_q + {31'd0, mem_w};
                if (!rr_early_w) begin
                    if (reseed_w) begin
                        for (wi = 0; wi < RR_LEN; wi = wi + 1) begin
                            antre_q[wi] <= med_w[RR_W-1:0];
                        end
                        semai_q <= semai_q + 32'd1;
                        gagal_q <= 32'd0;
                        jeda_q  <= 32'd0;
                    end else if (lolos_w) begin
                        for (wi = 0; wi < RR_LEN; wi = wi + 1) begin
                            antre_q[wi] <= antre_new[wi];
                        end
                    end
                    antre_len_q <= peny_n;
                    antre_sum_q <= pemb_n;
                    ra1_q       <= ra1_n;
                    pemb_q      <= pemb_n;
                    peny_q      <= peny_n;
                    if (!reseed_w) begin
                        gagal_q <= gagal_n;
                        jeda_q  <= jeda_n;
                    end
                end
            end

            // ---- event sideband, one cycle with the word that made it
            // One event per peak row: the row's verdict. The generator of the expected
            // vectors keys the row's kind and index on qrs_sample_index (K7's recording
            // row), so a refit row is a QRS event whose index is the recorded position,
            // which is earlier than the row's own sample index.
            m_ev_valid <= peak_w;
            m_ev_kind  <= rec_qrs_w ? afib_lite_pkg::EV_QRS : afib_lite_pkg::EV_PEAK_CAND;
            m_ev_idx   <= rec_qrs_w ? rec_idx_w : pos_w;
            m_ev_val   <= pv_w[31:0];
            d_valid    <= peak_w;
            d_thr      <= i1_w[W_THR-1:0];
            d_pk       <= {{(W_THR-W_HP_NODE){1'b0}}, pk_f_w};

            // ---- additive introspection. The words are post-increment, so on a peak
            // cycle they carry what the peak just did.
            dbg_valid_q <= peak_w;
            dbg_q[DBG_CALON_KEDUA*32 +: 32] <= c_calon_q + ((peak_w & c_calon_w) ? 32'd1 : 32'd0);
            dbg_q[DBG_CARI_MUNDUR*32 +: 32] <= c_cari_q + ((peak_w & sb_hit_w) ? 32'd1 : 32'd0);
            dbg_q[DBG_DIPERIKSA*32   +: 32] <= c_diper_q + ((peak_w & c_diper_w) ? 32'd1 : 32'd0);
            dbg_q[DBG_DITOLAK*32     +: 32] <= c_ditol_q + ((peak_w & c_ditol_w) ? 32'd1 : 32'd0);
            dbg_q[DBG_DITERIMA*32    +: 32] <= c_terima_q + ((peak_w & c_terim_w) ? 32'd1 : 32'd0);
            dbg_q[DBG_BERISIKO*32    +: 32] <= c_beri_q + ((peak_w & c_beri_w) ? 32'd1 : 32'd0);
            dbg_q[DBG_SEMAI*32       +: 32] <= semai_q +
                ((rr_beat_w & ~rr_early_w & reseed_w) ? 32'd1 : 32'd0);
            dbg_q[DBG_PENANDA*32     +: 32] <= c_penanda_q +
                (rr_beat_w ? {31'd0, mem_w} : 32'd0);
            dbg_q[DBG_LANGKAH*32     +: 32] <= c_langkah_q +
                (rr_beat_w ? 32'd1 : 32'd0);
            dbg_q[DBG_PV*32          +: 32] <= pv_w[31:0];
            dbg_q[DBG_KEM*32         +: 32] <= {{(32-W_DER_NODE){1'b0}}, kem_w};
            dbg_q[DBG_FLAGS*32       +: 32] <= (sig2_w   ? DBG_F_SIGNAL   : 32'd0) |
                                               (pita_w   ? DBG_F_INBAND   : 32'd0) |
                                               (trej_w   ? DBG_F_TREJECT  : 32'd0) |
                                               (sb_hit_w ? DBG_F_REFIT    : 32'd0) |
                                               ((sb_hit_w & ~sig2_w) ? DBG_F_REFITQRS : 32'd0);
            dbg_q[DBG_POS*32         +: 32] <= pos_w;
            dbg_q[DBG_RAILS*32       +: 32] <= (sig1_w       ? DBG_F_SIGNAL1  : 32'd0) |
                                               (sb_arm_w     ? DBG_F_ARMED    : 32'd0) |
                                               (sb_ovf_w     ? DBG_F_SBOVF    : 32'd0) |
                                               (scan_jump_w  ? DBG_F_SCANJUMP : 32'd0) |
                                               (state_rail_w ? DBG_F_STRAIL   : 32'd0) |
                                               (thr_rail_w   ? DBG_F_THRRAIL  : 32'd0);
        end
    end

    assign d_dbg       = dbg_q;
    assign d_dbg_valid = dbg_valid_q;

endmodule

`default_nettype wire
