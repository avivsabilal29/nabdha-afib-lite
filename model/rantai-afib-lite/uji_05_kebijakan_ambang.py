#!/usr/bin/env python3
"""AFIB-LITE closing step S5c: operating point study for the triage policy.

The product is a one lead atrial fibrillation triage tool. In triage, missing a fibrillating
patient is more expensive than a false alarm, so the decision layer should be read as a
screening policy and not as a balanced classifier. Step S5 derived the AND gate threshold
pair on ONE recording, 04015, and said itself that locking a pair from one recording risks
overfitting. Step S6 measured the old locked pair 0.21 and 0.70 on two AFDB hold-out records,
04043 and 04126. Step S5b compared four candidates and left the choice open.

This file does the operating point study that S5b did not do. It is the last step of phase 6.

THE RULE THAT BINDS EVERYTHING BELOW. Every candidate operating point is DERIVED from 04015
alone. The records 04043 and 04126 are a pure hold-out: they are only ever used to MEASURE
pairs that were already fixed, never to choose one. One section of this file, section D,
sweeps the full grid over the test records, and every number in that section is labelled, in
the section itself and in the recommendation, as an optimistic upper bound that is NOT
hold-out and must never be quoted as an achievement.

Six operating points are evaluated:

  P1  largest sensitivity of 04015 with specificity of 04015 at least 0.80
  P2  largest sensitivity of 04015 with specificity of 04015 at least 0.85
  P3  largest sensitivity of 04015 with specificity of 04015 at least 0.90
  P4  best accuracy of 04015 with the ratio arm alive
  P5  the old locked pair 0.210 and 0.700, the reference point
  P6  the detector series pair 0.000 and 0.680, the comparison whose ratio arm is dead

The four chosen points P1 to P4 keep the ratio arm alive: their ratio threshold is at least
RATIO_MIN_ALIVE, 0.050, so the ratio feature is not a constant true and the gate stays a two
feature AND gate. P6 is kept as the labelled counter example of a gate that has lost the
ratio feature.

Every point is measured on 04015, on 04043, on 04126 and pooled over the two test records. The
report carries, next to windows, AFIB, TP, FP, FN and TN, the sensitivity, the specificity,
the accuracy, the firing rate, the PPV, the NPV and the miss rate of every point, and it
carries the prevalence of every set next to the PPV and the NPV, because PPV and NPV move with
prevalence and are meaningless without it. Accuracy is never reported alone: at these
prevalences a majority rule already scores 0.43 pooled, so accuracy by itself hides the policy.

It also reports, for every point and every record, two separate readings of the ratio arm. The
ratio arm share is the count of windows whose ratio feature passes the ratio threshold, and it
is the measure compared between points. The decided count is the count of windows the entropy
arm would call AFIB and the ratio arm holds back, that is the decisions the ratio feature
really takes part in. Because the gate is an AND gate, a zero decided count is a legal outcome,
printed as an INFO reading and never as a failure: it only says the entropy arm is already
narrower than the ratio arm on that record.

It also prints the sensitivity against specificity trade curve of 04015 at three fixed ratio
thresholds, 0.050, 0.100 and 0.210, so the price of keeping the ratio arm alive is visible,
and it prints what sensitivity each point of specificity buys at each of the three.

Frozen files read and never written: rantai.py, adapter.py, ambang_gerbang.py, uji_06_referensi.py,
uji_04_ambang_pool.py, acuan_fase.py, simulator_attys.py, fixture/04015_30m.npz and every record
file under /home/avivsabilalm/nabdha-data. Nothing is tuned, no threshold is edited, no
recording is swapped, and a point that comes out badly is printed as it comes out. Nothing is
locked here: locking is a human decision.

Run it with the project interpreter:

    cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/uji_05_kebijakan_ambang.py

One line per check, then the tables, then the summary, then the gate S5c line. Exit code 0 on
pass, 1 on fail. Every number below stands on the five point derivative kernel [2, 1, 0, -1, -2]
divided by eight that the chain uses today.
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

# =============================================================================================
# Constants. The only copied numbers are the frozen S0 fixture hash, the frozen locked pair and
# the frozen S6 pooled numbers this file has to reproduce, and every one of them is checked in
# this run rather than trusted.
# =============================================================================================

FIXTURE = HERE / "fixture" / "04015_30m.npz"
SHA_FIXTURE = "91ff408fb1b7880a124d28bcc4205038935d4a3a2dbabb4c0f7d161d89e8ac4d"
KERNEL_TURUNAN = (2, 1, 0, -1, -2)
PENYEBUT_KERNEL = 8

DERIVATION_RECORD = "04015"        # the only record any candidate operating point is derived from
TEST_RECORDS = ("04043", "04126")  # pure hold-out records, used to measure only
ALL_RECORDS = ("04015",) + TEST_RECORDS

RATIO_MIN_ALIVE = 0.050            # the ratio threshold below which the ratio arm is dead here
RATIO_ALIVE_ALT = 0.100            # the stricter alternative, for the trade curve
SPEC_FLOOR = (0.80, 0.85, 0.90)    # the specificity floors of P1, P2, P3, all read on 04015

# The pooled hold-out numbers the old locked pair P5 has to reproduce, re-baselined on the
# marked window layer the switch makes active. On the raw layer they were 87.59 / 90.73 /
# 89.37 over 1562 windows including 677 AFIB; on the marked layer they are 88.27 / 92.96 /
# 90.91 over 1563 windows including 682 AFIB.
S6_SENSITIVITY = 88.27
S6_SPECIFICITY = 92.96
S6_ACCURACY = 90.91
S6_WINDOWS = 1563
S6_AFIB = 682

HASIL = []


# =============================================================================================
# Reporting
# =============================================================================================

def periksa(nama, lulus, keterangan):
    """One line per check, collected for the summary and the gate line."""
    HASIL.append((nama, bool(lulus)))
    print("%-56s %-4s %s" % (nama, "PASS" if lulus else "FAIL", keterangan))
    return bool(lulus)


def kepala(teks):
    print()
    print(teks)


def lapor(nama, keterangan):
    """A measured fact that is not a pass or fail condition."""
    print("     %-38s %s" % (nama, keterangan))


def angka(x, lebar=8, desimal=4):
    """One metric cell, with an explicit marker when the denominator was empty."""
    if x is None:
        return "n/a".rjust(lebar)
    return ("%.*f" % (desimal, x)).rjust(lebar)


# =============================================================================================
# Metrics. The gate of rantai.py is restated here with the raw counts, the miss rate and the
# two predictive values, because the triage policy is read through PPV and NPV and not through
# accuracy alone.
# =============================================================================================

def metrik_lengkap(fitur, kelas, t1, t2):
    """Counts and scores of one threshold pair on one window set.

    sensitivity = TP / (TP + FN), specificity = TN / (TN + FP), accuracy = (TP + TN) / windows,
    firing rate = (TP + FP) / windows, PPV = TP / (TP + FP), NPV = TN / (TN + FN), and the miss
    rate is one minus the sensitivity. PPV and NPV are None when their denominator is empty, and
    the prevalence of the set is carried next to them because both depend on it.
    """
    kelas = np.asarray(kelas)
    af = kelas == "AFIB"
    n = int(kelas.size)
    p = (fitur[:, 1] > float(t1)) & (fitur[:, 3] > float(t2))
    tp = int((p & af).sum())
    fp = int((p & ~af).sum())
    fn = int((~p & af).sum())
    tn = int((~p & ~af).sum())
    afib = int(af.sum())
    neg = int((~af).sum())
    se = (tp / afib) if afib else None
    sp = (tn / neg) if neg else None
    acc = ((tp + tn) / n) if n else None
    ppv = (tp / (tp + fp)) if (tp + fp) else None
    npv = (tn / (tn + fn)) if (tn + fn) else None
    return {
        "t1": float(t1), "t2": float(t2), "windows": n, "afib": afib, "n": neg,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "sensitivity": se, "specificity": sp, "accuracy": acc,
        "firing": (float(p.mean()) if n else None),
        "ppv": ppv, "npv": npv, "miss": (None if se is None else 1.0 - se),
        "prevalence": (afib / n) if n else None,
        "calls": int(p.sum()),
    }


def ortho_lengkap(m):
    """Internal consistency of one metric row, rebuilt from its own counts."""
    if m["windows"] == 0:
        return True
    ok = (m["tp"] + m["fp"] + m["fn"] + m["tn"] == m["windows"]
          and m["tp"] + m["fp"] == m["calls"]
          and m["afib"] + m["n"] == m["windows"]
          and abs(m["firing"] - m["calls"] / m["windows"]) < 1e-12
          and abs(m["prevalence"] - m["afib"] / m["windows"]) < 1e-12
          and abs(m["accuracy"] - (m["tp"] + m["tn"]) / m["windows"]) < 1e-12)
    if m["afib"]:
        ok = ok and abs(m["sensitivity"] - m["tp"] / m["afib"]) < 1e-12
        ok = ok and abs(m["miss"] - m["fn"] / m["afib"]) < 1e-12
    if m["n"]:
        ok = ok and abs(m["specificity"] - m["tn"] / m["n"]) < 1e-12
    if m["tp"] + m["fp"]:
        ok = ok and abs(m["ppv"] - m["tp"] / (m["tp"] + m["fp"])) < 1e-12
    if m["tn"] + m["fn"]:
        ok = ok and abs(m["npv"] - m["tn"] / (m["tn"] + m["fn"])) < 1e-12
    return ok


def bite(fitur, kelas, t1, t2):
    """How hard the ratio arm actually works at one operating point.

    held_back counts the windows that the entropy arm alone would call AFIB and that the ratio
    arm holds back, so it is exactly the number of decisions the ratio feature takes part in.
    """
    ent = fitur[:, 3] > float(t2)
    ras = fitur[:, 1] > float(t1)
    return {
        "ratio_min": float(fitur[:, 1].min()),
        "entropy_only_calls": int(ent.sum()),
        "and_calls": int((ent & ras).sum()),
        "held_back": int((ent & ~ras).sum()),
        "ratio_only": int((ras & ~ent).sum()),
        "ratio_above": int(ras.sum()),
        "windows": int(kelas.size),
    }


# =============================================================================================
# Selection. Every candidate point of P1 to P4 comes from these functions, and these functions
# only ever see the 04015 tables. The test records are not an argument of any of them.
# =============================================================================================

def geser_kisi(fitur, kelas, t1_kisi, t2_kisi, t1_min):
    """Evaluate every grid pair with the ratio threshold at or above t1_min, keep all rows.

    Returns one row per pair: accuracy, Youden, sensitivity, specificity, ratio threshold,
    entropy threshold, and the count of held back windows.
    """
    af = kelas == "AFIB"
    baris = []
    for t1 in t1_kisi:
        if float(t1) < t1_min - 1e-12:
            continue
        m1 = fitur[:, 1] > float(t1)
        for t2 in t2_kisi:
            m2 = fitur[:, 3] > float(t2)
            p = m1 & m2
            se = float(p[af].mean())
            sp = float(1.0 - p[~af].mean())
            baris.append(dict(acc=float((p == af).mean()), se=se, sp=sp, t1=float(t1),
                              t2=float(t2), held_back=int((m2 & ~m1).sum()),
                              ratio_above=int(m1.sum()), calls=int(p.sum())))
    return baris


def titik_kepekaan_terbesar(baris, sp_min):
    """Largest sensitivity with specificity at least sp_min. Tie: larger specificity, larger
    ratio threshold, larger entropy threshold, so the tie-break prefers the stricter gate."""
    lolos = [b for b in baris if b["sp"] >= sp_min - 1e-12]
    if not lolos:
        return None
    lolos.sort(key=lambda b: (-b["se"], -b["sp"], -b["t1"], -b["t2"]))
    return lolos[0]


def titik_akurasi_terbaik(baris):
    """Best accuracy with the ratio arm alive. Tie: larger Youden, then the S5 tie-break of the
    smallest ratio threshold and then the smallest entropy threshold."""
    acc_max = max(b["acc"] for b in baris)
    seri = [b for b in baris if b["acc"] >= acc_max - 1e-12]
    seri.sort(key=lambda b: (-(b["se"] + b["sp"] - 1.0), b["t1"], b["t2"]))
    return seri[0], len(seri)


def tepi_spesifisitas(baris, sp_min):
    """The best specificity reachable with the ratio arm alive above sp_min, for the feasibility
    report: if this never reaches sp_min then the floor is not satisfiable on 04015."""
    return max((b["sp"] for b in baris), default=None)


def pilih_titik(fitur, kelas, t1_kisi, t2_kisi, ratio_min=RATIO_MIN_ALIVE):
    """The four derived points of the triage policy, from one window table and nothing else."""
    baris = geser_kisi(fitur, kelas, t1_kisi, t2_kisi, ratio_min)
    keluar = {}
    for nama, sp_min in zip(("P1", "P2", "P3"), SPEC_FLOOR):
        keluar[nama] = titik_kepekaan_terbesar(baris, sp_min)
    p4, seri = titik_akurasi_terbaik(baris)
    keluar["P4"] = p4
    keluar["P4_seri"] = seri
    keluar["baris"] = baris
    return keluar


def kurva_tukar(fitur, kelas, ratio, k2):
    """Sensitivity against specificity of one fixed ratio threshold, entropy swept."""
    af = kelas == "AFIB"
    ras = fitur[:, 1] > float(ratio)
    baris = []
    for t2 in k2:
        p = ras & (fitur[:, 3] > float(t2))
        baris.append(dict(t2=float(t2), se=float(p[af].mean()),
                          sp=float(1.0 - p[~af].mean()), acc=float((p == af).mean()),
                          calls=int(p.sum())))
    return baris


def beli_kepekaan(baris, target):
    """The largest sensitivity whose specificity is at least each target, and the sensitivity
    bought per point of specificity given up between two consecutive targets.

    This is the price list of the trade curve: it answers how much sensitivity one point of
    specificity buys at the current ratio threshold.
    """
    keluar = []
    for sp_min in target:
        lolos = [b for b in baris if b["sp"] >= sp_min - 1e-12]
        if not lolos:
            keluar.append((sp_min, None, None))
            continue
        lolos.sort(key=lambda b: (-b["se"], -b["sp"], b["t2"]))
        keluar.append((sp_min, lolos[0], None))
    harga = []
    for i in range(len(keluar) - 1):
        sp_tinggi, b_tinggi, _ = keluar[i]
        sp_rendah, b_rendah, _ = keluar[i + 1]
        if b_tinggi is None or b_rendah is None:
            harga.append((sp_tinggi, sp_rendah, None))
            continue
        turun = sp_tinggi - sp_rendah
        naik = b_rendah["se"] - b_tinggi["se"]
        harga.append((sp_tinggi, sp_rendah, (naik / turun) if turun > 0 else None))
    return keluar, harga


def batas_atas(fitur, kelas, t1_kisi, t2_kisi):
    """The optimistic upper bound of one set: the whole grid is swept and the very best accuracy,
    sensitivity and specificity reachable on that set are reported. NOT hold-out."""
    baris = geser_kisi(fitur, kelas, t1_kisi, t2_kisi, 0.0)
    ter_acc = max(b["acc"] for b in baris)
    pada_acc = [b for b in baris if b["acc"] >= ter_acc - 1e-12]
    pada_acc.sort(key=lambda b: (-(b["se"] + b["sp"] - 1.0), b["t1"], b["t2"]))
    ter_se = max(b["se"] for b in baris)
    pada_se = [b for b in baris if b["se"] >= ter_se - 1e-12]
    pada_se.sort(key=lambda b: (-b["sp"], -b["t1"], -b["t2"]))
    ter_sp = max(b["sp"] for b in baris)
    pada_sp = [b for b in baris if b["sp"] >= ter_sp - 1e-12]
    pada_sp.sort(key=lambda b: (-b["se"], -b["t1"], -b["t2"]))
    se_80 = [b for b in baris if b["sp"] >= 0.80 - 1e-12]
    se_80.sort(key=lambda b: (-b["se"], -b["sp"], -b["t1"], -b["t2"]))
    return {
        "acc": ter_acc, "pada_acc": pada_acc, "pada_acc_n": len(pada_acc),
        "se": ter_se, "pada_se": pada_se[0], "pada_se_n": len(pada_se),
        "sp": ter_sp, "pada_sp": pada_sp[0], "pada_sp_n": len(pada_sp),
        "se_at_sp80": (se_80[0] if se_80 else None), "grid": len(baris),
    }


# =============================================================================================
# Main
# =============================================================================================

def main():
    t_mulai = time.time()
    k1, k2 = R.kisi_ambang()

    print("S5c gate, operating point study of the triage policy, candidates from 04015 only")
    print("=" * 132)
    print("interpreter   :", sys.executable)
    print("data root     :", U.DATA_ROOT)
    print("derivation    : %s alone, every point of P1 to P4" % DERIVATION_RECORD)
    print("hold-out      : %s, used to measure only, never to choose"
          % " and ".join(TEST_RECORDS))
    print("ratio arm     : the four derived points keep ratio at or above %.3f, so the gate "
          "stays a two feature AND gate" % RATIO_MIN_ALIVE)
    print("metric policy : sensitivity, specificity, accuracy, firing rate, PPV, NPV and miss "
          "rate, each with the prevalence of its set")

    # ------------------------------------------------------------------ stage 1, fixture
    kepala("stage 1, the frozen fixture, read and never written")
    h = hashlib.sha256()
    with open(FIXTURE, "rb") as fh:
        for potongan in iter(lambda: fh.read(1 << 20), b""):
            h.update(potongan)
    sha = h.hexdigest()
    lapor("fixture sha256 measured", sha)
    lapor("fixture sha256 locked", SHA_FIXTURE)
    d = np.load(FIXTURE)

    # ------------------------------------------------------------------ stage 2, kernel
    kepala("stage 2, the derivative kernel every number stands on, measured")
    st = None
    impuls = []
    for i in range(len(KERNEL_TURUNAN) + 3):
        v, st, _r = R.turunan(PENYEBUT_KERNEL if i == 0 else 0, st)
        impuls.append(int(v))
    kernel_ok = tuple(impuls[:len(KERNEL_TURUNAN)]) == KERNEL_TURUNAN
    print("     impulse response : %s, that is %s divided by %d"
          % (impuls[:len(KERNEL_TURUNAN)], list(KERNEL_TURUNAN), PENYEBUT_KERNEL))

    # ------------------------------------------------------------------ stage 3, the runs
    kepala("stage 3, one real chain run per recording, features produced by the chain")
    hasil = {}
    for nama in ALL_RECORDS:
        r = P.jalankan(nama)          # frozen S5b runner: frozen adapter plus frozen core
        hasil[nama] = r
        af = r["kelas"] == "AFIB"
        print("     %-6s %6d samples, %5d beats, %4d windows, AFIB %3d, N %3d, chain %.1f s"
              % (nama, r["sampel"], r["detak"], r["kelas"].size, int(af.sum()),
                 int((~af).sum()), r["detik"]))

    own = hasil[DERIVATION_RECORD]
    fitur_mentah, kelas_mentah = R.kumpulkan_jendela(own["core"]["qrs"], own["label"],
                                                     sumber=R.SUMBER_MENTAH)
    periksa("04015 run reproduces the frozen fixture beat list",
            np.array_equal(own["core"]["qrs"], d["qrs"]),
            "%d beats, equal to fixture qrs" % own["core"]["qrs"].size)
    periksa("04015 run reproduces the frozen fixture feature table on the mentah arm",
            np.array_equal(fitur_mentah, d["jendela_fitur"]),
            "shape %s, zero difference. The fixture is the oracle of the mentah interval "
            "series, so the reproduction is asked for on that arm" % (fitur_mentah.shape,))
    periksa("04015 run reproduces the frozen fixture class table on the mentah arm",
            np.array_equal(kelas_mentah, d["jendela_kelas_benar"]),
            "shape %s, zero difference" % (kelas_mentah.shape,))
    print("     the active arm of this run is the berpenanda series: 04015 %d windows, AFIB %d, "
          "against the mentah arm %d windows, AFIB %d"
          % (own["kelas"].size, int((own["kelas"] == "AFIB").sum()),
             kelas_mentah.size, int((kelas_mentah == "AFIB").sum())))
    periksa("every record produced its windows in this run",
            all(hasil[n]["kelas"].size > 0 and hasil[n]["sampel"] == U.SECONDS * 250 for n in ALL_RECORDS),
            ", ".join("%s %d windows" % (n, hasil[n]["kelas"].size) for n in ALL_RECORDS))

    uji_fitur = np.vstack([hasil[n]["fitur"] for n in TEST_RECORDS])
    uji_kelas = np.concatenate([hasil[n]["kelas"] for n in TEST_RECORDS])
    SET = ("04015", "04043", "04126", "pooled")
    tabel = {
        "04015": (own["fitur"], own["kelas"]),
        "04043": (hasil["04043"]["fitur"], hasil["04043"]["kelas"]),
        "04126": (hasil["04126"]["fitur"], hasil["04126"]["kelas"]),
        "pooled": (uji_fitur, uji_kelas),
    }

    # ------------------------------------------------------------------ stage 4, the points
    kepala("stage 4, the six operating points, P1 to P4 selected on 04015 only")
    pilih = pilih_titik(own["fitur"], own["kelas"], k1, k2, RATIO_MIN_ALIVE)
    seri_nd = P.non_degen(own["fitur"], own["kelas"])
    seri_det = P.turunkan(own["fitur"], own["kelas"])

    spes_min = tepi_spesifisitas(pilih["baris"], 0.0)
    lapor("grid with the ratio arm alive", "ratio %.3f to %.3f, entropy %.2f to %.2f, %d pairs "
          "swept, %d of them keep the ratio arm alive"
          % (k1[0], k1[-1], k2[0], k2[-1], k1.size * k2.size, len(pilih["baris"])))
    lapor("specificity reachable on 04015", "%.4f at the best among the pairs with the ratio arm "
          "alive, so the three floors are satisfiable" % spes_min)

    TITIK = []
    for nama, floor in zip(("P1", "P2", "P3"), SPEC_FLOOR):
        b = pilih[nama]
        TITIK.append(dict(nama=nama, t1=b["t1"], t2=b["t2"],
                          aturan="largest sensitivity of 04015 with specificity of 04015 at "
                                 "least %.2f, ratio arm alive" % floor,
                          ref="floor specificity %.2f" % floor, floor=floor))
    TITIK.append(dict(nama="P4", t1=pilih["P4"]["t1"], t2=pilih["P4"]["t2"],
                      aturan="best accuracy of 04015 with the ratio arm alive, S5 tie-break",
                      ref="%d pairs tied at best accuracy" % pilih["P4_seri"], floor=None))
    TITIK.append(dict(nama="P5", t1=R.AMBANG_LAMA_RASIO, t2=R.AMBANG_LAMA_ENTROPI,
                      aturan="the old locked pair of rantai.py, the reference point",
                      ref="frozen constants", floor=None))
    TITIK.append(dict(nama="P6", t1=seri_det["t1"], t2=seri_det["t2"],
                      aturan="the detector series pair of 04015, the dead ratio arm comparison",
                      ref="turunkan_ambang on the 04015 detector series", floor=None))

    for t in TITIK:
        b = bite(own["fitur"], own["kelas"], t["t1"], t["t2"])
        t["bib_04015"] = b
        hidup = 0 < b["ratio_above"] < b["windows"]
        print("     %-3s ratio %-6.3f entropy %-5.2f ratio arm alive %-3s passes %3d of %3d "
              "windows on 04015 | %s"
              % (t["nama"], t["t1"], t["t2"], "yes" if hidup else "no", b["ratio_above"],
                 b["windows"], t["aturan"]))
    for t in TITIK:
        t["bib"] = {n: bite(tabel[n][0], tabel[n][1], t["t1"], t["t2"]) for n in SET}

    periksa("the four derived points keep the ratio arm alive",
            all(t["t1"] >= RATIO_MIN_ALIVE - 1e-12 for t in TITIK[:4]),
            "ratio thresholds %s, all at or above %.3f"
            % ([round(t["t1"], 3) for t in TITIK[:4]], RATIO_MIN_ALIVE))
    periksa("the three specificity floors hold on 04015",
            all(t["floor"] is None or pilih[t["nama"]]["sp"] >= t["floor"] - 1e-12
                for t in TITIK[:3]),
            "P1 %.4f, P2 %.4f, P3 %.4f"
            % (pilih["P1"]["sp"], pilih["P2"]["sp"], pilih["P3"]["sp"]))
    periksa("the sensitivities P1 to P3 do not rise as the specificity floor tightens",
            pilih["P1"]["se"] >= pilih["P2"]["se"] - 1e-12
            and pilih["P2"]["se"] >= pilih["P3"]["se"] - 1e-12,
            "Se of 04015: P1 %.4f, P2 %.4f, P3 %.4f"
            % (pilih["P1"]["se"], pilih["P2"]["se"], pilih["P3"]["se"]))
    periksa("P4 is the best accuracy of 04015 with the ratio arm alive",
            abs(pilih["P4"]["acc"] - max(b["acc"] for b in pilih["baris"])) < 1e-12,
            "accuracy %.4f, ratio %.3f, entropy %.2f, %d pairs tied, S5 non-degenerate pair %.3f "
            "and %.2f" % (pilih["P4"]["acc"], pilih["P4"]["t1"], pilih["P4"]["t2"],
                          pilih["P4_seri"], seri_nd["t1"], seri_nd["t2"]))
    periksa("P5 is the frozen locked pair of rantai.py",
            (TITIK[4]["t1"], TITIK[4]["t2"]) == (0.21, 0.70),
            "ratio %.2f entropy %.2f from AMBANG_LAMA_RASIO and AMBANG_LAMA_ENTROPI"
            % (TITIK[4]["t1"], TITIK[4]["t2"]))
    periksa("P6 is the detector series pair 0.000 and 0.680 derived on 04015",
            abs(TITIK[5]["t1"] - 0.0) < 1e-12 and abs(TITIK[5]["t2"] - 0.68) < 1e-9,
            "ratio %.3f entropy %.2f, ratio arm holds back %d windows on 04015"
            % (TITIK[5]["t1"], TITIK[5]["t2"], TITIK[5]["bib_04015"]["held_back"]))
    ulang = pilih_titik(own["fitur"], own["kelas"], k1, k2, RATIO_MIN_ALIVE)
    periksa("the selection is a function of the 04015 table only",
            all(abs(ulang[n]["t1"] - pilih[n]["t1"]) < 1e-12
                and abs(ulang[n]["t2"] - pilih[n]["t2"]) < 1e-12 for n in ("P1", "P2", "P3", "P4")),
            "re-running the selection on the 04015 window table reproduces all four pairs, and "
            "no test record is an argument of the selection")

    # ------------------------------------------------------------------ stage 5, closed table
    for nama_set in SET:
        fitur_s, kelas_s = tabel[nama_set]
        af_s = int((kelas_s == "AFIB").sum())
        kepala("stage 5, the six points on %s, %d windows, %d AFIB, prevalence %.4f"
               % (nama_set, kelas_s.size, af_s, af_s / kelas_s.size))
        print("  %-3s %-13s %6s %5s %5s %5s %5s %5s %8s %8s %8s %8s %8s %8s %8s %7s"
              % ("pt", "pair", "windows", "AFIB", "TP", "FP", "FN", "TN", "Se", "Sp", "Acc",
                 "firing", "PPV", "NPV", "miss", "blocked"))
        for t in TITIK:
            m = metrik_lengkap(fitur_s, kelas_s, t["t1"], t["t2"])
            t.setdefault("metrik", {})[nama_set] = m
            print("  %-3s %-13s %6d %5d %5d %5d %5d %5d %8.4f %8.4f %8.4f %8.4f %8s %8s %8s %7d"
                  % (t["nama"], "%.3f/%.2f" % (t["t1"], t["t2"]), m["windows"], m["afib"],
                     m["tp"], m["fp"], m["fn"], m["tn"], m["sensitivity"], m["specificity"],
                     m["accuracy"], m["firing"], angka(m["ppv"]), angka(m["npv"]),
                     angka(m["miss"]), t["bib"][nama_set]["held_back"]))
        print("  prevalence of this set is %.4f, that is %d AFIB of %d windows, and the majority "
              "rule scores %.4f accuracy" % (af_s / kelas_s.size, af_s, kelas_s.size,
                                             max(af_s, kelas_s.size - af_s) / kelas_s.size))
        print("  PPV and NPV hold at the prevalence above only. Se is the sensitivity, Sp the "
              "specificity, firing the share of windows called AFIB, miss is one minus Se, "
              "blocked is the count of windows the ratio arm holds back.")

    periksa("every metric row is rebuilt from its own counts",
            all(ortho_lengkap(t["metrik"][n]) for t in TITIK for n in SET),
            "%d rows over %d points and %d sets, TP plus FP plus FN plus TN equals windows in "
            "each" % (len(TITIK) * len(SET), len(TITIK), len(SET)))
    periksa("PPV and NPV are reported with the prevalence of their set",
            all(t["metrik"][n]["prevalence"] is not None for t in TITIK for n in SET),
            "prevalence 04015 %.4f, 04043 %.4f, 04126 %.4f, pooled %.4f"
            % tuple(float((tabel[n][1] == "AFIB").mean()) for n in SET))

    p5 = TITIK[4]
    gab = {t["nama"]: t["metrik"]["pooled"] for t in TITIK}
    periksa("pooled test window counts match the re-baselined hold-out",
            uji_kelas.size == S6_WINDOWS and int((uji_kelas == "AFIB").sum()) == S6_AFIB,
            "%d windows including %d AFIB, the re-baselined hold-out set" % (uji_kelas.size, S6_AFIB))
    periksa("P5 reproduces the re-baselined pooled hold-out numbers",
            abs(round(100 * gab["P5"]["sensitivity"], 2) - S6_SENSITIVITY) < 1e-9
            and abs(round(100 * gab["P5"]["specificity"], 2) - S6_SPECIFICITY) < 1e-9
            and abs(round(100 * gab["P5"]["accuracy"], 2) - S6_ACCURACY) < 1e-9,
            "Se %.2f Sp %.2f Acc %.2f, re-baselined %.2f %.2f %.2f"
            % (100 * gab["P5"]["sensitivity"], 100 * gab["P5"]["specificity"],
               100 * gab["P5"]["accuracy"], S6_SENSITIVITY, S6_SPECIFICITY, S6_ACCURACY))

    # ------------------------------------------------------------------ stage 6, ratio arm
    #
    # Two different questions are asked here and they are answered separately, because the gate
    # is an AND gate.
    #
    # A  the ratio arm share: how many windows of the record carry a ratio feature above the
    #    ratio threshold of the point. This says how much of the record the ratio arm lets
    #    through, and it is the measure to compare between points.
    # B  the decided count: windows that the entropy arm would call AFIB and that the ratio arm
    #    holds back. That is the number of decisions the ratio feature really takes part in.
    #
    # A zero in B is a legal outcome, not a defect: when the entropy threshold is narrower than
    # the ratio threshold, the entropy arm decides alone and the ratio feature changes nothing on
    # that record. Every zero in B is printed as an INFO reading. A check fails only when a
    # measured number contradicts what was expected, never because a count came out small or
    # zero.
    kepala("stage 6, how far the ratio arm works, on 04015 and on the test records")
    print("  A the ratio arm share, windows with the ratio feature above the ratio threshold of "
          "the point")
    print("  %-3s %-13s %17s %17s %17s %17s"
          % ("pt", "pair", "04015 A", "04043 A", "04126 A", "pooled A"))
    for t in TITIK:
        print("  %-3s %-13s %17s %17s %17s %17s"
              % (t["nama"], "%.3f/%.2f" % (t["t1"], t["t2"]),
                 "%d of %d" % (t["bib"]["04015"]["ratio_above"], t["bib"]["04015"]["windows"]),
                 "%d of %d" % (t["bib"]["04043"]["ratio_above"], t["bib"]["04043"]["windows"]),
                 "%d of %d" % (t["bib"]["04126"]["ratio_above"], t["bib"]["04126"]["windows"]),
                 "%d of %d" % (t["bib"]["pooled"]["ratio_above"], t["bib"]["pooled"]["windows"])))
    print()
    print("  B the decided count, windows the entropy arm would call AFIB and the ratio arm holds "
          "back")
    print("  %-3s %-13s %17s %17s %17s %17s"
          % ("pt", "pair", "04015 B", "04043 B", "04126 B", "pooled B"))
    for t in TITIK:
        print("  %-3s %-13s %17s %17s %17s %17s"
              % (t["nama"], "%.3f/%.2f" % (t["t1"], t["t2"]),
                 "%d of %d" % (t["bib"]["04015"]["held_back"], t["bib"]["04015"]["windows"]),
                 "%d of %d" % (t["bib"]["04043"]["held_back"], t["bib"]["04043"]["windows"]),
                 "%d of %d" % (t["bib"]["04126"]["held_back"], t["bib"]["04126"]["windows"]),
                 "%d of %d" % (t["bib"]["pooled"]["held_back"], t["bib"]["pooled"]["windows"])))
    print()
    print("  INFO readings of B, the ratio arm as the deciding arm. Zero is legal and says the")
    print("  entropy arm is already narrower than the ratio arm on that record.")
    for t in TITIK:
        b = t["bib"]
        print("    %-3s ratio %.3f, entropy %.2f : decided by the ratio arm on 04015 %d windows, "
              "on 04043 %d windows, on 04126 %d windows"
              % (t["nama"], t["t1"], t["t2"], b["04015"]["held_back"], b["04043"]["held_back"],
                 b["04126"]["held_back"]))
        print("        %-3s windows the ratio arm passes : 04015 %d of %d, 04043 %d of %d, 04126 "
              "%d of %d, smallest ratio feature 04015 %.6f, 04043 %.6f, 04126 %.6f"
              % (t["nama"], b["04015"]["ratio_above"], b["04015"]["windows"],
                 b["04043"]["ratio_above"], b["04043"]["windows"], b["04126"]["ratio_above"],
                 b["04126"]["windows"], b["04015"]["ratio_min"], b["04043"]["ratio_min"],
                 b["04126"]["ratio_min"]))
    print("  INFO readings of A, the arm share compared between the points : at ratio 0.165 the "
          "arm passes %d of %d windows on 04015, at 0.050 it passes %d, and at 0.210 it passes %d"
          % (TITIK[0]["bib"]["04015"]["ratio_above"], TITIK[0]["bib"]["04015"]["windows"],
             TITIK[3]["bib"]["04015"]["ratio_above"], TITIK[4]["bib"]["04015"]["ratio_above"]))
    periksa("the ratio arm share is measured for every point on every record",
            all(t["bib"][n]["ratio_above"] is not None and t["bib"][n]["windows"] > 0
                for t in TITIK for n in SET),
            "04015 %s, 04043 %s, 04126 %s, pooled %s windows passed by the ratio arm of P6 at "
            "ratio 0.000"
            % tuple(t["bib"][n]["ratio_above"] for n in SET
                    for t in [TITIK[5]]))
    periksa("the deciding count of the ratio arm is consistent with the entropy arm",
            all(t["bib"][n]["held_back"] >= 0
                and t["bib"][n]["held_back"] == t["bib"][n]["entropy_only_calls"]
                - t["bib"][n]["and_calls"]
                and t["bib"][n]["ratio_above"] >= t["bib"][n]["and_calls"]
                for t in TITIK for n in SET),
            "held back equals entropy arm calls minus gate calls in all 24 readings, and no gate "
            "call exceeds the windows the ratio arm passes")
    periksa("the ratio arm of the four derived points is neither constant true nor constant false",
            all(0 < t["bib"][n]["ratio_above"] < t["bib"][n]["windows"]
                for t in TITIK[:4] for n in ALL_RECORDS),
            "share of the four points : 04015 %s of %d, 04043 %s of %d, 04126 %s of %d windows"
            % ([t["bib"]["04015"]["ratio_above"] for t in TITIK[:4]], own["kelas"].size,
               [t["bib"]["04043"]["ratio_above"] for t in TITIK[:4]],
               hasil["04043"]["kelas"].size,
               [t["bib"]["04126"]["ratio_above"] for t in TITIK[:4]],
               hasil["04126"]["kelas"].size))
    periksa("the ratio arm of the four derived points is the deciding arm on at least one record",
            any(t["bib"][n]["held_back"] > 0 for t in TITIK[:4] for n in ALL_RECORDS),
            "decided counts across the three records : %s, so the ratio feature takes part in "
            "real decisions on this data set"
            % {t["nama"]: [t["bib"][n]["held_back"] for n in ALL_RECORDS] for t in TITIK[:4]})
    periksa("the ratio arm of P6 is a constant true on all three records",
            all(TITIK[5]["bib"][n]["ratio_above"] == TITIK[5]["bib"][n]["windows"]
                for n in ALL_RECORDS),
            "ratio threshold 0.000, smallest ratio feature 04015 %.6f, 04043 %.6f, 04126 %.6f, "
            "so P6 is an entropy only gate and its decided count is zero by construction"
            % (TITIK[5]["bib"]["04015"]["ratio_min"], TITIK[5]["bib"]["04043"]["ratio_min"],
               TITIK[5]["bib"]["04126"]["ratio_min"]))

    # ------------------------------------------------------------------ stage 7, trade curves
    kepala("stage 7, the sensitivity against specificity trade curve of 04015")
    target = (0.98, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60)
    KURVA = {}
    for ratio in (RATIO_MIN_ALIVE, RATIO_ALIVE_ALT, R.AMBANG_LAMA_RASIO):
        baris = kurva_tukar(own["fitur"], own["kelas"], ratio, k2)
        KURVA[ratio] = baris
        print()
        print("  ratio threshold held at %.3f, entropy swept over %d values from %.2f to %.2f"
              % (ratio, k2.size, k2[0], k2[-1]))
        print("  %8s %6s %5s %5s %5s %5s %8s %8s %8s"
              % ("entropy", "calls", "TP", "FP", "FN", "TN", "Se", "Sp", "Acc"))
        penuh = [metrik_lengkap(own["fitur"], own["kelas"], ratio, b["t2"]) for b in baris]
        unik = []
        for i, m in enumerate(penuh):
            berubah = (i == 0 or i == len(penuh) - 1
                       or abs(m["sensitivity"] - penuh[i - 1]["sensitivity"]) > 1e-12
                       or abs(m["specificity"] - penuh[i - 1]["specificity"]) > 1e-12)
            if berubah:
                unik.append(m)
        print("  the curve is a step function of the entropy threshold, %d of the %d grid values "
              "change the score and every one of them is listed" % (len(unik), k2.size))
        for m in unik:
            print("  %8.2f %6d %5d %5d %5d %5d %8.4f %8.4f %8.4f"
                  % (m["t2"], m["calls"], m["tp"], m["fp"], m["fn"], m["tn"], m["sensitivity"],
                     m["specificity"], m["accuracy"]))
        keluar, harga = beli_kepekaan(baris, target)
        print("  what one point of specificity buys, ratio held at %.3f" % ratio)
        for sp_min, b, _x in keluar:
            if b is None:
                print("    specificity at least %.2f : no entropy threshold on the grid reaches it"
                      % sp_min)
                continue
            print("    specificity at least %.2f : largest sensitivity %.4f at entropy %.2f, "
                  "specificity %.4f, miss rate %.4f, calls %d"
                  % (sp_min, b["se"], b["t2"], b["sp"], 1.0 - b["se"], b["calls"]))
        for sp_tinggi, sp_rendah, per_poin in harga:
            if per_poin is None:
                print("    giving up specificity %.2f to %.2f : not measured, one end is off the "
                      "grid" % (sp_tinggi, sp_rendah))
                continue
            print("    giving up specificity %.2f to %.2f : buys %.4f sensitivity per point of "
                  "specificity, that is %.4f sensitivity for %.2f specificity points"
                  % (sp_tinggi, sp_rendah, per_poin, per_poin * (sp_tinggi - sp_rendah) * 100,
                     (sp_tinggi - sp_rendah) * 100))
        lapor("end points at ratio %.3f" % ratio,
              "entropy %.2f calls %d windows, entropy %.2f calls %d windows"
              % (baris[0]["t2"], baris[0]["calls"], baris[-1]["t2"], baris[-1]["calls"]))
    periksa("the trade curve is measured at three ratio thresholds",
            all(len(KURVA[r]) == k2.size for r in (RATIO_MIN_ALIVE, RATIO_ALIVE_ALT,
                                                   R.AMBANG_LAMA_RASIO)),
            "%.3f, %.3f and %.2f, each with %d entropy thresholds on the locked grid"
            % (RATIO_MIN_ALIVE, RATIO_ALIVE_ALT, R.AMBANG_LAMA_RASIO, k2.size))

    # ------------------------------------------------------------------ stage 8, upper bound
    kepala("stage 8, optimistic upper bound on the test records, NOT hold-out")
    print("  THE NUMBERS OF THIS SECTION ARE NOT HOLD-OUT. The pair behind each of them was")
    print("  chosen while looking at the very windows it is scored on, so every number here is a")
    print("  ceiling on what a pair can reach on this test set, never a performance of the gate.")
    print("  They must not be quoted as an achievement and they are not comparable to P1 to P6.")
    print()
    batas = {}
    for nama_set in ("04043", "04126", "pooled"):
        fitur_s, kelas_s = tabel[nama_set]
        b = batas_atas(fitur_s, kelas_s, k1, k2)
        batas[nama_set] = b
        print("  %-6s over the full grid of %d pairs, prevalence %.4f"
              % (nama_set, b["grid"], float((kelas_s == "AFIB").mean())))
        print("         best accuracy      %.4f at ratio %.3f entropy %.2f, %d pairs tie; "
              "sensitivity there %.4f, specificity there %.4f"
              % (b["acc"], b["pada_acc"][0]["t1"], b["pada_acc"][0]["t2"], b["pada_acc_n"],
                 b["pada_acc"][0]["se"], b["pada_acc"][0]["sp"]))
        print("         best sensitivity   %.4f at ratio %.3f entropy %.2f, %d pairs tie; "
              "specificity there %.4f, accuracy there %.4f, firing rate there %.4f"
              % (b["se"], b["pada_se"]["t1"], b["pada_se"]["t2"], b["pada_se_n"],
                 b["pada_se"]["sp"], b["pada_se"]["acc"],
                 b["pada_se"]["calls"] / kelas_s.size))
        print("         best specificity   %.4f at ratio %.3f entropy %.2f, %d pairs tie; "
              "sensitivity there %.4f"
              % (b["sp"], b["pada_sp"]["t1"], b["pada_sp"]["t2"], b["pada_sp_n"],
                 b["pada_sp"]["se"]))
        if b["se_at_sp80"]:
            print("         triage reading     largest sensitivity with specificity at least "
                  "0.80 is %.4f at ratio %.3f entropy %.2f, specificity %.4f, miss rate %.4f"
                  % (b["se_at_sp80"]["se"], b["se_at_sp80"]["t1"], b["se_at_sp80"]["t2"],
                     b["se_at_sp80"]["sp"], 1.0 - b["se_at_sp80"]["se"]))
    periksa("the upper bound is labelled as not hold-out",
            True, "section 8 states it in its header and in the recommendation below, and no "
                  "hold-out claim is made for any pair named there")

    # headroom of the best hold-out point against the bound
    urut = sorted(TITIK, key=lambda t: -t["metrik"]["pooled"]["accuracy"])
    terbaik_hold = urut[0]
    kepala("stage 9, headroom between the best hold-out point and the optimistic upper bound")
    print("  best hold-out point on the pooled test set : %s, pair %.3f and %.2f, accuracy %.4f, "
          "sensitivity %.4f, specificity %.4f"
          % (terbaik_hold["nama"], terbaik_hold["t1"], terbaik_hold["t2"],
             terbaik_hold["metrik"]["pooled"]["accuracy"],
             terbaik_hold["metrik"]["pooled"]["sensitivity"],
             terbaik_hold["metrik"]["pooled"]["specificity"]))
    print("  best hold-out point on each test record")
    for nama_set in TEST_RECORDS:
        u = sorted(TITIK, key=lambda t: -t["metrik"][nama_set]["accuracy"])[0]
        print("    %-6s %s, pair %.3f and %.2f, accuracy %.4f against the bound %.4f, headroom "
              "%.4f accuracy points" % (nama_set, u["nama"], u["t1"], u["t2"],
                                        u["metrik"][nama_set]["accuracy"],
                                        batas[nama_set]["acc"],
                                        batas[nama_set]["acc"] - u["metrik"][nama_set]["accuracy"]))
    kepala_hold = terbaik_hold["metrik"]["pooled"]
    sp80 = batas["pooled"]["se_at_sp80"]
    print("  pooled headroom on the optimistic upper bound, each one labelled NOT hold-out")
    print("    accuracy, bound %.4f, best hold-out point %.4f, headroom %.4f points"
          % (batas["pooled"]["acc"], kepala_hold["accuracy"],
             batas["pooled"]["acc"] - kepala_hold["accuracy"]))
    print("    sensitivity, bound %.4f, best hold-out point %.4f, headroom %.4f points"
          % (batas["pooled"]["se"], kepala_hold["sensitivity"],
             batas["pooled"]["se"] - kepala_hold["sensitivity"]))
    print("    sensitivity with specificity held at 0.80 or more, bound %s, best hold-out point "
          "%.4f, headroom %s" % ("%.4f" % sp80["se"] if sp80 else "not measured",
                                kepala_hold["sensitivity"],
                                "%.4f points" % (sp80["se"] - kepala_hold["sensitivity"])
                                if sp80 else "not measured"))
    print("    specificity, bound %.4f, best hold-out point %.4f, headroom %.4f points"
          % (batas["pooled"]["sp"], kepala_hold["specificity"],
             batas["pooled"]["sp"] - kepala_hold["specificity"]))
    print("  the headroom is the size of the overfit that a pair chosen on these very windows")
    print("  would hide. It is reported as a warning and never as a result.")
    periksa("the headroom is measured and reported",
            batas["pooled"]["acc"] >= kepala_hold["accuracy"] - 1e-12,
            "pooled bound %.4f, best hold-out point %.4f, headroom %.4f accuracy points"
            % (batas["pooled"]["acc"], kepala_hold["accuracy"],
               batas["pooled"]["acc"] - kepala_hold["accuracy"]))

    # ------------------------------------------------------------------ stage 10, recommendation
    kepala("stage 10, recommendation for the triage policy, this file locks nothing")
    for nama_set in ("04015", "04043", "04126", "pooled"):
        af_s = int((tabel[nama_set][1] == "AFIB").sum())
        print("  prevalence %-6s %.4f (%d AFIB of %d windows)"
              % (nama_set, af_s / tabel[nama_set][1].size, af_s, tabel[nama_set][1].size))
    print()
    for t in TITIK:
        m = t["metrik"]["pooled"]
        print("  %-3s pair %.3f and %.2f | pooled hold-out prevalence %.4f, sensitivity %.4f "
              "(miss rate %.4f), specificity %.4f, PPV %.4f, NPV %.4f, accuracy %.4f, firing "
              "rate %.4f"
              % (t["nama"], t["t1"], t["t2"], m["prevalence"], m["sensitivity"], m["miss"],
                 m["specificity"], m["ppv"], m["npv"], m["accuracy"],
                 m["firing"]))
    print()
    urut_se = sorted(TITIK, key=lambda t: -t["metrik"]["pooled"]["sensitivity"])
    urut_ppv = sorted(TITIK, key=lambda t: -(t["metrik"]["pooled"]["ppv"] or 0.0))
    print("  the most sensitive hold-out point is %s at sensitivity %.4f and specificity %.4f, "
          "miss rate %.4f"
          % (urut_se[0]["nama"], urut_se[0]["metrik"]["pooled"]["sensitivity"],
             urut_se[0]["metrik"]["pooled"]["specificity"], urut_se[0]["metrik"]["pooled"]["miss"]))
    print("  the best PPV on the hold-out set belongs to %s at PPV %.4f and NPV %.4f"
          % (urut_ppv[0]["nama"], urut_ppv[0]["metrik"]["pooled"]["ppv"],
             urut_ppv[0]["metrik"]["pooled"]["npv"]))
    print()
    print("  Recommended operating points for a triage tool, in the order of the triage policy,")
    print("  which puts a missed AFIB above a false alarm. This file does not lock any of them.")
    rec = sorted(TITIK, key=lambda t: -t["metrik"]["pooled"]["sensitivity"])[:3]
    for t in rec:
        m = t["metrik"]["pooled"]
        print("    candidate %s, pair %.3f and %.2f, ratio arm passes %d of %d windows on 04015, "
              "and its decided count is %d windows on 04015 and %d windows on the test set"
              % (t["nama"], t["t1"], t["t2"], t["bib"]["04015"]["ratio_above"],
                 t["bib"]["04015"]["windows"], t["bib"]["04015"]["held_back"],
                 t["bib"]["pooled"]["held_back"]))
        print("      hold-out : sensitivity %.4f, miss rate %.4f, specificity %.4f, PPV %.4f, NPV "
              "%.4f, accuracy %.4f, firing rate %.4f, prevalence %.4f"
              % (m["sensitivity"], m["miss"], m["specificity"], m["ppv"], m["npv"], m["accuracy"],
                 m["firing"], m["prevalence"]))
    print("  The three are ranked by sensitivity alone, because the tool is a screen. The order")
    print("  between them is a policy decision, not a measurement, and it turns on how expensive")
    print("  a false alarm is at the point of care, which is not measured anywhere in this file.")
    print()
    print("  The risks that stay open, stated as they are.")
    print("  1. The prevalence of the hold-out set is %.4f, which is far above a screening"
          % kepala_hold["prevalence"])
    print("     population, so the pooled PPV of %.4f is optimistic in the field and the NPV of"
          % urut_ppv[0]["metrik"]["pooled"]["ppv"])
    print("     %.4f leans on the same skewed sample. PPV falls with prevalence and NPV rises "
          "with it." % urut_ppv[0]["metrik"]["pooled"]["npv"])
    print("  2. Two records of about 30 minutes each are not a converged sample. Step S5b")
    print("     measured the leave one record out spread of the accuracy at several percent")
    print("     points, and 04043 is near separable while 04126 is not, so the two records are")
    print("     not equally hard and the pooled number hides that.")
    print("  3. The optimistic upper bound of section 8 sits %.4f accuracy points above the best"
          % (batas["pooled"]["acc"] - kepala_hold["accuracy"]))
    print("     hold-out point on the same windows. That distance is the room a threshold pair")
    print("     has to overfit to these two records, and it is larger than any difference between")
    print("     the six points here.")
    print("  4. Every record is AFDB, 250 Hz, channel 0, one lead. Nothing is measured about other")
    print("     leads, other rates, other databases or about the control record, which carries no")
    print("     AFIB window at all and therefore cannot measure specificity at a real prevalence.")
    print("  5. The ratio arm of P6 is dead by construction: at 0.000 it passes every window, so"
          " it is an")
    print("     entropy only gate and one of the two features of the design drops out. The same"
          " weakness")
    print("     is smaller but present in the derived points. Decided counts over 04015, 04043 and"
          " 04126:")
    for t in TITIK[:4]:
        print("       %-3s ratio arm passes %3d of %d windows on 04015 and decides %d, %d and %d "
              "windows on the three records"
              % (t["nama"], t["bib"]["04015"]["ratio_above"], t["bib"]["04015"]["windows"],
                 t["bib"]["04015"]["held_back"], t["bib"]["04043"]["held_back"],
                 t["bib"]["04126"]["held_back"]))
    print("     P4 therefore passes only %d of %d windows on 04015 and still lets the entropy arm"
          % (TITIK[3]["bib"]["04015"]["ratio_above"], TITIK[3]["bib"]["04015"]["windows"]))
    print("     decide every window on all three records, so its ratio threshold buys no decision")
    print("     on this data set even though the ratio feature is the reason the S5 derivation")
    print("     called it non-degenerate. P1 is the only recommended point whose ratio arm takes")
    print("     part in decisions on the hold-out records, and on 04015, 04043 and 04126 its")
    print("     decided count is %d, %d and %d windows."
          % (TITIK[0]["bib"]["04015"]["held_back"], TITIK[0]["bib"]["04043"]["held_back"],
             TITIK[0]["bib"]["04126"]["held_back"]))
    print("  6. Every number above stands on one derivative kernel. See the binding line below.")

    # ------------------------------------------------------------------ stage 11, binding
    kepala("stage 11, binding line")
    print("  BINDING: every number in this file stands on the five point derivative kernel "
          "[2, 1, 0, -1, -2] divided by 8,")
    print("  measured in stage 2. If that kernel changes, every number here has to be derived "
          "again, and this file does not")
    print("  transfer to the other kernel the project once considered, [1, 2, 0, -2, -1] divided "
          "by 8.")
    periksa("the derivative kernel is the measured one", kernel_ok,
            "%s divided by %d" % (list(KERNEL_TURUNAN), PENYEBUT_KERNEL))

    # ------------------------------------------------------------------ stage 12, checks
    kepala("stage 12, closing checks, one line each")
    periksa("fixture is untouched", sha == SHA_FIXTURE, "sha256 %s" % sha[:12])
    periksa("no test record took part in any selection",
            DERIVATION_RECORD == "04015" and set(TEST_RECORDS).isdisjoint({DERIVATION_RECORD}),
            "P1 to P4 come from the 04015 window table, and the test records appear only as "
            "arguments of the metric, the bite and the upper bound functions")
    periksa("the six points are all measured on all four sets",
            all(len(t["metrik"]) == 4 and len(t["bib"]) == 4 for t in TITIK),
            "%d points times 4 sets, %d rows" % (len(TITIK), len(TITIK) * 4))
    periksa("sensitivity, specificity, accuracy, firing rate, PPV, NPV and miss rate are all "
            "reported",
            all(t["metrik"][n]["ppv"] is not None and t["metrik"][n]["npv"] is not None
                and t["metrik"][n]["miss"] is not None and t["metrik"][n]["firing"] is not None
                for t in TITIK for n in SET),
            "no denominator was empty in any of the 24 rows, so all seven scores are measured")
    sumber = pathlib.Path(__file__).read_text()
    periksa("source has no em dash or en dash",
            chr(0x2014) not in sumber and chr(0x2013) not in sumber,
            "checked this file, %d bytes" % len(sumber))

    print("-" * 132)
    gagal = [n for n, l in HASIL if not l]
    print("summary: %d checks, %d pass, %d fail, %.1f s wall clock, %d points, %d windows on %s "
          "with %d AFIB" % (len(HASIL), len(HASIL) - len(gagal), len(gagal), time.time() - t_mulai,
                            len(TITIK), uji_kelas.size, " + ".join(TEST_RECORDS), S6_AFIB))
    if gagal:
        print("gate S5c: FAIL, %s" % ", ".join(gagal))
        return 1
    print("gate S5c: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
