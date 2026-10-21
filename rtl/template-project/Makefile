# Convenience wrapper around flow.sh, so the three flows are reachable with make.
#
#   make            lint, simulate, synthesise, report area
#   make lint       Verilator lint only
#   make sim        Icarus simulation of the self-checking testbench
#   make synth      Yosys synthesis to SKY130
#   make sim-vl     same testbench on Verilator instead of Icarus
#   make bench      simulator speed comparison, default 1M cycles: make bench CYCLES=10000000
#   make wave       run with tracing on, writes reports/counter8.vcd
#   make vcd        print the trace as text, and write reports/counter8_timing.html
#   make area       cell count and area report
#   make clean      remove build products and reports
#
# Override the toolchain root when your checkout differs:
#   make TOOLROOT=/path/to/repo/rtl-synthesis all

TOOLROOT ?= ../../rtl-synthesis

.PHONY: all lint sim sim-vl bench synth area clean

all:
	TOOLROOT=$(TOOLROOT) ./flow.sh all

lint:
	TOOLROOT=$(TOOLROOT) ./flow.sh lint

sim:
	TOOLROOT=$(TOOLROOT) ./flow.sh sim

sim-vl:
	TOOLROOT=$(TOOLROOT) ./flow.sh sim-vl

wave:
	TOOLROOT=$(TOOLROOT) ./flow.sh wave

vcd:
	TOOLROOT=$(TOOLROOT) ./flow.sh vcd

bench:
	TOOLROOT=$(TOOLROOT) ./flow.sh bench $(CYCLES)

synth:
	TOOLROOT=$(TOOLROOT) ./flow.sh synth

area:
	TOOLROOT=$(TOOLROOT) ./flow.sh area

clean:
	rm -rf build reports
