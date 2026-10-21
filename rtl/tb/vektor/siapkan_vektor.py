#!/usr/bin/env python3
"""Fase 2 of the AFIB-LITE RTL plan: build the stimulus column for tb_kuantisasi.sv.

Writes rtl/tb/vektor/04015.stimulus.hex, one 16 bit word per line, 4 hex digits:
  bits 15 to 12  the marker vector, bits 3 to 0 used, in the order of the package
                 (TU_CLAMP 0, TU_GAP 1, TU_WEAK 2, TU_UNSURE 3), which is also the order
                 of adapter.MARKER_ORDER, so the adapter byte is written unchanged
  bits 11 to 0   the 12 bit signed record count, two's complement

Why the stimulus is a count column and not the golden word column: the map from count to
word is 2 to 1 at the rail. 406 words of the golden column are exactly plus or minus
CLAMP_WORD, and only 402 of them were clipped; the other 4 are counts that landed exactly
on the rail (|c| == 1000), where the strict pre clamp test of adapter.py:337 does not fire.
The word column cannot say which is which, so the count column is taken from the record
itself and then proved against the word column, which is the authority for the output.

Gates printed by this script, all of them measured here:
  1 the integer quantiser, rail and round half to even, equals np.rint of the model over
    every count of -4095 to 4095, zero mismatches
  2 the quantiser of every one of the 450000 record counts equals the golden word column,
    zero mismatches, so the stimulus is a pre image of the golden output
  3 the clipped count of the record is 402, the number the Fase 0 manifest records
  4 the weak marker recomputed from the golden word column alone is 8817 words and is
    identical, word for word, to the adapter marker of the same record

Read only: the Fase 0 golden column, the Fase 0 manifest, the frozen model, the record.
Written: the stimulus file next to this script.

Run with:
  /home/avivsabilalm/.venvs/jupyter/bin/python -u siapkan_vektor.py
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]                      # rtl/tb/vektor -> rtl/tb -> rtl -> repo
MODEL = REPO / "model" / "rantai-afib-lite"
FASE0 = pathlib.Path("/home/avivsabilalm/.hermes/cache/scratch/rtlplan2/fase0")
RECORD = pathlib.Path("/home/avivsabilalm/.hermes/cache/scratch/afib/afdb_local/04015")
OUT = HERE / "04015.stimulus.hex"

CLAMP = 2047          # afib_lite_pkg CLAMP_COUNT
SHIFT = 4             # afib_lite_pkg SHIFT_IN
DIV = 1000            # afib_lite_pkg Q_DIVISOR, derived from 5 mV and 200 counts per mV
WEAK_WINDOW = 250     # adapter.WEAK_WINDOW
WEAK_WORD = int(round(0.5 * (2047 / 5.0))) << SHIFT   # adapter.WEAK_WORD, 3280
RAIL = CLAMP << SHIFT
N_MARK = 4


def q_pre(c: int) -> int:
    """Pre clamp value of one count, integer form of rantai.py:163 with rail at 2047."""
    n = c * CLAMP
    q = abs(n) // DIV
    rem = abs(n) - DIV * q
    if rem > DIV // 2:
        q += 1
    elif rem == DIV // 2:
        q += q & 1          # odd goes up, so the even neighbour wins
    return -q if n < 0 else q


def q_word(c: int) -> int:
    """The 16 bit word of one count: clip to the rail, then shift left by SHIFT_IN."""
    p = q_pre(c)
    p = CLAMP if p > CLAMP else (-CLAMP if p < -CLAMP else p)
    return p << SHIFT


def read_hex16(path: pathlib.Path) -> np.ndarray:
    """The exporter writes the 32 bit pattern of a 16 bit word, 8 hex digits per line."""
    raw = np.array([int(x, 16) & 0xFFFF for x in path.read_text().split()], dtype=np.int64)
    return np.where(raw >= 2 ** 15, raw - 2 ** 16, raw)


def weak_mask_from_words(words: np.ndarray) -> np.ndarray:
    """adapter._emit weak rule, recomputed from the word column alone.

    The marker is set when the trailing one second window of the absolute word stays
    below WEAK_WORD, and the window warms up over its first 249 samples.
    """
    absv = np.abs(words)
    out = np.zeros(absv.size, dtype=bool)
    dq = collections.deque()
    for i in range(absv.size):
        while dq and absv[dq[-1]] <= absv[i]:
            dq.pop()
        dq.append(i)
        floor = i - WEAK_WINDOW + 1
        while dq and dq[0] < floor:
            dq.popleft()
        if i >= WEAK_WINDOW - 1 and absv[dq[0]] < WEAK_WORD:
            out[i] = True
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vector", default=str(FASE0 / "04015.masukan16.hex"))
    ap.add_argument("--manifest", default=str(FASE0 / "04015.manifest.json"))
    ap.add_argument("--record", default=str(RECORD))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    fails = 0
    print("vector   : %s" % args.vector)
    print("manifest : %s" % args.manifest)
    print("record   : %s" % args.record)
    print("model    : %s" % MODEL)

    # ---------------------------------------------------------------- gate 1
    print()
    print("gate 1: integer quantiser against np.rint over -4095 to 4095")
    swept = np.arange(-4095, 4096, dtype=np.int64)
    # the model path: mv = count / gain of the record, then rint(mv * GAIN_COUNT), with
    # GAIN_COUNT = (2**11 - 1) / 5, so the whole ratio is 2047 / 1000 per count
    mv = swept.astype(np.float64) / 200.0
    ref = np.rint(mv * ((2 ** 11 - 1) / 5.0)).astype(np.int64)
    ref = np.clip(ref, -CLAMP, CLAMP) << SHIFT
    mine = np.array([q_word(int(c)) for c in swept], dtype=np.int64)
    bad = np.nonzero(ref != mine)[0]
    print("  counts swept          : %d" % swept.size)
    print("  mismatches against np.rint: %d" % bad.size)
    if bad.size:
        fails += 1
        print("  first difference      : count %d" % int(swept[bad[0]]))
    tie = swept[(np.abs(swept * CLAMP) % DIV) == DIV // 2]
    print("  tie counts in 0 to 4095: %s" % tie.tolist())
    for c in tie:
        print("  tie c=%6d pre=%6d word=%6d" % (c, q_pre(int(c)), q_word(int(c))))

    # ---------------------------------------------------------------- golden side
    gold = read_hex16(pathlib.Path(args.vector))
    manifest = json.loads(pathlib.Path(args.manifest).read_text())
    print()
    print("golden words            : %d, min %d max %d"
          % (gold.size, int(gold.min()), int(gold.max())))
    print("golden at the rail      : %d" % int(np.count_nonzero(np.abs(gold) == RAIL)))
    print("manifest frames         : %d, columns %d"
          % (manifest["frames"], len(manifest["columns"])))
    print("manifest markers        : %s" % manifest["adapter_check"]["markers"])

    # ---------------------------------------------------------------- record side
    sys.path.insert(0, str(MODEL))
    import adapter as AD  # noqa: E402

    src = AD.RecordSource(args.record, n_frames=gold.size, channel=0)
    info = src.open()
    counts = src.read_counts(info["used_frames"]).astype(np.int64)
    src.close()
    print()
    print("record %s              : fmt %s, gain %.1f counts per mV, zero %.1f"
          % (info["record"]["name"], info["channel"]["fmt"], info["channel"]["gain"],
             info["channel"]["zero"]))
    print("counts read             : %d, min %d max %d"
          % (counts.size, int(counts.min()), int(counts.max())))
    if (info["channel"]["zero"] != 0.0) or count_at_zero(info["channel"]["gain"]):
        print("  note: the count of the RTL is c = count - zero, this header has zero 0")
    if int(counts.min()) < -2048 or int(counts.max()) > 2047:
        fails += 1
        print("  FAIL the record count does not fit 12 bit signed")

    # ---------------------------------------------------------------- gate 2
    print()
    print("gate 2: the quantiser of every record count against the golden column")
    words = np.array([q_word(int(c)) for c in counts], dtype=np.int64)
    bad = np.nonzero(words != gold)[0]
    print("  words compared        : %d" % words.size)
    print("  mismatches            : %d" % bad.size)
    if bad.size:
        fails += 1
        print("  first difference      : index %d" % int(bad[0]))

    # ---------------------------------------------------------------- gate 3
    n = counts * CLAMP
    clipped = np.abs(n) // DIV > CLAMP
    exactly = (np.abs(n) // DIV == CLAMP) & ((np.abs(n) % DIV) == 0)
    print()
    print("gate 3: the clamp census of the record")
    print("  clipped, strict pre test  : %d" % int(clipped.sum()))
    print("  exactly on the rail       : %d" % int(exactly.sum()))
    print("  counts with |c| == 1000   : %d" % int(np.count_nonzero(np.abs(counts) == 1000)))
    print("  manifest clamp marker     : %d" % manifest["adapter_check"]["markers"]["clamp"])
    print("  rail words of the column  : %d" % int(np.count_nonzero(np.abs(gold) == RAIL)))
    print("  rail words minus clipped  : %d"
          % (int(np.count_nonzero(np.abs(gold) == RAIL)) - int(clipped.sum())))
    if int(clipped.sum()) != int(manifest["adapter_check"]["markers"]["clamp"]):
        fails += 1
        print("  FAIL the clipped count does not match the manifest clamp marker")

    # ---------------------------------------------------------------- gate 4
    a = AD.DatasetBulk(args.record, n_frames=gold.size, channel=0)
    a.open()
    idx, value16, mark = a.series(chunk=a.DEFAULT_CHUNK)
    markers = a.markers()
    a.close()
    mark = np.asarray(mark).astype(np.int64)
    weak_col = weak_mask_from_words(gold)
    weak_ada = (mark & 4).astype(bool)
    print()
    print("gate 4: the weak marker, recomputed from the word column alone")
    print("  weak from the word column : %d" % int(weak_col.sum()))
    print("  weak from adapter markers : %d" % int(weak_ada.sum()))
    print("  manifest weak marker      : %d" % manifest["adapter_check"]["markers"]["weak"])
    print("  the two masks are equal   : %s" % bool(np.array_equal(weak_col, weak_ada)))
    if not np.array_equal(weak_col, weak_ada):
        fails += 1
        print("  FAIL the weak marker is not a function of the word column")
    if int(weak_col.sum()) != int(manifest["adapter_check"]["markers"]["weak"]):
        fails += 1
        print("  FAIL the weak count does not match the manifest")

    # ---------------------------------------------------------------- stimulus
    # The adapter marker byte is written unchanged: its bit order is the package order.
    stim = ((mark & 0xF) << 12) | (counts & 0xFFF)
    out_path = pathlib.Path(args.out)
    text = "\n".join("%04X" % int(v) for v in stim) + "\n"
    out_path.write_text(text)
    print()
    print("stimulus written        : %s" % out_path)
    print("  lines                 : %d" % stim.size)
    print("  bytes                 : %d" % len(text))
    print("  format                : 4 hex digits, marker nibble then 12 bit count")
    print("  markers written       : %s"
          % {k: int(np.count_nonzero(mark & m))
             for m, k in ((1, "clamp"), (2, "gap"), (4, "weak"), (8, "uncertain"))})

    print()
    if fails:
        print("gate: FAIL, %d gate(s) failed" % fails)
        return 1
    print("gate: PASS, the stimulus reproduces the golden column and its censuses")
    return 0


def count_at_zero(gain: float) -> bool:
    """True when the record gain is the WFDB default, which is what makes Q_DIVISOR 1000."""
    return abs(float(gain) - 200.0) < 1e-9


if __name__ == "__main__":
    raise SystemExit(main())
