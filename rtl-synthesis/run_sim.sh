#!/usr/bin/env bash
# Compile and run a testbench with Icarus Verilog from the local toolchain.
#
# Usage:   ./run_sim.sh <testbench.sv> [other sources...]
# Example: ./run_sim.sh template/tb_template.sv template/design_template.sv
#
# Icarus looks for its `ivl` and `ivlpp` helpers on a path baked in at build time, so `-B` must point
# at the copy inside ./debroot. Without it the driver fails with "Unable to invoke ivl".
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

# Two supported installs, both detected here:
#   local   ./setup_tools.sh unpacked Icarus into ./debroot, no root needed
#   system  sudo apt install iverilog
IVLARGS=()
if [ -x "$HERE/debroot/usr/bin/iverilog" ]; then
    IVL="$HERE/debroot/usr/bin/iverilog"
    VVP="$HERE/debroot/usr/bin/vvp"
    IVLDIR="$HERE/debroot/usr/lib/x86_64-linux-gnu/ivl"
    if [ ! -d "$IVLDIR" ]; then
        IVLDIR="$(find "$HERE/debroot" -type d -name ivl 2>/dev/null | head -1)"
    fi
    if [ -n "$IVLDIR" ]; then
        IVLARGS=(-B "$IVLDIR")
    fi
else
    IVL="iverilog"
    VVP="vvp"
fi

if ! command -v "$IVL" >/dev/null; then
    echo "iverilog not found. Run ./setup_tools.sh, or install it with your package manager." >&2
    exit 1
fi

TB="${1:?usage: run_sim.sh <testbench.sv> [other sources...]}"
shift

mkdir -p reports/sim
OUT="reports/sim/$(basename "${TB%.sv}").vvp"

"$IVL" ${IVLARGS[@]+"${IVLARGS[@]}"} -g2012 -o "$OUT" "$TB" "$@"
"$VVP" "$OUT"
