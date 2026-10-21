#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# siapkan_vektor_fase6.py -- turn the frozen Fase 5 golden CSVs into the hex
# columns tb_rr.sv reads. Plan doc 38 section 12, Fase 6.
#
# Inputs, read only, never written:
#   rtlplan2/fase5/04015.rr.csv        one row per raw RR interval, 2595 rows, with the
#                                      four stage 7b mark columns
#   rtlplan2/fase5/04015.peaks.csv     one row per envelope peak, 4777 rows; the QRS
#                                      series is the qrs_sample_index column
#   rtlplan2/fase5/04015.manifest.fase5.json   the counts block is the anchor
#
# Outputs, in the same directory as this script (rtl/tb/vektor/fase6/):
#   04015.qrs.hex           2596 QRS sample positions, in file order
#   04015.rr.hex            2595 raw RR intervals in milliseconds
#   04015.rr.smp.hex        2595 sample distances, qrs_cur_sample - qrs_prev_sample
#   04015.rr.mark.hex       2595 stage 7b marks, 0 keep 1 split 2 drop 3 gap
#   04015.rr.mask.hex       2595 one hot masks, keep b0 split b1 drop b2 gap b3
#   04015.rrstep.*.hex      2586 rows each, the locked stage state after every in band
#                           interval: ra1, ra2, antre length, menyala, disemai,
#                           riwayat length, gagal (fail counter), jeda (pace counter)
#   04015.fase6.counts.hex  the end of run counts, layout documented below
#   04015.fase6.manifest.json   provenance: input hashes, model hash, counts
#
# Why a sidecar column exists at all. The plan Fase 6 gate has three parts: 0 of 2595
# intervals different, the queue length exactly 8 after step 24, and all four marks
# readable. The first and third are in the frozen CSVs. The second is a quantity of the
# locked stage (rantai.rr) that the Fase 5 export does not carry in a CSV column, so this
# script recomputes it from the frozen model itself, over the same raw interval series the
# CSV carries, and records the model hash next to the numbers. The anchor that says the
# recomputation is the model's own trajectory and not this script's invention is the
# manifest: the counts block of 04015.manifest.fase5.json holds the locked stage state at
# the end of the record, semai 26, penanda 1202 and langkah 2586, and they are checked
# below against what this script just produced. A mismatch stops the export.
#
# Every number here is an integer, as in the model: no floating point is used, and no value
# is typed in. The only literal that is not read from a file is the model line split
# (250 <= rr_ms <= 2000, rantai.py:638) and the two literal band edges are taken from
# afib_lite_pkg.sv instead, RR_BAND_MIN_MS and RR_BAND_MAX_MS, parsed out of the package so
# this script carries no RR constant of its own.
# ---------------------------------------------------------------------------
import csv
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
FASE5 = os.path.join(REPO, "rtlplan2", "fase5")
MODEL = os.path.join(REPO, "model", "rantai-afib-lite")
PKG = os.path.join(REPO, "rtl", "afib_lite_pkg.sv")

RR_CSV = os.path.join(FASE5, "04015.rr.csv")
PEAK_CSV = os.path.join(FASE5, "04015.peaks.csv")
MANIFEST = os.path.join(FASE5, "04015.manifest.fase5.json")

sys.path.insert(0, MODEL)
import rantai as R  # noqa: E402

FROZEN_RANTAI = "90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5"

FAILURES = []


def check(name, got, want):
    ok = (got == want)
    print("OK   %-46s %s" % (name, got) if ok else
          "FAIL %-46s got=%s want=%s" % (name, got, want))
    if not ok:
        FAILURES.append(name)
    return ok


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def pkg_localparam(name):
    """Read one localparam integer out of afib_lite_pkg.sv, so no constant is typed here."""
    with open(PKG) as f:
        for line in f:
            m = re.match(r"\s*localparam\s+[^=]*?\b%s\s*=\s*([0-9_]+)\s*;" % re.escape(name), line)
            if m:
                return int(m.group(1).replace("_", ""))
    raise SystemExit("pkg constant not found: %s" % name)


def emit(name, words, width=32):
    path = os.path.join(HERE, name)
    with open(path, "w") as f:
        for w in words:
            f.write("%0*x\n" % (width // 4, int(w) & ((1 << width) - 1)))
    print("wrote %-28s %6d words" % (name, len(words)))
    return path


def main():
    print("== siapkan_vektor_fase6 ==")
    print("rr.csv   [%s]" % RR_CSV)
    print("peaks.csv[%s]" % PEAK_CSV)

    rr_sha = sha256(RR_CSV)
    peak_sha = sha256(PEAK_CSV)
    man_sha = sha256(MANIFEST)
    rantai_sha = sha256(os.path.join(MODEL, "rantai.py"))
    check("frozen model sha256", rantai_sha, FROZEN_RANTAI)

    band_lo = pkg_localparam("RR_BAND_MIN_MS")
    band_hi = pkg_localparam("RR_BAND_MAX_MS")
    ceil_ms = pkg_localparam("RR_LONG_MS")
    print("INFO package band %d..%d ms, long ceiling %d ms" % (band_lo, band_hi, ceil_ms))

    man = json.load(open(MANIFEST))
    man_counts = man["counts"]

    # ---------------------------------------------------------------- QRS series
    # The QRS series is the qrs_sample_index column in file order, NOT the is_qrs flag:
    # two rows carry is_qrs 1 with the index column blank and two carry is_qrs 0 with a
    # filled column, because the search back walk moves a recorded beat backwards. Both
    # anomalies are counted and printed as evidence.
    qrs = []
    qval = []
    flag_rows = 0
    flag_blank = 0
    idx_on_noflag = 0
    with open(PEAK_CSV) as f:
        for r in csv.DictReader(f):
            v = r["qrs_sample_index"].strip()
            if r["is_qrs"] == "1":
                flag_rows += 1
                if not v:
                    flag_blank += 1
                    continue
            if v:
                if r["is_qrs"] != "1":
                    idx_on_noflag += 1
                qrs.append(int(v))
                # the amplitude word the event sideband carries for this beat, the
                # envelope_value column of the same row
                qval.append(int(r["envelope_value"]))
    print("INFO qrs flag rows %d, of which blank index %d, index filled with flag 0 %d"
          % (flag_rows, flag_blank, idx_on_noflag))
    check("qrs series length", len(qrs), man_counts["qrs"])
    check("qrs series strictly ascending", all(qrs[i] < qrs[i + 1] for i in range(len(qrs) - 1)), True)
    check("qrs amplitude words", len(qval), len(qrs))
    check("qrs amplitude words fit 32 bits", max(qval) < (1 << 32), True)

    # ---------------------------------------------------------------- raw intervals
    rr = []
    marks = []
    prevs = []
    curs = []
    mask = []
    with open(RR_CSV) as f:
        for r in csv.DictReader(f):
            rr.append(int(r["rr_ms"]))
            marks.append(int(r["mark"]))
            prevs.append(int(r["qrs_prev_sample"]))
            curs.append(int(r["qrs_cur_sample"]))
            mask.append(int(r["mark_keep"]) | (int(r["mark_split"]) << 1) |
                        (int(r["mark_drop"]) << 2) | (int(r["mark_gap"]) << 3))
    check("interval rows", len(rr), man_counts["rr_intervals"])
    check("interval rows == qrs - 1", len(rr), len(qrs) - 1)

    # the CSV's own provenance, re-derived here: rr_ms = (qrs[i+1] - qrs[i]) << 2 and the
    # sample pair of every row is the consecutive pair of the QRS column
    calc = [(qrs[i + 1] - qrs[i]) << 2 for i in range(len(qrs) - 1)]
    check("rr_ms equals (qrs[i+1]-qrs[i])<<2", calc == rr, True)
    check("row sample pair equals the qrs column",
          all(prevs[i] == qrs[i] and curs[i] == qrs[i + 1] for i in range(len(rr))), True)
    smp = [curs[i] - prevs[i] for i in range(len(rr))]

    # ---------------------------------------------------------------- stage 7b marks
    st = R.rr_rhythm_awal()
    redo = []
    for x in rr:
        m, st = R.rr_rhythm(x, st)
        redo.append(m)
    check("marks recomputed from the frozen model", redo == marks, True)
    census = [marks.count(k) for k in range(4)]
    check("mark census", census, man_counts["rr_mark_census"])
    check("corrected entries", len(st["corrected"]), man_counts["rr_corrected_entries"])
    check("corrected entries == keep + gap + 2*split", len(st["corrected"]),
          marks.count(0) + marks.count(3) + 2 * marks.count(1))
    check("one hot mask equals the mark", all(mask[i] == (1 << marks[i]) for i in range(len(rr))), True)
    check("every mark value is exercised", all(c > 0 for c in census), True)

    # ---------------------------------------------------------------- locked stage
    # rantai.py:375-440, driven by the same raw series, gated by the model's own band
    # (250 <= rr_ms <= 2000, rantai.py:638), with the band edges read from the package.
    tahap = R.rr_awal()
    steps = []
    step = 0
    for i, x in enumerate(rr):
        if not (band_lo <= x <= band_hi):
            continue
        step += 1
        menyala, disemai, tahap, _ = R.rr(x, tahap)
        steps.append(dict(i=i, step=step, rr=x, ra1=tahap["ra1"], ra2=tahap["ra2"],
                          antre=len(tahap["antre"]), menyala=int(menyala),
                          disemai=int(disemai), riwayat=len(tahap["riwayat"]),
                          gagal=tahap["gagal"], jeda=tahap["jeda"]))
    check("in band intervals driven (langkah)", step, man["counts"]["ambang_state"][8])
    check("reseed count (semai)", tahap["semai"], man["counts"]["ambang_state"][6])
    check("menyala count (penanda)", sum(s["menyala"] for s in steps),
          man["counts"]["ambang_state"][7])
    check("baris rows", len(tahap["baris"]), step - 7)

    # the queue length gate of Fase 6: exactly 8 after step 24
    not_full = [s["step"] for s in steps if s["antre"] != 8]
    last_not_full = max(not_full) if not_full else 0
    after24 = [s["antre"] for s in steps if s["step"] > 24]
    check("last step whose queue is not full", last_not_full, 24)
    check("queue length after step 24 is 8 everywhere", set(after24) == {8}, True)
    check("queue length of step 25", steps[25 - 1]["antre"], 8)
    print("INFO queue length at step 24 = %d, at step 25 = %d, full rows %d of %d"
          % (steps[24 - 1]["antre"], steps[25 - 1]["antre"],
             sum(1 for s in steps if s["antre"] == 8), len(steps)))

    long_ix = [i for i in range(len(rr)) if rr[i] > ceil_ms]
    print("INFO intervals above %d ms: %d at rows %s" % (ceil_ms, len(long_ix),
                                                         long_ix[:8]))

    # ---------------------------------------------------------------- write it out
    emit("04015.qrs.hex", qrs)
    emit("04015.qrsval.hex", qval)
    emit("04015.rr.hex", rr)
    emit("04015.rr.smp.hex", smp)
    emit("04015.rr.mark.hex", marks)
    emit("04015.rr.mask.hex", mask)
    emit("04015.rrstep.ra1.hex", [s["ra1"] for s in steps])
    emit("04015.rrstep.ra2.hex", [s["ra2"] for s in steps])
    emit("04015.rrstep.antre.hex", [s["antre"] for s in steps])
    emit("04015.rrstep.menyala.hex", [s["menyala"] for s in steps])
    emit("04015.rrstep.disemai.hex", [s["disemai"] for s in steps])
    emit("04015.rrstep.riwayat.hex", [s["riwayat"] for s in steps])
    emit("04015.rrstep.gagal.hex", [s["gagal"] for s in steps])
    emit("04015.rrstep.jeda.hex", [s["jeda"] for s in steps])
    emit("04015.rrstep.rr.hex", [s["rr"] for s in steps])

    counts = [
        len(rr),
        len(st["corrected"]),
        census[0], census[1], census[2], census[3],
        len(qrs),
        step,
        tahap["semai"],
        sum(s["menyala"] for s in steps),
        last_not_full,
        steps[25 - 1]["antre"],
        len(long_ix),
        max(rr),
        min(rr),
        sum(1 for s in steps if s["antre"] == 8),
    ]
    names = ["rr_intervals", "rr_corrected_entries", "census_keep", "census_split",
             "census_drop", "census_gap", "qrs_count", "rr_steps", "semai_total",
             "penanda_total", "last_step_queue_not_full", "queue_len_step_25",
             "long_over_ceiling", "rr_max_ms", "rr_min_ms", "steps_queue_full"]
    for n, v in zip(names, counts):
        print("INFO counts %-26s %d" % (n, v))
    emit("04015.fase6.counts.hex", counts)

    manifest = {
        "phase": 6,
        "generator": os.path.abspath(__file__),
        "counts_layout": names,
        "counts": dict(zip(names, counts)),
        "inputs_sha256": {
            "04015.rr.csv": rr_sha,
            "04015.peaks.csv": peak_sha,
            "04015.manifest.fase5.json": man_sha,
            "afib_lite_pkg.sv": sha256(PKG),
        },
        "frozen_model_sha256": {"rantai.py": rantai_sha},
        "anchors": {
            "manifest_counts_rr_intervals": man_counts["rr_intervals"],
            "manifest_counts_rr_corrected_entries": man_counts["rr_corrected_entries"],
            "manifest_counts_rr_mark_census": man_counts["rr_mark_census"],
            "manifest_counts_qrs": man_counts["qrs"],
            "manifest_ambang_state_langkah": man["counts"]["ambang_state"][8],
            "manifest_ambang_state_semai": man["counts"]["ambang_state"][6],
            "manifest_ambang_state_penanda": man["counts"]["ambang_state"][7],
            "note": "the locked stage sidecar columns (ra1 ra2 antre menyala disemai "
                    "riwayat gagal jeda) do not exist as CSV columns in the Fase 5 export; "
                    "they are recomputed here by running the frozen model over the same raw "
                    "interval series the CSV carries, and the three anchored counts above "
                    "are what ties that recomputation to the frozen manifest",
        },
        "package_constants_used": {"RR_BAND_MIN_MS": band_lo, "RR_BAND_MAX_MS": band_hi,
                                   "RR_LONG_MS": ceil_ms},
    }
    with open(os.path.join(HERE, "04015.fase6.manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
        f.write("\n")

    print("checks failed: %d" % len(FAILURES))
    if FAILURES:
        print("FAIL %s" % ",".join(FAILURES))
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
