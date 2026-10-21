#!/usr/bin/env python3
"""Fase 8 golden vector export into rtl/tb/vektor/fase8/.

Read only outside this directory. Sources:
  rtlplan2/fase5/04015.rr.csv            2595 raw intervals with their four marks
  rtlplan2/fase5/04015.windows.csv       602 golden windows, MARKED arm, 210 columns
  rtlplan2/fase5/04015.decisions.csv     588 golden windows, RAW arm
  model/rantai-afib-lite/fixture/04015_30m.npz   jendela_fitur (588,4) float, RAW arm

Every node of this layer is reproduced here in the exact integer form of rtl/features.sv, so
the manifest can state, node by node, how far the implemented form is from the golden column:

  sum_d2  = sum of 31 squared differences, exact
  mean31  = (sum_d2 * 17318417) >> 29, the plan's constant verbatim, with the negative
            remainder fold-back that the rounded constant makes necessary, plus the exact
            fraction table FRAC[rem] = round_half_even(rem*256/31).  Q19.8.
  R       = isqrt((sum_d2 * 31) << 24) = floor(rmssd * 256 * 496), the digit root, floor.
  rmssd   = round_half_even(R, 496)                     Q10.8 code
  ratio   = round_half_even(R << 9, 31 * sum_rr)         Q1.16 code
  cnt50   = #{|d_k| > 50}, exact
  pnn50   = PNN[cnt50] = round_half_even(cnt50*256, 31)  Q1.8 code
  core    = sort(rr)[8:24], span = max - min
  bins[k] = A[k] - A[k+1], A[k] = #{v : 16*(v - min) >= k*span}, A[0] = 16, A[16] = 0,
            the exact cross product, last edge inclusive
  ent     = round_half_even(sum over the 16 bins of TERM[c], 2**34)   Q1.14 code
            TERM[c] = round_half_even(c*(4 - log2 c)/64 * 2**48), log2 carried with 24
            fraction bits.

The class filter of rantai.py:818 is NOT applied here or in the RTL (no port for the label):
one window is emitted per stride position that passes the range gate 200 <= min(rr) and
max(rr) <= 3000. The map files carry the bridge to the golden rows.

OUTPUT FORMAT: every file is a sequence of 32 bit words, exactly 8 hex digits each, one word
per line, no comments, $readmemh compatible, unsigned (no word is ever read as signed):

  04015.fase8.rr.hex         2595 words   {2 zero, mark[1:0], rr_ms[15:0]}
  04015.fase8.sample.hex     2595 words   qrs_cur_sample of the interval
  04015.fase8.gold.d.hex     602*31 words d & 0x1FFF, row major, 13 bit two's complement
  04015.fase8.gold.bins.hex  602*4 words  word 4r+j holds bins 4j..4j+3, bin 4j in bits 7:0
  04015.fase8.gold.code.hex  602*3 words  per row: high, middle, low of the 92 bit code word
  04015.fase8.gold.raw.hex   588*3 words  the same layout for the raw arm, cnt50/mean31 zero
  04015.fase8.map.marked.hex 638*2 words  sample_end, golden row of windows.csv or FFFFFFFF
  04015.fase8.map.raw.hex    624*2 words  sample_end, golden row of decisions.csv or FFFFFFFF
  04015.fase8.manifest.json  counts, rules, the node error table against the golden columns,
                             and the sha256 of every file above
  04015.fase8.tables.txt     the three lookup tables and every constant, for the RTL header

The code word, 92 bits, bit 0 at the right (V[17:0] = rmssd, then ratio, ent, mean31, cnt50,
pnn50 in that order):
  V[17:0]   rmssd code, 18 bits
  V[34:18]  ratio code, 17 bits
  V[49:35]  ent code,   15 bits
  V[76:50]  mean31 code,27 bits
  V[82:77]  cnt50,       6 bits
  V[91:83]  pnn50 code,  9 bits
and the three words are V[95:64], V[63:32], V[31:0] in that order on the line.
"""
import csv
import hashlib
import json
import math
import pathlib
import sys

import numpy as np

REPO = pathlib.Path("/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite")
F5 = REPO / "rtlplan2" / "fase5"
OUT = REPO / "rtl" / "tb" / "vektor" / "fase8"
FIXTURE = REPO / "model" / "rantai-afib-lite" / "fixture" / "04015_30m.npz"

W_BEATS = 32
STRIDE = 4
RR_MIN_MS = 200
RR_MAX_MS = 3000
C31 = 17318417        # round(2**29 / 31), the plan's constant
SH31 = 29             # (sum_d2 * C31) >> 29
LOG2_Q = 24           # log2 table fraction bits, the derivation table only
TERM_Q = 48           # entropy term fraction bits of ent4
ENT_SHIFT = TERM_Q - 14
W_TERM = 48
FIELDS = (("rmssd", 18), ("ratio", 17), ("ent", 15), ("mean_q", 27), ("cnt50", 6), ("pnn50", 9))


def rhe_ratio(num, den):
    """round half to even of num / den, both positive integers"""
    q, rem = divmod(num, den)
    twice = 2 * rem
    if twice > den:
        q += 1
    elif twice == den:
        q += q % 2
    return q


def rhe_float(x, p):
    """round half to even of x * 2**p, x a float"""
    scaled = float(x) * (2.0 ** p)
    f = math.floor(scaled)
    frac = scaled - f
    q = int(f)
    if frac > 0.5:
        q += 1
    elif frac == 0.5:
        q += q % 2
    return q


def isqrt(n):
    r = math.isqrt(int(n))
    assert r * r <= n < (r + 1) * (r + 1)
    return r


# ------------------------------------------------------------------ lookup tables
LOG2T = [0] + [rhe_float(math.log2(c), LOG2_Q) for c in range(1, 17)]
TERM = [0] * 17
for c in range(1, 17):
    TERM[c] = rhe_ratio(c * (4 * (2 ** LOG2_Q) - LOG2T[c]) * (2 ** TERM_Q),
                        (2 ** LOG2_Q) * 64)
FRAC = [rhe_ratio(r * 256, 31) for r in range(32)]
PNN = [rhe_ratio(c * 256, 31) for c in range(32)]


def features(rr):
    """Every node of rtl/features.sv, in the exact integer form the RTL implements."""
    d = np.diff(rr)
    sum2 = int((d * d).sum())
    sum_rr = int(rr.sum())
    # step 3: the plan's constant, the fold-back, then the exact fraction table
    q0 = (sum2 * C31) >> SH31
    rem6 = (sum2 - 31 * q0) & 63
    if rem6 > 31:
        rem6 -= 33
        q0 -= 1
    mean_q = (q0 << 8) + FRAC[rem6]
    mean_q = min(mean_q, (1 << 27) - 1)
    # step 4: the digit root is isqrt, and the code rounds R/496 to even
    R = isqrt((sum2 * 31) << 24)
    rmssd = min(rhe_ratio(R, 496), (1 << 18) - 1)
    # step 9: numerator R << 9 over 31 * sum_rr, one final round half to even
    ratio = min(rhe_ratio(R << 9, 31 * sum_rr), (1 << 17) - 1)
    cnt50 = int(np.sum(np.abs(d) > 50))
    # step 6 and 7: the sorted core and the exact cross product histogram
    s = np.sort(rr)
    core = s[8:-8]
    mn, mx = int(core.min()), int(core.max())
    span = mx - mn
    cnt_core = 16
    acnt = [cnt_core] * 17
    for k in range(1, 16):
        thr = k * span
        acnt[k] = sum(1 for v in core if 16 * (int(v) - mn) >= thr)
    acnt[16] = 0
    bins = [acnt[k] - acnt[k + 1] for k in range(16)]
    # step 8: the folded entropy term table, one final round half to even
    ent = min(rhe_ratio(sum(TERM[c] for c in bins), 1 << ENT_SHIFT), (1 << 15) - 1)
    return dict(d=d, sum2=sum2, sum_rr=sum_rr, mean_q=mean_q, R=R, rmssd=rmssd,
                ratio=ratio, cnt50=cnt50, pnn50=PNN[cnt50], bins=bins, ent=ent)


def code_word(f):
    v = 0
    shift = 0
    for name, width in FIELDS:
        v |= (f[name] & ((1 << width) - 1)) << shift
        shift += width
    return v


def code_row(f, fields):
    v = 0
    shift = 0
    for name, width in fields:
        v |= (int(f[name]) & ((1 << width) - 1)) << shift
        shift += width
    return v


def scan(rr_series, sample_of):
    """The frozen window scan without the label filter, which the RTL has no input for."""
    n = rr_series.size
    em = []
    rej = 0
    for i in range(0, n - W_BEATS, STRIDE):
        seg = rr_series[i:i + W_BEATS]
        if seg.min() < RR_MIN_MS or seg.max() > RR_MAX_MS:
            rej += 1
            continue
        em.append((i, sample_of(i + W_BEATS - 1), features(seg)))
    return em, rej


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rr_rows = list(csv.DictReader(open(F5 / "04015.rr.csv")))
    rr_all = np.array([int(r["rr_ms"]) for r in rr_rows], dtype=np.int64)
    mark = np.array([int(r["mark"]) for r in rr_rows], dtype=np.int64)
    sample = np.array([int(r["qrs_cur_sample"]) for r in rr_rows], dtype=np.int64)
    gold = list(csv.DictReader(open(F5 / "04015.windows.csv")))
    dec_raw = list(csv.DictReader(open(F5 / "04015.decisions.csv")))
    fix = np.load(FIXTURE)
    jf = np.asarray(fix["jendela_fitur"], float)

    # the marked series, exactly rantai.seri_berpenanda: marks 0 and 1 survive whole
    keep = (mark == 0) | (mark == 1)
    src = np.flatnonzero(keep)
    rr_marked = rr_all[src]
    sample_marked = sample[src]

    # ------------------------------------------------------------------ arm A, marked
    em_a, rej_a = scan(rr_marked, lambda k: int(sample_marked[k]))
    rows_by_start = {int(g["src_start"]): k for k, g in enumerate(gold)}
    map_a = []
    hit = {}
    for i, s_end, f in em_a:
        r = rows_by_start.get(i, -1)
        if r >= 0:
            hit[r] = hit.get(r, 0) + 1
        map_a.append((s_end, r))
    assert len(hit) == len(gold), (len(hit), len(gold))
    assert all(v == 1 for v in hit.values()), "a golden row was mapped twice"

    # ------------------------------------------------------------------ arm B, raw
    em_b, rej_b = scan(rr_all, lambda k: int(sample[k]))
    dec_by_start = {int(r["src_start"]): k for k, r in enumerate(dec_raw)}
    map_b = []
    hitb = {}
    for i, s_end, f in em_b:
        r = dec_by_start.get(i, -1)
        if r >= 0:
            hitb[r] = hitb.get(r, 0) + 1
        map_b.append((s_end, r))
    assert len(hitb) == len(dec_raw), (len(hitb), len(dec_raw))
    assert all(v == 1 for v in hitb.values()), "a raw golden row was mapped twice"

    # ------------------------------------------------------------------ error tables
    # every golden column is compared with the RTL form of the same node
    bad = dict(d=0, bins=0, cnt50=0, pnn50=0, rmssd=0, ratio=0, ent=0, mean_q=0)
    over = dict(rmssd=0, ratio=0, ent=0, mean_q=0)
    worst = dict(rmssd=0, ratio=0, ent=0, mean_q=0)
    for i, s_end, f in em_a:
        r = rows_by_start.get(i, -1)
        if r < 0:
            continue
        g = gold[r]
        gd = np.array([int(g["d_%02d" % k]) for k in range(31)], dtype=np.int64)
        if not np.array_equal(f["d"], gd):
            bad["d"] += 1
        if f["bins"] != [int(g["bin_%02d" % k]) for k in range(16)]:
            bad["bins"] += 1
        if f["cnt50"] != int(g["cnt_gt50"]):
            bad["cnt50"] += 1
        if f["pnn50"] != rhe_float(float(g["pnn50"]), 8):
            bad["pnn50"] += 1
        for key, col, p in (("rmssd", "rmssd", 8), ("ratio", "ratio", 16),
                            ("ent", "ent4", 14), ("mean_q", "mean31", 8)):
            e = abs(f[key] - rhe_float(float(g[col]), p))
            worst[key] = max(worst[key], e)
            if e:
                bad[key] += 1
            if e > 1:
                over[key] += 1

    raw_over = 0
    raw_worst = dict(rmssd=0, ratio=0, ent=0, pnn50=0)
    for i, s_end, f in em_b:
        r = dec_by_start.get(i, -1)
        if r < 0:
            continue
        g = jf[r]
        e = dict(rmssd=abs(f["rmssd"] - rhe_float(g[0], 8)),
                 ratio=abs(f["ratio"] - rhe_float(g[1], 16)),
                 pnn50=abs(f["pnn50"] - rhe_float(g[2], 8)),
                 ent=abs(f["ent"] - rhe_float(g[3], 14)))
        for k in e:
            raw_worst[k] = max(raw_worst[k], e[k])
        if any(v > 1 for v in e.values()):
            raw_over += 1

    # ------------------------------------------------------------------ the vector files
    with open(OUT / "04015.fase8.rr.hex", "w") as fh:
        for i in range(rr_all.size):
            fh.write("%08X\n" % ((int(mark[i]) << 16) | int(rr_all[i])))
    with open(OUT / "04015.fase8.sample.hex", "w") as fh:
        for i in range(sample.size):
            fh.write("%08X\n" % int(sample[i]))

    with open(OUT / "04015.fase8.gold.d.hex", "w") as fh:
        for g in gold:
            for k in range(31):
                fh.write("%08X\n" % (int(g["d_%02d" % k]) & 0x1FFF))
    with open(OUT / "04015.fase8.gold.bins.hex", "w") as fh:
        for g in gold:
            b = [int(g["bin_%02d" % k]) for k in range(16)]
            for j in range(4):
                w = (b[4 * j] & 0xFF) | ((b[4 * j + 1] & 0xFF) << 8) | \
                    ((b[4 * j + 2] & 0xFF) << 16) | ((b[4 * j + 3] & 0xFF) << 24)
                fh.write("%08X\n" % w)

    def write_code(fh, f, fields):
        v = code_row(f, fields)
        fh.write("%08X\n" % ((v >> 64) & 0xFFFFFFFF))
        fh.write("%08X\n" % ((v >> 32) & 0xFFFFFFFF))
        fh.write("%08X\n" % (v & 0xFFFFFFFF))

    with open(OUT / "04015.fase8.gold.code.hex", "w") as fh:
        for r, g in enumerate(gold):
            rr = np.array([int(g["rr_%02d" % k]) for k in range(32)], dtype=np.int64)
            f = features(rr)
            gc = dict(rmssd=rhe_float(float(g["rmssd"]), 8),
                      ratio=rhe_float(float(g["ratio"]), 16),
                      ent=rhe_float(float(g["ent4"]), 14),
                      mean_q=rhe_float(float(g["mean31"]), 8),
                      cnt50=int(g["cnt_gt50"]),
                      pnn50=rhe_float(float(g["pnn50"]), 8))
            # the golden code row is the golden column, not my own arithmetic; the assert
            # below fails the run if the implemented form and the golden column disagree
            assert (gc["rmssd"], gc["ratio"], gc["ent"], gc["mean_q"]) == \
                   (f["rmssd"], f["ratio"], f["ent"], f["mean_q"]), (r, gc, f)
            write_code(fh, gc, FIELDS)
    with open(OUT / "04015.fase8.gold.raw.hex", "w") as fh:
        for r in range(len(dec_raw)):
            g = jf[r]
            write_code(fh, dict(rmssd=rhe_float(g[0], 8), ratio=rhe_float(g[1], 16),
                                ent=rhe_float(g[3], 14), mean_q=0, cnt50=0,
                                pnn50=rhe_float(g[2], 8)),
                       FIELDS)

    with open(OUT / "04015.fase8.map.marked.hex", "w") as fh:
        for se, r in map_a:
            fh.write("%08X\n%08X\n" % (se & 0xFFFFFFFF, r & 0xFFFFFFFF))
    with open(OUT / "04015.fase8.map.raw.hex", "w") as fh:
        for se, r in map_b:
            fh.write("%08X\n%08X\n" % (se & 0xFFFFFFFF, r & 0xFFFFFFFF))

    tables = []
    tables.append("log2 table, Q%d, index 0..16 (index 0 unused):" % LOG2_Q)
    tables.append("  " + ", ".join(str(v) for v in LOG2T))
    tables.append("entropy term table, units of 2**-%d of ent4, index 0..16:" % TERM_Q)
    tables.append("  " + ", ".join(str(v) for v in TERM))
    tables.append("entropy final shift: sum >> %d with round half to even" % ENT_SHIFT)
    tables.append("pNN50 code table, Q1.8, index 0..31:")
    tables.append("  " + ", ".join(str(v) for v in PNN))
    tables.append("fraction table for /31, index 0..31:")
    tables.append("  " + ", ".join(str(v) for v in FRAC))
    tables.append("mean31 constant C31 = %d, shift %d" % (C31, SH31))
    tables.append("root input shift 24, radicand width 58, digit root steps 29")
    tables.append("divider: pass 1 divide R by 496 in 29 steps, pass 2 divide R<<9 by "
                  "31*sum_rr in 38 steps")
    (OUT / "04015.fase8.tables.txt").write_text("\n".join(tables) + "\n")

    files = sorted(p.name for p in OUT.glob("04015.fase8.*"))
    manifest = {
        "record": "04015",
        "phase": "fase8",
        "generator": str(pathlib.Path(__file__).resolve()),
        "frozen_model_sha256": "90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5",
        "sources": {
            "rr_csv": str(F5 / "04015.rr.csv"),
            "windows_csv": str(F5 / "04015.windows.csv"),
            "decisions_csv": str(F5 / "04015.decisions.csv"),
            "fixture_npz": str(FIXTURE),
        },
        "counts": {
            "intervals_raw": int(rr_all.size),
            "intervals_marked": int(rr_marked.size),
            "emissions_marked": len(em_a),
            "emissions_raw": len(em_b),
            "golden_marked": len(gold),
            "golden_raw": len(dec_raw),
            "rejected_marked": rej_a,
            "rejected_raw": rej_b,
        },
        "rules": {
            "mean31": "RTL form: q0 = (sum_d2 * %d) >> %d, negative remainder folded back, "
                      "fraction from FRAC[rem], Q19.8" % (C31, SH31),
            "root": "digit root floor of (sum_d2 * 31) << 24, 29 steps, then round half to "
                    "even of R/496",
            "ratio": "R << 9 over 31*sum_rr truncating, then one round half to even stage, "
                     "17 bits with saturation",
            "entropy": "folded term table, log2 with %d fraction bits, term with %d, final "
                       "round half to even on >> %d" % (LOG2_Q, TERM_Q, ENT_SHIFT),
            "histogram": "exact cross product 16*x >= k*span, last bin inclusive, counted as "
                         "A[k] - A[k+1]",
            "pnn50": "31 comparators, then a 32 entry Q1.8 table",
            "class_filter": "not applied, no port for the rhythm label",
        },
        "node_error_vs_golden_marked": {
            "d_rows_differing": bad["d"],
            "bin_rows_differing": bad["bins"],
            "cnt50_rows_differing": bad["cnt50"],
            "pnn50_rows_differing": bad["pnn50"],
            "code_rows_differing": dict(rmssd=bad["rmssd"], ratio=bad["ratio"],
                                        ent=bad["ent"], mean_q=bad["mean_q"]),
            "code_rows_over_1_lsb": over,
            "code_worst_lsb": worst,
        },
        "node_error_vs_fixture_raw": {
            "rows": len(dec_raw),
            "rows_over_1_lsb": raw_over,
            "worst_lsb": raw_worst,
        },
        "files_sha256": {name: sha(OUT / name) for name in files},
    }
    (OUT / "04015.fase8.manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")

    print("== fase 8 vector export ==")
    print("intervals raw/marked      :", rr_all.size, rr_marked.size)
    print("emissions raw/marked      :", len(em_b), len(em_a))
    print("golden rows raw/marked    :", len(dec_raw), len(gold))
    print("rejections raw/marked     :", rej_b, rej_a)
    print("marked  d/bin/cnt/pnn dif :", bad["d"], bad["bins"], bad["cnt50"], bad["pnn50"])
    print("marked  code differ       :", {k: bad[k] for k in ("rmssd", "ratio", "ent", "mean_q")})
    print("marked  code over 1 LSB   :", over)
    print("marked  code worst LSB    :", worst)
    print("raw     over 1 LSB / worst:", raw_over, raw_worst)
    print("files                     :", len(files))
    for name in files:
        print("  %s  %s" % (manifest["files_sha256"][name], name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
