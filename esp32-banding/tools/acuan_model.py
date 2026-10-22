#!/usr/bin/env python3
"""acuan_model.py -- jawaban acuan model Python untuk banding ESP32.

Menjalankan rantai beku (tools/model_core.py -> model/rantai-afib-lite/rantai.py) atas kata
stimulus yang sama persis dengan yang ditanam di firmware, lalu menulis satu berkas JSON:

  - sidik jari enam kolom per sampel (masukan16, lp, hp, turunan, kuadrat, jendela)
  - deret QRS dan penanda irama 7b per interval
  - setiap posisi jendela 32 interval langkah 4 di lengan yang dipilih, dengan fitur model,
    kelas model (gerbang 0.165 / 0.63), label anotasi, dan apakah model menyimpannya

Model hanya menyimpan jendela yang labelnya seragam AFIB atau N dan lolos gerbang rentang
200..3000 ms (rantai.kumpulkan_jendela). Skrip ini mengulang loop yang sama sambil mencatat
posisi i tiap jendela, lalu MEMBUKTIKAN hasilnya identik dengan R.kumpulkan_jendela sebelum
menulis apa pun. Tidak ada aritmetika model yang ditulis ulang di sini.

Pemakaian (dari akar repo):
    python esp32-banding/tools/acuan_model.py --record 04015
    python esp32-banding/tools/acuan_model.py --record 04015 --limit 20000     # uji cepat

Butuh numpy. wfdb tidak wajib: anotasi .atr dibaca oleh pembaca format MIT di bawah.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).absolute().parent
BANDING = HERE.parent
ROOT = BANDING.parent
sys.path.insert(0, str(ROOT / "tools"))

T1 = 0.165          # uji_10_berpenanda.py:158
T2 = 0.63           # uji_10_berpenanda.py:159
MASK64 = (1 << 64) - 1


# ------------------------------------------------------------------------------------------
# Pembaca anotasi WFDB format MIT (cukup untuk sample + aux_note)
# ------------------------------------------------------------------------------------------
def baca_atr(path: pathlib.Path):
    """Kembalikan (sample[], aux_note[]) seperti wfdb.rdann(...).sample / .aux_note."""
    try:
        import wfdb  # noqa: F401
        an = wfdb.rdann(str(path.with_suffix("")), "atr")
        return np.asarray(an.sample, dtype=np.int64), [str(x) for x in an.aux_note]
    except Exception:
        pass
    data = path.read_bytes()
    i = 0
    t = 0
    samples, aux = [], []
    while i + 1 < len(data):
        word = data[i] | (data[i + 1] << 8)
        i += 2
        a, k = word >> 10, word & 0x3FF
        if a == 0 and k == 0:
            break
        if a == 59:                                   # SKIP, 32 bit dalam urutan PDP-11
            hi = data[i] | (data[i + 1] << 8)
            lo = data[i + 2] | (data[i + 3] << 8)
            i += 4
            skip = (hi << 16) | lo
            if skip & 0x80000000:
                skip -= 1 << 32
            t += skip
            continue
        if a in (60, 61, 62):                         # NUM, SUB, CHN
            continue
        if a == 63:                                   # AUX, k bita
            s = data[i:i + k].split(b"\x00")[0].decode("latin-1")
            i += k + (k & 1)
            if aux:
                aux[-1] = s
            continue
        t += k
        samples.append(t)
        aux.append("")
    return np.asarray(samples, dtype=np.int64), aux


def checksum(col) -> tuple[int, int]:
    """S1 = sum v, S2 = sum (i+1) v, keduanya modulo 2**64, v int64 komplemen dua.

    Firmware menghitung hal yang sama dengan uint64 yang membungkus."""
    v = np.asarray(col, dtype=np.int64).astype(np.uint64)
    idx = np.arange(1, v.size + 1, dtype=np.uint64)
    with np.errstate(over="ignore"):
        s1 = int(np.sum(v, dtype=np.uint64)) & MASK64
        s2 = int(np.sum(v * idx, dtype=np.uint64)) & MASK64
    return s1, s2


def dbits(x: float) -> str:
    return struct.pack(">d", float(x)).hex()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--record", default="04015")
    ap.add_argument("--stim", help="berkas stimulus .hex (default rtl/tb/vektor/<rec>.stimulus.hex)")
    ap.add_argument("--atr", help="anotasi .atr (default dataset/afdb/<rec>.atr)")
    ap.add_argument("--arm", choices=("berpenanda", "mentah"), default="berpenanda")
    ap.add_argument("--limit", type=int, help="potong di n sampel (uji cepat)")
    ap.add_argument("--out", help="berkas JSON keluaran (default esp32-banding/acuan/<rec>.<arm>.json)")
    args = ap.parse_args()

    import model_core as MC
    R = MC.R

    stim = pathlib.Path(args.stim) if args.stim else ROOT / "rtl" / "tb" / "vektor" / (
        "%s.stimulus.hex" % args.record)
    atr = pathlib.Path(args.atr) if args.atr else ROOT / "dataset" / "afdb" / ("%s.atr" % args.record)
    kata = MC.baca_stimulus(stim)
    if args.limit:
        kata = kata[:args.limit]
    n = int(kata.size)
    stim_sha = hashlib.sha256(np.asarray(kata, dtype="<u2").tobytes()).hexdigest()
    print("acuan: %d kata dari %s (sha256 biner %s...)" % (n, stim, stim_sha[:16]))

    t0 = time.time()
    out = MC.jalankan_model(kata)
    print("acuan: rantai beku selesai dalam %.1f s (inti %.1f s)" % (time.time() - t0, out["detik"]))

    qrs = np.asarray(out["qrs"], dtype=np.int64)
    rr_ms = np.diff(qrs) / R.FS_HZ * 1000.0
    tanda = np.asarray(R.tanda_deret(rr_ms), dtype=np.int64)
    if not np.array_equal(tanda, np.asarray(out["rr_mark_raw"], dtype=np.int64)):
        raise SystemExit("acuan: penanda tanda_deret berbeda dari rr_mark_raw rantai")

    lab = None
    if atr.exists():
        sampel, catatan = baca_atr(atr)
        lab = R.label_irama(sampel, catatan, n)
        print("acuan: %d anotasi dibaca dari %s" % (len(sampel), atr))
    else:
        print("acuan: anotasi %s tidak ada, label jendela kosong" % atr)

    # seri jendela, persis R.kumpulkan_jendela
    if args.arm == "berpenanda":
        rr_sel, src = R.seri_berpenanda(rr_ms, tanda)
    else:
        rr_sel, src = rr_ms.copy(), np.arange(rr_ms.size, dtype=np.int64)
    bl_all = lab[qrs[1:]] if lab is not None else np.array([""] * rr_ms.size, dtype=object)
    bl = bl_all[src]

    jendela = []
    simpan_arr, simpan_cls = [], []
    for i in range(0, rr_sel.size - R.JENDELA_DENYUT, R.LANGKAH_DENYUT):
        seg = rr_sel[i:i + R.JENDELA_DENYUT]
        u = np.unique(bl[i:i + R.JENDELA_DENYUT])
        label_ok = bool(u.size == 1 and u[0] in ("AFIB", "N"))
        gate = not (seg.min() < 200 or seg.max() > 3000)
        row = {"win_no": i // R.LANGKAH_DENYUT, "i_start": i,
               "src_first": int(src[i]), "src_last": int(src[i + R.JENDELA_DENYUT - 1]),
               "qrs_end": int(qrs[src[i + R.JENDELA_DENYUT - 1] + 1]),
               "label": str(u[0]) if u.size == 1 else "campur",
               "label_ok": label_ok, "gate_ok": gate, "disimpan_model": label_ok and gate}
        if gate:
            f = R.fitur_irama(seg)
            kelas = 2 if (f[1] > T1 and f[3] > T2) else 1
            row.update({"rmssd": f[0], "ratio": f[1], "pnn50": f[2], "ent4": f[3],
                        "bits": [dbits(f[0]), dbits(f[1]), dbits(f[2]), dbits(f[3])],
                        "kelas_model": kelas})
            if label_ok:
                simpan_arr.append(f)
                simpan_cls.append(str(u[0]))
        else:
            row["kelas_model"] = 0
        jendela.append(row)

    # bukti: loop di atas identik dengan R.kumpulkan_jendela
    if lab is not None:
        sumber = R.SUMBER_BERPENANDA if args.arm == "berpenanda" else R.SUMBER_MENTAH
        arr_ref, cls_ref = R.kumpulkan_jendela(qrs, lab, sumber=sumber, mark=tanda)
        arr_me = np.array(simpan_arr, float).reshape(-1, 4)
        if arr_ref.shape != arr_me.shape or not np.array_equal(arr_ref, arr_me) \
                or list(cls_ref) != simpan_cls:
            raise SystemExit("acuan: jendela yang dicatat berbeda dari R.kumpulkan_jendela")
        print("acuan: %d jendela disimpan model, identik dengan R.kumpulkan_jendela" % len(simpan_cls))

    kolom = {}
    for k in ("masukan16", "lp", "hp", "turunan", "kuadrat", "jendela"):
        s1, s2 = checksum(out[k])
        kolom[k] = {"s1": "%016x" % s1, "s2": "%016x" % s2}

    disimpan = [w for w in jendela if w["disimpan_model"]]
    census = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    for w in disimpan:
        af = w["label"] == "AFIB"
        fired = w["kelas_model"] == 2
        census["TP" if fired and af else "FP" if fired else "FN" if af else "TN"] += 1

    payload = {
        "record": args.record, "arm": args.arm, "n": n, "stim": str(stim), "stim_sha256": stim_sha,
        "t1": T1, "t2": T2, "kolom": kolom,
        "qrs": qrs.tolist(), "rr_ms": [int(x) for x in rr_ms], "mark": tanda.tolist(),
        "n_puncak": int(np.asarray(out["puncak"]).size),
        "jendela": jendela,
        "ringkas": {"posisi_jendela": len(jendela), "disimpan_model": len(disimpan),
                    "review_model": sum(1 for w in disimpan if w["kelas_model"] == 2),
                    "normal_model": sum(1 for w in disimpan if w["kelas_model"] == 1),
                    "census": census},
        "dibuat": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    out_path = pathlib.Path(args.out) if args.out else BANDING / "acuan" / (
        "%s.%s%s.json" % (args.record, args.arm, (".n%d" % n) if args.limit else ""))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload))
    print("acuan: %d QRS, %d posisi jendela, %d disimpan model (review %d, normal %d)"
          % (qrs.size, len(jendela), len(disimpan), payload["ringkas"]["review_model"],
             payload["ringkas"]["normal_model"]))
    print("acuan: census model vs label %s" % census)
    print("acuan: ditulis ke %s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
