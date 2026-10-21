// tb_counter8.sv
//
// Self-checking testbench for counter8.sv. No wave viewer needed and no manual reading: every check
// prints PASS or FAIL, and the run ends with a non-zero exit code if any check failed. That is what
// makes it usable as a gate in a script.
//
// Allowed here and nowhere else in the project: initial blocks, delays, $display.
//
// Three details here were paid for, and are worth keeping:
//   1. `expect` is a SystemVerilog keyword, so Icarus 12 refuses it as a task name. The check tasks
//      are called check8 and check1 instead. Verilator does not lint testbenches unless it is asked
//      to, so that mistake only appears at simulation time, which is why flow.sh lints this file.
//   2. One check task for 8-bit values and one for single-bit flags, so every argument matches its
//      port width and lint has nothing to say about implicit extension.
//   3. Task ports are declared in the Verilog-1995 style, which every simulator here accepts with no
//      extra flag.

`timescale 1ns/1ps
`default_nettype none

module tb_counter8;

    localparam integer CLK_PERIOD = 10;   // 100 MHz

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

    integer errors = 0;
    integer checks = 0;

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

    // One clock cycle, with the inputs held as they are.
    task tick;
        begin
            @(posedge clk);
            #1;
        end
    endtask

    // Compare an 8-bit value and report.
    task check8;
        input [255:0] what;
        input [7:0]   got;
        input [7:0]   want;
        begin
            checks = checks + 1;
            if (got !== want) begin
                errors = errors + 1;
                $display("FAIL %0s: got %0d, want %0d", what, got, want);
            end else begin
                $display("PASS %0s: %0d", what, got);
            end
        end
    endtask

    // Compare a single-bit flag and report.
    task check1;
        input [255:0] what;
        input         got;
        input         want;
        begin
            checks = checks + 1;
            if (got !== want) begin
                errors = errors + 1;
                $display("FAIL %0s: got %0b, want %0b", what, got, want);
            end else begin
                $display("PASS %0s: %0b", what, got);
            end
        end
    endtask

    initial begin
        $display("counter8 self check, %0d ns period", CLK_PERIOD);

        // Waveform on request, so the normal run stays silent. Run it with flow.sh wave.
        if ($test$plusargs("vcd")) begin
            $dumpfile("reports/counter8.vcd");
            $dumpvars(0, tb_counter8);
        end

        // Reset. Synchronous, so it needs a clock edge to take effect.
        rst_n = 1'b0; en = 1'b0; up = 1'b1; load = 1'b0; lval = 8'h00;
        tick; tick;
        check8("reset clears count", count, 8'h00);
        check1("reset clears carry", carry, 1'b0);
        check1("zero flag after reset", zero, 1'b1);

        // Enable low freezes the count.
        rst_n = 1'b1;
        tick; tick;
        check8("count frozen while en low", count, 8'h00);

        // Count up ten steps.
        en = 1'b1; up = 1'b1;
        repeat (10) tick;
        check8("ten up steps", count, 8'd10);
        check1("zero flag low at 10", zero, 1'b0);

        // Wrap up. Load 254 with one tick, then two ticks carry it through 255 and into 0.
        en = 1'b0; load = 1'b1; lval = 8'hFE; tick;
        load = 1'b0; en = 1'b1; up = 1'b1;
        check8("loaded 254", count, 8'd254);
        check1("terminal count flag at 254", tc, 1'b0);
        tick;
        check8("255 reached", count, 8'd255);
        check1("terminal count flag at 255", tc, 1'b1);
        check1("carry not yet", carry, 1'b0);
        tick;
        check8("wrapped to zero", count, 8'h00);
        check1("carry pulse on the wrap clock", carry, 1'b1);
        tick;
        check1("carry is one clock wide", carry, 1'b0);

        // Wrap down. Load 1, then two ticks carry it through 0 and into 255.
        load = 1'b1; lval = 8'h01; tick;
        load = 1'b0; up = 1'b0;
        check8("loaded 1", count, 8'd1);
        tick;
        check8("zero reached going down", count, 8'h00);
        check1("borrow not yet", borrow, 1'b0);
        tick;
        check8("wrapped down to 255", count, 8'd255);
        check1("borrow pulse on the wrap clock", borrow, 1'b1);
        tick;
        check1("borrow is one clock wide", borrow, 1'b0);

        // Load has priority over counting.
        load = 1'b1; lval = 8'h5A; tick;
        load = 1'b0;
        check8("load wins over enable", count, 8'h5A);

        // Down count from a loaded value.
        repeat (2) tick;
        check8("two down steps", count, 8'h58);

        $display("checks %0d, errors %0d", checks, errors);
        if (errors == 0) begin
            $display("RESULT PASS");
            $finish;
        end else begin
            $display("RESULT FAIL");
            $fatal(1, "counter8 self check failed with %0d error(s)", errors);
        end
    end

endmodule

`default_nettype wire
