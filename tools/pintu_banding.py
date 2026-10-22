#!/usr/bin/env python3
"""One door: compare the model side with the RTL side over the same input, down to the three
triage decisions, then print one summary.

What it does, in order:

  1. resolve the input source (a prepared record, or a sensor capture)
  2. stage the vector directories the full-chain testbench reads
  3. prepare the model side (six per-sample columns, per-window decisions)
  4. run the RTL replay (full-chain testbench with +DUMP)
  5. compare stream against stream, per sample
  6. compare decision against decision, per window
  7. summarise: print, write SUMMARY.md and summary.json

Usage, from the repo root:

  # a record whose model artefacts already exist (rtlplan2/fase0 and rtlplan2/fase5)
  tools/pintu_banding.py --record 04015

  # same record, first 20000 samples, Icarus engine, with the side-by-side value tables
  tools/pintu_banding.py --record 04015 --limit 20000 --engine icarus --table 6

  # model side only, no RTL replay
  tools/pintu_banding.py --record 04015 --no-rtl

  # from a sensor capture (8 bytes per sample: A5 5A, markers, sequence, count, reserved, checksum)
  tools/pintu_banding.py --sensor /path/capture.bin --format frame

  # step by step with every tool command and its output
  tools/pintu_banding.py --record 04015 --limit 20000 -v

Why there is a staging step: the full-chain testbench hardcodes the 04015.* file names inside its
vector directories, so another record is staged under those same names inside this script's output
directory. Record 04015 itself can be linked straight from the repo, which avoids copying hundreds of
megabytes.

Honest limits: the sensor path prepares the six columns and the window classes from the frozen model
chain, which covers the per-sample and the decision comparison. The other event vectors the testbench
demands (fase 5 peaks, fase 6 RR series, fase 8 row bridge) still have to come from the model
exporters; while they are missing for an input, the full-chain replay for it cannot run and the script
says so instead of guessing. Window classes are a function of the rhythm annotation, not of the
stimulus words, so an input without a rhythm label has no model decision table: the script then skips
the triage comparison and states why.

Indonesian flag aliases are kept (--rekaman, --keluar, --tanpa-rtl, --tabel, --bentuk, --mesin,
--vektor-peristiwa, --keputusan-model) so older notes keep working.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
RTLS = ROOT / "rtl-synthesis"
PY = pathlib.Path.home() / ".venvs" / "afib-lite" / "bin" / "python"
VERILATOR = pathlib.Path.home() / "eda" / "oss-cad-suite" / "bin" / "verilator"
STREAM_COMPARATOR = ROOT / "rtlplan2" / "fase0" / "banding_stream.py"
MODEL_CORE = ROOT / "tools" / "model_core.py"
MODEL_CORE_FALLBACK = pathlib.Path.home() / ".hermes" / "cache" / "scratch" / "pintu" / "model_core.py"

STREAMS = ("masukan16", "lp", "hp", "turunan", "kuadrat", "jendela")
CLASS_NAMES = {0: "undecided", 1: "normal", 2: "review (AF)"}

# The plusargs the full-chain testbench demands, the staging subdirectory each one points at, and the
# files it actually reads. The 04015 names are fixed because the testbench writes them itself; another
# record is staged under those names instead of renaming the real vectors.
VECTORS = {
    "VECTOR": ("fase0", ("04015.masukan16.hex", "04015.lp.hex", "04015.hp.hex",
                         "04015.turunan.hex", "04015.kuadrat.hex", "04015.jendela.hex")),
    "EXPECT": ("fase5", ("04015.fase5.counts.hex", "04015.ambang_state.hex", "04015.qrs.hex",
                         "04015.puncak.pos.hex", "04015.puncak.pv.hex", "04015.puncak.pkf.hex",
                         "04015.puncak.kem.hex", "04015.puncak.i1.hex", "04015.puncak.i2.hex",
                         "04015.puncak.flag.hex", "04015.puncak.evidx.hex", "04015.puncak.kind.hex")),
    "RRVEC": ("fase6", ("04015.rr.hex", "04015.rr.mark.hex", "04015.rr.smp.hex",
                        "04015.fase6.counts.hex")),
    "CLVEC": ("fase9", ("04015.fase9.counts.hex", "04015.mentah.asli.hex", "04015.mentah.kelas.hex",
                        "04015.mentah.qr.hex", "04015.mentah.qe.hex", "04015.berpenanda.asli.hex",
                        "04015.berpenanda.kelas.hex", "04015.berpenanda.qr.hex", "04015.berpenanda.qe.hex")),
    "F8VEC": ("fase8", ("04015.fase8.map.raw.hex", "04015.fase8.map.marked.hex")),
}
# +STIM takes a file, not a directory: the testbench calls $readmemh straight on this path
STIM_FILE = ("stimulus", "04015.stimulus.hex")
# Marker bit order in the RTL package: TU_CLAMP=0, TU_GAP=1, TU_WEAK=2, TU_UNSURE=3. The testbench
# drives bits 14..12 of the stimulus word, so the gap marker lands on bit 13.
BIT_GAP = 1 << (1 + 12)
REPO_SOURCES = {
    "fase0": ROOT / "rtlplan2" / "fase0",
    "stimulus": ROOT / "rtl" / "tb" / "vektor",
    "fase5": ROOT / "rtl" / "tb" / "vektor" / "fase5",
    "fase6": ROOT / "rtl" / "tb" / "vektor" / "fase6",
    "fase8": ROOT / "rtl" / "tb" / "vektor" / "fase8",
    "fase9": ROOT / "rtl" / "tb" / "vektor" / "fase9",
}

# ------------------------------------------------------------------------------------------- logging

_T0 = time.monotonic()
_RUN_LOG: list[str] = []
_LOG_DIR: pathlib.Path | None = None
_VERBOSITY = 1          # 0 quiet, 1 steps, 2 verbose (commands and tool output), 3 debug
_STEPS: list[dict] = []


def log(message: str = "", level: int = 1) -> None:
    """Print one timestamped line and mirror it into the run log.

    The run log written into the report always keeps steps and their detail (levels 1 and 2), whatever
    the console verbosity is, so the step-by-step trace survives a quiet run. Level 3 debug lines stay
    on the console only.
    """
    line = "[%7.2fs] %s" % (time.monotonic() - _T0, message)
    if level <= 2:
        _RUN_LOG.append(line)
    if level <= _VERBOSITY:
        print(line, flush=True)


def step(number: int, total: int, title: str) -> float:
    """Announce a step and start timing it."""
    log("")
    log("--- step %d/%d: %s" % (number, total, title))
    return time.monotonic()


def step_done(number: int, title: str, started: float, detail: str = "") -> None:
    elapsed = time.monotonic() - started
    line = "step %d/%d: %s -- %.2fs%s" % (number, TOTAL_STEPS, title, elapsed,
                                          (" (%s)" % detail) if detail else "")
    _STEPS.append({"step": number, "title": title, "seconds": round(elapsed, 3), "detail": detail})
    log("--- " + line, level=2)


TOTAL_STEPS = 7


def die(message: str) -> None:
    log("error: " + message)
    raise SystemExit("pintu: " + message)


def run(command, cwd=None, timeout: int = 1800, tag: str | None = None, show_tail: int = 0):
    """Run one command, mirror its output into the log file, return (returncode, output)."""
    log("run: %s" % " ".join(str(x) for x in command), level=2)
    result = subprocess.run([str(x) for x in command], cwd=str(cwd or ROOT),
                            capture_output=True, text=True, timeout=timeout)
    output = result.stdout + result.stderr
    if _LOG_DIR is not None and tag:
        (_LOG_DIR / ("%s.log" % tag)).write_text(output)
    if show_tail and output.strip():
        lines = output.rstrip().splitlines()
        log("output tail (%d lines total, last %d shown):" % (len(lines), min(show_tail, len(lines))), level=2)
        for line in lines[-show_tail:]:
            log("  | " + line, level=2)
    return result.returncode, output


def count_lines(path: pathlib.Path) -> int:
    """Count lines without loading the whole file."""
    total = 0
    with open(path, "rb") as handle:
        for _ in handle:
            total += 1
    return total


def head_lines(path: pathlib.Path, count: int, target: pathlib.Path) -> pathlib.Path:
    """Copy the first `count` lines of a file into `target`."""
    with open(path, "rb") as source, open(target, "wb") as destination:
        for index, line in enumerate(source):
            if index >= count:
                break
            destination.write(line)
    return target


# ---------------------------------------------------------------------------------------- staging


def stage_vectors(out_dir: pathlib.Path, record: str, link: bool = True) -> pathlib.Path:
    """Vector directory holding the file names the testbench expects.

    link True  : a record with model artefacts in the repo is linked, so no hundreds of megabytes are
                 copied.
    link False : only fase0 is populated (the sensor path), the event directories stay empty so that
                 whatever is missing is visible rather than assumed.
    """
    staging = out_dir / "vectors"
    for name in ("fase0", "fase5", "fase6", "fase8", "fase9", "stimulus"):
        (staging / name).mkdir(parents=True, exist_ok=True)
    if not link:
        log("staging: directories created under %s (event vectors left empty)" % staging, level=1)
        return staging
    linked = 0
    for name, source in REPO_SOURCES.items():
        target_dir = staging / name
        for source_file in sorted(source.glob("%s.*" % record)):
            target = target_dir / source_file.name
            if target.exists() or target.is_symlink():
                continue
            target.symlink_to(source_file)
            linked += 1
            log("linked %s -> %s" % (target.name, source_file), level=3)
    log("staging: %d vector files linked for record %s under %s" % (linked, record, staging))
    return staging


def plusarg_paths(staging: pathlib.Path) -> list[str]:
    """The six plusargs the testbench requires, all pointing into the staging directory."""
    args = ["+%s=%s" % (name, staging / sub) for name, (sub, _files) in VECTORS.items()]
    args.append("+STIM=%s" % (staging / STIM_FILE[0] / STIM_FILE[1]))
    return args


def missing_vectors(staging: pathlib.Path) -> list[str]:
    """Vector files the testbench demands but that are absent from the staging directory."""
    missing = []
    for _plusarg, (sub, files) in VECTORS.items():
        for name in files:
            if not (staging / sub / name).exists():
                missing.append("%s/%s" % (sub, name))
    if not (staging / STIM_FILE[0] / STIM_FILE[1]).exists():
        missing.append("%s/%s" % STIM_FILE)
    return missing


def frames_to_words(data: bytes) -> tuple[list[int], int, int]:
    """Turn a sensor frame stream into stimulus words.

    One frame is 8 bytes: A5 5A, markers, sequence, count (2 bytes little endian, 12-bit signed),
    reserved, checksum. A stimulus word is markers in bits 15..12 and count in bits 11..0.

    A frame that fails sync or checksum is not dropped, because dropping it would shift the time base
    of the whole record. It becomes one word carrying the gap marker and the previous count, so the
    length is preserved and the lost sample stays visible to the chain.
    Return (words, frames rejected, words replaced by a gap marker).
    """
    if len(data) % 8:
        return [], -1, 0
    words, rejected = [], 0
    last_count = 0
    for index in range(0, len(data), 8):
        chunk = data[index:index + 8]
        if chunk[0] != 0xA5 or chunk[1] != 0x5A or chunk[7] != sum(chunk[0:7]) % 256:
            rejected += 1
            words.append(BIT_GAP | (last_count & 0xFFF))
            continue
        count = int.from_bytes(chunk[4:6], "little", signed=True)
        last_count = count
        words.append(((chunk[2] & 0xF) << 12) | (count & 0xFFF))
    return words, rejected, rejected


# ------------------------------------------------------------------------------------- model side


def safe_write(path: pathlib.Path, text: str) -> None:
    """Write a file, unlinking a symlink first so the write can never land outside the output tree.

    This is not paranoia: the staging step links repo vector files on purpose, and a write through such
    a link would silently truncate the repo artefact instead of filling the staging copy.
    """
    if path.is_symlink():
        log("write guard: %s was a symlink, removed before writing" % path)
        path.unlink()
    path.write_text(text)


def model_from_sensor(capture: pathlib.Path, form: str, out_dir: pathlib.Path) -> None:
    """Turn a sensor capture into model columns plus the stimulus file the RTL bench reads."""
    core_path = MODEL_CORE if MODEL_CORE.exists() else MODEL_CORE_FALLBACK
    if not core_path.exists():
        die("the sensor path needs the model module at %s and it does not exist;\n"
            "       use --record when the model artefacts are already there." % MODEL_CORE)
    sys.path.insert(0, str(core_path.parent))
    import model_core  # noqa: E402

    if form == "frame":
        data = capture.read_bytes()
        log("sensor: %d bytes read from %s" % (len(data), capture), level=2)
        words, rejected, replaced = frames_to_words(data)
        if rejected < 0:
            die("file length %d bytes is not a multiple of 8, frames cannot be aligned" % len(data))
        log("sensor: %d frames decoded, %d failed a check and were replaced by a gap marker"
            % (len(words), rejected))
        if replaced:
            log("        length stays %d samples, so the recording time base does not shift" % len(words))
    else:
        words = [int(token, 16) for token in capture.read_text().split()]
        log("sensor: %d stimulus words read as they are" % len(words))

    log("sensor: running the frozen model chain over %d words" % len(words))
    result = model_core.jalankan_model(words)
    log("sensor: chain finished in %.2f s" % result["detik"], level=2)
    for name in STREAMS:
        array = result[name]
        safe_write(out_dir / "vectors" / "fase0" / ("04015.%s.hex" % name),
            "".join("%08X\n" % (int(v) & 0xFFFFFFFF) for v in array))
        log("wrote vectors/fase0/04015.%s.hex (%d words)" % (name, len(array)), level=2)
    stimulus = out_dir / "vectors" / STIM_FILE[0] / STIM_FILE[1]
    stimulus.parent.mkdir(parents=True, exist_ok=True)
    safe_write(stimulus, "".join("%04X\n" % (int(v) & 0xFFFF) for v in words))
    log("sensor: wrote vectors/%s/%s (%d words)" % (STIM_FILE[0], STIM_FILE[1], len(words)))


# --------------------------------------------------------------------------------------- RTL side


def build_verilator(obj_dir: pathlib.Path) -> float:
    """Build the Verilator binary when it is not there yet. Return the seconds it took."""
    binary = obj_dir / "vtop"
    if binary.exists():
        log("rtl: reusing the Verilator binary at %s" % binary)
        return 0.0
    obj_dir.mkdir(parents=True, exist_ok=True)
    sources = [str(ROOT / "rtl" / "afib_lite_pkg.sv")]
    sources += sorted(str(p) for p in (ROOT / "rtl").glob("*.sv"))
    sources.append(str(ROOT / "rtl" / "tb" / "tb_top.sv"))
    command = [str(VERILATOR), "--binary", "--timing", "-Wno-fatal", "-j", "4",
               "--top-module", "tb_top", "-Mdir", str(obj_dir), "-o", "vtop"] + sources
    started = time.monotonic()
    code, output = run(command, cwd=RTLS, timeout=900, tag="verilator_build", show_tail=20)
    if code != 0:
        log(output[-3000:])
        die("Verilator build failed with code %d" % code)
    seconds = time.monotonic() - started
    log("rtl: Verilator build finished in %.1f s" % seconds)
    return seconds


def run_rtl(staging: pathlib.Path, out_dir: pathlib.Path, engine: str, limit: int | None) -> dict:
    """Run the full-chain replay with +DUMP. Return a note of how the run went."""
    dump = out_dir / "rtl"
    if dump.exists():
        shutil.rmtree(dump)
    dump.mkdir(parents=True)
    plusargs = plusarg_paths(staging) + ["+DUMP=%s" % dump]
    if limit:
        plusargs.append("+LIMIT=%d" % limit)
    log("rtl: engine %s, dump directory %s" % (engine, dump))
    if limit:
        log("rtl: short run, the bench skips its end-of-record gates for the first %d samples" % limit)
    started = time.monotonic()
    if engine == "verilator":
        obj_dir = out_dir / "obj_vtop"
        build_verilator(obj_dir)
        code, output = run([obj_dir / "vtop"] + plusargs, cwd=RTLS, timeout=1800,
                           tag="rtl_replay", show_tail=25)
    else:
        command = ["./run_sim.sh", "../rtl/tb/tb_top.sv", "../rtl/afib_lite_pkg.sv"]
        command += sorted("../rtl/%s" % p.name for p in (ROOT / "rtl").glob("*.sv"))
        command += ["--"] + plusargs
        code, output = run(command, cwd=RTLS, timeout=1800, tag="rtl_replay", show_tail=25)
    seconds = time.monotonic() - started
    (out_dir / "rtl.log").write_text(output)
    note = parse_rtl_log(output)
    note["code"] = code
    note["seconds"] = round(seconds, 1)
    note["dump"] = str(dump)
    note["plusargs"] = plusargs
    note["engine"] = engine
    log("rtl: finished in %.1f s, exit code %d, total mismatches %s, testbench verdict %s"
        % (seconds, code, note.get("total_mismatch"), note.get("tb_verdict")))
    return note


def parse_rtl_log(output: str) -> dict:
    """Pull the bench's own verdict, mismatch counters and checksums out of its output."""
    note: dict = {}
    for line in output.splitlines():
        if "words compared" in line:
            note["words"] = {k.strip(): int(v) for k, v in
                             (part.split("=") for part in line.split(":", 1)[1].split() if "=" in part)}
        elif "data mismatches" in line:
            note["data_mismatches"] = {k.strip(): int(v) for k, v in
                                       (part.split("=") for part in line.split(":", 1)[1].split() if "=" in part)}
        elif "total mismatches" in line:
            note["total_mismatch"] = int(line.split("=")[1])
        elif line.startswith("tb_top: CK_"):
            key, value = line.split("=")
            note[key.strip().replace("tb_top: ", "")] = value.strip()
        elif line.strip() in ("tb_top: PASS", "tb_top: FAIL"):
            note["tb_verdict"] = line.strip().split(":")[1].strip()
    return note


# ------------------------------------------------------------------------------------ comparisons


def compare_streams(dump: pathlib.Path, out_dir: pathlib.Path, golden_dir: pathlib.Path) -> list[dict]:
    """Compare the six model columns with the six RTL dump files, word by word."""
    results = []
    cut_dir = out_dir / "cut"
    cut_dir.mkdir(exist_ok=True)
    for name in STREAMS:
        rtl_file = dump / ("dut.%s.hex" % name)
        if not rtl_file.exists():
            results.append({"stream": name, "words": 0, "mismatches": None,
                            "verdict": "RTL dump file missing"})
            continue
        words = count_lines(rtl_file)
        golden = head_lines(golden_dir / ("04015.%s.hex" % name), words, cut_dir / ("golden.%s.hex" % name))
        code, output = run([PY, STREAM_COMPARATOR, golden, rtl_file], timeout=900,
                           tag="compare_%s" % name)
        entry = {"stream": name, "words": words, "mismatches": None, "first_bad": "?",
                 "verdict": None, "code": code}
        for line in output.splitlines():
            if line.startswith("mismatches:"):
                entry["mismatches"] = int(line.split(":")[1])
            elif line.startswith("first bad idx"):
                entry["first_bad"] = line.split(":")[1].strip()
            elif line.startswith("verdict"):
                entry["verdict"] = line.split(":", 1)[1].strip()
        log("compare %-9s %8d words, %s mismatches, first bad %s"
            % (name, words, entry["mismatches"], entry["first_bad"]))
        for line in output.splitlines():
            if line.startswith("peak RSS") or line.startswith("words compared"):
                log("  | " + line, level=3)
        results.append(entry)
    return results


def read_hex_words(path: pathlib.Path) -> list[int]:
    return [int(token, 16) for token in path.read_text().split()] if path.exists() else []


def compare_decisions(dump: pathlib.Path, fase9_dir: pathlib.Path, model_file: pathlib.Path,
                      arm: str) -> dict:
    """Pair every RTL decision with the model decision on the same row, then count the census."""
    rtl_file = dump / "dut.decisions.csv"
    if not rtl_file.exists() or not model_file.exists():
        return {"available": False, "reason": "decision files incomplete"}
    import csv
    with open(model_file) as handle:
        model = list(csv.DictReader(handle))
    with open(rtl_file) as handle:
        rtl = list(csv.DictReader(handle))
    by_row = {int(row["window_index"]): row for row in model}
    truth_file = fase9_dir / ("04015.%s.asli.hex" % arm)
    truth = read_hex_words(truth_file)
    model_class, rtl_class = {}, {}
    agree = differ = unmatched = 0
    differences = []
    for row in rtl:
        index = int(row["window_row"])
        reference = by_row.get(index)
        if reference is None:
            unmatched += 1
            continue
        cls = int(row["class"])
        model_class[index] = int(reference["label"])
        rtl_class[index] = cls
        if cls == int(reference["label"]):
            agree += 1
        else:
            differ += 1
            if len(differences) < 5:
                differences.append({"row": index, "rtl": cls, "model": int(reference["label"])})
    census = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    for index, cls in rtl_class.items():
        if index >= len(truth):
            continue
        truth_af = int(truth[index]) == 2
        fired = cls == 2
        if fired and truth_af:
            census["TP"] += 1
        elif fired and not truth_af:
            census["FP"] += 1
        elif not fired and truth_af:
            census["FN"] += 1
        else:
            census["TN"] += 1
    rtl_spread = {k: 0 for k in CLASS_NAMES}
    for cls in rtl_class.values():
        rtl_spread[cls] = rtl_spread.get(cls, 0) + 1
    model_spread = {k: 0 for k in CLASS_NAMES}
    for cls in model_class.values():
        model_spread[cls] = model_spread.get(cls, 0) + 1
    log("triage: %d windows paired, %d agree, %d differ, %d RTL rows without a model row"
        % (len(rtl_class), agree, differ, unmatched))
    log("triage: fired windows RTL %d, model %d; census TP %d FP %d FN %d TN %d"
        % (sum(1 for v in rtl_class.values() if v == 2), sum(1 for v in model_class.values() if v == 2),
           census["TP"], census["FP"], census["FN"], census["TN"]))
    return {
        "available": True,
        "rows": len(rtl_class),
        "agree": agree,
        "differ": differ,
        "unmatched": unmatched,
        "differences": differences,
        "rtl_spread": rtl_spread,
        "model_spread": model_spread,
        "census_vs_truth": census,
        "fired_rtl": sum(1 for v in rtl_class.values() if v == 2),
        "fired_model": sum(1 for v in model_class.values() if v == 2),
        "model_file": str(model_file),
        "truth_file": str(truth_file),
    }


def triage_model_only(model_file: pathlib.Path, truth_file: pathlib.Path | None) -> dict | None:
    """Model-side class spread and census, used when the RTL replay is skipped."""
    if not model_file.exists():
        return None
    import csv
    with open(model_file) as handle:
        model = list(csv.DictReader(handle))
    classes = {int(row["window_index"]): int(row["label"]) for row in model}
    truth = read_hex_words(truth_file) if truth_file else []
    census = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    for index, cls in classes.items():
        if index >= len(truth):
            continue
        truth_af = int(truth[index]) == 2
        fired = cls == 2
        if fired and truth_af:
            census["TP"] += 1
        elif fired and not truth_af:
            census["FP"] += 1
        elif not fired and truth_af:
            census["FN"] += 1
        else:
            census["TN"] += 1
    spread = {k: 0 for k in CLASS_NAMES}
    for cls in classes.values():
        spread[cls] = spread.get(cls, 0) + 1
    return {"rows": len(classes), "spread": spread,
            "census_vs_truth": census if truth else None, "model_file": str(model_file)}


# --------------------------------------------------------------------------------------- summary


def print_summary(source: str, record: str, samples: int, rtl_note: dict | None,
                  per_sample: list[dict] | None, decisions: dict | None, baseline: dict | None,
                  full_length: bool = True, rtl_skipped: bool = False,
                  model_only: dict | None = None) -> bool:
    """Print the summary. Return True when every gate passed."""
    passed = not (rtl_note and rtl_note.get("code") != 0)
    print("")
    print("=" * 78)
    print("gate comparison: model against RTL")
    print("=" * 78)
    print("  source            : %s" % source)
    print("  record            : %s" % record)
    print("  samples           : %d" % samples)
    if rtl_note:
        print("  RTL replay        : exit code %s, %.1f s, %s total mismatches, testbench %s"
              % (rtl_note.get("code"), rtl_note.get("seconds", 0),
                 rtl_note.get("total_mismatch"), rtl_note.get("tb_verdict")))
        print("  engine            : %s" % rtl_note.get("engine"))

    if per_sample:
        print("")
        print("  per sample (model against RTL)")
        print("    %-10s %10s %11s %12s  %s" % ("stream", "words", "mismatches", "first bad", "verdict"))
        for entry in per_sample:
            if entry["mismatches"]:
                passed = False
            print("    %-10s %10d %11s %12s  %s"
                  % (entry["stream"], entry["words"], entry["mismatches"],
                     entry.get("first_bad", "?"), entry.get("verdict") or "-"))

    if decisions and decisions.get("available"):
        print("")
        print("  triage, three classes (model against RTL, %d windows)" % decisions["rows"])
        print("    %-22s %8s %8s %8s" % ("class", "model", "RTL", "truth"))
        truth = read_hex_words(pathlib.Path(decisions["truth_file"]))
        truth_spread = {k: 0 for k in CLASS_NAMES}
        for value in truth:
            truth_spread[int(value)] = truth_spread.get(int(value), 0) + 1
        for cls in sorted(CLASS_NAMES):
            print("    %-22s %8d %8d %8d" % (CLASS_NAMES[cls], decisions["model_spread"].get(cls, 0),
                                             decisions["rtl_spread"].get(cls, 0), truth_spread.get(cls, 0)))
        print("    class agreement model against RTL : %d of %d (%d differ)"
              % (decisions["agree"], decisions["rows"], decisions["differ"]))
        if decisions.get("unmatched"):
            passed = False
            print("    RTL rows with no model row        : %d" % decisions["unmatched"])
        print("    fired windows                     : RTL %d, model %d"
              % (decisions["fired_rtl"], decisions["fired_model"]))
        census = decisions["census_vs_truth"]
        print("    census against the truth labels   : TP %d, FP %d, FN %d, TN %d"
              % (census["TP"], census["FP"], census["FN"], census["TN"]))
        if census["TP"] + census["FN"]:
            print("    sensitivity                       : %d of %d" % (census["TP"], census["TP"] + census["FN"]))
        if census["TN"] + census["FP"]:
            print("    specificity                       : %d of %d" % (census["TN"], census["TN"] + census["FP"]))
        if decisions["differ"]:
            passed = False
            print("    first differences                 : %s" % decisions["differences"])

    if model_only:
        print("")
        print("  triage, three classes (model side only, %d windows)" % model_only["rows"])
        for cls in sorted(CLASS_NAMES):
            print("    %-22s %8d" % (CLASS_NAMES[cls], model_only["spread"].get(cls, 0)))
        census = model_only.get("census_vs_truth")
        if census:
            print("    census against the truth labels   : TP %d, FP %d, FN %d, TN %d"
                  % (census["TP"], census["FP"], census["FN"], census["TN"]))

    if rtl_note and not decisions and not model_only:
        print("")
        print("  triage, three classes: not compared, this input has no model decision table")
        print("                        (window classes are a function of the rhythm annotation,")
        print("                         not of the stimulus words)")

    if baseline and rtl_note and not full_length:
        print("")
        print("  arithmetic fingerprints: skipped, this run is cut at %d samples so the values" % samples)
        print("                          legitimately differ from the full-record baseline")
    elif baseline and rtl_note:
        print("")
        print("  arithmetic fingerprints (the dump path must not disturb them)")
        for key in ("CK_STREAM", "CK_PEAK", "CK_DOWN", "CK_EVENT"):
            value = rtl_note.get(key)
            reference = baseline.get(key)
            state = "same" if (value and reference and value == reference) else \
                ("no baseline" if not reference else "DIFFERENT")
            if state == "DIFFERENT":
                passed = False
            print("    %-10s %s   baseline %s   %s" % (key, value, reference, state))

    print("")
    if not passed:
        text = "REVIEW"
    elif rtl_skipped:
        text = "MODEL SIDE ONLY (RTL replay skipped)"
    else:
        text = "PASS"
    print("  VERDICT: %s" % text)
    print("=" * 78)
    return passed


def write_report(out_dir: pathlib.Path, payload: dict) -> None:
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    lines = ["# Gate comparison report: model against RTL", "",
             "- source: `%s`" % payload["source"],
             "- record: `%s`" % payload["record"],
             "- samples: %d" % payload["samples"],
             "- engine: %s" % payload["engine"],
             "- full record: %s" % ("yes" if payload["full_length"] else "no, cut short"),
             "- timestamp: %s" % payload["timestamp"],
             "- total seconds: %s" % payload["total_seconds"],
             "- verdict: **%s**" % ("PASS" if payload["passed"] else "REVIEW"), ""]
    if payload.get("rtl"):
        rtl = payload["rtl"]
        lines += ["## RTL replay", "",
                  "- exit code: %s" % rtl.get("code"),
                  "- seconds: %s" % rtl.get("seconds"),
                  "- total mismatches: %s" % rtl.get("total_mismatch"),
                  "- testbench verdict: %s" % rtl.get("tb_verdict"),
                  "- bench log: `%s`" % (out_dir / "rtl.log"),
                  "- plusargs: `%s`" % " ".join(rtl.get("plusargs", [])), ""]
    if payload.get("per_sample"):
        lines += ["## Per sample", "", "| stream | words | mismatches | first bad | verdict |",
                  "| --- | --- | --- | --- | --- |"]
        for entry in payload["per_sample"]:
            lines.append("| %s | %d | %s | %s | %s |" % (entry["stream"], entry["words"], entry["mismatches"],
                                                         entry.get("first_bad", "?"), entry.get("verdict") or "-"))
        lines.append("")
    decisions = payload.get("decisions")
    if decisions and decisions.get("available"):
        lines += ["## Triage, three classes", "",
                  "- windows compared: %d" % decisions["rows"],
                  "- class agreement model against RTL: %d (%d differ)" % (decisions["agree"], decisions["differ"]),
                  "- fired windows: RTL %d, model %d" % (decisions["fired_rtl"], decisions["fired_model"]),
                  "- class spread RTL: %s" % decisions["rtl_spread"],
                  "- class spread model: %s" % decisions["model_spread"],
                  "- census against the truth labels: %s" % decisions["census_vs_truth"],
                  "- model decision table: `%s`" % decisions["model_file"],
                  "- truth labels: `%s`" % decisions["truth_file"], ""]
    model_only = payload.get("model_only")
    if model_only:
        lines += ["## Triage, three classes (model side only)", "",
                  "- windows: %d" % model_only["rows"],
                  "- class spread model: %s" % model_only["spread"],
                  "- census against the truth labels: %s" % model_only["census_vs_truth"],
                  "- RTL replay skipped, so there is no side to compare against", ""]
    if payload.get("baseline") and payload.get("rtl"):
        if payload["full_length"]:
            lines += ["## Arithmetic fingerprints", "", "| checksum | this run | baseline | same |",
                      "| --- | --- | --- | --- |"]
            for key in ("CK_STREAM", "CK_PEAK", "CK_DOWN", "CK_EVENT"):
                value = payload["rtl"].get(key)
                reference = payload["baseline"].get(key)
                lines.append("| `%s` | `%s` | `%s` | %s |" % (key, value, reference,
                                                              "yes" if value == reference else "no"))
            lines.append("")
        else:
            lines += ["## Arithmetic fingerprints", "",
                      "Skipped: this run is cut at %d samples, so the values legitimately differ from the "
                      "full-record baseline." % payload["samples"], ""]
    lines += ["## Steps", "", "| step | what | seconds | detail |", "| --- | --- | --- | --- |"]
    for entry in payload.get("steps", []):
        lines.append("| %d | %s | %.2f | %s |" % (entry["step"], entry["title"], entry["seconds"],
                                                  entry.get("detail") or ""))
    lines += ["", "## Run log", "", "```"]
    lines += [line for line in payload.get("run_log", []) if line.strip()]
    lines += ["```", ""]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines))


def baseline_from_reports() -> dict:
    """The checksum values recorded in the fase 10 report, when that report exists."""
    import re
    for path in sorted((RTLS / "reports" / "fase10").glob("verilator_jalan1_*.log")):
        text = path.read_text()
        found = {}
        for key in ("CK_STREAM", "CK_PEAK", "CK_DOWN", "CK_EVENT"):
            match = re.search(r"%s\s*=\s*([0-9a-f]+)" % key, text)
            if match:
                found[key] = match.group(1)
        if len(found) == 4:
            log("baseline: checksums taken from %s" % path, level=2)
            return found
    return {}


# -------------------------------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One door comparing the model side with the RTL side, down to the three triage decisions.")
    parser.add_argument("--record", "--rekaman", dest="record", default="04015",
                        help="recording whose model artefacts exist in rtlplan2 (default 04015)")
    parser.add_argument("--sensor", help="sensor capture file")
    parser.add_argument("--format", "--bentuk", dest="form", default="frame",
                        help="sensor file shape: frame (8 bytes per sample) or word (one stimulus word per line)")
    parser.add_argument("--engine", "--mesin", dest="engine", choices=("verilator", "icarus"),
                        default="verilator", help="RTL engine (default verilator)")
    parser.add_argument("--limit", type=int, help="cut the record at n samples")
    parser.add_argument("--no-rtl", "--tanpa-rtl", dest="no_rtl", action="store_true",
                        help="model side only, no RTL replay")
    parser.add_argument("--table", "--tabel", dest="table", type=int, default=0,
                        help="also print n rows of side-by-side values per stream")
    parser.add_argument("--event-vectors", "--vektor-peristiwa", dest="event_vectors",
                        help="directory holding fase5/fase6/fase8/fase9 output of the model exporters")
    parser.add_argument("--model-decisions", "--keputusan-model", dest="model_decisions",
                        help="model decision table (window_index, label columns) to use as the triage reference")
    parser.add_argument("--out", "--keluar", dest="out_dir", help="output directory")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="more detail: -v prints every tool command and its output, -vv adds file-level links")
    parser.add_argument("-q", "--quiet", action="store_true", help="step lines only for warnings")
    args = parser.parse_args()

    global _VERBOSITY
    if args.quiet:
        _VERBOSITY = 0
    else:
        _VERBOSITY = 1 + args.verbose
    form = {"bingkai": "frame", "stimulus": "word"}.get(args.form, args.form)
    if form not in ("frame", "word"):
        parser.error("--format takes frame or word (bingkai or stimulus)")

    out_dir = pathlib.Path(args.out_dir).expanduser() if args.out_dir else \
        pathlib.Path.home() / ".hermes" / "cache" / "scratch" / "pintu" / args.record
    (out_dir / "log").mkdir(parents=True, exist_ok=True)
    global _LOG_DIR
    _LOG_DIR = out_dir / "log"

    log("gate comparison door: model against RTL")
    log("output directory : %s" % out_dir)
    log("verbosity        : %d (-v for every tool command and its output)" % _VERBOSITY)

    # ---- step 1: resolve the input source
    started = step(1, TOTAL_STEPS, "resolve the input source")
    source = "record %s" % args.record
    if args.sensor:
        source = "sensor %s" % args.sensor
        # Never link the repo vectors for a sensor capture: another record's event vectors would look
        # complete and the replay would silently compare against the wrong oracle. Only the model run
        # and an explicit --event-vectors may fill these directories.
        staging = stage_vectors(out_dir, args.record, link=False)
    else:
        staging = stage_vectors(out_dir, args.record)
    if args.event_vectors:
        origin = pathlib.Path(args.event_vectors).expanduser()
        for name in ("fase5", "fase6", "fase8", "fase9"):
            target_dir = staging / name
            target_dir.mkdir(parents=True, exist_ok=True)
            for path in sorted((origin / name).glob("*")):
                target = target_dir / path.name
                if not target.exists() and not target.is_symlink():
                    target.symlink_to(path)
        log("event vectors linked from %s" % origin)
    step_done(1, "resolve the input source", started, source)

    # ---- step 2: stage the vector directories the bench reads
    started = step(2, TOTAL_STEPS, "stage the vector directories")
    step_done(2, "stage the vector directories", started, str(staging))

    # ---- step 3: model side
    started = step(3, TOTAL_STEPS, "model side")
    if args.sensor:
        model_from_sensor(pathlib.Path(args.sensor), form, out_dir)
        model_detail = "columns produced from the frozen chain"
    else:
        model_detail = "artefacts already present"
        log("model: using the artefacts already in rtlplan2/fase0 and rtlplan2/fase5")
    arm = "berpenanda"
    if args.model_decisions:
        model_file = pathlib.Path(args.model_decisions).expanduser()
        model_detail = "decision table given with --model-decisions"
    elif not args.sensor:
        model_file = ROOT / "rtlplan2" / "fase5" / ("%s.decisions.berpenanda.csv" % args.record)
    else:
        candidate = staging / "fase5" / "04015.decisions.berpenanda.csv"
        model_file = candidate if candidate.exists() else None
    samples = count_lines(staging / "fase0" / ("%s.masukan16.hex" % args.record))
    if args.limit:
        samples = min(samples, args.limit)
    if model_file is None or not model_file.exists():
        log("model: no decision table for this input, so the triage will not be compared")
        log("       window classes are a function of the rhythm annotation, not of the stimulus words,")
        log("       so an input without rhythm labels has no model classes. Supply the labels through the")
        log("       model chain, or point at an existing table with --model-decisions.")
        model_file = None
    else:
        log("model: decision table %s" % model_file)
    step_done(3, "model side", started, model_detail)

    # ---- step 4: RTL replay
    started = step(4, TOTAL_STEPS, "RTL replay with +DUMP")
    rtl_note = None
    if args.no_rtl:
        log("rtl: skipped because --no-rtl was given")
        step_done(4, "RTL replay with +DUMP", started, "skipped")
    else:
        columns = staging / "fase0" / ("%s.masukan16.hex" % args.record)
        if args.sensor and not columns.exists():
            die("model columns are missing at %s" % columns)
        missing = missing_vectors(staging)
        if missing:
            log("rtl: the event vectors this record needs are incomplete: %s" % ", ".join(missing))
            log("     without them the full-chain testbench refuses to run ($fatal), so the replay is")
            log("     skipped. The model side is still available with --no-rtl.")
            step_done(4, "RTL replay with +DUMP", started, "skipped, %d vector files missing" % len(missing))
        else:
            rtl_note = run_rtl(staging, out_dir, args.engine, args.limit)
            step_done(4, "RTL replay with +DUMP", started,
                      "exit %s, %.1f s" % (rtl_note.get("code"), rtl_note.get("seconds", 0)))

    # ---- step 5: per-sample comparison
    started = step(5, TOTAL_STEPS, "per-sample comparison")
    per_sample = None
    if rtl_note and rtl_note.get("code") == 0:
        per_sample = compare_streams(pathlib.Path(rtl_note["dump"]), out_dir, staging / "fase0")
        bad = [entry["stream"] for entry in per_sample if entry["mismatches"]]
        step_done(5, "per-sample comparison", started,
                  "0 mismatches on all six streams" if not bad else "mismatching streams: %s" % ", ".join(bad))
    else:
        log("compare: skipped, no completed RTL replay")
        step_done(5, "per-sample comparison", started, "skipped")

    # ---- step 6: triage comparison
    started = step(6, TOTAL_STEPS, "triage comparison")
    decisions = None
    if rtl_note and rtl_note.get("code") == 0 and model_file:
        decisions = compare_decisions(pathlib.Path(rtl_note["dump"]), staging / "fase9", model_file, arm)
        step_done(6, "triage comparison", started,
                  "%d of %d windows agree" % (decisions.get("agree"), decisions.get("rows"))
                  if decisions.get("available") else "no decision files")
    else:
        log("triage: skipped, %s" % ("no completed RTL replay" if not rtl_note else "no model decision table"))
        step_done(6, "triage comparison", started, "skipped")

    # ---- step 7: summary
    started = step(7, TOTAL_STEPS, "summary")
    baseline = baseline_from_reports()
    full_length = args.limit is None
    rtl_skipped = rtl_note is None
    model_only = None
    if rtl_skipped and model_file:
        model_only = triage_model_only(model_file, staging / "fase9" / ("%s.berpenanda.asli.hex" % args.record))
    passed = print_summary(source, args.record, samples, rtl_note, per_sample, decisions, baseline,
                           full_length, rtl_skipped, model_only)
    step_done(7, "summary", started, "PASS" if passed else "REVIEW")
    payload = {
        "source": source, "record": args.record, "samples": samples, "engine": args.engine,
        "full_length": full_length, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_seconds": round(time.monotonic() - _T0, 1), "rtl": rtl_note,
        "per_sample": per_sample, "decisions": decisions, "model_only": model_only,
        "baseline": baseline, "passed": passed, "out_dir": str(out_dir),
        "steps": _STEPS, "run_log": _RUN_LOG,
    }
    write_report(out_dir, payload)
    print("")
    print("gate: report written to %s" % (out_dir / "SUMMARY.md"))
    print("gate: machine-readable summary %s" % (out_dir / "summary.json"))
    print("gate: step-by-step log %s" % (out_dir / "pintu.log"))
    (out_dir / "pintu.log").write_text("\n".join(_RUN_LOG) + "\n")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
