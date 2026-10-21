#!/usr/bin/env bash
# One entry point for the three tools this project needs: lint, simulate, synthesise.
#
#   ./flow.sh lint     Verilator lint of the design, before every other step
#   ./flow.sh sim      Icarus compile and run of the self-checking testbench
#   ./flow.sh synth    Yosys synthesis to SKY130 standard cells
#   ./flow.sh area     cell count and area from the netlist and the liberty file
#   ./flow.sh all      lint, then sim, then synth, then area
#
# The toolchain is the portable one already unpacked in ../rtl-synthesis/debroot, which needs no
# root. A system install works as a fallback. Each tool needs one environment variable when it comes
# from a relocated prefix, so they are set here instead of in the shell:
#   Icarus     -B, because it looks for ivl and ivlpp on a path baked in at build time
#   Verilator  VERILATOR_ROOT, and the binary must be called directly, not through the wrapper
#   Yosys      YOSYS_DATDIR, so it finds its technology files

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

TOOLROOT="${TOOLROOT:-$HERE/../../rtl-synthesis}"
DEB="$TOOLROOT/debroot"
LIB="${LIB:-$TOOLROOT/sky130_fd_sc_hd__tt_025C_1v80.lib}"
TOP="counter8"
SRC="counter8.sv"
TB="tb_counter8.sv"
TB2="tb_throughput.sv"

IVLARGS=()
if [ -x "$DEB/usr/bin/iverilog" ]; then
    IVL="$DEB/usr/bin/iverilog"; VVP="$DEB/usr/bin/vvp"
    IVLDIR="$DEB/usr/lib/x86_64-linux-gnu/ivl"
    [ -d "$IVLDIR" ] || IVLDIR="$(find "$DEB" -type d -name ivl 2>/dev/null | head -1)"
    [ -n "$IVLDIR" ] && IVLARGS=(-B "$IVLDIR")
else
    IVL="iverilog"; VVP="vvp"
fi

if [ -x "$DEB/usr/bin/verilator_bin" ]; then
    VL="$DEB/usr/bin/verilator_bin"
    export VERILATOR_ROOT="$DEB/usr/share/verilator"
else
    VL="verilator"
fi

if [ -x "$DEB/usr/bin/yosys" ]; then
    YOSYS="$DEB/usr/bin/yosys"
    export YOSYS_DATDIR="$DEB/usr/share/yosys"
else
    YOSYS="yosys"
fi

mkdir -p build reports

lint() {
    echo "== lint: design and testbench, with $("$VL" --version | head -1)"
    "$VL" --lint-only -sv --top-module "$TOP" -Wall -Wno-DECLFILENAME "$SRC"
    "$VL" --lint-only -sv --timing --top-module "tb_$TOP" -Wall -Wno-DECLFILENAME "$TB" "$SRC"
    "$VL" --lint-only -sv --timing --top-module tb_throughput -Wall -Wno-DECLFILENAME "$TB2" "$SRC"
    echo "lint clean"
}

sim() {
    echo "== sim: $TB with $("$IVL" -V 2>&1 | head -1)"
    "$IVL" ${IVLARGS[@]+"${IVLARGS[@]}"} -g2012 -o "build/$TB.vvp" "$TB" "$SRC"
    "$VVP" "build/$TB.vvp" | tee reports/sim.log
    grep -q "RESULT PASS" reports/sim.log
    echo "simulation passed"
}

synth() {
    echo "== synth: $SRC with $("$YOSYS" -V 2>&1 | head -1)"
    "$YOSYS" -l reports/synth.log -p "
        read_verilog -sv $SRC;
        hierarchy -top $TOP;
        synth -top $TOP;
        dfflibmap -liberty $LIB;
        abc -liberty $LIB;
        opt_clean;
        stat -liberty $LIB;
        write_json reports/$TOP.json
    " > reports/synth.txt 2>&1
    grep -E "Number of cells|Chip area" reports/synth.txt || true
    echo "netlist written to reports/$TOP.json"
}

area() {
    echo "== area: reports/$TOP.json against $(basename "$LIB")"
    python3 "$TOOLROOT/area_report.py" "reports/$TOP.json" "$LIB"
}

# Trace of the same run, for looking at waves. No viewer is installed on this machine, so the file
# is the deliverable: open it with Surfer, GTKWave, or a VCD viewer extension in the editor.
wave() {
    echo "== wave: $TB with tracing on"
    "$IVL" ${IVLARGS[@]+"${IVLARGS[@]}"} -g2012 -o "build/$TB.vvp" "$TB" "$SRC"
    "$VVP" "build/$TB.vvp" "+vcd" > reports/sim_wave.log
    ls -l reports/counter8.vcd
}

# Read the trace back. flow.sh wave writes reports/counter8.vcd; this prints it as text and also
# writes a standalone timing diagram, because no waveform viewer is installed here.
vcd() {
    local sig="clk,rst_n,en,load,count,carry,borrow,zero"
    [ -f reports/counter8.vcd ] || { echo "reports/counter8.vcd is missing, run ./flow.sh wave first" >&2; exit 1; }
    python3 vcd_view.py reports/counter8.vcd --signals "$sig" --mode wave
    python3 vcd_view.py reports/counter8.vcd --signals "$sig" --html reports/counter8_timing.html > /dev/null
    echo
    echo "timing diagram written to reports/counter8_timing.html"
}

# Simulate the same SystemVerilog testbench on Verilator instead of Icarus. Same file, same checks,
# different engine, and neither engine is Vivado.
sim_vl() {
    echo "== sim: $TB on Verilator"
    "$VL" --binary --timing --top-module "tb_$TOP" --Mdir build/vsim -Wno-DECLFILENAME \
          -o "vsim_$TOP" "$TB" "$SRC" > reports/verilator_build.log 2>&1
    "build/vsim/vsim_$TOP" | tee reports/sim_verilator.log
    grep -q "RESULT PASS" reports/sim_verilator.log
    echo "verilator simulation passed"
}

# How many clock cycles per second each simulator does on this design. Numbers, not feelings.
# Take the checksum seriously: both runs must print the same one, otherwise they are not simulating
# the same thing.
bench() {
    local n="${1:-1000000}"
    local t0 t1 ivl_s vl_s
    echo "== bench: $n clock cycles of $TOP"
    "$IVL" ${IVLARGS[@]+"${IVLARGS[@]}"} -g2012 -o "build/$TB2.vvp" "$TB2" "$SRC"
    "$VL" --binary --timing --top-module tb_throughput --Mdir build/vth -Wno-DECLFILENAME \
          -o vsim_throughput "$TB2" "$SRC" > reports/verilator_throughput_build.log 2>&1

    t0=$(date +%s.%N); "$VVP" "build/$TB2.vvp" "+cycles=$n" > reports/bench_icarus.log; t1=$(date +%s.%N)
    ivl_s=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.2f", b-a}')
    t0=$(date +%s.%N); "build/vth/vsim_throughput" "+cycles=$n" > reports/bench_verilator.log; t1=$(date +%s.%N)
    vl_s=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.2f", b-a}')

    sed 's/^/  icarus    /' reports/bench_icarus.log
    sed 's/^/  verilator /' reports/bench_verilator.log
    printf '  cycles %s  icarus %s s  verilator %s s\n' "$n" "$ivl_s" "$vl_s"
    awk -v i="$ivl_s" -v v="$vl_s" 'BEGIN{ if (v > 0) printf "  speedup %.1fx\n", i/v }'
}

case "${1:-all}" in
    lint)   lint ;;
    sim)    sim ;;
    sim-vl) sim_vl ;;
    wave)   wave ;;
    vcd)    vcd ;;
    bench)  bench "${2:-1000000}" ;;
    synth)  synth ;;
    area)   area ;;
    all)    lint; sim; synth; area ;;
    *)      echo "usage: $0 {lint|sim|sim-vl|wave|vcd|bench|synth|area|all}" >&2; exit 2 ;;
esac
