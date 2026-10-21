// tb_throughput.sv
//
// Not a functional check. This harness exists to answer one question with a number instead of a
// feeling: how many clock cycles per second can each simulator on this machine do on this design.
// It drives counter8 for a counted number of cycles and keeps a checksum of the count, so the
// counter cannot be optimised away.
//
//   +cycles=N   how many clock cycles to run, default 1000000
//
// The sampling point is on the falling edge, and that is not decoration. Reading the counter outputs
// in the same time step as the rising edge is a race between the flip-flop update and the read: Icarus
// and Verilator resolved it differently, and the checksums for the same 10 million cycles differed by
// exactly 128, which is 10000000 modulo 256. A difference of exactly the wrap residue means the two
// runs were one sample out of alignment, not that they computed different logic. Sampling on the
// opposite edge removes the race and both simulators agree to the last digit.
//
// Run it through flow.sh bench, which runs both simulators and prints the comparison.

`timescale 1ns/1ps
`default_nettype none

module tb_throughput;

    localparam integer CLK_PERIOD = 10;   // 100 MHz

    integer cycles = 1000000;
    integer i;

    reg        clk   = 1'b0;
    reg        rst_n = 1'b0;
    reg        en    = 1'b0;
    reg        up    = 1'b1;
    reg        load  = 1'b0;
    reg  [7:0] lval  = 8'h00;
    wire [7:0] count;
    wire       carry;
    wire       borrow;
    wire       zero;
    wire       tc;

    // Fold every output into one value, so nothing can be optimised away and lint has no unused
    // signal to complain about.
    reg [31:0] sum = 32'd0;

    counter8 dut (
        .clk_i      (clk),
        .rst_ni     (rst_n),
        .en_i       (en),
        .up_i       (up),
        .load_i     (load),
        .load_val_i (lval),
        .count_o    (count),
        .carry_o    (carry),
        .borrow_o   (borrow),
        .zero_o     (zero),
        .tc_o       (tc)
    );

    always #(CLK_PERIOD/2) clk <= ~clk;

    initial begin
        if (!$value$plusargs("cycles=%d", cycles)) begin
            cycles = 1000000;
        end

        // Release and enable one nanosecond after an edge, never in the same time step as an edge.
        // Changing an input in the same time step as a rising edge is a race: whether the flip-flop
        // sees the new value depends on the simulator's event ordering, and Icarus and Verilator then
        // disagree by one sample for the whole run.
        repeat (4) @(posedge clk);
        #1;
        rst_n = 1'b1;
        en    = 1'b1;
        up    = 1'b1;

        for (i = 0; i < cycles; i = i + 1) begin
            @(negedge clk);   // sample on the opposite edge: every flip-flop has settled long before
            sum = sum + {24'd0, count} + {31'd0, carry} + {31'd0, borrow} + {31'd0, zero} + {31'd0, tc};
        end

        $display("cycles %0d, checksum %0d", cycles, sum);
        $finish;
    end

endmodule

`default_nettype wire
