#!/usr/bin/env python3
"""Build the Fase-9 testbench vectors for the triage classifier from the golden data.

Reads, and never writes, the frozen golden data:
  rtlplan2/fase5/04015.decisions.csv            588 rows, raw interval series arm
  rtlplan2/fase5/04015.decisions.berpenanda.csv 602 rows, marked interval series arm
  rtlplan2/fase5/04015.manifest.fase5.json      triage_gate: predicate and every arm count
  rtlplan2/fase5/04015.windows.csv              label_class per marked window
  model/rantai-afib-lite/fixture/04015_30m.npz  jendela_fitur, jendela_kelas_benar (raw arm)
  model/rantai-afib-lite/vektor/04015_berpenanda.npz  jendela_fitur_berpenanda, kelas

Writes, into this directory: one 32 bit hex word per line, 8 digits, $readmemh compatible,
plus a manifest that records every count, every code and the sha256 of every file, so the
testbench can be audited later without re-deriving anything.

Why the feature words have to be encoded here (the one arithmetic this phase owns):
  the classifier compares integer words, the golden gate is stated on floats
  (`ratio > 0.165 and entropy_over_4 > 0.63`, manifest triage_gate.predicate). The plan
  pins the feature formats: ratio is Q1.16 in W_F_RATIO = 17 bits, entropy/4 is Q1.14 in
  W_F_ENT = 15 bits (afib_lite_pkg lines 65 and 66). The register codes are the same
  numbers rounded to those formats: 0.165 * 2**16 = 10813.44 -> 10813 and
  0.63 * 2**14 = 10321.92 -> 10322, which are exactly the two values the manifest calls
  ratio_register_q16 and entropy_register_q14. Rounding is ties to even, the rule the
  package names RND_TIES_EVEN.
  This script proves the encoding is boundary safe instead of assuming it: it counts the
  windows whose integer comparison disagrees with the float comparison for round, floor and
  truncate. The count is written into the manifest.
"""

import csv
import hashlib
import json
import pathlib

import numpy as np

REPO = pathlib.Path("/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite")
F5 = REPO / "rtlplan2" / "fase5"
MODEL = REPO / "model" / "rantai-afib-lite"
OUT = REPO / "rtl" / "tb" / "vektor" / "fase9"

W_F_RATIO = 17      # afib_lite_pkg::W_F_RATIO
W_F_ENT = 15        # afib_lite_pkg::W_F_ENT
Q_RATIO = 1 << 16   # ratio Q1.16
Q_ENT = 1 << 14      # entropy/4 Q1.14

KELAS_UNDECIDED = 0
KELAS_NORMAL = 1
KELAS_REVIEW = 2


def write_hex(words, name):
    data = b"".join(b"%08x\n" % (int(w) & 0xFFFFFFFF) for w in words)
    path = OUT / name
    path.write_bytes(data)
    return {"words": len(words), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def read_csv(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def quant_round(x, scale):
    return int(np.rint(np.asarray(x, float) * scale))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with open(F5 / "04015.manifest.fase5.json") as fh:
        man = json.load(fh)
    gate = man["triage_gate"]
    ratio_code = int(gate["ratio_register_q16"])
    ent_code = int(gate["entropy_register_q14"])
    pred = gate["predicate"]
    assert pred == "ratio > 0.165 and entropy_over_4 > 0.63", pred
    t_ratio_f, t_ent_f = 0.165, 0.63
    assert quant_round(t_ratio_f, Q_RATIO) == ratio_code, "manifest code != rounded 0.165"
    assert quant_round(t_ent_f, Q_ENT) == ent_code, "manifest code != rounded 0.63"

    fixture = np.load(MODEL / "fixture" / "04015_30m.npz", allow_pickle=True)
    vek = np.load(MODEL / "vektor" / "04015_berpenanda.npz", allow_pickle=True)
    dec_raw = read_csv(F5 / "04015.decisions.csv")
    dec_mark = read_csv(F5 / "04015.decisions.berpenanda.csv")
    win = read_csv(F5 / "04015.windows.csv")

    assert len(dec_raw) == 588 and len(dec_mark) == 602 and len(win) == 602

    arms = {}
    for name, rows, fit, kelas, kelas_src in (
            ("mentah", dec_raw, fixture["jendela_fitur"],
             fixture["jendela_kelas_benar"], "fixture jendela_kelas_benar"),
            ("berpenanda", dec_mark, vek["jendela_fitur_berpenanda"],
             vek["jendela_kelas_berpenanda"], "vektor jendela_kelas_berpenanda")):
        assert fit.shape == (len(rows), 4), (name, fit.shape)
        assert kelas.shape == (len(rows),), (name, kelas.shape)
        ratio = np.array([float(r["ratio"]) for r in rows], float)
        ent = np.array([float(r["entropy4"]) for r in rows], float)
        fired = np.array([int(r["fired"]) for r in rows], int)
        label = np.array([int(r["label"]) for r in rows], int)
        wi = np.array([int(r["window_index"]) for r in rows], int)
        # the CSV columns must be the frozen model's own feature columns, both arms
        assert np.array_equal(ratio, fit[:, 1]), name
        assert np.array_equal(ent, fit[:, 3]), name
        # the marked arm's ground truth also has to be the windows.csv column
        if name == "berpenanda":
            assert [str(c) for c in kelas] == [r["label_class"] for r in win], name
            assert np.array_equal(wi, np.array([int(r["window_index"]) for r in win]))
        # the CSV's own float predicate and the model's float predicate
        assert np.array_equal(fired, ((ratio > t_ratio_f) & (ent > t_ent_f)).astype(int)), name

        # feature words in the package formats
        qr_round = np.array([quant_round(v, Q_RATIO) for v in ratio], np.int64)
        qe_round = np.array([quant_round(v, Q_ENT) for v in ent], np.int64)
        qr_floor = np.array([int(np.floor(v * Q_RATIO)) for v in ratio], np.int64)
        qe_floor = np.array([int(np.floor(v * Q_ENT)) for v in ent], np.int64)
        qr_trunc = np.array([int(v * Q_RATIO) for v in ratio], np.int64)
        qe_trunc = np.array([int(v * Q_ENT) for v in ent], np.int64)

        b_round = (qr_round > ratio_code) & (qe_round > ent_code)
        b_floor = (qr_floor > ratio_code) & (qe_floor > ent_code)
        b_trunc = (qr_trunc > ratio_code) & (qe_trunc > ent_code)
        straddle = {"round": int((b_round != fired).sum()),
                    "floor": int((b_floor != fired).sum()),
                    "truncate": int((b_trunc != fired).sum())}
        assert qr_round.max() < (1 << W_F_RATIO), qr_round.max()
        assert qe_round.max() < (1 << W_F_ENT), qe_round.max()

        asli = np.array([KELAS_REVIEW if str(c) == "AFIB" else KELAS_NORMAL for c in kelas], np.int64)
        pred_kls = np.array([KELAS_REVIEW if f else KELAS_NORMAL for f in fired], np.int64)
        assert np.array_equal(pred_kls, label), name

        census = {"windows": int(fired.size), "afib": int((asli == KELAS_REVIEW).sum()),
                  "n": int((asli == KELAS_NORMAL).sum()), "fired": int(fired.sum()),
                  "true_positive": int((fired.astype(bool) & (asli == KELAS_REVIEW)).sum()),
                  "false_positive": int((fired.astype(bool) & (asli == KELAS_NORMAL)).sum()),
                  "false_negative": int(((~fired.astype(bool)) & (asli == KELAS_REVIEW)).sum()),
                  "true_negative": int(((~fired.astype(bool)) & (asli == KELAS_NORMAL)).sum())}
        ref = gate["marked_arm" if name == "berpenanda" else "raw_arm"]
        assert census["windows"] == int(ref["windows"]), (name, census, ref)
        assert census["fired"] == int(ref["fired"]), (name, census, ref)
        for k in ("true_positive", "false_positive", "false_negative"):
            assert census[k] == int(ref[k]), (name, k, census, ref)

        arms[name] = dict(ratio=ratio, ent=ent, fired=fired, qr=qr_round, qe=qe_round,
                          asli=asli, kelas=pred_kls, wi=wi, census=census,
                          straddle=straddle, kelas_src=kelas_src)

    m, b = arms["mentah"], arms["berpenanda"]

    # ---- perturbed threshold runs, recomputed from the same golden feature columns
    mut_ratio, mut_ent = 0, 0
    mut_fired = (b["qr"] > mut_ratio) & (b["qe"] > mut_ent)
    mut_kelas = np.where(mut_fired, KELAS_REVIEW, KELAS_NORMAL)
    mut_census = {"windows": int(b["qr"].size), "fired": int(mut_fired.sum()),
                  "ratio_code": mut_ratio, "entropy_code": mut_ent,
                  "predicate": "ratio_q16 > 0 and entropy_q14 > 0"}

    # the guard run enrolls the entropy arm alone, so a stage that ignores bit 15 of the field
    # would fire on almost every window instead of on none of them
    guard_ent = 1 << W_F_ENT   # bit 15 of the 16 bit register field set
    guard_fired = np.zeros(b["qr"].size, dtype=bool)   # the entropy arm can never be satisfied
    guard_kelas = np.where(guard_fired, KELAS_REVIEW, KELAS_NORMAL)
    guard_census = {"windows": int(b["qr"].size), "fired": int(guard_fired.sum()),
                    "ratio_code": ratio_code, "entropy_code": guard_ent,
                    "arm_select": 0b00010,
                    "predicate": "entropy arm only, entropy field 0x8000: arm unsatisfiable"}

    arm_single = 0b00010   # only the entropy arm enrolled, b4 clear
    single_fired = (b["qe"] > ent_code)
    single_kelas = np.where(single_fired, KELAS_REVIEW, KELAS_NORMAL)
    single_census = {"windows": int(b["qr"].size), "fired": int(single_fired.sum()),
                     "arm_select": int(arm_single),
                     "predicate": "entropy arm only: entropy_q14 > 10322"}

    files = {}
    files.update({("04015.%s.%s.hex" % (n, s)): write_hex(a[s], "04015.%s.%s.hex" % (n, s))
                  for n, a in arms.items()
                  for s in ("qr", "qe", "kelas", "asli", "wi")})
    files["04015.mutasi.kelas.hex"] = write_hex(mut_kelas, "04015.mutasi.kelas.hex")
    files["04015.guard.kelas.hex"] = write_hex(guard_kelas, "04015.guard.kelas.hex")
    files["04015.tunggal.kelas.hex"] = write_hex(single_kelas, "04015.tunggal.kelas.hex")

    counts = [b["census"]["windows"], m["census"]["windows"],
              b["census"]["fired"], m["census"]["fired"],
              b["census"]["true_positive"], b["census"]["false_positive"],
              b["census"]["false_negative"], b["census"]["true_negative"],
              m["census"]["true_positive"], m["census"]["false_positive"],
              m["census"]["false_negative"], m["census"]["true_negative"],
              b["census"]["afib"], b["census"]["n"], m["census"]["afib"], m["census"]["n"],
              ratio_code, ent_code,
              0x0F, 0x07,
              mut_ratio, mut_ent, guard_ent, int(arm_single),
              mut_census["fired"], single_census["fired"],
              single_census["windows"]]
    files["04015.fase9.counts.hex"] = write_hex(counts, "04015.fase9.counts.hex")

    manifest = {
        "record": "04015",
        "generator": str(pathlib.Path(__file__).resolve()),
        "golden_sources": {
            "decisions_raw": {"path": str(F5 / "04015.decisions.csv"),
                              "rows": len(dec_raw), "arm": "raw interval series"},
            "decisions_marked": {"path": str(F5 / "04015.decisions.berpenanda.csv"),
                                 "rows": len(dec_mark), "arm": "marked interval series"},
            "manifest_fase5": str(F5 / "04015.manifest.fase5.json"),
            "fixture": str(MODEL / "fixture" / "04015_30m.npz"),
            "vektor": str(MODEL / "vektor" / "04015_berpenanda.npz"),
        },
        "triage_gate": {"predicate": pred,
                        "ratio_register_q16": ratio_code,
                        "entropy_register_q14": ent_code,
                        "ratio_q16_from_float": quant_round(t_ratio_f, Q_RATIO),
                        "entropy_q14_from_float": quant_round(t_ent_f, Q_ENT)},
        "feature_formats": {"ratio": "Q1.16 in %d bits" % W_F_RATIO,
                            "entropy_over_4": "Q1.14 in %d bits" % W_F_ENT,
                            "rounding": "ties to even (RND_TIES_EVEN)"},
        "boundary_straddles": {n: a["straddle"] for n, a in arms.items()},
        "arms": {n: {"census": a["census"], "ground_truth_source": a["kelas_src"],
                     "ratio_q16_max": int(a["qr"].max()), "ent_q14_max": int(a["qe"].max())}
                 for n, a in arms.items()},
        "perturbed_runs": {"mutasi": mut_census, "guard": guard_census, "tunggal": single_census},
        "counts_words": {"order": [
            "n_marked", "n_raw", "fired_marked", "fired_raw",
            "tp_marked", "fp_marked", "fn_marked", "tn_marked",
            "tp_raw", "fp_raw", "fn_raw", "tn_raw",
            "afib_marked", "normal_marked", "afib_raw", "normal_raw",
            "ratio_code", "entropy_code", "arm_marked", "arm_raw",
            "mut_ratio_code", "mut_entropy_code", "guard_entropy_code", "arm_single",
            "fired_mutasi", "fired_tunggal", "n_tunggal"],
            "values": counts},
        "files": files,
    }
    (OUT / "04015.fase9.manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")

    print("== siapkan_vektor_fase9 ==")
    print("  ratio code %d  entropy code %d" % (ratio_code, ent_code))
    for n, a in arms.items():
        print("  arm %-10s windows %d AFIB %d N %d fired %d TP %d FP %d FN %d TN %d  straddle %s"
              % (n, a["census"]["windows"], a["census"]["afib"], a["census"]["n"],
                 a["census"]["fired"], a["census"]["true_positive"], a["census"]["false_positive"],
                 a["census"]["false_negative"], a["census"]["true_negative"], a["straddle"]))
        print("      q16 max %d (17 bit), q14 max %d (15 bit)"
              % (int(a["qr"].max()), int(a["qe"].max())))
    print("  mutasi t=(0,0)      fired %d" % mut_census["fired"])
    print("  guard ent=0x8000    fired %d" % guard_census["fired"])
    print("  tunggal arm=0b00010 fired %d" % single_census["fired"])
    print("  files written: %d" % len(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
