
`default_nettype none
module tb_dbg;
  localparam integer W_DER = 24, W_TW = 23;
  reg clk=0, rst_n=1; reg [W_DER-1:0] td=24'd1000; reg tv=0, tl=0; reg [7:0] tu=0; reg [31:0] ti=0;
  reg en=0, pv=0; reg [31:0] dl=0; reg dv=0; reg [W_DER-1:0] kq=0; reg kv=0;
  wire [W_TW-1:0] mt; wire mv, mo, ml; wire [7:0] mu; wire [31:0] mi; wire rj, dvl; wire [W_TW-1:0] dtw;
  wire pkv; wire [31:0] pki; wire pita; wire ovr;
  t_rule_dbg u (.clk_i(clk), .rst_ni(rst_n), .s_tdata(td), .s_tvalid(tv), .s_tlast(tl), .s_tuser(tu),
     .s_sample_idx(ti), .i_rule_enable(en), .m_tdata(mt), .m_tvalid(mv), .m_overflow(mo), .m_tlast(ml),
     .m_tuser(mu), .m_sample_idx(mi), .o_reject(rj), .d_valid(dvl), .d_tw(dtw),
     .i_peak_valid(pv), .i_delta(dl), .i_delta_valid(dv), .i_kem_qrs(kq), .i_kem_qrs_valid(kv),
     .o_peak_valid(pkv), .o_peak_idx(pki), .o_dalam_pita(pita), .o_overrun(ovr));
  always #5 clk = ~clk;
  integer w;
  initial begin
    rst_n = 0; repeat (4) @(posedge clk); rst_n = 1;
    for (w = 0; w < 60; w = w + 1) begin
      tv <= 1; td <= 24'd1000; ti <= w; tu <= w[7:0]; tl <= 0;
      if (w == 10) begin pv <= 1; en <= 1; dl <= 32'd50; dv <= 1; kq <= 24'd5000; kv <= 1; end
      else pv <= 0;
      @(posedge clk);
      if (pkv) $display("TB verdict at w=%0d idx=%0d kem=%0d rej=%0d", w, pki, mt, rj);
    end
    tv <= 0; repeat (4) @(posedge clk); $display("TB done"); $finish;
  end
endmodule
`default_nettype wire
