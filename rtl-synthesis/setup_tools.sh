#!/usr/bin/env bash
# Install the local toolchain for SKY130 synthesis and RTL simulation, without root.
#
# Everything lands in ./debs and ./debroot inside this folder, so deleting the folder deletes the
# toolchain. Ubuntu ships these tools as normal packages: `apt-get download` fetches the .deb files
# and `dpkg-deb -x` unpacks them into a local prefix. Neither command needs sudo.
#
# Usage:  ./setup_tools.sh           # native Yosys 0.33 + ABC + Icarus Verilog + Verilator
#         ./setup_tools.sh --wasm    # also install Yosys 0.70 (WASM build) into ./.venv
#
# Tested on Ubuntu 24.04 (noble). Expected download: about 20 MB of packages.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PACKAGES=(yosys yosys-abc iverilog verilator)

mkdir -p debs debroot

echo "== fetching packages, no root needed =="
if ! ( cd debs && apt-get download "${PACKAGES[@]}" ); then
    echo >&2
    echo "apt-get download failed. On a fresh machine the usual cause is an empty package cache:" >&2
    echo "  E: Unable to locate package yosys" >&2
    echo "The cache lives in /var/lib/apt/lists, so refreshing it needs root. Run one of these first:" >&2
    echo "  sudo apt update" >&2
    echo "  sudo apt-get update && sudo apt-get download ${PACKAGES[*]}" >&2
    exit 1
fi
for d in debs/*.deb; do dpkg-deb -x "$d" debroot/; done

echo
echo "== versions =="
export PATH="$ROOT/debroot/usr/bin:$PATH"
export YOSYS_DATDIR="$ROOT/debroot/usr/share/yosys"

# Capture output instead of piping into `head`. Under `set -o pipefail`, a program that writes more
# than one line and then sees its reader close the pipe dies with SIGPIPE, and this script would then
# exit 141 in the middle of its own report.
if command -v yosys >/dev/null; then
    YOSYS_VER="$(yosys -V 2>&1)"
    echo "${YOSYS_VER%%$'\n'*}"
else
    echo "yosys: NOT INSTALLED" >&2
fi

if [ -x "$ROOT/debroot/usr/bin/yosys-abc" ]; then
    echo "yosys-abc: present (yosys cannot map cells without it)"
else
    echo "yosys-abc: MISSING. Ubuntu ships it as a separate package, so make sure 'yosys-abc' is in PACKAGES." >&2
fi

IVL_VER="$("$ROOT/debroot/usr/bin/iverilog" -V 2>&1)"
echo "${IVL_VER%%$'\n'*}"
"$ROOT/debroot/usr/bin/verilator_bin" --version

if [ "${1:-}" = "--wasm" ]; then
    echo
    echo "== optional: Yosys 0.70, WASM build, in ./.venv (about 136 MB, mostly wasmtime) =="
    python3 -m venv .venv
    ./.venv/bin/pip install --quiet --upgrade pip
    ./.venv/bin/pip install --quiet -r requirements.txt
    WASM_VER="$(./.venv/bin/yowasp-yosys -V 2>&1)"
    echo "${WASM_VER%%$'\n'*}"
fi

echo
echo "== standard-cell library =="
if [ -f sky130_fd_sc_hd__tt_025C_1v80.lib ]; then
    SIZE="$(wc -c < sky130_fd_sc_hd__tt_025C_1v80.lib)"
    echo "present: $SIZE bytes"
    if [ "$SIZE" -ne 12800135 ]; then
        echo "WARNING: expected 12800135 bytes. A tiny file is usually a 404 page saved under the" >&2
        echo "         library name, because curl without -f reports success on a 404. Fetch it again." >&2
    fi
else
    echo "missing. Fetch it with, then check the byte count:"
    echo
    echo "  curl -fL -o sky130_fd_sc_hd__tt_025C_1v80.lib \\"
    echo "    https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/master/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
    echo "  wc -c sky130_fd_sc_hd__tt_025C_1v80.lib   # expect 12800135"
    echo
    echo "Without -f, a wrong branch name returns a 14-byte page that says '404: Not Found'."
fi

echo
echo "setup_tools.sh finished. Expected exit code: 0, anything else means the install is not ready."
echo "Next: ./setup_check.sh"
