# model

Python reference model of the AFIB-LITE pipeline, written as Jupyter notebooks.

## Why this folder exists

The RTL needs something to be checked against. This model implements the mathematics in floating
point, then again in the fixed-point formats the RTL uses, and exports the golden vectors the
testbench compares against. When the model and the RTL disagree, this folder decides which one is
wrong and why.

## What belongs here

- The reference model, as notebooks. A notebook per task: the pipeline, the fixed-point mirror,
  the threshold calibration, and the AFDB validation.
- `vectors/` with the golden vectors and a manifest per record.
- `requirements.txt` with pinned versions.
- A short note per experiment that records the input record, the settings, and the numbers that
  came out.

`test.ipynb` is a scratch file from the first commit. Replace it with the real notebooks and delete
it when they land.

## How to run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter lab
```

Run every notebook top to bottom before you commit. A notebook that only works because of cells you
already executed is not finished.

## Rules

- Write our own code. Importing MIT and BSD licensed libraries is fine: numpy, scipy, pandas,
  matplotlib, jupyter, wfdb, neurokit2.
- Do not copy code from GPL-3.0 projects such as `py-ecg-detectors` or `hrv-analysis`. Read them,
  cite them, then implement our own version. The hackathon checks originality, and a copied
  function would fail that check.
- Keep the model independent from the RTL. It defines the expected behaviour; it does not follow the
  RTL.

## Next step

Read `TASK_BRIEF.md` in this folder. It spells out the stages, the class structure, the input
handling, and the definition of done.
