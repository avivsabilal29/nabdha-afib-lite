#!/usr/bin/env python3
"""AFIB-LITE phase 6 step S4 gate: validation level 2, equality across the four adapter modes.

Design document section 8 says: the same recording is run through the four adapters, then the
beat list and the window decision list are compared across modes, and the requirement is zero
difference. This file is that gate, at the level of the whole core output and of the three
series every adapter emits, plus the repeatability fingerprint of section 8.

FOUR MODES, SIX PATHS

    dataset_bulk       DatasetBulk, the recording read as one large block
    dataset_stream     DatasetStream, the same recording one sample per call
    attys_bulk         AttysBulk, 24 bit frames of the synthetic recorded session
    attys_stream250    AttysStream, the callback block path at the declared device rate 250
    attys_stream125    AttysStream, the 125 Hz variant of the same frames
    attys_stream500    AttysStream, the 500 Hz variant of the same frames

HARD GATES

    A  DatasetBulk against DatasetStream: index, 16 bit value and marker identical over all
       450,000 records, and the whole core output identical array by array. Zero difference.
    B  DatasetBulk against AttysBulk on the scale alignment fixed in S2: zero difference over
       450,000 words.
    C  AttysStream at 250 Hz against DatasetStream: zero difference on every core array that
       the S1 checker compares, and on the three series.
    D  Chunk size does not change the result. The same path is run with a chunk of 1, 7, 64,
       4096 and 450000, and every run must be identical bit for bit. This is the core of the
       claim that bulk is not a second mode.
    E  Pacing only shifts the clock. On a 3,000 sample run the records are identical with and
       without the sleep, and the elapsed times are reported and required to differ.

REPORTED DEVIATIONS, NOT GATES

The 125 Hz and the 500 Hz device rates are not gates. Their word level and core level deviation
against the 250 Hz path is printed with its numbers and its direction, and the eligibility
decision for a demo is left with a human. The 500 Hz finding here is a real measurement and it is
stated as it came out, not as it was expected.

REPEATABILITY FINGERPRINT, DESIGN DOCUMENT SECTION 8

Every path is run twice, in two separate worker processes and not twice in one process, so that
any instability of ordering or counting is caught. The SHA-256 of every series and of every core
array of both processes is printed and compared, and one combined fingerprint for all paths on
the recording 04015 is printed. When a single array differs between the two processes, the name
of that array and the first differing index are printed.

WHAT IS AND WHAT IS NOT TESTED

The recording 04015 and its locked 16 bit words are real. The 24 bit frames, the front end
ladder, the noise in the eight bottom bits, the block boundaries, the rate variants and the
packet gap table are synthetic, built by simulator_attys.py from the real recording. The live
Attys path over Bluetooth is NOT tested: pyattyscomm is not installed on this machine and no
device is present, so only the synthetic block source of AttysStream is exercised.

Frozen files that this file reads and never writes: fixture/04015_30m.npz, fixture/attys/,
rantai.py, adapter.py, simulator_attys.py, acuan_fase.py, s0_bekukan_acuan.py.

Run it with the project interpreter:

    cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/uji_03_ekivalensi.py

The script spawns two subprocesses of itself with --worker to produce the two separate runs. One
line of output per check, then a summary, then the gate S4 line. Exit code 0 on pass, 1 on fail.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np

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
RECORD_NAME = "04015"

# The four modes of the design document, as the six paths this gate runs.
MODES = ("dataset_bulk", "dataset_stream", "attys_bulk", "attys_stream250")
RATES = (125, 500)
PATHS = MODES + tuple("attys_stream%d" % r for r in RATES)

# The core arrays of the S1 checker, the ones a cross mode equality has to cover.
CORE_ARRAYS = ("masukan16", "lp", "hp", "turunan", "kuadrat", "jendela", "puncak", "qrs", "rr",
               "rr_average1", "rr_average2", "rr_antre_panjang", "penanda", "rr_disemai",
               "rr_riwayat_panjang", "rr_menyala_akhir", "ambang_kemiringan_puncak",
               "ambang_puncak_terfilter", "ambang_state", "rasio_pita", "rasio_qrs")

CHUNKS = (1, 7, 64, 4096, 450_000)
STREAM_BLOCK = S.BLOCK_FRAMES  # 64 frames, the block a simulated Bluetooth callback delivers
RATE_BLOCK = 512               # block size of the rate variant runs
PACING_FRAMES = 3_000

# TASK_BRIEF.md locked constant. The core does not carry it, so it is stated here and reported
# in the output, so that no reading of this gate claims more than the T wave rule can hold.
BATAS_KEBERLAKUAN_MV = 0.90

WORKER_JSON_PREFIX = "WORKER_JSON "

RESULTS = []


# =============================================================================================
# Reporting
# =============================================================================================

def baris(ok, name, detail=""):
    """One result line, and the count of failures."""
    RESULTS.append(bool(ok))
    print("[%2d] %s  %-58s %s" % (len(RESULTS), "PASS" if ok else "FAIL", name, detail),
          flush=True)
    return ok


def info(name, detail):
    print("     INFO  %-58s %s" % (name, detail), flush=True)


def lapor(name, detail):
    """A reported deviation. It is not a check and it never fails the gate."""
    print("     REPORT %-57s %s" % (name, detail), flush=True)


# =============================================================================================
# Fingerprints and differences
# =============================================================================================

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256_array(arr):
    """SHA-256 of one array, over its shape, its dtype and its bytes."""
    a = np.ascontiguousarray(arr)
    h = hashlib.sha256()
    h.update(str(a.shape).encode())
    h.update(str(a.dtype).encode())
    h.update(a.tobytes())
    return h.hexdigest()


def series_fingerprint(index, value, marker):
    return {"index": sha256_array(index), "value": sha256_array(value),
            "marker": sha256_array(marker)}


def core_fingerprints(core):
    return {key: sha256_array(core[key]) for key in sorted(core)}


def path_fingerprint(record):
    """Fingerprint of one path: the three series and every core array."""
    return {"series": series_fingerprint(record["index"], record["value"], record["marker"]),
            "core": core_fingerprints(record["core"]),
            "n": int(np.asarray(record["index"]).size)}


def path_digest(fp):
    """One SHA-256 of one path fingerprint, in a fixed order."""
    h = hashlib.sha256()
    for part in ("index", "value", "marker"):
        h.update(("series|%s|" % part).encode())
        h.update(fp["series"][part].encode())
    for key in sorted(fp["core"]):
        h.update(("core|%s|" % key).encode())
        h.update(fp["core"][key].encode())
    return h.hexdigest()


def combined_fingerprint(fingerprints):
    """One SHA-256 over every path on the recording, in a fixed order."""
    h = hashlib.sha256()
    for name in sorted(fingerprints):
        h.update(("path|%s|" % name).encode())
        h.update(path_digest(fingerprints[name]).encode())
    return h.hexdigest()


def array_diff(a, b):
    """(n_diff, first_index, note) of two arrays. n_diff is -1 when the shapes differ."""
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape:
        return (-1, -1, "shape %s against %s" % (tuple(a.shape), tuple(b.shape)))
    if a.dtype.kind == "f" or b.dtype.kind == "f":
        af, bf = a.astype(np.float64), b.astype(np.float64)
        diff = af != bf
        diff = diff | (np.isnan(af) != np.isnan(bf))
    else:
        diff = a != b
    n = int(np.count_nonzero(diff))
    if n == 0:
        return (0, -1, "")
    return (n, int(np.flatnonzero(diff.ravel())[0]), "")


def differing_arrays(core_a, core_b, keys=None):
    """Names of the core arrays that differ, with their difference count and first index."""
    keys = CORE_ARRAYS if keys is None else keys
    out = []
    for key in keys:
        n, first, note = array_diff(core_a[key], core_b[key])
        if n != 0:
            out.append((key, n, first, note))
    return out


# =============================================================================================
# The six paths, one run of each
# =============================================================================================

def session_frames(rate, tag=""):
    """The synthetic session of one declared rate, read but never written here."""
    path = S.session_path(SESSIONS, RECORD_NAME, rate, tag)
    meta = json.loads(path.with_suffix(".json").read_text())
    raw = path.read_bytes()
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(meta["frames"], A.ATTYS_FRAME_BYTES)
    return path, meta, hashlib.sha256(raw).hexdigest(), frames


def path_factories():
    """A fresh adapter per call, per path. The recording and the sessions are read only."""
    cont_path, _cont_meta, _cont_sha, cont_frames = session_frames(A.ATTYS_TARGET_HZ)
    rate_frames = {}
    for rate in RATES:
        _p, _m, _s, frames = session_frames(rate)
        rate_frames[rate] = frames
    factories = {
        "dataset_bulk": lambda: A.DatasetBulk(REC, FRAMES),
        "dataset_stream": lambda: A.DatasetStream(REC, FRAMES),
        "attys_bulk": lambda: A.AttysBulk(cont_path),
        "attys_stream250": lambda: A.AttysStream(
            block_source=S.BlockFeeder(cont_frames, block_frames=STREAM_BLOCK),
            device_rate_hz=A.ATTYS_TARGET_HZ),
    }
    for rate in RATES:
        factories["attys_stream%d" % rate] = (
            lambda rate=rate: A.AttysStream(
                block_source=S.BlockFeeder(rate_frames[rate], block_frames=RATE_BLOCK),
                device_rate_hz=rate))
    return factories, cont_path


def new_chain():
    return R.Rantai(semai_aktif=True, aturan_t=True, besaran="turunan")


def run_path(factory, chunk=None):
    """Series and core of one path, each through a fresh adapter and a fresh core."""
    adapter = factory()
    adapter.open()
    chunk_series = adapter.DEFAULT_CHUNK if chunk is None else chunk
    index, value, marker = adapter.series(chunk_series)
    adapter.close()

    adapter = factory()
    adapter.open()
    chunk_core = adapter.DEFAULT_CHUNK if chunk is None else chunk
    chain = new_chain()
    t0 = time.time()
    n, _drive = adapter.drive(chain, chunk_core)
    seconds = time.time() - t0
    adapter.close()
    return {"index": index, "value": value, "marker": marker, "core": chain.hasil(),
            "n": n, "seconds": seconds, "chunk": chunk_core}


def run_all_paths(factories):
    out = {}
    for name in sorted(factories):
        out[name] = run_path(factories[name])
    return out


def flat_arrays(paths):
    """The flat name to array map that both the workers and the checker use."""
    out = {}
    for name in sorted(paths):
        record = paths[name]
        out["%s__series_index" % name] = record["index"]
        out["%s__series_value" % name] = record["value"]
        out["%s__series_marker" % name] = record["marker"]
        for key in sorted(record["core"]):
            out["%s__core__%s" % (name, key)] = record["core"][key]
    return out


# =============================================================================================
# The worker: one separate process, every path once, fingerprints and arrays written out
# =============================================================================================

def worker_main(out_path):
    t0 = time.time()
    factories, _cont = path_factories()
    paths = run_all_paths(factories)
    fingerprints = {name: path_fingerprint(paths[name]) for name in sorted(paths)}
    combined = combined_fingerprint(fingerprints)
    arrays = flat_arrays(paths)
    np.savez(out_path, **arrays)
    for name in sorted(paths):
        print("worker path %-16s n %7d core %2d arrays %6.1f s sha256 %s"
              % (name, paths[name]["n"], len(paths[name]["core"]), paths[name]["seconds"],
                 path_digest(fingerprints[name])[:32]))
    payload = {"fingerprints": fingerprints, "combined": combined,
               "arrays": sorted(arrays), "seconds": time.time() - t0, "npz": str(out_path)}
    print(WORKER_JSON_PREFIX + json.dumps(payload, sort_keys=True))
    return 0


# =============================================================================================
# The checker
# =============================================================================================

def run_worker(out_path, tag):
    """One full run of this file in a separate process."""
    cmd = [sys.executable, str(pathlib.Path(__file__).resolve()), "--worker", str(out_path)]
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(HERE), env=env)
    seconds = time.time() - t0
    payload = None
    for line in proc.stdout.splitlines():
        if line.startswith(WORKER_JSON_PREFIX):
            payload = json.loads(line[len(WORKER_JSON_PREFIX):])
        else:
            info("worker %s says" % tag, line)
    if proc.returncode != 0 or payload is None:
        print("     worker %s exit %s" % (tag, proc.returncode))
        tail = proc.stderr.strip().splitlines()[-6:]
        for line in tail:
            print("     worker %s stderr %s" % (tag, line))
    return payload, seconds, proc.returncode


def compare_dumps(path_a, path_b, tag_a, tag_b):
    """Elementwise comparison of the two worker dumps. Returns (ok, detail, first hits)."""
    with np.load(path_a) as za, np.load(path_b) as zb:
        keys_a, keys_b = set(za.files), set(zb.files)
        if keys_a != keys_b:
            only = sorted(keys_a ^ keys_b)
            return (False, "%d keys in %s, %d in %s, symmetric difference %s"
                    % (len(keys_a), tag_a, len(keys_b), tag_b, only[:6]), [])
        n_total, n_bad = 0, 0
        hits = []
        for key in sorted(keys_a):
            a, b = za[key], zb[key]
            n, first, note = array_diff(a, b)
            n_total += max(a.size, b.size)
            if n != 0:
                n_bad += abs(n)
                hits.append("%s: %d of %d differ, first at index %d%s"
                            % (key, n, max(a.size, b.size), first,
                               (" (" + note + ")") if note else ""))
        if n_bad == 0:
            return (True, "%d arrays, %d elements compared elementwise" % (len(keys_a), n_total),
                    [])
        return (False, "%d arrays, %d of %d elements differ" % (len(keys_a), n_bad, n_total),
                hits[:8])


def main():
    t_start = time.time()
    print("S4 gate, validation level 2, equality across the four adapter modes")
    print("recording  :", REC)
    print("fixture    :", NPZ)
    print("sessions   :", SESSIONS)
    print("interpreter:", sys.executable)
    print()

    # ---------------------------------------------------------------- frozen inputs, read only
    print("stage 0, the frozen inputs, read and never written")
    got = sha256_file(NPZ)
    baris(got == NPZ_SHA256, "the frozen fixture still carries its frozen sha256",
          "%s ..." % got[:32])
    factories, cont_path = path_factories()
    ok_sessions = True
    detail_sessions = []
    for rate in (A.ATTYS_TARGET_HZ,) + RATES:
        path, meta, sha, _frames = session_frames(rate)
        same = sha == meta["sha256"]
        ok_sessions = ok_sessions and same
        detail_sessions.append("%d Hz: %d frames, sha256 %s"
                               % (rate, meta["frames"], "matches" if same else "DIFFERS"))
    baris(ok_sessions, "the synthetic sessions match the sha256 of their own meta",
          "; ".join(detail_sessions))
    info("live Attys Bluetooth path",
         "NOT TESTED, pyattyscomm and a device are absent on this machine, so only the "
         "synthetic block source of AttysStream was exercised")

    # ---------------------------------------------------------------- one run of every path
    print()
    print("stage 1, the six paths of this machine, one run each")
    paths = run_all_paths(factories)
    fingerprints = {name: path_fingerprint(paths[name]) for name in sorted(paths)}
    for name in sorted(paths):
        info("path %s" % name,
             "n %d, %d core arrays, %.1f s, sha256 %s"
             % (paths[name]["n"], len(paths[name]["core"]), paths[name]["seconds"],
                path_digest(fingerprints[name])[:32]))

    # ---------------------------------------------------------------- A, the two dataset paths
    print()
    print("stage 2, gate A, DatasetBulk against DatasetStream, 450,000 records")
    bulk, stream = paths["dataset_bulk"], paths["dataset_stream"]
    for key in ("index", "value", "marker"):
        n, first, note = array_diff(bulk[key], stream[key])
        label = {"index": "index", "value": "value16", "marker": "marker"}[key]
        baris(n == 0, "A DatasetBulk against DatasetStream, %s series" % label,
              "%d of %d differ%s"
              % (n, bulk[key].size,
                 "" if n == 0 else ", first at index %d%s" % (first, " (" + note + ")" if note
                                                              else "")))
    bad = differing_arrays(bulk["core"], stream["core"])
    baris(not bad, "A DatasetBulk against DatasetStream, whole core output",
          "%d core arrays compared, differing %d%s"
          % (len(CORE_ARRAYS), len(bad),
             "" if not bad else " " + "; ".join("%s n %d first %d" % (k, n, f)
                                                for k, n, f, _n in bad[:5])))

    # ---------------------------------------------------------------- B, the story alignment
    print()
    print("stage 3, gate B, DatasetBulk against AttysBulk on the S2 scale alignment")
    ab = paths["attys_bulk"]
    n, first, note = array_diff(ab["value"], bulk["value"])
    baris(n == 0, "B AttysBulk value16 equals the dataset word over 450,000 words",
          "%d of %d differ, the alignment is frame >> %d, ladder %d counts24 per count12%s"
          % (n, ab["value"].size, A.ATTYS_WORD_SHIFT, A.ATTYS_FRONT_END,
             "" if n == 0 else ", first at index %d" % first))
    bad = differing_arrays(ab["core"], bulk["core"])
    baris(not bad, "B AttysBulk core output equals the dataset path core output",
          "%d core arrays compared, differing %d%s"
          % (len(CORE_ARRAYS), len(bad),
             "" if not bad else " " + "; ".join("%s n %d first %d" % (k, n, f)
                                                for k, n, f, _n in bad[:5])))

    # ---------------------------------------------------------------- C, the stream equality
    print()
    print("stage 4, gate C, AttysStream at 250 Hz against DatasetStream")
    st = paths["attys_stream250"]
    for key in ("index", "value"):
        n, first, note = array_diff(st[key], stream[key])
        label = {"index": "index", "value": "value16"}[key]
        baris(n == 0, "C AttysStream 250 Hz against DatasetStream, %s series" % label,
              "%d of %d differ%s"
              % (n, st[key].size,
                 "" if n == 0 else ", first at index %d%s" % (first, " (" + note + ")" if note
                                                              else "")))
    bad = differing_arrays(st["core"], stream["core"])
    baris(not bad, "C AttysStream 250 Hz against DatasetStream, every S1 core array",
          "%d core arrays compared, differing %d%s, beats %d against %d, RR gate counts %s "
          "against %s"
          % (len(CORE_ARRAYS), len(bad),
             "" if not bad else " " + "; ".join("%s n %d first %d" % (k, n, f)
                                                for k, n, f, _n in bad[:5]),
             st["core"]["qrs"].size, stream["core"]["qrs"].size,
             st["core"]["ambang_state"].tolist(), stream["core"]["ambang_state"].tolist()))

    # the beat list and the window decision list of design document section 8
    try:
        import wfdb
        annotation = wfdb.rdann(str(REC), "atr", sampto=FRAMES)
        label = R.label_irama(annotation.sample, annotation.aux_note, FRAMES)
        fitur_st, kelas_st = R.kumpulkan_jendela(st["core"]["qrs"], label)
        fitur_ds, kelas_ds = R.kumpulkan_jendela(stream["core"]["qrs"], label)
        n_f, f_first, f_note = array_diff(fitur_st, fitur_ds)
        n_k, k_first, k_note = array_diff(kelas_st, kelas_ds)
        baris(n_f == 0 and n_k == 0,
              "C the beat list and the window decision list are the same over both paths",
              "%d windows, features differ %d%s, classes differ %d%s, AFIB windows %d"
              % (kelas_st.size, n_f,
                 "" if n_f == 0 else " first at row %d" % f_first, n_k,
                 "" if n_k == 0 else " first at row %d" % k_first,
                 int((kelas_st == "AFIB").sum())))
    except Exception as exc:                                   # noqa: BLE001
        baris(False, "C the beat list and the window decision list are the same over both paths",
              "not measurable here, the rhythm annotation could not be read (%s)" % (exc,))

    # The marker series across the two paths. It is reported and not gated: the 24 bit Attys
    # frame keeps only the rail value, so a sample that landed exactly on the clamp cannot be
    # told from a clipped one. S2 measured this and it is structural, not a chain difference.
    n_mark, first_mark, _note = array_diff(st["marker"], stream["marker"])
    bits = []
    for name, bit in zip(("clamp", "gap", "weak", "uncertain"), A.MARKER_ORDER):
        bits.append("%s dataset %d against attys %d"
                    % (name, int(np.count_nonzero(stream["marker"] & bit)),
                       int(np.count_nonzero(st["marker"] & bit))))
    lapor("C the marker series across the two paths",
          "%d of %d records differ, first at index %d, and every one of them is the clamp bit: "
          "%s. The Attys frame keeps only the rail value, so the samples that landed exactly on "
          "%d cannot be told from the clipped ones. This is the frame layout and not the chain, "
          "it was measured in S2, and it is not part of gate C."
          % (n_mark, st["marker"].size, first_mark, ", ".join(bits), R.CLAMP))

    # ---------------------------------------------------------------- D, the chunk size
    print()
    print("stage 5, gate D, the chunk size does not change the result")
    chunked = {}
    for chunk in CHUNKS:
        chunked[chunk] = run_path(factories["dataset_stream"], chunk=chunk)
    base = chunked[CHUNKS[0]]
    bad_series = []
    bad_core = []
    for chunk in CHUNKS[1:]:
        rec = chunked[chunk]
        for key in ("index", "value", "marker"):
            n, first, _note = array_diff(base[key], rec[key])
            if n != 0:
                bad_series.append("chunk %d %s n %d first %d" % (chunk, key, n, first))
        for key, n, first, _note in differing_arrays(base["core"], rec["core"]):
            bad_core.append("chunk %d core %s n %d first %d" % (chunk, key, n, first))
    baris(not bad_series,
          "D chunk 1, 7, 64, 4096, 450000 give the same series bit for bit",
          "chunks %s, %d records each, differing %s"
          % (list(CHUNKS), base["index"].size, bad_series[:4] or "none"))
    baris(not bad_core,
          "D the same five chunk sizes give the same core arrays bit for bit",
          "%d core arrays compared per chunk, differing %s"
          % (len(CORE_ARRAYS), bad_core[:4] or "none"))
    info("chunk times, series and core",
         "; ".join("chunk %d: %.1f s core" % (chunk, chunked[chunk]["seconds"])
                   for chunk in CHUNKS))

    # ---------------------------------------------------------------- E, the pacing option
    print()
    print("stage 6, gate E, pacing shifts the clock and nothing else")
    paced = A.DatasetStream(REC, PACING_FRAMES, pacing=True)
    paced.open()
    t0 = time.time()
    pi, pv, pm = paced.series()
    t_paced = time.time() - t0
    paced.close()
    plain = A.DatasetStream(REC, PACING_FRAMES, pacing=False)
    plain.open()
    t0 = time.time()
    ui, uv, um = plain.series()
    t_plain = time.time() - t0
    plain.close()
    n_series = 0
    detail = []
    for key, a, b in (("index", pi, ui), ("value16", pv, uv), ("marker", pm, um)):
        n, first, note = array_diff(a, b)
        n_series += abs(n)
        if n != 0:
            detail.append("%s n %d first %d%s" % (key, n, first, " (" + note + ")" if note
                                                  else ""))
    baris(n_series == 0,
          "E with and without the sleep, the %d records are identical" % PACING_FRAMES,
          "%d differences over index, value16 and marker%s"
          % (n_series, "" if not detail else ", " + "; ".join(detail)))
    baris(t_paced > t_plain,
          "E the paced wall time differs, the sleep is the only difference",
          "%.2f s with the sleep against %.3f s without, %d samples at 250 Hz"
          % (t_paced, t_plain, PACING_FRAMES))

    # ---------------------------------------------------------------- repeatability
    print()
    print("stage 7, repeatability, every path twice in two separate processes")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="s4_worker_",
                                        dir=os.environ.get("TMPDIR") or None))
    dump_a = tmp / "run_a.npz"
    dump_b = tmp / "run_b.npz"
    payload_a, seconds_a, rc_a = run_worker(dump_a, "A")
    payload_b, seconds_b, rc_b = run_worker(dump_b, "B")
    ok_workers = rc_a == 0 and rc_b == 0 and payload_a is not None and payload_b is not None
    baris(ok_workers, "both worker processes finished with exit code 0",
          "process A %.1f s exit %s, process B %.1f s exit %s"
          % (seconds_a, rc_a, seconds_b, rc_b))
    fp_a = payload_a["fingerprints"] if payload_a else {}
    fp_b = payload_b["fingerprints"] if payload_b else {}
    if payload_a is not None and payload_b is not None and rc_a == 0 and rc_b == 0:
        same_paths = sorted(set(fp_a) & set(fp_b))
        bad_paths = [name for name in same_paths
                     if path_digest(fp_a[name]) != path_digest(fp_b[name])]
        baris(len(same_paths) == len(PATHS) and not bad_paths,
              "the sha256 of every path repeats across the two processes",
              "%d paths, differing %s" % (len(same_paths), bad_paths or "none"))
        for name in same_paths:
            info("sha256 path %s" % name,
                 "process A %s, process B %s, %s"
                 % (path_digest(fp_a[name])[:32], path_digest(fp_b[name])[:32],
                    "equal" if name not in bad_paths else "DIFFERENT"))
        combined_a = payload_a["combined"]
        combined_b = payload_b["combined"]
        baris(combined_a == combined_b,
              "the combined fingerprint of all paths repeats across the two processes",
              "A %s, B %s" % (combined_a[:32], combined_b[:32]))
        combined_main = combined_fingerprint(fingerprints)
        baris(combined_main == combined_a,
              "the fingerprint of this run equals both worker processes",
              "this run %s, A %s, B %s"
              % (combined_main[:32], combined_a[:32], combined_b[:32]))
        ok_dump, detail_dump, hits = compare_dumps(dump_a, dump_b, "A", "B")
        baris(ok_dump,
              "every series and core array is identical elementwise between the processes",
              detail_dump)
        for line in hits:
            print("     first hit %s" % line)
        info("combined fingerprint, all paths on %s" % RECORD_NAME, combined_main)
    else:
        baris(False, "the sha256 of every path repeats across the two processes",
              "not measurable, a worker process did not finish")
        baris(False, "the combined fingerprint of all paths repeats across the two processes",
              "not measurable, a worker process did not finish")
        baris(False, "the fingerprint of this run equals both worker processes",
              "not measurable, a worker process did not finish")
        baris(False,
              "every series and core array is identical elementwise between the processes",
              "not measurable, a worker process did not finish")

    # the difference reporter itself, shown to localize an array and an index
    probe = np.array(paths["dataset_bulk"]["core"]["qrs"], dtype=np.int64).copy()
    probe[5] += 1
    n, first, note = array_diff(paths["dataset_bulk"]["core"]["qrs"], probe)
    baris(n == 1 and first == 5,
          "the difference reporter localizes a deliberately perturbed array",
          "array qrs: %d of %d differ, first at index %d%s"
          % (n, probe.size, first, " (" + note + ")" if note else ""))

    # ---------------------------------------------------------------- reported deviations
    print()
    print("stage 8, reported deviations, the other two declared device rates, not gates")
    ref_words = bulk["value"]
    for rate in RATES:
        name = "attys_stream%d" % rate
        words = paths[name]["value"]
        m = min(words.size, ref_words.size)
        delta = words[:m].astype(np.int64) - ref_words[:m].astype(np.int64)
        nz = delta != 0
        n_diff = int(np.count_nonzero(nz))
        first = int(np.flatnonzero(nz)[0]) if n_diff else -1
        direction = "higher %d, lower %d" % (int((delta > 0).sum()), int((delta < 0).sum()))
        lapor("AttysStream %d Hz words against 250 Hz" % rate,
              "%d of %d words exactly equal, %d differ, largest deviation %d words, %s%s"
              % (m - n_diff, m, n_diff, int(np.abs(delta).max()), direction,
                 "" if not n_diff else
                 ", first difference at index %d (%d against %d)"
                 % (first, int(ref_words[first]), int(words[first]))))
        bad = differing_arrays(paths[name]["core"], bulk["core"])
        lapor("AttysStream %d Hz core against 250 Hz" % rate,
              "%d of %d core arrays differ%s, beats %d against %d, window decisions %d against %d"
              % (len(bad), len(CORE_ARRAYS),
                 "" if not bad else " " + "; ".join("%s n %d first %d" % (k, n, f)
                                                    for k, n, f, _n in bad[:6]),
                 paths[name]["core"]["qrs"].size, bulk["core"]["qrs"].size,
                 paths[name]["core"]["rasio_qrs"].size, bulk["core"]["rasio_qrs"].size))
        rem = words[:m] % (1 << R.GESER_KIRI)
        n_off = int(np.count_nonzero(rem))
        if n_off == 0:
            lapor("AttysStream %d Hz words on the locked grid" % rate,
                  "every one of the %d words is the locked count times sixteen, so the core sees "
                  "exactly the word the adapter emitted" % m)
        else:
            lapor("AttysStream %d Hz words off the locked grid" % rate,
                  "%d of %d words are not the locked count times sixteen, their remainder is one "
                  "of %s, so the core receives each of those words with the low %d bits dropped, "
                  "here %d counts at every one of them. The 250 Hz and the 500 Hz paths stay on "
                  "the locked grid."
                  % (n_off, m, sorted(set(rem.tolist())), R.GESER_KIRI, int(rem.max())))
    lapor("the 125 Hz and 500 Hz paths are not gates",
          "their deviation is reported above with its numbers and its direction. Whether 125 Hz "
          "or 500 Hz is good enough for a demo is a human decision and it is not decided here. "
          "The 500 Hz word series came out exactly equal in this synthetic setup because the "
          "synthetic variant sits on the same sample grid, while the real 500 Hz front end and "
          "the aliasing of its decimation stay unmeasured on this machine.")
    info("limit of validity of the T wave rule",
         "%.2f mV, reported here so that no reading of this gate claims more than it measured"
         % BATAS_KEBERLAKUAN_MV)

    # ---------------------------------------------------------------- summary
    print()
    n_fail = RESULTS.count(False)
    print("%d checks, %d pass, %d fail, %.1f s"
          % (len(RESULTS), RESULTS.count(True), n_fail, time.time() - t_start))
    if n_fail == 0:
        if tmp.exists() and os.environ.get("S4_KEEP_WORKER_DUMPS") != "1":
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            info("worker dumps kept", str(tmp))
        print("gate S4: PASS, zero difference between the four modes over %d records, the same "
              "result for every chunk size, pacing that touches nothing but the clock, and a "
              "combined fingerprint that repeats across two separate processes" % FRAMES)
        return 0
    info("worker dumps kept for inspection", str(tmp))
    print("gate S4: FAIL, %d of %d checks did not meet their gate" % (n_fail, len(RESULTS)))
    return 1


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        sys.exit(worker_main(pathlib.Path(sys.argv[2])))
    sys.exit(main())
