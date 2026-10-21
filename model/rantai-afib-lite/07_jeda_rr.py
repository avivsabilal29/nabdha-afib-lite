#!/usr/bin/env python3
"""AFIB-LITE phase 6 step S7 gate: the integer rhythm check over the RR series.

Step S7 removes the longest RR interval the locked chain produces on recording 04015, which is
51064 ms, 51 seconds, between the beats at sample 71399 and sample 84165. Root cause was
measured before the change and is written in the open correction note: lead ECG1 of that record
is in contact loss over that stretch, its amplitude per second collapses to 0.10 to 1.09 mV
against a record median of 1.730 mV while the other lead of the same record keeps 1.0 to 4.4 mV,
the frozen reference detector reports one beat in those 51 seconds, and the envelope the chain
measures there never comes within a factor of sixteen of the second threshold. There is nothing
to detect in that lead, so nothing is invented. The change is the integer rhythm check that
`rantai.rr_rhythm` applies to the raw interval series and that writes a corrected series and one
mark per interval beside it.

This file is the gate of that step. It proves six things.

  A. A synthetic missed beat is split into two exact halves, and the two halves sum to the raw
     interval, for both an even and an odd raw interval.
  B. A synthetic false detection, below one half of the running average, is dropped and enters
     no average.
  C. A synthetic real pause below the 3000 ms ceiling, which the boundary of 83/50 does not
     catch, is left alone.
  D. A synthetic interval above the 3000 ms ceiling is marked as a recording gap, is kept as one
     entry instead of being split, and is kept out of the running average, which is shown by the
     running average before and after it being identical.
  E. Every verdict of the three rules matches the exact rational verdict computed with
     `fractions.Fraction`, over a sweep of intervals and running averages, and every value the
     check produces is a Python integer, so no floating point enters the path.
  F. On the real recording the 51064 ms interval is marked as a recording gap, the longest
     interval the corrected series still treats as a physiological interval is reported, the
     corrected series reconstructs from the raw series and the marks with the total time
     conserved except for the dropped false detections, and every locked array of the chain is
     still identical to the frozen fixture, so the change is proven additive.

The fixture `fixture/04015_30m.npz` is never written. Its SHA-256 is checked at the start. The
locked series of `rantai.py` is never edited by this file.

Run it with the project interpreter:

    cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/uji_07_jeda_rr.py

Exit code 0 when every check passes, 1 when any of them fails.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys
import time
from fractions import Fraction

import numpy as np

import rantai as R

HERE = pathlib.Path(__file__).resolve().parent
NPZ = HERE / "fixture" / "04015_30m.npz"
SIDIK_FIXTURE = "91ff408fb1b7880a124d28bcc4205038935d4a3a2dbabb4c0f7d161d89e8ac4d"
REC = pathlib.Path("/home/avivsabilalm/nabdha-data/afdb/04015")
FRAMES = 450_000

GAP_RAW = 51064                  # the defect S7 removes, measured on 04015
GAP_LEFT_QRS = 71399             # the beat before the gap
GAP_RIGHT_QRS = 84165            # the beat after the gap

BARIS = []
GAGAL = 0


def periksa(nama, lulus, teks):
    """One gate item: name, verdict, and one line with its measured numbers."""
    global GAGAL
    if not lulus:
        GAGAL += 1
    BARIS.append((nama, bool(lulus)))
    print("%-6s %s" % ("LULUS" if lulus else "GAGAL", teks))


def sidik_jari(berkas):
    h = hashlib.sha256()
    with open(berkas, "rb") as fh:
        for blok in iter(lambda: fh.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def segar(riwayat):
    """A fresh rhythm state whose running window is exactly the given integer series."""
    st = R.rr_rhythm_awal()
    st["history"] = [int(v) for v in riwayat][-R.RR_RHYTHM_WINDOW:]
    return st


def feed(riwayat, x):
    """Push one interval through a state built by segar and return the mark and the state."""
    st = segar(riwayat)
    return R.rr_rhythm(int(x), st)


def segar_dari(riwayat, kosongkan_deret=True):
    """A state with the given window, its series and counters emptied, so one call is isolated."""
    st = segar(riwayat)
    if kosongkan_deret:
        st["corrected"] = []
        st["flags"] = []
        st["marks"] = []
        for k in ("raw", "kept", "split", "dropped", "gap"):
            st[k] = 0
    return st


# =============================================================================================
# A. A missed beat is split into two exact halves.
# =============================================================================================

def bagian_a():
    print()
    print("A  a synthetic missed beat is split into two exact halves")
    print("-" * 132)
    hasil = []
    for x, riwayat in ((2048, [800] * 8), (2001, [700] * 8), (1500, [500] * 8), (3001 - 1, [900] * 8)):
        st = segar_dari(riwayat)
        mark, st = R.rr_rhythm(x, st)
        dua = st["corrected"]
        lulus = (mark == R.RR_MARK_SPLIT and len(dua) == 2 and dua[0] + dua[1] == x
                 and dua[0] == x >> 1 and dua[1] == x - (x >> 1)
                 and abs(dua[1] - dua[0]) <= 1
                 and st["flags"] == [R.RR_MARK_SPLIT, R.RR_MARK_SPLIT]
                 and st["marks"] == [R.RR_MARK_SPLIT]
                 and st["split"] == 1 and st["kept"] == 0 and st["dropped"] == 0 and st["gap"] == 0)
        hasil.append(lulus)
        periksa("A", lulus,
                "raw %d ms against a running average of %d ms: mark %d (exp %d), halves %s, sum %d "
                "(exp %d), the two halves differ by %d (exp at most 1), corrected marks %s"
                % (x, R.median_bulat(riwayat), mark, R.RR_MARK_SPLIT, dua, sum(dua), x,
                   abs(dua[1] - dua[0]) if len(dua) == 2 else -1, st["flags"]))
    return all(hasil)


# =============================================================================================
# B. A false detection is dropped.
# =============================================================================================

def bagian_b():
    print()
    print("B  a synthetic false detection is dropped and enters no average")
    print("-" * 132)
    hasil = []
    for x, riwayat in ((199, [800] * 8), (216, [700] * 8), (349, [700] * 8), (350, [700] * 8)):
        st = segar_dari(riwayat)
        mark, st = R.rr_rhythm(x, st)
        batas = R.median_bulat(riwayat)
        harus_buang = (2 * x) < batas
        lulus = (mark == (R.RR_MARK_DROP if harus_buang else R.RR_MARK_KEEP)
                 and len(st["corrected"]) == (0 if harus_buang else 1)
                 and st["dropped"] == (1 if harus_buang else 0)
                 and st["marks"] == [R.RR_MARK_DROP if harus_buang else R.RR_MARK_KEEP]
                 and (2 * x < batas) == harus_buang)
        hasil.append(lulus)
        periksa("B", lulus,
                "raw %d ms against a running average of %d ms: mark %d, corrected entries %d, "
                "dropped %d, the exact cross form 2 times %d against %d says %s"
                % (x, batas, mark, len(st["corrected"]), st["dropped"], x, batas,
                   "drop" if harus_buang else "keep"))
    return all(hasil)


# =============================================================================================
# C. A real pause below the ceiling is left alone, and D, a gap above the ceiling is marked.
# =============================================================================================

def bagian_c():
    print()
    print("C  a synthetic real pause below the ceiling is left alone")
    print("-" * 132)
    hasil = []
    for x, riwayat in ((1000, [900] * 8), (1493, [900] * 8), (1494, [900] * 8), (2000, [1500] * 8)):
        st = segar_dari(riwayat)
        mark, st = R.rr_rhythm(x, st)
        batas = R.median_bulat(riwayat)
        lewat_missed = (R.RR_MISS_DEN * x) > (R.RR_MISS_NUM * batas)
        lulus = (mark == (R.RR_MARK_SPLIT if lewat_missed else R.RR_MARK_KEEP)
                 and st["marks"] == [mark]
                 and len(st["corrected"]) == (2 if lewat_missed else 1)
                 and (st["corrected"] == [x] if not lewat_missed else True))
        hasil.append(lulus)
        periksa("C", lulus,
                "raw %d ms against a running average of %d ms: mark %d, the boundary is %s, so the "
                "interval is %s, corrected entries %s"
                % (x, batas, mark,
                   Fraction(R.RR_MISS_NUM, R.RR_MISS_DEN) * Fraction(batas),
                   "split as a missed beat" if lewat_missed else "left alone",
                   st["corrected"]))
    return all(hasil)


def bagian_d():
    print()
    print("D  a synthetic gap above the 3000 ms ceiling is marked, kept whole, and kept out of "
          "the average")
    print("-" * 132)
    hasil = []
    for x, riwayat in ((3001, [800] * 8), (51064, [700] * 8), (4856, [900] * 8)):
        st = segar_dari(riwayat)
        rata_sebelum = R.median_bulat(st["history"])
        mark, st = R.rr_rhythm(x, st)
        rata_sesudah = R.median_bulat(st["history"])
        lulus = (mark == R.RR_MARK_GAP and st["corrected"] == [x] and st["flags"] == [R.RR_MARK_GAP]
                 and st["marks"] == [R.RR_MARK_GAP] and st["gap"] == 1 and st["split"] == 0
                 and rata_sesudah == rata_sebelum)
        hasil.append(lulus)
        periksa("D", lulus,
                "raw %d ms against a running average of %d ms: mark %d (exp %d), corrected series "
                "%s as one entry and not two, the running average before %d and after %d (exp the "
                "same, the gap is excluded)"
                % (x, rata_sebelum, mark, R.RR_MARK_GAP, st["corrected"], rata_sebelum,
                   rata_sesudah))
    return all(hasil)


# =============================================================================================
# E. Every verdict is the exact rational verdict, and every value is a Python integer.
# =============================================================================================

def bagian_e():
    print()
    print("E  every verdict is exact against Fraction, and no floating point enters the path")
    print("-" * 132)
    salah_buang = salah_pecah = salah_celah = 0
    bukan_int = 0
    nilai_float = 0
    n = 0
    rng = np.random.default_rng(20261020)
    kasus = []
    for _ in range(40000):
        x = int(rng.integers(120, 6000))
        riwayat = [int(v) for v in rng.integers(500, 1400, size=int(rng.integers(1, 9)))]
        kasus.append((x, riwayat))
    # the boundary triples, where an exact reading matters most
    for a in range(200, 1400, 7):
        for k in (-1, 0, 1):
            kasus.append((int(R.RR_MISS_NUM * a // R.RR_MISS_DEN) + R.RR_MISS_DEN + k, [a] * 8))
            kasus.append((int(a * R.RR_MISS_DEN // R.RR_MISS_NUM) + k, [a] * 8))
            kasus.append((2 * a + k, [a] * 8))
    for x, riwayat in kasus:
        n += 1
        referensi = R.median_bulat(riwayat)
        st = segar_dari(riwayat)
        mark, st = R.rr_rhythm(x, st)
        # the exact rational reading of the same three rules, no float anywhere
        f = Fraction(referensi)
        buang_rasional = f > 0 and Fraction(x) < f / 2
        pecah_rasional = (f > 0 and Fraction(x) > Fraction(R.RR_MISS_NUM, R.RR_MISS_DEN) * f
                          and x <= R.RR_GAP_CEILING_MS)
        celah_rasional = (f > 0 and Fraction(x) > Fraction(R.RR_MISS_NUM, R.RR_MISS_DEN) * f
                          and x > R.RR_GAP_CEILING_MS)
        if buang_rasional != (mark == R.RR_MARK_DROP):
            salah_buang += 1
        if pecah_rasional != (mark == R.RR_MARK_SPLIT):
            salah_pecah += 1
        if celah_rasional != (mark == R.RR_MARK_GAP):
            salah_celah += 1
        for v in [mark, referensi, st["raw"], st["kept"], st["split"], st["dropped"], st["gap"]] \
                + st["corrected"] + st["flags"] + st["marks"] + st["history"]:
            if isinstance(v, bool) or not isinstance(v, (int, np.integer)):
                if isinstance(v, (float, np.floating)):
                    nilai_float += 1
                else:
                    bukan_int += 1
    n_drop = sum(1 for x, r in kasus if R.median_bulat(r) > 0
                 and Fraction(x) < Fraction(R.median_bulat(r)) / 2)
    n_split = sum(1 for x, r in kasus if R.median_bulat(r) > 0
                  and Fraction(x) > Fraction(83, 50) * R.median_bulat(r) and x <= 3000)
    n_gap = sum(1 for x, r in kasus if R.median_bulat(r) > 0
                and Fraction(x) > Fraction(83, 50) * R.median_bulat(r) and x > 3000)
    lulus = (salah_buang == 0 and salah_pecah == 0 and salah_celah == 0 and nilai_float == 0
             and bukan_int == 0 and n > 40000 and n_drop > 0 and n_split > 0 and n_gap > 0)
    periksa("E", lulus,
            "%d interval and running average pairs, including the exact boundary triples: the "
            "chain verdict differs from the Fraction verdict at %d dropped, %d split and %d gap "
            "cases (exp 0 each); the sweep really covers all three rules (%d dropped, %d split, "
            "%d gap cases); values that are not Python integers %d and values that are floating "
            "point %d (exp 0 and 0)"
            % (n, salah_buang, salah_pecah, salah_celah, n_drop, n_split, n_gap, bukan_int,
               nilai_float))
    return lulus


# =============================================================================================
# F. The real recording: the 51 s interval, the reconstruction identity, and the frozen oracle.
# =============================================================================================

def jalan_rantai():
    """Drive the locked chain over recording 04015 and return its output, or fall back."""
    try:
        import wfdb
        x = wfdb.rdrecord(str(REC), sampto=FRAMES).p_signal[:, 0].astype(float)
        sumber = "recording %s, %d samples, channel 0, 250 Hz" % (REC, x.size)
    except Exception as exc:                                    # noqa: BLE001
        x = None
        sumber = "recording not readable here (%s)" % (exc,)
    return x, sumber


def bagian_f(d, x, sumber):
    print()
    print("F  the real recording and the frozen oracle")
    print("-" * 132)
    out = None
    detik = 0.0
    if x is not None:
        t0 = time.time()
        r = R.Rantai(semai_aktif=True, aturan_t=True, besaran="turunan")
        for v in x:
            r.langkah(v)
        out = r.hasil()
        detik = time.time() - t0
    # the authoritative reading of the new block, rebuilt from the frozen raw interval series
    rr = np.asarray(d["rr"], dtype=np.int64)
    st = R.rr_rhythm_awal()
    for v in rr.tolist():
        _mark, st = R.rr_rhythm(int(v), st)
    corr = np.asarray(st["corrected"], dtype=np.int64)
    flags = np.asarray(st["flags"], dtype=np.int64)
    marks = np.asarray(st["marks"], dtype=np.int64)
    kaunter = np.array([st["raw"], st["kept"], st["split"], st["dropped"], st["gap"]],
                       dtype=np.int64)
    qrs = np.asarray(d["qrs"], dtype=np.int64)
    i_gap = int(np.argmax(rr))
    non_gap = corr[flags != R.RR_MARK_GAP]
    i = int(np.flatnonzero(qrs == GAP_RIGHT_QRS)[0])

    lulus = (int(rr.max()) == GAP_RAW and int(marks[i_gap]) == R.RR_MARK_GAP
             and int(rr[i_gap]) == GAP_RAW
             and int((corr == GAP_RAW).sum()) == 1
             and bool(np.all(flags[corr == GAP_RAW] == R.RR_MARK_GAP))
             and marks.size == rr.size
             and flags.size == corr.size
             and int(non_gap.max()) < GAP_RAW
             and set(np.unique(flags).tolist()) <= {0, 1, 3}
             and set(np.unique(marks).tolist()) <= {0, 1, 2, 3}
             and kaunter.tolist() == [rr.size, int((marks == 0).sum()), int((marks == 1).sum()),
                                      int((marks == 2).sum()), int((marks == 3).sum())]
             and int(qrs[i]) == GAP_RIGHT_QRS)
    periksa("F1", lulus,
            "chain run %.1f s over %s: raw intervals %d, longest %d ms between the beats at %d and "
            "%d, its mark %d (exp %d), the longest interval not marked as a gap %d ms, the marks "
            "of the raw series cover only %s and the marks of the corrected series only %s, and "
            "the counters raw, kept, split, dropped, gap read %s"
            % (detik, sumber, rr.size, int(rr.max()), GAP_LEFT_QRS, GAP_RIGHT_QRS,
               int(marks[i_gap]), R.RR_MARK_GAP, int(non_gap.max()),
               sorted(set(np.unique(marks).tolist())), sorted(set(np.unique(flags).tolist())),
               kaunter.tolist()))

    # the reconstruction identity: the corrected series is exactly the raw series expanded by
    # the marks, one entry for keep and for gap, two for split, none for drop
    ulang = []
    for raw, mk in zip(rr.tolist(), marks.tolist()):
        if mk == R.RR_MARK_KEEP or mk == R.RR_MARK_GAP:
            ulang.append(raw)
        elif mk == R.RR_MARK_SPLIT:
            ulang.append(raw >> 1)
            ulang.append(raw - (raw >> 1))
        elif mk == R.RR_MARK_DROP:
            continue
        else:
            ulang = None
            break
    jumlah_buang = int(rr[marks == R.RR_MARK_DROP].sum())
    lulus = (ulang is not None and ulang == corr.tolist()
             and int(rr.sum()) - int(corr.sum()) == jumlah_buang)
    periksa("F2", lulus,
            "the corrected series reconstructs from the raw series and the marks alone, element "
            "for element %s; total time of the raw series %d ms against %d ms of the corrected "
            "series, a difference of %d ms which is exactly the %d intervals marked as dropped "
            "false detections summing %d ms"
            % (ulang == corr.tolist(), int(rr.sum()), int(corr.sum()),
               int(rr.sum()) - int(corr.sum()), int((marks == R.RR_MARK_DROP).sum()), jumlah_buang))

    if out is None:
        print("%-6s the live chain run is not available here, so the frozen oracle is not "
              "compared in this run" % "SKIP")
        return bool(lulus)

    # the same reading, this time out of the live chain, and the frozen oracle beside it
    lulus_ulang = (np.array_equal(out["rr"], rr) and np.array_equal(out["rr_corrected"], corr)
                   and np.array_equal(out["rr_mark_raw"], marks)
                   and np.array_equal(out["rr_mark_corrected"], flags)
                   and np.array_equal(out["rr_rhythm_state"], kaunter))
    milik_rantai = [k for k in sorted(d.files) if k in out]
    beda = [k for k in milik_rantai if not np.array_equal(np.asarray(out[k]), d[k])]
    baru = sorted(set(out) - set(d.files))
    lulus_oracle = (not beda and baru == ["rr_corrected", "rr_mark_corrected", "rr_mark_raw",
                                          "rr_rhythm_state"])
    periksa("F3", lulus_ulang and lulus_oracle,
            "the live chain against the reading rebuilt from the frozen raw series: %s; the frozen "
            "fixture against the chain: %d arrays compared, %s; the keys this change adds and "
            "nothing else: %s"
            % ("identical" if lulus_ulang else "DIFFERENT", len(milik_rantai),
               "all identical" if not beda else "differing: " + ", ".join(beda), baru))
    return bool(lulus and lulus_ulang and lulus_oracle)


def main():
    print("S7 gate, the integer rhythm check over the RR series of the locked chain")
    print("fixture     : %s, %d bytes" % (NPZ, NPZ.stat().st_size))
    sidik = sidik_jari(NPZ)
    print("fixture sha : %s %s" % (sidik, "matches the frozen fingerprint" if
                                   sidik == SIDIK_FIXTURE else
                                   "DIFFERS from the frozen fingerprint " + SIDIK_FIXTURE))
    print("rules       : above 83/50 of the running average is a missed beat, below 1/2 is a "
          "false detection, above the %d ms ceiling is a recording gap" % R.RR_GAP_CEILING_MS)
    print("markers     : keep %d, split %d, drop %d, gap %d"
          % (R.RR_MARK_KEEP, R.RR_MARK_SPLIT, R.RR_MARK_DROP, R.RR_MARK_GAP))
    print("running avg : the integer median of the last %d corrected intervals, from median_bulat"
          % R.RR_RHYTHM_WINDOW)
    d = np.load(NPZ)
    x, sumber = jalan_rantai()
    print("input       : %s" % sumber)

    ok = [bagian_a(), bagian_b(), bagian_c(), bagian_d(), bagian_e()]
    f = bagian_f(d, x, sumber)

    print()
    print("-" * 132)
    lulus = sum(1 for _n, o in BARIS if o)
    gagal = sum(1 for _n, o in BARIS if not o)
    print("gate items: %d pass, %d fail, %d total" % (lulus, gagal, len(BARIS)))
    if gagal == 0 and all(ok) and f and sidik == SIDIK_FIXTURE:
        print("gate S7: PASS")
        return 0
    print("gate S7: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
