#!/usr/bin/env python3
"""AFIB-LITE measurement only: what the window layer would do if it consumed the corrected RR
series instead of the raw RR series.

This file changes nothing. It reads the frozen modules, runs the frozen chain, and measures one
single question that step S7 left open in its own section 8, item 1:

    The corrected RR series exists (rantai.py stage 7b) but it is NOT consumed by the window
    decision layer. The window layer builds its interval series from the beat list `qrs`, by
    np.diff, and not from the RR stage at all. What would move if it consumed the corrected
    series instead, with the locked operating point left exactly as it is?

WHAT IS MEASURED, precisely.

For every recording the window feature table is produced TWICE, by the same rule, the frozen
rule of rantai.kumpulkan_jendela:

  ARM RAW        the interval series is np.diff(qrs) / FS_HZ * 1000, in ms, which is bit for bit
                 the series the pipeline consumes today, and the class of an interval is the
                 rhythm annotation at the beat that ends it, lab[qrs[1:]]. This arm is the
                 current pipeline, and it is produced by calling the frozen
                 rantai.kumpulkan_jendela itself. Nothing is reimplemented for it.

  ARM CORRECTED  the interval series is the stage 7b corrected series, rantai hasil()
                 ["rr_corrected"], in ms. Its per-interval class is propagated from the raw
                 interval each corrected entry came from, by the marker semantics of stage 7b:
                 mark 0 keep and mark 3 gap carry their source interval's class, mark 2 drop
                 produced no entry at all, and mark 1 split produced two entries that both
                 carry their source interval's class. The frozen window rule is then applied to
                 this series with a collector that is a line for line generalisation of
                 rantai.kumpulkan_jendula to any series with a class per interval: same 32
                 interval window, same step of 4, same single class AFIB or N requirement, same
                 200 ms to 3000 ms band, same fitur_irama.

WHY THE TWO ARMS ARE COMPARED BY THE SOURCE INTERVAL INDEX, and not by window ordinal.

The corrected series has a different length from the raw series (on 04015 it has more entries,
because a split adds one and a drop removes one), so window number k of one arm is not window
number k of the other arm. The two arms are therefore matched on the only axis they share: the
index of the raw interval series. The origin of a window is the index, in the raw interval
series, of the raw interval its first entry came from. For ARM RAW that is just the window start
i. For ARM CORRECTED it is src[i], the raw interval that produced corrected entry i. Both are
raw interval indices, so a window of one arm and a window of the other are "the same window"
when their origins are equal. Every matched origin may then be checked for a different feature
vector and for a different class. Windows whose origin exists in only one arm are counted
separately as arm only, which is itself part of the answer.

Because a split turns one raw interval into two entries, a 32 entry corrected window spans
fewer raw intervals than a 32 entry raw window. The measurement below states that plainly and
the limitation section repeats it: the two arms are the same rule over different lengths of
series, not the same physical window.

THE OPERATING POINTS. No threshold is derived here and no threshold is edited. Three pairs are
used exactly as they are locked or proposed, and they are used identically on both arms:

    K   ratio 0.165, entropy 0.63   the operating point locked by Aviv
    P2  ratio 0.165, entropy 0.67   the first spare row
    P5  ratio 0.210, entropy 0.70   the old locked pair, kept as the second spare row

Test records are 04043 and 04126, pooled into 1562 windows including 677 AFIB as
uji_06_referensi.py and uji_05_kebijakan_ambang.py count them. 04015 is the record the threshold was
derived on, so it is reported as a reference only and never used to choose anything.

Run it with the project interpreter:

    cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/uji_09_deret_terkoreksi.py

Exit code is 0 when the measurement self-checks pass, 1 when they do not. The self-checks only
guard that ARM RAW reproduces the frozen pipeline and that the generalised collector agrees with
the frozen collector. They are not a verdict on the corrected arm: no gate of the project is
re-run or re-scored by this file, and no number here chooses a threshold.

The honest list of what this file does NOT measure is at the end of the output and in the
function laporan_tidak_diukur.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import rantai as R                 # frozen, imported and never modified
import uji_06_referensi as U          # frozen, imported and never modified
import uji_04_ambang_pool as P        # frozen, imported and never modified
import uji_05_kebijakan_ambang as K   # frozen, imported and never modified
                                    # K.metrik_lengkap is the project's own metric with the raw
                                    # counts, PPV, NPV and the miss rate, reused here unchanged

# =============================================================================================
# Constants. Only locked numbers and the two frozen reference counts are copied here, and both
# are checked in the run rather than trusted.
# =============================================================================================

FIXTURE = HERE / "fixture" / "04015_30m.npz"
SHA_FIXTURE = "91ff408fb1b7880a124d28bcc4205038935d4a3a2dbabb4c0f7d161d89e8ac4d"

DERIVATION_RECORD = "04015"                 # reference only, never used to choose anything
TEST_RECORDS = ("04043", "04126")           # the two hold-out records
ALL_RECORDS = (DERIVATION_RECORD,) + TEST_RECORDS

# The three operating points, used exactly as locked or proposed. t1 is the ratio threshold,
# t2 the entropy threshold, and both land on the same two feature columns the pipeline uses,
# fitur[:, 1] = RMSSD / mean RR and fitur[:, 3] = entropy / 4.
TITIK = (
    ("K",  0.165, 0.63, "locked by Aviv, used as is"),
    ("P2", 0.165, 0.67, "spare row"),
    ("P5", 0.210, 0.70, "old locked pair, spare row"),
)

S6_WINDOWS = 1562               # pooled hold-out window count of the frozen pipeline
S6_AFIB = 677                   # pooled hold-out AFIB window count of the frozen pipeline

MAIN = "main"
SPARE = "spare"

HASIL = []


# =============================================================================================
# Reporting
# =============================================================================================

def periksa(nama, lulus, keterangan):
    """One self-check line, collected for the summary line."""
    HASIL.append((nama, bool(lulus)))
    print("%-58s %-4s %s" % (nama, "PASS" if lulus else "FAIL", keterangan), flush=True)
    return bool(lulus)


def kepala(teks):
    print()
    print(teks, flush=True)


def lapor(nama, keterangan):
    """A measured fact that is not a pass or fail condition."""
    print("     %-42s %s" % (nama, keterangan), flush=True)


def sel(x, lebar=8, desimal=4):
    """One metric cell, with an explicit marker when the denominator was empty."""
    if x is None:
        return "n/a".rjust(lebar)
    return ("%.*f" % (desimal, x)).rjust(lebar)


def bil(x, lebar=6):
    if x is None:
        return "n/a".rjust(lebar)
    return str(x).rjust(lebar)


# =============================================================================================
# The corrected interval series and its class per interval.
#
# Stage 7b exposes rr_corrected (the expanded series) and rr_mark_corrected (one mark per
# corrected entry). The source raw interval of every corrected entry is reconstructed here from
# rr_mark_raw, exactly by the vocabulary of stage 7b, and the class of the entry is taken from
# the class of that source raw interval. No value of any series is edited, and nothing is added
# or removed: this is a read only walk over the marks stage 7b already produced.
# =============================================================================================

def kelas_per_interval_mentah(core, label):
    """Class of every raw interval, the class at the beat that ends it, exactly as
    rantai.kumpulkan_jendela does: lab[qrs[1:]]."""
    qrs = np.asarray(core["qrs"])
    return label[qrs[1:]]


def deret_terkoreksi(core, kelas_mentah):
    """The corrected interval series in ms, its class per entry, and the source map.

    The marker vocabulary of stage 7b, restated as code so the walk is auditable:

        RR_MARK_KEEP  0  one corrected entry, the raw value kept, source one raw interval
        RR_MARK_SPLIT 1  two corrected entries, the two exact halves, both from one raw interval
        RR_MARK_DROP  2  no corrected entry at all, the raw interval produced nothing
        RR_MARK_GAP   3  one corrected entry, the gap value kept, source one raw interval

    Returns (deret_ms, kelas, sumber, kelas_mentah) where

        deret_ms    float array, the corrected intervals in milliseconds
        kelas       object array of the class of each corrected entry
        sumber      int array, source raw interval index of each corrected entry
        kelas_mentah the class axis the propagation reads, returned for the caller's checks
    """
    mark_mentah = np.asarray(core["rr_mark_raw"])
    corrected = np.asarray(core["rr_corrected"])
    n = int(corrected.size)
    sumber = np.empty(n, dtype=np.int64)
    k = 0
    for i in range(mark_mentah.size):
        mk = int(mark_mentah[i])
        if mk == R.RR_MARK_DROP:
            continue
        if mk == R.RR_MARK_SPLIT:
            sumber[k] = i
            sumber[k + 1] = i
            k += 2
        else:
            sumber[k] = i
            k += 1
    if k != n:
        raise RuntimeError("the mark walk wrote %d entries for a corrected series of %d" % (k, n))
    deret_ms = corrected.astype(float)
    kelas = kelas_mentah[sumber]
    return deret_ms, kelas, sumber, kelas_mentah


# =============================================================================================
# The window collector, a line for line generalisation of rantai.kumpulkan_jendela.
#
# The frozen function is not modified and is not called with anything but its own arguments.
# This generalisation keeps every rule of the frozen one: window of JENDELA_DENYUT intervals,
# step LANGKAH_DENYUT, kept only when all the class labels of the window are equal and that
# single class is AFIB or N, and only when every interval of the window is inside 200 ms to
# 3000 ms. The features come from rantai.fitur_irama itself, so the arithmetic is the frozen
# arithmetic. The only difference is that the interval series and the class axis are arguments
# instead of being derived from the beat list inside the function.
# =============================================================================================

def kumpulkan(deret_ms, kelas_interval, origin_map=None):
    """Windows of JENDELA_DENYUT intervals with a step of LANGKAH_DENYUT, one class each.

    Returns (fitur, kelas, origin). fitur is (n, 4) float, kelas is (n,) object, origin is
    (n,) int64, the window start index in the series, or its image by origin_map when one is
    given. origin_map is used to move the corrected window start onto the raw interval axis.
    """
    seri = np.asarray(deret_ms, float)
    bl = np.asarray(kelas_interval)
    fitur, kelas, origin = [], [], []
    for i in range(0, seri.size - R.JENDELA_DENYUT, R.LANGKAH_DENYUT):
        seg = seri[i:i + R.JENDELA_DENYUT]
        u = np.unique(bl[i:i + R.JENDELA_DENYUT])
        if u.size != 1 or u[0] not in ("AFIB", "N"):
            continue
        if seg.min() < 200 or seg.max() > 3000:
            continue
        fitur.append(R.fitur_irama(seg))
        kelas.append(u[0])
        origin.append(int(origin_map[i]) if origin_map is not None else i)
    if not fitur:
        return np.zeros((0, 4), float), np.zeros(0, dtype=object), np.zeros(0, dtype=np.int64)
    return (np.array(fitur, float),
            np.array(kelas, dtype=object),
            np.array(origin, dtype=np.int64))


# =============================================================================================
# Matching the two arms on the raw interval axis.
# =============================================================================================

def cocokkan(origin_mentah, kelas_mentah, fitur_mentah, origin_kor, kelas_kor, fitur_kor):
    """Match the two arms by window origin, the raw interval index of the window start.

    Returns a dict with the number of matched origins, how many matched windows have a class
    that differs, how many have a feature vector that differs, the same two counts at a coarse
    magnitude, the per feature mean absolute difference over the matched windows, and the
    windows that exist in only one arm.
    """
    if origin_mentah.size == 0 or origin_kor.size == 0:
        return dict(matched=0, kelas_beda=0, fitur_beda=0, fitur_beda_kasar=0,
                    mad=[0.0, 0.0, 0.0, 0.0], hanya_mentah=int(origin_mentah.size),
                    hanya_kor=int(origin_kor.size))
    pos_kor = {int(o): j for j, o in enumerate(origin_kor)}
    pos_men = {int(o): j for j, o in enumerate(origin_mentah)}
    matched = 0
    kelas_beda = 0
    fitur_beda = 0
    fitur_beda_kasar = 0
    akum = np.zeros(4, float)
    for j, o in enumerate(origin_mentah):
        o = int(o)
        p = pos_kor.get(o)
        if p is None:
            continue
        matched += 1
        if str(kelas_mentah[j]) != str(kelas_kor[p]):
            kelas_beda += 1
        d = np.abs(fitur_mentah[j] - fitur_kor[p])
        akum += d
        if float(d.max()) > 1e-9:
            fitur_beda += 1
        if float(d.max()) > 0.01:
            fitur_beda_kasar += 1
    mad = (akum / matched).tolist() if matched else [0.0, 0.0, 0.0, 0.0]
    hanya_mentah = int(sum(1 for o in origin_mentah if int(o) not in pos_kor))
    hanya_kor = int(sum(1 for o in origin_kor if int(o) not in pos_men))
    return dict(matched=matched, kelas_beda=kelas_beda, fitur_beda=fitur_beda,
                fitur_beda_kasar=fitur_beda_kasar, mad=mad,
                hanya_mentah=hanya_mentah, hanya_kor=hanya_kor)


def cocokkan_ordinal(fitur_m, kelas_m, fitur_k, kelas_k):
    """Row by row alignment of the two tables, INCLUDED ONLY TO SHOW THE TABLES DO NOT LINE UP.

    This is not a match. It pairs the k th accepted window of one arm with the k th accepted
    window of the other arm, which is what a reader would do if the two tables were assumed
    interchangeable. They are not, and the numbers below say so.
    """
    n = int(min(fitur_m.shape[0], fitur_k.shape[0]))
    kelas_beda = 0
    fitur_beda = 0
    for i in range(n):
        if str(kelas_m[i]) != str(kelas_k[i]):
            kelas_beda += 1
        if float(np.abs(fitur_m[i] - fitur_k[i]).max()) > 1e-9:
            fitur_beda += 1
    return n, fitur_beda, kelas_beda


def sensus_hanya(origin_a, kelas_a, origin_b):
    """Class census of the windows of arm A whose origin does not exist in arm B."""
    pos_b = set(int(o) for o in origin_b)
    out = {}
    for j, o in enumerate(origin_a):
        if int(o) in pos_b:
            continue
        k = str(kelas_a[j])
        out[k] = out.get(k, 0) + 1
    return out


# =============================================================================================
# Main
# =============================================================================================

def main():
    t_mulai = time.time()

    print("AFIB-LITE measurement only: the window layer on the corrected RR series instead of "
          "the raw RR series")
    print("=" * 132)
    print("interpreter   :", sys.executable)
    print("data root     :", U.DATA_ROOT)
    print("reference rec : %s, reported as reference only and never used to choose anything"
          % DERIVATION_RECORD)
    print("test records  : %s, pooled as the frozen gates pool them" % " and ".join(TEST_RECORDS))
    print("operating pts : " + " | ".join("%s ratio %.3f entropy %.2f (%s)"
                                          % (n, t1, t2, ket) for n, t1, t2, ket in TITIK))
    print("metric policy : sensitivity, specificity, accuracy, PPV, NPV and miss rate, each with "
          "the window count and the prevalence of its set")
    print("nothing is changed: no threshold is derived, no threshold is edited, no series is "
          "written, no fixture is touched")

    # ------------------------------------------------------------------ stage 1, the fixture
    kepala("stage 1, the frozen fixture, read and never written")
    h = hashlib.sha256()
    with open(FIXTURE, "rb") as fh:
        for potongan in iter(lambda: fh.read(1 << 20), b""):
            h.update(potongan)
    sha = h.hexdigest()
    lapor("fixture sha256 measured", sha)
    lapor("fixture sha256 expected", SHA_FIXTURE)
    d = np.load(FIXTURE)

    # ------------------------------------------------------------------ stage 2, the runs
    kepala("stage 2, one real chain run per recording, both window tables produced")
    hasil = {}
    for nama in ALL_RECORDS:
        r = P.jalankan(nama)                 # frozen S5b runner: frozen adapter plus frozen core
        core = r["core"]
        label = r["label"]

        # ARM RAW, exactly the frozen collector, exactly the pipeline input.
        # ARM RAW: the frozen collector itself, asked for the raw series by name. The chain
        # default is berpenanda now, so this arm must name mentah instead of inheriting it.
        if np.asarray(core["qrs"]).size < 2:
            fitur_mentah, kelas_mentah = np.zeros((0, 4), dtype=float), np.zeros(0, dtype=object)
        else:
            fitur_mentah, kelas_mentah = R.kumpulkan_jendela(
                core["qrs"], label, sumber=R.SUMBER_MENTAH)
        kelas_int_mentah = kelas_per_interval_mentah(core, label)
        deret_mentah = np.diff(np.asarray(core["qrs"])) / R.FS_HZ * 1000.0
        # the generalised collector on the raw arm, only to obtain the window origins and to
        # prove it agrees with the frozen collector.
        f_m2, k_m2, origin_mentah = kumpulkan(deret_mentah, kelas_int_mentah)

        # ARM CORRECTED, stage 7b series with its marker semantics.
        deret_kor, kelas_int_kor, sumber, _ = deret_terkoreksi(core, kelas_int_mentah)
        fitur_kor, kelas_kor, origin_kor = kumpulkan(deret_kor, kelas_int_kor, origin_map=sumber)

        hasil[nama] = dict(
            nama=nama, run=r, core=core, detik=r["detik"],
            fitur_mentah=fitur_mentah, kelas_mentah=kelas_mentah, origin_mentah=origin_mentah,
            fitur_kor=fitur_kor, kelas_kor=kelas_kor, origin_kor=origin_kor,
            f_m2=f_m2, k_m2=k_m2, sumber=sumber,
            deret_kor=deret_kor,
        )
        af = kelas_mentah == "AFIB"
        afk = kelas_kor == "AFIB"
        print("     %-6s %6d samples, %5d beats, raw intervals %5d, corrected entries %5d, "
              "chain %.1f s" % (nama, r["sampel"], int(core["qrs"].size), core["rr"].size,
                                core["rr_corrected"].size, r["detik"]))
        print("            raw windows %4d (AFIB %3d), corrected windows %4d (AFIB %3d), "
              "first corrected entry drawn from raw interval %s"
              % (kelas_mentah.size, int(af.sum()), kelas_kor.size, int(afk.sum()),
                 int(hasil[nama]["sumber"][0]) if hasil[nama]["sumber"].size else "-"))

    own = hasil[DERIVATION_RECORD]

    # ------------------------------------------------------------------ stage 3, self checks
    kepala("stage 3, self checks of the measurement harness, not a verdict on the corrected arm")
    periksa("fixture sha256 matches the frozen oracle",
            sha == SHA_FIXTURE, "measured %s" % sha[:16])
    periksa("raw arm reproduces the frozen 04015 feature table",
            np.array_equal(own["fitur_mentah"], d["jendela_fitur"]),
            "shape %s, zero difference" % (own["fitur_mentah"].shape,))
    periksa("raw arm reproduces the frozen 04015 class table",
            np.array_equal(own["kelas_mentah"], d["jendela_kelas_benar"]),
            "shape %s, zero difference" % (own["kelas_mentah"].shape,))
    periksa("raw arm window tables match the frozen collector element for element",
            all(np.array_equal(hasil[n]["fitur_mentah"], hasil[n]["f_m2"])
                and np.array_equal(hasil[n]["kelas_mentah"], hasil[n]["k_m2"])
                for n in ALL_RECORDS),
            "the generalised collector agrees on all three records")
    pooled_mentah_win = int(sum(hasil[n]["kelas_mentah"].size for n in TEST_RECORDS))
    pooled_mentah_afib = int(sum((hasil[n]["kelas_mentah"] == "AFIB").sum() for n in TEST_RECORDS))
    periksa("raw pooled hold-out count is the frozen 1562 windows and 677 AFIB",
            pooled_mentah_win == S6_WINDOWS and pooled_mentah_afib == S6_AFIB,
            "measured %d windows and %d AFIB" % (pooled_mentah_win, pooled_mentah_afib))
    periksa("raw series is bit for bit round(diff(qrs) in ms)",
            all(np.array_equal(np.asarray(hasil[n]["core"]["rr"]),
                               np.round(np.diff(np.asarray(hasil[n]["core"]["qrs"]))
                                        / R.FS_HZ * 1000.0).astype(np.int64))
                for n in ALL_RECORDS),
            "stage 7 rr equals the raw interval series on all three records")
    periksa("the mark walk reproduces the corrected series length on every record",
            all(hasil[n]["sumber"].size == hasil[n]["core"]["rr_corrected"].size
                for n in ALL_RECORDS),
            "corrected entries 04015 %d, 04043 %d, 04126 %d"
            % tuple(hasil[n]["core"]["rr_corrected"].size for n in ALL_RECORDS))

    # ------------------------------------------------------------------ stage 4, series census
    kepala("stage 4, the two interval series, side by side, per record")
    print("     %-6s %10s %14s %38s %30s" % ("record", "raw entries", "corrected ent.",
                                              "mark census raw 0/1/2/3",
                                              "mark census corrected 0/1/2/3"))
    for nama in ALL_RECORDS:
        core = hasil[nama]["core"]
        mm = np.asarray(core["rr_mark_raw"])
        mc = np.asarray(core["rr_mark_corrected"])
        cen_m = "/".join(str(int((mm == k).sum())) for k in (0, 1, 2, 3))
        cen_c = "/".join(str(int((mc == k).sum())) for k in (0, 1, 2, 3))
        print("     %-6s %10d %14d %38s %30s"
              % (nama, core["rr"].size, core["rr_corrected"].size, cen_m, cen_c))
        lapor("  longest interval raw / corrected",
              "%d ms / %d ms" % (int(core["rr"].max()), int(core["rr_corrected"].max())))
        lapor("  implied mean rate raw / corrected",
              "%.2f / %.2f beats per minute"
              % (60000.0 / float(np.mean(core["rr"])),
                 60000.0 / float(np.mean(core["rr_corrected"]))))

    # ------------------------------------------------------------------ stage 5, windows
    kepala("stage 5, the window tables of the two arms")
    print("     %-6s %12s %12s %12s %12s" % ("record", "raw win", "raw AFIB",
                                              "corr win", "corr AFIB"))
    for nama in ALL_RECORDS:
        a = hasil[nama]
        print("     %-6s %12d %12d %12d %12d"
              % (nama, a["kelas_mentah"].size, int((a["kelas_mentah"] == "AFIB").sum()),
                 a["kelas_kor"].size, int((a["kelas_kor"] == "AFIB").sum())))
    pooled_kor_win = int(sum(hasil[n]["kelas_kor"].size for n in TEST_RECORDS))
    pooled_kor_afib = int(sum((hasil[n]["kelas_kor"] == "AFIB").sum() for n in TEST_RECORDS))
    print("     %-6s %12d %12d %12d %12d"
          % ("pooled", pooled_mentah_win, pooled_mentah_afib, pooled_kor_win, pooled_kor_afib))
    lapor("windows added by the corrected arm, pooled test",
          "%d (%+0.1f percent of the raw hold-out set)"
          % (pooled_kor_win - pooled_mentah_win,
             100.0 * (pooled_kor_win - pooled_mentah_win) / max(1, pooled_mentah_win)))

    # ------------------------------------------------------------------ stage 6, matching
    kepala("stage 6, the two arms matched on the raw interval axis, window by window")
    print("     %-6s %8s %10s %10s %10s %10s %10s"
          % ("record", "matched", "feat diff", "class diff", "coarse", "raw only", "corr only"))
    cocok = {}
    for nama in ALL_RECORDS:
        a = hasil[nama]
        c = cocokkan(a["origin_mentah"], a["kelas_mentah"], a["fitur_mentah"],
                     a["origin_kor"], a["kelas_kor"], a["fitur_kor"])
        cocok[nama] = c
        print("     %-6s %8d %10d %10d %10d %10d %10d"
              % (nama, c["matched"], c["fitur_beda"], c["kelas_beda"],
                 c["fitur_beda_kasar"], c["hanya_mentah"], c["hanya_kor"]))
    mt = dict(matched=0, fitur_beda=0, kelas_beda=0, fitur_beda_kasar=0,
              hanya_mentah=0, hanya_kor=0, mad=[0.0, 0.0, 0.0, 0.0])
    for nama in TEST_RECORDS:
        for k in mt:
            if k == "mad":
                mt[k] = [x + y for x, y in zip(mt[k], cocok[nama][k])]
            else:
                mt[k] += cocok[nama][k]
    print("     %-6s %8d %10d %10d %10d %10d %10d"
          % ("pooled", mt["matched"], mt["fitur_beda"], mt["kelas_beda"],
             mt["fitur_beda_kasar"], mt["hanya_mentah"], mt["hanya_kor"]))
    print("     feature columns are RMSSD, RMSSD/mean, pNN50, entropy/4; coarse means any "
          "column moved by more than 0.010")
    print("     matched windows and per column mean absolute feature difference, raw to "
          "corrected:")
    for nama in ALL_RECORDS + ("pooled",):
        c = cocok[nama] if nama != "pooled" else mt
        print("       %-6s matched %4d, mean |delta| = %.4f  %.4f  %.4f  %.4f"
              % (nama, c["matched"], c["mad"][0], c["mad"][1], c["mad"][2], c["mad"][3]))

    print()
    print("     WHY THE MATCHED CLASS DIFFERENCE IS ZERO, AND WHY THAT IS NOT THE WHOLE ANSWER.")
    print("       The class of a window, in both arms, is the rhythm annotation of the beat that")
    print("       ends its first interval. Under the origin match the two windows of a pair share")
    print("       that first interval, so their class is the same by construction, and a nonzero")
    print("       matched class difference is impossible. The zero above is structural and must")
    print("       not be read as 'the classes did not move'. The classes DO move, through the")
    print("       window POPULATION: a corrected window can be accepted where the raw one was")
    print("       rejected, and the other way round, and the AFIB share of the accepted set")
    print("       changes with it. Stage 5 gives that movement, and the census below gives the")
    print("       class of the windows that exist in only one arm.")

    print()
    print("     class census of the windows that exist in only one arm")
    print("       %-6s %-28s %-28s" % ("record", "raw only, N/AFIB", "corrected only, N/AFIB"))
    for nama in ALL_RECORDS:
        a = hasil[nama]
        hm = sensus_hanya(a["origin_mentah"], a["kelas_mentah"], a["origin_kor"])
        hk = sensus_hanya(a["origin_kor"], a["kelas_kor"], a["origin_mentah"])
        print("       %-6s %-28s %-28s"
              % (nama, "N %d, AFIB %d" % (hm.get("N", 0), hm.get("AFIB", 0)),
                 "N %d, AFIB %d" % (hk.get("N", 0), hk.get("AFIB", 0))))
    hm_pool = {"N": 0, "AFIB": 0}
    hk_pool = {"N": 0, "AFIB": 0}
    for nama in TEST_RECORDS:
        a = hasil[nama]
        hm = sensus_hanya(a["origin_mentah"], a["kelas_mentah"], a["origin_kor"])
        hk = sensus_hanya(a["origin_kor"], a["kelas_kor"], a["origin_mentah"])
        for k in ("N", "AFIB"):
            hm_pool[k] += hm.get(k, 0)
            hk_pool[k] += hk.get(k, 0)
    print("       %-6s %-28s %-28s"
          % ("pooled", "N %d, AFIB %d" % (hm_pool["N"], hm_pool["AFIB"]),
             "N %d, AFIB %d" % (hk_pool["N"], hk_pool["AFIB"])))

    print()
    print("     row by row alignment of the two tables, NOT a match, only to show the tables do")
    print("     not line up: the k th accepted window of one arm against the k th of the other")
    print("       %-6s %8s %10s %10s" % ("record", "rows", "feat diff", "class diff"))
    for nama in ALL_RECORDS:
        a = hasil[nama]
        n, fd, kd = cocokkan_ordinal(a["fitur_mentah"], a["kelas_mentah"],
                                     a["fitur_kor"], a["kelas_kor"])
        print("       %-6s %8d %10d %10d" % (nama, n, fd, kd))
    fm = np.vstack([hasil[n]["fitur_mentah"] for n in TEST_RECORDS])
    km = np.concatenate([hasil[n]["kelas_mentah"] for n in TEST_RECORDS])
    fk = np.vstack([hasil[n]["fitur_kor"] for n in TEST_RECORDS])
    kk = np.concatenate([hasil[n]["kelas_kor"] for n in TEST_RECORDS])
    n, fd, kd = cocokkan_ordinal(fm, km, fk, kk)
    print("       %-6s %8d %10d %10d" % ("pooled", n, fd, kd))
    lapor("note", "the row by row class difference is large only because the two tables have "
                  "different lengths and different starts; it is not a class change of a window")

    # ------------------------------------------------------------------ stage 7, metrics
    kepala("stage 7, the locked and spare operating points on both arms")
    print("     K  = ratio 0.165, entropy 0.63, the operating point locked by Aviv")
    print("     P2 = ratio 0.165, entropy 0.67, spare row")
    print("     P5 = ratio 0.210, entropy 0.70, old locked pair, spare row")

    tabel = {
        "04015": (hasil["04015"]["fitur_mentah"], hasil["04015"]["kelas_mentah"],
                  hasil["04015"]["fitur_kor"], hasil["04015"]["kelas_kor"]),
        "04043": (hasil["04043"]["fitur_mentah"], hasil["04043"]["kelas_mentah"],
                  hasil["04043"]["fitur_kor"], hasil["04043"]["kelas_kor"]),
        "04126": (hasil["04126"]["fitur_mentah"], hasil["04126"]["kelas_mentah"],
                  hasil["04126"]["fitur_kor"], hasil["04126"]["kelas_kor"]),
        "pooled": (np.vstack([hasil[n]["fitur_mentah"] for n in TEST_RECORDS]),
                   np.concatenate([hasil[n]["kelas_mentah"] for n in TEST_RECORDS]),
                   np.vstack([hasil[n]["fitur_kor"] for n in TEST_RECORDS]),
                   np.concatenate([hasil[n]["kelas_kor"] for n in TEST_RECORDS])),
    }

    for nama_titik, t1, t2, ket in TITIK:
        kepala("operating point %s, ratio %.3f, entropy %.2f (%s)"
               % (nama_titik, t1, t2, ket))
        print("     %-7s %-10s %5s %5s %5s %5s %5s %5s %8s %8s %8s %8s %8s %8s %8s"
              % ("set", "arm", "win", "afib", "tp", "fp", "fn", "tn",
                 "Se", "Sp", "Acc", "PPV", "NPV", "miss", "fire"))
        for nama_set in ("04015", "04043", "04126", "pooled"):
            fm, km, fk, kk = tabel[nama_set]
            for arm, fitur, kelas in (("raw", fm, km), ("corrected", fk, kk)):
                m = K.metrik_lengkap(fitur, kelas, t1, t2)
                print("     %-7s %-10s %5d %5d %5d %5d %5d %5d %8s %8s %8s %8s %8s %8s %8s"
                      % (nama_set, arm, m["windows"], m["afib"], m["tp"], m["fp"],
                         m["fn"], m["tn"], sel(m["sensitivity"]), sel(m["specificity"]),
                         sel(m["accuracy"]), sel(m["ppv"]), sel(m["npv"]), sel(m["miss"]),
                         sel(m["firing"])))
            # the movement of the headline numbers, corrected minus raw, in the same block
            mm_raw = K.metrik_lengkap(fm, km, t1, t2)
            mm_kor = K.metrik_lengkap(fk, kk, t1, t2)
            deltas = []
            for kunci, tanda in (("sensitivity", "%+.4f"), ("specificity", "%+.4f"),
                                 ("accuracy", "%+.4f"), ("miss", "%+.4f")):
                a, b = mm_raw[kunci], mm_kor[kunci]
                deltas.append("d_%s " % kunci[:3] + (tanda % (b - a) if a is not None and b is not None
                                                     else "n/a"))
            print("     %-7s %-10s %s" % (nama_set, "delta", "  ".join(deltas)))

    # ------------------------------------------------------------------ truth about misses
    kepala("stage 7b, the miss rates of the locked point K, both arms, so the loss is explicit")
    t1, t2 = 0.165, 0.63
    print("     %-7s %10s %10s %10s %10s %10s %10s"
          % ("set", "raw Se", "corr Se", "raw miss", "corr miss", "raw FN", "corr FN"))
    for nama_set in ("04015", "04043", "04126", "pooled"):
        fm, km, fk, kk = tabel[nama_set]
        a = K.metrik_lengkap(fm, km, t1, t2)
        b = K.metrik_lengkap(fk, kk, t1, t2)
        print("     %-7s %10s %10s %10s %10s %10d %10d"
              % (nama_set, sel(a["sensitivity"], 7, 2), sel(b["sensitivity"], 7, 2),
                 sel(a["miss"], 7, 2), sel(b["miss"], 7, 2), a["fn"], b["fn"]))

    laporan_tidak_diukur()

    lulus = all(v for _n, v in HASIL)
    gagal = [n for n, v in HASIL if not v]
    kepala("summary")
    print("self checks %d of %d pass" % (len(HASIL) - len(gagal), len(HASIL)))
    if gagal:
        print("failing self checks: %s" % ", ".join(gagal))
    print("wall clock %.1f s" % (time.time() - t_mulai))
    print("measurement verdict: %s" % ("self checks PASS" if lulus else "self checks FAIL"))
    return 0 if lulus else 1


def laporan_tidak_diukur():
    """The honest list of what this measurement does not cover.

    Written as a report and not as a claim of completeness, because a reader of stage 7 above
    should know exactly where the numbers stop.
    """
    kepala("what this measurement does NOT measure, stated plainly")
    print("     1. It does not measure a physical window. The raw window is 32 raw intervals and "
          "the corrected window is 32 corrected entries, and because a split turns one interval "
          "into two, the corrected window of 32 entries spans fewer raw intervals, about 28 of "
          "them on 04015. The two arms are the same rule over series of different length, not "
          "the same span of time, and no attempt is made to equalise the spans.")
    print("     2. It does not match a window to itself in time. Matching is by the raw interval "
          "index of the window start only. A matched pair may cover different stretches, and a "
          "window whose origin exists in one arm only is counted as arm only, not as a miss.")
    print("     3. It does not re-derive any threshold and does not search the grid. The three "
          "pairs are used exactly as locked or proposed. A better or worse accuracy of the "
          "corrected arm is reported as it comes out, with no attempt to find a pair that "
          "would look better.")
    print("     4. It does not re-run the seven frozen gates of the project, and it does not "
          "score the corrected arm as a gate. Nothing in the repository was changed, so the "
          "frozen gates cannot move; that is asserted from the untouched files and not "
          "re-executed here.")
    print("     5. It does not test the marker policy that is the most defended alternative: "
          "reading the split mark and DISCARDING the two halves instead of keeping them. Only "
          "the literal S7 reading, the two exact halves kept, is measured. The alternative is "
          "available from the same marks and is left unmeasured.")
    print("     6. It does not measure the beat layer. qrs is untouched by stage 7b, so beat "
          "agreement, beat counts and anything computed from the real beats is unchanged by "
          "construction and is not measured here.")
    print("     7. It does not measure a per beat rate or a per beat rate variability against a "
          "reference, because the corrected series is not a beat series and has no reference "
          "annotation. Only the window features and the window decision are measured.")
    print("     8. It does not measure the effect on the other records in the data set "
          "(nsrdb/16265, mitdb/100) or on any record outside the frozen 30 minute window. Only "
          "the three AFDB records the gates use are measured.")
    print("     9. It does not choose. 04015 is printed as a reference only, because the locked "
          "point was derived on it; the test records 04043 and 04126 remain the hold-out, and "
          "no conclusion is drawn from a single number.")
    print("    10. It cannot give one single number for 'windows whose class changed'. Under the "
          "origin match that number is structurally zero, and it is explained where it is "
          "printed. The row by row number is large but it is not a class change of any window, "
          "only a sign that the two tables do not line up. Both are printed and neither is "
          "called the answer, because a class change of one window has no meaning without "
          "naming the correspondence that says which window of one arm is which of the other.")


if __name__ == "__main__":
    sys.exit(main())
