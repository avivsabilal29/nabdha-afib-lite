#!/usr/bin/env python3
"""Read a VCD waveform and show it as text, or as a standalone HTML timing diagram.

This exists because no waveform viewer is installed on this machine, and because a text dump is
often more useful than a GUI: it can be diffed, pasted into a report, or read over SSH. The file
format is the one every simulator writes, so it works with Icarus, Verilator, and xsim output alike.

    python3 vcd_view.py reports/counter8.vcd                  # table, one row per sampled clock
    python3 vcd_view.py reports/counter8.vcd --mode wave      # ASCII timing diagram
    python3 vcd_view.py reports/counter8.vcd --signals count,carry,borrow
    python3 vcd_view.py reports/counter8.vcd --from 150000 --to 250000 --max 40
    python3 vcd_view.py reports/counter8.vcd --html reports/timing.html

Two details of the format are handled on purpose, because ignoring them costs time:

1. One id code can carry several names. When a testbench wire is connected straight to a submodule
   port, Icarus declares both names and reuses one code, so `carry` and `carry_o` are the same
   signal. Every name is kept and matching works on any of them, otherwise half the signal list
   silently disappears from the listing.
2. Sampling happens one clock into the period, not on the edge. Sampling at the edge is a race, the
   same way it is inside a testbench, and two simulators can then disagree about what they saw.
"""

import argparse
import bisect
import html
import sys

SCALAR_CHARS = "01xzXZ"


def parse_vcd(path):
    """Return (signals, timeline).

    signals:  id -> list of (full_name, size), every alias of that code
    timeline: id -> sorted list of (time_ps, value), value None means x or z
    """
    signals = {}
    timeline = {}
    scope = []
    current_time = 0

    with open(path) as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith("$scope"):
                scope.append(line.split()[2])
            elif line.startswith("$upscope"):
                if scope:
                    scope.pop()
            elif line.startswith("$var"):
                parts = line.split()
                size = int(parts[2])
                sig_id = parts[3]
                signals.setdefault(sig_id, []).append((".".join(scope + [parts[4]]), size))
                timeline.setdefault(sig_id, [])
            elif line.startswith("$enddefinitions"):
                break

        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line[0] == "#":
                current_time = int(line[1:])
                continue
            if line[0] == "$":
                continue
            if line[0] in "bB":
                parts = line.split()
                if len(parts) < 2:
                    continue
                bits, sig_id = parts[0][1:], parts[1]
                if sig_id in signals:
                    value = None if ("x" in bits.lower() or "z" in bits.lower()) else int(bits, 2)
                    timeline[sig_id].append((current_time, value))
            elif line[0] in SCALAR_CHARS:
                value_char, sig_id = line[0], line[1:].strip()
                if sig_id in signals:
                    value = None if value_char in "xXzZ" else int(value_char)
                    timeline[sig_id].append((current_time, value))

    return signals, timeline


def names_of(signals, sig_id):
    return [name for name, _ in signals[sig_id]]


def display_name(signals, sig_id):
    """Shortest name with the fewest dots, which is normally the testbench level one."""
    return min(names_of(signals, sig_id), key=lambda name: (name.count("."), len(name)))


def size_of(signals, sig_id):
    return signals[sig_id][0][1]


def value_at(series, times, when):
    """Value of one signal at a time, using the last change at or before it."""
    index = bisect.bisect_right(times, when) - 1
    return None if index < 0 else series[index][1]


def leaf_names(signals, sig_id):
    return {name.split(".")[-1] for name in names_of(signals, sig_id)}


def pick(signals, wanted):
    """Signal codes to show.

    With no fragments: the signals declared at the top level, small ones only, so testbench
    bookkeeping integers do not drown the waveform.

    With fragments: an exact leaf name match wins outright. Substring matching is only a fallback,
    because `count` as a substring also matches count_next, count_o, and every task variable called
    got_count, which turns a six row diagram into a sixty row one.
    """
    if not wanted:
        return [sig_id for sig_id in signals
                if display_name(signals, sig_id).count(".") == 1 and size_of(signals, sig_id) <= 16]
    exact = [sig_id for sig_id in signals if leaf_names(signals, sig_id) & set(wanted)]
    if exact:
        return exact
    return [sig_id for sig_id in signals
            if any(part in name for name in names_of(signals, sig_id) for part in wanted)]


def as_watched(signals, watch):
    """Map requested leaf names onto codes, so any alias counts and no signal is reported twice."""
    wanted = set(watch)
    return [sig_id for sig_id in signals
            if any(name.split(".")[-1] in wanted for name in names_of(signals, sig_id))]


def sample_values(signals, timeline, sig_id, samples):
    series = timeline[sig_id]
    times = [t for t, _ in series]
    return [value_at(series, times, when) for when in samples]


def to_text(value, size):
    """Decimal for narrow signals, hexadecimal for wide ones, so a 256 bit bus stays one column."""
    if value is None:
        return "x"
    if size > 16:
        return format(value, "x")
    return str(value)


def print_table(signals, timeline, chosen, samples):
    columns = []
    for sig_id in chosen:
        name = display_name(signals, sig_id).split(".")[-1]
        cells = [to_text(value, size_of(signals, sig_id))
                 for value in sample_values(signals, timeline, sig_id, samples)]
        columns.append((name, max([len(name)] + [len(cell) for cell in cells]), cells))

    print("time_ps  " + " ".join(f"{name:>{w}}" for name, w, _ in columns))
    print(" " * 8 + " ".join("-" * w for _, w, _ in columns))
    for index, when in enumerate(samples):
        row = " ".join(f"{cells[index]:>{w}}" for _, w, cells in columns)
        print(f"{when:>7}  {row}")


def print_wave(signals, timeline, chosen, samples):
    """ASCII timing diagram. Every column is one sample and every row uses the same cell width, so
    the columns line up across signals and the time axis underneath stays readable."""
    label_w = max(len(display_name(signals, sig_id).split(".")[-1]) for sig_id in chosen)
    values = {sig_id: sample_values(signals, timeline, sig_id, samples) for sig_id in chosen}

    # Width cap keeps a wide bus from stretching every row: anything longer is shown from its low
    # digits with a marker, which is still enough to see that the value changed.
    cell_w = 1
    for sig_id in chosen:
        for value in values[sig_id]:
            text = to_text(value, size_of(signals, sig_id))
            cell_w = max(cell_w, min(len(text), 12))

    for sig_id in chosen:
        label = display_name(signals, sig_id).split(".")[-1]
        cells = []
        previous = object()
        for value in values[sig_id]:
            if size_of(signals, sig_id) == 1:
                cells.append(("_" if value in (0, None) else "\u203e") * cell_w)
            else:
                text = to_text(value, size_of(signals, sig_id))
                if len(text) > cell_w:
                    text = "~" + text[-cell_w + 1:]
                cells.append("-" * cell_w if text == previous else text.rjust(cell_w))
                previous = text
        print(f"{label:<{label_w}}  {''.join(cells)}")

    tick_every = 5
    axis = [" "] * (cell_w * len(samples))
    for index in range(0, len(samples), tick_every):
        start = index * cell_w
        for offset, char in enumerate(str(samples[index] // 1000)):
            if start + offset < len(axis):
                axis[start + offset] = char
    print(f"{'time_ns':<{label_w}}  {''.join(axis).rstrip()}")


def print_events(signals, timeline, samples, watch):
    """Report rising one-clock pulses on the watched signals, with the time they happened."""
    print("events:")
    found = False
    for sig_id in as_watched(signals, watch):
        values = sample_values(signals, timeline, sig_id, samples)
        previous = None
        for when, value in zip(samples, values):
            if value == 1 and previous != 1:
                print(f"  {when:>7} ps  {display_name(signals, sig_id)} pulses")
                found = True
            previous = value
    if not found:
        print("  none")


def write_html(path, signals, timeline, chosen, samples, title):
    """A standalone timing diagram, themed with the app CSS variables when they exist."""
    row_h = 34
    left = 170
    cell_w = 26
    width = left + cell_w * len(samples) + 20
    height = row_h * (len(chosen) + 1) + 40

    rows = []
    y = 30
    for sig_id in chosen:
        label = display_name(signals, sig_id)
        values = sample_values(signals, timeline, sig_id, samples)
        rows.append(f'<text x="10" y="{y + 18}" class="lbl">{html.escape(label)}</text>')
        if size_of(signals, sig_id) == 1:
            for index, value in enumerate(values):
                x0 = left + cell_w * index
                rows.append(f'<line x1="{x0 + 2}" y1="{y + 22}" x2="{x0 + cell_w - 2}" y2="{y + 22}" class="bit"/>')
                if value == 1:
                    rows.append(f'<rect x="{x0 + 2}" y="{y + 6}" width="{cell_w - 4}" height="16" class="hi"/>')
                if index and value != values[index - 1]:
                    rows.append(f'<line x1="{x0}" y1="{y + 6}" x2="{x0}" y2="{y + 22}" class="bit"/>')
        else:
            previous = None
            for index, value in enumerate(values):
                x0 = left + cell_w * index
                text = to_text(value, size_of(signals, sig_id))
                rows.append(f'<rect x="{x0 + 2}" y="{y + 9}" width="{cell_w - 4}" height="14" class="bus"/>')
                if text != previous:
                    rows.append(f'<text x="{x0 + cell_w / 2}" y="{y + 20}" class="val">{html.escape(text)}</text>')
                    previous = text
        y += row_h

    ticks = []
    step = max(1, len(samples) // 12)
    for index in range(0, len(samples), step):
        x = left + cell_w * index + cell_w / 2
        ticks.append(f'<text x="{x}" y="{y + 18}" class="tick">{samples[index] // 1000}</text>')
    axis = f'<line x1="{left}" y1="{y}" x2="{left + cell_w * len(samples)}" y2="{y}" class="axis"/>'

    doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>
  body {{ margin: 0; color: var(--foreground, #e6e6e6); background: transparent;
         font-family: var(--font-mono, ui-monospace, monospace); }}
  svg {{ display: block; }}
  .lbl {{ fill: var(--foreground, #e6e6e6); font-size: 12px; }}
  .tick {{ fill: var(--muted-foreground, #999); font-size: 10px; text-anchor: middle; }}
  .val {{ fill: var(--foreground, #e6e6e6); font-size: 10px; text-anchor: middle; }}
  .bit {{ stroke: var(--muted-foreground, #999); stroke-width: 1.5; }}
  .hi {{ fill: var(--accent, #4a9); opacity: 0.9; }}
  .bus {{ fill: var(--border, #444); opacity: 0.7; }}
  .axis {{ stroke: var(--muted-foreground, #999); stroke-width: 1; }}
</style></head><body>
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
{chr(10).join(rows)}
{axis}
{chr(10).join(ticks)}
</svg>
</body></html>
"""
    with open(path, "w") as handle:
        handle.write(doc)


def main():
    parser = argparse.ArgumentParser(description="Show a VCD waveform as text or HTML.")
    parser.add_argument("vcd")
    parser.add_argument("--signals", default="", help="comma separated name fragments, default top level")
    parser.add_argument("--from", dest="start", type=int, default=0, help="start time in picoseconds")
    parser.add_argument("--to", dest="stop", type=int, default=None, help="stop time in picoseconds")
    parser.add_argument("--period", type=int, default=10000, help="sampling period in picoseconds")
    parser.add_argument("--phase", type=int, default=5001, help="offset inside the period in picoseconds")
    parser.add_argument("--max", type=int, default=64, help="maximum number of sampled columns")
    parser.add_argument("--mode", choices=("table", "wave"), default="table")
    parser.add_argument("--html", default=None, help="also write a standalone timing diagram here")
    parser.add_argument("--events", default="carry,borrow", help="signals to report as one-clock pulses")
    args = parser.parse_args()

    signals, timeline = parse_vcd(args.vcd)
    if not signals:
        sys.exit(f"no signals found in {args.vcd}")

    last_time = max((series[-1][0] for series in timeline.values() if series), default=0)
    samples = list(range(args.start + args.phase, (args.stop or last_time) + 1, args.period))
    if len(samples) > args.max:
        samples = samples[:args.max]

    wanted = [part for part in args.signals.split(",") if part]
    chosen = pick(signals, wanted)
    if not chosen:
        sys.exit("no signal matched --signals")

    title = f"{args.vcd}, one sample every {args.period} ps, {len(signals)} signal codes"
    print(title)
    print()
    if args.mode == "table":
        print_table(signals, timeline, chosen, samples)
    else:
        print_wave(signals, timeline, chosen, samples)
    print()
    print_events(signals, timeline, samples, [part for part in args.events.split(",") if part])

    if args.html:
        write_html(args.html, signals, timeline, chosen, samples, title)
        print()
        print(f"timing diagram written to {args.html}")


if __name__ == "__main__":
    main()
