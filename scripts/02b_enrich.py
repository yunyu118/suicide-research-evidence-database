#!/usr/bin/env python3
"""Stage 4 (part 1) - Citation enrichment.

Runs after integration and before classification. Fills citation counts for the
large share of the corpus that reaches SRED through PubMed alone (PubMed
supplies no citation data), and attaches NIH's Relative Citation Ratio to every
record iCite recognises.

This matters more than a coverage statistic suggests. Without enrichment, every
citation analysis would be restricted to records indexed by OpenAlex or Europe
PMC - a subset biased toward exactly the well-indexed, high-profile venues whose
over-representation the citation analysis is supposed to detect.

Usage
-----
    python scripts/02b_enrich.py
    python scripts/02b_enrich.py --overwrite   # prefer iCite over other sources
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sred import http  # noqa: E402
from sred.sources import icite  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
INTERIM = ROOT / "data" / "interim"
MAILTO = os.environ.get("SRED_MAILTO", "sred@example.org")

# Log directory must exist before logging is configured. Git does not track
# empty directories, so a fresh clone has no logs/ and FileHandler would raise
# FileNotFoundError before the first line of work. This bit CI on the very
# first run, which is exactly what CI is for.
(ROOT / "logs").mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout),
                              logging.FileHandler(ROOT / "logs" / "enrich.log")])
log = logging.getLogger("enrich")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--src", default=str(PROCESSED / "sred_screened.parquet"))
    args = ap.parse_args()

    src = Path(args.src)
    if not src.exists():
        log.error("missing %s - run 02_integrate.py first", src)
        return 1

    http.set_cache(ROOT / "data" / "raw" / "_httpcache", enabled=True)
    df = pd.read_parquet(src)
    log.info("loaded %d records", len(df))

    before = float(df["cited_by_count"].notna().mean() * 100)
    records = df.to_dict("records")
    records, report = icite.enrich(records, mailto=MAILTO, overwrite=args.overwrite)

    out = pd.DataFrame(records)
    for col in ("cited_by_count", "n_clinical_citations"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")
    for col in ("relative_citation_ratio", "nih_percentile",
                "field_citation_rate", "expected_citations_per_year"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    after = float(out["cited_by_count"].notna().mean() * 100)
    report["citation_coverage_before_pct"] = round(before, 2)
    report["citation_coverage_after_pct"] = round(after, 2)
    report["citation_source_mix"] = out["citation_source"].value_counts(dropna=False) \
        .head(10).to_dict()
    report["citation_source_mix"] = {str(k): int(v)
                                     for k, v in report["citation_source_mix"].items()}
    log.info("citation coverage: %.2f%% -> %.2f%%", before, after)

    out.to_parquet(src, index=False)
    (INTERIM / "enrichment_report.json").write_text(json.dumps(report, indent=2))
    log.info("wrote %s and enrichment_report.json", src.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
