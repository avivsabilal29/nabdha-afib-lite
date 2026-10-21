#!/usr/bin/env python3
"""AFIB-LITE phase 6 step S5 gate: re-derivation of the AND gate thresholds.

The AND gate of the window decision layer is a pair of thresholds, one on the ratio
feature (RMSSD divided by the mean RR) and one on the normalized entropy feature. A
window is called AFIB only when both thresholds are exceeded.

The locked pair 0.21 and 0.70 was derived on the NeuroKit reference peak series. Design
section 6 forbids moving that pair to the detector series, because the median entropy of
class N moved from 0.6506 to 0.3119 when the peak series changed. This script therefore
derives the pair again on the detector series that rantai.py produces on recording 04015,
and reports the new pair next to the old pair and next to the pair derived on the
reference peak series.

Nothing frozen is touched. Every number below is measured in this run. The gate prints
one line per check, then one gate line, and the exit code is 0 only when every check
passes. Nothing is tuned to make a number look good.

Run it with the project interpreter:

    cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/ambang_gerbang.py
"""

import hashlib
import pathlib
import sys
import time

import numpy as np
import wfdb

import rantai as R

HERE = pathlib.Path(__file__).resolve().parent
NPZ = HERE / "fixture" / "04015_30m.npz"
REC = pathlib.Path("/home/avivsabilalm/nabdha-data/afdb/04015")
FRAMES = 450_000
SHA_FIXTURE = "91ff408fb1b7880a124d28bcc4205038935d4a3a2dbabb4c0f7d161d89e8ac4d"
KERNEL_TURUNAN = (2, 1, 0, -1, -2)
PENYEBUT_KERNEL = 8

BARIS = []


def periksa(nama, lulus, keterangan):
    """One report line per check, collected for the gate line at the end."""
    BARIS.append((nama, bool(lulus)))
    print("%-34s %-4s %s" % (nama, "PASS" if lulus else "FAIL", keterangan))
    return bool(lulus)


def kunci_seri(fitur, kelas, k1, k2):
    """Sweep the whole grid of threshold pairs and keep every pair at the best accuracy.

    The tie-break is the one of rantai.turunkan_ambang: largest accuracy, then largest
    Youden, then smallest ratio threshold, then smallest entropy threshold.
    """
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
    pilih = []
    for t1, t2 in seri:
        m = (fitur[:, 1] > t1) & (fitur[:, 3] > t2)
        pilih.append((float(m[af].mean()) + float(1.0 - m[~af].mean()) - 1.0, t1, t2))
    pilih.sort(key=lambda s: (-s[0], s[1], s[2]))
    return terbaik, seri, (pilih[0][1], pilih[0][2])


def dirinci(fitur, kelas, t1, t2):
    """Full window level counts of one threshold pair: sensitivity, specificity, accuracy."""
    af = kelas == "AFIB"
    p = (fitur[:, 1] > t1) & (fitur[:, 3] > t2)
    return dict(t1=t1, t2=t2,
                kepekaan=float(p[af].mean()), spesifisitas=float(1.0 - p[~af].mean()),
                akurasi=float((p == af).mean()),
                jendela=int(kelas.size), afib=int(af.sum()), n=int((~af).sum()),
                dipanggil_afib=int(p.sum()),
                tp=int((p & af).sum()), fp=int((p & ~af).sum()),
                fn=int((~p & af).sum()), tn=int((~p & ~af).sum()))


def jejak_kandidat(nama, fitur, kelas, t1, t2):
    """One row of the candidate table, printed as it is measured."""
    h = dirinci(fitur, kelas, t1, t2)
    print("  %-46s ratio %-6.3f entropy %-6.2f | Se %-7.4f Sp %-7.4f Acc %-7.4f | "
          "windows %3d AFIB %2d called %3d TP %2d FP %2d FN %2d TN %3d"
          % (nama, t1, t2, h["kepekaan"], h["spesifisitas"], h["akurasi"],
             h["jendela"], h["afib"], h["dipanggil_afib"], h["tp"], h["fp"], h["fn"], h["tn"]))
    return h


def main():
    print("S5 threshold re-derivation of the AND gate, on the detector series of 04015")
    print("=" * 132)
    print("fixture                         :", NPZ)
    print("fixture bytes                   :", NPZ.stat().st_size)
    print("interpreter                     :", sys.executable)
    print("recording                       :", REC)
    print()

    h = hashlib.sha256()
    with open(NPZ, "rb") as f:
        for potongan in iter(lambda: f.read(1 << 20), b""):
            h.update(potongan)
    sha = h.hexdigest()
    print("fixture sha256 measured         :", sha)
    print("fixture sha256 locked           :", SHA_FIXTURE)

    d = np.load(NPZ)
    rec = wfdb.rdrecord(str(REC), sampto=FRAMES)
    mentah = rec.p_signal[:, 0].astype(float)
    print("record name and fs              :", rec.record_name, rec.fs, "Hz")
    print("samples fed to the chain        :", mentah.size)
    print()

    # -----------------------------------------------------------------------------------------
    # The derivative kernel, measured, because every phase 5 and phase 6 number stands on it.
    # -----------------------------------------------------------------------------------------
    st = None
    impuls = []
    for i in range(len(KERNEL_TURUNAN) + 3):
        v, st, _r = R.turunan(PENYEBUT_KERNEL if i == 0 else 0, st)
        impuls.append(int(v))
    print("derivative kernel, impulse test : %s, that is %s divided by %d"
          % (impuls[:len(KERNEL_TURUNAN)], list(KERNEL_TURUNAN), PENYEBUT_KERNEL))
    print()

    # -----------------------------------------------------------------------------------------
    # A. Run the chain on the recording itself, not on a copy inside the fixture.
    # -----------------------------------------------------------------------------------------
    print("A. window table reproduced by a real run of the chain")
    print("-" * 132)
    t0 = time.time()
    r = R.Rantai(semai_aktif=True, aturan_t=True, besaran="turunan")
    langkah = r.langkah
    for v in mentah:
        langkah(v)
    on = r.hasil()
    detik = time.time() - t0
    anotasi = wfdb.rdann(str(REC), "atr")
    lab = R.label_irama(anotasi.sample, anotasi.aux_note, FRAMES)
    fitur, kelas = R.kumpulkan_jendela(on["qrs"], lab)
    af = kelas == "AFIB"
    print("  streaming run                 : %.1f s for %d samples" % (detik, mentah.size))
    print("  chain beats, rule on          : %d" % on["qrs"].size)
    print("  chain RR intervals, rule on   : %d" % on["rr"].size)
    print("  decision windows              : %d (AFIB %d, N %d)"
          % (kelas.size, int(af.sum()), int((~af).sum())))
    print("  window feature table          : shape %s %s"
          % (fitur.shape, fitur.dtype))
    print("  fixture window feature table  : shape %s %s"
          % (d["jendela_fitur"].shape, d["jendela_fitur"].dtype))
    print("  fixture window class table    : shape %s %s"
          % (d["jendela_kelas_benar"].shape, d["jendela_kelas_benar"].dtype))
    print()

    fitur_ref, kelas_ref = R.kumpulkan_jendela(
        np.asarray(d["puncak_acuan_neurokit"], dtype=np.int64), lab)
    af_ref = kelas_ref == "AFIB"
    print("  reference NeuroKit series     : beats %d, windows %d (AFIB %d, N %d)"
          % (d["puncak_acuan_neurokit"].size, kelas_ref.size,
             int(af_ref.sum()), int((~af_ref).sum())))
    print()

    # -----------------------------------------------------------------------------------------
    # B. Sweep the whole grid of threshold pairs.
    # -----------------------------------------------------------------------------------------
    k1, k2 = R.kisi_ambang()
    print("B. sweep of the threshold pair grid")
    print("-" * 132)
    print("  locked grid, ratio axis       : %d values %.3f .. %.3f, step %.3f"
          % (k1.size, k1[0], k1[-1], k1[1] - k1[0]))
    print("  locked grid, entropy axis     : %d values %.3f .. %.3f, step %.3f"
          % (k2.size, k2[0], k2[-1], k2[1] - k2[0]))
    print("  locked grid, pairs            : %d" % (k1.size * k2.size))
    t0 = time.time()
    acc_max, seri, pilih = kunci_seri(fitur, kelas, k1, k2)
    print("  sweep wall clock              : %.1f s" % (time.time() - t0))
    benar = int(round(acc_max * kelas.size))
    print("  best accuracy on this grid    : %.10f (%d of %d windows correct)"
          % (acc_max, benar, kelas.size))
    print("  pairs at that best accuracy   : %d" % len(seri))
    t1_seri = sorted({round(s[0], 3) for s in seri})
    t2_seri = sorted({round(s[1], 2) for s in seri})
    print("  ratio thresholds in that set  : %s" % (t1_seri,))
    print("  entropy thresholds in that set: %s" % (t2_seri,))
    print("  every pair at the best accuracy, grouped by entropy threshold")
    pasangan = sorted((round(s[0], 3), round(s[1], 2)) for s in seri)
    for k in t2_seri:
        print("    entropy %.2f : ratio %s"
              % (k, sorted(p[0] for p in pasangan if p[1] == k)))
    print("  tie-break output              : ratio %.3f entropy %.2f" % pilih)
    print()

    # A refinement probe, because the locked entropy axis has a step of 0.01, which is coarse
    # near the best region. It is a probe, not a replacement of the locked grid.
    k1f = np.arange(0.0000, 0.6125 + 1e-12, 0.0025)
    k2f = np.arange(0.020, 0.990, 0.0025)
    acc_f, seri_f, pilih_f = kunci_seri(fitur, kelas, k1f, k2f)
    print("  refined probe, ratio axis     : %d values %.4f .. %.4f, step %.4f"
          % (k1f.size, k1f[0], k1f[-1], k1f[1] - k1f[0]))
    print("  refined probe, entropy axis   : %d values %.3f .. %.3f, step %.4f"
          % (k2f.size, k2f[0], k2f[-1], k2f[1] - k2f[0]))
    print("  refined probe, pairs          : %d" % (k1f.size * k2f.size))
    print("  refined probe best accuracy   : %.10f (%d of %d windows correct)"
          % (acc_f, int(round(acc_f * kelas.size)), kelas.size))
    print("  refined probe pairs at best   : %d" % len(seri_f))
    print("  refined probe ratio range     : %.4f .. %.4f"
          % (min(s[0] for s in seri_f), max(s[0] for s in seri_f)))
    print("  refined probe entropy range   : %.4f .. %.4f"
          % (min(s[1] for s in seri_f), max(s[1] for s in seri_f)))
    print("  refined probe tie-break       : ratio %.4f entropy %.4f" % pilih_f)
    print("  gain of the refined probe     : %d windows more correct out of %d, "
          "that is %.4f accuracy points"
          % (int(round(acc_f * kelas.size)) - benar, kelas.size, acc_f - acc_max))
    print()

    # -----------------------------------------------------------------------------------------
    # C. The four candidate policies, side by side.
    # -----------------------------------------------------------------------------------------
    ambang = R.turunkan_ambang(fitur, kelas, k1, k2)
    ambang_ref = R.turunkan_ambang(fitur_ref, kelas_ref, k1, k2)
    non_degen = [s for s in seri if s[0] > 0.0]
    yn = []
    for t1, t2 in non_degen:
        m = (fitur[:, 1] > t1) & (fitur[:, 3] > t2)
        yn.append((float(m[af].mean()) + float(1.0 - m[~af].mean()) - 1.0, t1, t2))
    yn.sort(key=lambda s: (-s[0], s[1], s[2]))
    pilih_nd = (yn[0][1], yn[0][2])

    print("C. four candidate policies, side by side")
    print("-" * 132)
    print("  evaluated on the detector series, %d windows with %d AFIB and %d N"
          % (kelas.size, int(af.sum()), int((~af).sum())))
    print("  evaluated on the reference series, %d windows with %d AFIB and %d N"
          % (kelas_ref.size, int(af_ref.sum()), int((~af_ref).sum())))
    print()
    baris_kandidat = []
    baris_kandidat.append(("1 locked pair, 0.21 and 0.70",
                           jejak_kandidat("1 locked pair, 0.21 and 0.70", fitur, kelas,
                                          R.AMBANG_LAMA_RASIO, R.AMBANG_LAMA_ENTROPI)))
    baris_kandidat.append(("2 derived on the detector series",
                           jejak_kandidat("2 derived on the detector series", fitur, kelas,
                                          ambang["t1"], ambang["t2"])))
    baris_kandidat.append(("3 derived on the reference NeuroKit series, own series",
                           jejak_kandidat("3 derived on the reference series, own windows",
                                          fitur_ref, kelas_ref,
                                          ambang_ref["t1"], ambang_ref["t2"])))
    baris_kandidat.append(("4 best non-degenerate, ratio above zero",
                           jejak_kandidat("4 best with ratio above zero", fitur, kelas,
                                          pilih_nd[0], pilih_nd[1])))
    brs = baris_kandidat[0][1]
    print()
    print("  the same four pairs crossed over both series, because at run time the chain")
    print("  always classifies its own windows")
    jejak_kandidat("1 locked pair on the reference series", fitur_ref, kelas_ref,
                   R.AMBANG_LAMA_RASIO, R.AMBANG_LAMA_ENTROPI)
    jejak_kandidat("2 detector pair on the reference series", fitur_ref, kelas_ref,
                   ambang["t1"], ambang["t2"])
    jejak_kandidat("3 reference pair on the detector series", fitur, kelas,
                   ambang_ref["t1"], ambang_ref["t2"])
    jejak_kandidat("4 non-degenerate pair on the reference series", fitur_ref, kelas_ref,
                   pilih_nd[0], pilih_nd[1])
    print()

    # -----------------------------------------------------------------------------------------
    # D. What a ratio threshold of 0.000 does.
    # -----------------------------------------------------------------------------------------
    rasio = fitur[:, 1]
    entropi = fitur[:, 3]
    h_nol = dirinci(fitur, kelas, 0.0, ambang["t2"])
    aturan_entropi = entropi > ambang["t2"]
    print("D. what the ratio threshold 0.000 does")
    print("-" * 132)
    print("  windows with ratio above 0.000: %d of %d, so the ratio test never fails at 0.000"
          % (int((rasio > 0.0).sum()), rasio.size))
    print("  smallest ratio feature        : %.6f, so every ratio threshold up to that value "
          "leaves the ratio arm a constant true" % float(rasio.min()))
    print("  largest ratio feature         : %.6f" % float(rasio.max()))
    print("  ratio arm constant true up to : %.6f" % float(rasio.min()))
    print("  pair 0.000 and %.2f calls          : %d windows AFIB, Se %.4f, Sp %.4f, Acc %.4f"
          % (ambang["t2"], h_nol["dipanggil_afib"], h_nol["kepekaan"], h_nol["spesifisitas"],
             h_nol["akurasi"]))
    print("  entropy only, entropy above %.2f  : %d windows AFIB, Se %.4f, Sp %.4f, Acc %.4f"
          % (ambang["t2"], int(aturan_entropi.sum()), float(aturan_entropi[af].mean()),
             float(1.0 - aturan_entropi[~af].mean()), float((aturan_entropi == af).mean())))
    p_nol = (rasio > 0.0) & (entropi > ambang["t2"])
    print("  windows where the two rules differ: %d"
          % int((p_nol != aturan_entropi).sum()))
    print("  median ratio, AFIB and N      : %.4f and %.4f"
          % (float(np.median(rasio[af])), float(np.median(rasio[~af]))))
    print("  median entropy, AFIB and N    : %.4f and %.4f"
          % (float(np.median(entropi[af])), float(np.median(entropi[~af]))))
    print("  rank AUC of the ratio feature : %.4f" % R.auc_rank(rasio[af], rasio[~af]))
    print("  rank AUC of the entropy feature: %.4f" % R.auc_rank(entropi[af], entropi[~af]))
    mayoritas = max(int(af.sum()), int((~af).sum())) / kelas.size
    print("  majority class rule, all N    : %.4f accuracy, so any rule below that is worse "
          "than guessing the majority" % mayoritas)
    b1 = max(float(((rasio > float(t)) == af).mean()) for t in k1)
    print("  best accuracy of the ratio arm alone on this grid: %.4f" % b1)
    b2 = max(float(((entropi > float(t)) == af).mean()) for t in k2)
    print("  best accuracy of the entropy arm alone on this grid: %.4f" % b2)
    print("  ratio threshold of the best pair that keeps the ratio arm alive: %.3f, "
          "accuracy %.4f" % (pilih_nd[0], dirinci(fitur, kelas, *pilih_nd)["akurasi"]))
    print()

    # -----------------------------------------------------------------------------------------
    # E. Methodological caveat.
    # -----------------------------------------------------------------------------------------
    print("E. methodological caveat, stated before any recommendation")
    print("-" * 132)
    print("  This pair is derived from ONE recording of about 30 minutes, 04015, with %d"
          % kelas.size)
    print("  decision windows and %d AFIB windows. Locking a pair on one recording risks"
          % int(af.sum()))
    print("  overfitting, because another recording can have a different feature spread.")
    print("  The measured spread of the ratio feature on this recording is %.6f to %.6f and"
          % (float(rasio.min()), float(rasio.max())))
    print("  of the entropy feature %.4f to %.4f, and the accuracy is a plateau, not a point:"
          % (float(entropi.min()), float(entropi.max())))
    print("  %d pairs reach the best accuracy on the locked grid, with the entropy threshold"
          % len(seri))
    print("  free between %.2f and %.2f, and the refined probe moves the best accuracy by only"
          % (min(t2_seri), max(t2_seri)))
    print("  %.4f, that is %d windows out of %d. A spread of that size on one recording is not"
          % (acc_f - acc_max, int(round(acc_f * kelas.size)) - benar, kelas.size))
    print("  evidence that a threshold is stable.")
    print()
    print("  Therefore the final locking should wait for a re-derivation over the test")
    print("  recording set of step S6, which adds at least two AFDB recordings and one non")
    print("  fibrillation control recording, and the pair reported here stays a candidate.")
    print("  This script does not decide the final locking.")
    print()
    print("F. kernel dependency")
    print("-" * 132)
    print("  Every phase 5 and phase 6 number stands on the derivative kernel now used by the")
    print("  chain, %s divided by %d, measured above. The 04015 recording never touched the"
          % (list(KERNEL_TURUNAN), PENYEBUT_KERNEL))
    print("  fs/6 peak claim of section 7, because that claim was written for the other kernel")
    print("  %s divided by %d, and that decision is still open with Aviv. If the kernel"
          % ([1, 2, 0, -2, -1], PENYEBUT_KERNEL))
    print("  changes, every number in this step has to be derived again.")
    print()

    # -----------------------------------------------------------------------------------------
    # Checks and the gate line.
    # -----------------------------------------------------------------------------------------
    print("checks, one line each")
    print("-" * 132)
    periksa("fixture untouched", sha == SHA_FIXTURE, "sha256 %s" % sha[:12])
    periksa("recording is the primary copy",
            REC.with_suffix(".hea").exists() and REC.with_suffix(".atr").exists()
            and rec.record_name == REC.name,
            "%s with .hea, .dat and .atr present" % REC)
    periksa("sample count is the frozen 30 minutes", mentah.size == FRAMES,
            "%d samples at %s Hz" % (mentah.size, rec.fs))
    periksa("chain beat series is the fixture one", np.array_equal(on["qrs"], d["qrs"]),
            "%d beats, equal to fixture qrs" % on["qrs"].size)
    periksa("window feature table, zero difference",
            np.array_equal(fitur, d["jendela_fitur"]),
            "shape %s, %d elements, zero difference" % (fitur.shape, fitur.size))
    periksa("window class table, zero difference",
            np.array_equal(kelas, d["jendela_kelas_benar"]),
            "shape %s, %d entries, zero difference" % (kelas.shape, kelas.size))
    periksa("window count and AFIB count", kelas.size == 588 and int(af.sum()) == 95,
            "%d windows including %d AFIB" % (kelas.size, int(af.sum())))
    periksa("derived pair equals the fixture pair",
            np.array_equal(np.array([ambang["t1"], ambang["t2"]]), d["jendela_ambang"]),
            "ratio %.3f entropy %.2f" % (ambang["t1"], ambang["t2"]))
    periksa("reference pair equals the fixture pair",
            np.array_equal(np.array([ambang_ref["t1"], ambang_ref["t2"]]),
                           d["jendela_ambang_ref"]),
            "ratio %.3f entropy %.2f" % (ambang_ref["t1"], ambang_ref["t2"]))
    periksa("locked pair on the detector series",
            abs(brs["akurasi"] - 0.8809523809523809) < 1e-12,
            "Se %.4f Sp %.4f Acc %.4f" % (brs["kepekaan"], brs["spesifisitas"], brs["akurasi"]))
    periksa("derived pair reports the known numbers",
            abs(ambang["kepekaan"] - 0.9263157894736842) < 1e-12
            and abs(ambang["spesifisitas"] - 0.896551724137931) < 1e-12
            and abs(ambang["akurasi"] - 0.9013605442176871) < 1e-12,
            "Se %.4f Sp %.4f Acc %.4f" % (ambang["kepekaan"], ambang["spesifisitas"],
                                          ambang["akurasi"]))
    periksa("reference pair reports the known numbers",
            abs(ambang_ref["kepekaan"] - 0.5684210526315789) < 1e-12
            and abs(ambang_ref["spesifisitas"] - 0.9535353535353536) < 1e-12
            and abs(ambang_ref["akurasi"] - 0.8915254237288136) < 1e-12,
            "Se %.4f Sp %.4f Acc %.4f" % (ambang_ref["kepekaan"], ambang_ref["spesifisitas"],
                                          ambang_ref["akurasi"]))
    periksa("grid is swept whole",
            len(seri) == 75 and k1.size * k2.size == 12028,
            "%d pairs swept, %d at the best accuracy" % (k1.size * k2.size, len(seri)))
    periksa("candidate counts are internally consistent",
            all(b["tp"] + b["fp"] + b["fn"] + b["tn"] == b["jendela"]
                and b["dipanggil_afib"] == b["tp"] + b["fp"]
                and abs(b["kepekaan"] - b["tp"] / b["afib"]) < 1e-12
                and abs(b["spesifisitas"] - b["tn"] / b["n"]) < 1e-12
                and abs(b["akurasi"] - (b["tp"] + b["tn"]) / b["jendela"]) < 1e-12
                for _n, b in baris_kandidat),
            "four candidates, each rebuilt from its own predictions")
    periksa("non-degenerate candidate keeps the ratio arm alive",
            pilih_nd[0] > 0.0 and abs(dirinci(fitur, kelas, *pilih_nd)["akurasi"] - acc_max) < 1e-12,
            "ratio %.3f entropy %.2f, accuracy %.4f" % (pilih_nd[0], pilih_nd[1],
                                                        dirinci(fitur, kelas, *pilih_nd)["akurasi"]))
    periksa("ratio arm is a constant true at 0.000", bool((rasio > 0.0).all()),
            "every ratio value is above %.6f" % float(rasio.min()))
    periksa("derivative kernel is the measured one",
            tuple(impuls[:len(KERNEL_TURUNAN)]) == KERNEL_TURUNAN,
            "%s divided by %d" % (list(KERNEL_TURUNAN), PENYEBUT_KERNEL))
    sumber = pathlib.Path(__file__).read_text()
    periksa("source has no em dash or en dash",
            chr(0x2014) not in sumber and chr(0x2013) not in sumber,
            "checked this file, %d bytes" % len(sumber))
    print("-" * 132)
    gagal = [n for n, l in BARIS if not l]
    print("checks: %d, pass: %d, fail: %d" % (len(BARIS), len(BARIS) - len(gagal), len(gagal)))
    if gagal:
        print("gate S5: FAIL, %s" % ", ".join(gagal))
        return 1
    print("gate S5: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
