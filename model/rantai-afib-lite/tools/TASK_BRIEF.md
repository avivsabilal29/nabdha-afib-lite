# TASK_BRIEF for `model/rantai-afib-lite/`

This folder holds the end to end chain of AFIB-LITE (phase 6). The chain unifies the locked
mathematics that was validated in the seven phase notebooks with the acquisition paths. The design is
written in the vault document `end-to-end-validation-design.md`, and the locked product decisions are
in `34 - Spesifikasi Produk Terkunci, Rencana Fase, dan Perubahan Breakdown.md`.

## Source of truth

The seven notebooks in `model/math-equation-afib/` are the only source of truth for the arithmetic.
They are labelled in the order the chain applies them.

- `00 - low-pass-filter-equation.ipynb`
- `01 - high-pass-filter-equation.ipynb`
- `02 - five-point-derivative-equation.ipynb`
- `03 - squaring-and-moving-window-integrator-equation.ipynb`
- `04 - adaptive-threshold-equations.ipynb`
- `05 - rr-interval-averaging-equations.ipynb`
- `06 - t-wave-discrimination.ipynb`

`07 - end-to-end-chain.ipynb` is not a stage notebook. It runs the chain in this folder and the
frozen gates and reports the numbers each gate printed.

The labels were added after the notebooks were frozen, so the arithmetic and the saved outputs are
untouched. A mention of an unlabelled name inside a frozen notebook or a frozen note resolves to the
labelled file with the same stem, for example `low-pass-filter-equation.ipynb` is now
`00 - low-pass-filter-equation.ipynb`.

## Two layers and the notebook

The model has two layers. The phase notebooks in `model/math-equation-afib/` fix the arithmetic of
one stage each, and `model/rantai-afib-lite/` holds the frozen end to end chain that unifies them
with the acquisition paths. `model/math-equation-afib/07 - end-to-end-chain.ipynb` runs that chain
and runs the six frozen gate scripts (`uji_00_teorema.py`, `uji_02_adapter.py`, `uji_03_ekivalensi.py`,
`uji_05_kebijakan_ambang.py`, `uji_06_referensi.py`, `uji_07_jeda_rr.py`) over the chain modules
`rantai.py` and `adapter.py`, reporting the numbers each gate printed; its saved gate output lives beside it in `model/math-equation-afib/gate-cache/`, which is a
speed cache only and is ignored by git: the notebook runs any gate whose saved text is missing or
whose script hash moved, and writes the text back itself, so deleting that directory breaks
nothing. The chain folder is frozen: read it and run it, and change it only through a measured step.

Two rules follow from this.

1. The notebooks are never edited. Nothing in this folder may change the arithmetic of a stage.
2. Every function that has a counterpart in a notebook must behave identically to that notebook, bit
   for bit, on the frozen fixture. When a vectorized notebook function and a streaming function
   disagree by one count, the streaming function is wrong.

## Locked constants of the chain

| Name | Value | Note |
|---|---|---|
| `FS` | 250.0 | locked sample rate, Hz |
| `GAIN_COUNT` | `(2**11 - 1) / 5.0` | counts per millivolt, plus minus 5 mV over 12 bit |
| `CLAMP` | 2047 | input clamp |
| `GESER_KIRI` | 4 | input word is shifted left by four bits |
| `N_A`, `N_B` | 37, 38 | alternating integration window, mean 37.5 samples |
| `PANTUL` | 50 | refractory gate, 200 millisecond |
| `PITA_MS` | (200.0, 360.0) | band where the T wave rule is meaningful |
| `DELAPAN` | 8 | length of the RR averaging window |
| `SEMAI_PANJANG` | 32 | history length for the RR reseeding median |
| `SEMAI_JEDA` | 8 | reseeding is allowed once per eight beats |
| `LEBAR_JENDELA_KEMIRINGAN` | 37 | slope window width, half window 18 |
| `BATAS_KEBERLAKUAN_MV` | 0.90 | limit of validity of the T wave rule, in millivolt |

## Stage order, lock order

The input is quantized first, then the eight stages run in this order.

| Order | Function | Locked behaviour |
|---|---|---|
| 0 | `kuantisasi` | clip to plus minus 2047, shift left four bits |
| 1 | `tapis_lp` | low pass, DC gain 36, zero at multiples of the sample rate divided by six |
| 2 | `tapis_hp` | high pass, single pole at z equal to minus one, DC gain alternating 16 and 0 |
| 3 | `turunan` | five point derivative, exact zero DC gain, group delay two samples, divided by eight |
| 4 | `kuadrat` | square, never negative, 32 bit is enough |
| 5 | `jendela` | moving window integration, alternating width 37 and 38, circular buffer |
| 6 | `ambang` | adaptive threshold, difference form, right shift downward, half cut, warm up from zero |
| 7 | `rr` | RR intervals, eight interval queue, exact band 23/25 to 29/25 of the second average, plus the P4-5 reseeding rule |
| 8 | `gelombang_t` | T wave rule, slope from the five point derivative output, cross form two times the slope smaller than the previous slope, slope window 37 samples |

The window decision layer then uses four features per window, namely RMSSD, RMSSD divided by the mean
RR, pNN50, and normalized entropy.

## Integer rules of the core

1. The core is integer only. No floating point division and no floating point arithmetic inside a
   stage.
2. No hard multipliers. A multiplier is allowed only when it is a power of two, which in hardware is a
   shift, together with additions and subtractions. Division by eight, by four, and by two is a right
   shift of an integer.
3. Division of integers rounds toward negative infinity, exactly as Python does with `//`. The
   derivative divides sign symmetrically, as the notebook does.
4. Every stage function returns its output together with the measured range of that output, so that
   the bit width check runs automatically instead of by hand.
5. The input conversion `kuantisasi` is the only place where the floating point form appears, because
   the notebook itself does it in floating point. It must reproduce the notebook count for count.

## The state machine

`rantai.py` holds one state object and one streaming entry point.

```
class Rantai:
    def __init__(self, semai_aktif=True, aturan_t=True, besaran="turunan"): ...
    def langkah(self, nilai): ...   # one sample in, one record of that sample out
```

Bulk is not a second mode. Bulk is streaming driven to completion. An adapter that reads a whole file
calls `langkah` in large chunks, an adapter that replays a file calls it once per sample, and the
results are identical by construction. The chain never sees a bit width, a sample rate, or the origin
of the data. It receives time, value, and quality marker per sample, and the adapters own every format
detail.

## Files of this folder

| File | Content |
|---|---|
| `rantai.py` | the locked core, one state class, every stage as a function with its measured range |
| `adapter.py` | `DatasetBulk`, `DatasetStream`, `AttysBulk`, `AttysStream` over one interface |
| `simulator_attys.py` | synthetic 24 bit two channel frames derived from a dataset recording |
| `uji_00_teorema.py` | validation level 1, one closed form theorem per stage |
| `uji_03_ekivalensi.py` | validation level 2, equality across the four adapters plus a repeatability fingerprint |
| `uji_06_referensi.py` | validation level 3, sensitivity and specificity against rhythm annotation, plus the budget |
| `fixture/` | the frozen reference arrays and their SHA-256 fingerprints |
| `s0_bekukan_acuan.py` | the script that freezes the reference |
| `acuan_fase.py` | verbatim extraction of the notebook functions, generated, never edited by hand |
| `README.md`, `TASK_BRIEF.md` | general rules and this task material |

## Rename map, the reading order of the test files

The twelve test files were relabelled so that a directory listing reads in the order the gates run.
The label sits after the `uji_` prefix, because a Python module name may not begin with a digit, so
the pattern is `uji_NN_nama.py`. Only the file names and the references to them changed. No test
file changed beyond its import lines and its references to the renamed files, and no frozen array
changed. `rantai.py` keeps its name because it is imported by that name everywhere.

| former name | current name |
|---|---|
| `uji_teorema.py` | `uji_00_teorema.py` |
| `uji_kesetaraan_s1.py` | `uji_01_kesetaraan_s1.py` |
| `uji_adapter.py` | `uji_02_adapter.py` |
| `uji_ekivalensi.py` | `uji_03_ekivalensi.py` |
| `uji_ambang_pool.py` | `uji_04_ambang_pool.py` |
| `uji_kebijakan_ambang.py` | `uji_05_kebijakan_ambang.py` |
| `uji_referensi.py` | `uji_06_referensi.py` |
| `uji_jeda_rr.py` | `uji_07_jeda_rr.py` |
| `uji_sumber_jendela.py` | `uji_08_sumber_jendela.py` |
| `uji_deret_terkoreksi.py` | `uji_09_deret_terkoreksi.py` |
| `uji_berpenanda.py` | `uji_10_berpenanda.py` |
| `uji_hampir_meleset.py` | `uji_11_hampir_meleset.py` |

A document or a frozen file that still names a test file by its former name resolves through the
table above, so no mention is lost. The frozen files of this folder (`rantai.py`, `adapter.py`,
`acuan_fase.py`, `simulator_attys.py`, `ambang_gerbang.py`, `periksa_verbatim.py`,
`s0_bekukan_acuan.py`) and the historical note `S7_OPEN_CORRECTION_NOTE.md` were not edited, so any
former name printed inside them is resolved by the same table.

The relabel moved one recorded fingerprint. `S7_OPEN_CORRECTION_NOTE.md` records
`uji_jeda_rr.py` as `b5f25fa2` and that value describes the file as it was before the relabel; the
file is now `uji_07_jeda_rr.py` with sha256 `60bb1b45b763ffb9`, the same content with its references and its
usage line updated.

## Gates

| Step | Gate |
|---|---|
| S0 | every frozen array matches the phase notebook outputs, and the fingerprints repeat on a second run |
| S1 | zero bit difference against the fixture on all 450,000 samples, for every stage array |

A failed gate stops the next step. It is not carried forward.

## Bans that apply everywhere

1. Nothing is committed by the assistant. Commit belongs to Aviv.
2. Sources inside this repository are in English. Vault documents are in Indonesian.
3. Every number comes from a real run. Anything not yet measured is written as a prediction.
4. The phrase window classification is used, never beat detection accuracy, because AFDB carries
   rhythm annotation and not beat annotation.
5. The limit of validity of the T wave rule, 0.90 millivolt, is reported in the final output.
6. No em dash and no en dash in any file.
