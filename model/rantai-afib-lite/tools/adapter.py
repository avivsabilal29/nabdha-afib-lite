#!/usr/bin/env python3
"""AFIB-LITE phase 6 step S2: four acquisition adapters over one interface.

    DatasetBulk    an AFDB record, .hea plus .dat, read as one large block
    DatasetStream  the same record, one sample per call, optional 250 Hz pacing
    AttysBulk      a recorded Attys session, 24 bit two channel frames
    AttysStream    Attys over Bluetooth, callback blocks, 125 / 250 / 500 Hz resampled to 250 Hz

The locked core of rantai.py is imported and never modified. The adapters own every format
detail: format detection, the alignment to the locked 16 bit word, the resampling to the
declared rate, and the packet gap bookkeeping. The core receives one value per sample.

Per sample record, exactly three fields:

    index    monotone sample counter of the output rate, never a wall clock
    value16  the locked 16 bit input word, kuantisasi of the recording value
    marker   bit 0 clamp, bit 1 packet gap, bit 2 weak signal, bit 3 uncertain

Bulk is not a second mode. Adapter.frames(chunk=1) is the streaming form and
Adapter.frames(chunk=8192) is the bulk form of the same loop over the same read() function,
so the two modes share the core path exactly and cannot drift apart.

The rate is declared once, by open(). No method infers a rate in the middle of a stream.

The team choices in this file, stated as choices and not as facts:

  resampler       exact rational linear interpolation of the 16 bit word, see LinearResampler
  clamp marker    a sample is marked clamped when its rounded count strictly exceeds the
                  locked clamp of 2047, so a sample that lands exactly on 2047 is not marked
  weak marker     trailing one second window of the absolute 16 bit word below 0.5 mV
  gap recovery    a lost sample leaves the core memory contaminated for GAP_RECOVERY samples
"""

from __future__ import annotations

import json
import math
import pathlib
import sys
import time
from collections import deque, namedtuple

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import rantai as R  # the locked core, imported, never modified

# =============================================================================================
# Marker bits. Requirement of the design document: at least clamp, packet gap and weak.
# =============================================================================================

MARKER_CLAMP = 1 << 0
MARKER_GAP = 1 << 1
MARKER_WEAK = 1 << 2
MARKER_UNCERTAIN = 1 << 3
MARKER_ORDER = (MARKER_CLAMP, MARKER_GAP, MARKER_WEAK, MARKER_UNCERTAIN)
MARKER_NAME = {MARKER_CLAMP: "clamp", MARKER_GAP: "gap", MARKER_WEAK: "weak",
               MARKER_UNCERTAIN: "uncertain"}

# Weak signal. Team choice: the trailing one second window of the absolute 16 bit word
# stays below 0.5 mV, which is ten percent of the locked plus minus 5 mV full scale.
# A trailing window and not a centered one, so that bulk and stream compute the same value
# at the same index by construction.
WEAK_MV = 0.5
WEAK_WINDOW = 250  # one second at the core rate
WEAK_WORD = int(round(WEAK_MV * R.GAIN_COUNT)) << R.GESER_KIRI

# Packet gap recovery. A lost input sample contaminates every core output that looks back
# at it: the low pass looks back 12 samples, the high pass 32, the derivative 4 and the
# window 38, which is 86 samples for one output sample. The envelope peak picker adds its
# radius of 27 samples and the slope measurement its half window of 18. The recovery window
# below is the conservative sum.
GAP_RECOVERY = 12 + 32 + 4 + 38 + 27 + 18

# =============================================================================================
# Attys constants. The front end ladder is a chosen assumption of the simulator, not a
# measured device property, because no Attys device is available on this machine.
# =============================================================================================

ATTYS_TARGET_HZ = 250
ATTYS_DEVICE_HZ = (125, 250, 500)
ATTYS_CHANNELS = 2
ATTYS_FRAME_BYTES = 6  # two 24 bit channels, little endian, 3 bytes each
ATTYS_WORD_SHIFT = 8  # bits 23..8 are the locked 16 bit word, bits 7..0 are front end noise
ATTYS_FRONT_END = 1 << 12  # counts24 per locked count12, the ladder the simulator writes

WFDB_DEFAULT_GAIN = 200.0  # gain 0 in a WFDB header means this, as the WFDB library reads it

Sample = namedtuple("Sample", "index value16 marker")


# =============================================================================================
# WFDB record reading. Format detection is explicit, the decode is written here instead of
# being hidden, and both are checked against the WFDB library by uji_adapter.py.
# =============================================================================================

def _field(fields, i, default=None):
    """Field of a header line, with a default when the header leaves it out."""
    if i >= len(fields) or fields[i] == "":
        return default
    return fields[i]


def read_header(hea_path):
    """Format detection of a WFDB header file.

    Returns (record, channels). record carries name, n_sig, fs and the declared sample
    count. Each channel carries the dat file, the format code, the gain, the resolution in
    bits, the zero level, the initial value and the signal name. A declared gain of zero
    means the WFDB default of 200 counts per millivolt, and that is what the fixture
    recording 04015 carries.
    """
    rows = [line.split() for line in pathlib.Path(hea_path).read_text().splitlines()
            if line.strip()]
    first = rows[0]
    record = {"name": first[0], "n_sig": int(first[1]), "fs": float(first[2]),
              "n_samples": int(first[3])}
    channels = []
    for fields in rows[1:]:
        # The samples per frame field is optional. When it is present the gain fields shift
        # by one place, and a header line then carries eleven fields or more instead of nine.
        shift = 2 if len(fields) >= 11 else 0
        gain = _field(fields, 2 + shift)
        gain = float(gain) if gain is not None else 0.0
        channels.append({
            "dat": fields[0],
            "fmt": fields[1],
            "gain_declared": gain,
            "gain": gain if gain != 0 else WFDB_DEFAULT_GAIN,
            "res": int(_field(fields, 3 + shift, 0)),
            "zero": float(_field(fields, 4 + shift, 0) or 0.0),
            "init": int(_field(fields, 5 + shift, 0) or 0),
            "desc": fields[-1],
        })
    return record, channels


def decode_212(buf):
    """WFDB format 212: two 12 bit samples in three little endian bytes.

    even = byte0 + 256 * (byte1 & 0x0F), odd = byte2 + 256 * (byte1 >> 4). Values above
    2047 are two's complement and get 4096 subtracted.
    """
    b = np.frombuffer(buf, dtype=np.uint8)
    b = b[:(b.size // 3) * 3].astype(np.int32).reshape(-1, 3)
    even = b[:, 0] + 256 * (b[:, 1] & 0x0F)
    odd = b[:, 2] + 256 * ((b[:, 1] >> 4) & 0x0F)
    out = np.empty(even.size * 2, dtype=np.int64)
    out[0::2] = even
    out[1::2] = odd
    out[out > 2047] -= 4096
    return out


class RecordSource:
    """Format detection and block reads of one WFDB record.

    Only the byte aligned interleaved formats are decoded here, 212 by the function above,
    16 and 32 by a plain little endian read. Every other format is refused with an error
    instead of being guessed.
    """

    def __init__(self, record_path, n_frames=None, channel=0, block_frames=4096):
        self.record_path = pathlib.Path(record_path)
        self.n_frames = None if n_frames is None else int(n_frames)
        self.channel = int(channel)
        self.block_frames = int(block_frames)
        self.record = None
        self.channels = None
        self.fmt = None
        self.gain = None
        self.zero = None
        self.frame_bytes = None
        self.n_avail = 0
        self.pos = 0
        self._fh = None

    def open(self):
        """Detect the format, open the dat file, and report what was found."""
        self.record, self.channels = read_header(self.record_path.with_suffix(".hea"))
        ch = self.channels[self.channel]
        self.fmt = ch["fmt"]
        self.gain = ch["gain"]
        self.zero = ch["zero"]
        if self.fmt == "212":
            bytes_per_sample = 1.5
        elif self.fmt == "16":
            bytes_per_sample = 2.0
        elif self.fmt == "32":
            bytes_per_sample = 4.0
        else:
            raise ValueError("format %r is not decoded by this adapter, it is not guessed"
                             % (self.fmt,))
        span = bytes_per_sample * self.record["n_sig"]
        if float(span) != int(span):
            raise ValueError("a frame of %d signals of format %s is not a whole number of "
                             "bytes, block reads are refused" % (self.record["n_sig"], self.fmt))
        self.frame_bytes = int(span)
        dat_path = self.record_path.with_suffix("." + ch["dat"].rsplit(".", 1)[-1])
        if not dat_path.exists():
            dat_path = self.record_path.parent / ch["dat"]
        size = dat_path.stat().st_size
        self.n_avail = size // self.frame_bytes
        declared = self.record["n_samples"]
        want = self.n_avail if self.n_frames is None else min(self.n_frames, self.n_avail)
        self.n_frames = want
        self._fh = open(dat_path, "rb")
        return {"record": self.record, "channel": ch, "dat": str(dat_path),
                "declared_frames": declared, "available_frames": self.n_avail,
                "used_frames": self.n_frames, "frame_bytes": self.frame_bytes,
                "bytes_per_sample": bytes_per_sample}

    def rewind(self):
        self.pos = 0
        self._fh.seek(0)

    def read_counts(self, want):
        """Digital counts of the selected channel for the next want frames."""
        want = int(min(want, self.n_frames - self.pos))
        if want <= 0:
            return np.empty(0, dtype=np.int64)
        self._fh.seek(self.pos * self.frame_bytes)
        raw = self._fh.read(want * self.frame_bytes)
        if self.fmt == "212":
            samples = decode_212(raw)
        elif self.fmt == "16":
            samples = np.frombuffer(raw, dtype="<i2").astype(np.int64)
        else:
            samples = np.frombuffer(raw, dtype="<i4").astype(np.int64)
        frames = samples[:want * self.record["n_sig"]].reshape(want, self.record["n_sig"])
        self.pos += want
        return frames[:, self.channel]

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None


def locked_word(count, gain, zero):
    """One 12 bit count of a recording to the locked 16 bit word.

    Returns (value16, pre_clamp_count). pre_clamp_count is the count before the clamp, so
    the clamp marker can tell a sample that was clipped from one that landed exactly on the
    clamp value. The conversion itself is rantai.kuantisasi, the locked convention, and it
    is not reimplemented here.
    """
    mv = (float(count) - float(zero)) / float(gain)
    pre = int(np.rint(mv * R.GAIN_COUNT))
    value16, _state, _range = R.kuantisasi(mv)
    return int(value16), pre


# =============================================================================================
# The one interface.
# =============================================================================================

class Adapter:
    """One interface for four sources.

    Subclasses implement open() and read(). Everything else, the marker bookkeeping, the
    monotone index, the weak window, the batching of the bulk mode and the driving of the
    locked core, lives here so that no two adapters can drift apart.
    """

    MODE = "adapter"
    SOURCE = "abstract"
    BLOCK_FRAMES = 4096
    DEFAULT_CHUNK = 1  # streaming by default, a bulk adapter declares a large chunk

    def __init__(self):
        self._rate = None
        self._index = 0
        self._weak = deque()
        self._uncertain_until = 0
        self._count = {m: 0 for m in MARKER_ORDER}
        self._opened = False
        self._closed = False
        self.declared = None

    # ------------------------------------------------------------------ the declared rate
    def declare_rate(self, rate_hz):
        """Declare the output rate once, at open(). Never in the middle of a stream."""
        if self._opened:
            raise RuntimeError("the rate of %s is already declared" % (self.MODE,))
        self._rate = float(rate_hz)
        self._opened = True
        self.declared = {"mode": self.MODE, "source": self.SOURCE, "rate_hz": self._rate,
                         "block_frames": self.BLOCK_FRAMES, "default_chunk": self.DEFAULT_CHUNK}
        return self._rate

    @property
    def rate_hz(self):
        if self._rate is None:
            raise RuntimeError("the rate is declared by open(), it is never inferred "
                               "in the middle of a stream (mode %s)" % (self.MODE,))
        return self._rate

    def open(self):
        raise NotImplementedError

    def read(self):
        """The next sample, or None at the end of the source."""
        raise NotImplementedError

    def close(self):
        self._closed = True

    # ------------------------------------------------------------------ the marker bits
    def mark_recovery(self, n_after):
        """Mark the next n_after output samples as touched by a packet gap."""
        end = self._index + int(n_after)
        if end > self._uncertain_until:
            self._uncertain_until = end

    def _emit(self, value16, pre=None, gap=False, uncertain=False):
        """Build the record of one output sample and advance the monotone index."""
        i = self._index
        self._index += 1
        a = abs(int(value16))
        ring = self._weak
        while ring and ring[-1][1] <= a:
            ring.pop()
        ring.append((i, a))
        floor_index = i - WEAK_WINDOW + 1
        while ring and ring[0][0] < floor_index:
            ring.popleft()
        marker = 0
        # Clamp. With the pre clamp count the test is strict, so a sample that lands exactly
        # on 2047 is not marked. Without it, as on the Attys paths where only the rail value
        # survives, the test is the rail value itself.
        if pre is not None:
            clipped = abs(int(pre)) > R.CLAMP
        else:
            clipped = a >= (R.CLAMP << R.GESER_KIRI)
        if clipped:
            marker |= MARKER_CLAMP
        # Weak. The bit warms up over the first window, like the threshold stage warms up
        # from zero, so a partial window never claims a weak signal.
        if i >= WEAK_WINDOW - 1 and ring[0][1] < WEAK_WORD:
            marker |= MARKER_WEAK
        if gap:
            marker |= MARKER_GAP
        if uncertain or i < self._uncertain_until:
            marker |= MARKER_UNCERTAIN
        for bit in MARKER_ORDER:
            if marker & bit:
                self._count[bit] += 1
        return Sample(i, int(value16), marker)

    def markers(self):
        """Count of every marker bit over the samples emitted so far."""
        return {MARKER_NAME[b]: self._count[b] for b in MARKER_ORDER}

    # ------------------------------------------------------------------ the one core path
    def chain_value(self, sample):
        """The value handed to the locked core.

        The core applies kuantisasi itself, so the adapter hands it the millivolt value
        whose locked conversion is exactly the 16 bit word of the record. That inverse is
        exact for every word, because the word is always the locked count times sixteen.
        """
        return (sample.value16 >> R.GESER_KIRI) / R.GAIN_COUNT

    def frames(self, chunk=None):
        """Blocks of samples. chunk of one is the streaming form, a large chunk is the bulk form.

        Both forms call read() the same number of times in the same order, so the two modes
        produce the same series by construction and not by a later test.
        """
        n = self.DEFAULT_CHUNK if chunk is None else int(chunk)
        if n < 1:
            raise ValueError("a chunk must carry at least one sample")
        if n == 1:
            while True:
                sample = self.read()
                if sample is None:
                    return
                yield [sample]
        else:
            while True:
                block = []
                while len(block) < n:
                    sample = self.read()
                    if sample is None:
                        break
                    block.append(sample)
                if not block:
                    return
                yield block

    def drive(self, chain, chunk=None):
        """One locked chain driven to completion. Returns (n_samples, seconds)."""
        t0 = time.time()
        n = 0
        step = chain.langkah
        for block in self.frames(chunk):
            for sample in block:
                step(self.chain_value(sample))
                n += 1
        return n, time.time() - t0

    def series(self, chunk=None):
        """The three frozen series of this adapter: index, value16, marker, as arrays."""
        idx, val, mark = [], [], []
        for block in self.frames(chunk):
            for sample in block:
                idx.append(sample.index)
                val.append(sample.value16)
                mark.append(sample.marker)
        return (np.array(idx, dtype=np.int64), np.array(val, dtype=np.int64),
                np.array(mark, dtype=np.int64))


# =============================================================================================
# 1 and 2. The dataset paths. The same record, one read as a large block, one replayed
# sample by sample with optional pacing.
# =============================================================================================

class DatasetBulk(Adapter):
    """An AFDB record. 12 bit counts shifted left four to the 16 bit word, 250 Hz straight
    into the core, rhythm annotation read from the .atr file for validation."""

    MODE = "dataset bulk"
    SOURCE = "wfdb record, one large block"
    BLOCK_FRAMES = 1 << 30  # the whole recording is one block
    DEFAULT_CHUNK = 8192

    def __init__(self, record_path, n_frames=450_000, channel=0):
        super().__init__()
        self.record_path = pathlib.Path(record_path)
        self.n_frames = int(n_frames)
        self.channel = int(channel)
        self.source = None
        self.info = None
        self._counts = None
        self._cursor = 0
        self._notes = None

    def open(self):
        self.source = RecordSource(self.record_path, self.n_frames, self.channel,
                                   self.BLOCK_FRAMES)
        self.info = self.source.open()
        self._counts = self.source.read_counts(self.source.n_frames)  # one large block
        self._cursor = 0
        return self.declare_rate(self.info["record"]["fs"])

    def read(self):
        if self._counts is None or self._cursor >= self._counts.size:
            return None
        count = int(self._counts[self._cursor])
        self._cursor += 1
        value16, pre = locked_word(count, self.source.gain, self.source.zero)
        return self._emit(value16, pre=pre)

    def annotations(self):
        """Rhythm annotation of the record, read from the .atr file.

        The annotation is validation material. It never enters the sample path, and the
        reader for it is the WFDB library, not this module.
        """
        if self._notes is None:
            import wfdb
            an = wfdb.rdann(str(self.record_path), "atr", sampto=self.n_frames)
            self._notes = (an.sample.astype(np.int64),
                           np.array([str(n) for n in an.aux_note]),
                           np.array([str(s) for s in an.symbol]))
        return self._notes

    def close(self):
        self.source.close()
        super().close()


class DatasetStream(Adapter):
    """The same record replayed one sample per call, the path the demo scenario uses.

    The dat file is read in blocks of BLOCK_FRAMES frames and replayed one sample at a
    time, so this is the streaming form of the same source. Pacing sleeps for one sample
    period to feel real time. The sleep never touches the arithmetic: the record carries a
    monotone sample index and no time, so the value cannot depend on the wall clock.
    """

    MODE = "dataset stream"
    SOURCE = "wfdb record, replayed per sample"
    BLOCK_FRAMES = 4096
    DEFAULT_CHUNK = 1

    def __init__(self, record_path, n_frames=450_000, channel=0, pacing=False):
        super().__init__()
        self.record_path = pathlib.Path(record_path)
        self.n_frames = int(n_frames)
        self.channel = int(channel)
        self.pacing = bool(pacing)
        self.source = None
        self.info = None
        self._buffer = np.empty(0, dtype=np.int64)
        self._cursor = 0
        self._notes = None

    def open(self):
        self.source = RecordSource(self.record_path, self.n_frames, self.channel,
                                   self.BLOCK_FRAMES)
        self.info = self.source.open()
        self._buffer = np.empty(0, dtype=np.int64)
        self._cursor = 0
        return self.declare_rate(self.info["record"]["fs"])

    def read(self):
        if self._cursor >= self._buffer.size:
            block = self.source.read_counts(self.BLOCK_FRAMES)
            if block.size == 0:
                return None
            self._buffer = block
            self._cursor = 0
        count = int(self._buffer[self._cursor])
        self._cursor += 1
        value16, pre = locked_word(count, self.source.gain, self.source.zero)
        sample = self._emit(value16, pre=pre)
        if self.pacing:
            time.sleep(1.0 / self.rate_hz)
        return sample

    def annotations(self):
        if self._notes is None:
            import wfdb
            an = wfdb.rdann(str(self.record_path), "atr", sampto=self.n_frames)
            self._notes = (an.sample.astype(np.int64),
                           np.array([str(n) for n in an.aux_note]),
                           np.array([str(s) for s in an.symbol]))
        return self._notes

    def close(self):
        self.source.close()
        super().close()


# =============================================================================================
# 3 and 4. The Attys paths. The front end delivers 24 bit two channel frames. Only the top
# 16 bits are read, because the bottom byte is front end noise.
# =============================================================================================

def attys_frame_word(frame, channel=0):
    """One 24 bit frame to the locked 16 bit word of one channel.

    The frame is six little endian bytes, channel 0 in the first three and channel 1 in the
    next three, each a signed 24 bit count. Bits 23..8 are the locked word and bits 7..0 are
    front end noise, so an arithmetic shift right by eight is the whole scale alignment
    between the Attys front end and the locked domain. This is the scalar reference; the
    vectorized block_words() below must agree with it, and uji_adapter.py checks that.
    """
    b = int(frame[3 * channel]) | (int(frame[3 * channel + 1]) << 8) \
        | (int(frame[3 * channel + 2]) << 16)
    if b & 0x800000:
        b -= 1 << 24
    return b >> ATTYS_WORD_SHIFT


def block_words(block, channel=0):
    """The locked word of every frame of one block, vectorized.

    Two block layouts are accepted, because two device drivers hand over two shapes:

      (n, 6) unsigned bytes   raw frames, the layout of a recorded session and of the
                              simulator, six bytes per frame
      (n, 2) integers         decoded 24 bit channel values, the layout a device library
                              hands to its callback
    """
    b = np.asarray(block)
    if b.ndim != 2:
        raise ValueError("a block of frames must be two dimensional, got shape %s"
                         % (b.shape,))
    if b.shape[1] == ATTYS_FRAME_BYTES:
        b = b.astype(np.int64)
        v = b[:, 3 * channel] | (b[:, 3 * channel + 1] << 8) | (b[:, 3 * channel + 2] << 16)
    elif b.shape[1] == ATTYS_CHANNELS:
        v = b.astype(np.int64)[:, channel]
    else:
        raise ValueError("a block of %d columns is neither %d raw bytes per frame nor %d "
                         "decoded channels per frame"
                         % (b.shape[1], ATTYS_FRAME_BYTES, ATTYS_CHANNELS))
    v = v & 0xFFFFFF
    v = np.where(v & 0x800000, v - (1 << 24), v)
    return v >> ATTYS_WORD_SHIFT


class LinearResampler:
    """Exact rational linear interpolation of the locked 16 bit word between two rates.

    Team choice, with the reason, because neither the notebooks nor the design document
    fixes a method.

    Chosen: linear interpolation between the two nearest device samples, in integer
    arithmetic on the 16 bit word, with the fractional weight written as an exact rational.

    Reasons. The three declared device rates are 125, 250 and 500 Hz against a 250 Hz core,
    so the ratio reduces to 1/2, 1/1 and 2/1 and every interpolation weight is a power of
    two fraction, 0, 1/2 or 1. The resampler is therefore a shift and an add: no hard
    multiplier, no floating point, and nothing that a bit width has to absorb. It is also
    exactly invertible at 125 to 250 and at 500 to 250, which is what makes the equality
    between the Attys paths and the dataset path provable instead of approximate. A
    windowed sinc or polyphase FIR would be sharper, but it needs multipliers in the
    hardware path and the three declared rates do not need it.

    Known limit, stated and not hidden: this is interpolation, not a resampling filter.
    Careful decimation from 500 Hz to 250 Hz would also need an anti alias filter. The
    effective analog bandwidth of the Attys front end is not measured on this machine, so
    no anti alias filter is added and the aliasing error of the real 500 Hz path is left
    unmeasured rather than claimed to be zero.
    """

    def __init__(self, rate_in, rate_out):
        rate_in, rate_out = int(rate_in), int(rate_out)
        g = math.gcd(rate_in, rate_out)
        self.num = rate_in // g  # input samples per output sample, times den
        self.den = rate_out // g
        if self.den & (self.den - 1):
            raise ValueError("the interpolation weight denominator %d is not a power of two, "
                             "so the weights would need a hard multiplier" % (self.den,))
        self.rate_in = rate_in
        self.rate_out = rate_out
        self.n_in = 0
        self.n_out = 0
        self._word = deque()
        self._gap = deque()
        self._unc = deque()
        self._base = 0

    def push(self, words, gap, uncertain):
        """Append one block of device samples."""
        for w, g, u in zip(words, gap, uncertain):
            self._word.append(int(w))
            self._gap.append(bool(g))
            self._unc.append(bool(u))
        self.n_in += len(words)

    def _at(self, j):
        k = j - self._base
        return self._word[k], self._gap[k], self._unc[k]

    def _drop_before(self, j):
        while self._base < j and self._word:
            self._word.popleft()
            self._gap.popleft()
            self._unc.popleft()
            self._base += 1

    def drain(self, finish=False):
        """Emit every output sample whose interpolation window has arrived.

        Returns (words, gap, uncertain) of the new output samples. With finish True the tail
        is emitted by repeating the last device sample.
        """
        out_w, out_g, out_u = [], [], []
        while True:
            if self.n_in == 0:
                break
            p = (self.n_out * self.num) // self.den
            rem = (self.n_out * self.num) % self.den
            last = self.n_in - 1
            if p > last:
                break
            if rem and p + 1 > last and not finish:
                break
            a, ga, ua = self._at(p)
            if rem == 0 or p + 1 > last:
                w, g, u = a, ga, ua
            else:
                b, gb, ub = self._at(p + 1)
                s = a * (self.den - rem) + b * rem
                w = (s + self.den // 2) // self.den if s >= 0 \
                    else -((-s + self.den // 2) // self.den)
                g = ga and gb
                u = ua or ub
            self.n_out += 1
            out_w.append(w)
            out_g.append(g)
            out_u.append(u)
            self._drop_before(p)
        return out_w, out_g, out_u


class AttysBulk(Adapter):
    """A recorded Attys session. 24 bit two channel frames in a .bin file with a .json meta.

    The frame at index i is six bytes, channel 0 in the first three and channel 1 in the
    next three, each signed 24 bit little endian. Only bits 23..8 are read.
    """

    MODE = "attys bulk"
    SOURCE = "recorded attys session"
    BLOCK_FRAMES = 1 << 20
    DEFAULT_CHUNK = 8192

    def __init__(self, session_path, channel=0):
        super().__init__()
        self.session_path = pathlib.Path(session_path)
        self.channel = int(channel)
        self.meta = None
        self._frames = None
        self._cursor = 0
        self._pending = deque()

    def open(self):
        meta_path = self.session_path.with_suffix(".json")
        self.meta = json.loads(meta_path.read_text())
        n = int(self.meta["frames"])
        raw = self.session_path.read_bytes()
        if len(raw) != n * ATTYS_FRAME_BYTES:
            raise ValueError("%s carries %d bytes but the meta declares %d frames of %d bytes"
                             % (self.session_path, len(raw), n, ATTYS_FRAME_BYTES))
        front = int(self.meta.get("front_end_counts", ATTYS_FRONT_END))
        if front != ATTYS_FRONT_END:
            raise ValueError("the session declares a front end ladder of %d counts per locked "
                             "count, the adapter knows %d" % (front, ATTYS_FRONT_END))
        self._frames = np.frombuffer(raw, dtype=np.uint8).reshape(n, ATTYS_FRAME_BYTES)
        self._words = block_words(self._frames, self.channel)
        # The gap table of the recorded session: the device lost n samples before frame i.
        # Every lost sample is emitted as a fill with the gap bit, so the monotone index
        # still counts the acquisition time and not only the delivered frames.
        self._gaps = {}
        for index, count in self.meta.get("gaps", []):
            self._gaps[int(index)] = int(count)
        self._cursor = 0
        self._pending = deque()
        return self.declare_rate(self.meta["rate_hz"])

    def _fill_gap(self, count):
        """The lost samples, as marked fills, and the uncertainty window that follows.

        The window is opened before the fills are emitted, so the fills themselves are part
        of it and both the recorded path and the live path mark the same range.
        """
        self.mark_recovery(max(GAP_RECOVERY, int(count)))
        for _ in range(int(count)):
            self._pending.append(self._emit(0, pre=None, gap=True, uncertain=True))

    def read(self):
        if self._pending:
            sample = self._pending.popleft()
            return sample
        if self._frames is None or self._cursor >= self._frames.shape[0]:
            return None
        count = self._gaps.pop(self._cursor, 0)
        if count:
            self._fill_gap(count)
            if self._pending:
                return self._pending.popleft()
        word = int(self._words[self._cursor])
        self._cursor += 1
        return self._emit(word, pre=None)

    def close(self):
        super().close()


class AttysStream(Adapter):
    """Attys over Bluetooth: callback blocks from pyattyscomm, device rate 125, 250 or
    500 Hz, resampled to the 250 Hz core rate, with packet gap marking.

    Two block sources feed the same per block path, so the resampler and the gap marking
    are identical in both and only the origin of the blocks differs:

      block_source  a callable returning (frames, n_lost) for the next block, or None at the
                    end. This is what the checker drives, from the synthetic frames.
      live_device   a pyattyscomm like object. The wiring below is written but NOT verified
                    on this machine: the package is not installed here and there is no
                    device, so the live radio path stays untested until Aviv runs it.
    """

    MODE = "attys stream"
    SOURCE = "attys bluetooth blocks"
    DEFAULT_CHUNK = 1

    def __init__(self, block_source=None, device_rate_hz=ATTYS_TARGET_HZ, live_device=None,
                 target_rate_hz=ATTYS_TARGET_HZ, channel=0, block_timeout=1.0):
        super().__init__()
        self.block_source = block_source
        self.device_rate_hz = int(device_rate_hz)
        self.live_device = live_device
        self.target_rate_hz = int(target_rate_hz)
        self.channel = int(channel)
        self.block_timeout = float(block_timeout)
        self.resampler = None
        self.live = False
        self.blocks = 0
        self.lost = 0
        self._live_queue = None
        self._pending = deque()
        self._recovery_at = None

    def open(self):
        if self.device_rate_hz not in ATTYS_DEVICE_HZ:
            raise ValueError("the device rate must be one of %s, %d was asked for"
                             % (list(ATTYS_DEVICE_HZ), self.device_rate_hz))
        self.resampler = LinearResampler(self.device_rate_hz, self.target_rate_hz)
        rate = self.declare_rate(self.target_rate_hz)
        self.declared["device_rate_hz"] = self.device_rate_hz
        self.declared["resampler"] = ("exact rational linear interpolation on the 16 bit word, "
                                      "weights 0, 1 of 2 and 1")
        if self.live_device is not None:
            self._attach_live(self.live_device)
        if self.block_source is None and not self.live:
            raise ValueError("no block source and no live device: the adapter would idle")
        return rate

    # ------------------------------------------------------------------ the live wiring
    def _attach_live(self, device):
        """Wire a pyattyscomm like device. Unverified: no library and no device here."""
        try:
            import pyattyscomm  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("the live Attys path needs pyattyscomm, which is not "
                               "available here (%s). Use a block source instead." % (exc,))
        self._live_queue = deque()
        device.setSampleRate(self.device_rate_hz)
        device.registerCallback(self._on_live_block)
        device.start()
        self.live = True

    def _on_live_block(self, payload):
        """Callback of the live device.

        Accepted payload shapes, expected but unverified here: a frame block of shape
        (n, 2), a tuple (block, n_lost), or a list of samples with a .data attribute. The
        block is pushed to the live queue and read() pulls it, so the live path shares the
        resampler and the gap marking with the simulated path.
        """
        n_lost = 0
        block = payload
        if isinstance(payload, tuple) and len(payload) == 2:
            block, n_lost = payload
        if isinstance(block, list) and block and hasattr(block[0], "data"):
            block = np.array([s.data for s in block], dtype=np.int64)
        self._live_queue.append((np.asarray(block), int(n_lost)))

    # ------------------------------------------------------------------ the one block path
    def _next_block(self):
        """The next (frames, n_lost) block, from the live queue or from the block source."""
        if self.live:
            end = time.time() + self.block_timeout
            while not self._live_queue:
                if time.time() > end:
                    return None
                time.sleep(0.001)
            return self._live_queue.popleft()
        if self.block_source is None:
            return None
        block = self.block_source()
        if block is None:
            return None
        return block

    def _pull(self, finish=False):
        """Fill the pending queue with resampled output samples."""
        while not self._pending:
            got = self._next_block()
            if got is None:
                finish = True
            else:
                frames, n_lost = got
                n_lost = int(n_lost)
                block = block_words(frames, self.channel)
                self.blocks += 1
                self.lost += n_lost
                words, gap, unc = [], [], []
                # A packet gap means n_lost samples never arrived. They are filled with zero
                # and marked, so the monotone index keeps counting the acquisition time and
                # the corrupted stretch is marked uncertain, never smoothed over.
                for _ in range(n_lost):
                    words.append(0)
                    gap.append(True)
                    unc.append(True)
                for word in block:
                    words.append(int(word))
                    gap.append(False)
                    unc.append(False)
                if n_lost:
                    self._recovery_at = self.resampler.n_out
                self.resampler.push(words, gap, unc)
            out_w, out_g, out_u = self.resampler.drain(finish=finish)
            start = self.resampler.n_out - len(out_w)
            for k in range(len(out_w)):
                uncertain = out_u[k]
                if self._recovery_at is not None \
                        and start + k < self._recovery_at + GAP_RECOVERY:
                    uncertain = True
                self._pending.append(self._emit(out_w[k], pre=None, gap=out_g[k],
                                                uncertain=uncertain))
            if finish and not self._pending:
                return

    def read(self):
        if not self._pending:
            self._pull()
        if not self._pending:
            return None
        return self._pending.popleft()


def open_adapter(kind, **kwargs):
    """Convenience factory. The four kinds, one interface."""
    kinds = {"dataset_bulk": DatasetBulk, "dataset_stream": DatasetStream,
             "attys_bulk": AttysBulk, "attys_stream": AttysStream}
    if kind not in kinds:
        raise ValueError("unknown adapter %r, the four kinds are %s"
                         % (kind, sorted(kinds)))
    adapter = kinds[kind](**kwargs)
    adapter.open()
    return adapter
