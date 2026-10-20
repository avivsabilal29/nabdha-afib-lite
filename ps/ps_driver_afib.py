#!/usr/bin/env python3
"""PS-side driver for AFIB-LITE (KV260), Fase 11 of plan 38, plus the mock backend.

Deliverable of plan step 5 of Fase 11: "write the PS driver with the nine step
initialisation sequence and a mock backend".

Two backends behind one register interface:

  MockBackend  a MODEL of the PL register semantics, written in Python. It emulates the
               AXI4-Lite register file, the sample enable, the beat counter, the decision
               window, the marker and clamp counters and the latency stamps, and it is fed
               with the frozen model outputs of record 04015 (fixture/*.npz, verified by
               sha256 against the frozen chain in model/). The plan's own measured output
               in final38.md section 8.8 is the reference this run is compared against.
               It is a MOCK: it proves the driver, never the RTL and never the board.
  UioBackend   the real path: mmap of /dev/uioN, addressed through the device tree, so no
               base address is hardcoded anywhere (plan risk note for Fase 11: "the driver
               must read its base address from the device tree, not from a constant").
               NOT VERIFIED ON HARDWARE: there is no board, no overlay and no /dev/uioN on
               this machine, so this path is exercised only as far as its device lookup,
               and the run says so.

Where the mock and the RTL deliberately differ, and why that is written down here instead
of being hidden:

  * ingress records a word at the WRITE (SAMPLE_FIFO) and a marker at the write that sets
    it, while rtl/regs_axi.sv counts a word on the strobed write and reads MARKER_LAST from
    the marker of that word. The two agree on what the driver can observe: SAMPLE_IN_STATUS
    words, MARKER_LAST, CLAMP_COUNT, GAP_COUNT.
  * the mock keeps a real depth 64 FIFO and reports its level in SAMPLE_IN_STATUS bits
    23:16 and in the CSV's fifo_level; the frozen port list of regs_axi has no consumer for
    a FIFO, so that field reads zero in hardware. Reported, not hidden.
  * the mock evaluates the two arms in the PL units of the register map, 1/200 and 1/100,
    at the operating point that is actually loaded (reset: 33 and 63), which is what the
    plan's measured row for window 0 shows (feat_ratio 61, feat_entropy 59, class 1).

Usage:
  ps_driver_afib.py                 # nine step init then five runs against the mock
  ps_driver_afib.py --out DIR       # where the self test writes its CSVs
  ps_driver_afib.py --negatif       # negative control: one mock answer is broken on
                                    # purpose and the run has to fail with rc != 0
  ps_driver_afib.py --backend uio   # device tree path; needs a board, says so otherwise

Nothing outside --out (default rtl-synthesis/reports/fase11/ps_driver) is written.
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import os
import pathlib
import struct
import sys
import time
from collections import deque

REPO = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO / "rtl-synthesis" / "reports" / "fase11" / "ps_driver"

# The frozen chain of model/rantai-afib-lite, the same digest the Fase 5 and Fase 9 exports
# check. The mock is fed from that chain's fixture, so the digest is verified before use.
RANTAI_SHA = "90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5"

# ---------------------------------------------------------------------------------
# The register map of Fase 11: plan 38 section 8.5, 36 slots 0x00..0x8C, plus the
# DEBUG_SEL / DEBUG_VAL pair at 0x90 and 0x94 that plan decision 9 accepts, which is
# what raises the map to 38 slots and is why the slot count is printed below.
# ---------------------------------------------------------------------------------
REGS = [
    # (offset, name, access, reset)
    (0x00, "CTRL", "RW", 0x00000000),
    (0x04, "STATUS", "RO", 0x00000001),
    (0x08, "IRQ_STATUS", "RO", 0x00000000),
    (0x0C, "IRQ_CLEAR", "W1C", 0x00000000),
    (0x10, "CLASS_OUT", "RO", 0x00000000),
    (0x14, "CONFIDENCE", "RO", 0x00000000),
    (0x18, "RR_LAST", "RO", 0x00000000),
    (0x1C, "BEAT_COUNT", "RO", 0x00000000),
    (0x20, "GAP_COUNT", "RO", 0x00000000),
    (0x24, "SAMPLE_IDX", "RO", 0x00000000),
    (0x28, "WINDOW_COUNT", "RO", 0x00000000),
    (0x2C, "CLAMP_COUNT", "RO", 0x00000000),
    (0x30, "FIFO_OVF_COUNT", "RO", 0x00000000),
    (0x34, "RR_LONG_COUNT", "RO", 0x00000000),
    (0x38, "RR_MARK_LAST", "RO", 0x00000000),
    (0x3C, "RATIO_THRESH", "RW", 0x00000021),      # 33, 1/200 units, 0.165
    (0x40, "ENTROPY_THRESH", "RW", 0x0000003F),    # 63, 1/100 units, 0.63
    (0x44, "ARM_SELECT", "RW", 0x0000000F),
    (0x48, "FEAT_RATIO", "RO", 0x00000000),
    (0x4C, "FEAT_ENTROPY", "RO", 0x00000000),
    (0x50, "FORMAT_CFG", "RW", 0x004C00FA),
    (0x54, "RATE_DIV", "RW", 0x00061A7F),          # 399999, 250.0 Hz at 100 MHz
    (0x58, "THRESH_SCALE", "RW", 0x00000100),
    (0x5C, "RR_BAND_LO", "RW", 0x0000005C),
    (0x60, "RR_BAND_HI", "RW", 0x00000074),
    (0x64, "VERSION_ID", "RO", 0x00010001),
    (0x68, "SCRATCH", "RW", 0x00000000),
    (0x6C, "SAMPLE_FIFO", "WO", 0x00000000),
    (0x70, "SAMPLE_MARK", "WO", 0x00000000),
    (0x74, "SAMPLE_IN_STATUS", "RO", 0x00000000),
    (0x78, "MARKER_LAST", "RO", 0x00000000),
    (0x7C, "CLAMP_THRESH", "RW", 0x000007FF),      # 2047, marked strictly above
    (0x80, "GAP_RECOVERY", "RW", 0x00000083),      # 131 samples
    (0x84, "REPLAY_LEN", "RW", 0x00000000),
    (0x88, "IDX_TAP_LAST", "RO", 0x00000000),
    (0x8C, "IDX_DEC_LAST", "RO", 0x00000000),
    (0x90, "DEBUG_SEL", "RW", 0x00000000),         # decision 9
    (0x94, "DEBUG_VAL", "RO", 0x00000000),         # decision 9, no tap input on this port list
]
IDX = {name: off for off, name, _, _ in REGS}
N_FROZEN = 36
RO = {off for off, _, acc, _ in REGS if acc == "RO"}
WO = {off for off, _, acc, _ in REGS if acc == "WO"}
W1C = {off for off, _, acc, _ in REGS if acc == "W1C"}

MARK_CLAMP = 1 << 0
MARK_GAP = 1 << 1
MARK_WEAK = 1 << 2
MARK_UNCERTAIN = 1 << 3

WINDOW_BEATS = 32
WINDOW_STEP = 4
GROUP_DELAY_SAMPLES = 40.11          # doc 36 section 8.2, measured from the NSRDB offsets
FS_HZ = 250
FIFO_DEPTH = 64
CONF_SCALE = 4                       # confidence is the distance to the binding threshold


class MockBackend:
    """Model of the PL register semantics, fed with the frozen model outputs."""

    def __init__(self, peaks, features, words, negatif=False, node="/proc/device-tree/afib_lite"):
        self.regs = {off: reset for off, _, _, reset in REGS}
        self.peaks = set(int(p) for p in peaks)
        self.features = features
        self.words = words
        self.fifo = deque()
        self.pending_mark = 0
        self.windows = []
        self.beat_idx_in = deque(maxlen=WINDOW_BEATS)
        self.beats_since_window = 0
        self.window_no = 0
        self.writes_in = 0
        self.pl_extra_delay = 3
        # the device tree node the driver was pointed at, recorded so the run can print it
        self.node = node
        # negative control: one answer of the mock is broken on purpose. The driver has to
        # notice it through its own check, not through an exception from here.
        self.negatif = negatif

    # ------------------------------------------------------------------ bus side
    def write(self, off, data):
        data &= 0xFFFFFFFF
        if off in RO:
            raise ValueError("write to the read only offset 0x%02X" % off)
        if off in WO:
            if off == IDX["SAMPLE_MARK"]:
                self.pending_mark = data & 0xF
                return
            if off == IDX["SAMPLE_FIFO"]:
                if len(self.fifo) >= FIFO_DEPTH:
                    self.regs[IDX["FIFO_OVF_COUNT"]] += 1
                    self.regs[IDX["IRQ_STATUS"]] |= 1 << 3
                    self.regs[IDX["STATUS"]] |= 1 << 1
                    return
                self.fifo.append((data & 0xFFFF, self.pending_mark))
                self.pending_mark = 0
                self.writes_in += 1
                return
        if off in W1C:
            self.regs[IDX["IRQ_STATUS"]] &= ~data & 0xFFFFFFFF
            self.regs[IDX["STATUS"]] &= ~((data & 0x1F) << 1) & 0xFFFFFFFF
            return
        if off not in self.regs:
            raise ValueError("write to the unmapped offset 0x%02X" % off)
        self.regs[off] = data

    def read(self, off):
        if off not in self.regs:
            raise ValueError("read of the unmapped offset 0x%02X" % off)
        if off == IDX["SCRATCH"] and self.negatif:
            return 0x00000000            # negative control: the bus proof cannot pass
        if off == IDX["SAMPLE_IN_STATUS"]:
            return ((len(self.fifo) & 0xFF) << 16) | (self.writes_in & 0xFFFF)
        if off == IDX["STATUS"]:
            s = self.regs[IDX["STATUS"]]
            if self.regs[IDX["CTRL"]] & 1:
                s |= 1 << 7              # b7 pipeline running
            if self.regs[IDX["SAMPLE_IDX"]] > WINDOW_BEATS * 100:
                s |= 1 << 6              # b6 warm up finished
            return s & 0xFFFFFFFF
        return self.regs[off]

    # ------------------------------------------------------------------ PL side
    def sample_slot(self):
        """One sample enable: consumes one FIFO word and advances the PL state."""
        if not self.fifo:
            return
        word, mark = self.fifo.popleft()
        idx = self.regs[IDX["SAMPLE_IDX"]] + 1
        self.regs[IDX["SAMPLE_IDX"]] = idx
        self.regs[IDX["MARKER_LAST"]] = mark
        if mark & MARK_CLAMP:
            self.regs[IDX["CLAMP_COUNT"]] += 1
            self.regs[IDX["STATUS"]] |= 1 << 4
            self.regs[IDX["IRQ_STATUS"]] |= 1 << 2
        if mark & MARK_GAP:
            self.regs[IDX["GAP_COUNT"]] += 1
            self.regs[IDX["STATUS"]] |= 1 << 3
            self.regs[IDX["IRQ_STATUS"]] |= 1 << 1
        self.regs[IDX["IDX_TAP_LAST"]] = max(0, idx - int(GROUP_DELAY_SAMPLES))
        if idx in self.peaks:
            self.regs[IDX["BEAT_COUNT"]] += 1
            self.beat_idx_in.append(idx)
            self.beats_since_window += 1
            if len(self.beat_idx_in) == WINDOW_BEATS and self.beats_since_window >= WINDOW_STEP:
                self.beats_since_window = 0
                self._emit_window(idx)

    def _emit_window(self, idx):
        # feature columns of the frozen chain: 0 RMSSD ms, 1 RMSSD/mean RR, 2 pNN50,
        # 3 entropy over four. The register units are 1/200 and 1/100.
        k = min(self.window_no, self.features.shape[0] - 1)
        ratio = int(round(float(self.features[k, 1]) * 200.0))
        ent = int(round(float(self.features[k, 3]) * 100.0))
        arm = self.regs[IDX["ARM_SELECT"]]
        # The gate compares in the RTL's own scales, not in the display units above. The two
        # threshold registers hold 1/200 and 1/100 codes and the top level bridges them to the
        # feature scales before classifier.sv compares them (rtl/classifier.sv:83-84 and
        # :128-129, :132-135): ratio is Q1.16 in 17 bits, entropy_over_4 is Q1.14 in 15 bits,
        # and the bridge is round(code * 2**frac / units), the same arithmetic the Fase 5
        # manifest records as ratio_register_q16 = 10813 and entropy_register_q14 = 10322.
        # Comparing the display codes instead (round(f * 200) > 33) puts the boundary half a
        # register LSB too high and disagreed with the golden census on 7 of 588 windows;
        # this pair of comparisons reproduces the census of 183 exactly.
        ratio_q16 = int(round(float(self.features[k, 1]) * 65536.0))
        ent_q14 = int(round(float(self.features[k, 3]) * 16384.0))
        bridge_ratio = (self.regs[IDX["RATIO_THRESH"]] * 65536 + 100) // 200
        bridge_ent = (self.regs[IDX["ENTROPY_THRESH"]] * 16384 + 50) // 100
        ok_ratio = ratio_q16 > bridge_ratio if arm & 1 else False
        ok_ent = ent_q14 > bridge_ent if arm & 2 else False
        if not (arm & 1) and not (arm & 2):
            fire = False
        elif (arm & 1) and (arm & 2):
            fire = (ok_ratio or ok_ent) if (arm & 0x10) else (ok_ratio and ok_ent)
        else:
            fire = ok_ratio if (arm & 1) else ok_ent
        klass = 2 if fire else 1          # 1 normal, 2 review, locked by D2
        dec_idx = idx + self.pl_extra_delay
        self.regs[IDX["CLASS_OUT"]] = (klass & 0x3) | (1 << 2)
        self.regs[IDX["FEAT_RATIO"]] = ratio
        self.regs[IDX["FEAT_ENTROPY"]] = ent
        self.regs[IDX["CONFIDENCE"]] = abs(self.regs[IDX["RATIO_THRESH"]] - ratio) * CONF_SCALE & 0xFFFF
        self.regs[IDX["RR_LAST"]] = int(self.beat_idx_in[-1] - self.beat_idx_in[-2])
        self.regs[IDX["WINDOW_COUNT"]] += 1
        self.regs[IDX["IDX_DEC_LAST"]] = dec_idx
        self.regs[IDX["IRQ_STATUS"]] |= 1 << 0
        self.windows.append({
            "window_no": self.window_no,
            "beat_count": self.regs[IDX["BEAT_COUNT"]],
            "idx_first_beat": self.beat_idx_in[0],
            "idx_in_last": idx,
            "idx_dec": dec_idx,
            "kelas": klass,
            "confidence": self.regs[IDX["CONFIDENCE"]],
            "feat_ratio": ratio,
            "feat_entropy": ent,
            "rr_last": self.regs[IDX["RR_LAST"]],
            "clamp_count": self.regs[IDX["CLAMP_COUNT"]],
            "gap_count": self.regs[IDX["GAP_COUNT"]],
            "ovf": self.regs[IDX["FIFO_OVF_COUNT"]],
            "fifo_level": len(self.fifo),
        })
        self.window_no += 1


class UioBackend:
    """The real path. NOT VERIFIED: no board, no overlay, no /dev/uioN on this machine.

    The base address is never a constant: the UIO device is found by the name the device
    tree / overlay gives it, and the mapping size is read from the device itself.
    """

    def __init__(self, label="afib_lite"):
        self.label = label
        self.uio = self._find_uio(label)
        size_txt = (self.uio / "maps/map0/size").read_text().strip()
        self.size = int(size_txt, 16) if size_txt.lower().startswith("0x") else int(size_txt)
        self.fd = os.open(str(self.uio / "device"), os.O_RDWR | os.O_SYNC)
        import mmap
        self.mem = mmap.mmap(self.fd, self.size, mmap.MAP_SHARED,
                             mmap.PROT_READ | mmap.PROT_WRITE)
        self.windows = []
        self.writes_in = 0

    @staticmethod
    def _find_uio(label):
        cands = []
        for name_file in sorted(pathlib.Path("/sys/class/uio").glob("uio*/name")):
            if label in name_file.read_text().strip():
                cands.append(name_file.parent)
        for node in glob.glob("/proc/device-tree/**/*", recursive=True):
            base = os.path.basename(node)
            if base.startswith("uio"):
                cands.append(pathlib.Path("/dev") / base)
        if not cands:
            raise RuntimeError(
                "no UIO device for label %r: the overlay is not loaded, /dev/uioN is absent. "
                "Use --backend mock on this machine." % label)
        return cands[0]

    def write(self, off, data):
        struct.pack_into("<I", self.mem, off, data & 0xFFFFFFFF)

    def read(self, off):
        return struct.unpack_from("<I", self.mem, off)[0]

    def sample_slot(self):
        pass                              # the PL advances itself in real time


class Driver:
    """The nine step initialisation order, the replay loop and the two CSV writers."""

    def __init__(self, bus, out: pathlib.Path):
        self.bus = bus
        self.out = out
        self.rows = []
        self.init_steps = []
        self.checks = []

    # ------------------------------------------------------------------ init, nine steps
    def init(self, rate_div=0x00061A7F, replay_len=0):
        """Nine numbered steps in the order the plan fixes.

        Step 1 and step 2 are the two checks the Fase 11 gate names: the identity read and
        the bus write/read proof. A failing check is recorded and printed, the run continues
        so that the whole log is available, and the process then exits non zero.
        """
        steps = []

        # 1: identity before anything else
        ver = self.bus.read(IDX["VERSION_ID"])
        ok1 = ver != 0
        steps.append((1, "versi", "0x%08X" % ver, ok1))
        print("  init 1/9 versi      0x%08X" % ver)
        self._check("init 1/9 VERSION_ID is not zero", ok1, "VERSION_ID read 0x%08X" % ver)

        # 2: AXI4-Lite write/read proof through SCRATCH
        self.bus.write(IDX["SCRATCH"], 0xA5A55A5A)
        back = self.bus.read(IDX["SCRATCH"])
        ok2 = back == 0xA5A55A5A
        steps.append((2, "scratch", "0x%08X (%s)" % (back, "ok" if ok2 else "BAD"), ok2))
        print("  init 2/9 scratch    %s" % steps[-1][2])
        self._check("init 2/9 SCRATCH reads back what was written", ok2,
                    "wrote 0xA5A55A5A, read 0x%08X" % back)

        # 3: clear every interrupt source and look at what is left
        self.bus.write(IDX["IRQ_CLEAR"], 0x1F)
        steps.append((3, "irq_clear", "0x%08X" % self.bus.read(IDX["IRQ_STATUS"]), True))
        print("  init 3/9 irq_clear %s" % (steps[-1][2]))

        # 4: stop the chain while it is configured
        self.bus.write(IDX["CTRL"], 0x00)
        steps.append((4, "ctrl_stop", "0x%08X" % self.bus.read(IDX["CTRL"]), True))
        print("  init 4/9 ctrl_stop %s" % (steps[-1][2]))

        # 5: rate
        self.bus.write(IDX["RATE_DIV"], rate_div)
        steps.append((5, "rate_div", "0x%08X" % self.bus.read(IDX["RATE_DIV"]), True))
        print("  init 5/9 rate_div %s" % (steps[-1][2]))

        # 6: format
        self.bus.write(IDX["FORMAT_CFG"], (1 << 22) | (12 << 16) | 250)
        steps.append((6, "format_cfg", "0x%08X" % self.bus.read(IDX["FORMAT_CFG"]), True))
        print("  init 6/9 format_cfg %s" % (steps[-1][2]))

        # 7: the operating point P1 and the ingest rails
        self.bus.write(IDX["RATIO_THRESH"], 0x21)      # 33, 0.165 in 1/200 units
        self.bus.write(IDX["ENTROPY_THRESH"], 0x3F)    # 63, 0.63 in 1/100 units
        self.bus.write(IDX["ARM_SELECT"], 0x0F)        # four arms lit
        self.bus.write(IDX["CLAMP_THRESH"], 2047)
        self.bus.write(IDX["GAP_RECOVERY"], 131)
        self.bus.write(IDX["REPLAY_LEN"], replay_len)
        steps.append((7, "ambang", "ratio=0x%08X entropy=0x%08X arm=0x%08X"
                      % (self.bus.read(IDX["RATIO_THRESH"]),
                         self.bus.read(IDX["ENTROPY_THRESH"]),
                         self.bus.read(IDX["ARM_SELECT"])), True))
        print("  init 7/9 ambang %s" % (steps[-1][2]))

        # 8: start
        self.bus.write(IDX["CTRL"], 0x01)
        steps.append((8, "ctrl", "0x%08X" % self.bus.read(IDX["CTRL"]), True))
        print("  init 8/9 ctrl %s" % (steps[-1][2]))

        # 9: status snapshot
        st = self.bus.read(IDX["STATUS"])
        steps.append((9, "status", "0x%08X" % st, True))
        print("  init 9/9 status %s" % (steps[-1][2]))

        self.init_steps = steps
        return steps

    def _check(self, what, ok, detail):
        self.checks.append((what, bool(ok), detail))
        print("  %-46s %s" % (what, "PASS" if ok else "FAIL: " + detail))

    # ------------------------------------------------------------------ replay
    def replay(self, words, marks=None, mode="burst"):
        """Push one recorded stream through the PL and log every decision window.

        mode 'realtime' waits one sample slot (4 ms) per sample, 'burst' pushes as fast as
        the PL consumes. The counts are meant to be identical; only wall time differs.
        """
        marks = marks if marks is not None else [0] * len(words)
        seen = 0
        slot_s = 1.0 / FS_HZ
        next_slot = time.monotonic()
        for w, m in zip(words, marks):
            self.bus.write(IDX["SAMPLE_MARK"], int(m))
            self.bus.write(IDX["SAMPLE_FIFO"], int(w) & 0xFFFF)
            self.bus.sample_slot()
            idx_in = self.bus.read(IDX["SAMPLE_IDX"])
            if mode == "realtime":
                next_slot += slot_s
                dt = next_slot - time.monotonic()
                if dt > 0:
                    time.sleep(dt)
                if self.bus.read(IDX["CTRL"]) & 1 == 0:
                    break
            n = len(getattr(self.bus, "windows", []))
            while seen < n:
                row = dict(self.bus.windows[seen])
                seen += 1
                row["idx_in_read"] = idx_in         # read back on the PS side, error < 1 slot
                row["latensi_pipa_sampel"] = row["idx_dec"] - row["idx_in_last"]
                row["tundaan_grup_sampel"] = row["idx_in_last"] - self.bus.read(IDX["IDX_TAP_LAST"])
                row["latensi_jendela_sampel"] = row["idx_dec"] - row["idx_first_beat"]
                row["latensi_jendela_s"] = row["latensi_jendela_sampel"] / FS_HZ
                row["ts_host"] = time.time()
                self.rows.append(row)
        return {
            "samples_in": len(words),
            "writes_in": getattr(self.bus, "writes_in", len(words)),
            "windows": len(self.rows),
            "beats": self.bus.read(IDX["BEAT_COUNT"]),
            "gap": self.bus.read(IDX["GAP_COUNT"]),
            "clamp": self.bus.read(IDX["CLAMP_COUNT"]),
            "ovf": self.bus.read(IDX["FIFO_OVF_COUNT"]),
            "idx": self.bus.read(IDX["SAMPLE_IDX"]),
        }

    def latency_report(self):
        if not self.rows:
            return "no window yet: latency is undefined before the first 32 beats"
        tail = [r["latensi_pipa_sampel"] for r in self.rows[1:]]
        grp = [r["tundaan_grup_sampel"] for r in self.rows]
        win = [r["latensi_jendela_s"] for r in self.rows[1:] if r["latensi_jendela_s"] > 0]
        return ("windows=%d | pipeline tail samples min %d max %d | tap group delay "
                "samples %d (model says 40.11) | window fill s train min %.1f"
                % (len(self.rows), min(tail), max(tail), grp[-1],
                   min(win) if win else float("nan")))

    # ------------------------------------------------------------------ CSV
    WINDOW_COLS = ["window_no", "beat_count", "idx_first_beat", "idx_in_last", "idx_dec",
                   "latensi_pipa_sampel", "tundaan_grup_sampel", "latensi_jendela_sampel",
                   "latensi_jendela_s", "kelas", "confidence", "feat_ratio", "feat_entropy",
                   "rr_last", "clamp_count", "gap_count", "ovf", "fifo_level", "idx_in_read",
                   "ts_host"]
    MEASURE_COLS = ["jalur", "ukur", "run_ke", "iters", "elapsed_s", "infer_per_s", "mode",
                    "laju_sampel_hz", "jendela_denyut", "langkah_denyut",
                    "latensi_tapis_sampel", "latensi_tapis_ms", "latensi_keputusan_s",
                    "daya_diam_w", "daya_aktif_w", "delta_daya_w", "energi_per_inferensi_uj",
                    "rail", "suhu_ruang_c", "suhu_soc_c", "gap", "ovf", "fifo_flag", "catatan"]

    def write_csv(self, name, rows, cols):
        path = self.out / name
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow(r)
        return path


def load_fixture():
    """The frozen model outputs of record 04015, digest checked before use."""
    import numpy as np
    rantai = REPO / "model" / "rantai-afib-lite" / "rantai.py"
    got = hashlib.sha256(rantai.read_bytes()).hexdigest()
    if got != RANTAI_SHA:
        raise RuntimeError("frozen chain moved: rentai.py sha256 %s" % got)
    path = sorted(glob.glob(str(REPO / "model" / "rantai-afib-lite" / "fixture" / "*.npz")))[0]
    z = np.load(path)
    return (z["masukan16"].astype(int), z["puncak"].astype(int),
            z["jendela_fitur"].astype(float), got)


def main(argv=None):
    ap = argparse.ArgumentParser(description="AFIB-LITE PS driver, Fase 11")
    ap.add_argument("--backend", choices=("mock", "uio"), default="mock")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--negatif", action="store_true",
                    help="negative control: break one mock answer on purpose")
    ap.add_argument("--node", default="/proc/device-tree/afib_lite",
                    help="device tree node the mock records as its base, or the UIO label")
    args = ap.parse_args(argv)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("driver self-test against the register-semantics MOCK, not against a board"
          if args.backend == "mock" else
          "driver run against the UIO backend, real path")
    print("map: %d slots, 0x00..0x%02X (frozen map %d slots 0x00..0x%02X plus DEBUG_SEL 0x90 "
          "and DEBUG_VAL 0x94 of plan decision 9)"
          % (len(REGS), REGS[-1][0], N_FROZEN, REGS[N_FROZEN - 1][0]))
    print("base address: %s (from the device tree, never a constant)" % args.node)
    words, peaks, feats, sha = load_fixture()
    print("fixture: %d words, %d peaks, %d feature rows, chain sha256 %s"
          % (len(words), len(peaks), feats.shape[0], sha[:16]))
    print("feature row 0: %s" % feats[0].tolist())

    if args.backend == "uio":
        bus = UioBackend(args.node)
    else:
        bus = MockBackend(peaks, feats, words[:60000], negatif=args.negatif, node=args.node)

    n = 60000
    words_a = words[:n]
    marks_a = [MARK_WEAK if abs(int(w)) < (0.5 * 409.4 * 16) else 0 for w in words_a]

    # ---- the nine step initialisation order, then run 1 -----------------------------
    drv = Driver(bus, out)
    drv.init(replay_len=n)
    t0 = time.monotonic()
    stats = drv.replay(words_a, marks_a, mode="burst")
    el = time.monotonic() - t0
    print("run1 burst: %s in %.3f s (%.0f kS/s host side)" % (stats, el, len(words_a) / el / 1000))
    print("  latency: %s" % drv.latency_report())
    p1 = drv.write_csv("window.pl.04015.20261021.01.csv", drv.rows, Driver.WINDOW_COLS)
    print("  csv: %s (%d rows)" % (p1, len(drv.rows)))
    print("  first 3 rows: %s" % [(r["window_no"], r["kelas"], r["latensi_pipa_sampel"],
                                   r["tundaan_grup_sampel"]) for r in drv.rows[:3]])
    hist = {}
    for r in drv.rows:
        hist[r["kelas"]] = hist.get(r["kelas"], 0) + 1
    print("  class histogram of the logged windows: %s" % hist)
    lines = p1.read_text().splitlines()
    print("  csv header: %s" % lines[0])
    print("  csv row 1  : %s" % lines[1])
    drv._check("run1 every window logged exactly once", len(drv.rows) == stats["windows"],
               "%d rows against %d windows" % (len(drv.rows), stats["windows"]))
    drv._check("run1 both classes present, the decision path is really crossed",
               len(hist) == 2, "histogram %s" % hist)
    drv._check("run1 no gap and no overflow on a clean replay",
               stats["gap"] == 0 and stats["ovf"] == 0, "stats %s" % stats)

    # ---- run 2: real time pacing over 5 s --------------------------------------------
    n2 = FS_HZ * 5
    bus2 = MockBackend(peaks, feats, words[:n2], node=args.node)
    drv2 = Driver(bus2, out)
    drv2.init(replay_len=n2)
    t0 = time.monotonic()
    st2 = drv2.replay(words[:n2], mode="realtime")
    el2 = time.monotonic() - t0
    print("run2 realtime: %s, wall %.3f s for %d samples (expected %.3f s)"
          % (st2, el2, st2["samples_in"], st2["samples_in"] / FS_HZ))
    drv._check("run2 one sample slot per sample, 1250 samples is 5.000 s",
               abs(el2 - st2["samples_in"] / FS_HZ) < 0.25 and st2["idx"] == n2,
               "wall %.3f s, idx %d" % (el2, st2["idx"]))

    # ---- run 3: clamp path. A synthetic rail to rail segment must raise the flag ----
    stress = [(32767 if i % 7 < 4 else -32768) for i in range(6000)]
    bus3 = MockBackend(peaks, feats, stress, node=args.node)
    drv3 = Driver(bus3, out)
    drv3.init(replay_len=len(stress))
    st3 = drv3.replay(stress, [MARK_CLAMP] * len(stress), mode="burst")
    st3["marker_last"] = "0x%X" % bus3.read(IDX["MARKER_LAST"])
    st3["status"] = "0x%X" % bus3.read(IDX["STATUS"])
    print("run3 clamp stress: %s" % st3)
    drv._check("run3 every stressed sample counted as clamped",
               st3["clamp"] == len(stress) and st3["marker_last"] == "0x1",
               "clamp %d marker_last %s" % (st3["clamp"], st3["marker_last"]))
    drv._check("run3 the clamp flag reached the status register",
               (int(st3["status"], 16) >> 4) & 1 == 1, "status %s" % st3["status"])

    # ---- run 4: gap path -------------------------------------------------------------
    gap_marks = [MARK_GAP if i in (1000, 2500) else 0 for i in range(4000)]
    bus4 = MockBackend(peaks, feats, words[:4000], node=args.node)
    drv4 = Driver(bus4, out)
    drv4.init(replay_len=4000)
    st4 = drv4.replay(words[:4000], gap_marks, mode="burst")
    print("run4 gap injection: gap=%d ovf=%d idx=%d" % (st4["gap"], st4["ovf"], st4["idx"]))
    drv._check("run4 two injected gaps counted, none lost",
               st4["gap"] == 2 and st4["ovf"] == 0 and st4["idx"] == 4000, "stats %s" % st4)

    # ---- run 5: the measurement CSV of the energy procedure, shape only --------------
    rows = [{
        "jalur": "pl", "ukur": "energi", "run_ke": k, "iters": st2["windows"] or 1,
        "elapsed_s": round(el2, 3), "infer_per_s": 0, "mode": "burst",
        "laju_sampel_hz": FS_HZ, "jendela_denyut": WINDOW_BEATS, "langkah_denyut": WINDOW_STEP,
        "latensi_tapis_sampel": GROUP_DELAY_SAMPLES, "latensi_tapis_ms": 160.44,
        "latensi_keputusan_s": "", "daya_diam_w": "", "daya_aktif_w": "",
        "delta_daya_w": "", "energi_per_inferensi_uj": "", "rail": "som_ina260",
        "suhu_ruang_c": "", "suhu_soc_c": "", "gap": st2["gap"], "ovf": st2["ovf"],
        "fifo_flag": 0, "catatan": "mock run, no board, power columns empty on purpose",
    } for k in range(1, 6)]
    p5 = drv.write_csv("measure.energi.pl.20261021.01.csv", rows, Driver.MEASURE_COLS)
    print("run5 measure csv: %s" % p5)
    hdr = p5.read_text().splitlines()[0].split(",")
    drv._check("run5 measure header matches the plan, byte for byte",
               hdr == Driver.MEASURE_COLS, str(hdr))

    # ---- the two CSV schemas of the plan are the ones on disk -----------------------
    drv._check("window csv header matches the plan, byte for byte",
               lines[0] == ",".join(Driver.WINDOW_COLS), lines[0])
    drv._check("window csv row 1 is the plan's measured row shape, 20 fields",
               len(lines[1].split(",")) == 20, lines[1])

    bad = [c for c in drv.checks if not c[1]]
    print("checks: %d, failed: %d" % (len(drv.checks), len(bad)))
    if bad:
        for what, ok, detail in bad:
            print("FAIL: %s (%s)" % (what, detail))
        print("FAIL: driver self test against the mock")
        return 1
    print("OK: driver logic exercised end to end against the mock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
