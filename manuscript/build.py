#!/usr/bin/env python3
"""Render the manuscript, substituting every number from results.json.

No figure in the prose is typed by hand. The source document
(``manuscript/manuscript.md``) carries ``{{dotted.path}}`` placeholders that are
resolved against ``data/processed/results.json`` at build time, so re-running
the pipeline and rebuilding the manuscript cannot leave a stale number behind.

An unresolved placeholder is a hard error, not a silent blank: a manuscript
that builds is a manuscript whose every claim traces to the data.

Usage
-----
    python manuscript/build.py                 # -> manuscript/manuscript_built.md
    python manuscript/build.py --docx          # also render .docx via pandoc
    python manuscript/build.py --check         # validate placeholders only
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "processed" / "results.json"
SRC = Path(__file__).parent / "manuscript.md"
OUT = Path(__file__).parent / "manuscript_built.md"

PLACEHOLDER = re.compile(r"\{\{([a-zA-Z0-9_.\[\]|,:-]+)\}\}")


def resolve(path: str, data: dict) -> Any:
    """Resolve a dotted path, with list indexing and an optional format spec.

    Examples::

        growth.article_cagr_pct
        methodology_overall[0].pct
        citations.mean_citations|1        # round to 1 decimal
        corpus.n_records|,                # thousands separator
    """
    fmt = None
    if "|" in path:
        path, fmt = path.split("|", 1)

    cur: Any = data
    for part in path.split("."):
        m = re.match(r"^([a-zA-Z0-9_-]+)\[(-?\d+)\]$", part)
        if m:
            key, idx = m.group(1), int(m.group(2))
            cur = cur[key][idx]
        else:
            cur = cur[part]

    if fmt is None:
        return cur
    if fmt == ",":
        return f"{int(cur):,}"
    if fmt.isdigit():
        return f"{float(cur):.{int(fmt)}f}"
    if fmt == "pct0":
        return f"{float(cur):.0f}"
    return format(cur, fmt)


def render(text: str, data: dict) -> tuple[str, list[str]]:
    missing: list[str] = []

    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        try:
            v = resolve(key, data)
        except (KeyError, IndexError, TypeError, ValueError) as e:
            missing.append(f"{key} ({type(e).__name__})")
            return f"[[UNRESOLVED: {key}]]"
        if isinstance(v, float):
            return f"{v:.2f}".rstrip("0").rstrip(".")
        return str(v)

    return PLACEHOLDER.sub(sub, text), missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not RESULTS.exists():
        print(f"error: {RESULTS} not found - run scripts/04_analyze.py first",
              file=sys.stderr)
        return 1
    if not SRC.exists():
        print(f"error: {SRC} not found", file=sys.stderr)
        return 1

    data = json.loads(RESULTS.read_text())
    text, missing = render(SRC.read_text(), data)

    n_placeholders = len(PLACEHOLDER.findall(SRC.read_text()))
    if missing:
        print(f"{len(missing)} unresolved placeholder(s) of {n_placeholders}:",
              file=sys.stderr)
        for m in sorted(set(missing)):
            print(f"  - {m}", file=sys.stderr)
        return 1

    if args.check:
        print(f"all {n_placeholders} placeholders resolve")
        return 0

    OUT.write_text(text)
    print(f"wrote {OUT} ({n_placeholders} placeholders resolved, "
          f"{len(text.split())} words)")

    if args.docx:
        docx = OUT.with_suffix(".docx")
        try:
            subprocess.run(
                ["pandoc", str(OUT), "-o", str(docx),
                 "--reference-doc", str(Path(__file__).parent / "reference.docx")]
                if (Path(__file__).parent / "reference.docx").exists()
                else ["pandoc", str(OUT), "-o", str(docx)],
                check=True)
            print(f"wrote {docx}")
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"pandoc unavailable or failed ({e}); markdown written only",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
