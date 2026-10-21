#!/usr/bin/env python3
"""Verifikasi asal kolom emas Fase 5 terhadap larik keluaran model.

Latar: skrip penyiap vektor fase lain (6, 7, 8, 9, 11) menghitung ulang kolom emasnya
terhadap ekspresi aturan model dan menggagalkan diri bila ada beda. Skrip
`siapkan_vektor_fase5.py` tidak melakukannya: ia hanya memeriksa struktur lalu mempack
`rtlplan2/fase5/04015.peaks.csv`, sehingga asal kolom emasnya tidak terbukti dari dalam repo.
Skrip ini menutup lubang itu.

Yang diperiksa (semua terhadap fixture model, bukan terhadap berkas yang sama):

1. Kolom `sample_index` pada peaks.csv identik dengan larik `puncak` model.
2. Kolom `in_band` identik dengan bit 1 berkas bendera `04015.puncak.flag.hex`.
3. Kolom `t_rejected` identik dengan bit 2 berkas bendera yang sama.
4. Berkas `04015.puncak.pos.hex` (yang dibaca testbench) identik dengan kolom `sample_index`.
5. Cacah baris dengan `is_qrs` menyala sama dengan panjang larik `qrs` model.

Jalankan dari akar repo:

    python3 rtl/tb/vektor/fase5/verifikasi_fase5.py

Kode keluar 0 bila seluruh pemeriksaan cocok, 1 bila ada yang tidak cocok.
"""

from __future__ import annotations

import csv
import pathlib
import sys

AKAR = pathlib.Path(__file__).resolve().parents[4]
FIKS = AKAR / "model" / "rantai-afib-lite" / "fixture" / "04015_30m.npz"
PEAKS = AKAR / "rtlplan2" / "fase5" / "04015.peaks.csv"
BENDERA = AKAR / "rtl" / "tb" / "vektor" / "fase5" / "04015.puncak.flag.hex"
POS_HEX = AKAR / "rtl" / "tb" / "vektor" / "fase5" / "04015.puncak.pos.hex"


def baca_hex(path: pathlib.Path) -> list[int]:
    return [int(t, 16) for t in path.read_text().split()]


def baca_peaks(path: pathlib.Path) -> list[dict]:
    with path.open() as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    gagal: list[str] = []
    lapor: list[str] = []

    for p in (FIKS, PEAKS, BENDERA, POS_HEX):
        if not p.exists():
            print(f"GAGAL: berkas tidak ada: {p}")
            return 1

    import numpy as np

    z = np.load(FIKS)
    rows = baca_peaks(PEAKS)
    bendera = baca_hex(BENDERA)
    pos_hex = baca_hex(POS_HEX)

    puncak = z["puncak"].astype(int)
    qrs = z["qrs"].astype(int) if "qrs" in z else None

    # 1. jumlah baris
    if len(rows) != len(puncak):
        gagal.append(f"jumlah baris peaks.csv {len(rows)} != larik puncak model {len(puncak)}")
    else:
        lapor.append(f"jumlah baris: {len(rows)} == larik puncak model")

    # 2. sample_index vs puncak
    try:
        si = [int(r["sample_index"]) for r in rows]
        beda = [i for i, (a, b) in enumerate(zip(si, puncak)) if a != b]
        if beda:
            gagal.append(f"sample_index beda pada {len(beda)} baris, contoh {beda[:5]}")
        else:
            lapor.append(f"sample_index identik dengan larik puncak ({len(si)} baris, beda 0)")
    except (KeyError, ValueError) as exc:
        gagal.append(f"kolom sample_index tidak terbaca: {exc}")

    # 3. bendera: bit 1 = in_band, bit 2 = t_rejected
    if len(bendera) != len(rows):
        gagal.append(f"panjang berkas bendera {len(bendera)} != jumlah baris peaks {len(rows)}")
    else:
        for nama_kolom, bit in (("in_band", 1), ("t_rejected", 2)):
            try:
                kol = [int(r[nama_kolom] or 0) for r in rows]
            except (KeyError, ValueError) as exc:
                gagal.append(f"kolom {nama_kolom} tidak terbaca: {exc}")
                continue
            bit_v = [(x >> bit) & 1 for x in bendera]
            beda = [i for i, (a, b) in enumerate(zip(kol, bit_v)) if a != b]
            if beda:
                gagal.append(
                    f"bendera bit {bit} beda dari kolom {nama_kolom} pada {len(beda)} baris, "
                    f"contoh {beda[:5]}"
                )
            else:
                lapor.append(f"bendera bit {bit} == kolom {nama_kolom} ({len(kol)} baris, beda 0)")

    # 4. berkas pos yang dibaca testbench vs kolom sample_index
    if len(pos_hex) != len(rows):
        gagal.append(f"panjang {POS_HEX.name} {len(pos_hex)} != jumlah baris peaks {len(rows)}")
    else:
        si = [int(r["sample_index"]) for r in rows]
        beda = [i for i, (a, b) in enumerate(zip(pos_hex, si)) if a != b]
        if beda:
            gagal.append(f"{POS_HEX.name} beda dari sample_index pada {len(beda)} baris, contoh {beda[:5]}")
        else:
            lapor.append(f"{POS_HEX.name} identik dengan sample_index ({len(pos_hex)} kata, beda 0)")

    # 5. cacah is_qrs vs panjang larik qrs model
    if qrs is not None:
        cacah = sum(1 for r in rows if int(r.get("is_qrs") or 0) == 1)
        if cacah != len(qrs):
            gagal.append(f"cacah is_qrs={cacah} != panjang larik qrs model {len(qrs)}")
        else:
            lapor.append(f"cacah is_qrs == panjang larik qrs model ({cacah})")
    else:
        lapor.append("larik qrs tidak ada di fixture, pemeriksaan 5 dilewati")

    print("verifikasi fase 5: asal kolom emas terhadap model")
    for baris in lapor:
        print(f"  OK   {baris}")
    for baris in gagal:
        print(f"  BEDA {baris}")
    if gagal:
        print(f"\nGAGAL: {len(gagal)} pemeriksaan tidak cocok")
        return 1
    print(f"\nLULUS: {len(lapor)} pemeriksaan cocok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
