#!/usr/bin/env python3
"""S0: freeze the equivalence reference of the AFIB-LITE integer Pan-Tompkins chain.

The script loads the frozen fixture recording AFDB 04015, the first 30 minutes that live in
04015.dat (450000 frames, two 12 bit samples per frame), converts it to the locked 16 bit input
word, and then runs the eight official stages in the official order using functions taken
verbatim from the phase 1 to phase 5 notebooks through acuan_fase.py. No arithmetic is changed
and no number is invented.

Chain, in the order fixed by the product document:
  1. input        : 12 bit samples, clipped to plus minus 2047, shifted left 4 bits
  2. low-pass     : DC gain 36, zeros at multiples of the sample rate divided by six
  3. high-pass    : single pole at z equal to minus one, alternating DC gain 16 and 0
  4. derivative   : five point derivative, exact zero DC gain, group delay 2 samples
  5. squaring     : never negative, 32 bits wide is enough
  6. window       : moving window integration, alternating width 37 and 38 samples
  7. threshold    : adaptive threshold, difference form, shift right, halving, two second init
  8. rr           : RR averaging, queue of eight intervals, exact 25 RR greater or equal 23 AVERAGE2
  9. t wave       : T wave discrimination, slope from the derivative output, cross form

The frozen fixture uses the phase 5 notebook pipeline exactly as it stands, with the defaults
ATURAN_T_BAWAAN True, BESARAN_BAWAAN "turunan", UJI_SETENGAH_BAWAAN "silang", semai_aktif True,
peaks from puncak_radius(sel, 27), and thresholds that start from zero and warm up by themselves.
A single comparison variant, where the threshold starts from the maximum of the first 500
samples following the phase 3 notebook, is measured separately and written to a separate file.
It is never written into the frozen fixture.

Run it with the project interpreter:

    cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/s0_bekukan_acuan.py
"""

import hashlib
import pathlib
import sys
import time

import numpy as np
import wfdb

import acuan_fase as A

HERE = pathlib.Path(__file__).resolve().parent
REC = pathlib.Path("/home/avivsabilalm/.hermes/cache/scratch/afib/afdb_local/04015")
FRAMES = 450_000
FS = 250.0
FIXDIR = HERE / "fixture"
NPZ = FIXDIR / "04015_30m.npz"
FINGERPRINT = FIXDIR / "sidik_jari.txt"
COMPARE = FIXDIR / "pembanding_inisialisasi_fase3.txt"

# Threshold grid of the phase 5 decision layer, copied from t-wave-discrimination.ipynb cell 27.
KISI1 = np.arange(0.00, 0.62, 0.005)
KISI2 = np.arange(0.02, 0.99, 0.01)


def load_recording():
    """Read channel ECG1 of the fixture, the same call the phase 5 notebook makes."""
    rec = wfdb.rdrecord(str(REC), sampto=FRAMES)
    mv = rec.p_signal[:, 0].astype(float)
    return rec, mv


def pipeline_a(mentah):
    """Frozen pipeline: quantization, filter chain, envelope, peaks, threshold stage, RR stage."""
    t0 = time.time()
    masukan = A.kuantisasi(mentah)
    y1, y2, y3 = A.rantai_tapis(masukan)
    A.y3 = y3                       # deret_besaran() reads the module global y3
    ku, sel = A.selubung_bergantian(y3)
    puncak = A.puncak_radius(sel, 27)
    h = A.jalankan(sel, puncak, y2)
    qrs = np.array(h["qrs"], dtype=np.int64)
    rr = np.array(h["rr_ms"], dtype=np.int64)
    rows, tahap = A.jejak_penanda(rr, semai_aktif=True)
    rows = np.array(rows, dtype=np.int64)
    out = dict(masukan16=masukan, lp=y1, hp=y2, turunan=y3, kuadrat=ku, jendela=sel,
               puncak=puncak, qrs=qrs, rr=rr, h=h, tahap=tahap, rows=rows,
               ambang_kemiringan=np.array(h["kem"], dtype=np.int64),
               ambang_puncak_terfilter=np.array(h["pk_f"], dtype=np.int64),
               rasio_pita=np.asarray(h["rasio_pita"], dtype=float),
               rasio_qrs=np.asarray(h["rasio_qrs"], dtype=float),
               ambang_state=np.array([h["calon_kedua"], h["cari_mundur"], h["diperiksa"],
                                      h["ditolak"], h["diterima_pita"], h["berisiko"], h["semai"],
                                      h["penanda"], h["langkah"]], dtype=np.int64))
    print("  chain wall clock                 : %.1f s" % (time.time() - t0))
    return out


def fingerprint_rows(arrays):
    rows = []
    for name in sorted(arrays):
        arr = arrays[name]
        a = np.asarray(arr)
        raw = a.tobytes()
        if a.dtype.kind in "iufb":
            mx = float(np.max(np.abs(a.astype(np.float64)))) if a.size else 0.0
        else:
            mx = float("nan")
        rows.append(dict(name=name, shape=str(a.shape), dtype=str(a.dtype),
                         maxabs=mx, sha256=hashlib.sha256(raw).hexdigest(), nbytes=len(raw)))
    return rows


def write_fingerprint(rows, extra):
    lines = ["# SHA-256 fingerprint of the frozen fixture arrays",
             "# every digest is computed over arr.tobytes() of the array as it is written,",
             "# so it does not depend on the dtype used when the file is read back",
             ""]
    for k, v in extra:
        lines.append("# %-32s %s" % (k, v))
    lines.append("")
    lines.append("| key | shape | dtype | max abs | bytes | sha256 |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        lines.append("| %s | %s | %s | %.6g | %d | %s |" % (r["name"], r["shape"], r["dtype"],
                                                               r["maxabs"], r["nbytes"], r["sha256"]))
    lines.append("")
    FINGERPRINT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return lines


def variant_b_phase3(mentah):
    """Comparison variant: the phase 3 notebook pipeline with the two second threshold init.

    This is not the frozen fixture. It is the phase 3 chain as that notebook runs it, so it
    differs from pipeline A in three ways at once: the filter chain is the closed form version
    (FIR moving average instead of the recursive low-pass), the peak picker is scipy find_peaks
    inside deteksi_puncak instead of puncak_radius, and the threshold starts from the maximum of
    the first 500 samples through nilai_awal_taksiran.
    """
    x = A.kuantisasi__fase3(mentah)
    _, y2b, z3b = A.rantai_tapis__fase3(x)
    sq = (z3b >> A.GESER_AMBANG) ** 2
    selb = A.jendela_jumlah(sq, A.LEBAR_JENDELA)
    puncakb = A.deteksi_puncak(selb)
    awal = A.nilai_awal_taksiran(selb)
    A.AWAL_I = awal
    hk = A.tata_cara_ambang(selb, puncakb, mode_potong="kriteria")
    ht = A.tata_cara_ambang(selb, puncakb, mode_potong="tetap")
    return dict(x=x, y2=y2b, z3=z3b, sq=sq, sel=selb, puncak=puncakb, awal=awal,
                kriteria=hk, tetap=ht, terfilter=np.abs(y2b))


def main():
    FIXDIR.mkdir(parents=True, exist_ok=True)
    print("S0 frozen equivalence reference")
    print("record                           :", REC)
    print("interpreter                      :", sys.executable)
    rec, mentah = load_recording()
    print("header record name and rate      :", rec.record_name, rec.fs, "Hz")
    print("header declared length (samples) :", rec.sig_len)
    print("samples actually read            :", mentah.size)
    print("frames in 04015.dat              :", 450_000, "=", 450_000 / FS / 60.0, "minutes")
    terjepit = int(np.count_nonzero(np.abs(np.rint(mentah * A.GAIN_COUNT)) > A.CLAMP))
    print("clipped input samples            :", terjepit)

    print()
    print("pipeline A, phase 5 defaults, this is the frozen fixture")
    a = pipeline_a(mentah)
    h = a["h"]
    off = A.jalankan(a["jendela"], a["puncak"], a["hp"], aturan_t=False)
    print("  puncak_radius peaks            :", a["puncak"].size,
          "| odd position fraction %.4f" % float(np.mean(a["puncak"] % 2 == 1)))
    print("  bit width lp, hp, derivative   :", int(np.max(np.abs(a["lp"]))).bit_length(),
          int(np.max(np.abs(a["hp"]))).bit_length(), int(np.max(np.abs(a["turunan"]))).bit_length())
    print("  bit width square, envelope     :", int(np.max(a["kuadrat"])).bit_length(),
          int(a["jendela"].max()).bit_length())
    print("  envelope max, median           :", int(a["jendela"].max()), float(np.median(a["jendela"])))
    print("  beats with T wave rule ON      :", len(h["qrs"]))
    print("  beats with T wave rule OFF     :", len(off["qrs"]))
    print("  checked, rejected, accepted    :", h["diperiksa"], h["ditolak"], h["diterima_pita"])
    print("  ratio pool ON, valid QRS pool  :", a["rasio_pita"].size, a["rasio_qrs"].size,
          "| risky QRS ON", h["berisiko"])
    print("  ratio pool OFF, valid QRS OFF  :", np.asarray(off["rasio_pita"]).size,
          np.asarray(off["rasio_qrs"]).size, "| risky QRS OFF", off["berisiko"])
    print("  RR intervals                   :", a["rr"].size)
    print("  marker beats and steps         :", h["penanda"], h["langkah"])
    print("  marker beats and steps, OFF    :", off["penanda"], off["langkah"])
    print("  reseed events, ON and OFF      :", h["semai"], off["semai"])
    print("  ambang_state ON                :", a["ambang_state"].tolist())
    print("  ambang_state OFF               :", [off["calon_kedua"], off["cari_mundur"], off["diperiksa"],
                                                 off["ditolak"], off["diterima_pita"], off["berisiko"],
                                                 off["semai"], off["penanda"], off["langkah"]])

    # Decision layer of the phase 5 notebook, verbatim.
    anotasi = wfdb.rdann(str(REC), "atr")
    lab = A.label_irama(anotasi, FRAMES)
    fitur, kelas = A.kumpulkan_jendela(np.array(h["qrs"], dtype=np.int64), lab)
    ambang = A.turunkan_ambang(fitur, kelas, KISI1, KISI2)
    print("  decision windows               :", kelas.size,
          "(AFIB %d, N %d)" % (int((kelas == "AFIB").sum()), int((kelas == "N").sum())))
    print("  derived thresholds             : ratio %.3f, entropy %.2f, accuracy %.4f"
          % (ambang["t1"], ambang["t2"], ambang["akurasi"]))

    # Reference beat series of the phase 5 notebook, kept because the notebook reports its
    # window counts, so the cross check can compare like with like.
    import neurokit2 as nk
    bersih = nk.ecg_clean(mentah, sampling_rate=int(A.FS), method="pantompkins1985")
    acuan = nk.ecg_findpeaks(bersih, sampling_rate=int(A.FS),
                             method="pantompkins1985")["ECG_R_Peaks"].astype(np.int64)
    fitur_ref, kelas_ref = A.kumpulkan_jendela(acuan, lab)
    fitur_off, kelas_off = A.kumpulkan_jendela(np.array(off["qrs"], dtype=np.int64), lab)
    print("  beats OFF, decision windows    :", kelas_off.size,
          "(AFIB %d, N %d)" % (int((kelas_off == "AFIB").sum()), int((kelas_off == "N").sum())))
    print("  NeuroKit reference RR median ms: %.1f"
          % float(np.median(np.diff(acuan) / A.FS * 1000.0)))
    ambang_ref = A.turunkan_ambang(fitur_ref, kelas_ref, KISI1, KISI2)
    print("  NeuroKit reference beats       :", acuan.size)
    print("  NeuroKit reference windows     :", kelas_ref.size,
          "(AFIB %d, N %d)" % (int((kelas_ref == "AFIB").sum()), int((kelas_ref == "N").sum())))
    print("  NeuroKit reference AUC ratio and entropy: %.4f %.4f"
          % (A.auc_rank(fitur_ref[kelas_ref == "AFIB", 1], fitur_ref[kelas_ref != "AFIB", 1]),
             A.auc_rank(fitur_ref[kelas_ref == "AFIB", 3], fitur_ref[kelas_ref != "AFIB", 3])))
    print("  NeuroKit reference old threshold gate: %s"
          % A.nilai_gerbang(fitur_ref, kelas_ref, A.AMBANG_LAMA_RASIO, A.AMBANG_LAMA_ENTROPI))
    for nama, f, c in (("detector rule ON ", fitur, kelas), ("detector rule OFF", fitur_off, kelas_off),
                       ("reference NeuroKit", fitur_ref, kelas_ref)):
        af = c == "AFIB"
        auc = [float(A.auc_rank(f[af, j], f[~af, j])) for j in range(4)]
        print("  AUC four features, %s: %s"
              % (nama, " ".join("%.4f" % v for v in auc)))
        amb = A.turunkan_ambang(f, c, KISI1, KISI2)
        lama = A.nilai_gerbang(f, c, A.AMBANG_LAMA_RASIO, A.AMBANG_LAMA_ENTROPI)
        print("  gate %s: derived ratio %.3f entropy %.2f accuracy %.4f | old 0.21 and 0.70 accuracy %.4f"
              % (nama, amb["t1"], amb["t2"], amb["akurasi"], lama["akurasi"]))

    rows = a["rows"]
    arrays = {
        "masukan16": a["masukan16"],
        "lp": a["lp"],
        "hp": a["hp"],
        "turunan": a["turunan"],
        "kuadrat": a["kuadrat"],
        "jendela": a["jendela"],
        "puncak": a["puncak"],
        "ambang_state": a["ambang_state"],
        "ambang_kemiringan_puncak": a["ambang_kemiringan"],
        "ambang_puncak_terfilter": a["ambang_puncak_terfilter"],
        "jendela_aturan_t_mati": np.array(off["qrs"], dtype=np.int64),
        "jendela_fitur_aturan_t_mati": fitur_off,
        "jendela_kelas_aturan_t_mati": np.array([str(x) for x in kelas_off], dtype="U6"),
        "rasio_pita": a["rasio_pita"],
        "rasio_qrs": a["rasio_qrs"],
        "rasio_pita_aturan_t_mati": np.asarray(off["rasio_pita"], dtype=float),
        "rasio_qrs_aturan_t_mati": np.asarray(off["rasio_qrs"], dtype=float),
        "qrs": a["qrs"],
        "rr": a["rr"],
        "rr_average1": rows[:, 0],
        "rr_average2": rows[:, 1],
        "rr_antre_panjang": rows[:, 2],
        "penanda": rows[:, 3],
        "rr_disemai": rows[:, 4],
        "rr_riwayat_panjang": rows[:, 5],
        "rr_menyala_akhir": np.array(int(h["menyala_akhir"]), dtype=np.int64),
        "jendela_fitur": fitur,
        "jendela_kelas_benar": np.array([str(x) for x in kelas], dtype="U6"),
        "jendela_ambang": np.array([float(ambang["t1"]), float(ambang["t2"])]),
        "jendela_ambang_ref": np.array([float(ambang_ref["t1"]), float(ambang_ref["t2"])]),
        "jendela_fitur_acuan": fitur_ref,
        "jendela_kelas_acuan": np.array([str(x) for x in kelas_ref], dtype="U6"),
        "puncak_acuan_neurokit": acuan,
    }
    arrays["rr_menyala_akhir"] = np.array(int(h["menyala_akhir"]), dtype=np.int64)
    np.savez(NPZ, **arrays)
    print()
    print("saved                             :", NPZ, NPZ.stat().st_size, "bytes")

    fp = fingerprint_rows(arrays)
    extra = [("record", str(REC)), ("frames read", str(FRAMES)), ("fs Hz", str(FS)),
             ("sample clipping count", str(terjepit)),
             ("ambang_state order", "calon_kedua, cari_mundur, diperiksa, ditolak, diterima_pita, "
                                    "berisiko, semai, penanda, langkah"),
             ("jendela_fitur columns", "RMSSD, RMSSD/meanRR, pNN50, normalized entropy"),
             ("npz sha256", hashlib.sha256(NPZ.read_bytes()).hexdigest())]
    lines = write_fingerprint(fp, extra)
    print("fingerprint                       :", FINGERPRINT)
    digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    print("fingerprint content sha256        :", digest)
    for r in fp:
        print("  %-30s %-14s %-8s %14.6g %s" % (r["name"], r["shape"], r["dtype"], r["maxabs"],
                                                 r["sha256"][:16]))

    # Comparison variant, never written into the frozen fixture.
    print()
    print("comparison variant, phase 3 pipeline with the two second threshold init")
    b = variant_b_phase3(mentah)
    hk, ht = b["kriteria"], b["tetap"]
    print("  candidate peaks                :", b["puncak"].size)
    print("  two second init value          :", b["awal"][0])
    print("  beats with criteria            :", hk["n_qrs"])
    print("  beats without halving          :", ht["n_qrs"])
    print("  RR windows tested              :", hk["n_jendela"])
    print("  irregular RR windows           :", hk["n_jendela_tidak_teratur"])
    print("  search back activations        :", hk["n_searchback"])
    print("  halving activations            :", hk["n_potong"])

    # Isolate the effect of the initialization on the phase 5 peak series, using the phase 3
    # function that owns the initialization, so the difference is measured and not guessed.
    pv = a["jendela"][a["puncak"]].astype(np.int64)
    n_awal_puncak = int(np.count_nonzero(a["puncak"] < 500))
    df_max = A.jalankan_ambang(pv, n_awal=n_awal_puncak, cara_init="maksimum dua detik")
    df_nol = A.jalankan_ambang(pv, n_awal=n_awal_puncak, cara_init="nol")
    lolos_max = int(np.count_nonzero(pv > df_max["THRESHOLD_I1"].to_numpy()))
    lolos_nol = int(np.count_nonzero(pv > df_nol["THRESHOLD_I1"].to_numpy()))
    print("  phase 5 peak series, init max of the first %d peaks: %d peaks above threshold"
          % (n_awal_puncak, lolos_max))
    print("  phase 5 peak series, init zero                    : %d peaks above threshold" % lolos_nol)

    out = ["# Comparison variant, threshold started from the maximum of the first 500 samples",
           "# following the phase 3 notebook. This variant is NOT the frozen fixture.",
           "# Report produced by model/rantai-afib-lite/s0_bekukan_acuan.py",
           "",
           "## Why the variant is a different pipeline, not only a different initialization",
           "",
           "The phase 5 notebook function jalankan() builds SPKI, NPKI, SPKF and NPKF inside its",
           "own body and starts them from zero. It has no argument that accepts an initial value,",
           "so a two second initialization cannot be injected into it without editing its",
           "arithmetic, which is forbidden. The variant therefore runs the phase 3 notebook",
           "pipeline as that notebook runs it, and it differs from pipeline A in three ways at",
           "once. The measured differences below are the difference of the whole phase 3 pipeline,",
           "not of the initialization alone. The initialization alone is measured separately at",
           "the end of this file, on the phase 5 peak series, through the phase 3 function",
           "jalankan_ambang() that owns that initialization.",
           "",
           "| aspect | pipeline A (frozen fixture) | variant B (phase 3 pipeline) |",
           "|---|---|---|",
           "| filter chain | rantai_tapis() phase 5, recursive low-pass equation (3) | "
           "rantai_tapis__fase3() phase 3, closed form FIR moving average |",
           "| envelope window | selubung_bergantian(), alternating 37 and 38 samples | "
           "jendela_jumlah(sq, 38), fixed 38 samples |",
           "| peak picker | puncak_radius(sel, 27) | deteksi_puncak(), scipy find_peaks, "
           "distance 50 samples |",
           "| threshold start | zero, warms up | maximum of the first 500 samples of the envelope |",
           "| halving | mode_half default \"tidak\" | mode_potong \"kriteria\" through BATAS_RR_TIDAK_TERATUR |",
           "| T wave rule | on, ATURAN_T_BAWAAN True | absent, the phase 3 notebook has no T wave rule |",
           "",
           "## Measured on AFDB 04015, first 450000 frames",
           "",
           "| quantity | pipeline A | variant B |",
           "|---|---|---|",
           "| candidate peaks | %d | %d |" % (a["puncak"].size, b["puncak"].size),
           "| beats with the T wave rule on | %d | %d (no T wave rule in phase 3) |" % (len(h["qrs"]), hk["n_qrs"]),
           "| beats with the T wave rule off | %d | %d (no halving, mode_potong tetap) |" % (len(off["qrs"]), ht["n_qrs"]),
           "| RR intervals | %d | %d |" % (a["rr"].size, hk["n_jendela"]),
           "| decision windows (32 beats, step 4) | %d | not measurable, see note |" % kelas.size,
           "| window features | %d rows x 4 columns | not measurable, see note |" % fitur.shape[0],
           "| derived ratio threshold | %.3f | not measurable, see note |" % ambang["t1"],
           "| derived entropy threshold | %.2f | not measurable, see note |" % ambang["t2"],
           "| accuracy at derived thresholds | %.4f | not measurable, see note |" % ambang["akurasi"],
           "",
           "Note on the missing variant B window metrics: the phase 3 function tata_cara_ambang()",
           "returns counters only, n_qrs, n_jendela, n_searchback, and the threshold traces, but it",
           "does not return the beat positions. The 32 beat decision windows are built from beat",
           "positions, so they cannot be produced from the phase 3 pipeline without rewriting the",
           "loop, which is out of scope here. They are reported as not measurable rather than",
           "guessed.",
           "",
           "The RR window count of variant B, %d, is the count of RR intervals that the phase 3" % hk["n_jendela"],
           "function evaluated with the P3-3 irregular rhythm criterion, and it is a different",
           "quantity from the 32 beat decision window count of pipeline A, %d." % kelas.size,
           "",
           "## Initialization alone, measured on the phase 5 peak series",
           "",
           "The phase 3 function jalankan_ambang() is run on the phase 5 peak values",
           "(the envelope sampled at the %d peaks of pipeline A), twice: once with" % a["puncak"].size,
           "cara_init \"maksimum dua detik\" over the first %d peaks, the number of phase 5 peaks" % n_awal_puncak,
           "inside the first 500 samples, and once with cara_init \"nol\".",
           "",
           "| initialization | peaks above the first threshold | of | first threshold value |",
           "|---|---|---|---|",
           "| maximum of the first %d peaks | %d | %d | %.1f |" % (n_awal_puncak, lolos_max,
                                                                    pv.size, df_max["THRESHOLD_I1"].iloc[0]),
           "| zero | %d | %d | %.1f |" % (lolos_nol, pv.size, df_nol["THRESHOLD_I1"].iloc[0]),
           "",
           "Difference: %d peaks, that is %+d." % (lolos_max - lolos_nol, lolos_max - lolos_nol),
           "",
           "## Phase 3 pipeline counters, from the notebook itself for comparison",
           "",
           "The phase 3 notebook reports on the same recording: 4805 candidate peaks, 2618 RR",
           "windows tested, 2620 beats with the criterion, 2599 beats without halving, 1801",
           "halving activations, and search back activations 1 with the criterion.",
           ""]
    COMPARE.write_text("\n".join(out), encoding="utf-8")
    print("comparison file                   :", COMPARE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
