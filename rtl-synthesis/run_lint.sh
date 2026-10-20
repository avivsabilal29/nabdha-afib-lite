#!/usr/bin/env bash
# Lint SystemVerilog with Verilator from the local toolchain.
#
# Usage:   ./run_lint.sh <design.sv> <top module> [more sources ...]
#          ./run_lint.sh --chain [top module]        # top defaults to afib_lite_top
# Example: ./run_lint.sh template/design_template.sv design_template
#          ./run_lint.sh --chain
#          ./run_lint.sh ../rtl/tb/tb_pkg_konstanta.sv tb_pkg_konstanta ../rtl/afib_lite_pkg.sv
#
# Fase 1 fix (plan doc 38, Fase 1 step 5 and step 6). Two defects are closed here:
#
#   1 The script used to lint exactly one file, so linting the whole chain took one command
#      per file and a stage could pass while the chain did not elaborate. It now takes any
#      number of sources: the first positional argument is a source, the second is the top
#      module, and every argument after that is an extra source. A Verilator lint run
#      elaborates every module reachable from the top, so one run covers the whole chain.
#      --chain is the shortcut that globs rtl/*.sv with afib_lite_top as the top module.
#   2 -Wno-UNUSEDPARAM was missing. The plan requires it because every Fase 1 module keeps
#      the parameters its real body will need and the placeholder body does not read all of
#      them yet. Without the flag the chain cannot be linted clean, and the gate would be
#      met by deleting the parameters instead of by fixing the code.
#
# Testbenches are linted with --timing (plan 7.1: testbenches are linted too, with
# --timing and --top-module, so a testbench that cannot be parsed does not hide behind a
# clean design lint). The flag is added automatically for a source whose file name starts
# with tb_.
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

SOURCES=()
TOP=""
TIMING=()

if [ "${1:-}" = "--chain" ]; then
    # the whole chain in one command: the package plus every design file, afib_lite_top on top
    while IFS= read -r f; do SOURCES+=("$f"); done < <(find ../rtl -maxdepth 1 -name '*.sv' | LC_ALL=C sort)
    TOP="${2:-afib_lite_top}"
    if [ "${#SOURCES[@]}" -eq 0 ]; then
        echo "run_lint.sh --chain: no .sv file found under ../rtl" >&2
        exit 1
    fi
else
    SRC="${1:?usage: run_lint.sh <design.sv> <top module> [more sources ...] | run_lint.sh --chain [top]}"
    TOP="${2:?usage: run_lint.sh <design.sv> <top module> [more sources ...] | run_lint.sh --chain [top]}"
    shift 2
    SOURCES=("$SRC")
    while [ "$#" -gt 0 ]; do SOURCES+=("$1"); shift; done
fi

# Verilator parses files in command-line order and a package must be declared before a
# module that reaches into it (PKGNODECL). afib_lite_pkg.sv is therefore always moved to
# the front of the source list, whatever order the caller gave.
ORDERED=()
for f in "${SOURCES[@]}"; do
    case "$(basename "$f")" in
        afib_lite_pkg.sv) ORDERED=("$f" ${ORDERED[@]+"${ORDERED[@]}"});;
        *)                ORDERED+=("$f");;
    esac
done
SOURCES=("${ORDERED[@]}")

# a testbench needs the timing constructs enabled
for f in "${SOURCES[@]}"; do
    case "$(basename "$f")" in
        tb_*) TIMING=(--timing);;
    esac
done

echo "run_lint.sh: top=$TOP sources=${#SOURCES[@]} timing=${#TIMING[@]}"
for f in "${SOURCES[@]}"; do echo "  $f"; done

"$VL" --lint-only -sv --top-module "$TOP" -Wall -Wno-DECLFILENAME -Wno-UNUSEDPARAM \
      ${TIMING[@]+"${TIMING[@]}"} "${SOURCES[@]}"
echo "lint clean: top=$TOP sources=${#SOURCES[@]} ($VL)"
