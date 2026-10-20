#!/usr/bin/env bash
# Compile and run a testbench with Icarus Verilog from the local toolchain.
#
# Usage:   ./run_sim.sh <testbench.sv> [other sources ...] [-- <plusarg> ...]
# Example: ./run_sim.sh template/tb_template.sv template/design_template.sv
#          ./run_sim.sh ../rtl/tb/tb_pkg_konstanta.sv ../rtl/afib_lite_pkg.sv -- +MANIFEST=/tmp/m.json
#
# Fase 1 fix (plan doc 38, Fase 1 step 6 and rtl/TASK_BRIEF.md section 7). The defect: the
# final line used to be `"$VVP" "$OUT"`, so every argument of this script went to iverilog
# and the runtime plusargs, for example `+GOLD=<file>` or `+VEC=<file>`, never reached vvp.
# TASK_BRIEF.md had to work around it by passing file names through environment variables.
# The fix is a `--` separator: arguments before it go to iverilog, arguments after it go to
# vvp. The separator form is used instead of "any argument that starts with a plus" because
# iverilog has legitimate plus arguments of its own, such as `+incdir+<dir>+<dir>`, and
# guessing would silently send those to the wrong tool.
#
# Backward compatible: with no `--` the behaviour is unchanged and every extra argument is a
# source file, so the command lines documented in rtl/TASK_BRIEF.md keep working.
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

TB="${1:?usage: run_sim.sh <testbench.sv> [other sources ...] [-- <plusarg> ...]}"
shift

# split the remaining arguments at the first `--`: left of it are sources, right of it are plusargs
SOURCES=()
PLUSARGS=()
SEEN_SEP=0
for a in "$@"; do
    if [ "$SEEN_SEP" -eq 0 ] && [ "$a" = "--" ]; then
        SEEN_SEP=1
    elif [ "$SEEN_SEP" -eq 1 ]; then
        PLUSARGS+=("$a")
    else
        SOURCES+=("$a")
    fi
done

mkdir -p reports/sim
OUT="reports/sim/$(basename "${TB%.sv}").vvp"

echo "run_sim.sh: tb=$TB sources=${#SOURCES[@]} plusargs=${#PLUSARGS[@]}"
if [ "${#PLUSARGS[@]}" -gt 0 ]; then
    echo "  plusargs forwarded to vvp: ${PLUSARGS[*]}"
fi

# Fase 1 fix number 2 (measured, see rtl-synthesis/reports/LAPORAN-FASE1.md). Icarus parses
# files in command line order and resolves a package reference in a later file as a syntax
# error, so every *_pkg.sv source is moved ahead of the testbench. Before this fix
# `run_sim.sh tb_pkg_konstanta.sv ../rtl/afib_lite_pkg.sv` failed with
# `tb_pkg_konstanta.sv:1: syntax error` on the first localparam that named a package
# constant, even though run_lint.sh handled the same ordering for Verilator.
PKGFILES=()
OTHERFILES=()
for a in ${SOURCES[@]+"${SOURCES[@]}"}; do
    case "$(basename "$a")" in
        *_pkg.sv|*_pkgs.sv) PKGFILES+=("$a") ;;
        *)                  OTHERFILES+=("$a") ;;
    esac
done
if [ "${#PKGFILES[@]}" -gt 0 ]; then
    echo "  compiled first (packages): ${PKGFILES[*]}"
fi

"$IVL" ${IVLARGS[@]+"${IVLARGS[@]}"} -g2012 -o "$OUT" \
    ${PKGFILES[@]+"${PKGFILES[@]}"} "$TB" ${OTHERFILES[@]+"${OTHERFILES[@]}"}
"$VVP" "$OUT" ${PLUSARGS[@]+"${PLUSARGS[@]}"}
