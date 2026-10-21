#!/usr/bin/env bash
# Synthesise one SystemVerilog file to SKY130 standard cells and report cell count and area.
#
# Usage:   ./run_synth.sh <source.sv> <top module> [liberty file] [extra sources ...]
# Example: ./run_synth.sh demo_counter.sv demo_counter sky130_fd_sc_hd__tt_025C_1v80.lib
#          ./run_synth.sh ../rtl/derivative.sv derivative
#
# Extra sources go after the liberty file and are read before the main source. On top of that, every
# `*_pkg.sv` sitting next to the main source is read first automatically. Packages must be read before
# any module that imports them, exactly as run_lint.sh and run_sim.sh already do. Without this, a
# module that names a package width or package constant inside a localparam dies at elaboration with
#   ERROR: Failed to evaluate system function `$clog2' with non-constant value
# which is the defect that hit derivative.sv:99 on 20 October 2026.
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

SRC="${1:?usage: run_synth.sh <source.sv> <top module> [liberty file] [extra sources ...]}"
TOP="${2:?usage: run_synth.sh <source.sv> <top module> [liberty file] [extra sources ...]}"
LIB="${3:-sky130_fd_sc_hd__tt_025C_1v80.lib}"
YOSYS="${YOSYS:-yosys}"

# Optional extra sources after the liberty file.
EXTRA=()
if [ "$#" -gt 3 ]; then
    EXTRA=("${@:4}")
fi

# Every package file next to the main source is read first, so a module that imports the package
# elaborates instead of failing on a non-constant $clog2. Absolute paths, because this script changes
# directory before it runs yosys.
SRCDIR="$(cd "$(dirname "$SRC")" && pwd)"
SRCABS="$SRCDIR/$(basename "$SRC")"
PKGS=()
for candidate in "$SRCDIR"/*_pkg.sv; do
    if [ -e "$candidate" ] && [ "$candidate" != "$SRCABS" ]; then
        PKGS+=("$candidate")
    fi
done

READS=""
for f in ${PKGS[@]+"${PKGS[@]}"} ${EXTRA[@]+"${EXTRA[@]}"}; do
    READS+="    read_verilog -sv $f;
"
done
READS+="    read_verilog -sv $SRCABS;
"
SOURCES_LIST="${PKGS[*]:-} ${EXTRA[*]:-} $SRCABS"

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
$READS    hierarchy -top $TOP;
    synth -top $TOP;
    dfflibmap -liberty $LIB;
    abc -liberty $LIB;
    opt_clean;
    stat -liberty $LIB;
    write_json $JSON
"

echo "tool     : $YOSYS_VER"
echo "route    : $ROUTE"
echo "sources  : $SOURCES_LIST"
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
