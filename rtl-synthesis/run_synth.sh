#!/usr/bin/env bash
# Synthesise one SystemVerilog file to SKY130 standard cells and report cell count and area.
#
# Usage:   ./run_synth.sh <source.sv> <top module> [liberty file]
# Example: ./run_synth.sh demo_counter.sv demo_counter sky130_fd_sc_hd__tt_025C_1v80.lib
#
# Needs Yosys and ABC. Install them with ./setup_tools.sh, which needs no root, then run this script
# with no environment setup. A system yosys works too, and the WASM build works through YOSYS:
#   YOSYS=.venv/bin/yowasp-yosys ./run_synth.sh demo_counter.sv demo_counter
#
# The order matters. `dfflibmap` maps the flip-flops before `abc` maps the combinational logic.
# Leave it out and the flops stay as internal Yosys cells, which no library describes, so the area
# comes out too small.
set -euo pipefail

# Run from this folder so the library, the reports, and the toolchain resolve the same way from any
# working directory.
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

# Use the toolchain from setup_tools.sh when it is present. Yosys finds its technology files through
# YOSYS_DATDIR, which a relocated package install does not set on its own.
if [ -z "${YOSYS:-}" ] && [ -x "$HERE/debroot/usr/bin/yosys" ]; then
    export PATH="$HERE/debroot/usr/bin:$PATH"
    export YOSYS_DATDIR="$HERE/debroot/usr/share/yosys"
fi

SRC="${1:?usage: run_synth.sh <source.sv> <top module> [liberty file]}"
TOP="${2:?usage: run_synth.sh <source.sv> <top module> [liberty file]}"
LIB="${3:-sky130_fd_sc_hd__tt_025C_1v80.lib}"
YOSYS="${YOSYS:-yosys}"

# Provenance naming. A run only overwrites its own route and day, so a Route A report never destroys a
# Route B report. The header printed below and written into the log carries the exact time and the
# tool version.
case "${YOSYS##*/}" in
    yowasp-yosys) ROUTE="wasm" ;;
    *)            ROUTE="native" ;;
esac
STAMP="$(date +%Y%m%d)"
OUT="reports"
mkdir -p "$OUT"
LOG="$OUT/$TOP.$ROUTE.$STAMP.log"
JSON="$OUT/$TOP.$ROUTE.$STAMP.json"

if [ ! -f "$LIB" ]; then
    echo "library not found: $LIB" >&2
    echo "fetch it with, then check the byte count:" >&2
    echo "  curl -fL -o sky130_fd_sc_hd__tt_025C_1v80.lib \\" >&2
    echo "    https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/master/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib" >&2
    echo "  wc -c sky130_fd_sc_hd__tt_025C_1v80.lib   # expect 12800135" >&2
    exit 1
fi

# Capture the version instead of piping into `head`: under `set -o pipefail` a truncated pipe becomes
# a SIGPIPE failure and the script would stop before it reports anything.
YOSYS_VER="$("$YOSYS" -V 2>&1)"
YOSYS_VER="${YOSYS_VER%%$'\n'*}"

# -l writes the full log to a file: with the YoWASP build, pass output after ABC does not reach stdout.
"$YOSYS" -l "$LOG" -p "
    read_verilog -sv $SRC;
    hierarchy -top $TOP;
    synth -top $TOP;
    dfflibmap -liberty $LIB;
    abc -liberty $LIB;
    opt_clean;
    stat -liberty $LIB;
    write_json $JSON
"

echo "tool     : $YOSYS_VER"
echo "route    : $ROUTE"
echo "source   : $SRC"
echo "library  : $LIB"
echo "run at   : $(date +%Y-%m-%dT%H:%M:%S%z)"
echo "log      : $LOG"
echo "netlist  : $JSON"
echo

python3 area_report.py "$JSON" "$LIB"

# stat -liberty prints a total even when some cells are unmapped, so refuse to publish it.
if grep -q "is unknown" "$LOG"; then
    echo "FAIL: the log reports unmapped cells, so the area printed above is too small." >&2
    echo "      Check that dfflibmap runs before abc and that the liberty path is correct." >&2
    exit 2
fi
