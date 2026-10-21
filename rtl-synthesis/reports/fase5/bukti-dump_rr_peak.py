#!/usr/bin/env python3
"""Dump the frozen model's RR sub state at every peak, to be compared with the RTL.

Same driving loop as rujukan_fase5.py (which is bit exact against the golden CSVs), plus
the state the RTL mirror of rantai.py:375-440 must reproduce: pembilang, penyebut, ra1,
ra2, gagal, jeda, semai and the search back gate 200*delta*penyebut > 83*pembilang.
"""
import binascii
import pathlib
import sys

import numpy as np

REPO = pathlib.Path("/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite")
F0 = REPO / "rtlplan2" / "fase0"
sys.path.insert(0, str(REPO / "model" / "rantai-afib-lite"))
import rantai as R  # noqa: E402


def read_hex(path):
    raw = path.read_bytes()
    return np.frombuffer(binascii.unhexlify(raw.replace(b"\n", b"")), dtype=">u4")


def main():
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 970
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 995
    jendela = read_hex(F0 / "04015.jendela.hex").astype(np.int64)
    hpv = read_hex(F0 / "04015.hp.hex").view(np.int32).astype(np.int64)
    turv = read_hex(F0 / "04015.turunan.hex").view(np.int32).astype(np.int64)

    ring_sel, ring_hp, ring_bes = R.GarisTunda(64), R.GarisTunda(64), R.GarisTunda(64)
    scan = R.RADIUS_PUNCAK
    puncak = []
    st_ambang = R.ambang_awal(semai_aktif=True, aturan_t=True, puncak=puncak)
    st_t = R.gelombang_t_awal(ring_bes)
    idx = 0
    for n in range(jendela.size):
        ring_sel.dorong(int(jendela[n]))
        ring_hp.dorong(int(hpv[n]))
        ring_bes.dorong(int(turv[n]))
        baru = []
        while scan + R.RADIUS_PUNCAK <= n:
            v = ring_sel.ambil(scan)
            if v > 0 and v >= ring_sel.maks(scan - R.RADIUS_PUNCAK, scan + R.RADIUS_PUNCAK):
                baru.append(scan)
                scan += R.RADIUS_PUNCAK
            else:
                scan += 1
        for pos in baru:
            st = st_ambang
            rr = st["tahap_rr"]
            pv = ring_sel.ambil(pos)
            pk_f = ring_hp.maks_mutlak(pos - R.JENDELA_F, pos + R.JENDELA_F)
            spki, npki, spkf, npkf = st["spki"], st["npki"], st["spkf"], st["npkf"]
            i1 = npki + ((spki - npki) >> 2)
            i2 = i1 >> 1
            iq = st["i_qrs"]
            delta = None if iq is None else pos - iq
            # the gate of rantai.py:580-585, before the walk
            if rr["penyebut"] > 0:
                aktif = 200 * delta * rr["penyebut"] > 83 * rr["pembilang"] if delta is not None else False
            elif rr["ra1"] > 0:
                aktif = 200 * delta > 83 * rr["ra1"] if delta is not None else False
            else:
                aktif = False
            if lo <= idx <= hi:
                print("PK %4d pos %7d i1 %9d i2 %9d iqrs %7s delta %6s pemb %7d peny %2d ra1 %7d ra2 %7d "
                      "gagal %2d jeda %2d semai %2d deret %2d antre %2d riw %2d gate %d"
                      % (idx, pos, i1, i2, iq, delta, rr["pembilang"], rr["penyebut"], rr["ra1"],
                         rr["ra2"], rr["gagal"], rr["jeda"], rr["semai"], len(rr["deret"]),
                         len(rr["antre"]), len(rr["riwayat"]), 1 if aktif else 0))
            st["puncak_nilai"].append(pv)
            puncak.append(pos)     # the driver's own append, rantai.py index of search_back
            _kep, st_ambang, _r = R.ambang(st, pos, idx, pv, pk_f, st_t)
            if lo <= idx <= hi:
                rr2 = st_ambang["tahap_rr"]
                print("   -> after: pemb %7d peny %2d ra1 %7d gagal %2d jeda %2d semai %2d cari %d"
                      % (rr2["pembilang"], rr2["penyebut"], rr2["ra1"], rr2["gagal"], rr2["jeda"],
                         rr2["semai"], st_ambang["cari_mundur"]))
            idx += 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
