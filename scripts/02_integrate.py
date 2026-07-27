#!/usr/bin/env python3
"""Stages 2-5 - Deduplication, normalisation, screening, and quality assurance.

Reads every NDJSON shard written by ``01_harvest.py`` and produces the
integrated SRED corpus:

    data/processed/sred_papers.parquet   one row per unique work
    data/interim/dedup_report.json       merge counts + review-band pairs
    data/interim/normalisation_log.json  every fuzzy journal decision
    data/interim/screen_report.json      exclusion counts by reason
    data/interim/qa_report.json          integrity checks

The stage order matters. Deduplication runs *before* normalisation so that a
record's best available journal string (usually the OpenAlex/Crossref one)
survives the merge and drives normalisation; screening runs *after* the merge
so a record is judged on its union of metadata rather than on whichever
fragment a single provider happened to return.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sred.integrate.dedupe import deduplicate  # noqa: E402
from sred.integrate.normalize import JournalNormalizer  # noqa: E402
from sred.integrate.screen import Screener  # noqa: E402

RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout),
                              logging.FileHandler(ROOT / "logs" / "integrate.log")])
log = logging.getLogger("integrate")


def load_shards(channels: list[str]) -> list[dict]:
    recs: list[dict] = []
    per_channel = Counter()
    for ch in channels:
        d = RAW / ch
        if not d.exists():
            log.warning("channel missing: %s", ch)
            continue
        for f in sorted(d.glob("*.ndjson")):
            if not f.with_suffix(".done").exists():
                log.warning("skipping incomplete shard %s", f.name)
                continue
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        recs.append(json.loads(line))
                        per_channel[ch] += 1
    log.info("loaded %d raw records: %s", len(recs), dict(per_channel))
    return recs


def qa_checks(df: pd.DataFrame) -> dict:
    """Referential and plausibility checks, mirroring Perron et al. Stage 5."""
    checks: dict = {}
    checks["n_records"] = int(len(df))
    checks["duplicate_sred_ids"] = int(df["sred_id"].duplicated().sum())
    checks["duplicate_dois"] = int(df.loc[df["doi"].notna(), "doi"].duplicated().sum())
    checks["missing_title"] = int((df["title"].fillna("").str.len() == 0).sum())
    checks["missing_abstract"] = int((df["abstract"].fillna("").str.len() == 0).sum())
    checks["missing_year"] = int(df["year"].isna().sum())
    checks["missing_journal"] = int((df["journal_canonical"].fillna("").str.len() == 0).sum())
    checks["year_out_of_range"] = int(((df["year"] < 1900) | (df["year"] > 2026)).sum())
    checks["zero_author_records"] = int((df["n_authors"].fillna(0) == 0).sum())
    checks["implausible_author_count"] = int((df["n_authors"].fillna(0) > 200).sum())
    checks["negative_citations"] = int((df["cited_by_count"].fillna(0) < 0).sum())
    checks["doi_coverage_pct"] = round(float(df["doi"].notna().mean() * 100), 2)
    checks["abstract_coverage_pct"] = round(
        float((df["abstract"].fillna("").str.len() > 0).mean() * 100), 2)
    checks["citation_coverage_pct"] = round(
        float(df["cited_by_count"].notna().mean() * 100), 2)
    checks["records_by_source"] = {k: int(v) for k, v in
                                   df["source"].value_counts().to_dict().items()}
    checks["records_by_venue_tier"] = {k: int(v) for k, v in
                                       df["venue_tier"].value_counts().to_dict().items()}
    checks["records_by_topic_focus"] = {str(k): int(v) for k, v in
                                        df["topic_focus"].value_counts(dropna=False).to_dict().items()}
    checks["n_unique_journals"] = int(df["journal_canonical"].nunique())
    checks["year_min"] = int(df["year"].min()) if df["year"].notna().any() else None
    checks["year_max"] = int(df["year"].max()) if df["year"].notna().any() else None
    failures = [k for k in ("duplicate_sred_ids", "year_out_of_range",
                            "negative_citations") if checks.get(k)]
    checks["hard_failures"] = failures
    return checks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channels", default="pubmed,europepmc,openalex_venue,openalex_topic")
    args = ap.parse_args()
    channels = [c.strip() for c in args.channels.split(",") if c.strip()]

    INTERIM.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    raw = load_shards(channels)
    if not raw:
        log.error("no records loaded - run 01_harvest.py first")
        return 1

    # --- Stage 2: deduplication ------------------------------------------
    deduped, dedup_report = deduplicate(raw)
    (INTERIM / "dedup_report.json").write_text(json.dumps(dedup_report, indent=2))

    # --- Stage 3: normalisation ------------------------------------------
    norm = JournalNormalizer().fit(deduped)
    methods = Counter()
    for r in deduped:
        canon, method = norm.resolve(r.get("journal_raw"), r.get("issn_l"))
        r["journal_canonical"] = canon
        methods[method] += 1
    norm.write_log(INTERIM / "normalisation_log.json")
    log.info("journal resolution methods: %s", dict(methods))

    # --- Stage 4: screening ----------------------------------------------
    with open(ROOT / "config" / "query_terms.yml") as fh:
        cfg = yaml.safe_load(fh)
    screener = Screener(cfg)
    deduped = screener.apply(deduped)
    screen_report = screener.report()
    screen_report["journal_resolution_methods"] = dict(methods)
    (INTERIM / "screen_report.json").write_text(json.dumps(screen_report, indent=2))

    # --- assemble ---------------------------------------------------------
    df = pd.DataFrame(deduped)
    for col in ("authors", "affiliations_raw", "countries", "funders",
                "mesh_terms", "mesh_major_terms", "keywords", "source_ids"):
        if col in df.columns:
            df[col] = df[col].apply(lambda v: json.dumps(v, ensure_ascii=False)
                                    if isinstance(v, (list, dict)) else v)
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    if "cited_by_count" in df.columns:
        df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").astype("Int64")

    # --- Stage 5: QA ------------------------------------------------------
    qa = qa_checks(df)
    (INTERIM / "qa_report.json").write_text(json.dumps(qa, indent=2))
    log.info("QA: %s", json.dumps({k: v for k, v in qa.items()
                                   if not isinstance(v, dict)}, indent=None))
    if qa["hard_failures"]:
        log.error("HARD QA FAILURES: %s", qa["hard_failures"])

    out = PROCESSED / "sred_papers.parquet"
    df.to_parquet(out, index=False)
    log.info("wrote %s (%d rows, %d cols)", out.name, len(df), len(df.columns))

    kept = df[df["screen_pass"]]
    kept.to_parquet(PROCESSED / "sred_screened.parquet", index=False)
    log.info("wrote sred_screened.parquet (%d rows)", len(kept))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
