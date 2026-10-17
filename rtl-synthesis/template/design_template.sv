// Template for one synthesisable block of AFIB-LITE.
//
// Copy this file, rename the module, keep the port list, and fill in the body. Keep the rules below:
// the same file has to survive two backends, Yosys for the SKY130 numbers and Vivado for the KV260
// build.
//
//   one clock, synchronous active-low reset, no latches, no vendor primitives
//   one sample stream in: 16-bit word with 12 significant bits, valid, last
//   fixed point throughout, with the binary point of every signal written down
//   no delays and no initial blocks in synthesisable code
//   wire and reg instead of logic, so every tool in the chain accepts the file
//
// Run all three before you trust any number:
//   ./run_lint.sh  template/design_template.sv design_template
//   ./run_sim.sh   template/tb_template.sv template/design_template.sv
//   ./run_synth.sh template/design_template.sv design_template

`default_nettype none

module design_template (
    input  wire        clk_i,
    input  wire        rst_ni,     // synchronous, active low

    // sample stream in
    input  wire [15:0] s_tdata,    // 12 significant bits, sign extended by the source
    input  wire        s_tvalid,
    input  wire        s_tlast,

    // decision out, one pulse per window
    output reg         out_valid,
    output reg  [1:0]  out_class,  // 0 normal, 1 atrial fibrillation, 2 undecided
    output reg  [15:0] out_conf    // confidence, 0 to 1000
);

    // Fixed point: write the scale of every signal you add, for example "Q1.15 in units of the
    // average RR interval". Nothing here may depend on simulation-only behaviour, because Vivado and
    // Yosys read the same file.

    reg [15:0] sample_q;
    reg        valid_q;
    reg        last_q;    // window boundary marker, one pulse at the end of a decision window

    always @(posedge clk_i) begin
        if (!rst_ni) begin
            sample_q  <= 16'd0;
            valid_q   <= 1'b0;
            last_q    <= 1'b0;
            out_valid <= 1'b0;
            out_class <= 2'd0;
            out_conf  <= 16'd0;
        end else begin
            // Stage 1: register the incoming sample. Replace the placeholder below with the real
            // stage, one stage at a time, and keep the simulation check green after each change.
            sample_q  <= s_tdata;
            valid_q   <= s_tvalid;
            last_q    <= s_tlast;

            // Placeholder output. It forwards the registered sample at the window boundary so that
            // every port and the handshake are exercised end to end. Verilator treats an unread
            // signal as a failure, so either use a signal or delete it, and never leave one behind.
            out_valid <= valid_q;
            out_class <= 2'd2;
            out_conf  <= last_q ? sample_q : 16'd0;
        end
    end

endmodule

`default_nettype wire
