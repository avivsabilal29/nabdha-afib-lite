`default_nettype none
// Probe for RR mirror state: feeds the golden columns one sample per cycle and prints the
// debug words at the envelope peaks between two sample indices. Debug only, outside the repo.
module tb_probe;
    reg clk = 1'b0;
    reg rst_n;
    integer i;
    reg [32:0] td;
    reg [25:0] hp;
    reg [23:0] be;
    reg        tv;
    reg [31:0] idx;
    wire [16*32-1:0] dbg;
    wire         dbgv;
    wire         ovf;
    wire [31:0]  beats;

    peak_detect u (
        .clk_i (clk), .rst_ni (rst_n),
        .s_tdata (td), .s_tvalid (tv), .s_tlast (1'b0), .s_tuser (8'd0),
        .s_sample_idx (idx), .i_enable (1'b1), .i_clear_counters (1'b0),
        .m_tdata (), .m_tvalid (), .m_overflow (ovf), .m_tlast (), .m_tuser (),
        .m_sample_idx (), .m_ev_valid (), .m_ev_kind (), .m_ev_idx (), .m_ev_val (),
        .d_valid (), .d_thr (), .d_pk (), .o_beat_count (beats),
        .s_hp (hp), .s_besaran (be), .d_dbg (dbg), .d_dbg_valid (dbgv)
    );

    always #5 clk <= ~clk;

    reg [31:0] mw [0:449999];
    reg [31:0] mh [0:449999];
    reg [31:0] mb [0:449999];

    initial begin
        $readmemh("../rtlplan2/fase0/04015.jendela.hex", mw);
        $readmemh("../rtlplan2/fase0/04015.hp.hex", mh);
        $readmemh("../rtlplan2/fase0/04015.turunan.hex", mb);
        rst_n = 1'b0; tv = 1'b0; td = 33'd0; hp = 26'd0; be = 24'd0; idx = 32'd0;
        repeat (8) @(posedge clk);
        rst_n = 1'b1;
        for (i = 0; i < 92600; i = i + 1) begin
            @(negedge clk);
            tv  = 1'b1;
            td  = {1'b0, mw[i][31:0]};
            hp  = mh[i][25:0];
            be  = mb[i][23:0];
            idx = i[31:0];
            @(posedge clk);
            #1;
            if (dbgv && (i >= 91300) && (i <= 92600)) begin
                $display("PROBE feed=%0d pos=%0d arm=%b ovf=%b w14=%08x w15=%08x flags=%08x kind/idx=%08x",
                         i, dbg[12*32+:32], dbg[416+1], ovf, dbg[14*32+:32], dbg[15*32+:32],
                         dbg[11*32+:32], dbg[10*32+:32]);
            end
            @(negedge clk);
            tv = 1'b0;
        end
        $display("PROBE done beats=%0d", beats);
        $finish;
    end
endmodule
`default_nettype wire
