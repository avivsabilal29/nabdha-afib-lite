# doc

Design notes, figures, measured logs, and meeting records that belong to more than one part of the
project.

## What goes here

- Design notes that span the model, the RTL, and the board at once.
- Figures and diagrams used in the report or the pitch.
- Measurement logs: synthesis runs, power readings, bench results, with the date and the tool
  version recorded next to each number.
- Meeting records and decisions, including the options that were rejected and why.

## Naming

Use `YYYY-MM-DD-topic.md` for notes and logs, and `YYYY-MM-DD-topic.png` for figures. A dated name
survives reordering and makes it obvious which note is current.

## What stays out

- Generated outputs from Vivado, Cadence, or Yosys. Those live in the tool folder and stay untracked.
- Vendor licence files and anything copied out of a licensed tool.
- Binary documents that a teammate cannot diff. Export the text form and keep the source.
