#!/usr/bin/env python3
"""siapkan_vektor_fase7.py -- Fase 7 (aturan gelombang T) vector reduction.

Reads the FROZEN Fase 0 column and the FROZEN Fase 5 fixture and writes the vectors
`rtl/tb/tb_gelombang_t.sv` compares against. Nothing in rtlplan2/, model/ or rtl2/ is
written; model/rantai-afib-lite/rantai.py is imported read-only as the behaviour source
(sha256 recorded in the manifest, must stay
90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5).

Every golden number below comes from one of two places, and the script prints the check:

  1. the frozen model's own function `GarisTunda.maks_mutlak` (rantai.py:137-148), called on
     the frozen `04015.turunan.hex` column, for the slope `kem` of each measured peak;
     cross checked against the `slope` column of rtlplan2/fase5/04015.peaks.csv;
  2. the frozen run's own columns of rtlplan2/fase5/04015.peaks.csv
     (`sample_delta`, `in_band`, `t_rejected`, `is_qrs`, `slope`).

The reconstruction of the model's `kem_qrs` state (the slope of the previous accepted QRS)
is proved, not assumed: for every one of the 4777 peaks the frozen column `t_rejected`
must equal `in_band and (2*kem < kem_qrs)` with kem_qrs taken from the last row with
`is_qrs = 1`. The script aborts on any mismatch.

Vectors written (all in the directory given on the command line, default = this directory):

  04015.turunan.hex           450000 words, byte-identical copy of the frozen Fase 0 column
  04015.fase7.pos.hex         4777 peak positions (rantai.py:990 `scan`)
  04015.fase7.kem.hex         4777 slopes, model maks_mutlak over [pos-18, pos+18]
  04015.fase7.delta.hex       4777 `delta` = pos - i_qrs, in SAMPLES (rantai.py:664)
  04015.fase7.kemqrs.hex      4777 slopes of the previous accepted QRS
  04015.fase7.flag.hex        4777 flag words, see FLAG_* below
  04015.sintetis.turunan.hex  60000 word synthetic derivative line
  04015.sintetis.pos.hex      sampled positions on that line
  04015.sintetis.kem.hex      golden slope at each sampled position
  04015.stair.der.hex         block constant derivative value per row (grid rows first)
  04015.stair.sp.hex          i_kem_qrs per row
  04015.stair.delta.hex       i_delta per row
  04015.stair.flag.hex        flag word per row, see SFLAG_* below
  04015.fase7.counts.hex      counts, see COUNTS below
  04015.fase7.manifest.json   counts, sha256 of every written file, sources and checks
  04015.grid.full.out         the raw full 4096x4096 grid run of the frozen model's theorem

Grid rows (SFLAG_GRID): the boundary complete lattice of the crossing form,
{(s, sp) : sp in 0..4095, s in {floor(sp/2)-1, floor(sp/2), floor(sp/2)+1} clamped at 0},
which contains every pair where the crossing form and the forbidden shift form can differ,
plus a pseudo random sample of pairs over the whole 12 bit square.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import pathlib
import sys

import numpy as np

BASE = pathlib.Path("/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite")
MODEL = BASE / "model/rantai-afib-lite/rantai.py"
FASE0 = BASE / "rtlplan2/fase0"
FASE5 = BASE / "rtlplan2/fase5"

MODEL_SHA_FROZEN = "90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5"

# flag word of 04015.fase7.flag.hex, one bit per fact, no measured number is stored
FLAG_DELTA_VALID = 0      # b0: the model had a previous QRS, delta is not None
FLAG_KEMQRS_VALID = 1     # b1: the model had a previous QRS slope, kem_qrs is not None
FLAG_IN_BAND = 2          # b2: rtlplan2/fase5/04015.peaks.csv column in_band
FLAG_T_REJECTED = 3       # b3: rtlplan2/fase5/04015.peaks.csv column t_rejected
FLAG_SIGNAL = 4           # b4: the frozen run's final signal verdict
FLAG_IS_QRS = 5           # b5: the frozen run accepted this peak as a QRS

# flag word of 04015.stair.flag.hex
SFLAG_DELTA_VALID = 0     # b0: drive i_delta_valid
SFLAG_KEMQRS_VALID = 1    # b1: drive i_kem_qrs_valid
SFLAG_ENABLE = 2          # b2: drive i_rule_enable
SFLAG_EXP_IN_BAND = 3     # b3: golden dalam_pita of this row
SFLAG_EXP_REJECT = 4      # b4: golden ditolak of this row
SFLAG_GRID = 5            # b5: 1 = grid row, 0 = edge case row

# counts of 04015.fase7.counts.hex, index order is fixed
COUNTS = ("frames", "peaks", "peaks_usable", "sint_words", "sint_pos", "grid_rows",
          "edge_rows", "stair_rows", "grid_shift_differ_sim", "grid_float_differ_sim",
          "sint_pos_usable")

SINT_WORDS = 60000        # synthetic derivative line length
SINT_STEP = 11            # sampled positions every 11 words (must exceed the scan busy 10)
GRID_KISI = 4096          # the model's KISI_T, uji_00_teorema.py:83
GRID_RANDOM = 4096        # pseudo random pairs added to the boundary lattice
RNG_SEED = 801            # same seed as uji_00_teorema.py:778


def sha256_of(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_hex_words(path: pathlib.Path) -> np.ndarray:
    """One 8 hex digit word per line, the Fase 0 format. Returns the 32 bit pattern."""
    return np.array([int(line, 16) for line in path.read_text().split()], dtype=np.int64)


def word(value: int) -> str:
    """The Fase 0 word format: 8 hex digits, two's complement of the 32 bit pattern."""
    return "%08X" % (int(value) & 0xFFFFFFFF)


def write_hex(values, path: pathlib.Path) -> None:
    path.write_text("".join(word(v) + "\n" for v in values))


def import_frozen_model():
    spec = importlib.util.spec_from_file_location("rantai_beku", MODEL)
    assert spec is not None and spec.loader is not None, "cannot import the frozen model"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    out_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    sha_model = sha256_of(MODEL)
    if sha_model != MODEL_SHA_FROZEN:
        print("FATAL: rantai.py sha256 %s differs from the frozen %s" % (sha_model, MODEL_SHA_FROZEN))
        return 2
    M = import_frozen_model()
    setengah = int(M.SETENGAH_JENDELA)
    if setengah != 18:
        print("FATAL: SETENGAH_JENDELA changed")
        return 2

    # ---------------------------------------------------------------- frozen inputs
    tur_words = load_hex_words(FASE0 / "04015.turunan.hex")
    tur = tur_words.copy()
    tur[tur >= 2 ** 31] -= 2 ** 32                       # the 24 bit signed value
    if not np.all((tur >= -2 ** 23) & (tur < 2 ** 23)):
        print("FATAL: a turunan word does not fit signed 24 bit")
        return 2
    frames = int(tur.size)

    rows = list(csv.DictReader((FASE5 / "04015.peaks.csv").open()))
    pos = np.array([int(r["sample_index"]) for r in rows], dtype=np.int64)
    slope_csv = np.array([int(r["slope"]) for r in rows], dtype=np.int64)
    delta_csv = np.array([int(r["sample_delta"]) for r in rows], dtype=np.int64)
    in_band = np.array([int(r["in_band"]) for r in rows], dtype=np.int64)
    t_reject = np.array([int(r["t_rejected"]) for r in rows], dtype=np.int64)
    is_qrs = np.array([int(r["is_qrs"]) for r in rows], dtype=np.int64)
    signal = np.array([int(r["signal"]) for r in rows], dtype=np.int64)
    n_peak = int(pos.size)

    # ------------------------------------------------- model kem for every real peak
    garis = M.GarisTunda(64)                              # :933, the model's own ring
    kem = np.zeros(n_peak, dtype=np.int64)
    pushed = -1
    for k in range(n_peak):
        p = int(pos[k])
        hi = p + setengah
        stop = hi if hi < frames - 1 else frames - 1
        for i in range(pushed + 1, stop + 1):
            garis.dorong(int(tur[i]))
        pushed = stop
        kem[k] = int(garis.maks_mutlak(p - setengah, hi))
    kem_bad = int(np.count_nonzero(kem != slope_csv))
    print("CHECK model maks_mutlak vs peaks.csv slope: mismatches = %d of %d" % (kem_bad, n_peak))
    if kem_bad:
        bad = np.nonzero(kem != slope_csv)[0][:5]
        for k in bad:
            print("   k=%d pos=%d model=%d csv=%d" % (k, pos[k], kem[k], slope_csv[k]))
        return 2

    # --------------------------------- delta state, the model's recorded QRS sample
    # The model's `i_qrs` is the SAMPLE index of the last RECORDED QRS (rantai.py:664, the
    # search back records `sp`, not the candidate `pos`), and delta is taken before the
    # update. The frozen fixture carries that recorded index in `qrs_sample_index`, so the
    # reconstruction below is the model's own state and not a guess. `delta` is in SAMPLES.
    # The fixture's `sample_delta` column is written as 0 on the rows that are themselves a
    # QRS, so it is NOT used as the source here; it is only counted as a cross check below.
    delta = np.zeros(n_peak, dtype=np.int64)
    d_valid = np.zeros(n_peak, dtype=np.int64)
    kem_qrs = np.zeros(n_peak, dtype=np.int64)
    kq_valid = np.zeros(n_peak, dtype=np.int64)
    state_pos = -1
    state_kem = -1
    for k in range(n_peak):
        if state_pos >= 0:
            delta[k] = int(pos[k]) - state_pos
            d_valid[k] = 1
        if state_kem >= 0:
            kem_qrs[k] = state_kem
            kq_valid[k] = 1
        if is_qrs[k]:
            qsi = rows[k]["qrs_sample_index"]
            if qsi != "":
                state_pos = int(qsi)
            state_kem = int(slope_csv[k])
    delta_vs_csv = int(np.count_nonzero(delta != delta_csv))
    delta_vs_csv_nonzero = int(np.count_nonzero((delta != delta_csv) & (delta_csv != 0)))
    print("CHECK driven delta vs peaks.csv sample_delta: differ = %d (of which %d have a "
          "nonzero csv value; the csv writes 0 on the QRS rows themselves)"
          % (delta_vs_csv, delta_vs_csv_nonzero))

    # the decisive check of the three inputs: the model's own dalam_pita column
    band_rec = ((((delta << 2) < 360) & (d_valid == 1) & (kq_valid == 1))).astype(np.int64)
    band_bad = int(np.count_nonzero(band_rec != in_band))
    print("CHECK delta_valid & kem_qrs_valid & (delta<<2 < 360) vs peaks.csv in_band: "
          "mismatches = %d of %d (in_band ones = %d)" % (band_bad, n_peak, int(in_band.sum())))
    if band_bad:
        return 2
    cross = 2 * kem < kem_qrs
    exp_reject = ((in_band == 1) & cross).astype(np.int64)
    rej_bad = int(np.count_nonzero(exp_reject != t_reject))
    print("CHECK in_band and (2*kem < kem_qrs) vs peaks.csv t_rejected: mismatches = %d of %d "
          "(t_rejected ones = %d)" % (rej_bad, n_peak, int(t_reject.sum())))
    if rej_bad:
        return 2

    # the forbidden shift route, on the pairs that are really checked in the band
    checked = (signal == 1) & (in_band == 1)
    n_checked = int(np.count_nonzero(checked))
    s_chk = kem[checked]
    sp_chk = kem_qrs[checked]
    shift_pair_diff = int(np.count_nonzero((2 * s_chk < sp_chk) != (s_chk < (sp_chk >> 1))))
    float_pair_diff = int(np.count_nonzero((2 * s_chk < sp_chk) != (s_chk < sp_chk / 2.0)))
    print("real in band pairs checked by the rule = %d, cross vs shift differ = %d, "
          "cross vs float differ = %d" % (n_checked, shift_pair_diff, float_pair_diff))

    # ------------------------------------------------------- full grid, frozen model
    s_all = np.arange(GRID_KISI, dtype=np.int64)
    grid_shift = 0
    grid_float = 0
    for sp in s_all:
        cross_row = 2 * s_all < int(sp)
        grid_shift += int(np.count_nonzero(cross_row != (s_all < (int(sp) >> 1))))
        grid_float += int(np.count_nonzero(cross_row != (s_all < (int(sp) / 2.0))))
    grid_pairs = GRID_KISI * GRID_KISI
    rng = np.random.default_rng(RNG_SEED)
    is_s = rng.integers(0, GRID_KISI, 200000)
    is_p = rng.integers(0, GRID_KISI, 200000)
    from fractions import Fraction
    grid_rational = 0
    for i, j in zip(is_s, is_p):
        if (2 * int(i) < int(j)) != bool(Fraction(2 * int(i)) < Fraction(int(j))):
            grid_rational += 1
    full = []
    full.append("grid of the frozen model theorem (uji_00_teorema.py:766-777, doc 06 section 4.1)")
    full.append("grid: s and s_prev both 0..%d, pairs = %d" % (GRID_KISI - 1, grid_pairs))
    full.append("cross form 2*s < s_prev vs float route s < s_prev/2.0 : differ = %d" % grid_float)
    full.append("cross form 2*s < s_prev vs forbidden shift s < (s_prev >> 1) : differ = %d"
                % grid_shift)
    full.append("cross form vs exact rational (Fraction), 200000 random pairs : differ = %d"
                % grid_rational)
    full.append("fraction of the grid where the shift route differs = %d/%d = %.8f"
                % (grid_shift, grid_pairs, grid_shift / grid_pairs))
    text = "\n".join(full) + "\n"
    (out_dir / "04015.grid.full.out").write_text(text)
    print(text, end="")

    # ----------------------------------------------------------- 04015.fase7 columns
    write_hex(pos, out_dir / "04015.fase7.pos.hex")
    write_hex(kem, out_dir / "04015.fase7.kem.hex")
    write_hex(delta, out_dir / "04015.fase7.delta.hex")
    write_hex(kem_qrs, out_dir / "04015.fase7.kemqrs.hex")
    flag = (d_valid << FLAG_DELTA_VALID) | (kq_valid << FLAG_KEMQRS_VALID) \
           | (in_band << FLAG_IN_BAND) | (t_reject << FLAG_T_REJECTED) \
           | (signal << FLAG_SIGNAL) | (is_qrs << FLAG_IS_QRS)
    write_hex(flag, out_dir / "04015.fase7.flag.hex")

    # ---------------------------------------------------------------- synthetic line
    x = 20261020
    sint = np.zeros(SINT_WORDS, dtype=np.int64)
    for i in range(SINT_WORDS):
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        v = ((x >> 8) % (2 ** 22)) - 2 ** 21
        if i % 997 == 0:
            v = 4194303                      # the top of the derivative node, W_DER/Q17.7
        elif i % 613 == 0:
            v = -4194303
        sint[i] = v
    write_hex(sint & 0xFFFFFFFF, out_dir / "04015.sintetis.turunan.hex")
    # capacity must cover the WHOLE line: GarisTunda is a ring, and _potong() clamps the
    # query to the samples still held, so a short ring would answer every early position
    # with the tail of the line and the golden would be wrong (found by this phase).
    garis_s = M.GarisTunda(SINT_WORDS)
    for v in sint:
        garis_s.dorong(int(v))
    s_pos = [i for i in range(0, SINT_WORDS - setengah) if i % SINT_STEP == 0]
    s_kem = [int(garis_s.maks_mutlak(p - setengah, min(p + setengah, SINT_WORDS - 1)))
             for p in s_pos]
    write_hex(s_pos, out_dir / "04015.sintetis.pos.hex")
    write_hex(s_kem, out_dir / "04015.sintetis.kem.hex")
    print("synthetic line: %d words, %d sampled positions, max golden kem = %d"
          % (SINT_WORDS, len(s_pos), max(s_kem)))

    # ------------------------------------------------------------------- stair rows
    der_rows = []
    sp_rows = []
    delta_rows = []
    sflag_rows = []

    def push(der, sp, delta_v, flags):
        der_rows.append(der)
        sp_rows.append(sp)
        delta_rows.append(delta_v)
        sflag_rows.append(flags)

    grid_pairs_list = []
    for sp in range(GRID_KISI):
        t = sp >> 1
        for d in (-1, 0, 1):
            s = t + d
            if s < 0:
                continue
            grid_pairs_list.append((s, sp))
    rng_g = np.random.default_rng(7)
    extra_s = rng_g.integers(0, 2 ** 22, GRID_RANDOM)
    extra_p = rng_g.integers(0, 2 ** 22, GRID_RANDOM)
    for i in range(GRID_RANDOM):
        grid_pairs_list.append((int(extra_s[i]), int(extra_p[i])))
    for s, sp in grid_pairs_list:
        push(s, sp, 0, (1 << SFLAG_DELTA_VALID) | (1 << SFLAG_KEMQRS_VALID)
             | (1 << SFLAG_ENABLE) | (1 << SFLAG_GRID)
             | (1 << SFLAG_EXP_IN_BAND) | ((1 << SFLAG_EXP_REJECT) if 2 * s < sp else 0))
    n_grid = len(grid_pairs_list)

    # edge cases. der is the constant derivative value of the row's 37 word block, so the
    # window slope equals its magnitude, clamped by the block to W_TW, see the RTL header.
    rail = 2 ** 23 - 1
    edge = [
        # der, kem_qrs, delta, delta_valid, kemqrs_valid, enable, exp_in_band, exp_reject, why
        (100000, 200001, 10, 1, 1, 1, 1, 1, "2*kem = 200000 < 200001, rejected"),
        (100000, 200000, 10, 1, 1, 1, 1, 0, "2*kem = kem_qrs exactly, cross form FALSE"),
        (100000, 199999, 10, 1, 1, 1, 1, 0, "2*kem = kem_qrs + 1"),
        (0, 1, 10, 1, 1, 1, 1, 1, "kem = 0 < 1/2, rejected"),
        (0, 0, 10, 1, 1, 1, 1, 0, "kem_qrs = 0, 2*0 < 0 false"),
        (100000, 200001, 89, 1, 1, 1, 1, 1, "delta 89: 89<<2 = 356 < 360, in band"),
        (100000, 200001, 90, 1, 1, 1, 0, 0, "delta 90: 90<<2 = 360 is NOT < 360, out of band"),
        (100000, 200001, 91, 1, 1, 1, 0, 0, "delta 91: out of band"),
        (3995970, 7991941, 74, 1, 1, 1, 1, 1, "largest measured slope, 2*kem < kem_qrs"),
        (3995970, 7991940, 74, 1, 1, 1, 1, 0, "largest measured slope at the exact boundary"),
        (100000, 200001, 10, 0, 1, 1, 0, 0, "no previous QRS, delta None"),
        (100000, 200001, 10, 1, 1, 0, 0, 0, "rule disabled by i_rule_enable, slope measured"),
        (8388607, 16777215, 10, 1, 1, 1, 1, 1, "the largest slope that still fits the report"
         " port (2*kem = 2**24-2) against the largest kem_qrs the 24 bit port carries"
         " (2**24-1): a rejection at the very top of both operands"),
        (-8388608, 16777215, 10, 1, 1, 1, 1, 0, "the most negative derivative word: the slope"
         " 2**23 saturates the report word at 2**23-1 (m_overflow) while the rule compares the"
         " full 2**23, and 2*kem = 2**24 is above any kem_qrs this port can carry, so no"
         " rejection is possible: the one pair where report word and compared value differ"),
    ]
    for der, sp, dl, dv, kv, en, ib, rj, _why in edge:
        push(der, sp, dl,
             ((1 << SFLAG_DELTA_VALID) if dv else 0) | ((1 << SFLAG_KEMQRS_VALID) if kv else 0)
             | ((1 << SFLAG_ENABLE) if en else 0) | ((1 << SFLAG_EXP_IN_BAND) if ib else 0)
             | ((1 << SFLAG_EXP_REJECT) if rj else 0))
    n_edge = len(edge)

    write_hex(der_rows, out_dir / "04015.stair.der.hex")
    write_hex(sp_rows, out_dir / "04015.stair.sp.hex")
    write_hex(delta_rows, out_dir / "04015.stair.delta.hex")
    write_hex(sflag_rows, out_dir / "04015.stair.flag.hex")
    # how many of these simulated pairs the forbidden shift route gets wrong, and the
    # same for the float route, so the testbench compares against a golden count
    g_shift_sim = 0
    g_float_sim = 0
    for (s, sp) in grid_pairs_list:
        cross_row = 2 * s < sp
        if cross_row != (s < (sp >> 1)):
            g_shift_sim += 1
        if cross_row != (s < sp / 2.0):
            g_float_sim += 1
    # A sampled position gets a verdict when the accepted word that carries its candidate
    # still has the rest of the pipeline behind it: the window completes at p + setengah, the
    # serializer then needs SCAN_CYC = 10 accepted words and the verdict stage one more, so
    # p + setengah + 1 + 10 + 1 = p + 30 must still be inside the line. The accepted word
    # index equals the sample index, and the testbench measures the same 30 accepted words.
    sint_usable = sum(1 for p in s_pos if p + setengah + 1 + 10 + 1 <= SINT_WORDS - 1)
    counts = (frames, n_peak, int(np.count_nonzero(pos + setengah <= frames - 1)),
              SINT_WORDS, len(s_pos), n_grid, n_edge, len(der_rows),
              g_shift_sim, g_float_sim, sint_usable)
    write_hex(counts, out_dir / "04015.fase7.counts.hex")

    # the frozen Fase 0 column is COPIED so that one +VECTOR directory holds everything the
    # testbench reads. The copy must be byte identical to the frozen source.
    src = (FASE0 / "04015.turunan.hex").read_bytes()
    (out_dir / "04015.turunan.hex").write_bytes(src)
    copy_ok = sha256_of(out_dir / "04015.turunan.hex") == hashlib.sha256(src).hexdigest()
    print("turunan.hex copy identical to the frozen column: %s" % copy_ok)
    if not copy_ok:
        return 2

    files = {}
    for p in sorted(out_dir.glob("04015.*")):
        if p.name == "04015.fase7.manifest.json":
            continue
        files[p.name] = {"bytes": p.stat().st_size, "sha256": sha256_of(p)}
    manifest = {
        "generator": "rtl/tb/vektor/fase7/siapkan_vektor_fase7.py",
        "phase": 7,
        "rate_hz": 250.0,
        "word_format": "one 32 bit word per line, 8 hex digits, two's complement, no comments",
        "sources": {
            "rantai.py": {"path": str(MODEL), "sha256": sha_model, "role": "frozen behaviour"},
            "04015.turunan.hex": {"path": str(FASE0 / "04015.turunan.hex"),
                                  "sha256": sha256_of(FASE0 / "04015.turunan.hex")},
            "04015.peaks.csv": {"path": str(FASE5 / "04015.peaks.csv"),
                                "sha256": sha256_of(FASE5 / "04015.peaks.csv")},
        },
        "counts": dict(zip(COUNTS, counts)),
        "interfaces": {
            "constant": {"SETENGAH_JENDELA": setengah, "window_words": 2 * setengah + 1,
                         "PITA_MS_ATAS": 360, "delta_shift": 2},
            "flag_bits": ["delta_valid", "kem_qrs_valid", "in_band", "t_rejected", "signal",
                          "is_qrs"],
            "stair_flag_bits": ["delta_valid", "kem_qrs_valid", "rule_enable", "exp_in_band",
                                "exp_reject", "grid_row"],
        },
        "checks": {
            "model_kem_vs_csv_slope_mismatches": kem_bad,
            "driven_delta_vs_csv_sample_delta_differ": delta_vs_csv,
            "driven_delta_vs_csv_sample_delta_differ_nonzero": delta_vs_csv_nonzero,
            "in_band_rebuild_mismatches": band_bad,
            "in_band_ones": int(in_band.sum()),
            "t_rejected_rebuild_mismatches": rej_bad,
            "t_rejected_ones": int(t_reject.sum()),
            "signal_ones": int(signal.sum()),
            "is_qrs_ones": int(is_qrs.sum()),
            "real_in_band_pairs_checked": n_checked,
            "real_pairs_cross_vs_shift_differ": shift_pair_diff,
            "real_pairs_cross_vs_float_differ": float_pair_diff,
            "grid_pairs": grid_pairs,
            "grid_cross_vs_float_differ": grid_float,
            "grid_cross_vs_shift_differ": grid_shift,
            "grid_cross_vs_rational_differ_200k": grid_rational,
            "grid_simulated_pairs": n_grid,
            "grid_simulated_cross_vs_shift_differ": g_shift_sim,
            "grid_simulated_cross_vs_float_differ": g_float_sim,
            "synthetic_positions_with_a_verdict": sint_usable,
        },
        "edge_reasons": [e[8] for e in edge],
        "files": files,
    }
    (out_dir / "04015.fase7.manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print("counts:", dict(zip(COUNTS, counts)))
    print("wrote %d files to %s" % (len(files) + 1, out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
