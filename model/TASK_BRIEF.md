# Task brief: reference model

**Deliverable:** Jupyter notebooks plus exported golden vectors, in this folder.
**Why it comes first:** the RTL owner cannot check anything against numbers that do not exist yet.

## Goal

Write a Python reference model that reproduces the mathematics of AFIB-LITE as described in the
teaching note, note 31, _Memahami AFIB-LITE_, in the project vault. The model takes an ECG sample
stream and returns the same information the RTL will produce: the R peak positions, the RR series,
the four features, the triage class, and the confidence value.

The model is the measured truth. When it disagrees with the RTL, we trust the model and fix the RTL,
unless we can show the model is wrong.

Acceptance in one sentence: for any input we feed it, the model's output equals the arithmetic of the
formulas in note 31, and the exported vectors let the RTL prove the same thing in hardware.

## 1. The pipeline, stage by stage

Build these stages in order. Each row names the section of note 31 that defines the maths.

| Stage                  | What it does                                                                                             | Acceptance check                                                                 |
| ---------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| 1. Bandpass            | keeps 5 to 15 Hz, removes baseline wander and mains hum                                                  | a 50 Hz sine in, a quiet output out; QRS survives                                |
| 2. Derivative          | five-point difference, coefficients `2, 1, 0, -1, -2` divided by 8                                       | peaks line up with QRS slopes, group delay of 2 samples recorded                 |
| 3. Squaring            | squares the derivative sample by sample                                                                  | output never negative, no overflow in the fixed-point path                       |
| 4. Moving window       | running average over 150 ms                                                                              | at 250 Hz the window is 37.5 samples, so alternate 37 and 38                     |
| 5. Peak detection      | adaptive thresholds `SPKI`, `NPKI`, `T1`, `T2`, 200 ms refractory, search-back at 1.66 times the mean RR | one peak per beat, no double counts, T wave rejected                             |
| 6. RR series           | distance between consecutive peaks in sample counts                                                      | RR in samples, never in wall-clock time                                          |
| 7. Features            | RMSSD, RMSSD divided by mean RR, pNN50, normalised Shannon entropy                                       | values match hand-computed numbers on a short synthetic series                   |
| 8. Classifier          | two thresholds, AND logic, three classes                                                                 | AF, normal, or undecided; thresholds are constructor parameters                  |
| 9. Confidence          | `c = min over features of abs(f - threshold) / sigma`                                                    | `c` reads in standard deviations, printed next to the class                      |
| 10. Fixed-point mirror | the same pipeline in the integer formats the RTL uses                                                    | per-stage difference against the float path below 1 percent of that stage's peak |

Stage 7 details that break a model when they are wrong:

- RMSSD divides the root mean square of successive RR differences by the mean RR before any threshold
  sees it. In our own run on AFDB, absolute RMSSD scored AUC 0.634 while the normalised version scored
  0.770.
- Entropy measures the spread of the RR histogram, not the sample entropy of the series. Use 16
  equal-width bins over the range that remains after dropping the 8 longest and 8 shortest values, then
  divide by `log2(16)` so the output sits between 0 and 1.

## 2. Object-oriented structure

Compose the model from small objects that each own one stage. No global state, no printing inside a
stage, and no stage that reaches into another stage's internals.

| Class                                                               | Responsibility                                                                           | Main method                                 |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------- |
| `SampleSource`                                                      | abstract input                                                                           | `read(n_samples) -> Samples`                |
| `FileSource`                                                        | WFDB, CSV, or `.npy` input                                                               | same interface                              |
| `ArraySource`                                                       | array already in memory                                                                  | same interface                              |
| `StreamSource`                                                      | chunked input that mimics the programmable logic, including gap flags and window markers | same interface                              |
| `BandpassFilter`, `Derivative`, `Squarer`, `MovingWindowIntegrator` | one arithmetic stage each                                                                | `process(x) -> y`                           |
| `PeakDetector`                                                      | adaptive thresholds and refractory logic                                                 | `process(envelope) -> peak_indices`         |
| `RRExtractor`                                                       | RR series in sample counts                                                               | `process(peak_indices) -> rr_ms_or_samples` |
| `FeatureExtractor`                                                  | the four features over a rolling window                                                  | `process(rr) -> Features`                   |
| `TriageClassifier`                                                  | thresholds, AND logic, confidence                                                        | `process(features) -> Decision`             |
| `FixedPointQuantiser`                                               | format conversion for the integer mirror                                                 | `quantise(x) -> int`                        |
| `Pipeline`                                                          | wires the stages, runs file or stream input                                              | `run()` and `step()`                        |

Rules for every public method:

- One job per function. If the docstring needs the word "and" to describe it, split the function.
- The docstring states what it computes, which section of note 31 defines it, the units and dtype of
  every argument, the units and dtype of the return value, and the check that proves it works.
- Parameters live in the constructor, not in magic numbers inside the body.
- Name things after the signal, not after the code: `envelope`, `peak_indices`, `rr_samples`.

## 3. Input flexibility

The same pipeline must accept three kinds of input without code changes in the stages.

1. **File**: an AFDB record, a CSV, or a `.npy` array.
2. **Raw array**: samples already in memory, useful for unit checks.
3. **Stream**: chunks that arrive over time, which is how the board delivers samples.

Fix one sample format across all three: `int16`, 12 significant bits left justified, 250 Hz nominal,
plus a `gap` flag and a window marker. The stream source simulates dropped samples and stalls, because
the RTL gap detector needs something to detect. Reading a file in chunks is not optional: the same code
path has to serve replay and a live feed.

Acceptance: `Pipeline(source=FileSource(...))`, `Pipeline(source=ArraySource(...))`, and
`Pipeline(source=StreamSource(...))` all run, and produce identical features for identical data.

## 4. Measurable output

A notebook, `export_vectors.ipynb`, writes the golden vectors for one record:

```
model/vectors/<record>/
|-- stage_01_bandpass.npz
|-- stage_02_derivative.npz
|-- ...
|-- decisions.npz
`-- manifest.json
```

The manifest records the record name, the sample rate, the word format, each fixed-point scale, the
model version or commit, and the command that produced the files. Without the manifest the vectors
are useless three days later, so treat it as part of the deliverable.

Two more notebooks complete the folder:

- `validate.ipynb` prints, per stage, the largest absolute difference between the float path and the
  fixed-point path as a percentage of that stage's peak; the R peak count against the AFDB
  annotation; and the features per window with their labels.
- `calibrate.ipynb` sweeps the two thresholds over a grid, reports sensitivity, specificity, accuracy,
  and the share of windows that land in the undecided class, and picks the operating point the team
  will use. Tune on some records, test on others, and say which is which in the notebook.

## 5. Definition of done

- [ ] `jupyter` runs every notebook top to bottom on a clean machine after `pip install -r requirements.txt`.
- [ ] Each stage has a numeric check against the formula, using a short synthetic signal whose answer
      a human can verify by hand.
- [ ] All three sources produce the same features for the same data.
- [ ] The fixed-point path stays within 1 percent of the float path per stage, and the notebook prints
      the actual numbers rather than a pass or fail flag.
- [ ] `model/vectors/` holds the vectors and a manifest naming the record, the sample rate, and the scales.
- [ ] The RTL owner gets the vectors with one command, documented in `model/README.md`.
- [ ] No GPL-licensed code is copied; the notebook cites every external idea it uses.
- [ ] The results are written to `doc/` as a dated note: what ran, what the numbers were, what failed.

## 6. Traps that cost a day each

1. At 250 Hz a 150 ms window is 37.5 samples. Alternate 37 and 38, or the window silently becomes
   148 ms or 152 ms and every quoted number in the report becomes wrong.
2. Ectopic beats and rhythm transitions raise RMSSD without raising entropy. Expect a mixed-evidence
   group and send it to the undecided class instead of forcing a binary answer.
3. Do not tune a threshold and report the same data as the test. Split records first, then tune, then
   test, and write the split in the notebook.
4. Exclude AFDB records `04936` and `05091`. Published work reports their rhythm annotations as wrong.
5. Count samples, not seconds. The board's RR measurement works in sample indices, and the model has
   to match that or the comparison fails for reasons that have nothing to do with the algorithm.
6. Do not treat the 24-bit recorder output as a 12-bit word. Scale it, write the scale into the
   manifest, and check that a normal QRS does not clip.

## 7. Order of work

| Step | Output                                                        | Rough effort |
| ---- | ------------------------------------------------------------- | ------------ |
| 1    | Stage interfaces, the three sources, a synthetic test signal  | half a day   |
| 2    | Stages 1 to 5, with the envelope and the peak plot            | one day      |
| 3    | Stages 6 and 7, with hand-checked feature values              | half a day   |
| 4    | Stage 8, plus the calibration notebook                        | half a day   |
| 5    | Stage 9, the fixed-point mirror, and vector export            | one day      |
| 6    | The validation note in `doc/` and a handover to the RTL owner | two hours    |

Report progress in the group chat at the end of each step. A step that is nearly done is not done.

## 8. References

- Teaching note 31, _Memahami AFIB-LITE_, project vault. Defines every formula in this brief.
- Dash et al. 2009, _Automatic real time detection of atrial fibrillation_, Annals of Biomedical
  Engineering 37(9):1701. Three features, normalised RMSSD, 16-bin entropy, thresholds from ROC.
- Tateno and Glass 2001, coefficient of variation and RR histogram density.
- Zhou et al. 2015, symbolic dynamics with Shannon entropy, threshold 0.353.
- Libraries to import: `numpy`, `scipy`, `pandas`, `matplotlib`, `jupyter`, `wfdb` (MIT),
  `neurokit2` (MIT). A first validation run used neurokit2 0.2.13 and wfdb 4.3.1.
- Reference only, do not copy code: `berndporr/py-ecg-detectors` (GPL-3.0),
  `Aura-healthcare/hrv-analysis` (GPL-3.0).
- Baseline numbers from our own first run, record `04015`, 30 minutes, 590 windows of 32 beats:
  AUC 0.634 for absolute RMSSD, 0.770 for normalised RMSSD, 0.828 for pNN50, 0.904 for normalised
  entropy. Two-feature AND rule at its in-sample optimum: sensitivity 92.6 percent, specificity
  79.6 percent. Beat these numbers with a proper train and test split.
