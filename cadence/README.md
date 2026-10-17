# cadence

Scripts and reports produced with Cadence tools.

## What belongs here

- Tcl scripts for whichever Cadence tools the organisers provide. Typical names: Genus for logic
  synthesis, Innovus for place and route, Xcelium for simulation, JasperGold for formal checks.
- Reports those tools write: area, timing, power, and constraint coverage.
- A short note per run that records the tool version, the design revision, and the command used.

## Why this folder exists

The RTL has to run through a commercial flow at some point, and the hackathon provides that flow on
site. Keeping the scripts here means the team can reproduce a run instead of retyping commands from
memory under time pressure.

## How to run

Source the setup script for the tool on the machine that holds the licence, then run the Tcl script
in batch mode. Record the exact command in the run note.

```bash
# example, adjust names to the installed tool
cadence_tool -batch -files scripts/<script>.tcl
```

## What stays out

- Licence files, vendor installers, and anything copied from the licensed installation.
- Tool databases and log dumps. Add them to `.gitignore` and keep only the reports you cite.
