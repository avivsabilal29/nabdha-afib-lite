#!/usr/bin/env python3
"""Class composition of the first 450,000 samples (30 minutes at 250 Hz) of every AFDB record."""
import pathlib

import wfdb

D = pathlib.Path("/home/avivsabilalm/nabdha-data/afdb")
W = 450_000

print("%-8s %9s %9s %9s %9s %s" % ("record", "AFIB%", "N%", "AFL%", "other%", "segments in window"))
for name in sorted(p.stem for p in D.glob("*.hea")):
    an = wfdb.rdann(str(D / name), "atr")
    tot = {}
    segs = 0
    for i in range(an.sample.size):
        note = str(an.aux_note[i]).strip()
        if not note:
            continue
        label = note.strip("(").strip(")")
        start = int(an.sample[i])
        end = int(an.sample[i + 1]) if i + 1 < an.sample.size else W
        e = min(end, W)
        if e <= start:
            continue
        segs += 1
        tot[label] = tot.get(label, 0) + (e - start)
    afib = tot.get("AFIB", 0)
    nrm = tot.get("N", 0)
    afl = tot.get("AFL", 0)
    other = W - afib - nrm - afl
    print("%-8s %8.2f %9.2f %9.2f %9.2f  %d" % (name, 100 * afib / W, 100 * nrm / W,
                                                100 * afl / W, 100 * other / W, segs))
