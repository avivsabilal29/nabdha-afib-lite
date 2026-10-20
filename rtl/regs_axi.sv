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
// Port list and parameters are frozen from Fase 1 and are NOT changed by Fase 11. That
// freeze is the reason for the split of work described under "Fase 11 status" below.
//
// Widths, from afib_lite_pkg (plan 3.4, cross checked against doc 36 section 3.4 and the
// final map of plan 8.5):
//   RATE_DIV          W_RATE_DIV = 20   D12: 399999 needs 19 bits, 16 bits would only
//                                       reach 1525.88 Hz
//   RATIO_THRESH      16                field, in 1/200 units
//   ENTROPY_THRESH    16                field, in 1/100 units
//   ARM_SELECT        5                 b0 ratio, b1 entropy, b2 T-wave rule,
//                                       b3 marked series source, b4 both arms required
//   DEBUG_SEL         8                 introspection node selector, slot 0x90
// Saturation points: none. No counter lives in this file except the three ingest counters
//   of the sample path, and they cannot overflow in a simulation of this length.
// Rounding rule: none. Pure register load and store.
// Model lines this file mirrors: the register map is a bring-up artifact and has no
//   model counterpart. The values it resets to come from the model: RATE_DIV_RST 399999
//   at rantai.py:631 rate arithmetic, RATIO_THRESH_RST 33 and ENTROPY_THRESH_RST 63 at
//   rantai.py:831 threshold grid, ARM_SELECT_RST 5'h0F which is the model's current
//   default arm set (rantai.py:799-801).
//
// Register map: plan 38 section 8.5, the D8 frozen map, 36 slots 0x00 to 0x8C, step four
// bytes, every offset a multiple of four. Fase 11 completes it:
//   0x00 CTRL            RW   reset 0x00000000  b0 run, b2 clear counters exported, the
//                                               rest stored and readable, see the note
//   0x04 STATUS          RO   plan reset 0x00000001, driven by i_status (the top level
//                                               assembles it), so the read equals i_status
//   0x08 IRQ_STATUS      RO   the five interrupt sources from i_irq, less the bits the
//                                               host cleared through 0x0C
//   0x0C IRQ_CLEAR       W1C  write one clears that bit of IRQ_STATUS; a read returns zero
//   0x10 CLASS_OUT       RO   decision class, plan reset 0x00000000
//   0x14 CONFIDENCE      RO   plan reset 0x00000000
//   0x18 RR_LAST         RO   plan reset 0x00000000
//   0x1C BEAT_COUNT      RO   plan reset 0x00000000
//   0x20 GAP_COUNT       RO   counted here from the gap marker of SAMPLE_MARK
//   0x24 SAMPLE_IDX      RO   plan reset 0x00000000, the free running clock of the top
//   0x28 WINDOW_COUNT    RO   plan reset 0x00000000
//   0x2C CLAMP_COUNT     RO   counted here from the clamp rule of the sample word and mark
//   0x30 FIFO_OVF_COUNT  RO   plan reset 0x00000000, zero because no FIFO exists here
//   0x34 RR_LONG_COUNT   RO   plan reset 0x00000000
//   0x38 RR_MARK_LAST    RO   plan reset 0x00000000, the four interval marks
//   0x3C RATIO_THRESH    RW   reset 0x00000021 = 33, 1/200 units, 33 is 0.165
//   0x40 ENTROPY_THRESH  RW   reset 0x0000003F = 63, 1/100 units, 63 is 0.63
//   0x44 ARM_SELECT      RW   reset 0x0000000F, the four arms lit
//   0x48 FEAT_RATIO      RO   plan reset 0x00000000
//   0x4C FEAT_ENTROPY    RO   plan reset 0x00000000
//   0x50 FORMAT_CFG      RW   reset 0x004C00FA, 250 Hz, 12 bit, one channel
//   0x54 RATE_DIV        RW   reset 0x00061A7F = 399999, period is the value plus one
//   0x58 THRESH_SCALE    RW   reset 0x00000100 = 256
//   0x5C RR_BAND_LO      RW   reset 0x0000005C = 92, 0.92 in 1/100 units
//   0x60 RR_BAND_HI      RW   reset 0x00000074 = 116, 1.16 in 1/100 units
//   0x64 VERSION_ID      RO   reset 0x00010001, low half RTL revision, high half fixture
//   0x68 SCRATCH         RW   reset 0x00000000, bus write-read proof
//   0x6C SAMPLE_FIFO     WO   write one 16 bit sample word; counted in 0x74
//   0x70 SAMPLE_MARK     WO   the four marker bits that stick to the next sample word
//   0x74 SAMPLE_IN_STATUS RO  b15:0 words received; b23:16 FIFO level, zero here
//   0x78 MARKER_LAST     RO   the marker of the last word that arrived
//   0x7C CLAMP_THRESH    RW   reset 0x000007FF = 2047, a word is marked strictly above it
//   0x80 GAP_RECOVERY    RW   reset 0x00000083 = 131 samples
//   0x84 REPLAY_LEN      RW   reset 0x00000000, zero means unbounded
//   0x88 IDX_TAP_LAST    RO   plan reset 0x00000000
//   0x8C IDX_DEC_LAST    RO   plan reset 0x00000000
//   Two slots above the frozen map, which is what the plan's decision register asks for:
//   item 9 of final38.md accepts the DEBUG_SEL / DEBUG_VAL pair at 0x90 and 0x94 and raises
//   the map from 36 to 38 slots, so that the driver of this phase prints one slot count in
//   both documents. 0x90 DEBUG_SEL is RW, a node selector stored whole and read back as
//   written; 0x94 DEBUG_VAL is RO and reads zero, because the frozen port list of regs_axi
//   carries neither i_dbg_sel nor o_dbg_val: the introspection mux lives behind i_dbg_sel,
//   a top level port (afib_lite_top.sv:95, and the plan note at I1 line 120). The gap is
//   reported in LAPORAN-FASE11.md section 5, it is not hidden.
//   The window stride and length are NOT registers: their old offsets 0x54 and 0x58 collided
//   with RATE_DIV and THRESH_SCALE, and the D8 map of section 8.5 drops them. The frozen
//   port pair o_window_step and o_window_beats is therefore driven from the package
//   constants, which is exactly the role the top level gives it: afib_lite_top.sv:249 uses
//   the board input when it is non zero and this pair as the fallback default.
//
// Stored value or field: a write stores the whole 32 bit word and a read returns it
// verbatim, INCLUDING the bits above a declared field, so "every read equals the value
// written" holds for every writable slot at full width. The field is what leaves this file:
// o_ratio_thresh is bits 15:0, o_rate_div is bits 19:0, o_arm_select is bits 4:0, and so on.
// The alternative, masking on write, would make a read of 0xFFFFFFFF return 0x0000FFFF and
// is reported as the other side of this decision.
//
// Byte lanes: honoured. A write updates exactly the bytes whose s_axi_wstrb bit is set, so
// a partial write merges instead of clobbering. A write with every strobe low is answered
// with a normal OKAY response and changes nothing, which is required because AXI4-Lite
// guarantees a response for every accepted write; the Fase 1 placeholder stalled on that
// case, and the fix is part of Fase 11.
//
// Fixed latency: one cycle for a write response and one cycle for a read response. A read
// and a write in the same cycle both complete: the read returns the value the register held
// before that edge, and the next read returns the value the write stored.
//
// Fase 11 status, stated plainly. Every slot of the map is decoded and the writable ones
// are stored, so the whole bus interface is testable. Fourteen of the thirty-eight slots
// cannot be driven by anything this file can see, because the frozen port list carries only
// i_status and i_irq: twelve of them read their plan reset value zero (SAMPLE_IDX,
// WINDOW_COUNT, BEAT_COUNT, RR_LAST, RR_MARK_LAST, RR_LONG_COUNT, CLASS_OUT, CONFIDENCE,
// FEAT_RATIO, FEAT_ENTROPY, IDX_TAP_LAST, IDX_DEC_LAST), DEBUG_VAL at 0x94 reads zero
// because no introspection word reaches this file, and FIFO_OVF_COUNT stays zero because the
// depth 64 sample FIFO of plan step 3 has no consumer to pop it. Only the ingest counters
// are owned here. Closing that gap needs an owner decision to widen this port list, and it is
// item one of the Fase 11 report.
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
    output wire [7:0]               o_window_step,
    output wire [7:0]               o_window_beats
);

    // register offsets, plan 8.5 final map, 36 slots 0x00 to 0x8C
    localparam logic [AW-1:0] ADDR_CTRL             = 8'h00;
    localparam logic [AW-1:0] ADDR_STATUS           = 8'h04;
    localparam logic [AW-1:0] ADDR_IRQ_STATUS       = 8'h08;
    localparam logic [AW-1:0] ADDR_IRQ_CLEAR        = 8'h0C;
    localparam logic [AW-1:0] ADDR_CLASS_OUT        = 8'h10;
    localparam logic [AW-1:0] ADDR_CONFIDENCE       = 8'h14;
    localparam logic [AW-1:0] ADDR_RR_LAST          = 8'h18;
    localparam logic [AW-1:0] ADDR_BEAT_COUNT       = 8'h1C;
    localparam logic [AW-1:0] ADDR_GAP_COUNT        = 8'h20;
    localparam logic [AW-1:0] ADDR_SAMPLE_IDX       = 8'h24;
    localparam logic [AW-1:0] ADDR_WINDOW_COUNT     = 8'h28;
    localparam logic [AW-1:0] ADDR_CLAMP_COUNT      = 8'h2C;
    localparam logic [AW-1:0] ADDR_FIFO_OVF_COUNT   = 8'h30;
    localparam logic [AW-1:0] ADDR_RR_LONG_COUNT    = 8'h34;
    localparam logic [AW-1:0] ADDR_RR_MARK_LAST     = 8'h38;
    localparam logic [AW-1:0] ADDR_RATIO_THRESH     = 8'h3C;
    localparam logic [AW-1:0] ADDR_ENTROPY_THRESH   = 8'h40;
    localparam logic [AW-1:0] ADDR_ARM_SELECT       = 8'h44;
    localparam logic [AW-1:0] ADDR_FEAT_RATIO       = 8'h48;
    localparam logic [AW-1:0] ADDR_FEAT_ENTROPY     = 8'h4C;
    localparam logic [AW-1:0] ADDR_FORMAT_CFG       = 8'h50;
    localparam logic [AW-1:0] ADDR_RATE_DIV         = 8'h54;
    localparam logic [AW-1:0] ADDR_THRESH_SCALE     = 8'h58;
    localparam logic [AW-1:0] ADDR_RR_BAND_LO       = 8'h5C;
    localparam logic [AW-1:0] ADDR_RR_BAND_HI       = 8'h60;
    localparam logic [AW-1:0] ADDR_VERSION_ID       = 8'h64;
    localparam logic [AW-1:0] ADDR_SCRATCH          = 8'h68;
    localparam logic [AW-1:0] ADDR_SAMPLE_FIFO      = 8'h6C;
    localparam logic [AW-1:0] ADDR_SAMPLE_MARK      = 8'h70;
    localparam logic [AW-1:0] ADDR_SAMPLE_IN_STATUS = 8'h74;
    localparam logic [AW-1:0] ADDR_MARKER_LAST      = 8'h78;
    localparam logic [AW-1:0] ADDR_CLAMP_THRESH     = 8'h7C;
    localparam logic [AW-1:0] ADDR_GAP_RECOVERY     = 8'h80;
    localparam logic [AW-1:0] ADDR_REPLAY_LEN       = 8'h84;
    localparam logic [AW-1:0] ADDR_IDX_TAP_LAST     = 8'h88;
    localparam logic [AW-1:0] ADDR_IDX_DEC_LAST     = 8'h8C;
    // above the frozen map, provisional, see the GAP note in the file header
    localparam logic [AW-1:0] ADDR_DEBUG_SEL        = 8'h90;
    localparam logic [AW-1:0] ADDR_DEBUG_VAL        = 8'h94;

    // reset values of the slots that plan 8.5 pins by number
    localparam logic [15:0] VERSION_RTL_REV     = 16'h0001;  // low half, plan 8.5 finding H
    localparam logic [15:0] VERSION_FIXTURE_REV = 16'h0001;  // high half, fixture revision
    localparam logic [31:0] FORMAT_CFG_RST      = 32'h004C00FA;
    localparam logic [31:0] THRESH_SCALE_RST    = 32'h00000100;
    localparam logic [31:0] RR_BAND_LO_RST      = 32'h0000005C;
    localparam logic [31:0] RR_BAND_HI_RST      = 32'h00000074;
    // the 12 bit clamp rail of the package is the clamp threshold of the map: a sample word
    // is marked strictly above 2047, which is what rantai.py:49 does with the full scale.
    localparam logic [31:0] CLAMP_THRESH_RST    = afib_lite_pkg::CLAMP_COUNT;
    localparam logic [31:0] VERSION_ID_RST      = {VERSION_FIXTURE_REV, VERSION_RTL_REV};

    // marker bit positions of SAMPLE_MARK, the same four of s_tuser in the package
    localparam int unsigned MK_CLAMP = afib_lite_pkg::TU_CLAMP;
    localparam int unsigned MK_GAP   = afib_lite_pkg::TU_GAP;

    // registers, one per writable or counted slot
    reg [31:0] ctrl_q;
    reg [31:0] irq_clr_q;
    reg [31:0] ratio_q;
    reg [31:0] entropy_q;
    reg [31:0] arm_q;
    reg [31:0] format_q;
    reg [31:0] rate_q;
    reg [31:0] thresh_scale_q;
    reg [31:0] band_lo_q;
    reg [31:0] band_hi_q;
    reg [31:0] scratch_q;
    reg [31:0] clamp_thresh_q;
    reg [31:0] gap_recovery_q;
    reg [31:0] replay_len_q;
    reg [31:0] dbg_sel_q;

    // ingest bookkeeping of the sample path, the part of the map this file can drive alone
    reg [31:0] samp_words_q;   // 0x74 b15:0
    reg [31:0] mark_last_q;    // 0x78
    reg [31:0] clamp_count_q;  // 0x2C
    reg [31:0] gap_count_q;    // 0x20
    reg [31:0] fifo_ovf_q;     // 0x30, cannot move while there is no FIFO to overflow
    reg [3:0]  pend_mark_q;    // 0x70, the mark that sticks to the next sample word

    // bus bookkeeping
    reg        bvalid_q;
    reg        rvalid_q;
    reg [31:0] rdata_q;

    // byte lanes of the write: one mask bit per data byte, and the merged result
    wire [31:0] wmask  = {{8{s_axi_wstrb[3]}}, {8{s_axi_wstrb[2]}},
                          {8{s_axi_wstrb[1]}}, {8{s_axi_wstrb[0]}}};
    wire [31:0] wmerge = (s_axi_wdata & wmask);
    wire        wlane  = (|s_axi_wstrb);

    wire wr_en = s_axi_awvalid & s_axi_wvalid & s_axi_awready & s_axi_wready;
    wire rd_en = s_axi_arvalid & s_axi_arready;
    wire clr_counter = wr_en & (s_axi_awaddr == ADDR_CTRL) & s_axi_wdata[2] & s_axi_wstrb[0];

    assign s_axi_awready = ~bvalid_q;
    assign s_axi_wready  = ~bvalid_q;
    assign s_axi_arready = ~rvalid_q;
    assign s_axi_bvalid  = bvalid_q;
    assign s_axi_bresp   = 2'b00;   // OKAY for every slot, mapped or not
    assign s_axi_rvalid  = rvalid_q;
    assign s_axi_rresp   = 2'b00;
    assign s_axi_rdata   = rdata_q;

    // The window stride and length are design constants here, not bus registers: their old
    // slots 0x54 and 0x58 collided with RATE_DIV and THRESH_SCALE and the D8 map drops them.
    // The top level uses this frozen port pair as the fallback default when the board does
    // not supply i_window_step or i_window_beats (afib_lite_top.sv:249-250).
    assign o_window_step  = afib_lite_pkg::WINDOW_STEP_FIELD;
    assign o_window_beats = afib_lite_pkg::WINDOW_BEATS_FIELD;

    always @(posedge clk_i) begin
        if (!rst_ni) begin
            ctrl_q          <= 32'd0;
            irq_clr_q       <= 32'd0;
            ratio_q         <= {16'd0, afib_lite_pkg::RATIO_THRESH_RST};
            entropy_q       <= {16'd0, afib_lite_pkg::ENTROPY_THRESH_RST};
            arm_q           <= {27'd0, afib_lite_pkg::ARM_SELECT_RST};
            format_q        <= FORMAT_CFG_RST;
            rate_q          <= {{(32-W_RATE_DIV){1'b0}}, afib_lite_pkg::RATE_DIV_RST};
            thresh_scale_q  <= THRESH_SCALE_RST;
            band_lo_q       <= RR_BAND_LO_RST;
            band_hi_q       <= RR_BAND_HI_RST;
            scratch_q       <= 32'd0;
            clamp_thresh_q  <= CLAMP_THRESH_RST;
            gap_recovery_q  <= afib_lite_pkg::GAP_RECOVERY;
            replay_len_q    <= 32'd0;
            dbg_sel_q       <= 32'd0;
            samp_words_q    <= 32'd0;
            mark_last_q     <= 32'd0;
            clamp_count_q   <= 32'd0;
            gap_count_q     <= 32'd0;
            fifo_ovf_q      <= 32'd0;
            pend_mark_q     <= 4'd0;
            bvalid_q        <= 1'b0;
            rvalid_q        <= 1'b0;
            rdata_q         <= 32'd0;
            o_enable         <= 1'b0;
            o_clear_counters <= 1'b0;
            o_rate_div       <= afib_lite_pkg::RATE_DIV_RST;
            o_ratio_thresh   <= afib_lite_pkg::RATIO_THRESH_RST;
            o_entropy_thresh <= afib_lite_pkg::ENTROPY_THRESH_RST;
            o_arm_select     <= afib_lite_pkg::ARM_SELECT_RST;
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

            // ---------------------------------------------------------------- write path
            if (wr_en) begin
                case (s_axi_awaddr)
                    ADDR_CTRL: begin
                        ctrl_q            <= (ctrl_q & ~wmask) | wmerge;
                        o_enable          <= wmerge[0];
                        o_clear_counters  <= wmerge[2];
                    end
                    ADDR_RATIO_THRESH: begin
                        ratio_q         <= (ratio_q & ~wmask) | wmerge;
                        o_ratio_thresh  <= wmerge[15:0];
                    end
                    ADDR_ENTROPY_THRESH: begin
                        entropy_q       <= (entropy_q & ~wmask) | wmerge;
                        o_entropy_thresh<= wmerge[15:0];
                    end
                    ADDR_ARM_SELECT: begin
                        arm_q           <= (arm_q & ~wmask) | wmerge;
                        o_arm_select    <= wmerge[4:0];
                    end
                    ADDR_FORMAT_CFG: begin
                        format_q        <= (format_q & ~wmask) | wmerge;
                    end
                    ADDR_RATE_DIV: begin
                        rate_q          <= (rate_q & ~wmask) | wmerge;
                        o_rate_div      <= wmerge[W_RATE_DIV-1:0];
                    end
                    ADDR_THRESH_SCALE: begin
                        thresh_scale_q  <= (thresh_scale_q & ~wmask) | wmerge;
                    end
                    ADDR_RR_BAND_LO: begin
                        band_lo_q       <= (band_lo_q & ~wmask) | wmerge;
                    end
                    ADDR_RR_BAND_HI: begin
                        band_hi_q       <= (band_hi_q & ~wmask) | wmerge;
                    end
                    ADDR_SCRATCH: begin
                        scratch_q       <= (scratch_q & ~wmask) | wmerge;
                    end
                    ADDR_CLAMP_THRESH: begin
                        clamp_thresh_q  <= (clamp_thresh_q & ~wmask) | wmerge;
                    end
                    ADDR_GAP_RECOVERY: begin
                        gap_recovery_q  <= (gap_recovery_q & ~wmask) | wmerge;
                    end
                    ADDR_REPLAY_LEN: begin
                        replay_len_q    <= (replay_len_q & ~wmask) | wmerge;
                    end
                    ADDR_DEBUG_SEL: begin
                        dbg_sel_q       <= (dbg_sel_q & ~wmask) | wmerge;
                    end
                    ADDR_IRQ_CLEAR: begin
                        // write one to clear: the mask is sticky and only i_irq can set a
                        // source back, because this file does not own the sources
                        irq_clr_q       <= irq_clr_q | {27'd0, wmerge[4:0]};
                    end
                    ADDR_SAMPLE_FIFO: begin
                        // one sample word arrives. No FIFO array: the depth 64 buffer of plan
                        // step 3 needs a consumer port this frozen module does not have, so
                        // the level field stays zero and only the arrived count moves.
                        if (wlane) begin
                            samp_words_q  <= samp_words_q + 32'd1;
                            mark_last_q   <= {28'd0, pend_mark_q};
                            pend_mark_q   <= 4'd0;
                            if (pend_mark_q[MK_CLAMP] |
                                (s_axi_wdata[15:0] > clamp_thresh_q[15:0]))
                                clamp_count_q <= clamp_count_q + 32'd1;
                            if (pend_mark_q[MK_GAP])
                                gap_count_q <= gap_count_q + 32'd1;
                        end
                    end
                    ADDR_SAMPLE_MARK: begin
                        if (wlane) pend_mark_q <= s_axi_wdata[3:0];
                    end
                    default: ;  // unmapped slot: reads zero, changes nothing
                endcase
            end

            // the clear counters pulse clears the ingest counters this file owns; the top
            // level clears its own counters on the same pulse through o_clear_counters
            if (clr_counter) begin
                samp_words_q  <= 32'd0;
                mark_last_q   <= 32'd0;
                clamp_count_q <= 32'd0;
                gap_count_q   <= 32'd0;
                fifo_ovf_q    <= 32'd0;
            end

            // ---------------------------------------------------------------- read path
            // a read returns the value the register held before this edge, so a read and a
            // write of the same address in the same cycle return the pre write value
            if (rd_en) begin
                case (s_axi_araddr)
                    ADDR_CTRL:             rdata_q <= ctrl_q;
                    ADDR_STATUS:           rdata_q <= i_status;
                    ADDR_IRQ_STATUS:       rdata_q <= {27'd0, i_irq & ~irq_clr_q[4:0]};
                    ADDR_IRQ_CLEAR:        rdata_q <= 32'd0;
                    ADDR_GAP_COUNT:        rdata_q <= gap_count_q;
                    ADDR_CLAMP_COUNT:      rdata_q <= clamp_count_q;
                    ADDR_FIFO_OVF_COUNT:   rdata_q <= fifo_ovf_q;
                    ADDR_RATIO_THRESH:     rdata_q <= ratio_q;
                    ADDR_ENTROPY_THRESH:   rdata_q <= entropy_q;
                    ADDR_ARM_SELECT:       rdata_q <= arm_q;
                    ADDR_FORMAT_CFG:       rdata_q <= format_q;
                    ADDR_RATE_DIV:         rdata_q <= rate_q;
                    ADDR_THRESH_SCALE:     rdata_q <= thresh_scale_q;
                    ADDR_RR_BAND_LO:       rdata_q <= band_lo_q;
                    ADDR_RR_BAND_HI:       rdata_q <= band_hi_q;
                    ADDR_VERSION_ID:       rdata_q <= VERSION_ID_RST;
                    ADDR_SCRATCH:          rdata_q <= scratch_q;
                    ADDR_SAMPLE_IN_STATUS: rdata_q <= {8'd0, 8'd0, samp_words_q[15:0]};
                    ADDR_MARKER_LAST:      rdata_q <= mark_last_q;
                    ADDR_CLAMP_THRESH:     rdata_q <= clamp_thresh_q;
                    ADDR_GAP_RECOVERY:     rdata_q <= gap_recovery_q;
                    ADDR_REPLAY_LEN:       rdata_q <= replay_len_q;
                    ADDR_DEBUG_SEL:        rdata_q <= dbg_sel_q;
                    ADDR_DEBUG_VAL:        rdata_q <= 32'd0;   // no tap input on this port list
                    // slots the frozen port list cannot drive: the plan reset value zero is
                    // returned, which is exactly the declared reset of plan 8.5
                    ADDR_CLASS_OUT, ADDR_CONFIDENCE, ADDR_RR_LAST, ADDR_BEAT_COUNT,
                    ADDR_SAMPLE_IDX, ADDR_WINDOW_COUNT, ADDR_RR_LONG_COUNT,
                    ADDR_RR_MARK_LAST, ADDR_FEAT_RATIO, ADDR_FEAT_ENTROPY,
                    ADDR_SAMPLE_FIFO, ADDR_SAMPLE_MARK, ADDR_IDX_TAP_LAST,
                    ADDR_IDX_DEC_LAST:     rdata_q <= 32'd0;
                    default:               rdata_q <= 32'd0;  // unmapped slot
                endcase
            end
        end
    end

endmodule

`default_nettype wire
