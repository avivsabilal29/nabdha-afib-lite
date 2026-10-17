# NABDHA AFIB-LITE

An FPGA IP block that triages atrial fibrillation from a single-lead ECG, offline, inside the
programmable logic.

Entry for the Indonesia Chip Hackathon Challenge 2026 (ICDeC, ITB, 21 to 23 October 2026).
Target platform: AMD Kria KV260 with SystemVerilog.

## What the block does

The block reads 250 Hz, 12-bit ECG samples, finds R peaks with the Pan-Tompkins chain, measures
beat-to-beat variability of the RR series, and returns one of three labels: needs review, appears
normal, or undecided. Every step runs in the programmable logic. The block needs no network and no
specialist on site, which matters for primary care facilities that record an ECG and have nobody
trained to read it.

The teaching note that explains each stage and derives every formula sits in the project vault as
note 31, _Memahami AFIB-LITE_. Read it before touching the model or the RTL.

## Repository layout

| Folder           | Contents                                                                                                                                             |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `model/`         | Python reference model in Jupyter notebooks. This is the measured golden reference the RTL is checked against. Start at `model/TASK_BRIEF.md`.       |
| `rtl/`           | SystemVerilog source of the pipeline. Portable to ASIC: one clock, synchronous reset, no vendor primitives.                                          |
| `rtl-synthesis/` | Scripts and reports that map the RTL onto SKY130 standard cells. Numbers from here go into the final report. Start at `rtl-synthesis/TASK_BRIEF.md`. |
| `fpga/`          | Board-level files for the KV260: block design notes, constraints, bitstream and device tree overlay, power measurement procedure.                    |
| `vivado/`        | Tcl scripts and non-project build files for Vivado.                                                                                                  |
| `cadence/`       | Scripts and reports from Cadence tools. Licence-restricted, so nothing proprietary is committed.                                                     |
| `doc/`           | Design notes, figures, measurement logs, and meeting records that do not belong to a single folder.                                                  |

## How the parts connect

```
model/  ->  rtl/  ->  rtl-synthesis/  ->  fpga/
Python      SystemVerilog   SKY130 numbers      KV260 bitstream
golden      implementation  area and timing     live demo
reference
```

The model comes first. It fixes the interface, the fixed-point formats, and the expected numbers.
The RTL implements the same pipeline and is checked block by block against the model. Synthesis
proves the RTL fits a standard-cell library and reports area and critical path. The FPGA build
puts the pipeline on the board for the demo.

## Input source and disclaimer

The demo may run on one of two inputs:

- a live ECG signal from the recording front end, or
- recorded data played back through the same interface with a testbench vector.

When the demo uses recorded data, this README and the pitch must say so. The organisers require
that disclaimer, and the recorded path stays available as a fallback when the front end fails on
site. Both paths enter the design through the same sample interface, so the pipeline does not care
which one is feeding it.

## Build and run

Nothing builds yet. Each folder README lists the commands for that part once it exists. The order
of work is model, then RTL, then the FPGA build, with synthesis running in parallel once the RTL
is stable.

## Team

| Member | Area                                     |
| ------ | ---------------------------------------- |
| Aviv   | RTL, FPGA integration, hardware bring-up |
| Bryan  | Reference model and validation           |
| Raihan | Synthesis and reporting                  |
| Rajab  | Documentation and pitch                  |

## Status

| Date              | Milestone                             |
| ----------------- | ------------------------------------- |
| 14 Oct 2026       | Mini proposal submitted               |
| 15 Oct 2026       | Finalist announcement, project starts |
| 16 to 19 Oct 2026 | Online preparation phase              |
| 21 to 23 Oct 2026 | On-site build and presentation        |
