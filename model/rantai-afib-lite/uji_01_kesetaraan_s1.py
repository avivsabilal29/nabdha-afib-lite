#!/usr/bin/env python3
"""AFIB-LITE phase 6 step S1 gate: the streaming chain against the frozen fixture.

Loads model/rantai-afib-lite/fixture/04015_30m.npz, runs the streaming chain of
rantai.py over the 450000 samples of the fixture recording, and compares every frozen
array with the array the chain produced, one array per line. The gate passes only when
every line reads IDENTIK.

Arrays that are not produced by the chain itself:
  puncak_acuan_neurokit   an input. It is taken from the fixture and fed to the window
                          decision layer, exactly as s0_bekukan_acuan.py fed the NeuroKit
                          peak series it obtained from that library.
  jendela_*_acuan         produced by the chain window layer over that peak series.

Options used per array:
  aturan_t=True   masukan16, lp, hp, turunan, kuadrat, jendela, puncak, qrs, rr,
                  rr_average1, rr_average2, rr_antre_panjang, penanda, rr_disemai,
                  rr_riwayat_panjang, rr_menyala_akhir, ambang_kemiringan_puncak,
                  ambang_puncak_terfilter, ambang_state, rasio_pita, rasio_qrs,
                  jendela_fitur, jendela_kelas_benar, jendela_ambang
  aturan_t=False  jendela_aturan_t_mati, jendela_fitur_aturan_t_mati,
                  jendela_kelas_aturan_t_mati, rasio_pita_aturan_t_mati,
                  rasio_qrs_aturan_t_mati
  peak series of the fixture  jendela_fitur_acuan, jendela_kelas_acuan, jendela_ambang_ref

Run it with the project interpreter:

    cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/uji_01_kesetaraan_s1.py
"""

import pathlib
import sys
import time

import numpy as np
import wfdb

import rantai as R

HERE = pathlib.Path(__file__).resolve().parent
NPZ = HERE / "fixture" / "04015_30m.npz"
REC = pathlib.Path("/home/avivsabilalm/.hermes/cache/scratch/afib/afdb_local/04015")
FRAMES = 450_000


def jalan(nilai, aturan_t):
    """Drive one full run and return its arrays plus the wall clock."""
    t0 = time.time()
    r = R.Rantai(semai_aktif=True, aturan_t=aturan_t, besaran="turunan")
    langkah = r.langkah
    for v in nilai:
        langkah(v)
    out = r.hasil()
    out["_rentang"] = r.rentang_terukur()
    out["_lebar"] = r.lebar()
    out["_lebar_tanpa_tanda"] = r.lebar_tanpa_tanda()
    out["_detik"] = time.time() - t0
    return out


def baris(nama, dapat, acuan, sumber):
    """One report line per array: name, shape, and IDENTIK or BEDA with the difference."""
    a = np.asarray(dapat)
    b = np.asarray(acuan)
    bentuk = str(tuple(b.shape))
    if a.shape != b.shape:
        return "%-28s %-12s BEDA bentuk, chain %s lawan fixture %s [%s]" % (
            nama, bentuk, tuple(a.shape), tuple(b.shape), sumber)
    if b.dtype.kind == "U":
        bad = np.flatnonzero(a != b)
        if bad.size == 0:
            return "%-28s %-12s IDENTIK %s [%s]" % (nama, bentuk, b.dtype, sumber)
        return "%-28s %-12s BEDA %d dari %d beda, pertama di indeks %d [%s]" % (
            nama, bentuk, bad.size, b.size, int(bad[0]), sumber)
    if a.size == 0:
        return "%-28s %-12s IDENTIK %s [%s]" % (nama, bentuk, b.dtype, sumber)
    if np.array_equal(a, b):
        return "%-28s %-12s IDENTIK %s [%s]" % (nama, bentuk, b.dtype, sumber)
    d = np.abs(a.astype(np.float64) - b.astype(np.float64))
    bad = np.flatnonzero(a != b)
    return "%-28s %-12s BEDA selisih mutlak terbesar %.6g di indeks %d, %d dari %d beda [%s]" % (
        nama, bentuk, float(d.max()), int(bad[0]), bad.size, b.size, sumber)


def main():
    print("S1 equivalence gate, streaming chain against the frozen fixture")
    print("fixture                          :", NPZ, NPZ.stat().st_size, "bytes")
    print("interpreter                      :", sys.executable)
    d = np.load(NPZ)

    rec = wfdb.rdrecord(str(REC), sampto=FRAMES)
    mentah = rec.p_signal[:, 0].astype(float)
    print("recording                        :", REC, "|", rec.record_name, rec.fs, "Hz")
    print("samples fed to the chain         :", mentah.size)
    print()

    on = jalan(mentah, True)
    print("run aturan_t=True                : %.1f s" % on["_detik"])
    off = jalan(mentah, False)
    print("run aturan_t=False               : %.1f s" % off["_detik"])
    print()

    anotasi = wfdb.rdann(str(REC), "atr")
    lab = R.label_irama(anotasi.sample, anotasi.aux_note, FRAMES)
    k1, k2 = R.kisi_ambang()

    fitur, kelas = R.kumpulkan_jendela(on["qrs"], lab, sumber=R.SUMBER_MENTAH)
    fitur_off, kelas_off = R.kumpulkan_jendela(off["qrs"], lab, sumber=R.SUMBER_MENTAH)
    puncak_acuan = np.asarray(d["puncak_acuan_neurokit"], dtype=np.int64)
    fitur_ref, kelas_ref = R.kumpulkan_jendela(puncak_acuan, lab, sumber=R.SUMBER_MENTAH)
    fitur_aktif, kelas_aktif = R.kumpulkan_jendela(on["qrs"], lab)
    fitur_aktif_off, kelas_aktif_off = R.kumpulkan_jendela(off["qrs"], lab)
    fitur_aktif_ref, kelas_aktif_ref = R.kumpulkan_jendela(puncak_acuan, lab)
    ambang = R.turunkan_ambang(fitur, kelas, k1, k2)
    ambang_ref = R.turunkan_ambang(fitur_ref, kelas_ref, k1, k2)
    ambang_aktif = R.turunkan_ambang(fitur_aktif, kelas_aktif, k1, k2)

    print("chain beats, rule on             :", on["qrs"].size)
    print("chain beats, rule off            :", off["qrs"].size)
    print("chain RR intervals, rule on      :", on["rr"].size)
    print("windows, rule on                 :", kelas.size,
          "(AFIB %d, N %d)" % (int((kelas == "AFIB").sum()), int((kelas == "N").sum())))
    print("windows, rule off                :", kelas_off.size,
          "(AFIB %d, N %d)" % (int((kelas_off == "AFIB").sum()), int((kelas_off == "N").sum())))
    print("windows, NeuroKit peak series    :", kelas_ref.size,
          "(AFIB %d, N %d)" % (int((kelas_ref == "AFIB").sum()), int((kelas_ref == "N").sum())))
    print("derived thresholds, rule on      : ratio %.3f, entropy %.2f, accuracy %.4f, "
          "Se %.4f, Sp %.4f"
          % (ambang["t1"], ambang["t2"], ambang["akurasi"], ambang["kepekaan"],
             ambang["spesifisitas"]))
    print("derived thresholds, reference    : ratio %.3f, entropy %.2f, accuracy %.4f, "
          "Se %.4f, Sp %.4f"
          % (ambang_ref["t1"], ambang_ref["t2"], ambang_ref["akurasi"],
             ambang_ref["kepekaan"], ambang_ref["spesifisitas"]))
    print("chain ambang_state               : %s" % (on["ambang_state"].tolist(),))
    print("order                            : calon_kedua, cari_mundur, diperiksa, ditolak, "
          "diterima_pita, berisiko, semai, penanda, langkah")

    periksa = [
        ("masukan16", "masukan16", "aturan_t=True"),
        ("lp", "lp", "aturan_t=True"),
        ("hp", "hp", "aturan_t=True"),
        ("turunan", "turunan", "aturan_t=True"),
        ("kuadrat", "kuadrat", "aturan_t=True"),
        ("jendela", "jendela", "aturan_t=True"),
        ("puncak", "puncak", "aturan_t=True"),
        ("qrs", "qrs", "aturan_t=True"),
        ("rr", "rr", "aturan_t=True"),
        ("rr_average1", "rr_average1", "aturan_t=True"),
        ("rr_average2", "rr_average2", "aturan_t=True"),
        ("rr_antre_panjang", "rr_antre_panjang", "aturan_t=True"),
        ("penanda", "penanda", "aturan_t=True"),
        ("rr_disemai", "rr_disemai", "aturan_t=True"),
        ("rr_riwayat_panjang", "rr_riwayat_panjang", "aturan_t=True"),
        ("rr_menyala_akhir", "rr_menyala_akhir", "aturan_t=True"),
        ("ambang_kemiringan_puncak", "ambang_kemiringan_puncak", "aturan_t=True"),
        ("ambang_puncak_terfilter", "ambang_puncak_terfilter", "aturan_t=True"),
        ("ambang_state", "ambang_state", "aturan_t=True"),
        ("rasio_pita", "rasio_pita", "aturan_t=True"),
        ("rasio_qrs", "rasio_qrs", "aturan_t=True"),
        ("jendela_fitur", "jendela_fitur", "aturan_t=True"),
        ("jendela_kelas_benar", "jendela_kelas_benar", "aturan_t=True"),
        ("jendela_ambang", "jendela_ambang", "aturan_t=True"),
        ("jendela_aturan_t_mati", "jendela_aturan_t_mati", "aturan_t=False"),
        ("jendela_fitur_aturan_t_mati", "jendela_fitur_aturan_t_mati", "aturan_t=False"),
        ("jendela_kelas_aturan_t_mati", "jendela_kelas_aturan_t_mati", "aturan_t=False"),
        ("rasio_pita_aturan_t_mati", "rasio_pita_aturan_t_mati", "aturan_t=False"),
        ("rasio_qrs_aturan_t_mati", "rasio_qrs_aturan_t_mati", "aturan_t=False"),
        ("jendela_fitur_acuan", "jendela_fitur_acuan", "peak series of the fixture"),
        ("jendela_kelas_acuan", "jendela_kelas_acuan", "peak series of the fixture"),
        ("jendela_ambang_ref", "jendela_ambang_ref", "peak series of the fixture"),
    ]
    dari_rantai = {
        "masukan16": on["masukan16"], "lp": on["lp"], "hp": on["hp"], "turunan": on["turunan"],
        "kuadrat": on["kuadrat"], "jendela": on["jendela"], "puncak": on["puncak"],
        "qrs": on["qrs"], "rr": on["rr"], "rr_average1": on["rr_average1"],
        "rr_average2": on["rr_average2"], "rr_antre_panjang": on["rr_antre_panjang"],
        "penanda": on["penanda"], "rr_disemai": on["rr_disemai"],
        "rr_riwayat_panjang": on["rr_riwayat_panjang"],
        "rr_menyala_akhir": on["rr_menyala_akhir"],
        "ambang_kemiringan_puncak": on["ambang_kemiringan_puncak"],
        "ambang_puncak_terfilter": on["ambang_puncak_terfilter"],
        "ambang_state": on["ambang_state"], "rasio_pita": on["rasio_pita"],
        "rasio_qrs": on["rasio_qrs"],
        "jendela_fitur": fitur, "jendela_kelas_benar": kelas,
        "jendela_ambang": np.array([float(ambang["t1"]), float(ambang["t2"])]),
        "jendela_aturan_t_mati": off["qrs"],
        "jendela_fitur_aturan_t_mati": fitur_off,
        "jendela_kelas_aturan_t_mati": kelas_off,
        "rasio_pita_aturan_t_mati": off["rasio_pita"],
        "rasio_qrs_aturan_t_mati": off["rasio_qrs"],
        "jendela_fitur_acuan": fitur_ref, "jendela_kelas_acuan": kelas_ref,
        "jendela_ambang_ref": np.array([float(ambang_ref["t1"]), float(ambang_ref["t2"])]),
    }

    print()
    print("per array result")
    print("-" * 132)
    gagal = 0
    for nama, kunci, sumber in periksa:
        line = baris(nama, dari_rantai[nama], d[kunci], sumber)
        print(line)
        if "IDENTIK" not in line:
            gagal += 1
    print("-" * 132)
    print("the active arm of this run, reported beside the fixture and not gated against it")
    print("  berpenanda windows, rule on       : %d (AFIB %d, N %d)"
          % (kelas_aktif.size, int((kelas_aktif == "AFIB").sum()),
             int((kelas_aktif == "N").sum())))
    print("  berpenanda windows, rule off      : %d (AFIB %d, N %d)"
          % (kelas_aktif_off.size, int((kelas_aktif_off == "AFIB").sum()),
             int((kelas_aktif_off == "N").sum())))
    print("  berpenanda windows, NeuroKit      : %d (AFIB %d, N %d)"
          % (kelas_aktif_ref.size, int((kelas_aktif_ref == "AFIB").sum()),
             int((kelas_aktif_ref == "N").sum())))
    print("  berpenanda derived thresholds     : ratio %.3f, entropy %.2f, accuracy %.4f, "
          "Se %.4f, Sp %.4f"
          % (ambang_aktif["t1"], ambang_aktif["t2"], ambang_aktif["akurasi"],
             ambang_aktif["kepekaan"], ambang_aktif["spesifisitas"]))
    print("  the mentah arms above are the frozen fixture arms, so every IDENTIK line reads "
          "against the oracle of that arm, while the active arm is the berpenanda series of "
          "rantai.kumpulkan_jendela")
    print("input of the fixture, not produced by the chain")
    print("puncak_acuan_neurokit          %-12s taken from the fixture, fed to the window layer"
          % (str(tuple(puncak_acuan.shape)),))
    try:
        import neurokit2 as nk
        bersih = nk.ecg_clean(mentah, sampling_rate=int(R.FS_HZ), method="pantompkins1985")
        ulang = nk.ecg_findpeaks(bersih, sampling_rate=int(R.FS_HZ),
                                 method="pantompkins1985")["ECG_R_Peaks"].astype(np.int64)
        print("neurokit2 rerun on this machine: %s, %s" % (ulang.size,
              "identical to the fixture series" if np.array_equal(ulang, puncak_acuan) else
              "differs from the fixture series, so the fixture series is the input used"))
    except Exception as exc:                                  # noqa: BLE001
        print("neurokit2 rerun                 : not available here (%s)" % (exc,))

    print()
    print("measured range and bit width per stage, rule on run")
    lebar_td = on["_lebar_tanpa_tanda"]
    for k, r in on["_rentang"].items():
        if r is None or r[0] is None:
            print("  %-14s range not measurable" % k)
            continue
        tanda = "signed %2d bits" % on["_lebar"][k]
        tanpa = "unsigned %2d bits" % lebar_td[k] if lebar_td[k] else "unsigned not applicable"
        print("  %-14s range %14d .. %14d | %s | %s" % (k, r[0], r[1], tanda, tanpa))
    print()
    print("a stage range that does not fit a signed 32 bit word is a hardware finding, not a"
          " chain error: the chain itself has arbitrary precision integers.")
    print()
    if gagal == 0:
        print("gate S1: PASS, every array identical")
        return 0
    print("gate S1: FAIL, %d of %d arrays differ" % (gagal, len(periksa)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
