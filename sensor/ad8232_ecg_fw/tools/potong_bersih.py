#!/usr/bin/env python3
"""
potong_bersih.py - potong segmen bersih dari berkas .bin memakai FrameParser + write_outputs
dari ecg_ingest.py (bukan dari .csv), lalu catat asal potongan di manifest.

Contoh (rekaman direkam dengan --skip-seconds 30, potong detik 120-1500 sesudah buangan itu):
    python tools/potong_bersih.py --bin data/ad8232_raihan_duduk30m_250hz.bin \
        --skip-seconds 30 --mulai 120 --akhir 1500 --sesi raihan_duduk30m_bersih
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecg_ingest import FrameParser, write_outputs  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Potong segmen bersih dari .bin")
    ap.add_argument("--bin", required=True)
    ap.add_argument("--skip-seconds", type=float, default=0.0,
                    help="buangan awal yang sama dengan saat merekam")
    ap.add_argument("--mulai", type=float, required=True, help="detik, sesudah buangan awal")
    ap.add_argument("--akhir", type=float, required=True, help="detik (eksklusif)")
    ap.add_argument("--sesi", required=True)
    ap.add_argument("--out", default="data")
    a = ap.parse_args()

    p = FrameParser()
    with open(a.bin, "rb") as fh:
        p.feed(fh.read())
    rate = int(p.header_first.get("sample_hz", 250))
    k = int(a.skip_seconds * rate)
    i0, i1 = k + int(a.mulai * rate), k + int(a.akhir * rate)
    if i1 > p.n_samples or i0 >= i1:
        sys.exit(f"rentang di luar rekaman: {i0}..{i1} dari {p.n_samples} sampel")
    p.counts, p.flags = p.counts[i0:i1], p.flags[i0:i1]

    s = write_outputs(p, a.out, a.sesi, sys.argv, a.bin)
    s["potongan"] = {
        "sumber_bin": os.path.basename(a.bin),
        "buang_awal_s": a.skip_seconds,
        "mulai_s_sesudah_buangan": a.mulai, "akhir_s_sesudah_buangan": a.akhir,
        "indeks_sampel_bin": [i0, i1],
        "catatan": "statistik_aliran dihitung atas seluruh .bin, bukan hanya potongan",
    }
    path = os.path.join(a.out, f"ad8232_{a.sesi}_250hz.manifest.json")
    with open(path, "w") as fh:
        json.dump(s, fh, indent=2, ensure_ascii=False)
    print(json.dumps({kk: s[kk] for kk in ("jumlah_sampel", "durasi_s", "ringkasan_sinyal",
                                            "potongan")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
