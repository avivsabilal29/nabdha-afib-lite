# fpga

Board-level work for the AMD Kria KV260.

## What belongs here

- Block design notes and the PS preset the team agreed on.
- Constraint files (`XDC`) for the PL clock and any Pmod pins.
- The clock plan: `pl_clk0` at 100 MHz plus the 250 Hz sample enable. At 100 MHz the divider is
  exactly 400000, so the sample tick is exact with no remainder.
- Build and load notes for the bitstream, the device tree overlay, and the boot files.
- Power and latency measurement logs.

## Build and load, in outline

1. Build the design in Vivado and write the bitstream.
2. Convert the bitstream for the Zynq UltraScale+ boot path:
   `bootgen -arch zynqmp -process_bitstream bin`.
3. Compile the overlay with `dtc -@` and add a `shell.json` beside it.
4. Copy the folder to `/lib/firmware/xilinx/afib_lite/` on the board.
5. Load it with `sudo xmutil loadapp afib_lite`.

A raw `.bit` file fails to load. The converted `.bit.bin` plus overlay is the working path.

## Board limits worth remembering

| Item                        | Limit                                                                               |
| --------------------------- | ----------------------------------------------------------------------------------- |
| Pmod                        | 12 pins, 3.3 V, 100 mA total                                                        |
| 40-pin GPIO header          | none on this carrier                                                                |
| MIO                         | fixed by the boot firmware, do not repurpose                                        |
| Power telemetry             | INA260 on the VCC_SOM rail at I2C address 0x40, read with `xmutil platformstats -p` |
| What power telemetry covers | PS, PL, and DDR only, it excludes regulator loss                                    |

## What stays out

- Bitstreams and overlays. Keep them untracked and rebuild them, or attach them to a release.
- Vivado project directories. They live with the build scripts in `vivado/`.
- RTL source. It lives in `rtl/`.
