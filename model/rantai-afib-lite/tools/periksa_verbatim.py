"""Verbatim checker for the frozen reference module acuan_fase.py.

The checker reads the module, walks every "# ===== SOURCE:" header, and for each header it
derives the expected text straight from the notebook named in that header. The block text found
in the module and the text sliced out of the .ipynb are then compared byte for byte. Nothing is
taken on trust: the expected text is located by function name, not by a recorded line number, so
a wrong line number in the generator would show up as a mismatch.

Run it with the project interpreter:

    /home/avivsabilalm/.venvs/afib-lite/bin/python model/rantai-afib-lite/periksa_verbatim.py
"""

import ast
import difflib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
NB_DIR = REPO / "model" / "math-equation-afib"
MODULE = HERE / "acuan_fase.py"

HEADER = re.compile(r"^# ===== SOURCE: (.+?) \| CELL (\d+) \| (def|class|const) \| (.+?) ===== *$")
GENERATED = re.compile(r"^# GENERATED BINDING:")
ALIAS = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*__fase\d+(_sel\d+)? = [A-Za-z_][A-Za-z0-9_]*$")
MAGIC = re.compile(r"^\s*[%!]\S")


def cell_source(nb_name, cell_index):
    nb = json.loads((NB_DIR / nb_name).read_text(encoding="utf-8"))
    return "".join(nb["cells"][cell_index]["source"])


def derive(nb_name, cell_index, kind, names):
    """Slice the expected text out of the notebook, located by name."""
    src = cell_source(nb_name, cell_index)
    lines = src.split("\n")
    san = ["" if MAGIC.match(ln) else ln for ln in lines]
    tree = ast.parse("\n".join(san))
    want = set(names.split(","))
    for node in tree.body:
        if kind in ("def", "class") and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                          ast.ClassDef)):
            if getattr(node, "name", None) == names:
                return "\n".join(lines[node.lineno - 1:node.end_lineno])
        if kind == "const" and isinstance(node, (ast.Assign, ast.AnnAssign)):
            got = set()
            tgts = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in tgts:
                if isinstance(t, ast.Name):
                    got.add(t.id)
                elif isinstance(t, (ast.Tuple, ast.List)):
                    got.update(e.id for e in t.elts if isinstance(e, ast.Name))
            if got == want:
                end = node.end_lineno
                while end < len(lines) and any(lines[end].strip().startswith(n + "[")
                                               for n in got):
                    end += 1
                return "\n".join(lines[node.lineno - 1:end])
    raise LookupError("not found in %s cell %d: %s %s" % (nb_name, cell_index, kind, names))


def blocks_in_module():
    lines = MODULE.read_text(encoding="utf-8").split("\n")
    starts = [i for i, ln in enumerate(lines) if HEADER.match(ln)]
    out = []
    for n, i in enumerate(starts):
        m = HEADER.match(lines[i])
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        body = lines[i + 1:end]
        while body and (GENERATED.match(body[0]) or ALIAS.match(body[0])):
            body.pop(0)
        while body and (body[-1].strip() == "" or body[-1].startswith("# =======")
                        or body[-1].startswith("# NOTEBOOK ")):
            body.pop()
        out.append((m.group(1), int(m.group(2)), m.group(3), m.group(4), "\n".join(body),
                    i + 1))
    return out


def main():
    blocks = blocks_in_module()
    n_ok = n_bad = n_err = 0
    bad = []
    for nb, ci, kind, names, text, line in blocks:
        try:
            expect = derive(nb, ci, kind, names)
        except LookupError as exc:
            n_err += 1
            bad.append((nb, ci, kind, names, str(exc), "", ""))
            continue
        if expect == text:
            n_ok += 1
        else:
            n_bad += 1
            d = "\n".join(difflib.unified_diff(expect.split("\n"), text.split("\n"),
                                               "notebook", "acuan_fase.py", lineterm="", n=0))
            bad.append((nb, ci, kind, names, "text differs", text, d))
    print("module            :", MODULE)
    print("blocks in module  :", len(blocks))
    print("identical         :", n_ok)
    print("differing         :", n_bad)
    print("not found         :", n_err)
    if bad:
        print()
        for nb, ci, kind, names, msg, text, d in bad:
            print("MISMATCH %s | cell %d | %s | %s | %s" % (nb, ci, kind, names, msg))
            if d:
                print(d)
    print()
    print("VERDICT:", "all blocks are verbatim" if n_bad == 0 and n_err == 0
          else "NOT verbatim: %d differ, %d missing" % (n_bad, n_err))
    return 0 if (n_bad == 0 and n_err == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
