#!/usr/bin/env python3
"""
ecg_ingest.py - pengurai aliran AD8232/ESP32 (rekaman 8 bita @250 Hz).

Satu rekaman menghasilkan berkas (catatan vault 44 bagian 6):
    ad8232_<sesi>_250hz.bin       bita mentah dari serial (bisa diurai ulang)
    ad8232_<sesi>_250hz.csv       indeks,cacah,clamp,gap,weak,tegangan_mv
    ad8232_<sesi>_250hz.stim.hex  4 digit heks/baris untuk +STIM testbench RTL
    ad8232_<sesi>_250hz.npz       cacah (int16), penanda (uint8), laju_hz
    ad8232_<sesi>_250hz.manifest.json

Contoh:
    # rekam 60 detik langsung dari ESP32
    python tools/ecg_ingest.py --port COM5 --seconds 60 --sesi uji01

    # urai ulang berkas .bin yang sudah ada
    python tools/ecg_ingest.py --from-bin data/ad8232_uji01_250hz.bin --sesi uji01

Format rekaman (little-endian):
    [0]=A5 [1]=5A [2]=penanda [3]=urutan [4..5]=cacah int16 [6]=00 [7]=jumlah(0..6)%256
    penanda: bit0 clamp, bit1 gap, bit2 weak, bit3 header
    header : [3]=ID kolom, [4..5]=nilai uint16 (tidak memakan nomor urut sampel)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import struct
import sys
import time

import numpy as np

SYNC0, SYNC1 = 0xA5, 0x5A
FRAME_LEN = 8
FLAG_CLAMP, FLAG_GAP, FLAG_WEAK, FLAG_HEADER = 0x01, 0x02, 0x04, 0x08
COUNTS_PER_MV_DEFAULT = 200

HEADER_NAMES = {
    0: "fw_version",
    1: "kit_gain",
    2: "adc_full_scale_mv",
    3: "sample_hz",
    4: "baseline_mv",
    5: "counts_per_mv",
    6: "adc_source",
    7: "status",
}


# ---------------------------------------------------------------------------
# Pengurai
# ---------------------------------------------------------------------------
class FrameParser:
    """Pengurai bertahap: bisa diberi potongan bita dari serial atau dari berkas."""

    def __init__(self) -> None:
        self.buf = bytearray()
        self.counts: list[int] = []
        self.flags: list[int] = []
        self.header: dict[str, int] = {}
        self.header_first: dict[str, int] = {}
        self.last_seq: int | None = None
        self.stats = {
            "bytes_in": 0,
            "frames_ok": 0,
            "header_frames": 0,
            "checksum_errors": 0,
            "bytes_skipped": 0,
            "lost_samples": 0,
            "seq_breaks": 0,
        }

    def feed(self, data: bytes) -> None:
        self.stats["bytes_in"] += len(data)
        self.buf.extend(data)
        b = self.buf
        i = 0
        n = len(b)
        while i + FRAME_LEN <= n:
            if b[i] != SYNC0 or b[i + 1] != SYNC1:
                i += 1
                self.stats["bytes_skipped"] += 1
                continue
            frame = b[i:i + FRAME_LEN]
            if (sum(frame[:7]) & 0xFF) != frame[7]:
                # bukan rekaman sah (atau rusak): geser satu bita lalu cari sinkron lagi
                self.stats["checksum_errors"] += 1
                i += 1
                self.stats["bytes_skipped"] += 1
                continue
            self._handle(frame)
            i += FRAME_LEN
        del b[:i]

    def _handle(self, f: bytes) -> None:
        flags = f[2]
        if flags & FLAG_HEADER:
            fid = f[3]
            val = f[4] | (f[5] << 8)
            name = HEADER_NAMES.get(fid, f"field_{fid}")
            self.header[name] = val
            self.header_first.setdefault(name, val)
            self.stats["header_frames"] += 1
            return

        seq = f[3]
        counts = struct.unpack_from("<h", f, 4)[0]
        if self.last_seq is not None:
            expected = (self.last_seq + 1) & 0xFF
            if seq != expected:
                lost = (seq - expected) & 0xFF
                self.stats["lost_samples"] += lost
                self.stats["seq_breaks"] += 1
                flags |= FLAG_GAP   # TU_GAP: sampel ini menyusul sampel yang hilang
        self.last_seq = seq
        self.counts.append(counts)
        self.flags.append(flags & 0x07)
        self.stats["frames_ok"] += 1

    @property
    def n_samples(self) -> int:
        return len(self.counts)


# ---------------------------------------------------------------------------
# Keluaran
# ---------------------------------------------------------------------------
def stim_word(counts: int, flags: int) -> int:
    """[14] weak [13] gap [12] clamp [11:0] cacah (komplemen dua 12 bit)."""
    w = counts & 0x0FFF
    if flags & FLAG_CLAMP:
        w |= 1 << 12
    if flags & FLAG_GAP:
        w |= 1 << 13
    if flags & FLAG_WEAK:
        w |= 1 << 14
    return w


def write_outputs(p: FrameParser, out_dir: str, sesi: str, argv: list[str],
                  raw_path: str | None) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, f"ad8232_{sesi}_250hz")
    counts = np.asarray(p.counts, dtype=np.int16)
    flags = np.asarray(p.flags, dtype=np.uint8)
    rate = int(p.header_first.get("sample_hz", 250))
    cpm = int(p.header_first.get("counts_per_mv", COUNTS_PER_MV_DEFAULT)) or COUNTS_PER_MV_DEFAULT

    # CSV
    with open(stem + ".csv", "w", newline="") as fh:
        fh.write("indeks,cacah,clamp,gap,weak,tegangan_mv\n")
        for i, (c, fl) in enumerate(zip(counts.tolist(), flags.tolist())):
            fh.write(f"{i},{c},{fl & 1},{(fl >> 1) & 1},{(fl >> 2) & 1},{c / cpm:.4f}\n")

    # HEX untuk +STIM
    with open(stem + ".stim.hex", "w") as fh:
        for c, fl in zip(counts.tolist(), flags.tolist()):
            fh.write(f"{stim_word(c, fl):04x}\n")

    # NPZ
    np.savez(stem + ".npz", cacah=counts, penanda=flags, laju_hz=np.int32(rate))

    n = len(counts)
    summary = {
        "sesi": sesi,
        "dibuat": _dt.datetime.now().isoformat(timespec="seconds"),
        "perintah": " ".join(argv),
        "berkas_bin": os.path.basename(raw_path) if raw_path else None,
        "jumlah_sampel": n,
        "durasi_s": round(n / rate, 3) if rate else None,
        "laju_hz": rate,
        "skala": f"{cpm} cacah per mV acuan input, dijepit +-2047",
        "format_kata_rtl": "s_tdata = {cacah[11:0], 4'b0000}; s_tuser = {weak, gap, clamp}",
        "format_hex": "4 digit heks per baris: [14] weak [13] gap [12] clamp [11:0] cacah (komplemen dua)",
        "header_firmware": p.header_first,
        "header_terakhir": p.header,
        "statistik_aliran": p.stats,
        "ringkasan_sinyal": {
            "cacah_min": int(counts.min()) if n else None,
            "cacah_maks": int(counts.max()) if n else None,
            "persen_gap": round(100.0 * float(np.mean((flags & FLAG_GAP) > 0)), 3) if n else None,
            "persen_clamp": round(100.0 * float(np.mean((flags & FLAG_CLAMP) > 0)), 3) if n else None,
        },
    }
    with open(stem + ".manifest.json", "w") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    return summary


# ---------------------------------------------------------------------------
# Sumber data
# ---------------------------------------------------------------------------
def capture_serial(port: str, baud: int, seconds: float, raw_path: str, p: FrameParser) -> None:
    try:
        import serial  # pyserial
    except ImportError:
        sys.exit("pyserial belum terpasang: pip install pyserial")

    with serial.Serial(port, baud, timeout=0.2) as ser, open(raw_path, "wb") as raw:
        ser.reset_input_buffer()
        t0 = time.time()
        last_report = t0
        print(f"merekam {seconds:.0f} s dari {port} @ {baud} ... (Ctrl+C untuk berhenti lebih awal)")
        try:
            while time.time() - t0 < seconds:
                data = ser.read(4096)
                if data:
                    raw.write(data)
                    p.feed(data)
                now = time.time()
                if now - last_report >= 1.0:
                    last_report = now
                    gap = sum(1 for f in p.flags[-250:] if f & FLAG_GAP)
                    last = p.counts[-1] if p.counts else 0
                    print(f"  t={now - t0:5.1f}s sampel={p.n_samples:6d} "
                          f"cacah_terakhir={last:6d} gap_1s={gap:3d} "
                          f"cksum_err={p.stats['checksum_errors']} hilang={p.stats['lost_samples']}")
        except KeyboardInterrupt:
            print("dihentikan pengguna")


def main() -> None:
    ap = argparse.ArgumentParser(description="Pengurai aliran AD8232/ESP32 -> csv, stim.hex, npz")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--port", help="port serial, mis. COM5 atau /dev/ttyUSB0")
    src.add_argument("--from-bin", help="urai berkas .bin hasil rekaman sebelumnya")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=60.0, help="lama rekaman (detik)")
    ap.add_argument("--sesi", required=True, help="nama sesi, mis. uji01, sinus1mv, subjekA")
    ap.add_argument("--out", default="data", help="folder keluaran (bawaan: data)")
    ap.add_argument("--skip-seconds", type=float, default=0.0,
                    help="buang N detik pertama (mis. saat elektroda baru ditempel)")
    args = ap.parse_args()

    p = FrameParser()
    os.makedirs(args.out, exist_ok=True)
    if args.port:
        raw_path = os.path.join(args.out, f"ad8232_{args.sesi}_250hz.bin")
        capture_serial(args.port, args.baud, args.seconds, raw_path, p)
    else:
        raw_path = args.from_bin
        with open(raw_path, "rb") as fh:
            p.feed(fh.read())

    if args.skip_seconds > 0:
        k = int(args.skip_seconds * int(p.header_first.get("sample_hz", 250)))
        p.counts, p.flags = p.counts[k:], p.flags[k:]

    if p.n_samples == 0:
        sys.exit("tidak ada sampel sah. Cek: firmware mode biner? baud 115200? port benar?")

    s = write_outputs(p, args.out, args.sesi, sys.argv, raw_path)
    print(json.dumps({k: s[k] for k in ("jumlah_sampel", "durasi_s", "header_firmware",
                                         "statistik_aliran", "ringkasan_sinyal")},
                     indent=2, ensure_ascii=False))
    print(f"berkas ditulis ke folder: {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
