#!/usr/bin/env bash
# Verify that this folder can synthesise and simulate on this machine.
#
# Run ./setup_tools.sh first, and make sure sky130_fd_sc_hd__tt_025C_1v80.lib is in this folder.
# Prints one line per check and exits 1 if anything fails, so it doubles as a smoke test before you
# claim a number.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

LIB="sky130_fd_sc_hd__tt_025C_1v80.lib"
mkdir -p reports
pass=0
fail=0
ok()  { printf '  PASS  %s\n' "$1"; pass=$((pass + 1)); }
bad() { printf '  FAIL  %s\n' "$1"; fail=$((fail + 1)); }

# Resolve a tool: the local toolchain from ./setup_tools.sh first, then a system install.
resolve() {
    if [ -x "debroot/usr/bin/$1" ]; then
        echo "debroot/usr/bin/$1"
    else
        command -v "$1" || true
    fi
}

echo "== 1. tools =="
YOSYS_BIN="$(resolve yosys)"
if [ -n "$YOSYS_BIN" ]; then ok "yosys: $("$YOSYS_BIN" -V 2>&1 | head -1) [$YOSYS_BIN]"; else bad "yosys missing, run ./setup_tools.sh or install it"; fi
if [ -n "$(resolve yosys-abc)" ]; then ok "yosys-abc present"; else bad "yosys-abc missing, and yosys cannot map cells without it"; fi
IVL_BIN="$(resolve iverilog)"
if [ -n "$IVL_BIN" ]; then ok "iverilog: $("$IVL_BIN" -V 2>&1 | head -1) [$IVL_BIN]"; else bad "iverilog missing, run ./setup_tools.sh or install it"; fi
VL_BIN="$(resolve verilator_bin)"
if [ -z "$VL_BIN" ]; then VL_BIN="$(command -v verilator || true)"; fi
if [ -n "$VL_BIN" ]; then ok "verilator: $("$VL_BIN" --version 2>&1 | head -1) [$VL_BIN]"; else bad "verilator missing, run ./setup_tools.sh or install it"; fi

echo "== 2. system =="
ok "kernel: $(uname -sr) on $(uname -m)"
if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    OS_NAME="$(. /etc/os-release && echo "$PRETTY_NAME")"
    case "$OS_NAME" in
        *Ubuntu*|*Debian*) ok "distribution: $OS_NAME" ;;
        *) ok "distribution: $OS_NAME, which this flow has not been tested on. Expect to adapt the install path" ;;
    esac
else
    bad "no /etc/os-release, so the distribution is unknown"
fi

echo "== 3. library =="
LIB_BYTES=0
if [ -f "$LIB" ]; then LIB_BYTES="$(wc -c < "$LIB")"; fi
if [ "$LIB_BYTES" -gt 1000000 ]; then
    ok "liberty: $LIB_BYTES bytes, $(grep -c 'cell (' "$LIB") cell blocks"
    if [ "$LIB_BYTES" -eq 12800135 ]; then
        ok "liberty size matches the pinned corner file"
    else
        bad "liberty is $LIB_BYTES bytes, not the pinned 12800135. A different corner changes the area"
    fi
    if grep -q 'delay_model' "$LIB"; then ok "liberty has timing tables"; else bad "liberty has no delay_model, wrong file?"; fi
else
    bad "liberty is $LIB_BYTES bytes, which is not a library. A 14-byte file is a saved 404 page, so refetch with: curl -fL -o $LIB <url>"
fi

echo "== 4. simulation =="
if ./run_sim.sh template/tb_template.sv template/design_template.sv >reports/sim_check.log 2>&1; then
    if grep -q 'PASS' reports/sim_check.log; then ok "testbench ran and reported PASS"; else bad "testbench ran without PASS, see reports/sim_check.log"; fi
else
    bad "simulation failed, see reports/sim_check.log"
fi

echo "== 5. lint =="
if ./run_lint.sh template/design_template.sv design_template >reports/lint_check.log 2>&1; then
    ok "verilator lint clean on template/design_template.sv"
else
    bad "verilator lint failed, see reports/lint_check.log"
fi

echo "== 6. synthesis =="
for pair in "demo_counter.sv demo_counter" "demo_integrator.sv demo_integrator"; do
    set -- $pair
    design=$1
    top=$2
    if ./run_synth.sh "$design" "$top" >"reports/synth_check_$top.log" 2>&1; then
        if grep -q 'is unknown' "reports/synth_check_$top.log"; then
            bad "$top: unmapped cells in the log, the area is wrong"
        else
            cells=$(grep -E 'Number of cells' "reports/synth_check_$top.log" | tail -1 | tr -s ' ')
            area=$(grep -E '^area ' "reports/synth_check_$top.log" | tail -1 | tr -s ' ')
            ok "$top: ${cells:-mapped} | ${area:-no area line}"
        fi
    else
        bad "$top: synthesis failed, see reports/synth_check_$top.log"
    fi
done

echo
echo "checks passed: $pass, failed: $fail"
if [ "$fail" -gt 0 ]; then
    exit 1
fi
echo "This machine is ready. Compare the cell counts and areas above with the figures in TASK_BRIEF.md."
