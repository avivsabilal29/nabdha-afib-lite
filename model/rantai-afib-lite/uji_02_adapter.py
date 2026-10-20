#!/usr/bin/env python3
"""AFIB-LITE phase 6 step S2 gate: the four adapters against the frozen fixture.

One line per check. Every number printed here comes from a real run of this file, and a
check that cannot be met is printed as FAIL with its measured numbers, not hidden.

What is real and what is synthetic is labelled on every line that touches the Attys paths:
the recording and its locked 16 bit words are real, the 24 bit frames, the front end
ladder, the noise, the rate variants and the packet gap table are synthetic, and the live
Bluetooth wiring is written but not exercised, because there is no device here and
pyattyscomm is not installed.

Run it with the project interpreter:

    cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/uji_02_adapter.py
"""

from __future__ import annotations

import hashlib
import pathlib
import sys
import time

import numpy as np
import wfdb

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import adapter as A
import rantai as R
import simulator_attys as S

NPZ = HERE / "fixture" / "04015_30m.npz"
NPZ_SHA256 = "91ff408fb1b7880a124d28bcc4205038935d4a3a2dbabb4c0f7d161d89e8ac4d"
REC = pathlib.Path("/home/avivsabilalm/.hermes/cache/scratch/afib/afdb_local/04015")
FRAMES = 450_000
SESSIONS = HERE / "fixture" / "attys"
CORE_ARRAYS = ("masukan16", "lp", "hp", "turunan", "kuadrat", "jendela", "puncak",
               "qrs", "rr", "rr_average1", "rr_average2", "rr_antre_panjang", "penanda",
               "rr_disemai", "rr_riwayat_panjang", "rr_menyala_akhir",
               "ambang_kemiringan_puncak", "ambang_puncak_terfilter", "ambang_state",
               "rasio_pita", "rasio_qrs")

RESULTS = []


def baris(ok, name, detail=""):
    """One result line, and the count of failures."""
    RESULTS.append(bool(ok))
    print("[%2d] %s  %-58s %s" % (len(RESULTS), "PASS" if ok else "FAIL", name, detail),
          flush=True)
    return ok


def info(name, detail):
    print("     INFO  %-58s %s" % (name, detail), flush=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(idx, val, mark):
    """One hash of a three series record, for the repeatability check."""
    h = hashlib.sha256()
    for arr in (idx, val, mark):
        h.update(np.ascontiguousarray(arr, dtype=np.int64).tobytes())
    return h.hexdigest()


def n_diff(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape:
        return -1
    return int(np.count_nonzero(a != b))


def differing(res_a, res_b, keys=None):
    """Keys whose arrays differ between two core runs, shape mismatch included."""
    keys = keys if keys is not None else [k for k in res_a if k in res_b]
    bad = []
    for k in keys:
        a, b = np.asarray(res_a[k]), np.asarray(res_b[k])
        if a.shape != b.shape or not np.array_equal(a, b):
            bad.append(k)
    return bad


def run_core(adapter, chunk=None):
    """Drive one fresh core over one adapter. Returns (result dict, n, seconds)."""
    chain = R.Rantai(semai_aktif=True, aturan_t=True, besaran="turunan")
    t0 = time.time()
    n, _t = adapter.drive(chain, chunk)
    return chain.hasil(), n, time.time() - t0


def dataset_bulk():
    a = A.DatasetBulk(REC, FRAMES)
    a.open()
    return a


def dataset_stream(n=None, pacing=False):
    a = A.DatasetStream(REC, FRAMES if n is None else n, pacing=pacing)
    a.open()
    return a


def attys_bulk(path):
    a = A.AttysBulk(path)
    a.open()
    return a


def attys_stream(rate, frames, block_frames=1024, gap_table=()):
    a = A.AttysStream(block_source=S.BlockFeeder(frames, block_frames=block_frames,
                                                 gap_table=gap_table),
                      device_rate_hz=rate)
    a.open()
    return a


def inverse_ok(words):
    """Every word through the millivolt inverse and back through the locked convention.

    This is exactly what an adapter hands the core, so it is checked on the whole series.
    """
    bad = []
    for i, w in enumerate(words):
        mv = (int(w) >> R.GESER_KIRI) / R.GAIN_COUNT
        back, _s, _r = R.kuantisasi(mv)
        if back != int(w):
            bad.append(i)
    return bad


def main():
    t_start = time.time()
    print("S2 gate, four adapters over one interface, against the frozen fixture")
    print("fixture    :", NPZ)
    print("recording  :", REC)
    print("interpreter:", sys.executable)
    print()

    d = np.load(NPZ)
    masukan16 = d["masukan16"]
    frozen_keys = sorted(d.files)

    # ------------------------------------------------------------------ stage 0, the fixture
    print("stage 0, the frozen fixture is not touched")
    got = sha256_file(NPZ)
    baris(got == NPZ_SHA256, "fixture sha256 is the frozen hash", got[:16] + " ...")
    baris(masukan16.size == FRAMES, "fixture masukan16 carries %d words" % FRAMES,
          "shape %s dtype %s" % (masukan16.shape, masukan16.dtype))
    rail16 = R.CLAMP << R.GESER_KIRI
    baris(int(np.abs(masukan16).max()) == rail16,
          "fixture masukan16 tops out at the locked clamp word",
          "max |word| %d, clamp word %d" % (int(np.abs(masukan16).max()), rail16))
    baris(int(np.count_nonzero(masukan16 % (1 << R.GESER_KIRI))) == 0,
          "every fixture word is the locked count times sixteen",
          "remainders present %s" % (sorted(set((masukan16 % 16).tolist())),))
    marker_like = [k for k in frozen_keys if "mark" in k.lower()]
    baris(len(frozen_keys) == 33 and not marker_like,
          "no adapter marker array in the fixture",
          "%d arrays, the only penanda is the chain RR gate of %d entries"
          % (len(frozen_keys), int(d["penanda"].size)))

    # ------------------------------------------------------------------ stage 1, the dataset
    print()
    print("stage 1, the two dataset paths over one source")
    bulk = dataset_bulk()
    rate_bulk = bulk.rate_hz
    t0 = time.time()
    bi, bv, bm = bulk.series()
    t_bulk = time.time() - t0
    baris(rate_bulk == R.FS_HZ, "DatasetBulk declares the rate once, at open",
          "%r Hz, the header says %r Hz" % (rate_bulk, bulk.info["record"]["fs"]))
    info("DatasetBulk format detection",
         "format %s, gain %g counts per mV, zero %g, resolution %d bits, %s"
         % (bulk.info["channel"]["fmt"], bulk.info["channel"]["gain"],
            bulk.info["channel"]["zero"], bulk.info["channel"]["res"],
            bulk.info["channel"]["desc"]))
    info("DatasetBulk read shape",
         "declared %d frames, available %d, used %d, frame %d bytes"
         % (bulk.info["declared_frames"], bulk.info["available_frames"],
            bulk.info["used_frames"], bulk.info["frame_bytes"]))
    baris(bv.size == FRAMES, "DatasetBulk emits one record per frame",
          "%d records in %.1f s" % (bv.size, t_bulk))
    baris(bi.size == FRAMES and np.array_equal(bi, np.arange(FRAMES, dtype=np.int64)),
          "the index is the monotone sample counter, not a clock",
          "index 0 to %d, strictly increasing by one" % (int(bi[-1]) if bi.size else -1))
    bad = n_diff(bv, masukan16) if bv.size == masukan16.size else -1
    baris(bad == 0, "DatasetBulk value16 equals fixture masukan16 elementwise",
          "%d of %d words differ" % (bad, FRAMES))

    # the clamp marker, measured against a source the adapter does not use
    raw = wfdb.rdrecord(str(REC), sampto=FRAMES, physical=False)
    mv_ref = raw.d_signal[:, 0].astype(float) / raw.adc_gain[0]
    pre_ref = np.rint(mv_ref * R.GAIN_COUNT).astype(np.int64)
    clamp_idx = np.flatnonzero(np.abs(pre_ref) > R.CLAMP)
    rail_idx = np.flatnonzero(np.abs(masukan16) >= rail16)
    marker_clamp = np.flatnonzero(bm & A.MARKER_CLAMP)
    baris(clamp_idx.size == 402, "the clipped samples number 402 on the source",
          "%d samples whose rounded count is strictly beyond %d"
          % (clamp_idx.size, R.CLAMP))
    baris(np.array_equal(marker_clamp, clamp_idx),
          "the clamp marker lights on exactly those indices",
          "marker %d indices, source %d indices, symmetric difference %d"
          % (marker_clamp.size, clamp_idx.size,
             np.setxor1d(marker_clamp, clamp_idx).size))
    print("     clamp index count   :", int(clamp_idx.size))
    text = [str(int(i)) for i in clamp_idx]
    for k in range(0, len(text), 20):
        print("     clamp indices %4d  : %s" % (k, ", ".join(text[k:k + 20])))
    baris(rail_idx.size == 406, "the word series alone would claim 406, the marker says 402",
          "%d samples sit on the rail word, the %d that landed exactly on %d are not "
          "clipped and the marker keeps them out"
          % (rail_idx.size, rail_idx.size - clamp_idx.size, R.CLAMP))
    info("markers, dataset bulk", "%s" % (bulk.markers(),))

    stream = dataset_stream()
    t0 = time.time()
    si, sv, sm = stream.series()
    t_stream = time.time() - t0
    baris(si.size == bi.size and np.array_equal(si, bi),
          "DatasetStream index series equals the DatasetBulk index series",
          "%d records, %.1f s per sample replay against %.1f s one bulk block"
          % (si.size, t_stream, t_bulk))
    baris(np.array_equal(sv, bv), "DatasetStream value16 series equals DatasetBulk",
          "%d of %d records differ" % (n_diff(sv, bv), FRAMES))
    baris(np.array_equal(sm, bm), "DatasetStream marker series equals DatasetBulk",
          "%d of %d records differ" % (n_diff(sm, bm), FRAMES))
    info("markers, dataset stream", "%s" % (stream.markers(),))

    fp_a = fingerprint(bi, bv, bm)
    stream2 = dataset_stream()
    si2, sv2, sm2 = stream2.series()
    baris(fingerprint(si2, sv2, sm2) == fp_a, "a second run repeats the same fingerprint",
          fp_a[:32])

    short = dataset_stream(300)
    ia, va, ma = short.series()
    paced = dataset_stream(300, pacing=True)
    t0 = time.time()
    ip, vp, mp = paced.series()
    t_paced = time.time() - t0
    baris(np.array_equal(ip, ia) and np.array_equal(vp, va) and np.array_equal(mp, ma),
          "pacing with the sleep changes nothing but the clock",
          "%d records identical, %.2f s with pacing" % (ia.size, t_paced))

    n_bad_inv = len(inverse_ok(bv))
    baris(n_bad_inv == 0, "the word to millivolt inverse reproduces the same word",
          "%d of %d words come back changed" % (n_bad_inv, FRAMES))

    # ------------------------------------------------------------------ stage 2, the core
    print()
    print("stage 2, the same core over both dataset paths")
    res_bulk, n_bulk, t_bulk_core = run_core(dataset_bulk(), 8192)
    res_stream, n_stream, t_stream_core = run_core(dataset_stream(), 1)
    baris(n_bulk == FRAMES and n_stream == FRAMES,
          "both paths drive the core to completion",
          "%d records, %.1f s with a bulk chunk and %.1f s with a stream chunk"
          % (n_bulk, t_bulk_core, t_stream_core))
    bad = differing(res_bulk, res_stream)
    baris(not bad, "every core array is identical between bulk and stream",
          "%d arrays compared, differing %s" % (len(res_bulk), bad))
    bad = [k for k in CORE_ARRAYS if not np.array_equal(res_bulk[k], d[k])]
    baris(not bad, "the core over the adapter reproduces the S1 fixture arrays",
          "%d arrays compared, differing %s" % (len(CORE_ARRAYS), bad))
    info("core over the dataset path",
         "%d envelope peaks, %d beats, %d RR intervals, %d RR gate on counts"
         % (res_bulk["puncak"].size, res_bulk["qrs"].size, res_bulk["rr"].size,
            int(res_bulk["ambang_state"][7])))

    # ------------------------------------------------------------------ stage 3, the Attys paths
    print()
    print("stage 3, the Attys paths, synthetic frames built from the real recording")
    t0 = time.time()
    sessions = S.build(out_dir=SESSIONS, n_frames=FRAMES, verbose=False)
    cont_path, cont_meta = sessions["continuous"]
    gap_path, gap_meta = sessions["gaps"]
    info("sessions written",
         "%d files under %s in %.1f s" % (len(sessions), SESSIONS, time.time() - t0))
    baris(cont_meta["source_record"] == str(REC),
          "the synthetic frames are built from the frozen recording",
          "%s, %.2f MB, sha256 %s"
          % (cont_path.name, cont_path.stat().st_size / 1e6, cont_meta["sha256"][:16]))
    raw_frames = np.frombuffer(cont_path.read_bytes(), dtype=np.uint8)
    raw_frames = raw_frames.reshape(FRAMES, A.ATTYS_FRAME_BYTES)
    decoded = A.block_words(raw_frames, 0)
    baris(all(A.attys_frame_word(raw_frames[i], 0) == decoded[i]
              for i in range(0, FRAMES, 997)),
          "the vectorized frame decode agrees with the scalar reference",
          "every 997th frame of %d, plus the first, compared" % FRAMES)
    low24 = raw_frames[:, 0].astype(np.int64) | (raw_frames[:, 1].astype(np.int64) << 8) \
        | (raw_frames[:, 2].astype(np.int64) << 16)
    noise = low24 & 0xFF
    baris(int(noise.min()) == 0 and int(noise.max()) == 255,
          "the bottom eight bits of every frame are front end noise",
          "noise byte spans %d to %d, so the top 16 bits are the only signal"
          % (int(noise.min()), int(noise.max())))

    ab = attys_bulk(cont_path)
    ai, av, am = ab.series()
    baris(ai.size == FRAMES, "AttysBulk emits one record per recorded frame",
          "%d records at %g Hz, 6 bytes per frame" % (ai.size, ab.rate_hz))
    bad = n_diff(av, masukan16) if av.size == masukan16.size else -1
    baris(bad == 0,
          "AttysBulk value16 equals the dataset word after the scale alignment",
          "%d of %d differ, the alignment is frame >> %d, ladder %d counts24 per count12"
          % (bad, FRAMES, A.ATTYS_WORD_SHIFT, A.ATTYS_FRONT_END))
    n_rail = int(np.count_nonzero(np.abs(av) >= rail16))
    n_mark = int(np.count_nonzero(am & A.MARKER_CLAMP))
    baris(n_mark == n_rail,
          "the Attys clamp marker is rail detection and it counts %d" % n_rail,
          "%d samples sit on the rail word; the dataset path counts %d clipped because it "
          "still sees the pre clamp count, while the Attys frame keeps only the rail value, "
          "so the %d samples that landed exactly on %d cannot be told from the clipped ones"
          % (n_rail, clamp_idx.size, n_rail - clamp_idx.size, R.CLAMP))
    res_ab, n_ab, t_ab = run_core(attys_bulk(cont_path), 8192)
    bad = differing(res_ab, res_bulk)
    baris(not bad, "the core over AttysBulk equals the core over the dataset path",
          "%d arrays compared, differing %s, %.1f s" % (len(res_ab), bad, t_ab))

    st250 = attys_stream(250, raw_frames, 1024)
    ti, tv, tm = st250.series()
    baris(ti.size == ai.size and np.array_equal(ti, ai) and np.array_equal(tv, av)
          and np.array_equal(tm, am),
          "AttysStream at 250 Hz equals AttysBulk on the same frames",
          "%d records, %d blocks, %d lost samples reported" % (ti.size, st250.blocks,
                                                               st250.lost))
    res_st, n_st, t_st = run_core(attys_stream(250, raw_frames, 1024), 1)
    bad = differing(res_st, res_bulk)
    baris(not bad, "the core over AttysStream 250 Hz equals the dataset path core",
          "%d arrays compared, differing %s, %.1f s" % (len(res_st), bad, t_st))

    quiet = S.pack_frames(np.full((400, A.ATTYS_CHANNELS), 100, dtype=np.int64), seed=11)
    ad_q = attys_stream(250, quiet, 64)
    _, vq, mq = ad_q.series()
    n_weak = int(np.count_nonzero(mq & A.MARKER_WEAK))
    baris(n_weak == 400 - (A.WEAK_WINDOW - 1) and int(vq[0]) == 100,
          "the weak bit turns on after one window under %.2f mV" % A.WEAK_MV,
          "%d of %d records marked weak on a synthetic flat segment of %d word, the bit "
          "warms up over the first %d samples, the recording marks %d"
          % (n_weak, mq.size, 100, A.WEAK_WINDOW - 1, bulk.markers()["weak"]))

    # ------------------------------------------------------------------ stage 4, the rates
    print()
    print("stage 4, the resampler at the other two declared device rates")
    for rate in (125, 500):
        path, meta = sessions["rate_%d" % rate]
        frames_r = np.frombuffer(path.read_bytes(), dtype=np.uint8)
        frames_r = frames_r.reshape(meta["frames"], A.ATTYS_FRAME_BYTES)
        ad = attys_stream(rate, frames_r, 512)
        ri, rv, rm = ad.series()
        ref = av[:min(rv.size, av.size)]
        same = int(np.count_nonzero(rv[:ref.size] == ref)) if rv.size else -1
        dev = int(np.abs(rv[:ref.size].astype(np.int64) - ref).max()) if rv.size else -1
        n_unc = int(np.count_nonzero(rm & A.MARKER_UNCERTAIN))
        baris(ri.size == FRAMES and np.array_equal(ri, np.arange(FRAMES, dtype=np.int64)),
              "AttysStream at %d Hz declares once and lands on %d records at 250 Hz"
              % (rate, ri.size),
              "declared device %r Hz, output %r Hz" % (ad.declared["device_rate_hz"],
                                                       ad.declared["rate_hz"]))
        baris(rv.size == FRAMES,
              "AttysStream at %d Hz lands on %d records, deviation reported"
              % (rate, rv.size),
              "%d of %d words exactly equal, largest deviation %d words, %d samples marked "
              "uncertain; this is interpolation and not a filter, so the outputs between two "
              "device samples are their average" % (same, rv.size, dev, n_unc))
        res_r, n_r, t_r = run_core(attys_stream(rate, frames_r, 512), 1)
        bad = differing(res_r, res_bulk, CORE_ARRAYS)
        baris(n_r == rv.size, "the core over AttysStream %d Hz runs to completion" % rate,
              "%d records in %.1f s, core arrays that differ from the dataset path: %s"
              % (n_r, t_r, bad or "none"))

    # ------------------------------------------------------------------ stage 5, packet gaps
    print()
    print("stage 5, packet gaps are marked and never smoothed over")
    total_lost = sum(n for _i, n in S.GAP_TABLE if _i < FRAMES)
    gb = attys_bulk(gap_path)
    gi, gv, gm = gb.series()
    fills = (gm & A.MARKER_GAP) != 0
    kept = ~fills
    baris(gi.size == FRAMES + total_lost,
          "the recorded session with losses keeps the acquisition index",
          "%d records for %d frames and %d lost samples" % (gi.size, FRAMES, total_lost))
    baris(int(np.count_nonzero(fills)) == total_lost,
          "the gap bit lights on exactly the lost samples",
          "%d marked, %d lost from the gap table %s"
          % (int(np.count_nonzero(fills)), total_lost,
             [[i, n] for i, n in S.GAP_TABLE if i < FRAMES]))
    baris(np.array_equal(gv[kept], av[:int(kept.sum())]),
          "the delivered values still equal the continuous session",
          "%d delivered records compared, %d differ"
          % (int(kept.sum()), n_diff(gv[kept], av[:int(kept.sum())])))
    rec = np.flatnonzero((gm & A.MARKER_UNCERTAIN) != 0)
    expect_set = set()
    shift = 0
    for i, n in S.GAP_TABLE:
        if i >= FRAMES:
            continue
        start = i + shift
        expect_set.update(range(start, start + max(A.GAP_RECOVERY, n)))
        shift += n
    baris(rec.size == len(expect_set) and set(rec.tolist()) == expect_set,
          "the uncertainty window is exactly %d samples from the first fill"
          % A.GAP_RECOVERY,
          "%d marked, %d expected over %d gaps"
          % (rec.size, len(expect_set), len(expect_set) and
             sum(1 for i, _n in S.GAP_TABLE if i < FRAMES)))
    res_gb, n_gb, t_gb = run_core(attys_bulk(gap_path), 8192)
    n_window = int(np.count_nonzero(res_gb["jendela"][:FRAMES] != res_bulk["jendela"]))
    baris(n_window > 0,
          "a lost sample does reach the core output, so the marking is not decoration",
          "%d of the first %d window integration samples differ from the continuous run, "
          "the gapped run carries %d records against %d, %.1f s"
          % (n_window, FRAMES, n_gb, FRAMES, t_gb))

    gap_blocks = ((5, 3), (40, 1), (200, 7), (300, 2), (350, 2))
    gap_blocks = tuple((b, n) for b, n in gap_blocks if b * 1024 < FRAMES)
    lost_blocks = sum(n for _b, n in gap_blocks)
    st_gap = attys_stream(250, raw_frames, 1024, gap_blocks)
    qi, qv, qm = st_gap.series()
    qfill = (qm & A.MARKER_GAP) != 0
    qkeep = ~qfill
    qunc = np.flatnonzero((qm & A.MARKER_UNCERTAIN) != 0)
    baris(qi.size == FRAMES + lost_blocks and int(np.count_nonzero(qfill)) == lost_blocks,
          "the callback blocks report their losses and the fills are marked",
          "%d records, %d blocks, %d lost samples reported, %d fills"
          % (qi.size, st_gap.blocks, st_gap.lost, int(np.count_nonzero(qfill))))
    baris(np.array_equal(qv[qkeep], av[:int(qkeep.sum())]),
          "the blocks that did arrive still carry the locked words",
          "%d delivered records compared, %d differ"
          % (int(qkeep.sum()), n_diff(qv[qkeep], av[:int(qkeep.sum())])))
    expect_q = set()
    shift = 0
    for b, n in gap_blocks:
        start = b * 1024 + shift
        expect_q.update(range(start, start + max(A.GAP_RECOVERY, n)))
        shift += n
    baris(set(qunc.tolist()) == expect_q,
          "each gap opens an uncertainty window of %d samples" % A.GAP_RECOVERY,
          "%d marked uncertain, %d expected, first marked index %d"
          % (qunc.size, len(expect_q), int(qunc[0]) if qunc.size else -1))

    # ------------------------------------------------------------------ stage 6, the contract
    print()
    print("stage 6, the contract itself")
    ok = True
    try:
        st250.declare_rate(500)
        ok = False
    except RuntimeError:
        ok = True
    baris(ok, "the rate is declared once and a second declaration is refused",
          "; ".join("%s says %r Hz" % (a.MODE, a.rate_hz)
                    for a in (bulk, stream, ab, st250)))
    baris(int(np.count_nonzero(bv % (1 << R.GESER_KIRI))) == 0
          and int(np.count_nonzero(av % (1 << R.GESER_KIRI))) == 0,
          "every word leaving an adapter is the locked count times sixteen",
          "dataset path and Attys path, %d records each" % FRAMES)
    baris(st250.declared["resampler"].startswith("exact rational linear"),
          "the resampler method is declared with the adapter",
          "%s, device %d Hz to output %d Hz"
          % (st250.declared["resampler"], st250.declared["device_rate_hz"],
             st250.declared["rate_hz"]))
    try:
        import pyattyscomm  # noqa: F401
        live = "is importable on this machine, but there is still no device"
    except ImportError as exc:
        live = "is not importable here (%s)" % (exc,)
    info("live Attys Bluetooth path",
         "NOT TESTED, pyattyscomm %s, so only the synthetic block source of AttysStream "
         "was exercised and the radio path stays with Aviv" % live)

    print()
    n_fail = RESULTS.count(False)
    print("%d checks, %d pass, %d fail, %.1f s"
          % (len(RESULTS), RESULTS.count(True), n_fail, time.time() - t_start))
    if n_fail == 0:
        print("gate S2: PASS, one source gives the same index, word and marker through the "
              "bulk and the stream path, and the clamp marker lights on 402 samples")
        return 0
    print("gate S2: FAIL, %d checks did not meet their gate" % n_fail)
    return 1


if __name__ == "__main__":
    sys.exit(main())
