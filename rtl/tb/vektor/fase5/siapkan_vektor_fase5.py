#!/usr/bin/env python3
"""Build the Fase-5 testbench vectors from the golden reference data.

Reads, and never writes, the frozen golden data under rtlplan2/:
  rtlplan2/fase5/04015.peaks.csv            one row per envelope peak, 15 columns
  rtlplan2/fase5/04015.manifest.fase5.json  counts and the 9 element ambang_state
  rtlplan2/fase0/04015.manifest.json        the column word count (450000)

Writes, into this directory: one 32 bit hex word per line, 8 digits, $readmemh
compatible, plus a manifest that records the counts and the sha256 of every file so a
later run of the testbench can be audited without re-deriving anything.

Why a derived copy is needed at all: the testbench may not carry a measured number
(final38.md:890-897), so the expected peak positions, envelope values, filtered peaks,
slopes, thresholds, event indices and kinds, and the 9 element ambang_state all have to
arrive as data. The columns of 04015.peaks.csv are exactly those quantities.

Files written here:
  04015.fase5.counts.hex        [peaks, qrs, ambang words, frames]
  04015.puncak.pos.hex          sample_index per peak                 (peaks words)
  04015.puncak.pv.hex           envelope_value per peak
  04015.puncak.pkf.hex          filtered_peak per peak
  04015.puncak.kem.hex          slope per peak
  04015.puncak.i1.hex           i1 per peak
  04015.puncak.i2.hex           i2 per peak
  04015.puncak.flag.hex         bit0 signal, bit1 in_band, bit2 t_rejected,
                                bit3 search_back, bit4 kind is qrs_search_back
  04015.puncak.evidx.hex        expected m_ev_idx per peak
  04015.puncak.kind.hex         expected m_ev_kind per peak, 1 QRS, 2 candidate
  04015.qrs.hex                 the QRS series in recording order          (qrs words)
  04015.ambang_state.hex        the 9 element ambang_state
  04015.fase5.manifest.json     counts and sha256 of everything above
"""
import binascii
import csv
import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path("/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite")
SRC = REPO / "rtlplan2" / "fase5"
F0 = REPO / "rtlplan2" / "fase0"
OUT = REPO / "rtl" / "tb" / "vektor" / "fase5"

EV_QRS = 1
EV_PEAK_CAND = 2


def write_hex(words, name):
    data = b"".join(b"%08x\n" % (w & 0xFFFFFFFF) for w in words)
    path = OUT / name
    path.write_bytes(data)
    return {"words": len(words), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with open(SRC / "04015.peaks.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    with open(SRC / "04015.manifest.fase5.json") as fh:
        man = json.load(fh)
    with open(F0 / "04015.manifest.json") as fh:
        man0 = json.load(fh)

    frames = int(man0["frames"])
    amb = [int(v) for v in man["counts"]["ambang_state"]]
    assert len(amb) == 9, amb

    pos, pv, pkf, kem, i1v, i2v, flag, evidx, kind = ([] for _ in range(9))
    qrs_series = []
    for k, r in enumerate(rows):
        assert int(r["peak_index"]) == k
        s = int(r["sample_index"])
        pos.append(s)
        pv.append(int(r["envelope_value"]))
        pkf.append(int(r["filtered_peak"]))
        kem.append(int(r["slope"]))
        i1v.append(int(r["i1"]))
        i2v.append(int(r["i2"]))
        fl = 0
        fl |= 1 if int(r["signal"]) else 0
        fl |= 2 if int(r["in_band"]) else 0
        fl |= 4 if int(r["t_rejected"]) else 0
        fl |= 8 if int(r["search_back"]) else 0
        fl |= 16 if r["event_kind"] == "qrs_search_back" else 0
        flag.append(fl)
        e = r["qrs_sample_index"]
        if e == "":
            assert r["event_kind"] in ("rejected_t", "noise"), r
            evidx.append(s)
            kind.append(EV_PEAK_CAND)
        else:
            qrs_series.append(int(e))
            evidx.append(int(e))
            kind.append(EV_QRS)

    files = {}
    files["04015.fase5.counts.hex"] = write_hex([len(pos), len(qrs_series), len(amb), frames],
                                                "04015.fase5.counts.hex")
    for name, col in (("04015.puncak.pos.hex", pos), ("04015.puncak.pv.hex", pv),
                      ("04015.puncak.pkf.hex", pkf), ("04015.puncak.kem.hex", kem),
                      ("04015.puncak.i1.hex", i1v), ("04015.puncak.i2.hex", i2v),
                      ("04015.puncak.flag.hex", flag), ("04015.puncak.evidx.hex", evidx),
                      ("04015.puncak.kind.hex", kind)):
        files[name] = write_hex(col, name)
    files["04015.qrs.hex"] = write_hex(qrs_series, "04015.qrs.hex")
    files["04015.ambang_state.hex"] = write_hex(amb, "04015.ambang_state.hex")

    out_man = {
        "generator": "rtl/tb/vektor/fase5/siapkan_vektor_fase5.py",
        "source": {
            "peaks_csv": "rtlplan2/fase5/04015.peaks.csv",
            "peaks_csv_sha256": hashlib.sha256(
                (SRC / "04015.peaks.csv").read_bytes()).hexdigest(),
            "manifest_fase5_sha256": hashlib.sha256(
                (SRC / "04015.manifest.fase5.json").read_bytes()).hexdigest(),
            "manifest_fase0_sha256": hashlib.sha256(
                (F0 / "04015.manifest.json").read_bytes()).hexdigest(),
        },
        "counts": {"peaks": len(pos), "qrs": len(qrs_series), "ambang_state": len(amb),
                   "frames": frames},
        "ambang_state": amb,
        "kind_encoding": {"EV_QRS": EV_QRS, "EV_PEAK_CAND": EV_PEAK_CAND},
        "flag_bits": ["signal", "in_band", "t_rejected", "search_back",
                      "kind_is_qrs_search_back"],
        "files": files,
        "note": "derived from the frozen golden data, no golden file was modified",
    }
    (OUT / "04015.fase5.manifest.json").write_text(json.dumps(out_man, indent=1) + "\n")

    print("peaks %d  qrs %d  ambang_state %s  frames %d"
          % (len(pos), len(qrs_series), amb, frames))
    for name in sorted(files):
        print("  %-32s words %6d bytes %8d sha256 %s"
              % (name, files[name]["words"], files[name]["bytes"],
                 files[name]["sha256"][:32]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
