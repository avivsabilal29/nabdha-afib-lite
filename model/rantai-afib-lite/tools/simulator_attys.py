#!/usr/bin/env python3
"""AFIB-LITE phase 6 step S2: a synthetic Attys block and session generator.

The direct Attys path cannot be tested without a device, so this module builds the frames
that a device would have delivered, out of a real recording. What is real and what is
synthetic, stated plainly:

  real       the AFDB recording 04015, its two channels, its 12 bit counts, and the locked
             16 bit words derived from them by rantai.kuantisasi
  synthetic  the 24 bit frame layout, the front end gain ladder, the noise in the eight
             bottom bits, the session block boundaries, the rate variants, and the packet
             gap table

Frame layout, six bytes per frame, two channels of three little endian bytes each:

    bits 23..8   the locked 16 bit word, so bits 23..12 hold the locked 12 bit count
    bits 11..0   the bottom of the front end ladder plus eight bits of front end noise

The front end ladder is 4096 counts24 per locked count12, that is 2 to the power of 12.
It is a chosen assumption, not a measured device property: it is chosen so that the scale
alignment between the Attys front end and the locked domain is an exact shift, which is
what lets the Attys paths be compared with the dataset path for exact equality instead of
approximately. Bits 7..0 of every frame are uniform noise, which is why the adapters read
only the top 16 bits.

Run it with the project interpreter to rebuild every session into the fixture folder:

    cd /home/avivsabilalm/hackathon-semiconductor-programs/nabdha-afib-lite
    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/simulator_attys.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import adapter as A

DEFAULT_RECORD = pathlib.Path("/home/avivsabilalm/.hermes/cache/scratch/afib/afdb_local/04015")
DEFAULT_FRAMES = 450_000
DEFAULT_SEED = 20261019
BLOCK_FRAMES = 64  # the block size a Bluetooth callback delivers in the simulation
GAP_TABLE = ((1000, 3), (50_000, 1), (200_000, 7), (350_000, 2))  # frame index, samples lost
RATE_VARIANTS = (125, 500)  # the other two declared device rates, 250 comes straight from the record


def locked_words(record_path, n_frames=DEFAULT_FRAMES, channel=0):
    """The locked 16 bit word of every frame of one channel of a recording.

    The words are the real part of this module: they are the same words the dataset
    adapters emit, computed by rantai.kuantisasi, the locked convention.
    """
    source = A.RecordSource(record_path, n_frames, channel, block_frames=1 << 30)
    source.open()
    counts = source.read_counts(source.n_frames)
    words = np.empty(counts.size, dtype=np.int64)
    for i in range(counts.size):
        word, _pre = A.locked_word(int(counts[i]), source.gain, source.zero)
        words[i] = word
    source.close()
    return words


def pack_frames(words, seed=DEFAULT_SEED):
    """Two channels of locked words to 24 bit frames with front end noise.

    Channel 0 and channel 1 are packed from the words of the same frame index. The bottom
    eight bits of every channel are uniform noise, so reading only the top 16 bits discards
    nothing but noise.
    """
    words = np.asarray(words, dtype=np.int64)
    if words.ndim == 1:
        words = words[:, None]
    n, n_ch = words.shape
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, 256, size=(n, n_ch), dtype=np.int64)
    value24 = (words << A.ATTYS_WORD_SHIFT) | noise
    frames = np.empty((n, n_ch * 3), dtype=np.uint8)
    for c in range(n_ch):
        v = value24[:, c] & 0xFFFFFF
        frames[:, 3 * c] = (v & 0xFF).astype(np.uint8)
        frames[:, 3 * c + 1] = ((v >> 8) & 0xFF).astype(np.uint8)
        frames[:, 3 * c + 2] = ((v >> 16) & 0xFF).astype(np.uint8)
    return frames


def rate_variant(words, rate_hz, base_rate_hz=A.ATTYS_TARGET_HZ):
    """A session at another declared device rate, from the 250 Hz words.

    These conversions are synthetic and they are the weak point of the rate tests, so they
    are built by a method that is independent of the adapter resampler:

      125 Hz   decimation, every second sample, phase zero. This is what a device sampling
               at 125 Hz would have measured if the analog front end band limited the signal.
      500 Hz   linear interpolation onto a grid of twice the density, through numpy, not
               through the adapter resampler.
    """
    words = np.asarray(words, dtype=np.int64)
    if words.ndim == 1:
        return rate_variant(words[:, None], rate_hz, base_rate_hz)[:, 0]
    if rate_hz == base_rate_hz:
        return words.copy()
    if rate_hz * 2 == base_rate_hz:
        return words[0::2].copy()
    if rate_hz == base_rate_hz * 2:
        dense = np.arange(0, words.shape[0], 0.5)
        grid = np.arange(words.shape[0])
        out = np.empty((dense.size, words.shape[1]), dtype=np.int64)
        for c in range(words.shape[1]):
            out[:, c] = np.rint(np.interp(dense, grid, words[:, c].astype(float)))
        return out
    raise ValueError("no synthetic rate conversion from %d Hz to %d Hz"
                     % (base_rate_hz, rate_hz))


def write_session(bin_path, frames, rate_hz, meta_extra=None):
    """Write one session: the frames as raw bytes, and the meta as a json sidecar."""
    bin_path = pathlib.Path(bin_path)
    raw = np.asarray(frames, dtype=np.uint8).tobytes()
    bin_path.write_bytes(raw)
    meta = {
        "format": "attys 24 bit two channel frames, channel 0 first, little endian",
        "rate_hz": int(rate_hz),
        "channels": A.ATTYS_CHANNELS,
        "frame_bytes": A.ATTYS_FRAME_BYTES,
        "frames": int(np.asarray(frames).shape[0]),
        "front_end_counts": A.ATTYS_FRONT_END,
        "bottom_bits": "8 bits of uniform noise, not ECG",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    if meta_extra:
        meta.update(meta_extra)
    bin_path.with_suffix(".json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    return meta


class BlockFeeder:
    """The block source of AttysStream, standing in for the pyattyscomm callback.

    Every call returns (frames, n_lost) or None at the end. n_lost is the number of samples
    the device reports as lost before this block, which on a real device comes from the
    block sequence of the library and on this machine comes from the table below.
    """

    def __init__(self, frames, block_frames=BLOCK_FRAMES, gap_table=(), shift=0):
        self.frames = np.asarray(frames, dtype=np.uint8)
        self.block_frames = int(block_frames)
        self.gaps = {int(i): int(n) for i, n in gap_table}
        self.shift = int(shift)
        self.pos = 0
        self.blocks = 0

    def __call__(self):
        if self.pos >= self.frames.shape[0]:
            return None
        block = self.frames[self.pos:self.pos + self.block_frames]
        n_lost = self.gaps.get(self.blocks + self.shift, 0)
        self.pos += block.shape[0]
        self.blocks += 1
        return block, n_lost

    @property
    def total(self):
        return self.frames.shape[0]


def session_path(out_dir, record_name, rate_hz, tag=""):
    """One session file name: attys_<record>_<rate>hz<tag>.bin"""
    stem = "attys_%s_%dhz%s" % (record_name, int(rate_hz), tag)
    return pathlib.Path(out_dir) / (stem + ".bin")


def build(record_path=DEFAULT_RECORD, out_dir=None, n_frames=DEFAULT_FRAMES,
          seed=DEFAULT_SEED, verbose=True):
    """Build every session and return {name: (path, meta)}."""
    record_path = pathlib.Path(record_path)
    out_dir = pathlib.Path(out_dir) if out_dir is not None else HERE / "fixture" / "attys"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = record_path.name

    ch0 = locked_words(record_path, n_frames, 0)
    ch1 = locked_words(record_path, n_frames, 1)
    words = np.stack([ch0, ch1], axis=1)
    frames = pack_frames(words, seed=seed)

    out = {}
    common = {"source_record": str(record_path), "seed": int(seed),
              "synthetic": "frames, ladder, noise, block boundaries, rate variants, gap table",
              "real": "the recording and its locked 16 bit words"}
    base = session_path(out_dir, name, A.ATTYS_TARGET_HZ)
    meta = write_session(base, frames, A.ATTYS_TARGET_HZ, common)
    out["continuous"] = (base, meta)

    gap_meta = dict(common)
    gap_meta["gaps"] = [[i, n] for i, n in GAP_TABLE]
    gap_meta["gaps_note"] = ("frame index, samples lost before that frame, from the block "
                             "sequence of the simulated callback")
    gbase = session_path(out_dir, name, A.ATTYS_TARGET_HZ, "_gaps")
    gmeta = write_session(gbase, frames, A.ATTYS_TARGET_HZ, gap_meta)
    out["gaps"] = (gbase, gmeta)

    for rate in RATE_VARIANTS:
        vw = rate_variant(words, rate)
        vf = pack_frames(vw, seed=seed + rate)
        extra = dict(common)
        extra["rate_variant"] = ("synthetic conversion from %d Hz, see rate_variant()"
                                 % (A.ATTYS_TARGET_HZ,))
        p = session_path(out_dir, name, rate)
        m = write_session(p, vf, rate, extra)
        out["rate_%d" % rate] = (p, m)

    if verbose:
        print("simulator attys, sessions written to", out_dir)
        for key, (path, m) in sorted(out.items()):
            print("  %-12s %-46s %9d frames %9d bytes rate %3d Hz sha256 %s"
                  % (key, path.name, m["frames"], path.stat().st_size, m["rate_hz"],
                     m["sha256"][:12]))
        print("  real      : the recording %s and its locked 16 bit words" % (record_path,))
        print("  synthetic : the 24 bit frame layout, the front end ladder, the eight noise "
              "bits, the block boundaries, the rate variants and the gap table")
    return out


def main(argv):
    out_dir = pathlib.Path(argv[1]) if len(argv) > 1 else None
    n = int(argv[2]) if len(argv) > 2 else DEFAULT_FRAMES
    build(out_dir=out_dir, n_frames=n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
