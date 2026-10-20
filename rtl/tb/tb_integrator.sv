// ---------------------------------------------------------------------------
// tb_integrator.sv -- moving window gate for rtl/integrator.sv.
//
// Two phases, one run:
//
// Phase A, the window width gate of plan doc 38 phase 4 and section 4.6 table ("lebar
//   jendela 37.000 dan 38.000 terbaca pada masukan konstan 1.000"): the input is held at
//   the constant 1000 and the moving window must read N_WIN_ALT times that value on an
//   even index and N_WIN times that value on an odd index, that is 37000 and 38000. Both
//   observed numbers are printed, and the phase also checks every warm-up word against
//   (index + 1) times the constant, which is what the model's zero initial condition
//   gives before the first tap leaves the window.
//
// Phase B, the parity gate: d_win and m_tdata match 04015.jendela.hex for every one of
//   the 450000 samples.
//
// Golden data: +VECTOR=<dir> holds the Fase 0 columns, one 32 bit word per line, exactly
//   8 hex digits, no comments, $readmemh compatible:
//     04015.kuadrat.hex    the window input column, 30 bit count squared
//     04015.jendela.hex    the golden window output, 33 bit signed, 32 unsigned
// The jendela column holds 27 words at or above 2**31 (largest 3105281786), so this file
//   declares the memories as unsigned reg [31:0] and never reads a column as a signed 32
//   bit value; the count of those words is printed on every run as evidence. Each output
//   word is compared against the zero extended golden word at the full 33 bit port width,
//   so a stray high bit cannot hide behind a matching low half.
//
// Optional plusargs: +LIMIT=<n> to run a short smoke pass on the parity phase (phase A
//   always runs its 80 constant words), +VECTOR=<dir> required.
//
// No file level timescale, same reason as the other testbenches: the package carries none
//   and Verilator raises TIMESCALEMOD on a file level timescale here.
//
// House style: expected values come from the golden column or from the package constants,
//   never typed here.
// ---------------------------------------------------------------------------
`default_nettype none

module tb_integrator;

    localparam integer N_MAX  = 450000;
    localparam integer CAD    = 8;                          // cycles between samples
    localparam integer CST_N  = 80;                         // constant input words, phase A
    localparam integer CST_IN = 1000;                       // plan 1.3: masukan konstan 1.000
    localparam integer N_A    = afib_lite_pkg::N_WIN_ALT;    // 37, even index window
    localparam integer N_B    = afib_lite_pkg::N_WIN;        // 38, odd index window

    localparam [2:0] PH_RST  = 3'd0;   // reset before phase A
    localparam [2:0] PH_CST  = 3'd1;   // phase A, constant input
    localparam [2:0] PH_RST2 = 3'd2;   // reset between the phases
    localparam [2:0] PH_GOLD = 3'd3;   // phase B, golden column
    localparam [2:0] PH_DONE = 3'd4;

    reg clk = 1'b0;
    reg rst_n;
    reg [2:0] phase;      // written by the sequencer below, and only there
    reg [3:0] rst_cnt;

    reg  [29:0] s_tdata;
    reg         s_tvalid;
    reg         s_tlast;
    reg  [7:0]  s_tuser;
    reg  [31:0] s_sample_idx;

    wire [32:0] m_tdata;
    wire        m_tvalid;
    wire        m_overflow;
    wire        m_tlast;
    wire [7:0]  m_tuser;
    wire [31:0] m_sample_idx;
    wire        d_valid;
    wire [32:0] d_win;

    integrator u_dut (
        .clk_i        (clk),
        .rst_ni       (rst_n),
        .s_tdata      (s_tdata),
        .s_tvalid     (s_tvalid),
        .s_tlast      (s_tlast),
        .s_tuser      (s_tuser),
        .s_sample_idx (s_sample_idx),
        .m_tdata      (m_tdata),
        .m_tvalid     (m_tvalid),
        .m_overflow   (m_overflow),
        .m_tlast      (m_tlast),
        .m_tuser      (m_tuser),
        .m_sample_idx (m_sample_idx),
        .d_valid      (d_valid),
        .d_win        (d_win)
    );

    always #5 clk <= ~clk;

    reg [31:0] mem_in  [0:N_MAX-1];
    reg [31:0] mem_win [0:N_MAX-1];

    reg [1023:0] vdir;
    reg [1023:0] f_in;
    reg [1023:0] f_win;

    integer limit_n;
    integer feed;
    integer nout;
    integer cst_out;
    integer cyc;
    integer cyc_limit;
    integer cad_q;

    integer cst_mism;
    integer mism_win;
    integer mism_td;
    integer mism_idx;
    integer mism_user;
    integer mism_last;
    integer mism_total;
    integer ovf_cnt;
    integer dval_cnt;
    integer hi_cnt;

    reg [32:0] baca_a;
    reg [32:0] baca_b;

    // phase A expectation, computed from the package widths and the constant input:
    // before the first tap leaves the window the sum is (index + 1) * constant, and from
    // N_WIN_ALT on it alternates between the 37 wide sum and the 38 wide sum.
    wire [31:0] exp_cst = (cst_out < N_A) ? ((cst_out + 1) * CST_IN) :
                          (cst_out[0] ? (N_B * CST_IN) : (N_A * CST_IN));

    // ---- sequencer: one writer per signal, so no phase change races the driver -------
    always @(posedge clk) begin
        cyc <= cyc + 1;
        case (phase)
            PH_RST: begin
                rst_n        <= 1'b0;
                s_tvalid     <= 1'b0;
                s_tdata      <= 30'd0;
                s_tlast      <= 1'b0;
                s_tuser      <= 8'd0;
                s_sample_idx <= 32'd0;
                cad_q        <= 0;
                feed         <= 0;
                rst_cnt      <= rst_cnt + 4'd1;
                if (rst_cnt >= 8) begin
                    rst_n   <= 1'b1;
                    rst_cnt <= 4'd0;
                    phase   <= PH_CST;
                end
            end
            PH_CST: begin
                if ((cad_q == 0) && (feed < CST_N)) begin
                    s_tvalid     <= 1'b1;
                    s_tdata      <= CST_IN[29:0];
                    s_tlast      <= (feed == (CST_N - 1));
                    s_tuser      <= feed[7:0];
                    s_sample_idx <= feed[31:0];
                    feed         <= feed + 1;
                    cad_q        <= CAD - 1;
                end else begin
                    s_tvalid <= 1'b0;
                    if (cad_q > 0) cad_q <= cad_q - 1;
                    // the output of the last word lands one cycle after it was accepted,
                    // so the phase turns over only after the cadence counter has drained
                    if ((cad_q == 0) && (feed >= CST_N)) phase <= PH_RST2;
                end
            end
            PH_RST2: begin
                rst_n        <= 1'b0;
                s_tvalid     <= 1'b0;
                s_tdata      <= 30'd0;
                s_tlast      <= 1'b0;
                s_tuser      <= 8'd0;
                s_sample_idx <= 32'd0;
                cad_q        <= 0;
                feed         <= 0;
                rst_cnt      <= rst_cnt + 4'd1;
                if (rst_cnt >= 8) begin
                    rst_n   <= 1'b1;
                    rst_cnt <= 4'd0;
                    phase   <= PH_GOLD;
                end
            end
            PH_GOLD: begin
                if ((cad_q == 0) && (feed < limit_n)) begin
                    s_tvalid     <= 1'b1;
                    s_tdata      <= mem_in[feed][29:0];
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

    // ---- phase A checking ------------------------------------------------------------
    always @(posedge clk) begin
        if (rst_n && (phase == PH_CST) && m_tvalid) begin
            if (cst_out < CST_N) begin
                if (d_win !== {1'b0, exp_cst}) cst_mism <= cst_mism + 1;
                if (cst_out >= N_A) begin
                    if (cst_out[0]) baca_b <= d_win;
                    else            baca_a <= d_win;
                end
            end
            cst_out <= cst_out + 1;
        end
    end

    // ---- phase B checking ------------------------------------------------------------
    always @(posedge clk) begin
        if (rst_n && (phase == PH_GOLD) && m_tvalid) begin
            if (nout < limit_n) begin
                if (d_win !== {1'b0, mem_win[nout]})       mism_win  <= mism_win + 1;
                if (m_tdata !== {1'b0, mem_win[nout]})     mism_td   <= mism_td + 1;
                if (m_sample_idx !== nout[31:0])           mism_idx  <= mism_idx + 1;
                if (m_tuser !== nout[7:0])                 mism_user <= mism_user + 1;
                if (mem_win[nout][31])                     hi_cnt    <= hi_cnt + 1;
            end
            if (m_tlast !== (nout == (limit_n - 1)))       mism_last <= mism_last + 1;
            if (m_overflow) ovf_cnt <= ovf_cnt + 1;
            nout <= nout + 1;
        end
        if (rst_n && (phase == PH_GOLD) && d_valid) dval_cnt <= dval_cnt + 1;
    end

    initial begin
        limit_n = N_MAX;
        if (!$value$plusargs("LIMIT=%d", limit_n)) limit_n = N_MAX;
        if (!$value$plusargs("VECTOR=%s", vdir)) begin
            $display("tb_integrator: FAIL no +VECTOR (want a directory)");
            $finish;
        end
        $sformat(f_in,  "%0s/04015.kuadrat.hex", vdir);
        $sformat(f_win, "%0s/04015.jendela.hex", vdir);
        $readmemh(f_in, mem_in);
        $readmemh(f_win, mem_win);
        $display("tb_integrator: vectors = %0s", vdir);
        $display("tb_integrator: limit   = %0d of %0d", limit_n, N_MAX);
        $display("tb_integrator: phase A  = window width gate, constant input %0d, %0d words",
                 CST_IN, CST_N);

        feed      = 0;
        nout      = 0;
        cst_out   = 0;
        cyc       = 0;
        cad_q     = 0;
        rst_cnt   = 0;
        cst_mism  = 0;
        mism_win  = 0;
        mism_td   = 0;
        mism_idx  = 0;
        mism_user = 0;
        mism_last = 0;
        ovf_cnt   = 0;
        dval_cnt  = 0;
        hi_cnt    = 0;
        baca_a    = 33'd0;
        baca_b    = 33'd0;

        phase = PH_RST;
        rst_n = 1'b0;
        s_tdata = 30'd0;
        s_tvalid = 1'b0;
        s_tlast = 1'b0;
        s_tuser = 8'd0;
        s_sample_idx = 32'd0;

        cyc_limit = (CST_N + limit_n) * CAD + 200000;
        while ((phase != PH_DONE) && (cyc < cyc_limit)) @(posedge clk);
        repeat (8) @(posedge clk);

        mism_total = mism_win + mism_td + mism_idx + mism_user + mism_last;
        $display("tb_integrator: phase A outputs checked = %0d of %0d", cst_out, CST_N);
        $display("tb_integrator: phase A window width %0d reads = %0d", N_A, baca_a);
        $display("tb_integrator: phase A window width %0d reads = %0d", N_B, baca_b);
        $display("tb_integrator: phase A mismatches = %0d", cst_mism);
        $display("tb_integrator: presented = %0d", feed);
        $display("tb_integrator: outputs   = %0d", nout);
        $display("tb_integrator: compared  = %0d", limit_n);
        $display("tb_integrator: d_win mismatches   = %0d", mism_win);
        $display("tb_integrator: m_tdata mismatches = %0d", mism_td);
        $display("tb_integrator: sample_idx mismatch = %0d", mism_idx);
        $display("tb_integrator: tuser mismatches   = %0d", mism_user);
        $display("tb_integrator: tlast mismatches   = %0d", mism_last);
        $display("tb_integrator: jendela words at or above 2**31 = %0d", hi_cnt);
        $display("tb_integrator: overflow pulses    = %0d", ovf_cnt);
        $display("tb_integrator: d_valid pulses     = %0d", dval_cnt);
        $display("tb_integrator: mismatches = %0d out of %0d", mism_total, limit_n);
        if ((nout == limit_n) && (mism_total == 0) && (ovf_cnt == 0) &&
            (cst_out == CST_N) && (cst_mism == 0) &&
            (baca_a == {1'b0, N_A * CST_IN}) && (baca_b == {1'b0, N_B * CST_IN})) begin
            $display("tb_integrator: PASS");
        end else begin
            $display("tb_integrator: FAIL");
        end
        $finish;
    end

endmodule

`default_nettype wire
