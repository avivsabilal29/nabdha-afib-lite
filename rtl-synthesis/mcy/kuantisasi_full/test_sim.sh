#!/bin/bash
# Mutation test for the acquisition and quantiser stage (Fase 2).
# Called by mcy inside a per mutant working directory. create_mutated.sh reads input.txt
# written by mcy plus ../../database/design.il and produces mutated.v in this directory.
exec 2>&1
set -x
# mcy reads tasks/<id>/output.txt and crashes if it is missing, so the verdict file is
# written before anything else can fail.
echo "1 ERROR" > output.txt

REPO=/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
DEB=$REPO/rtl-synthesis/debroot/usr/bin
IVLDIR=$REPO/rtl-synthesis/debroot/usr/lib/x86_64-linux-gnu/ivl
F0=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0

bash $SCRIPTS/create_mutated.sh

$DEB/iverilog -B $IVLDIR -g2012 -o sim.vvp \
    $REPO/rtl/afib_lite_pkg.sv \
    $REPO/rtl/tb/tb_kuantisasi.sv \
    mutated.v

# A mutation that breaks sample_en or sample_idx makes the bench wait loop spin forever, so
# every simulation is bounded. A timeout counts as FAIL: the mutant never emits a valid sample,
# which means the design is provably broken. The timeout count is reported separately afterwards.
TIMEOUT_S=${TIMEOUT_S:-120}
timeout $TIMEOUT_S $DEB/vvp sim.vvp \
    +VECTOR=$F0/04015.masukan16.hex \
    +MANIFEST=$F0/04015.manifest.json \
    +STIM=$REPO/rtl/tb/vektor/04015.stimulus.hex \
    +LIMIT=20000 > sim.out
sim_rc=$?

# output.txt must hold verdict lines only, in the form "<count> <TAG>", because mcy parses every
# line. A prose line here aborts the whole campaign with "Invalid line format".
if [ "$sim_rc" -eq 124 ]; then
    echo "TIMEOUT after ${TIMEOUT_S}s, counted as a kill"
    echo "1 FAIL" > output.txt
elif grep -q "failures: 0" sim.out; then
    echo "1 PASS" | tee output.txt
else
    echo "1 FAIL" | tee output.txt
fi

exit 0
