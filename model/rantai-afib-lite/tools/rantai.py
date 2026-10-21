#!/usr/bin/env python3
"""AFIB-LITE locked core of phase 6, step S1.

One state object and one streaming entry point:

    class Rantai:
        def __init__(self, semai_aktif=True, aturan_t=True, besaran="turunan")
        def langkah(self, nilai)      # one sample in, one record of that sample out

Bulk is not a second mode. Bulk is streaming driven to completion, so an adapter that
reads a whole file and an adapter that replays one sample at a time produce the same
arrays by construction.

Integer rules of the sample chain:

1. The sample chain is pure integer arithmetic. There is no floating point division and
   no floating point multiplication anywhere in it. The single exception is
   kuantisasi(), because the notebook itself converts millivolt to count in floating
   point; it is reproduced count for count.
2. The only multipliers are powers of two, which in hardware are shifts, together with
   additions and subtractions. Division by eight, by four and by two is a right shift of
   an integer, which rounds toward negative infinity, exactly as the notebook.
3. The exact rational comparisons 23/25, 29/25 and 83/50 are written in cross form, the
   same form the notebook uses, so no division appears at all.
4. Every stage function returns its output, its state and the measured range of that
   output, so the bit width check runs automatically instead of by hand.
5. The window decision layer is floating point, because the notebook is floating point
   there. Its arrays must be numerically equal, not integer.
6. Step S7 adds one block beside the locked stage 7: an integer rhythm check over the raw RR
   series, in the cross forms 83/50, 23/25 and 1/2 and with an absolute 3000 ms ceiling. It
   writes a corrected series and one mark per interval beside the locked series, and it leaves
   the locked series, the beat series and every other stage bit for bit as they were. The rules,
   the running average and the marker vocabulary are documented at the stage itself.

The reference of behaviour is model/math-equation-afib/, extracted verbatim in
acuan_fase.py. This file is an independent integer implementation. It never imports
acuan_fase, it never reads a notebook global, and it changes no arithmetic.
"""

from __future__ import annotations

import numpy as np

# =============================================================================================
# Locked constants. TASK_BRIEF.md and the phase 1 to phase 5 notebooks.
# =============================================================================================

FS_HZ = 250                      # locked sample rate, Hz
GAIN_COUNT = (2 ** 11 - 1) / 5.0  # counts per mV, plus minus 5 mV over 12 bit. Float by design.
CLAMP = 2047                     # input clamp, not 2048, so the 16 bit word cannot overflow
GESER_KIRI = 4                   # the input word is shifted left by four bits

N_A = 37                         # even index integration width
N_B = 38                         # odd index integration width
RADIUS_PUNCAK = 27               # radius of the envelope peak picker, in samples
JENDELA_F = 25                   # half window of the filtered peak, in samples
PANTUL = 50                      # refractory gate, 200 ms at 250 Hz
PITA_MS_ATAS = 360               # upper edge of the T wave band, in ms
SETENGAH_JENDELA = 18            # half window of the slope measurement, 37 samples total
GESER_AMBANG = 8                 # right shift of the derivative before squaring

DELAPAN = 8                      # length of the RR averaging queue
SEMAI_PANJANG = 32               # length of the RR history feeding the reseeding median
SEMAI_JEDA = 8                   # reseeding is allowed once per eight beats

# The band check of the notebook is (p - i_qrs) * 1000.0 / FS < 360.0. Because
# 1000 / 250 is exactly 4, that is (p - i_qrs) << 2 < 360 with no division at all.
BATAS_PITA_SAMPEL = PITA_MS_ATAS  # used as (delta << 2) < BATAS_PITA_SAMPEL


def lebar_bit(nilai):
    """Number of bits in the magnitude of an integer. 0 maps to 0."""
    v = int(nilai)
    if v < 0:
        v = -v
    return v.bit_length()


def lebar_rentang(lo, hi):
    """Smallest two's complement word width that holds the closed range [lo, hi].

    A positive peak hi needs 2**(k-1) - 1 >= hi, a negative peak lo needs
    2**(k-1) >= -lo. The magnitude form of both bounds is tested separately so the answer
    is exact and not one bit wide by accident.
    """
    atas = lebar_bit(hi) if hi >= 0 else 0
    bawah = lebar_bit(-lo - 1) if lo < 0 else 0
    return max(atas, bawah) + 1


class GarisTunda:
    """Fixed length integer delay line addressed by absolute sample index.

    The line holds the last `kapasitas` samples. A read of an index that has not arrived
    yet, or that lies before the start of the chain, returns 0. That is exactly the zero
    initial condition of the notebook filters, so no separate padding path is needed.
    """

    def __init__(self, kapasitas):
        self.kapasitas = int(kapasitas)
        self.data = [0] * self.kapasitas
        self.akhir = -1

    def dorong(self, nilai):
        """Append one sample and return its absolute index."""
        self.akhir += 1
        self.data[self.akhir % self.kapasitas] = int(nilai)
        return self.akhir

    def ambil(self, indeks):
        """Value at an absolute index, zero when the chain has not reached it yet."""
        if indeks < 0 or indeks > self.akhir:
            return 0
        if indeks <= self.akhir - self.kapasitas:
            raise IndexError("index %d has already left the delay line" % indeks)
        return self.data[indeks % self.kapasitas]

    def _potong(self, lo, hi):
        """The stored samples over the closed interval [lo, hi], oldest first."""
        if lo < 0:
            lo = 0
        if hi > self.akhir:
            hi = self.akhir
        if hi < lo:
            return []
        a = lo % self.kapasitas
        n = hi - lo + 1
        if a + n <= self.kapasitas:
            return self.data[a:a + n]
        return self.data[a:] + self.data[:a + n - self.kapasitas]

    def maks(self, lo, hi):
        """Largest value over the closed interval [lo, hi]."""
        j = self._potong(lo, hi)
        return max(j) if j else 0

    def maks_mutlak(self, lo, hi):
        """Largest absolute value over the closed interval [lo, hi]."""
        j = self._potong(lo, hi)
        if not j:
            return 0
        m = 0
        for v in j:
            if v < 0:
                v = -v
            if v > m:
                m = v
        return m


# =============================================================================================
# Stage 0: input conversion. The only floating point form of the core, and the notebook
# does it in floating point as well, so it is reproduced count for count.
# =============================================================================================

def kuantisasi(nilai):
    """Input to the chain: plus minus 5 mV, 12 significant bits, clamped, shifted left 4.

    Notebook form: np.clip(np.rint(v * GAIN_COUNT), -CLAMP, CLAMP) * (2 ** GESER_KIRI).
    Returns (masukan, state, rentang) like every other stage, with state always None
    because this stage has no memory.
    """
    hitung = int(np.clip(np.rint(float(nilai) * GAIN_COUNT), -CLAMP, CLAMP))
    masukan = hitung * (2 ** GESER_KIRI)
    return masukan, None, (masukan, masukan)


# =============================================================================================
# Stage 1: low-pass. y[i] = 2 y[i-1] - y[i-2] + x[i] - 2 x[i-6] + x[i-12], zero initial
# conditions. DC gain 36, zeros at multiples of the sample rate divided by six.
# =============================================================================================

def tapis_lp(nilai, state=None):
    """One sample of the low-pass. Returns (y, state, rentang)."""
    if state is None:
        state = {"x": [0] * 13, "y": [0, 0], "lo": None, "hi": None}
    x = state["x"]
    x.append(int(nilai))
    if len(x) > 13:
        x.pop(0)
    y = state["y"]
    yn = 2 * y[-1] - y[-2] + x[-1] - 2 * x[-7] + x[-13]
    y.append(yn)
    y.pop(0)
    if state["lo"] is None or yn < state["lo"]:
        state["lo"] = yn
    if state["hi"] is None or yn > state["hi"]:
        state["hi"] = yn
    return yn, state, (state["lo"], state["hi"])


# =============================================================================================
# Stage 2: high-pass. y[i] = 32 x[i-16] - (y[i-1] + x[i] - x[i-32]), zero initial
# conditions. Single pole at z equal to minus one.
# =============================================================================================

def tapis_hp(nilai, state=None):
    """One sample of the high-pass. Returns (y, state, rentang)."""
    if state is None:
        state = {"x": GarisTunda(33), "y": [0, 0], "lo": None, "hi": None}
    x = state["x"]
    i = x.dorong(nilai)
    y = state["y"]
    yn = 32 * x.ambil(i - 16) - (y[-1] + x.ambil(i) - x.ambil(i - 32))
    y.append(yn)
    y.pop(0)
    if state["lo"] is None or yn < state["lo"]:
        state["lo"] = yn
    if state["hi"] is None or yn > state["hi"]:
        state["hi"] = yn
    return yn, state, (state["lo"], state["hi"])


# =============================================================================================
# Stage 3: five point derivative, exact zero DC gain, group delay two samples, divided by
# eight. The division is sign symmetric, exactly as the notebook:
#   s // 8 if s >= 0 else -((-s) // 8)
# A plain right shift would round toward negative infinity and shift the series.
# =============================================================================================

def turunan(nilai, state=None):
    """One sample of the derivative. Returns (y, state, rentang)."""
    if state is None:
        state = {"x": GarisTunda(5), "lo": None, "hi": None}
    x = state["x"]
    i = x.dorong(nilai)
    s = 2 * x.ambil(i) + x.ambil(i - 1) - x.ambil(i - 3) - 2 * x.ambil(i - 4)
    yn = s // 8 if s >= 0 else -((-s) // 8)
    if state["lo"] is None or yn < state["lo"]:
        state["lo"] = yn
    if state["hi"] is None or yn > state["hi"]:
        state["hi"] = yn
    return yn, state, (state["lo"], state["hi"])


# =============================================================================================
# Stage 4: squaring. The shift is applied first, then the square, so the word stays narrow.
# =============================================================================================

def kuadrat(nilai, state=None):
    """One sample of the squaring. Input is the derivative output. Returns (ku, state, rentang)."""
    if state is None:
        state = {"lo": None, "hi": None}
    d = int(nilai) >> GESER_AMBANG
    ku = d * d
    if state["lo"] is None or ku < state["lo"]:
        state["lo"] = ku
    if state["hi"] is None or ku > state["hi"]:
        state["hi"] = ku
    return ku, state, (state["lo"], state["hi"])


# =============================================================================================
# Stage 5: moving window integration, alternating width 37 and 38 samples, the window ends
# at the index, so the start is index minus width plus one clamped to zero.
#   i even -> width 37, i odd -> width 38
# =============================================================================================

def jendela(nilai, state=None):
    """One sample of the moving window sum. Input is the squaring output.

    Returns (sel, state, rentang). The running total always covers the last 38 samples,
    and the width 37 window is that total minus the 38th sample back, the same value the
    notebook builds from the cumulative sum.
    """
    if state is None:
        state = {"x": GarisTunda(39), "jumlah": 0, "lo": None, "hi": None}
    x = state["x"]
    i = x.dorong(nilai)
    state["jumlah"] += int(nilai)
    if i >= N_B:
        state["jumlah"] -= x.ambil(i - N_B)
    sel = state["jumlah"]
    if i % 2 == 0 and i >= N_A:
        sel -= x.ambil(i - N_A)
    if state["lo"] is None or sel < state["lo"]:
        state["lo"] = sel
    if state["hi"] is None or sel > state["hi"]:
        state["hi"] = sel
    return sel, state, (state["lo"], state["hi"])


# =============================================================================================
# Peak picker of the envelope, kept as a batch function because the notebook is a batch
# function here. The streaming chain reproduces it with a fixed delay of RADIUS_PUNCAK
# samples and the same jump of RADIUS_PUNCAK samples after an accepted peak.
# =============================================================================================

def puncak_radius(sel, r=RADIUS_PUNCAK):
    """Envelope peak picker. i is a peak when sel[i] is the largest of sel[i-r..i+r] and positive.

    After an accepted peak the scan jumps r samples forward, not one.
    """
    n = sel.size
    pk = []
    i = r
    while i < n - r:
        if sel[i] >= sel[i - r:i + r + 1].max() and sel[i] > 0:
            pk.append(i)
            i += r
        else:
            i += 1
    return np.array(pk, dtype=np.int64)


# =============================================================================================
# Stage 8: T wave rule of page 234. The slope of a peak is the largest absolute value of
# the slope series over a 37 sample window centred on the peak. Inside the 360 ms band,
# two times the slope smaller than the slope of the previous QRS rejects the peak. The
# cross form 2 s < s_prev is used exactly, never a shift.
# =============================================================================================

def gelombang_t_awal(garis_besaran):
    """State of the T wave stage: the slope series and the measured range of the slope."""
    return {"garis": garis_besaran, "lo": None, "hi": None}


def gelombang_t(state, pos, delta, kem_qrs, aktif=True):
    """Slope of the peak at pos, plus the T wave verdict.

    state holds the slope series (the five point derivative output for besaran "turunan",
    the first difference of the high-pass output for besaran "beda").
    delta is the distance in samples to the previous QRS, or None when there is none.
    aktif is the aturan_t switch. The slope is measured always, because the ratio pools
    are collected whether the rule is on or off.

    Returns (kem, dalam_pita, ditolak, rentang).
    """
    garis = state["garis"]
    lo = pos - SETENGAH_JENDELA
    if lo < 0:
        lo = 0
    kem = garis.maks_mutlak(lo, pos + SETENGAH_JENDELA)
    if state["lo"] is None or kem < state["lo"]:
        state["lo"] = kem
    if state["hi"] is None or kem > state["hi"]:
        state["hi"] = kem
    dalam_pita = bool(aktif) and delta is not None and kem_qrs is not None \
        and (delta << 2) < BATAS_PITA_SAMPEL
    ditolak = bool(dalam_pita) and (2 * kem < kem_qrs)
    return kem, dalam_pita, ditolak, (state["lo"], state["hi"])


# =============================================================================================
# Stage 7: RR intervals. Equation (24) to (29) plus the P4-5 reseeding rule. Integer only,
# the exact band 23/25 to 29/25 of the second average, queue of eight, first average from
# a right shift by three, reseeding from the median of the last 32 intervals, at most once
# per eight beats.
# =============================================================================================

def rr_awal(semai_aktif=True):
    """State of the RR stage."""
    return {"deret": [], "antre": [], "riwayat": [], "gagal": 0, "jeda": SEMAI_JEDA,
            "semai": 0, "menyala": 0, "ra1": 0, "ra2": 0, "pembilang": 0, "penyebut": 0,
            "semai_aktif": bool(semai_aktif), "baris": [], "lo": None, "hi": None,
            "irama": rr_rhythm_awal()}


def _dalam_batas(x, pembilang, penyebut):
    """Exact band of the notebook: 25 * penyebut * x >= 23 * pembilang and <= 29 * pembilang."""
    return (25 * penyebut * x >= 23 * pembilang) and (25 * penyebut * x <= 29 * pembilang)


def median_bulat(nilai):
    """Median of a list of integers, truncated toward zero, as int(np.median(...)) does."""
    v = sorted(int(x) for x in nilai)
    m = len(v)
    if m == 0:
        return 0
    if m % 2:
        return v[m // 2]
    return (v[m // 2 - 1] + v[m // 2]) // 2


def rr(nilai_ms, state=None):
    """One beat of the RR stage. Returns (menyala, disemai, state, rentang).

    rentang is the measured (min, max) of the intervals fed to the stage. The internal
    averages are readable from the state: ra1, ra2, pembilang, penyebut, semai.
    """
    if state is None:
        state = rr_awal()
    x = int(nilai_ms)
    deret = state["deret"]
    deret.append(x)
    if len(deret) > DELAPAN:
        deret.pop(0)
    riwayat = state["riwayat"]
    riwayat.append(x)
    if len(riwayat) > SEMAI_PANJANG:
        riwayat.pop(0)
    if state["lo"] is None or x < state["lo"]:
        state["lo"] = x
    if state["hi"] is None or x > state["hi"]:
        state["hi"] = x
    rentang = (state["lo"], state["hi"])
    if len(deret) < DELAPAN:
        return 0, 0, state, rentang
    ra1 = sum(deret) >> 3
    pembilang = sum(state["antre"])
    penyebut = len(state["antre"])
    if penyebut > 0:
        acuan, acuan_penyebut = pembilang, penyebut
    else:
        acuan, acuan_penyebut = ra1, 1
    lolos = _dalam_batas(x, acuan, acuan_penyebut)
    if lolos:
        state["gagal"] = 0
    else:
        state["gagal"] += 1
    state["jeda"] += 1
    disemai = 0
    if state["semai_aktif"] and state["gagal"] >= DELAPAN and state["jeda"] >= SEMAI_JEDA:
        tengah = median_bulat(riwayat)
        state["antre"] = [tengah] * DELAPAN
        state["semai"] += 1
        disemai = 1
        state["gagal"] = 0
        state["jeda"] = 0
    elif lolos:
        state["antre"].append(x)
        if len(state["antre"]) > DELAPAN:
            state["antre"].pop(0)
    pembilang = sum(state["antre"])
    penyebut = len(state["antre"])
    ra2 = pembilang // penyebut if penyebut > 0 else ra1
    state["ra1"] = ra1
    state["ra2"] = ra2
    state["pembilang"] = pembilang
    state["penyebut"] = penyebut
    menyala = 0
    if penyebut == DELAPAN:
        menyala = 1
        for r in deret:
            if not _dalam_batas(r, pembilang, penyebut):
                menyala = 0
                break
    state["menyala"] = menyala
    state["baris"].append((ra1, ra2, len(state["antre"]), menyala, disemai, len(riwayat)))
    return menyala, disemai, state, rentang


# =============================================================================================
# Stage 7b: the integer rhythm check over the raw RR series. This block is step S7, the one
# change of that step.
#
# The longest interval the locked stage above produces on recording 04015 is 51064 ms, 51
# seconds, between the beats at sample 71399 and sample 84165, 285.60 s to 336.66 s. The root
# cause was measured before this block was written, and the numbers are in the open correction
# note. In short: the lead ECG1 of 04015, the only lead this chain consumes, is in contact loss
# over that stretch. Its amplitude per second collapses to 0.10 to 1.09 mV against a record
# median of 1.730 mV, while the other lead of the same record, ECG2, keeps 1.0 to 4.4 mV, so the
# heart keeps beating and the lead does not carry it. An independent detector, the same library
# the frozen reference series came from, reports exactly one beat inside those 51 seconds. The
# envelope this chain measures there never comes within a factor of sixteen of the second
# threshold, so the locked detection path is not the cause, there is nothing to detect in that
# lead, and nothing may be invented.
#
# The check below therefore does not touch detection and does not touch the locked series. It
# reads the raw interval series the stage above already produced, and it adds, beside it, one
# corrected series and one mark per interval, in exact integer arithmetic only:
#
#   1. interval above 83/50 of the running average is a missed beat. The comparison is the cross
#      form 50 * x > 83 * reference, the form the phase 4 notebook already writes for the missed
#      boundary, so no division appears at all. The interval becomes two exact halves, first is
#      x >> 1 and second is x - first, so the two halves sum to x and no millisecond is lost or
#      invented.
#   2. interval below 1/2 of the running average is a false detection. The exact cross form
#      2 * x < reference removes it, and it enters no average.
#   3. an interval that the missed beat rule catches and that is also over the absolute ceiling
#      of 3000 ms is a recording gap, not a missed beat. It is marked as a gap, it stays in the
#      corrected series as one entry instead of being split, and it is kept out of the running
#      average.
#
# The running average is the integer median of the last RR_RHYTHM_WINDOW corrected intervals,
# taken from median_bulat above, the helper this file already carries. A median is chosen over a
# mean because a mean is dragged by exactly the outlier this block exists to repair, and because
# the file already holds an exact integer median. The window length is DELAPAN, the length the
# locked stage above already uses for its own RR average.
#
# The locked series is not edited, so the frozen fixture keeps its meaning as the oracle of the
# old behaviour, and a downstream window can tell a corrected interval from a raw one by reading
# the marks:
#
#   RR_MARK_KEEP   0  the raw interval was kept as it came
#   RR_MARK_SPLIT  1  the raw interval was a missed beat and became two exact halves
#   RR_MARK_DROP   2  the raw interval was a false detection and produced no entry at all
#   RR_MARK_GAP    3  the raw interval was a recording gap, marked and kept out of the average
#
# rr_mark_raw carries one entry per raw interval of state["rr"], rr_mark_corrected one entry per
# corrected interval of rr_corrected, so a reader can line the two series up without any
# floating point. Every value in this block is a Python integer, and every ratio is a cross
# multiplication.
# =============================================================================================

RR_GAP_CEILING_MS = 3000        # absolute ceiling of a plausible interval, milliseconds
RR_RHYTHM_WINDOW = DELAPAN      # running window of the rhythm check, eight corrected intervals
RR_MISS_NUM = 83                # the missed beat fraction 83/50 in cross form, no division
RR_MISS_DEN = 50
RR_MARK_KEEP = 0                # the raw interval was kept as it came
RR_MARK_SPLIT = 1               # the raw interval was a missed beat and became two halves
RR_MARK_DROP = 2                # the raw interval was a false detection and was dropped
RR_MARK_GAP = 3                 # the raw interval was a recording gap over the ceiling


def rr_rhythm_awal():
    """State of the rhythm check. Integer only, no floating point anywhere."""
    return {"history": [], "corrected": [], "flags": [], "marks": [],
            "raw": 0, "kept": 0, "split": 0, "dropped": 0, "gap": 0}


def _rr_push_window(history, nilai):
    """Append one accepted interval to the running window and drop the oldest over the length."""
    history.append(int(nilai))
    if len(history) > RR_RHYTHM_WINDOW:
        del history[:len(history) - RR_RHYTHM_WINDOW]


def rr_rhythm(x, state):
    """One raw interval through the integer rhythm check. Returns (mark, state).

    mark is RR_MARK_KEEP, RR_MARK_SPLIT, RR_MARK_DROP or RR_MARK_GAP for this one interval.
    The corrected series and its own marks are readable from the state afterwards. Nothing here
    divides, and nothing here uses floating point.
    """
    x = int(x)
    state["raw"] += 1
    reference = median_bulat(state["history"])
    if reference > 0 and (2 * x) < reference:
        # a false detection: below one half of the running average
        state["marks"].append(RR_MARK_DROP)
        state["dropped"] += 1
        return RR_MARK_DROP, state
    if reference > 0 and (RR_MISS_DEN * x) > (RR_MISS_NUM * reference):
        # above the missed beat boundary, 83/50 of the running average
        if x > RR_GAP_CEILING_MS:
            # over the absolute ceiling: a recording gap, marked, never split
            state["corrected"].append(x)
            state["flags"].append(RR_MARK_GAP)
            state["marks"].append(RR_MARK_GAP)
            state["gap"] += 1
            return RR_MARK_GAP, state
        first = x >> 1
        second = x - first
        state["corrected"].append(first)
        state["flags"].append(RR_MARK_SPLIT)
        state["corrected"].append(second)
        state["flags"].append(RR_MARK_SPLIT)
        state["marks"].append(RR_MARK_SPLIT)
        state["split"] += 1
        _rr_push_window(state["history"], first)
        _rr_push_window(state["history"], second)
        return RR_MARK_SPLIT, state
    state["corrected"].append(x)
    state["flags"].append(RR_MARK_KEEP)
    state["marks"].append(RR_MARK_KEEP)
    state["kept"] += 1
    _rr_push_window(state["history"], x)
    return RR_MARK_KEEP, state


# =============================================================================================
# Search back. Only on a peak that did not pass. The limit is 83/50 times the second
# average, written in cross form so no division appears. The candidate is the largest
# envelope value between the last QRS and this peak whose value is above the second
# threshold and not above the first. Its update uses a right shift by two, not three.
# =============================================================================================

def search_back(state, pos, i_puncak, i1, i2):
    """Returns (kandidat, rentang) with kandidat None or (pos, nilai, pk_f, kem, indeks)."""
    i_qrs = state["i_qrs"]
    if i_qrs is None:
        return None, (state["lo_sb"], state["hi_sb"])
    pembilang = state["tahap_rr"]["pembilang"]
    penyebut = state["tahap_rr"]["penyebut"]
    ra1 = state["tahap_rr"]["ra1"]
    delta = pos - i_qrs
    # 83.0 * ra2 / 50.0 with ra2 = pembilang / penyebut, cross multiplied:
    #   delta * 4 > 83 * pembilang / (50 * penyebut)  <=>  200 * delta * penyebut > 83 * pembilang
    if penyebut > 0:
        aktif = 200 * delta * penyebut > 83 * pembilang
    elif ra1 > 0:
        aktif = 200 * delta > 83 * ra1
    else:
        aktif = False
    if not aktif:
        return None, (state["lo_sb"], state["hi_sb"])
    best = None
    a = state["i_qrs_puncak"] + 1
    puncak = state["puncak"]
    for j in range(a, i_puncak + 1):
        v = state["puncak_nilai"][j]
        if i2 < v <= i1 and (best is None or v > best[1]):
            best = (puncak[j], v, state["puncak_terfilter"][j], state["puncak_kemiringan"][j], j)
    if best is not None:
        if state["lo_sb"] is None or best[1] < state["lo_sb"]:
            state["lo_sb"] = best[1]
        if state["hi_sb"] is None or best[1] > state["hi_sb"]:
            state["hi_sb"] = best[1]
    return best, (state["lo_sb"], state["hi_sb"])


# =============================================================================================
# Stage 6: adaptive threshold, equations (12) to (23). SPKI, NPKI, SPKF and NPKF start from
# zero and warm up by themselves. The difference form with a right shift by two, the second
# threshold from a right shift by one, the refractory gate of 50 samples, and the update
# shift by three.
# =============================================================================================

def ambang_awal(semai_aktif=True, aturan_t=True, puncak=None):
    """State of the threshold stage."""
    return {"spki": 0, "npki": 0, "spkf": 0, "npkf": 0,
            "i_qrs": None, "i_qrs_puncak": None, "kem_qrs": None,
            "calon_kedua": 0, "cari_mundur": 0, "diperiksa": 0, "ditolak": 0,
            "diterima_pita": 0, "berisiko": 0, "penanda": 0, "langkah": 0,
            "qrs": [], "rr": [], "rasio_pita": [], "rasio_qrs": [],
            "puncak": puncak if puncak is not None else [],
            "puncak_nilai": [], "puncak_terfilter": [], "puncak_kemiringan": [],
            "tahap_rr": rr_awal(semai_aktif=semai_aktif),
            "aturan_t": bool(aturan_t),
            "lo_i1": None, "hi_i1": None, "lo_sb": None, "hi_sb": None}


def _catat(state, pos, i_puncak):
    """Record one QRS, produce its RR interval, and advance the RR stage when it is in band."""
    qrs = state["qrs"]
    qrs.append(pos)
    state["i_qrs"] = pos
    state["i_qrs_puncak"] = i_puncak
    if len(qrs) >= 2:
        # (qrs[-1] - qrs[-2]) * 1000 // 250, and 1000 / 250 is exactly 4.
        rr_ms = (qrs[-1] - qrs[-2]) << 2
        state["rr"].append(rr_ms)
        # Step S7: the integer rhythm check reads the same raw interval and writes its own
        # corrected series and marks beside it. It never edits the raw series, so the frozen
        # fixture keeps its meaning and the locked stage keeps its arithmetic.
        _mark, state["tahap_rr"]["irama"] = rr_rhythm(rr_ms, state["tahap_rr"]["irama"])
        if 250 <= rr_ms <= 2000:
            menyala, _disemai, tahap, _r = rr(rr_ms, state["tahap_rr"])
            state["tahap_rr"] = tahap
            state["penanda"] += menyala
            state["langkah"] += 1


def ambang(state, pos, i_puncak, pv, pk_f, state_t):
    """One envelope peak through the adaptive threshold stage.

    Returns (keputusan, state, rentang) with rentang the measured (min, max) of the first
    threshold I1. keputusan is a dict with the verdict of this peak.
    """
    spki = state["spki"]
    npki = state["npki"]
    spkf = state["spkf"]
    npkf = state["npkf"]
    i1 = npki + ((spki - npki) >> 2)
    f1 = npkf + ((spkf - npkf) >> 2)
    i2 = i1 >> 1
    if state["lo_i1"] is None or i1 < state["lo_i1"]:
        state["lo_i1"] = i1
    if state["hi_i1"] is None or i1 > state["hi_i1"]:
        state["hi_i1"] = i1
    sinyal = pv > i1
    i_qrs = state["i_qrs"]
    delta = None if i_qrs is None else pos - i_qrs
    if sinyal and delta is not None and delta < PANTUL:
        sinyal = False                                  # refractory gate, 200 ms
    state["puncak_terfilter"].append(pk_f)
    kem, dalam_pita, ditolak_t, _r_kem = gelombang_t(
        state_t, pos, delta, state["kem_qrs"], aktif=state["aturan_t"])
    state["puncak_kemiringan"].append(kem)
    if sinyal and dalam_pita:
        state["diperiksa"] += 1
        state["rasio_pita"].append(
            float(kem) / float(state["kem_qrs"]) if state["kem_qrs"] > 0 else float("inf"))
        if ditolak_t:
            sinyal = False
            state["ditolak"] += 1
        else:
            state["diterima_pita"] += 1
    if not sinyal and pv > i2:
        state["calon_kedua"] += 1
    if sinyal:
        state["spki"] = spki + ((pv - spki) >> 3)
        if pk_f > f1:
            state["spkf"] = spkf + ((pk_f - spkf) >> 3)
        else:
            state["npkf"] = npkf + ((pk_f - npkf) >> 3)
        if delta is not None and state["kem_qrs"] is not None:
            if (delta << 2) < BATAS_PITA_SAMPEL:
                state["rasio_qrs"].append(
                    float(kem) / float(state["kem_qrs"]) if state["kem_qrs"] > 0
                    else float("inf"))
                if state["kem_qrs"] > 0 and (2 * kem < state["kem_qrs"]):
                    state["berisiko"] += 1
        state["kem_qrs"] = kem
        _catat(state, pos, i_puncak)
        return dict(sinyal=True, ditolak_t=False, cari_mundur=False,
                    kem=kem, dalam_pita=dalam_pita), state, (state["lo_i1"], state["hi_i1"])
    state["npki"] = npki + ((pv - npki) >> 3)
    state["npkf"] = npkf + ((pk_f - npkf) >> 3)
    kandidat, _r_sb = search_back(state, pos, i_puncak, i1, i2)
    if kandidat is not None:
        sp, v, vf, vk, j = kandidat
        state["cari_mundur"] += 1
        if vf > f1:
            state["spkf"] = spkf + ((vf - spkf) >> 2)
        else:
            state["npkf"] = state["npkf"] + ((vf - state["npkf"]) >> 2)
        state["spki"] = spki + ((v - spki) >> 2)
        state["kem_qrs"] = vk
        _catat(state, sp, j)
        return dict(sinyal=False, ditolak_t=ditolak_t, cari_mundur=True,
                    kem=kem, dalam_pita=dalam_pita), state, (state["lo_i1"], state["hi_i1"])
    return dict(sinyal=False, ditolak_t=ditolak_t, cari_mundur=False,
                kem=kem, dalam_pita=dalam_pita), state, (state["lo_i1"], state["hi_i1"])


# =============================================================================================
# The window decision layer. Floating point, because the notebook is floating point here.
# Only the windows that are entirely one class, AFIB or N, and whose RR interval lies
# between 200 and 3000 ms, are kept.
#
# The interval series the window features are built from is chosen by the SUMBER switch.
#
#   SUMBER_BERPENANDA  the new active behaviour. The features are built from the marked
#                      interval series instead of the raw one, with the marker policy
#                      uji_berpenanda.py states and measures, and not with a second one:
#
#                        mark 0 KEEP    the interval is kept exactly as it came.
#                        mark 1 SPLIT   INERT. The missed beat rule stays off, so a long
#                                       interval stays whole and is neither halved nor
#                                       discarded. Atrial fibrillation is irregular by
#                                       construction, so an interval above 83/50 of the
#                                       running average is the normal state of the rhythm and
#                                       not evidence of a missed beat.
#                        mark 2 DROP    the false detection leaves the series, so the intervals
#                                       to its left and to its right become adjacent entries,
#                                       the join, with no duration invented and no halving.
#                        mark 3 GAP     the recording gap leaves the window interval statistics
#                                       completely, so no window mean, no window RMSSD, no
#                                       pNN50 and no window entropy is drawn from a stretch
#                                       where the lead carries no signal.
#
#   SUMBER_MENTAH      the raw interval series exactly as the pipeline consumed it before this
#                      switch existed, bit for bit.
#
# WHAT THE SWITCH DOES NOT TOUCH. The qrs series, every integer stage including the adaptive
# threshold and the stage 7b marking, and every array the fixture stores. The marks read here
# are the marks the frozen stage 7b produced; when a caller does not carry them they are
# restated from the same raw interval series with the same integer rhythm check, so the marking
# itself is never edited by this layer, it is only read.
# =============================================================================================

JENDELA_DENYUT = 32
LANGKAH_DENYUT = 4
AMBANG_LAMA_RASIO = 0.21
AMBANG_LAMA_ENTROPI = 0.70

SUMBER_MENTAH = "mentah"
SUMBER_BERPENANDA = "berpenanda"
SUMBER = (SUMBER_MENTAH, SUMBER_BERPENANDA)


def seri_berpenanda(rr_ms, mark):
    """The marked interval series, the policy uji_berpenanda.py states and measures.

    rr_ms  the raw interval series in ms, one entry per raw interval
    mark   the stage 7b mark of every raw interval, one entry per raw interval
    Returns (nilai, sumber) with nilai the surviving entries in ms and sumber the index of the
    raw interval every surviving entry came from, so the class axis of the series can be built
    by indexing the raw class array with sumber and no second rule is needed.

    A mark 0 and a mark 1 entry are both kept whole. A mark 2 and a mark 3 entry leave the
    series completely. Nothing is halved, nothing is invented, and no duration is changed.
    """
    rr = np.asarray(rr_ms, float)
    mk = np.asarray(mark)
    if mk.size != rr.size:
        raise ValueError("the mark series has %d entries for %d raw intervals"
                         % (mk.size, rr.size))
    simpan = (mk == RR_MARK_KEEP) | (mk == RR_MARK_SPLIT)
    sumber = np.flatnonzero(simpan).astype(np.int64)
    return rr[sumber], sumber


def tanda_deret(rr_ms):
    """The stage 7b marks of a raw interval series, read back with the frozen integer check.

    This calls the frozen rr_rhythm over the series and returns the marks it produced, one per
    raw interval. It is the same arithmetic the chain runs inside its own stage 7b, so the marks
    a caller does not carry are restated and not redefined.
    """
    state = rr_rhythm_awal()
    for nilai in np.asarray(rr_ms, float).reshape(-1):
        _mark, state = rr_rhythm(int(nilai), state)
    return np.asarray(state["marks"], dtype=np.int64)


def kumpulkan_jendela(puncak, lab, sumber=SUMBER_BERPENANDA, mark=None):
    """Windows of 32 beats with a step of 4 beats, one class each, RR inside 200 to 3000 ms.

    sumber chooses the interval series the windows are built from, see the block comment above.
    mark carries the stage 7b mark of every raw interval when the caller has it; when it is
    absent and sumber is berpenanda the marks are restated from the same raw series by
    tanda_deret. With sumber mentah the mark argument is ignored entirely.
    """
    if sumber not in SUMBER:
        raise ValueError("unknown window interval series: %r" % (sumber,))
    rr = np.diff(puncak) / FS_HZ * 1000.0
    bl = lab[puncak[1:]]
    if sumber == SUMBER_BERPENANDA:
        tanda = tanda_deret(rr) if mark is None else np.asarray(mark)
        rr, sumber_interval = seri_berpenanda(rr, tanda)
        bl = bl[sumber_interval]
    baris = []
    for i in range(0, rr.size - JENDELA_DENYUT, LANGKAH_DENYUT):
        seg = rr[i:i + JENDELA_DENYUT]
        u = np.unique(bl[i:i + JENDELA_DENYUT])
        if u.size != 1 or u[0] not in ("AFIB", "N"):
            continue
        if seg.min() < 200 or seg.max() > 3000:
            continue
        baris.append((u[0], *fitur_irama(seg)))
    arr = np.array([[b[1], b[2], b[3], b[4]] for b in baris], float)
    cls = np.array([b[0] for b in baris])
    return arr, cls


def kisi_ambang():
    """Threshold grid of the phase 5 decision layer, copied from the notebook."""
    return np.arange(0.00, 0.62, 0.005), np.arange(0.02, 0.99, 0.01)


def label_irama(sampel, catatan, n):
    """Rhythm label per sample, built from the annotation, exactly as the notebook does."""
    lab = np.array([""] * n, dtype=object)
    cur = ""
    for t, nt in zip(sampel, catatan):
        if nt:
            s = nt.strip()
            if s.startswith("("):
                cur = s.strip("(").strip(")")
        if 0 <= t < n:
            lab[t:] = cur
    return lab


def fitur_irama(rr_ms):
    """Four features of one window: RMSSD, RMSSD divided by the mean RR, pNN50, entropy / 4."""
    rr = np.asarray(rr_ms, float)
    d = np.diff(rr)
    rmssd = float(np.sqrt(np.mean(d ** 2)))
    pnn50 = float(np.mean(np.abs(d) > 50.0))
    s = np.sort(rr)
    core = s[8:-8] if s.size > 20 else s
    edges = np.linspace(core.min(), core.max(), 17)
    edges[-1] += 1e-9
    cnt, _ = np.histogram(core, bins=edges)
    p = cnt[cnt > 0] / cnt.sum()
    h = float(-(p * np.log2(p)).sum())
    return rmssd, rmssd / rr.mean(), pnn50, h / 4.0


def auc_rank(x, y):
    """Rank AUC, kept for the report of the reference series."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    r = np.argsort(np.concatenate([x, y])).argsort() + 1
    return float((r[:x.size].sum() - x.size * (x.size + 1) / 2) / (x.size * y.size))


def nilai_gerbang(arr, cls, t1, t2):
    """AND gate: ratio above t1 and entropy above t2."""
    af = cls == "AFIB"
    p = (arr[:, 1] > t1) & (arr[:, 3] > t2)
    return dict(kepekaan=float(p[af].mean()), spesifisitas=float(1.0 - p[~af].mean()),
                akurasi=float((p == af).mean()), jendela=int(cls.size),
                afib=int(af.sum()), n=int((~af).sum()))


def turunkan_ambang(arr, cls, kisi1, kisi2):
    """Derive the threshold pair: largest accuracy, then largest Youden, then smallest threshold."""
    af = cls == "AFIB"
    seri = []
    for t1 in kisi1:
        m1 = arr[:, 1] > t1
        for t2 in kisi2:
            p = m1 & (arr[:, 3] > t2)
            se = float(p[af].mean())
            sp = float(1.0 - p[~af].mean())
            acc = float((p == af).mean())
            youden = se + sp - 1.0
            seri.append((acc, youden, float(t1), float(t2), se, sp))
    acc_max = max(s[0] for s in seri)
    seri = [s for s in seri if s[0] >= acc_max - 1e-12]
    seri.sort(key=lambda s: (-s[1], s[2], s[3]))
    acc, youden, t1, t2, se, sp = seri[0]
    return dict(t1=t1, t2=t2, kepekaan=se, spesifisitas=sp, akurasi=acc, youden=youden,
                jendela=int(cls.size), afib=int(af.sum()), n=int((~af).sum()),
                seri=len(seri), t2_min=min(s[3] for s in seri),
                t2_max=max(s[3] for s in seri), t1_max=max(s[2] for s in seri))


# =============================================================================================
# The state machine. One object, one entry point.
# =============================================================================================

class Rantai:
    """The locked integer chain, streaming.

    semai_aktif  P4-5 reseeding rule of the RR stage, on by default
    aturan_t     T wave rule of page 234, on by default
    besaran      slope series, "turunan" (five point derivative) or "beda" (first
                 difference of the high-pass output)
    """

    KOLOM = ("masukan16", "lp", "hp", "turunan", "kuadrat", "jendela")

    def __init__(self, semai_aktif=True, aturan_t=True, besaran="turunan"):
        if besaran not in ("turunan", "beda"):
            raise ValueError("unknown slope series: %r" % (besaran,))
        self.semai_aktif = bool(semai_aktif)
        self.aturan_t = bool(aturan_t)
        self.besaran = besaran

        self.n = 0
        self.st_lp = None
        self.st_hp = None
        self.st_tur = None
        self.st_ku = None
        self.st_sel = None

        self.ring_hp = GarisTunda(64)
        self.ring_besaran = GarisTunda(64)
        self.ring_sel = GarisTunda(64)
        self.hp_lalu = 0

        self.kolom = {k: [] for k in self.KOLOM}
        self.puncak = []
        self.scan = RADIUS_PUNCAK
        self.st_ambang = ambang_awal(semai_aktif=self.semai_aktif, aturan_t=self.aturan_t,
                                     puncak=self.puncak)
        self.st_t = gelombang_t_awal(self.ring_besaran)

        self.rentang = {}
        self.rentang_masukan = None

    # -----------------------------------------------------------------------------------------
    def langkah(self, nilai):
        """One sample in, one record of that sample out."""
        n = self.n
        masukan, _, _r = kuantisasi(nilai)
        if self.rentang_masukan is None:
            self.rentang_masukan = (masukan, masukan)
        elif masukan < self.rentang_masukan[0]:
            self.rentang_masukan = (masukan, self.rentang_masukan[1])
        elif masukan > self.rentang_masukan[1]:
            self.rentang_masukan = (self.rentang_masukan[0], masukan)
        lp, self.st_lp, r_lp = tapis_lp(masukan, self.st_lp)
        hp, self.st_hp, r_hp = tapis_hp(lp, self.st_hp)
        tur, self.st_tur, r_tur = turunan(hp, self.st_tur)
        ku, self.st_ku, r_ku = kuadrat(tur, self.st_ku)
        sel, self.st_sel, r_sel = jendela(ku, self.st_sel)

        self.ring_hp.dorong(hp)
        if self.besaran == "turunan":
            self.ring_besaran.dorong(tur)
        else:
            self.ring_besaran.dorong(0 if n == 0 else hp - self.hp_lalu)
        self.hp_lalu = hp
        self.ring_sel.dorong(sel)

        kolom = self.kolom
        kolom["masukan16"].append(masukan)
        kolom["lp"].append(lp)
        kolom["hp"].append(hp)
        kolom["turunan"].append(tur)
        kolom["kuadrat"].append(ku)
        kolom["jendela"].append(sel)
        self.rentang = {"masukan16": self.rentang_masukan, "lp": r_lp, "hp": r_hp,
                        "turunan": r_tur, "kuadrat": r_ku, "jendela": r_sel}

        # Envelope peak picker, same rule as puncak_radius with a fixed delay of RADIUS_PUNCAK.
        puncak_baru = []
        scan = self.scan
        ring = self.ring_sel
        while scan + RADIUS_PUNCAK <= n:
            v = ring.ambil(scan)
            if v > 0 and v >= ring.maks(scan - RADIUS_PUNCAK, scan + RADIUS_PUNCAK):
                puncak_baru.append(scan)
                scan += RADIUS_PUNCAK
            else:
                scan += 1
        self.scan = scan

        qrs_baru = []
        keputusan = []
        for pos in puncak_baru:
            i_puncak = len(self.puncak)
            self.puncak.append(pos)
            pv = ring.ambil(pos)
            pk_f = self.ring_hp.maks_mutlak(pos - JENDELA_F, pos + JENDELA_F)
            state = self.st_ambang
            state["puncak_nilai"].append(pv)
            sebelum = len(state["qrs"])
            kep, self.st_ambang, r_amb = ambang(state, pos, i_puncak, pv, pk_f, self.st_t)
            self.rentang["ambang"] = r_amb
            keputusan.append((pos, kep))
            if len(self.st_ambang["qrs"]) > sebelum:
                qrs_baru.append(self.st_ambang["qrs"][-1])

        self.n += 1
        return {"n": n, "masukan16": masukan, "lp": lp, "hp": hp, "turunan": tur,
                "kuadrat": ku, "jendela": sel, "puncak": puncak_baru,
                "qrs": qrs_baru, "keputusan": keputusan}

    # -----------------------------------------------------------------------------------------
    def hasil(self):
        """Every array this run produced, keyed like the frozen fixture."""
        st = self.st_ambang
        baris = np.array(st["tahap_rr"]["baris"], dtype=np.int64)
        if baris.size == 0:
            baris = np.zeros((0, 6), dtype=np.int64)
        return {
            "masukan16": np.array(self.kolom["masukan16"], dtype=np.int64),
            "lp": np.array(self.kolom["lp"], dtype=np.int64),
            "hp": np.array(self.kolom["hp"], dtype=np.int64),
            "turunan": np.array(self.kolom["turunan"], dtype=np.int64),
            "kuadrat": np.array(self.kolom["kuadrat"], dtype=np.int64),
            "jendela": np.array(self.kolom["jendela"], dtype=np.int64),
            "puncak": np.array(self.puncak, dtype=np.int64),
            "qrs": np.array(st["qrs"], dtype=np.int64),
            "rr": np.array(st["rr"], dtype=np.int64),
            "rr_corrected": np.array(st["tahap_rr"]["irama"]["corrected"], dtype=np.int64),
            "rr_mark_corrected": np.array(st["tahap_rr"]["irama"]["flags"], dtype=np.int64),
            "rr_mark_raw": np.array(st["tahap_rr"]["irama"]["marks"], dtype=np.int64),
            "rr_rhythm_state": np.array([st["tahap_rr"]["irama"]["raw"],
                                         st["tahap_rr"]["irama"]["kept"],
                                         st["tahap_rr"]["irama"]["split"],
                                         st["tahap_rr"]["irama"]["dropped"],
                                         st["tahap_rr"]["irama"]["gap"]], dtype=np.int64),
            "rr_average1": baris[:, 0],
            "rr_average2": baris[:, 1],
            "rr_antre_panjang": baris[:, 2],
            "penanda": baris[:, 3],
            "rr_disemai": baris[:, 4],
            "rr_riwayat_panjang": baris[:, 5],
            "rr_menyala_akhir": np.array(int(st["tahap_rr"]["menyala"]), dtype=np.int64),
            "ambang_kemiringan_puncak": np.array(st["puncak_kemiringan"], dtype=np.int64),
            "ambang_puncak_terfilter": np.array(st["puncak_terfilter"], dtype=np.int64),
            "ambang_state": np.array([st["calon_kedua"], st["cari_mundur"], st["diperiksa"],
                                      st["ditolak"], st["diterima_pita"], st["berisiko"],
                                      st["tahap_rr"]["semai"], st["penanda"], st["langkah"]],
                                     dtype=np.int64),
            "rasio_pita": np.array(st["rasio_pita"], dtype=float),
            "rasio_qrs": np.array(st["rasio_qrs"], dtype=float),
        }

    def rentang_terukur(self):
        """Measured range and bit width of every stage output of this run."""
        st = self.st_ambang
        out = {k: self.rentang.get(k) for k in ("masukan16", "lp", "hp", "turunan",
                                                "kuadrat", "jendela")}
        out["ambang"] = (st["lo_i1"], st["hi_i1"])
        out["search_back"] = (st["lo_sb"], st["hi_sb"])
        out["rr"] = (st["tahap_rr"]["lo"], st["tahap_rr"]["hi"])
        out["gelombang_t"] = (self.st_t["lo"], self.st_t["hi"])
        return out

    def lebar(self):
        """Bit width of the measured range of every stage, for the hardware budget.

        The value is the smallest two's complement word that holds the measured range.
        A range that cannot be negative also fits in the unsigned width, which is reported
        separately by lebar_tanpa_tanda().
        """
        out = {}
        for k, r in self.rentang_terukur().items():
            if r is None or r[0] is None:
                out[k] = None
                continue
            out[k] = lebar_rentang(r[0], r[1])
        return out

    def lebar_tanpa_tanda(self):
        """Unsigned width of every non negative stage range, None for a signed range."""
        out = {}
        for k, r in self.rentang_terukur().items():
            if r is None or r[0] is None:
                out[k] = None
                continue
            elif r[0] >= 0:
                out[k] = lebar_bit(r[1])
            else:
                out[k] = None
        return out

# Wrapper for notebook pipeline
def rantai_process(signal, fs):
    """Process full signal using Rantai class. Returns dict with 'ratio' and 'entropy' keys.
    Ratio from rasio_pita, entropy from rasio_qrs (first element if arrays).
    """
    import numpy as np
    r = Rantai()
    for s in signal:
        r.langkah(s)
    out = r.hasil()
    ratio_arr = out.get('rasio_pita')
    entropy_arr = out.get('rasio_qrs')
    ratio = float(ratio_arr[0]) if isinstance(ratio_arr, np.ndarray) and ratio_arr.size else None
    entropy = float(entropy_arr[0]) if isinstance(entropy_arr, np.ndarray) and entropy_arr.size else None
    return {'ratio': ratio, 'entropy': entropy}

