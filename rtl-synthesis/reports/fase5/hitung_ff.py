#!/usr/bin/env python3
"""Count the flip-flop bits of rtl/peak_detect.sv by construction.

Rule D1 of plan 38 (rtlplan2/final38.md:1679-1686) says every buffer has a fixed depth
derived from the model, and that synthesis compares each buffer's flip-flop count with
depth times width. This script does exactly that comparison without a synthesis run: it
parses the register declarations of the module, evaluates every width expression against
the frozen package constants and the module's own localparams, and multiplies depth by
width per buffer.

Reads:  rtl/peak_detect.sv, rtl/afib_lite_pkg.sv (never writes either).
Usage:  python3 rtl-synthesis/reports/fase5/hitung_ff.py
"""
import re
import sys

REPO = "/home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite"


def load():
    src = open(REPO + "/rtl/peak_detect.sv").read()
    pkg = open(REPO + "/rtl/afib_lite_pkg.sv").read()
    return src, pkg


def package_constants(pkg):
    """Every numeric localparam of the frozen package."""
    out = {}
    for m in re.finditer(
        r"localparam\s+(?:int\s+unsigned|logic\s*\[[^\]]*\]|int)\s+(\w+)\s*=\s*([^;]+);", pkg
    ):
        expr = m.group(2).strip()
        if re.fullmatch(r"\d+", expr):
            out[m.group(1)] = int(expr)
    return out


def module_localparams(src, consts):
    """Module localparams, in declaration order, evaluated against the package."""
    env = dict(consts)
    order = []
    for m in re.finditer(
        r"localparam\s+(?:int\s+unsigned|logic\s*\[[^\]]*\]|int)\s+(\w+)\s*=\s*([^;]+);", src
    ):
        name, expr = m.group(1), m.group(2).strip()
        expr = re.sub(r"\bafib_lite_pkg::", "", expr)
        try:
            env[name] = int(eval(expr, {}, env))  # noqa: S307, local source only
        except Exception:
            env[name] = None
        order.append(name)
    return env


def main():
    src, pkg = load()
    consts = package_constants(pkg)
    env = module_localparams(src, consts)

    def ev(expr):
        if expr is None:
            return None
        e = re.sub(r"\bafib_lite_pkg::", "", expr).strip()
        for key in sorted(env, key=len, reverse=True):
            if env[key] is not None:
                e = re.sub(r"\b%s\b" % key, str(env[key]), e)
        try:
            return int(eval(e, {}, {}))  # noqa: S307, local source only
        except Exception:
            return None

    rows = []
    for lineno, line in enumerate(src.splitlines(), 1):
        # packed arrays and unpacked arrays, one declaration per line in this module
        m = re.match(
            r"\s*reg\s+(?:signed\s+)?(?:\[([^\]]*)\]\s*)?(\w+)\s*(?:\[([^\]]*)\]\s*)?\s*;", line
        )
        if not m:
            # output reg declarations inside the port list
            m = re.match(
                r"\s*output\s+reg\s+(?:signed\s+)?(?:\[([^\]]*)\]\s*)?(\w+)\s*(?:\[([^\]]*)\]\s*)?[,)]",
                line,
            )
        if not m:
            continue
        rng, name, unpack = m.group(1), m.group(2), m.group(3)
        # a declaration is state when it is assigned only on a clock edge; the module keeps
        # the clocked ones on the _q / _vec / output name convention documented in the file
        if not (name.endswith("_q") or name.endswith("_vec") or name.startswith(("m_", "d_", "o_"))):
            continue
        w = 1
        if rng:
            hi = ev(rng.split(":")[0])
            lo = ev(rng.split(":")[1])
            if hi is None or lo is None:
                print("WIDTH UNKNOWN: %s [%s] at line %d" % (name, rng, lineno))
                continue
            w = abs(int(hi) - int(lo)) + 1
        depth = 1
        if unpack:
            a = ev(unpack.split(":")[0])
            b = ev(unpack.split(":")[1])
            depth = abs(int(a) - int(b)) + 1
        rows.append((lineno, name, depth, w, depth * w))

    groups = {
        "penampan kandidat penelusuran balik (bpk_vec)": lambda n: n == "bpk_vec",
        "garis tunda jalur data (sel_vec, hp_vec, bes_vec)": lambda n: n.endswith("_vec")
        and n != "bpk_vec",
        "sub-tahap RR (deret, antre, rih, ra1, pemb, peny, semai, gagal, jeda)": lambda n: any(
            n.startswith(p)
            for p in ("deret_", "antre_", "rih_", "ra1_", "pemb_", "peny_", "semai_", "gagal_", "jeda_")
        ),
        "pelacak fitur dan QRS (i_qrs, i_qrs_pk, kem_qrs dan benderanya)": lambda n: n.startswith(
            ("i_qrs", "kem_qrs")
        ),
        "state ambang adaptif (spki, npki, spkf, npkf)": lambda n: n
        in ("spki_q", "npki_q", "spkf_q", "npkf_q"),
        "introspeksi aditif (dbg_q, dbg_valid_q)": lambda n: n.startswith("dbg"),
        "pencacah ambang_state (delapan kali 32 bit)": lambda n: n.startswith("c_"),
        "pemindai amplop dan pencacah puncak (scan_q, pk_cnt_q)": lambda n: n in ("scan_q", "pk_cnt_q"),
        "keluaran aliran, sisi, dan introspeksi (m_*, d_*, o_beat_count)": lambda n: n.startswith(
            ("m_", "d_", "o_")
        ),
    }
    print("peak_detect flip-flop bits by construction, depth x width (plan 38 D1)")
    print("")
    print("%-70s %8s %8s %10s" % ("register", "depth", "width", "bits"))
    seen = set()
    total = 0
    for title, test in groups.items():
        sub = [r for r in rows if test(r[1]) and r[1] not in seen]
        if not sub:
            continue
        print("-- %s" % title)
        for lineno, name, depth, w, bits in sub:
            seen.add(name)
            print("%-70s %8d %8d %10d   (line %d)" % (name, depth, w, bits, lineno))
        print("%-70s %8s %8s %10d" % ("  subtotal", "", "", sum(r[4] for r in sub)))
        total += sum(r[4] for r in sub)
    rest = [r for r in rows if r[1] not in seen]
    if rest:
        print("-- tidak tergolong")
        for lineno, name, depth, w, bits in rest:
            print("%-70s %8d %8d %10d   (line %d)" % (name, depth, w, bits, lineno))
            total += bits
    print("")
    print("TOTAL flip-flop bit = %d" % total)
    print("")
    print("Rencana 38 (final38.md:1850-1858), anggaran state seluruh rantai:")
    plan = [
        ("penampan kandidat penelusuran balik, 128 entri 112 bit", 14336),
        ("jalur data, tujuh ring", 8152),
        ("antrean dan riwayat RR", 896),
        ("lapisan fitur", 1232),
        ("penampan keluaran keputusan", 1024),
    ]
    for title, bits in plan:
        print("  %-60s %6d" % (title, bits))
    print("  %-60s %6d" % ("total rantai", sum(b for _, b in plan)))
    print("")
    print("modul ini %d bit, jadi %d bit di bawah anggaran seluruh rantai" % (total, 25640 - total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
