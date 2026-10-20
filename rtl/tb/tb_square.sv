// ---------------------------------------------------------------------------
// tb_square.sv -- squaring gate for rtl/square.sv against the golden column.
//
// Golden data: +VECTOR=<dir> holds the Fase 0 columns, one 32 bit word per line,
//   exactly 8 hex digits, no comments, $readmemh compatible:
//     04015.turunan.hex    the square input column, 24 bit Q17.7 words
//     04015.kuadrat.hex    the golden square output, 30 bit count squared
// No conversion helper is needed: the columns are already in $readmemh form and the
//   value sits in the low bits of the 32 bit word, which the format counter below
//   proves word by word before the comparison is trusted. The kuadrat column is never
//   negative, so the unused high bits 31:30 must read zero and a set bit there is
//   counted as a format fault rather than compared silently.
//
// Gate: d_sq and m_tdata match 04015.kuadrat.hex for every one of the 450000 samples.
// Extra evidence reported on the same run: m_sample_idx against the presented index,
//   m_tuser, m_tlast, the m_overflow pulse count (0 on this record: the largest golden
//   square is 350438400 and the saturation point SQ_SAT is 1073741823, so the flag must
//   stay low and a pulse here is a finding, not something to clamp away), the d_valid
//   pulse count, and the count of golden words whose unused high bits are not zero.
//
// Optional plusargs: +LIMIT=<n> to run a short smoke pass, +VECTOR=<dir> required.
//
// No file level timescale: rtl/afib_lite_pkg.sv carries none and a file level
//   timescale in this file makes Verilator raise TIMESCALEMOD against the package in
//   the lint run. The clock is event driven, so the time unit changes no result.
//
// House style: expected values come from the golden column, never typed here.
// ---------------------------------------------------------------------------
`default_nettype none

module tb_square;

    localparam integer N_MAX = 450000;
    localparam integer CAD   = 8;    // cycles between samples, > the 1 cycle latency

    reg clk = 1'b0;
    reg rst_n = 1'b0;

    reg  [23:0] s_tdata;
    reg         s_tvalid;
    reg         s_tlast;
    reg  [7:0]  s_tuser;
    reg  [31:0] s_sample_idx;

    wire [29:0] m_tdata;
    wire        m_tvalid;
    wire        m_overflow;
    wire        m_tlast;
    wire [7:0]  m_tuser;
    wire [31:0] m_sample_idx;
    wire        d_valid;
    wire [29:0] d_sq;

    square u_dut (
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
        .d_sq         (d_sq)
    );

    always #5 clk <= ~clk;

    reg [31:0] mem_in [0:N_MAX-1];
    reg [31:0] mem_ku [0:N_MAX-1];

    reg [1023:0] vdir;
    reg [1023:0] f_in;
    reg [1023:0] f_ku;

    integer limit_n;
    integer feed;
    integer nout;
    integer cyc;
    integer cyc_limit;
    integer cad_q;
    integer mism_sq;
    integer mism_td;
    integer mism_idx;
    integer mism_user;
    integer mism_last;
    integer mism_total;
    integer ovf_cnt;
    integer dval_cnt;
    integer bad_fmt;

    initial begin
        limit_n = N_MAX;
        if (!$value$plusargs("LIMIT=%d", limit_n)) limit_n = N_MAX;
        if (!$value$plusargs("VECTOR=%s", vdir)) begin
            $display("tb_square: FAIL no +VECTOR (want a directory)");
            $finish;
        end
        $sformat(f_in, "%0s/04015.turunan.hex", vdir);
        $sformat(f_ku, "%0s/04015.kuadrat.hex", vdir);
        $readmemh(f_in, mem_in);
        $readmemh(f_ku, mem_ku);
        $display("tb_square: vectors = %0s", vdir);
        $display("tb_square: limit   = %0d of %0d", limit_n, N_MAX);

        feed = 0;
        nout = 0;
        cyc = 0;
        cad_q = 0;
        mism_sq = 0;
        mism_td = 0;
        mism_idx = 0;
        mism_user = 0;
        mism_last = 0;
        ovf_cnt = 0;
        dval_cnt = 0;
        bad_fmt = 0;

        rst_n = 1'b0;
        s_tvalid = 1'b0;
        s_tdata = 24'd0;
        s_tlast = 1'b0;
        s_tuser = 8'd0;
        s_sample_idx = 32'd0;
        repeat (8) @(posedge clk);
        rst_n = 1'b1;

        cyc_limit = limit_n * CAD + 200000;
        while ((nout < limit_n) && (cyc < cyc_limit)) @(posedge clk);
        repeat (8) @(posedge clk);

        mism_total = mism_sq + mism_td + mism_idx + mism_user + mism_last + bad_fmt;
        $display("tb_square: presented = %0d", feed);
        $display("tb_square: outputs   = %0d", nout);
        $display("tb_square: compared  = %0d", limit_n);
        $display("tb_square: d_sq mismatches    = %0d", mism_sq);
        $display("tb_square: m_tdata mismatches = %0d", mism_td);
        $display("tb_square: sample_idx mismatch= %0d", mism_idx);
        $display("tb_square: tuser mismatches   = %0d", mism_user);
        $display("tb_square: tlast mismatches   = %0d", mism_last);
        $display("tb_square: golden format odd  = %0d", bad_fmt);
        $display("tb_square: overflow pulses    = %0d", ovf_cnt);
        $display("tb_square: d_valid pulses     = %0d", dval_cnt);
        $display("tb_square: mismatches = %0d out of %0d", mism_total, limit_n);
        if ((nout == limit_n) && (mism_total == 0) && (ovf_cnt == 0)) begin
            $display("tb_square: PASS");
        end else begin
            $display("tb_square: FAIL");
        end
        $finish;
    end

    // presentation: one cycle of s_tvalid every CAD cycles, inside a fixed cadence
    always @(posedge clk) begin
        cyc <= cyc + 1;
        if (!rst_n) begin
            s_tvalid     <= 1'b0;
            s_tdata      <= 24'd0;
            s_tlast      <= 1'b0;
            s_tuser      <= 8'd0;
            s_sample_idx <= 32'd0;
            cad_q        <= 0;
            feed         <= 0;
        end else if ((cad_q == 0) && (feed < limit_n)) begin
            s_tvalid     <= 1'b1;
            s_tdata      <= mem_in[feed][23:0];
            s_tlast      <= (feed == (limit_n - 1));
            s_tuser      <= feed[7:0];
            s_sample_idx <= feed[31:0];
            feed         <= feed + 1;
            cad_q        <= CAD - 1;
        end else begin
            s_tvalid <= 1'b0;
            if (cad_q > 0) cad_q <= cad_q - 1;
        end
    end

    // checking: every output word is compared with the golden column of its index
    always @(posedge clk) begin
        if (rst_n && m_tvalid) begin
            if (nout < limit_n) begin
                if (d_sq !== mem_ku[nout][29:0])            mism_sq   <= mism_sq + 1;
                if (m_tdata !== mem_ku[nout][29:0])         mism_td   <= mism_td + 1;
                if (m_sample_idx !== nout[31:0])            mism_idx  <= mism_idx + 1;
                if (m_tuser !== nout[7:0])                  mism_user <= mism_user + 1;
                if (mem_ku[nout][31:30] !== 2'b00)          bad_fmt   <= bad_fmt + 1;
            end
            if (m_tlast !== (nout == (limit_n - 1)))        mism_last <= mism_last + 1;
            if (m_overflow) ovf_cnt <= ovf_cnt + 1;
            nout <= nout + 1;
        end
        if (rst_n && d_valid) dval_cnt <= dval_cnt + 1;
    end

endmodule

`default_nettype wire
