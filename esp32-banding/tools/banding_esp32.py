#!/usr/bin/env python3
"""banding_esp32.py -- satu pintu banding: ESP32 (atau uji PC) terhadap model Python.

Subperintah

  periksa LOG            cek kebenaran satu log VERIF (dari ESP32 atau host_run) terhadap
                         berkas acuan model: sidik jari 6 kolom, deret QRS, penanda irama,
                         fitur dan kelas setiap jendela.

  jalankan --dut COMx    jalankan urutan uji lengkap di ESP32 lewat USB, sambil merekam logger
           [--logger COMy] INA219 di port kedua, lalu tulis laporan. Urutan default:
                           INFO, VERIF, PROF 3, POWER 5x(20 s idle + 20 s bench), RT 60 s.

  analisis DIR           tulis ulang laporan dari log yang sudah terekam di DIR
                         (dut.log, logger.log), tanpa perangkat.

Contoh (dari akar repo, Windows):
  python esp32-banding\\tools\\acuan_model.py --record 04015
  python esp32-banding\\tools\\banding_esp32.py jalankan --dut COM5 --logger COM6
  python esp32-banding\\tools\\banding_esp32.py analisis esp32-banding\\hasil\\20261022-1100

Isian sisi chip (opsional, untuk kolom perbandingan): --chip chip.json berisi
  {"f_clk_mhz": 100, "cyc_per_sample": 1, "cyc_per_window": 136,
   "p_mw": null, "e_per_window_uj": null, "sumber": "RTL fase 8/9, SKY130 report_power"}
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import statistics as stats
import struct
import sys
import threading
import time

HERE = pathlib.Path(__file__).absolute().parent
BANDING = HERE.parent
ROOT = BANDING.parent

KELAS = {0: "undecided", 1: "normal", 2: "review (AF)"}
KOLOM = ("masukan16", "lp", "hp", "turunan", "kuadrat", "jendela")
MK = {0: "transisi", 1: "bench", 2: "idle", 3: "realtime"}


# =========================================================================== parsing log DUT
def kv(fields):
    out = {}
    for f in fields:
        if "=" in f:
            k, v = f.split("=", 1)
            out[k] = v
    return out


def num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return float(v)
        except (TypeError, ValueError):
            return v


def bits_ke_double(h: str) -> float:
    return struct.unpack(">d", bytes.fromhex(h))[0]


def parse_dut(lines):
    """Pisahkan log DUT per mode. Baris lain (log ESP-IDF, gema) diabaikan."""
    runs = []
    cur = None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#AFIB"):
            cur = {"head": kv(line.split(",")[1:]), "Q": [], "W": [], "K": {}, "C": {}, "T": [],
                   "H": None, "PH": [], "PLAN": None, "V": {}, "RT": [], "end": False}
            runs.append(cur)
            continue
        if cur is None:
            continue
        f = line.split(",")
        tag = f[0]
        if tag == "Q" and len(f) >= 5:
            cur["Q"].append((int(f[1]), int(f[2]), int(f[3]), int(f[4])))
        elif tag == "W" and len(f) >= 16:
            cur["W"].append({
                "win_no": int(f[1]), "i_start": int(f[2]), "src_first": int(f[3]),
                "src_last": int(f[4]), "qrs_end": int(f[5]), "sample_dec": int(f[6]),
                "rr_min": int(f[7]), "rr_max": int(f[8]), "gate_ok": int(f[9]), "kelas": int(f[10]),
                "bits": [f[11], f[12], f[13], f[14]], "cycles": int(f[15])})
        elif tag == "K" and len(f) >= 4:
            cur["K"][f[1]] = {"s1": f[2], "s2": f[3]}
        elif tag == "C":
            cur["C"] = {k: num(v) for k, v in kv(f[1:]).items()}
        elif tag == "V":
            cur["V"] = {k: num(v) for k, v in kv(f[1:]).items()}
        elif tag == "T":
            cur["T"].append({"jenis": f[1], **{k: num(v) for k, v in kv(f[2:]).items()}})
        elif tag == "H":
            cur["H"] = line
        elif tag == "PLAN":
            cur["PLAN"] = {k: num(v) for k, v in kv(f[1:]).items()}
        elif tag == "PH" and len(f) >= 5:
            cur["PH"].append({"rep": int(f[1]), "fase": f[2], "t0_us": int(f[3]), "dur_us": int(f[4]),
                              "loops": int(f[5]) if len(f) > 5 else 0,
                              "samples": int(f[6]) if len(f) > 6 else 0,
                              "jendela": int(f[7]) if len(f) > 7 else 0,
                              "review": int(f[8]) if len(f) > 8 else 0,
                              **{k: num(v) for k, v in kv(f[9:]).items()}})
        elif tag == "END":
            cur["end"] = True
    return runs


def parse_logger(lines):
    head, segs, live = {}, [], []
    for raw in lines:
        line = raw.strip()
        if line.startswith("#INA"):
            head = {k: num(v) for k, v in kv(line.split(",")[1:]).items()}
        elif line.startswith("SEG,"):
            f = line.split(",")
            if len(f) >= 13:
                segs.append({"k": int(f[1]), "code": int(f[2]), "t0_ms": int(f[3]), "dur_ms": int(f[4]),
                             "n": int(f[5]), "i_ma": float(f[6]), "i_sd_ma": float(f[7]),
                             "v": float(f[8]), "p_mw": float(f[9]), "p_min_mw": float(f[10]),
                             "p_max_mw": float(f[11]), "e_mj": float(f[12])})
        elif line.startswith("L,"):
            f = line.split(",")
            if len(f) >= 6:
                live.append((int(f[1]), int(f[2]), float(f[3]), float(f[4]), float(f[5])))
    return head, segs, live


# =========================================================================== kebenaran
def muat_acuan(path=None, record="04015", arm="berpenanda"):
    p = pathlib.Path(path) if path else BANDING / "acuan" / ("%s.%s.json" % (record, arm))
    if not p.exists():
        raise SystemExit("acuan %s belum ada. Jalankan dulu:\n  python esp32-banding/tools/acuan_model.py"
                         " --record %s" % (p, record))
    return json.loads(p.read_text()), p


def periksa_run(run, acuan, cetak=True):
    """Bandingkan satu run VERIF dengan acuan. Kembalikan dict hasil."""
    h = run["head"]
    res = {"sumber": h.get("src"), "n": num(h.get("n")), "arm": h.get("arm"), "lulus": True, "catatan": []}

    def gagal(msg):
        res["lulus"] = False
        res["catatan"].append(msg)

    if num(h.get("n")) != acuan["n"]:
        gagal("panjang run %s, acuan %s" % (h.get("n"), acuan["n"]))
    if h.get("arm") != acuan["arm"]:
        gagal("lengan run %s, acuan %s" % (h.get("arm"), acuan["arm"]))
    sha = h.get("stim_sha", "na")
    res["stim_sha_cocok"] = None if sha == "na" else (sha == acuan["stim_sha256"])
    if sha not in ("na", acuan["stim_sha256"]):
        gagal("sha256 stimulus di flash %s... beda dari acuan %s..." % (sha[:16], acuan["stim_sha256"][:16]))

    # kolom per sampel
    kol = {}
    for k in KOLOM:
        a, b = acuan["kolom"][k], run["K"].get(k)
        sama = b is not None and a["s1"] == b["s1"] and a["s2"] == b["s2"]
        kol[k] = sama
        if not sama:
            gagal("sidik jari kolom %s beda" % k)
    res["kolom"] = kol

    # QRS dan penanda
    q_run = [q[1] for q in run["Q"]]
    q_ref = acuan["qrs"]
    res["qrs_run"], res["qrs_acuan"] = len(q_run), len(q_ref)
    beda_q = next((i for i, (x, y) in enumerate(zip(q_run, q_ref)) if x != y), None)
    if len(q_run) != len(q_ref) or beda_q is not None:
        gagal("deret QRS beda (run %d, acuan %d, pertama beda di %s)" % (len(q_run), len(q_ref), beda_q))
    mk_run = [q[3] for q in run["Q"][1:]]
    res["mark_sama"] = mk_run == acuan["mark"]
    if not res["mark_sama"]:
        gagal("penanda irama 7b beda")

    # jendela
    ref_by_i = {w["i_start"]: w for w in acuan["jendela"]}
    run_by_i = {w["i_start"]: w for w in run["W"]}
    res["jendela_run"], res["jendela_acuan"] = len(run_by_i), len(ref_by_i)
    if set(ref_by_i) != set(run_by_i):
        gagal("posisi jendela beda: hanya di run %d, hanya di acuan %d"
              % (len(set(run_by_i) - set(ref_by_i)), len(set(ref_by_i) - set(run_by_i))))
    bit_sama = fitur_tol = fitur_beda = 0
    kelas_sama = kelas_beda = 0
    beda_contoh = []
    census = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    sebaran_run = {0: 0, 1: 0, 2: 0}
    sebaran_model = {0: 0, 1: 0, 2: 0}
    disimpan = 0
    baris = []
    for i in sorted(ref_by_i):
        r, w = ref_by_i[i], run_by_i.get(i)
        if w is None:
            continue
        for key in ("src_first", "src_last", "qrs_end"):
            if r[key] != w[key]:
                gagal("jendela %d: %s run %d acuan %d" % (i, key, w[key], r[key]))
        if bool(r["gate_ok"]) != bool(w["gate_ok"]):
            gagal("jendela %d: gerbang rentang beda" % i)
        if r["gate_ok"]:
            if r["bits"] == w["bits"]:
                bit_sama += 1
            else:
                vr = [r["rmssd"], r["ratio"], r["pnn50"], r["ent4"]]
                vw = [bits_ke_double(b) for b in w["bits"]]
                if all(abs(a - b) <= 1e-12 * max(1.0, abs(a)) for a, b in zip(vr, vw)):
                    fitur_tol += 1
                else:
                    fitur_beda += 1
                    gagal("jendela %d: fitur beda %s vs %s" % (i, vw, vr))
        if r["kelas_model"] == w["kelas"]:
            kelas_sama += 1
        else:
            kelas_beda += 1
            if len(beda_contoh) < 5:
                beda_contoh.append((i, w["kelas"], r["kelas_model"]))
        if r["disimpan_model"]:
            disimpan += 1
            sebaran_run[w["kelas"]] += 1
            sebaran_model[r["kelas_model"]] += 1
            af = r["label"] == "AFIB"
            fired = w["kelas"] == 2
            census["TP" if fired and af else "FP" if fired else "FN" if af else "TN"] += 1
        vw = [bits_ke_double(b) for b in w["bits"]]
        baris.append({"i_start": i, "win_no": w["win_no"], "qrs_end": w["qrs_end"],
                      "sample_dec": w["sample_dec"], "label": r["label"],
                      "disimpan_model": r["disimpan_model"], "kelas_model": r["kelas_model"],
                      "kelas_esp32": w["kelas"], "ratio": vw[1], "ent4": vw[3],
                      "cycles": w["cycles"]})
    if kelas_beda:
        gagal("%d jendela beda kelas, contoh (i, run, model) %s" % (kelas_beda, beda_contoh))
    res.update({"fitur_bit_identik": bit_sama, "fitur_dalam_toleransi": fitur_tol,
                "fitur_beda": fitur_beda, "kelas_sama": kelas_sama, "kelas_beda": kelas_beda,
                "disimpan_model": disimpan, "sebaran_run": sebaran_run, "sebaran_model": sebaran_model,
                "census": census, "baris": baris})
    if cetak:
        cetak_periksa(res)
    return res


def cetak_periksa(res):
    print("=" * 74)
    print("kebenaran: %s terhadap model Python (lengan %s, %s sampel)" % (res["sumber"], res["arm"], res["n"]))
    print("=" * 74)
    if res.get("stim_sha_cocok") is not None:
        print("  sha256 stimulus di flash   : %s" % ("cocok" if res["stim_sha_cocok"] else "BEDA"))
    print("  sidik jari kolom per sampel: %s" % ", ".join(
        "%s %s" % (k, "sama" if v else "BEDA") for k, v in res["kolom"].items()))
    print("  deret QRS                  : run %d, acuan %d" % (res["qrs_run"], res["qrs_acuan"]))
    print("  penanda irama 7b           : %s" % ("sama" if res["mark_sama"] else "BEDA"))
    print("  posisi jendela             : run %d, acuan %d" % (res["jendela_run"], res["jendela_acuan"]))
    print("  fitur jendela              : %d identik bit, %d dalam 1e-12, %d beda"
          % (res["fitur_bit_identik"], res["fitur_dalam_toleransi"], res["fitur_beda"]))
    print("  kelas per posisi jendela   : %d sama, %d beda" % (res["kelas_sama"], res["kelas_beda"]))
    print("")
    print("  triase 3 kelas pada %d jendela yang disimpan model" % res["disimpan_model"])
    print("    %-14s %8s %8s" % ("kelas", "model", "ESP32" if res["sumber"] == "esp32" else res["sumber"]))
    for k in (0, 1, 2):
        print("    %-14s %8d %8d" % (KELAS[k], res["sebaran_model"][k], res["sebaran_run"][k]))
    c = res["census"]
    print("    census vs label anotasi : TP %d, FP %d, FN %d, TN %d" % (c["TP"], c["FP"], c["FN"], c["TN"]))
    if c["TP"] + c["FN"]:
        print("    sensitivitas            : %.4f (%d/%d)" % (c["TP"] / (c["TP"] + c["FN"]), c["TP"], c["TP"] + c["FN"]))
    if c["TN"] + c["FP"]:
        print("    spesifisitas            : %.4f (%d/%d)" % (c["TN"] / (c["TN"] + c["FP"]), c["TN"], c["TN"] + c["FP"]))
    for msg in res["catatan"][:10]:
        print("  ! " + msg)
    print("  VERDICT KEBENARAN: %s" % ("PASS" if res["lulus"] else "REVIEW"))
    print("=" * 74)


# =========================================================================== waktu
def ringkas_waktu(prof, fcpu):
    if not prof:
        return None
    a = [t for t in prof["T"] if t["jenis"] == "A"]
    b = {t["tahap"]: t for t in prof["T"] if t["jenis"] == "B"}
    w = next((t for t in prof["T"] if t["jenis"] == "WIN"), None)
    if not a:
        return None
    n = a[0]["n"]
    means = [t["cyc_mean"] for t in a]
    out = {"fcpu_mhz": fcpu, "rep": len(a), "n": n,
           "cyc_mean": stats.mean(means), "cyc_mean_sd": stats.pstdev(means),
           "p50": a[0]["p50"], "p90": a[0]["p90"], "p99": a[0]["p99"], "p999": a[0]["p999"],
           "max": max(t["max"] for t in a), "us_loop": stats.mean(t["us_loop"] for t in a),
           "jendela": a[0]["jendela"], "review": a[0]["review"]}
    if fcpu:
        f = float(fcpu)
        out["us_per_sampel"] = out["cyc_mean"] / f
        out["us_p99"] = out["p99"] / f
        out["us_max"] = out["max"] / f
        rekaman_s = n / 250.0
        hitung_s = out["cyc_mean"] * n / (f * 1e6)
        out["hitung_s_per_rekaman"] = hitung_s
        out["faktor_realtime"] = rekaman_s / hitung_s if hitung_s else None
        out["beban_cpu_250hz_persen"] = out["cyc_mean"] * 250.0 / (f * 1e6) * 100.0
        out["tenggat_4ms_cyc"] = int(4e-3 * f * 1e6)
    if b:
        tot_thr = b.get("ambang_rr", {}).get("cyc", 0)
        tot_win = b.get("jendela", {}).get("cyc", 0)
        out["tahap"] = {
            "filter (LP,HP,turunan,kuadrat,MWI)": b.get("filter", {}).get("cyc", 0) / n,
            "pemilih puncak": b.get("picker", {}).get("cyc", 0) / n,
            "ambang+T+search back+RR": (tot_thr - tot_win) / n,
            "fitur+kelas jendela": tot_win / n,
        }
    if w:
        out["jendela_cyc_mean"] = w["cyc_mean"]
        out["jendela_cyc_max"] = w["cyc_max"]
        if fcpu:
            out["jendela_us_mean"] = w["cyc_mean"] / float(fcpu)
            out["jendela_us_max"] = w["cyc_max"] / float(fcpu)
    return out


# =========================================================================== daya
def pasangkan_fase(power_runs, rt_runs, segs, min_ms=500):
    """Urutan fase DUT dicocokkan dengan urutan segmen logger, per kode pin."""
    fase = []
    for run in power_runs:
        for ph in run["PH"]:
            fase.append({**ph, "code": 2 if ph["fase"] == "idle" else 1,
                         "fcpu": num(run["head"].get("fcpu_mhz"))})
    for run in rt_runs:
        for ph in run["PH"]:
            fase.append({**ph, "code": 2 if ph["fase"] == "rtidle" else 3,
                         "fcpu": num(run["head"].get("fcpu_mhz"))})
    fase.sort(key=lambda x: x["t0_us"] if "urut" not in x else x["urut"])
    sg = [s for s in segs if s["dur_ms"] >= min_ms and s["code"] != 0]
    pas = []
    j = 0
    for f in fase:
        while j < len(sg) and sg[j]["code"] != f["code"]:
            j += 1
        if j >= len(sg):
            pas.append((f, None))
            continue
        pas.append((f, sg[j]))
        j += 1
    return pas


def fase_dut(power_runs, rt_runs):
    """Daftar fase DUT berurutan waktu (jam DUT, mikrodetik sejak boot)."""
    fase = []
    for run in power_runs:
        for ph in run["PH"]:
            fase.append({**ph, "code": 2 if ph["fase"] == "idle" else 1,
                         "fcpu": num(run["head"].get("fcpu_mhz"))})
    for run in rt_runs:
        for ph in run["PH"]:
            fase.append({**ph, "code": 2 if ph["fase"] == "rtidle" else 3,
                         "fcpu": num(run["head"].get("fcpu_mhz"))})
    fase.sort(key=lambda x: x["t0_us"])
    return fase


def selaraskan_tanpa_penanda(fase, live, trim_ms=500):
    """Cadangan bila pin penanda tidak terbaca: cari selisih jam logger - jam DUT yang paling
    cocok dengan pola arus (bench tinggi, idle rendah), lalu ambil statistik tiap fase dari
    baris L (rata-rata 100 ms). Kembalikan (pasangan, info)."""
    import bisect
    if not live or not fase:
        return [], None
    t = [x[0] for x in live]
    pref_p = [0.0]
    pref_i = [0.0]
    pref_v = [0.0]
    for x in live:
        pref_p.append(pref_p[-1] + x[4])
        pref_i.append(pref_i[-1] + x[2])
        pref_v.append(pref_v[-1] + x[3])

    def rata(a_ms, b_ms):
        i, j = bisect.bisect_left(t, a_ms), bisect.bisect_right(t, b_ms)
        if j - i < 3:
            return None
        n = j - i
        return n, (pref_i[j] - pref_i[i]) / n, (pref_v[j] - pref_v[i]) / n, (pref_p[j] - pref_p[i]) / n, i, j

    bench = [f for f in fase if f["fase"] == "bench"]
    idle = [f for f in fase if f["fase"] == "idle"]
    if not bench or not idle:
        return [], None
    f0 = fase[0]["t0_us"] / 1000.0
    f1 = (fase[-1]["t0_us"] + fase[-1]["dur_us"]) / 1000.0
    lo, hi = t[0] - f0, t[-1] - f1
    best = None
    for step in (1000, 100):
        rng = range(int(lo), int(hi) + 1, step) if best is None else \
            range(int(best[1]) - 2000, int(best[1]) + 2001, step)
        for off in rng:
            pb = [rata(f["t0_us"] / 1000 + off + trim_ms, (f["t0_us"] + f["dur_us"]) / 1000 + off - trim_ms) for f in bench]
            pi = [rata(f["t0_us"] / 1000 + off + trim_ms, (f["t0_us"] + f["dur_us"]) / 1000 + off - trim_ms) for f in idle]
            if any(x is None for x in pb + pi):
                continue
            skor = min(x[3] for x in pb) - max(x[3] for x in pi)    # bench terendah harus > idle tertinggi
            if best is None or skor > best[0]:
                best = (skor, off)
    if best is None:
        return [], None
    off = best[1]
    pas = []
    for k, f in enumerate(fase):
        r = rata(f["t0_us"] / 1000 + off + trim_ms, (f["t0_us"] + f["dur_us"]) / 1000 + off - trim_ms)
        if r is None:
            pas.append((f, None))
            continue
        n, i_ma, v, p, a, b = r
        ps = [live[q][4] for q in range(a, b)]
        im = [live[q][2] for q in range(a, b)]
        seg = {"k": k, "code": f["code"], "t0_ms": int(f["t0_us"] / 1000 + off), "dur_ms": int(f["dur_us"] / 1000),
               "n": n, "i_ma": i_ma, "i_sd_ma": stats.pstdev(im) if len(im) > 1 else 0.0, "v": v,
               "p_mw": p, "p_min_mw": min(ps), "p_max_mw": max(ps), "e_mj": p * f["dur_us"] / 1e6}
        pas.append((f, seg))
    return pas, {"offset_ms": off, "skor_mw": best[0], "trim_ms": trim_ms}


def ringkas_daya(pas, waktu, jarak_rekaman_s=None):
    """ΔP bench = P_bench - P_idle sebelumnya pada frekuensi yang sama."""
    reps = []
    idle_prev = None
    rt = {}
    for f, s in pas:
        if s is None:
            continue
        if f["fase"] == "idle":
            idle_prev = (f, s)
        elif f["fase"] == "bench" and idle_prev is not None:
            fi, si = idle_prev
            dur_s = f["dur_us"] / 1e6
            samples = f["samples"]
            loops = max(1, f["loops"])
            win_loop = f["jendela"]
            dp = s["p_mw"] - si["p_mw"]
            t_sampel_us = f["dur_us"] / samples if samples else None
            reps.append({
                "rep": f["rep"], "fcpu": f["fcpu"], "p_idle_mw": si["p_mw"], "p_bench_mw": s["p_mw"],
                "i_idle_ma": si["i_ma"], "i_bench_ma": s["i_ma"], "v_bench": s["v"],
                "dp_mw": dp, "dur_s": dur_s, "loops": loops, "samples": samples,
                "t_sampel_us": t_sampel_us,
                "e_sampel_nj": dp * t_sampel_us if t_sampel_us else None,           # mW x us = nJ
                "e_jendela_uj": dp * (f["dur_us"] / loops) / win_loop / 1000.0 if win_loop else None,
                "e_rekaman_mj": dp * (f["dur_us"] / loops) / 1e6,                    # mW x s = mJ
                "e_bench_seg_mj": s["e_mj"], "logger_dur_ms": s["dur_ms"],
            })
            idle_prev = None
        elif f["fase"] in ("rtidle", "rt"):
            rt[f["fase"]] = (f, s)
    out = {"reps": reps}
    by_f = {}
    for r in reps:
        by_f.setdefault(r["fcpu"], []).append(r)
    out["per_frek"] = {}
    for fc, rs in by_f.items():
        def m(key):
            vals = [r[key] for r in rs if r[key] is not None]
            return (stats.mean(vals), stats.pstdev(vals)) if vals else (None, None)
        out["per_frek"][fc] = {k: m(k) for k in ("p_idle_mw", "p_bench_mw", "dp_mw", "i_bench_ma",
                                                 "v_bench", "t_sampel_us", "e_sampel_nj",
                                                 "e_jendela_uj", "e_rekaman_mj")}
        out["per_frek"][fc]["n"] = len(rs)
    if "rt" in rt:
        f, s = rt["rt"]
        o = {"p_rt_mw": s["p_mw"], "i_rt_ma": s["i_ma"], "dur_s": f["dur_us"] / 1e6,
             "samples": f["samples"], "jendela": f["jendela"], "review": f["review"],
             "cyc_mean": f.get("cyc_mean"), "cyc_max": f.get("cyc_max"), "telat": f.get("telat"),
             "fmax": f.get("fmax"), "fmin": f.get("fmin"), "ls": f.get("ls")}
        if "rtidle" in rt:
            fi, si = rt["rtidle"]
            o["p_rtidle_mw"] = si["p_mw"]
            o["dp_rt_mw"] = s["p_mw"] - si["p_mw"]
        # jarak antar keputusan: rata-rata seluruh rekaman dari VERIF (638 jendela / 1800 s pada
        # 04015); fase RT yang pendek masih dalam pemanasan 32 denyut pertama, jadi kurang wakil.
        jarak_s = jarak_rekaman_s or ((f["samples"] / 250.0) / f["jendela"] if f["jendela"] else None)
        if jarak_s:
            o["jarak_keputusan_s"] = jarak_s
            o["e_keputusan_sistem_mj"] = s["p_mw"] * jarak_s
            if "dp_rt_mw" in o:
                o["e_keputusan_bersih_uj"] = o["dp_rt_mw"] * jarak_s * 1000.0
        out["realtime"] = o
    return out


# =========================================================================== laporan
def fmt(x, nd=3, unit=""):
    if x is None:
        return "-"
    if isinstance(x, tuple):
        mu, sd = x
        if mu is None:
            return "-"
        return ("%.*f ± %.*f%s" % (nd, mu, nd, sd, unit))
    if isinstance(x, float):
        return "%.*f%s" % (nd, x, unit)
    return "%s%s" % (x, unit)


def tulis_laporan(out_dir: pathlib.Path, kebenaran, waktu, daya, chip, head, waktu_list=None):
    L = ["# Banding AFIB-LITE: ESP32 terhadap model Python", ""]
    L += ["- rekaman: `%s`, %s sampel, lengan %s" % (head.get("rec"), head.get("n"), head.get("arm")),
          "- sumber: %s, CPU %s MHz" % (head.get("src"), head.get("fcpu_mhz")),
          "- sha256 stimulus: `%s`" % head.get("stim_sha"),
          "- dibuat: %s" % time.strftime("%Y-%m-%d %H:%M:%S"), ""]
    if kebenaran:
        k = kebenaran
        L += ["## 1. Kebenaran triase", "",
              "| pemeriksaan | hasil |", "| --- | --- |",
              "| sidik jari 6 kolom per sampel | %s |" % ", ".join("%s %s" % (a, "sama" if b else "**beda**") for a, b in k["kolom"].items()),
              "| deret QRS | ESP32 %d, model %d |" % (k["qrs_run"], k["qrs_acuan"]),
              "| penanda irama 7b | %s |" % ("sama" if k["mark_sama"] else "**beda**"),
              "| posisi jendela | ESP32 %d, model %d |" % (k["jendela_run"], k["jendela_acuan"]),
              "| fitur jendela | %d identik bit, %d dalam 1e-12, %d beda |" % (k["fitur_bit_identik"], k["fitur_dalam_toleransi"], k["fitur_beda"]),
              "| kelas per posisi jendela | %d sama, %d beda |" % (k["kelas_sama"], k["kelas_beda"]),
              "| **verdict** | **%s** |" % ("PASS" if k["lulus"] else "REVIEW"), "",
              "Triase pada %d jendela yang disimpan model:" % k["disimpan_model"], "",
              "| kelas | model | ESP32 |", "| --- | --- | --- |"]
        for c in (0, 1, 2):
            L.append("| %s | %d | %d |" % (KELAS[c], k["sebaran_model"][c], k["sebaran_run"][c]))
        c = k["census"]
        L += ["", "Census terhadap label anotasi: TP %d, FP %d, FN %d, TN %d." % (c["TP"], c["FP"], c["FN"], c["TN"]), ""]
    if waktu:
        w = waktu
        L += ["## 2. Waktu proses di ESP32", "",
              "| metrik | nilai |", "| --- | --- |",
              "| frekuensi CPU | %s MHz |" % w["fcpu_mhz"],
              "| siklus per sampel, rata-rata (%d ulangan) | %s |" % (w["rep"], fmt((w["cyc_mean"], w["cyc_mean_sd"]), 2)),
              "| siklus per sampel p50 / p99 / p99.9 / maks | %d / %d / %d / %d |" % (w["p50"], w["p99"], w["p999"], w["max"]),
              "| waktu per sampel rata-rata | %s |" % fmt(w.get("us_per_sampel"), 3, " µs"),
              "| waktu per sampel p99 / maks | %s / %s |" % (fmt(w.get("us_p99"), 2, " µs"), fmt(w.get("us_max"), 2, " µs")),
              "| waktu hitung rekaman 30 menit | %s |" % fmt(w.get("hitung_s_per_rekaman"), 3, " s"),
              "| faktor real-time | %s |" % fmt(w.get("faktor_realtime"), 0, " x"),
              "| beban CPU pada 250 Hz | %s |" % fmt(w.get("beban_cpu_250hz_persen"), 4, " %"),
              "| siklus per keputusan jendela rata-rata / maks | %s / %s |" % (fmt(w.get("jendela_cyc_mean"), 0), w.get("jendela_cyc_max")),
              "| waktu per keputusan jendela rata-rata / maks | %s / %s |" % (fmt(w.get("jendela_us_mean"), 2, " µs"), fmt(w.get("jendela_us_max"), 2, " µs")),
              ""]
        if w.get("tahap"):
            L += ["Rincian siklus per sampel per tahap (run berinstrumen, rata-rata atas semua sampel):", "",
                  "| tahap | siklus/sampel |", "| --- | --- |"]
            for k2, v in w["tahap"].items():
                L.append("| %s | %.2f |" % (k2, v))
            L.append("")
    if waktu_list and len(waktu_list) > 1:
        L += ["Sapuan frekuensi CPU (PROF per frekuensi, rata-rata ulangan; wall = us_loop / n):", "",
              "| f CPU | siklus/sampel | µs/sampel | wall µs/sampel | maks siklus (µs) | beban CPU 250 Hz "
              "| faktor real-time | keputusan jendela rata-rata / maks | jendela, review |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for x in waktu_list:
            L.append("| %s MHz | %s | %s | %s | %d (%s) | %s | %s | %s / %s | %d, %d |" % (
                x["fcpu_mhz"], fmt((x["cyc_mean"], x["cyc_mean_sd"]), 2), fmt(x.get("us_per_sampel"), 3),
                fmt(x["us_loop"] / x["n"], 3), x["max"], fmt(x.get("us_max"), 1, " µs"),
                fmt(x.get("beban_cpu_250hz_persen"), 4, " %"), fmt(x.get("faktor_realtime"), 0, " x"),
                fmt(x.get("jendela_us_mean"), 2, " µs"), fmt(x.get("jendela_us_max"), 2, " µs"),
                x["jendela"], x["review"]))
        L.append("")
    if daya:
        L += ["## 3. Daya dan energi ESP32 (INA219 di rail 3V3)", ""]
        for fc, d in daya["per_frek"].items():
            L += ["### CPU %s MHz (%d ulangan, rata-rata ± simpangan)" % (fc, d["n"]), "",
                  "| metrik | nilai |", "| --- | --- |",
                  "| P idle (task tidur, WAITI) | %s |" % fmt(d["p_idle_mw"], 2, " mW"),
                  "| P bench (rantai berjalan terus) | %s |" % fmt(d["p_bench_mw"], 2, " mW"),
                  "| I bench | %s |" % fmt(d["i_bench_ma"], 2, " mA"),
                  "| V rail | %s |" % fmt(d["v_bench"], 3, " V"),
                  "| ΔP = P bench − P idle | %s |" % fmt(d["dp_mw"], 2, " mW"),
                  "| waktu per sampel (wall, termasuk salin blok) | %s |" % fmt(d["t_sampel_us"], 3, " µs"),
                  "| energi bersih per sampel | %s |" % fmt(d["e_sampel_nj"], 2, " nJ"),
                  "| energi bersih per keputusan jendela (diamortisasi) | %s |" % fmt(d["e_jendela_uj"], 3, " µJ"),
                  "| energi bersih per rekaman 30 menit | %s |" % fmt(d["e_rekaman_mj"], 3, " mJ"), ""]
        rt = daya.get("realtime")
        if rt:
            L += ["### Operasi real-time 250 Hz", "",
                  "| metrik | nilai |", "| --- | --- |",
                  "| setelan PM | fmax %s MHz, fmin %s MHz, light sleep %s |" % (rt.get("fmax"), rt.get("fmin"), rt.get("ls")),
                  "| durasi, sampel, jendela | %.1f s, %s, %s |" % (rt["dur_s"], rt["samples"], rt["jendela"]),
                  "| P rata-rata, timer saja (tanpa rantai) | %s |" % fmt(rt.get("p_rtidle_mw"), 2, " mW"),
                  "| P rata-rata, rantai berjalan | %s |" % fmt(rt["p_rt_mw"], 2, " mW"),
                  "| ΔP rantai | %s |" % fmt(rt.get("dp_rt_mw"), 3, " mW"),
                  "| siklus per sampel rata-rata / maks | %s / %s |" % (rt.get("cyc_mean"), rt.get("cyc_max")),
                  "| sampel terlambat (> 4 ms) | %s |" % rt.get("telat"),
                  "| jarak antar keputusan (rata-rata rekaman) | %s |" % fmt(rt.get("jarak_keputusan_s"), 3, " s"),
                  "| energi sistem per keputusan (P rata-rata × jarak) | %s |" % fmt(rt.get("e_keputusan_sistem_mj"), 2, " mJ"),
                  "| energi bersih rantai per keputusan | %s |" % fmt(rt.get("e_keputusan_bersih_uj"), 2, " µJ"), ""]
        if daya.get("selaras_tanpa_penanda"):
            sl = daya["selaras_tanpa_penanda"]
            L += ["**Penanda tidak terbaca di run ini.** Batas fase diambil dari jadwal fase DUT yang "
                  "diselaraskan ke pola arus logger (selisih jam %d ms; bench terendah melebihi idle tertinggi "
                  "%.2f mW), statistik dari rata-rata 100 ms dengan trim %d ms di tiap ujung fase."
                  % (sl["offset_ms"], sl["skor_mw"], sl["trim_ms"]), ""]
        L += ["Catatan level ukur: INA219 dipasang di antara LDO dan rail 3V3 board, jadi angka mutlak memuat "
              "LED power dan chip USB-UART bila keduanya disuplai rail 3V3. ΔP menghapus beban tetap itu.", ""]
    if chip:
        L += ["## 4. Banding dengan chip", "", "| metrik | ESP32 | chip | rasio ESP32/chip |", "| --- | --- | --- | --- |"]
        if waktu and waktu.get("us_per_sampel") and chip.get("f_clk_mhz") and chip.get("cyc_per_sample"):
            us_chip = chip["cyc_per_sample"] / chip["f_clk_mhz"]
            L.append("| waktu per sampel | %.3f µs | %.4f µs | %.0f x |" % (waktu["us_per_sampel"], us_chip, waktu["us_per_sampel"] / us_chip))
        if waktu and waktu.get("jendela_us_mean") and chip.get("f_clk_mhz") and chip.get("cyc_per_window"):
            us_chip = chip["cyc_per_window"] / chip["f_clk_mhz"]
            L.append("| waktu per keputusan jendela | %.2f µs | %.3f µs | %.0f x |" % (waktu["jendela_us_mean"], us_chip, waktu["jendela_us_mean"] / us_chip))
        if daya and daya["per_frek"] and chip.get("p_mw"):
            d = next(iter(daya["per_frek"].values()))
            if d["p_bench_mw"][0]:
                L.append("| daya aktif | %.2f mW | %.4f mW | %.0f x |" % (d["p_bench_mw"][0], chip["p_mw"], d["p_bench_mw"][0] / chip["p_mw"]))
        if daya and daya["per_frek"] and chip.get("e_per_window_uj"):
            d = next(iter(daya["per_frek"].values()))
            if d["e_jendela_uj"][0]:
                L.append("| energi per keputusan | %.3f µJ | %.5f µJ | %.0f x |" % (d["e_jendela_uj"][0], chip["e_per_window_uj"], d["e_jendela_uj"][0] / chip["e_per_window_uj"]))
        L += ["", "Sumber angka chip: %s" % chip.get("sumber", "-"), ""]
    (out_dir / "SUMMARY.md").write_text("\n".join(L), encoding="utf-8")


def analisis(out_dir: pathlib.Path, acuan_path=None, chip_path=None, min_seg_ms=500):
    dut_lines = (out_dir / "dut.log").read_text(encoding="utf-8", errors="replace").splitlines()
    runs = parse_dut(dut_lines)
    verif = [r for r in runs if r["head"].get("mode") == "VERIF"]
    prof = [r for r in runs if r["head"].get("mode") == "PROF"]
    power = [r for r in runs if r["head"].get("mode") == "POWER"]
    rt = [r for r in runs if r["head"].get("mode") == "RT"]
    head = (verif or runs or [{"head": {}}])[0]["head"]
    kebenaran = None
    if verif:
        acuan, _ = muat_acuan(acuan_path, head.get("rec", "04015"), head.get("arm", "berpenanda"))
        kebenaran = periksa_run(verif[-1], acuan)
        with open(out_dir / "jendela_esp32_vs_model.csv", "w", encoding="utf-8") as fh:
            cols = ["i_start", "win_no", "qrs_end", "sample_dec", "label", "disimpan_model",
                    "kelas_model", "kelas_esp32", "ratio", "ent4", "cycles"]
            fh.write(",".join(cols) + "\n")
            for b in kebenaran["baris"]:
                fh.write(",".join(str(b[c]) for c in cols) + "\n")
    waktu_list = []
    for p in prof:
        w = ringkas_waktu(p, num(p["head"].get("fcpu_mhz")))
        if w:
            waktu_list.append(w)
    waktu = waktu_list[0] if waktu_list else None
    daya = None
    selaras = None
    lg = out_dir / "logger.log"
    if lg.exists() and (power or rt):
        _h, segs, live = parse_logger(lg.read_text(encoding="utf-8", errors="replace").splitlines())
        pas = pasangkan_fase(power, rt, segs, min_seg_ms)
        tidak = sum(1 for _f, s in pas if s is None)
        if tidak:
            print("daya: %d fase DUT tidak menemukan segmen logger yang cocok" % tidak)
        if pas and tidak == len(pas):
            pas2, info = selaraskan_tanpa_penanda(fase_dut(power, rt), live)
            if info and info["skor_mw"] > 0:
                pas = pas2
                selaras = info
                print("daya: pin penanda tidak terbaca; fase diselaraskan dari pola arus "
                      "(selisih jam %d ms, bench terendah - idle tertinggi = %.2f mW)"
                      % (info["offset_ms"], info["skor_mw"]))
            else:
                print("daya: penyelarasan dari pola arus juga gagal; cek kabel penanda dan GND")
        jarak = None
        if verif and verif[-1]["C"].get("jendela"):
            jarak = num(verif[-1]["head"].get("n")) / 250.0 / verif[-1]["C"]["jendela"]
        daya = ringkas_daya(pas, waktu, jarak)
        if selaras:
            daya["selaras_tanpa_penanda"] = selaras
    chip = json.loads(pathlib.Path(chip_path).read_text()) if chip_path else None
    tulis_laporan(out_dir, kebenaran, waktu, daya, chip, head, waktu_list)
    payload = {"kebenaran": {k: v for k, v in (kebenaran or {}).items() if k != "baris"},
               "waktu": waktu, "waktu_semua_frek": waktu_list, "daya": daya, "chip": chip}
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    # cetak ringkas ke layar
    if waktu:
        print("waktu: %.1f siklus/sampel rata-rata (p99 %d, maks %d) @ %s MHz -> %s µs/sampel, "
              "beban CPU 250 Hz %s %%" % (waktu["cyc_mean"], waktu["p99"], waktu["max"], waktu["fcpu_mhz"],
                                         fmt(waktu.get("us_per_sampel"), 3), fmt(waktu.get("beban_cpu_250hz_persen"), 4)))
    for x in waktu_list[1:]:
        print("waktu @%s MHz: %.1f siklus/sampel -> %s µs/sampel, maks %s µs, beban CPU 250 Hz %s %%"
              % (x["fcpu_mhz"], x["cyc_mean"], fmt(x.get("us_per_sampel"), 3), fmt(x.get("us_max"), 1),
                 fmt(x.get("beban_cpu_250hz_persen"), 4)))
    if daya:
        for fc, d in daya["per_frek"].items():
            print("daya @%s MHz: idle %s mW, bench %s mW, ΔP %s mW, energi/keputusan %s µJ"
                  % (fc, fmt(d["p_idle_mw"], 2), fmt(d["p_bench_mw"], 2), fmt(d["dp_mw"], 2), fmt(d["e_jendela_uj"], 3)))
        if daya.get("realtime"):
            r = daya["realtime"]
            print("realtime: P %s mW (timer saja %s mW), energi sistem/keputusan %s mJ"
                  % (fmt(r["p_rt_mw"], 2), fmt(r.get("p_rtidle_mw"), 2), fmt(r.get("e_keputusan_sistem_mj"), 2)))
    print("laporan: %s" % (out_dir / "SUMMARY.md"))
    return 0 if (kebenaran is None or kebenaran["lulus"]) else 1


# =========================================================================== perangkat
class Port:
    """Pembaca serial di thread terpisah, setiap baris disimpan ke berkas."""

    def __init__(self, name, baud, path, label):
        import serial  # pyserial
        # serial_for_url menerima COM5, /dev/ttyUSB0, atau socket://host:port (uji emulator)
        self.s = serial.serial_for_url(name, do_not_open=True)
        self.s.baudrate = baud
        self.s.timeout = 0.2
        self.s.dtr = False          # jangan menahan EN/IO0 lewat sirkuit auto-reset
        self.s.rts = False
        self.s.open()
        self.fh = open(path, "w", encoding="utf-8")
        self.label = label
        self.nbytes = 0
        self.raw_head = b""
        self.lines = []
        self.lock = threading.Lock()
        self.stop = False
        self.t = threading.Thread(target=self._loop, daemon=True)
        self.t.start()

    def _loop(self):
        buf = b""
        while not self.stop:
            try:
                # read(4096) pada CH340 di Windows menunggu buffer penuh selama data terus mengalir
                # (logger 10 baris/s): baris tiba per ~4 KB (~12 s) dan ujung log hilang saat port ditutup
                chunk = self.s.read(max(1, self.s.in_waiting))
            except Exception as exc:  # noqa: BLE001
                print("[%s] baca gagal: %s" % (self.label, exc))
                break
            if not chunk:
                continue
            self.nbytes += len(chunk)
            if len(self.raw_head) < 400:
                self.raw_head += chunk[:400 - len(self.raw_head)]
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode("utf-8", errors="replace").rstrip("\r")
                self.fh.write(line + "\n")
                self.fh.flush()
                with self.lock:
                    self.lines.append(line)

    def reset(self):
        """Reset ala esptool lewat sirkuit auto-reset DevKit: EN rendah 0.1 s, IO0 tetap tinggi."""
        self.s.dtr = False
        self.s.rts = True
        time.sleep(0.12)
        self.s.rts = False

    def tulis(self, text):
        self.s.write((text + "\n").encode())
        self.s.flush()

    def tunggu(self, pred, timeout, dari=0, gema=None):
        t_end = time.time() + timeout
        i = dari
        while time.time() < t_end:
            with self.lock:
                baru = self.lines[i:]
                n = len(self.lines)
            for line in baru:
                if gema and gema(line):
                    print("  [%s] %s" % (self.label, line))
                if pred(line):
                    return True, n
            i = n
            time.sleep(0.05)
        return False, i

    def tutup(self):
        self.stop = True
        self.t.join(timeout=1)
        self.s.close()
        self.fh.close()


def jalankan(args):
    out_dir = pathlib.Path(args.out) if args.out else BANDING / "hasil" / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    print("hasil: %s" % out_dir)
    muat_acuan(args.acuan, args.record, "berpenanda")   # gagal cepat bila acuan belum dibuat
    dut = Port(args.dut, args.dut_baud, out_dir / "dut.log", "DUT")
    lg = Port(args.logger, args.logger_baud, out_dir / "logger.log", "LOG") if args.logger else None
    if lg is None:
        print("peringatan: tanpa --logger, hanya kebenaran dan waktu yang diukur")
    try:
        ok = False
        for _ in range(3):
            dut.tulis("INFO")
            ok, _n = dut.tunggu(lambda s: s.startswith("READY"), 1.0)
            if ok:
                break
        if not ok and not args.no_reset:
            print("DUT belum menjawab, reset lewat RTS lalu tunggu READY dari boot...")
            dut.reset()
            ok, _n = dut.tunggu(lambda s: s.startswith("READY"), 5.0)
            for _ in range(5):
                if ok:
                    break
                dut.tulis("INFO")
                ok, _n = dut.tunggu(lambda s: s.startswith("READY"), 1.0)
        if not ok:
            print("DUT tidak menjawab READY. Bita diterima dari %s: %d" % (args.dut, dut.nbytes))
            if dut.nbytes:
                print("  awal data mentah: %r" % dut.raw_head[:200])
            print("  Jalankan diagnosis:  python esp32-banding\\tools\\banding_esp32.py cek --port %s" % args.dut)
            raise SystemExit(2)
        if lg:
            okl = False
            for _ in range(4):                 # logger bisa ter-reset saat port dibuka, beri waktu boot
                lg.tulis("INFO")
                okl, _ = lg.tunggu(lambda s: s.startswith("#INA"), 2.0)
                if okl:
                    break
            if not okl:
                print("peringatan: logger tidak menjawab #INA (bita diterima %d), lanjut saja" % lg.nbytes)
            elif not any("ina=ok" in s for s in lg.lines):
                print("peringatan: logger menjawab tetapi INA219 tidak terdeteksi (ina=TIDAK_ADA)")
            if args.shunt:
                lg.tulis("SHUNT %s" % args.shunt)

        crash = ("Guru Meditation", "Rebooting...", "rst:0x", "abort() was called")

        def perintah(cmd, end_tag, timeout, gema=None):
            with dut.lock:
                start = len(dut.lines)
            print("> %s" % cmd)
            dut.tulis(cmd)
            ok, _ = dut.tunggu(lambda s: s.startswith("END,%s" % end_tag) or s.startswith("ERR")
                               or any(c in s for c in crash), timeout, dari=start, gema=gema)
            with dut.lock:
                baru = dut.lines[start:]
            if any(any(c in s for c in crash) for s in baru):
                print("  !! DUT crash/reboot saat %s. Log lengkap ada di dut.log." % cmd)
                if cmd.startswith("RT"):
                    print("     Ulangi dengan mode tanpa DFS/light sleep: --rt-fmin 240 --rt-no-sleep")
                if cmd.startswith("FREQ"):
                    print("     Pakai --freqs 240 saja (frekuensi bawaan, tanpa ganti PLL).")
                dut.tunggu(lambda s: s.startswith("READY"), 8.0, dari=start)
                return False
            if not any(s.startswith("END,%s" % end_tag) for s in baru):
                print("  batas waktu menunggu END,%s" % end_tag)
                return False
            return True

        tampil = lambda s: s.startswith(("PH,", "T,A", "T,WIN", "OK", "ERR", "C,"))  # noqa: E731
        perintah("VERIF", "VERIF", 180, gema=lambda s: s.startswith(("C,", "ERR")))
        for fq in args.freqs:
            perintah("FREQ %d" % fq, "FREQ", 10, gema=tampil)
            perintah("PROF %d" % args.prof_reps, "PROF", 300, gema=tampil)
            if not args.no_power:
                tw = args.reps * (args.idle + args.active + 10) + 60
                perintah("POWER %d %d %d" % (args.reps, args.idle, args.active), "POWER", tw, gema=tampil)
        if args.rt > 0 and not args.no_power:
            perintah("RT %d %d %d %d" % (args.rt, args.rt_fmax, args.rt_fmin, 0 if args.rt_no_sleep else 1),
                     "RT", 2 * args.rt + 60, gema=tampil)
        perintah("FREQ 240", "FREQ", 10)
        time.sleep(1.5)          # beri logger waktu menutup segmen terakhir
    finally:
        dut.tutup()
        if lg:
            lg.tutup()
    return analisis(out_dir, args.acuan, args.chip)


def cek(args):
    """Diagnosis port: siapa yang bicara di port ini, pada baud berapa."""
    import serial
    from serial.tools import list_ports
    print("port serial yang terlihat:")
    for pi in list_ports.comports():
        print("  %-8s %s  [%s]" % (pi.device, pi.description, pi.hwid))
    if not args.port:
        return 0
    temuan = {}
    for baud in (115200, 921600):           # firmware sekarang 115200; 921600 untuk build lama
        try:
            s = serial.serial_for_url(args.port, do_not_open=True)
            s.baudrate = baud
            s.timeout = 0.1
            s.dtr = False
            s.rts = False
            s.open()
        except Exception as exc:  # noqa: BLE001
            print("\n%s tidak bisa dibuka: %s" % (args.port, exc))
            print("  Port dipakai program lain (serial monitor VS Code / PlatformIO)? Tutup dulu.")
            return 2
        data = b""
        if not args.no_reset:
            s.rts = True
            time.sleep(0.12)
            s.rts = False
        t_end = time.time() + 3.0
        while time.time() < t_end:
            data += s.read(max(1, s.in_waiting))
        s.write(b"INFO\n")
        s.flush()
        t_end = time.time() + 1.5
        while time.time() < t_end:
            data += s.read(max(1, s.in_waiting))
        s.close()
        teks = data.decode("utf-8", errors="replace")
        temuan[baud] = (data, teks)
        baris = teks.splitlines()
        nl = sum(1 for line in baris if line.startswith("L,"))
        print("\n--- %s @ %d baud: %d bita%s" % (args.port, baud, len(data),
                                             ", %d baris L logger (tidak ditampilkan)" % nl if nl else ""))
        for line in [x for x in baris if not x.startswith("L,")][:14]:
            print("  | " + line[:150])
    d921, t921 = temuan[921600]
    d115, t115 = temuan[115200]
    print("\ndiagnosis:")
    for baud, (_d, t) in temuan.items():
        ready = [x for x in t.splitlines() if x.startswith("READY,fw=afib-esp32-bench")]
        ina = [x for x in t.splitlines() if x.startswith("#INA")]
        if ready:
            print("  OK: firmware DUT benchmark hidup di port ini dan menjawab di %d baud." % baud)
            if "sha_ok=0" in ready[-1]:
                print("  PERHATIAN: sha_ok=0, stimulus di flash tidak cocok dengan acuan; upload ulang dut_fw.")
            return 0
        if ina:
            print("  Ini port ESP32 LOGGER (menjawab #INA di %d baud). Pakai port ini untuk --logger." % baud)
            if "ina=ok" not in ina[-1]:
                print("  PERHATIAN: INA219 tidak terdeteksi; cek SDA21 SCL22 VCC GND.")
            return 0
    if "rst:" in t115 or "ets " in t115:
        print("  Board hidup dan bisa reset (pesan boot ROM terlihat di 115200), tapi tidak ada READY/#INA.")
        print("  Kemungkinan firmware DUT/logger belum ter-upload ke board ini (mungkin masih firmware sensor).")
        print("  Upload ulang dari D:\\pio\\afib\\dut_fw (atau logger_fw) dan pastikan log upload berakhir"
              " 'Hash of data verified'.")
        if "Brownout" in t115 or "brownout" in t115:
            print("  PERHATIAN: ada pesan brownout -> tegangan rail 3V3 jatuh, cek jalur LDO/INA219.")
    elif d115 and not d921:
        print("  Ada data di 115200 tetapi bukan boot ROM: kemungkinan firmware lain (sensor AD8232) masih terpasang.")
    elif not d921 and not d115:
        print("  Tidak ada satu bita pun di dua baud, bahkan setelah reset. Artinya ESP32 tidak bersuara:")
        print("   1. Rail 3V3 DUT tanpa daya? Ukur pin 3V3 ke GND, harus ~3.3 V. Bila LDO sudah dilepas,")
        print("      jalur LDO -> INA219 VIN+ -> VIN- -> 3V3 harus sudah tersambung (atau jumper sementara).")
        print("   2. Port salah: lihat daftar port di atas, cabut-colok USB DUT untuk tahu COM mana yang hilang.")
        print("   3. Board tertahan reset: coba lagi dengan --no-reset, atau tekan EN saat perintah berjalan.")
    else:
        print("  Ada data tetapi bukan READY/#INA; lihat cuplikan di atas.")
    return 0


# =========================================================================== main
def main() -> int:
    ap = argparse.ArgumentParser(description="banding ESP32 terhadap model Python")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("periksa", help="cek kebenaran satu log VERIF")
    p.add_argument("log")
    p.add_argument("--acuan")

    p = sub.add_parser("analisis", help="tulis laporan dari log yang sudah ada")
    p.add_argument("dir")
    p.add_argument("--acuan")
    p.add_argument("--chip")
    p.add_argument("--min-seg-ms", type=int, default=500)

    p = sub.add_parser("cek", help="diagnosis port: daftar port, siapa yang menjawab, di baud berapa")
    p.add_argument("--port", help="port yang diperiksa, contoh COM19")
    p.add_argument("--no-reset", action="store_true", help="jangan reset lewat RTS")

    p = sub.add_parser("jalankan", help="jalankan urutan uji di ESP32 dan rekam logger")
    p.add_argument("--no-reset", action="store_true", help="jangan reset DUT lewat RTS bila tidak menjawab")
    p.add_argument("--dut", required=True, help="port ESP32 yang diuji, contoh COM5")
    p.add_argument("--logger", help="port ESP32 logger INA219, contoh COM6")
    p.add_argument("--dut-baud", type=int, default=115200)
    p.add_argument("--logger-baud", type=int, default=115200)
    p.add_argument("--record", default="04015")
    p.add_argument("--acuan")
    p.add_argument("--chip")
    p.add_argument("--out")
    p.add_argument("--freqs", type=lambda s: [int(x) for x in s.split(",")], default=[240],
                   help="frekuensi CPU untuk PROF dan POWER, contoh 240,160,80")
    p.add_argument("--prof-reps", type=int, default=3)
    p.add_argument("--reps", type=int, default=5)
    p.add_argument("--idle", type=int, default=20)
    p.add_argument("--active", type=int, default=20)
    p.add_argument("--rt", type=int, default=60, help="detik tiap fase real-time, 0 = lewati")
    p.add_argument("--rt-fmax", type=int, default=240)
    p.add_argument("--rt-fmin", type=int, default=40)
    p.add_argument("--rt-no-sleep", action="store_true")
    p.add_argument("--no-power", action="store_true", help="hanya kebenaran dan waktu")
    p.add_argument("--shunt", help="nilai shunt INA219 dalam ohm bila bukan 0.1")
    args = ap.parse_args()

    if args.cmd == "periksa":
        runs = [r for r in parse_dut(pathlib.Path(args.log).read_text(encoding="utf-8", errors="replace").splitlines())
                if r["head"].get("mode") == "VERIF"]
        if not runs:
            raise SystemExit("tidak ada run VERIF di %s" % args.log)
        h = runs[-1]["head"]
        acuan, ap_ = muat_acuan(args.acuan, h.get("rec", "04015"), h.get("arm", "berpenanda"))
        print("acuan: %s" % ap_)
        return 0 if periksa_run(runs[-1], acuan)["lulus"] else 1
    if args.cmd == "cek":
        return cek(args)
    if args.cmd == "analisis":
        return analisis(pathlib.Path(args.dir), args.acuan, args.chip, args.min_seg_ms)
    return jalankan(args)


if __name__ == "__main__":
    sys.exit(main())
