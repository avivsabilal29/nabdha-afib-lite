#!/usr/bin/env python3
"""
make_synthetic_stream.py - buat aliran .bin tiruan ESP32 tanpa perangkat keras.

Memakai rumus skala yang sama dengan firmware (ecg_frame.c):
    ADC 2 kHz (mV di OUT) -> jumlah 8 -> cacah = floor(25*(jumlah - 8*dasar)/gain)
lalu dibungkus rekaman 8 bita + header tiap detik. Hasilnya diurai dengan
ecg_ingest.py --from-bin, sehingga Aviv bisa menguji replay +STIM sebelum sensor siap.

    python tools/make_synthetic_stream.py --seconds 60 --out data/sintetis.bin
    python tools/ecg_ingest.py --from-bin data/sintetis.bin --sesi sintetis

Bagian pertama teratur (75 BPM), bagian kedua RR acak (mirip AF), dan ada
0,5 s elektroda lepas di tengah bagian kedua.
"""
import argparse
import struct

import numpy as np

FS_SUB, NSUB, FS = 2000, 8, 250


def beat(t):
    g = lambda mu, s, a: a * np.exp(-0.5 * ((t - mu) / s) ** 2)
    return (g(-0.20, 0.025, 0.12) + g(-0.03, 0.010, -0.15) + g(0.0, 0.012, 1.20)
            + g(0.03, 0.010, -0.25) + g(0.30, 0.050, 0.30))


def frame(flags, b3, value16):
    f = bytearray([0xA5, 0x5A, flags, b3]) + struct.pack("<H", value16 & 0xFFFF) + b"\x00"
    f.append(sum(f) & 0xFF)
    return bytes(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--gain", type=int, default=100)
    ap.add_argument("--baseline-mv", type=int, default=1650)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="data/sintetis.bin")
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    half = a.seconds / 2
    peaks, t = [], 0.4
    while t < a.seconds:
        peaks.append(t)
        t += 0.80 if t < half else rng.uniform(0.45, 0.85)
    peaks = np.array(peaks)

    ts = np.arange(int(a.seconds * FS_SUB)) / FS_SUB
    mv_in = np.zeros_like(ts)
    for p in peaks:
        m = (ts > p - 0.4) & (ts < p + 0.6)
        mv_in[m] += beat(ts[m] - p)
    lead_off = (ts >= half + 4.0) & (ts < half + 4.5)
    mv_out = np.round(a.baseline_mv + a.gain * mv_in + rng.integers(-3, 4, ts.size)).astype(np.int64)
    mv_out[lead_off] = 3100

    n = ts.size // NSUB
    sums = mv_out[: n * NSUB].reshape(n, NSUB).sum(axis=1)
    lo = lead_off[: n * NSUB].reshape(n, NSUB).any(axis=1)
    rail = (mv_out[: n * NSUB] >= 3090).reshape(n, NSUB).any(axis=1)
    counts = np.floor_divide(25 * (sums - 8 * a.baseline_mv), a.gain)
    clamp = rail | (counts > 2047) | (counts < -2047)
    counts = np.clip(counts, -2047, 2047)

    hdr = [0x0100, a.gain, 3100, FS, a.baseline_mv, 200, 0, 0]   # adc_source 0 = sintetis
    out = bytearray(b"ets Jun  8 2016 00:22:57\r\n")              # sampah boot, seperti ESP32 asli
    for i in range(n):
        if i % FS == 0:
            for fid, v in enumerate(hdr):
                out += frame(0x08, fid, v)
        flags = (1 if clamp[i] else 0) | (2 if lo[i] else 0)
        out += frame(flags, i & 0xFF, int(counts[i]))

    import os
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "wb") as fh:
        fh.write(out)
    print(f"{n} sampel ({n / FS:.1f} s) ditulis ke {a.out}")


if __name__ == "__main__":
    main()
