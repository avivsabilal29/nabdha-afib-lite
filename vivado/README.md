# vivado

Tcl scripts and project files for Vivado.

## What belongs here

- Scripts that build the project from source rather than from a checked-in project directory:
  `create_project`, `create_bd_design`, `add_files`, `package_ip`, `build_bitstream`.
- The block design script for the Kria KV260 base design with the PS preset.
- IP packaging for the AFIB-LITE block, so the PL shows up as AXI4-Lite and AXI4-Stream endpoints.
- Report scripts for utilisation, timing, and power.
- A run note per build that records the Vivado version and the device part.

## How to run

Batch mode keeps the flow repeatable and keeps the scripts in version control:

```bash
vivado -mode batch -source scripts/build.tcl
```

Record the Vivado version and the part number in the run note. A build that cannot be reproduced
from these scripts does not count as done.

## Device and licence

The KV260 carries the Kria K26 SOM, so the Vivado install needs support for the Zynq UltraScale+
MPSoC and the K26 part. Vivado ML Standard covers it. Check the licence on the lab machine before
the on-site session starts, and note whether the organisers provide the licence or the team does.

## What stays out

- Project directories, journals, `.Xil`, runs, and caches. They stay untracked.
- Bitstreams. They belong to `fpga/` as a release artefact or a rebuild step.
- RTL source. It lives in `rtl/`.
