// ---------------------------------------------------------------------------
// regs_axi.sv -- register file behind the host bus. Contract profile: apex stage (I1).
//
// Contract: rtl/afib_lite_pkg.sv, signal table marker "TBL|", 43 rows (plan doc 38
// section 3.2). This file is separate from afib_lite_top.sv on purpose so two people can
// work at the same time (plan 3.4, file ownership rule 3).
//
// The AXI4-Lite bus itself is NOT a row of the 43 row signal table: that table is the
// sample, decision and status contract. The bus is the host boundary, and it is placed
// here because plan 8.5 puts the register map behind AXI4-Lite on pl_clk0, the same
// single clock, so there is no clock domain crossing anywhere in the PL.
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 section 3.4 and the
// final map of plan 8.5):
//   RATE_DIV          W_RATE_DIV = 20   D12: 399999 needs 19 bits, 16 bits would only
//                                       reach 1525.88 Hz
//   RATIO_THRESH      16                field, in 1/200 units
//   ENTROPY_THRESH    16                field, in 1/100 units
//   ARM_SELECT        5                 b0 ratio, b1 entropy, b2 T-wave rule,
//                                       b3 marked series source, b4 both arms required
//   WINDOW_STEP       8                 stride in beats
//   WINDOW_BEATS      8                 window length in beats
// Saturation points: none. Fields are truncated to the declared widths and no counter
//   lives in this file, so nothing can overflow here. The FIFO overflow of the sample
//   input path is counted elsewhere and reported through i_status.
// Rounding rule: none. Pure register load and store.
// Model lines this file mirrors: the register map is a bring-up artifact and has no
//   model counterpart. The values it resets to come from the model: RATE_DIV_RST 399999
//   at rantai.py:631 rate arithmetic, RATIO_THRESH_RST 33 and ENTROPY_THRESH_RST 63 at
//   rantai.py:831 threshold grid, ARM_SELECT_RST 5'h0F which is the model's current
//   default arm set (rantai.py:799-801).
//
// Register map, offsets from the final map of plan 8.5. Fase 1 freezes the D8 minimum
// subset: VERSION_ID, SCRATCH, CTRL, STATUS, RATE_DIV, the two triage thresholds and the
// two window parameters. The remaining slots land in Fase 11.
//   0x00 CTRL            RW   reset 0x00000000
//   0x04 STATUS          RO   read only, assembled by the top level and passed in
//   0x64 VERSION_ID      RO   reset 0x00010001, low half RTL revision, high half fixture
//   0x68 SCRATCH         RW   reset 0x00000000, bus write-read proof
//   0x3C RATIO_THRESH    RW   reset 33
//   0x40 ENTROPY_THRESH  RW   reset 63
//   0x44 ARM_SELECT      RW   reset 5'h0F
//   0x54 RATE_DIV        RW   reset 399999
// The offset values above are the map, not measurements, so they are written here as
// address literals with the plan 8.5 offset in the comment on each decode arm.
//
// Fixed latency: one cycle for a write response and one cycle for a read response.
//
// Fase 1 status: PLACEHOLDER. Byte lanes are not honoured (s_axi_wstrb is used only as a
// write-enable qualifier) and the counter registers of the full map are absent. Fase 11
// owns the complete 36 slot map and the byte lanes.
// House style: wire and reg only (D10), one clock, synchronous active low reset.
// ---------------------------------------------------------------------------
`default_nettype none

module regs_axi #(
    parameter int unsigned W_RATE_DIV = afib_lite_pkg::W_RATE_DIV,
    parameter int unsigned AW         = 8
) (
    input  wire                     clk_i,
    input  wire                     rst_ni,

    // AXI4-Lite slave, one clock, no clock domain crossing
    input  wire [AW-1:0]            s_axi_awaddr,
    input  wire                     s_axi_awvalid,
    output wire                     s_axi_awready,
    input  wire [31:0]              s_axi_wdata,
    input  wire [3:0]               s_axi_wstrb,
    input  wire                     s_axi_wvalid,
    output wire                     s_axi_wready,
    output wire [1:0]               s_axi_bresp,
    output wire                     s_axi_bvalid,
    input  wire                     s_axi_bready,
    input  wire [AW-1:0]            s_axi_araddr,
    input  wire                     s_axi_arvalid,
    output wire                     s_axi_arready,
    output wire [31:0]              s_axi_rdata,
    output wire [1:0]               s_axi_rresp,
    output wire                     s_axi_rvalid,
    input  wire                     s_axi_rready,

    // status in, assembled by the top level
    input  wire [31:0]              i_status,
    input  wire [4:0]               i_irq,

    // configuration out, the D8 minimum subset
    output reg                      o_enable,
    output reg                      o_clear_counters,
    output reg  [W_RATE_DIV-1:0]    o_rate_div,
    output reg  [15:0]              o_ratio_thresh,
    output reg  [15:0]              o_entropy_thresh,
    output reg  [4:0]               o_arm_select,
    output reg  [7:0]               o_window_step,
    output reg  [7:0]               o_window_beats
);

    // register offsets, plan 8.5 final map
    localparam logic [AW-1:0] ADDR_CTRL      = 8'h00;
    localparam logic [AW-1:0] ADDR_STATUS    = 8'h04;
    localparam logic [AW-1:0] ADDR_RATIO     = 8'h3C;
    localparam logic [AW-1:0] ADDR_ENTROPY   = 8'h40;
    localparam logic [AW-1:0] ADDR_ARM       = 8'h44;
    localparam logic [AW-1:0] ADDR_RATE_DIV  = 8'h54;
    localparam logic [AW-1:0] ADDR_VERSION   = 8'h64;
    localparam logic [AW-1:0] ADDR_SCRATCH   = 8'h68;
    // GAP, reported, not resolved silently: the D8 minimum subset frozen in plan 13.3
    // requires the window parameters in registers, while the final 36 slot map of plan
    // 8.5 carries no window parameter slot (0x00 to 0x8C is fully assigned). These two
    // addresses therefore sit above the frozen map and are provisional until the owner
    // places them. Nothing else in the map is displaced.
    localparam logic [AW-1:0] ADDR_WIN_STEP  = 8'h90;
    localparam logic [AW-1:0] ADDR_WIN_BEATS = 8'h94;

    localparam logic [15:0] VERSION_ID_RST = 16'h0001;  // low half RTL revision, plan 8.5 finding H

    reg [31:0] ctrl_q;
    reg [31:0] scratch_q;
    reg        bvalid_q;
    reg        rvalid_q;
    reg [31:0] rdata_q;

    wire wr_en = s_axi_awvalid & s_axi_wvalid & s_axi_awready & s_axi_wready & (|s_axi_wstrb);
    wire rd_en = s_axi_arvalid & s_axi_arready;

    assign s_axi_awready = ~bvalid_q;
    assign s_axi_wready  = ~bvalid_q;
    assign s_axi_arready = ~rvalid_q;
    assign s_axi_bvalid  = bvalid_q;
    assign s_axi_bresp   = 2'b00;   // OKAY, no error response in the placeholder
    assign s_axi_rvalid  = rvalid_q;
    assign s_axi_rresp   = 2'b00;
    assign s_axi_rdata   = rdata_q;

    always @(posedge clk_i) begin
        if (!rst_ni) begin
            ctrl_q          <= 32'd0;
            scratch_q       <= 32'd0;
            bvalid_q        <= 1'b0;
            rvalid_q        <= 1'b0;
            rdata_q         <= 32'd0;
            o_enable        <= 1'b0;
            o_clear_counters<= 1'b0;
            o_rate_div      <= afib_lite_pkg::RATE_DIV_RST;
            o_ratio_thresh  <= afib_lite_pkg::RATIO_THRESH_RST;
            o_entropy_thresh<= afib_lite_pkg::ENTROPY_THRESH_RST;
            o_arm_select    <= afib_lite_pkg::ARM_SELECT_RST;
            o_window_step   <= afib_lite_pkg::WINDOW_STEP_FIELD;
            o_window_beats  <= afib_lite_pkg::WINDOW_BEATS_FIELD;
        end else begin
            // write response, fixed latency of one cycle
            if (bvalid_q) begin
                bvalid_q <= ~s_axi_bready;
            end else if (wr_en) begin
                bvalid_q <= 1'b1;
            end

            // read response, fixed latency of one cycle
            if (rvalid_q) begin
                rvalid_q <= ~s_axi_rready;
            end else if (rd_en) begin
                rvalid_q <= 1'b1;
            end

            if (wr_en) begin
                case (s_axi_awaddr)
                    ADDR_CTRL: begin
                        ctrl_q            <= s_axi_wdata;
                        o_enable          <= s_axi_wdata[0];
                        o_clear_counters  <= s_axi_wdata[2];
                    end
                    ADDR_RATIO:     o_ratio_thresh   <= s_axi_wdata[15:0];
                    ADDR_ENTROPY:   o_entropy_thresh <= s_axi_wdata[15:0];
                    ADDR_ARM:       o_arm_select     <= s_axi_wdata[4:0];
                    ADDR_RATE_DIV:  o_rate_div       <= s_axi_wdata[W_RATE_DIV-1:0];
                    ADDR_SCRATCH:   scratch_q        <= s_axi_wdata;
                    ADDR_WIN_STEP:  o_window_step   <= s_axi_wdata[7:0];
                    ADDR_WIN_BEATS: o_window_beats  <= s_axi_wdata[7:0];
                    default: ;  // unmapped slot: the full 36 slot map lands in Fase 11
                endcase
            end

            if (rd_en) begin
                case (s_axi_araddr)
                    ADDR_CTRL:      rdata_q <= ctrl_q;
                    ADDR_STATUS:    rdata_q <= i_status;
                    ADDR_RATIO:     rdata_q <= {16'd0, o_ratio_thresh};
                    ADDR_ENTROPY:   rdata_q <= {16'd0, o_entropy_thresh};
                    ADDR_ARM:       rdata_q <= {27'd0, o_arm_select};
                    ADDR_RATE_DIV:  rdata_q <= {{(32-W_RATE_DIV){1'b0}}, o_rate_div};
                    ADDR_VERSION:   rdata_q <= {16'd0, VERSION_ID_RST};
                    ADDR_SCRATCH:   rdata_q <= scratch_q;
                    ADDR_WIN_STEP:  rdata_q <= {24'd0, o_window_step};
                    ADDR_WIN_BEATS: rdata_q <= {24'd0, o_window_beats};
                    default:        rdata_q <= {27'd0, i_irq};
                endcase
            end
        end
    end

endmodule

`default_nettype wire
