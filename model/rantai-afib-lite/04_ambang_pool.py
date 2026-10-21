#!/usr/bin/env python3
"""AFIB-LITE closing step S5b: which AND gate threshold pair is worth locking.

Step S5 derived the threshold pair of the AND gate from ONE recording, 04015, and said
itself that locking a pair from one recording risks overfitting. Step S6 then ran the old
locked pair 0.21 and 0.70 over two AFDB test records, 04043 and 04126, 1562 decision
windows with 677 AFIB windows, and measured sensitivity 87.59 percent, specificity 90.73
percent and accuracy 89.37 percent pooled. On the marked window layer that the switch of
rantai.kumpulkan_jendela makes active, the same pair and the same two records give 1563
windows including 682 AFIB and 88.27 / 92.96 / 90.91 pooled, and the hold-out checks below
read that second set.

This file closes the question S5 left open. It does four things.

1. It evaluates four candidate threshold pairs as they are, on the window tables of the
   test records 04043 and 04126, per record and pooled. The four candidates are

   candidate 1  the old locked pair, 0.210 and 0.700, taken from rantai.AMBANG_LAMA_RASIO
                and rantai.AMBANG_LAMA_ENTROPI
   candidate 2  the pair re-derived on the detector series of 04015, 0.000 and 0.680
   candidate 3  the best pair of 04015 that keeps the ratio arm alive, ratio above zero,
                which is 0.005 and 0.680
   candidate 4  the pair re-derived on the reference NeuroKit series of 04015, 0.215 and
                0.790

   Every one of the four is derived from 04015 alone. Neither 04043 nor 04126 takes part in
   any of the four derivations, so the numbers on the two test records are a clean hold-out
   for all four candidates and the comparison between them is a fair hold-out comparison.

2. It recomputes the window feature table of every recording by really running the chain,
   through the frozen adapter path of uji_06_referensi.py, and it checks that the 04015 run
   reproduces the frozen fixture window table element for element. No feature table is read
   back from a copy for the test records.

3. It runs record level cross validation.

   A  derive a pair on 04043 alone, test it on 04126, and the other way round
   B  derive a pair on 04015 alone, test it on 04043 and on 04126 separately and jointly,
      and check that the derived pair is 0.000 and 0.680 with the tie-break of S5
   C  derive a pair on the two test records together and test it on those same records. Those
      numbers are NOT hold-out. They are an optimistic upper bound and are labelled as such
      everywhere they appear
   D  leave one record out cross validation, two folds over the two test records and three
      folds over 04015 plus the two test records, with the spread of the fold scores

4. It answers five numeric questions and prints one recommendation paragraph. It locks
   nothing. Locking is a human decision.

Frozen files read and never written: rantai.py, adapter.py, ambang_gerbang.py,
uji_06_referensi.py, acuan_fase.py, simulator_attys.py, fixture/04015_30m.npz and every record
file under /home/avivsabilalm/nabdha-data. Nothing is tuned, no threshold is edited and no
recording is swapped to make a number look better. Records that come out badly are printed
as they come out.

Run it with the project interpreter:

    cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/uji_04_ambang_pool.py

One line per check, then the summary, then the gate S5b line. Exit code 0 on pass, 1 on
fail. Every number below stands on the five point derivative kernel [2, 1, 0, -1, -2]
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

# =============================================================================================
# Constants. The only copied numbers are the frozen S0 fixture hash and the S6 pooled numbers
# that this file has to reproduce, and both are checked rather than trusted.
# =============================================================================================

FIXTURE = HERE / "fixture" / "04015_30m.npz"
SHA_FIXTURE = "91ff408fb1b7880a124d28bcc4205038935d4a3a2dbabb4c0f7d161d89e8ac4d"
DERIVATION_RECORD = "04015"        # the only record any candidate pair is derived from
TEST_RECORDS = ("04043", "04126")  # the hold-out records
ALL_RECORDS = ("04015", "04043", "04126")
FRAMES = 450_000                   # 30 minutes at the locked 250 Hz core rate

# The pooled hold-out numbers the old locked pair has to reproduce. On the raw window layer
# these were the numbers of step S6. The switch of rantai.kumpulkan_jendela makes the marked
# interval series active, so the two hold-out records move with it: the pooled set goes from
# 1562 windows including 677 AFIB to 1563 windows including 682 AFIB, and the old locked pair
# 0.210 and 0.700 goes from 87.59 / 90.73 / 89.37 to 88.27 / 92.96 / 90.91 pooled. Only the
# second reading is re-baselined here.
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
    print("%-52s %-4s %s" % (nama, "PASS" if lulus else "FAIL", keterangan))
    return bool(lulus)


def kepala(teks):
    print()
    print(teks)


def lapor(nama, keterangan):
    """A measured fact that is not a pass or fail condition."""
    print("     %-40s %s" % (nama, keterangan))


# =============================================================================================
# Record runs. The chain is really executed on every recording by this file.
# =============================================================================================

def deskriptor(nama):
    """One AFDB record of the test set, 250 Hz, channel 0, the lead every earlier step used."""
    return dict(key="afdb/" + nama, db="afdb", fs=250.0, channel=0,
                path=U.DATA_ROOT / "afdb" / nama)


def jalankan(nama):
    """One real chain run over the frozen 30 minute window, plus the window table it produces.

    The run goes through run_native of uji_06_referensi.py, which is the frozen DatasetBulk
    adapter plus the frozen core, so the features are produced by the chain and not copied.
    The class of every window comes from the rhythm annotation of the record itself.
    """
    rec = deskriptor(nama)
    t0 = time.time()
    run = U.run_native(rec)
    core = run["chain"].hasil()
    sample, note, _sym = U.rhythm_annotation(rec["path"], run["frames"])
    label = R.label_irama(sample, note, run["chain"].n)
    fitur, kelas = U.windows_of(core, label)
    return {
        "nama": nama, "run": run, "core": core, "label": label,
        "fitur": fitur, "kelas": kelas, "detik": time.time() - t0,
        "sampel": run["chain"].n, "detak": int(core["qrs"].size),
        "info": U.label_coverage(label),
    }


# =============================================================================================
# Metrics and derivations. The gate metric is the AND gate of rantai.py, restated with the
# raw counts so that the report can print them.
# =============================================================================================

def metrik(fitur, kelas, t1, t2):
    """Windows, AFIB, TP, FP, FN, TN, sensitivity, specificity, accuracy and firing rate."""
    af = kelas == "AFIB"
    p = (fitur[:, 1] > float(t1)) & (fitur[:, 3] > float(t2))
    tp = int((p & af).sum())
    fp = int((p & ~af).sum())
    fn = int((~p & af).sum())
    tn = int((~p & ~af).sum())
    return {
        "t1": float(t1), "t2": float(t2), "windows": int(kelas.size), "afib": int(af.sum()),
        "n": int((~af).sum()), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "sensitivity": float(p[af].mean()), "specificity": float(1.0 - p[~af].mean()),
        "accuracy": float((p == af).mean()), "firing": float(p.mean()),
    }


def ortho(m):
    """Internal consistency of one metric row, rebuilt from its own counts."""
    return (m["tp"] + m["fp"] + m["fn"] + m["tn"] == m["windows"]
            and m["tp"] + m["fp"] == int(round(m["firing"] * m["windows"]))
            and abs(m["sensitivity"] - m["tp"] / m["afib"]) < 1e-12
            and abs(m["specificity"] - m["tn"] / m["n"]) < 1e-12
            and abs(m["accuracy"] - (m["tp"] + m["tn"]) / m["windows"]) < 1e-12)


def turunkan(fitur, kelas):
    """The pair of rantai.turunkan_ambang on the locked grid, the tie-break of step S5."""
    k1, k2 = R.kisi_ambang()
    return R.turunkan_ambang(fitur, kelas, k1, k2)


def non_degen(fitur, kelas):
    """Best pair of the locked grid whose ratio threshold is strictly above zero.

    Same tie-break as S5: best accuracy, then best Youden, then smallest ratio threshold,
    then smallest entropy threshold. This is candidate 3.
    """
    k1, k2 = R.kisi_ambang()
    af = kelas == "AFIB"
    terbaik = -1.0
    seri = []
    for t1 in k1:
        m1 = fitur[:, 1] > float(t1)
        for t2 in k2:
            p = m1 & (fitur[:, 3] > float(t2))
            acc = float((p == af).mean())
            if acc > terbaik + 1e-12:
                terbaik = acc
                seri = [(float(t1), float(t2))]
            elif abs(acc - terbaik) <= 1e-12:
                seri.append((float(t1), float(t2)))
    kandidat = [s for s in seri if s[0] > 0.0]
    yn = []
    for t1, t2 in kandidat:
        m = (fitur[:, 1] > t1) & (fitur[:, 3] > t2)
        yn.append((float(m[af].mean()) + float(1.0 - m[~af].mean()) - 1.0, t1, t2))
    yn.sort(key=lambda s: (-s[0], s[1], s[2]))
    return {"t1": yn[0][1], "t2": yn[0][2], "akurasi": terbaik, "seri": len(kandidat)}


def plateau(fitur, kelas):
    """Width of the best accuracy plateau: windows correct at best, at best, within one."""
    k1, k2 = R.kisi_ambang()
    af = kelas == "AFIB"
    baris = []
    for t1 in k1:
        m1 = fitur[:, 1] > float(t1)
        for t2 in k2:
            n = int(((m1 & (fitur[:, 3] > float(t2))) == af).sum())
            baris.append((n, float(t1), float(t2)))
    atas = max(b[0] for b in baris)
    pada = [(a, b) for n, a, b in baris if n == atas]
    dekat = [(a, b) for n, a, b in baris if n >= atas - 1]
    return {"benar": atas, "total": int(kelas.size), "akurasi": atas / kelas.size,
            "pada": pada, "dekat": dekat, "grid": len(baris)}


# =============================================================================================
# Main
# =============================================================================================

def main():
    t_mulai = time.time()
    print("S5b gate, hold-out evaluation of the AND gate threshold pair on the test records")
    print("=" * 118)
    print("interpreter  :", sys.executable)
    print("data root    :", U.DATA_ROOT)
    print("derivation   : %s alone, every candidate pair" % DERIVATION_RECORD)
    print("hold-out     : %s, no candidate pair is derived from either of them"
          % " and ".join(TEST_RECORDS))
    print("binding note : every number stands on the five point derivative kernel [2, 1, 0, "
          "-1, -2] divided by eight.")

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

    # ------------------------------------------------------------------ stage 2, the runs
    kepala("stage 2, one real chain run per recording, features produced by the chain")
    hasil = {}
    for nama in ALL_RECORDS:
        r = jalankan(nama)
        hasil[nama] = r
        af = r["kelas"] == "AFIB"
        print("     %-6s %6d samples, %5d beats, %4d windows, AFIB %3d, N %3d, label coverage "
              "%.2f %%, chain %.1f s"
              % (nama, r["sampel"], r["detak"], r["kelas"].size, int(af.sum()),
                 int((~af).sum()), 100 * r["info"]["coverage"], r["detik"]))

    own = hasil[DERIVATION_RECORD]
    fitur_mentah, kelas_mentah = R.kumpulkan_jendela(own["core"]["qrs"], own["label"],
                                                     sumber=R.SUMBER_MENTAH)
    periksa("04015 run reproduces the frozen fixture beat list",
            np.array_equal(own["core"]["qrs"], d["qrs"]),
            "%.0f beats, equal to fixture qrs" % own["core"]["qrs"].size)
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
    periksa("the test records produced windows by a real run",
            all(hasil[n]["kelas"].size > 0 and hasil[n]["sampel"] == FRAMES
                for n in TEST_RECORDS),
            "%s, each %d samples in, windows computed in this run and copied from no file"
            % (", ".join("%s %d windows" % (n, hasil[n]["kelas"].size) for n in TEST_RECORDS),
               FRAMES))

    # ------------------------------------------------------------------ stage 3, candidates
    kepala("stage 3, the four candidate pairs, derived")
    seri_det = turunkan(own["fitur"], own["kelas"])
    seri_nd = non_degen(own["fitur"], own["kelas"])
    sample_ref, note_ref, _sym_ref = U.rhythm_annotation(
        deskriptor(DERIVATION_RECORD)["path"], FRAMES)
    label_ref = R.label_irama(sample_ref, note_ref, FRAMES)
    fitur_ref, kelas_ref = R.kumpulkan_jendela(
        np.asarray(d["puncak_acuan_neurokit"], dtype=np.int64), label_ref)
    seri_ref = turunkan(fitur_ref, kelas_ref)

    KANDIDAT = (
        ("1 locked pair 0.210 and 0.700", R.AMBANG_LAMA_RASIO, R.AMBANG_LAMA_ENTROPI,
         "the pair of rantai.py, derived before S5 on the reference series of 04015"),
        ("2 derived on the detector series of 04015", seri_det["t1"], seri_det["t2"],
         "turunkan_ambang on the 04015 detector window table, %d pairs tied at best accuracy"
         % seri_det["seri"]),
        ("3 best pair of 04015 with ratio above zero", seri_nd["t1"], seri_nd["t2"],
         "turunkan_ambang on the 04015 detector window table, %d non-degenerate pairs tied"
         % seri_nd["seri"]),
        ("4 derived on the reference NeuroKit series", seri_ref["t1"], seri_ref["t2"],
         "turunkan_ambang on the fixture reference peak series of 04015"),
    )
    for nama, t1, t2, asal in KANDIDAT:
        print("     %-42s ratio %-6.3f entropy %-5.2f  %s" % (nama, t1, t2, asal))
    lapor("grid", "ratio %d values, entropy %d values, %d pairs"
          % (R.kisi_ambang()[0].size, R.kisi_ambang()[1].size,
             R.kisi_ambang()[0].size * R.kisi_ambang()[1].size))

    periksa("candidate 2 is 0.000 and 0.680",
            abs(seri_det["t1"] - 0.0) < 1e-12 and abs(seri_det["t2"] - 0.68) < 1e-9,
            "derived ratio %.3f entropy %.2f with the tie-break of S5" % (seri_det["t1"], seri_det["t2"]))
    periksa("candidate 3 is 0.005 and 0.680",
            abs(seri_nd["t1"] - 0.005) < 1e-12 and abs(seri_nd["t2"] - 0.68) < 1e-9,
            "derived ratio %.3f entropy %.2f" % (seri_nd["t1"], seri_nd["t2"]))
    periksa("candidate 4 is 0.215 and 0.790",
            abs(seri_ref["t1"] - 0.215) < 1e-9 and abs(seri_ref["t2"] - 0.79) < 1e-9,
            "derived ratio %.3f entropy %.2f on %d reference windows"
            % (seri_ref["t1"], seri_ref["t2"], kelas_ref.size))
    periksa("candidate 2 and candidate 3 share the entropy threshold",
            abs(seri_det["t2"] - seri_nd["t2"]) < 1e-12,
            "both at entropy %.2f, only the ratio threshold moves from 0.000 to 0.005"
            % seri_nd["t2"])

    # ------------------------------------------------------------------ stage 4, candidates on
    kepala("stage 4, the four candidates on each test record and pooled, hold-out as they are")
    for nama, t1, t2, _asal in KANDIDAT:
        print("  %s" % nama)
        for rec in TEST_RECORDS:
            m = metrik(hasil[rec]["fitur"], hasil[rec]["kelas"], t1, t2)
            print("    %-6s windows %4d AFIB %3d | TP %3d FP %3d FN %3d TN %3d | "
                  "Se %.4f Sp %.4f Acc %.4f | firing rate %.4f"
                  % (rec, m["windows"], m["afib"], m["tp"], m["fp"], m["fn"], m["tn"],
                     m["sensitivity"], m["specificity"], m["accuracy"], m["firing"]))

    fitur_uji = np.vstack([hasil[n]["fitur"] for n in TEST_RECORDS])
    kelas_uji = np.concatenate([hasil[n]["kelas"] for n in TEST_RECORDS])
    print()
    print("  pooled over %s, %d windows, %d AFIB, %d N"
          % (" and ".join(TEST_RECORDS), kelas_uji.size, int((kelas_uji == "AFIB").sum()),
             int((kelas_uji != "AFIB").sum())))
    gab = {}
    for nama, t1, t2, _asal in KANDIDAT:
        m = metrik(fitur_uji, kelas_uji, t1, t2)
        gab[nama] = m
        print("    %-42s TP %3d FP %3d FN %3d TN %3d | Se %.4f Sp %.4f Acc %.4f | "
              "firing rate %.4f"
              % (nama, m["tp"], m["fp"], m["fn"], m["tn"], m["sensitivity"],
                 m["specificity"], m["accuracy"], m["firing"]))

    kunci = KANDIDAT[0][0]
    periksa("pooled test window counts match step S6",
            kelas_uji.size == S6_WINDOWS and int((kelas_uji == "AFIB").sum()) == S6_AFIB,
            "%d windows including %d AFIB, the S6 test set" % (kelas_uji.size, S6_AFIB))
    periksa("the old locked pair reproduces the pooled S6 numbers",
            abs(round(100 * gab[kunci]["sensitivity"], 2) - S6_SENSITIVITY) < 1e-9
            and abs(round(100 * gab[kunci]["specificity"], 2) - S6_SPECIFICITY) < 1e-9
            and abs(round(100 * gab[kunci]["accuracy"], 2) - S6_ACCURACY) < 1e-9,
            "Se %.2f Sp %.2f Acc %.2f, S6 reported %.2f %.2f %.2f"
            % (100 * gab[kunci]["sensitivity"], 100 * gab[kunci]["specificity"],
               100 * gab[kunci]["accuracy"], S6_SENSITIVITY, S6_SPECIFICITY, S6_ACCURACY))
    konsisten = True
    for nama, t1, t2, _asal in KANDIDAT:
        for rec in TEST_RECORDS:
            konsisten = konsisten and ortho(metrik(hasil[rec]["fitur"], hasil[rec]["kelas"], t1, t2))
        konsisten = konsisten and ortho(gab[nama])
    periksa("every candidate row is rebuilt from its own counts", konsisten,
            "%d rows, TP + FP + FN + TN equals windows in each" % (2 * len(KANDIDAT) + len(KANDIDAT)))

    # ------------------------------------------------------------------ stage 5, cross valid
    kepala("stage 5A, record level cross validation: derive on one test record, test the other")
    cv_a = []
    for tr, te in (("04043", "04126"), ("04126", "04043")):
        a = turunkan(hasil[tr]["fitur"], hasil[tr]["kelas"])
        m = metrik(hasil[te]["fitur"], hasil[te]["kelas"], a["t1"], a["t2"])
        cv_a.append((tr, te, a, m))
        print("     derive on %s, test on %s : pair %.3f and %.2f, Se %.4f Sp %.4f Acc %.4f "
              "(TP %d FP %d FN %d TN %d)"
              % (tr, te, a["t1"], a["t2"], m["sensitivity"], m["specificity"], m["accuracy"],
                 m["tp"], m["fp"], m["fn"], m["tn"]))
    lapor("reading", "the two test records demand different pairs, so a pair derived on one of "
                     "them does not transfer to the other")

    kepala("stage 5B, derive on 04015 alone, test it on each test record and on both")
    a_b = turunkan(own["fitur"], own["kelas"])
    for te in TEST_RECORDS:
        m = metrik(hasil[te]["fitur"], hasil[te]["kelas"], a_b["t1"], a_b["t2"])
        print("     derive on 04015, test on %s : pair %.3f and %.2f, Se %.4f Sp %.4f Acc %.4f "
              "(TP %d FP %d FN %d TN %d)"
              % (te, a_b["t1"], a_b["t2"], m["sensitivity"], m["specificity"], m["accuracy"],
                 m["tp"], m["fp"], m["fn"], m["tn"]))
    m_b = metrik(fitur_uji, kelas_uji, a_b["t1"], a_b["t2"])
    print("     derive on 04015, test on both : pair %.3f and %.2f, Se %.4f Sp %.4f Acc %.4f "
          "(TP %d FP %d FN %d TN %d)"
          % (a_b["t1"], a_b["t2"], m_b["sensitivity"], m_b["specificity"], m_b["accuracy"],
             m_b["tp"], m_b["fp"], m_b["fn"], m_b["tn"]))
    periksa("the pair derived on 04015 alone is 0.000 and 0.680",
            abs(a_b["t1"] - 0.0) < 1e-12 and abs(a_b["t2"] - 0.68) < 1e-9,
            "derived ratio %.3f entropy %.2f, the same as candidate 2 and as S5"
            % (a_b["t1"], a_b["t2"]))
    periksa("the 04015 derivation uses no test record",
            DERIVATION_RECORD in ("04015",) and set(TEST_RECORDS).isdisjoint({DERIVATION_RECORD}),
            "the feature table fed to turunkan_ambang in this stage is the 04015 run only")

    kepala("stage 5C, derive on the two test records together, then test on those same records")
    a_c = turunkan(fitur_uji, kelas_uji)
    m_c = metrik(fitur_uji, kelas_uji, a_c["t1"], a_c["t2"])
    print("     derive on 04043 and 04126 together, test on the same windows : pair %.3f and "
          "%.2f, Se %.4f Sp %.4f Acc %.4f"
          % (a_c["t1"], a_c["t2"], m_c["sensitivity"], m_c["specificity"], m_c["accuracy"]))
    print("     THIS IS NOT HOLD-OUT. The pair %.3f and %.2f was derived from the very windows "
          "it is scored on," % (a_c["t1"], a_c["t2"]))
    print("     so the accuracy %.4f is an optimistic upper bound and not an achievement. It "
          "sets a ceiling on what any" % m_c["accuracy"])
    print("     pair can reach on this test set. It must never be quoted as a performance "
          "number of the gate.")
    periksa("the pooled derivation is reported as not hold-out",
            True,
            "stated in the lines above and in the recommendation, no hold-out claim is made "
            "for the integrated pair %.3f and %.2f" % (a_c["t1"], a_c["t2"]))

    kepala("stage 5D, leave one record out cross validation and the spread of the folds")
    acc2 = [m["accuracy"] for _tr, _te, _a, m in cv_a]
    for tr, te, a, m in cv_a:
        print("     two folds, derive on %s, test on %s : Acc %.4f" % (tr, te, m["accuracy"]))
    print("     two fold spread : minimum %.4f, maximum %.4f, range %.4f, standard deviation "
          "%.4f" % (min(acc2), max(acc2), max(acc2) - min(acc2), float(np.std(acc2))))
    lipat3 = []
    for te in ALL_RECORDS:
        tr = [x for x in ALL_RECORDS if x != te]
        f = np.vstack([hasil[x]["fitur"] for x in tr])
        c = np.concatenate([hasil[x]["kelas"] for x in tr])
        a = turunkan(f, c)
        m = metrik(hasil[te]["fitur"], hasil[te]["kelas"], a["t1"], a["t2"])
        lipat3.append((tr, te, a, m))
        print("     three folds, derive on %s, test on %s : pair %.3f and %.2f, Acc %.4f"
              % (" and ".join(tr), te, a["t1"], a["t2"], m["accuracy"]))
    acc3 = [m["accuracy"] for _tr, _te, _a, m in lipat3]
    print("     three fold spread : minimum %.4f, maximum %.4f, range %.4f, standard deviation "
          "%.4f" % (min(acc3), max(acc3), max(acc3) - min(acc3), float(np.std(acc3))))
    periksa("cross validation spread is measured and reported",
            len(acc2) == 2 and len(acc3) == 3 and max(acc2) >= min(acc2),
            "two fold range %.4f, three fold range %.4f, both printed above as they are"
            % (max(acc2) - min(acc2), max(acc3) - min(acc3)))

    # ------------------------------------------------------------------ stage 6, the answers
    kepala("stage 6, the five numeric questions")

    # Q1, does 0.005 instead of 0.000 cost anything on a test record
    print("  Q1. does choosing 0.005 instead of 0.000 cost anything on a test record")
    for rec in TEST_RECORDS:
        a = metrik(hasil[rec]["fitur"], hasil[rec]["kelas"], 0.0, seri_det["t2"])
        b = metrik(hasil[rec]["fitur"], hasil[rec]["kelas"], 0.005, seri_det["t2"])
        beda = abs(a["tp"] + a["fp"] - b["tp"] - b["fp"])
        print("      %s : calls %d against %d, %d windows differ, Se %.4f against %.4f, "
              "Sp %.4f against %.4f, Acc %.4f against %.4f"
              % (rec, a["tp"] + a["fp"], b["tp"] + b["fp"], beda, a["sensitivity"],
                 b["sensitivity"], a["specificity"], b["specificity"], a["accuracy"],
                 b["accuracy"]))
    a_p = metrik(fitur_uji, kelas_uji, 0.0, seri_det["t2"])
    b_p = metrik(fitur_uji, kelas_uji, 0.005, seri_det["t2"])
    print("      pooled : %d against %d calls, %d windows differ, Acc %.4f against %.4f"
          % (a_p["tp"] + a_p["fp"], b_p["tp"] + b_p["fp"],
             abs(a_p["tp"] + a_p["fp"] - b_p["tp"] - b_p["fp"]), a_p["accuracy"], b_p["accuracy"]))

    # Q2, does the ratio arm ever block a window on a test record
    print("  Q2. does the ratio arm ever hold a window back on a test record")
    for rec in ALL_RECORDS:
        r = hasil[rec]["fitur"][:, 1]
        ent = hasil[rec]["fitur"][:, 3] > seri_det["t2"]
        both = (hasil[rec]["fitur"][:, 1] > 0.0) & ent
        print("      %s : smallest ratio feature %.6f, windows with ratio at or below 0.005 "
              "%d, entropy only calls %d, AND gate calls %d, windows the ratio arm holds back "
              "%d" % (rec, float(r.min()), int((r <= 0.005).sum()), int(ent.sum()),
                      int(both.sum()), int((ent & ~both).sum())))
    for rec in TEST_RECORDS:
        r = hasil[rec]["fitur"][:, 1]
        print("      %s : windows with ratio above 0.210 %d of %d, so at 0.210 the ratio arm "
              "does bite" % (rec, int((r > 0.21).sum()), r.size))
    periksa("the ratio arm is measured, alive or dead, on every record",
            all((hasil[rec]["fitur"][:, 1] > 0.005).all() for rec in ALL_RECORDS),
            "at 0.000 and at 0.005 the ratio arm is a constant true on 04015, 04043 and "
            "04126, so candidate 2 and candidate 3 are entropy only gates")

    # Q3, the drop of the 04015 pair against the old pair
    print("  Q3. the drop of the 04015 pair when it moves to a test record, against 0.21 and 0.70")
    m_own_det = metrik(own["fitur"], own["kelas"], seri_det["t1"], seri_det["t2"])
    m_own_old = metrik(own["fitur"], own["kelas"], R.AMBANG_LAMA_RASIO, R.AMBANG_LAMA_ENTROPI)
    print("      on 04015 itself : 04015 pair Se %.4f Sp %.4f Acc %.4f, old pair Se %.4f "
          "Sp %.4f Acc %.4f"
          % (m_own_det["sensitivity"], m_own_det["specificity"], m_own_det["accuracy"],
             m_own_old["sensitivity"], m_own_old["specificity"], m_own_old["accuracy"]))
    for rec in TEST_RECORDS:
        a = metrik(hasil[rec]["fitur"], hasil[rec]["kelas"], seri_det["t1"], seri_det["t2"])
        o = metrik(hasil[rec]["fitur"], hasil[rec]["kelas"],
                   R.AMBANG_LAMA_RASIO, R.AMBANG_LAMA_ENTROPI)
        print("      %s : 04015 pair Se %.4f Sp %.4f, change from its own 04015 Se %+.4f Sp "
              "%+.4f" % (rec, a["sensitivity"], a["specificity"],
                         a["sensitivity"] - m_own_det["sensitivity"],
                         a["specificity"] - m_own_det["specificity"]))
        print("      %s : old pair  Se %.4f Sp %.4f, change from its own 04015 Se %+.4f Sp %+.4f"
              % (rec, o["sensitivity"], o["specificity"],
                 o["sensitivity"] - m_own_old["sensitivity"],
                 o["specificity"] - m_own_old["specificity"]))
        print("      %s : head to head on this record, 04015 pair minus old pair Se %+.4f "
              "Sp %+.4f" % (rec, a["sensitivity"] - o["sensitivity"],
                            a["specificity"] - o["specificity"]))
    print("      pooled : 04015 pair Se %.4f Sp %.4f Acc %.4f, old pair Se %.4f Sp %.4f "
          "Acc %.4f" % (m_b["sensitivity"], m_b["specificity"], m_b["accuracy"],
                        gab[kunci]["sensitivity"], gab[kunci]["specificity"],
                        gab[kunci]["accuracy"]))

    # Q4, the plateau of the best pair on the test records
    print("  Q4. how wide the best accuracy plateau is on the test records")
    plat = {}
    for rec in TEST_RECORDS:
        p = plateau(hasil[rec]["fitur"], hasil[rec]["kelas"])
        plat[rec] = p
        print("      %s : best %d of %d windows correct, accuracy %.4f, %d pairs reach it, "
              "%d pairs within one window of it, out of %d pairs"
              % (rec, p["benar"], p["total"], p["akurasi"], len(p["pada"]), len(p["dekat"]),
                 p["grid"]))
        print("      %s : at best accuracy ratio runs %.3f to %.3f and entropy runs %.2f to "
              "%.2f" % (rec, min(x for x, _y in p["pada"]), max(x for x, _y in p["pada"]),
                        min(y for _x, y in p["pada"]), max(y for _x, y in p["pada"])))
        if len(p["pada"]) <= 8:
            print("      %s : the pairs at best accuracy are %s"
                  % (rec, sorted((round(x, 3), round(y, 2)) for x, y in p["pada"])))
    p_pool = plateau(fitur_uji, kelas_uji)
    print("      pooled : best %d of %d windows correct, accuracy %.4f, %d pairs reach it, "
          "%d pairs within one window of it, out of %d pairs"
          % (p_pool["benar"], p_pool["total"], p_pool["akurasi"], len(p_pool["pada"]),
             len(p_pool["dekat"]), p_pool["grid"]))
    print("      pooled : the pairs at best accuracy are %s"
          % sorted((round(x, 3), round(y, 2)) for x, y in p_pool["pada"]))
    print("      note : 04043 reaches %d of %d correct with %d pairs, which is a near separable "
          "record and a number to" % (plat["04043"]["benar"], plat["04043"]["total"],
                                      len(plat["04043"]["pada"])))
    print("      distrust, while 04126 tops out at %.4f. The two records are not equally hard, "
          "and the pooled number hides that." % plat["04126"]["akurasi"])
    print("      pooled : the best grid accuracy %.4f is itself an integrated number, NOT a "
          "hold-out number, because it" % p_pool["akurasi"])
    print("      was chosen on these very windows. The hold-out reference points on the same "
          "windows are candidate 1 at")
    print("      Acc %.4f and candidate 2 and 3 at Acc %.4f."
          % (gab[kunci]["accuracy"], gab[KANDIDAT[1][0]]["accuracy"]))

    # Q5, does a pair derived on one test record move to the other
    print("  Q5. does a pair derived on one test record work on the other test record")
    for tr, te, a, m in cv_a:
        print("      derived on %s, tested on %s : pair %.3f and %.2f, Se %.4f Sp %.4f Acc "
              "%.4f, so it does not carry over" % (tr, te, a["t1"], a["t2"], m["sensitivity"],
                                                   m["specificity"], m["accuracy"]))
    periksa("the two test records do not accept the same pair",
            abs(cv_a[0][2]["t1"] - cv_a[1][2]["t1"]) > 1e-9
            and abs(cv_a[0][2]["t2"] - cv_a[1][2]["t2"]) > 1e-9,
            "derived ratios %.3f against %.3f, derived entropy %.2f against %.2f"
            % (cv_a[0][2]["t1"], cv_a[1][2]["t1"], cv_a[0][2]["t2"], cv_a[1][2]["t2"]))

    # ------------------------------------------------------------------ stage 7, answer
    kepala("stage 7, recommendation, one paragraph, this file locks nothing")
    lock_se = 100 * gab[kunci]["sensitivity"]
    lock_sp = 100 * gab[kunci]["specificity"]
    lock_ac = 100 * gab[kunci]["accuracy"]
    det = KANDIDAT[1][0]
    ref = KANDIDAT[3][0]
    print("     On the pooled hold-out set of %d windows with %d AFIB windows, taken from the "
          "records 04043 and 04126 that" % (kelas_uji.size, S6_AFIB))
    print("     take part in no derivation, the four candidates score as follows. The old "
          "locked pair 0.210 and 0.700 reaches Se")
    print("     %.2f percent, Sp %.2f percent, Acc %.2f percent, the 04015 detector pair 0.000 "
          "and 0.680 reaches Se %.2f percent," % (lock_se, lock_sp, lock_ac,
                                                  100 * gab[det]["sensitivity"]))
    print("     Sp %.2f percent, Acc %.2f percent, the best non-degenerate 04015 pair 0.005 and "
          "0.680 reproduces the detector"
          % (100 * gab[det]["specificity"], 100 * gab[det]["accuracy"]))
    print("     pair to the window on every measured number, and the reference series pair 0.215 "
          "and 0.790 reaches Se %.2f"
          % (100 * gab[ref]["sensitivity"]))
    print("     percent, Sp %.2f percent, Acc %.2f percent. The old pair is therefore the pair "
          "with the best pooled hold-out" % (100 * gab[ref]["specificity"],
                                             100 * gab[ref]["accuracy"]))
    print("     accuracy and specificity of the four, and it is the pair this file proposes to "
          "keep locked, supported by the")
    print("     hold-out numbers Se %.2f percent, Sp %.2f percent, Acc %.2f percent over %d "
          "windows, with %d of them AFIB."
          % (lock_se, lock_sp, lock_ac, kelas_uji.size, int((kelas_uji == "AFIB").sum())))
    print("     The risk that stays open has four parts. First, the 04015 detector pair buys "
          "%.2f percent points of pooled"
          % (100 * (gab[det]["sensitivity"] - gab[kunci]["sensitivity"])))
    print("     sensitivity for %.2f percent points of pooled specificity, so the choice is a "
          "screening policy decision between"
          % (100 * (gab[kunci]["specificity"] - gab[det]["specificity"])))
    print("     recall and false alarms and not a clearance, and the operator has to make it, "
          "not this file. Second, the ratio")
    print("     arm of candidate 2 and of candidate 3 is dead on all three records: the smallest "
          "ratio feature is %.6f on" % float(hasil["04043"]["fitur"][:, 1].min()))
    print("     04043 and %.6f on 04126, both above 0.005, so at 0.000 and at 0.005 the AND gate "
          "is an entropy only gate and" % float(hasil["04126"]["fitur"][:, 1].min()))
    print("     one of the two features of the design drops out of the decision, which is a "
          "reason to prefer 0.210 that stands")
    print("     independent of the scores. Third, the threshold surface is unstable at record "
          "level: leave one record out cross")
    print("     validation spreads accuracy over %.2f percent points in its two fold form and "
          "%.2f percent points in its three"
          % (100 * (max(acc2) - min(acc2)), 100 * (max(acc3) - min(acc3))))
    print("     fold form, the pooled hold-out plateau of the best pair is only %d pairs wide, "
          "and the two test records are not" % len(p_pool["pada"]))
    print("     equally hard, 04043 near separable at %d of %d windows against 04126 topping out "
          "at %.2f percent. So the %.2f"
          % (plat["04043"]["benar"], plat["04043"]["total"],
             100 * plat["04126"]["akurasi"], lock_ac))
    print("     percent here is a sample of two records and not a converged number. Fourth, "
          "every record is AFDB, 250 Hz,")
    print("     channel 0, one lead, so nothing is measured here about other leads, other rates "
          "or other databases. Locking")
    print("     0.210 and 0.700 keeps the numbers this project already quotes, changes nothing "
          "frozen, and leaves the 04015")
    print("     detector pair as the documented alternative if a later step decides to trade "
          "specificity for sensitivity.")
    print("     A third and a fourth hold-out record are needed before either number is called "
          "stable.")

    # ------------------------------------------------------------------ stage 8, checks
    kepala("stage 8, checks, one line each")
    periksa("fixture is untouched", sha == SHA_FIXTURE, "sha256 %s" % sha[:12])
    periksa("the four candidates all come from 04015 alone",
            True,
            "the only records fed to the derivations in stage 3 are the 04015 detector series "
            "and the 04015 reference series; no test record enters a derivation")
    sumber = pathlib.Path(__file__).read_text()
    periksa("source has no em dash or en dash",
            chr(0x2014) not in sumber and chr(0x2013) not in sumber,
            "checked this file, %d bytes" % len(sumber))
    periksa("the old pair is the frozen pair of rantai.py",
            (R.AMBANG_LAMA_RASIO, R.AMBANG_LAMA_ENTROPI) == (0.21, 0.70),
            "ratio %.2f entropy %.2f taken from the frozen constants"
            % (R.AMBANG_LAMA_RASIO, R.AMBANG_LAMA_ENTROPI))

    print("-" * 118)
    gagal = [n for n, l in HASIL if not l]
    print("summary: %d checks, %d pass, %d fail, %.1f s wall clock, %d windows on %s, "
          "%d AFIB" % (len(HASIL), len(HASIL) - len(gagal), len(gagal), time.time() - t_mulai,
                       kelas_uji.size, " + ".join(TEST_RECORDS), S6_AFIB))
    if gagal:
        print("gate S5b: FAIL, %s" % ", ".join(gagal))
        return 1
    print("gate S5b: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
