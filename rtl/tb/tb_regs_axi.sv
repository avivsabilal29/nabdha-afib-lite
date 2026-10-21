`default_nettype none
// ---------------------------------------------------------------------------
// tb_regs_axi.sv -- Fase 11 of plan 38: the AXI4-Lite register file of regs_axi.sv.
//
// Gates of Fase 11 (plan section 12, line 128) and where each one is closed here:
//   1. "every read equals the value written". Section ROUND TRIP writes six patterns to
//      every writable slot of the map with all four byte lanes and compares the read with
//      the written word, then compares it again with an INDEPENDENT mirror this testbench
//      keeps and updates with the same byte lane rule. Section PARTIAL does the same with
//      six partial strobe patterns, where the expectation is built from the mirror and the
//      strobe mask alone, never from the DUT. Every comparison is counted and printed, and
//      the count of comparisons has to be non zero: "PASS with words compared: 0" is a
//      failure here, like everywhere else in this repository.
//   2. "ARM_SELECT turns the T wave rule arm off and the result equals the fixture of that
//      arm". Section ARM RUNS writes ARM_SELECT through the bus, reads it back, and then
//      scores the frozen feature columns of the arm that the register selects, using the
//      thresholds READ BACK FROM THE REGISTER FILE, against the fixture class column of
//      that arm: 602 windows for the marked series arm and 588 windows for the raw series
//      arm, with the confusion counts (fired, TP, FP, FN, TN) checked against the counts
//      vector that comes from the frozen manifest. Both candidate bit attributions of the
//      raw arm are run and printed: b2 cleared (0x0B, the mapping of the task brief) and b3
//      cleared (0x07, the mapping of the Fase 9 vector export of this tree). The two arms
//      are proved to differ, which is what turns the bit into a gate and not a comment.
//      Before any arm is scored the operating point code is INJECTED through the bus and read
//      back, because the fixture was made at the model operating point while the D8 reset
//      codes (33 in 1/200 units, 63 in 1/100) are the same point in a coarser unit. Section
//      ARM RUNS also checks that the two unit pairs agree to within one LSB of each unit, in
//      integers, and prints both.
//      What this does NOT prove is written in the report: the T wave rule datapath belongs
//      to Fase 7 and the marked series source belongs to Fase 6, not to this file.
//   3. protocol edges: an unmapped address, the reset value of ARM_SELECT after reset, a
//      read and a write in the same cycle, a write with every strobe low, write attempts on
//      read only slots, and the write-one-to-clear behaviour of IRQ_CLEAR.
//
// Every expected number comes from a vector file in +VECTOR (default
// ../rtl/tb/vektor/fase11), 8 hex digits per line, one word per line, written by
// rtl-synthesis/reports/fase11/gen_vektor_fase11.py from the frozen reference data. No
// measured result is written inside this file; the map table below is the register map of
// plan 8.5 transcribed once, and it is checked word for word against the map vectors, so a
// mistyped address fails the run instead of passing silently.
//
// A missing or short vector file stops the run with a fatal, never with a skip.
//
// No file level timescale, on purpose: rtl/afib_lite_pkg.sv carries none and a file level
// timescale here makes Verilator raise TIMESCALEMOD against the package in the lint run.
// The same convention is used by tb_highpass.sv and tb_lowpass.sv. The clock is event
// driven, so the time unit changes no result.
//
// Tool: iverilog 12.0 and vvp from rtl-synthesis/debroot, through run_sim.sh.
// ---------------------------------------------------------------------------
module tb_regs_axi;

    // ------------------------------------------------------------ package constants
    localparam int unsigned W_RATE_DIV = afib_lite_pkg::W_RATE_DIV;
    localparam [W_RATE_DIV-1:0] RATE_RST    = afib_lite_pkg::RATE_DIV_RST;
    localparam [15:0]           RATIO_RST   = afib_lite_pkg::RATIO_THRESH_RST;
    localparam [15:0]           ENTROPY_RST = afib_lite_pkg::ENTROPY_THRESH_RST;
    localparam [4:0]            ARM_RST     = afib_lite_pkg::ARM_SELECT_RST;
    localparam [7:0]            WSTEP_RST   = afib_lite_pkg::WINDOW_STEP_FIELD;
    localparam [7:0]            WBEATS_RST  = afib_lite_pkg::WINDOW_BEATS_FIELD;
    localparam [1:0]            KELAS_NORMAL_B = afib_lite_pkg::KELAS_NORMAL;
    localparam [1:0]            KELAS_REVIEW_B = afib_lite_pkg::KELAS_REVIEW;

    // ------------------------------------------------------------ vector capacities
    // The capacities are the fixture row counts of record 04015. They are checked at run
    // time against the line count of every vector file AND against the counts vector, so a
    // changed fixture fails loudly instead of being truncated.
    localparam integer N_RAW = 588;
    localparam integer N_MARK = 602;
    localparam integer N_MAP = 38;
    localparam integer N_CNT = 31;

    // access kinds of the map vectors
    localparam [1:0] K_RW  = 2'd0;
    localparam [1:0] K_RO  = 2'd1;
    localparam [1:0] K_WO  = 2'd2;
    localparam [1:0] K_W1C = 2'd3;

    // index of every counted value in f11.counts.hex, the same order as the manifest
    localparam integer C_N_MARK = 0,  C_N_RAW = 1,  C_FIRED_MARK = 2, C_FIRED_RAW = 3;
    localparam integer C_TP_MARK = 4, C_FP_MARK = 5, C_FN_MARK = 6, C_TN_MARK = 7;
    localparam integer C_TP_RAW = 8,  C_FP_RAW = 9,  C_FN_RAW = 10,  C_TN_RAW = 11;
    localparam integer C_AFIB_MARK = 12, C_NORMAL_MARK = 13;
    localparam integer C_AFIB_RAW = 14,  C_NORMAL_RAW = 15;
    localparam integer C_RATIO = 16, C_ENT = 17;
    localparam integer C_ARM_DEFAULT = 18, C_ARM_RAW_TREE = 19, C_ARM_T_OFF = 20;
    localparam integer C_ARM_SINGLE = 21, C_GUARD_ENT = 22, C_ARM_EITHER = 23;
    localparam integer C_FIRED_TUNGGAL = 24, C_FIRED_GUARD = 25, C_FIRED_EITHER = 26;
    localparam integer C_TP_EITHER = 27, C_FP_EITHER = 28;
    localparam integer C_MAP_SLOTS = 29, C_FROZEN_SLOTS = 30;

    // expected class column selectors of the arm runs
    localparam integer E_RAW = 0, E_T_OFF = 1, E_MARK = 2;
    localparam integer E_TUNGGAL = 3, E_GUARD = 4, E_EITHER = 5;

    // ------------------------------------------------------------ DUT
    reg          clk_i;
    reg          rst_ni;
    reg  [7:0]   s_axi_awaddr;
    reg          s_axi_awvalid;
    wire         s_axi_awready;
    reg  [31:0]  s_axi_wdata;
    reg  [3:0]   s_axi_wstrb;
    reg          s_axi_wvalid;
    wire         s_axi_wready;
    wire [1:0]   s_axi_bresp;
    wire         s_axi_bvalid;
    reg          s_axi_bready;
    reg  [7:0]   s_axi_araddr;
    reg          s_axi_arvalid;
    wire         s_axi_arready;
    wire [31:0]  s_axi_rdata;
    wire [1:0]   s_axi_rresp;
    wire         s_axi_rvalid;
    reg          s_axi_rready;
    reg  [31:0]  i_status;
    reg  [4:0]   i_irq;
    wire         o_enable;
    wire         o_clear_counters;
    wire [W_RATE_DIV-1:0] o_rate_div;
    wire [15:0]  o_ratio_thresh;
    wire [15:0]  o_entropy_thresh;
    wire [4:0]   o_arm_select;
    wire [7:0]   o_window_step;
    wire [7:0]   o_window_beats;

    regs_axi dut (
        .clk_i (clk_i), .rst_ni (rst_ni),
        .s_axi_awaddr (s_axi_awaddr), .s_axi_awvalid (s_axi_awvalid),
        .s_axi_awready (s_axi_awready),
        .s_axi_wdata (s_axi_wdata), .s_axi_wstrb (s_axi_wstrb),
        .s_axi_wvalid (s_axi_wvalid), .s_axi_wready (s_axi_wready),
        .s_axi_bresp (s_axi_bresp), .s_axi_bvalid (s_axi_bvalid),
        .s_axi_bready (s_axi_bready),
        .s_axi_araddr (s_axi_araddr), .s_axi_arvalid (s_axi_arvalid),
        .s_axi_arready (s_axi_arready),
        .s_axi_rdata (s_axi_rdata), .s_axi_rresp (s_axi_rresp),
        .s_axi_rvalid (s_axi_rvalid), .s_axi_rready (s_axi_rready),
        .i_status (i_status), .i_irq (i_irq),
        .o_enable (o_enable), .o_clear_counters (o_clear_counters),
        .o_rate_div (o_rate_div), .o_ratio_thresh (o_ratio_thresh),
        .o_entropy_thresh (o_entropy_thresh), .o_arm_select (o_arm_select),
        .o_window_step (o_window_step), .o_window_beats (o_window_beats)
    );

    // 100 MHz, the PL clock of doc 36 section 3.1. The period is the unit only; every
    // check in this file waits on an edge, never on an absolute time.
    initial clk_i = 1'b0;
    always #5 clk_i <= ~clk_i;

    // ------------------------------------------------------------ vectors
    reg [31:0] map_offs  [0:N_MAP-1];
    reg [31:0] map_kind  [0:N_MAP-1];
    reg [31:0] map_rst   [0:N_MAP-1];
    reg [31:0] counts    [0:N_CNT-1];
    reg [31:0] qr_raw    [0:N_RAW-1];
    reg [31:0] qe_raw    [0:N_RAW-1];
    reg [31:0] kelas_raw [0:N_RAW-1];
    reg [31:0] asli_raw  [0:N_RAW-1];
    reg [31:0] kelas_toff[0:N_RAW-1];
    reg [31:0] qr_mark   [0:N_MARK-1];
    reg [31:0] qe_mark   [0:N_MARK-1];
    reg [31:0] kelas_mark[0:N_MARK-1];
    reg [31:0] asli_mark [0:N_MARK-1];
    reg [31:0] kelas_tunggal [0:N_MARK-1];
    reg [31:0] kelas_guard   [0:N_MARK-1];
    reg [31:0] kelas_either  [0:N_MARK-1];
    reg [31:0] mirror   [0:N_MAP-1];

    string vec_dir;
    string vec_path;

    integer checks, fails, mism_total, cmp_total;
    integer i, j, k, n, mm, fired_cnt, tp, fp, fn, tn;
    integer lines;
    reg [31:0] wpat, rdat, want, prev;
    reg [3:0]  wstrb_c;
    reg [7:0]  aoff;
    reg [1:0]  akind;
    reg [31:0] arst;
    reg [41:0] slot;
    reg [31:0] thr_ratio, thr_ent;
    reg [4:0]  arm_rb;
    reg [31:0] qr_v, qe_v, asli_v;
    integer fr, fe, fire, kelas_v, exp_kelas;
    integer ok_w, ok_r;
    reg [31:0] pr_a, pr_b;
    integer mism_rt, cmp_rt, mism_partial, cmp_partial, mism_arm, cmp_arm;
    integer mism_unmap, cmp_unmap, mism_ro, cmp_ro, mism_reset, cmp_reset;
    integer runs_fired [0:5];

    // 32 bit views of the narrow signals, so every call of expect_equal and expect_ok has
    // both arguments at one width and Verilator's WIDTHEXPAND check stays meaningful
    wire [31:0] v_enable   = {31'd0, o_enable};
    wire [31:0] v_clear    = {31'd0, o_clear_counters};
    wire [31:0] v_rate     = {{(32-W_RATE_DIV){1'b0}}, o_rate_div};
    wire [31:0] v_ratio    = {16'd0, o_ratio_thresh};
    wire [31:0] v_entropy  = {16'd0, o_entropy_thresh};
    wire [31:0] v_arm      = {27'd0, o_arm_select};
    wire [31:0] v_wstep    = {24'd0, o_window_step};
    wire [31:0] v_wbeats   = {24'd0, o_window_beats};
    localparam [31:0] ARM_RST32     = {27'd0, ARM_RST};
    localparam [31:0] RATIO_RST32   = {16'd0, RATIO_RST};
    localparam [31:0] ENTROPY_RST32 = {16'd0, ENTROPY_RST};
    localparam [31:0] RATE_RST32    = {{(32-W_RATE_DIV){1'b0}}, RATE_RST};
    localparam [31:0] WSTEP_RST32   = {24'd0, WSTEP_RST};
    localparam [31:0] WBEATS_RST32  = {24'd0, WBEATS_RST};
    localparam [31:0] CLAMP_THRESH_RST32 = 32'h000007FF;   // plan 8.5, slot 0x7C

    // byte lane mask of a strobe nibble
    function automatic [31:0] mask_of(input [3:0] strb);
        begin
            mask_of = {{8{strb[3]}}, {8{strb[2]}}, {8{strb[1]}}, {8{strb[0]}}};
        end
    endfunction

    // ------------------------------------------------------------ slot table of the testbench
    // {kind[1:0], offset[7:0], reset[31:0]} for the 36 slots of plan 8.5 and the two
    // provisional window parameter slots. Checked against f11.map.offs/kind/rst.hex below.
    function automatic [41:0] tb_slot(input integer sel);
        begin
            case (sel)
                // --- the D8 frozen map, 36 slots, 0x00 to 0x8C step 4 -------------------
                0:  tb_slot = {K_RW,  8'h00, 32'h00000000};   // CTRL
                1:  tb_slot = {K_RO,  8'h04, 32'h00000001};   // STATUS
                2:  tb_slot = {K_RO,  8'h08, 32'h00000000};   // IRQ_STATUS
                3:  tb_slot = {K_W1C, 8'h0C, 32'h00000000};   // IRQ_CLEAR
                4:  tb_slot = {K_RO,  8'h10, 32'h00000000};   // CLASS_OUT
                5:  tb_slot = {K_RO,  8'h14, 32'h00000000};   // CONFIDENCE
                6:  tb_slot = {K_RO,  8'h18, 32'h00000000};   // RR_LAST
                7:  tb_slot = {K_RO,  8'h1C, 32'h00000000};   // BEAT_COUNT
                8:  tb_slot = {K_RO,  8'h20, 32'h00000000};   // GAP_COUNT
                9:  tb_slot = {K_RO,  8'h24, 32'h00000000};   // SAMPLE_IDX
                10: tb_slot = {K_RO,  8'h28, 32'h00000000};   // WINDOW_COUNT
                11: tb_slot = {K_RO,  8'h2C, 32'h00000000};   // CLAMP_COUNT
                12: tb_slot = {K_RO,  8'h30, 32'h00000000};   // FIFO_OVF_COUNT
                13: tb_slot = {K_RO,  8'h34, 32'h00000000};   // RR_LONG_COUNT
                14: tb_slot = {K_RO,  8'h38, 32'h00000000};   // RR_MARK_LAST
                15: tb_slot = {K_RW,  8'h3C, 32'h00000021};   // RATIO_THRESH
                16: tb_slot = {K_RW,  8'h40, 32'h0000003F};   // ENTROPY_THRESH
                17: tb_slot = {K_RW,  8'h44, 32'h0000000F};   // ARM_SELECT
                18: tb_slot = {K_RO,  8'h48, 32'h00000000};   // FEAT_RATIO
                19: tb_slot = {K_RO,  8'h4C, 32'h00000000};   // FEAT_ENTROPY
                20: tb_slot = {K_RW,  8'h50, 32'h004C00FA};   // FORMAT_CFG
                21: tb_slot = {K_RW,  8'h54, 32'h00061A7F};   // RATE_DIV
                22: tb_slot = {K_RW,  8'h58, 32'h00000100};   // THRESH_SCALE
                23: tb_slot = {K_RW,  8'h5C, 32'h0000005C};   // RR_BAND_LO
                24: tb_slot = {K_RW,  8'h60, 32'h00000074};   // RR_BAND_HI
                25: tb_slot = {K_RO,  8'h64, 32'h00010001};   // VERSION_ID
                26: tb_slot = {K_RW,  8'h68, 32'h00000000};   // SCRATCH
                27: tb_slot = {K_WO,  8'h6C, 32'h00000000};   // SAMPLE_FIFO
                28: tb_slot = {K_WO,  8'h70, 32'h00000000};   // SAMPLE_MARK
                29: tb_slot = {K_RO,  8'h74, 32'h00000000};   // SAMPLE_IN_STATUS
                30: tb_slot = {K_RO,  8'h78, 32'h00000000};   // MARKER_LAST
                31: tb_slot = {K_RW,  8'h7C, 32'h000007FF};   // CLAMP_THRESH
                32: tb_slot = {K_RW,  8'h80, 32'h00000083};   // GAP_RECOVERY
                33: tb_slot = {K_RW,  8'h84, 32'h00000000};   // REPLAY_LEN
                34: tb_slot = {K_RO,  8'h88, 32'h00000000};   // IDX_TAP_LAST
                35: tb_slot = {K_RO,  8'h8C, 32'h00000000};   // IDX_DEC_LAST
                // --- above the frozen map: plan decision 9 raises the map to 38 slots ---
                36: tb_slot = {K_RW,  8'h90, 32'h00000000};   // DEBUG_SEL
                37: tb_slot = {K_RO,  8'h94, 32'h00000000};   // DEBUG_VAL
                default: tb_slot = {K_RO, 8'h00, 32'h00000000};
            endcase
        end
    endfunction

    // ------------------------------------------------------------ helpers
    task automatic expect_equal(input [8*96-1:0] what, input [31:0] got, input [31:0] want_v);
        begin
            checks = checks + 1;
            if (got !== want_v) begin
                fails = fails + 1;
                $display("FAIL %0s got=%0d want=%0d", what, got, want_v);
            end else begin
                $display("OK   %0s %0d", what, got);
            end
        end
    endtask

    task automatic expect_ok(input [8*96-1:0] what, input [31:0] got);
        begin
            checks = checks + 1;
            if (got == 32'd0) begin
                fails = fails + 1;
                $display("FAIL %0s", what);
            end else begin
                $display("OK   %0s", what);
            end
        end
    endtask

    task automatic die(input [8*160-1:0] what);
        begin
            fails = fails + 1;
            $display("FATAL %0s", what);
            $fatal(1, "tb_regs_axi: %0s", what);
        end
    endtask

    function automatic integer count_lines(input string path);
        integer f, nl;
        reg [8*512-1:0] line;
        begin
            nl = 0;
            f = $fopen(path, "r");
            if (f == 0) begin
                $display("FATAL cannot open %0s", path);
                $fatal(1, "tb_regs_axi: vector file missing");
            end
            while ($fgets(line, f) != 0)
                if (line != 0) nl = nl + 1;
            $fclose(f);
            count_lines = nl;
        end
    endfunction

    // every vector file is length checked before it is read; a short file is fatal
    task automatic check_vector(input string name, input integer want_lines);
        begin
            vec_path = $sformatf("%s/%s", vec_dir, name);
            lines = count_lines(vec_path);
            if (lines != want_lines) begin
                $display("FATAL %0s has %0d lines, the fixture has %0d",
                         name, lines, want_lines);
                $fatal(1, "tb_regs_axi: vector file length");
            end
        end
    endtask

    // ------------------------------------------------------------ AXI4-Lite master
    // The stimulus is driven at the falling edge and released one cycle later, so the DUT
    // samples a stable value at every rising edge and there is no drive/deassert race.
    task automatic axi_write(input [7:0] addr, input [31:0] data, input [3:0] strb,
                             output [31:0] resp_ok);
        begin
            @(negedge clk_i);
            s_axi_awaddr  = addr;
            s_axi_awvalid = 1'b1;
            s_axi_wdata   = data;
            s_axi_wstrb   = strb;
            s_axi_wvalid  = 1'b1;
            s_axi_bready  = 1'b1;
            // The handshake happens at the rising edge that follows a cycle where both write
            // channels were ready, so readiness is sampled in the SAME cycle the request is
            // driven. Waiting one cycle longer would issue the request twice: invisible on a
            // plain register, but a double count on the ingest counters of this map.
            while (!(s_axi_awready && s_axi_wready)) @(negedge clk_i);
            @(posedge clk_i);
            #1;
            if (s_axi_bvalid !== 1'b1) begin
                $display("FATAL no write response at 0x%02X", addr);
                $fatal(1, "tb_regs_axi: write response");
            end
            resp_ok = {31'd0, (s_axi_bresp === 2'b00)};
            @(negedge clk_i);
            s_axi_awvalid = 1'b0;
            s_axi_wvalid  = 1'b0;
            @(posedge clk_i);
            #1;
            s_axi_bready = 1'b0;
        end
    endtask

    task automatic axi_read(input [7:0] addr, output [31:0] data, output [31:0] resp_ok);
        begin
            @(negedge clk_i);
            s_axi_araddr  = addr;
            s_axi_arvalid = 1'b1;
            s_axi_rready  = 1'b1;
            // same rule as the write path: arready is sampled in the drive cycle, so the read
            // is accepted at the rising edge that follows
            while (!s_axi_arready) @(negedge clk_i);
            @(posedge clk_i);
            #1;
            if (s_axi_rvalid !== 1'b1) begin
                $display("FATAL no read response at 0x%02X", addr);
                $fatal(1, "tb_regs_axi: read response");
            end
            data    = s_axi_rdata;
            resp_ok = {31'd0, (s_axi_rresp === 2'b00)};
            @(negedge clk_i);
            s_axi_arvalid = 1'b0;
            @(posedge clk_i);
            #1;
            s_axi_rready = 1'b0;
        end
    endtask

    // A write and a read accepted in the same cycle, both answered. The read returns the
    // value the register held before that edge, which is the documented contract of this
    // register file.
    task automatic axi_write_read(input [7:0] waddr, input [31:0] wdat,
                                  input [7:0] raddr,
                                  output [31:0] rdat_v, output [31:0] w_ok,
                                  output [31:0] r_ok);
        begin
            @(negedge clk_i);
            s_axi_awaddr  = waddr;
            s_axi_awvalid = 1'b1;
            s_axi_wdata   = wdat;
            s_axi_wstrb   = 4'hF;
            s_axi_wvalid  = 1'b1;
            s_axi_bready  = 1'b1;
            s_axi_araddr  = raddr;
            s_axi_arvalid = 1'b1;
            s_axi_rready  = 1'b1;
            // both channels ready in one cycle, sampled in the drive cycle, so the write and
            // the read are accepted at the SAME rising edge: that is the case this task is here
            // for, and it is what makes the pre write value rule testable
            while (!(s_axi_awready && s_axi_wready && s_axi_arready)) @(negedge clk_i);
            @(posedge clk_i);
            #1;
            w_ok  = {31'd0, (s_axi_bvalid === 1'b1) && (s_axi_bresp === 2'b00)};
            r_ok  = {31'd0, (s_axi_rvalid === 1'b1) && (s_axi_rresp === 2'b00)};
            rdat_v = s_axi_rdata;
            @(negedge clk_i);
            s_axi_awvalid = 1'b0;
            s_axi_wvalid  = 1'b0;
            s_axi_arvalid = 1'b0;
            @(posedge clk_i);
            #1;
            s_axi_bready = 1'b0;
            s_axi_rready = 1'b0;
        end
    endtask

    // write one slot and keep the independent mirror in step with the byte lane rule, so a
    // later section can build its expectation from the mirror without reading the DUT back
    task automatic write_slot(input [7:0] addr, input [31:0] data, input [3:0] strb);
        begin
            axi_write(addr, data, strb, ok_w);
            // the module level slot word is used here as a scratch: no caller of this task is
            // inside a loop that relies on its value
            for (k = 0; k < N_MAP; k = k + 1) begin
                slot = tb_slot(k);
                if ((slot[39:32] == addr) && (slot[41:40] == K_RW))
                    mirror[k] = (mirror[k] & ~mask_of(strb)) | (data & mask_of(strb));
            end
        end
    endtask

    task automatic do_reset(input integer cycles);
        begin
            rst_ni = 1'b0;
            s_axi_awaddr = 8'h00;  s_axi_awvalid = 1'b0;
            s_axi_wdata  = 32'd0;  s_axi_wstrb   = 4'h0;  s_axi_wvalid = 1'b0;
            s_axi_bready = 1'b0;
            s_axi_araddr = 8'h00;  s_axi_arvalid = 1'b0;  s_axi_rready = 1'b0;
            i_status = 32'h00000001;   // the declared reset value of STATUS, per plan 8.5
            i_irq    = 5'd0;
            repeat (cycles) @(posedge clk_i);
            rst_ni = 1'b1;
            @(posedge clk_i);
        end
    endtask

    // Snapshot every slot the map calls readable into the mirror.
    task automatic snapshot_mirror;
        begin
            for (i = 0; i < N_MAP; i = i + 1) begin
                slot  = tb_slot(i);
                akind = slot[41:40];
                aoff  = slot[39:32];
                if (akind != K_WO) begin
                    axi_read(aoff, rdat, ok_r);
                    mirror[i] = rdat;
                end
            end
        end
    endtask

    // Score one arm run: the enrolled arms, the thresholds read back from the register
    // file, the frozen feature columns of the selected arm, and the expected class column
    // of the run. Also builds the four confusion counts against the ground truth column.
    task automatic score_run(input integer src_sel, input integer exp_sel,
                             input integer sel_bit, input [4:0] arm,
                             input [31:0] thr_r, input [31:0] thr_e,
                             input [8*32-1:0] tag,
                             output integer n_cmp, output integer n_mism,
                             output integer n_fired, output integer o_tp, output integer o_fp,
                             output integer o_fn, output integer o_tn);
        integer sel2, nloc;
        begin
            nloc = (src_sel == 1) ? N_MARK : N_RAW;
            // the bit of ARM_SELECT that this run claims selects the source has to hold, or
            // the run is scoring a different arm than the one it names. A run that does not
            // name a source bit passes -1 and makes no claim.
            if ((sel_bit >= 0) &&
                ((src_sel == 1) ? (arm[sel_bit] != 1'b1) : (arm[sel_bit] != 1'b0))) begin
                checks = checks + 1;
                fails = fails + 1;
                $display("FAIL arm run %0s: bit %0d of ARM_SELECT is %0d for source %0d",
                         tag, sel_bit, arm[sel_bit], src_sel);
            end
            n_cmp = 0; n_mism = 0; n_fired = 0; o_tp = 0; o_fp = 0; o_fn = 0; o_tn = 0;
            for (sel2 = 0; sel2 < nloc; sel2 = sel2 + 1) begin
                if (src_sel == 1) begin
                    qr_v = qr_mark[sel2]; qe_v = qe_mark[sel2]; asli_v = asli_mark[sel2];
                end else begin
                    qr_v = qr_raw[sel2];  qe_v = qe_raw[sel2];  asli_v = asli_raw[sel2];
                end
                fr = (arm[0] && (qr_v > thr_r)) ? 32'd1 : 32'd0;
                fe = (arm[1] && (qe_v > thr_e)) ? 32'd1 : 32'd0;
                if (arm[0] && arm[1])      fire = arm[4] ? (fr | fe) : (fr & fe);
                else if (arm[0])           fire = fr;
                else if (arm[1])           fire = fe;
                else                       fire = 0;
                kelas_v = (fire != 0) ? {30'd0, KELAS_REVIEW_B} : {30'd0, KELAS_NORMAL_B};
                case (exp_sel)
                    E_RAW:     exp_kelas = kelas_raw[sel2];
                    E_T_OFF:   exp_kelas = kelas_toff[sel2];
                    E_MARK:    exp_kelas = kelas_mark[sel2];
                    E_TUNGGAL: exp_kelas = kelas_tunggal[sel2];
                    E_GUARD:   exp_kelas = kelas_guard[sel2];
                    default:   exp_kelas = kelas_either[sel2];
                endcase
                if (kelas_v !== exp_kelas) begin
                    n_mism = n_mism + 1;
                    if (n_mism <= 3)
                        $display("MISMATCH arm run %0s window %0d got=%0d want=%0d",
                                 tag, sel2, kelas_v, exp_kelas);
                end
                n_cmp = n_cmp + 1;
                if (fire != 0) begin
                    n_fired = n_fired + 1;
                    if (asli_v == {30'd0, KELAS_REVIEW_B}) o_tp = o_tp + 1;
                    else o_fp = o_fp + 1;
                end else begin
                    if (asli_v == {30'd0, KELAS_REVIEW_B}) o_fn = o_fn + 1;
                    else o_tn = o_tn + 1;
                end
            end
        end
    endtask

    // ------------------------------------------------------------ main
    initial begin
        checks = 0; fails = 0; mism_total = 0; cmp_total = 0;
        mism_rt = 0; cmp_rt = 0; mism_partial = 0; cmp_partial = 0;
        mism_arm = 0; cmp_arm = 0; mism_unmap = 0; cmp_unmap = 0;
        mism_ro = 0; cmp_ro = 0; mism_reset = 0; cmp_reset = 0;
        for (i = 0; i < 6; i = i + 1) runs_fired[i] = 0;

        vec_dir = "../rtl/tb/vektor/fase11";
        if ($value$plusargs("VECTOR=%s", vec_dir))
            $display("INFO  vector directory from +VECTOR");
        $display("== tb_regs_axi, Fase 11, register map of plan 38 section 8.5 ==");
        $display("INFO  vector dir [%0s]", vec_dir);

        // ============================================================ 0. vectors
        check_vector("f11.map.offs.hex", N_MAP);
        check_vector("f11.map.kind.hex", N_MAP);
        check_vector("f11.map.rst.hex", N_MAP);
        check_vector("f11.counts.hex", N_CNT);
        check_vector("f11.mentah.qr.hex", N_RAW);
        check_vector("f11.mentah.qe.hex", N_RAW);
        check_vector("f11.mentah.kelas.hex", N_RAW);
        check_vector("f11.mentah.asli.hex", N_RAW);
        check_vector("f11.t_off.kelas.hex", N_RAW);
        check_vector("f11.berpenanda.qr.hex", N_MARK);
        check_vector("f11.berpenanda.qe.hex", N_MARK);
        check_vector("f11.berpenanda.kelas.hex", N_MARK);
        check_vector("f11.berpenanda.asli.hex", N_MARK);
        check_vector("f11.tunggal.kelas.hex", N_MARK);
        check_vector("f11.guard.kelas.hex", N_MARK);
        check_vector("f11.either.kelas.hex", N_MARK);

        $readmemh($sformatf("%s/f11.map.offs.hex", vec_dir), map_offs);
        $readmemh($sformatf("%s/f11.map.kind.hex", vec_dir), map_kind);
        $readmemh($sformatf("%s/f11.map.rst.hex", vec_dir), map_rst);
        $readmemh($sformatf("%s/f11.counts.hex", vec_dir), counts);
        $readmemh($sformatf("%s/f11.mentah.qr.hex", vec_dir), qr_raw);
        $readmemh($sformatf("%s/f11.mentah.qe.hex", vec_dir), qe_raw);
        $readmemh($sformatf("%s/f11.mentah.kelas.hex", vec_dir), kelas_raw);
        $readmemh($sformatf("%s/f11.mentah.asli.hex", vec_dir), asli_raw);
        $readmemh($sformatf("%s/f11.t_off.kelas.hex", vec_dir), kelas_toff);
        $readmemh($sformatf("%s/f11.berpenanda.qr.hex", vec_dir), qr_mark);
        $readmemh($sformatf("%s/f11.berpenanda.qe.hex", vec_dir), qe_mark);
        $readmemh($sformatf("%s/f11.berpenanda.kelas.hex", vec_dir), kelas_mark);
        $readmemh($sformatf("%s/f11.berpenanda.asli.hex", vec_dir), asli_mark);
        $readmemh($sformatf("%s/f11.tunggal.kelas.hex", vec_dir), kelas_tunggal);
        $readmemh($sformatf("%s/f11.guard.kelas.hex", vec_dir), kelas_guard);
        $readmemh($sformatf("%s/f11.either.kelas.hex", vec_dir), kelas_either);

        $display("INFO  map slots in the vector: %0d, frozen: %0d",
                 counts[C_MAP_SLOTS], counts[C_FROZEN_SLOTS]);
        expect_equal("vector map slot count", counts[C_MAP_SLOTS], N_MAP);
        expect_equal("vector frozen slot count", counts[C_FROZEN_SLOTS], 36);
        expect_equal("vector marked windows", counts[C_N_MARK], N_MARK);
        expect_equal("vector raw windows", counts[C_N_RAW], N_RAW);

        // the map table of this testbench must be the map of the vectors, word for word
        for (i = 0; i < N_MAP; i = i + 1) begin
            slot  = tb_slot(i);
            akind = slot[41:40];
            aoff  = slot[39:32];
            arst  = slot[31:0];
            if (aoff !== map_offs[i][7:0]) begin
                $display("FATAL slot %0d offset tb=0x%02X vector=0x%02X",
                         i, aoff, map_offs[i][7:0]);
                mism_reset = mism_reset + 1;
            end
            if (akind !== map_kind[i][1:0]) begin
                $display("FATAL slot %0d kind tb=%0d vector=%0d",
                         i, akind, map_kind[i][1:0]);
                mism_reset = mism_reset + 1;
            end
            if (arst !== map_rst[i]) begin
                $display("FATAL slot %0d reset tb=0x%08X vector=0x%08X",
                         i, arst, map_rst[i]);
                mism_reset = mism_reset + 1;
            end
        end
        expect_equal("map table matches the map vectors", mism_reset, 0);
        mism_reset = 0;

        // ============================================================ 1. reset values
        $display("-- reset: every slot of the map, and the frozen outputs --");
        do_reset(4);
        for (i = 0; i < N_MAP; i = i + 1) begin
            slot  = tb_slot(i);
            aoff  = slot[39:32];
            arst  = slot[31:0];
            axi_read(aoff, rdat, ok_r);
            cmp_reset = cmp_reset + 1;
            if (rdat !== arst) begin
                mism_reset = mism_reset + 1;
                if (mism_reset <= 6)
                    $display("MISMATCH reset slot %0d addr 0x%02X got=0x%08X want=0x%08X",
                             i, aoff, rdat, arst);
            end
            if (aoff != 8'h6C && aoff != 8'h70) mirror[i] = rdat;
        end
        $display("reset slot comparisons: %0d", cmp_reset);
        $display("reset mismatches: %0d", mism_reset);
        expect_equal("reset value mismatches", mism_reset, 0);
        mism_total = mism_total + mism_reset;
        cmp_total  = cmp_total + cmp_reset;

        // the frozen configuration outputs come back to their reset values, ARM_SELECT
        // included, which is the bit reset the phase gate asks for by name
        expect_equal("o_arm_select reset", v_arm, ARM_RST32);
        expect_equal("o_arm_select reset low bits", v_arm, 32'd15);
        expect_equal("o_ratio_thresh reset", v_ratio, RATIO_RST32);
        expect_equal("o_entropy_thresh reset", v_entropy, ENTROPY_RST32);
        expect_equal("o_rate_div reset", v_rate, RATE_RST32);
        expect_equal("o_window_step reset", v_wstep, WSTEP_RST32);
        expect_equal("o_window_beats reset", v_wbeats, WBEATS_RST32);
        expect_equal("o_enable reset", v_enable, 0);
        expect_equal("o_clear_counters reset", v_clear, 0);
        axi_read(8'h64, rdat, ok_r);
        expect_equal("VERSION_ID reset", rdat, 32'h00010001);
        expect_ok("VERSION_ID is not zero", {31'd0, rdat != 32'd0});
        axi_read(8'h04, rdat, ok_r);
        expect_equal("STATUS follows i_status", rdat, 32'h00000001);
        i_status = 32'hA5A50000;
        #1;
        axi_read(8'h04, rdat, ok_r);
        expect_equal("STATUS follows i_status again", rdat, 32'hA5A50000);
        i_status = 32'h00000001;
        #1;

        // ============================================================ 2. round trip
        // six patterns, every writable slot, all four byte lanes, the read compared with
        // the written word AND with the independent mirror
        $display("-- round trip: every writable slot, six patterns --");
        for (k = 0; k < 6; k = k + 1) begin
            case (k)
                0: wpat = 32'h00000000;
                1: wpat = 32'hFFFFFFFF;
                2: wpat = 32'hA5A55A5A;
                3: wpat = 32'h5A5A5A5A;
                4: wpat = 32'h00010000;
                default: wpat = 32'hFFFF0000;
            endcase
            for (i = 0; i < N_MAP; i = i + 1) begin
                slot  = tb_slot(i);
                akind = slot[41:40];
                aoff  = slot[39:32];
                if (akind == K_RW) begin
                    axi_write(aoff, wpat, 4'hF, ok_w);
                    axi_read(aoff, rdat, ok_r);
                    // gate: the read equals the value written
                    if (rdat !== wpat) begin
                        mism_rt = mism_rt + 1;
                        if (mism_rt <= 6)
                            $display("MISMATCH read/write slot %0d addr 0x%02X got=0x%08X wrote=0x%08X",
                                     i, aoff, rdat, wpat);
                    end
                    // independent mirror: a full strobe write replaces every byte
                    mirror[i] = wpat;
                    if (rdat !== mirror[i]) begin
                        mism_rt = mism_rt + 1;
                        $display("MISMATCH mirror slot %0d addr 0x%02X got=0x%08X mirror=0x%08X",
                                 i, aoff, rdat, mirror[i]);
                    end
                    cmp_rt = cmp_rt + 2;
                end else if (akind == K_RO) begin
                    // a read only slot must not move when it is written
                    axi_write(aoff, wpat, 4'hF, ok_w);
                    axi_read(aoff, rdat, ok_r);
                    cmp_ro = cmp_ro + 1;
                    if (rdat !== mirror[i]) begin
                        mism_ro = mism_ro + 1;
                        if (mism_ro <= 4)
                            $display("MISMATCH read only slot %0d addr 0x%02X got=0x%08X was=0x%08X wrote=0x%08X",
                                     i, aoff, rdat, mirror[i], wpat);
                    end
                end
            end
        end
        expect_ok("write response always OKAY", ok_w);
        $display("round trip comparisons: %0d", cmp_rt);
        $display("round trip mismatches: %0d", mism_rt);
        $display("read only slot comparisons: %0d", cmp_ro);
        $display("read only slot mismatches: %0d", mism_ro);
        expect_equal("round trip mismatches", mism_rt, 0);
        expect_equal("read only slot mismatches", mism_ro, 0);
        mism_total = mism_total + mism_rt + mism_ro;
        cmp_total  = cmp_total + cmp_rt + cmp_ro;
        mism_ro = 0; cmp_ro = 0;

        // the exported fields follow the written word
        write_slot(8'h00, 32'h00000005, 4'hF);
        #1;
        expect_equal("o_enable after CTRL b0", v_enable, 1);
        expect_equal("o_clear_counters after CTRL b2", v_clear, 1);
        write_slot(8'h00, 32'h00000000, 4'hF);
        write_slot(8'h3C, 32'h00001234, 4'hF);
        write_slot(8'h40, 32'h00005678, 4'hF);
        write_slot(8'h44, 32'h0000000A, 4'hF);
        write_slot(8'h54, 32'h000FFFFF, 4'hF);
        // slot 0x90 is the DEBUG_SEL node selector of plan decision 9: stored whole and read
        // back as written. Slot 0x94 is DEBUG_VAL, read only, and reads zero because the
        // frozen port list of regs_axi carries no introspection input.
        write_slot(8'h90, 32'h000000A5, 4'hF);
        axi_read(8'h90, rdat, ok_r);
        expect_equal("DEBUG_SEL read equals write", rdat, 32'h000000A5);
        axi_read(8'h94, rdat, ok_r);
        expect_equal("DEBUG_VAL reads zero", rdat, 32'h00000000);
        #1;
        expect_equal("o_ratio_thresh field", v_ratio, 32'h00001234);
        expect_equal("o_entropy_thresh field", v_entropy, 32'h00005678);
        expect_equal("o_arm_select field", v_arm, 32'd10);
        expect_equal("o_rate_div field", v_rate, 32'h000FFFFF);
        // the window pair is a design constant of this file now, not a slot: D8 dropped its
        // old offsets and the top level uses the pair as its fallback default
        expect_equal("o_window_step holds the design constant", v_wstep, 32'd4);
        expect_equal("o_window_beats holds the design constant", v_wbeats, 32'd32);
        axi_read(8'h54, rdat, ok_r);
        expect_equal("RATE_DIV read equals write", rdat, 32'h000FFFFF);

        // ============================================================ 3. byte lanes
        // partial strobe writes on every writable slot; the expectation is built here from
        // the mirror and the strobe mask, never from the DUT
        $display("-- partial strobe writes on every writable slot --");
        for (i = 0; i < N_MAP; i = i + 1) begin
            slot  = tb_slot(i);
            akind = slot[41:40];
            aoff  = slot[39:32];
            if (akind == K_RW) begin
                axi_read(aoff, prev, ok_r);
                if (prev !== mirror[i]) begin
                    mism_partial = mism_partial + 1;
                    $display("MISMATCH mirror before partial slot %0d addr 0x%02X got=0x%08X mirror=0x%08X",
                             i, aoff, prev, mirror[i]);
                end
                for (j = 0; j < 6; j = j + 1) begin
                    case (j)
                        0: begin wpat = 32'h11223344; wstrb_c = 4'h1; end
                        1: begin wpat = 32'h11223344; wstrb_c = 4'h2; end
                        2: begin wpat = 32'h11223344; wstrb_c = 4'h4; end
                        3: begin wpat = 32'h11223344; wstrb_c = 4'h8; end
                        4: begin wpat = 32'h89ABCDEF; wstrb_c = 4'h3; end
                        default: begin wpat = 32'h89ABCDEF; wstrb_c = 4'hC; end
                    endcase
                    axi_write(aoff, wpat, wstrb_c, ok_w);
                    axi_read(aoff, rdat, ok_r);
                    want = (mirror[i] & ~mask_of(wstrb_c)) | (wpat & mask_of(wstrb_c));
                    mirror[i] = want;
                    cmp_partial = cmp_partial + 1;
                    if (rdat !== want) begin
                        mism_partial = mism_partial + 1;
                        if (mism_partial <= 6)
                            $display("MISMATCH byte lane slot %0d addr 0x%02X strb=%b got=0x%08X want=0x%08X",
                                     i, aoff, wstrb_c, rdat, want);
                    end
                end
            end
        end
        $display("byte lane comparisons: %0d", cmp_partial);
        $display("byte lane mismatches: %0d", mism_partial);
        expect_equal("byte lane mismatches", mism_partial, 0);
        mism_total = mism_total + mism_partial;
        cmp_total  = cmp_total + cmp_partial;

        // a write with every strobe low is answered and changes nothing
        axi_write(8'h68, 32'hA5A55A5A, 4'hF, ok_w);
        axi_write(8'h68, 32'hDEADBEEF, 4'h0, ok_w);
        expect_ok("zero strobe write is answered", ok_w);
        axi_read(8'h68, rdat, ok_r);
        expect_equal("zero strobe write changes nothing", rdat, 32'hA5A55A5A);
        axi_write(8'h6C, 32'h0000FFFF, 4'h0, ok_w);
        expect_ok("zero strobe sample word is answered", ok_w);
        axi_read(8'h74, rdat, ok_r);
        expect_equal("zero strobe sample word is not counted", {16'd0, rdat[15:0]}, 0);

        // ============================================================ 4. write only slots
        $display("-- write only slots and the ingest counters --");
        // the byte lane section above writes every writable slot, CLAMP_THRESH included, so the
        // clamp rail is put back to its reset value here: the word rule below is measured
        // against a known rail, not against whatever pattern was left behind
        write_slot(8'h7C, CLAMP_THRESH_RST32, 4'hF);
        axi_read(8'h7C, rdat, ok_r);
        expect_equal("CLAMP_THRESH before the ingest test", rdat, CLAMP_THRESH_RST32);
        axi_write(8'h70, 32'h00000001, 4'hF, ok_w);
        axi_write(8'h6C, 32'h00001000, 4'hF, ok_w);   // 4096 is above the clamp threshold
        axi_read(8'h74, rdat, ok_r);
        expect_equal("SAMPLE_IN_STATUS counts one word", {16'd0, rdat[15:0]}, 1);
        expect_equal("SAMPLE_IN_STATUS level is zero, no FIFO here", {24'd0, rdat[23:16]}, 0);
        axi_read(8'h78, rdat, ok_r);
        expect_equal("MARKER_LAST carries the mark", rdat, 32'h00000001);
        axi_read(8'h2C, rdat, ok_r);
        expect_equal("clamp count from the mark", rdat, 32'h00000001);
        axi_write(8'h6C, 32'h00001000, 4'hF, ok_w);   // no mark now, the word rule fires
        axi_read(8'h2C, rdat, ok_r);
        expect_equal("clamp count from the word rule", rdat, 32'h00000002);
        axi_read(8'h78, rdat, ok_r);
        expect_equal("MARKER_LAST cleared with the word", rdat, 32'h00000000);
        axi_write(8'h70, 32'h00000002, 4'hF, ok_w);
        axi_write(8'h6C, 32'h00000001, 4'hF, ok_w);
        axi_read(8'h20, rdat, ok_r);
        expect_equal("gap count from the gap mark", rdat, 32'h00000001);
        axi_read(8'h2C, rdat, ok_r);
        expect_equal("clamp count unchanged by a low word", rdat, 32'h00000002);
        axi_read(8'h74, rdat, ok_r);
        expect_equal("three words received", {16'd0, rdat[15:0]}, 3);
        axi_read(8'h30, rdat, ok_r);
        expect_equal("FIFO_OVF_COUNT stays zero", rdat, 32'h00000000);
        // the clear counters pulse of CTRL b2 clears the ingest counters
        axi_write(8'h00, 32'h00000004, 4'hF, ok_w);
        axi_read(8'h74, rdat, ok_r);
        expect_equal("clear counters clears the word count", {16'd0, rdat[15:0]}, 0);
        axi_read(8'h2C, rdat, ok_r);
        expect_equal("clear counters clears clamp", rdat, 32'h00000000);
        axi_read(8'h20, rdat, ok_r);
        expect_equal("clear counters clears gap", rdat, 32'h00000000);
        axi_write(8'h00, 32'h00000000, 4'hF, ok_w);

        // ============================================================ 5. interrupts
        $display("-- IRQ_STATUS and the write one to clear of IRQ_CLEAR --");
        i_irq = 5'b11111;
        #1;
        axi_read(8'h08, rdat, ok_r);
        expect_equal("IRQ_STATUS follows i_irq", rdat, 32'h0000001F);
        axi_write(8'h0C, 32'h0000000F, 4'hF, ok_w);
        axi_read(8'h08, rdat, ok_r);
        expect_equal("IRQ_CLEAR clears the four low sources", rdat, 32'h00000010);
        axi_read(8'h0C, rdat, ok_r);
        expect_equal("IRQ_CLEAR reads zero", rdat, 32'h00000000);
        i_irq = 5'b00000;
        #1;
        axi_read(8'h08, rdat, ok_r);
        expect_equal("IRQ_STATUS follows i_irq down", rdat, 32'h00000000);
        i_irq = 5'b11111;
        #1;
        axi_read(8'h08, rdat, ok_r);
        expect_equal("a cleared source stays cleared while i_irq holds it", rdat, 32'h00000010);
        i_irq = 5'b00000;
        #1;

        // ============================================================ 6. unmapped slots
        // the map is 0x00 to 0x8C plus the two provisional slots: everything else must read
        // zero, answer OKAY, and change no register at all
        $display("-- unmapped addresses --");
        snapshot_mirror;
        for (k = 0; k < 10; k = k + 1) begin
            case (k)
                0: aoff = 8'h98;
                1: aoff = 8'h9C;
                2: aoff = 8'hA0;
                3: aoff = 8'hF0;
                4: aoff = 8'hFC;
                5: aoff = 8'h01;
                6: aoff = 8'h02;
                7: aoff = 8'h06;
                8: aoff = 8'h8E;
                default: aoff = 8'h93;
            endcase
            axi_read(aoff, rdat, ok_r);
            cmp_unmap = cmp_unmap + 1;
            if ((rdat !== 32'd0) || (ok_r == 0)) begin
                mism_unmap = mism_unmap + 1;
                $display("MISMATCH unmapped read 0x%02X got=0x%08X ok=%0d", aoff, rdat, ok_r);
            end
            axi_write(aoff, 32'hFFFFFFFF, 4'hF, ok_w);
            cmp_unmap = cmp_unmap + 1;
            if (ok_w == 0) begin
                mism_unmap = mism_unmap + 1;
                $display("MISMATCH unmapped write 0x%02X not OKAY", aoff);
            end
        end
        for (i = 0; i < N_MAP; i = i + 1) begin
            slot  = tb_slot(i);
            akind = slot[41:40];
            aoff  = slot[39:32];
            if (akind != K_WO) begin
                axi_read(aoff, rdat, ok_r);
                cmp_unmap = cmp_unmap + 1;
                if (rdat !== mirror[i]) begin
                    mism_unmap = mism_unmap + 1;
                    if (mism_unmap <= 4)
                        $display("MISMATCH unmapped write changed slot %0d addr 0x%02X got=0x%08X was=0x%08X",
                                 i, aoff, rdat, mirror[i]);
                end
            end
        end
        $display("unmapped comparisons: %0d", cmp_unmap);
        $display("unmapped mismatches: %0d", mism_unmap);
        expect_equal("unmapped mismatches", mism_unmap, 0);
        mism_total = mism_total + mism_unmap;
        cmp_total  = cmp_total + cmp_unmap;

        // ============================================================ 7. read while write
        $display("-- read and write in the same cycle --");
        axi_write(8'h68, 32'hA5A55A5A, 4'hF, ok_w);
        axi_write_read(8'h68, 32'h12345678, 8'h68, rdat, ok_w, ok_r);
        expect_ok("simultaneous write answered", ok_w);
        expect_ok("simultaneous read answered", ok_r);
        expect_equal("simultaneous read returns the pre write value", rdat, 32'hA5A55A5A);
        axi_read(8'h68, rdat, ok_r);
        expect_equal("the write landed", rdat, 32'h12345678);
        axi_write(8'h68, 32'h0BADF00D, 4'hF, ok_w);
        axi_write_read(8'h68, 32'hFEEDFACE, 8'h64, rdat, ok_w, ok_r);
        expect_ok("simultaneous write, other address, answered", ok_w);
        expect_ok("simultaneous read, other address, answered", ok_r);
        expect_equal("VERSION_ID read during a write", rdat, 32'h00010001);
        axi_read(8'h68, rdat, ok_r);
        expect_equal("SCRATCH after the second pair", rdat, 32'hFEEDFACE);

        // ============================================================ 8. arm runs
        // The gate: ARM_SELECT selects the arm, the thresholds come out of the register
        // file, and the result equals the fixture of that arm. Both candidate bit
        // attributions of the raw arm are run: b2 cleared and b3 cleared.
        $display("-- triage arm runs against the arm fixtures --");
        do_reset(4);
        // the reset codes of the D8 map come straight out of the frozen package
        axi_read(8'h3C, thr_ratio, ok_r);
        axi_read(8'h40, thr_ent, ok_r);
        expect_equal("RATIO_THRESH reset code", thr_ratio, RATIO_RST32);
        expect_equal("ENTROPY_THRESH reset code", thr_ent, ENTROPY_RST32);
        // The reset code and the model code are one operating point written in two units:
        // 33 in 1/200 units is 0.165 and 10813 in Q16 is 0.164994; 63 in 1/100 units is 0.63
        // and 10322 in Q14 is 0.630005. They agree to within one LSB of their own unit, which
        // is what is checked here, in integers:
        //   |33 * 65536 - 10813 * 200| <= 200   and   |63 * 16384 - 10322 * 100| <= 100
        pr_a = RATIO_RST32 * 32'd65536;
        pr_b = counts[C_RATIO] * 32'd200;
        expect_ok("RATIO_THRESH reset code is the same point as the Q16 code",
                  {31'd0, (((pr_a - pr_b) <= 32'd200) | ((pr_b - pr_a) <= 32'd200))});
        pr_a = ENTROPY_RST32 * 32'd16384;
        pr_b = counts[C_ENT] * 32'd100;
        expect_ok("ENTROPY_THRESH reset code is the same point as the Q14 code",
                  {31'd0, (((pr_a - pr_b) <= 32'd100) | ((pr_b - pr_a) <= 32'd100))});

        // The fixture of an arm was made at the model operating point, and the plan warns that
        // comparing against it while another operating point is loaded compares apples with
        // oranges (final38.md, section 12, Fase 9 risk note). So the operating point code is
        // INJECTED through the bus and read back before any arm is scored. It is also the
        // write/read gate on a second pair of slots.
        write_slot(8'h3C, counts[C_RATIO], 4'hF);
        write_slot(8'h40, counts[C_ENT], 4'hF);
        axi_read(8'h3C, thr_ratio, ok_r);
        axi_read(8'h40, thr_ent, ok_r);
        expect_equal("RATIO_THRESH injected code read back", thr_ratio, counts[C_RATIO]);
        expect_equal("ENTROPY_THRESH injected code read back", thr_ent, counts[C_ENT]);
        expect_equal("o_ratio_thresh follows the injected code", v_ratio, counts[C_RATIO]);
        expect_equal("o_entropy_thresh follows the injected code", v_entropy, counts[C_ENT]);

        // run 1: the default arm set, marked series, both arms required
        axi_write(8'h44, {27'd0, counts[C_ARM_DEFAULT][4:0]}, 4'hF, ok_w);
        axi_read(8'h44, rdat, ok_r);
        arm_rb = rdat[4:0];
        expect_equal("ARM_SELECT default read back", {27'd0, arm_rb}, {27'd0, counts[C_ARM_DEFAULT][4:0]});
        expect_equal("o_arm_select default", v_arm, {27'd0, counts[C_ARM_DEFAULT][4:0]});
        expect_equal("b3 set selects the marked source", {31'd0, arm_rb[3]}, 1);
        expect_equal("b2 set keeps the T wave arm", {31'd0, arm_rb[2]}, 1);
        score_run(1, E_MARK, 3, arm_rb, thr_ratio, thr_ent, "berpenanda",
                  n, mm, fired_cnt, tp, fp, fn, tn);
        runs_fired[0] = fired_cnt;
        $display("arm run berpenanda arm=0x%02X windows=%0d fired=%0d TP=%0d FP=%0d FN=%0d TN=%0d",
                 arm_rb, n, fired_cnt, tp, fp, fn, tn);
        expect_equal("berpenanda windows", n, counts[C_N_MARK]);
        expect_equal("berpenanda fired", fired_cnt, counts[C_FIRED_MARK]);
        expect_equal("berpenanda TP", tp, counts[C_TP_MARK]);
        expect_equal("berpenanda FP", fp, counts[C_FP_MARK]);
        expect_equal("berpenanda FN", fn, counts[C_FN_MARK]);
        expect_equal("berpenanda TN", tn, counts[C_TN_MARK]);
        mism_arm = mism_arm + mm; cmp_arm = cmp_arm + n;

        // run 2: the T wave rule arm cleared, marked series kept: the mapping of the task
        // brief, ARM_SELECT 0x0B, and the answer has to be the raw arm fixture
        axi_write(8'h44, {27'd0, counts[C_ARM_T_OFF][4:0]}, 4'hF, ok_w);
        axi_read(8'h44, rdat, ok_r);
        arm_rb = rdat[4:0];
        expect_equal("ARM_SELECT T rule off read back", {27'd0, arm_rb}, {27'd0, counts[C_ARM_T_OFF][4:0]});
        expect_equal("o_arm_select T rule off", v_arm, {27'd0, counts[C_ARM_T_OFF][4:0]});
        expect_equal("b2 cleared", {31'd0, arm_rb[2]}, 0);
        expect_equal("b3 kept", {31'd0, arm_rb[3]}, 1);
        score_run(0, E_T_OFF, 2, arm_rb, thr_ratio, thr_ent, "t_off",
                  n, mm, fired_cnt, tp, fp, fn, tn);
        runs_fired[1] = fired_cnt;
        $display("arm run t_off      arm=0x%02X windows=%0d fired=%0d TP=%0d FP=%0d FN=%0d TN=%0d",
                 arm_rb, n, fired_cnt, tp, fp, fn, tn);
        expect_equal("t_off windows", n, counts[C_N_RAW]);
        expect_equal("t_off fired", fired_cnt, counts[C_FIRED_RAW]);
        expect_equal("t_off TP", tp, counts[C_TP_RAW]);
        expect_equal("t_off FP", fp, counts[C_FP_RAW]);
        expect_equal("t_off FN", fn, counts[C_FN_RAW]);
        expect_equal("t_off TN", tn, counts[C_TN_RAW]);
        mism_arm = mism_arm + mm; cmp_arm = cmp_arm + n;

        // run 3: the raw series source cleared the other way, b3 clear: the mapping the
        // Fase 9 vector export of this tree uses, ARM_SELECT 0x07, same raw arm fixture
        axi_write(8'h44, {27'd0, counts[C_ARM_RAW_TREE][4:0]}, 4'hF, ok_w);
        axi_read(8'h44, rdat, ok_r);
        arm_rb = rdat[4:0];
        expect_equal("ARM_SELECT raw source read back", {27'd0, arm_rb}, {27'd0, counts[C_ARM_RAW_TREE][4:0]});
        expect_equal("b3 cleared", {31'd0, arm_rb[3]}, 0);
        score_run(0, E_RAW, 3, arm_rb, thr_ratio, thr_ent, "mentah",
                  n, mm, fired_cnt, tp, fp, fn, tn);
        runs_fired[2] = fired_cnt;
        $display("arm run mentah     arm=0x%02X windows=%0d fired=%0d TP=%0d FP=%0d FN=%0d TN=%0d",
                 arm_rb, n, fired_cnt, tp, fp, fn, tn);
        expect_equal("mentah fired", fired_cnt, counts[C_FIRED_RAW]);
        expect_equal("mentah windows", n, counts[C_N_RAW]);
        mism_arm = mism_arm + mm; cmp_arm = cmp_arm + n;

        // the two arms differ, which is what makes the bit a gate rather than a comment
        expect_ok("the T rule arm changes the arm",
                  {31'd0, (counts[C_N_MARK] != counts[C_N_RAW])});
        expect_ok("the T rule arm changes the fired count",
                  {31'd0, (counts[C_FIRED_MARK] != counts[C_FIRED_RAW])});
        expect_equal("both arms keep every AFIB window, marked", counts[C_FN_MARK], 0);
        expect_equal("both arms keep every AFIB window, raw", counts[C_FN_RAW], 0);
        expect_equal("marked arm AFIB windows", counts[C_AFIB_MARK], counts[C_AFIB_RAW]);

        // run 4: one enrolled arm, b4 clear: the entropy arm decides alone
        axi_write(8'h44, {27'd0, counts[C_ARM_SINGLE][4:0]}, 4'hF, ok_w);
        axi_read(8'h44, rdat, ok_r);
        arm_rb = rdat[4:0];
        expect_equal("ARM_SELECT single arm read back", {27'd0, arm_rb}, {27'd0, counts[C_ARM_SINGLE][4:0]});
        // one arm enrolled, marked columns: b3 does not select the source here, so this run
        // claims no source bit and passes -1
        score_run(1, E_TUNGGAL, -1, arm_rb, thr_ratio, thr_ent, "tunggal",
                  n, mm, fired_cnt, tp, fp, fn, tn);
        runs_fired[3] = fired_cnt;
        $display("arm run tunggal    arm=0x%02X windows=%0d fired=%0d", arm_rb, n, fired_cnt);
        expect_equal("single arm fired", fired_cnt, counts[C_FIRED_TUNGGAL]);
        mism_arm = mism_arm + mm; cmp_arm = cmp_arm + n;

        // run 5: the guard run. The entropy threshold is set to bit 15 of the 16 bit field,
        // so nothing can satisfy the entropy arm: this catches a field that is read back or
        // compared at 15 bits or less.
        axi_write(8'h40, counts[C_GUARD_ENT], 4'hF, ok_w);
        axi_read(8'h40, rdat, ok_r);
        expect_equal("ENTROPY_THRESH field holds bit 15", rdat, counts[C_GUARD_ENT]);
        score_run(1, E_GUARD, -1, arm_rb, thr_ratio, rdat, "guard",
                  n, mm, fired_cnt, tp, fp, fn, tn);
        runs_fired[4] = fired_cnt;
        $display("arm run guard      arm=0x%02X ent=0x%08X windows=%0d fired=%0d",
                 arm_rb, rdat, n, fired_cnt);
        expect_equal("guard run fired", fired_cnt, counts[C_FIRED_GUARD]);
        expect_equal("guard run fired is zero", fired_cnt, 0);
        mism_arm = mism_arm + mm; cmp_arm = cmp_arm + n;
        write_slot(8'h40, counts[C_ENT], 4'hF);   // back to the injected operating point

        // run 6: b4 set, either arm is enough: the disjunction cannot fire less often
        axi_write(8'h44, {27'd0, counts[C_ARM_EITHER][4:0]}, 4'hF, ok_w);
        axi_read(8'h44, rdat, ok_r);
        arm_rb = rdat[4:0];
        expect_equal("ARM_SELECT either arm read back", {27'd0, arm_rb}, {27'd0, counts[C_ARM_EITHER][4:0]});
        expect_equal("b4 decides the combination", {31'd0, arm_rb[4]}, 1);
        score_run(1, E_EITHER, 3, arm_rb, thr_ratio, thr_ent, "either",
                  n, mm, fired_cnt, tp, fp, fn, tn);
        runs_fired[5] = fired_cnt;
        $display("arm run either     arm=0x%02X windows=%0d fired=%0d TP=%0d FP=%0d",
                 arm_rb, n, fired_cnt, tp, fp);
        expect_equal("either arm fired", fired_cnt, counts[C_FIRED_EITHER]);
        expect_equal("either arm TP", tp, counts[C_TP_EITHER]);
        expect_equal("either arm FP", fp, counts[C_FP_EITHER]);
        expect_ok("the disjunction fires at least as often as the conjunction",
                  {31'd0, (runs_fired[5] >= runs_fired[0])});
        mism_arm = mism_arm + mm; cmp_arm = cmp_arm + n;

        $display("arm comparisons: %0d", cmp_arm);
        $display("arm mismatches: %0d", mism_arm);
        expect_equal("arm mismatches", mism_arm, 0);
        mism_total = mism_total + mism_arm;
        cmp_total  = cmp_total + cmp_arm;

        // ============================================================ 9. summary
        // the operating point is restored, so the part leaves this testbench as it was
        axi_write(8'h44, {27'd0, ARM_RST}, 4'hF, ok_w);
        axi_write(8'h3C, {16'd0, RATIO_RST}, 4'hF, ok_w);
        axi_write(8'h40, {16'd0, ENTROPY_RST}, 4'hF, ok_w);
        axi_read(8'h44, rdat, ok_r);
        expect_equal("ARM_SELECT restored", {27'd0, rdat[4:0]}, ARM_RST32);
        axi_read(8'h3C, rdat, ok_r);
        expect_equal("RATIO_THRESH restored", {16'd0, rdat[15:0]}, RATIO_RST32);
        axi_read(8'h40, rdat, ok_r);
        expect_equal("ENTROPY_THRESH restored", {16'd0, rdat[15:0]}, ENTROPY_RST32);

        $display("checks: %0d", checks);
        $display("words compared: %0d", cmp_total);
        $display("mismatches = %0d out of %0d", mism_total, cmp_total);
        $display("failures: %0d", fails);
        if (cmp_total == 0) begin
            $display("FATAL nothing was compared: a pass with zero comparisons is a failure");
            $fatal(1, "tb_regs_axi: zero comparisons");
        end
        if ((mism_total != 0) || (fails != 0)) begin
            $display("gate: FAIL, see the lines above");
            $fatal(1, "tb_regs_axi: %0d mismatches, %0d failures", mism_total, fails);
        end
        $display("gate: PASS");
        $display("PASS");
        $finish;
    end

endmodule
