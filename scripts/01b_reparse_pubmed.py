#!/usr/bin/env python3
"""Re-parse cached PubMed XML without re-fetching.

The PubMed connector's parser evolves - new fields get extracted, edge cases
in date and MeSH handling get fixed. Re-running ``01_harvest.py`` after such a
change would re-download the entire corpus, because NCBI's history-server
``WebEnv`` token is session-scoped: a fresh ESearch produces new EFetch URLs,
so nothing in the URL-keyed HTTP cache would hit.

This script sidesteps that entirely. It walks the on-disk HTTP cache, picks out
every response that is a ``PubmedArticleSet``, and re-runs the *current* parser
over it, re-sharding the output by publication year. No network, no NCBI load,
and the result is byte-for-byte what a fresh harvest with this parser would
have produced.

Usage
-----
    python scripts/01b_reparse_pubmed.py
    python scripts/01b_reparse_pubmed.py --dry-run
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sred.sources.pubmed import parse_efetch  # noqa: E402

CACHE = ROOT / "data" / "raw" / "_httpcache"
OUT = ROOT / "data" / "raw" / "pubmed"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("reparse")


def is_pubmed_payload(head: str) -> bool:
    return "<PubmedArticleSet" in head or "PubmedArticle" in head[:4000]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not CACHE.exists():
        log.error("no HTTP cache at %s - nothing to re-parse", CACHE)
        return 1

    files = sorted(CACHE.rglob("*.json.gz"))
    log.info("scanning %d cached responses", len(files))

    by_year: dict[int, list[dict]] = defaultdict(list)
    seen_pmids: set[str] = set()
    n_payloads = 0

    for i, f in enumerate(files, 1):
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                body = fh.read()
        except (OSError, EOFError, gzip.BadGzipFile):
            continue
        if not body or not is_pubmed_payload(body[:5000]):
            continue
        n_payloads += 1
        for paper in parse_efetch(body):
            if paper.pmid and paper.pmid in seen_pmids:
                continue
            if paper.pmid:
                seen_pmids.add(paper.pmid)
            if paper.year:
                by_year[int(paper.year)].append(paper.to_dict())
        if i % 500 == 0:
            log.info("scanned %d/%d files, %d payloads, %d records",
                     i, len(files), n_payloads, len(seen_pmids))

    total = sum(len(v) for v in by_year.values())
    log.info("re-parsed %d PubMed payloads -> %d unique records across %d years",
             n_payloads, total, len(by_year))
    if not total:
        log.error("no PubMed records recovered from cache; run 01_harvest.py instead")
        return 1

    if args.dry_run:
        for y in sorted(by_year):
            log.info("  %d: %d records", y, len(by_year[y]))
        return 0

    backup = OUT.with_name("pubmed_prev_parser")
    if OUT.exists():
        if backup.exists():
            shutil.rmtree(backup)
        OUT.rename(backup)
        log.info("previous shards moved to %s", backup.name)
    OUT.mkdir(parents=True, exist_ok=True)

    for year in sorted(by_year):
        path = OUT / f"pubmed_{year}.ndjson"
        with open(path, "w", encoding="utf-8") as fh:
            for r in by_year[year]:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        path.with_suffix(".done").write_text(str(len(by_year[year])))
    log.info("wrote %d year shards to %s", len(by_year), OUT)

    focused = sum(1 for v in by_year.values() for r in v
                  if r.get("topic_focus") == "focused")
    log.info("topic focus: %d focused / %d total (%.1f%%)",
             focused, total, focused / total * 100)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
