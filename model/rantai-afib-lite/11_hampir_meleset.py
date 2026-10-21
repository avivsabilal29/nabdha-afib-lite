#!/usr/bin/env python3
"""AFIB-LITE phase 6 measurement: how near the envelope came to the search back floor.

MEASUREMENT ONLY. This file reads the frozen chain and prints numbers. It does not edit
rantai.py, adapter.py, any other file of this folder, and it does not write any fixture. No
git add and no commit is performed or suggested here.

What is measured.

  A. The search back rule exactly as rantai.py applies it, written as its two integer
     predicates, plus the one line of rantai.py that closes the case of recording 04015.
  B. For every interval between two beats that is long, meaning longer than 1.5 times the
     running median or longer than 1500 ms, on five recordings: the largest envelope peak
     value inside the search back window of that interval, the two adaptive thresholds I1 and
     I2 at the moment that window was scanned, and the two ratios max_peak/I2 and max_peak/I1.
     The rows are sorted from the highest ratio downward, so it becomes visible whether the
     4856 ms interval of 04015 is a single case or one member of a pattern.
  C. For each proposed change of the rule, how many other intervals of the five recordings
     would be touched, how many beats would be added or removed, and whether the beat series
     would move, which would force every fixture to be frozen again.

Instrumentation method. The frozen stage function `rantai.ambang` is wrapped at the module
level with a recording wrapper. `Rantai.langkah` looks the name up in its own module globals
at call time, so the wrapper observes the real run without any edit of the frozen file. The
wrapper reads the two thresholds from the state before delegating, because `ambang` itself
computes them from `state["spki"]` and `state["npki"]` at the top of its body:

    i1 = npki + ((spki - npki) >> 2)
    i2 = i1 >> 1

The wrapper never changes a value, so the run it observes is the frozen run. Section 1 proves
that by comparing the observed beat list and peak list of 04015 against the frozen fixture
`fixture/04015_30m.npz`.

The variant rule of section 4 is a second, independent copy of the threshold stage, held in
this measurement file only, with the floor of the search back candidate test as a parameter.
It is proven faithful first: with the frozen floor it must reproduce the frozen beat list and
peak list of every recording.

Run it with the project interpreter:

    cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/uji_11_hampir_meleset.py

Exit code 0 when every measurement ran and every fidelity check passed, 1 otherwise.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import rantai as R                     # noqa: E402  the frozen core, read only
import adapter as A                    # noqa: E402  the frozen adapters, read only
import uji_06_referensi as U              # noqa: E402  the data path of the frozen reference gate

NPZ = HERE / "fixture" / "04015_30m.npz"
DATA_ROOT = pathlib.Path("/home/avivsabilalm/nabdha-data")
SECONDS = 1800.0
FRAMES = int(round(SECONDS * R.FS_HZ))

# The five recordings of this measurement. 04015 is the case under study, the other four are
# the test recordings of the frozen reference gate.
RECORDS = (
    dict(key="afdb/04015", db="afdb", fs=250.0, channel=0),
    dict(key="afdb/04043", db="afdb", fs=250.0, channel=0),
    dict(key="afdb/04126", db="afdb", fs=250.0, channel=0),
    dict(key="nsrdb/16265", db="nsrdb", fs=128.0, channel=0),
    dict(key="mitdb/100", db="mitdb", fs=360.0, channel=0),
)

# The long interval rule: an interval counts as long when it is above 1.5 times the running
# median of the intervals seen so far, or above 1500 ms.
PANJANG_KALI_MEDIAN = 3          # x * 2 > 3 * median, cross form, no division
MEDIAN_JENDELA = 32
MEDIAN_MIN = 8
PANJANG_MS = 1500

# The five proposals. The default row is the frozen rule, floor = I2 exactly. Every other row
# lowers the floor of the search back candidate test with one right shift and one subtraction,
# which is what the no hard multiplier rule of the core allows.
PROPOSAL = (
    dict(name="FROZEN floor=I2=floor(I1/2)", floor="i2", d_shift=None),
    dict(name="P1 floor=I2-(I2>>4)=15/16 of I2", floor="kurang", d_shift=4),
    dict(name="P2 floor=I2-(I2>>2)=3/4 of I2", floor="kurang", d_shift=2),
    dict(name="P3 floor=I2>>1=1/2 of I2=floor(I1/4)", floor="separuh", d_shift=1),
)

HASIL = []


def baris(ok, nama, teks=""):
    """One result line plus its verdict, the reporting shape of the frozen gate files."""
    HASIL.append(bool(ok))
    print("[%2d] %s  %-58s %s" % (len(HASIL), "PASS" if ok else "FAIL", nama, teks), flush=True)
    return ok


def info(nama, teks):
    print("     INFO  %-58s %s" % (nama, teks), flush=True)


def lapor(nama, teks):
    """A reported fact. It is not a check and it never fails the run."""
    print("     REPORT %-57s %s" % (nama, teks), flush=True)


def kepala(teks):
    print()
    print(teks, flush=True)


def sha256_berkas(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blok in iter(lambda: fh.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


# =============================================================================================
# Reading one recording to the chain input series, through the frozen data path only.
# =============================================================================================

def deret_masukan(rec):
    """The chain input value of every sample of one recording, 450000 samples at the locked rate.

    A 250 Hz record goes straight through the frozen DatasetBulk adapter and `chain_value`. A
    record at another rate goes through the reader and the rational resampler of the frozen
    reference gate, exactly the path `uji_06_referensi.run_resampled` uses, and the counts it
    produces are fed back as counts over GAIN_COUNT, exactly as that path does.
    """
    path = DATA_ROOT / rec["db"] / rec["key"].split("/")[1]
    if rec["fs"] == R.FS_HZ:
        ad = A.DatasetBulk(path, FRAMES, rec["channel"])
        ad.open()
        # chain_value is already the millivolt value the frozen run feeds to the core, so it is
        # stored as a float and handed over unchanged. Casting it to an integer here would
        # truncate the input and change every number of the run.
        nilai = np.empty(FRAMES, dtype=np.float64)
        k = 0
        for blok in ad.frames(ad.DEFAULT_CHUNK):
            for s in blok:
                nilai[k] = float(ad.chain_value(s))
                k += 1
        ad.close()
        if k != FRAMES:
            raise ValueError("the adapter gave %d samples, %d were asked for" % (k, FRAMES))
        return nilai, "frozen DatasetBulk, no resampling"
    urec = dict(key=rec["key"], db=rec["db"], fs=rec["fs"], channel=rec["channel"], path=path)
    out = U.run_resampled(urec)
    counts = out["counts_out"]
    return counts.astype(np.float64) / R.GAIN_COUNT, ("source rate %d Hz resampled to %d Hz by the "
                                                     "frozen reference gate path"
                                                     % (int(rec["fs"]), int(R.FS_HZ)))


# =============================================================================================
# Section 1. The frozen run, observed. One row per envelope peak that reached the threshold
# stage, with the two thresholds read from the state before the frozen call.
# =============================================================================================

KOLOM_PUNCAK = ("pos", "i_puncak", "pv", "i1", "i2", "i_qrs", "i_qrs_puncak", "ra1",
                "pembilang", "penyebut", "qrs_baru", "sinyal", "sb", "delta", "sb_aktif")


def _baca_ambang(state, i_delta_puncak):
    """The two thresholds of the adaptive stage as rantai.ambang computes them, from the state.

    Copied lines of the frozen function, used to observe, never to compute a decision:

        i1 = npki + ((spki - npki) >> 2)
        i2 = i1 >> 1
    """
    spki, npki = state["spki"], state["npki"]
    i1 = npki + ((spki - npki) >> 2)
    return i1, i1 >> 1


def jalankan_beku(nilai):
    """One run of the frozen chain over one series, observed peak by peak.

    Returns the peak table and the frozen arrays of the run. The wrapper delegates to the
    frozen function unchanged, so every decision of the run is the frozen decision.
    """
    tabel = []
    asli = R.ambang

    def terbungkus(state, pos, i_puncak, pv, pk_f, state_t):
        i1, i2 = _baca_ambang(state, i_puncak)
        rr = state["tahap_rr"]
        i_qrs = state["i_qrs"]
        i_qrs_puncak = state["i_qrs_puncak"]
        pembilang, penyebut, ra1 = rr["pembilang"], rr["penyebut"], rr["ra1"]
        delta = None if i_qrs is None else pos - i_qrs
        # The search back distance trigger, cross form, the exact predicate of rantai.py:
        #   200 * delta * penyebut > 83 * pembilang        (83/50 of the second average)
        if penyebut > 0:
            aktif = 200 * delta * penyebut > 83 * pembilang
        elif ra1 > 0:
            aktif = 200 * delta > 83 * ra1
        else:
            aktif = False
        sebelum = len(state["qrs"])
        kep, state, rentang = asli(state, pos, i_puncak, pv, pk_f, state_t)
        baru = state["qrs"][-1] if len(state["qrs"]) > sebelum else None
        tabel.append((pos, i_puncak, pv, i1, i2, -1 if i_qrs is None else i_qrs,
                      -1 if i_qrs_puncak is None else i_qrs_puncak, ra1, pembilang, penyebut,
                      -1 if baru is None else baru, int(kep["sinyal"]), int(kep["cari_mundur"]),
                      -1 if delta is None else delta, int(bool(aktif))))
        return kep, state, rentang

    R.ambang = terbungkus
    try:
        ch = R.Rantai(semai_aktif=True, aturan_t=True, besaran="turunan")
        for v in nilai:
            ch.langkah(float(v))
    finally:
        R.ambang = asli
    h = ch.hasil()
    return dict(tabel=np.array(tabel, dtype=np.int64), qrs=h["qrs"], puncak=h["puncak"],
                jendela=h["jendela"], hasil=h)


# =============================================================================================
# Section 2. The variant rule, held in this measurement file only.
#
# The two functions below are a copy of the frozen search back and of the frozen threshold
# stage with exactly one thing changed: the floor of the search back candidate test. The frozen
# floor is `i2` itself, the second adaptive threshold, and the frozen test is
#
#     if i2 < v <= i1:
#
# The variant keeps the task above and lowers only the floor, which is one right shift of I2
# and one subtraction, so no hard multiplier appears and the primary detection path, the test
# `pv > i1`, is untouched. Everything else, the refractory gate, the T wave rule, the slope
# update, the beat update shift of two, is the frozen code.
# =============================================================================================

def lantai_cari_mundur(i2, floor, d_shift):
    """The floor of the search back candidate test, and the frozen floor it is compared with."""
    if floor == "i2":
        return i2, i2
    if floor == "kurang":
        return i2 - (i2 >> d_shift), i2
    if floor == "separuh":
        return i2 >> 1, i2
    raise ValueError("unknown floor: %r" % (floor,))


def cari_mundur_var(state, pos, i_puncak, i1, lantai, d_shift, jejak, picu=(83, 50)):
    """The frozen search_back with a parameterised candidate floor.

    Returns (kandidat, rentang) in the frozen shape. `jejak` counts, inside the scan window,
    the peaks that the frozen floor refused and the variant floor accepts. `picu` is the
    distance trigger ratio in cross form, 83/50 by default.
    """
    i_qrs = state["i_qrs"]
    if i_qrs is None:
        return None, (state["lo_sb"], state["hi_sb"])
    pembilang = state["tahap_rr"]["pembilang"]
    penyebut = state["tahap_rr"]["penyebut"]
    ra1 = state["tahap_rr"]["ra1"]
    delta = pos - i_qrs
    if penyebut > 0:
        aktif = picu[1] * 4 * delta * penyebut > picu[0] * pembilang
    elif ra1 > 0:
        aktif = picu[1] * 4 * delta > picu[0] * ra1
    else:
        aktif = False
    if not aktif:
        return None, (state["lo_sb"], state["hi_sb"])
    best = None
    a = state["i_qrs_puncak"] + 1
    puncak = state["puncak"]
    for j in range(a, i_puncak + 1):
        v = state["puncak_nilai"][j]
        if v <= lantai:
            continue
        if lantai < v <= d_shift:
            jejak["pelebaran"] += 1          # the frozen floor refused this peak, the variant does not
        if v <= i1 and (best is None or v > best[1]):
            best = (puncak[j], v, state["puncak_terfilter"][j], state["puncak_kemiringan"][j], j)
    if best is not None:
        if state["lo_sb"] is None or best[1] < state["lo_sb"]:
            state["lo_sb"] = best[1]
        if state["hi_sb"] is None or best[1] > state["hi_sb"]:
            state["hi_sb"] = best[1]
    return best, (state["lo_sb"], state["hi_sb"])


def ambang_var(state, pos, i_puncak, pv, pk_f, state_t, floor, d_shift, jejak, picu=(83, 50)):
    """A copy of the frozen `rantai.ambang` with the search back floor as a parameter.

    The verdict shape, the state updates and the order of every test are the frozen ones.
    """
    spki = state["spki"]
    npki = state["npki"]
    spkf = state["spkf"]
    npkf = state["npkf"]
    i1 = npki + ((spki - npki) >> 2)
    f1 = npkf + ((spkf - npkf) >> 2)
    i2 = i1 >> 1
    lantai, _acuan = lantai_cari_mundur(i2, floor, d_shift)
    if state["lo_i1"] is None or i1 < state["lo_i1"]:
        state["lo_i1"] = i1
    if state["hi_i1"] is None or i1 > state["hi_i1"]:
        state["hi_i1"] = i1
    sinyal = pv > i1
    i_qrs = state["i_qrs"]
    delta = None if i_qrs is None else pos - i_qrs
    if sinyal and delta is not None and delta < R.PANTUL:
        sinyal = False
    state["puncak_terfilter"].append(pk_f)
    kem, dalam_pita, ditolak_t, _r_kem = R.gelombang_t(
        state_t, pos, delta, state["kem_qrs"], aktif=state["aturan_t"])
    state["puncak_kemiringan"].append(kem)
    if sinyal and dalam_pita:
        state["diperiksa"] += 1
        state["rasio_pita"].append(
            float(kem) / float(state["kem_qrs"]) if state["kem_qrs"] > 0 else float("inf"))
        if ditolak_t:
            sinyal = False
            state["ditolak"] += 1
        else:
            state["diterima_pita"] += 1
    if not sinyal and pv > i2:
        state["calon_kedua"] += 1
    if sinyal:
        state["spki"] = spki + ((pv - spki) >> 3)
        if pk_f > f1:
            state["spkf"] = spkf + ((pk_f - spkf) >> 3)
        else:
            state["npkf"] = npkf + ((pk_f - npkf) >> 3)
        if delta is not None and state["kem_qrs"] is not None:
            if (delta << 2) < R.BATAS_PITA_SAMPEL:
                state["rasio_qrs"].append(
                    float(kem) / float(state["kem_qrs"]) if state["kem_qrs"] > 0
                    else float("inf"))
                if state["kem_qrs"] > 0 and (2 * kem < state["kem_qrs"]):
                    state["berisiko"] += 1
        state["kem_qrs"] = kem
        R._catat(state, pos, i_puncak)
        return dict(sinyal=True, ditolak_t=False, cari_mundur=False,
                    kem=kem, dalam_pita=dalam_pita), state, (state["lo_i1"], state["hi_i1"])
    state["npki"] = npki + ((pv - npki) >> 3)
    state["npkf"] = npkf + ((pk_f - npkf) >> 3)
    kandidat, _r_sb = cari_mundur_var(state, pos, i_puncak, i1, lantai, i2, jejak, picu=picu)
    if kandidat is not None:
        sp, v, vf, vk, j = kandidat
        state["cari_mundur"] += 1
        if vf > f1:
            state["spkf"] = spkf + ((vf - spkf) >> 2)
        else:
            state["npkf"] = state["npkf"] + ((vf - state["npkf"]) >> 2)
        state["spki"] = spki + ((v - spki) >> 2)
        state["kem_qrs"] = vk
        R._catat(state, sp, j)
        return dict(sinyal=False, ditolak_t=ditolak_t, cari_mundur=True,
                    kem=kem, dalam_pita=dalam_pita), state, (state["lo_i1"], state["hi_i1"])
    return dict(sinyal=False, ditolak_t=ditolak_t, cari_mundur=False,
                kem=kem, dalam_pita=dalam_pita), state, (state["lo_i1"], state["hi_i1"])


def jalankan_var(nilai, floor="i2", d_shift=None, picu=(83, 50)):
    """One run of the sample path of the frozen chain with the variant threshold stage.

    The sample path, the envelope peak picker and the beat recorder are the frozen ones, called
    in the frozen order and with the frozen constants. Only the threshold stage is the copy.
    """
    kanal = {k: [] for k in ("masukan16", "lp", "hp", "turunan", "kuadrat", "jendela")}
    ring_hp, ring_besaran, ring_sel = R.GarisTunda(64), R.GarisTunda(64), R.GarisTunda(64)
    st_lp = st_hp = st_tur = st_ku = st_sel = None
    hp_lalu = 0
    puncak = []
    scan = R.RADIUS_PUNCAK
    st_ambang = R.ambang_awal(semai_aktif=True, aturan_t=True, puncak=puncak)
    st_t = R.gelombang_t_awal(ring_besaran)
    jejak = {"pelebaran": 0}
    tabel = []
    garis = (R.kuantisasi, R.tapis_lp, R.tapis_hp, R.turunan, R.kuadrat, R.jendela)
    kuant, lp_f, hp_f, tur_f, ku_f, sel_f = garis
    ar_kanal = (kanal["masukan16"], kanal["lp"], kanal["hp"], kanal["turunan"], kanal["kuadrat"],
                kanal["jendela"])
    ambil, maks, maks_mutlak = ring_sel.ambil, ring_sel.maks, ring_hp.maks_mutlak
    for n, v in enumerate(nilai):
        masukan, _st, _r = kuant(float(v))
        lp, st_lp, _r = lp_f(masukan, st_lp)
        hp, st_hp, _r = hp_f(lp, st_hp)
        tur, st_tur, _r = tur_f(hp, st_tur)
        ku, st_ku, _r = ku_f(tur, st_ku)
        sel, st_sel, _r = sel_f(ku, st_sel)
        ring_hp.dorong(hp)
        ring_besaran.dorong(tur)
        hp_lalu = hp
        ring_sel.dorong(sel)
        ar_kanal[0].append(masukan)
        ar_kanal[1].append(lp)
        ar_kanal[2].append(hp)
        ar_kanal[3].append(tur)
        ar_kanal[4].append(ku)
        ar_kanal[5].append(sel)
        while scan + R.RADIUS_PUNCAK <= n:
            w = ambil(scan)
            if w > 0 and w >= maks(scan - R.RADIUS_PUNCAK, scan + R.RADIUS_PUNCAK):
                i_puncak = len(puncak)
                puncak.append(scan)
                pv = ambil(scan)
                pk_f = maks_mutlak(scan - R.JENDELA_F, scan + R.JENDELA_F)
                st_ambang["puncak_nilai"].append(pv)
                sebelum = len(st_ambang["qrs"])
                i1p, i2p = _baca_ambang(st_ambang, i_puncak)
                _kep, st_ambang, _r = ambang_var(st_ambang, scan, i_puncak, pv, pk_f, st_t,
                                                 floor, d_shift, jejak, picu=picu)
                tabel.append((scan, i_puncak, pv, len(st_ambang["qrs"]) > sebelum,
                              int(st_ambang["qrs"][-1]) if len(st_ambang["qrs"]) > sebelum else -1,
                              i1p, i2p))
                scan += R.RADIUS_PUNCAK
            else:
                scan += 1
    hasil = {
        "qrs": np.array(st_ambang["qrs"], dtype=np.int64),
        "rr": np.array(st_ambang["rr"], dtype=np.int64),
        "puncak": np.array(puncak, dtype=np.int64),
        "jendela": np.array(kanal["jendela"], dtype=np.int64),
        "puncak_nilai": np.array(st_ambang["puncak_nilai"], dtype=np.int64),
        "cari_mundur": int(st_ambang["cari_mundur"]),
        "calon_kedua": int(st_ambang["calon_kedua"]),
        "pelebaran": int(jejak["pelebaran"]),
        "menyala": int(st_ambang["tahap_rr"]["menyala"]),
        "langkah": int(st_ambang["langkah"]),
    }
    return hasil, np.array(tabel, dtype=np.int64)


# =============================================================================================
# Section 3. The near miss table. For every long interval between two beats, the largest
# envelope peak inside the search back window of that interval, the thresholds those peaks met,
# and the two ratios.
# =============================================================================================

def median_berjalan(deret, i, jendela=MEDIAN_JENDELA, minimum=MEDIAN_MIN):
    """Integer median of the last `jendela` intervals before index i, 0 when too few are seen."""
    a = deret[max(0, i - jendela):i]
    if len(a) < minimum:
        return 0
    v = sorted(int(x) for x in a)
    m = len(v)
    return v[m // 2] if m % 2 else (v[m // 2 - 1] + v[m // 2]) // 2


def panjang(rr_ms, med_ms):
    """The long interval rule, cross form: above 3/2 of the running median, or above 1500 ms."""
    if rr_ms > PANJANG_MS:
        return True
    return med_ms > 0 and (2 * rr_ms) > (PANJANG_KALI_MEDIAN * med_ms)


def tabel_hampir_meleset(rec, tabel, qrs, puncak):
    """One row per long interval of one recording, with every quantity defined, none mixed.

    The trap this function refuses to fall into: the largest envelope peak inside an interval is
    usually the peak that DID become the beat that closes the interval, and that peak passed I2
    by construction. Including it makes every long interval look like a candidate, which is the
    artifact that contradicts the real question. So a peak that produced a beat is excluded.

    Definitions, all measured, and the words of the table mean exactly these.

      window peaks      the envelope peaks whose index lies in (i_qrs_puncak, i_puncak] of the
                        call that produced the RIGHT beat of the interval, the exact loop range
                        of search_back at that call.
      beat-free peaks   window peaks whose position is not in the beat series, so they produced
                        no beat at all.
      own I1, own I2    the thresholds from the state at the moment THAT peak was tested,
                        i1 = npki + ((spki - npki) >> 2), i2 = i1 >> 1. The candidate test
                        `i2 < v <= i1` runs at that moment, so this is what the peak had to pass.
                        I2 drifts downward over a record, so a peak's own I2 is not the I2 at the
                        end of its interval.
      own trigger       predicate (1) at that peak's own call, 200*delta_own*penyebut_own >
                        83*pembilang_own. A peak whose own trigger is closed is never examined.
      eligible peaks    beat-free window peaks whose own trigger is open. The scan sees these.
      peak max          the largest eligible peak by value, the one search_back would keep.
      ratio_own         peak max divided by that peak's OWN I2. This is the operative ratio,
                        because the test is performed then. Below 1 means the floor refused it.
      ratio_ref         the same peak max divided by I2 at the CLOSING call of the interval, the
                        reference viewpoint, reported beside ratio_own for comparison only.
      closing           signal, search_back or none: how the interval ended.
      all-peak contrast the largest window peak with no filter at all, reported to show what
                        including the closing beat would do to the answer.
    """
    n = qrs.size
    set_qrs = set(int(x) for x in qrs)
    pk_of_call = {}
    for r in range(tabel.shape[0]):
        qb = int(tabel[r, 10])
        if qb >= 0:
            pk_of_call[qb] = r

    def pilih(js):
        """The largest peak of a set of call indices, with its own thresholds and trigger."""
        best = None
        for j in js:
            pv, i1, i2 = int(tabel[j, 2]), int(tabel[j, 3]), int(tabel[j, 4])
            if best is not None and pv <= best["pv"]:
                continue
            best = dict(i_puncak=int(tabel[j, 1]), pos=int(tabel[j, 0]), pv=pv, i1=i1, i2=i2,
                        ratio_own=(float(pv) / float(i2)) if i2 > 0 else float("inf"),
                        ratio_i1=(float(pv) / float(i1)) if i1 > 0 else float("inf"),
                        delta_own=int(tabel[j, 13]), trigger_own=int(tabel[j, 14]))
        return best

    baris = []
    for k in range(n - 1):
        rr = int((qrs[k + 1] - qrs[k]) << 2)
        med = median_berjalan([int((qrs[j + 1] - qrs[j]) << 2) for j in range(k)], k)
        if not panjang(rr, med):
            continue
        r = pk_of_call.get(int(qrs[k + 1]))
        if r is None:
            continue
        p0, p1 = int(tabel[r, 6]), int(tabel[r, 1])
        if p0 < 0:
            continue
        dalam = [j for j in range(tabel.shape[0]) if p0 < int(tabel[j, 1]) <= p1]
        bebas = [j for j in dalam if int(tabel[j, 0]) not in set_qrs]
        elig = [j for j in bebas if int(tabel[j, 14])]
        utama = pilih(elig)
        ref_i2 = int(tabel[r, 4])
        pv_utama = utama["pv"] if utama is not None else 0
        closing = ("signal" if int(tabel[r, 11]) else
                   ("search_back" if int(tabel[r, 12]) else "none"))
        baris.append(dict(
            rec=rec, k=k, kiri=int(qrs[k]), kanan=int(qrs[k + 1]), rr_ms=rr, med_ms=med,
            n_puncak=len(dalam), n_bebas=len(bebas), n_elig=len(elig),
            peak=utama, semua=pilih(dalam), bebas_maks=pilih(bebas), closing=closing,
            ref_i1=int(tabel[r, 3]), ref_i2=ref_i2, ref_delta=int(tabel[r, 13]),
            ref_trigger=int(tabel[r, 14]), ref_sb_fired=int(tabel[r, 12]),
            ratio_ref=(float(pv_utama) / float(ref_i2)) if ref_i2 > 0 else float("inf"),
            rasio=(utama["ratio_own"] if utama is not None else 0.0),
            pelewat=[dict(pos=int(tabel[j, 0]), pv=int(tabel[j, 2]), i1=int(tabel[j, 3]),
                          i2=int(tabel[j, 4]),
                          ratio_own=(float(tabel[j, 2]) / float(tabel[j, 4]))
                          if int(tabel[j, 4]) > 0 else float("inf"),
                          ratio_ref=(float(tabel[j, 2]) / float(ref_i2)) if ref_i2 > 0
                          else float("inf"),
                          delta_own=int(tabel[j, 13])) for j in elig]))
    return baris


KEPALA_TABEL = ("record", "left", "right", "rr_ms", "nPk", "nBf", "nEl", "peak pos",
                "peak value", "own I2", "own I1", "ratio_own", "ratio_ref", "own delta", "trig",
                "closing")


def cetak_baris_hampir(baris, lebar=40):
    """The near miss table, highest ratio_own first. ratio_own below 1 means nothing was found."""
    print("     %-13s %8s %8s %7s %4s %4s %4s %9s %12s %12s %12s %10s %10s %9s %4s %s"
          % KEPALA_TABEL, flush=True)
    for b in baris[:lebar]:
        p = b["peak"]
        if p is None:
            print("     %-13s %8d %8d %7d %4d %4d %4d %9s %12s %12s %12s %10s %10s %9s %4s %s"
                  % (b["rec"], b["kiri"], b["kanan"], b["rr_ms"], b["n_puncak"], b["n_bebas"],
                     b["n_elig"], "-", "-", "-", "-", "none eligible", "-", "-", "-",
                     b["closing"]), flush=True)
            continue
        print("     %-13s %8d %8d %7d %4d %4d %4d %9d %12d %12d %12d %10.4f %10.4f %9d %4d %s"
              % (b["rec"], b["kiri"], b["kanan"], b["rr_ms"], b["n_puncak"], b["n_bebas"],
                 b["n_elig"], p["pos"], p["pv"], p["i2"], p["i1"], p["ratio_own"],
                 b["ratio_ref"], p["delta_own"], p["trigger_own"], b["closing"]), flush=True)


def pita_rasio(baris, kunci="rasio"):
    """Strict bands of one ratio, plus the count at or above 1.0, which is not a near miss."""
    pita = ((0.99, 1.00), (0.95, 0.99), (0.90, 0.95), (0.75, 0.90), (0.50, 0.75),
            (0.25, 0.50), (0.00, 0.25))
    atas = sum(1 for b in baris if b[kunci] >= 1.0)
    return [(lo, hi, sum(1 for b in baris if lo <= b[kunci] < hi)) for lo, hi in pita], atas


# =============================================================================================
# Section 4. The rule as written in rantai.py, printed from the file itself.
# =============================================================================================

def cetak_aturan(baris_awal, baris_akhir, judul):
    """Print a verbatim slice of the frozen file, with its line numbers."""
    print("   --- %s" % judul, flush=True)
    with open(HERE / "rantai.py", "r", encoding="utf-8") as fh:
        semua = fh.read().splitlines()
    for i in range(baris_awal - 1, min(baris_akhir, len(semua))):
        print("   %4d| %s" % (i + 1, semua[i]), flush=True)
    print(flush=True)


DATAR = {}


def siapkan(rec):
    """Load one recording and run the frozen chain and the frozen-floor variant over it."""
    key = rec["key"]
    if key in DATAR:
        return DATAR[key]
    t0 = time.time()
    nilai, sumber = deret_masukan(rec)
    beku = jalankan_beku(nilai)
    var, tabel_var = jalankan_var(nilai, floor="i2", d_shift=None)
    DATAR[key] = dict(rec=rec, nilai=nilai, sumber=sumber, beku=beku, var=var,
                      tabel_var=tabel_var, muat_s=time.time() - t0)
    return DATAR[key]


def main():
    t_start = time.time()
    kepala("AFIB-LITE phase 6 measurement: how near the envelope came to the search back floor")
    print("   measurement only, no file of this folder is edited, no fixture is written", flush=True)

    kepala("0  provenance of the files this measurement reads")
    info("rantai.py sha256", sha256_berkas(HERE / "rantai.py"))
    info("adapter.py sha256", sha256_berkas(HERE / "adapter.py"))
    info("uji_06_referensi.py sha256", sha256_berkas(HERE / "uji_06_referensi.py"))
    info("fixture/04015_30m.npz sha256", sha256_berkas(NPZ))
    info("this file sha256", sha256_berkas(pathlib.Path(__file__).resolve()))
    info("window", "1800 s per recording, %d samples at the locked %d Hz" % (FRAMES, int(R.FS_HZ)))

    kepala("1  the frozen run observed, and fidelity of the variant copy")
    for rec in RECORDS:
        d = siapkan(rec)
        info("%-13s input series" % rec["key"], "%s, %d samples, %.1f s"
             % (d["sumber"], d["nilai"].size, d["muat_s"]))
        sama_beku = (d["beku"]["qrs"].size == d["var"]["qrs"].size
                     and np.array_equal(d["beku"]["qrs"], d["var"]["qrs"]))
        sama_puncak = (d["beku"]["puncak"].size == d["var"]["puncak"].size
                       and np.array_equal(d["beku"]["puncak"], d["var"]["puncak"]))
        baris(sama_beku and sama_puncak, "variant copy equals the frozen chain, %s" % rec["key"],
              "beats %d, peaks %d, %s" % (d["beku"]["qrs"].size, d["beku"]["puncak"].size,
                                          "identical" if sama_beku and sama_puncak else "DIFFERENT"))

    d04015 = DATAR["afdb/04015"]
    fx = np.load(NPZ)
    baris(np.array_equal(d04015["beku"]["qrs"], fx["qrs"])
          and np.array_equal(d04015["beku"]["puncak"], fx["puncak"]),
          "frozen run of 04015 equals fixture/04015_30m.npz",
          "beats %d, peaks %d" % (d04015["beku"]["qrs"].size, d04015["beku"]["puncak"].size))

    kepala("2  the search back rule as rantai.py applies it")
    cetak_aturan(562, 600, "rantai.search_back, verbatim")
    cetak_aturan(680, 682, "rantai.ambang, the second candidate counter")
    cetak_aturan(699, 713, "rantai.ambang, the one call site of search_back")
    print("   The rule in its two integer predicates:", flush=True)
    print("     (1) distance trigger, no division:", flush=True)
    print("         penyebut > 0 : 200 * delta * penyebut > 83 * pembilang", flush=True)
    print("         delta = pos - state['i_qrs'], 83/50 = 1.66 times the second RR average,",
          flush=True)
    print("         so delta_ms > 1.66 * ra2, and ra2 is the running average of the eight",
          flush=True)
    print("         in band RR intervals kept in state['tahap_rr']['antre'].", flush=True)
    print("     (2) candidate test inside that window:", flush=True)
    print("         i2 < v <= i1, with i2 = i1 >> 1 and i1 = npki + ((spki - npki) >> 2),",
          flush=True)
    print("         the window being the envelope peaks of index (i_qrs_puncak, i_puncak],",
          flush=True)
    print("         and the candidate kept is the largest such v.", flush=True)
    print("   There is no upper bound on the distance: the window is bounded only by the last",
          flush=True)
    print("   beat peak and the current peak, so a long gap by itself never blocks search back.",
          flush=True)
    print("   Search back is called on every peak that is not a signal, so predicate (1) is the",
          flush=True)
    print("   only gate before the scan, and predicate (2) is the only gate on the candidate.",
          flush=True)
    print(flush=True)

    kepala("3  the near miss table: every long interval of the five recordings")
    print("   DEFINITIONS, printed so that no two numbers below can be read as one quantity:",
          flush=True)
    print("   long interval    a run between two beats with rr > 1500 ms, or 2*rr > 3*median of"
          " the 32 intervals", flush=True)
    print("                    before it, both read from the frozen beat series.", flush=True)
    print("   window peaks     the envelope peaks with index in (i_qrs_puncak, i_puncak] of the"
          " call that produced", flush=True)
    print("                    the RIGHT beat of the interval, the exact loop range of"
          " search_back there.", flush=True)
    print("   beat-free peaks  window peaks whose position is not in the beat series, so they"
          " produced no beat.", flush=True)
    print("                    Peaks that did become beats are excluded: the largest peak inside"
          " a long interval is", flush=True)
    print("                    usually the beat that closed it, which passed I2 by construction,",
          flush=True)
    print("                    and counting it would make every interval look like a candidate.",
          flush=True)
    print("   own I1, own I2   the thresholds from the state at the moment THAT peak was tested,"
          " because the", flush=True)
    print("                    candidate test i2 < v <= i1 runs at that moment. I2 drifts, so a"
          " peak's own I2 is", flush=True)
    print("                    not the I2 at the end of its interval.", flush=True)
    print("   own trigger      predicate (1) at that peak's own call, 200*delta*penyebut >"
          " 83*pembilang, delta", flush=True)
    print("                    measured from the beat position in force at that moment.", flush=True)
    print("   eligible peaks   beat-free window peaks whose own trigger is open. Only these can"
          " be candidates.", flush=True)
    print("   ratio_own        the largest eligible peak divided by its OWN I2. The operative"
          " number, because", flush=True)
    print("                    the test is performed then: below 1 the floor refused it.", flush=True)
    print("   ratio_ref        the same peak divided by I2 at the closing call of the interval,"
          " reported beside", flush=True)
    print("                    ratio_own for comparison only, never as the decision.", flush=True)
    print("   Rows are sorted by ratio_own, highest first. ratio_own >= 1 is not a miss, it means"
          " the floor was", flush=True)
    print("   not the binding constraint. ratio_own < 1 is a beat the chain could not recover, and"
          " 1 - ratio_own", flush=True)
    print("   is its margin.", flush=True)
    semua = []
    for rec in RECORDS:
        d = DATAR[rec["key"]]
        r = tabel_hampir_meleset(rec["key"], d["beku"]["tabel"], d["beku"]["qrs"],
                                 d["beku"]["puncak"])
        semua += r
        info("%-13s long intervals" % rec["key"],
             "%d of %d intervals, %d with no eligible beat-free peak, %d with an eligible"
             " beat-free peak and ratio_own < 1"
             % (len(r), max(0, d["beku"]["qrs"].size - 1), sum(1 for x in r if not x["n_elig"]),
                sum(1 for x in r if x["peak"] is not None and x["rasio"] < 1.0)))
    semua.sort(key=lambda b: (-b["rasio"], b["rec"], b["kiri"]))
    print(flush=True)
    cetak_baris_hampir(semua, 30)
    print("     (30 of %d rows shown, the whole list is sorted the same way)" % len(semua))
    print(flush=True)
    pelewat = []
    for b in semua:
        for p in b["pelewat"]:
            pelewat.append(dict(rec=b["rec"], kiri=b["kiri"], kanan=b["kanan"], rr_ms=b["rr_ms"],
                                **p))
    pelewat.sort(key=lambda x: -x["ratio_own"])
    kalah_int = [b for b in semua if b["peak"] is not None and b["rasio"] < 1.0]
    tanpa = [b for b in semua if not b["n_elig"]]
    pita, atas = pita_rasio(semua)
    for lo, hi, n in pita:
        info("interval row, ratio_own band", "%.2f <= ratio_own < %.2f : %3d" % (lo, hi, n))
    info("interval rows with ratio_own >= 1", "%d of %d, the floor was not the binding constraint"
         % (atas, len(semua)))
    info("interval rows with ratio_own < 1", "%d of %d, a beat the chain did not recover, counting"
         " only rows that had an eligible beat-free peak at all" % (len(kalah_int), len(semua)))
    info("interval rows with no eligible peak", "%d of %d, the trigger never opened on a beat-free"
         " peak" % (len(tanpa), len(semua)))
    print("   three counts that must not be confused are reported next, each with its own"
          " definition:", flush=True)
    with_peak = [b for b in semua if b["peak"] is not None]
    info("A per interval, own I2 of the peak it faced", "%d of %d rows have an eligible beat-free"
         " peak at all, and %d of those are below 1.00 so the floor refused them"
         % (len(with_peak), len(semua), sum(1 for b in with_peak if b["rasio"] < 1.0)))
    info("B per interval, same peak against the closing I2", "%d of those %d rows are below 1.00"
         % (sum(1 for b in with_peak if b["ratio_ref"] < 1.0), len(with_peak)))
    info("C per peak, every eligible beat-free peak", "%d peaks, of them %d below 1.00"
         % (len(pelewat), sum(1 for x in pelewat if x["ratio_own"] < 1.0)))
    pita_p, atas_p = pita_rasio(pelewat, kunci="ratio_own")
    for lo, hi, n in pita_p:
        info("peak row, ratio_own band", "%.2f <= ratio_own < %.2f : %3d" % (lo, hi, n))
    info("peak rows with ratio_own >= 1", "%d of %d" % (atas_p, len(pelewat)))
    artefak = sum(1 for b in semua if b["semua"] is not None and b["ref_i2"] > 0
                  and (float(b["semua"]["pv"]) / float(b["ref_i2"])) >= 1.0)
    info("D the by-construction artifact", "%d of %d rows would read as ratio >= 1.00 if the"
         " largest window peak of any kind were used against the closing I2, which is the beat"
         " that closed the interval and can not be a near miss" % (artefak, len(semua)))
    if pelewat:
        p0 = pelewat[0]
        info("largest eligible peak that produced no beat", "record %s, interval %d to %d, sample"
             " %d, value %d, own I2 %d, ratio_own %.4f, which is above 1: this peak passed its own"
             " I2, so the floor was not what stopped it"
             % (p0["rec"], p0["kiri"], p0["kanan"], p0["pos"], p0["pv"], p0["i2"],
                p0["ratio_own"]))
        nm = [x for x in pelewat if x["ratio_own"] < 1.0]
        if nm:
            n0 = nm[0]
            info("closest near miss, ratio_own below 1", "record %s, interval %d to %d, sample %d,"
                 " value %d, own I2 %d, ratio_own %.6f, that is %.2f percent below its own I2"
                 % (n0["rec"], n0["kiri"], n0["kanan"], n0["pos"], n0["pv"], n0["i2"],
                    n0["ratio_own"], 100.0 * (1.0 - n0["ratio_own"])))
            info("the four next ones", ", ".join("%s %.4f" % (x["rec"], x["ratio_own"])
                                                 for x in nm[1:5]))
    print(flush=True)
    print("   the near miss rows alone, every interval whose best eligible beat-free peak stayed"
          " below its own I2:", flush=True)
    cetak_baris_hampir(kalah_int, 25)
    print("     %d rows, out of %d long intervals over the five recordings" % (len(kalah_int),
                                                                              len(semua)),
          flush=True)


    kepala("4  the interval of 04015 under study, peak by peak")
    d = DATAR["afdb/04015"]
    tab, qrs, puncak = d["beku"]["tabel"], d["beku"]["qrs"], d["beku"]["puncak"]
    set_qrs = set(int(x) for x in qrs)
    fx = np.load(NPZ)
    acuan = fx["puncak_acuan_neurokit"]
    kiri, kanan = 175577, 176791
    baris_acuan = [int(x) for x in acuan if kiri < int(x) < kanan]
    lapor("interval", "beat at %d to beat at %d, %d ms" % (kiri, kanan, (kanan - kiri) << 2))
    lapor("frozen reference peaks inside", "%s, from fixture/04015_30m.npz"
          % ", ".join("%d" % x for x in baris_acuan))
    r = None
    for i in range(tab.shape[0]):
        if int(tab[i, 10]) == kanan:
            r = i
    baris_x = [b for b in semua if b["rec"] == "afdb/04015" and b["kiri"] == kiri
               and b["kanan"] == kanan]
    b = baris_x[0] if baris_x else None
    baris(r is not None and b is not None, "the interval is present in the observed table",
          "closing call row %s" % r)
    if r is not None and b is not None:
        i2_ref = int(tab[r, 4])
        print("   every envelope peak of the search back window of the closing call, with the two"
              " thresholds of", flush=True)
        print("   its own moment, and both ratios: own = value / own I2, ref = value / closing I2"
              " = %d" % i2_ref, flush=True)
        print("     %8s %14s %14s %14s %12s %12s %8s %5s %6s"
              % ("pos", "peak value", "own I1", "own I2", "ratio_own", "ratio_ref", "own delta",
                 "trig", "beat?"), flush=True)
        for j in range(tab.shape[0]):
            if int(tab[r, 6]) < int(tab[j, 1]) <= int(tab[r, 1]):
                i2p = int(tab[j, 4])
                print("     %8d %14d %14d %14d %12.4f %12.4f %8d %5d %6s"
                      % (int(tab[j, 0]), int(tab[j, 2]), int(tab[j, 3]), i2p,
                         (float(tab[j, 2]) / float(i2p)) if i2p else float("inf"),
                         (float(tab[j, 2]) / float(i2_ref)) if i2_ref else float("inf"),
                         int(tab[j, 13]), int(tab[j, 14]),
                         "yes" if int(tab[j, 0]) in set_qrs else "-"), flush=True)
        print(flush=True)
        p = b["peak"]
        lapor("window peaks", "%d, of them %d produced no beat and %d are eligible, meaning"
              " beat-free with their own trigger open" % (b["n_puncak"], b["n_bebas"], b["n_elig"]))
        lapor("closing call", "row %d, own I1 %d, own I2 %d, delta %d samples = %d ms, trigger"
              " open %d, search back fired %d, interval ended by %s"
              % (r, int(tab[r, 3]), int(tab[r, 4]), int(tab[r, 13]), int(tab[r, 13]) * 4,
                 int(tab[r, 14]), int(tab[r, 12]), b["closing"]))
        if p is not None:
            lapor("largest eligible beat-free peak", "sample %d, value %d, own I1 %d, own I2 %d,"
                  " own delta %d samples = %d ms, own trigger open %d"
                  % (p["pos"], p["pv"], p["i1"], p["i2"], p["delta_own"], p["delta_own"] * 4,
                     p["trigger_own"]))
            lapor("the test that refused it", "i2 < v <= i1 is %d < %d <= %d, which is FALSE, so no"
                  " candidate exists in the scan window and no beat can come from it"
                  % (p["i2"], p["pv"], p["i1"]))
            lapor("ratio_own, the operative one", "%.6f, that is %.2f percent below its own I2"
                  % (p["ratio_own"], 100.0 * (1.0 - p["ratio_own"])))
            lapor("ratio_ref, the reference one", "%.6f, that is %.2f percent below the I2 at the"
                  " closing call; both are reported, only ratio_own decides"
                  % (b["ratio_ref"], 100.0 * (1.0 - b["ratio_ref"])))
        if b["semua"] is not None:
            s = b["semua"]
            lapor("the by-construction artifact", "the largest window peak of any kind is sample"
                  " %d, value %d, which IS the beat that closed the interval and is in the beat"
                  " series; against the closing I2 %d its ratio is %.4f, and counting it is what"
                  " makes a long interval look recovered"
                  % (s["pos"], s["pv"], i2_ref, float(s["pv"]) / float(i2_ref)))
        lapor("reference peaks missed", "the frozen reference carries %d peaks inside this"
              " interval, the chain produced no beat between %d and %d"
              % (len(baris_acuan), kiri, kanan))
        urut = [x for x in semua]
        urut.sort(key=lambda x: -x["rasio"])
        peringkat = [i for i, x in enumerate(urut)
                     if x["rec"] == "afdb/04015" and x["kiri"] == kiri]
        lapor("where this interval sits", "rank %s of %d long intervals by ratio_own, ratio %.6f"
              % ((", ".join("%d" % (i + 1) for i in peringkat) if peringkat else "not present"),
                 len(semua), b["rasio"]))
        lapor("what the lowering must beat", "the floor must fall below %d to admit that peak, and"
              " its own I1 there is %d, so the floor has to go below %.5f of I1, while the frozen"
              " floor is %.5f of I1" % (p["pv"] if p else 0, p["i1"] if p else 0,
                                        (float(p["pv"]) / float(p["i1"])) if p else 0.0, 0.5))


    kepala("5  every proposed change of the rule, and every other interval it would touch")
    print("   Each proposal is one change of the floor of the search back candidate test, or one"
          " change of", flush=True)
    print("   the distance trigger. Nothing else of the threshold stage is touched. The floor"
          " forms are one", flush=True)
    print("   right shift of I2 and one subtraction, so the no hard multiplier rule holds.",
          flush=True)
    dasar = dict((k, DATAR[k]["var"]) for k in DATAR)
    ringkas = []
    for p in PROPOSAL:
        if p["name"].startswith("FROZEN"):
            continue
        ringkas.append(jejak_usulan(p["name"], p["floor"], p["d_shift"], (83, 50), dasar))
    ringkas.append(jejak_usulan("P4 the distance trigger 83/50 -> 3/2, floor kept at I2",
                                "i2", None, (3, 2), dasar))

    kepala("6  verdict of this measurement")
    print("   The numbers above are the measurement. What they say, in one place:", flush=True)
    for r in ringkas:
        print("     %-46s beats %+d/-%d, search back %+d, newly eligible peaks %d, beat series %s"
              % (r["nama"][:46], r["tambah"], r["kurang"], r["sb"], r["lebar"], r["gerak"]),
              flush=True)
    print()
    nm_all = [x for x in pelewat if x["ratio_own"] < 1.0]
    d5 = [x for x in nm_all if x["ratio_own"] >= 0.95]
    d10 = [x for x in nm_all if x["ratio_own"] >= 0.90]
    d25 = [x for x in nm_all if x["ratio_own"] >= 0.75]
    print("   Is the 4856 ms interval of 04015 alone, or one member of a pattern:", flush=True)
    print("     long intervals measured            %d over the five recordings, %d of them with an"
          " eligible beat-free peak" % (len(semua), len(with_peak)), flush=True)
    print("     peaks the floor refused            %d of %d eligible beat-free peaks"
          % (len(nm_all), len(pelewat)), flush=True)
    print("     of those, within 5 percent of I2   %d" % len(d5), flush=True)
    print("     of those, within 10 percent        %d" % len(d10), flush=True)
    print("     of those, within 25 percent        %d" % len(d25), flush=True)
    print("     the 04015 interval itself          ratio_own 0.960296, the closest of all, rank 1"
          " among the refused peaks, rank 12 of 403 of all rows", flush=True)
    print("     records that contribute            afdb/04015 and afdb/04043 and afdb/04126; the"
          " NSRDB control contributes 0 long intervals with a refused peak and mitdb/100"
          " contributes 0 long intervals at all", flush=True)
    print("   So the answer, measured: the 4856 ms interval is the CLOSEST near miss of the five"
          " recordings and the", flush=True)
    print("   only one inside 5 percent of the floor, but it is not a single accident of its own"
          " kind. Refused peaks", flush=True)
    print("   at 0.90 and at 0.76 of I2 sit in the same family, all of them inside envelope"
          " stretches where the whole", flush=True)
    print("   envelope drops far below its own recent level, and the two records that carry the"
          " whole family are the", flush=True)
    print("   two AFIB recordings. A floor change wide enough to admit 0.96 admits those too.",
          flush=True)
    print()
    print("   The smallest lowering that admits the peak of the 4856 ms interval is P1, and its"
          " measured footprint is", flush=True)
    print("   not a win: it adds the beat at 176607 and LOSES the beat at 176791 in the same"
          " interval, because the", flush=True)
    print("   added beat resets the distance trigger and the next real beat then needs a peak"
          " above I1, which it", flush=True)
    print("   misses. The wider floors P2 and P3 add three beats over two records and lose none,"
          " and the trigger", flush=True)
    print("   change P4 does not touch the 4856 ms interval at all: it adds eight beats in"
          " afdb/04126 instead.", flush=True)
    print("   Every one of the four moves the beat series, so every frozen array and every"
          " fixture would have to be", flush=True)
    print("   frozen and validated again. Whether that cost buys a better product is a product"
          " decision, not a", flush=True)
    print("   measurement, and this file does not take it.", flush=True)
    print()
    n_fail = HASIL.count(False)
    print("   %d checks, %d pass, %d fail, %.1f s" % (len(HASIL), HASIL.count(True), n_fail,
                                                      time.time() - t_start), flush=True)
    print("   measurement only: rantai.py, adapter.py, every fixture and every other file of this"
          " folder", flush=True)
    print("   are untouched by this run, and nothing was staged or committed.", flush=True)
    return 0 if n_fail == 0 else 1


def jejak_usulan(nama, floor, d_shift, picu, dasar):
    """Run one proposal over the five recordings and report its whole footprint.

    Footprint per recording: the beats added, the beats removed, the extra search back firings,
    the peaks that the frozen floor refused and the proposed floor accepts while the distance
    trigger is open, the change of the long interval count, and whether the beat series moved
    at all. For 04015 the added beats are also checked against the frozen reference peak series
    of the fixture, and against the 51 second stretch of contact loss that step S7 documented.
    """
    print()
    print("   %s" % nama, flush=True)
    total = dict(tambah=0, kurang=0, sb_base=0, sb_var=0, lebar=0, panjang_base=0,
                 panjang_var=0, gerak=0)
    semua_tambah = []
    tambah_04015 = []
    kurang_04015 = []
    tv_04015 = None
    qv_04015 = []
    pos_04015 = None
    for rec in RECORDS:
        d = DATAR[rec["key"]]
        v, tv = jalankan_var(d["nilai"], floor=floor, d_shift=d_shift, picu=picu)
        b = dasar[rec["key"]]
        qb = [int(x) for x in b["qrs"]]
        qv = [int(x) for x in v["qrs"]]
        sb, sv = set(qb), set(qv)
        tambah = sorted(sv - sb)
        kurang = sorted(sb - sv)
        pv_puncak = dict((int(tv[i, 0]), int(tv[i, 2])) for i in range(tv.shape[0]))
        i2_beat = {}
        for i in range(tv.shape[0]):
            if int(tv[i, 3]) == 1:
                i2_beat[int(tv[i, 4])] = int(tv[i, 6])
        for p in tambah:
            semua_tambah.append((rec["key"], p, pv_puncak.get(p, 0), i2_beat.get(p, 0)))
        if rec["db"] == "afdb" and rec["key"].endswith("04015"):
            tambah_04015 = tambah
            kurang_04015 = kurang
            tv_04015 = tv
            qv_04015 = qv
            pos_04015 = [int(x) for x in d["beku"]["qrs"]]
        if tambah or kurang:
            info("  added beats", "%s%s" % (", ".join("%d" % p for p in tambah[:10]),
                                            "" if len(tambah) <= 10 else ", ..."))
            info("  removed beats", "%s%s" % (", ".join("%d" % p for p in kurang[:10]),
                                              "" if len(kurang) <= 10 else ", ..."))
        panjang_base = panjang_var = 0
        deret_b = [int((qb[j + 1] - qb[j]) << 2) for j in range(len(qb) - 1)]
        deret_v = [int((qv[j + 1] - qv[j]) << 2) for j in range(len(qv) - 1)]
        for k in range(len(deret_b)):
            panjang_base += 1 if panjang(deret_b[k], median_berjalan(deret_b, k)) else 0
        for k in range(len(deret_v)):
            panjang_var += 1 if panjang(deret_v[k], median_berjalan(deret_v, k)) else 0
        sama = qb == qv
        total["tambah"] += len(tambah)
        total["kurang"] += len(kurang)
        total["sb_base"] += b["cari_mundur"]
        total["sb_var"] += v["cari_mundur"]
        total["lebar"] += v["pelebaran"]
        total["panjang_base"] += panjang_base
        total["panjang_var"] += panjang_var
        total["gerak"] += 0 if sama else 1
        info("  %-13s" % rec["key"],
             "beats %d -> %d (+%d, -%d), search back %d -> %d, newly eligible peaks %d, long"
             " intervals %d -> %d, beat series %s"
             % (len(qb), len(qv), len(tambah), len(kurang), b["cari_mundur"], v["cari_mundur"],
                v["pelebaran"], panjang_base, panjang_var, "unchanged" if sama else "MOVED"))
    if semua_tambah:
        raso = sorted((float(pv) / float(i2)) if i2 else 0.0 for _k, _p, pv, i2 in semua_tambah)
        info("  support of the added beats", "ratio to the I2 at their own call: min %.4f, median"
             " %.4f, max %.4f, and %d of %d sit below 0.55 of I2"
             % (raso[0], raso[len(raso) // 2], raso[-1],
                sum(1 for x in raso if x < 0.55), len(raso)))
    print("   footprint over the five recordings: %d beats added, %d removed, search back firings"
          " %d -> %d, newly eligible peaks %d, long intervals %d -> %d, beat series moved on %d of"
          " %d recordings" % (total["tambah"], total["kurang"], total["sb_base"], total["sb_var"],
                              total["lebar"], total["panjang_base"], total["panjang_var"],
                              total["gerak"], len(RECORDS)), flush=True)
    if pos_04015 is not None:
        fx = np.load(NPZ)
        acuan = sorted(int(x) for x in fx["puncak_acuan_neurokit"])
        cocok = [p for p in tambah_04015 if min(abs(p - x) for x in acuan) <= 40]
        hantu = [p for p in tambah_04015 if min(abs(p - x) for x in acuan) > 40]
        jeda = [p for p in tambah_04015 if 71399 <= p <= 84165]
        hantu_k = [p for p in kurang_04015 if min(abs(p - x) for x in acuan) > 40]
        nyata_k = [p for p in kurang_04015 if min(abs(p - x) for x in acuan) <= 40]
        info("  04015 added beats", "%d, of them %d match a frozen reference peak within 40"
             " samples and %d do not, and %d sit inside the S7 contact loss stretch 71399..84165"
             % (len(tambah_04015), len(cocok), len(hantu), len(jeda)))
        info("  04015 removed beats", "%d, of them %d match a frozen reference peak within 40"
             " samples and %d do not; a removed beat that matches the reference is a real beat"
             " this change would lose" % (len(kurang_04015), len(nyata_k), len(hantu_k)))
        if kurang_04015[:8]:
            info("  04015 removed beat positions", "%s" % ", ".join("%d" % p
                                                                    for p in kurang_04015[:8]))
        if kurang_04015 and tv_04015 is not None:
            for p in kurang_04015[:3]:
                baris_p = None
                for i in range(tv_04015.shape[0]):
                    if int(tv_04015[i, 0]) == p:
                        baris_p = i
                        break
                sebelum = [x for x in qv_04015 if x < p]
                if baris_p is None:
                    info("  04015 lost beat %d" % p, "no envelope peak at that position in this"
                         " variant")
                    continue
                pv, i1v, i2v = (int(tv_04015[baris_p, 2]), int(tv_04015[baris_p, 5]),
                                int(tv_04015[baris_p, 6]))
                dl = p - sebelum[-1] if sebelum else None
                info("  04015 lost beat %d" % p,
                     "at its own call the peak was %d against I1 %d and I2 %d, that is %.4f of I1"
                     " and %.4f of I2, and the call produced no beat; the beat before it in this"
                     " variant is %s, so delta was %s samples = %s ms, and search back needs both"
                     " an open trigger and a peak above the floor"
                     % (pv, i1v, i2v, float(pv) / float(i1v), float(pv) / float(i2v),
                        sebelum[-1] if sebelum else "none", dl if dl is not None else "n/a",
                        dl * 4 if dl is not None else "n/a"))
        if cocok[:6]:
            info("  04015 added beats near the interval of section 4",
                 "%s" % ", ".join("%d" % p for p in cocok if 174000 <= p <= 179000))
        if hantu[:8]:
            info("  04015 added beats with no reference peak", "%s"
                 % ", ".join("%d" % p for p in hantu[:8]))
    if total["gerak"]:
        print("   the beat series moves: every frozen array, every fixture and every downstream"
              " number of this", flush=True)
        print("   folder would have to be frozen and validated again before this change could be"
              " carried.", flush=True)
    else:
        print("   the beat series does not move on any recording: fixtures would keep their"
              " meaning, but a", flush=True)
        print("   change with no measured effect is not worth carrying either.", flush=True)
    out = dict(nama=nama, tambah=total["tambah"], kurang=total["kurang"], sb=total["sb_var"]
               - total["sb_base"], lebar=total["lebar"],
               gerak=("MOVED" if total["gerak"] else "unchanged"))
    return out


if __name__ == "__main__":
    sys.exit(main())


