#!/usr/bin/env python3
"""Uji pembanding mock PS terhadap aturan RTL, memakai kelas MockBackend yang asli.

Latar: pembanding mock di `ps/ps_driver_afib.py` pernah membandingkan fitur dalam satuan
tampilan register (`round(f_ratio x 200) > 33`), sedangkan RTL membandingkan kata fitur dalam
skalanya sendiri setelah batas top menjembatani kedua register itu (lihat
`rtl/classifier.sv:83-84`, `:128-129`, `:132-135`). Selisih setengah LSB itu membuat mock
kehilangan 7 dari 588 putusan terhadap sensus emas. Uji ini menjaga agar tidak kembali.

Yang diuji: putusan menyala kelas `2` (review) dari `_emit_window`, dibandingkan dengan aturan
RTL: ratio Q1.16 > 10813 dan entropy_over_4 Q1.14 > 10322 — nilai jembatan register 33 x 65536/200
dan 63 x 16384/100. Aturan sisi RTL ini yang mereproduksi `arms.mentah.census.fired = 183`
pada manifes fase 9.

Dipakai dari akar repo:
    python3 ps/uji_mock_vs_rtl.py
Keluar dengan 0 bila sama seluruhnya, 1 bila ada beda.
"""
import importlib.util
import pathlib
import sys

import numpy as np

AKAR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AKAR / "ps"))

spec = importlib.util.spec_from_file_location("psd", AKAR / "ps" / "ps_driver_afib.py")
assert spec is not None and spec.loader is not None
psd = importlib.util.module_from_spec(spec)
sys.modules["psd"] = psd
spec.loader.exec_module(psd)

z = np.load(sorted((AKAR / "model" / "rantai-afib-lite" / "fixture").glob("*.npz"))[0])
F = z["jendela_fitur"].astype(float)

# jembatan register ke skala fitur, sama dengan aturan K7 (dibulatkan ke terdekat)
BR_RASIO = round(33 * 65536 / 200)      # 10813
BR_ENTROPI = round(63 * 16384 / 100)    # 10322
q16 = np.round(F[:, 1] * 65536.0).astype(np.int64)
q14 = np.round(F[:, 3] * 16384.0).astype(np.int64)
rtl = (q16 > BR_RASIO) & (q14 > BR_ENTROPI)

mock = psd.MockBackend(peaks=[], features=F, words={})
IDX = psd.IDX
menyala = np.zeros(len(F), dtype=bool)
for k in range(len(F)):
    mock.window_no = k
    mock.beat_idx_in = [0, 100]
    mock.regs[IDX["ARM_SELECT"]] = 0x0F
    mock.regs[IDX["RATIO_THRESH"]] = 0x21
    mock.regs[IDX["ENTROPY_THRESH"]] = 0x3F
    mock.windows.clear()
    mock._emit_window(1000 + k)
    menyala[k] = (mock.regs[IDX["CLASS_OUT"]] & 0x3) == 2

beda = np.flatnonzero(menyala != rtl)
print("uji pembanding mock PS terhadap aturan RTL")
print(f"  jendela diuji           : {len(F)}")
print(f"  mock menyala            : {int(menyala.sum())}")
print(f"  RTL menyala (aturan K7) : {int(rtl.sum())}")
print(f"  putusan berbeda         : {len(beda)}")
for k in beda[:10]:
    print(f"    jendela {k}: rasio={F[k,1]:.8f} entropy_over_4={F[k,3]:.8f} "
          f"mock={bool(menyala[k])} rtl={bool(rtl[k])}")
if len(beda):
    print(f"BEDA ({len(beda)} jendela)")
    sys.exit(1)
print("LULUS")
