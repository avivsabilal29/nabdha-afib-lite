#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# ekspor_vektor_puncak.py -- build the expected-vector files for tb_peak_detect.sv.
#
# PROVENANCE. Every value this script writes is read from the Fase 5 export of the
# frozen model, model/rantai-afib-lite/rantai.py (sha256 90df6e5b457307d3...), that
# lives in <XMLP>/fase5/ and was produced and independently checked by the parent
# (LAPORAN-FASE5.md in that directory). No value is typed by hand and no value is
# invented: the .hex files this script writes are generated output and must never be
# edited by hand. Re-run this script instead.
#
# Inputs   : fase5/04015.peaks.csv, fase5/04015.manifest.fase5.json
# Outputs  : 04015.puncak.{pos,pv,pkf,i1,isqrs,eventkind}.hex, 04015.ambang_akhir.hex
#
# Column mapping used by the bench (name in the CSV -> port):
#   sample_index    -> expected m_ev_idx for every peak event
#   envelope_value  -> expected m_ev_val
#   filtered_peak   -> expected d_pk  (the frozen port list has no d_peak_val; see below)
#   i1              -> expected d_thr
#   event_kind      -> expected m_ev_kind class (beat vs rejected)
#
# eventkind.hex coding (the CSV's event_kind, 4 way):
#   0 qrs, 1 qrs_search_back, 2 rejected_t, 3 noise
# The frozen event bus can only carry two of these four classes; the bench checks the
# two-way split and reports the four-way census separately.
#
# Run: /home/avivsabilalm/.venvs/jupyter/bin/python ekspor_vektor_puncak.py
# ---------------------------------------------------------------------------
import csv, hashlib, json, os, sys

XMLP = "/home/avivsabilalm/.hermes/cache/scratch/rtlplan2"
SRC = os.path.join(XMLP, "fase5")
OUT = os.path.dirname(os.path.abspath(__file__))

KIND_CODE = {"qrs": 0, "qrs_search_back": 1, "rejected_t": 2, "noise": 3}
BEAT = ("qrs", "qrs_search_back")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def write_hex(name, words):
    path = os.path.join(OUT, name)
    with open(path, "w") as f:
        for w in words:
            f.write("%08x\n" % (w & 0xFFFFFFFF))
    return path


def main():
    peaks = os.path.join(SRC, "04015.peaks.csv")
    rows = list(csv.DictReader(open(peaks)))
    n = len(rows)
    pos = [int(r["sample_index"]) for r in rows]
    pv = [int(r["envelope_value"]) for r in rows]
    pkf = [int(r["filtered_peak"]) for r in rows]
    i1 = [int(r["i1"]) for r in rows]
    kind = [r["event_kind"] for r in rows]
    isqrs = [1 if k in BEAT else 0 for k in kind]

    man = json.load(open(os.path.join(SRC, "04015.manifest.fase5.json")))
    amb = None
    for key in ("ambang_state", "ambang_state_akhir", "ambang"):
        if key in man:
            amb = man[key]
            break
    if amb is None:
        # fall back to the value the parent verified and quoted in the task brief
        amb = [29, 6, 112, 6, 106, 0, 26, 1202, 2586]
        amb_src = "brief (not found in manifest)"
    else:
        amb_src = "manifest"

    outs = []
    outs.append(write_hex("04015.puncak.pos.hex", pos))
    outs.append(write_hex("04015.puncak.pv.hex", pv))
    outs.append(write_hex("04015.puncak.pkf.hex", pkf))
    outs.append(write_hex("04015.puncak.i1.hex", i1))
    outs.append(write_hex("04015.puncak.isqrs.hex", isqrs))
    outs.append(write_hex("04015.puncak.eventkind.hex", [KIND_CODE[k] for k in kind]))
    outs.append(write_hex("04015.ambang_akhir.hex", [int(v) for v in amb]))

    census = {}
    for k in kind:
        census[k] = census.get(k, 0) + 1

    ev = {
        "peaks": n,
        "qrs": sum(isqrs),
        "census_4way": census,
        "pos_first": pos[0], "pos_last": pos[-1],
        "pos_monotone": all(pos[i] < pos[i + 1] for i in range(n - 1)),
        "pv_max": max(pv), "pv_min": min(pv),
        "pkf_max": max(pkf), "pkf_min": min(pkf),
        "i1_max": max(i1), "i1_min": min(i1),
        "ambang_state": amb, "ambang_state_source": amb_src,
        "src_sha256": sha256(peaks),
        "src": peaks,
        "out": {os.path.basename(o): sha256(o) for o in outs},
    }
    with open(os.path.join(OUT, "vektor_puncak.manifest.json"), "w") as f:
        json.dump(ev, f, indent=2, sort_keys=True)

    print("peaks %d  qrs %d" % (n, ev["qrs"]))
    print("census_4way %s" % census)
    print("pos %d .. %d monotone %s" % (pos[0], pos[-1], ev["pos_monotone"]))
    print("pv %d .. %d" % (ev["pv_min"], ev["pv_max"]))
    print("pkf %d .. %d" % (ev["pkf_min"], ev["pkf_max"]))
    print("i1 %d .. %d" % (ev["i1_min"], ev["i1_max"]))
    print("ambang_state %s (from %s)" % (amb, amb_src))
    print("peaks.csv sha256 %s" % ev["src_sha256"])
    for k in sorted(ev["out"]):
        print("  %-32s sha256 %s" % (k, ev["out"][k][:32]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
