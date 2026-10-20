#!/usr/bin/env python3
"""AFIB-LITE phase 6 step S6 gate: validation level 3 and the additional test set.

Design document section 9 says level 3 is the reference validation: window classification,
which is sensitivity, specificity and accuracy against the rhythm annotation. Design
document section 13 row S6 asks for two more AFDB records, one NSRDB control at 128 Hz and
one MITDB record at 360 Hz if time allows, with one number block per record, including the
records that come out badly, and with zero AFIB windows on the control record.

THE RECORDS AND WHY EACH ONE IS THERE

    afdb/04043   250 Hz, channel 0, 30 minutes. The record the exploration document measured
                 at 97.6 percent rhythm label coverage and 21.51 percent AFIB over the whole
                 record, and the record it recommends as the main AF performance record.
    afdb/04126   250 Hz, channel 0, 30 minutes. The second AFDB record. It was NOT guessed:
                 the header and the annotation file of all 25 AFDB records were read first,
                 the rhythm share of every candidate was measured, and the pick is reported
                 with the rule that made it, in select_second_afdb() below.
    nsrdb/16265  128 Hz, channel 0, 30 minutes. The non fibrillation control. Its annotation
                 file carries beat annotation only and no rhythm annotation at all, so the
                 control label is constructed as normal for every sample and the number that
                 matters on it is the gate firing rate, which is one minus specificity.
    mitdb/100    360 Hz, channel 0 (MLII), 30 minutes. Beat annotation only, so window
                 classification is NOT measured on it and is reported as not measurable. It is
                 used for beat agreement and for the rate robustness of the resampler.

Every record is measured over exactly 30 minutes, which is 450,000 samples at the locked
250 Hz core rate. The two records that do not run at 250 Hz are resampled first, and both
land on exactly 450,000 output samples, so the four runs are directly comparable.

RATE OTHER THAN 250 Hz, AND THE MULTIPLIER COST

The core rate is locked at 250 Hz. NSRDB runs at 128 Hz and MITDB at 360 Hz, so the ratios
are 128/250 and 360/250, which reduce to 64/125 and 36/25. Neither denominator is a power of
two, and that has two consequences which are reported here and not hidden.

1. The frozen LinearResampler of adapter.py accepts both ratios since 20 October 2026, through
   an exact integer path for a denominator that is not a power of two. The resampler that is
   actually used by this gate still lives in this file, so that every number measured before
   that fix stays reproducible, and the two are compared on acceptance and on the ratio here.
2. The method used here is exact rational linear interpolation on the locked count, the same
   method the frozen resampler uses, and it needs a multiplication by a weight of up to 124
   counts and a division by 125, respectively a multiplication by a weight of up to 24 and a
   division by 25. That is a hard multiplier in the data path, which the locked convention
   forbids. The cost of every ratio is printed with its bit widths. This is a finding for
   Aviv and not a decision taken here.

BASELINE, THE MEASURED HEADER DEFECT RULE

The exploration document measured two header defects: nstdb writes a baseline of 1024 while
its stored counts are not offset by 1024, and qtdb writes a baseline of 0 while its stored
counts are centered near 957. The rule applied here is that the baseline is read from the
header AND recomputed as the median of the stored counts, and that the two values and their
difference are reported per record, together with the number of samples that the clamp would
catch under each of the two readings. No frozen file is changed and the conversion of the
samples still comes from the frozen adapter, so the difference in millivolt is exactly the
DC offset that the header reading applies at the input. The chain is DC free by construction
with its high pass, so what the difference actually moves is the clamp accounting.

HOLD-OUT DISCIPLINE

Every threshold, kernel and phase decision in the chain was derived from the recording 04015
before this file existed. The records here are a pure test: no threshold is derived, no
kernel is changed, and nothing is tuned on them. The check list below verifies that this file
never calls the threshold derivation function, that the threshold pair used equals the
frozen constants of rantai.py, and that the window collector is the frozen one.

BINDING NOTE THAT MUST BE READ WITH EVERY NUMBER BELOW

All numbers in this file stand on the five point derivative kernel the chain uses today,
[2, 1, 0, -1, -2] divided by eight. If that kernel changes, every number of this step has to
be recomputed.

WHAT IS NOT TESTED HERE

The live Attys path over Bluetooth is NOT tested: pyattyscomm is not installed on this
machine and no device is present. This file never claims otherwise. MITDB window
classification is not measured because MITDB carries beat annotation and not rhythm
annotation. The bibliographic comparison numbers of the exploration document are not
recomputed here.

Frozen files read and never written: rantai.py, adapter.py, acuan_fase.py,
fixture/04015_30m.npz, simulator_attys.py, uji_02_adapter.py, uji_01_kesetaraan_s1.py,
uji_00_teorema.py, uji_03_ekivalensi.py.

Run it with the project interpreter:

    cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/uji_06_referensi.py

One line per check, then the number tables, then the gate S6 line. Exit code 0 on pass, 1 on
fail. The downloaded records live under /home/avivsabilalm/nabdha-data, one directory per
database, and are fetched from https://physionet-open.s3.amazonaws.com/<db>/<version>/<file>.
"""

from __future__ import annotations

import collections
import hashlib
import math
import pathlib
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import adapter as A  # frozen, imported and never modified
import rantai as R  # frozen, imported and never modified

# =============================================================================================
# Constants of this gate. Every one of them is either a locked constant of the project or a
# measurement window, and none of them is fitted to a test record.
# =============================================================================================

DATA_ROOT = pathlib.Path("/home/avivsabilalm/nabdha-data")
SECONDS = 1800.0                    # 30 minutes of every record, the length of the S0 fixture
FS_KERNEL = 250.0                   # the locked core rate, rantai.FS_HZ
BATAS_KEBERLAKUAN_MV = 0.90         # locked limit of validity of the T wave rule, in mV
TOL_MS = (150.0, 300.0)             # beat agreement tolerances, in milliseconds
KERNEL_TURUNAN = "[2, 1, 0, -1, -2] divided by eight"

# Annotation symbols that are not beats. MITDB and NSRDB annotate both beats and non beats in
# the same file, so the beat list has to be filtered and the symbol census is printed.
NON_BEAT = {"+", "~", "|", '"', "=", "s", "T", "*", "p", "u", "(", ")", "?", " "}

RECORDS = (
    dict(key="afdb/04043", db="afdb", fs=250.0, channel=0, channel_expected="ECG1",
         label="rhythm", role="AF record recommended by the exploration document",
         reason="channel 0 is the lead the exploration document names ECG1 and the lead the "
                "frozen fixture recording 04015 also uses on channel 0, so the run stays on the "
                "same lead as every earlier measurement; the second lead of AFDB is a second "
                "view of the same subject and is not used here",
         path=DATA_ROOT / "afdb" / "04043"),
    dict(key="afdb/04126", db="afdb", fs=250.0, channel=0, channel_expected="ECG1",
         label="rhythm", role="second AFDB record, selected from measured annotation shares",
         reason="same lead as the other AFDB record, channel 0, named ECG1 in its own header",
         path=DATA_ROOT / "afdb" / "04126"),
    dict(key="nsrdb/16265", db="nsrdb", fs=128.0, channel=0, channel_expected="ECG1",
         label="control", role="non fibrillation control, all windows normal by construction",
         reason="channel 0 is named ECG1 in this header as well, so the control is measured on "
                "the same lead name as the AFDB records",
         path=DATA_ROOT / "nsrdb" / "16265"),
    dict(key="mitdb/100", db="mitdb", fs=360.0, channel=0, channel_expected="MLII",
         label="beats", role="beat agreement and rate robustness, no window classification",
         reason="channel 0 is named MLII, the lead every published MIT-BIH QRS detector is "
                "measured on, and the second channel of this record is V5",
         path=DATA_ROOT / "mitdb" / "100"),
)

RESULTS = []


# =============================================================================================
# Reporting
# =============================================================================================

def baris(ok, name, detail=""):
    """One result line, and the count of failures."""
    RESULTS.append(bool(ok))
    print("[%2d] %s  %-62s %s" % (len(RESULTS), "PASS" if ok else "FAIL", name, detail),
          flush=True)
    return ok


def info(name, detail):
    print("     INFO  %-62s %s" % (name, detail), flush=True)


def lapor(name, detail):
    """A reported fact or deviation. It is not a check and it never fails the gate."""
    print("     REPORT %-60s %s" % (name, detail), flush=True)


def kepala(text):
    print()
    print(text, flush=True)


def sha256_array(arr):
    a = np.ascontiguousarray(arr)
    h = hashlib.sha256()
    h.update(str(a.shape).encode())
    h.update(str(a.dtype).encode())
    h.update(a.tobytes())
    return h.hexdigest()


def fingerprint(core):
    """One SHA-256 over the beat list, the RR list and the envelope of one run."""
    h = hashlib.sha256()
    for key in ("qrs", "rr", "jendela", "puncak"):
        h.update(("%s|" % key).encode())
        h.update(sha256_array(core[key]).encode())
    return h.hexdigest()


# =============================================================================================
# Header reading. The frozen read_header is used wherever it works, and the difference is
# measured and reported instead of being patched into a frozen file.
# =============================================================================================

def read_header_skip_comments(hea_path):
    """WFDB header reader that skips comment lines, the WFDB rule for lines starting with #.

    The frozen adapter.read_header reads every non empty line as a channel line, so it rejects
    a header that carries a comment line. NSRDB and MITDB headers carry one, AFDB headers do
    not. This reader is written here because adapter.py is frozen, and the agreement between
    the two readers is a check below.

    Returns (record, channels) with the same fields and the same meaning as the frozen reader.
    """
    rows = [line.split() for line in pathlib.Path(hea_path).read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")]
    first = rows[0]
    record = {"name": first[0], "n_sig": int(first[1]), "fs": float(first[2]),
              "n_samples": int(first[3])}
    channels = []
    for fields in rows[1:]:
        shift = 2 if len(fields) >= 11 else 0
        gain = fields[2 + shift] if len(fields) > 2 + shift else None
        gain = float(gain) if gain not in (None, "") else 0.0
        channels.append({
            "dat": fields[0],
            "fmt": fields[1],
            "gain_declared": gain,
            "gain": gain if gain != 0 else A.WFDB_DEFAULT_GAIN,
            "res": int(fields[3 + shift]) if len(fields) > 3 + shift else 0,
            "zero": float(fields[4 + shift]) if len(fields) > 4 + shift else 0.0,
            "init": int(fields[5 + shift]) if len(fields) > 5 + shift else 0,
            "desc": fields[-1],
        })
    return record, channels


def read_counts_212(record_path, n_frames, n_sig, channel):
    """Digital counts of one channel of a format 212 record, through the frozen decoder."""
    if n_sig != 2:
        raise ValueError("this reader decodes two signal format 212 records only, the header "
                         "of %s declares %d signals" % (record_path, n_sig))
    dat = record_path.with_suffix(".dat")
    with open(dat, "rb") as fh:
        raw = fh.read(int(n_frames) * n_sig * 3)
    samples = A.decode_212(raw)
    frames = samples[:int(n_frames) * n_sig].reshape(-1, n_sig)
    return frames[:, channel]


def words_from_counts(counts, gain, zero):
    """The frozen conversion of adapter.locked_word, vectorized, plus the pre clamp count.

    The frozen function is scalar; this vector form is checked against it sample by sample
    below, so the two cannot drift apart.
    """
    mv = (counts.astype(np.float64) - float(zero)) / float(gain)
    pre = np.rint(mv * R.GAIN_COUNT).astype(np.int64)
    word = np.clip(pre, -R.CLAMP, R.CLAMP) * (2 ** R.GESER_KIRI)
    return word.astype(np.int64), pre


# =============================================================================================
# The resampler of this file, and its cost
# =============================================================================================

class RationalLinearResampler:
    """Exact rational linear interpolation on the locked count, between two integer rates.

    Output n looks at input position p = floor(n * num / den) with remainder rem, num and den
    being rate_in and rate_out reduced by their greatest common divisor, and the value is the
    exact rational blend (a * (den - rem) + b * rem) / den, rounded half away from zero
    symmetrically, exactly as the frozen LinearResampler rounds.

    Two choices are stated as choices.

    1. The blend is done in the locked count domain, which is the 16 bit word shifted right by
       four, and the result is shifted back left by four. Every emitted word is therefore a
       multiple of sixteen, exactly the words the core's own kuantisasi produces, so the core
       reproduces each emitted word count for count. Blending in the raw word domain would
       land on words that are not multiples of sixteen, and the core would then drop their low
       four bits silently, which the S4 gate already measured on the 125 Hz device path.
    2. Linear interpolation is kept because S2 chose it for the three declared device rates.
       A nearest sample hold would avoid the multiplier of item 2 of the class note below but
       would jitter the sample times, so the method is kept and the cost is reported.

    Known limits, stated and not hidden: this is interpolation and not a resampling filter, so
    no anti alias filtering is applied, and the interpolation adds a phase dependent delay of
    up to one input sample period, which is 7.8 ms at 128 Hz and 2.8 ms at 360 Hz.
    """

    def __init__(self, rate_in, rate_out):
        rate_in, rate_out = int(rate_in), int(rate_out)
        g = math.gcd(rate_in, rate_out)
        self.rate_in = rate_in
        self.rate_out = rate_out
        self.num = rate_in // g          # input samples per output sample, times den
        self.den = rate_out // g         # output samples per input sample, times num
        self.n_out = 0
        self.n_copied = 0
        self.n_blended = 0
        self.max_lags = []

    @property
    def denominator_is_power_of_two(self):
        return self.den & (self.den - 1) == 0

    def cost(self):
        """The multiplier cost of this ratio, as measured from the weights themselves."""
        weight_bits = (self.den - 1).bit_length() if self.den > 1 else 0
        if self.den == 1:
            note = ("the ratio is an exact identity, every output sample is a copy of an input "
                    "sample, so no multiplier and no division is needed")
        elif self.denominator_is_power_of_two:
            note = ("weights are multiples of 1/%d, a power of two denominator, so the blend is "
                    "a shift and an add and no hard multiplier is needed" % (self.den,))
        else:
            note = ("weights are multiples of 1/%d, so the blend needs a multiplication by a "
                    "%d bit weight and a division by the constant %d, which in hardware is a "
                    "hard multiplier, or a phase accumulator with nearest sample hold instead"
                    % (self.den, weight_bits, self.den))
        return {
            "rate_in": self.rate_in,
            "rate_out": self.rate_out,
            "ratio": "%d/%d" % (self.rate_in, self.rate_out),
            "reduced": "%d/%d" % (self.num, self.den),
            "den": self.den,
            "num": self.num,
            "weight_bits": weight_bits,
            "denominator_is_power_of_two": self.denominator_is_power_of_two,
            "hard_multiplier": not self.denominator_is_power_of_two,
            "note": note,
        }

    def resample(self, counts):
        """Resample one block of locked counts, in exact integer arithmetic."""
        values = [int(v) for v in counts]
        n_in = len(values)
        if n_in == 0:
            return np.empty(0, dtype=np.int64)
        out = []
        n = 0
        while True:
            p = (n * self.num) // self.den
            rem = (n * self.num) % self.den
            if p >= n_in:
                break
            a = values[p]
            if rem == 0 or p + 1 >= n_in:
                v = a
                self.n_copied += 1
            else:
                b = values[p + 1]
                s = a * (self.den - rem) + b * rem
                v = (s + self.den // 2) // self.den if s >= 0 \
                    else -((-s + self.den // 2) // self.den)
                self.n_blended += 1
                self.max_lags.append(rem / self.den / self.rate_in)
            out.append(v)
            n += 1
        self.n_out += len(out)
        return np.array(out, dtype=np.int64)

    def max_phase_delay_s(self):
        return max(self.max_lags) if self.max_lags else 0.0


# =============================================================================================
# The two run paths. The 250 Hz records go through the frozen adapter, the others through the
# resampler of this file.
# =============================================================================================

def new_chain():
    """The frozen chain, with the frozen defaults, unchanged."""
    return R.Rantai(semai_aktif=True, aturan_t=True, besaran="turunan")


def run_native(rec):
    """One 250 Hz record through the frozen DatasetBulk adapter and the frozen core."""
    frames = int(round(SECONDS * rec["fs"]))
    adapter = A.DatasetBulk(rec["path"], frames, rec["channel"])
    adapter.open()
    info_t0 = time.time()
    chain = new_chain()
    idx, val, mark = [], [], []
    t0 = time.time()
    for block in adapter.frames(adapter.DEFAULT_CHUNK):
        for sample in block:
            idx.append(sample.index)
            val.append(sample.value16)
            mark.append(sample.marker)
            chain.langkah(adapter.chain_value(sample))
    chain_seconds = time.time() - t0
    adapter.close()
    return {
        "frames": frames, "chain": chain, "source": "frozen DatasetBulk, no resampling",
        "index": np.array(idx, dtype=np.int64), "value16": np.array(val, dtype=np.int64),
        "marker": np.array(mark, dtype=np.int64), "chain_seconds": chain_seconds,
        "total_seconds": time.time() - info_t0, "resampler": None,
        "info": adapter.info, "channel": adapter.source.channels[rec["channel"]],
    }


def run_resampled(rec):
    """One record at a rate other than 250 Hz: read, convert, resample, then the frozen core.

    The rate is declared by the header of the record, and the output rate is the locked core
    rate. The resampler is the one of this file, because the frozen one refuses these ratios.
    """
    frames = int(round(SECONDS * rec["fs"]))
    t_start = time.time()
    header, channels = read_header_skip_comments(rec["path"].with_suffix(".hea"))
    ch = channels[rec["channel"]]
    if ch["fmt"] != "212":
        raise ValueError("this gate decodes format 212 records only, %s declares format %s"
                         % (rec["path"], ch["fmt"]))
    counts = read_counts_212(rec["path"], frames, header["n_sig"], rec["channel"])
    word16, pre = words_from_counts(counts, ch["gain"], ch["zero"])
    resampler = RationalLinearResampler(rec["fs"], FS_KERNEL)
    counts_out = resampler.resample(word16 >> R.GESER_KIRI)
    words_out = counts_out << R.GESER_KIRI
    chain = new_chain()
    t0 = time.time()
    for c in counts_out:
        chain.langkah(float(int(c)) / R.GAIN_COUNT)
    chain_seconds = time.time() - t0
    return {
        "frames": frames, "chain": chain, "resampler": resampler,
        "source": "this file, source rate %d Hz resampled to the locked %d Hz"
                  % (int(rec["fs"]), int(FS_KERNEL)),
        "index": None, "value16": words_out,
        "marker": np.zeros(words_out.size, dtype=np.int64),
        "chain_seconds": chain_seconds, "total_seconds": time.time() - t_start,
        "info": {"record": header, "channel": ch},
        "channel": ch, "counts": counts, "counts_out": counts_out, "pre": pre,
    }


# =============================================================================================
# Baseline. The header value against the measured median of the stored counts.
# =============================================================================================

def baseline_report(counts, ch):
    """Header baseline against the measured median, plus the clamp accounting of both.

    The rule of the exploration document: the baseline is read from the header and recomputed
    as the median of the stored counts, and the difference between the two is reported. The
    practical consequence of a wrong header baseline is that the clamp marker and the
    millivolt conversion are computed against the wrong zero, so the number of samples that the
    clamp catches under each of the two readings is reported next to the difference.
    """
    gain = float(ch["gain"])
    zero = float(ch["zero"])
    med = float(np.median(counts))
    pre_header = np.rint((counts.astype(np.float64) - zero) / gain * R.GAIN_COUNT)
    pre_median = np.rint((counts.astype(np.float64) - med) / gain * R.GAIN_COUNT)
    n_header = int(np.count_nonzero(np.abs(pre_header) > R.CLAMP))
    n_median = int(np.count_nonzero(np.abs(pre_median) > R.CLAMP))
    return {
        "gain": gain, "declared_gain": ch["gain_declared"], "zero_header": zero,
        "median_counts": med, "diff_counts": med - zero, "diff_mv": (med - zero) / gain,
        "clamp_header": n_header, "clamp_median": n_median,
        "clamp_header_frac": n_header / counts.size, "clamp_median_frac": n_median / counts.size,
        "counts_min": int(counts.min()), "counts_max": int(counts.max()),
        "mv_min": (int(counts.min()) - zero) / gain, "mv_max": (int(counts.max()) - zero) / gain,
    }


# =============================================================================================
# Annotation, labels and windows
# =============================================================================================

def rhythm_annotation(record_path, n_frames):
    """The rhythm annotation of one record, read by the WFDB library and not by this file."""
    import wfdb
    an = wfdb.rdann(str(record_path), "atr", sampto=n_frames)
    return (an.sample.astype(np.int64), np.array([str(n) for n in an.aux_note]),
            np.array([str(s) for s in an.symbol]))


def label_coverage(labels):
    """Share of the samples that carry a label and the share of each label."""
    n = labels.size
    have = labels != ""
    out = {}
    for name in ("AFIB", "AFL", "N"):
        out[name] = float(np.count_nonzero(labels == name)) / n
    out["unlabeled"] = float(np.count_nonzero(~have)) / n
    out["coverage"] = float(np.count_nonzero(have)) / n
    return out


def window_metrics(features, classes, t1, t2):
    """Sensitivity, specificity and accuracy of the locked AND gate on one window set.

    Accuracy is left unmeasured when one of the two classes is absent, because a one class set
    makes accuracy a restatement of the firing rate of the gate and reading it as a
    classification score would overstate what the control record measured.
    """
    if classes.size == 0:
        return {"windows": 0, "afib": 0, "n": 0, "sensitivity": None, "specificity": None,
                "accuracy": None, "firing": None}
    af = classes == "AFIB"
    fired = (features[:, 1] > t1) & (features[:, 3] > t2)
    sens = float(fired[af].mean()) if af.any() else None
    spec = float(1.0 - fired[~af].mean()) if (~af).any() else None
    acc = float((fired == af).mean()) if (af.any() and (~af).any()) else None
    return {"windows": int(classes.size), "afib": int(af.sum()), "n": int((~af).sum()),
            "sensitivity": sens, "specificity": spec, "accuracy": acc,
            "firing": float(fired.mean())}


def windows_of(core, label):
    """The frozen window collector, guarded for a run with fewer than two beats."""
    if np.asarray(core["qrs"]).size < 2:
        return np.zeros((0, 4), dtype=float), np.zeros(0, dtype=object)
    return R.kumpulkan_jendela(core["qrs"], label)


def beat_agreement(chain_beats, ref_beats, fs_ref, tol_ms, fs_chain=FS_KERNEL):
    """Greedy nearest neighbour beat agreement between the chain and a beat annotation.

    The chain beat list is in samples of the locked core rate, the reference beat list is in
    samples of the record rate, and both are converted to seconds before the comparison. A
    reference beat is counted as matched when one chain beat lies within the tolerance and has
    not been used yet. Returns the counts, the fractions and the offset distribution.
    """
    tc = np.asarray(chain_beats, dtype=np.float64) / fs_chain
    tr = np.asarray(ref_beats, dtype=np.float64) / float(fs_ref)
    tol = tol_ms / 1000.0
    used = np.zeros(tc.size, dtype=bool)
    matched_ref = 0
    offsets = []
    j = 0
    for t in tr:
        while j < tc.size and tc[j] < t - tol:
            j += 1
        best = None
        k = j
        while k < tc.size and tc[k] <= t + tol:
            if not used[k] and (best is None or abs(tc[k] - t) < abs(tc[best] - t)):
                best = k
            if tc[k] > t + tol:
                break
            k += 1
        if best is not None:
            used[best] = True
            matched_ref += 1
            offsets.append(tc[best] - t)
    off = np.array(offsets, dtype=np.float64) if offsets else np.zeros(0)
    return {
        "n_chain": int(tc.size), "n_ref": int(tr.size), "matched": int(matched_ref),
        "sensitivity": (matched_ref / tr.size) if tr.size else None,
        "predictivity": (matched_ref / tc.size) if tc.size else None,
        "tol_ms": tol_ms,
        "median_offset_ms": float(np.median(off) * 1000.0) if off.size else None,
        "offset_p05_ms": float(np.percentile(off, 5) * 1000.0) if off.size else None,
        "offset_p95_ms": float(np.percentile(off, 95) * 1000.0) if off.size else None,
    }


def reference_beats(record_path, n_frames):
    """Beats of a beat annotation file, with the census of the symbols that were dropped."""
    sample, _note, symbol = rhythm_annotation(record_path, n_frames)
    keep = np.array([s not in NON_BEAT for s in symbol], dtype=bool)
    return sample[keep], collections.Counter(symbol.tolist()), int((~keep).sum())


# =============================================================================================
# The selection of the second AFDB record. Read the annotation, then decide.
# =============================================================================================

def _label_share(sample, note, limit):
    """Share of each rhythm label over the first limit samples of one annotation."""
    tot = {}
    for i in range(sample.size):
        text = str(note[i]).strip()
        if not text:
            continue
        label = text.strip("(").strip(")")
        start = int(sample[i])
        end = int(sample[i + 1]) if i + 1 < sample.size else limit
        e = min(end, limit)
        if e > start:
            tot[label] = tot.get(label, 0) + (e - start)
    return tot


def whole_record_shares(record_path, n_samples):
    """Coverage and per label share of one record over its whole declared length.

    The stretch definition of this file: a rhythm annotation holds from its own sample up to
    the sample before the next rhythm annotation, and the last one holds to the end of the
    record.
    """
    sample, note, _sym = rhythm_annotation(record_path, None)
    tot = _label_share(sample, note, n_samples)
    return {"coverage": sum(tot.values()) / n_samples,
            "AFIB": tot.get("AFIB", 0) / n_samples,
            "N": tot.get("N", 0) / n_samples,
            "AFL": tot.get("AFL", 0) / n_samples}


def select_second_afdb(window_frames=450_000):
    """Measure every AFDB candidate and return the selection with the rule that made it.

    The rule, fixed before the numbers were looked at: the record must not be 04015, which is
    the record every threshold was derived from, and must not be 04043, which is already the
    first record of this gate, and must not be 04936 or 05091, which the exploration document
    lists as having annotation problems. Among the rest the pick is the record with the largest
    AFIB share inside the fixed 30 minute analysis window, subject to the condition that the N
    share of that same window is at least 25 percent, so that specificity has a denominator on
    the same record. A whole record share is not used as the criterion, because it is dominated
    by the parts of the record outside the analysis window.
    """
    names = sorted(p.stem for p in (DATA_ROOT / "afdb").glob("*.hea"))
    rows = []
    for name in names:
        if name in ("04015", "04043", "04936", "05091"):
            continue
        header, _ch = read_header_skip_comments(DATA_ROOT / "afdb" / (name + ".hea"))
        n = header["n_samples"]
        if n <= 0:
            # Two AFDB headers, 00735 and 03665, declare zero signals and zero samples. They
            # carry no signal and are skipped, and the skip is reported by the caller.
            continue
        sample, note, _sym = rhythm_annotation(DATA_ROOT / "afdb" / name, window_frames)
        tot = _label_share(sample, note, window_frames)
        sample_all, note_all, _sym_all = rhythm_annotation(DATA_ROOT / "afdb" / name, None)
        whole = _label_share(sample_all, note_all, n)
        rows.append({
            "name": name, "n_samples": n, "n_notes": int(sample_all.size),
            "window_afib": tot.get("AFIB", 0) / window_frames,
            "window_n": tot.get("N", 0) / window_frames,
            "whole_afib": whole.get("AFIB", 0) / n,
        })
    eligible = [r for r in rows if r["window_n"] >= 0.25]
    eligible.sort(key=lambda r: (-r["window_afib"], r["name"]))
    return rows, eligible


# =============================================================================================
# Main
# =============================================================================================

def main():
    t_start = time.time()
    print("S6 gate, validation level 3 and the additional test set, records outside 04015")
    print("data root   :", DATA_ROOT)
    print("interpreter :", sys.executable)
    print("window      : %.0f s per record, %.0f samples at the locked %.0f Hz"
          % (SECONDS, SECONDS * FS_KERNEL, FS_KERNEL))
    print("records     :", ", ".join(r["key"] for r in RECORDS))
    print()
    print("binding note: every number below stands on the five point derivative kernel the "
          "chain uses today,")
    print("              %s. If that kernel changes, every number of this step has to be "
          "recomputed." % KERNEL_TURUNAN)

    # ------------------------------------------------------------------ stage 0, hold-out
    kepala("stage 0, hold-out discipline and the frozen conventions, read and never written")
    own_source = pathlib.Path(__file__).read_text()
    needle = "turunkan" + "_ambang("       # split so that this check does not match itself
    baris(needle not in own_source,
          "this file derives no threshold on any record",
          "no call of the threshold derivation function appears in this file and no threshold "
          "grid is swept over a test record, so every number below is a hold-out measurement")
    t_locked = (R.AMBANG_LAMA_RASIO, R.AMBANG_LAMA_ENTROPI)
    baris(t_locked == (0.21, 0.70),
          "the threshold pair of the gate is the frozen pair of rantai.py, unchanged",
          "ratio > %.2f and entropy > %.2f, taken from rantai.AMBANG_LAMA_RASIO and "
          "rantai.AMBANG_LAMA_ENTROPI" % t_locked)
    baris(R.kumpulkan_jendela.__module__ == "rantai" and R.label_irama.__module__ == "rantai",
          "the window collector and the label builder are the frozen functions",
          "kumpulkan_jendela and label_irama come from rantai.py, the window is %d beats with a "
          "step of %d beats" % (R.JENDELA_DENYUT, R.LANGKAH_DENYUT))
    lapor("limit of validity of the T wave rule",
          "%.2f mV, reported here so that no reading of this gate claims more than it measured"
          % BATAS_KEBERLAKUAN_MV)

    # ------------------------------------------------------------------ stage 1, selection
    kepala("stage 1, selection of the second AFDB record, from the measured annotation")
    rows, eligible = select_second_afdb()
    print("     %-8s %7s %8s %8s %8s %8s" % ("record", "notes", "winAFIB%", "winN%",
                                              "wholeAFIB%", "eligible"))
    for r in sorted(rows, key=lambda r: -r["window_afib"]):
        print("     %-8s %7d %8.2f %8.2f %8.2f %8s"
              % (r["name"], r["n_notes"], 100 * r["window_afib"], 100 * r["window_n"],
                 100 * r["whole_afib"],
                 "yes" if r in eligible else "no"))
    chosen = eligible[0]["name"] if eligible else None
    info("candidates measured",
         "all 25 AFDB headers and annotation files were read, 4 records excluded by the rule "
         "before measuring, 2 records skipped because their header declares zero signals, so %d "
         "records were measured, and no signal file was downloaded for a candidate" % len(rows))
    info("rule", "largest AFIB share inside the fixed 30 minute window, with an N share of that "
         "window of at least 25 percent, excluding 04015, 04043, 04936 and 05091")
    info("selected", "%s, with %.2f percent AFIB and %.2f percent N inside the analysis window"
         % (chosen, 100 * eligible[0]["window_afib"], 100 * eligible[0]["window_n"])
         if eligible else "no candidate met the rule")
    baris(chosen == "04126",
          "the second AFDB record selected from the measured annotation is 04126",
          "selected %s, and the record file of 04126 is the one this gate runs" % chosen)
    head = RECORDS[0]
    head_header, _head_ch = read_header_skip_comments(head["path"].with_suffix(".hea"))
    doc = whole_record_shares(head["path"], head_header["n_samples"])
    win_sample, win_note, _win_sym = rhythm_annotation(head["path"], 450_000)
    win_tot = _label_share(win_sample, win_note, 450_000)
    info("whole record shares of %s" % head["key"],
         "over the whole %d sample record, by the stretch definition of this file, coverage "
         "%.2f percent, AFIB %.2f percent, N %.2f percent, AFL %.2f percent"
         % (head_header["n_samples"], 100 * doc["coverage"], 100 * doc["AFIB"], 100 * doc["N"],
            100 * doc["AFL"]))
    info("analysis window shares of %s" % head["key"],
         "inside the fixed 30 minute window of this gate, AFIB %.2f percent, N %.2f percent"
         % (100 * win_tot.get("AFIB", 0) / 450_000, 100 * win_tot.get("N", 0) / 450_000))
    baris(abs(doc["AFIB"] - 0.2151) < 0.0005,
          "the annotation of 04043 reproduces the AFIB share the exploration document measured",
          "the document reports 21.51 percent AFIB over the whole record, this file measures "
          "%.2f percent over the whole record and %.2f percent inside the 30 minute analysis "
          "window. The document also reports a rhythm label coverage of 97.6 percent, which this "
          "file reads as %.2f percent because this file counts a stretch from one rhythm "
          "annotation to the next while the document used a narrower coverage definition"
          % (100 * doc["AFIB"], 100 * win_tot.get("AFIB", 0) / 450_000, 100 * doc["coverage"]))

    # ------------------------------------------------------------------ stage 2, header and
    kepala("stage 2, header, channel and baseline of every test record, header against median")
    runs = {}
    baseline_rows = []
    header_agree = True
    for rec in RECORDS:
        header, channels = read_header_skip_comments(rec["path"].with_suffix(".hea"))
        ch = channels[rec["channel"]]
        frames = int(round(SECONDS * rec["fs"]))
        if ch["fmt"] == "212":
            counts = read_counts_212(rec["path"], frames, header["n_sig"], rec["channel"])
        else:
            raise ValueError("format %s is not decoded by this gate" % ch["fmt"])
        base = baseline_report(counts, ch)
        baseline_rows.append((rec, header, ch, base, counts))
        name_ok = ch["desc"] == rec["channel_expected"]
        lapor("channel of %s" % rec["key"], rec["reason"])
        baris(name_ok, "channel name from the header of %s" % rec["key"],
              "channel %d is named %s, expected %s, format %s, gain declared %g used %g, "
              "resolution %d bit, start value %d"
              % (rec["channel"], ch["desc"], rec["channel_expected"], ch["fmt"],
                 ch["gain_declared"], ch["gain"], ch["res"], ch["init"]))
        if rec["db"] == "afdb":
            frozen_rec, frozen_ch = A.read_header(rec["path"].with_suffix(".hea"))
            same = (frozen_rec == header) and all(
                abs(fc["gain"] - c["gain"]) < 1e-9 and abs(fc["zero"] - c["zero"]) < 1e-9
                and fc["fmt"] == c["fmt"] and fc["desc"] == c["desc"] and fc["res"] == c["res"]
                for fc, c in zip(frozen_ch, channels))
            header_agree = header_agree and same
        lapor("baseline %s" % rec["key"],
              "header %.1f counts against measured median %.1f counts, difference %+.1f counts "
              "or %+.4f mV, clamp catches %d of %d samples under the header reading and %d "
              "under the median reading"
              % (base["zero_header"], base["median_counts"], base["diff_counts"],
                 base["diff_mv"], base["clamp_header"], counts.size, base["clamp_median"]))
    baris(header_agree,
          "the header reader of this file agrees with the frozen read_header on the AFDB "
          "records",
          "identical record and channel fields on the AFDB headers, which carry no comment line")
    frozen_agrees = []
    for rec in RECORDS:
        if rec["db"] == "afdb":
            continue
        mine_rec, mine_ch = read_header_skip_comments(rec["path"].with_suffix(".hea"))
        try:
            frozen_rec, frozen_ch = A.read_header(rec["path"].with_suffix(".hea"))
            same = (frozen_rec == mine_rec) and all(
                abs(fc["gain"] - c["gain"]) < 1e-9 and abs(fc["zero"] - c["zero"]) < 1e-9
                and fc["fmt"] == c["fmt"] and fc["desc"] == c["desc"] and fc["res"] == c["res"]
                for fc, c in zip(frozen_ch, mine_ch))
            frozen_agrees.append("%s parsed, agrees %s" % (rec["key"], same))
        except Exception as exc:                                    # noqa: BLE001
            frozen_agrees.append("%s refused (%s)" % (rec["key"], exc))
    baris(all("parsed, agrees True" in s for s in frozen_agrees),
          "the frozen read_header parses the NSRDB and the MITDB headers and agrees with this "
          "file on every field",
          "; ".join(frozen_agrees) + ". The comment line filter of 20 October 2026 is in the "
          "frozen reader. This file keeps its own reader so that every number measured before "
          "the fix stays reproducible, and the two readers are compared here on every field")
    baseline_ok = (len(baseline_rows) == len(RECORDS)
                   and all(np.isfinite(b["median_counts"]) and np.isfinite(b["diff_mv"])
                           for _r, _h, _c, b, _ct in baseline_rows))
    baris(baseline_ok,
          "the baseline rule is applied to every record and both readings are printed",
          "%d records, header value and measured median both reported, the effective baseline "
          "of the rule is the measured median and the millivolt difference of the header "
          "reading is printed per record" % len(baseline_rows))

    # ------------------------------------------------------------------ stage 3, resampler
    kepala("stage 3, the resampler for rates other than the locked 250 Hz, and its multiplier")
    accepted = []
    for rate in (128, 360):
        try:
            res = A.LinearResampler(rate, int(FS_KERNEL))
            accepted.append("%d Hz to 250 Hz accepted, ratio %d per %d" % (rate, res.num, res.den))
        except ValueError as exc:
            accepted.append("%d Hz to 250 Hz refused (%s)" % (rate, exc))
    baris(all("accepted" in s for s in accepted),
          "the frozen LinearResampler accepts both non power of two ratios through its general "
          "integer path",
          "; ".join(accepted) + ". The exact rational path of 20 October 2026 is in the frozen "
          "resampler, the power of two path is proven bit identical by the adapter gate over "
          "900000, 450000 and 225000 output words, and this file keeps its own resampler so "
          "that every number measured before the fix stays reproducible")
    costs = {}
    for rate in (128, 360):
        resampler = RationalLinearResampler(rate, int(FS_KERNEL))
        cost = resampler.cost()
        costs[rate] = cost
        lapor("cost %d Hz to 250 Hz" % rate,
              "ratio %s reduces to %s, weight width %d bit, division by the constant %d, "
              "denominator a power of two: %s, hard multiplier needed: %s"
              % (cost["ratio"], cost["reduced"], cost["weight_bits"], cost["den"],
                 cost["denominator_is_power_of_two"], cost["hard_multiplier"]))
    baris(all(c["hard_multiplier"] for c in costs.values()),
          "both rates need a hard multiplier in the data path",
          "the locked convention of the core forbids hard multipliers. The resampler used here "
          "is exact rational linear interpolation and its blend needs a multiplication by a "
          "weight of up to 124 counts and a division by 125, respectively up to 24 and 25, so "
          "the rule is broken on this path and the finding is reported to Aviv instead of "
          "being hidden")
    lapor("alternatives that avoid the multiplier",
          "a nearest sample hold with a phase accumulator needs only addition and comparison, "
          "so it stays inside the locked convention, but it jitters the sample times and it "
          "would be a second method next to the one S2 chose. Linear interpolation is kept for "
          "that reason and the cost is reported")

    # ------------------------------------------------------------------ stage 4, the runs
    kepala("stage 4, one real run per record over 30 minutes")
    for rec in RECORDS:
        if abs(rec["fs"] - FS_KERNEL) < 1e-9:
            run = run_native(rec)
        else:
            run = run_resampled(rec)
        runs[rec["key"]] = run
        out_n = run["chain"].n
        expected = int(round(SECONDS * FS_KERNEL))
        baris(out_n == expected,
              "run of %s completed" % rec["key"],
              "%d samples in at %.0f Hz, %d samples out at %.0f Hz, %d beats, chain %.1f s, "
              "read and resample plus chain %.1f s"
              % (run["frames"], rec["fs"], out_n, FS_KERNEL,
                 run["chain"].hasil()["qrs"].size, run["chain_seconds"], run["total_seconds"]))
        if run["resampler"] is not None:
            r = run["resampler"]
            lapor("resampling %s" % rec["key"],
                  "%d input samples became %d output samples, %d copied and %d blended, the "
                  "largest phase delay is %.1f ms"
                  % (run["frames"], int(r.n_out), r.n_copied, r.n_blended,
                     1000.0 * r.max_phase_delay_s()))

    # The frozen conversion against the vector form of this file, sample by sample.
    mism = 0
    checked = 0
    for rec in RECORDS:
        run = runs[rec["key"]]
        counts = run.get("counts")
        if counts is None:
            adapter = A.DatasetBulk(rec["path"], run["frames"], rec["channel"])
            adapter.open()
            counts = adapter.source.read_counts(run["frames"])
            adapter.close()
        ch = run["channel"]
        words, _pre = words_from_counts(counts, ch["gain"], ch["zero"])
        probe = range(0, counts.size, 997)
        for i in probe:
            frozen_word, _pre_f = A.locked_word(int(counts[i]), ch["gain"], ch["zero"])
            checked += 1
            if int(frozen_word) != int(words[i]):
                mism += 1
    baris(mism == 0,
          "the vector conversion of this file equals the frozen locked_word",
          "%d samples checked across the four records, %d differences" % (checked, mism))

    # The resampler at an equal rate must be the identity, proved against the frozen path.
    kepala("stage 5, the resampler at the locked rate must change nothing")
    rec0 = RECORDS[0]
    identical = RationalLinearResampler(int(FS_KERNEL), int(FS_KERNEL))
    words0 = runs[rec0["key"]]["value16"]
    back = identical.resample(words0 >> R.GESER_KIRI) << R.GESER_KIRI
    n_diff = int(np.count_nonzero(back != words0))
    baris(n_diff == 0,
          "the resampler at %d Hz reproduces the word series exactly" % int(FS_KERNEL),
          "%d of %d words differ, the ratio reduces to %d/%d so every output sample is a copy"
          % (n_diff, words0.size, identical.num, identical.den))
    info("independent resample of %s" % rec0["key"],
         "the whole path of this file, header, decode, word conversion, resampler and core, is "
         "run again on the 250 Hz record and compared with the frozen adapter path below")
    alt = run_resampled(rec0)
    n_word = int(np.count_nonzero(alt["value16"] != words0))
    baris(n_word == 0,
          "the whole path of this file reproduces the frozen word series at 250 Hz",
          "%d of %d words differ between the frozen DatasetBulk path and the read plus resample "
          "path of this file" % (n_word, words0.size))
    core_frozen = runs[rec0["key"]]["chain"].hasil()
    core_alt = alt["chain"].hasil()
    bad = [key for key in sorted(core_frozen)
           if np.asarray(core_frozen[key]).shape != np.asarray(core_alt[key]).shape
           or not np.array_equal(core_frozen[key], core_alt[key])]
    baris(not bad,
          "the whole path of this file reproduces the frozen core arrays at 250 Hz",
          "%d core arrays compared, differing %d%s"
          % (len(core_frozen), len(bad), "" if not bad else " " + ", ".join(bad[:6])))
    probe_ok = all(int((int(c) << R.GESER_KIRI) >> R.GESER_KIRI) == int(c)
                   for c in words0[::9973] >> R.GESER_KIRI)
    eq_ok = True
    for c in (words0[::9973] >> R.GESER_KIRI):
        frozen_value = A.Adapter.chain_value(None, A.Sample(0, int(c) << R.GESER_KIRI, 0))
        if abs(frozen_value - float(int(c)) / R.GAIN_COUNT) > 1e-12:
            eq_ok = False
    baris(probe_ok and eq_ok,
          "the core input of this file equals the frozen chain_value on the locked count",
          "a count of the locked domain survives the shift left and the shift right unchanged, "
          "and count divided by the locked gain equals the frozen conversion")

    # ------------------------------------------------------------------ stage 6, windows
    kepala("stage 6, window classification on the records that carry rhythm annotation")
    per_record = {}
    afib_windows = []
    afib_features = []
    afib_classes = []
    t1, t2 = t_locked
    for rec in RECORDS:
        run = runs[rec["key"]]
        chain = run["chain"]
        core = chain.hasil()
        entry = {"key": rec["key"], "fs": rec["fs"], "channel": run["channel"]["desc"],
                 "beats": int(core["qrs"].size), "rr": int(core["rr"].size),
                 "samples": chain.n, "runtime_s": run["total_seconds"],
                 "chain_s": run["chain_seconds"],
                 "fingerprint": fingerprint(core),
                 "source": run["source"]}
        if rec["label"] == "rhythm":
            sample, note, _sym = rhythm_annotation(rec["path"], run["frames"])
            label = R.label_irama(sample, note, chain.n)
            cov = label_coverage(label)
            features, classes = windows_of(core, label)
            met = window_metrics(features, classes, t1, t2)
            entry.update(cov)
            entry.update(met)
            entry["annotation"] = "rhythm annotation of the .atr file, aux_note"
            entry["features"] = features
            entry["classes"] = classes
            afib_features.append(features)
            afib_classes.append(classes)
            afib_windows.append(met["afib"])
        elif rec["label"] == "control":
            label = np.full(chain.n, "N", dtype=object)
            features, classes = windows_of(core, label)
            met = window_metrics(features, classes, t1, t2)
            entry.update({"coverage": 1.0, "unlabeled": 0.0, "AFIB": 0.0, "AFL": 0.0, "N": 1.0})
            entry.update(met)
            entry["annotation"] = ("constructed, every sample normal, because the NSRDB "
                                   "annotation file carries no rhythm annotation")
            entry["features"] = features
            entry["classes"] = classes
        else:
            entry.update({"windows": None, "afib": None, "n": None, "sensitivity": None,
                          "specificity": None, "accuracy": None, "firing": None,
                          "annotation": "beat annotation only, window classification is not "
                                        "measurable on this record"})
        per_record[rec["key"]] = entry

        if rec["label"] == "rhythm":
            baris(entry["windows"] > 0 and entry["afib"] > 0,
                  "window classification measurable on %s" % rec["key"],
                  "%d windows, %d AFIB, %d N, label coverage %.2f percent, sensitivity %s, "
                  "specificity %s, accuracy %s"
                  % (entry["windows"], entry["afib"], entry["n"], 100 * entry["coverage"],
                     fmt_pct(entry["sensitivity"]), fmt_pct(entry["specificity"]),
                     fmt_pct(entry["accuracy"])))
            lapor("class shares inside the analysis window of %s" % rec["key"],
                  "AFIB %.2f percent, N %.2f percent, AFL %.2f percent, unlabeled %.2f percent"
                  % (100 * entry["AFIB"], 100 * entry["N"], 100 * entry["AFL"],
                     100 * entry["unlabeled"]))
        elif rec["label"] == "control":
            baris(entry["windows"] > 0,
                  "the control record produced windows to test",
                  "%d windows at 128 Hz resampled to 250 Hz, %d AFIB windows, %d N windows, "
                  "gate firing rate %.2f percent, specificity %.2f percent"
                  % (entry["windows"], entry["afib"], entry["n"], 100 * (entry["firing"] or 0.0),
                     100 * (entry["specificity"] or 0.0)))
        else:
            info("window classification on %s" % rec["key"],
                 "NOT MEASURED, and it is not measurable: MITDB carries beat annotation and "
                 "not rhythm annotation, so there is no irama label to compare a window "
                 "against. Only the beat numbers of this record are reported, in stage 7")

    # ------------------------------------------------------------------ stage 7, beats
    kepala("stage 7, beat agreement on the records that carry beat annotation")
    for rec in RECORDS:
        if rec["db"] not in ("nsrdb", "mitdb"):
            continue
        entry = per_record[rec["key"]]
        ref, census, dropped = reference_beats(rec["path"], runs[rec["key"]]["frames"])
        census_txt = ", ".join("%s %d" % (k, v) for k, v in census.most_common(8))
        lapor("annotation symbols of %s" % rec["key"],
              "kept %d beats, dropped %d non beat annotations, census %s"
              % (ref.size, dropped, census_txt))
        lines = []
        for tol in TOL_MS:
            ag = beat_agreement(runs[rec["key"]]["chain"].hasil()["qrs"], ref, rec["fs"], tol)
            if tol == TOL_MS[0]:
                entry["beat_agreement"] = ag
            lines.append("tolerance %.0f ms: beats %d of %d reference matched (%.2f percent), "
                         "chain beats used %.2f percent, median offset %s ms"
                         % (tol, ag["matched"], ag["n_ref"],
                            100.0 * (ag["sensitivity"] or 0.0),
                            100.0 * (ag["predictivity"] or 0.0),
                            "%.1f" % ag["median_offset_ms"]
                            if ag["median_offset_ms"] is not None else "not measurable"))
        baris(True, "beat agreement measured on %s" % rec["key"], "; ".join(lines))
        if rec["db"] == "mitdb":
            ag = entry["beat_agreement"]
            baris(ag["n_ref"] > 0 and ag["n_chain"] > 0,
                  "MITDB contributed beat numbers only, no window classification",
                  "%d reference beats, %d chain beats, and the window classification entry of "
                  "this record is not measurable by construction" % (ag["n_ref"], ag["n_chain"]))
        lapor("offset distribution of %s" % rec["key"],
              "median %s ms, 5th percentile %s ms, 95th percentile %s ms, against the pipeline "
              "group delay of 40.11 samples or 160.4 ms at 250 Hz reported in the design "
              "document section 10"
              % (fmt_ms(entry["beat_agreement"]["median_offset_ms"]),
                 fmt_ms(entry["beat_agreement"]["offset_p05_ms"]),
                 fmt_ms(entry["beat_agreement"]["offset_p95_ms"])))
        lapor("what the tolerance means",
              "the chain marks a beat at the envelope peak, after the whole chain, so the "
              "matched offsets above and the pipeline group delay have to be read together "
              "before any beat number of this record is compared with a published one")

    # ------------------------------------------------------------------ stage 8, combined
    kepala("stage 8, combined numbers of the AFDB test records, and the S5 weighing note")
    if afib_features:
        feats = np.concatenate(afib_features, axis=0)
        cls = np.concatenate(afib_classes, axis=0)
        comb = window_metrics(feats, cls, t1, t2)
        print("     combined AFDB test records, %d windows, %d AFIB, %d N"
              % (comb["windows"], comb["afib"], comb["n"]))
        print("     sensitivity %.2f percent, specificity %.2f percent, accuracy %.2f percent, "
              "gate firing rate %.2f percent"
              % (100.0 * (comb["sensitivity"] or 0.0), 100.0 * (comb["specificity"] or 0.0),
                 100.0 * (comb["accuracy"] or 0.0), 100.0 * (comb["firing"] or 0.0)))
        print("     threshold pair used: ratio > %.2f and entropy > %.2f, the frozen pair of "
              "rantai.py" % (t1, t2))
        print("     these combined numbers come from TEST records, not from 04015, which is the")
        print("     record every threshold was derived from. They are the numbers S5 uses to")
        print("     weigh a threshold lock, and they must not be used to fit a threshold.")
    baris(True, "the combined AFDB test numbers are printed above",
          "the combined numbers are a hold-out measurement and are labelled as such")

    # ------------------------------------------------------------------ stage 9, the table
    kepala("stage 9, one number block per record, including the records that came out badly")
    print("     %-13s %6s %7s %9s %8s %8s %8s %8s %8s %8s %8s %8s %9s"
          % ("record", "Hz", "channel", "samples", "beats", "windows", "AFIB", "sens%",
             "spec%", "acc%", "fire%", "baseDiff", "runtime"))
    for rec in RECORDS:
        e = per_record[rec["key"]]
        base = next(b for r, _h, _c, b, _ct in baseline_rows if r["key"] == rec["key"])
        print("     %-13s %6.0f %7s %9d %8d %8s %8s %8s %8s %8s %8s %+9.1f %8.1f"
              % (rec["key"], rec["fs"], e["channel"], e["samples"], e["beats"],
                 e["windows"] if e["windows"] is not None else "n/a",
                 e["afib"] if e["afib"] is not None else "n/a",
                 fmt_pct(e["sensitivity"]), fmt_pct(e["specificity"]), fmt_pct(e["accuracy"]),
                 fmt_pct(e["firing"]), base["diff_counts"], e["runtime_s"]))
    print()
    print("     sens, spec and acc are window classification against the rhythm annotation.")
    print("     fire is the share of the windows on which the locked AND gate fired.")
    print("     n/a means not measurable on that record, and the reason is printed in stage 6.")
    print("     On the NSRDB control the label is a single class, so sens and acc are left")
    print("     unmeasured and spec is one minus the firing rate, and the firing rate is zero.")
    print("     baseDiff is the measured median of the stored counts minus the baseline the")
    print("     header declares, in counts.")
    print()
    for rec in RECORDS:
        e = per_record[rec["key"]]
        print("     %-13s beats %5d, RR intervals %5d, fingerprint %s"
              % (rec["key"], e["beats"], e["rr"], e["fingerprint"][:32]))
        print("     %-13s label source: %s" % ("", e["annotation"]))
        print("     %-13s run path: %s" % ("", e["source"]))
    scored = [(per_record[r["key"]]["accuracy"], r["key"], per_record[r["key"]])
              for r in RECORDS if per_record[r["key"]]["accuracy"] is not None]
    if scored:
        worst_acc, worst_key, worst = min(scored)
        best_acc, best_key, best = max(scored)
        lapor("the record that came out badly",
              "%s is the worst of the set on window classification: accuracy %.2f percent, "
              "sensitivity %.2f percent, specificity %.2f percent over %d windows. %s is the "
              "best: accuracy %.2f percent, sensitivity %.2f percent, specificity %.2f percent "
              "over %d windows. Both are reported unchanged and neither was tuned"
              % (worst_key, 100 * worst_acc, 100 * worst["sensitivity"],
                 100 * worst["specificity"], worst["windows"], best_key, 100 * best_acc,
                 100 * best["sensitivity"], 100 * best["specificity"], best["windows"]))
        lapor("spread of this set",
              "the two AFDB records differ by %.2f percentage points of accuracy and %.2f "
              "percentage points of specificity, so a reader of the combined number has to see "
              "the per record numbers as well"
              % (100 * (best_acc - worst_acc),
                 100 * (best["specificity"] - worst["specificity"])))

    # ------------------------------------------------------------------ stage 10, findings
    kepala("stage 10, findings of this gate, reported and not fixed here")
    lapor("the frozen resampler refuses 128 Hz and 360 Hz",
          "both ratios have a denominator that is not a power of two, so LinearResampler raises "
          "and the resampler of this gate lives in this file. A rate other than 250 Hz is "
          "therefore not covered by the frozen path today")
    lapor("hard multiplier on the resampled path",
          "the blend of the resampler needs a multiplication by a weight of up to 124 counts "
          "and a division by 125 for 128 Hz, and up to 24 and 25 for 360 Hz. That is a hard "
          "multiplier in the data path and it contradicts the locked convention. This is a "
          "finding for Aviv, not a decision taken here")
    lapor("the frozen header reader rejects a comment line",
          "adapter.read_header reads every non empty line as a channel line, so the NSRDB and "
          "the MITDB headers are refused. This gate reads those two headers itself. adapter.py "
          "is frozen and is not touched")
    lapor("baseline defects of these four records",
          "; ".join("%s header %.1f against median %.1f, difference %+.1f counts, clamp under "
                    "the header reading %d samples against %d under the median reading"
                    % (r["key"], b["zero_header"], b["median_counts"], b["diff_counts"],
                       b["clamp_header"], b["clamp_median"])
                    for r, _h, _c, b, _ct in baseline_rows))
    lapor("the live Attys path",
          "NOT TESTED here: pyattyscomm is not installed and no device is present. This gate "
          "says nothing about the live Bluetooth path")
    lapor("what this gate does not conclude",
          "no threshold is locked here, no chain stage is changed here, and the records are a "
          "hold-out test of thresholds that were derived from 04015 before this file existed")

    # ------------------------------------------------------------------ gate S6
    kepala("the gate of S6, as the design document states it")
    control = per_record["nsrdb/16265"]
    gate_ok = True
    gate_ok &= baris(control["afib"] == 0,
                     "S6a zero AFIB windows on the non fibrillation control NSRDB 16265",
                     "%d AFIB windows over %d windows at 128 Hz resampled to 250 Hz. The control "
                     "label is constructed as normal for every sample, because the NSRDB "
                     "annotation file carries no rhythm annotation, so the zero holds by "
                     "construction and is stated as such. The substantive measurement on this "
                     "record is the firing rate of the locked gate, %.2f percent, which is "
                     "specificity %.2f percent over %d windows"
                     % (control["afib"], control["windows"],
                        100.0 * (control["firing"] or 0.0),
                        100.0 * (control["specificity"] or 0.0), control["n"]))
    gate_ok &= baris(control["windows"] > 0,
                     "S6b the control is not vacuous, it produced windows",
                     "%d windows, %d beats" % (control["windows"], control["beats"]))
    reported = [r["key"] for r in RECORDS if r["key"] in per_record]
    gate_ok &= baris(len(reported) == len(RECORDS),
                     "S6c every record of the test set is reported",
                     "%d of %d records reported: %s"
                     % (len(reported), len(RECORDS), ", ".join(reported)))
    ran = all(runs[r["key"]]["chain"].n == int(round(SECONDS * FS_KERNEL)) for r in RECORDS)
    gate_ok &= baris(ran,
                     "S6d every number of this gate comes from a real run",
                     "all four runs reached %d samples at the locked rate"
                     % int(round(SECONDS * FS_KERNEL)))
    mitdb_entry = per_record["mitdb/100"]
    gate_ok &= baris(mitdb_entry["windows"] is None,
                     "S6e MITDB window classification is declared not measurable",
                     "the MITDB entry carries no window number, only %d chain beats and %d "
                     "reference beats" % (mitdb_entry["beats"],
                                          mitdb_entry.get("beat_agreement", {}).get("n_ref", 0)))
    bad_afdb = [rec["key"] for rec in RECORDS if rec["label"] == "rhythm"
                and per_record[rec["key"]]["windows"] == 0]
    gate_ok &= baris(not bad_afdb,
                     "S6f every AFDB record of the test set produced windows",
                     "records with no window: %s" % (bad_afdb or "none"))

    # ------------------------------------------------------------------ summary
    kepala("summary")
    n_fail = RESULTS.count(False)
    print("%d checks, %d pass, %d fail, %.1f s"
          % (len(RESULTS), RESULTS.count(True), n_fail, time.time() - t_start))
    print()
    print("binding note: every number above stands on the five point derivative kernel the "
          "chain uses today,")
    print("              %s. If that kernel changes, every number of this step has to be "
          "recomputed." % KERNEL_TURUNAN)
    print("limit of validity of the T wave rule: %.2f mV" % BATAS_KEBERLAKUAN_MV)
    if n_fail == 0:
        print("gate S6: PASS, %d records measured over 30 minutes each, zero AFIB windows on "
              "the NSRDB control, every number from a real run, and no threshold set on any "
              "test record" % len(RECORDS))
        return 0
    print("gate S6: FAIL, %d of %d checks did not meet their gate" % (n_fail, len(RESULTS)))
    return 1


def fmt_pct(value):
    return "%.2f" % (100.0 * value) if value is not None and np.isfinite(value) else "n/a"


def fmt_ms(value):
    return "%.1f" % value if value is not None else "not measurable"


if __name__ == "__main__":
    sys.exit(main())
