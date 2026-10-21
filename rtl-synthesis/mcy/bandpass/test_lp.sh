exec 2>&1
set -x
# mcy reads tasks/<id>/output.txt and crashes when it is missing, so write the verdict first.
VERDICT=output.txt
echo "1 ERROR" > $VERDICT

REPO=/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
DEB=$REPO/rtl-synthesis/debroot/usr/bin
IVLDIR=$REPO/rtl-synthesis/debroot/usr/lib/x86_64-linux-gnu/ivl
F0=/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0

bash $SCRIPTS/create_mutated.sh

$DEB/iverilog -B $IVLDIR -g2012 -o sim.vvp \
    $REPO/rtl/afib_lite_pkg.sv \
    $REPO/rtl/tb/tb_lowpass.sv \
    mutated.v

$DEB/vvp sim.vvp +VECTOR=$F0 +LIMIT=20000 > sim.out

if grep -q ": PASS" sim.out; then
    echo "1 PASS" | tee $VERDICT
else
    echo "1 FAIL" | tee $VERDICT
fi

exit 0
