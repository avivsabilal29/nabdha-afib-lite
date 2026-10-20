#!/usr/bin/env python3
"""Which rule does `penanda` follow, and where does the old rule first disagree?

The RTL mirror of rantai.py:375-440 counts a beat as "lit" (menyala) when all eight
intervals of the current deret fall inside the band formed by the queue as it stands
*after* the beat has been absorbed (rantai.py:424-437 recomputes pembilang and penyebut
after the append and pop, then loops over deret). The first revision of the RTL formed
that band from the pre update reference, the one that decides `lolos`, and its full run
gave penanda 1195. This script replays the frozen model over the golden columns, counts
the lit beats under both rules, and reports the first beat where they disagree, so the
diagnosis is measured instead of guessed.
"""
import binascii
import pathlib
import sys

import numpy as np

REPO = pathlib.Path("/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite")
F0 = REPO / "rtlplan2" / "fase0"
sys.path.insert(0, str(REPO / "model" / "rantai-afib-lite"))
import rantai as R  # noqa: E402

DELAPAN = 8
orig_rr = R.rr
stat = {"checked": 0, "post": 0, "pre": 0, "first": None, "cur_idx": None, "cur_pos": None}


def wrapped(nilai_ms, state=None):
    deret_pre = list(state["deret"])
    antre_pre = list(state["antre"])
    deret_new = deret_pre + [nilai_ms]
    if len(deret_new) > DELAPAN:
        deret_new = deret_new[-DELAPAN:]
    pemb_pre = sum(antre_pre)
    peny_pre = len(antre_pre)
    ra1_post = (sum(deret_new) >> 3) if deret_new else 0
    out = orig_rr(nilai_ms, state)
    menyala = out[0]
    st2 = out[2]
    peny_post = len(st2["antre"])
    early = len(deret_pre) + 1 < DELAPAN
    if (not early) and (peny_post == DELAPAN):
        ref_pre = pemb_pre if peny_pre > 0 else ra1_post
        lit_pre = 1
        for t in deret_new:
            if not ((25 * DELAPAN * t >= 23 * ref_pre) and (25 * DELAPAN * t <= 29 * ref_pre)):
                lit_pre = 0
                break
        stat["checked"] += 1
        stat["post"] += menyala
        stat["pre"] += lit_pre
        if (menyala != lit_pre) and stat["first"] is None:
            stat["first"] = (stat["checked"], int(menyala), int(lit_pre),
                             stat["cur_idx"], stat["cur_pos"], pemb_pre, peny_pre, ra1_post)
    return out


R.rr = wrapped



def read_hex(path):
    raw = path.read_bytes()
    return np.frombuffer(binascii.unhexlify(raw.replace(b"\n", b"")), dtype=">u4")


def main():
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
            stat["cur_idx"] = idx
            stat["cur_pos"] = pos
            pv = ring_sel.ambil(pos)
            pk_f = ring_hp.maks_mutlak(pos - R.JENDELA_F, pos + R.JENDELA_F)
            st_ambang["puncak_nilai"].append(pv)
            puncak.append(pos)
            _kep, st_ambang, _r = R.ambang(st_ambang, pos, idx, pv, pk_f, st_t)
            idx += 1
    penanda_model = st_ambang["penanda"]
    print("beats with a full deret (checked)      = %d" % stat["checked"])
    print("langkah (all in band beats)            = %d" % st_ambang["langkah"])
    print("penanda under the post update band     = %d   (model state says %d)"
          % (stat["post"], penanda_model))
    print("penanda under the pre update band      = %d   (first RTL revision gave 1195)"
          % stat["pre"])
    print("difference post minus pre              = %d" % (stat["post"] - stat["pre"]))
    f = stat["first"]
    if f is None:
        print("first disagreement: none, both rules agree on every checked beat")
    else:
        print("first disagreement at checked beat #%d (peak index %s, sample %s): "
              "post %d pre %d   [pemb_pre %d peny_pre %d ra1_post %d]"
              % (f[0], f[3], f[4], f[1], f[2], f[5], f[6], f[7]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
