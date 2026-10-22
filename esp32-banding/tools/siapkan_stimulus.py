#!/usr/bin/env python3
"""siapkan_stimulus.py -- kata stimulus .hex (satu kata 4 digit per baris) -> biner uint16 LE.

Biner inilah yang ditanam di flash firmware (dut_fw/data/stimulus.bin) dan dibaca uji PC.
Isinya kata yang sama persis dengan +STIM testbench RTL, jadi ESP32, RTL dan model Python
makan masukan yang identik. sha256 biner dicetak di sini, dicetak lagi oleh ESP32 saat boot,
dan dicatat di berkas acuan, supaya ketiganya bisa dicocokkan.

    python esp32-banding/tools/siapkan_stimulus.py --record 04015
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys

HERE = pathlib.Path(__file__).absolute().parent
BANDING = HERE.parent
ROOT = BANDING.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", default="04015")
    ap.add_argument("--hex", help="default rtl/tb/vektor/<rec>.stimulus.hex")
    ap.add_argument("--out", help="default esp32-banding/dut_fw/data/stimulus.bin")
    args = ap.parse_args()
    src = pathlib.Path(args.hex) if args.hex else ROOT / "rtl" / "tb" / "vektor" / (
        "%s.stimulus.hex" % args.record)
    out = pathlib.Path(args.out) if args.out else BANDING / "dut_fw" / "data" / "stimulus.bin"
    words = [int(t, 16) for t in src.read_text().split()]
    bad = [w for w in words if w < 0 or w > 0x7FFF]
    if bad:
        raise SystemExit("kata di luar 15 bit: %d buah" % len(bad))
    blob = struct.pack("<%dH" % len(words), *words)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    sha = hashlib.sha256(blob).hexdigest()
    try:
        src_txt = src.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        src_txt = str(src)
    man = {"record": args.record, "source": src_txt, "words": len(words), "bytes": len(blob),
           "sha256": sha, "format": "uint16 little endian, bit 11..0 hitungan 12 bit bertanda, "
                                    "bit 14..12 penanda"}
    out.with_suffix(".json").write_text(json.dumps(man, indent=2))
    # header untuk firmware: nama rekaman, panjang, sha256 yang diharapkan
    info = BANDING / "dut_fw" / "src" / "stimulus_info.h"
    if not args.out:
        info.write_text("/* dibuat oleh tools/siapkan_stimulus.py, jangan disunting */\n"
                        "#pragma once\n#define STIM_REC \"%s\"\n#define STIM_N %du\n"
                        "#define STIM_SHA256 \"%s\"\n" % (args.record, len(words), sha))
        print("stimulus: %s ditulis" % info)
    print("stimulus: %d kata -> %s (%d bita)" % (len(words), out, len(blob)))
    print("stimulus: sha256 %s" % sha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
