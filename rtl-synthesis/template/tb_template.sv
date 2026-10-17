// Testbench template for one block. Runs with Icarus Verilog through ./run_sim.sh.
//
// It drives the sample stream, checks that the design answers, and prints PASS or FAIL. It matches
// template/design_template.sv, so it runs as-is, and you extend the checks as the design fills in.
//
// The beat divider is short here so the simulation finishes fast. On the board the same beat arrives
// every 400000 cycles of the 100 MHz clock, which is 250 Hz.
`timescale 1ns/1ps
`default_nettype none

module tb_template;

    localparam CLK_DIV = 8;    // board value 400000, the divider is shortened for simulation speed
    localparam NBEAT   = 64;   // samples to drive

    reg        clk     = 1'b0;
    reg        rst_ni  = 1'b0;
    reg [15:0] s_tdata = 16'd0;
    reg        s_tvalid = 1'b0;
    reg        s_tlast  = 1'b0;
    wire       out_valid;
    wire [1:0] out_class;
    wire [15:0] out_conf;

    reg [31:0] divider = 32'd0;
    reg        beat    = 1'b0;
    integer    pulses  = 0;
    integer    i;

    design_template dut (
        .clk_i(clk), .rst_ni(rst_ni),
        .s_tdata(s_tdata), .s_tvalid(s_tvalid), .s_tlast(s_tlast),
        .out_valid(out_valid), .out_class(out_class), .out_conf(out_conf)
    );

    always #5 clk = ~clk;   // 100 MHz

    // Sample beat: one pulse every CLK_DIV cycles, the same idea as the enable in the PL.
    always @(posedge clk) begin
        if (!rst_ni) begin
            divider <= 32'd0;
            beat    <= 1'b0;
        end else if (divider == CLK_DIV - 1) begin
            divider <= 32'd0;
            beat    <= 1'b1;
        end else begin
            divider <= divider + 32'd1;
            beat    <= 1'b0;
        end
    end

    always @(posedge clk) begin
        if (rst_ni && out_valid) pulses <= pulses + 1;
    end

    initial begin
        $dumpfile("reports/sim/tb_template.vcd");
        $dumpvars(0, tb_template);

        rst_ni = 1'b0;
        repeat (10) @(posedge clk);
        rst_ni = 1'b1;

        for (i = 0; i < NBEAT; i = i + 1) begin
            repeat (CLK_DIV) @(posedge clk);
            s_tdata  = 16'd1000 + i;
            s_tvalid = 1'b1;
            s_tlast  = (i == NBEAT - 1);
            @(posedge clk);
            s_tvalid = 1'b0;
            s_tlast  = 1'b0;
        end

        repeat (4 * CLK_DIV) @(posedge clk);

        $display("samples driven: %0d, output pulses: %0d", NBEAT, pulses);

        if (pulses == 0) begin
            $fatal(1, "FAIL: no output pulse, check the reset and the handshake");
        end
        if (pulses < NBEAT - 2) begin
            $fatal(1, "FAIL: samples are being dropped");
        end

        $display("PASS: tb_template");
        $finish;
    end

endmodule

`default_nettype wire
