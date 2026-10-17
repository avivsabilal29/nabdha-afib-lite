# Task brief: SKY130 synthesis

**Deliverable:** a working synthesis flow on your own laptop, one report per design revision, and the
area numbers that go into the final report.
**When:** start now. This work does not wait for the finished RTL, because the flow is the hard part
and the RTL arrives late.

Two exit codes to remember: `./setup_tools.sh` ends at 0 when the install is ready, and
`./setup_check.sh` ends at 0 with **13 PASS** lines. Anything else means stop and fix the install
before you synthesise anything.

## 1. What you own

You turn SystemVerilog into standard cells and report what it costs: how many cells, how many
flip-flops, and how much area in square micrometres. You are the person who answers "how big is this
block" with a number and a log behind it.

You do not write the RTL. You do not measure timing on your laptop, and section 7 explains why and
where that number comes from instead.

## 2. What you learn, and how you prove it

| Skill                                 | You prove it by                                                                                |
| ------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Run an open synthesis flow end to end | `./setup_check.sh` reports 13 PASS and exit code 0 on your laptop                              |
| Read a liberty file                   | Naming the corner, the cell count, and the flip-flop area from the file itself                 |
| Explain technology mapping            | Telling the group what `synth` does, what `dfflibmap` does, and what `abc` does, in that order |
| Explain why area needs a check        | Reproducing the `dfflibmap` trap and showing the two areas for one netlist                     |
| Compare two tool versions honestly    | Reporting one design under two versions and refusing to treat the numbers as comparable        |
| Find the expensive part of a design   | Reading a flop-share figure and naming the change that removes flops                           |
| Know what timing needs                | Listing the routes to a critical path and why none of them is this laptop                      |

## 3. Set up your own laptop

### What you need

- Ubuntu 22.04 or 24.04 on x86-64. Another Debian derivative usually works, and the check script
  prints your kernel and distribution so you can see what it ran on.
- `python3` with `venv`, `curl`, and `git`.
- About 100 MB of disk for the tools, plus 13 MB for the library, plus logs.
- Network access to `archive.ubuntu.com` and `raw.githubusercontent.com`.
- **sudo is optional.** Part 1a installs everything into this folder with no root. Part 1b uses your
  package manager if you have sudo. Both modes are supported by the scripts.

### 1a. No-root setup, works without sudo

```bash
cd rtl-synthesis

# 1. tools: Yosys 0.33 native, ABC, Icarus Verilog 12.0, Verilator 5.020
./setup_tools.sh              # fetches 18 MB, unpacks 62 MB into ./debroot, exits 0

# 2. the standard-cell library. -f makes curl fail instead of saving an error page
curl -fL -o sky130_fd_sc_hd__tt_025C_1v80.lib \
  https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/master/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
wc -c sky130_fd_sc_hd__tt_025C_1v80.lib       # expect 12800135

# 3. the gate
./setup_check.sh              # expect 13 PASS and exit code 0
```

`setup_tools.sh` runs `apt-get download` and `dpkg-deb -x`, which fetch the .deb files and unpack them
into `./debroot`. Nothing touches the system, and `rm -rf debs debroot` undoes it.

Two traps in that block, both harmless once you know them:

- **`curl` without `-f` reports success on a 404.** A wrong branch name returns a 14-byte file whose
  content is `404: Not Found`, and the byte count is the only clue. Check the count, and keep `-f` so
  the command fails loudly.
- **`apt-get download` needs a populated package cache.** On a fresh machine it answers
  `E: Unable to locate package yosys` and exits 100. The cache lives in `/var/lib/apt/lists`, so
  refreshing it needs root. Run `sudo apt update` once, then rerun the script.

### 1b. With sudo, if you have it

```bash
sudo apt update
sudo apt install yosys yosys-abc iverilog verilator curl
curl -fL -o sky130_fd_sc_hd__tt_025C_1v80.lib \
  https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/master/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
wc -c sky130_fd_sc_hd__tt_025C_1v80.lib       # expect 12800135
./setup_check.sh
```

The scripts pick up either install. A system install needs no `-B`, no `YOSYS_DATDIR`, and no
`VERILATOR_ROOT`, and the scripts add those only when they use the local `./debroot`.

### 1c. Optional: the WASM route

Route A runs Yosys 0.70 built for WebAssembly, inside a virtual environment. It bundles its own ABC,
and it costs about 136 MB on disk, mostly wasmtime.

```bash
./setup_tools.sh --wasm      # adds ./.venv with yowasp-yosys 0.70.0.0.post1259
YOSYS=.venv/bin/yowasp-yosys ./run_synth.sh demo_counter.sv demo_counter
```

Two routes, two sets of numbers. Pick one, write it in every report, and never compare across them.
`run_synth.sh` puts the route in every output file name for exactly this reason.

|                      | Route A, WASM                                  | Route B, native                                     |
| -------------------- | ---------------------------------------------- | --------------------------------------------------- |
| Binary               | `.venv/bin/yowasp-yosys`                       | `debroot/usr/bin/yosys`                             |
| Version              | 0.70, package `yowasp-yosys` 0.70.0.0.post1259 | 0.33, packages `yosys` and `yosys-abc` 0.33-5build2 |
| Install cost         | about 136 MB, mostly wasmtime                  | those two packages are 9 MB of the 18 MB fetch      |
| `demo_counter.sv`    | 35 cells, 311.55 um^2, 51.4 percent flops      | 33 cells, 316.5536 um^2, 50.6 percent flops         |
| `demo_integrator.sv` | 1,396 cells, 16,442.02 um^2, 58 percent flops  | 1,885 cells, 20,275.70 um^2, 47.6 percent flops     |

The gap between the routes is real and comes from different optimisation in two Yosys releases. The
same release on two machines reproduces to the last digit.

### 1d. What the tools are, and what each one does for you

| Tool             | What it does for you                                                    | Where it came from                                    |
| ---------------- | ----------------------------------------------------------------------- | ----------------------------------------------------- |
| Yosys            | reads RTL, optimises it, maps it onto library cells, writes the netlist | `yosys` package, or `yowasp-yosys` for the WASM build |
| ABC              | the combinational mapper, invoked as `abc -liberty`                     | `yosys-abc` package, a separate .deb                  |
| Icarus Verilog   | compiles and runs the testbench before you synthesise anything          | `iverilog` package                                    |
| Verilator        | lints SystemVerilog and fails on warnings                               | `verilator` package                                   |
| The liberty file | describes every available cell, its area, and its timing tables         | one 12.8 MB file, fetched with curl                   |

### 1e. If a check fails

| Message or symptom                                  | Cause                                        | Fix                                                              |
| --------------------------------------------------- | -------------------------------------------- | ---------------------------------------------------------------- |
| `yosys: command not found`                          | neither install exists                       | run `./setup_tools.sh`, or install with sudo                     |
| `E: Unable to locate package yosys`, exit 100       | empty apt cache                              | `sudo apt update`, then rerun                                    |
| `curl` exits 0 but the library is 14 bytes          | a 404 page saved under the library name      | use `-f`, and check for 12800135 bytes                           |
| `Can't open include file verilatedos.h`             | Verilator called without its data directory  | use `./run_lint.sh`, which sets `VERILATOR_ROOT`                 |
| `Unable to invoke ivl`                              | Icarus called without `-B`                   | use `./run_sim.sh`, which adds `-B`                              |
| `Area for cell type $_SDFFE_... is unknown`         | flip-flops were never mapped                 | make sure `dfflibmap` runs before `abc`                          |
| Cell count far below the expected figure            | wrong liberty path, or the wrong corner file | check the file name and the byte count                           |
| Library is 71 MB instead of 12.8 MB                 | a corner with CCS noise data                 | use `tt_025C_1v80`, exactly                                      |
| `abc` produces nothing and the netlist has no cells | seen once with the WASM build                | switch to Route B and rerun                                      |
| Verilator exits with `Exiting due to N warning(s)`  | Verilator treats warnings as failures        | fix the warning. A latch or an unread signal is a bug, not noise |

## 4. The flow

```
read_verilog -sv <source>
hierarchy -top <top>
synth -top <top>
dfflibmap -liberty <library>     # maps the flip-flops
abc -liberty <library>           # maps the combinational logic
opt_clean
stat -liberty <library>          # prints the cell table and the chip area
write_json <out>.json
```

`./run_synth.sh <source.sv> <top> [library]` runs that sequence, checks the result with
`area_report.py`, and prints the tool version, the route, the source, the library, the run time, the
log path, the netlist path, then cells, flip-flops, area, and flop share.

Output files carry provenance: `reports/<top>.<route>.<YYYYMMDD>.log` and the matching `.json`. A
Route A run and a Route B run cannot overwrite each other.

`./run_lint.sh <source.sv> <top>` lints first. `./run_sim.sh <tb.sv> [other sources]` simulates.

### The trap that corrupts the headline number

`stat -liberty` prints the area of every cell it recognises, and it prints a confident total while
silently skipping every cell it does not. Leave out `dfflibmap` and the flip-flops stay as
Yosys-internal cells that no library describes. Measured on one netlist:

| Run                 | Reported area                                                                                 |
| ------------------- | --------------------------------------------------------------------------------------------- |
| With `dfflibmap`    | 316.5536 um^2, 33 cells, 8 flip-flops                                                         |
| Without `dfflibmap` | **98.8448 um^2**, 23 cells, 0 flip-flops, plus `Area for cell type $_SDFFE_PN0P_ is unknown!` |

A 3.2x error, and the summary carries no warning. Raw Yosys still exits 0, while the wrapper script is
stricter: it exits 2 and refuses to publish the figure. So if you break the flow on purpose and the
script exits 2, it is working. The signal to look for is `flip-flops 0`.

Check any log you did not produce yourself with:

```bash
grep -E 'Number of cells|Chip area|is unknown' reports/<top>.<route>.<date>.log
```

## 5. The library

One liberty file carries the corner. Yosys needs nothing else for cell count and area.

```bash
curl -fL -o sky130_fd_sc_hd__tt_025C_1v80.lib \
  https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/master/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
wc -c sky130_fd_sc_hd__tt_025C_1v80.lib      # expect 12800135
```

12,800,135 bytes, corner `tt_025C_1v80`, a real NLDM library (`delay_model : "table_lookup"`). Three
counts describe the same file, and knowing which one you read saves an argument:

| Count                     | Number | What it means                                                       |
| ------------------------- | ------ | ------------------------------------------------------------------- |
| Text matches for `cell (` | 452    | the crude grep the smoke check prints                               |
| Cell definitions          | 428    | what `area_report.py` parses and reports as the library size        |
| Cells ABC maps            | 334    | the rest are sequential, tri-state, or have no function ABC can map |

- Do not chase `google/skywater-pdk-libs-*`. That repository holds `.lib.json` metadata and LFS
  pointers, and the raw URL 404s.
- **Pin the exact corner filename.** In the same PDK, `sky130_fd_sc_hd__tt_025C_1v80.lib` is 12.8 MB
  while `sky130_fd_sc_hd__ff_n40C_1v95.lib` is 71 MB, because one corner ships CCS noise data.
  Mapping a different corner changes the area without telling you.
- CIEL downloads the full PDK, and its own downloader stalls on a slow link, seen at 3 percent and at
  41 percent with a read timeout and no retry flag. When you need the whole PDK, read the resumable
  links out of the static manifest and fetch with `curl -C -`:

  ```bash
  curl -sSL 'https://fossi-foundation.github.io/ciel-releases/sky130/<PDK_COMMIT>/manifest.json'
  # assets[].url points at a GitHub release, for example
  # https://github.com/fossi-foundation/ciel-releases/releases/download/sky130-<PDK_COMMIT>/sky130_fd_sc_hd.tar.zst
  ```

  That tarball is 167 MB compressed, near 1 GB extracted. Budget the disk.

Useful areas from this library, so you can sanity-check a figure in your head:

| Cell                                            | Area         |
| ----------------------------------------------- | ------------ |
| `sky130_fd_sc_hd__dfxtp_1`, the plain flip-flop | 20.0192 um^2 |
| `clkinv_1`, `nand2_1`, `nor2_1`                 | 3.754 um^2   |
| `a21oi_1`, `nand3_1`, `o21ai_0`                 | 5.005 um^2   |
| `a22o_1`                                        | 8.758 um^2   |
| `maj3_1`                                        | 10.010 um^2  |

## 6. Verified results

Every figure below came from a real run on the designs in this folder, on Ubuntu 24.04 x86-64.

| Design                                                            | Route          | Cells | Flip-flops | Area           | Flop share   |
| ----------------------------------------------------------------- | -------------- | ----- | ---------- | -------------- | ------------ |
| `demo_counter.sv`, an 8-bit counter with a comparator             | B, native 0.33 | 33    | 8          | 316.5536 um^2  | 50.6 percent |
| `demo_counter.sv`                                                 | A, WASM 0.70   | 35    | 8          | 311.55 um^2    | 51.4 percent |
| `demo_integrator.sv`, a 37-tap moving average with a divide by 37 | B, native 0.33 | 1,885 | 482        | 20,275.70 um^2 | 47.6 percent |
| `demo_integrator.sv`                                              | A, WASM 0.70   | 1,396 | 476        | 16,442.02 um^2 | 58 percent   |
| `template/design_template.sv`, the starting skeleton              | B, native 0.33 | 71    | 36         | 939.65 um^2    | 76.7 percent |

Reproduce the rows for the route you installed. A Route B reader has no reason to install Route A.

Read the integrator row before the RTL is final, because it changes design choices. A 37-sample
window of 18-bit words held in flip-flops costs about 480 flops at 20.0192 um^2 each, and flip-flops
take roughly half the area. Three changes belong in the RTL review:

- Use a 32-sample window and a shift instead of 37 and a divide. Smaller, and exact.
- Hold the delay line in block RAM as the window grows.
- Replace a divide by a constant with a multiply by a reciprocal, or pick a power of two.

For scale, 1 mm^2 is 1,000,000 um^2, so the integrator occupies 0.02 mm^2.

## 7. Timing

Plain Yosys does not time a design usefully. `ltp` reports a path length of 0 on most mapped netlists
and a meaningless 1 on others. Never present a made-up delay. Four routes exist, and none of them is
the RTL author's laptop:

1. **On site, with the organisers' Cadence.** It reports real timing, and it produces the number worth
   quoting. Prepare the RTL and the constraints before you travel, then run it there. Genus maps
   sequential and combinational cells inside `syn_map`, so nothing plays the role of `dfflibmap`, and
   the lesson still holds: check that every instance in the netlist is a library cell before you trust
   a report.
2. **Build OpenSTA, if you have sudo and an afternoon.** No package manager ships OpenSTA, in apt,
   PyPI, or conda-forge, so it gets compiled. Its `find_package(SWIG 3.0 REQUIRED)` is unconditional,
   and swig itself is available: `sudo apt install swig git cmake tcl-dev` covers the prerequisites.
3. **A container on any machine with Docker.** The machine that wrote this brief runs Docker 29.1.3
   with a live daemon. Candidate images: `efabless/openlane`, `openroad/orfs`,
   `hpretl/iic-osic-tools`. A container carries a built timing tool, so swig never matters.
4. **LibreLane**, `pip install librelane` (3.0.16, Python 3.10 or newer). The wheel holds the flow
   engine only, and LibreLane documents two ways to supply the EDA binaries, Nix or Docker, so use
   `librelane --dockerized`.

Until one of those runs, publish cell count and area, and write "timing comes from the on-site flow"
in the report.

## 8. When the RTL arrives

Aviv lands the RTL in `rtl/` block by block, with a testbench and golden vectors from the Python model.
Two files here are your starting point for each block:

- `template/design_template.sv`, the port contract every block follows: one clock, synchronous
  active-low reset, and one sample stream with `tdata`, `tvalid`, and `tlast`.
- `template/tb_template.sv`, a testbench that drives that stream at the sample beat and prints PASS or
  FAIL. It drives 64 samples and expects 64 output pulses, so a broken handshake fails it.

### The order to work in

| Step | Command                                                                                                          | What you check                                   |
| ---- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| 1    | `./run_lint.sh rtl/<block>.sv <top>`                                                                             | no warnings. Warnings fail lint here             |
| 2    | `./run_sim.sh rtl/tb_<block>.sv rtl/<block>.sv`                                                                  | the testbench prints PASS                        |
| 3    | `./run_synth.sh rtl/<block>.sv <top>`                                                                            | cells, flops, area, and no `is unknown`          |
| 4    | repeat for every block: filter, derivative, squaring, integrator, peak detector, RR series, features, classifier |                                                  |
| 5    | `./run_synth.sh rtl/<top>.sv <top>`                                                                              | the top-level area against the sum of the blocks |
| 6    | write the table into `doc/` with the date, the library, and the tool version                                     |                                                  |

A gap larger than a few percent between the top level and the sum of the blocks means cross-module
logic that no block owns. Find it before you publish either number.

If lint or simulation fails, fix that first. Synthesis tells you the size of a design that already
works, and it happily maps a design that does not.

### Where your flow goes next

Genus on site replaces the Yosys script step for step, and each command has a counterpart. Prepare a
Tcl file before you travel so the on-site time goes into running, not into reading manuals.

| Yosys                                 | Genus                       | What it does                         |
| ------------------------------------- | --------------------------- | ------------------------------------ |
| `read_verilog -sv <file>`             | `read_hdl -sv <file>`       | reads the source                     |
| `hierarchy -top <top>`                | `elaborate <top>`           | builds the design                    |
| (none)                                | `read_libs <liberty>`       | attaches the library                 |
| (none)                                | `read_sdc <constraints>`    | attaches clock and delay constraints |
| `synth -top <top>`                    | `syn_generic`               | optimises without a library          |
| `dfflibmap -liberty` + `abc -liberty` | `syn_map`                   | maps to library cells                |
| `opt_clean`                           | `syn_opt`                   | cleans up after mapping              |
| `stat -liberty`                       | `report_area`, `report_qor` | reports cells and area               |
| (not in Yosys)                        | `report_timing`             | reports slack and the critical path  |
| `write_json`                          | `write_hdl`                 | writes the netlist                   |

Vivado runs the same RTL on the other backend, for the KV260 demo. `synth_design`, `opt_design`,
`place_design`, `route_design`, `write_bitstream`, then `report_utilization`, `report_timing_summary`,
and `report_power`. Vivado counts LUTs, registers, BRAM, and DSP blocks, so its figures never mix with
the SKY130 ones.

## 9. What to do, in order

| Step | Output                                                                                                                                                                                                                                                                             |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Set up Part 1a or 1b on your own laptop. `./setup_check.sh` reports 13 PASS and exit 0                                                                                                                                                                                             |
| 2    | Reproduce the section 6 rows for your route. A different figure means the setup is wrong, not the design                                                                                                                                                                           |
| 3    | Break it once on purpose: remove `dfflibmap` from a copy of the script and watch the area collapse. The copy exits 2 by design, and the flop count drops to 0. You will recognise it later                                                                                         |
| 4    | Learn the library: open the file, search for `sky130_fd_sc_hd__dfxtp_1` (the name is quoted inside the file), and read its `area`. Then find a `timing ()` block with `related_pin : "CLK"` and read `rise_constraint` and `fall_constraint`, which are the setup and hold numbers |
| 5    | Learn the flow: `./debroot/usr/bin/yosys -p "help synth"` lists the stages, and `synth -run begin:coarse` stops after one of them. Run the stages one at a time and watch the netlist change                                                                                       |
| 6    | Synthesise each RTL block as it lands, one report per block                                                                                                                                                                                                                        |
| 7    | Add up the blocks, compare with the top level, and explain any gap                                                                                                                                                                                                                 |
| 8    | Prepare the Genus Tcl file, and take the timing number from the on-site tool                                                                                                                                                                                                       |

## 10. Definition of done

- [ ] `./setup_check.sh` reports 13 PASS and exit code 0 on your laptop, and you can explain what each check proves.
- [ ] The section 6 rows for your route reproduce, and the areas match.
- [ ] Every report names the RTL revision, the library file, the corner, and the tool version. The script prints the tool version and the run time, so keep that header with the figure.
- [ ] `dfflibmap` runs before `abc`, and no report contains `is unknown`.
- [ ] `reports/` holds one log and one netlist JSON per run, named `<top>.<route>.<date>`, so two routes cannot overwrite each other.
- [ ] The per-block areas add up to the top-level area within a few percent, or the gap has an owner.
- [ ] You can say where every number came from, and that timing comes from the on-site flow.
- [ ] No one treats a Route A figure and a Route B figure as comparable.

## 11. Report template

```
Design         :
RTL revision   :
Library        :
Corner         :
Tool           : yosys <version>, route A or B
Run at         : <timestamp, copied from the script header>
Cells          : N (flops N, combinational N)
Area           : N.NN um^2 (flops N.NN, combinational N.NN)
Flop share     : N percent
Unmapped cells : none / list
Timing         : not measured here / source of the number
Notes          :
```

## 12. References

- Yosys manual, `synth`, `dfflibmap`, `abc`, and the equivalence checking flow:
  https://yosyshq.readthedocs.io/projects/yosys/en/latest/
- The liberty file used here:
  https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/tree/master/flow/platforms/sky130hd/lib
- SKY130 HD library documentation:
  https://skywater-pdk.readthedocs.io/en/main/contents/libraries/foundry-standard-cell-libraries/
- CIEL, the PDK downloader, and its release manifest:
  https://github.com/fossi-foundation/ciel-releases
- LibreLane installation, and why it needs Nix or Docker:
  https://librelane.readthedocs.io/en/latest/installation/docker_installation/index.html
- Verilator warning list, including `UNUSEDSIGNAL` and `WIDTH`: https://verilator.org/warn/
