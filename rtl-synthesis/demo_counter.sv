// Reference design for flow checks: an 8-bit counter with a comparator.
// Synthesise this first to confirm the flow works before touching the real pipeline.
// Synchronous reset, one clock, no vendor primitives: the same rules the AFIB-LITE RTL follows.
//
// Verified result with sky130_fd_sc_hd__tt_025C_1v80.lib: 35 cells, 8 flip-flops, 311.55 um^2.
module demo_counter #(
    parameter int WIDTH = 8
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             enable,
    output logic [WIDTH-1:0] count,
    output logic             match
);

    logic [WIDTH-1:0] count_next;

    always_comb begin
        count_next = count + 1'b1;
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            count <= '0;
        end else if (enable) begin
            count <= count_next;
        end
    end

    assign match = (count == {WIDTH{1'b1}});

endmodule
