// ---------------------------------------------------------------------------
// tb_gelombang_t.sv -- Fase 7 gate for rtl/t_rule.sv, the canonical T-wave rule block
// (plan doc 38 phase 7; testbench name from plan 7.1 table row 10 and plan 3.4).
//
// The gate this file closes, quoted from rtlplan2/final38.md:124:
//   "bentuk silang sama dengan rute float pada seluruh pasangan nyata, 0 beda; selisih
//    2.048 dari 16.777.216 pada grid didokumentasikan"
//
// Four phases, one run:
//
// PH_REAL  the frozen recording. The derivative column 04015.turunan.hex is streamed at the
//          chain cadence (one accepted word every CAD cycles), and a peak candidate pulse is
//          raised on every one of the 4777 envelope peak positions of rtlplan2/fase5/
//          04015.peaks.csv, carrying the model's own delta and kem_qrs. Every verdict is
//          compared against three independent things:
//            (a) the frozen run's columns in_band and t_rejected (the model's dalam_pita and
//                ditolak, 2029 and 1909 ones),
//            (b) the model's slope column, recomputed by siapkan_vektor_fase7.py with the
//                frozen model's own GarisTunda.maks_mutlak,
//            (c) the FLOAT ROUTE computed here on the same pair: dalam_pita and
//                (kem < kem_qrs / 2.0) in real arithmetic, a different route from the integer
//                cross form the RTL uses.
//          The forbidden shift route (kem < (kem_qrs >> 1)) is counted here as well, to show
//          that the recording alone cannot tell the two forms apart (the plan's point).
//
// PH_SINT  a synthetic derivative line (04015.sintetis.turunan.hex, a documented LCG plus
//          spikes) with 5453 sampled peak positions, to test the 37 word absolute maximum
//          window itself, including the model's lo clamp at the start of the line.
//
// PH_STAIR the pair grid, driven through the SAME block: every row gets a 37 word constant
//          derivative block, so the window slope equals that row's value, and a peak pulse in
//          the middle of the block (rantai.py's window covers exactly that block). Rows
//          0..16381 are the boundary complete lattice of the crossing form plus a pseudo
//          random sample: {(s, s_prev) : s_prev in 0..4095, s in {floor(s_prev/2)-1,
//          floor(s_prev/2), floor(s_prev/2)+1} clamped at 0} and 4096 random pairs. That set
//          contains EVERY pair where the crossing form and the forbidden shift form can
//          differ. The last 13 rows are the edge cases: delta exactly 89 (in band) and exactly
//          90 (out of band, 90<<2 = 360 is not < 360), 2*kem exactly kem_qrs (never a
//          rejection), 2*kem = kem_qrs - 1 (a rejection), kem_qrs = 0, delta None (no QRS
//          yet), kem_qrs None, the rule disabled, and the magnitude rail where kem saturates
//          the W_TW report word.
//
// PH_OVR   the overrun detector itself: peaks 10 accepted words apart must be served, peaks 9
//          apart must set o_overrun and drop the candidate, never mis-evaluate it.
//
// Golden data: +VECTOR=<dir> holds the Fase 7 vectors written by rtl/tb/vektor/fase7/
// siapkan_vektor_fase7.py: one 32 bit word per line, 8 hex digits, two's complement, no
// comments, $readmemh compatible. 04015.turunan.hex inside that directory is a byte identical
// copy of the frozen Fase 0 column. NO expected measurement is typed in this file: every
// compared number comes from a vector column, from afib_lite_pkg, or from the float route
// computed here out of the vector columns. The only constants typed here are structural: the
// word counts of the columns and the documented latency, 19 + 10 + 1 = 30 accepted words,
// which this file also MEASURES and prints.
//
// Optional plusargs: +LIMIT=<n> shortens PH_REAL only (the other phases always run whole).
//
// No file level timescale, same reason as the other testbenches: the package carries none and
// the lint tool raises TIMESCALEMOD on a file level timescale here.
// ---------------------------------------------------------------------------
`default_nettype none

module tb_gelombang_t;

    // ---- sizes of the vector columns, from 04015.fase7.manifest.json ----
    localparam integer N_FRAMES = 450000;
    localparam integer N_PEAK   = 4777;     // memory capacity, the live count is mem_cnt
    localparam integer N_SINT   = 60000;
    localparam integer N_SPOS   = 5453;     // memory capacity, the live count is mem_cnt
    localparam integer N_STAIR  = 16396;    // memory capacity, the live count is mem_cnt

    // ---- structure constants ----
    localparam integer CAD      = 8;    // cycles between accepted words, the chain cadence
    localparam integer BLOCK    = 37;   // stair block length = the model's window length
    localparam integer N_TAIL   = 80;   // words after the last block so it gets its verdict
    localparam integer LAT_ACC  = 30;   // PEAK_DEPTH 19 + SCAN_CYC 10 + LAT_CYCLES 1
    localparam integer HALF_WIN = afib_lite_pkg::SETENGAH_JENDELA;   // 18, rantai.py:59
    localparam integer W_DER    = afib_lite_pkg::W_DER;              // 24
    localparam integer W_TW     = afib_lite_pkg::W_TW;               // 23
    localparam integer KEM_RAIL = (1 << W_TW) - 1;                   // 2**23 - 1

    // ---- flag bits of 04015.fase7.flag.hex ----
    localparam integer F_DVALID = 0;   // the model had a previous QRS
    localparam integer F_KVALID = 1;   // the model had a previous QRS slope
    localparam integer F_INBAND = 2;   // the frozen run's in_band column
    localparam integer F_TREJ   = 3;   // the frozen run's t_rejected column

    // ---- flag bits of 04015.stair.flag.hex ----
    localparam integer S_DVALID = 0;
    localparam integer S_KVALID = 1;
    localparam integer S_ENABLE = 2;
    localparam integer S_INBAND = 3;
    localparam integer S_REJECT = 4;
    localparam integer S_GRID   = 5;

    // ---- counts of 04015.fase7.counts.hex ----
    localparam integer C_FRAMES   = 0;
    localparam integer C_PEAKS    = 1;
    localparam integer C_SINTW    = 3;
    localparam integer C_SINTPOS  = 4;
    localparam integer C_STAIR    = 7;
    localparam integer C_GRIDSIM  = 8;   // shift route differences over the simulated pairs
    localparam integer C_FLOATSIM = 9;   // float route differences over the simulated pairs

    localparam [3:0] PH_RST   = 4'd0;
    localparam [3:0] PH_REAL  = 4'd1;
    localparam [3:0] PH_RST2  = 4'd2;
    localparam [3:0] PH_SINT  = 4'd3;
    localparam [3:0] PH_RST3  = 4'd4;
    localparam [3:0] PH_STAIR = 4'd5;
    localparam [3:0] PH_RST4  = 4'd6;
    localparam [3:0] PH_OVR   = 4'd7;
    localparam [3:0] PH_DONE  = 4'd8;

    reg clk = 1'b0;
    reg rst_n;
    reg [3:0] phase;
    reg [3:0] rst_cnt;

    reg  [W_DER-1:0]  s_tdata;
    reg               s_tvalid;
    reg               s_tlast;
    reg  [7:0]        s_tuser;
    reg  [31:0]       s_sample_idx;
    reg               i_rule_enable;
    reg               i_peak_valid;
    reg  [31:0]       i_delta;
    reg               i_delta_valid;
    reg  [W_DER-1:0]  i_kem_qrs;
    reg               i_kem_qrs_valid;

    wire [W_TW-1:0]   m_tdata;
    wire              m_tvalid;
    wire              m_overflow;
    wire              m_tlast;
    wire [7:0]        m_tuser;
    wire [31:0]       m_sample_idx;
    wire              o_reject;
    wire              d_valid;
    wire [W_TW-1:0]   d_tw;
    wire              o_peak_valid;
    wire [31:0]       o_peak_idx;
    wire              o_dalam_pita;
    wire              o_overrun;

    t_rule u_dut (
        .clk_i            (clk),
        .rst_ni           (rst_n),
        .s_tdata          (s_tdata),
        .s_tvalid         (s_tvalid),
        .s_tlast          (s_tlast),
        .s_tuser          (s_tuser),
        .s_sample_idx     (s_sample_idx),
        .i_rule_enable    (i_rule_enable),
        .m_tdata          (m_tdata),
        .m_tvalid         (m_tvalid),
        .m_overflow       (m_overflow),
        .m_tlast          (m_tlast),
        .m_tuser          (m_tuser),
        .m_sample_idx     (m_sample_idx),
        .o_reject         (o_reject),
        .d_valid          (d_valid),
        .d_tw             (d_tw),
        .i_peak_valid     (i_peak_valid),
        .i_delta          (i_delta),
        .i_delta_valid    (i_delta_valid),
        .i_kem_qrs        (i_kem_qrs),
        .i_kem_qrs_valid  (i_kem_qrs_valid),
        .o_peak_valid     (o_peak_valid),
        .o_peak_idx       (o_peak_idx),
        .o_dalam_pita     (o_dalam_pita),
        .o_overrun        (o_overrun)
    );

    always #5 clk <= ~clk;

    // The derivative columns hold the 32 bit two's complement pattern of a signed 24 bit
    // value (Fase 0 manifest, word_interpretation), so they are read as unsigned 32 bit words
    // and the low W_DER bits are taken as the signed word.
    reg [31:0] mem_der  [0:N_FRAMES-1];
    reg [31:0] mem_pos  [0:N_PEAK-1];
    reg [31:0] mem_kem  [0:N_PEAK-1];
    reg [31:0] mem_del  [0:N_PEAK-1];
    reg [31:0] mem_kq   [0:N_PEAK-1];
    reg [31:0] mem_flag [0:N_PEAK-1];
    reg [31:0] mem_sin  [0:N_SINT-1];
    reg [31:0] mem_spos [0:N_SPOS-1];
    reg [31:0] mem_skem [0:N_SPOS-1];
    reg [31:0] mem_sder [0:N_STAIR-1];
    reg [31:0] mem_ssp  [0:N_STAIR-1];
    reg [31:0] mem_sdel [0:N_STAIR-1];
    reg [31:0] mem_sflg [0:N_STAIR-1];
    reg [31:0] mem_cnt  [0:10];   // one word per entry of COUNTS in the vector script

    reg [1023:0] vdir;
    reg [1023:0] fpath;

    // ---- driver state ----
    integer limit_n;
    integer n_peak;      // live counts, read from 04015.fase7.counts.hex, never typed here
    integer n_spos;
    integer n_stair;
    integer feed;
    integer cad_q;
    integer pk_feed;
    integer sint_feed;
    integer spos_feed;
    integer stair_word;
    reg [31:0] acc_idx;
    integer lat_meas;
    integer lat_bad;
    integer ovr_w_idx;

    // ---- counters, PH_REAL ----
    integer r_vr;
    integer r_exp;
    integer r_mism_idx;
    integer r_mism_kem;
    integer r_mism_pita;
    integer r_mism_rej;
    integer r_mism_float;
    integer r_diff_shift;
    integer r_high_slope;
    integer r_mism_user;
    integer r_mism_last;
    integer r_mism_alive;
    integer r_ovr;
    integer r_ovf;
    integer r_inband_seen;
    integer r_rej_seen;
    integer r_min_spacing;
    integer r_words;
    integer r_pulses;
    reg [3:0] ph_last;

    // ---- counters, PH_SINT ----
    integer s_vr;
    integer s_exp;
    integer s_mism_idx;
    integer s_mism_kem;

    // ---- counters, PH_STAIR ----
    integer g_vr;
    integer g_mism_idx;
    integer g_mism_kem;
    integer g_mism_pita;
    integer g_mism_rej;
    integer g_mism_float;
    integer g_diff_shift;
    integer g_diff_float;
    integer g_mism_ovf;
    integer g_rail_seen;

    // ---- counters, PH_OVR ----
    integer o_vr;
    integer o_mism_idx;
    integer o_mism_kem;
    integer o_ovr_early;
    integer o_ovr_late;

    integer mism_total;
    integer i;


    // =======================================================================
    // Route helpers. The float route divides (kem < kem_qrs / 2.0), the forbidden shift
    // route shifts (kem < (kem_qrs >> 1)), and the cross form the RTL uses multiplies.
    // Only the first two are computed here, and only to compare against the block. kem is
    // the UNSATURATED window magnitude, W_DER bits wide: exactly what the rule compares.
    // =======================================================================
    function automatic [W_DER-1:0] f_kem_true (input [W_DER-1:0] v);
        begin
            f_kem_true = v[W_DER-1] ? ({W_DER{1'b0}} - v) : v;
        end
    endfunction

    function automatic bit f_float_reject (input bit in_band,
                                           input [W_DER-1:0] kem,
                                           input [W_DER-1:0] kemq);
        begin
            f_float_reject = in_band && ($itor(kem) < ($itor(kemq) / 2.0));
        end
    endfunction

    // the forbidden shift route halves with a shift, floor for an unsigned word
    function automatic integer f_shift_half (input [W_DER-1:0] kemq);
        reg [W_DER:0] even;
        begin
            even = {1'b0, kemq} - {{W_DER{1'b0}}, kemq[0]};
            f_shift_half = 32'(even) >> 1;
        end
    endfunction

    function automatic bit f_shift_reject (input bit in_band,
                                           input [W_DER-1:0] kem,
                                           input [W_DER-1:0] kemq);
        begin
            f_shift_reject = in_band && (32'(kem) < f_shift_half(kemq));
        end
    endfunction

    // the rail of the W_TW report port, and the word actually reported
    function automatic bit f_rail (input [W_DER-1:0] v);
        begin
            f_rail = (f_kem_true(v) > W_DER'(KEM_RAIL));
        end
    endfunction

    function automatic [W_TW-1:0] f_report (input [W_DER-1:0] v);
        begin
            f_report = f_rail(v) ? W_TW'(KEM_RAIL) : W_TW'(f_kem_true(v));
        end
    endfunction

    function automatic integer f_blk (input integer w);
        begin
            f_blk = w / BLOCK;
        end
    endfunction

    function automatic integer f_off (input integer w);
        begin
            f_off = w % BLOCK;
        end
    endfunction

    // =======================================================================
    // Driver: one writer per signal, so no phase change races the stream.
    // =======================================================================
    always @(posedge clk) begin
        if (!rst_n) begin
            s_tvalid        <= 1'b0;
            s_tdata         <= {W_DER{1'b0}};
            s_tlast         <= 1'b0;
            s_tuser         <= 8'd0;
            s_sample_idx    <= 32'd0;
            i_rule_enable   <= 1'b0;
            i_peak_valid    <= 1'b0;
            i_delta         <= 32'd0;
            i_delta_valid   <= 1'b0;
            i_kem_qrs       <= {W_DER{1'b0}};
            i_kem_qrs_valid <= 1'b0;
            cad_q           <= 0;
            feed            <= 0;
            pk_feed         <= 0;
            sint_feed       <= 0;
            spos_feed       <= 0;
            stair_word      <= 0;
            ovr_w_idx       <= 0;
            // eight reset cycles, then the next phase starts
            if (rst_cnt >= 4'd7) begin
                rst_cnt <= 4'd0;
                rst_n   <= 1'b1;
                case (phase)
                    PH_RST:  phase <= PH_REAL;
                    PH_RST2: phase <= PH_SINT;
                    PH_RST3: phase <= PH_STAIR;
                    PH_RST4: phase <= PH_OVR;
                    default: ;
                endcase
            end else begin
                rst_cnt <= rst_cnt + 4'd1;
            end
        end else begin
            if (s_tvalid && o_peak_valid) begin
                lat_meas <= acc_idx - o_peak_idx;
                if ((acc_idx - o_peak_idx) != LAT_ACC) lat_bad <= lat_bad + 1;
            end
            // the peak word is the accepted word the candidate pulse rides on, so the verdict
            // word is exactly LAT_ACC accepted words later; r_words counts what PH_REAL fed
            if (rst_n && (phase == PH_REAL) && !s_tvalid && (feed == limit_n)) begin
                r_words  <= feed;
                r_pulses <= pk_feed;
            end

            case (phase)
                PH_REAL: begin
                    if ((cad_q == 0) && (feed < limit_n)) begin
                        s_tvalid     <= 1'b1;
                        s_tdata      <= mem_der[feed][W_DER-1:0];
                        s_tuser      <= 8'(feed);
                        s_sample_idx <= 32'(feed);
                        acc_idx      <= 32'(feed);
                        s_tlast      <= (feed == (limit_n - 1));
                        cad_q        <= CAD - 1;
                        feed         <= feed + 1;
                        if ((pk_feed < n_peak) && (mem_pos[pk_feed] == 32'(feed))) begin
                            i_peak_valid    <= 1'b1;
                            i_rule_enable   <= 1'b1;   // the frozen run has aturan_t True
                            i_delta         <= mem_del[pk_feed];
                            i_delta_valid   <= mem_flag[pk_feed][F_DVALID];
                            i_kem_qrs       <= mem_kq[pk_feed][W_DER-1:0];
                            i_kem_qrs_valid <= mem_flag[pk_feed][F_KVALID];
                            pk_feed         <= pk_feed + 1;
                        end else begin
                            i_peak_valid <= 1'b0;
                        end
                    end else begin
                        s_tvalid     <= 1'b0;
                        i_peak_valid <= 1'b0;
                        s_tlast      <= 1'b0;
                        if (cad_q > 0) cad_q <= cad_q - 1;
                        if ((cad_q == 0) && (feed >= limit_n)) begin
                            phase <= PH_RST2;
                            rst_n <= 1'b0;
                        end
                    end
                end

                PH_SINT: begin
                    if ((cad_q == 0) && (sint_feed < N_SINT)) begin
                        s_tvalid     <= 1'b1;
                        s_tdata      <= mem_sin[sint_feed][W_DER-1:0];
                        s_tuser      <= 8'(sint_feed);
                        s_sample_idx <= 32'(sint_feed);
                        acc_idx      <= 32'(sint_feed);
                        s_tlast      <= (sint_feed == (N_SINT - 1));
                        cad_q        <= CAD - 1;
                        sint_feed    <= sint_feed + 1;
                        if ((spos_feed < n_spos) && (mem_spos[spos_feed] == 32'(sint_feed))) begin
                            i_peak_valid    <= 1'b1;   // kem only, the rule stays silent here
                            i_rule_enable   <= 1'b0;
                            i_delta         <= 32'd0;
                            i_delta_valid   <= 1'b0;
                            i_kem_qrs       <= {W_DER{1'b0}};
                            i_kem_qrs_valid <= 1'b0;
                            spos_feed       <= spos_feed + 1;
                        end else begin
                            i_peak_valid <= 1'b0;
                        end
                    end else begin
                        s_tvalid     <= 1'b0;
                        i_peak_valid <= 1'b0;
                        s_tlast      <= 1'b0;
                        if (cad_q > 0) cad_q <= cad_q - 1;
                        if ((cad_q == 0) && (sint_feed >= N_SINT)) begin
                            phase <= PH_RST3;
                            rst_n <= 1'b0;
                        end
                    end
                end

                PH_STAIR: begin
                    // one accepted word per cycle: the block sees the highest achievable peak
                    // rate, and the row spacing is the contract minimum times almost four
                    if (stair_word < ((n_stair * BLOCK) + N_TAIL)) begin
                        s_tvalid     <= 1'b1;
                        s_sample_idx <= 32'(stair_word);
                        acc_idx      <= 32'(stair_word);
                        s_tuser      <= 8'(stair_word);
                        s_tlast      <= 1'b0;
                        if (stair_word < (n_stair * BLOCK)) begin
                            s_tdata <= mem_sder[f_blk(stair_word)][W_DER-1:0];
                            if (f_off(stair_word) == HALF_WIN) begin
                                i_peak_valid    <= 1'b1;
                                i_rule_enable   <= mem_sflg[f_blk(stair_word)][S_ENABLE];
                                i_delta         <= mem_sdel[f_blk(stair_word)];
                                i_delta_valid   <= mem_sflg[f_blk(stair_word)][S_DVALID];
                                i_kem_qrs       <= mem_ssp[f_blk(stair_word)][W_DER-1:0];
                                i_kem_qrs_valid <= mem_sflg[f_blk(stair_word)][S_KVALID];
                            end else begin
                                i_peak_valid <= 1'b0;
                            end
                        end else begin
                            s_tdata      <= {W_DER{1'b0}};
                            i_peak_valid <= 1'b0;
                        end
                        stair_word <= stair_word + 1;
                    end else begin
                        s_tvalid <= 1'b0;
                        phase    <= PH_RST4;
                        rst_n    <= 1'b0;
                    end
                end

                PH_OVR: begin
                    // derivative held at 1000, so the window slope is 1000 at every peak.
                    // peak words 0, 10, 20, 29: the first three are 10 accepted words apart
                    // and must be served, the fourth is 9 apart and must be refused with
                    // o_overrun set.
                    if (ovr_w_idx < 90) begin
                        s_tvalid     <= 1'b1;
                        s_tdata      <= 24'd1000;
                        s_tuser      <= 8'(ovr_w_idx);
                        s_sample_idx <= 32'(ovr_w_idx);
                        acc_idx      <= 32'(ovr_w_idx);
                        s_tlast      <= (ovr_w_idx == 89);
                        if ((ovr_w_idx == 0) || (ovr_w_idx == 10) ||
                            (ovr_w_idx == 20) || (ovr_w_idx == 29)) begin
                            i_peak_valid    <= 1'b1;
                            i_rule_enable   <= 1'b1;
                            i_delta         <= 32'd50;      // 50<<2 = 200 < 360, in band
                            i_delta_valid   <= 1'b1;
                            i_kem_qrs       <= 24'd5000;
                            i_kem_qrs_valid <= 1'b1;
                        end else begin
                            i_peak_valid <= 1'b0;
                        end
                        ovr_w_idx <= ovr_w_idx + 1;
                    end else begin
                        s_tvalid <= 1'b0;
                        phase    <= PH_DONE;
                    end
                end

                default: ;   // the reset phases are served by the branch above
            endcase
        end
    end

    // =======================================================================
    // PH_REAL and PH_SINT checkers. Both index the golden columns by the verdict order,
    // which the peak order fixes: the real phase never drops a candidate (asserted).
    // =======================================================================
    always @(posedge clk) begin
        if (rst_n && (phase == PH_REAL) && s_tvalid && o_peak_valid) begin
            if (r_vr < n_peak) begin
                if (o_peak_idx !== mem_pos[r_vr])                  r_mism_idx   <= r_mism_idx + 1;
                if (m_sample_idx !== mem_pos[r_vr])                r_mism_alive <= r_mism_alive + 1;
                if (o_dalam_pita !== mem_flag[r_vr][F_INBAND])     r_mism_pita  <= r_mism_pita + 1;
                if (o_reject !== mem_flag[r_vr][F_TREJ])           r_mism_rej   <= r_mism_rej + 1;
                if (m_tdata !== mem_kem[r_vr][W_TW-1:0])           r_mism_kem   <= r_mism_kem + 1;
                if (m_tuser !== mem_pos[r_vr][7:0])                r_mism_user  <= r_mism_user + 1;
                if (m_tlast !== (mem_pos[r_vr] == (limit_n - 1)))  r_mism_last  <= r_mism_last + 1;
                if (!m_tvalid || !d_valid)                         r_mism_alive <= r_mism_alive + 1;
                if (d_tw !== m_tdata)                              r_mism_alive <= r_mism_alive + 1;
                if (mem_kem[r_vr][W_TW-1])                         r_high_slope <= r_high_slope + 1;
                if (mem_flag[r_vr][F_INBAND]) r_inband_seen <= r_inband_seen + 1;
                if (mem_flag[r_vr][F_TREJ])   r_rej_seen    <= r_rej_seen + 1;

                // (b) the float route on the same pair, from the slope the DUT reported
                if (o_reject !== f_float_reject(mem_flag[r_vr][F_INBAND] != 0, W_DER'(m_tdata),
                                                mem_kq[r_vr][W_DER-1:0]))
                    r_mism_float <= r_mism_float + 1;

                // (c) the forbidden shift route, counted, never used
                if ((o_reject != 0) !== f_shift_reject(mem_flag[r_vr][F_INBAND] != 0, W_DER'(m_tdata),
                                                       mem_kq[r_vr][W_DER-1:0]))
                    r_diff_shift <= r_diff_shift + 1;
            end
            r_vr <= r_vr + 1;
        end
        if (rst_n && (phase == PH_REAL) && o_overrun) r_ovr <= r_ovr + 1;
        if (rst_n && (phase == PH_REAL) && m_overflow) r_ovf <= r_ovf + 1;

        if (rst_n && (phase == PH_SINT) && s_tvalid && o_peak_valid) begin
            if (s_vr < n_spos) begin
                if (o_peak_idx !== mem_spos[s_vr])        s_mism_idx <= s_mism_idx + 1;
                if (m_tdata !== mem_skem[s_vr][W_TW-1:0]) s_mism_kem <= s_mism_kem + 1;
            end
            s_vr <= s_vr + 1;
        end
    end

    // =======================================================================
    // PH_STAIR checker: the pair grid and the edge cases, through the block.
    // =======================================================================
    always @(posedge clk) begin
        if (rst_n && (phase == PH_STAIR) && s_tvalid && o_peak_valid) begin
            if (g_vr < n_stair) begin
                if (o_peak_idx !== (32'(g_vr * BLOCK) + 32'(HALF_WIN))) g_mism_idx  <= g_mism_idx + 1;
                if (o_dalam_pita !== mem_sflg[g_vr][S_INBAND])          g_mism_pita <= g_mism_pita + 1;
                if (o_reject !== mem_sflg[g_vr][S_REJECT])              g_mism_rej  <= g_mism_rej + 1;

                if (m_tdata !== f_report(mem_sder[g_vr][W_DER-1:0]))
                    g_mism_kem <= g_mism_kem + 1;

                // the float route on the same pair
                if (o_reject !== f_float_reject(mem_sflg[g_vr][S_INBAND] != 0,
                                                f_kem_true(mem_sder[g_vr][W_DER-1:0]),
                                                mem_ssp[g_vr][W_DER-1:0]))
                    g_mism_float <= g_mism_float + 1;

                if (mem_sflg[g_vr][S_GRID]) begin
                    if ((o_reject != 0) !== f_shift_reject(mem_sflg[g_vr][S_INBAND] != 0,
                                                           f_kem_true(mem_sder[g_vr][W_DER-1:0]),
                                                           mem_ssp[g_vr][W_DER-1:0]))
                        g_diff_shift <= g_diff_shift + 1;
                    if (o_reject !== f_float_reject(mem_sflg[g_vr][S_INBAND] != 0,
                                                   f_kem_true(mem_sder[g_vr][W_DER-1:0]),
                                                   mem_ssp[g_vr][W_DER-1:0]))
                        g_diff_float <= g_diff_float + 1;
                end

                // the saturation flag: 0 on every row before the rail row, 1 from it on
                if (f_rail(mem_sder[g_vr][W_DER-1:0])) begin
                    g_rail_seen <= g_rail_seen + 1;
                    if (!m_overflow) g_mism_ovf <= g_mism_ovf + 1;
                end else if (m_overflow) begin
                    g_mism_ovf <= g_mism_ovf + 1;
                end
            end
            g_vr <= g_vr + 1;
        end
    end

    // =======================================================================
    // PH_OVR checker: three served peaks, the fourth refused with o_overrun set.
    // =======================================================================
    always @(posedge clk) begin
        if (rst_n && (phase == PH_OVR) && s_tvalid && o_peak_valid) begin
            if (o_vr == 0) begin
                if (o_peak_idx !== 32'd0)  o_mism_idx <= o_mism_idx + 1;
                if (o_overrun)             o_ovr_early <= o_ovr_early + 1;
            end else if (o_vr == 1) begin
                if (o_peak_idx !== 32'd10) o_mism_idx <= o_mism_idx + 1;
                if (o_overrun)             o_ovr_early <= o_ovr_early + 1;
            end else if (o_vr == 2) begin
                if (o_peak_idx !== 32'd20) o_mism_idx <= o_mism_idx + 1;
            end else begin
                o_mism_idx <= o_mism_idx + 1;   // only three candidates may be served
            end
            if (m_tdata !== 23'd1000) o_mism_kem <= o_mism_kem + 1;
            o_vr <= o_vr + 1;
        end
        if (rst_n && (phase == PH_OVR) && o_overrun) o_ovr_late <= o_ovr_late + 1;
    end

    // =======================================================================
    // Sequencer: load the vectors, walk the phases, print the summary, fail loudly.
    // =======================================================================
    initial begin
        limit_n = N_FRAMES;
        if (!$value$plusargs("LIMIT=%d", limit_n)) limit_n = N_FRAMES;
        if (!$value$plusargs("VECTOR=%s", vdir))
            $fatal(1, "tb_gelombang_t: FAIL no +VECTOR (want the Fase 7 vector directory)");
        if ((limit_n > N_FRAMES) || (limit_n < 100))
            $fatal(1, "tb_gelombang_t: FAIL limit out of range (%0d), want 100 .. %0d",
                   limit_n, N_FRAMES);

        $sformat(fpath, "%0s/04015.turunan.hex",          vdir); $readmemh(fpath, mem_der);
        $sformat(fpath, "%0s/04015.fase7.pos.hex",        vdir); $readmemh(fpath, mem_pos);
        $sformat(fpath, "%0s/04015.fase7.kem.hex",        vdir); $readmemh(fpath, mem_kem);
        $sformat(fpath, "%0s/04015.fase7.delta.hex",      vdir); $readmemh(fpath, mem_del);
        $sformat(fpath, "%0s/04015.fase7.kemqrs.hex",     vdir); $readmemh(fpath, mem_kq);
        $sformat(fpath, "%0s/04015.fase7.flag.hex",       vdir); $readmemh(fpath, mem_flag);
        $sformat(fpath, "%0s/04015.sintetis.turunan.hex", vdir); $readmemh(fpath, mem_sin);
        $sformat(fpath, "%0s/04015.sintetis.pos.hex",     vdir); $readmemh(fpath, mem_spos);
        $sformat(fpath, "%0s/04015.sintetis.kem.hex",     vdir); $readmemh(fpath, mem_skem);
        $sformat(fpath, "%0s/04015.stair.der.hex",        vdir); $readmemh(fpath, mem_sder);
        $sformat(fpath, "%0s/04015.stair.sp.hex",         vdir); $readmemh(fpath, mem_ssp);
        $sformat(fpath, "%0s/04015.stair.delta.hex",      vdir); $readmemh(fpath, mem_sdel);
        $sformat(fpath, "%0s/04015.stair.flag.hex",       vdir); $readmemh(fpath, mem_sflg);
        $sformat(fpath, "%0s/04015.fase7.counts.hex",     vdir); $readmemh(fpath, mem_cnt);

        n_peak  = mem_cnt[C_PEAKS];
        n_spos  = mem_cnt[C_SINTPOS];
        n_stair = mem_cnt[C_STAIR];
        if ((n_peak < 1) || (n_peak > N_PEAK) ||
            (n_spos < 1) || (n_spos > N_SPOS) ||
            (n_stair < 1) || (n_stair > N_STAIR))
            $fatal(1, "tb_gelombang_t: FAIL vector counts out of range (%0d, %0d, %0d)",
                   n_peak, n_spos, n_stair);

        $display("tb_gelombang_t: vectors = %0s", vdir);
        $display("tb_gelombang_t: limit   = %0d of %0d frames", limit_n, mem_cnt[C_FRAMES]);
        $display("tb_gelombang_t: peaks   = %0d, sint words = %0d, stair rows = %0d",
                 n_peak, mem_cnt[C_SINTW], n_stair);

        phase           = PH_RST;
        rst_n           = 1'b0;
        rst_cnt         = 0;
        s_tdata         = {W_DER{1'b0}};
        s_tvalid        = 1'b0;
        s_tlast         = 1'b0;
        s_tuser         = 8'd0;
        s_sample_idx    = 32'd0;
        i_rule_enable   = 1'b0;
        i_peak_valid    = 1'b0;
        i_delta         = 32'd0;
        i_delta_valid   = 1'b0;
        i_kem_qrs       = {W_DER{1'b0}};
        i_kem_qrs_valid = 1'b0;
        feed = 0; pk_feed = 0; sint_feed = 0; spos_feed = 0; stair_word = 0;
        cad_q = 0; lat_meas = 0; lat_bad = 0;
        ovr_w_idx = 0;
        acc_idx = 32'd0;

        r_vr = 0; r_exp = 0; r_mism_idx = 0; r_mism_kem = 0; r_mism_pita = 0;
        r_mism_rej = 0; r_mism_float = 0; r_diff_shift = 0; r_high_slope = 0;
        r_mism_user = 0; r_mism_last = 0; r_mism_alive = 0;
        r_ovr = 0; r_ovf = 0; r_inband_seen = 0; r_rej_seen = 0; r_min_spacing = 0;
        r_words = 0; r_pulses = 0;
        s_vr = 0; s_exp = 0; s_mism_idx = 0; s_mism_kem = 0;
        g_vr = 0; g_mism_idx = 0; g_mism_kem = 0; g_mism_pita = 0; g_mism_rej = 0;
        g_mism_float = 0; g_diff_shift = 0; g_diff_float = 0; g_mism_ovf = 0;
        g_rail_seen = 0;
        o_vr = 0; o_mism_idx = 0; o_mism_kem = 0; o_ovr_early = 0; o_ovr_late = 0;

        // expected verdict counts, from the vector columns: a peak whose verdict word would
        // fall past the end of its stream gets no verdict, and none is invented for it
        for (i = 0; i < n_peak; i = i + 1)
            if ((mem_pos[i] + LAT_ACC) <= (limit_n - 1)) r_exp = r_exp + 1;
        for (i = 0; i < n_spos; i = i + 1)
            if ((mem_spos[i] + LAT_ACC) <= (N_SINT - 1)) s_exp = s_exp + 1;

        // the minimum peak spacing of the frozen fixture, printed as evidence for the
        // documented spacing contract of the block (SCAN_CYC = 10 accepted words)
        r_min_spacing = limit_n;
        for (i = 1; i < n_peak; i = i + 1)
            if ((mem_pos[i] - mem_pos[i-1]) < r_min_spacing)
                r_min_spacing = mem_pos[i] - mem_pos[i-1];

        $display("tb_gelombang_t: fixture minimum peak spacing = %0d samples", r_min_spacing);

        ph_last = PH_RST;
        while (phase != PH_DONE) begin
            @(posedge clk);
            if (phase !== ph_last) begin
                ph_last = phase;
                if (phase == PH_REAL)  $display("tb_gelombang_t: PH_REAL starts, %0d of %0d peaks expected to report", r_exp, n_peak);
                if (phase == PH_SINT)  $display("tb_gelombang_t: PH_SINT starts, %0d sampled positions expected", s_exp);
                if (phase == PH_STAIR) $display("tb_gelombang_t: PH_STAIR starts, %0d rows expected", n_stair);
                if (phase == PH_OVR)   $display("tb_gelombang_t: PH_OVR starts, 3 peaks expected to be served");
            end
        end
        repeat (8) @(posedge clk);

        $display("tb_gelombang_t: PH_REAL words presented   = %0d", r_words);
        $display("tb_gelombang_t: PH_REAL peak pulses       = %0d of %0d", r_pulses, n_peak);
        $display("tb_gelombang_t: PH_REAL verdicts          = %0d of %0d expected", r_vr, r_exp);
        $display("tb_gelombang_t: PH_REAL in band verdicts  = %0d", r_inband_seen);
        $display("tb_gelombang_t: PH_REAL rejected verdicts = %0d", r_rej_seen);
        $display("tb_gelombang_t: PH_REAL slopes with bit %0d set = %0d", W_TW-1, r_high_slope);
        $display("tb_gelombang_t: PH_REAL overlay mismatches = %0d",
                 r_mism_idx + r_mism_alive + r_mism_user + r_mism_last);
        $display("tb_gelombang_t: PH_REAL kem mismatches    = %0d", r_mism_kem);
        $display("tb_gelombang_t: PH_REAL dalam_pita mismatches = %0d", r_mism_pita);
        $display("tb_gelombang_t: PH_REAL reject mismatches = %0d", r_mism_rej);
        $display("tb_gelombang_t: PH_REAL cross vs float route differences = %0d", r_mism_float);
        $display("tb_gelombang_t: PH_REAL cross vs forbidden shift differences = %0d", r_diff_shift);
        $display("tb_gelombang_t: PH_REAL overflow pulses   = %0d", r_ovf);
        $display("tb_gelombang_t: PH_REAL overrun cycles    = %0d", r_ovr);
        $display("tb_gelombang_t: PH_SINT verdicts          = %0d of %0d expected", s_vr, s_exp);
        $display("tb_gelombang_t: PH_SINT index mismatches  = %0d", s_mism_idx);
        $display("tb_gelombang_t: PH_SINT kem mismatches    = %0d", s_mism_kem);
        $display("tb_gelombang_t: PH_STAIR verdicts         = %0d of %0d expected", g_vr, n_stair);
        $display("tb_gelombang_t: PH_STAIR index mismatches = %0d", g_mism_idx);
        $display("tb_gelombang_t: PH_STAIR kem mismatches   = %0d", g_mism_kem);
        $display("tb_gelombang_t: PH_STAIR dalam_pita mismatches = %0d", g_mism_pita);
        $display("tb_gelombang_t: PH_STAIR reject mismatches = %0d", g_mism_rej);
        $display("tb_gelombang_t: PH_STAIR cross vs float differences = %0d of %0d rows",
                 g_mism_float, n_stair);
        $display("tb_gelombang_t: PH_STAIR cross vs forbidden shift differences = %0d, vector expects %0d",
                 g_diff_shift, mem_cnt[C_GRIDSIM]);
        $display("tb_gelombang_t: PH_STAIR grid rows cross vs float differences = %0d, vector expects %0d",
                 g_diff_float, mem_cnt[C_FLOATSIM]);
        $display("tb_gelombang_t: PH_STAIR saturation flag mismatches = %0d (rail rows = %0d)",
                 g_mism_ovf, g_rail_seen);
        $display("tb_gelombang_t: PH_OVR verdicts           = %0d of 3 expected", o_vr);
        $display("tb_gelombang_t: PH_OVR index mismatches   = %0d", o_mism_idx);
        $display("tb_gelombang_t: PH_OVR kem mismatches     = %0d", o_mism_kem);
        $display("tb_gelombang_t: PH_OVR overrun before the tight pair = %0d", o_ovr_early);
        $display("tb_gelombang_t: PH_OVR overrun seen after = %0d", o_ovr_late);
        $display("tb_gelombang_t: measured latency = %0d accepted words, expected %0d, bad = %0d",
                 lat_meas, LAT_ACC, lat_bad);

        // g_diff_shift and g_diff_float are EVIDENCE counters, not mismatches: the crossing
        // form and the forbidden shift form differ by construction, so the number of rows
        // where they differ is compared against the vector's own count instead of against 0
        mism_total = r_mism_idx + r_mism_alive + r_mism_user + r_mism_last + r_mism_kem +
                     r_mism_pita + r_mism_rej + r_mism_float + r_diff_shift + lat_bad +
                     s_mism_idx + s_mism_kem + g_mism_idx + g_mism_kem + g_mism_pita +
                     g_mism_rej + g_mism_float + g_mism_ovf +
                     o_mism_idx + o_mism_kem;
        $display("tb_gelombang_t: words compared = %0d (real %0d + sint %0d + stair %0d + ovr %0d)",
                 r_vr + s_vr + g_vr + o_vr, r_vr, s_vr, g_vr, o_vr);
        $display("tb_gelombang_t: mismatches = %0d out of %0d",
                 mism_total, r_vr + s_vr + g_vr + o_vr);

        if ((mism_total == 0) &&
            (r_vr == r_exp) && (s_vr == s_exp) && (g_vr == n_stair) && (o_vr == 3) &&
            (r_vr > 0) && (s_vr > 0) && (g_vr > 0) &&
            (lat_meas == LAT_ACC) && (lat_bad == 0) &&
            (g_diff_shift == mem_cnt[C_GRIDSIM]) &&
            (g_diff_float == mem_cnt[C_FLOATSIM]) &&
            (r_ovf == 0) && (r_ovr == 0) && (g_rail_seen > 0) &&
            (o_ovr_early == 0) && (o_ovr_late > 0)) begin
            $display("tb_gelombang_t: PASS");
        end else begin
            $display("tb_gelombang_t: FAIL");
            $fatal(1, "tb_gelombang_t: gate violation, see the counters above");
        end
        $finish;
    end

endmodule

`default_nettype wire
