#!/usr/bin/env python3
"""Stage 1 - Source-specific extraction.

Harvests the SRED corpus from every configured provider and writes one
newline-delimited JSON file per source-channel into data/raw/. Each file is
append-only and resumable: re-running skips year slices already on disk, so a
harvest interrupted after eight hours resumes rather than restarts.

Usage
-----
    python scripts/01_harvest.py --sources pubmed,openalex_venue,openalex_topic
    python scripts/01_harvest.py --sources pubmed --years 1989-1995
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sred import http  # noqa: E402
from sred.sources import europepmc, openalex, pubmed, scopus, wos  # noqa: E402

RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
MAILTO = os.environ.get("SRED_MAILTO", "sred@example.org")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler(ROOT / "logs" / "harvest.log")],
)
log = logging.getLogger("harvest")


def load_cfg():
    with open(ROOT / "config" / "query_terms.yml") as fh:
        terms = yaml.safe_load(fh)
    with open(ROOT / "config" / "journals_core.yml") as fh:
        journals = yaml.safe_load(fh)
    return terms, journals


class ShardWriter:
    """Append-only NDJSON writer with a per-shard completion marker."""

    def __init__(self, path: Path):
        self.path = path
        self.done = path.with_suffix(".done")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.n = 0
        self._fh = None

    def complete(self) -> bool:
        return self.done.exists()

    def __enter__(self):
        self._fh = open(self.path, "w", encoding="utf-8")
        return self

    def write(self, paper) -> None:
        self._fh.write(json.dumps(paper.to_dict(), ensure_ascii=False) + "\n")
        self.n += 1

    def __exit__(self, exc_type, *_):
        self._fh.close()
        if exc_type is None:
            self.done.write_text(str(self.n))
            log.info("shard complete: %s (%d records)", self.path.name, self.n)
        else:
            log.error("shard FAILED: %s", self.path.name)
        return False


# ---------------------------------------------------------------------------

def run_pubmed(terms: dict, years: range) -> None:
    api_key = os.environ.get("NCBI_API_KEY", "")
    query = pubmed.build_query(terms)
    log.info("PubMed query: %s", query)
    (INTERIM / "queries").mkdir(parents=True, exist_ok=True)
    (INTERIM / "queries" / "pubmed_query.txt").write_text(query)

    for year in years:
        shard = ShardWriter(RAW / "pubmed" / f"pubmed_{year}.ndjson")
        if shard.complete():
            log.info("skip pubmed %d (done)", year)
            continue
        with shard as w:
            for p in pubmed.harvest(terms, range(year, year + 1),
                                    api_key=api_key, mailto=MAILTO):
                w.write(p)


def run_openalex_venue(journals: dict, terms: dict) -> None:
    dr = terms["date_range"]
    resolution = {}
    for tier_key, tier_label in (("tier_a", "core_a"), ("tier_b", "adjacent_b")):
        for j in journals.get(tier_key) or []:
            issn = j.get("issn_l")  # noqa: B007 - used below via `use_issn`
            name = j["name"]
            src = openalex.resolve_source(issn or name, mailto=MAILTO)
            resolution[name] = {
                "config_issn_l": issn,
                "resolved_id": (src or {}).get("id"),
                "resolved_name": (src or {}).get("display_name"),
                "resolved_issn_l": (src or {}).get("issn_l"),
                "works_count": (src or {}).get("works_count"),
                "tier": tier_label,
            }
            if not src:
                log.warning("UNRESOLVED source: %s (%s)", name, issn)
                continue
            use_issn = src.get("issn_l") or issn
            slug = (issn or name).replace("/", "-").replace(" ", "_")
            shard = ShardWriter(RAW / "openalex_venue" / f"venue_{slug}.ndjson")
            if shard.complete():
                log.info("skip venue %s (done)", name)
                continue
            with shard as w:
                for p in openalex.harvest_venue(use_issn, tier_label,
                                                dr["start"], dr["end"], mailto=MAILTO):
                    w.write(p)
            # Historical predecessor titles (e.g. "Suicide" -> SLTB)
            if j.get("predecessor_issn"):
                psrc = openalex.resolve_source(j["predecessor_issn"], mailto=MAILTO)
                if psrc:
                    ps = ShardWriter(RAW / "openalex_venue" / f"venue_{j['predecessor_issn']}.ndjson")
                    if not ps.complete():
                        with ps as w:
                            for p in openalex.harvest_venue(
                                    psrc.get("issn_l") or j["predecessor_issn"],
                                    tier_label, dr["start"], dr["end"], mailto=MAILTO):
                                w.write(p)

    (INTERIM).mkdir(parents=True, exist_ok=True)
    (INTERIM / "source_resolution.json").write_text(json.dumps(resolution, indent=2))
    log.info("venue resolution written (%d journals)", len(resolution))


def run_openalex_topic(terms: dict, years: range) -> None:
    oa = terms["openalex"]
    for year in years:
        shard = ShardWriter(RAW / "openalex_topic" / f"topic_{year}.ndjson")
        if shard.complete():
            log.info("skip openalex topic %d (done)", year)
            continue
        with shard as w:
            for p in openalex.harvest_topic(
                    oa["search_terms"], f"{year}-01-01", f"{year}-12-31",
                    oa["restrict_types"], mailto=MAILTO, year_slice=False,
                    field=oa.get("delineation_field", "title"),
                    require_abstract=oa.get("require_abstract", True)):
                w.write(p)


def run_europepmc(terms: dict, years: range) -> None:
    ep = terms["europepmc"]
    for year in years:
        shard = ShardWriter(RAW / "europepmc" / f"epmc_{year}.ndjson")
        if shard.complete():
            log.info("skip europepmc %d (done)", year)
            continue
        with shard as w:
            for p in europepmc.harvest(
                    ep["search_terms"], year, year, mailto=MAILTO,
                    field=ep.get("delineation_field", "TITLE"),
                    require_abstract=ep.get("require_abstract", True)):
                w.write(p)


def run_commercial(kind: str, terms: dict, years: range) -> None:
    """Optional Scopus / Web of Science channels.

    Never used for published results - see the module docstrings in
    sources/scopus.py and sources/wos.py. Present so a subscribing institution
    can quantify what commercial indexing adds over the open sources.
    """
    mod = {"scopus": scopus, "wos": wos}[kind]
    terms_list = terms["europepmc"]["search_terms"]
    field = {"scopus": "TITLE", "wos": "TI"}[kind]
    for year in years:
        shard = ShardWriter(RAW / kind / f"{kind}_{year}.ndjson")
        if shard.complete():
            log.info("skip %s %d (done)", kind, year)
            continue
        try:
            with shard as w:
                for p in mod.harvest(terms_list, range(year, year + 1),
                                     mailto=MAILTO, field=field):
                    w.write(p)
        except (scopus.ScopusNotConfigured, wos.WosNotConfigured) as e:
            log.warning("%s channel skipped: %s", kind, e)
            return


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="pubmed,openalex_venue,openalex_topic")
    ap.add_argument("--years", default=None, help="e.g. 1989-2025")
    args = ap.parse_args()

    terms, journals = load_cfg()
    dr = terms["date_range"]
    if args.years:
        a, b = args.years.split("-")
        years = range(int(a), int(b) + 1)
    else:
        years = range(int(dr["start"][:4]), int(dr["end"][:4]) + 1)

    http.set_cache(RAW / "_httpcache", enabled=True)
    (ROOT / "logs").mkdir(exist_ok=True)

    wanted = [s.strip() for s in args.sources.split(",") if s.strip()]
    if "openalex_venue" in wanted:
        run_openalex_venue(journals, terms)
    if "pubmed" in wanted:
        run_pubmed(terms, years)
    if "openalex_topic" in wanted:
        run_openalex_topic(terms, years)
    if "europepmc" in wanted:
        run_europepmc(terms, years)
    for kind in ("scopus", "wos"):
        if kind in wanted:
            run_commercial(kind, terms, years)

    log.info("harvest complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
