// ---------------------------------------------------------------------------
// afib_lite_top.sv -- the whole chain, the register map boundary and the introspection
// mux. Contract profile: top level (I1).
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). This file exposes every row of that table. Two deliberate deviations,
// both reported rather than hidden:
//   1 the row o_dbg_val says "together with o_dbg_valid", but the 43 row table has no
//     o_dbg_valid row. No extra port is added here; the mismatch is sent to the owner.
//   2 the individual d_<node> taps are NOT brought out as ports at this level. Plan 13.3
//     question 6 recommends one introspection mux in afib_lite_top.sv with the taps kept
//     off the bitstream port list, so the taps reach the outside only through o_dbg_val
//     selected by i_dbg_sel.
//
// The AXI4-Lite host bus is also exposed here and is NOT a row of the 43 row table: the
// table is the sample, decision and status contract, while the bus is the host boundary
// (plan 8.5 puts the register map behind AXI4-Lite on pl_clk0, the same single clock, so
// the PL has no clock domain crossing).
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 section 2.2): see
// group 1 of the package. The chain widths in order are
//   W_IN 16 -> W_LP 22 -> W_HP 26 -> W_DER 24 -> W_SQ 30 -> W_WIN 33 -> W_THR 30,
//   with W_TW 23 for the T-wave slope, W_RR_MS 16 / W_RR_SMP 15 for the RR series,
//   W_F_RMSSD 18 / W_F_RATIO 17 / W_F_ENT 15 / W_F_MEANQ 27 for the features and
//   W_CONF 16 for the confidence. The last datapath word, m_tdata, is the window node at
//   W_WIN 33, the widest sample word in the chain.
// Saturation points: each stage owns its own bound and its own sticky m_overflow, and all
//   of them are OR-ed into STATUS.b1 here. The clamps are CLAMP_COUNT 2047 and
//   CLAMP_WORD 32752 at the input, the threshold uses THRESH_SCALE 256, RR uses
//   RR_LONG_MS 3000 and RR_MAX_MS 65535, and the search back uses SEARCH_BACK_DEPTH 128.
// Rounding rule: no arithmetic happens at this level. The three rules live in the stages:
//   RND_TIES_EVEN at the quantiser, RND_TRUNC_ZERO at the derivative, RND_FLOOR
//   everywhere else.
// Model lines this file mirrors: it wires the stages, so the model lines are the union of
//   the stage headers: rantai.py:49-51, :156-165, :173-189, :197-211, :221-233, :240-250,
//   :259-280, :313-341, :375-440, :443-559, :569-600, :610-715, :754-861, :983-1002.
//
// Fixed latency per stage, no back pressure inside (D1). The whole chain uses 97 cycles
// against 400000 cycles available per sample, so s_ready is the enable and nothing stalls.
//
// Fase 1 status: PLACEHOLDER. Every stage loads its input into its output register with a
// fixed latency, so lint and a smoke simulation pass and the whole chain elaborates. No
// real arithmetic exists yet and no parity claim is made.
// House style: wire and reg only (D10), one clock, synchronous active low reset.
// ---------------------------------------------------------------------------
`default_nettype none

module afib_lite_top #(
    parameter int unsigned W_IN       = afib_lite_pkg::W_IN,
    parameter int unsigned W_LP       = afib_lite_pkg::W_LP,
    parameter int unsigned W_HP       = afib_lite_pkg::W_HP,
    parameter int unsigned W_DER      = afib_lite_pkg::W_DER,
    parameter int unsigned W_SQ       = afib_lite_pkg::W_SQ,
    parameter int unsigned W_WIN      = afib_lite_pkg::W_WIN,
    parameter int unsigned W_THR      = afib_lite_pkg::W_THR,
    parameter int unsigned W_TW       = afib_lite_pkg::W_TW,
    parameter int unsigned W_RR_MS    = afib_lite_pkg::W_RR_MS,
    parameter int unsigned W_RR_SMP   = afib_lite_pkg::W_RR_SMP,
    parameter int unsigned W_F_RATIO  = afib_lite_pkg::W_F_RATIO,
    parameter int unsigned W_F_ENT    = afib_lite_pkg::W_F_ENT,
    parameter int unsigned W_F_MEANQ  = afib_lite_pkg::W_F_MEANQ,
    parameter int unsigned W_F_RMSSD  = afib_lite_pkg::W_F_RMSSD,
    parameter int unsigned W_CONF     = afib_lite_pkg::W_CONF,
    parameter int unsigned W_IDX      = afib_lite_pkg::W_IDX,
    parameter int unsigned W_TUSER    = afib_lite_pkg::W_TUSER,
    parameter int unsigned W_EVKIND   = afib_lite_pkg::W_EVKIND,
    parameter int unsigned W_RATE_DIV = afib_lite_pkg::W_RATE_DIV
) (
    input  wire                     clk_i,
    input  wire                     rst_ni,

    // sample group
    input  wire [W_IN-1:0]          s_tdata,
    input  wire                     s_tvalid,
    output wire                     s_ready,
    input  wire                     s_tlast,
    input  wire [W_TUSER-1:0]       s_tuser,
    input  wire [W_IDX-1:0]         s_sample_idx,
    output wire [W_WIN-1:0]         m_tdata,
    output wire                     m_tvalid,
    output wire                     m_overflow,
    output wire                     m_tlast,
    output wire [W_TUSER-1:0]       m_tuser,
    output wire [W_IDX-1:0]         m_sample_idx,

    // event group
    output wire                     m_ev_valid,
    output wire [W_EVKIND-1:0]      m_ev_kind,
    output wire [W_IDX-1:0]         m_ev_idx,
    output wire [31:0]              m_ev_val,

    // introspection group: validity plus the mux of plan 13.3 question 6
    output wire                     d_valid,
    output wire [31:0]              o_dbg_val,
    input  wire [7:0]               i_dbg_sel,

    // decision group
    output wire                     m_dvalid,
    output wire [1:0]               m_class,
    output wire [W_CONF-1:0]        m_conf,
    output wire [W_IDX-1:0]         m_win_idx,
    output wire [W_RR_MS-1:0]       m_rr_last,
    output wire [1:0]               m_rr_mark,

    // status group
    output wire [31:0]              o_sample_idx,
    output wire [31:0]              o_beat_count,
    output wire [31:0]              o_gap_count,
    output wire [31:0]              o_clamp_count,
    output wire [31:0]              o_window_count,
    output wire [31:0]              o_rr_long_count,
    output wire [4:0]               o_irq,

    // configuration group
    input  wire [W_RATE_DIV-1:0]    i_rate_div,
    input  wire                     i_enable,
    input  wire                     i_clear_counters,
    input  wire [15:0]              i_ratio_thresh,
    input  wire [15:0]              i_entropy_thresh,
    input  wire [4:0]               i_arm_select,
    input  wire [7:0]               i_window_step,
    input  wire [7:0]               i_window_beats,

    // AXI4-Lite host bus, not a row of the 43 row table
    input  wire [7:0]               s_axi_awaddr,
    input  wire                     s_axi_awvalid,
    output wire                     s_axi_awready,
    input  wire [31:0]              s_axi_wdata,
    input  wire [3:0]               s_axi_wstrb,
    input  wire                     s_axi_wvalid,
    output wire                     s_axi_wready,
    output wire [1:0]               s_axi_bresp,
    output wire                     s_axi_bvalid,
    input  wire                     s_axi_bready,
    input  wire [7:0]               s_axi_araddr,
    input  wire                     s_axi_arvalid,
    output wire                     s_axi_arready,
    output wire [31:0]              s_axi_rdata,
    output wire [1:0]               s_axi_rresp,
    output wire                     s_axi_rvalid,
    input  wire                     s_axi_rready
);

    // ---------------------------------------------------------------- chain wires
    wire [W_IN-1:0]   a_word;
    wire              a_valid, a_last, a_ovf;
    wire [W_TUSER-1:0] a_user;
    wire [W_IDX-1:0]  a_idx;
    wire              a_ev_valid;
    wire [W_EVKIND-1:0] a_ev_kind;
    wire [W_IDX-1:0]  a_ev_idx;
    wire [31:0]       a_ev_val;
    wire              a_dvalid;
    wire [W_IN-1:0]   a_dword;

    wire [W_HP-1:0]   b_word;
    wire              b_valid, b_last, b_ovf;
    wire [W_TUSER-1:0] b_user;
    wire [W_IDX-1:0]  b_idx;
    wire              b_dvalid;
    wire [W_LP-1:0]   b_lp;
    wire [W_HP-1:0]   b_hp;

    wire [W_DER-1:0]  c_word;
    wire              c_valid, c_last, c_ovf;
    wire [W_TUSER-1:0] c_user;
    wire [W_IDX-1:0]  c_idx;
    wire              c_dvalid;
    wire [W_DER-1:0]  c_der;

    wire [W_SQ-1:0]   d_word;
    wire              d_valid_w, d_last, d_ovf;
    wire [W_TUSER-1:0] d_user;
    wire [W_IDX-1:0]  d_idx;
    wire              d_sq_valid;
    wire [W_SQ-1:0]   d_sq;

    wire [W_WIN-1:0]  e_word;
    wire              e_valid, e_last, e_ovf;
    wire [W_TUSER-1:0] e_user;
    wire [W_IDX-1:0]  e_idx;
    wire              e_dvalid;
    wire [W_WIN-1:0]  e_win;

    wire [W_WIN-1:0]  p_word;
    wire              p_valid, p_last, p_ovf;
    wire [W_TUSER-1:0] p_user;
    wire [W_IDX-1:0]  p_idx;
    wire              p_ev_valid;
    wire [W_EVKIND-1:0] p_ev_kind;
    wire [W_IDX-1:0]  p_ev_idx;
    wire [31:0]       p_ev_val;
    wire              p_dvalid;
    wire [W_THR-1:0]  p_thr;
    wire [W_THR-1:0]  p_pk;

    wire [W_TW-1:0]   tw_word;
    wire              tw_valid, tw_ovf;
    wire              tw_last;
    wire [W_TUSER-1:0] tw_user;
    wire [W_IDX-1:0]  tw_idx;
    wire [W_TW-1:0]   tw_dtw;
    wire              tw_reject;
    wire              tw_dvalid;

    wire [W_RR_MS-1:0] rr_ms;
    wire [1:0]         rr_mark;
    wire              rr_ev_valid;
    wire [W_EVKIND-1:0] rr_ev_kind;
    wire [W_IDX-1:0]  rr_ev_idx;
    wire [31:0]       rr_ev_val;
    wire              rr_dvalid;
    wire [W_RR_MS-1:0] rr_d_ms;
    wire [W_RR_SMP-1:0] rr_d_smp;

    wire              f_dvalid;
    wire [W_F_RMSSD-1:0] f_rmssd;
    wire [W_F_RATIO-1:0] f_ratio;
    wire [W_F_ENT-1:0]   f_ent;
    wire [W_F_MEANQ-1:0] f_meanq;
    wire              f_ev_valid;
    wire [W_EVKIND-1:0] f_ev_kind;
    wire [W_IDX-1:0]  f_ev_idx;
    wire [31:0]       f_ev_val;

    wire              cl_dvalid;
    wire [1:0]        cl_class;
    wire [W_CONF-1:0] cl_conf;
    wire [W_IDX-1:0]  cl_win_idx;
    wire [1:0]        cl_d_class;
    wire [W_CONF-1:0] cl_d_conf;
    wire [31:0]       cl_window_count;

    // register file outputs
    wire              r_enable, r_clear;
    wire [W_RATE_DIV-1:0] r_rate_div;
    wire [15:0]       r_ratio_thresh, r_entropy_thresh;
    wire [4:0]        r_arm_select;
    wire [7:0]        r_window_step, r_window_beats;

    // ---------------------------------------------------------------- configuration
    // Bring-up placeholder, stated plainly: a direct configuration port that is not zero
    // wins over the register file, and zero means "not driven, take the register". Fase 11
    // inverts this priority once the host bus becomes the master.
    wire [W_RATE_DIV-1:0] cfg_rate_div      = (i_rate_div      != {W_RATE_DIV{1'b0}}) ? i_rate_div      : r_rate_div;
    wire [15:0]           cfg_ratio_thresh  = (i_ratio_thresh  != 16'd0) ? i_ratio_thresh  : r_ratio_thresh;
    wire [15:0]           cfg_entropy_thresh= (i_entropy_thresh!= 16'd0) ? i_entropy_thresh: r_entropy_thresh;
    wire [4:0]            cfg_arm_select    = (i_arm_select    != 5'd0)  ? i_arm_select    : r_arm_select;
    wire [7:0]            cfg_window_step   = (i_window_step   != 8'd0)  ? i_window_step   : r_window_step;
    wire [7:0]            cfg_window_beats  = (i_window_beats  != 8'd0)  ? i_window_beats  : r_window_beats;
    wire                  cfg_enable        = i_enable | r_enable;
    wire                  cfg_clear         = i_clear_counters | r_clear;

    // ---------------------------------------------------------------- sticky flags
    wire any_ovf = a_ovf | b_ovf | c_ovf | d_ovf | e_ovf | p_ovf | tw_ovf;

    reg gap_seen_q;
    reg clamp_seen_q;
    reg fifo_ovf_seen_q;
    reg rr_long_seen_q;
    reg win_done_seen_q;

    wire gap_now   = a_ev_valid & (a_ev_kind == afib_lite_pkg::EV_GAP);
    wire clamp_now = (o_clamp_count != 32'd0);
    wire win_now   = cl_dvalid;
    wire long_now  = rr_ev_valid & (rr_ev_kind == afib_lite_pkg::EV_RR) &
                     (rr_ev_val[W_RR_MS-1:0] > afib_lite_pkg::RR_LONG_MS);

    always @(posedge clk_i) begin
        if (!rst_ni) begin
            gap_seen_q      <= 1'b0;
            clamp_seen_q    <= 1'b0;
            fifo_ovf_seen_q <= 1'b0;
            rr_long_seen_q  <= 1'b0;
            win_done_seen_q <= 1'b0;
        end else if (cfg_clear) begin
            gap_seen_q      <= 1'b0;
            clamp_seen_q    <= 1'b0;
            fifo_ovf_seen_q <= 1'b0;
            rr_long_seen_q  <= 1'b0;
            win_done_seen_q <= 1'b0;
        end else begin
            gap_seen_q      <= gap_seen_q      | gap_now;
            clamp_seen_q    <= clamp_seen_q    | clamp_now;
            fifo_ovf_seen_q <= fifo_ovf_seen_q | any_ovf;
            rr_long_seen_q  <= rr_long_seen_q  | long_now;
            win_done_seen_q <= win_done_seen_q | win_now;
        end
    end

    // o_irq bit order follows the table row: b0 window done, b1 gap, b2 clamp,
    // b3 FIFO overflow, b4 long interval.
    assign o_irq = {rr_long_seen_q, fifo_ovf_seen_q, clamp_seen_q, gap_seen_q, win_done_seen_q};

    // ---------------------------------------------------------------- status word
    // Every tap and every stage valid flag reaches the outside, either through the
    // introspection mux or through this aggregate, because Verilator treats an unread
    // signal as a failure. taps_active is the placeholder "the chain moved" indicator.
    wire taps_active = |{a_dvalid, b_dvalid, c_dvalid, d_sq_valid, e_dvalid,
                         tw_valid, tw_last, tw_dvalid, rr_dvalid, f_dvalid, cl_dvalid};

    wire warmup_done = 1'b0;   // Fase 5 raises this after 23 to 32 beats (doc 36 5.1)
    wire running     = cfg_enable & (o_sample_idx != 32'd0);
    wire alive       = taps_active;

    wire [31:0] status_w = {23'd0, p_ovf, running, warmup_done,
                            rr_long_seen_q, clamp_seen_q, gap_seen_q, alive,
                            fifo_ovf_seen_q, 1'b1};

    // ---------------------------------------------------------------- introspection mux
    // One mux, per plan 13.3 question 6, so no d_ tap becomes a port on the bitstream.
    reg [31:0] o_dbg_val_w;

    always @(*) begin
        case (i_dbg_sel)
            8'd0:    o_dbg_val_w = {{(32-W_IN){1'b0}}, a_dword};
            8'd1:    o_dbg_val_w = {{(32-W_LP){b_lp[W_LP-1]}}, b_lp};
            8'd2:    o_dbg_val_w = {{(32-W_HP){b_hp[W_HP-1]}}, b_hp};
            8'd3:    o_dbg_val_w = {{(32-W_DER){c_der[W_DER-1]}}, c_der};
            8'd4:    o_dbg_val_w = {{(32-W_SQ){1'b0}}, d_sq};
            8'd5:    o_dbg_val_w = e_win[W_WIN-1] ? e_win[W_WIN-1:1] : e_win[31:0];
            8'd6:    o_dbg_val_w = {{(32-W_THR){p_thr[W_THR-1]}}, p_thr};
            8'd7:    o_dbg_val_w = {{(32-W_THR){p_pk[W_THR-1]}}, p_pk};
            8'd8:    o_dbg_val_w = {{(32-W_TW){tw_dtw[W_TW-1]}}, tw_dtw};
            8'd9:    o_dbg_val_w = {{(32-W_RR_MS){1'b0}}, rr_d_ms};
            8'd10:   o_dbg_val_w = {{(32-W_RR_SMP){1'b0}}, rr_d_smp};
            8'd11:   o_dbg_val_w = {{(32-W_F_RMSSD){1'b0}}, f_rmssd};
            8'd12:   o_dbg_val_w = {{(32-W_F_RATIO){1'b0}}, f_ratio};
            8'd13:   o_dbg_val_w = {{(32-W_F_ENT){1'b0}}, f_ent};
            8'd14:   o_dbg_val_w = {{(32-W_F_MEANQ){1'b0}}, f_meanq};
            8'd15:   o_dbg_val_w = {30'd0, cl_d_class};
            8'd16:   o_dbg_val_w = {{(32-W_TW){tw_word[W_TW-1]}}, tw_word};
            8'd17:   o_dbg_val_w = {31'd0, tw_valid};
            8'd18:   o_dbg_val_w = rr_ev_idx;   // 32 bit, no extension needed
            8'd19:   o_dbg_val_w = f_ev_val;    // 32 bit, no extension needed
            8'd20:   o_dbg_val_w = {{(32-W_CONF){1'b0}}, cl_d_conf};
            8'd21:   o_dbg_val_w = a_ev_val;    // 32 bit, no extension needed
            8'd22:   o_dbg_val_w = {31'd0, taps_active};
            8'd23:   o_dbg_val_w = s_sample_idx;  // the caller must read this contract input
            8'd24:   o_dbg_val_w = a_ev_idx;
            8'd25:   o_dbg_val_w = {{(32-W_TUSER){1'b0}}, tw_user};
            8'd26:   o_dbg_val_w = tw_idx;
            8'd27:   o_dbg_val_w = rr_ev_val;
            default: o_dbg_val_w = {29'd0, tw_reject, p_dvalid, cl_dvalid};
        endcase
    end

    assign o_dbg_val = o_dbg_val_w;

    // ---------------------------------------------------------------- chain instances
    acq_frontend u_acq_frontend (
        .clk_i, .rst_ni,
        .s_tdata(s_tdata), .s_tvalid(s_tvalid), .s_tlast(s_tlast), .s_tuser(s_tuser),
        .i_enable(cfg_enable), .i_rate_div(cfg_rate_div), .i_clear_counters(cfg_clear),
        .m_tdata(a_word), .m_tvalid(a_valid), .m_overflow(a_ovf), .m_tlast(a_last),
        .m_tuser(a_user), .m_sample_idx(a_idx),
        .m_ev_valid(a_ev_valid), .m_ev_kind(a_ev_kind), .m_ev_idx(a_ev_idx), .m_ev_val(a_ev_val),
        .d_valid(a_dvalid), .d_word(a_dword),
        .o_sample_idx(o_sample_idx), .o_gap_count(o_gap_count), .o_clamp_count(o_clamp_count)
    );

    bandpass u_bandpass (
        .clk_i, .rst_ni,
        .s_tdata(a_word), .s_tvalid(a_valid), .s_tlast(a_last), .s_tuser(a_user),
        .s_sample_idx(a_idx),
        .m_tdata(b_word), .m_tvalid(b_valid), .m_overflow(b_ovf), .m_tlast(b_last),
        .m_tuser(b_user), .m_sample_idx(b_idx),
        .d_valid(b_dvalid), .d_lp(b_lp), .d_hp(b_hp)
    );

    derivative u_derivative (
        .clk_i, .rst_ni,
        .s_tdata(b_word), .s_tvalid(b_valid), .s_tlast(b_last), .s_tuser(b_user),
        .s_sample_idx(b_idx),
        .m_tdata(c_word), .m_tvalid(c_valid), .m_overflow(c_ovf), .m_tlast(c_last),
        .m_tuser(c_user), .m_sample_idx(c_idx),
        .d_valid(c_dvalid), .d_der(c_der)
    );

    square u_square (
        .clk_i, .rst_ni,
        .s_tdata(c_word), .s_tvalid(c_valid), .s_tlast(c_last), .s_tuser(c_user),
        .s_sample_idx(c_idx),
        .m_tdata(d_word), .m_tvalid(d_valid_w), .m_overflow(d_ovf), .m_tlast(d_last),
        .m_tuser(d_user), .m_sample_idx(d_idx),
        .d_valid(d_sq_valid), .d_sq(d_sq)
    );

    integrator u_integrator (
        .clk_i, .rst_ni,
        .s_tdata(d_word), .s_tvalid(d_valid_w), .s_tlast(d_last), .s_tuser(d_user),
        .s_sample_idx(d_idx),
        .m_tdata(e_word), .m_tvalid(e_valid), .m_overflow(e_ovf), .m_tlast(e_last),
        .m_tuser(e_user), .m_sample_idx(e_idx),
        .d_valid(e_dvalid), .d_win(e_win)
    );

    peak_detect u_peak_detect (
        .clk_i, .rst_ni,
        .s_tdata(e_word), .s_tvalid(e_valid), .s_tlast(e_last), .s_tuser(e_user),
        .s_sample_idx(e_idx),
        .i_enable(cfg_enable), .i_clear_counters(cfg_clear),
        .m_tdata(p_word), .m_tvalid(p_valid), .m_overflow(p_ovf), .m_tlast(p_last),
        .m_tuser(p_user), .m_sample_idx(p_idx),
        .m_ev_valid(p_ev_valid), .m_ev_kind(p_ev_kind), .m_ev_idx(p_ev_idx), .m_ev_val(p_ev_val),
        .d_valid(p_dvalid), .d_thr(p_thr), .d_pk(p_pk),
        .o_beat_count(o_beat_count)
    );

    t_rule u_t_rule (
        .clk_i, .rst_ni,
        .s_tdata(c_word), .s_tvalid(c_valid), .s_tlast(c_last), .s_tuser(c_user),
        .s_sample_idx(c_idx),
        .i_rule_enable(cfg_arm_select[2]),
        .m_tdata(tw_word), .m_tvalid(tw_valid), .m_overflow(tw_ovf), .m_tlast(tw_last),
        .m_tuser(tw_user), .m_sample_idx(tw_idx),
        .o_reject(tw_reject),
        .d_valid(tw_dvalid), .d_tw(tw_dtw)
    );

    rr_series u_rr_series (
        .clk_i, .rst_ni,
        .i_enable(cfg_enable), .i_clear_counters(cfg_clear),
        .s_tvalid(p_valid), .s_tlast(p_last), .s_tuser(p_user), .s_sample_idx(p_idx),
        .s_ev_valid(p_ev_valid), .s_ev_kind(p_ev_kind), .s_ev_idx(p_ev_idx), .s_ev_val(p_ev_val),
        .m_rr_last(rr_ms), .m_rr_mark(rr_mark),
        .m_ev_valid(rr_ev_valid), .m_ev_kind(rr_ev_kind), .m_ev_idx(rr_ev_idx), .m_ev_val(rr_ev_val),
        .d_valid(rr_dvalid), .d_rr_ms(rr_d_ms), .d_rr_smp(rr_d_smp),
        .o_rr_long_count(o_rr_long_count)
    );

    features u_features (
        .clk_i, .rst_ni,
        .s_valid(p_ev_valid & (p_ev_kind == afib_lite_pkg::EV_QRS)),
        .s_rr_ms(p_ev_val[W_RR_MS-1:0]),
        .s_rr_mark(rr_mark),
        .s_window_idx(p_ev_idx),
        .i_enable(cfg_enable), .i_clear_counters(cfg_clear),
        .i_arm_select(cfg_arm_select),
        .i_window_step(cfg_window_step), .i_window_beats(cfg_window_beats),
        .d_valid(f_dvalid), .d_rmssd(f_rmssd), .d_ratio(f_ratio), .d_ent(f_ent), .d_meanq(f_meanq),
        .m_ev_valid(f_ev_valid), .m_ev_kind(f_ev_kind), .m_ev_idx(f_ev_idx), .m_ev_val(f_ev_val)
    );

    classifier u_classifier (
        .clk_i, .rst_ni,
        .f_valid(f_dvalid), .f_ratio(f_ratio), .f_ent(f_ent), .f_win_idx(f_ev_idx),
        .i_enable(cfg_enable), .i_clear_counters(cfg_clear),
        .i_ratio_thresh(cfg_ratio_thresh), .i_entropy_thresh(cfg_entropy_thresh),
        .i_arm_select(cfg_arm_select),
        .m_dvalid(cl_dvalid), .m_class(cl_class), .m_conf(cl_conf), .m_win_idx(cl_win_idx),
        .d_class(cl_d_class), .d_conf(cl_d_conf),
        .o_window_count(cl_window_count)
    );

    regs_axi u_regs_axi (
        .clk_i, .rst_ni,
        .s_axi_awaddr(s_axi_awaddr), .s_axi_awvalid(s_axi_awvalid), .s_axi_awready(s_axi_awready),
        .s_axi_wdata(s_axi_wdata), .s_axi_wstrb(s_axi_wstrb), .s_axi_wvalid(s_axi_wvalid),
        .s_axi_wready(s_axi_wready), .s_axi_bresp(s_axi_bresp), .s_axi_bvalid(s_axi_bvalid),
        .s_axi_bready(s_axi_bready),
        .s_axi_araddr(s_axi_araddr), .s_axi_arvalid(s_axi_arvalid), .s_axi_arready(s_axi_arready),
        .s_axi_rdata(s_axi_rdata), .s_axi_rresp(s_axi_rresp), .s_axi_rvalid(s_axi_rvalid),
        .s_axi_rready(s_axi_rready),
        .i_status(status_w), .i_irq(o_irq),
        .o_enable(r_enable), .o_clear_counters(r_clear), .o_rate_div(r_rate_div),
        .o_ratio_thresh(r_ratio_thresh), .o_entropy_thresh(r_entropy_thresh),
        .o_arm_select(r_arm_select), .o_window_step(r_window_step), .o_window_beats(r_window_beats)
    );

    // ---------------------------------------------------------------- top level outputs
    assign s_ready      = cfg_enable;   // fixed latency, nothing inside stalls (D1)
    assign m_tdata      = p_word;
    assign m_tvalid     = p_valid;
    assign m_overflow   = any_ovf;
    assign m_tlast      = p_last;
    assign m_tuser      = p_user;
    assign m_sample_idx = p_idx;
    assign m_ev_valid   = f_ev_valid;
    assign m_ev_kind    = f_ev_kind;
    assign m_ev_idx     = f_ev_idx;
    assign m_ev_val     = f_ev_val;
    assign d_valid      = p_dvalid;
    assign m_dvalid     = cl_dvalid;
    assign m_class      = cl_class;
    assign m_conf       = cl_conf;
    assign m_win_idx    = cl_win_idx;
    assign m_rr_last    = rr_ms;
    assign m_rr_mark    = rr_mark;
    assign o_window_count = cl_window_count;

endmodule

`default_nettype wire
