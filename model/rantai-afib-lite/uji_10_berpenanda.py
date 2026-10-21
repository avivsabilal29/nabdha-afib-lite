#!/usr/bin/env python3
"""AFIB-LITE measurement only: the marker arm, side by side with the raw arm and with the full
corrected arm of uji_09_deret_terkoreksi.py.

This file changes nothing. It reads the frozen modules, runs the frozen chain, and measures one
question: if the window feature layer consumes an interval series that USES the stage 7b markers
but DOES NOT use the split rule, does that arm beat the raw series, and does it beat the full
corrected series that step S7 left open?

THE THREE ARMS, STATED EXACTLY.

ARM RAW
    The series the pipeline consumes today: rr = np.diff(qrs) / FS_HZ * 1000, in ms, one class
    per interval from the rhythm annotation of the beat that ends it, lab[qrs[1:]]. It is built
    by the frozen rantai.kumpulkan_jendela itself, asked for the raw series by name since the
    chain default became berpenanda. Nothing is
    reimplemented for this arm.

ARM CORRECTED (full S7 reading)
    The series rantai hasil()["rr_corrected"], that is the raw series with mark 1 intervals
    replaced by their two exact halves, mark 2 intervals removed, and mark 3 intervals kept as
    one entry. It is produced here by importing uji_09_deret_terkoreksi.py and calling its own
    functions, deret_terkoreksi and kumpulkan, unchanged, so the middle arm of this report is
    bit for bit the arm that file measures.

ARM MARKED (the new arm this file is about)
    The series is the RAW interval series, in ms, with the same one class per interval,
    lab[qrs[1:]], and with the marker policy of stage 7b applied to it. The markers are read
    from the frozen stage itself, core["rr_mark_raw"], one mark per raw interval:

        mark 0 KEEP    the interval is kept exactly as it came, value and class unchanged.
        mark 1 SPLIT   INERT in this arm. The missed beat rule is switched OFF. It is not
                       applied and it is not compensated for: the interval stays whole, exactly
                       as the raw arm has it. The interval is still a member of the series.
        mark 2 DROP    the interval was a false detection (below half the running average). It
                       is removed from the series. The intervals to its left and to its right
                       then become adjacent entries of the series, which is the join: no
                       duration is invented and no interval is halved. This is the same
                       treatment the frozen stage already gives a mark 2 interval, which
                       "produced no entry at all" in the corrected series.
        mark 3 GAP     the interval was a recording gap (above the absolute 3000 ms ceiling).
                       It is removed from the window interval statistics rather than halved, so
                       no window mean, no window RMSSD, no pNN50 and no window entropy is drawn
                       from a stretch where the lead carries no signal. It leaves the series
                       completely instead of standing in it as one 51064 ms entry.

    WHY THE SPLIT RULE IS OFF, the biological reason, and the measured one.
    Atrial fibrillation is irregular by construction: the RR series has no regular cycle to
    protect. The missed beat rule assumes the opposite. It asks whether an interval exceeds
    83/50 of the running average, and in a regular rhythm that excess is evidence of a beat the
    detector did not see. In atrial fibrillation the same excess is the normal state of the
    rhythm, so the rule splits genuinely long physiological intervals into two halves and
    smooths exactly the irregularity the window features exist to measure. On 04015 it fires on
    397 of 2595 intervals, while the parts of that record which are really artefact are the 3
    gaps and the 9 false detections. That is why the full corrected arm moves the pooled
    hold-out miss rate from 0.0148 to 0.0334, and that is why this arm keeps the long interval
    whole and takes only the two marker readings that are artefact readings.

    HOW THE AVERAGE OF THE LAST EIGHT INTERVALS IS FORMED, and where the number eight appears.
    There are two averages of eight interval length in this chain and this arm treats the gap
    consistently in both.

    (i)  The running reference of the rhythm check itself. Stage 7b compares every raw interval
         against the INTEGER MEDIAN of the last 8 entries of its own corrected series
         (RR_RHYTHM_WINDOW = DELAPAN = 8, rantai.median_bulat). A mark 2 interval enters that
         average not at all, and a mark 3 gap enters it not at all, both by the frozen rule. A
         mark 1 interval enters it as its two halves, also by the frozen rule. In this arm the
         markers are taken from that frozen run as they come, so this average is the frozen
         average and no number of it is re-derived. The one place the switched off split rule
         could touch that average is if the check were re-run with the rule off, in which case
         the long interval would enter the window whole instead of as two halves and would
         raise the reference. Stage 8 measures that variant from the same raw series, so the
         effect of the definition is visible rather than assumed.

    (ii) The window features. A window is 32 consecutive intervals of the marked series and
         rantai.fitur_irama takes the arithmetic mean of exactly those 32 intervals for its
         second column, RMSSD divided by the mean RR. Because the mark 2 and mark 3 intervals
         are removed from the series before any window is formed, neither of them is in any
         such mean, and no window is formed across a gap at all.

    WINDOW RULE. The marked series goes through the same frozen rule as every other arm, that
    is uji_09_deret_terkoreksi.kumpulkan, a line for line generalisation of rantai.kumpulkan_jendela:
    windows of 32 intervals, step 4, kept only when every interval of the window carries the
    same class and that class is AFIB or N, and only when every interval lies inside 200 ms to
    3000 ms. The features come from rantai.fitur_irama itself.

WHAT IS MEASURED AND REPORTED.

  1. The three arms side by side at the operating point LOCKED by Aviv, ratio 0.165 and entropy
     0.63, used exactly as locked and identically on all three arms, on 04015 as the reference
     record and on the pooled hold-out of 04043 and 04126, which is 1562 windows including 677
     AFIB on the raw arm. Windows, sensitivity, specificity, accuracy, PPV, NPV, miss rate and
     firing rate are printed for every arm on every set.
  2. The operating point is then re-derived for the marker arm alone, with the selection rule
     of study S5c: the same ratio and entropy grid, the ratio arm alive at a ratio threshold of
     at least 0.050, the specificity of 04015 at least 0.80, the largest sensitivity wins, and
     the winning pair is then measured on the hold-out. The report says plainly whether that
     point dominates the locked point, that is whether it reaches a higher sensitivity at the
     same specificity or a higher specificity at the same sensitivity.
  3. The honesty of the selection: the headroom of the new point against the optimistic upper
     bound of the same hold-out windows, and the width of the selection noise, measured as the
     tied pairs of the grid on the derivation record and as the leave one record out spread over
     the test records. Both caveats are the ones the phase 6 documents already carry, restated
     for this arm.
  4. One diagnostic that the arm comparison cannot do by itself. Removing an interval shortens
     the series, so the step of 4 window grid of the marked arm starts on a different set of
     intervals than the grid of the raw arm, and a raw difference between the arms therefore
     mixes the marker policy with a change of which windows are sampled. Stage 5b asks both arms
     for a window at the SAME raw starting interval and prints the paired numbers, so the part
     that is policy and the part that is resampling are separated instead of being added
     together. Stage 5b is a diagnostic and not a fourth arm.

NO GATE OF THE PROJECT IS RE-RUN OR RE-SCORED HERE, no threshold is edited, no series is
written, no fixture is touched, and the marker arm is not proposed as a new default. The switch
belongs to Aviv.

Run it with the project interpreter:

    cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/uji_10_berpenanda.py

Exit code is 0 when the self-checks pass, 1 when they do not. The self-checks only guard that
the harness reproduces the frozen pipeline and the locked figures. They are not a verdict on the
marker arm.
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

import rantai as R                    # frozen, imported and never modified
import uji_06_referensi as U             # frozen, imported and never modified
import uji_04_ambang_pool as P           # frozen, imported and never modified
import uji_05_kebijakan_ambang as K      # frozen, imported and never modified
import uji_09_deret_terkoreksi as C      # frozen, imported and never modified

# =============================================================================================
# Constants. The only copied numbers are the frozen fixture hash, the locked operating point and
# the locked pooled hold-out figures, and every one of them is checked in this run.
# =============================================================================================

FIXTURE = HERE / "fixture" / "04015_30m.npz"
SHA_FIXTURE = "91ff408fb1b7880a124d28bcc4205038935d4a3a2dbabb4c0f7d161d89e8ac4d"

DERIVATION_RECORD = "04015"                 # the record every threshold is derived on
TEST_RECORDS = ("04043", "04126")           # the hold-out records
ALL_RECORDS = (DERIVATION_RECORD,) + TEST_RECORDS

T1_LOCKED = 0.165                           # ratio threshold of the locked point
T2_LOCKED = 0.63                            # entropy threshold of the locked point

LOCKED_SE = 0.9852                          # locked pooled hold-out figures of the raw arm
LOCKED_SP = 0.8282
LOCKED_ACC = 0.8963
LOCKED_PPV = 0.8144
LOCKED_NPV = 0.9865
LOCKED_MISS = 0.0148
S6_WINDOWS = 1562                           # pooled raw hold-out windows
S6_AFIB = 677                               # pooled raw hold-out AFIB windows

ALIVE = K.RATIO_MIN_ALIVE                   # 0.050, the ratio threshold that keeps the arm alive
SP_FLOOR = K.SPEC_FLOOR[0]                  # 0.80, the specificity floor of P1 in study S5c

MAIN = "marked"                             # the arm this file is about
RAW = "raw"
COR = "corrected"
ARM_LABEL = {RAW: "raw", COR: "corrected", MAIN: "marked"}

HASIL = []


# =============================================================================================
# Reporting
# =============================================================================================

def periksa(nama, lulus, keterangan):
    """One self-check line, collected for the summary line."""
    HASIL.append((nama, bool(lulus)))
    print("%-62s %-4s %s" % (nama, "PASS" if lulus else "FAIL", keterangan), flush=True)
    return bool(lulus)


def kepala(teks):
    print()
    print(teks, flush=True)


def lapor(nama, keterangan):
    """A measured fact that is not a pass or fail condition."""
    print("     %-46s %s" % (nama, keterangan), flush=True)


def sel(x, lebar=8, desimal=4):
    """One metric cell, with an explicit marker when the denominator was empty."""
    if x is None:
        return "n/a".rjust(lebar)
    return ("%.*f" % (desimal, x)).rjust(lebar)


def bil(x, lebar=5):
    if x is None:
        return "n/a".rjust(lebar)
    return str(int(x)).rjust(lebar)


# =============================================================================================
# The marked series. Reading only: no value is edited and nothing is written anywhere.
# =============================================================================================

def kelas_per_interval_mentah(core, label):
    """Class of every raw interval, the class at the beat that ends it, exactly as the frozen
    window layer has it: lab[qrs[1:]]."""
    qrs = np.asarray(core["qrs"])
    return label[qrs[1:]]


def seri_berpenanda(core, kelas_mentah, drop="omit"):
    """The marked interval series in ms, its class per entry and the source raw interval index.

    The marker policy, in code, so the walk is auditable:

        mark 0 KEEP   the entry is the raw interval, value and class unchanged
        mark 1 SPLIT  INERT: the missed beat rule is off, the raw interval is kept whole, and
                      the entry is still in the series
        mark 2 DROP   no entry: the interval leaves the series and its left and right
                      neighbours become adjacent entries, the join, with no duration invented
        mark 3 GAP    no entry: the gap leaves the window interval statistics completely, it is
                      not halved and it is not carried as a 51064 ms value either

    drop="omit" is the arm. drop="merge_left" is a definitional variant measured in stage 8 only:
    a mark 2 interval is added to the entry immediately to its left when that entry came from the
    raw interval just before it, and is kept as its own entry otherwise. It is printed as a
    variant and never as the arm, because the arm definition above is the one the brief states.

    Returns (deret_ms, kelas, sumber) with sumber the raw interval index of every entry.
    """
    rr = np.asarray(core["rr"]).astype(float)
    mk = np.asarray(core["rr_mark_raw"])
    n = int(rr.size)
    if int(mk.size) != n:
        raise RuntimeError("the mark series has %d entries for %d raw intervals" % (mk.size, n))
    nilai, kelas, sumber = [], [], []
    for i in range(n):
        m = int(mk[i])
        if m in (R.RR_MARK_KEEP, R.RR_MARK_SPLIT):
            nilai.append(float(rr[i]))
            kelas.append(kelas_mentah[i])
            sumber.append(i)
            continue
        if m == R.RR_MARK_GAP:
            continue                                # leaves the series, not halved
        if m == R.RR_MARK_DROP:
            if drop == "merge_left" and nilai and sumber[-1] == i - 1:
                nilai[-1] = nilai[-1] + float(rr[i])
            continue
        raise RuntimeError("unknown mark %d at raw interval %d" % (m, i))
    return (np.asarray(nilai, float), np.asarray(kelas, dtype=object),
            np.asarray(sumber, np.int64))


def tanda_dihitung_ulang(rr, split_aktif=False):
    """The frozen stage 7b rhythm check, re-run from the raw series with the split rule settable.

    This is a measurement side restatement of the integer arithmetic of rantai.rr_rhythm:
    the reference is the integer median of the last 8 entries of the running window
    (R.median_bulat, window R.RR_RHYTHM_WINDOW), a false detection is 2 * x < reference, a
    missed beat is 50 * x > 83 * reference, and an interval over R.RR_GAP_CEILING_MS caught by
    the missed beat rule is a gap and not a missed beat. A mark 2 and a mark 3 interval enter
    the running window not at all; with split_aktif=True a mark 1 interval enters as its two
    halves, which is the frozen behaviour, and with split_aktif=False it enters WHOLE, which is
    the variant this arm is about. rantai.py is not imported for this and is not modified.
    """
    hist = []
    tanda = np.empty(int(np.asarray(rr).size), dtype=np.int64)
    for i, x in enumerate(rr):
        x = int(x)
        ref = R.median_bulat(hist)
        if ref > 0 and 2 * x < ref:
            tanda[i] = R.RR_MARK_DROP
            continue                                     # enters no average
        if ref > 0 and (R.RR_MISS_DEN * x) > (R.RR_MISS_NUM * ref):
            if x > R.RR_GAP_CEILING_MS:
                tanda[i] = R.RR_MARK_GAP
                continue                                 # enters no average
            tanda[i] = R.RR_MARK_SPLIT
            if split_aktif:
                first = x >> 1
                hist.append(first)
                hist.append(x - first)
            else:
                hist.append(x)
            if len(hist) > R.RR_RHYTHM_WINDOW:
                del hist[:len(hist) - R.RR_RHYTHM_WINDOW]
            continue
        tanda[i] = R.RR_MARK_KEEP
        hist.append(x)
        if len(hist) > R.RR_RHYTHM_WINDOW:
            del hist[:len(hist) - R.RR_RHYTHM_WINDOW]
    return tanda


def jendela_berpenanda(deret, kelas, sumber):
    """The frozen window rule over the marked series. Delegated to the frozen generalisation of
    uji_09_deret_terkoreksi.kumpulkan, so the arm cannot differ from the raw arm by a rule."""
    return C.kumpulkan(deret, kelas, origin_map=sumber)


def jendela_pada_asal(deret_pen, kelas_int_pen, sumber_pen, deret_raw, kelas_int_raw):
    """The same window rule, asked for at the window starts the RAW grid uses, in both arms.

    This is a diagnostic and not an arm. Removing intervals shortens the marked series, so the
    step of 4 grid of the marked arm sits on a different set of starting intervals than the grid
    of the raw arm, and the metric difference between the two arms then mixes the marker policy
    with a change of which windows are sampled. Asking both arms for a window at the SAME raw
    starting interval removes the sampling part and leaves the policy part.

    A raw window at raw interval i is paired with the marked window at the position that raw
    interval i occupies in the marked series, and a pair is kept only when BOTH windows satisfy
    the frozen acceptance rule: one class, AFIB or N, and every interval inside 200 ms to 3000 ms.

    Returns (asal, fitur_raw, fitur_pen, kelas) over the paired origins.
    """
    pos = {int(s): j for j, s in enumerate(sumber_pen)}
    asal, f_raw, f_pen, kel = [], [], [], []
    for i in range(0, deret_raw.size - R.JENDELA_DENYUT, R.LANGKAH_DENYUT):
        u_r = np.unique(kelas_int_raw[i:i + R.JENDELA_DENYUT])
        if u_r.size != 1 or u_r[0] not in ("AFIB", "N"):
            continue
        seg_r = deret_raw[i:i + R.JENDELA_DENYUT]
        if seg_r.min() < 200 or seg_r.max() > 3000:
            continue
        j = pos.get(int(i))
        if j is None or j + R.JENDELA_DENYUT > deret_pen.size:
            continue
        u_p = np.unique(kelas_int_pen[j:j + R.JENDELA_DENYUT])
        if u_p.size != 1 or u_p[0] not in ("AFIB", "N") or str(u_p[0]) != str(u_r[0]):
            continue
        seg_p = deret_pen[j:j + R.JENDELA_DENYUT]
        if seg_p.min() < 200 or seg_p.max() > 3000:
            continue
        asal.append(i)
        f_raw.append(R.fitur_irama(seg_r))
        f_pen.append(R.fitur_irama(seg_p))
        kel.append(str(u_r[0]))
    return (np.asarray(asal, np.int64),
            np.asarray(f_raw, float).reshape(-1, 4),
            np.asarray(f_pen, float).reshape(-1, 4),
            np.asarray(kel, dtype=object))


# =============================================================================================
# Main
# =============================================================================================

def main():
    t_mulai = time.time()
    k1, k2 = R.kisi_ambang()

    print("AFIB-LITE measurement only: the marker arm against the raw arm and the corrected arm")
    print("=" * 138)
    print("interpreter   :", sys.executable)
    print("data root     :", U.DATA_ROOT)
    print("reference rec : %s, reported as reference only and never used to score a hold-out"
          % DERIVATION_RECORD)
    print("test records  : %s, pooled as the frozen gates pool them" % " and ".join(TEST_RECORDS))
    print("locked point  : ratio %.3f entropy %.2f, Aviv's locked pair, used as is on all three "
          "arms" % (T1_LOCKED, T2_LOCKED))
    print("arms          : raw, as the pipeline consumes it today | corrected, the full S7 "
          "reading from uji_09_deret_terkoreksi.py | marked, the new arm")
    print("metric policy : sensitivity, specificity, accuracy, PPV, NPV and miss rate, each "
          "with the window count and the prevalence of its set")
    print("nothing is changed: no threshold is derived in place, no threshold is edited, no "
          "series is written, no fixture is touched, nothing is staged")

    # ------------------------------------------------------------------ stage 0, the arm
    kepala("stage 0, the marked arm stated exactly, so the rule and the reason are not implied")
    print("     The series is the raw interval series in ms, one class per interval from the")
    print("     rhythm annotation of the beat that ends it. The stage 7b markers are read from")
    print("     the frozen run, core['rr_mark_raw'], and used as follows.")
    print("       mark 0 KEEP   the interval is kept exactly as it came.")
    print("       mark 1 SPLIT  the missed beat rule is OFF. The interval stays whole, exactly as")
    print("                     the raw arm has it. It is not halved and it is not discarded.")
    print("       mark 2 DROP   the false detection leaves the series, so the intervals to its")
    print("                     left and to its right become adjacent entries: the join. No")
    print("                     duration is invented and no interval is halved.")
    print("       mark 3 GAP    the recording gap leaves the window interval statistics")
    print("                     completely. It is neither halved nor carried as one 51064 ms")
    print("                     entry, so no window mean and no window irregularity is drawn")
    print("                     from a stretch where the lead carries no signal.")
    print("     The average of the last eight intervals takes the gap the same way in both")
    print("     places it appears. In the running reference of the rhythm check, the integer")
    print("     median of the last 8 entries, a mark 2 interval and a mark 3 gap enter not at")
    print("     all and a mark 1 interval enters as its two halves by the frozen rule, which is")
    print("     the run the markers are read from. In the window features, the second column of")
    print("     rantai.fitur_irama is RMSSD over the arithmetic mean of the 32 intervals of the")
    print("     window, and because mark 2 and mark 3 intervals are removed before any window is")
    print("     formed, neither of them is in any such mean and no window spans a gap.")
    print("     The biological reason the split rule is off: atrial fibrillation is irregular by")
    print("     nature, so an interval above 83/50 of the running average is not evidence of a")
    print("     missed beat but the normal state of the rhythm. On 04015 the rule fires on 397 of")
    print("     2595 intervals while the record holds 3 gaps and 9 false detections, so the rule")
    print("     mostly splits genuinely long physiological intervals and smooths the very")
    print("     irregularity the window features measure.")

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
    kepala("stage 2, one real chain run per recording, all three window tables produced")
    hasil = {}
    for nama in ALL_RECORDS:
        r = P.jalankan(nama)                       # frozen S5b runner, adapter plus core
        core = r["core"]
        label = r["label"]
        kelas_int = kelas_per_interval_mentah(core, label)

        # ARM RAW: the frozen collector itself.
        # ARM RAW: the frozen collector itself, asked for the raw series by name. The chain
        # default is berpenanda now, so this arm must name mentah instead of inheriting it.
        if np.asarray(core["qrs"]).size < 2:
            fitur_mentah, kelas_mentah = np.zeros((0, 4), dtype=float), np.zeros(0, dtype=object)
        else:
            fitur_mentah, kelas_mentah = R.kumpulkan_jendela(
                core["qrs"], label, sumber=R.SUMBER_MENTAH)
        # ARM MARKED: the new arm, the marker policy over the raw series.
        deret_pen, kelas_int_pen, sumber_pen = seri_berpenanda(core, kelas_int, drop="omit")
        fitur_pen, kelas_pen, origin_pen = jendela_berpenanda(deret_pen, kelas_int_pen, sumber_pen)
        # ARM CORRECTED: the full S7 reading, produced by the frozen file that measures it.
        deret_kor, kelas_int_kor, sumber_kor, _ = C.deret_terkoreksi(core, kelas_int)
        fitur_kor, kelas_kor, origin_kor = C.kumpulkan(deret_kor, kelas_int_kor, origin_map=sumber_kor)

        # the marked series with the alternative reading of the join, variant only
        deret_v, kelas_int_v, sumber_v = seri_berpenanda(core, kelas_int, drop="merge_left")
        fitur_v, kelas_v, origin_v = jendela_berpenanda(deret_v, kelas_int_v, sumber_v)
        # the marked series with the rhythm check re-run with the split rule off, variant only
        tanda_v = tanda_dihitung_ulang(core["rr"], split_aktif=False)
        core_v = dict(core)
        core_v["rr_mark_raw"] = tanda_v
        deret_w, kelas_int_w, sumber_w = seri_berpenanda(core_v, kelas_int, drop="omit")
        fitur_w, kelas_w, origin_w = jendela_berpenanda(deret_w, kelas_int_w, sumber_w)

        mk = np.asarray(core["rr_mark_raw"])
        hasil[nama] = dict(
            nama=nama, run=r, core=core, detik=r["detik"], label=label,
            fitur={RAW: fitur_mentah, MAIN: fitur_pen, COR: fitur_kor},
            kelas={RAW: kelas_mentah, MAIN: kelas_pen, COR: kelas_kor},
            origin={RAW: np.arange(kelas_mentah.size, dtype=np.int64), MAIN: origin_pen,
                    COR: origin_kor},
            deret={RAW: np.diff(np.asarray(core["qrs"])) / R.FS_HZ * 1000.0, MAIN: deret_pen,
                   COR: deret_kor},
            kelas_int={RAW: kelas_int, MAIN: kelas_int_pen, COR: kelas_int_kor},
            sumber={MAIN: sumber_pen, COR: sumber_kor},
            varian=dict(merge=(fitur_v, kelas_v), ulang=(fitur_w, kelas_w),
                        tandabeda=int((tanda_v != mk).sum())),
            mark=int(mk.size), keep=int((mk == 0).sum()), split=int((mk == 1).sum()),
            drop=int((mk == 2).sum()), gap=int((mk == 3).sum()),
        )
        a = hasil[nama]
        print("     %-6s %6d samples, %5d beats, raw intervals %5d, marked entries %5d, "
              "corrected entries %5d, chain %.1f s"
              % (nama, r["sampel"], int(core["qrs"].size), core["rr"].size,
                 deret_pen.size, core["rr_corrected"].size, r["detik"]))
        print("            markers 0/1/2/3 = %d/%d/%d/%d, so the marked arm takes %d intervals "
              "out of the series (%d false detections and %d gaps) and expands nothing"
              % (a["keep"], a["split"], a["drop"], a["gap"], a["drop"] + a["gap"],
                 a["drop"], a["gap"]))
        print("            windows raw %4d (AFIB %3d), marked %4d (AFIB %3d), corrected %4d "
              "(AFIB %3d)"
              % (kelas_mentah.size, int((kelas_mentah == "AFIB").sum()),
                 kelas_pen.size, int((kelas_pen == "AFIB").sum()),
                 kelas_kor.size, int((kelas_kor == "AFIB").sum())))

    own = hasil[DERIVATION_RECORD]

    # ------------------------------------------------------------------ stage 3, self checks
    kepala("stage 3, self checks of the measurement harness, not a verdict on the marked arm")
    periksa("fixture sha256 matches the frozen oracle",
            sha == SHA_FIXTURE, "measured %s" % sha[:16])
    periksa("the raw arm reproduces the frozen 04015 feature table",
            np.array_equal(own["fitur"][RAW], d["jendela_fitur"]),
            "shape %s, zero difference" % (own["fitur"][RAW].shape,))
    periksa("the raw arm reproduces the frozen 04015 class table",
            np.array_equal(own["kelas"][RAW], d["jendela_kelas_benar"]),
            "shape %s, zero difference" % (own["kelas"][RAW].shape,))
    periksa("the raw arm reproduces the frozen 04015 beat list",
            np.array_equal(own["core"]["qrs"], d["qrs"]),
            "%d beats, equal to the fixture" % own["core"]["qrs"].size)
    pooled_raw_win = int(sum(hasil[n]["kelas"][RAW].size for n in TEST_RECORDS))
    pooled_raw_afib = int(sum((hasil[n]["kelas"][RAW] == "AFIB").sum() for n in TEST_RECORDS))
    periksa("the raw pooled hold-out is the frozen 1562 windows and 677 AFIB",
            pooled_raw_win == S6_WINDOWS and pooled_raw_afib == S6_AFIB,
            "measured %d windows and %d AFIB" % (pooled_raw_win, pooled_raw_afib))
    m_raw_locked = K.metrik_lengkap(own["fitur"][RAW], own["kelas"][RAW], T1_LOCKED, T2_LOCKED)
    gab_raw_locked = K.metrik_lengkap(
        np.vstack([hasil[n]["fitur"][RAW] for n in TEST_RECORDS]),
        np.concatenate([hasil[n]["kelas"][RAW] for n in TEST_RECORDS]), T1_LOCKED, T2_LOCKED)
    periksa("the raw arm reproduces the locked point figures on the pooled hold-out",
            abs(gab_raw_locked["sensitivity"] - LOCKED_SE) < 5e-5
            and abs(gab_raw_locked["specificity"] - LOCKED_SP) < 5e-5
            and abs(gab_raw_locked["accuracy"] - LOCKED_ACC) < 5e-5
            and abs(gab_raw_locked["ppv"] - LOCKED_PPV) < 5e-5
            and abs(gab_raw_locked["npv"] - LOCKED_NPV) < 5e-5
            and abs(gab_raw_locked["miss"] - LOCKED_MISS) < 5e-5,
            "Se %.4f Sp %.4f Acc %.4f PPV %.4f NPV %.4f miss %.4f against the locked %.4f %.4f "
            "%.4f %.4f %.4f %.4f"
            % (gab_raw_locked["sensitivity"], gab_raw_locked["specificity"],
               gab_raw_locked["accuracy"], gab_raw_locked["ppv"], gab_raw_locked["npv"],
               gab_raw_locked["miss"], LOCKED_SE, LOCKED_SP, LOCKED_ACC, LOCKED_PPV, LOCKED_NPV,
               LOCKED_MISS))
    periksa("the marked series keeps every mark 0 and mark 1 interval and removes every mark 2 "
            "and mark 3 interval",
            all(hasil[n]["deret"][MAIN].size == hasil[n]["mark"] - hasil[n]["drop"] - hasil[n]["gap"]
                for n in ALL_RECORDS),
            "marked entries " + ", ".join("%s %d of %d" % (n, hasil[n]["deret"][MAIN].size,
                                                           hasil[n]["mark"])
                                          for n in ALL_RECORDS))
    periksa("the marked arm expands nothing: no entry is a half of another entry",
            all(hasil[n]["deret"][MAIN].size <= hasil[n]["deret"][RAW].size for n in ALL_RECORDS),
            "raw intervals minus removed entries equals the marked series on every record")
    periksa("the marked arm and the raw arm share one collector, so no rule was added",
            all(np.array_equal(hasil[n]["fitur"][RAW],
                               C.kumpulkan(hasil[n]["deret"][RAW], hasil[n]["kelas_int"][RAW])[0])
                for n in ALL_RECORDS),
            "the generalisation agrees with the frozen collector on the raw series of all three "
            "records")
    periksa("the corrected arm measured here is the one uji_09_deret_terkoreksi.py measures",
            all(hasil[n]["deret"][COR].size == hasil[n]["core"]["rr_corrected"].size
                for n in ALL_RECORDS),
            "corrected entries 04015 %d, 04043 %d, 04126 %d"
            % tuple(hasil[n]["deret"][COR].size for n in ALL_RECORDS))

    # ------------------------------------------------------------------ stage 4, census
    kepala("stage 4, the three series and the three window tables, per record")
    print("     %-6s %8s %10s %10s %8s %8s %8s %8s %10s %10s %10s"
          % ("record", "raw int", "marks 0", "marks 1", "marks 2", "marks 3", "marked",
             "corrected", "raw win", "mrk win", "cor win"))
    for nama in ALL_RECORDS:
        a = hasil[nama]
        print("     %-6s %8d %10d %10d %8d %8d %8d %8d %10d %10d %10d"
              % (nama, a["mark"], a["keep"], a["split"], a["drop"], a["gap"],
                 a["deret"][MAIN].size, a["deret"][COR].size,
                 a["kelas"][RAW].size, a["kelas"][MAIN].size, a["kelas"][COR].size))
    print("     pooled hold-out windows: raw %d, marked %d, corrected %d"
          % (pooled_raw_win,
             int(sum(hasil[n]["kelas"][MAIN].size for n in TEST_RECORDS)),
             int(sum(hasil[n]["kelas"][COR].size for n in TEST_RECORDS))))
    print("     pooled hold-out AFIB   : raw %d, marked %d, corrected %d"
          % (pooled_raw_afib,
             int(sum((hasil[n]["kelas"][MAIN] == "AFIB").sum() for n in TEST_RECORDS)),
             int(sum((hasil[n]["kelas"][COR] == "AFIB").sum() for n in TEST_RECORDS))))
    for nama in ALL_RECORDS:
        fo = hasil[nama]["origin"][MAIN]
        fr = hasil[nama]["origin"][RAW]
        sama = int(np.intersect1d(fo, fr).size)
        lapor("  %s window origins shared with raw" % nama,
              "%d of %d marked windows start on a raw interval that also starts a raw window"
              % (sama, fo.size))

    # ------------------------------------------------------------------ stage 5, metrics
    kepala("stage 5, the three arms at the LOCKED point, ratio %.3f entropy %.2f, used as is"
           % (T1_LOCKED, T2_LOCKED))
    tabel = {}
    for nama in ALL_RECORDS:
        tabel[nama] = {arm: (hasil[nama]["fitur"][arm], hasil[nama]["kelas"][arm])
                       for arm in (RAW, MAIN, COR)}
    tabel["pooled"] = {
        arm: (np.vstack([hasil[n]["fitur"][arm] for n in TEST_RECORDS]),
              np.concatenate([hasil[n]["kelas"][arm] for n in TEST_RECORDS]))
        for arm in (RAW, MAIN, COR)}
    metrik = {}
    for nama_set in ("04015", "04043", "04126", "pooled"):
        print()
        f_r, k_r = tabel[nama_set][RAW]
        print("  %s, %d windows, %d AFIB, prevalence %.4f"
              % (nama_set, k_r.size, int((k_r == "AFIB").sum()),
                 float((k_r == "AFIB").mean())))
        print("  %-10s %6s %5s %5s %5s %5s %5s %8s %8s %8s %8s %8s %8s %8s"
              % ("arm", "win", "afib", "tp", "fp", "fn", "tn", "Se", "Sp", "Acc", "PPV", "NPV",
                 "miss", "fire"))
        for arm in (RAW, MAIN, COR):
            f, k = tabel[nama_set][arm]
            m = K.metrik_lengkap(f, k, T1_LOCKED, T2_LOCKED)
            metrik[(nama_set, arm)] = m
            print("  %-10s %6d %5d %5d %5d %5d %5d %8s %8s %8s %8s %8s %8s %8s"
                  % (ARM_LABEL[arm], m["windows"], m["afib"], m["tp"], m["fp"], m["fn"], m["tn"],
                     sel(m["sensitivity"]), sel(m["specificity"]), sel(m["accuracy"]),
                     sel(m["ppv"]), sel(m["npv"]), sel(m["miss"]), sel(m["firing"])))
        base = metrik[(nama_set, RAW)]
        for arm in (MAIN, COR):
            m = metrik[(nama_set, arm)]
            print("  %-10s %6s d_win %+d  d_Se %+.4f  d_Sp %+.4f  d_Acc %+.4f  d_PPV %s  "
                  "d_NPV %s  d_miss %+.4f  d_fire %+.4f"
                  % ("delta " + ARM_LABEL[arm][:4], "",
                     m["windows"] - base["windows"],
                     m["sensitivity"] - base["sensitivity"],
                     m["specificity"] - base["specificity"],
                     m["accuracy"] - base["accuracy"],
                     "%+.4f" % (m["ppv"] - base["ppv"]) if (m["ppv"] is not None
                                                            and base["ppv"] is not None) else "n/a",
                     "%+.4f" % (m["npv"] - base["npv"]) if (m["npv"] is not None
                                                            and base["npv"] is not None) else "n/a",
                     m["miss"] - base["miss"], m["firing"] - base["firing"]))
        print("  prevalence of this set is %.4f at %d AFIB of %d windows, and PPV and NPV hold "
              "at that prevalence only" % (float((k_r == "AFIB").mean()),
                                           int((k_r == "AFIB").sum()), k_r.size))
    print()
    print("  the question this table answers, read on the pooled hold-out")
    a = metrik[("pooled", MAIN)]
    b = metrik[("pooled", RAW)]
    c = metrik[("pooled", COR)]
    print("    marked against raw     : Se %+.4f, Sp %+.4f, Acc %+.4f, miss %+.4f, windows %+d"
          % (a["sensitivity"] - b["sensitivity"], a["specificity"] - b["specificity"],
             a["accuracy"] - b["accuracy"], a["miss"] - b["miss"], a["windows"] - b["windows"]))
    print("    marked against corrected: Se %+.4f, Sp %+.4f, Acc %+.4f, miss %+.4f, windows %+d"
          % (a["sensitivity"] - c["sensitivity"], a["specificity"] - c["specificity"],
             a["accuracy"] - c["accuracy"], a["miss"] - c["miss"], a["windows"] - c["windows"]))
    print("    corrected against raw  : Se %+.4f, Sp %+.4f, Acc %+.4f, miss %+.4f, windows %+d"
          % (c["sensitivity"] - b["sensitivity"], c["specificity"] - b["specificity"],
             c["accuracy"] - b["accuracy"], c["miss"] - b["miss"], c["windows"] - b["windows"]))
    print("  the window counts of the three arms are not comparable one to one: removing an")
    print("  interval shortens the series, so the step of 4 grid of the marked arm starts on a")
    print("  different set of intervals than the grid of the raw arm, and part of the movement")
    print("  above is therefore a change of which windows are sampled and not the marker policy.")
    print("  Stage 5b removes that part by asking both arms for a window at the same start.")

    # ------------------------------------------------------------------ stage 5b, paired
    kepala("stage 5b, both arms asked for a window at the SAME raw starting interval")
    print("  A pair is kept only when the raw window and the marked window at that same start both")
    print("  satisfy the frozen acceptance rule, so the two columns below run at the same pair "
          "%.3f and %.2f" % (T1_LOCKED, T2_LOCKED))
    print("  over the same starting intervals and the same classes, and only the interval series "
          "differs.")
    pasangan = {}
    print("  %-8s %14s %14s %12s %12s %10s"
          % ("set", "raw accepted", "paired", "paired AFIB", "lost to remov", "passed thr"))
    for nama in ALL_RECORDS + ("pooled",):
        if nama == "pooled":
            asal = np.concatenate([pasangan[n][0] for n in TEST_RECORDS])
            fr = np.vstack([pasangan[n][1] for n in TEST_RECORDS])
            fp = np.vstack([pasangan[n][2] for n in TEST_RECORDS])
            kl = np.concatenate([pasangan[n][3] for n in TEST_RECORDS])
            hilang = sum(pasangan[n][4] for n in TEST_RECORDS)
            raw_acc = sum(pasangan[n][5] for n in TEST_RECORDS)
        else:
            a_rec = hasil[nama]
            asal, fr, fp, kl = jendela_pada_asal(a_rec["deret"][MAIN], a_rec["kelas_int"][MAIN],
                                                 a_rec["sumber"][MAIN], a_rec["deret"][RAW],
                                                 a_rec["kelas_int"][RAW])
            raw_acc = a_rec["kelas"][RAW].size
            hilang = raw_acc - asal.size
            pasangan[nama] = None
        pasangan[nama] = (asal, fr, fp, kl, hilang, raw_acc)
        m_r = K.metrik_lengkap(fr, kl, T1_LOCKED, T2_LOCKED)
        m_p = K.metrik_lengkap(fp, kl, T1_LOCKED, T2_LOCKED)
        print("  %-8s %14d %14d %12d %12d %10d"
              % (nama, raw_acc, asal.size, int((kl == "AFIB").sum()), hilang,
                 m_r["tp"] + m_r["fp"]))
        print("  %-8s raw    Se %.4f Sp %.4f Acc %.4f miss %.4f | marked Se %.4f Sp %.4f "
              "Acc %.4f miss %.4f" % ("", m_r["sensitivity"], m_r["specificity"],
                                      m_r["accuracy"], m_r["miss"], m_p["sensitivity"],
                                      m_p["specificity"], m_p["accuracy"], m_p["miss"]))
        ras = (fr[:, 1] > T1_LOCKED) & (fr[:, 3] > T2_LOCKED)
        pen = (fp[:, 1] > T1_LOCKED) & (fp[:, 3] > T2_LOCKED)
        naik = int((pen & ~ras).sum())
        turun = int((ras & ~pen).sum())
        print("  %-8s %s" % ("", "decisions that change: %d window(s) the raw arm holds back and "
                                 "the marked arm calls AFIB, %d the other way round, out of %d "
                                 "paired windows" % (naik, turun, asal.size)))
    pool = pasangan["pooled"]
    periksa("the paired diagnostic keeps the same classes in both arms by construction",
            True,
            "%d paired windows on the pooled hold-out, and the class of a pair comes from the "
            "class of one and the same raw starting interval" % pool[0].size)

    # ------------------------------------------------------------------ stage 6, new point
    kepala("stage 6, the operating point re-derived for the MARKED arm alone, rule of study S5c")
    print("  derivation record %s only, grid ratio %.3f to %.3f and entropy %.2f to %.2f, %d "
          "pairs, ratio arm alive at a ratio threshold of at least %.3f, specificity floor %.2f, "
          "largest sensitivity wins"
          % (DERIVATION_RECORD, k1[0], k1[-1], k2[0], k2[-1], k1.size * k2.size, ALIVE, SP_FLOOR))
    pilih = K.pilih_titik(own["fitur"][MAIN], own["kelas"][MAIN], k1, k2, ALIVE)
    for nama_pt in ("P1", "P2", "P3", "P4"):
        b_pt = pilih[nama_pt]
        aturan = ("largest sensitivity of 04015 with specificity at least %.2f"
                  % K.SPEC_FLOOR[("P1", "P2", "P3").index(nama_pt)] if nama_pt in ("P1", "P2", "P3")
                  else "best accuracy of 04015 with the ratio arm alive")
        print("    %-3s ratio %.3f entropy %.2f | on 04015 Se %.4f Sp %.4f Acc %.4f, ratio arm "
              "passes %d of %d windows, holds back %d | %s"
              % (nama_pt, b_pt["t1"], b_pt["t2"], b_pt["se"], b_pt["sp"], b_pt["acc"],
                 b_pt["ratio_above"], own["kelas"][MAIN].size, b_pt["held_back"], aturan))
    p1 = pilih["P1"]
    T1_NEW, T2_NEW = float(p1["t1"]), float(p1["t2"])
    print()
    print("  the same rule run on the other two 04015 tables, so the reader can see whether the")
    print("  derivation moved because the series moved or because the rule is simply unstable")
    for arm in (RAW, MAIN, COR):
        p_arm = K.pilih_titik(own["fitur"][arm], own["kelas"][arm], k1, k2, ALIVE)["P1"]
        print("    %-9s S5c P1 on 04015: ratio %.3f entropy %.2f, Se %.4f Sp %.4f Acc %.4f"
              % (ARM_LABEL[arm], p_arm["t1"], p_arm["t2"], p_arm["se"], p_arm["sp"], p_arm["acc"]))
    print()
    print("  the new point of the marked arm is ratio %.3f, entropy %.2f, derived on 04015 only"
          % (T1_NEW, T2_NEW))
    periksa("the new point keeps the ratio arm alive",
            T1_NEW >= ALIVE - 1e-12,
            "ratio %.3f, at or above %.3f, so the gate is still a two feature AND gate"
            % (T1_NEW, ALIVE))
    periksa("the new point meets the specificity floor on the derivation record",
            p1["sp"] >= SP_FLOOR - 1e-12,
            "specificity of 04015 %.4f against the floor %.2f" % (p1["sp"], SP_FLOOR))

    print()
    print("  the new point and the locked point, both measured on the MARKED arm, so the "
          "comparison is like for like")
    print("  %-8s %-16s %6s %5s %5s %5s %5s %5s %8s %8s %8s %8s %8s %8s %8s"
          % ("set", "point", "win", "afib", "tp", "fp", "fn", "tn", "Se", "Sp", "Acc", "PPV",
             "NPV", "miss", "fire"))
    baru = {}
    kunci = {}
    for nama_set in ("04015", "04043", "04126", "pooled"):
        f, k = tabel[nama_set][MAIN]
        for tag, t1, t2 in (("new", T1_NEW, T2_NEW), ("locked", T1_LOCKED, T2_LOCKED)):
            m = K.metrik_lengkap(f, k, t1, t2)
            (baru if tag == "new" else kunci)[nama_set] = m
            print("  %-8s %-16s %6d %5d %5d %5d %5d %5d %8s %8s %8s %8s %8s %8s %8s"
                  % (nama_set, "%s %.3f/%.2f" % (tag, t1, t2), m["windows"], m["afib"], m["tp"],
                     m["fp"], m["fn"], m["tn"], sel(m["sensitivity"]), sel(m["specificity"]),
                     sel(m["accuracy"]), sel(m["ppv"]), sel(m["npv"]), sel(m["miss"]),
                     sel(m["firing"])))
    print()
    mn, ml = baru["pooled"], kunci["pooled"]
    d_se = mn["sensitivity"] - ml["sensitivity"]
    d_sp = mn["specificity"] - ml["specificity"]
    tol = 1e-12
    menang = ((d_se >= -tol and d_sp >= -tol) and (d_se > tol or d_sp > tol))
    print("  pooled hold-out, new point minus locked point, on the marked arm: d_Se %+.4f, "
          "d_Sp %+.4f, d_Acc %+.4f, d_miss %+.4f, d_PPV %s, d_NPV %s"
          % (d_se, d_sp, mn["accuracy"] - ml["accuracy"], mn["miss"] - ml["miss"],
             "%+.4f" % (mn["ppv"] - ml["ppv"]),
             "%+.4f" % (mn["npv"] - ml["npv"])))
    if menang:
        arah = ("higher sensitivity at equal or better specificity" if d_se > tol
                else "higher specificity at equal or better sensitivity")
        print("  VERDICT: the new point DOMINATES the locked point, by %s." % arah)
    elif abs(d_se) <= tol and abs(d_sp) <= tol:
        print("  VERDICT: the new point is IDENTICAL to the locked point on the pooled hold-out,")
        print("  and on the derivation record as well: the rule of study S5c applied to the marked")
        print("  04015 table re-derives Aviv's locked pair %.3f and %.2f exactly. So the marker "
              "arm buys no different" % (T1_LOCKED, T2_LOCKED))
        print("  operating point, and the comparison between the arms is the one stage 5 prints,")
        print("  run at one and the same pair. Nothing about the arm was tuned to reach that.")
    else:
        print("  VERDICT: the new point does NOT dominate the locked point. It gives up %+.4f "
              "sensitivity and %+.4f specificity, so the two points simply trade one against "
              "the other." % (d_se, d_sp))
    print("  the same comparison on the raw arm, for context only, is printed in stage 5: the "
          "marked arm hold-out set has a different window population, so the two verdicts are "
          "not the same question.")
    periksa("the new point is a function of the 04015 marked table only",
            all(pilih[x]["t1"] is not None for x in ("P1", "P2", "P3", "P4")),
            "no test record is an argument of the selection; the hold-out records are used to "
            "measure the pair that was already fixed")

    # ------------------------------------------------------------------ stage 7, honesty
    kepala("stage 7, the honesty of the selection, the two caveats the phase 6 documents carry")
    batas = K.batas_atas(tabel["pooled"][MAIN][0], tabel["pooled"][MAIN][1], k1, k2)
    print("  A the optimistic upper bound of the SAME hold-out windows. NOT hold-out: the pair "
          "behind each number was chosen while looking at the very windows it is scored on, so "
          "every number here is a ceiling and must never be quoted as an achievement.")
    print("    pooled marked hold-out, %d windows, %d AFIB, full grid of %d pairs"
          % (tabel["pooled"][MAIN][1].size,
             int((tabel["pooled"][MAIN][1] == "AFIB").sum()), batas["grid"]))
    print("    best accuracy      %.4f at ratio %.3f entropy %.2f, %d pairs tie, sensitivity "
          "there %.4f, specificity there %.4f"
          % (batas["acc"], batas["pada_acc"][0]["t1"], batas["pada_acc"][0]["t2"],
             batas["pada_acc_n"], batas["pada_acc"][0]["se"], batas["pada_acc"][0]["sp"]))
    print("    best sensitivity   %.4f at ratio %.3f entropy %.2f, %d pairs tie, specificity "
          "there %.4f"
          % (batas["se"], batas["pada_se"]["t1"], batas["pada_se"]["t2"], batas["pada_se_n"],
             batas["pada_se"]["sp"]))
    print("    best specificity   %.4f at ratio %.3f entropy %.2f, %d pairs tie, sensitivity "
          "there %.4f"
          % (batas["sp"], batas["pada_sp"]["t1"], batas["pada_sp"]["t2"], batas["pada_sp_n"],
             batas["pada_sp"]["se"]))
    if batas["se_at_sp80"]:
        print("    triage reading     largest sensitivity with specificity at least 0.80 is "
              "%.4f at ratio %.3f entropy %.2f, specificity %.4f"
              % (batas["se_at_sp80"]["se"], batas["se_at_sp80"]["t1"],
                 batas["se_at_sp80"]["t2"], batas["se_at_sp80"]["sp"]))
    print("  B the headroom of the new point against that bound")
    print("    accuracy    bound %.4f, new point %.4f, headroom %.4f accuracy points"
          % (batas["acc"], mn["accuracy"], batas["acc"] - mn["accuracy"]))
    print("    sensitivity bound %.4f, new point %.4f, headroom %.4f points"
          % (batas["se"], mn["sensitivity"], batas["se"] - mn["sensitivity"]))
    if batas["se_at_sp80"]:
        print("    sensitivity with specificity held at 0.80 or more, bound %.4f, new point "
              "%.4f, headroom %.4f points"
              % (batas["se_at_sp80"]["se"], mn["sensitivity"],
                 batas["se_at_sp80"]["se"] - mn["sensitivity"]))
    print("    specificity bound %.4f, new point %.4f, headroom %.4f points"
          % (batas["sp"], mn["specificity"], batas["sp"] - mn["specificity"]))
    print("  C the width of the selection noise, so a difference smaller than these widths is "
          "not evidence")
    plat_own = P.plateau(own["fitur"][MAIN], own["kelas"][MAIN])
    baris = pilih["baris"]
    acc_max = max(b["acc"] for b in baris)
    seri_tepat = [b for b in baris if abs(b["acc"] - acc_max) <= 1e-12]
    seri_dekat = [b for b in baris if b["acc"] >= acc_max - 1.0 / own["kelas"][MAIN].size - 1e-12]
    print("    derivation record %s: best accuracy %.4f of %d windows, reached by %d of the %d "
          "pairs with the ratio arm alive, and %d pairs come within one window of it"
          % (DERIVATION_RECORD, acc_max, own["kelas"][MAIN].size, len(seri_tepat), len(baris),
             len(seri_dekat)))
    print("    derivation record %s: at best accuracy the ratio threshold runs %.3f to %.3f and "
          "the entropy threshold runs %.2f to %.2f"
          % (DERIVATION_RECORD, min(b["t1"] for b in seri_tepat),
             max(b["t1"] for b in seri_tepat), min(b["t2"] for b in seri_tepat),
             max(b["t2"] for b in seri_tepat)))
    plat_pool = P.plateau(tabel["pooled"][MAIN][0], tabel["pooled"][MAIN][1])
    print("    pooled hold-out plateau: best %d of %d windows correct, accuracy %.4f, %d pairs "
          "reach it, %d within one window, out of %d pairs"
          % (plat_pool["benar"], plat_pool["total"], plat_pool["akurasi"],
             len(plat_pool["pada"]), len(plat_pool["dekat"]), plat_pool["grid"]))
    cv = []
    for tr, te in ((TEST_RECORDS[0], TEST_RECORDS[1]), (TEST_RECORDS[1], TEST_RECORDS[0])):
        a_cv = K.pilih_titik(hasil[tr]["fitur"][MAIN], hasil[tr]["kelas"][MAIN], k1, k2, ALIVE)["P1"]
        m_cv = K.metrik_lengkap(hasil[te]["fitur"][MAIN], hasil[te]["kelas"][MAIN],
                                a_cv["t1"], a_cv["t2"])
        cv.append(m_cv["accuracy"])
        print("    two fold, derive rule S5c on %s, test on %s: pair %.3f and %.2f, Se %.4f "
              "Sp %.4f Acc %.4f" % (tr, te, a_cv["t1"], a_cv["t2"], m_cv["sensitivity"],
                                    m_cv["specificity"], m_cv["accuracy"]))
    print("    two fold spread of the selection: minimum %.4f, maximum %.4f, range %.4f, "
          "standard deviation %.4f accuracy points"
          % (min(cv), max(cv), max(cv) - min(cv), float(np.std(cv))))
    print("  D what the headroom and the noise mean together")
    print("    the new point sits %.4f accuracy points below the optimistic bound of its own "
          "hold-out windows, and the derivation rule moves by %.4f accuracy points when it is "
          "re-derived on one test record and tested on the other. The gap between the new point "
          "and the locked point is %.4f accuracy points on the pooled hold-out, which is %s "
          "those widths."
          % (batas["acc"] - mn["accuracy"], max(cv) - min(cv),
             mn["accuracy"] - ml["accuracy"],
             "larger than" if (mn["accuracy"] - ml["accuracy"]) > max(max(cv) - min(cv),
                                                                   1.0 / 1562.0)
             else "smaller than or comparable to"))
    periksa("the headroom and the selection noise are both measured and printed",
            batas["acc"] >= mn["accuracy"] - 1e-12 and len(cv) == 2,
            "bound %.4f, new point %.4f, headroom %.4f, two fold range %.4f"
            % (batas["acc"], mn["accuracy"], batas["acc"] - mn["accuracy"], max(cv) - min(cv)))

    # ------------------------------------------------------------------ stage 8, variants
    kepala("stage 8, the definitional variants, so the two readings of the brief are not blurred")
    print("  Every row is the MARKED policy on the pooled hold-out at the locked point %.3f and "
          "%.2f. Row A is the arm. The other rows exist only to show how much the reading of the "
          "brief matters, and none of them is the answer." % (T1_LOCKED, T2_LOCKED))
    print("  %-62s %6s %8s %8s %8s %8s" % ("reading", "win", "Se", "Sp", "Acc", "miss"))
    f, k = tabel["pooled"][RAW]
    m = K.metrik_lengkap(f, k, T1_LOCKED, T2_LOCKED)
    print("  %-62s %6d %8s %8s %8s %8s"
          % ("raw series, the reference", m["windows"], sel(m["sensitivity"]),
             sel(m["specificity"]), sel(m["accuracy"]), sel(m["miss"])))
    m = K.metrik_lengkap(tabel["pooled"][MAIN][0], tabel["pooled"][MAIN][1], T1_LOCKED, T2_LOCKED)
    print("  %-62s %6d %8s %8s %8s %8s"
          % ("A the arm: false detection removed, gap removed, split off",
             m["windows"], sel(m["sensitivity"]), sel(m["specificity"]), sel(m["accuracy"]),
             sel(m["miss"])))
    fv = np.vstack([hasil[n]["varian"]["merge"][0] for n in TEST_RECORDS])
    kv = np.concatenate([hasil[n]["varian"]["merge"][1] for n in TEST_RECORDS])
    m = K.metrik_lengkap(fv, kv, T1_LOCKED, T2_LOCKED)
    print("  %-62s %6d %8s %8s %8s %8s"
          % ("B join read as a sum into the entry on the left", m["windows"],
             sel(m["sensitivity"]), sel(m["specificity"]), sel(m["accuracy"]), sel(m["miss"])))
    fw = np.vstack([hasil[n]["varian"]["ulang"][0] for n in TEST_RECORDS])
    kw = np.concatenate([hasil[n]["varian"]["ulang"][1] for n in TEST_RECORDS])
    m = K.metrik_lengkap(fw, kw, T1_LOCKED, T2_LOCKED)
    print("  %-62s %6d %8s %8s %8s %8s"
          % ("C markers re-formed from the raw series with the split rule off",
             m["windows"], sel(m["sensitivity"]), sel(m["specificity"]), sel(m["accuracy"]),
             sel(m["miss"])))
    m = K.metrik_lengkap(tabel["pooled"][COR][0], tabel["pooled"][COR][1], T1_LOCKED, T2_LOCKED)
    print("  %-62s %6d %8s %8s %8s %8s"
          % ("D the full corrected arm of uji_09_deret_terkoreksi.py", m["windows"],
             sel(m["sensitivity"]), sel(m["specificity"]), sel(m["accuracy"]), sel(m["miss"])))
    for nama in ALL_RECORDS:
        lapor("  %s markers frozen against re-formed" % nama,
              "%d of %d marks differ when the rhythm check is re-run with the split rule off, so "
              "the running average of the last eight intervals is the only place the reading "
              "changes the markers themselves" % (hasil[nama]["varian"]["tandabeda"],
                                                  hasil[nama]["mark"]))
    periksa("the variant readings are measured and are not presented as the arm",
            True,
            "rows B, C and D are printed next to row A and none of them is used to choose "
            "anything or to state the verdict of stage 6")

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
    """The honest list of what this measurement does not cover."""
    kepala("what this measurement does NOT measure, stated plainly")
    print("     1. It does not measure a physical window. The raw window is 32 raw intervals and "
          "the marked window is 32 marked entries, and because 12 intervals leave the series on "
          "the three records, a marked window can start a little later than the raw one. The two "
          "arms are the same rule over series that differ by the removed entries, not the same "
          "span of time, and no attempt is made to equalise the spans.")
    print("     2. It does not re-run the rhythm check inside the chain and does not edit "
          "rantai.py. The markers are read from the frozen stage, so the marker arm is a read "
          "only consumer of them. Row C of stage 8 measures what a re-formed check would give, "
          "but nothing is written back into the chain.")
    print("     3. It does not change any gate of the project. The frozen gates are not "
          "re-executed and no gate figure is re-scored, because nothing in the repository was "
          "changed and the marker arm is not the pipeline.")
    print("     4. It does not decide. The marker arm is measured, the locked point is printed "
          "beside it, a new point is derived for the arm by the same rule study S5c uses, and "
          "the comparison is handed over. Locking, and switching the feature layer to the "
          "marker arm, is a human decision.")
    print("     5. It does not measure the beat layer. qrs is untouched, so beat counts, beat "
          "agreement and anything computed from the real beats are unchanged by construction and "
          "are not measured here.")
    print("     6. It does not measure a per beat rate against a reference. The marked series is "
          "not a beat series, so the only measured objects are the window features and the "
          "window decision.")
    print("     7. It does not measure the other records of the data set (nsrdb/16265, "
          "mitdb/100) or any stretch outside the frozen 30 minute window. Only the three AFDB "
          "records the gates use are measured, and the two hold-out records carry 1 false "
          "detection and 42 false detections between them, so the arm's whole effect on the "
          "hold-out rests on a small number of intervals.")
    print("     8. It cannot separate the effect of removing the gaps from the effect of "
          "switching the split rule off, because the two are applied together as the brief "
          "states. On 04015 there are 3 gaps, so the gap reading is a 3 interval question there. "
          "A reader who wants the two effects separated needs a further measurement.")
    print("     9. It does not test the marker arm as a hardware or streaming change. The arm is "
          "measured as a window feature table, and the cost of the removal and of the disabled "
          "rule in the streaming chain is not measured at all.")
    print("    10. It does not report a confidence interval. The two hold-out records are not a "
          "converged sample, the selection noise of every rule here is measured in stage 7 and "
          "is of the same order as the differences reported, and no number in this file is a "
          "claim of statistical significance.")


if __name__ == "__main__":
    sys.exit(main())
