#!/usr/bin/env python3
"""
analisis_rekaman.py - analisis rekaman AD8232 (keluaran ecg_ingest.py) terhadap rantai beku.

Langkah:
  1. .stim.hex identik dengan .npz (cacah 12 bit + penanda), statistik aliran dari manifest.
  2. Per detik: simpangan baku, kekuatan QRS pita 5-15 Hz, amplitudo 50 Hz, gap, datar, clamp.
  3. QRS dari rantai beku AFIB-LITE lewat model_core.jalankan_model (jalur yang sama dengan
     acuan_model.py / RTL), dicek silang dengan detektor energi pita 5-15 Hz.
  4. RR: median, BPM, RR janggal (di luar 0,7-1,3 x median, global dan median lokal 33 detak).
  5. Jendela 32 interval langkah 4, lengan berpenanda, fitur rantai.fitur_irama
     (RMSSD, RMSSD/rerata RR, pNN50 ambang 50 ms, entropi 16 bin buang 8+8 dibagi 4),
     kelas gerbang 0.165 / 0.63 (2 = review, 1 = normal, 0 = gagal gerbang 200-3000 ms).
  6. Detik bersih/buruk, segmen bersih terpanjang, grafik PNG, laporan JSON.

Contoh:
    python tools/analisis_rekaman.py --sesi raihan_duduk30m
    python tools/analisis_rekaman.py --sesi raihan_duduk30m --repo "D:/Data raihan/.../nabdha-afib-lite"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

FS = 250
REPO_BAWAAN = r"D:\Data raihan\Bismillah Hackathon\chiphack26\nabdha-afib-lite"
T1, T2 = 0.165, 0.63            # gerbang model (acuan_model.py, uji_10_berpenanda.py)
DATAR_STD = 12
TUNDA_RANTAI_MAKS = 60          # sampel; QRS rantai tertunda ~31 sampel dari puncak R

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cek_kualitas import bandpass_fft, deteksi_r  # noqa: E402


def muat_model(repo):
    sys.path.insert(0, os.path.join(repo, "tools"))
    import model_core as MC  # noqa: E402
    return MC


def runs(mask):
    """(mulai, akhir_eksklusif) untuk setiap deret True."""
    t = np.flatnonzero(np.diff(np.r_[0, mask.astype(int), 0]))
    return list(zip(t[::2].tolist(), t[1::2].tolist()))


def main():
    ap = argparse.ArgumentParser(description="Analisis rekaman AD8232 terhadap rantai beku")
    ap.add_argument("--sesi", required=True)
    ap.add_argument("--data", default="data")
    ap.add_argument("--repo", default=REPO_BAWAAN)
    a = ap.parse_args()

    stem = os.path.join(a.data, f"ad8232_{a.sesi}_250hz")
    d = np.load(stem + ".npz")
    cacah = d["cacah"].astype(np.int64)
    pen = d["penanda"].astype(np.int64)
    man = json.load(open(stem + ".manifest.json", encoding="utf-8"))
    n = cacah.size
    lap = {"sesi": a.sesi, "sampel": int(n), "durasi_s": round(n / FS, 2)}

    # 1. hex == npz ------------------------------------------------------------------------
    MC = muat_model(a.repo)
    kata = MC.baca_stimulus(stem + ".stim.hex")
    lap["hex_baris"] = int(kata.size)
    lap["hex_identik_npz"] = bool(
        kata.size == n
        and np.array_equal(MC.kata_ke_count(kata), cacah)
        and np.array_equal(MC.kata_ke_penanda(kata) & 0x7,
                           ((pen & 1) << 0) | (((pen >> 1) & 1) << 1) | (((pen >> 2) & 1) << 2)))
    st = man["statistik_aliran"]
    lap["sampel_hilang"] = st["lost_samples"]
    lap["putus_urutan"] = st["seq_breaks"]
    lap["checksum_error"] = st["checksum_errors"]
    lap["header_firmware"] = man["header_firmware"]
    gap = (pen & 2) > 0
    clamp = (pen & 1) > 0
    lap["persen_gap"] = round(100 * float(gap.mean()), 3)
    lap["persen_clamp"] = round(100 * float(clamp.mean()), 3)
    lap["cacah_min_maks"] = [int(cacah.min()), int(cacah.max())]

    # 3. rantai beku -------------------------------------------------------------------------
    t0 = time.time()
    out = MC.jalankan_model(kata)
    lap["waktu_rantai_s"] = round(time.time() - t0, 1)
    qrs = np.asarray(out["qrs"], np.int64)
    x = cacah.astype(float)
    r_det, _ = deteksi_r(x)
    lap["qrs_rantai"] = int(qrs.size)
    lap["r_detektor_skrip"] = int(r_det.size)
    # pasangkan: QRS rantai tertunda 0..TUNDA_RANTAI_MAKS sampel dari puncak R skrip
    if qrs.size and r_det.size:
        j = np.searchsorted(qrs, r_det)
        pas = np.zeros(r_det.size, bool)
        tunda = []
        for k, p in enumerate(r_det):
            if j[k] < qrs.size and 0 <= qrs[j[k]] - p <= TUNDA_RANTAI_MAKS:
                pas[k] = True
                tunda.append(int(qrs[j[k]] - p))
        lap["r_skrip_berpasangan_rantai"] = int(pas.sum())
        lap["tunda_rantai_median_sampel"] = float(np.median(tunda)) if tunda else None
        r_lepas = r_det[~pas]
    else:
        r_lepas = r_det

    # 4. RR ---------------------------------------------------------------------------------
    rr = np.diff(qrs).astype(float)              # sampel
    rr_ms = rr * 4.0
    med = float(np.median(rr_ms))
    lap["rr_median_ms"] = med
    lap["bpm_median"] = round(60000 / med, 1)
    lap["rr_min_maks_ms"] = [float(rr_ms.min()), float(rr_ms.max())]
    jg_global = (rr_ms < 0.7 * med) | (rr_ms > 1.3 * med)
    pad = 16
    rp = np.pad(rr_ms, pad, mode="edge")
    med_lok = np.array([np.median(rp[i:i + 2 * pad + 1]) for i in range(rr_ms.size)])
    jg_lokal = (rr_ms < 0.7 * med_lok) | (rr_ms > 1.3 * med_lok)
    lap["rr_janggal_global"] = int(jg_global.sum())
    lap["rr_janggal_lokal"] = int(jg_lokal.sum())
    tanda = np.asarray(out["rr_mark_raw"], np.int64)
    lap["penanda_rr_7b"] = {str(k): int((tanda == k).sum()) for k in np.unique(tanda)}

    # 5. jendela (lengan berpenanda, sama dengan acuan_model.py) ----------------------------
    R = MC.R
    rr_sel, src = R.seri_berpenanda(rr_ms, tanda)
    jendela = []
    for i in range(0, rr_sel.size - R.JENDELA_DENYUT, R.LANGKAH_DENYUT):
        seg = rr_sel[i:i + R.JENDELA_DENYUT]
        row = {"win_no": i // R.LANGKAH_DENYUT, "i_start": i,
               "qrs_end": int(qrs[src[i + R.JENDELA_DENYUT - 1] + 1])}
        if seg.min() < 200 or seg.max() > 3000:
            row["kelas_model"] = 0
        else:
            f = R.fitur_irama(seg)
            row.update({"rmssd": f[0], "ratio": f[1], "pnn50": f[2], "ent4": f[3],
                        "kelas_model": 2 if (f[1] > T1 and f[3] > T2) else 1})
        jendela.append(row)
    kel = np.array([w["kelas_model"] for w in jendela])
    lap["jendela"] = {"total": int(kel.size), "normal": int((kel == 1).sum()),
                      "review": int((kel == 2).sum()), "gagal_gerbang": int((kel == 0).sum())}
    fit = np.array([[w["ratio"], w["pnn50"], w["ent4"]] for w in jendela if w["kelas_model"]])
    if fit.size:
        lap["fitur_median"] = {"rmssd_per_rerata": round(float(np.median(fit[:, 0])), 4),
                               "pnn50": round(float(np.median(fit[:, 1])), 4),
                               "entropi_per_4": round(float(np.median(fit[:, 2])), 4)}

    # 2 + 6. per detik --------------------------------------------------------------------
    det = n // FS
    blk = x[:det * FS].reshape(det, FS)
    std_s = blk.std(axis=1)
    bp = bandpass_fft(x, 5, 15)
    pq = (bp[:det * FS].reshape(det, FS) ** 2).mean(axis=1)
    pq_med = float(np.median(pq))
    b50 = bandpass_fft(x, 49, 51)
    a50 = np.sqrt(2 * (b50[:det * FS].reshape(det, FS) ** 2).mean(axis=1))
    gap_s = gap[:det * FS].reshape(det, FS).any(axis=1)
    datar_s = std_s < DATAR_STD
    # clamp yang tidak berada dalam 48 ms dari puncak R
    ic = np.flatnonzero(clamp)
    if ic.size and r_det.size:
        j = np.clip(np.searchsorted(r_det, ic), 1, r_det.size - 1)
        jarak = np.minimum(np.abs(ic - r_det[j - 1]), np.abs(ic - r_det[j]))
        cl_jauh = ic[jarak > 12]
    else:
        cl_jauh = ic
    cl_s = np.zeros(det, bool)
    cl_s[np.unique(cl_jauh // FS)[np.unique(cl_jauh // FS) < det]] = True
    qrs_lemah = pq < 0.25 * pq_med
    qrs_kuat = pq > 4.0 * pq_med
    jg_s = np.zeros(det, bool)
    for k in np.flatnonzero(jg_lokal):
        lo, hi = int(qrs[k] // FS), int(qrs[k + 1] // FS)
        jg_s[lo:min(det, hi + 1)] = True
    lepas_s = np.zeros(det, bool)
    lepas_s[np.unique(r_lepas // FS)[np.unique(r_lepas // FS) < det]] = True
    buruk = gap_s | datar_s | cl_s | qrs_lemah | qrs_kuat | jg_s
    lap["detik"] = {"total": int(det), "gap": int(gap_s.sum()), "datar": int(datar_s.sum()),
                    "datar_tanpa_gap": int((datar_s & ~gap_s).sum()),
                    "clamp_di_luar_R": int(cl_s.sum()), "qrs_lemah": int(qrs_lemah.sum()),
                    "qrs_berlebih": int(qrs_kuat.sum()), "rr_janggal": int(jg_s.sum()),
                    "r_skrip_tanpa_qrs_rantai": int(lepas_s.sum()), "buruk": int(buruk.sum())}
    lap["amplitudo_50hz_cacah"] = {"median": round(float(np.median(a50)), 1),
                                   "p95": round(float(np.percentile(a50, 95)), 1)}
    seg_b = [(s, e) for s, e in runs(~buruk)]
    seg_b.sort(key=lambda t: t[1] - t[0], reverse=True)
    lap["segmen_bersih_terpanjang_s"] = [[s, e] for s, e in seg_b[:5]]
    lap["segmen_buruk_s"] = [[s, e] for s, e in runs(buruk)]
    lap["sebab_buruk_per_detik"] = {
        int(i): [nm for nm, m in (("gap", gap_s), ("datar", datar_s), ("clamp", cl_s),
                                  ("qrs_lemah", qrs_lemah), ("qrs_berlebih", qrs_kuat),
                                  ("rr_janggal", jg_s)) if m[i]]
        for i in np.flatnonzero(buruk)}

    # simpan --------------------------------------------------------------------------------
    js = os.path.join(a.data, f"analisis_{a.sesi}.json")
    with open(js, "w", encoding="utf-8") as fh:
        json.dump({"ringkas": lap, "jendela": jendela,
                   "qrs_rantai": qrs.tolist(), "rr_tanda_7b": tanda.tolist()},
                  fh, indent=1, ensure_ascii=False)

    # grafik ------------------------------------------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    BIRU, MERAH, KUNING, ABU, TINTA = "#2a78d6", "#d03b3b", "#fab219", "#52514e", "#0b0b0b"
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": ABU, "axes.labelcolor": TINTA,
                         "xtick.color": ABU, "ytick.color": ABU, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.facecolor": "#fcfcfb",
                         "axes.facecolor": "#fcfcfb"})
    fig, ax = plt.subplots(5, 1, figsize=(12, 13), constrained_layout=True)
    tm = np.arange(det) / 60.0

    ax[0].plot(tm, pq, color=BIRU, lw=1)
    ax[0].set_yscale("log")
    ax[0].axhline(0.25 * pq_med, color=ABU, ls="--", lw=1)
    ax[0].axhline(4 * pq_med, color=ABU, ls="--", lw=1)
    for s, e in runs(buruk):
        ax[0].axvspan(s / 60, e / 60, color=MERAH, alpha=0.18, lw=0)
    ax[0].set_title("Kekuatan QRS per detik (pita 5-15 Hz, cacah²); merah = detik buruk", loc="left")
    ax[0].set_xlabel("menit")

    ax[1].plot(tm, a50, color=BIRU, lw=1)
    ax[1].set_title("Amplitudo dengung 50 Hz per detik (cacah; 200 cacah = 1 mV)", loc="left")
    ax[1].set_xlabel("menit")

    tq = qrs[1:] / FS / 60
    ax[2].plot(tq, rr_ms, color=BIRU, lw=1)
    if jg_lokal.any():
        ax[2].plot(tq[jg_lokal], rr_ms[jg_lokal], "o", ms=5, color=MERAH, mec="#fcfcfb",
                   mew=1.5, label=f"RR janggal ({int(jg_lokal.sum())})")
        ax[2].legend(frameon=False, loc="upper right")
    ax[2].set_title(f"RR dari QRS rantai beku (ms); median {med:.0f} ms = {60000 / med:.1f} BPM",
                    loc="left")
    ax[2].set_xlabel("menit")

    tw = np.array([w["qrs_end"] for w in jendela]) / FS / 60
    rat = np.array([w.get("ratio", np.nan) for w in jendela])
    ax[3].plot(tw, rat, color=BIRU, lw=1)
    ax[3].axhline(T1, color=ABU, ls="--", lw=1)
    ax[3].text(tw[0] if tw.size else 0, T1, f"  ambang {T1}", va="bottom", color=ABU)
    ax[3].set_title(f"RMSSD / rerata RR per jendela 32 detak "
                    f"(normal {lap['jendela']['normal']}, review {lap['jendela']['review']}, "
                    f"gagal gerbang {lap['jendela']['gagal_gerbang']})", loc="left")
    ax[3].set_xlabel("menit")

    i0 = int(seg_b[0][0] * FS) if seg_b else 0
    sl = slice(i0, min(n, i0 + 10 * FS))
    ts = np.arange(sl.start, sl.stop) / FS
    ax[4].plot(ts, cacah[sl], color=BIRU, lw=1)
    rr_in = r_det[(r_det >= sl.start) & (r_det < sl.stop)]
    ax[4].plot(rr_in / FS, cacah[rr_in], "o", ms=5, color=TINTA, mec="#fcfcfb", mew=1.5)
    ax[4].set_title("Contoh 10 s dari segmen bersih terpanjang (cacah); titik = puncak R", loc="left")
    ax[4].set_xlabel("detik")
    png = os.path.join(a.data, f"analisis_{a.sesi}.png")
    fig.savefig(png, dpi=110)

    print(json.dumps({k: v for k, v in lap.items() if k not in ("sebab_buruk_per_detik",)},
                     indent=1, ensure_ascii=False))
    print("berkas:", js, png)


if __name__ == "__main__":
    main()
