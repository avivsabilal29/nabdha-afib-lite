// ---------------------------------------------------------------------------
// tb_derivative.sv -- derivative gate for rtl/derivative.sv against the golden column,
// plus the synthetic hand series the plan requires. Two runs in one simulation.
//
// Run 1, golden, "04015": +VECTOR=<dir> holds the Fase 0 columns, one 32 bit word per
//   line, exactly 8 hex digits, no comments, $readmemh compatible:
//     04015.hp.hex         the derivative input column, 26 bit Q22.4 words
//     04015.turunan.hex    the golden derivative output, 24 bit Q17.7 words
//   No conversion helper is needed: the columns are already in $readmemh form and the value
//   sits sign extended in the low bits of the 32 bit word, which the format counter below
//   proves word by word before the comparison is trusted. The comparison takes the low
//   W_DER bits of each golden word, exactly as tb_lowpass.sv does.
//   Gate: m_tdata matches 04015.turunan.hex for every one of the 450000 samples.
//
// Run 2, synthetic, the negative series the plan and the task brief require. The frozen
//   fixture cannot test the truncate-toward-zero rule at all: the raw sum is divisible by 8
//   on 450000 of 450000 samples, so a floor shift reproduces the whole golden column (0
//   mismatches, measured twice: once against the fixture and once with a floor model). The
//   series below is built by hand so that the raw sums s = 2x[i] + x[i-1] - x[i-3] - 2x[i-4]
//   and the expected y = trunc(s / 8) are both known without the fixture:
//     part A  x = [        0, 1, 0, 0, 0]  sums      0,   2,   1,    0,    -1,    -2
//                                          the plan 4.4 trap series, floor gives -1 at the tail
//     part B  x = [        0,10, 0, 0, 0]  sums      0,  20,  10,    0,   -10,   -20
//                                          floor gives -2, -3 where truncation gives -1, -2
//     part C  x = [        0,-10,0, 0, 0]  sums      0, -20, -10,    0,    10,    20
//                                          the mirrored case, same proof on the other sign
//     part D  x = [        0,A,  0, 0, 0]  sums      0, 2A,  A,     0,    -A,    -2A
//                                          A = 12000000, inside the measured |hp| <= 19286208
//     part E  x = [        A,A,  0,-A,-A]  sums     2A, 3A,  A,  -3A,   -6A,   -3A, ...
//                                          -6A = -72000000, y = -9000000 saturates W_DER
//   The array is padded with four zeros after every part, so no kernel tail of one part
//   reaches the next, and the packed vector below carries the raw sum of every word in its
//   own comment. Every expected word is typed from that arithmetic, which is the one place
//   in this tree where a number is written instead of read: the plan asks for exactly this
//   vector because the fixture cannot supply it.
//   Gate: run 2 mismatches 0 of 45 words, first flagged overflow sample index 40.
//   The series has teeth, measured with the same kernel in python: a floor shift
//   (s >> 3) differs from the golden rule on 6 of the 45 words and the first difference is
//   index 4, so a stage that used an arithmetic shift would fail run 2 while passing run 1.
//
// Optional plusargs: +VECTOR=<dir> required, +LIMIT=<n> to shorten run 1 (default 450000).
//   +LIMIT exists so a smoke pass costs seconds; the default is the full column, and the
//   gate reported in the report is the full run.
//
// No file level timescale: rtl/afib_lite_pkg.sv carries none and a file level timescale in
//   this file makes Verilator raise TIMESCALEMOD against the package in the lint run. The
//   clock is event driven, so the time unit changes no result.
//
// House style: expected values come from the golden column in run 1 and from the hand
//   series in run 2, never from a measured number typed here.
// ---------------------------------------------------------------------------
`default_nettype none

module tb_derivative;

    localparam integer N_MAX = 450000;
    localparam integer CAD   = 24;   // cycles between samples, > the 17 cycle latency
    localparam integer N_SYN = 45;   // words in the synthetic series

    // synthetic series, packed MSB first so that word 0 sits at the top of SYN_IN.
    // Comment per word: index, x[i], raw sum s, expected y = trunc(s / 8), saturated.
    localparam [N_SYN*26-1:0] SYN_IN = {
        26'sd0,           // [ 0] x=         0  s=          0  y=        0
        26'sd1,           // [ 1] x=         1  s=          2  y=        0
        26'sd0,           // [ 2] x=         0  s=          1  y=        0
        26'sd0,           // [ 3] x=         0  s=          0  y=        0
        26'sd0,           // [ 4] x=         0  s=         -1  y=        0
        26'sd0,           // [ 5] x=         0  s=         -2  y=        0
        26'sd0,           // [ 6] x=         0  s=          0  y=        0
        26'sd0,           // [ 7] x=         0  s=          0  y=        0
        26'sd0,           // [ 8] x=         0  s=          0  y=        0
        26'sd0,           // [ 9] x=         0  s=          0  y=        0
        26'sd10,          // [10] x=        10  s=         20  y=        2
        26'sd0,           // [11] x=         0  s=         10  y=        1
        26'sd0,           // [12] x=         0  s=          0  y=        0
        26'sd0,           // [13] x=         0  s=        -10  y=       -1
        26'sd0,           // [14] x=         0  s=        -20  y=       -2
        26'sd0,           // [15] x=         0  s=          0  y=        0
        26'sd0,           // [16] x=         0  s=          0  y=        0
        26'sd0,           // [17] x=         0  s=          0  y=        0
        26'sd0,           // [18] x=         0  s=          0  y=        0
        -26'sd10,         // [19] x=       -10  s=        -20  y=       -2
        26'sd0,           // [20] x=         0  s=        -10  y=       -1
        26'sd0,           // [21] x=         0  s=          0  y=        0
        26'sd0,           // [22] x=         0  s=         10  y=        1
        26'sd0,           // [23] x=         0  s=         20  y=        2
        26'sd0,           // [24] x=         0  s=          0  y=        0
        26'sd0,           // [25] x=         0  s=          0  y=        0
        26'sd0,           // [26] x=         0  s=          0  y=        0
        26'sd0,           // [27] x=         0  s=          0  y=        0
        26'sd12000000,    // [28] x=  12000000  s=   24000000  y=  3000000
        26'sd0,           // [29] x=         0  s=   12000000  y=  1500000
        26'sd0,           // [30] x=         0  s=          0  y=        0
        26'sd0,           // [31] x=         0  s=  -12000000  y= -1500000
        26'sd0,           // [32] x=         0  s=  -24000000  y= -3000000
        26'sd0,           // [33] x=         0  s=          0  y=        0
        26'sd0,           // [34] x=         0  s=          0  y=        0
        26'sd0,           // [35] x=         0  s=          0  y=        0
        26'sd12000000,    // [36] x=  12000000  s=   24000000  y=  3000000
        26'sd12000000,    // [37] x=  12000000  s=   36000000  y=  4500000
        26'sd0,           // [38] x=         0  s=   12000000  y=  1500000
        -26'sd12000000,   // [39] x= -12000000  s=  -36000000  y= -4500000
        -26'sd12000000,   // [40] x= -12000000  s=  -72000000  y= -9000000 SATURATES
        26'sd0,           // [41] x=         0  s=  -36000000  y= -4500000
        26'sd0,           // [42] x=         0  s=   12000000  y=  1500000
        26'sd0,           // [43] x=         0  s=   36000000  y=  4500000
        26'sd0            // [44] x=         0  s=   24000000  y=  3000000
    };

    // expected derivative words, 24 bit two's complement, saturated at +-8388607 the way
    // bandpass.sv saturates its own output register
    localparam [N_SYN*24-1:0] SYN_EXP = {
        24'h000000, 24'h000000, 24'h000000, 24'h000000, 24'h000000,
        24'h000000, 24'h000000, 24'h000000, 24'h000000, 24'h000000,
        24'h000002, 24'h000001, 24'h000000, 24'hFFFFFF, 24'hFFFFFE,
        24'h000000, 24'h000000, 24'h000000, 24'h000000, 24'hFFFFFE,
        24'hFFFFFF, 24'h000000, 24'h000001, 24'h000002, 24'h000000,
        24'h000000, 24'h000000, 24'h000000, 24'h2DC6C0, 24'h16E360,
        24'h000000, 24'hE91CA0, 24'hD23940, 24'h000000, 24'h000000,
        24'h000000, 24'h2DC6C0, 24'h44AA20, 24'h16E360, 24'hBB55E0,
        24'h800000,   // [40] saturation of -9000000
        24'hBB55E0, 24'h16E360, 24'h44AA20, 24'h2DC6C0
    };

    reg clk = 1'b0;
    reg rst_n = 1'b0;

    reg  [25:0] s_tdata;
    reg         s_tvalid;
    reg         s_tlast;
    reg  [7:0]  s_tuser;
    reg  [31:0] s_sample_idx;

    wire [23:0] m_tdata;
    wire        m_tvalid;
    wire        m_overflow;
    wire        m_tlast;
    wire [7:0]  m_tuser;
    wire [31:0] m_sample_idx;
    wire        d_valid;
    wire [23:0] d_der;

    derivative u_dut (
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
        .d_der        (d_der)
    );

    always #5 clk <= ~clk;

    reg [31:0] mem_in  [0:N_MAX-1];   // 04015.hp.hex,      the stage input
    reg [31:0] mem_der [0:N_MAX-1];   // 04015.turunan.hex, the golden output

    reg [1023:0] vdir;
    reg [1023:0] f_in;
    reg [1023:0] f_der;

    integer limit_n;
    integer limit_run;
    integer mode;          // 0 golden run, 1 synthetic run
    integer feed;
    integer nout;
    integer cyc;
    integer cyc_limit;
    integer cad_q;

    integer feed_a;
    integer nout_a;
    integer mism_der;      // m_tdata against the golden turunan column
    integer mism_dd;       // d_der against the same column
    integer mism_idx;
    integer mism_user;
    integer mism_last;
    integer mism_first;
    integer ovf_cnt;
    integer ovf_first;
    integer dval_cnt;
    integer bad_fmt;
    integer syn_mism;      // m_tdata against the hand expected words
    integer syn_mism_dd;
    integer syn_mism_idx;
    integer syn_first;
    integer syn_ovf_cnt;
    integer syn_ovf_first;
    integer syn_out;

    initial begin
        limit_n = N_MAX;
        if (!$value$plusargs("LIMIT=%d", limit_n)) limit_n = N_MAX;
        if (!$value$plusargs("VECTOR=%s", vdir)) begin
            $display("tb_derivative: FAIL no +VECTOR (want a directory)");
            $finish;
        end
        $sformat(f_in,  "%0s/04015.hp.hex", vdir);
        $sformat(f_der, "%0s/04015.turunan.hex", vdir);
        $readmemh(f_in, mem_in);
        $readmemh(f_der, mem_der);
        $display("tb_derivative: vectors = %0s", vdir);
        $display("tb_derivative: limit   = %0d of %0d", limit_n, N_MAX);

        feed = 0;
        nout = 0;
        cyc = 0;
        cad_q = 0;
        mode = 0;
        limit_run = limit_n;
        mism_der = 0;
        mism_dd = 0;
        mism_idx = 0;
        mism_user = 0;
        mism_last = 0;
        mism_first = -1;
        ovf_cnt = 0;
        ovf_first = -1;
        dval_cnt = 0;
        bad_fmt = 0;
        syn_mism = 0;
        syn_mism_dd = 0;
        syn_mism_idx = 0;
        syn_first = -1;
        syn_ovf_cnt = 0;
        syn_ovf_first = -1;
        syn_out = 0;

        rst_n = 1'b0;
        repeat (8) @(posedge clk);
        rst_n = 1'b1;

        // ---- run 1: the golden column ------------------------------------
        cyc_limit = limit_n * CAD + 200000;
        while ((nout < limit_n) && (cyc < cyc_limit)) @(posedge clk);
        repeat (8) @(posedge clk);

        feed_a = feed;
        nout_a = nout;
        $display("tb_derivative: [golden] presented       = %0d", feed_a);
        $display("tb_derivative: [golden] outputs         = %0d", nout_a);
        $display("tb_derivative: [golden] words compared: %0d", limit_n);
        $display("tb_derivative: [golden] mismatches: %0d   (m_tdata against turunan)", mism_der);
        $display("tb_derivative: [golden] d_der mismatches   = %0d", mism_dd);
        $display("tb_derivative: [golden] sample_idx mismatch= %0d", mism_idx);
        $display("tb_derivative: [golden] tuser mismatches   = %0d", mism_user);
        $display("tb_derivative: [golden] tlast mismatches   = %0d", mism_last);
        $display("tb_derivative: [golden] first bad index    = %0d", mism_first);
        $display("tb_derivative: [golden] overflow pulses    = %0d", ovf_cnt);
        $display("tb_derivative: [golden] first overflow idx = %0d", ovf_first);
        $display("tb_derivative: [golden] d_valid pulses     = %0d", dval_cnt);
        $display("tb_derivative: [golden] golden format odd  = %0d", bad_fmt);
        if ((nout_a == limit_n) && (mism_der == 0) && (mism_dd == 0) && (mism_idx == 0) &&
            (mism_user == 0) && (mism_last == 0) && (bad_fmt == 0)) begin
            $display("tb_derivative: [golden] PASS");
        end else begin
            $display("tb_derivative: [golden] FAIL");
        end

        // ---- run 2: the synthetic hand series ----------------------------
        // rst_n falls first, so the clocked blocks are in their reset branch while the
        // counters below are set from this block; nothing else can write them at that edge.
        // The wait is a plain repeat, not the shared cyc guard: cyc keeps counting from run 1
        // and a blocking reset of it would be overwritten by the same edge's nonblocking
        // increment, which is exactly how the first draft reported 0 synthetic outputs.
        rst_n = 1'b0;
        repeat (8) @(posedge clk);
        mode      = 1;
        limit_run = N_SYN;
        feed      = 0;
        nout      = 0;
        cad_q     = 0;
        rst_n     = 1'b1;

        repeat (N_SYN * CAD + 200) @(posedge clk);
        syn_out = nout;

        $display("tb_derivative: [synthetic] length          = %0d", N_SYN);
        $display("tb_derivative: [synthetic] outputs         = %0d", syn_out);
        $display("tb_derivative: [synthetic] words compared: %0d", N_SYN);
        $display("tb_derivative: [synthetic] mismatches: %0d   (floor shift differs on 6)", syn_mism);
        $display("tb_derivative: [synthetic] d_der mismatches   = %0d", syn_mism_dd);
        $display("tb_derivative: [synthetic] sample_idx mismatch= %0d", syn_mism_idx);
        $display("tb_derivative: [synthetic] first bad index    = %0d", syn_first);
        $display("tb_derivative: [synthetic] first overflow idx = %0d (expected 40)", syn_ovf_first);
        $display("tb_derivative: [synthetic] overflow pulses    = %0d (expected 5)", syn_ovf_cnt);
        if ((syn_out == N_SYN) && (syn_mism == 0) && (syn_mism_dd == 0) &&
            (syn_mism_idx == 0) && (syn_ovf_first == 40)) begin
            $display("tb_derivative: [synthetic] PASS");
        end else begin
            $display("tb_derivative: [synthetic] FAIL");
        end

        if (((nout_a == limit_n) && (mism_der == 0) && (mism_dd == 0) && (mism_idx == 0) &&
             (mism_user == 0) && (mism_last == 0) && (bad_fmt == 0)) &&
            ((syn_out == N_SYN) && (syn_mism == 0) && (syn_mism_dd == 0) &&
             (syn_mism_idx == 0) && (syn_ovf_first == 40))) begin
            $display("tb_derivative: PASS");
            $finish;
        end else begin
            $display("tb_derivative: FAIL");
            $fatal(1, "tb_derivative: gate failed");
        end
    end

    // presentation: one cycle of s_tvalid every CAD cycles, inside a fixed cadence.
    // run 2 takes the same cadence, so the 17 cycle latency has the same margin in both.
    always @(posedge clk) begin
        cyc <= cyc + 1;
        if (!rst_n) begin
            s_tvalid     <= 1'b0;
            s_tdata      <= 26'sd0;
            s_tlast      <= 1'b0;
            s_tuser      <= 8'd0;
            s_sample_idx <= 32'd0;
            cad_q        <= 0;
            feed         <= 0;
        end else if ((cad_q == 0) && (feed < limit_run)) begin
            s_tvalid     <= 1'b1;
            s_tdata      <= (mode == 0) ? mem_in[feed][25:0]
                                        : SYN_IN[(N_SYN-1-feed)*26 +: 26];
            s_tlast      <= (feed == (limit_run - 1));
            s_tuser      <= feed[7:0];
            s_sample_idx <= feed[31:0];
            feed         <= feed + 1;
            cad_q        <= CAD - 1;
        end else begin
            s_tvalid <= 1'b0;
            if (cad_q > 0) cad_q <= cad_q - 1;
        end
    end

    // checking: every output word is compared with the golden column of its index in run 1
    // and with the hand word of its index in run 2.
    always @(posedge clk) begin
        if (rst_n && m_tvalid) begin
            if (mode == 0) begin
                if (nout < limit_n) begin
                    if (m_tdata !== mem_der[nout][23:0]) begin
                        mism_der <= mism_der + 1;
                        if (mism_first < 0) mism_first <= nout;
                    end
                    if (d_der  !== mem_der[nout][23:0]) mism_dd   <= mism_dd + 1;
                    if (m_sample_idx !== nout[31:0])    mism_idx  <= mism_idx + 1;
                    if (m_tuser !== nout[7:0])          mism_user <= mism_user + 1;
                    if (mem_der[nout][31:24] !== {8{mem_der[nout][23]}}) bad_fmt <= bad_fmt + 1;
                    if (mem_in[nout][31:26] !== {6{mem_in[nout][25]}})   bad_fmt <= bad_fmt + 1;
                end
                if (m_tlast !== (nout == (limit_n - 1))) mism_last <= mism_last + 1;
                if (m_overflow) begin
                    ovf_cnt <= ovf_cnt + 1;
                    if (ovf_first < 0) ovf_first <= nout;
                end
            end else begin
                if (nout < N_SYN) begin
                    if (m_tdata !== SYN_EXP[(N_SYN-1-nout)*24 +: 24]) begin
                        syn_mism <= syn_mism + 1;
                        if (syn_first < 0) syn_first <= nout;
                    end
                    if (d_der !== SYN_EXP[(N_SYN-1-nout)*24 +: 24]) syn_mism_dd <= syn_mism_dd + 1;
                    if (m_sample_idx !== nout[31:0]) syn_mism_idx <= syn_mism_idx + 1;
                end
                if (m_overflow) begin
                    syn_ovf_cnt <= syn_ovf_cnt + 1;
                    if (syn_ovf_first < 0) syn_ovf_first <= nout;
                end
            end
            nout <= nout + 1;
        end
        if (rst_n && d_valid) dval_cnt <= dval_cnt + 1;
    end

endmodule

`default_nettype wire
