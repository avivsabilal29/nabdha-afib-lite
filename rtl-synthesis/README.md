# rtl-synthesis

Mapping the SystemVerilog in `rtl/` onto the SKY130 standard-cell library, and reporting the numbers
that go into the report.

## Why this folder exists

A bitstream alone does not answer the question the judges ask. They want to know whether the design
fits on silicon, which means three measured numbers: how many standard cells it needs, how much area
those cells take in square micrometres, and how long the slowest path is in nanoseconds. This folder
holds the runs that produce those numbers.

## What belongs here

- The synthesis script, kept small enough to read in one sitting.
- `reports/` with the cell statistics, the area report, and the timing report for each design
  revision, each file named with the date and the RTL commit.
- A run note per synthesis: the tool version string, the RTL commit, the exact library file name, the
  corner, and the command line. A number without the run note behind it is a guess.
- Timing constraints for the clock the design actually runs on.

## Library

Record which cell library and which corner each run used. The open SKY130 high-density library is
`sky130_fd_sc_hd`, and the typical corner file name ends in `tt_025C_1v80`. Mixing corners between
runs makes two reports incomparable, so write the file name down.

Do not commit the PDK. It is large, and it carries its own terms. Fetch it on the machine that runs
the synthesis, and keep the fetch command in this folder.

## How to run

```bash
./setup_tools.sh      # tools into ./debroot, no root needed; add --wasm for the WASM route
curl -fL -o sky130_fd_sc_hd__tt_025C_1v80.lib \
  https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/master/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
wc -c sky130_fd_sc_hd__tt_025C_1v80.lib       # expect 12800135
./setup_check.sh      # 13 checks over system, tools, library, simulation, lint, and synthesis

./run_lint.sh  template/design_template.sv design_template
./run_sim.sh   template/tb_template.sv template/design_template.sv
./run_synth.sh demo_counter.sv demo_counter
```

The library comes from the `master` branch, which is the repository default. A wrong branch name
returns a 14-byte page whose content is `404: Not Found`, and curl reports success unless you pass
`-f`, so check the byte count.

Verified on the machine that wrote this, on Ubuntu 24.04 x86-64. Native Yosys 0.33: `demo_counter.sv`
gives 33 cells and 316.5536 um^2, and `demo_integrator.sv` gives 1,885 cells and 20,275.70 um^2. WASM
Yosys 0.70: 35 cells and 311.55 um^2, and 1,396 cells and 16,442.02 um^2. Two routes, two sets of
numbers, so every report records which one produced it, and output files are named
`reports/<top>.<route>.<date>.log` for the same reason. The library stays untracked, so fetch it
instead of committing it.

## Files

| Path                                    | What it is                                                                           |
| --------------------------------------- | ------------------------------------------------------------------------------------ |
| `setup_tools.sh`                        | installs Yosys, ABC, Icarus Verilog, and Verilator into `./debroot`, with no root    |
| `setup_check.sh`                        | verifies the install across tools, library, simulation, lint, and two synthesis runs |
| `run_synth.sh`                          | synthesises one file and reports cells, flip-flops, area, and flop share             |
| `run_sim.sh`                            | compiles and runs a testbench with Icarus Verilog                                    |
| `run_lint.sh`                           | lints SystemVerilog with Verilator, and fails on warnings                            |
| `area_report.py`                        | reads the netlist JSON and the library, and names every unmapped cell type           |
| `template/`                             | the block skeleton and its testbench, both ready to run                              |
| `demo_counter.sv`, `demo_integrator.sv` | two small designs that prove the flow works                                          |
| `requirements.txt`                      | the pinned WASM Yosys, for the optional route A                                      |
| `reports/`                              | one log, one netlist JSON, and one area report per run                               |

Every script picks up either the local `./debroot` or a system install, so a laptop with sudo can use
its package manager instead.

`TASK_BRIEF.md` in this folder carries the setup for your own machine, the pitfalls, the verified
numbers, and the order of work.

## Status

The flow is installed, checked, and reproducible from scratch on a second machine. What remains is the
real work: the reference model in `model/` and a stable `rtl/` top level, then one report per block.

## What stays out

- The PDK and any downloaded toolchain. Fetch, do not commit.
- Synthesis output databases and build trees. Keep the reports and the scripts.
- RTL source. It lives in `rtl/`.
