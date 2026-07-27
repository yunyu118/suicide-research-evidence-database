#!/usr/bin/env python3
"""Build the public release artefacts.

Two products, because the full working corpus and the redistributable corpus
are not the same thing.

``sred_vX_public.parquet``
    Everything except abstract text. Abstracts are the publishers' copyright;
    PubMed and Europe PMC permit retrieval but not blanket redistribution, and
    OpenAlex stores them as inverted indices for exactly that reason. Dropping
    the column keeps the release licence-clean and, incidentally, cuts it to a
    size that fits in a Git repository. Every record retains its DOI and PMID,
    so anyone can re-fetch the abstracts themselves in a few minutes with the
    pipeline's own connectors.

``sred_vX.duckdb``
    The full relational database, for local analysis. Too large for version
    control; published as a release asset instead.

A manifest records row counts, column lists, the harvest window, and a SHA-256
for each artefact, so a downloaded file can be checked against the release it
claims to be.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RELEASES = ROOT / "data" / "releases"

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
log = logging.getLogger("release")

# Columns withheld from the redistributable Parquet.
WITHHELD = ["abstract"]

# Working columns that are meaningful only inside the pipeline.
INTERNAL_PREFIXES = ("meta_", "rule_", "label_", "_")


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="1.0")
    ap.add_argument("--keep-internal", action="store_true",
                    help="retain meta_/rule_/label_ working columns")
    args = ap.parse_args()

    src = PROCESSED / "sred_classified.parquet"
    if not src.exists():
        log.error("missing %s - run the pipeline first", src)
        return 1

    RELEASES.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(src)
    log.info("loaded %d records, %d columns", len(df), len(df.columns))

    drop = [c for c in df.columns if c in WITHHELD]
    if not args.keep_internal:
        drop += [c for c in df.columns
                 if c.startswith(INTERNAL_PREFIXES) and c not in
                 ("label_source_is_scientific", "label_source_is_empirical",
                  "label_source_methodology")]
    public = df.drop(columns=sorted(set(drop)), errors="ignore")
    log.info("dropped %d columns: %s", len(set(drop)), sorted(set(drop))[:12])

    out = RELEASES / f"sred_v{args.version}_public.parquet"
    public.to_parquet(out, index=False, compression="zstd")
    log.info("wrote %s (%.1f MB, %d cols)", out.name,
             out.stat().st_size / 1e6, len(public.columns))

    manifest = {
        "release_version": args.version,
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "n_records": int(len(public)),
        "year_min": int(pd.to_numeric(public["year"], errors="coerce").min()),
        "year_max": int(pd.to_numeric(public["year"], errors="coerce").max()),
        "n_journals": int(public["journal_canonical"].nunique()),
        "columns": sorted(public.columns.tolist()),
        "withheld_columns": sorted(set(drop)),
        "withheld_reason": (
            "Abstract text is subject to publisher copyright and is not "
            "redistributed. DOIs and PMIDs are retained so abstracts can be "
            "re-fetched with scripts/01_harvest.py."),
        "artefacts": {},
        "license": {"code": "MIT", "data": "CC BY 4.0"},
        "sources": ["PubMed/MEDLINE", "Europe PMC", "OpenAlex", "NIH iCite"],
    }

    for f in sorted(RELEASES.glob(f"sred_v{args.version}*")):
        if f.name.endswith(".json"):
            continue
        manifest["artefacts"][f.name] = {
            "bytes": f.stat().st_size,
            "mb": round(f.stat().st_size / 1e6, 1),
            "sha256": sha256(f),
        }
        log.info("hashed %s (%.1f MB)", f.name, f.stat().st_size / 1e6)

    mpath = RELEASES / f"MANIFEST_v{args.version}.json"
    mpath.write_text(json.dumps(manifest, indent=2))
    log.info("manifest -> %s", mpath.name)

    big = [n for n, a in manifest["artefacts"].items() if a["mb"] > 90]
    if big:
        log.warning("attach these to a GitHub Release rather than committing "
                    "them (>90 MB): %s", big)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
