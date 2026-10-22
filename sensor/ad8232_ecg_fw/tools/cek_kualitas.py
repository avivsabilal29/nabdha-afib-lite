#!/usr/bin/env python3
"""
cek_kualitas.py - cek kualitas sinyal AD8232 dari firmware mode teks (env esp32dev_text).

Membaca baris Teleplot ">ecg:N", ">gap:N", ">clamp:N" dan "dasar=..mV telat=.. buang=.."
selama 60 s: 30 s pertama DIAM, 30 s terakhir uji GOYANG (kabel digoyang pelan).
Hanya butuh pyserial + numpy.

Contoh:
    python tools/cek_kualitas.py --port COM14
    python tools/cek_kualitas.py --port COM14 --tanpa-reset     # tidak menunggu EN/RST

Keluaran: data/cek_kualitas/cek_<waktu>.csv (sampel) dan .json (laporan).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import time

import numpy as np

FS = 250
RE_DASAR = re.compile(r"dasar=(-?\d+)mV telat=(\d+) buang=(\d+)")
RE_BOOT = re.compile(r"(dasar terukur (\d+) mV|elektroda belum terpasang)")

# Kriteria lulus (cacah: 200 cacah = 1 mV acuan input)
DASAR_MV = (1580, 1750)   # disetujui Raihan 22 Okt: board 1 = 1593 mV, board 2 = 1723 mV
RIAK_MAKS = 50          # setengah rentang p2,5..p97,5 di luar QRS, segmen diam
DATAR_STD = 12          # simpangan baku per detik di bawah ini = detik datar
RASIO_50HZ_MAKS = 0.5   # daya 49-51 Hz dibagi daya 5-15 Hz
BPM = (50, 110)


def beep(f=1000, ms=300):
    try:
        import winsound
        winsound.Beep(f, ms)
    except Exception:
        print("\a", end="", flush=True)


# ---------------------------------------------------------------------------
# Pengolahan sinyal (numpy saja)
# ---------------------------------------------------------------------------
def bandpass_fft(x, lo, hi, fs=FS):
    x = np.asarray(x, float)
    X = np.fft.rfft(x - x.mean())
    f = np.fft.rfftfreq(x.size, 1.0 / fs)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, n=x.size)


def moving_mean(x, n):
    k = np.ones(n) / n
    return np.convolve(np.pad(x, (n // 2, n - 1 - n // 2), mode="edge"), k, mode="valid")


def deteksi_r(x, thr_dari=None, fs=FS):
    """Puncak R: energi pita 5-15 Hz, ambang 0,3 x median maksimum per detik, refrakter 250 ms."""
    bp = bandpass_fft(x, 5, 15, fs)
    e = moving_mean(bp ** 2, 8)
    ref = e if thr_dari is None else e[thr_dari]
    n_det = ref.size // fs
    if n_det == 0:
        return np.array([], int), bp
    maks = ref[: n_det * fs].reshape(n_det, fs).max(axis=1)
    thr = 0.3 * float(np.median(maks))
    ref_n = int(0.25 * fs)
    puncak = []
    i = 1
    while i < e.size - 1:
        if e[i] > thr and e[i] >= e[i - 1] and e[i] >= e[i + 1]:
            j1, j2 = i, min(e.size, i + ref_n)
            j = j1 + int(np.argmax(e[j1:j2]))          # maksimum dalam jendela refrakter
            a, b = max(0, j - 10), min(x.size, j + 10)  # +-40 ms: titik |bp| terbesar
            puncak.append(a + int(np.argmax(np.abs(bp[a:b]))))
            i = j + ref_n
        else:
            i += 1
    return np.unique(np.asarray(puncak, int)), bp


def analisis(c, g, k, t_goyang):
    n = c.size
    x = c.astype(float)
    det = n // FS
    hasil = {"sampel": int(n), "durasi_s": round(n / FS, 2)}

    hasil["persen_gap"] = round(100 * float(g.mean()), 3)
    hasil["persen_clamp"] = round(100 * float(k.mean()), 3)

    i_g = int(t_goyang * FS)
    diam = slice(0, min(i_g, n))
    r_all, _ = deteksi_r(x, thr_dari=diam)
    hasil["jumlah_r"] = int(r_all.size)

    # per detik
    blk = x[: det * FS].reshape(det, FS)
    std_s = blk.std(axis=1)
    gap_s = g[: det * FS].reshape(det, FS).any(axis=1)
    datar = [int(i) for i in np.flatnonzero(std_s < DATAR_STD)]
    hasil["std_per_detik"] = [round(float(s), 1) for s in std_s]
    hasil["detik_datar"] = datar
    hasil["detik_datar_tanpa_gap"] = [i for i in datar if not gap_s[i]]
    hasil["detik_ada_gap"] = [int(i) for i in np.flatnonzero(gap_s)]
    tepi = np.flatnonzero(np.diff(np.r_[0, g.astype(int), 0]))
    hasil["gap_mulai_s_panjang"] = [(round(a / FS, 2), int(b - a)) for a, b in zip(tepi[::2], tepi[1::2])]

    # clamp hanya di pucuk R?
    ic = np.flatnonzero(k)
    if ic.size and r_all.size:
        jarak = np.min(np.abs(ic[:, None] - r_all[None, :]), axis=1)
        hasil["clamp_dekat_r_persen"] = round(100 * float(np.mean(jarak <= 12)), 1)  # <=48 ms
    else:
        hasil["clamp_dekat_r_persen"] = None if ic.size else 100.0

    def segmen(lo, hi, nama):
        s = {}
        xs = x[lo:hi]
        r = r_all[(r_all >= lo) & (r_all < hi)] - lo
        s["detik"] = [round(lo / FS, 1), round(hi / FS, 1)]
        s["jumlah_r"] = int(r.size)
        rr = np.diff(r)
        if rr.size >= 2:
            med = float(np.median(rr))
            s["rr_median_sampel"] = med
            s["rr_median_ms"] = med * 4
            s["bpm"] = round(60 * FS / med, 1)
            janggal = (rr < 0.7 * med) | (rr > 1.3 * med)
            s["rr_janggal"] = int(janggal.sum())
            s["rr_sampel"] = rr.tolist()
        else:
            s["bpm"] = None
            s["rr_janggal"] = None
        # riak di luar QRS (+-80 ms), setelah membuang garis dasar lambat (rata-rata 1 s)
        hp = xs - moving_mean(xs, FS)
        m = np.ones(xs.size, bool)
        for p in r:
            m[max(0, p - 20): p + 20] = False
        if m.sum() > FS:
            # riak_setengah_rentang ikut memuat gelombang T (0,2-0,3 mV), jadi hanya info;
            # kriteria lulus memakai riak_hf: komponen > 20 Hz (derau listrik/otot) di luar QRS
            q = np.percentile(hp[m], [2.5, 97.5])
            s["riak_std"] = round(float(hp[m].std()), 1)
            s["riak_setengah_rentang"] = round(float((q[1] - q[0]) / 2), 1)
            hf = bandpass_fft(xs, 20, FS / 2)[m]
            q = np.percentile(hf, [2.5, 97.5])
            s["riak_hf_std"] = round(float(hf.std()), 1)
            s["riak_hf"] = round(float((q[1] - q[0]) / 2), 1)
        # 50 Hz
        X = np.abs(np.fft.rfft(xs - xs.mean())) ** 2
        f = np.fft.rfftfreq(xs.size, 1.0 / FS)
        p50 = float(X[(f >= 49) & (f <= 51)].sum())
        pq = float(X[(f >= 5) & (f <= 15)].sum())
        s["rasio_50hz"] = round(p50 / pq, 3) if pq > 0 else None
        amp = 2 * np.sqrt(p50) / xs.size
        s["amplitudo_50hz_cacah"] = round(float(amp), 1)
        # pola periode 5 sampel: autokorelasi lag 5 dari sisa (x - rata-rata 5 sampel)
        res = xs - moving_mean(xs, 5)
        if res.std() > 0:
            s["autokorelasi_lag5"] = round(float(np.corrcoef(res[:-5], res[5:])[0, 1]), 3)
        s["simpangan_baku"] = round(float(xs.std()), 1)
        return s

    hasil["diam"] = segmen(0, min(i_g, n), "diam")
    if n > i_g + FS:
        hasil["goyang"] = segmen(i_g, n, "goyang")
    return hasil


# ---------------------------------------------------------------------------
# Rekam dari serial
# ---------------------------------------------------------------------------
def rekam(port, baud, detik, t_goyang, tanpa_reset):
    import serial

    ser = serial.Serial()
    ser.port, ser.baudrate, ser.timeout = port, baud, 0.1
    ser.dtr = False   # jangan memicu reset otomatis saat port dibuka
    ser.rts = False
    ser.open()
    ser.reset_input_buffer()

    buf = b""
    dasar = []          # (t, dasar_mv, telat, buang)
    boot = None

    def baca_baris():
        nonlocal buf
        data = ser.read(4096)
        if data:
            buf += data
        *lines, buf = buf.split(b"\n")
        return [ln.decode("ascii", "replace").strip() for ln in lines]

    if not tanpa_reset:
        print("\n>>> Tekan tombol EN/RST di ESP32 sekarang, lalu DIAM (jangan bergerak/bicara).")
        beep(800, 200)
        t0 = time.time()
        while time.time() - t0 < 30 and boot is None:
            for ln in baca_baris():
                mm = RE_BOOT.search(ln)
                if mm:
                    boot = ln
                    print("    boot:", ln)
        if boot is None:
            print("    (tidak terlihat baris boot dalam 30 s; lanjut memakai baris 'dasar=')")
        print("    menunggu 3 s agar sinyal tenang ...")
        t0 = time.time()
        while time.time() - t0 < 3:
            baca_baris()

    c, g, k = [], [], []
    print(f"\n>>> Merekam {detik:.0f} s. 0-{t_goyang:.0f} s: DIAM.")
    beep(1000, 300)
    t0 = time.time()
    goyang_diumumkan = False
    lapor = t0
    while time.time() - t0 < detik:
        for ln in baca_baris():
            if ln.startswith(">ecg:"):
                try:
                    c.append(int(ln[5:])); g.append(0); k.append(0)
                except ValueError:
                    pass
            elif ln.startswith(">gap:") and c:
                g[-1] = 1 if ln[5:] == "1" else 0
            elif ln.startswith(">clamp:") and c:
                k[-1] = 1 if ln[7:] == "1" else 0
            else:
                mm = RE_DASAR.search(ln)
                if mm:
                    dasar.append((round(time.time() - t0, 1), int(mm[1]), int(mm[2]), int(mm[3])))
        now = time.time()
        if not goyang_diumumkan and now - t0 >= t_goyang:
            goyang_diumumkan = True
            beep(1500, 500)
            print(f"\n>>> t={t_goyang:.0f} s: GOYANGKAN KABEL ELEKTRODA PELAN-PELAN sampai selesai.\n")
        if now - lapor >= 5:
            lapor = now
            last = np.array(c[-FS:], float) if len(c) >= FS else np.array([0.0])
            print(f"  t={now - t0:5.1f}s sampel={len(c):6d} std_1s={last.std():6.1f} "
                  f"gap_1s={sum(g[-FS:]):3d} clamp_1s={sum(k[-FS:]):3d}")
    ser.close()
    beep(1000, 200); beep(1000, 200)
    print(">>> Selesai merekam.")
    return (np.array(c, np.int32), np.array(g, np.uint8), np.array(k, np.uint8),
            dasar, boot, time.time() - t0)


def nilai(h, dasar):
    """Bandingkan dengan kriteria lulus."""
    d = h["diam"]
    cek = {}
    dm = [x[1] for x in dasar]
    cek["dasar_mV"] = (dm[-1] if dm else None,
                       bool(dm) and DASAR_MV[0] <= dm[-1] <= DASAR_MV[1])
    cek["gap_persen"] = (h["persen_gap"], h["persen_gap"] == 0)
    cdr = h["clamp_dekat_r_persen"]
    cek["clamp_dekat_R_persen"] = (cdr, cdr is None or cdr >= 95)
    cek["riak_hf_diam"] = (d.get("riak_hf"),
                           d.get("riak_hf") is not None and d["riak_hf"] <= RIAK_MAKS)
    cek["rasio_50hz_diam"] = (d.get("rasio_50hz"),
                              d.get("rasio_50hz") is not None and d["rasio_50hz"] <= RASIO_50HZ_MAKS)
    cek["detik_datar"] = (h["detik_datar"], len(h["detik_datar"]) == 0)
    cek["bpm_diam"] = (d.get("bpm"), d.get("bpm") is not None and BPM[0] <= d["bpm"] <= BPM[1])
    if len(dasar) >= 2:
        dt = dasar[-1][2] - dasar[0][2]
        db = dasar[-1][3] - dasar[0][3]
        cek["telat_buang_naik"] = ((dt, db), dt == 0 and db == 0)
    return cek


def main():
    ap = argparse.ArgumentParser(description="Cek kualitas sinyal AD8232 (mode teks)")
    ap.add_argument("--port", default="COM14")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--detik", type=float, default=60)
    ap.add_argument("--goyang", type=float, default=30, help="detik mulai uji goyang")
    ap.add_argument("--tanpa-reset", action="store_true")
    ap.add_argument("--out", default="data/cek_kualitas")
    a = ap.parse_args()

    c, g, k, dasar, boot, dur = rekam(a.port, a.baud, a.detik, a.goyang, a.tanpa_reset)
    if c.size < 5 * FS:
        sys.exit(f"sampel terlalu sedikit ({c.size}). Firmware mode teks? port benar?")

    h = analisis(c, g, k, a.goyang)
    h["laju_terukur_hz"] = round(c.size / dur, 1)
    h["boot"] = boot
    h["dasar_telat_buang"] = dasar
    h["cek"] = nilai(h, dasar)
    lulus = all(v[1] for v in h["cek"].values())
    h["lulus"] = lulus

    os.makedirs(a.out, exist_ok=True)
    stem = os.path.join(a.out, "cek_" + _dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    np.savetxt(stem + ".csv", np.c_[np.arange(c.size), c, g, k], fmt="%d", delimiter=",",
               header="indeks,cacah,gap,clamp", comments="")
    with open(stem + ".json", "w") as fh:
        json.dump(h, fh, indent=1, ensure_ascii=False)

    print("\n================ LAPORAN CEK KUALITAS ================")
    print(f"sampel {h['sampel']} ({h['durasi_s']} s, laju terukur {h['laju_terukur_hz']} Hz)")
    for nama, (v, ok) in h["cek"].items():
        print(f"  {'OK  ' if ok else 'GAGAL'} {nama:28s} {v}")
    for seg in ("diam", "goyang"):
        if seg in h:
            s = {kk: vv for kk, vv in h[seg].items() if kk != "rr_sampel"}
            print(f"  [{seg}] {s}")
    print(f"  detik datar tanpa gap: {h['detik_datar_tanpa_gap']}  detik ada gap: {h['detik_ada_gap']}")
    print("HASIL:", "LULUS" if lulus else "TIDAK LULUS")
    print("berkas:", stem + ".json")


if __name__ == "__main__":
    main()
