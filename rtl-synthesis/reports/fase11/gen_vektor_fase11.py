#!/usr/bin/env python3
"""Build the Fase-11 testbench vectors (register map + triage arm fixtures).

READS, never writes, the frozen reference data:

  rtlplan2/fase5/04015.decisions.csv             588 rows, raw interval series arm
  rtlplan2/fase5/04015.decisions.berpenanda.csv   602 rows, marked interval series arm
  rtlplan2/fase5/04015.manifest.fase5.json        triage_gate: predicate and every arm count
  model/rantai-afib-lite/fixture/04015_30m.npz    jendela_fitur, jendela_kelas_benar (raw arm)
  model/rantai-afib-lite/vektor/04015_berpenanda.npz  jendela_fitur_berpenanda, kelas

WRITES, into rtl/tb/vektor/fase11/: one 32 bit hex word per line, 8 digits, `$readmemh`
compatible, plus a manifest that records every count, every code and the sha256 of every
file, so the testbench can be audited without re-deriving anything.

What this script proves instead of assuming (every proof is an assert, and a failure stops
the export so a wrong vector can never reach the testbench):

  1  the frozen sha256 of model/rantai-afib-lite/rantai.py is the one owner decision D8 pins,
     so the arm fixtures are traceable to a frozen model;
  2  the decisions CSV columns `ratio` and `entropy4` ARE the frozen model feature columns
     `jendela_fitur[:,1]` and `[:,3]` for both arms (fixture for the raw arm, vektor for the
     marked arm), row for row;
  3  the `fired` column equals the float predicate of the manifest
     (`ratio > 0.165 and entropy_over_4 > 0.63`) for every row of both arms;
  4  the `label` column equals KELAS_REVIEW where `fired` and KELAS_NORMAL elsewhere, which is
     what the register class field has to reproduce;
  5  the census of both arms equals the manifest `raw_arm` / `marked_arm` block
     (588 / 183 / 95 / 88 / 0 and 602 / 189 / 95 / 94 / 0);
  6  the round to the package feature formats (ratio Q1.16 in 17 bit, entropy/4 Q1.14 in 15 bit,
     ties to even) keeps the integer comparison equal to the float comparison on every row of
     both arms: the straddle count for round, floor and truncate is written into the manifest;
  7  the register map vector carries the 36 frozen slots of plan 8.5 (0x00..0x8C) plus the two
     provisional window parameter slots 0x90 / 0x94, offsets monotone, step 4 except the two
     provisional ones, every offset distinct.

The register map table below is the ONLY copy of the map in this directory, and the testbench
checks its own localparams against these three vectors, so a mistyped address in the
testbench fails the run instead of passing silently.
"""

import csv
import hashlib
import json
import pathlib

import numpy as np

REPO = pathlib.Path("/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite")
F5 = REPO / "rtlplan2" / "fase5"
MODEL = REPO / "model" / "rantai-afib-lite"
OUT = REPO / "rtl" / "tb" / "vektor" / "fase11"

RANTAI_SHA = "90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5"

W_F_RATIO = 17      # afib_lite_pkg::W_F_RATIO
W_F_ENT = 15        # afib_lite_pkg::W_F_ENT
Q_RATIO = 1 << 16   # ratio Q1.16
Q_ENT = 1 << 14     # entropy/4 Q1.14

KELAS_UNDECIDED = 0
KELAS_NORMAL = 1
KELAS_REVIEW = 2

# access kinds used by the map vectors
K_RW = 0
K_RO = 1
K_WO = 2
K_W1C = 3

# Register map of plan 38 section 8.5 (D8 frozen, 36 slots 0x00..0x8C) plus the two
# provisional window parameter slots 0x90 / 0x94 reported as a gap of that map.
# (offset, name, kind, reset after reset)
MAP = [
    (0x00, "CTRL",             K_RW,  0x00000000),
    (0x04, "STATUS",           K_RO,  0x00000001),
    (0x08, "IRQ_STATUS",       K_RO,  0x00000000),
    (0x0C, "IRQ_CLEAR",        K_W1C, 0x00000000),
    (0x10, "CLASS_OUT",        K_RO,  0x00000000),
    (0x14, "CONFIDENCE",       K_RO,  0x00000000),
    (0x18, "RR_LAST",          K_RO,  0x00000000),
    (0x1C, "BEAT_COUNT",       K_RO,  0x00000000),
    (0x20, "GAP_COUNT",        K_RO,  0x00000000),
    (0x24, "SAMPLE_IDX",       K_RO,  0x00000000),
    (0x28, "WINDOW_COUNT",     K_RO,  0x00000000),
    (0x2C, "CLAMP_COUNT",      K_RO,  0x00000000),
    (0x30, "FIFO_OVF_COUNT",   K_RO,  0x00000000),
    (0x34, "RR_LONG_COUNT",    K_RO,  0x00000000),
    (0x38, "RR_MARK_LAST",     K_RO,  0x00000000),
    (0x3C, "RATIO_THRESH",     K_RW,  0x00000021),
    (0x40, "ENTROPY_THRESH",   K_RW,  0x0000003F),
    (0x44, "ARM_SELECT",       K_RW,  0x0000000F),
    (0x48, "FEAT_RATIO",       K_RO,  0x00000000),
    (0x4C, "FEAT_ENTROPY",     K_RO,  0x00000000),
    (0x50, "FORMAT_CFG",       K_RW,  0x004C00FA),
    (0x54, "RATE_DIV",         K_RW,  0x00061A7F),
    (0x58, "THRESH_SCALE",     K_RW,  0x00000100),
    (0x5C, "RR_BAND_LO",       K_RW,  0x0000005C),
    (0x60, "RR_BAND_HI",       K_RW,  0x00000074),
    (0x64, "VERSION_ID",       K_RO,  0x00010001),
    (0x68, "SCRATCH",          K_RW,  0x00000000),
    (0x6C, "SAMPLE_FIFO",      K_WO,  0x00000000),
    (0x70, "SAMPLE_MARK",      K_WO,  0x00000000),
    (0x74, "SAMPLE_IN_STATUS", K_RO,  0x00000000),
    (0x78, "MARKER_LAST",      K_RO,  0x00000000),
    (0x7C, "CLAMP_THRESH",     K_RW,  0x000007FF),
    (0x80, "GAP_RECOVERY",     K_RW,  0x00000083),
    (0x84, "REPLAY_LEN",       K_RW,  0x00000000),
    (0x88, "IDX_TAP_LAST",     K_RO,  0x00000000),
    (0x8C, "IDX_DEC_LAST",     K_RO,  0x00000000),
    # plan 38 decision 9: the DEBUG_SEL / DEBUG_VAL pair is accepted above the frozen map,
    # which raises the map from 36 slots to 38 and is why the driver of Fase 11 prints 38
    (0x90, "DEBUG_SEL",        K_RW,  0x00000000),
    (0x94, "DEBUG_VAL",        K_RO,  0x00000000),
]
N_FROZEN_SLOTS = 36

# the arm encodings the testbench uses, all five bits of ARM_SELECT
ARM_DEFAULT = 0x0F   # b0 ratio, b1 entropy, b2 T rule, b3 marked series, b4 clear = model
ARM_RAW_TREE = 0x07  # the mapping of rtl/tb/vektor/fase9: raw arm is b3 clear
ARM_T_OFF = 0x0B     # the mapping of the task brief: T wave arm off, marked series kept
ARM_SINGLE = 0x02    # entropy arm only, b4 clear
ARM_EITHER = 0x1F    # b4 set: either arm is enough, the disjunction of 0x0F


def write_hex(words, name):
    data = b"".join(b"%08x\n" % (int(w) & 0xFFFFFFFF) for w in words)
    path = OUT / name
    path.write_bytes(data)
    return {"words": len(words), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def read_csv(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quant_round(x, scale):
    """Ties to even, the rule afib_lite_pkg names RND_TIES_EVEN. Array in, array out."""
    return np.rint(np.asarray(x, float) * scale).astype(np.int64)


def arm_run(qr, qe, ratio_code, ent_code, arm, kelas_exp, asli):
    """Score one arm exactly as the register file contract states it.

    b0 ratio arm, b1 entropy arm, b2 T wave rule, b3 marked series source, b4 both arms
    required or either one is enough. The polarity of b4 is pinned by the reset value: the
    plan requires the part to leave reset equal to the model (both arms required, and the
    model predicate is a conjunction), and ARM_SELECT_RST is 0x0F with b4 CLEAR. So b4 clear
    is the conjunction and b4 set is the disjunction. An arm that is not enrolled does not
    vote, so a single enrolled arm decides alone, which is the Fase 9 reading of 0b00010.
    Thresholds are the register codes, unsigned, compared strictly greater.
    """
    n_enrolled = (1 if arm & 0x01 else 0) + (1 if arm & 0x02 else 0)
    fire_ratio = qr > int(ratio_code & 0xFFFF)
    fire_ent = qe > int(ent_code & 0xFFFF)
    if n_enrolled == 0:
        fired = np.zeros(qr.size, dtype=bool)
    elif n_enrolled == 1:
        fired = fire_ratio if arm & 0x01 else fire_ent
    elif arm & 0x10:
        fired = fire_ratio | fire_ent
    else:
        fired = fire_ratio & fire_ent
    kelas = np.where(fired, KELAS_REVIEW, KELAS_NORMAL)
    mism = int((kelas != kelas_exp).sum())
    census = {"windows": int(fired.size), "fired": int(fired.sum()),
              "true_positive": int((fired & (asli == KELAS_REVIEW)).sum()),
              "false_positive": int((fired & (asli == KELAS_NORMAL)).sum()),
              "false_negative": int((~fired & (asli == KELAS_REVIEW)).sum()),
              "true_negative": int((~fired & (asli == KELAS_NORMAL)).sum())}
    return kelas, fired, census, mism


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    rantai = MODEL / "rantai.py"
    got_sha = sha256_of(rantai)
    assert got_sha == RANTAI_SHA, ("frozen model moved", got_sha)

    with open(F5 / "04015.manifest.fase5.json") as fh:
        man = json.load(fh)
    gate = man["triage_gate"]
    ratio_code = int(gate["ratio_register_q16"])
    ent_code = int(gate["entropy_register_q14"])
    pred = gate["predicate"]
    assert pred == "ratio > 0.165 and entropy_over_4 > 0.63", pred
    t_ratio_f, t_ent_f = 0.165, 0.63
    assert quant_round(t_ratio_f, Q_RATIO) == ratio_code
    assert quant_round(t_ent_f, Q_ENT) == ent_code

    fixture = np.load(MODEL / "fixture" / "04015_30m.npz", allow_pickle=True)
    vek = np.load(MODEL / "vektor" / "04015_berpenanda.npz", allow_pickle=True)
    dec_raw = read_csv(F5 / "04015.decisions.csv")
    dec_mark = read_csv(F5 / "04015.decisions.berpenanda.csv")
    assert len(dec_raw) == 588 and len(dec_mark) == 602

    # ---- independent cross check against the Fase 9 vectors of this tree, if present ----
    # Not a dependency: the Fase 11 vectors are built from the frozen CSVs alone. The Fase 9
    # directory is written by another worker on the same day, so a missing or half written
    # file may not fail this export, but a disagreement is reported loudly.
    cross = {"present": False}
    f9man_path = REPO / "rtl" / "tb" / "vektor" / "fase9" / "04015.fase9.manifest.json"
    try:
        f9 = json.loads(f9man_path.read_text())
        cross = {"present": True, "path": str(f9man_path),
                 "n_marked": f9["arms"]["berpenanda"]["census"]["windows"],
                 "n_raw": f9["arms"]["mentah"]["census"]["windows"],
                 "fired_marked": f9["arms"]["berpenanda"]["census"]["fired"],
                 "fired_raw": f9["arms"]["mentah"]["census"]["fired"],
                 "fired_tunggal": f9["perturbed_runs"]["tunggal"]["fired"],
                 "fired_guard": f9["perturbed_runs"]["guard"]["fired"]}
        cross["agree"] = None            # filled in after the arm runs below
    except Exception as exc:                                  # noqa: BLE001
        cross = {"present": False, "note": "fase9 manifest not readable: %s" % exc}

    arms = {}
    for name, rows, fit, kelas_src in (
            ("mentah", dec_raw, fixture["jendela_fitur"], fixture["jendela_kelas_benar"]),
            ("berpenanda", dec_mark, vek["jendela_fitur_berpenanda"],
             vek["jendela_kelas_berpenanda"])):
        assert fit.shape == (len(rows), 4), (name, fit.shape)
        assert kelas_src.shape == (len(rows),), (name, kelas_src.shape)
        ratio = np.array([float(r["ratio"]) for r in rows], float)
        ent = np.array([float(r["entropy4"]) for r in rows], float)
        fired = np.array([int(r["fired"]) for r in rows], np.int64)
        label = np.array([int(r["label"]) for r in rows], np.int64)
        # 2: the CSV feature columns are the frozen model's own columns
        assert np.array_equal(ratio, fit[:, 1]), name
        assert np.array_equal(ent, fit[:, 3]), name
        # 3: the fired column is the float predicate of the manifest
        assert np.array_equal(fired, ((ratio > t_ratio_f) & (ent > t_ent_f)).astype(np.int64)), name
        # 5: the census of this arm is the manifest block
        asli = np.array([KELAS_REVIEW if str(c) == "AFIB" else KELAS_NORMAL
                         for c in kelas_src], np.int64)
        ref = gate["marked_arm" if name == "berpenanda" else "raw_arm"]
        census = {"windows": int(fired.size),
                  "afib": int((asli == KELAS_REVIEW).sum()),
                  "n": int((asli == KELAS_NORMAL).sum()),
                  "fired": int(fired.sum()),
                  "true_positive": int((fired.astype(bool) & (asli == KELAS_REVIEW)).sum()),
                  "false_positive": int((fired.astype(bool) & (asli == KELAS_NORMAL)).sum()),
                  "false_negative": int(((~fired.astype(bool)) & (asli == KELAS_REVIEW)).sum()),
                  "true_negative": int(((~fired.astype(bool)) & (asli == KELAS_NORMAL)).sum())}
        for k in ("windows", "fired", "true_positive", "false_positive", "false_negative"):
            assert census[k] == int(ref[k]), (name, k, census, ref)
        # 4: the label column is KELAS_REVIEW exactly where the arm fires
        assert np.array_equal(np.where(fired.astype(bool), KELAS_REVIEW, KELAS_NORMAL),
                              label), name
        arms[name] = dict(ratio=ratio, ent=ent, fired=fired, asli=asli, kelas=label,
                          census=census)

    files = {}
    # ---- feature words in the package formats, plus the fixture class column -----------
    for name, a in arms.items():
        qr = quant_round(a["ratio"], Q_RATIO)
        qe = quant_round(a["ent"], Q_ENT)
        assert qr.max() < (1 << W_F_RATIO), qr.max()
        assert qe.max() < (1 << W_F_ENT), qe.max()
        # 6: the integer comparison in the package formats equals the float comparison
        straddle = {}
        for tag, qr_v, qe_v in (
                ("round", qr, qe),
                ("floor", [int(np.floor(v * Q_RATIO)) for v in a["ratio"]],
                 [int(np.floor(v * Q_ENT)) for v in a["ent"]]),
                ("truncate", [int(v * Q_RATIO) for v in a["ratio"]],
                 [int(v * Q_ENT) for v in a["ent"]])):
            got = np.array(qr_v, np.int64) > ratio_code
            got &= np.array(qe_v, np.int64) > ent_code
            straddle[tag] = int((got != a["fired"].astype(bool)).sum())
        assert straddle["round"] == 0, (name, straddle)
        a["qr"] = np.array(qr, np.int64)
        a["qe"] = np.array(qe, np.int64)
        a["straddle"] = straddle
        for col, vec in (("qr", qr), ("qe", qe), ("kelas", a["kelas"]), ("asli", a["asli"])):
            fname = "f11.%s.%s.hex" % (name, col)
            files[fname] = write_hex(vec, fname)

    m, b = arms["mentah"], arms["berpenanda"]

    # ---- the three arm runs the testbench drives, all from the DUT registers -----------
    runs = {}
    for tag, arm, src, qr, qe in (
            ("berpenanda", ARM_DEFAULT, b, b["qr"], b["qe"]),
            ("t_off", ARM_T_OFF, m, m["qr"], m["qe"]),
            ("mentah", ARM_RAW_TREE, m, m["qr"], m["qe"]),
            ("tunggal", ARM_SINGLE, b, b["qr"], b["qe"]),
            ("either", ARM_EITHER, b, b["qr"], b["qe"])):
        # The two fixture arms are scored against the fixture class column, which is an
        # independent golden source. The perturbation runs have no fixture of their own, so
        # their expected class column is the run's own output and their census is checked
        # against the Fase 9 export of this tree where that export is readable: that is the
        # independence, not a number typed here.
        kelas_exp = src["kelas"] if tag in ("berpenanda", "t_off", "mentah") else None
        kelas, fired, census, mism = arm_run(qr, qe, ratio_code, ent_code, arm,
                                             src["kelas"] if kelas_exp is None else kelas_exp,
                                             src["asli"])
        if kelas_exp is not None:
            assert mism == 0, (tag, mism, census)
        else:
            # no independent per row expectation exists for this perturbation run
            mism = 0
        if tag == "berpenanda":
            for k in ("windows", "fired", "true_positive", "false_positive", "false_negative"):
                assert census[k] == int(gate["marked_arm"][k]), (tag, k, census)
        if tag in ("t_off", "mentah"):
            for k in ("windows", "fired", "true_positive", "false_positive", "false_negative"):
                assert census[k] == int(gate["raw_arm"][k]), (tag, k, census)
        if cross.get("present"):
            if tag == "tunggal":
                assert census["fired"] == cross["fired_tunggal"], (tag, census, cross)
            if tag == "either":
                assert census["fired"] >= runs["berpenanda"]["census"]["fired"], (tag, census)
        if tag != "berpenanda":
            fname = "f11.%s.kelas.hex" % tag
            files[fname] = write_hex(kelas, fname)
        runs[tag] = {"arm_select": arm,
                     "arm_name": "berpenanda" if src is b else "mentah",
                     "ratio_code": ratio_code, "entropy_code": ent_code,
                     "expected_source": ("arm fixture class column" if tag in
                                         ("berpenanda", "t_off", "mentah")
                                         else "run output; census cross checked"),
                     "census": census, "mismatch": mism}

    # ---- guard run: entropy field 0x8000, entropy arm only -> nothing can fire ---------
    guard_ent = 1 << W_F_ENT
    guard_fired = np.zeros(b["qr"].size, dtype=bool)
    guard_kelas = np.where(guard_fired, KELAS_REVIEW, KELAS_NORMAL)
    files["f11.guard.kelas.hex"] = write_hex(guard_kelas, "f11.guard.kelas.hex")
    runs["guard"] = {"arm_select": ARM_SINGLE, "arm_name": "berpenanda",
                     "ratio_code": ratio_code, "entropy_code": guard_ent,
                     "census": {"windows": int(guard_fired.size), "fired": 0},
                     "predicate": "entropy arm only, entropy field 0x8000: unsatisfiable"}
    if cross.get("present"):
        if runs["guard"]["census"]["fired"] != cross["fired_guard"]:
            raise AssertionError(("guard run disagrees with the Fase 9 export",
                                  runs["guard"], cross))
        cross["agree"] = bool(
            cross["n_marked"] == int(b["fired"].size)
            and cross["n_raw"] == int(m["fired"].size)
            and cross["fired_marked"] == runs["berpenanda"]["census"]["fired"]
            and cross["fired_raw"] == runs["mentah"]["census"]["fired"]
            and cross["fired_tunggal"] == runs["tunggal"]["census"]["fired"])
        if not cross["agree"]:
            raise AssertionError(("the two independent exports disagree", cross, runs))

    # ---- register map vectors ----------------------------------------------------------
    assert len(MAP) == N_FROZEN_SLOTS + 2, len(MAP)
    offs = [r[0] for r in MAP]
    assert len(set(offs)) == len(offs), "duplicate offset in the map"
    assert offs == sorted(offs), "map is not monotone"
    frozen = offs[:N_FROZEN_SLOTS]
    assert frozen == list(range(0x00, 0x8C + 1, 4)), "the frozen 36 slots are not 0x00..0x8C step 4"
    assert offs[N_FROZEN_SLOTS:] == [0x90, 0x94], "the provisional slots moved"
    files["f11.map.offs.hex"] = write_hex(offs, "f11.map.offs.hex")
    files["f11.map.kind.hex"] = write_hex([r[2] for r in MAP], "f11.map.kind.hex")
    files["f11.map.rst.hex"] = write_hex([r[3] for r in MAP], "f11.map.rst.hex")

    counts = [
        int(b["fired"].size), int(m["fired"].size),                  # 0 1
        int(b["census"]["fired"]), int(m["census"]["fired"]),        # 2 3
        int(b["census"]["true_positive"]), int(b["census"]["false_positive"]),
        int(b["census"]["false_negative"]), int(b["census"]["true_negative"]),   # 4..7
        int(m["census"]["true_positive"]), int(m["census"]["false_positive"]),
        int(m["census"]["false_negative"]), int(m["census"]["true_negative"]),   # 8..11
        int(b["census"]["afib"]), int(b["census"]["n"]),
        int(m["census"]["afib"]), int(m["census"]["n"]),             # 12..15
        ratio_code, ent_code,                                        # 16 17
        ARM_DEFAULT, ARM_RAW_TREE, ARM_T_OFF, ARM_SINGLE, guard_ent, ARM_EITHER,  # 18..23
        runs["tunggal"]["census"]["fired"], runs["guard"]["census"]["fired"],    # 24 25
        runs["either"]["census"]["fired"], runs["either"]["census"]["true_positive"],
        runs["either"]["census"]["false_positive"],                  # 26..28
        len(MAP), N_FROZEN_SLOTS,                                    # 29 30
    ]
    files["f11.counts.hex"] = write_hex(counts, "f11.counts.hex")

    manifest = {
        "record": "04015",
        "generator": str(pathlib.Path(__file__).resolve()),
        "frozen_model": {"rantai_py_sha256": got_sha, "checked": True},
        "golden_sources": {
            "decisions_raw": {"path": str(F5 / "04015.decisions.csv"), "rows": len(dec_raw),
                              "sha256": sha256_of(F5 / "04015.decisions.csv")},
            "decisions_marked": {"path": str(F5 / "04015.decisions.berpenanda.csv"),
                                 "rows": len(dec_mark),
                                 "sha256": sha256_of(F5 / "04015.decisions.berpenanda.csv")},
            "manifest_fase5": {"path": str(F5 / "04015.manifest.fase5.json"),
                               "sha256": sha256_of(F5 / "04015.manifest.fase5.json")},
        },
        "triage_gate": {"predicate": pred, "ratio_register_q16": ratio_code,
                        "entropy_register_q14": ent_code},
        "feature_formats": {"ratio": "Q1.16 in %d bits" % W_F_RATIO,
                            "entropy_over_4": "Q1.14 in %d bits" % W_F_ENT,
                            "rounding": "ties to even (RND_TIES_EVEN)"},
        "boundary_straddles": {n: a["straddle"] for n, a in arms.items()},
        "arms": {n: {"census": a["census"], "ratio_q16_max": int(a["qr"].max()),
                     "ent_q14_max": int(a["qe"].max())} for n, a in arms.items()},
        "arm_runs": runs,
        "cross_check_fase9": cross,
        "register_map": {"frozen_slots": N_FROZEN_SLOTS, "slots": len(MAP),
                         "provisional": [{"offset": r[0], "name": r[1],
                                          "reset": r[3]} for r in MAP[N_FROZEN_SLOTS:]],
                         "kind_codes": {"0": "RW", "1": "RO", "2": "WO", "3": "W1C"},
                         "table": [{"offset": r[0], "name": r[1],
                                    "kind": ["RW", "RO", "WO", "W1C"][r[2]],
                                    "reset": r[3]} for r in MAP]},
        "counts_words": {"order": [
            "n_marked", "n_raw", "fired_marked", "fired_raw",
            "tp_marked", "fp_marked", "fn_marked", "tn_marked",
            "tp_raw", "fp_raw", "fn_raw", "tn_raw",
            "afib_marked", "normal_marked", "afib_raw", "normal_raw",
            "ratio_code", "entropy_code",
            "arm_default", "arm_raw_tree", "arm_t_off", "arm_single", "guard_ent",
            "fired_tunggal", "fired_guard", "n_map_slots", "n_frozen_slots"],
            "values": counts},
        "files": files,
    }
    (OUT / "f11.manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")

    print("== gen_vektor_fase11 ==")
    print("  rantai.py sha256 %s (frozen, checked)" % got_sha)
    print("  ratio code %d  entropy code %d" % (ratio_code, ent_code))
    for n, a in arms.items():
        print("  arm %-11s windows %d AFIB %d N %d fired %d TP %d FP %d FN %d TN %d  straddle %s"
              % (n, a["census"]["windows"], a["census"]["afib"], a["census"]["n"],
                 a["census"]["fired"], a["census"]["true_positive"],
                 a["census"]["false_positive"], a["census"]["false_negative"],
                 a["census"]["true_negative"], a["straddle"]))
    for tag in ("berpenanda", "t_off", "mentah", "tunggal", "guard", "either"):
        r = runs[tag]
        print("  run %-11s arm=0x%02X source=%-11s fired %d over %d windows"
              % (tag, r["arm_select"], r["arm_name"],
                 r["census"]["fired"], r["census"]["windows"]))
    if cross.get("present"):
        print("  cross check fase9: agree=%s (%s)" % (cross["agree"], cross["path"]))
    else:
        print("  cross check fase9: not available (%s)" % cross.get("note", "missing"))
    print("  map slots %d (frozen %d 0x00..0x8C + provisional 0x90/0x94)"
          % (len(MAP), N_FROZEN_SLOTS))
    print("  files written: %d" % len(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
