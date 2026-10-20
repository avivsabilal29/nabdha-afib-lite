# template-project: 8-bit counter

Smallest complete project in this repository: RTL, self-checking testbench, lint, simulation, and
synthesis to SKY130 standard cells. Use it to check that your local toolchain works, and as the shape
to copy when you start a real block.

Nothing here is part of AFIB-LITE. It is a one-file, one-module design that a reader can finish in
five minutes, which is the point: if something fails, the failure is in the setup, not in the design.

## Files

| File | What it is |
| --- | --- |
| `counter8.sv` | 8-bit up and down counter, synchronous reset, enable, parallel load, wrap flags |
| `tb_counter8.sv` | Self-checking testbench, prints PASS or FAIL per check and returns a non-zero exit code on failure |
| `tb_throughput.sv` | Cycle harness for the simulator speed comparison, not a functional check |
| `vcd_view.py` | Reads a VCD trace and prints it as text or writes a standalone timing diagram |
| `flow.sh` | lint, simulate on two engines, trace, read the trace, bench, synthesise, area |
| `Makefile` | thin wrapper around `flow.sh` |
| `reports/` | generated: simulation log, Yosys log, netlist JSON |
| `build/` | generated: compiled simulation binary |

## Run it

```bash
cd rtl/template-project
./flow.sh all          # or: make
```

Step by step:

```bash
./flow.sh lint         # Verilator, catches latches, width mismatches, undriven signals
./flow.sh sim          # Icarus, runs the self-checking testbench
./flow.sh synth        # Yosys, maps to sky130_fd_sc_hd cells, writes reports/counter8.json
./flow.sh area         # cell count and area read from the liberty file, nothing estimated
./flow.sh sim-vl       # the same testbench on Verilator instead of Icarus
./flow.sh wave         # run with tracing on, writes reports/counter8.vcd
./flow.sh vcd          # print the trace as text, and write reports/counter8_timing.html
./flow.sh bench        # simulator speed comparison, 1M cycles: ./flow.sh bench 10000000
```

The toolchain is the root-free one in `../rtl-synthesis/debroot`; a system install is used as a
fallback. Override it with `TOOLROOT=/path/to/rtl-synthesis ./flow.sh all`.

## What a clean run looks like

- lint prints `lint clean`, and it covers both `counter8.sv` and `tb_counter8.sv`
- sim prints one `PASS` line per check, then `checks N, errors 0` and `RESULT PASS`
- synth prints the mapped cell count and the chip area from the library
- area prints cell count, flip-flop count, and total area in square micrometres

## Recorded run

Run on this machine on 20 October 2026, with the toolchain in `../rtl-synthesis/debroot`:

| Step | Tool | Result |
| --- | --- | --- |
| lint | Verilator 5.020, `-Wall`, design and testbench | clean, zero warnings |
| sim | Icarus Verilog 12.0, `-g2012` | 22 checks, 0 errors, `RESULT PASS` |
| synth | Yosys 0.33, `sky130_fd_sc_hd` | 67 mapped cells, 10 flip-flops |
| area | `sky130_fd_sc_hd__tt_025C_1v80.lib` | 578.05 um^2, flops 34.6 percent of it |
| sim, second engine | Verilator 5.020, same testbench file | 22 checks, 0 errors, `RESULT PASS` |
| bench 1M cycles | Icarus 3.44 s, Verilator 0.77 s | Verilator 4.5x faster, identical checksum |
| bench 10M cycles | Icarus 33.63 s, Verilator 7.68 s | Verilator 4.4x faster, identical checksum |

No Vivado is involved in any row of that table. Everything here runs on the free toolchain in
`../rtl-synthesis/debroot`. Vivado enters later, for the bitstream and for the Zynq block design,
not for knowing whether the RTL is correct.

The flip-flop count is the useful number to sanity check against: 8 for the counter, 1 for carry, 1
for borrow, and nothing else. Ten is exactly right. If a future change makes it thirteen, something
got registered that should not have been.

## Seeing the result

Three ways, in increasing order of effort. None of them needs Vivado, and none needs a GUI.

**1. The log file.** Every run writes what it checked, one line per check, into `reports/sim.log`:

```
PASS 255 reached: 255
PASS terminal count flag at 255: 1
PASS wrapped to zero: 0
PASS carry pulse on the wrap clock: 1
checks 22, errors 0
RESULT PASS
```

That is the file to read first, and the file to attach to a report. `grep FAIL reports/sim.log` answers
"did anything break" without reading anything else.

**2. The trace as text.** `./flow.sh wave` writes `reports/counter8.vcd`, and `./flow.sh vcd` prints it:

```
zero    ‾‾‾‾‾‾‾‾‾‾‾‾____________________________________‾‾‾______‾‾‾_______________
count     0---------  1  2  3  4  5  6  7  8  9 10254255  0  1---  0255254 90 89 88
carry   ________________________________________________‾‾‾________________________
borrow  ____________________________________________________________‾‾‾____________
load    __________________________________________‾‾‾_________‾‾‾_________‾‾‾______
time_ns  5              55             105            155            205

events:
   165001 ps  tb_counter8.carry pulses
   205001 ps  tb_counter8.borrow pulses
```

Read it like a scope: `count` climbs 0 to 10, jumps to 254 and 255 on `load`, wraps to 0 with `carry`
high for exactly one clock, walks down to 0 and wraps to 255 with `borrow`. Wide signals print in
hexadecimal so a wide bus stays one column, and `-` means unchanged since the previous column.

**3. A real timing diagram.** The same command writes `reports/counter8_timing.html`, a standalone SVG
with a bus for the counter and step waveforms for the flags. Open it in a browser, or in the chat, and
it needs no installed viewer:

    python3 vcd_view.py reports/counter8.vcd --html reports/counter8_timing.html

Useful options: `--signals a,b` to choose signals, `--from 150000 --to 250000` to narrow the window,
`--period` and `--phase` if the clock is not 100 MHz, `--max` to cap the number of columns.

A GUI viewer is nicer for long traces if you want one. The usual choices are Surfer or GTKWave, both
open the same VCD file with no conversion.

## Pitfalls hit while building this

Written down because each one cost real time and will reappear in AFIB-LITE:

1. **`expect` is a SystemVerilog keyword.** Icarus 12 fails the parse with `syntax error` at the task
   declaration and gives no hint that the name is the problem. A task named `check` compiles.
   The failure looks like a broken file, not a reserved word.
2. **Verilator does not lint the testbench unless you ask.** The design linted clean while the
   testbench was unparsable. `flow.sh lint` now runs both, with `--timing` for the testbench.
3. **Task argument widths have to match the call.** A single check task with 32-bit arguments
   produced 44 `WIDTHEXPAND` warnings under `-Wall`. Splitting it into `check8` and `check1` made
   lint silent, which is what makes a clean lint run meaningful.
4. **A blocking assignment in the clock generator trips `BLKSEQ`.** `clk <= ~clk;` is quiet.
5. **Changing an input in the same time step as a rising edge is a race.** The first version of the
   throughput harness set `en` at the same moment as a clock edge. Icarus and Verilator then disagreed
   on the checksum for the same 10 million cycles, by exactly 128, which is 10000000 modulo 256. A
   difference of exactly the wrap residue means the runs were one sample out of alignment, not that
   they computed different logic. Moving the stimulus one nanosecond past the edge made both engines
   print the same checksum to the last digit. Cross-simulator agreement is only meaningful once the
   harness has no such race.
6. **One VCD id code can carry several names.** When a testbench wire is wired straight to a
   submodule port, Icarus declares both names and reuses one code, so `carry` and `carry_o` are one
   signal with two names, and `zero` and `zero_o` likewise. A reader that stores one name per code
   silently loses the testbench level name, which is the one you usually want to see. `vcd_view.py`
   keeps every alias and matches on any of them.
7. **A testbench that passes is not a testbench that is right.** The first version of this one failed
   11 of 20 checks, and every failure was the stimulus sampling one clock late, not the design. Check
   the checker before you believe a failure.

## The rules this file demonstrates

Every rule in `rtl/README.md` appears at least once in `counter8.sv`, so the file doubles as the
worked example:

1. One clock, synchronous active-low reset.
2. Combinational next state computed separately, then one flop bank. This is what keeps latches out.
3. Every branch in the combinational block assigns a default, so no path can infer a latch.
4. `wire` and `reg` only, no `logic`, so Yosys and Vivado accept the same source.
5. `default_nettype none` at the top, restored at the bottom.
6. No delays, no `initial` blocks, no vendor primitives in the synthesisable file.
7. Wrap pulses are registered, so they are exactly one clock wide and easy to observe.

## How to grow this into a real block

1. Copy the shape: one file, one module, one testbench, same three flows.
2. Add the block to `../README.md` file list, or to the plan document in the vault once it exists.
3. Before writing arithmetic, take the widths from the model, not from intuition. For AFIB-LITE the
   authoritative table comes from `../../tools/qformat.py`.
4. Compare against the model bit for bit at every stage. A tolerance-based comparison hides the bug
   you are looking for.
5. Run lint before every simulation and every synthesis. A latch that lint reports is a bug that
   synthesis accepts in silence.
