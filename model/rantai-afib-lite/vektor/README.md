# `vektor/04015_berpenanda.npz` ,  frozen vectors of the active window arm

This directory is the comparator a testbench needs for the **active** interval source of the
window feature layer, `SUMBER_BERPENANDA`. The frozen fixture `fixture/04015_30m.npz` does not
carry that arm: it stores `jendela_fitur` (588, 4) for the raw arm and `jendela_fitur_acuan`
(590, 4) for the NeuroKit reference arm, and no array at all for the marked-source arm. This file
fills that hole and nothing else.

**This file is NOT a replacement for the frozen fixture.** It is an addition. `fixture/` is read
only, was not touched, and stays the oracle of the raw and reference arms. Where the two files
overlap (`masukan16`, `jendela`, `puncak`, `qrs`, `rr`) this file carries a verbatim copy of the
frozen arrays, so a testbench can drive the DUT from one file; the copy was checked element for
element against the fixture at write time (see *Round trip* below).

## File facts

| item | value |
|---|---|
| path | `model/rantai-afib-lite/vektor/04015_berpenanda.npz` |
| sha256 | `162f2c4ff49d4336f234187e50883cfba46fa55a6b2f32620188144658b902d7` |
| size | 2406321 bytes |
| record | AFDB 04015, first 450000 frames = 30 min at 250 Hz |
| source of the features | `rantai.kumpulkan_jendela(qrs, lab, sumber=SUMBER_BERPENANDA)` |
| windows kept | 602 (AFIB 95, N 507); raw arm 588, reference arm 590 |

## Arrays

Every integer quantity is stored as `int64`; the feature matrix keeps the float64 the frozen
layer produces, because it is float64 in origin (only its column 2, pNN50, and column 3, entropy /
4, are drawn from integer arithmetic).

| key | shape | dtype | meaning |
|---|---|---|---|
| `masukan16` | (450000,) | int64 | the locked 16 bit input word of the fixture, verbatim |
| `jendela` | (450000,) | int64 | the envelope (moving window integration) of the fixture, verbatim |
| `puncak` | (4777,) | int64 | the peak candidates of the frozen chain, verbatim |
| `qrs` | (2596,) | int64 | the accepted beats of the frozen chain, verbatim |
| `rr` | (2595,) | int64 | the raw RR interval series in ms, verbatim |
| `penanda` | (2595,) | int64 | the stage 7b mark of every raw interval, from `rantai.tanda_deret(rr)`, the series the marked arm reads |
| `sumber_interval` | (2583,) | int64 | index of the raw interval every surviving entry of the marked series came from, from `rantai.seri_berpenanda` |
| `rr_berpenanda` | (2583,) | int64 | the marked interval series in ms, `rr[sumber_interval]` |
| `jendela_awal` | (602,) | int64 | index into `rr_berpenanda` of the first interval of every kept window |
| `jendela_fitur_berpenanda` | (602, 4) | float64 | the four window features: RMSSD, RMSSD / mean RR, pNN50, entropy / 4 |
| `jendela_kelas_berpenanda` | (602,) | `<U6` | the class of every kept window, `AFIB` or `N` |
| `sidik_rantai` | (1,) | `<U72` | sha256 of the `rantai.py` that produced the arrays |
| `sidik_fixture` | (1,) | `<U72` | sha256 of the fixture the arrays came from |
| `sumber` | (1,) | `<U16` | the source switch used, `berpenanda` |

### How the marked arm is built, and why `penanda` means the stage 7b marks here

Under `SUMBER_BERPENANDA` the window layer does not read `rr` directly. It reads the stage 7b
mark of every raw interval and keeps an interval unless its mark is DROP (2) or GAP (3); a SPLIT
(1) interval is kept whole, because the missed beat rule is inert. On this fixture the marks are
`0:2186 1:397 2:9 3:3`, so 2595 raw intervals become a 2583 entry series and 12 intervals leave.

**Naming warning.** The fixture's own key `penanda` is a different array: it is `baris[:, 3]` of
the RR trace, shape (2579,), not the mark series. The `penanda` in this file is the mark series,
shape (2595,), one entry per raw interval, which is what `kumpulkan_jendela` consumes. Do not
swap the two.

## How the arrays were produced

The frozen model and the frozen fixture, read only:

```
model/rantai-afib-lite/rantai.py                 sha256 90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5
model/rantai-afib-lite/fixture/04015_30m.npz     sha256 91ff408fb1b7880a124d28bcc4205038935d4a3a2dbabb4c0f7d161d89e8ac4d
dataset/afdb/04015.atr                           sha256 ea11d47f1a52422939eadb46c544b1ae42c2111afbe1fd14afd43f4469fa2c8d
interpreter                                      /home/avivsabilalm/.venvs/afib-lite/bin/python (numpy 2.4.6, wfdb 4.3.1, python 3.11.15)
```

The rhythm labels come from the annotation through the frozen `label_irama`, exactly as the chain
does it. Nothing in the repo was edited; only this directory was written.

The whole recipe, runnable from the repository root:

```python
import hashlib, pathlib, sys
import numpy as np
sys.path.insert(0, "model/rantai-afib-lite")
import rantai as R
import wfdb

FRAMES = 450_000
d = np.load("model/rantai-afib-lite/fixture/04015_30m.npz")
qrs = np.asarray(d["qrs"], dtype=np.int64)
an = wfdb.rdann("dataset/afdb/04015", "atr")
lab = R.label_irama(an.sample, an.aux_note, FRAMES)          # the frozen label builder

rr_ms = np.diff(qrs) / R.FS_HZ * 1000.0
tanda = R.tanda_deret(rr_ms)                                  # the stage 7b marks
rr_berpenanda, sumber_interval = R.seri_berpenanda(rr_ms, tanda)

fitur, kelas = R.kumpulkan_jendela(qrs, lab, sumber=R.SUMBER_BERPENANDA, mark=tanda)

bl = lab[qrs[1:]][sumber_interval]
awal = [i for i in range(0, rr_berpenanda.size - R.JENDELA_DENYUT, R.LANGKAH_DENYUT)
        if np.unique(bl[i:i + R.JENDELA_DENYUT]).size == 1
        and np.unique(bl[i:i + R.JENDELA_DENYUT])[0] in ("AFIB", "N")
        and rr_berpenanda[i:i + R.JENDELA_DENYUT].min() >= 200
        and rr_berpenanda[i:i + R.JENDELA_DENYUT].max() <= 3000]
assert len(awal) == fitur.shape[0]                            # 602

np.savez_compressed(
    "model/rantai-afib-lite/vektor/04015_berpenanda.npz",
    masukan16=np.asarray(d["masukan16"], dtype=np.int64),
    jendela=np.asarray(d["jendela"], dtype=np.int64),
    puncak=np.asarray(d["puncak"], dtype=np.int64),
    qrs=qrs,
    rr=np.asarray(d["rr"], dtype=np.int64),
    penanda=tanda,
    sumber_interval=sumber_interval,
    rr_berpenanda=np.rint(rr_berpenanda).astype(np.int64),
    jendela_awal=np.asarray(awal, dtype=np.int64),
    jendela_fitur_berpenanda=fitur,
    jendela_kelas_berpenanda=np.array([str(x) for x in kelas], dtype="U6"),
    sidik_rantai=np.array(["90df6e5b457307d37158a96b6dbedb4e72be03f35349769a858918f6314f1fe5"], dtype="U72"),
    sidik_fixture=np.array(["91ff408fb1b7880a124d28bcc4205038935d4a3a2dbabb4c0f7d161d89e8ac4d"], dtype="U72"),
    sumber=np.array(["berpenanda"], dtype="U16"),
)
```

The generating script of this session was `/home/avivsabilalm/.hermes/cache/scratch/rtlplan/vektor_tulis.py`
(scratch, not part of the repo). Its raw output, kept with the session, is
`/home/avivsabilalm/.hermes/cache/scratch/rtlplan/vektor_tulis.out.txt`.

The snippet above was run with only the output path redirected to scratch
(`/home/avivsabilalm/.hermes/cache/scratch/rtlplan/resep_ulang.py`), and the file it wrote compares
equal, element for element, with this directory's file for all 14 keys. So the recipe is the one
that produced the arrays. The recorded sha256 is the digest of the container as written at that
time; a re-run regenerates the same arrays, but the zip container carries an entry timestamp, so
compare arrays and not the container digest when checking a regeneration.

## Round trip

Read back from the written file and compared against the frozen functions and the frozen fixture,
element for element: `masukan16` True, `jendela` True, `puncak` True, `qrs` True, `rr` True,
`jendela_fitur_berpenanda` against `R.kumpulkan_jendela(...)` True, `jendela_kelas_berpenanda`
against its class array True. The same call without the `mark` argument, so with the marks
restated inside the layer by `tanda_deret`, returns the identical features and classes; the write
was aborted by an assertion if it had not.

## The four features of the marked arm

| column | feature | range over the 602 windows |
|---|---|---|
| 0 | RMSSD in ms | 8.500474370065 .. 457.347189357170 |
| 1 | RMSSD / mean RR | 0.011206953685 .. 0.611414653804 |
| 2 | pNN50 | 0 .. 0.935483870968 |
| 3 | entropy / 4 | 0 .. 0.875 |

Widths, ranges and the proposed fixed point binary points of every node of this arm, next to the
raw arm and the reference layer, are in
`/home/avivsabilalm/.hermes/cache/scratch/rtlplan/H3-berpenanda-acuan.md`.
