// Stage 4 of the AFIB-LITE pipeline in miniature: a 37-sample moving average of a 12-bit sample
// stream. At 250 Hz that window is the 150 ms integration window of the Pan-Tompkins chain.
// Signed arithmetic, one clock, synchronous reset. The divide by 37 is deliberate: it is what the
// real design does, and it costs cells, which is the number this flow exists to measure.
//
// Verified result with sky130_fd_sc_hd__tt_025C_1v80.lib: 1,396 cells, 476 flip-flops, 16442.02 um^2.
// Without `dfflibmap` the same design reports 2,752 um^2, because the flip-flops stay unmapped.
module demo_integrator #(
    parameter int WINDOW = 37,
    parameter int IN_W   = 12
) (
    input  logic                    clk,
    input  logic                    rst_n,
    input  logic                    sample_valid,
    input  logic signed [IN_W-1:0]  sample_in,
    output logic                    envelope_valid,
    output logic signed [IN_W+6:0]  envelope_out
);

    localparam int SUM_W = IN_W + 6;   // 37 * 2^11 = 75776, so 18 signed bits hold the sum

    logic signed [SUM_W-1:0] shift_reg [WINDOW];
    logic signed [SUM_W-1:0] acc;
    logic signed [SUM_W-1:0] acc_next;
    integer i;

    always_comb begin
        acc_next = acc - shift_reg[WINDOW-1] + {{(SUM_W-IN_W){sample_in[IN_W-1]}}, sample_in};
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            acc            <= '0;
            envelope_out   <= '0;
            envelope_valid <= 1'b0;
            for (i = 0; i < WINDOW; i = i + 1) begin
                shift_reg[i] <= '0;
            end
        end else begin
            envelope_valid <= sample_valid;
            if (sample_valid) begin
                acc          <= acc_next;
                envelope_out <= acc_next / WINDOW;
                for (i = WINDOW-1; i > 0; i = i - 1) begin
                    shift_reg[i] <= shift_reg[i-1];
                end
                shift_reg[0] <= {{(SUM_W-IN_W){sample_in[IN_W-1]}}, sample_in};
            end
        end
    end

endmodule
