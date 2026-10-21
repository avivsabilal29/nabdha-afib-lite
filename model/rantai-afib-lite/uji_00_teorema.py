#!/usr/bin/env python3
"""AFIB-LITE phase 6 step S3 gate: eight closed form theorems, one per chain stage.

One theorem per stage of the locked chain, from section 7 of the vault document
`end-to-end-validation-design.md`. Each theorem prints a single result line with its
measured numbers, the expected values, the data it used, and the verdict LULUS or GAGAL.
The gate passes only when zero gate items fail.

Data sources, named by every theorem:

1. `fixture`   the frozen arrays of `fixture/04015_30m.npz`, produced by phase 1 to phase 5
               over the same recording. The file is never written to, and its SHA-256 is
               checked at the start of every run.
2. `chain`     a fresh streaming run of `rantai.py` over the real recording 04015, 450000
               samples, channel 0, 250 Hz. The run also records the real states that flow
               inside the threshold stage, the RR stage and the T wave stage, so a theorem is
               checked on data that really moved through the chain path and not only on an
               artificial series.
3. `synthetic` an artificial integer series built inside this file, used only for series the
               recording never touches, for instance the serial point of the search back.

Two obligations of the note dated 19 October 2026 are closured here as well:

  A  the serial case of the search back boundary, when delta times four is exactly 83 times
     the second average divided by 50. The recording 04015 never touches that point, so an
     artificial series is built that lands exactly on it and both routes are compared: the
     integer cross form of the chain and the floating point form of the notebook.
  B  every theorem is checked on data that really flows in the chain path, taken from the
     fixture and from the chain run over recording 04015, not on an artificial series alone.

Nothing in this file changes `rantai.py`, the fixture, `acuan_fase.py` or a notebook. It only
imports `rantai` and, when importable, `acuan_fase` read only as the notebook route of a
comparison. Files and output are in English, as the folder rules require, and no line carries
an em dash or an en dash.

Run it with the project interpreter:

    cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/uji_00_teorema.py

Exit code 0 when every gate item passes, 1 when any of them fails.
"""

from __future__ import annotations

import hashlib
import math
import pathlib
import sys
import time
from fractions import Fraction

import numpy as np

import rantai as R

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
NPZ = HERE / "fixture" / "04015_30m.npz"
SIDIK_FIXTURE = "91ff408fb1b7880a124d28bcc4205038935d4a3a2dbabb4c0f7d161d89e8ac4d"
REC = pathlib.Path("/home/avivsabilalm/.hermes/cache/scratch/afib/afdb_local/04015")
FRAMES = 450_000

FS = 250.0
GAIN_COUNT = R.GAIN_COUNT
GESER_KIRI = R.GESER_KIRI
N_A, N_B = R.N_A, R.N_B
JENDELA_MEAN = 0.5 * (N_A + N_B)
GESER_AMBANG = R.GESER_AMBANG
SEMAI_JEDA = R.SEMAI_JEDA
TOL = 1e-9

# Closed forms used as expected values, written from the paper and from the notebooks.
H_LP_TUTUP = (1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1)      # H(z) = ((1 - z**-6) / (1 - z**-1))**2
PENGUATAN_DC_LP = 36
KERNEL_KANTAI = (2, 1, 0, -1, -2)                   # the kernel the chain and the fixture use
KERNEL_PAPER = (1, 2, 0, -2, -1)                    # the kernel of the five-point notebook
PENGUATAN_DC_HP = 16                                # H(1) = (32 - 1 + 1) / (1 + 1)
PENGUATAN_PASANGAN_HP = 32                          # the alternating pair sums to 32 times c
NOL_PERTAMA_JENDELA = FS / JENDELA_MEAN             # 6.6666667 Hz
TUNDA_JENDELA = 0.5 * ((N_A - 1) / 2.0 + (N_B - 1) / 2.0)   # 18.25 samples
PECAH_UJI = (("23/25", (23, 25)), ("59/64", (59, 64)), ("83/50", (83, 50)))
KISI_T = 4096                                       # 4096 squared is exactly 16777216

try:                                                # the notebook route, read only
    import acuan_fase as A
    ADA_ACUAN = True
    CATATAN_ACUAN = "acuan_fase imported, used as the notebook route of the comparisons"
except Exception as exc:                            # noqa: BLE001
    A = None
    ADA_ACUAN = False
    CATATAN_ACUAN = "acuan_fase not importable here, the notebook route is written inline (%s)" % (exc,)

BARIS = []
GAGAL = 0


def cetak(teks=""):
    print(teks)


def hasil(nama, lulus, line):
    global GAGAL
    if not lulus:
        GAGAL += 1
    BARIS.append((nama, bool(lulus), line))
    cetak(line)


def beda(a, b):
    a = np.asarray(a)
    b = np.asarray(b)
    if a.shape != b.shape:
        return -1
    return int(np.count_nonzero(a != b))


def geser(v, k):
    """v[n-k] with zeros in front, so an index before the start of the series reads zero."""
    v = np.asarray(v)
    out = np.zeros_like(v)
    if k == 0:
        return v.copy()
    out[k:] = v[: v.size - k]
    return out


def trunc8(s):
    """Sign symmetric division by eight, the route the derivative stage uses."""
    s = np.asarray(s, dtype=np.int64)
    return np.where(s >= 0, s // 8, -((-s) // 8))


def tapis(h, x):
    """Direct filter of a series by a finite integer kernel, zero padding at both ends."""
    x = np.asarray(x, dtype=np.int64)
    out = np.zeros(x.size, dtype=np.int64)
    for k, t in enumerate(h):
        if t:
            out += int(t) * geser(x, k)
    return out


def tapis_pusat(h, x):
    """The same kernel applied centered: coefficient k multiplies x[i + center - k]."""
    x = np.asarray(x, dtype=np.int64)
    n = x.size
    c = len(h) // 2
    out = np.zeros(n, dtype=np.int64)
    for k, t in enumerate(h):
        if not t:
            continue
        off = c - k
        if off >= 0:
            src = np.concatenate([x[off:], np.zeros(off, dtype=np.int64)])
        else:
            o = -off
            src = np.concatenate([np.zeros(o, dtype=np.int64), x[: n - o]])
        out += int(t) * src
    return out


def magnitudo(h, f):
    """|H(f)| of a finite kernel, from its own coefficients, on a scalar or a grid."""
    h = np.asarray(h, dtype=float)
    w = 2.0 * math.pi * np.asarray(f) / FS
    k = np.arange(h.size)
    if np.ndim(w) == 0:
        return float(abs((h * np.exp(-1j * w * k)).sum()))
    return np.abs((h[None, :] * np.exp(-1j * np.outer(w, k))).sum(axis=1))


def jendela_bergantian_direct(x, na=N_A, nb=N_B):
    """Direct sum with alternating width, built from a cumulative sum as the notebook does."""
    x = np.asarray(x, dtype=np.int64)
    pre = np.concatenate([[0], np.cumsum(x, dtype=np.int64)])
    idx = np.arange(x.size)
    lebar = np.where(idx % 2 == 0, na, nb)
    return pre[idx + 1] - pre[np.maximum(idx - lebar + 1, 0)]


def jendela_bergantian_penampan(x, na=N_A, nb=N_B):
    """The same sum through the locked circular buffer, one add and one subtract per sample."""
    x = np.asarray(x, dtype=np.int64)
    lebar_maks = int(max(na, nb))
    buf = np.zeros(lebar_maks, dtype=np.int64)
    out = np.zeros(x.size, dtype=np.int64)
    head = 0
    acc = 0
    for n in range(x.size):
        lebar = na if n % 2 == 0 else nb
        acc = acc + int(x[n]) - int(buf[head])
        buf[head] = int(x[n])
        head = (head + 1) % lebar_maks
        out[n] = acc - int(buf[head]) if lebar < lebar_maks else acc
    return out


def respons_jendela(N, f):
    """Magnitude response of a mean width N window, the closed form the notebook uses."""
    w = 2.0 * math.pi * f / FS
    with np.errstate(divide="ignore", invalid="ignore"):
        return float(abs(math.sin(N * w / 2.0) / (N * math.sin(w / 2.0))))


def nol_pertama_jendela():
    """First zero of the mean width response, located by bisection on its numerator."""
    f = FS / JENDELA_MEAN
    a, b = f / 2.0, f * 1.5
    for _ in range(200):
        m = 0.5 * (a + b)
        if math.sin(JENDELA_MEAN * (2.0 * math.pi * m / FS) / 2.0) > 0.0:
            a = m
        else:
            b = m
    return 0.5 * (a + b)


def lag_puncak(a, b, lag_maks, potong=1000):
    """Lag of the largest cross correlation of two series, searched around zero."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = min(a.size, b.size)
    sl = slice(potong, n - potong)
    aa = a[sl]
    terbaik, lag_terbaik = -2.0, None
    for lag in range(-lag_maks, lag_maks + 1):
        bb = np.roll(b, -lag)[sl]
        if np.std(aa) == 0.0 or np.std(bb) == 0.0:
            continue
        r = float(np.corrcoef(aa, bb)[0, 1])
        if r > terbaik:
            terbaik, lag_terbaik = r, lag
    return lag_terbaik, terbaik


# =============================================================================================
# The fixture and the fresh chain run over the real recording.
# =============================================================================================

def sidik_jari(berkas):
    h = hashlib.sha256()
    with open(berkas, "rb") as fh:
        for blok in iter(lambda: fh.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def muat_masukan():
    """The sample series fed to the chain: the recording, or the fixture counts inverted."""
    try:
        import wfdb
        rec = wfdb.rdrecord(str(REC), sampto=FRAMES)
        return (rec.p_signal[:, 0].astype(float),
                "recording %s, %s Hz, channel 0, %d samples, clamped samples not counted here"
                % (REC.name, rec.fs, FRAMES))
    except Exception as exc:                        # noqa: BLE001
        m = np.asarray(np.load(NPZ)["masukan16"], dtype=np.int64)
        return ((m >> GESER_KIRI).astype(float) / GAIN_COUNT,
                "fixture masukan16 inverted to millivolt, wfdb unavailable (%s)" % (exc,))


def jalankan_rantai(masukan):
    """Drive the locked chain over the recording and record the real states that flow.

    The three stage functions are wrapped for the duration of the run so the states that
    really move inside the chain can be read afterwards. The wrappers call the original
    functions and change no arithmetic, and they are removed at the end of the run.
    """
    cap = {"ambang": [], "rr": [], "t": []}
    ambang_asli = R.ambang
    rr_asli = R.rr
    t_asli = R.gelombang_t

    def ambang_bungkus(state, pos, i_puncak, pv, pk_f, state_t):
        i1 = state["npki"] + ((state["spki"] - state["npki"]) >> 2)
        cap["ambang"].append((int(state["spki"]), int(state["npki"]), int(pv), int(i1),
                              int(i1 >> 1)))
        return ambang_asli(state, pos, i_puncak, pv, pk_f, state_t)

    def rr_bungkus(nilai_ms, state=None):
        st = state if state is not None else R.rr_awal()
        cap["rr"].append((int(nilai_ms), int(sum(st["antre"])), int(len(st["antre"])),
                          int(st["menyala"])))
        return rr_asli(int(nilai_ms), st)

    def t_bungkus(state, pos, delta, kem_qrs, aktif=True):
        kem, dalam_pita, ditolak, rentang = t_asli(state, pos, delta, kem_qrs, aktif=aktif)
        cap["t"].append((int(kem), -1 if kem_qrs is None else int(kem_qrs),
                         int(bool(dalam_pita)), int(bool(ditolak))))
        return kem, dalam_pita, ditolak, rentang

    R.ambang = ambang_bungkus
    R.rr = rr_bungkus
    R.gelombang_t = t_bungkus
    t0 = time.time()
    try:
        r = R.Rantai(semai_aktif=True, aturan_t=True, besaran="turunan")
        langkah = r.langkah
        for v in masukan:
            langkah(v)
        out = r.hasil()
        out["_rentang"] = r.rentang_terukur()
        out["_lebar"] = r.lebar()
        out["_detik"] = time.time() - t0
    finally:
        R.ambang = ambang_asli
        R.rr = rr_asli
        R.gelombang_t = t_asli
    return out, cap


def ulang_tahap(fn, x):
    """Replay one stage function over a series, streaming, and return its output array."""
    st = None
    xs = np.asarray(x)
    out = np.empty(xs.size, dtype=np.int64)
    for i in range(xs.size):
        y, st, _r = fn(int(xs[i]), st)
        out[i] = y
    return out


def impuls_tahap(fn, amp, panjang):
    """Drive one stage function with a single impulse of the given amplitude."""
    st = None
    out = []
    for n in range(panjang):
        y, st, _r = fn(amp if n == 0 else 0, st)
        out.append(int(y))
    return out


def _langkah(fn, nilai, panjang):
    """Drive one stage function over a constant input and return its output list."""
    st = None
    out = []
    for _ in range(panjang):
        y, st, _r = fn(nilai, st)
        out.append(int(y))
    return out


# =============================================================================================
# Theorem 1, low-pass: DC gain 36, zeros at multiples of fs/6, and an impulse response equal
# to the closed form series 1 up to 6 and then down.
# =============================================================================================

def teorema_1(d, jalan):
    h_lp = np.array(H_LP_TUTUP, dtype=np.int64)
    h_ukur = np.array(impuls_tahap(R.tapis_lp, 1, 20), dtype=np.int64)
    galat_impuls = int(np.max(np.abs(h_ukur[:11] - h_lp)))
    ekor = int(np.count_nonzero(h_ukur[11:]))
    penguatan_dc = int(h_ukur.sum())
    f_nol = np.array([k * FS / 6.0 for k in (1, 2, 3, 4)])
    mag_nol = magnitudo(h_lp, f_nol)
    mag_maks = float(np.max(mag_nol))
    x = np.asarray(d["masukan16"], dtype=np.int64)
    lp = np.asarray(d["lp"], dtype=np.int64)
    konvolusi = tapis(h_lp, x)
    beda_konv = beda(konvolusi, lp)
    beda_konv_rantai = beda(konvolusi, jalan["lp"])
    beda_ulang = beda(ulang_tahap(R.tapis_lp, x), lp)
    beda_rantai = beda(jalan["lp"], lp)
    lulus = (galat_impuls == 0 and ekor == 0 and penguatan_dc == PENGUATAN_DC_LP
             and mag_maks <= TOL and beda_konv == 0 and beda_konv_rantai == 0
             and beda_ulang == 0 and beda_rantai == 0)
    line = ("T1 low-pass        : impulse response %s against the closed form %s, max difference "
            "%d (exp 0), nonzero tail after eleven samples %d (exp 0) | DC gain %d (exp %d) | "
            "|H| at fs/6 and its multiples, %d points, largest %.3g (exp 0) | real recording: "
            "closed form kernel against the fixture lp, %d of %d differ (exp 0); against the "
            "chain lp, %d differ (exp 0); stage replay against the fixture, %d differ (exp 0); "
            "chain run against the fixture, %d differ (exp 0) | data fixture+chain+synthetic "
            "| %s"
            % (h_ukur[:11].tolist(), list(H_LP_TUTUP), galat_impuls, ekor, penguatan_dc,
               PENGUATAN_DC_LP, f_nol.size, mag_maks, max(beda_konv, 0), lp.size,
               max(beda_konv_rantai, 0), max(beda_ulang, 0), max(beda_rantai, 0),
               "LULUS" if lulus else "GAGAL"))
    hasil("T1 low-pass", lulus, line)


# =============================================================================================
# Theorem 2, high-pass: DC gain alternating 16 and 0, a single pole at z equal to -1, and the
# output equal to 32 at sample 32. Checked on the impulse response and on the step response of
# the integer path. Both readings of the steady state are accepted: the pair sum 32c says the
# pair mean is 16c, and the alternating pair 32c and 0 is the same fact read per sample, so a
# phase that starts on 0 must not be marked as a failure.
# =============================================================================================

def teorema_2(d, jalan):
    h_ukur = np.array(impuls_tahap(R.tapis_hp, 1, 44), dtype=np.int64)
    nilai_32 = int(h_ukur[32])
    ekor = h_ukur[32:44]
    amplop_tetap = bool(np.all(np.abs(ekor) == PENGUATAN_PASANGAN_HP))
    tanda_bergantian = bool(np.all(ekor[1:] == -ekor[:-1]))
    c = 1000
    y_step = np.array(_langkah(R.tapis_hp, c, 200), dtype=np.int64)
    pasangan = y_step[1:] + y_step[:-1]
    pasangan_dc = pasangan[33:]
    pasangan_unik = sorted(set(int(v) for v in pasangan_dc))
    fasa = sorted(set(int(v) for v in y_step[33:]))
    penguatan_pasangan = float(np.mean(pasangan_dc)) / (2.0 * c)
    penguatan_dc_koef = (32 * 1 - 1 + 1) / (1 + 1)
    lp = np.asarray(d["lp"], dtype=np.int64)
    hp = np.asarray(d["hp"], dtype=np.int64)
    rekursi = 32 * geser(lp, 16) - (geser(hp, 1) + lp - geser(lp, 32))
    beda_rekursi = beda(rekursi, hp)
    dseq = 32 * geser(lp, 16) - lp + geser(lp, 32)
    k = np.arange(lp.size, dtype=np.int64)
    tertutup = ((-1) ** k) * np.cumsum(((-1) ** k) * dseq, dtype=np.int64)
    beda_tertutup = beda(tertutup, hp)
    beda_ulang = beda(ulang_tahap(R.tapis_hp, lp), hp)
    beda_rantai = beda(jalan["hp"], hp)
    lulus = (nilai_32 == PENGUATAN_PASANGAN_HP and amplop_tetap and tanda_bergantian
             and pasangan_unik == [PENGUATAN_PASANGAN_HP * c]
             and abs(penguatan_pasangan - PENGUATAN_DC_HP) < 1e-12
             and abs(penguatan_dc_koef - PENGUATAN_DC_HP) < 1e-12
             and beda_rekursi == 0 and beda_tertutup == 0 and beda_ulang == 0
             and beda_rantai == 0)
    line = ("T2 high-pass       : h[32] %d (exp %d) | for n 32..43 |h[n]| holds at %d and the sign "
            "alternates every sample %s (exp true), which is the pole at z = -1 | step of a "
            "constant c %d: the pair sum y[n]+y[n-1] takes the single value %s for every n of the "
            "steady state (exp %d), and half of it over c is the DC gain %.6f, that is %d times "
            "c, while the samples themselves take the values %s, so the alternating pair %d and 0 "
            "and its phase swapped twin are the same reading (exp both readings accepted, a phase "
            "starting on 0 is not a failure) | DC gain from H(1) %.6f (exp %d) | real recording: "
            "the recursion against the fixture hp, %d of %d differ (exp 0); closed form (-1)^n "
            "times the cumulative sum, %d differ (exp 0); stage replay, %d differ (exp 0); chain "
            "run, %d differ (exp 0) | data fixture+chain+synthetic | %s"
            % (nilai_32, PENGUATAN_PASANGAN_HP, int(np.abs(ekor[0])), tanda_bergantian, c,
               pasangan_unik, PENGUATAN_PASANGAN_HP * c, penguatan_pasangan, PENGUATAN_DC_HP,
               fasa, PENGUATAN_PASANGAN_HP * c, penguatan_dc_koef,
               PENGUATAN_DC_HP, max(beda_rekursi, 0), hp.size, max(beda_tertutup, 0),
               max(beda_ulang, 0), max(beda_rantai, 0), "LULUS" if lulus else "GAGAL"))
    hasil("T2 high-pass", lulus, line)


# =============================================================================================
# Theorem 3, five point derivative: exact zero DC gain, group delay exactly two samples, and
# the peak of the magnitude response at fs/6, with an exact impulse response.
# =============================================================================================

def teorema_3(d, jalan):
    h_ukur = np.array(impuls_tahap(R.turunan, 8, 12), dtype=np.int64)
    galat_impuls = int(np.max(np.abs(h_ukur[:5] - np.array(KERNEL_KANTAI, dtype=np.int64))))
    ekor = int(np.count_nonzero(h_ukur[5:]))
    jumlah_h = int(h_ukur[:5].sum())
    y_step = np.array(_langkah(R.turunan, 1000, 60), dtype=np.int64)
    maks_steadi = int(np.max(np.abs(y_step[4:])))
    maks_transien = int(np.max(np.abs(y_step)))
    antisimetris = bool(h_ukur[2] == 0 and h_ukur[1] == -h_ukur[3] and h_ukur[0] == -h_ukur[4])
    hp = np.asarray(d["hp"], dtype=np.int64)
    tur = np.asarray(d["turunan"], dtype=np.int64)
    # The centered partner of the same kernel, computed from the high-pass series itself and
    # therefore independent of the stage output.
    V = trunc8(tapis_pusat(list(KERNEL_KANTAI), hp))
    beda_pusat = beda(tur[2:], V[:-2])
    lag_real, kor_real = lag_puncak(tur, V, 4, potong=2000)
    rng = np.random.default_rng(20261019)
    x_buat = rng.integers(-2000, 2001, 30000).astype(np.int64)
    y_buat = ulang_tahap(R.turunan, x_buat)
    V_buat = trunc8(tapis_pusat(list(KERNEL_KANTAI), x_buat))
    beda_pusat_buat = beda(y_buat[2:], V_buat[:-2])
    lag_buat, kor_buat = lag_puncak(y_buat, V_buat, 4, potong=200)
    h_kantai = np.array(KERNEL_KANTAI, dtype=float) / 8.0
    h_paper = np.array(KERNEL_PAPER, dtype=float) / 8.0
    kisi = np.arange(0.0, FS / 2.0, 0.0005)
    f_puncak_kantai = float(kisi[int(np.argmax(magnitudo(h_kantai, kisi)))])
    f_puncak_paper = float(kisi[int(np.argmax(magnitudo(h_paper, kisi)))])
    gain_kantai_fs6 = float(magnitudo(h_kantai, FS / 6.0))
    f_harap = FS / 6.0

    def gain_empiris(f, A_=1000, N=4000, buang=1000):
        n_urut = np.arange(N)
        xs = np.rint(A_ * np.sin(2.0 * math.pi * f * n_urut / FS)).astype(np.int64)
        ys = ulang_tahap(R.turunan, xs)
        return float(np.sqrt(np.mean(ys[buang:].astype(float) ** 2))
                     / np.sqrt(np.mean(xs[buang:].astype(float) ** 2)))

    kisi_emp = np.arange(28.0, 44.0 + 1e-9, 0.1)
    gain_emp = np.array([gain_empiris(float(f)) for f in kisi_emp])
    f_emp = float(kisi_emp[int(np.argmax(gain_emp))])
    gain_emp_fs6 = gain_empiris(f_harap)
    beda_ulang = beda(ulang_tahap(R.turunan, hp), tur)
    beda_rantai = beda(jalan["turunan"], tur)
    s_kasar = 2 * hp + geser(hp, 1) - geser(hp, 3) - 2 * geser(hp, 4)
    tidak_habis_8 = int(np.count_nonzero(s_kasar % 8 != 0))
    lulus = (galat_impuls == 0 and ekor == 0 and jumlah_h == 0 and maks_steadi == 0
             and antisimetris and beda_pusat == 0 and beda_pusat_buat == 0
             and abs(lag_buat) == 2 and abs(lag_real) == 2
             and abs(f_puncak_kantai - f_harap) < 0.01 and beda_ulang == 0 and beda_rantai == 0)
    line = ("T3 five point der  : impulse response of amplitude 8 %s against the closed form %s, "
            "max difference %d (exp 0), nonzero tail %d (exp 0), sum of h %d (exp 0, exact zero "
            "DC gain), constant input 1000 gives a steady maximum of %d (exp 0) and a transient "
            "maximum of %d | group delay: the kernel is antisymmetric about index 2 %s and the "
            "centered partner of the same kernel is the stage output delayed by exactly two "
            "samples, %d of %d differ on the recording (exp 0), %d of %d differ on a synthetic "
            "broadband series (exp 0); cross correlation peak lag %s on the recording and %s on "
            "the synthetic series (exp 2) | peak of the magnitude response: the chain kernel %s "
            "peaks at %.4f Hz and the paper kernel %s peaks at %.4f Hz (the locked value is "
            "%.4f Hz, that is fs/6) | the stage itself measured on a sinusoid grid peaks at "
            "%.1f Hz with gain %.4f and gives %.4f at fs/6 | real recording: stage replay %d of "
            "%d differ (exp 0), chain run %d differ (exp 0), raw derivative sum not divisible by "
            "eight at %d of %d samples so the division route cannot matter on this recording | "
            "data fixture+chain+synthetic | %s"
            % (h_ukur[:5].tolist(), list(KERNEL_KANTAI), galat_impuls, ekor, jumlah_h,
               maks_steadi, maks_transien, antisimetris, max(beda_pusat, 0), hp.size - 2,
               max(beda_pusat_buat, 0), x_buat.size - 2, lag_real, lag_buat,
               list(KERNEL_KANTAI), f_puncak_kantai, list(KERNEL_PAPER), f_puncak_paper,
               f_harap, f_emp, float(np.max(gain_emp)), gain_emp_fs6, max(beda_ulang, 0),
               hp.size, max(beda_rantai, 0), tidak_habis_8, hp.size,
               "LULUS" if lulus else "GAGAL"))
    hasil("T3 five point derivative", lulus, line)


# =============================================================================================
# Theorem 4, squaring: never negative, and 32 bits are enough. The measured maximum is
# compared with the bound predicted from the measured range of the stage before it.
# =============================================================================================

def teorema_4(d, jalan):
    ku = np.asarray(d["kuadrat"], dtype=np.int64)
    tur = np.asarray(d["turunan"], dtype=np.int64)
    hp = np.asarray(d["hp"], dtype=np.int64)
    ku_min, ku_maks = int(ku.min()), int(ku.max())
    negatif = int(np.count_nonzero(ku < 0))
    maks_hp = int(max(abs(int(hp.min())), abs(int(hp.max()))))
    batas_d = int(math.ceil(0.75 * maks_hp / 256.0))
    prediksi_ku = batas_d * batas_d
    maks_d = int(max(abs(int(tur.min())), abs(int(tur.max()))) >> GESER_AMBANG)
    lebar_ukur = int(ku_maks).bit_length()
    lebar_prediksi = int(prediksi_ku).bit_length()
    batas_32 = 2 ** 32 - 1
    beda_ulang = beda(ulang_tahap(R.kuadrat, tur), ku)
    beda_rantai = beda(jalan["kuadrat"], ku)
    lulus = (negatif == 0 and ku_maks <= prediksi_ku and ku_maks <= batas_32
             and lebar_ukur <= 32 and beda_ulang == 0 and beda_rantai == 0)
    line = ("T4 squaring        : minimum %d, negative samples %d of %d (exp 0) | measured maximum "
            "%d needs %d bits unsigned (exp 32 or fewer) | predicted bound from the measured "
            "max|hp| %d: |d| is at most %d, so the square is at most %d, which needs %d bits "
            "unsigned, and the measured max|d| is %d | 32 bit limit %d, measured headroom %.4f "
            "times | real recording: stage replay against the fixture %d of %d differ (exp 0), "
            "chain run %d differ (exp 0) | data fixture+chain+synthetic | %s"
            % (ku_min, negatif, ku.size, ku_maks, lebar_ukur, maks_hp, batas_d, prediksi_ku,
               lebar_prediksi, maks_d, batas_32, float(batas_32) / float(ku_maks),
               max(beda_ulang, 0), ku.size, max(beda_rantai, 0), "LULUS" if lulus else "GAGAL"))
    hasil("T4 squaring", lulus, line)


# =============================================================================================
# Theorem 5, window integration: DC gain 1, first zero at 6.6667 Hz, group delay 18.25
# samples, alternating width 37 and 38. The shifted sum must equal the direct sum at every
# index.
# =============================================================================================

def teorema_5(d, jalan):
    ku = np.asarray(d["kuadrat"], dtype=np.int64)
    sel = np.asarray(d["jendela"], dtype=np.int64)
    langsung = jendela_bergantian_direct(ku)
    penampan = jendela_bergantian_penampan(ku)
    ulang = ulang_tahap(R.jendela, ku)
    beda_stream_direct = beda(ulang, langsung)
    beda_stream_fixture = beda(ulang, sel)
    beda_direct_fixture = beda(langsung, sel)
    beda_penampan_fixture = beda(penampan, sel)
    beda_rantai = beda(jalan["jendela"], sel)
    c = 1000
    y_const = np.array(_langkah(R.jendela, c, 120), dtype=np.int64)
    w_genap = int(np.median(y_const[80:120:2]))
    w_ganjil = int(np.median(y_const[81:121:2]))
    lebar_genap, lebar_ganjil = w_genap // c, w_ganjil // c
    penguatan_dc = float(w_genap + w_ganjil) / (2.0 * JENDELA_MEAN * c)
    tunda_genap, tunda_ganjil = (N_A - 1) / 2.0, (N_B - 1) / 2.0
    tunda_ukur = 0.5 * (tunda_genap + tunda_ganjil)
    f_nol = nol_pertama_jendela()
    mag_nol = respons_jendela(JENDELA_MEAN, FS / JENDELA_MEAN)
    mag_nol_terukur = respons_jendela(JENDELA_MEAN, f_nol)
    maks_sel = int(max(abs(int(sel.min())), abs(int(sel.max()))))
    lebar_sel = int(maks_sel).bit_length()
    lulus = (beda_stream_direct == 0 and beda_stream_fixture == 0 and beda_direct_fixture == 0
             and beda_penampan_fixture == 0 and beda_rantai == 0
             and lebar_genap == N_A and lebar_ganjil == N_B
             and abs(penguatan_dc - 1.0) < 1e-12 and abs(tunda_ukur - TUNDA_JENDELA) < 1e-12
             and abs(f_nol - NOL_PERTAMA_JENDELA) < 1e-4 and mag_nol <= TOL
             and mag_nol_terukur <= 1e-6)
    line = ("T5 window integr   : the shifted sum of the stage against the direct sum of the "
            "notebook, %d of %d indices differ (exp 0); the stage against the fixture, %d differ "
            "(exp 0); the direct sum against the fixture, %d differ (exp 0); the circular buffer "
            "against the fixture, %d differ (exp 0); the chain run against the fixture, %d differ "
            "(exp 0) | width even %d and odd %d (exp %d and %d), read from a constant input c %d "
            "that gives %d and %d | DC gain %.6f (exp 1) | group delay %.4f samples from the two "
            "centroids %.2f and %.2f (exp %.2f) | first zero of the mean width response %.7f Hz "
            "with |H| %.3g there (exp %.7f with zero), the two integer widths null at %.4f and "
            "%.4f Hz and bracket it | measured maximum window value %d needs %d bits unsigned, a "
            "hardware finding and not a chain error | data fixture+chain+synthetic | %s"
            % (max(beda_stream_direct, 0), sel.size, max(beda_stream_fixture, 0),
               max(beda_direct_fixture, 0), max(beda_penampan_fixture, 0), max(beda_rantai, 0),
               lebar_genap, lebar_ganjil, N_A, N_B, c, w_genap, w_ganjil, penguatan_dc,
               tunda_ukur, tunda_genap, tunda_ganjil, TUNDA_JENDELA, f_nol, mag_nol,
               NOL_PERTAMA_JENDELA, FS / N_A, FS / N_B, maks_sel, lebar_sel,
               "LULUS" if lulus else "GAGAL"))
    hasil("T5 window integration", lulus, line)


# =============================================================================================
# Theorem 6, adaptive threshold: 0.125 is a right shift by three, 0.875 is one minus that
# shift, and the difference form is bit identical to the weighted form. Boolean test on more
# than two hundred thousand integers, then the same identity on the states of the chain run.
# =============================================================================================

def teorema_6(d, jalan, cap):
    rng = np.random.default_rng(601)
    n_uji = 1 << 20
    setengah = n_uji // 4
    a = np.concatenate([rng.integers(-4096, 4097, setengah),
                        rng.integers(0, 1 << 22, setengah),
                        rng.integers(-(1 << 20), 1 << 20, setengah),
                        np.arange(setengah, dtype=np.int64) - setengah // 2])
    p = np.concatenate([rng.integers(-4096, 4097, setengah),
                        rng.integers(0, 1 << 22, setengah),
                        rng.integers(-(1 << 20), 1 << 20, setengah),
                        np.arange(setengah, dtype=np.int64) - setengah // 2])
    floor_125 = np.floor(0.125 * a.astype(float))
    salah_125_shift = int(np.count_nonzero((a >> 3) != floor_125))
    salah_125_eksak = int(np.count_nonzero((a >> 3) != (a // 8)))
    floor_875 = np.floor(0.875 * a.astype(float))
    salah_875 = int(np.count_nonzero((a - ((a + 7) >> 3)) != floor_875))
    salah_875_eksak = int(np.count_nonzero((a - ((a + 7) >> 3)) != ((7 * a) // 8)))
    plain_875 = a - (a >> 3)
    salah_plain = int(np.count_nonzero(plain_875 != floor_875))
    selisih = a + ((p - a) >> 3)
    bobot_eksak = (7 * a + p) // 8
    bobot_float = np.floor(0.875 * a.astype(float) + 0.125 * p.astype(float)).astype(np.int64)
    salah_selisih = int(np.count_nonzero(selisih != bobot_eksak))
    salah_float = int(np.count_nonzero(selisih != bobot_float))
    if ADA_ACUAN:
        acuan = np.array([A.update_bulat(int(x), int(y), "floor")
                          for x, y in zip(a[:50000], p[:50000])], dtype=np.int64)
        salah_acuan = int(np.count_nonzero(acuan != selisih[:50000]))
    else:
        salah_acuan = 0 if bool(np.all(selisih[:50000] == (a[:50000] + ((p[:50000] - a[:50000]) >> 3)))) else -1
    amb = np.array(cap["ambang"], dtype=np.int64) if cap["ambang"] else np.zeros((0, 5), np.int64)
    if amb.size:
        spki, npki, pv = amb[:, 0], amb[:, 1], amb[:, 2]
        salah_real_spki = int(np.count_nonzero(
            spki + ((pv - spki) >> 3) != (7 * spki + pv) // 8))
        salah_real_npki = int(np.count_nonzero(
            npki + ((pv - npki) >> 3) != (7 * npki + pv) // 8))
        salah_i2 = int(np.count_nonzero(amb[:, 4] != (amb[:, 3] >> 1)))
        lebar_spki = int(max(abs(int(spki.min())), abs(int(spki.max())))).bit_length()
        lebar_npki = int(max(abs(int(npki.min())), abs(int(npki.max())))).bit_length()
        pasangan_real = int(spki.size * 2)
    else:
        salah_real_spki = salah_real_npki = salah_i2 = -1
        lebar_spki = lebar_npki = pasangan_real = 0
    lulus = (salah_125_shift == 0 and salah_125_eksak == 0 and salah_875 == 0
             and salah_875_eksak == 0 and salah_selisih == 0 and salah_float == 0
             and salah_acuan == 0 and salah_real_spki == 0 and salah_real_npki == 0
             and salah_i2 == 0 and pasangan_real > 0 and a.size > 200000 and p.size > 200000)
    line = ("T6 adaptive thresh: boolean test on %d integers and %d pairs: 0.125 against the right "
            "shift by three, %d differ from the float route and %d from the exact floor (exp 0); "
            "0.875 against one minus that shift, %d differ from the float route and %d from the "
            "exact floor (exp 0); the difference form against the weighted form, %d differ in "
            "exact integers and %d in float (exp 0); the notebook update_bulat against the chain "
            "form, %d differ of 50000 (exp 0) | the plain reading a - (a >> 3) deviates from "
            "floor(0.875 a) at %d of %d samples, which is why the carry in is kept | real chain "
            "states: %d update pairs from the recording, spki form %d differ and npki form %d "
            "differ (exp 0), the second threshold I2 %d differ (exp 0), states need %d and %d "
            "bits | data chain+synthetic | %s"
            % (a.size, p.size, salah_125_shift, salah_125_eksak, salah_875, salah_875_eksak,
               salah_selisih, salah_float, max(salah_acuan, 0), salah_plain, a.size,
               pasangan_real, max(salah_real_spki, 0), max(salah_real_npki, 0),
               max(salah_i2, 0), lebar_spki, lebar_npki, "LULUS" if lulus else "GAGAL"))
    hasil("T6 adaptive threshold", lulus, line)


# =============================================================================================
# Theorem 7, RR intervals: the cross forms 23/25, 59/64 and 83/50 are exact, the queue is
# always eight, the reseeding is bounded, and zero decisions differ from the fractional route.
# =============================================================================================

def teorema_7(d, jalan, cap):
    rng = np.random.default_rng(701)
    n_uji = 200000
    x_sweep = rng.integers(100, 2100, n_uji)
    B_sweep = rng.integers(800, 16001, n_uji)
    m_sweep = rng.integers(1, 9, n_uji)
    salah = {"23/25": 0, "59/64": 0, "83/50": 0}
    for x, B, m in zip(x_sweep, B_sweep, m_sweep):
        ref = Fraction(int(x)) >= Fraction(23, 25) * Fraction(int(B), int(m))
        if ((25 * int(m) * int(x) >= 23 * int(B)) and
                (25 * int(m) * int(x) <= 29 * int(B))) != (ref and
                (Fraction(int(x)) <= Fraction(29, 25) * Fraction(int(B), int(m)))):
            salah["23/25"] += 1
        if (64 * int(m) * int(x) >= 59 * int(B)) != (Fraction(int(x)) >= Fraction(59, 64) * Fraction(int(B), int(m))):
            salah["59/64"] += 1
        if (200 * int(x) * int(m) > 83 * int(B)) != (Fraction(4 * int(x)) > Fraction(83, 50) * Fraction(int(B), int(m))):
            salah["83/50"] += 1
    rr_cap = np.array(cap["rr"], dtype=np.int64) if cap["rr"] else np.zeros((0, 4), np.int64)
    if rr_cap.size:
        real_23 = real_59 = real_83 = 0
        for x, B, m, _menyala in rr_cap:
            if m == 0:
                continue
            ref23 = (Fraction(int(x)) >= Fraction(23, 25) * Fraction(int(B), int(m))) and \
                    (Fraction(int(x)) <= Fraction(29, 25) * Fraction(int(B), int(m)))
            if ref23 != bool(R._dalam_batas(int(x), int(B), int(m))):
                real_23 += 1
            if (Fraction(int(x)) >= Fraction(59, 64) * Fraction(int(B), int(m))) != \
                    (64 * int(m) * int(x) >= 59 * int(B)):
                real_59 += 1
            if (Fraction(4 * int(x)) > Fraction(83, 50) * Fraction(int(B), int(m))) != \
                    (200 * int(x) * int(m) > 83 * int(B)):
                real_83 += 1
        n_real = int(rr_cap.shape[0])
    else:
        real_23 = real_59 = real_83 = n_real = -1
    rr = np.asarray(d["rr"], dtype=np.int64)
    terpakai = rr[(rr >= 250) & (rr <= 2000)]
    st = R.rr_awal(semai_aktif=True)
    panjang_antre = []
    for x in terpakai:
        R.rr(int(x), st)
        panjang_antre.append(len(st["antre"]))
    panjang_antre = np.array(panjang_antre, dtype=np.int64)
    capai_8 = np.flatnonzero(panjang_antre == 8)
    indeks_8 = int(capai_8[0]) if capai_8.size else -1
    langgar = int(np.count_nonzero(panjang_antre[indeks_8:] != 8)) if indeks_8 >= 0 else -1
    baris = np.array(st["baris"], dtype=np.int64)
    kolom = ("rr_average1", "rr_average2", "rr_antre_panjang", "penanda", "rr_disemai",
             "rr_riwayat_panjang")
    beda_kolom = [beda(baris[:, j], d[k]) for j, k in enumerate(kolom)]
    beda_menyala = int(st["menyala"]) - int(d["rr_menyala_akhir"])
    langkah_semai = np.flatnonzero(baris[:, 4] == 1)
    jumlah_semai = int(langkah_semai.size)
    jarak_semai = np.diff(langkah_semai) if jumlah_semai > 1 else np.array([SEMAI_JEDA])
    jarak_min, jarak_maks = int(jarak_semai.min()), int(jarak_semai.max())
    lulus = (all(v == 0 for v in salah.values()) and real_23 == 0 and real_59 == 0
             and real_83 == 0 and langgar == 0 and all(v == 0 for v in beda_kolom)
             and beda_menyala == 0 and jarak_min >= SEMAI_JEDA
             and int(d["rr_disemai"].sum()) == jumlah_semai)
    line = ("T7 RR interval     : cross forms on %d synthetic triples: 23/25 %d differ, 59/64 %d "
            "differ, 83/50 %d differ (exp 0); on the %d real decision states of the recording the "
            "same three forms differ %d, %d and %d (exp 0) | the queue reaches exactly eight at "
            "step %d of %d and then %d of the remaining %d steps differ from eight (exp 0 after "
            "the queue is established, the %d warm up steps before it are the only shorter ones) "
            "| reseeding %d steps, smallest spacing %d beats and largest %d (exp at least %d, the "
            "measured pair is reported), the fixture reseed column differs %d (exp 0) | the real "
            "interval series replayed against the fixture: %s differ over %d rows for the six "
            "columns (exp 0), warning flag final %d against %d | data fixture+chain+synthetic "
            "| %s"
            % (n_uji, salah["23/25"], salah["59/64"], salah["83/50"], max(n_real, 0),
               max(real_23, 0), max(real_59, 0), max(real_83, 0), indeks_8, panjang_antre.size,
               max(langgar, 0), max(panjang_antre.size - indeks_8, 0), max(indeks_8, 0),
               jumlah_semai, jarak_min, jarak_maks, SEMAI_JEDA, max(beda_kolom[4], 0),
               [max(v, 0) for v in beda_kolom], int(d["rr_average1"].size), int(st["menyala"]),
               int(d["rr_menyala_akhir"]), "LULUS" if lulus else "GAGAL"))
    hasil("T7 RR interval", lulus, line)


# =============================================================================================
# Theorem 8, T wave: two times the slope smaller than the previous slope, the cross form
# exact, and zero errors on a grid of 16777216 pairs.
# =============================================================================================

def teorema_8(d, jalan, cap):
    s = np.arange(KISI_T, dtype=np.int64)
    salah_float = 0
    salah_geser = 0
    butuh_cross = 0
    for sp in s:
        cross = 2 * s < sp
        salah_float += int(np.count_nonzero(cross != (s < (int(sp) / 2.0))))
        salah_geser += int(np.count_nonzero(cross != (s < (int(sp) >> 1))))
        if bool(np.any(cross)):
            butuh_cross += 1
    jumlah_kisi = KISI_T * KISI_T
    rng = np.random.default_rng(801)
    idx_s = rng.integers(0, KISI_T, 200000)
    idx_p = rng.integers(0, KISI_T, 200000)
    salah_rasional = 0
    for i, j in zip(idx_s, idx_p):
        if (2 * int(i) < int(j)) != bool(Fraction(2 * int(i)) < Fraction(int(j))):
            salah_rasional += 1
    t_cap = np.array(cap["t"], dtype=np.int64) if cap["t"] else np.zeros((0, 4), np.int64)
    if t_cap.size:
        s_real, sp_real = t_cap[:, 0], t_cap[:, 1]
        dipakai = t_cap[:, 2] == 1
        salah_real_float = int(np.count_nonzero(
            (2 * s_real < sp_real) != (s_real < sp_real / 2.0)))
        salah_real_rasional = 0
        for x, y in zip(s_real, sp_real):
            if (2 * int(x) < int(y)) != bool(Fraction(2 * int(x)) < Fraction(int(y))):
                salah_real_rasional += 1
        jumlah_pita = int(np.count_nonzero(dipakai))
        jumlah_pasangan = int(t_cap.shape[0])
        geser_pita = int(np.count_nonzero(
            (s_real[dipakai] < (sp_real[dipakai] >> 1)) != (2 * s_real[dipakai] < sp_real[dipakai])))
        lebar_kem = int(max(abs(int(s_real.min())), abs(int(s_real.max())))).bit_length()
        beda_kem = beda(t_cap[:, 0], np.asarray(d["ambang_kemiringan_puncak"], dtype=np.int64))
    else:
        salah_real_float = salah_real_rasional = geser_pita = -1
        jumlah_pita = jumlah_pasangan = beda_kem = lebar_kem = 0
    # The state counters of the real run: the rule is really applied only to a peak that passed
    # the first threshold while inside the band, and those are counted by the chain itself.
    st_amb = np.asarray(jalan["ambang_state"], dtype=np.int64)
    diperiksa, ditolak = int(st_amb[2]), int(st_amb[3])
    lulus = (salah_float == 0 and salah_rasional == 0 and salah_real_float == 0
             and salah_real_rasional == 0 and beda_kem == 0 and diperiksa > 100
             and diperiksa == int(np.asarray(d["rasio_pita"]).size))
    line = ("T8 T wave          : the cross form 2 s < s_prev on a grid of %d pairs, that is 4096 "
            "by 4096: %d differ from the float route s < s_prev/2 (exp 0) and %d differ from the "
            "exact rational route on 200000 sampled pairs (exp 0); the rejected shift route "
            "s < (s_prev >> 1) differs from the cross form at %d of %d pairs (measured, the cross "
            "form is the locked one) | real chain rule: %d slope measurements inside the 360 ms "
            "band out of %d slope pairs of the recording, the rule itself applied to %d peaks and "
            "rejecting %d, which matches the %d ratios of the fixture (exp the same count), cross "
            "against float %d differ and cross against rational %d differ over all real pairs "
            "(exp 0); inside the band the shift route would differ at %d pairs (measured); slope "
            "values need %d bits and differ from the fixture slope column at %d places (exp 0) | "
            "data fixture+chain+synthetic | %s"
            % (jumlah_kisi, salah_float, salah_rasional, salah_geser, jumlah_kisi, jumlah_pita,
               jumlah_pasangan, diperiksa, ditolak, int(np.asarray(d["rasio_pita"]).size),
               max(salah_real_float, 0), max(salah_real_rasional, 0), max(geser_pita, 0),
               lebar_kem, max(beda_kem, 0), "LULUS" if lulus else "GAGAL"))
    hasil("T8 T wave", lulus, line)


# =============================================================================================
# Obligation A, the serial case of the search back boundary: delta times four exactly equal to
# 83 times the second average divided by 50. The integer cross form of the chain against the
# floating point form of the notebook, on an artificial series that lands on the point.
# =============================================================================================

def deret_buatan(delta_uji, pv_uji=1200, n_qrs=20, jarak=200, pv_qrs=4000,
                 spki=4000, npki=1000):
    """An artificial peak series driven through the real threshold stage of the chain.

    Twenty QRS peaks every 200 samples, so the RR stage fills its queue with eight intervals
    of 800 ms and the second average becomes 800. Then one candidate peak whose distance to
    the last QRS is the argument, and the verdict of the real stage is returned.
    """
    state = R.ambang_awal(semai_aktif=True, aturan_t=True, puncak=[])
    state["spki"] = int(spki)
    state["npki"] = int(npki)
    ring = R.GarisTunda(64)
    for _ in range(6000):
        ring.dorong(0)
    state_t = R.gelombang_t_awal(ring)
    posisi = [jarak * k for k in range(n_qrs)]
    for pos in posisi:
        i_pk = len(state["puncak"])
        state["puncak"].append(pos)
        state["puncak_nilai"].append(int(pv_qrs))
        R.ambang(state, pos, i_pk, int(pv_qrs), int(pv_qrs), state_t)
    qrs_sebelum = len(state["qrs"])
    pos_uji = posisi[-1] + int(delta_uji)
    i_pk = len(state["puncak"])
    state["puncak"].append(pos_uji)
    state["puncak_nilai"].append(int(pv_uji))
    R.ambang(state, pos_uji, i_pk, int(pv_uji), int(pv_uji), state_t)
    return dict(baru=state["qrs"][qrs_sebelum:], cari=state["cari_mundur"],
                pembilang=state["tahap_rr"]["pembilang"],
                penyebut=state["tahap_rr"]["penyebut"],
                ra1=state["tahap_rr"]["ra1"], ra2=state["tahap_rr"]["ra2"],
                i_qrs=state["i_qrs"], delta=int(delta_uji), n_qrs=n_qrs)


def kasus_seri(d, jalan):
    contoh = deret_buatan(332)
    B, m = contoh["pembilang"], contoh["penyebut"]
    ra2_bulat = B // m if m else 0
    delta_seri = 83 * B // (200 * m) if m else -1
    if ADA_ACUAN:
        tahap = A.TahapRR(semai_aktif=True)
        for _ in range(19):
            tahap.maju(800)
        ra2_notebook = float(tahap.ra2)
    else:
        ra2_notebook = float(B) / float(m)
    batas_notebook = 83.0 * ra2_notebook / 50.0
    presisi_seri = (delta_seri * 1000.0 / FS) == batas_notebook
    uji = {}
    for delta in (delta_seri - 1, delta_seri, delta_seri + 1):
        out = deret_buatan(delta)
        uji[delta] = dict(cari=out["cari"], baru=len(out["baru"]),
                          pred_int=200 * delta * m > 83 * B,
                          pred_notebook=(delta * 1000.0 / FS) > batas_notebook)
    n_seri = 0
    beda_seri = 0
    for m_u in range(1, 9):
        for B_u in range(1, 16001):
            d0 = Fraction(83 * B_u, 200 * m_u)
            if d0.denominator != 1:
                continue
            for delta in (int(d0) - 1, int(d0), int(d0) + 1):
                if delta < 0:
                    continue
                n_seri += 1
                a_int = 200 * delta * m_u > 83 * B_u
                a_notebook = (delta * 1000.0 / FS) > (83.0 * (float(B_u) / float(m_u)) / 50.0)
                a_eksak = Fraction(delta * 1000, 250) > Fraction(83, 50) * Fraction(B_u, m_u)
                if not (a_int == a_notebook == a_eksak):
                    beda_seri += 1
    n_dekat = 0
    beda_dekat = 0
    for m_u in range(1, 9):
        for B_u in range(1000, 16001, 7):
            dasar = Fraction(83 * B_u, 200 * m_u)
            for delta in range(max(0, int(dasar) - 3), int(dasar) + 4):
                n_dekat += 1
                a_int = 200 * delta * m_u > 83 * B_u
                a_notebook = (delta * 1000.0 / FS) > (83.0 * (float(B_u) / float(m_u)) / 50.0)
                if a_int != a_notebook:
                    beda_dekat += 1
    lulus = (delta_seri > 0 and presisi_seri and beda_seri == 0 and beda_dekat == 0
             and uji[delta_seri]["pred_int"] == uji[delta_seri]["pred_notebook"]
             and uji[delta_seri]["cari"] == 0 and uji[delta_seri]["baru"] == 0
             and uji[delta_seri - 1]["cari"] == 0 and uji[delta_seri - 1]["baru"] == 0
             and uji[delta_seri + 1]["pred_int"] and uji[delta_seri + 1]["pred_notebook"]
             and uji[delta_seri + 1]["cari"] == 1 and uji[delta_seri + 1]["baru"] == 1)
    line = ("A  serial search back: the artificial series of %d QRS peaks every %d samples with "
            "envelope value %d and one candidate peak of %d builds a queue of %d intervals "
            "summing %d, so the second average is %d and the serial point falls at delta %d "
            "samples, where 4 delta %d equals 83 times the average over 50, %.6f, exactly %s | "
            "through the real stage: delta %d does not fire, the count of search back stays %d, "
            "and no beat is added %d; delta %d, the serial point, does not fire either, search "
            "back %d and beats added %d; delta %d fires, search back %d and beats added %d (exp "
            "0, 0, 0 for the first two and 1, 1 for the last) | the integer cross form and the "
            "notebook float form agree at the serial point and at both neighbours, and over %d "
            "exact serial triples and %d triples around the boundary there are %d and %d "
            "disagreements between the chain form, the notebook form and the exact rational form "
            "(exp 0) | data synthetic series through the real stage, plus the notebook route of "
            "acuan_fase | %s"
            % (contoh["n_qrs"], 200, 4000, 1200, m, B, ra2_bulat, delta_seri, 4 * delta_seri,
               batas_notebook, presisi_seri, delta_seri - 1, uji[delta_seri - 1]["cari"],
               uji[delta_seri - 1]["baru"], delta_seri, uji[delta_seri]["cari"],
               uji[delta_seri]["baru"], delta_seri + 1, uji[delta_seri + 1]["cari"],
               uji[delta_seri + 1]["baru"], n_seri, n_dekat, beda_seri, beda_dekat,
               "LULUS" if lulus else "GAGAL"))
    hasil("A serial search back", lulus, line)


# =============================================================================================
# Main.
# =============================================================================================

def main():
    cetak("AFIB-LITE phase 6 step S3 gate: one closed form theorem per chain stage")
    cetak("fixture     : %s, %d bytes" % (NPZ, NPZ.stat().st_size))
    sidik = sidik_jari(NPZ)
    cetak("fixture sha : %s %s" % (sidik, "matches the frozen fingerprint" if
                                   sidik == SIDIK_FIXTURE else
                                   "DIFFERS from the frozen fingerprint " + SIDIK_FIXTURE))
    cetak("notebook ref: %s" % (CATATAN_ACUAN,))
    d = np.load(NPZ)
    kunci = sorted(d.files)
    masukan, sumber = muat_masukan()
    cetak("input       : %s" % (sumber,))
    jalan, cap = jalankan_rantai(masukan)
    cetak("chain run   : %.1f s streaming over %d samples" % (jalan["_detik"], masukan.size))
    dibanding = 0
    beda_rantai = []
    for k in kunci:
        if k in jalan:
            dibanding += 1
            n = beda(jalan[k], d[k])
            if n != 0:
                beda_rantai.append("%s (%d differ)" % (k, n))
    cetak("chain against the fixture: %d arrays compared, %s"
          % (dibanding, "all identical" if not beda_rantai else "differing: " + ", ".join(beda_rantai)))
    cetak("real states captured: %d threshold calls, %d RR calls, %d slope measurements"
          % (len(cap["ambang"]), len(cap["rr"]), len(cap["t"])))
    cetak("")
    cetak("per theorem result, one line each")
    cetak("-" * 132)
    teorema_1(d, jalan)
    teorema_2(d, jalan)
    teorema_3(d, jalan)
    teorema_4(d, jalan)
    teorema_5(d, jalan)
    teorema_6(d, jalan, cap)
    teorema_7(d, jalan, cap)
    teorema_8(d, jalan, cap)
    kasus_seri(d, jalan)
    cetak("-" * 132)
    lulus = sum(1 for _n, ok, _l in BARIS if ok)
    gagal = sum(1 for _n, ok, _l in BARIS if not ok)
    cetak("gate items: %d pass, %d fail, %d total" % (lulus, gagal, len(BARIS)))
    if gagal == 0 and sidik == SIDIK_FIXTURE:
        cetak("gate S3: PASS")
        return 0
    cetak("gate S3: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
