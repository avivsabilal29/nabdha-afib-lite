#!/usr/bin/env python3
"""AFIB-LITE quantization calculator and measured bit-width table for the RTL port.

The tool consumes the two integer measurement views of the frozen chain:

    rantai.Rantai.rentang_terukur()   the measured (min, max) of every stage output
    rantai.Rantai.lebar()             two's complement width of every measured range
    rantai.Rantai.lebar_tanpa_tanda() unsigned width of every non negative range

and prints one arithmetic node table per recording:

    node | measured range on the test record | two's complement width needed | Q format
    (binary point position) | saturation point | rounding rule in force at that node

EVERY NUMBER HAS ONE OF THREE SOURCES, AND THE TOOL NEVER GUESSES

  measured   the range the frozen chain really produced over the recording it was run on
  operator   the exact integer or power-of-two operator of the node applied to the measured
             range of its input, evaluated in unbounded Python integers (for example the
             squaring stage is the square of the shifted derivative output, and the running
             window is the sum of the measured square range over its own window length)
  design     a bound stated by a constant or a comment of rantai.py, quoted with its line

The bit width of the measured range is an observation on one recording. It is a floor for
the hardware budget and not a proof over all inputs; the rows that carry a design bound say
so, and the rows that do not carry one say that too.

THE SQUARING STAGE, AND THE ONE WAY TO GET IT WRONG

The derivative output can be large, so the square of its maximum may not fit in a signed
64 bit word. Taking the maximum of that stage through a numpy int64 product therefore
overflows: the product wraps, and the width read off the wrapped value is false. This tool
computes the square of the shifted derivative maximum in Python integers, which cannot
overflow, and then proves on a short separate slice that the elementwise integer square
agrees with the numpy int64 path there, so the exact scalar square is the width that counts.

BINARY POINT AND Q FORMAT

The chain is tracked in locked counts. One count is the quantum of kuantisasi, 5 / 2047 mV,
about 2.4426 uV, and it is NOT a power of two, so the input conversion is a gain stage and
not a pure bit shift. Every node below it, however, is built only from integer additions,
integer multiplications and powers of two, so each node has a well defined binary point
relative to the count: a node value in count units is (stored integer) / 2**p.

    p      the number of fractional bits of the stored integer, in count units
    Q      Qm.n with n = max(p, 0) and m = width - n, so m + n is the total word width
    LSB    the physical size of one least significant bit, as an exact fraction of mV

When p is negative the LSB is larger than one count and the LSB column, not the Q column,
carries the physical scale. The value is printed as an exact rational, because 5 / 2047 has
no finite decimal form.

Run with no mandatory argument, from the repository root:

    /home/avivsabilalm/.venvs/afib-lite/bin/python tools/qformat.py

Options select the recording, the output shape and the fingerprint block. Nothing is
written anywhere: this tool only reads rantai.py, adapter.py, the fixture and the records.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import pathlib
import sys
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext
from fractions import Fraction

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
MODEL_DIR = ROOT / "model" / "rantai-afib-lite"
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

import rantai as R  # the frozen core, read and never modified

DATA_ROOT = pathlib.Path("/home/avivsabilalm/nabdha-data")
FIXTURE_DIR = MODEL_DIR / "fixture"
DEFAULT_RECORD = "04015"
DEFAULT_FRAMES = 450_000

# The classifier thresholds of the locked operating point, read from uji_10_berpenanda.py
# lines 158 and 159 (ratio 0.165, entropy 0.63), beside the older pair that rantai.py itself
# carries (AMBANG_LAMA_RASIO 0.21 line 756, AMBANG_LAMA_ENTROPI 0.70 line 757).
T1_LOCKED = 0.165
T2_LOCKED = 0.63
T1_LAMA = R.AMBANG_LAMA_RASIO
T2_LAMA = R.AMBANG_LAMA_ENTROPI

# One count in mV, exactly: kuantisasi divides the millivolt by 5 / 2047 counts (line 49).
MV_PER_COUNT = Fraction(5, 2047)


# =============================================================================================
# Fingerprints and small numeric helpers
# =============================================================================================

def sidik_jari(path):
    """sha256 of one file, or None when it is not there. Reads only."""
    p = pathlib.Path(path)
    if not p.exists():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for potongan in iter(lambda: fh.read(1 << 20), b""):
            h.update(potongan)
    return h.hexdigest()


def q_format(lebar, p):
    """Qm.n string of a word of `lebar` bits whose stored integer carries p fractional bits.

    n is max(p, 0) and m = lebar - n, so m + n is the word width. When p is negative the word
    has no fractional bits at all and the LSB is 2**-p count units, which the LSB column of
    the table states.
    """
    n = p if p > 0 else 0
    return "Q%d.%d" % (lebar - n, n)


def lsb_mv(unit_pangkat, p):
    """Exact LSB of one node in the physical unit, as a Fraction.

    unit_pangkat is the power of the count the node works in: 1 for a node whose value is in
    counts, 2 for a node whose value is in counts squared (the envelope power domain).
    The LSB is 2**-p of that unit, and one count is 5 / 2047 mV.
    """
    skala = MV_PER_COUNT ** unit_pangkat
    return Fraction(2) ** (-p) * skala


def lsb_teks(unit_pangkat, p):
    """The LSB of one node as an exact fraction of mV, or as the millisecond integer."""
    if unit_pangkat == 0:
        return "1 ms (the interval is an integer count of ms)"
    x = lsb_mv(unit_pangkat, p)
    if unit_pangkat == 1:
        return "%s/%s mV = %.4e mV" % (x.numerator, x.denominator, float(x))
    return "%s/%s mV^2 = %.4e mV^2" % (x.numerator, x.denominator, float(x))


def lebar_python(lo, hi, lebar_fungsi):
    """Width of a range through the frozen width rule of rantai.py, lines 79 to 88."""
    return lebar_fungsi(lo, hi)


def q_kode(x, bit_pecahan):
    """Integer code of a float threshold in Q0.bit, round half to even, the np.rint tie rule."""
    skala = 1 << bit_pecahan
    return int(round(x * skala))


# =============================================================================================
# The node table. One row per arithmetic node of the chain, in chain order.
# =============================================================================================

# The rounding rule of every node, quoted from rantai.py by line. These strings are read from
# the file and not recalled: each one names the lines it comes from.
ATURAN = {
    "masukan16": "np.rint, round half to even, then clip to the locked count rail 2047, then "
                 "a left shift by four that is exact. Lines 163 to 164.",
    "lp": "exact integer: the gains are 2, 1 and 1 and the recursion is a pure sum, so no "
          "rounding happens at all. Line 182.",
    "hp": "exact integer: the only gain is 32, which is a left shift by five, and the "
          "recursion is a pure sum. Line 204.",
    "turunan": "division by eight truncates toward zero and is sign symmetric, "
               "s // 8 if s >= 0 else -((-s) // 8), written out so it is not a plain shift. "
               "Line 228.",
    "geser8": "python right shift of an int, which is an arithmetic shift and rounds toward "
              "negative infinity, so it is not the truncation of line 228. Line 244.",
    "kuadrat": "exact integer product d * d, no rounding; the only rounding of this stage is "
               "the shift of line 244 that feeds it. Line 245.",
    "jendela": "exact integer: a running sum with the 38th sample back subtracted and, on "
               "even indices, the 37th sample back subtracted too. No division and no "
               "rounding. Lines 270 to 275.",
    "ambang_i1": "arithmetic right shift by two of the difference of the two envelopes, so "
                 "floor toward negative infinity. Line 655. The filtered pair uses the same "
                 "rule on line 656.",
    "ambang_i2": "arithmetic right shift by one of the first threshold, floor toward negative "
                 "infinity. Line 657.",
    "spki_npki": "the exponential update is spki + ((pv - spki) >> 3): an arithmetic right "
                 "shift by three of the difference, floor toward negative infinity. Lines 683, "
                 "685, 687, 699 and 700. The search back update uses >> 2, lines 706, 708, 709.",
    "gelombang_t": "no rounding of its own: it is the largest absolute value of the slope "
                   "series over the window, and the verdict is the exact cross form "
                   "2 * kem < kem_qrs and the exact shift test (delta << 2) < 360. "
                   "Lines 333, 338 to 340.",
    "rr": "integer only: the raw interval is (delta << 2) ms, exact (line 632); the first "
          "average is sum >> 3, floor (line 399); the second average is pembilang // penyebut, "
          "floor toward negative infinity (line 426); the reseeding median of an even count "
          "truncates toward zero, (a + b) // 2 (line 372). The band test of lines 359 to 361 "
          "is a cross multiplication with no division.",
    "rr_irama": "integer only: the reference is the median of the last eight corrected "
                "intervals through median_bulat (line 528); a false detection is the exact "
                "cross form 2 * x < reference (line 529); a missed beat is the exact cross "
                "form 50 * x > 83 * reference (line 534); the two halves are x >> 1, floor, "
                "and x - first, exact (lines 543 to 544).",
    "fitur_irama": "floating point, IEEE-754 binary64 with round to nearest even at every "
                   "operation: np.sqrt of np.mean of the squared differences, a division by "
                   "the window mean, a mean of a comparison, and an entropy over a 17 bin "
                   "histogram of the sorted core. Lines 848 to 861.",
    "kumpulkan_jendela": "floating point: the interval series is np.diff(puncak) / FS_HZ * "
                         "1000.0 (line 809) and the window filters are exact comparisons "
                         "(lines 818 to 822). No rounding decision is taken here.",
    "klasifier": "floating point comparison of two features against two thresholds, "
                 "ratio > t1 and entropy > t2 (line 875). The thresholds are the locked pair "
                 "0.165 and 0.63; in hardware they are integer codes, and the code and its "
                 "error are printed by this tool.",
}


def baris_sampul(rentang, lebar, lebar_tt, hasil=None):
    """The rows of the arithmetic node table.

    rentang, lebar and lebar_tt are exactly what Rantai.rentang_terukur(), Rantai.lebar() and
    Rantai.lebar_tanpa_tanda() returned for the run, so the table is a view of that output and
    not a second measurement.

    The derived rows (the shift of the derivative, the second threshold, the squared check)
    apply the exact operator of the node to the measured range of its input in Python
    integers, which cannot overflow.
    """
    r_masukan = rentang["masukan16"]
    r_lp = rentang["lp"]
    r_hp = rentang["hp"]
    r_tur = rentang["turunan"]
    r_ku = rentang["kuadrat"]
    r_sel = rentang["jendela"]
    r_i1 = rentang["ambang"]
    r_sb = rentang["search_back"]
    r_rr = rentang["rr"]
    r_kem = rentang["gelombang_t"]

    # the shift of the derivative, exactly as line 244 computes it: a Python right shift is
    # an arithmetic shift, that is floor toward negative infinity on every value.
    lo_d = int(r_tur[0]) >> R.GESER_AMBANG
    hi_d = int(r_tur[1]) >> R.GESER_AMBANG
    # the square of that shifted range, in Python integers, so it cannot wrap
    hi_ku = max(lo_d * lo_d, hi_d * hi_d)
    lo_ku = 0
    # the second threshold, exactly as line 657 computes it
    lo_i2 = int(r_i1[0]) >> 1
    hi_i2 = int(r_i1[1]) >> 1

    def baris(nama, lo, hi, unit_pangkat, p, aturan, sumber, catatan="", saturasi=""):
        """One row, with the frozen width rules applied to the range."""
        return {
            "simpul": nama,
            "saturasi": saturasi,
            "lo": lo,
            "hi": hi,
            "lebar": lebar_python(lo, hi, R.lebar_rentang),
            "lebar_tt": R.lebar_bit(hi) if lo >= 0 else None,
            "unit_pangkat": unit_pangkat,
            "p": p,
            "q": q_format(lebar_python(lo, hi, R.lebar_rentang), p),
            "lsb": lsb_teks(unit_pangkat, p),
            "aturan": aturan,
            "sumber": sumber,
            "catatan": catatan,
        }

    baris_tabel = [
        baris("masukan16  kuantisasi", r_masukan[0], r_masukan[1], 1, 4, ATURAN["masukan16"],
              "measured, rentang_terukur()['masukan16']; width agrees with lebar()['masukan16']",
              "design bound: the rail of line 50 is +/-2047 counts, so the word saturates at "
              "+/-2047 << 4 = +/-32752",
              saturasi="+/-32752, the rail at the locked clamp of line 50"),
        baris("lp  low-pass", r_lp[0], r_lp[1], 1, 4, ATURAN["lp"],
              "measured, rentang_terukur()['lp']",
              "design bound: the stage is ((1 - z^-6) / (1 - z^-1))^2 with a DC gain of 36 "
              "(line 170), so |lp| <= 36 * 32752 = 1179072",
              saturasi="+/-1179072, DC gain 36 (line 170) times the input rail"),
        baris("hp  high-pass", r_hp[0], r_hp[1], 1, 4, ATURAN["hp"],
              "measured, rentang_terukur()['hp']",
              "no sharp design bound: the single pole sits at z = -1 (line 194), so the worst "
              "case over an arbitrary input grows with the length of the record. The measured "
              "value is the only evidence, and a proof is not verified",
              saturasi="no sharp bound, pole at z = -1 (line 194): not verified"),
        baris("turunan  five point derivative", r_tur[0], r_tur[1], 1, 7, ATURAN["turunan"],
              "measured, rentang_terukur()['turunan']",
              "design bound from the operator: the kernel is 2, 1, 0, -1, -2 with an l1 norm "
              "of 6 (line 227) and a division by 8 (line 228), so |turunan| <= "
              "(6 / 8) * max|hp|; it is only as sharp as the hp bound above",
              saturasi="+/-14464656, the operator bound (6/8) * measured max|hp| (lines 227 "
                       "to 228)"),
        baris("geser8  turunan >> 8", lo_d, hi_d, 1, -1, ATURAN["geser8"],
              "operator, applied to the measured turunan range: >> 8 floors toward negative "
              "infinity on both ends",
              "no saturation: a shift has no rail of its own",
              saturasi="none of its own, a shift saturates nothing"),
        baris("kuadrat  d * d", lo_ku, hi_ku, 2, -2, ATURAN["kuadrat"],
              "operator, applied to the shifted range in Python integers: max(d^2) with "
              "max(|d|) = %d, whose exact square is %d" % (max(abs(lo_d), abs(hi_d)), hi_ku),
              "cross-check against the measured rentang_terukur()['kuadrat'] below",
              saturasi="0 .. %d, exact square of max|d| in Python integers" % hi_ku),
        baris("jendela  38 / 37 sample window", r_sel[0], r_sel[1], 2, -2, ATURAN["jendela"],
              "measured, rentang_terukur()['jendela']",
              "design bound from the operator: the widest window is N_B = 38 samples "
              "(line 54), so |jendela| <= 38 * max(kuadrat) = %d" % (38 * hi_ku),
              saturasi="0 .. %d, the N_B = 38 sample window times max(kuadrat), line 54"
                       % (38 * hi_ku)),
        baris("ambang  i1 first threshold", r_i1[0], r_i1[1], 2, -2, ATURAN["ambang_i1"],
              "measured, rentang_terukur()['ambang']",
              "no rail: i1 is a shift of a difference of two envelope estimates, so it stays "
              "between them and the updates of lines 683 and 699 keep both inside the "
              "envelope range",
              saturasi="none of its own, it lies between the two envelope estimates"),
        baris("ambang  i2 second threshold", lo_i2, hi_i2, 2, -3, ATURAN["ambang_i2"],
              "operator, applied to the measured i1 range: >> 1 floors toward negative "
              "infinity on both ends",
              "no rail: it is half of i1 by construction",
              saturasi="none of its own, half of i1 by line 657"),
        baris("gelombang_t  slope kem", r_kem[0], r_kem[1], 1, 7, ATURAN["gelombang_t"],
              "measured, rentang_terukur()['gelombang_t']",
              "no rail of its own: it is the largest absolute value of the slope series, so "
              "its LSB is the LSB of that series",
              saturasi="none of its own, at most max|turunan|"),
        baris("search_back  candidate value", r_sb[0], r_sb[1], 2, -2, ATURAN["spki_npki"],
              "measured, rentang_terukur()['search_back']",
              "no rail: it is one envelope value out of the recorded peak list, so it is "
              "bounded by the jendela range",
              saturasi="none of its own, one envelope value of the recorded peak list"),
        baris("rr  interval, ms", r_rr[0], r_rr[1], 0, 0, ATURAN["rr"],
              "measured, rentang_terukur()['rr']",
              "design bound: the stage is fed only when 250 <= rr_ms <= 2000 (line 638) and "
              "the rhythm check has the absolute ceiling of 3000 ms (line 496)",
              saturasi="250 .. 2000 ms accepted (line 638); 3000 ms ceiling (line 496)"),
    ]

    if hasil is not None:
        rr_kor = np.asarray(hasil["rr_corrected"])
        mk = np.asarray(hasil["rr_mark_raw"])
        if rr_kor.size:
            baris_tabel.append(baris(
                "rr_corrected  marked series", int(rr_kor.min()), int(rr_kor.max()), 0, 0,
                ATURAN["rr_irama"],
                "measured over the corrected series of this run, hasil()['rr_corrected'], "
                "with the marks hasil()['rr_mark_raw']",
                "marks present: %s" % ", ".join(
                    "mark %d x %d" % (m, int((mk == m).sum())) for m in (0, 1, 2, 3)),
                saturasi="a gap over 3000 ms is kept whole and marked, lines 536 to 542"))

    # The width view of the frozen chain has to agree with the width recomputed here, key by
    # key, or the table is not a view of that output at all.
    cocok, beda = True, []
    for k, r in rentang.items():
        if r is None or r[0] is None:
            continue
        ulang = lebar_python(r[0], r[1], R.lebar_rentang)
        if lebar.get(k) is not None and lebar[k] != ulang:
            cocok = False
            beda.append("%s: lebar() %s against recomputed %s" % (k, lebar[k], ulang))
        tt = lebar_tt.get(k)
        if tt is not None and tt != R.lebar_bit(r[1]):
            cocok = False
            beda.append("%s: lebar_tanpa_tanda() %s against recomputed %s"
                        % (k, tt, R.lebar_bit(r[1])))
    return baris_tabel, cocok, beda


# =============================================================================================
# The squaring stage: the exact square, and the proof that the integer path is exact
# =============================================================================================

def periksa_kuadrat(array_turunan, panjang_potongan=4096):
    """Exact maximum of the squaring stage, and an exactness proof on a short slice.

    Returns a dict the report prints. The scalar square of the shifted derivative maximum is
    computed in Python integers. The proof runs the same square elementwise over the first
    `panjang_potongan` samples of the derivative series, once in Python integers and once
    through numpy int64, and compares. A numpy int64 product would wrap silently and report
    a false width, so the comparison is the evidence that the int64 path happens to be exact
    on that slice.
    """
    a = np.asarray(array_turunan)
    d_python = [int(v) >> R.GESER_AMBANG for v in a[:panjang_potongan]]
    exak = [v * v for v in d_python]
    try:
        with np.errstate(over="ignore"):
            d_int = (a[:panjang_potongan].astype(np.int64) >> np.int64(R.GESER_AMBANG))
            lewat = (d_int * d_int)
        sama = all(int(x) == int(y) for x, y in zip(exak, lewat))
    except Exception as exc:  # a numpy that refuses rather than wraps
        sama, lewat = False, None
        print("     the numpy int64 slice raised %s, so the integer path is refused there" % exc)

    # the measured array of the same stage, when the caller has it
    return {
        "potongan": int(min(panjang_potongan, a.size)),
        "max_abs_d": max(abs(int(v) >> R.GESER_AMBANG) for v in a),
        "max_abs_d_potongan": max(abs(v) for v in d_python) if d_python else 0,
        "sama": bool(sama),
        "lewat_negatif": bool(lewat is not None and any(int(v) < 0 for v in lewat)),
    }


def demo_luapan():
    """The failure mode the note warns about, shown with the numbers it makes."""
    big = np.int64(1) << np.int64(33)
    with np.errstate(over="ignore"):
        bungkus = int(big * big)
    return {
        "nilai": 2 ** 33,
        "bungkus": bungkus,
        "exak": 2 ** 66,
        "lebar_bungkus": R.lebar_bit(bungkus),
        "lebar_exak": R.lebar_bit(2 ** 66),
    }


# =============================================================================================
# The recording: the frozen fixture, or a WFDB record through the frozen adapter
# =============================================================================================

def muat_fixture(nama):
    """The frozen fixture of one recording, as the 16 bit word sequence of the record."""
    path = FIXTURE_DIR / ("%s_30m.npz" % nama)
    if not path.exists():
        return None
    d = np.load(path)
    return {"path": path, "data": d, "masukan16": d["masukan16"],
            "sidik": sidik_jari(path), "sumber": "frozen fixture, key masukan16"}


def muat_wfdb(nama, frames):
    """The first `frames` samples of an AFDB record, through the frozen adapter of step S2."""
    import adapter as A
    info = None
    for kandidat in (DATA_ROOT / "afdb" / nama, ROOT / "dataset" / "afdb" / nama):
        if kandidat.with_suffix(".hea").exists():
            info = kandidat
            break
    if info is None:
        raise SystemExit("record %r is neither a fixture nor a WFDB record under %s or %s"
                         % (nama, DATA_ROOT / "afdb", ROOT / "dataset" / "afdb"))
    src = A.DatasetBulk(info, n_frames=frames)
    src.open()
    kata = []
    while True:
        s = src.read()
        if s is None:
            break
        kata.append(s.value16)
    src.close()
    return {"path": info, "data": None, "masukan16": np.asarray(kata, dtype=np.int64),
            "path": info.with_suffix(".hea"),
            "sidik": sidik_jari(info.with_suffix(".hea")),
            "sumber": "WFDB record %s, first %d frames, through the frozen adapter" % (nama, frames)}


def jalankan_rantai(masukan16):
    """One real run of the frozen chain over the locked words.

    The conversion back to millivolt is the exact inverse the adapter uses on line 366 of
    adapter.py, so the chain sees the same millivolt values the adapter hands it and
    kuantisasi returns the very word that was stored.
    """
    c = R.Rantai()
    for v in masukan16:
        c.langkah((int(v) >> R.GESER_KIRI) / R.GAIN_COUNT)
    return c


# =============================================================================================
# Printing
# =============================================================================================

KOLOM = ("node", "measured range", "W two's comp", "W unsigned", "p", "Q format",
         "LSB (exact)", "saturation point", "rounding rule at this node")


def cetak_teks(tabel, info, sumber_rekaman, cek, luapan, r):
    """The plain text table, one row per node, then the checks."""
    print()
    print("TABLE 1, arithmetic nodes of the sample chain, plain text")
    print("record %s, %d samples, from the %s" % (info["nama"], info["sampel"], sumber_rekaman))
    print()
    print("%-32s %-30s %4s %4s %4s %-8s %-24s %-52s %s"
          % ("node", "measured range", "W(s)", "W(u)", "p", "Q", "LSB exact",
             "saturation point", "rounding rule"))
    print("-" * 240)
    for b in tabel:
        print("%-32s %-30s %4d %4s %4d %-8s %-24s %-52s %s"
              % (b["simpul"], "[%d, %d]" % (b["lo"], b["hi"]), b["lebar"],
                 "-" if b["lebar_tt"] is None else b["lebar_tt"],
                 b["p"], b["q"], b["lsb"], b["saturasi"], b["aturan"]))
    print()
    print("sources and notes, one line per node")
    for b in tabel:
        print("  %-32s %s" % (b["simpul"], b["sumber"]))
        if b["catatan"]:
            print("  %-32s %s" % ("", b["catatan"]))
    print()
    print("checks")
    print("  the width view of the chain agrees with the width recomputed from the ranges: %s"
          % ("YES" if cek["cocok"] else "NO"))
    for b in cek["beda"]:
        print("    %s" % b)
    print("  the squaring stage, exact square: max|d| = %d, exact max(d^2) = %d"
          % (cek["kuadrat"]["max_abs_d"], cek["kuadrat"]["max_abs_d"] ** 2))
    print("  the squaring stage, exactness proved on a slice of %d samples: %s"
          % (cek["kuadrat"]["potongan"],
             "the Python integer square and the numpy int64 square agree elementwise"
             if cek["kuadrat"]["sama"] else "they do NOT agree, so the int64 path is not exact"))
    print("  measured rentang_terukur()['kuadrat'] = %s, and the operator applied to the "
          "shifted derivative range gives [0, %d]" % (r["kuadrat"], cek["kuadrat"]["max_abs_d"] ** 2))
    print("  naive int64 failure mode, shown and not used: (%d)^2 in numpy int64 gives %d, "
          "whose width would be read as %d bits, while the exact value %d needs %d bits"
          % (luapan["nilai"], luapan["bungkus"], luapan["lebar_bungkus"], luapan["exak"],
             luapan["lebar_exak"]))


def cetak_markdown(tabel, cek, r, nama):
    """The same table as markdown, so it can be pasted into a design document."""
    print()
    print("TABLE 1, arithmetic nodes of the sample chain, markdown, record %s" % nama)
    print()
    print("| " + " | ".join(KOLOM) + " |")
    print("|" + "---|" * len(KOLOM))
    for b in tabel:
        print("| %s | [%d, %d] | %d | %s | %d | `%s` | %s | %s | %s |"
              % (b["simpul"], b["lo"], b["hi"], b["lebar"],
                 "-" if b["lebar_tt"] is None else b["lebar_tt"], b["p"], b["q"],
                 b["lsb"].replace("|", "\\|"), b["saturasi"].replace("|", "\\|"),
                 b["aturan"].replace("|", "\\|")))
    print()
    print("| check | value |")
    print("|---|---|")
    print("| max abs of the shifted derivative | %d |" % cek["kuadrat"]["max_abs_d"])
    print("| exact square of that maximum, Python integer | %d |"
          % (cek["kuadrat"]["max_abs_d"] ** 2))
    print("| measured kuadrat range | %s |" % (r["kuadrat"],))
    print("| int64 exactness on the slice | %s |" % ("exact" if cek["kuadrat"]["sama"] else "WRAPS"))
    print("| width view agrees with recomputed widths | %s |" % ("yes" if cek["cocok"] else "no"))
    if cek.get("fixture_sama") is not None:
        print("| the run reproduces the frozen fixture arrays element for element | %s |"
              % ("all equal" if all(cek["fixture_sama"].values()) else "DIFFERENT"))


def cetak_pecahan(d, bit_tambahan=16):
    """The floating point tail: the window features and the classifier thresholds."""
    print()
    print("TABLE 2, the floating point tail of the chain, and the classifier in fixed point")
    print("  the window feature layer is floating point by design (rantai.py lines 719 to 726),")
    print("  so it has no bit width of its own; the rows below state what a hardware port has")
    print("  to reproduce and what the encoder of each threshold costs.")
    print()
    fit = None
    if d is not None and "jendela_fitur" in d.files:
        fit = np.asarray(d["jendela_fitur"], float)
    print("%-34s %-28s %s" % ("node", "measured range", "rounding rule"))
    print("-" * 200)
    nama_fitur = ("rmssd (ms)", "rmssd / mean rr", "pnn50", "entropy / 4")
    if fit is not None and fit.size:
        for j, nm in enumerate(nama_fitur):
            print("%-34s [%14.6f, %14.6f] %s"
                  % (nm, float(fit[:, j].min()), float(fit[:, j].max()),
                     "floating point binary64, IEEE-754, round to nearest even"))
    else:
        print("%-34s %-28s %s" % ("fitur_irama", "not verified",
                                  "floating point binary64, no fixture table for this record"))
    print("%-34s %-28s %s" % ("rr series in ms (window layer)", "float",
                              "floating point binary64, no rounding decision"))
    print("%-34s %-28s %s" % ("classifier verdict", "bool",
                              "two float comparisons, ratio > t1 and entropy > t2"))
    print()
    print("  classifier thresholds as integer codes (round half to even, the np.rint tie rule)")
    print("  %-10s %-14s %8s %-16s %-14s %s"
          % ("bit", "threshold", "code", "code / 2**bit", "abs error", "error in LSB"))
    for bit in sorted({12, 14, 16, 18, 20, int(bit_tambahan)}):
        for nm, x in (("ratio", T1_LOCKED), ("entropy", T2_LOCKED),
                      ("ratio_lama", T1_LAMA), ("entropy_lama", T2_LAMA)):
            kode = q_kode(x, bit)
            nilai = kode / float(1 << bit)
            print("  %-10d %-14s %8d %-16.10f %-14.3e %.4f"
                  % (bit, nm, kode, nilai, abs(nilai - x), abs(nilai - x) * (1 << bit)))
    print()


# =============================================================================================
# The window feature layer: fixed point node table down to the intermediate values
# =============================================================================================
#
# rantai.py lines 848 to 861 is the whole arithmetic of the window feature layer, and it is
# floating point by design. This section measures it and states what a fixed point port of the
# same arithmetic needs, node by node, down to the intermediate values and not only at the four
# outputs the chain returns. The layer is copied here statement by statement, with one probe
# after every statement, and the copy is verified element for element against the frozen fixture
# array jendela_fitur before a single number of the table is printed, so every range below is a
# range of the frozen layer and not of a second implementation.
#
# THE NODES OF THE LAYER, IN ORDER (rantai.py lines 848 to 861)
#
#   line 851  d       = np.diff(rr)                 the interval differences, in ms
#   line 852  d * d                                 the squared differences
#   line 852  np.mean(d ** 2) = sum(d^2) / 31       the mean square, an exact / 31
#   line 852  np.sqrt(...)                          the RMSSD root
#   line 853  np.abs(d) > 50.0                      the pNN50 comparison
#   line 853  np.mean(...) = count / 31             the pNN50 ratio, an exact / 31
#   line 854  np.sort(rr)                           the sorted window, 32 values
#   line 855  s[8:-8]                               the trimmed core, 16 values
#   line 856  np.linspace(min, max, 17)             the edge grid, an exact / 16
#   line 858  np.histogram                          the bin counts, 16 bins
#   line 859  cnt[cnt > 0] / cnt.sum()              the bin probabilities, an exact / 16
#   line 860  np.log2(p)                            the logarithm base two
#   line 860  -(p * np.log2(p)).sum()               the entropy
#   line 861  h / 4.0                               the entropy over four, an exact / 4
#
# The edge grid of line 856 is np.linspace(core.min(), core.max(), 17): seventeen EDGE POINTS,
# so SIXTEEN bins and not seventeen. The last edge of line 857 is widened by 1e-9 so that the
# maximum of the core falls inside the last bin; that is a deliberate perturbation of the grid
# and not a rounding of a value, and sixteen is the bin count the layer really has.
#
# EXACT RATIONALS, NEVER FLOAT64, DECIDE EVERY WIDTH OF A DIVISION OR A ROOT
#
# The interval series is an exact integer count of ms, because 1000 / 250 is exactly 4 (line
# 809), so every sum that feeds a division of this layer is an exact integer. sum(d^2) / 31 is
# an exact rational, and the root of an exact positive rational is bracketed with an integer
# square root: r / (b 10**k) <= sqrt(a / b) < (r + 1) / (b 10**k) with r = isqrt(a b 10**(2k)).
# A binary64 copy of the same value is a rounded value and could put the width one bit out, so
# no width below is read off a float64.
#
# THE BINARY POINT PROPOSED FOR EVERY DIVISION AND ROOT
#
#   p is the number of fractional bits the node keeps, in the unit of the node itself, so the
#   node value is (stored integer) / 2**p. The printed integer range is floor(lo * 2**p) to
#   ceil(hi * 2**p), taken exactly with the fractions module.
#
#   / 31   mean square, pNN50        p = 8    the residue of an inexact / 31 falls below
#                                             1 / 256 of a unit
#   / 32   mean RR                   p = 4    32 is a power of two, so the division itself is a
#                                             binary exponent change; p is only the scale
#   / 16   bin width                 p = 4    the step of the edge grid; 16 is a power of two,
#                                             so p = 4 is the exact point of the value
#   / 16   bin probability           p = 4    the count sum of the core; exact at p = 4
#   / 4    entropy over four         p = 8    4 is a power of two, the division is a shift
#   sqrt   RMSSD root                p = 4    an LSB of 1 / 16 ms
#   /      ratio RMSSD / mean RR     p = 8    keeps the classifier threshold 0.165 above its
#                                             own 8 bit code
#
# WHAT IS NOT MEASURED HERE
#
# The layer has no integer chain to lean on, so every range below is an observation on one or
# three peak series of one recording, and a port that must hold all inputs needs the design
# bound column, not the measured column. The nodes whose value is irrational (the root, the
# logarithm, the entropy) carry a certified bracket instead of an exact rational, because no
# finite binary word holds them; the bracket, and not a rounded decimal, sets their width.

NODA_LAPISAN = (
    # key, name, unit, p, saturation point, rounding rule at the node
    ("rr_jendela", "rr  window intervals, ms", "ms", 0,
     "200 .. 3000 ms: the window filter of line 821 rejects every window outside it, so the "
     "word may saturate at the rails and drop the window",
     "exact: np.diff of integer sample indices, then / FS_HZ * 1000.0 with 1000 / 250 = 4 "
     "exactly, so the value is an exact integer count of ms. Lines 809 and 816."),
    ("selisih_d", "d  np.diff(rr), ms", "ms", 0,
     "-2800 .. 2800 ms, the span of the accepted rails of line 821",
     "exact: np.diff subtracts two integers far below 2**53, so binary64 holds both exactly. "
     "Line 851."),
    ("kuadrat_d", "d * d, ms^2", "ms2", 0,
     "0 .. 2800**2 = 7840000 ms^2, the square of the design bound of d",
     "exact: d * d of an integer far below 2**26, below 2**53. Line 852."),
    ("jumlah_kuadrat", "sum(d * d) over 31, ms^2", "ms2", 0,
     "0 .. 31 * 7840000 = 243040000 ms^2, the window length times the square bound",
     "exact: np.sum of integer squares whose largest partial sum here is far below 2**53. "
     "Line 852."),
    ("rata_kuadrat", "sum(d * d) / 31, ms^2", "ms2", 8,
     "0 .. 7840000 ms^2, the mean of the square bound",
     "IEEE-754 binary64 division by 31, round to nearest even; the exact residue is 1 / 31 of "
     "an ms^2 and has no finite binary form. Line 852. A port rounds half to even at p bits."),
    ("akar_rmsd", "sqrt(mean(d * d)) = RMSSD, ms", "ms", 4,
     "0 .. 2800 ms, the root of the mean square bound",
     "np.sqrt, IEEE-754 binary64 square root, round to nearest even of the division result. "
     "Line 852. The value is irrational in general, so the range below is a certified bracket. "
     "A port uses an integer square root with round half to even at p bits."),
    ("rata_rr", "mean(rr) = sum(rr) / 32, ms", "ms", 4,
     "200 .. 3000 ms, the rails of the window filter of line 821",
     "exact: rr.mean() divides by the window length 32, a power of two, so the division is a "
     "binary exponent change and adds no rounding of its own. Line 861, reached from 852."),
    ("rasio", "RMSSD / mean(rr), dimensionless", "rasio", 8,
     "0 .. 2800 / 200 = 14, the ratio of the design rails",
     "IEEE-754 binary64 division, round to nearest even. Line 861. The value is irrational in "
     "general, so the range below is a certified bracket. A port rounds half to even at p bits."),
    ("pnn50_cacah", "count(|d| > 50.0), beats", "count", 0,
     "0 .. 31 counts, the window length",
     "exact: np.count_nonzero of the strict comparison np.abs(d) > 50.0, an integer count. "
     "Line 853."),
    ("pnn50", "count(|d| > 50.0) / 31, dimensionless", "rasio", 8,
     "0 .. 1 by construction",
     "IEEE-754 binary64 mean over 31 entries, so a division by 31, round to nearest even. "
     "Line 853."),
    ("urut_rr", "np.sort(rr), 32 values, ms", "ms", 0,
     "200 .. 3000 ms, the same values as rr_jendela in another order",
     "exact: np.sort is a permutation, with no arithmetic and no rounding. Line 854."),
    ("teras", "s[8:-8], 16 values, ms", "ms", 0,
     "200 .. 3000 ms, the middle 16 of the 32 sorted intervals",
     "exact: the slice s[8:-8] of the sorted window keeps 16 of the 32 values. Line 855."),
    ("lebar_bin", "(core.max() - core.min()) / 16, ms", "ms", 4,
     "0 .. (3000 - 200) / 16 = 175 ms, the fraction of the design span",
     "exact: np.linspace divides the span of the core by 16, a power of two, so the step is "
     "exact in binary64. Line 856."),
    ("histogram_cacah", "np.histogram counts, 16 bins", "count", 0,
     "0 .. 16 counts, the length of the core",
     "exact: np.histogram counts, an integer per bin. The last edge was widened by 1e-9 on "
     "line 857 so the core maximum falls inside the last bin; no value is rounded. Line 858."),
    ("probabilitas", "cnt[cnt > 0] / cnt.sum(), dimensionless", "rasio", 4,
     "1 / 16 .. 1, the smallest possible nonzero bin probability over the 16 bin core",
     "exact: the division is by cnt.sum(), the count sum of the 16 value core, a power of two. "
     "Line 859."),
    ("log2_p", "np.log2(p), bit", "bit", 8,
     "-4 .. 0 bit: sixteen bins put the smallest probability at 1 / 16 and log2 of it at -4",
     "np.log2, IEEE-754 binary64 logarithm; the last bit of a transcendental is not fixed by "
     "IEEE-754 and is left to the library. Line 860. The value is irrational except at the "
     "powers of two, so the range below is a high precision bracket, not a proof. A port needs "
     "a table or an LUT with interpolation."),
    ("entropi_h", "-(p * np.log2(p)).sum(), bit", "bit", 8,
     "0 .. 4 bit, log2 of the sixteen bin core",
     "IEEE-754 binary64: a product p * log2(p) and a running sum, round to nearest even at "
     "every operation. Line 860. The bracket below is the certified range of the sum."),
    ("entropi_per_empat", "h / 4.0, bit", "bit", 8,
     "0 .. 1 bit, the entropy bound over four",
     "exact: h / 4.0 divides by a power of two, so the division adds no error beyond the "
     "entropy it scales. Line 861."),
)

NODA_KUNCI = tuple(b[0] for b in NODA_LAPISAN)
_DIGIT_AKAR = 40


def akar_bracket(q, digit=_DIGIT_AKAR):
    """Certified [lo, hi] bracket of sqrt(q) of an exact positive Fraction, by integer sqrt.

    r = isqrt(a b 10**(2k)) gives r / (b 10**k) <= sqrt(a / b) < (r + 1) / (b 10**k), which is
    exact integer arithmetic and not a float64 estimate.
    """
    a, b = q.numerator, q.denominator
    r = math.isqrt(a * b * 10 ** (2 * digit))
    return Fraction(r, b * 10 ** digit), Fraction(r + 1, b * 10 ** digit)


def log2_bracket(q, digit=_DIGIT_AKAR):
    """High precision [lo, hi] bracket of log2(q) of an exact positive Fraction.

    Decimal is used only here, on an irrational node where no exact form exists; the bracket is
    a high precision numerical bound and is labelled as such and not as a proof.
    """
    with localcontext() as ctx:
        ctx.prec = digit + 20
        x = Decimal(q.numerator) / Decimal(q.denominator)
        lg = x.ln() / Decimal(2).ln()
        skala = Decimal(10) ** digit
        y = lg * skala
        lo = int(y.to_integral_value(rounding=ROUND_FLOOR))
        hi = int(y.to_integral_value(rounding=ROUND_CEILING))
    return Fraction(lo, 10 ** digit), Fraction(hi, 10 ** digit)


def dua_biner(x, p):
    """Exact floor and ceil of x * 2**p for an exact Fraction x."""
    y = x * (1 << p) if p >= 0 else x / (1 << -p)
    return y.numerator // y.denominator, -((-y.numerator) // y.denominator)


def lebar_q(lo, hi, p):
    """Two's complement width of the closed range [lo, hi] stored with p fractional bits."""
    lo_i, _ = dua_biner(lo, p)
    _, hi_i = dua_biner(hi, p)
    return R.lebar_rentang(lo_i, hi_i), lo_i, hi_i


def lsb_lapisan(unit, p):
    """Exact LSB of a layer node in its own unit."""
    if unit == "count":
        return "1 count (integer)"
    pangkat = "1" if p <= 0 else "1/%d" % (1 << p)
    satuan = {"ms": "ms", "ms2": "ms^2", "rasio": "", "bit": "bit"}[unit]
    return ("%s %s" % (pangkat, satuan)).strip()


def _bracket_tambah(acc, nama, lo, hi):
    """One window contributes the closed interval [lo, hi] to a node of the table."""
    a = acc.setdefault(nama, [lo, hi])
    if lo < a[0]:
        a[0] = lo
    if hi > a[1]:
        a[1] = hi


def _probe_fitur(rr_ms, acc):
    """fitur_irama of rantai.py lines 848 to 861, one probe after every statement.

    Every accumulated range is in exact Fractions: an integer, an exact / 31 or / 32, a
    certified root bracket, or a bin probability of the form k / 16. No float64 decides a width.
    """
    rr = np.asarray(rr_ms, float)
    _bracket_tambah(acc, "rr_jendela", Fraction(int(rr.min())), Fraction(int(rr.max())))
    T = int(round(float(rr.sum())))
    _bracket_tambah(acc, "rata_rr", Fraction(T, 32), Fraction(T, 32))

    d = np.diff(rr)                                                        # line 851
    _bracket_tambah(acc, "selisih_d", Fraction(int(d.min())), Fraction(int(d.max())))
    _bracket_tambah(acc, "kuadrat_d", Fraction(0), Fraction(int(np.max(d ** 2))))
    S = int(round(float(np.sum(d ** 2))))                                  # line 852
    _bracket_tambah(acc, "jumlah_kuadrat", Fraction(0), Fraction(S))
    _bracket_tambah(acc, "rata_kuadrat", Fraction(S, 31), Fraction(S, 31))
    ak = akar_bracket(Fraction(S, 31))
    _bracket_tambah(acc, "akar_rmsd", ak[0], ak[1])
    # the ratio is the root divided by the window mean T / 32, so it is bracketed by the same
    # certified root bracket scaled by 32 / T, and never by a float64 quotient
    _bracket_tambah(acc, "rasio", ak[0] * 32 / T, ak[1] * 32 / T)

    c50 = int(np.count_nonzero(np.abs(d) > 50.0))                           # line 853
    _bracket_tambah(acc, "pnn50_cacah", Fraction(0), Fraction(c50))
    _bracket_tambah(acc, "pnn50", Fraction(c50, 31), Fraction(c50, 31))

    s = np.sort(rr)                                                         # line 854
    _bracket_tambah(acc, "urut_rr", Fraction(int(s.min())), Fraction(int(s.max())))
    core = s[8:-8] if s.size > 20 else s                                    # line 855
    _bracket_tambah(acc, "teras", Fraction(int(core.min())), Fraction(int(core.max())))
    _bracket_tambah(acc, "lebar_bin",
                    Fraction(int(core.max()) - int(core.min()), 16),
                    Fraction(int(core.max()) - int(core.min()), 16))

    edges = np.linspace(core.min(), core.max(), 17)                         # line 856
    acc.setdefault("_edges", []).append(int(edges.size))
    edges[-1] += 1e-9                                                       # line 857
    cnt, _ = np.histogram(core, bins=edges)                                 # line 858
    acc.setdefault("_bin", []).append(int(cnt.size))
    acc.setdefault("_cacah_isi", []).append(int(cnt.sum()))
    _bracket_tambah(acc, "histogram_cacah", Fraction(0), Fraction(int(cnt.max())))
    nz = cnt[cnt > 0]                                                       # line 859
    acc.setdefault("_bin_terisi", []).append(int(nz.size))
    _bracket_tambah(acc, "probabilitas",
                    Fraction(int(nz.min()), 16), Fraction(int(nz.max()), 16))

    lg = [log2_bracket(Fraction(int(k), 16)) for k in nz]                    # line 860
    _bracket_tambah(acc, "log2_p", min(x[0] for x in lg), max(x[1] for x in lg))
    pk = [Fraction(int(k), 16) for k in nz]
    h_lo = -sum(b * hi for b, (lo, hi) in zip(pk, lg))   # h falls as log2 rises
    h_hi = -sum(b * lo for b, (lo, hi) in zip(pk, lg))
    _bracket_tambah(acc, "entropi_h", h_lo, h_hi)
    _bracket_tambah(acc, "entropi_per_empat", h_lo / 4, h_hi / 4)           # line 861
    return acc


def ukur_lapisan_fitur(puncak, lab, sumber=None):
    """kumpulkan_jendela of rantai.py lines 799 to 826 with the probe inside fitur_irama.

    The window scan, the two filters of lines 819 and 821 and the step of line 816 are the
    frozen ones; only the window source argument is chosen by the caller.
    """
    if sumber is None:
        sumber = R.SUMBER_MENTAH
    rr = np.diff(puncak) / R.FS_HZ * 1000.0
    bl = lab[puncak[1:]]
    if sumber == R.SUMBER_BERPENANDA:
        rr, idx = R.seri_berpenanda(rr, R.tanda_deret(rr))
        bl = bl[idx]
    baris, acc = [], {}
    for i in range(0, rr.size - R.JENDELA_DENYUT, R.LANGKAH_DENYUT):
        seg = rr[i:i + R.JENDELA_DENYUT]
        u = np.unique(bl[i:i + R.JENDELA_DENYUT])
        if u.size != 1 or u[0] not in ("AFIB", "N"):
            continue
        if seg.min() < 200 or seg.max() > 3000:
            continue
        baris.append(u[0])
        _probe_fitur(seg, acc)
    acc["_jendela"] = len(baris)
    return acc


def cari_anotasi(nama):
    """Record stem of the WFDB annotation of one recording, or None when it is not there."""
    for kandidat in (DATA_ROOT / "afdb" / nama, ROOT / "dataset" / "afdb" / nama):
        if kandidat.with_suffix(".atr").exists():
            return kandidat
    return None


def label_lapisan(nama, n):
    """The rhythm label array of one recording, or (None, reason) when it cannot be built."""
    stem = cari_anotasi(nama)
    if stem is None:
        return None, "no annotation file under %s or %s" % (DATA_ROOT / "afdb",
                                                            ROOT / "dataset" / "afdb")
    try:
        import wfdb
        an = wfdb.rdann(str(stem), "atr")
    except Exception as exc:  # wfdb absent, or an unreadable annotation
        return None, "wfdb.rdann(%s.atr) raised %s" % (stem, exc)
    return R.label_irama(an.sample, an.aux_note, n), str(stem.with_suffix(".atr"))


def arms_lapisan(data, hasil):
    """The peak series arms the layer is measured over, each with its fixture oracle.

    The fixture stores the three arms the S1 equivalence test builds: the chain run of this
    tool, the chain run with aturan_t=False, and the reference peak series. Each arm is
    measured with the raw interval source, which is the source the fixture arrays were built
    with (uji_01_kesetaraan_s1.py lines 108 to 111).
    """
    arms = [("chain of this run", np.asarray(hasil["qrs"], dtype=np.int64), "jendela_fitur")]
    if data is not None and hasattr(data, "files"):
        if "jendela_aturan_t_mati" in data.files and "jendela_fitur_aturan_t_mati" in data.files:
            arms.append(("chain with aturan_t=False",
                         np.asarray(data["jendela_aturan_t_mati"], dtype=np.int64),
                         "jendela_fitur_aturan_t_mati"))
        if "puncak_acuan_neurokit" in data.files and "jendela_fitur_acuan" in data.files:
            arms.append(("reference peak series",
                         np.asarray(data["puncak_acuan_neurokit"], dtype=np.int64),
                         "jendela_fitur_acuan"))
    return arms


def tabel_lapisan_fitur(data, hasil, nama, n):
    """Measure the window feature layer and return the rows, the checks and the arm results."""
    lab, sumber_lab = label_lapisan(nama, n)
    cek = {"anotasi": sumber_lab, "lab_ok": lab is not None, "arms": [], "cocok": None}
    if lab is None:
        return [], cek, None

    gabung, per_arm = {}, {}
    for nama_arm, puncak, kunci_oracle in arms_lapisan(data, hasil):
        acc = ukur_lapisan_fitur(puncak, lab)
        per_arm[nama_arm] = acc
        masuk = {
            "arm": nama_arm, "oracle": kunci_oracle, "jendela": acc["_jendela"],
            "equalities": None, "equalities_kelas": None,
            "bin": sorted(set(acc.get("_bin", []))), "edges": sorted(set(acc.get("_edges", []))),
            "cacah_isi": sorted(set(acc.get("_cacah_isi", []))),
            "bin_terisi_max": max(acc.get("_bin_terisi", [0])),
        }
        if data is not None and hasattr(data, "files") and kunci_oracle in data.files:
            masuk["equalities"] = None  # the intermediates are not stored, only the outputs
        for k, v in acc.items():
            if k.startswith("_"):
                continue
            a = gabung.setdefault(k, [v[0], v[1]])
            a[0] = min(a[0], v[0])
            a[1] = max(a[1], v[1])
        cek["arms"].append(masuk)
    return gabung, cek, per_arm


def cetak_lapisan_fitur(data, hasil, nama, n):
    """TABLE 3, the fixed point node table of the window feature layer, and its checks."""
    gabung, cek, per_arm = tabel_lapisan_fitur(data, hasil, nama, n)
    print()
    print("TABLE 3, fixed point nodes of the window feature layer, measured range and width")
    print("  the layer is rantai.py kumpulkan_jendela lines 799 to 826, fitur_irama lines 848")
    print("  to 861, and the window filter of line 821; p is the proposed binary point and the")
    print("  integer range is floor(lo * 2**p) to ceil(hi * 2**p), taken exactly.")
    print()
    if not cek["lab_ok"]:
        print("  NOT MEASURED: the rhythm label array cannot be built, %s" % cek["anotasi"])
        print("  the layer is driven by the annotation of the record, so no window can be kept")
        return cek
    print("  annotation        %s" % cek["anotasi"])
    for a in cek["arms"]:
        print("  arm %-28s %4d windows kept, oracle %s"
              % (a["arm"], a["jendela"], a["oracle"]))
    print()
    print("%-40s %-24s %-18s %4s %4s %-8s %-12s %s"
          % ("node", "measured range (unit)", "stored integer range", "W(s)", "p", "Q",
             "LSB exact", "saturation point"))
    print("-" * 240)
    baris = []
    for kunci, nama_noda, unit, p, saturasi, aturan in NODA_LAPISAN:
        if kunci not in gabung:
            print("%-40s %s" % (nama_noda, "NOT MEASURED, the node did not occur"))
            baris.append({"simpul": nama_noda, "lebar_bit": 0, "q_format": "-",
                          "rentang": "not measured", "p": p, "saturasi": saturasi,
                          "aturan": aturan, "unit": unit, "terukur": False})
            continue
        lo, hi = gabung[kunci]
        w, lo_i, hi_i = lebar_q(lo, hi, p)
        baris.append({"simpul": nama_noda, "lebar_bit": w, "q_format": q_format(w, p),
                      "rentang": "[%.12g, %.12g]" % (float(lo), float(hi)),
                      "rentang_int": "[%d, %d]" % (lo_i, hi_i), "p": p,
                      "lsb": lsb_lapisan(unit, p), "saturasi": saturasi, "aturan": aturan,
                      "unit": unit, "terukur": True})
        print("%-40s %-24s %-18s %4d %4d %-8s %-12s %s"
              % (nama_noda, "[%.12g, %.12g]" % (float(lo), float(hi)),
                 "[%d, %d]" % (lo_i, hi_i), w, p, q_format(w, p), lsb_lapisan(unit, p),
                 saturasi))
    print()
    print("  rounding rule at every node, and the line it comes from")
    for b in baris:
        print("  %-40s %s" % (b["simpul"], b["aturan"]))
    print()
    print("checks")
    for a in cek["arms"]:
        print("  arm %-28s edge points %s, bins %s, count sum %s, max filled bins %d"
              % (a["arm"], a["edges"], a["bin"], a["cacah_isi"], a["bin_terisi_max"]))
    print("  the edge grid of line 856 has 17 points, so the histogram has 16 bins: the note")
    print("  that speaks of a 17 bin histogram counts the edges and not the bins")
    print("  the entropy nodes are irrational, so their range is a certified bracket: the root")
    print("  and the ratio by integer square root, the logarithms by Decimal at %d digits"
          % _DIGIT_AKAR)
    print()
    return {"cek": cek, "baris": baris}


def cetak_markdown_lapisan(hasil_tabel, nama):
    """TABLE 3 as markdown, so it can be pasted into a design document."""
    if not hasil_tabel:
        return
    baris = hasil_tabel["baris"]
    print()
    print("TABLE 3, fixed point nodes of the window feature layer, markdown, record %s" % nama)
    print()
    print("| node | measured range (unit) | stored integer range | W two's comp | p | Q format | "
          "LSB exact | saturation point | rounding rule at this node |")
    print("|" + "---|" * 9)
    for b in baris:
        print("| %s | %s | %s | %d | %d | `%s` | %s | %s | %s |"
              % (b["simpul"], b["rentang"], b.get("rentang_int", "-"), b["lebar_bit"], b["p"],
                 b["q_format"], b["lsb"] if "lsb" in b else "-",
                 b["saturasi"].replace("|", "\\|"), b["aturan"].replace("|", "\\|")))
    print()


# =============================================================================================
# Main
# =============================================================================================

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="qformat.py",
        description="quantization calculator and measured bit-width table of the AFIB-LITE "
                    "chain, for the RTL port",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="runs with no mandatory argument: tools/qformat.py alone prints the table of "
               "the frozen 04015 fixture in plain text and in markdown")
    ap.add_argument("--rekaman", default=DEFAULT_RECORD, metavar="NAMA",
                    help="recording to measure: the fixture name (default %(default)s), a path "
                         "to a .npz fixture, or an AFDB record name read through the frozen "
                         "adapter")
    ap.add_argument("--frame", type=int, default=DEFAULT_FRAMES, metavar="N",
                    help="samples to read from a WFDB record (default %(default)s)")
    ap.add_argument("--bentuk", choices=("teks", "markdown", "keduanya"), default="keduanya",
                    help="output shape: plain text, markdown, or both (default %(default)s)")
    ap.add_argument("--markdown", action="store_true",
                    help="shorthand for --bentuk keduanya")
    ap.add_argument("--teks-saja", action="store_true",
                    help="shorthand for --bentuk teks")
    ap.add_argument("--sidik-jari", action=argparse.BooleanOptionalAction, default=True,
                    help="print the sha256 fingerprint of every model file the table "
                         "depends on, so the table can be traced to a code version "
                         "(default %(default)s)")
    ap.add_argument("--tanpa-sidik-jari", dest="sidik_jari", action="store_false",
                    help="alias of --no-sidik-jari")
    ap.add_argument("--potongan", type=int, default=4096, metavar="N",
                    help="length of the separate short slice on which the exactness of the "
                         "integer square is proved (default %(default)s)")
    ap.add_argument("--bit-ambang", type=int, default=16, metavar="B",
                    help="one extra word width of the classifier threshold grid, in bits, "
                         "beside the fixed 12, 14, 16, 18 and 20 (default %(default)s)")
    ap.add_argument("--lapisan-fitur", action="store_true",
                    help="also print TABLE 3, the fixed point node table of the window feature "
                         "layer, measured down to the intermediate values, with the binary point "
                         "of every division and root and the rounding rule of every node")
    a = ap.parse_args(argv)

    if a.teks_saja and a.markdown:
        raise SystemExit("--teks-saja and --markdown contradict each other")
    if a.markdown:
        bentuk = ("teks", "markdown")
    elif a.teks_saja:
        bentuk = ("teks",)
    elif a.bentuk == "keduanya":
        bentuk = ("teks", "markdown")
    else:
        bentuk = (a.bentuk,)

    # ------------------------------------------------------------------ the recording
    npz_path = pathlib.Path(a.rekaman)
    if str(a.rekaman).endswith(".npz") or (npz_path.exists() and npz_path.is_file()):
        d = np.load(npz_path)
        sumber_rekaman = "frozen fixture at %s, key masukan16" % npz_path
        fid = {"path": npz_path, "data": d, "masukan16": d["masukan16"],
               "sidik": sidik_jari(npz_path), "sumber": sumber_rekaman}
        nama = npz_path.stem
    else:
        fid = muat_fixture(a.rekaman)
        nama = a.rekaman
        if fid is None:
            fid = muat_wfdb(a.rekaman, a.frame)
        sumber_rekaman = fid["sumber"]

    masukan16 = fid["masukan16"]
    c = jalankan_rantai(masukan16)
    rentang = c.rentang_terukur()
    lebar = c.lebar()
    lebar_tt = c.lebar_tanpa_tanda()
    hasil = c.hasil()

    tabel, cocok, beda = baris_sampul(rentang, lebar, lebar_tt, hasil)
    cek = {"cocok": cocok, "beda": beda}
    if fid["data"] is not None and "turunan" in fid["data"].files:
        cek["kuadrat"] = periksa_kuadrat(fid["data"]["turunan"], a.potongan)
        # The frozen fixture is the oracle of the frozen chain, so the arrays of this run are
        # compared with it element for element. A run that did not reproduce the fixture would
        # make every measured range below a statement about a different chain.
        cek["fixture_sama"] = {}
        for k in ("masukan16", "lp", "hp", "turunan", "kuadrat", "jendela"):
            if k in fid["data"].files:
                cek["fixture_sama"][k] = bool(np.array_equal(
                    np.asarray(hasil[k]), np.asarray(fid["data"][k])))
        for k in ("puncak", "qrs", "rr"):
            if k in fid["data"].files:
                cek["fixture_sama"][k] = bool(np.array_equal(
                    np.asarray(hasil[k]), np.asarray(fid["data"][k])))
    else:
        cek["kuadrat"] = periksa_kuadrat(np.asarray(hasil["turunan"]), a.potongan)
        cek["fixture_sama"] = None
    luapan = demo_luapan()

    info = {"nama": nama, "sampel": int(masukan16.size)}
    print("AFIB-LITE quantization calculator and measured bit-width table, for the RTL port")
    print("=" * 108)
    print("record            : %s, %d samples, %s" % (nama, info["sampel"], sumber_rekaman))
    print("interpreter       : %s" % sys.executable)
    print("chain constants   : FS_HZ %d, GAIN_COUNT 2047/5 = %.4f counts per mV, CLAMP %d, "
          "GESER_KIRI %d, GESER_AMBANG %d, N_A %d, N_B %d, RADIUS_PUNCAK %d, JENDELA_F %d, "
          "PANTUL %d, SETENGAH_JENDELA %d, DELAPAN %d, RR_GAP_CEILING_MS %d"
          % (R.FS_HZ, R.GAIN_COUNT, R.CLAMP, R.GESER_KIRI, R.GESER_AMBANG, R.N_A, R.N_B,
             R.RADIUS_PUNCAK, R.JENDELA_F, R.PANTUL, R.SETENGAH_JENDELA, R.DELAPAN,
             R.RR_GAP_CEILING_MS))
    print("one count         : 5/2047 mV = %.4e mV, so the input word LSB is 5/32752 mV"
          % float(MV_PER_COUNT))
    if a.sidik_jari:
        print("model fingerprints, so this table can be traced to a code version")
        for nm, path in (("rantai.py", MODEL_DIR / "rantai.py"),
                         ("adapter.py", MODEL_DIR / "adapter.py"),
                         ("fixture/record", fid["path"])):
            h = sidik_jari(path)
            print("  %-14s %-60s %s" % (nm, str(path), h if h else "absent"))
    else:
        print("model fingerprints suppressed by --no-sidik-jari / --tanpa-sidik-jari")
    if cek["fixture_sama"] is not None:
        semua = all(cek["fixture_sama"].values())
        print("fixture self-check : every array of this run against the frozen fixture: %s"
              % ("ALL EQUAL" if semua else "DIFFERENT"))
        for k, v in cek["fixture_sama"].items():
            print("  %-14s %s" % (k, "equal" if v else "DIFFERENT"))

    if "teks" in bentuk:
        cetak_teks(tabel, info, sumber_rekaman, cek, luapan, rentang)
    if "markdown" in bentuk:
        cetak_markdown(tabel, cek, rentang, nama)
    cetak_pecahan(fid["data"], a.bit_ambang)
    if a.lapisan_fitur:
        hasil_tabel = cetak_lapisan_fitur(fid["data"], hasil, nama, int(masukan16.size))
        if "markdown" in bentuk:
            cetak_markdown_lapisan(hasil_tabel, nama)
    print("nothing was written: no fixture, no model file and no record was modified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
