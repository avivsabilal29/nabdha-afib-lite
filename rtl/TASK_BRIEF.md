# RTL Task Brief: AFIB-LITE Model-to-RTL Port

Audience: the engineer writing SystemVerilog in `rtl/`. You can follow this brief without opening
the vault. Every number here has a source; the vault plan (`36 - Rencana Port Model ke RTL`) carries
the full derivation and the line numbers.

Read `rtl/README.md` first for the agreed house style. This brief adds the model-to-RTL contract, the
per-stage done definitions, and the exact commands that work on this machine.

## 1. Ground rules

1. Never edit `model/rantai-afib-lite/rantai.py` or anything under `model/rantai-afib-lite/fixture/`.
   They are frozen references. `rantai.py` is sha256 `90df6e5b457307d3...`; the fixture
   `fixture/04015_30m.npz` is sha256 `91ff408fb1b7880a...`.
2. Never edit another author's file while they hold it. One file, one owner, one branch.
3. Do not commit and do not `git add`. Aviv commits.
4. Do not delete files without asking Aviv first.
5. Everything inside the repo is English: folder names, file names, module names, port and signal
   names, parameters, `function` and `task` names, `typedef` and `enum` names, comments, headers,
   testbench names, Tcl and XDC comments, CSV column names, and log strings. No non ASCII character
   in an identifier. Units belong in the name or the trailing comment, never assumed: `rr_ms`,
   `ratio_q16`, `latency_cycles`. One module per file, and the file name equals the module name,
   because a mismatch is the most common way a synthesis tool reads the wrong file. Testbenches are
   `tb_<dut>.sv`. A model term that has no English name gets translated once in the package, and the
   translation, with its model counterpart, goes in the file header. The vault plan is Indonesian
   and stays Indonesian: it is the explanation, not the deliverable.
6. One clock domain. `pl_clk0` at 100 MHz drives everything, including the AXI4-Lite port. There is no
   clock-domain crossing in the PL.
7. Target both flows from the same source: SKY130 standard cells through Yosys, and Vivado for the
   KV260 bitstream. No vendor primitives, no FPGA macros, no `initial` blocks outside testbenches.

## 2. What the block does

One lead of ECG at 250 Hz, 16-bit samples, in. Three triage classes out: undecided, normal, needs
review. The pipeline is Pan-Tompkins with two deliberate deviations: a five-point derivative with the
kernel `[2, 1, 0, -1, -2]`, and a moving-window integrator of 38 samples that alternates between 37
and 38 during warm-up.

## 2.1 Where samples come from

The PL never parses a file and never resamples. The locked 16-bit word at 250 Hz arrives already in the
model grid: 409.4 counts per millivolt, clamp at 2047 counts, so one count is 2.4426 microvolts and the
full scale is about 5 mV either way. `model/rantai-afib-lite/adapter.py` owns every format detail on the
PS side: WFDB records (12-bit counts times the header gain and zero level) and Attys sessions (24-bit
frames, bits 23..8 kept and the low byte dropped). Attys device rates 125, 250 and 500 Hz are resampled
to 250 Hz by exact rational linear interpolation, which reduces to 1/2, 1/1 and 2/1 on a shift only path
with no multiplier. Records at 128 Hz and 360 Hz also pass, since 20 October 2026, through a general
exact integer path whose weights reduce to 64/125 and 36/25; that path needs a hard multiplier, which is
the reason the rate is declared once by `open()` and never inferred inside a stream. Comment lines in a
`.hea` header are skipped, so the NSRDB and MITDB headers parse.

Two consequences for RTL. First, a lost sample contaminates the chain memory for 131 samples, which is
524 ms at 250 Hz, counted as 12 + 32 + 4 + 38 + 27 + 18; mark that span through `GAP_COUNT` and let the
window layer ignore it. Second, the clamp marker is strict, so a sample that lands exactly on 2047 is not
marked clamped.

Columns to compare are fixed by the 33 arrays of the fixture, and section 2.8 of the vault plan
carries the full grouping. Three of them are easy to forget: `qrs`, the QRS detection output;
`puncak_acuan_neurokit`, the NeuroKit reference arm, which exists to show the gap to an outside
reference rather than to define parity; and the T-rule-off family, `jendela_aturan_t_mati`,
`jendela_fitur_aturan_t_mati`, `jendela_kelas_aturan_t_mati`, `rasio_pita_aturan_t_mati` and
`rasio_qrs_aturan_t_mati`, which must stay selectable through `ARM_SELECT.b2`.

The RR stage carries four interval marks that the RTL must expose: keep 0, split 1 when the interval
was a missed beat and becomes two exact halves, drop 2 when it was a false detection, and gap 3 when
it was a recording gap. The missed-beat test compares in cross form, `RR_MISS_NUM / RR_MISS_DEN` equal
to 83/50, written as a multiplication so no divider is needed. The rhythm marker runs over eight
intervals, the reseeding history holds 32, and reseeding happens at most once per eight intervals.
Those are buffer lengths rather than time constants, so derive them from the beat or sample counter.

Delay lines are addressed by absolute sample index, and a read of an index that has not arrived yet
returns zero. That is exactly the zero initial condition of the notebook filters, so no separate
padding path is needed. A read of an index that has already left the line is a design error, not a
value to return.

Widths that depend on the recording, measured today by running the same chain over three records at
250 Hz:

| Record | Beats | Peaks | Largest RR (ms) | Largest beat-to-beat gap (samples) | Most search-back candidates | RR width |
|---|---|---|---|---|---|---|
| 04015 | 2596 | 4777 | 51064 | 12766 | 128 | 16 bit |
| 04043 | 3223 | 4617 | 11160 | 2790 | 9 | 15 bit |
| 04126 | 3399 | 4522 | 1304 | 326 | 4 | 12 bit |

Units are easy to mix here: the RR series carries milliseconds and the search-back distance carries
samples, so the same physical gap reads 51064 in one place and 12766 in the other. Registers and queue
storage for RR are milliseconds at 16 bits; the distance accumulator inside the search-back walk is
samples at 15 bits.

Size RR at 16 bits. The 12-bit view holds on 04015 and breaks on 04043, and Python never overflows, so
the fault would appear on the board as false missed beats rather than as a crash. The search-back depth
is not bounded in the model: `state["puncak_nilai"]` grows without pruning, and `search_back` walks every
peak between the last beat and the current peak. Provide 128 entries and add an overflow flag that
lights when the walk passes 128; do not treat 128 as proven for other records. The decision output
buffer is 8 entries deep, because the densest record yields one decision per four beats.

The window feature layer runs over 32-interval windows with a stride of 4 and computes four features:
RMSSD, RMSSD divided by the mean RR, pNN50, and entropy divided by four. Widths measured by
`tools/qformat.py --lapisan-fitur`:

| Node | Range | Width | Q |
|---|---|---|---|
| window of 32 intervals, ms | [200, 1992] | 12 | Q12.0 |
| d = diff(rr), ms | [-1556, 1680] | 12 | Q12.0 |
| d * d, ms squared | [0, 2822400] | 23 | Q23.0 |
| sum of 31 terms, ms squared | [0, 7052752] | 24 | Q24.0 |
| sum divided by 31 | [72.26, 227508.13] | 27 | Q19.8 |
| square root, RMSSD, ms | [8.50, 476.98] | 14 | Q10.4 |
| mean rr, ms | [407, 822.25] | 15 | Q11.4 |
| RMSSD divided by mean rr | [0.0112, 0.6300] | 9 | Q1.8 |
| count of diffs above 50 ms | [0, 29] | 6 | Q6.0 |
| count divided by 31, pNN50 | [0, 0.9355] | 9 | Q1.8 |
| sorted 32 values, ms | [200, 1992] | 12 | Q12.0 |
| 16 middle values after dropping 8 edges, ms | [328, 936] | 11 | Q11.0 |
| spread divided by 16, ms | [0, 27.25] | 10 | Q6.4 |
| histogram 16 bins, counts | [0, 16] | 6 | Q6.0 |
| filled bins divided by total | [0.0625, 1] | 6 | Q2.4 |
| log2 of bin probability, bits | [-4, 0] | 11 | Q3.8 |
| entropy sum, bits | [0, 3.625] | 11 | Q3.8 |
| entropy divided by four, bits | [0, 0.90625] | 9 | Q1.8 |

Four of these have no exact width: log2 and the square root are transcendental or irrational for almost
every input, so the widths above are bounds rather than identities. Pin the implementations yourself, an
integer square root that rounds down and a log2 lookup over 256 entries, and state the rounding in the
file header. Without a pinned implementation, bit parity between model and RTL cannot be reached or
proved.

Two widths are now pinned by Aviv, 20 October 2026. The ratio feature packs as 17 bit Q1.16, because the
threshold sweep parity needs precision 16 while 13 bit would only be enough to store. The threshold
register `RATIO_THRESH` stays 16 bit in 1/200 units, since it holds a scalar and not the feature.

Two widths are set by records other than 04015. Measured over 30 minutes each: the adaptive threshold
stage and the search back stage both need 30 bit on `nsrdb/16265` at 128 Hz, one bit more than 04015
asks for, so build both 30 bit wide. `mitdb/100` at 360 Hz never triggers search back in its 30 minutes,
so that path needs a synthetic vector; the vault plan section 2.2.1 carries the full table.

Two nodes stay unmeasured, and say so rather than guessing: the marked source arm is the active one but
the fixture stores no feature array for it, so its ranges are unknown; and the reference layer in
`acuan_fase.py` was not executed.

## 3. Arithmetic map

Widths are signed two's complement as reported by the model, measured on the frozen fixture. The
authoritative machine-readable table comes from `tools/qformat.py`; treat that script as the source,
not this table.

| Stage | Width | Q format | Rounding rule | Source |
|---|---|---|---|---|
| input quantize | 16 | Q12.4 | `np.rint`, round half to even | `rantai.py:163` |
| low-pass | 22 | Q18.4 | integer only | `rantai.py:182` |
| high-pass | 26 | Q22.4 | integer only | `rantai.py:204` |
| derivative | 24 | Q17.7 | truncate toward zero | `rantai.py:228` |
| shift right 8 | 24 | Q9.7 | arithmetic shift, floor | `rantai.py:244` |
| square | 30 signed, 29 unsigned | count squared | none | `rantai.py:244` |
| window 38 | 33 signed, 32 unsigned | count squared | none | `rantai.py:244` |
| adaptive threshold | 29 signed, 28 unsigned | Q29.0 | arithmetic shift, floor | `rantai.py:683` |
| search back | 29 signed, 28 unsigned | Q29.0 | none | `rantai.py:683` |
| RR interval | 12 | Q12.0 samples | floor of integer mean | `rantai.py:496` |
| T-wave discriminant | 23 signed, 22 unsigned | Q9.7 | arithmetic shift | `rantai.py:340` |

Two rounding rules coexist on purpose.

* The derivative truncates toward zero, at `rantai.py:228`, written as `s // 8 if s >= 0 else -((-s) // 8)`.
  It keeps the derivative antisymmetric. Replacing it with a floor injects a negative bias of up to
  7/8 of a count.
* Every other right shift is an arithmetic shift, which floors. Theorem 6 in the model depends on that
  identity: `a + ((p - a) >> 3) == (7a + p) // 8`. Truncation toward zero breaks it, and the model
  measures 87316 of 200000 threshold pairs diverging when it is broken.
* A third rule hides in the adapter: `np.rint` at `rantai.py:163` rounds half to even, so `rint(2.5)`
  is 2.

Measured trap: the derivative raw sum is always divisible by 8 on the frozen fixture, 0 of 450000
samples leave a remainder. The fixture therefore cannot test the truncation rule. Add a synthetic
pulse vector with the raw sums `[0, 2, 1, 0, -1, -2]`; floor gives -1, truncation gives 0.

Worst-case widths, distinct from the measured widths above: the square bound times 38 gives 37 bits
for the window, and the derivative bound is 25 bits, not 24. Size registers from the worst case when
you can afford it, and record which width you chose and why.

## 4. Interface contract

Three contracts exist in the tree and they disagree. Resolve in this order:

| Item | Decision |
|---|---|
| Inner block stream ports | `s_tdata`, `s_tvalid`, `s_tready`, `s_tlast` as in `rtl-synthesis/template/design_template.sv` |
| Top-level sample ports | `sample_data`, `sample_valid`, `sample_gap`, `sample_last` as in `rtl/README.md:29` |
| Class encoding | `rtl/README.md:33` wins: 0 undecided, 1 normal, 2 needs review. `design_template.sv:31` currently says the opposite and is wrong |
| Confidence | 0 to 1000 in model grid units, not a standard deviation |
| `tdata` bit alignment | 12 significant bits, left justified |
| Sample enable | 250 Hz from `pl_clk0`; `100e6 / 400000 = 250.0` exactly, so the terminal count is 399999 |
| AXI clock | `pl_clk0`. No CDC in the PL |
| Divider register width | 20 bits; 399999 needs 19 |

Register map, AXI4-Lite, 25 slots. Reset values put the triage operating point and the feature arm
selection in registers instead of constants. Full table with fields is in the vault plan section 3.

| Offset | Name | Width | Access | Reset | Meaning |
|---|---|---|---|---|---|
| 0x00 | `CTRL` | 32 | RW | 0x00000000 | b0 pipeline enable, b1 soft reset, b2 continuous replay, b3 clear counters, b4 burst one window |
| 0x04 | `STATUS` | 32 | RO | 0 | b0 busy, b1 decision valid, b2 gap seen, b3 input saturated, b4 FIFO overflow, b5 warm-up done, b7 clock alive |
| 0x08 | `VERSION_ID` | 32 | RO | 0x00010001 | low half RTL revision, high half fixture revision |
| 0x0C | `ARM_SELECT` | 32 | RW | 0x0000000F | b0 ratio arm, b1 entropy arm, b2 T-wave rule, b3 marked-series source |
| 0x10 | `RATIO_THRESH` | 16 | RW | 33 | ratio threshold in 1/200 units; 33 is 0.165 |
| 0x14 | `ENTROPY_THRESH` | 16 | RW | 63 | entropy threshold in 1/100 units; 63 is 0.63 |
| 0x18 | `SAMPLE_IDX` | 32 | RO | 0 | free-running sample counter |
| 0x1C | `BEAT_COUNT` | 24 | RO | 0 | accepted beats |
| 0x20 | `WINDOW_COUNT` | 24 | RO | 0 | completed decision windows |
| 0x24 | `GAP_COUNT` | 16 | RO | 0 | detected sample gaps |
| 0x28 | `CLASS_OUT` | 8 | RO | 0 | b1:0 class, b7 valid |
| 0x2C | `CONFIDENCE` | 16 | RO | 0 | 0 to 1000 |
| 0x30 | `FEATURE_RATIO` | 16 | RO | 0 | last ratio feature, 1/200 units |
| 0x34 | `FEATURE_ENTROPY` | 16 | RO | 0 | last entropy feature, 1/100 units |
| 0x38 | `LAST_RR` | 16 | RO | 0 | last accepted RR interval in samples |
| 0x3C | `RR_QUEUE_LEN` | 8 | RO | 0 | filled entries of the eight-deep queue |
| 0x40 | `SCRATCH` | 32 | RW | 0 | write-read test for the bridge |
| 0x44 | `SAMPLE_IN` | 16 | WO | 0 | PS normally writes the sample stream here |
| 0x48 | `SAMPLE_IN_STATUS` | 32 | RO | 0 | written count and FIFO level |
| 0x4C | `DEBUG_SEL` | 8 | RW | 0 | node index exposed on `DEBUG_VAL` |
| 0x50 | `DEBUG_VAL` | 32 | RO | 0 | internal node value, signed |
| 0x54 | `WINDOW_STEP` | 8 | RW | 4 | decision window stride in beats |
| 0x58 | `WINDOW_BEATS` | 8 | RW | 32 | decision window length in beats |
| 0x5C | `REPLAY_LEN` | 32 | RW | 0 | replay length in samples |
| 0x60 | `REPLAY_PTR` | 32 | RO | 0 | replay read pointer |
| 0x64 | `ID_EXPECT` | 32 | RO | 0x41464942 | constant "AFIB" for address-decode testing |
| 0x68 | `GAP_THRESH` | 16 | RW | 1000 | samples of silence that count as a gap |

## 5. File layout

```
rtl/
  README.md            house style, interface, layout. Read first.
  TASK_BRIEF.md        this file.
  afib_lite_pkg.sv     widths, constants, and types taken from the model.
  acq_frontend.sv      sample index, sample enable, gap detector.
  bandpass.sv          low-pass then high-pass.
  derivative.sv        five-point kernel and the shift by 8.
  square.sv            squaring with the defined shift order.
  integrator.sv        moving window, 37 and 38 alternating.
  peak_detect.sv       adaptive threshold, refractory, T-wave rule, search back.
  rr_series.sv         RR queue, eight-interval mean, rhythm marker.
  features.sv          four window features.
  classifier.sv        three-class decision, thresholds from registers.
  regs_axi.sv          AXI4-Lite register file.
  afib_lite_top.sv     top level, wires the blocks and the sample path.
  tb/                  one testbench per block plus the integration testbench.
```

Synthesis and simulation live in `rtl-synthesis/`. Board files live in `fpga/`. Do not add a second
copy of a runner script inside `rtl/`.

## 6. Done definition per stage

Every stage carries the same bar: the testbench compares against golden vectors exported from the
model and reports zero mismatched words. Tolerance is not a pass. A stage is done when:

1. `run_lint.sh` reports clean, and every warning would have been a hard failure of the same class as
   the intentional latch test (Verilator exits 1 on warnings here).
2. The per-stage testbench reports zero mismatches on the frozen fixture for that stage's columns.
3. The integration testbench reports zero mismatches for the columns completed so far.
4. The stage header states the equation, the width, the Q format, and the rounding rule it uses.
5. The synthesis number for the stage is recorded in `rtl-synthesis/reports/` with the tool version,
   the route, the date, and the hour.

Stage order and the minimum subset for day one:

| Stage | Files | Accept when |
|---|---|---|
| 0 | `afib_lite_pkg.sv`, `tb/tb_harness.sv` | golden against golden gives zero mismatches |
| 1 | `acq_frontend.sv` | 250 Hz exact, gap counter matches the fixture |
| 2 | `bandpass.sv` | `lp` and `hp` columns bit-identical |
| 3 | `derivative.sv`, `square.sv`, `integrator.sv` | `turunan`, `kuadrat`, `jendela` columns bit-identical |
| 4 | `peak_detect.sv` | `puncak` column bit-identical, warm-up 23 to 32 beats |
| 5 | `rr_series.sv` | 0 of 2595 intervals differ |
| 6 | `features.sv`, `classifier.sv` | class identical after dropping warm-up |
| 7 | `regs_axi.sv`, `afib_lite_top.sv` | register read-back from Linux matches |

Stages 0 to 3 are the minimum that still proves something: bit parity on four fixture columns.

## 7. How to run things

The tools are not on `PATH`. They live in `rtl-synthesis/debroot/usr/bin/`, and the runner scripts
already point there.

```bash
cd ~/hackathon-semiconductor-programs/nabdha-afib-lite/rtl-synthesis

# machine readiness gate: 13 PASS, exit 0
bash setup_check.sh

# lint before every simulation. Warnings are hard failures.
./run_lint.sh template/design_template.sv design_template
./run_lint.sh ../rtl/bandpass.sv bandpass

# simulate
./run_sim.sh template/tb_template.sv template/design_template.sv
./run_sim.sh ../rtl/tb/tb_bandpass.sv ../rtl/bandpass.sv

# synthesize to SKY130 cells and area
./run_synth.sh demo_counter.sv demo_counter

# widths, Q formats, saturation points, rounding rules per node
cd .. && /home/avivsabilalm/.venvs/afib-lite/bin/python tools/qformat.py
```

Verified versions on this machine: Yosys 0.33 (git sha1 2584903a060), Icarus Verilog 12.0,
Verilator 5.020, Docker 29.1.3. OpenROAD, KLayout, OpenSTA, cocotb, and librelane are absent, so
gate-level and timing verification stay out of scope.

Two practical notes. `run_sim.sh` passes extra arguments to `iverilog`, but its final line runs `vvp`
without `"$@"`, so runtime plusargs such as `+GOLD=<file>` must arrive through an environment variable
until that line is fixed. Synthesis report names carry only a date, so two runs in one day overwrite
each other; add the hour and a lane tag.

## 8. Golden vectors and parity

Export vectors from the model instead of typing numbers into a testbench. Retyped numbers have already
caused bugs here. The fixture is a valid oracle: rerunning the chain over `fixture.masukan16` gives
zero differences on 13 columns across 450000 samples in 9.27 seconds.

Parity proof per stage: export the input and output of each stage to a file, read it in the testbench
with `$readmemh`, compare word by word, and fail on the first mismatch with its index. A proven
harness checks gold against gold first, then raises one count and expects exactly one mismatch at index
1000, then truncates the vector and expects a `$readmemh` warning plus 1048 mismatches.

When parity breaks, bisect in this order: quantize, low-pass, high-pass, derivative, shift,
square, window, threshold, search back, RR queue, features, classifier. Compare the first differing
sample index at each node, because the first divergence localizes the fault.

## 9. Pitfalls that already cost time here

| Symptom | Cause |
|---|---|
| Parabola-shaped error, clean lint | Width copied from theory instead of from `tools/qformat.py` |
| Correct on positives, wrong on negatives | Sign extension across mixed widths, or `>>` on a signed value |
| Derivative shifted by half a sample | Truncation toward zero and arithmetic shift swapped |
| Reported width above 64 bits | Square maximum computed inside `int64`, which overflows |
| First 23 or 24 beats are garbage | Threshold initialised from zero instead of the first two seconds |
| Window drifts one sample after reset | 37 or 38 chosen from a local counter instead of the model constant |
| Two runs, same netlist, different area | Tool version differs between routes, so record it |
| Area tiny and `flip-flops 0` | `dfflibmap` skipped in the Yosys sequence |
| Raw-arm numbers changed with nobody touching the detector | The window source switch defaulted differently, so set `sumber` explicitly |

## 10. Open decisions that block work

Four items need Aviv's answer before the first testbench. Recommended defaults sit in the vault plan
section 14; the ones that change RTL shape are the class encoding, the port contract, the `tdata`
alignment, and the confidence unit. The register reset values for the triage operating point follow
the locked P1 pair, ratio 0.165 and entropy 0.63, not the 0.21 and 0.70 constants that the frozen model
still carries in its own source.
