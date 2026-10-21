// counter8.sv
//
// Reference project for the AFIB-LITE RTL work: an 8-bit synchronous counter on SKY130 standard
// cells and on the Kria KV260. Copy the structure, not the function.
//
// House rules from rtl/README.md, all of them visible here on purpose:
//   one clock, synchronous active-low reset, no latches, no vendor primitives, no delays
//   wire and reg only, so Yosys and Vivado read the same file
//   every branch assigns a default, so no latch can appear
//   combinational logic separated from sequential logic, next state computed before the flop
//
// Behaviour:
//   load_i has priority over counting, counting happens only while en_i is high
//   up_i selects up or down, and the wrap pulses are registered so they are one clock wide
//   carry_o pulses on the clock where the count leaves 255 going up
//   borrow_o pulses on the clock where the count leaves 0 going down

`default_nettype none

module counter8 (
    input  wire       clk_i,       // single clock, 100 MHz on the KV260
    input  wire       rst_ni,      // synchronous reset, active low
    input  wire       en_i,        // count enable, one step per clock while high
    input  wire       up_i,        // 1 counts up, 0 counts down
    input  wire       load_i,      // parallel load, takes priority over counting
    input  wire [7:0] load_val_i,  // value taken when load_i is high
    output reg  [7:0] count_o,     // current count
    output reg        carry_o,     // one clock wide pulse on wrap up, 255 to 0
    output reg        borrow_o,    // one clock wide pulse on wrap down, 0 to 255
    output wire       zero_o,      // count is zero
    output wire       tc_o         // terminal count, count is all ones
);

    // -------------------------------------------------------------------------------------------
    // Next state. Pure combinational, with a default on every path so nothing can latch.
    // -------------------------------------------------------------------------------------------
    reg [7:0] count_next;

    always @(*) begin
        count_next = count_o;
        if (load_i) begin
            count_next = load_val_i;
        end else if (en_i) begin
            count_next = up_i ? (count_o + 8'h01) : (count_o - 8'h01);
        end
    end

    // -------------------------------------------------------------------------------------------
    // State. One flop bank for the count and one flop per wrap flag.
    // -------------------------------------------------------------------------------------------
    always @(posedge clk_i) begin
        if (!rst_ni) begin
            count_o  <= 8'h00;
            carry_o  <= 1'b0;
            borrow_o <= 1'b0;
        end else begin
            count_o  <= count_next;
            carry_o  <= (en_i && !load_i &&  up_i && (count_o == 8'hFF));
            borrow_o <= (en_i && !load_i && !up_i && (count_o == 8'h00));
        end
    end

    // -------------------------------------------------------------------------------------------
    // Status. Combinational, so the flag follows the register output in the same cycle.
    // -------------------------------------------------------------------------------------------
    assign zero_o = (count_o == 8'h00);
    assign tc_o   = (count_o == 8'hFF);

endmodule

`default_nettype wire
