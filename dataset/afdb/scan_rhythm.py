#!/usr/bin/env python3
"""Scan the rhythm annotation of every AFDB candidate and report the AFIB share.

Read only. The record itself is not downloaded for the candidates; only the header and the
annotation file are needed, because the share is a property of the annotation and the
declared sample count.
"""
import pathlib
import sys

import wfdb

D = pathlib.Path("/home/avivsabilalm/nabdha-data/afdb")


def stretches(path):
    an = wfdb.rdann(str(path), "atr")
    n = an.sample.size
    out = []
    for i in range(n):
        note = str(an.aux_note[i]).strip()
        if not note:
            continue
        label = note.strip("(").strip(")")
        start = int(an.sample[i])
        end = int(an.sample[i + 1]) if i + 1 < n else None
        out.append((start, end, label))
    return an, out


def main():
    names = [l.strip() for l in (D / "RECORDS").read_text().splitlines() if l.strip()] \
        if (D / "RECORDS").exists() else sorted(p.stem for p in D.glob("*.hea"))
    # the RECORDS list was fetched to /tmp, fall back to the local files
    names = sorted(p.stem for p in D.glob("*.hea"))
    print("%-8s %10s %6s %8s %9s %9s %9s %9s" %
          ("record", "n_samp", "notes", "rhythm", "cover%", "AFIB%", "AFL%", "N%"))
    rows = []
    for name in names:
        hea = (D / (name + ".hea")).read_text().split("\n")[0].split()
        n = int(hea[3]) if len(hea) > 3 else 0
        try:
            an, seg = stretches(D / name)
        except Exception as exc:                                  # noqa: BLE001
            print("%-8s %10d  annotation could not be read: %s" % (name, n, exc))
            continue
        if n == 0:
            n = int(an.sample[-1]) + 1 if an.sample.size else 0
        tot = {}
        cover = 0
        for start, end, label in seg:
            e = n - 1 if end is None else min(end - 1, n - 1)
            if e < start:
                continue
            length = e - start + 1
            cover += length
            tot[label] = tot.get(label, 0) + length
        afib = tot.get("AFIB", 0)
        afl = tot.get("AFL", 0)
        nrm = tot.get("N", 0)
        rows.append((name, n, afib / n if n else 0.0, len(seg)))
        print("%-8s %10d %6d %8d %8.2f %8.2f %8.2f %8.2f  labels %s"
              % (name, n, an.sample.size, len(seg), 100.0 * cover / n if n else 0.0,
                 100.0 * afib / n if n else 0.0, 100.0 * afl / n if n else 0.0,
                 100.0 * nrm / n if n else 0.0,
                 ",".join("%s=%d" % (k, v) for k, v in sorted(tot.items()))))
    print()
    print("sorted by AFIB share, descending")
    for name, n, share, nseg in sorted(rows, key=lambda r: -r[2]):
        print("  %-8s %6.2f percent AFIB, %d rhythm segments" % (name, 100 * share, nseg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
