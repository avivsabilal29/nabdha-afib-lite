#!/usr/bin/env bash
# Lint SystemVerilog with Verilator from the local toolchain.
#
# Usage:   ./run_lint.sh <design.sv> <top module>
# Example: ./run_lint.sh template/design_template.sv design_template
#
# Verilator's wrapper script execs `<VERILATOR_ROOT>/verilator_bin`, which does not exist in a
# relocated package prefix, so this calls the binary directly and sets VERILATOR_ROOT for the include
# files. Without the variable the binary fails on `verilatedos.h`.
#
# Run lint before every synthesis run. Verilator catches latches, width mismatches, and undriven
# signals, and Yosys accepts all three in silence.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

# Two supported installs, both detected here:
#   local   ./setup_tools.sh unpacked Verilator into ./debroot, no root needed
#   system  sudo apt install verilator
#
# A relocated Verilator needs both the direct binary call and VERILATOR_ROOT. Its wrapper script
# execs `<VERILATOR_ROOT>/verilator_bin`, which does not exist in a relocated prefix, and without the
# variable the binary fails on `verilatedos.h`.
if [ -x "$HERE/debroot/usr/bin/verilator_bin" ]; then
    VL="$HERE/debroot/usr/bin/verilator_bin"
    export VERILATOR_ROOT="$HERE/debroot/usr/share/verilator"
else
    VL="verilator"
fi

if ! command -v "$VL" >/dev/null; then
    echo "verilator not found. Run ./setup_tools.sh, or install it with your package manager." >&2
    exit 1
fi

SRC="${1:?usage: run_lint.sh <design.sv> <top module>}"
TOP="${2:?usage: run_lint.sh <design.sv> <top module>}"

"$VL" --lint-only -sv --top-module "$TOP" -Wall -Wno-DECLFILENAME "$SRC"
echo "lint clean: $SRC ($TOP)"
