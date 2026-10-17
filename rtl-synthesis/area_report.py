#!/usr/bin/env python3
"""Report cell count and area for a mapped Yosys netlist.

Inputs:
  * a Yosys JSON netlist written after `dfflibmap -liberty <lib>` and `abc -liberty <lib>`
  * the same liberty file used for the mapping

Area comes from the library: each mapped cell is looked up in the liberty `area` attribute.
Nothing is estimated. If a cell type is missing from the library, the script names it instead of
counting it as zero.

Flip-flops are counted by the marker in the cell name, because a cell such as
`sky130_fd_sc_hd__dfxtp_1` does not begin with `dfxtp`.

Usage:  python3 area_report.py reports/<design>.json <liberty file>
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter

# Any of these substrings in a cell name marks a sequential cell in the SKY130 library.
FF_MARKERS = ("dfxtp", "dfrtp", "dfstp", "dfbbn", "dfbbp", "dfxbp", "dfrbp",
              "edfxtp", "sedfxtp", "sdfxtp", "sdfrtp", "sdfstp")


def is_flip_flop(cell_type: str) -> bool:
    return any(marker in cell_type for marker in FF_MARKERS)


def load_liberty_areas(path: str) -> dict[str, float]:
    """Return {cell name: area in square micrometres} from a liberty file."""
    areas: dict[str, float] = {}
    cell_re = re.compile(r'^\s*cell\s*\(\s*"?([A-Za-z0-9_]+)"?\s*\)\s*\{')
    area_re = re.compile(r'^\s*area\s*:\s*([0-9.eE+-]+)\s*;')
    current = None
    depth = 0
    with open(path, errors="replace") as fh:
        for line in fh:
            if current is None:
                m = cell_re.match(line)
                if m:
                    current = m.group(1)
                    depth = 1
                continue
            if depth == 1:
                m = area_re.match(line)
                if m and current not in areas:
                    areas[current] = float(m.group(1))
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                current = None
                depth = 0
    return areas


def load_mapped_cells(path: str) -> Counter:
    """Return a Counter of cell types in a Yosys JSON netlist."""
    with open(path) as fh:
        data = json.load(fh)
    types: Counter = Counter()
    for module in data.get("modules", {}).values():
        for cell in module.get("cells", {}).values():
            types[cell.get("type", "?")] += 1
    return types


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    json_path, lib_path = sys.argv[1], sys.argv[2]
    areas = load_liberty_areas(lib_path)
    if not areas:
        print("FATAL: no cell areas parsed from the liberty file")
        return 1
    types = load_mapped_cells(json_path)

    total_cells = sum(types.values())
    unknown = {t: n for t, n in types.items() if t not in areas}
    known = {t: n for t, n in types.items() if t in areas}
    total_area = sum(areas[t] * n for t, n in known.items())
    ff_cells = sum(n for t, n in known.items() if is_flip_flop(t))
    ff_area = sum(areas[t] * n for t, n in known.items() if is_flip_flop(t))
    comb_area = total_area - ff_area

    print(f"netlist       : {json_path}")
    print(f"library       : {lib_path}  ({len(areas)} cells described)")
    print(f"cells mapped  : {total_cells}  (flip-flops {ff_cells}, combinational {total_cells - ff_cells})")
    if unknown:
        print(f"unmapped      : {len(unknown)} types -> {list(unknown)[:5]}")
    print(f"area          : {total_area:.2f} um^2   (flops {ff_area:.2f} um^2, combinational {comb_area:.2f} um^2)")
    if total_area > 0:
        print(f"flop share    : {100.0 * ff_area / total_area:.1f} percent of the area")
    print()
    print("top cell types:")
    for t, n in types.most_common(12):
        a = areas.get(t)
        label = f"{a:.3f} um^2 each" if a is not None else "NOT IN LIBERTY"
        print(f"  {t:34s} x{n:5d}   {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
