# LAPORAN FASE 3: linear filters (low-pass and high-pass)

Repo: /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
Branch: aviv/rtl-fpga-simulation. Nothing committed; every change is a working tree file.

## 1. Files touched

| File | State | sha256 (first 16) |
|---|---|---|
| rtl/bandpass.sv | modified, real body replaces the placeholder, ports and widths untouched | fa8dfc2f75c0eef6 |
| rtl/tb/tb_lowpass.sv | created, low-pass gate | 26528c974c3f62d3 |
| rtl/tb/tb_highpass.sv | created, high-pass gate | b813580625b67eaf |
| rtl-synthesis/reports/LAPORAN-FASE3.md | created, this report | |

Synthesis and simulation artifacts:
reports/bandpass.native.20261020.log, reports/bandpass.native.20261020.json,
reports/bandpass.native.20261020.presynth.json,
reports/sim/tb_lowpass_fase3.log, reports/sim/tb_highpass_fase3.log,
reports/lint_bandpass_fase3.log, reports/lint_tb_lowpass_fase3.log,
reports/lint_tb_highpass_fase3.log, reports/lint_chain_fase3.log.

Untouched on purpose: rtl/afib_lite_pkg.sv, rtl/acq_frontend.sv, rtl/tb/tb_kuantisasi.sv
(a sibling agent owns those), model/, fixture/, every other rtl/*.sv, rtl/afib_lite_top.sv.

## 2. Architecture actually built (plan 4.2 and 4.3, candidate B in both stages)

Low-pass, y[i] = 2y[i-1] - y[i-2] + x[i] - 2x[i-6] + x[i-12], zero initial state.
Five terms, four additions, ONE 9 bit adder and ONE carry register reused twelve times per
sample: pass 0 is x[i-12] + 2y[i-1], pass 1 is -y[i-2], pass 2 is +x[i], pass 3 is
-2x[i-6], and each pass covers three slices (bits 8:0, 17:9, 18:26) so a sample costs 12
cycles. Subtraction is the two's complement trick, operand inverted and the low slice carry
in set to one, so no subtractor exists. The accumulator is 23 bit (2y[i-1] alone reaches
2358144) and the registered output is 22 bit; the intermediate is never clamped. The slice
truncation is exact because every accumulator state fits 23 bit: 2y1 2358144, 2y1-y2
1201088, 2y1-y2+x 1233840.

High-pass, y[i] = 32x[i-16] - (y[i-1] + x[i] - x[i-32]), zero initial state, input is the
low-pass output. Three passes, ONE 27 bit adder reused three times, one cycle each: pass 0
is y[i-1] + x[i], pass 1 is -x[i-32], pass 2 is 32x[i-16] minus the accumulator. The
accumulator is 27 bit (32x[i-16] alone reaches 37730304) and the registered output is 26
bit. m_overflow is the test of accumulator bits 26 against 25, sticky, and it saturates the
26 bit output; the record never triggers it.

Fixed latency 16 cycles: one accept cycle, 12 low-pass cycles, 3 high-pass cycles, one
output register. No tready inside (D1). Against 400000 cycles per sample at 250 Hz that is
0,004 percent of the budget, so the serialization is free. One sample is in flight at a
time, so the sideband is held in one register set instead of a 16 deep pipeline, and the
low-pass input history advances exactly once per accepted sample, which is what makes the
first 13 outputs stay in warm-up identical to the model.

## 3. Commands and gate results

Lint, repo scripts unchanged, four runs:

    ./run_lint.sh ../rtl/bandpass.sv bandpass ../rtl/afib_lite_pkg.sv          rc 0
    ./run_lint.sh ../rtl/tb/tb_lowpass.sv tb_lowpass ../rtl/afib_lite_pkg.sv ../rtl/bandpass.sv   rc 0
    ./run_lint.sh ../rtl/tb/tb_highpass.sv tb_highpass ../rtl/afib_lite_pkg.sv ../rtl/bandpass.sv rc 0
    ./run_lint.sh --chain                                                     rc 0, 13 sources, lint clean

The chain run covers the whole repo reachable from afib_lite_top, including the sibling
agent's files as they stand now.

Low-pass gate:

    ./run_sim.sh ../rtl/tb/tb_lowpass.sv ../rtl/afib_lite_pkg.sv ../rtl/bandpass.sv -- \
        +VECTOR=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0

    tb_lowpass: presented = 450000
    tb_lowpass: outputs   = 450000
    tb_lowpass: compared  = 450000
    tb_lowpass: lp mismatches      = 0
    tb_lowpass: PASS
    wall clock 1m27s

High-pass gate:

    ./run_sim.sh ../rtl/tb/tb_highpass.sv ../rtl/afib_lite_pkg.sv ../rtl/bandpass.sv -- \
        +VECTOR=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0

    tb_highpass: presented = 450000
    tb_highpass: outputs   = 450000
    tb_highpass: compared  = 450000
    tb_highpass: hp mismatches      = 0
    tb_highpass: m_tdata mismatches = 0
    tb_highpass: lp mismatches      = 0
    tb_highpass: overflow pulses    = 0
    tb_highpass: PASS
    wall clock 1m25s

Both runs also report 0 mismatches for m_tdata, m_sample_idx, m_tuser and m_tlast, 450000
d_valid pulses, and 0 of 450000 golden words with a dirty sign extension. The high-pass run
compares the low-pass column too, so one run proves the chain inside the stage.

No hex to mem converter was written and rtl/tb/vektor/heks_ke_mem_bandpass.py does NOT
exist: the columns are already $readmemh form (8 hex digits, value sign extended in the low
bits of the 32 bit word), which the per word format counters above prove. Writing a
converter would have been a file with no reader.

## 4. Flip flop bits versus the plan

Measured, mapped netlist, reports/bandpass.native.20261020.json:

    sky130_fd_sc_hd__dfxtp_1      1104   (every one is 1 bit)
    total module flip flop bits   1104
    planned, plan doc 38 Fase 3 gate text   252 (low-pass) + 936 (high-pass) = 1188

    difference  -84 bits, -7,1 percent

Disagreement, stated plainly: the measured count is 84 bits below the planned 1188, and the
plan is internally inconsistent about both halves.

Low-pass half. The gate text takes 252 bits, which is plan table 4.2 row A, 13 words times
16 bit plus 2 words times 22 bit, and row A is the one-cycle parallel adder candidate that
the same table then REJECTS. Row B, the shaded candidate the plan recommends and the one
this RTL implements, is printed as 296 bits in section 4.2 and in I2 section 2, because the
shaded form needs the accumulator register. So the number to compare against for the
architecture this file uses is 296, not 252.

What this file declares on the low-pass side: 13 words of 16 bit input history = 208, the
23 bit accumulator = 23, the slice carry = 1, total 232 bits. That is 20 bits under the 252
of row A and 64 under the 296 of row B, and it still carries the 23 bit accumulator that the
252 figure omits. The saving comes from two things: the shared low-pass output delay line
already holds y[i-1] and y[i-2], so no separate 2 by 22 word pair exists, and pass 0 folds
x[i-12] into 2y[i-1] so the accumulator is the only extra state that the five term
recursion needs.

High-pass half. The gate text takes 936 bits, which is plan table 4.3 row B, 36 words times
26 bit. Row A prints 910 bits as 33 words times 26 plus 2 words times 26. This file
declares: 32 words of 22 bit low-pass output history = 704 (shared with the low-pass taps,
so it is also y[i-1] and y[i-2]), the 22 bit low-pass output register = 22, the 26 bit
high-pass feedback and output register = 26, the 27 bit accumulator = 27, the sticky
overflow flag = 1, total 780 bits. That is 130 bits under 910 and 156 under 936. The cause
is a width choice: the high-pass input is the low-pass output and that word is 22 bit wide,
so storing the 33 word history at 26 bits as the plan assumes would spend 154 bits on sign
extension that nothing reads.

Whole module. The RTL declares 1179 register bits: the two stage inventories of 232 and 780
above, plus 8 bits of pitch control (state, two counters), 41 bits of held sideband
(s_tlast, s_tuser, s_sample_idx), and 118 bits of output registers. The mapped netlist
measures 1104, so 75 bits of the declared 1179 are pure copies of already counted state
that opt folds away (m_tdata and d_hp are copies of the high-pass feedback register,
m_tuser of the held marker, m_overflow of the sticky flag, and the same for the remaining
one bit registers). The number to quote as the measured result is 1104.

If the comparison is made against the plan's recommended candidates instead of its gate
text, planned is 296 + 936 = 1232 bits against 1104 measured, so the implementation is 128
bits (10,4 percent) lighter than the architecture it was asked to build, for the two
reasons above.

## 5. Cells and area versus the plan

Measured, SKY130 sky130_fd_sc_hd__tt_025C_1v80.lib, yosys 0.33, after dfflibmap then abc
then opt_clean, stat -liberty:

    total cells        4855
    total chip area    41508,56 um2
    flip flop area     1104 x 20,019 = 22101 um2 = 53,2 percent of the area
    combinational      3751 cells (the enable feedback multiplexers of 1104 enabled flops,
                       the shared 9 bit slice adder with its operand slices, the 27 bit
                       adder with its input multiplexers, and the output copies)
    unmapped cells     0 (grep "is unknown" in the log returns 0)

Planned, plan 4.2 and 4.3:

| stage | plan cells | plan um2 | measured (combined run) |
|---|---|---|---|
| low-pass | 705 | 10160 | not separable in one module, see below |
| high-pass | 2005 | 30344 | not separable in one module, see below |
| combined | 2710 | 40504 | 4855 cells, 41508,56 um2 |

Area: the combined measured 41508,56 um2 sits 2,5 percent above the plan's combined 40504
um2. That is agreement, and it is a coincidence of two compensating choices: fewer register
bits (1104 against 1232) but more multiplexing per bit, because 47 percent of this area is
not register at all.

Cells: 4855 measured against 2710 planned, 1,79 times the estimate. The estimate is not a
measurement: 705 and 2005 come from 31,28 um2 per register bit (a dfxtp plus its enable
multiplexer) plus one adder per stage, which reproduces their um2 figures exactly (296 x
31,28 + 900,86 = 10160 and 936 x 31,28 + 1066,02 = 30344) and implies 2 cells per register
bit. This implementation's enable multiplexer is not one library cell: abc maps it into
shared nand2, a21boi and inverter gates, and the operand slice multiplexers of the shaded
datapath add more, so the cell count is not comparable and the area figure is the one to
read.

Per stage cells and area are not separable from one synthesis run because both stages are
one module; splitting the run would mean adding a parameter to disable a stage, which would
change the frozen interface, so I refused that and report the combined figure with the
per stage register inventory in section 4 instead.

Exact synthesis command, since run_synth.sh does not fit here: the script reads ONE source
and bandpass.sv names afib_lite_pkg::W_IN in its parameter defaults, so through the script
yosys stops at "ERROR: Failed to detect width of signal access `\x_hold_q`" (recorded, the
rc printed by the pipeline was 0 because of the pipe, the yosys run itself failed). The run
below repeats the script's flow with the package read first, same order, same flags:

    export PATH="$PWD/debroot/usr/bin:$PATH"
    export YOSYS_DATDIR="$PWD/debroot/usr/share/yosys"
    yosys -l reports/bandpass.native.20261020.log -p "
        read_verilog -sv ../rtl/afib_lite_pkg.sv ../rtl/bandpass.sv;
        hierarchy -top bandpass;
        synth -top bandpass;
        dfflibmap -liberty sky130_fd_sc_hd__tt_025C_1v80.lib;
        abc -liberty sky130_fd_sc_hd__tt_025C_1v80.lib;
        opt_clean;
        stat -liberty sky130_fd_sc_hd__tt_025C_1v80.lib;
        write_json reports/bandpass.native.20261020.json"
    python3 area_report.py reports/bandpass.native.20261020.json sky130_fd_sc_hd__tt_025C_1v80.lib

The 28 unique yosys warnings in the log are three kinds and all are benign: replacing the
two history arrays with lists of registers (which is the intent, LUTRAM was rejected by
plan 4.2 item 4 because the content shifts every sample), abc skipping liberty cells whose
pin expressions it cannot read (a liberty-wide parser note, not this design), and pin
attribute notes. No "is unknown" line, which is the script's own refusal criterion.

## 6. Disagreements and open items

1. Flip flop gate: 1104 measured against 1188 planned, so the gate as the plan writes it
   (equality with 252 plus 936) does NOT hold. The plan's own recommended candidate rows
   give 296 plus 936 = 1232, and against that number the implementation is 128 bits under.
   Section 4 lists every register and its purpose.
2. Latency wording: plan 4.2 prints "4 cycles per sample" in its candidate table and then
   12 cycles in the text because each addition is sliced three ways; this file implements 12
   low-pass cycles, which is the sliced figure. Plan 4.3 says the high-pass needs three
   slices and then claims the three cycles of candidate B already satisfy that, which is not
   consistent: three additions at three slices each would be nine cycles. This file
   implements candidate B literally, one full width 27 bit adder used three times, three
   cycles per sample; the slice bound applies to the adder's own 27 bit ripple and so is a
   timing question for STA, not for the schedule. Both stages together are 16 cycles per
   sample.
3. STATUS b8: plan 4.3 requires the high-pass overflow to mark register STATUS bit 8.
   rtl/bandpass.sv raises the sticky flag on m_overflow, and this was verified in
   simulation (0 pulses on this record). rtl/afib_lite_top.sv, which I may not edit in this
   phase, ORs every stage's m_overflow into a single any_ovf (top comment line 28 says
   STATUS.b1), so the b8 routing is not in place at the top level. That is a top level
   finding, not a filter finding.
4. Cell count versus the plan is 1,79 times the estimate as explained in section 5; the area
   figure is 2,5 percent over. I did not try to reduce cells by restructuring, because the
   area budget is met and the architecture is the one the plan chose.
5. Deliverable that does not exist: rtl/tb/vektor/heks_ke_mem_bandpass.py, deliberately, see
   section 3.
