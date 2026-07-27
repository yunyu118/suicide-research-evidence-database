"""Scopus connector (activatable; unused in published results).

SRED's published results are built entirely from sources that require no
institutional subscription, because a reproducibility claim that only holds for
subscribers is not a reproducibility claim. This connector exists so that a
subscribing institution can answer the adjacent question: **what does
commercial indexing add that open sources miss, and what does it miss that they
catch?**

Activate by setting ``SCOPUS_API_KEY`` (and ``SCOPUS_INST_TOKEN`` for off-campus
access) and adding ``scopus`` to ``01_harvest.py --sources``. The output is
written to its own channel, so a build with Scopus and a build without are
directly comparable record for record.

Elsevier's terms permit metadata retrieval and redistribution of derived
counts, but *not* redistribution of abstract text. The pipeline therefore keeps
Scopus abstracts local: they participate in classification but are excluded
from `data/releases/`. See ``docs/licensing.md``.
"""

from __future__ import annotations

import logging
import os
import urllib.parse
from datetime import datetime, timezone
from typing import Iterator

from ..http import get_json
from ..schema import Paper, normalize_doi

log = logging.getLogger(__name__)

SEARCH = "https://api.elsevier.com/content/search/scopus"
PER_PAGE = 25          # Elsevier's standard-tier ceiling
MAX_OFFSET = 5000      # deep-paging limit; queries must be sliced below this


class ScopusNotConfigured(RuntimeError):
    """Raised when a Scopus harvest is requested without credentials."""


def _headers() -> dict[str, str]:
    key = os.environ.get("SCOPUS_API_KEY")
    if not key:
        raise ScopusNotConfigured(
            "SCOPUS_API_KEY is not set. SRED's published results do not use "
            "Scopus; set the key only if you are running the commercial-coverage "
            "comparison described in docs/methods.md.")
    h = {"X-ELS-APIKey": key, "Accept": "application/json"}
    tok = os.environ.get("SCOPUS_INST_TOKEN")
    if tok:
        h["X-ELS-Insttoken"] = tok
    return h


def build_query(terms: list[str], year: int, field: str = "TITLE") -> str:
    """Scopus advanced-search string for one publication year."""
    clause = " OR ".join(f'{field}("{t}")' for t in terms)
    return f"({clause}) AND PUBYEAR = {year} AND DOCTYPE(ar OR re)"


def _entry_to_paper(e: dict) -> Paper:
    now = datetime.now(timezone.utc).isoformat()
    authors = []
    for i, a in enumerate(e.get("author") or []):
        name = a.get("authname") or a.get("ce:indexed-name")
        if name:
            authors.append({"name": name, "orcid": a.get("orcid"),
                            "affiliation": None, "position": i + 1})
    n_auth = len(authors) or int(e.get("author-count", {}).get("@total", 0) or 0)

    date = e.get("prism:coverDate") or ""
    year = int(date[:4]) if date[:4].isdigit() else None

    return Paper(
        source="scopus",
        source_id=(e.get("dc:identifier") or "").replace("SCOPUS_ID:", ""),
        doi=normalize_doi(e.get("prism:doi")),
        pmid=e.get("pubmed-id"),
        title=(e.get("dc:title") or "").strip(),
        abstract=(e.get("dc:description") or "").strip(),
        journal_raw=(e.get("prism:publicationName") or "").strip(),
        issn_l=e.get("prism:issn") or e.get("prism:eIssn"),
        year=year,
        pub_date=date or None,
        volume=e.get("prism:volume"),
        issue=e.get("prism:issueIdentifier"),
        pages=e.get("prism:pageRange"),
        doc_type_raw=e.get("subtypeDescription"),
        is_oa=(e.get("openaccessFlag") is True),
        n_authors=n_auth,
        authors=authors,
        affiliations_raw=[a.get("affilname") for a in (e.get("affiliation") or [])
                          if a.get("affilname")],
        countries=sorted({a.get("affiliation-country") for a in (e.get("affiliation") or [])
                          if a.get("affiliation-country")}),
        keywords=[k.strip() for k in (e.get("authkeywords") or "").split("|") if k.strip()],
        cited_by_count=int(e.get("citedby-count") or 0),
        citation_source="scopus",
        url=next((l.get("@href") for l in (e.get("link") or [])
                  if l.get("@ref") == "scopus"), None),
        harvest_ts=now,
    )


def harvest(terms: list[str], years: range, mailto: str = "",
            field: str = "TITLE") -> Iterator[Paper]:
    """Harvest the Scopus topical corpus, one publication year at a time.

    Year slicing is not optional: Scopus refuses offsets beyond 5,000, and the
    suicide literature exceeds that for every year after roughly 2010 on an
    unsliced query.
    """
    headers = _headers()
    for year in years:
        query = build_query(terms, year, field)
        start, total = 0, None
        while True:
            params = {"query": query, "count": str(PER_PAGE), "start": str(start),
                      "view": "COMPLETE", "sort": "coverDate"}
            url = f"{SEARCH}?{urllib.parse.urlencode(params)}"
            data = get_json(url, headers=headers, mailto=mailto)
            res = data.get("search-results") or {}
            if total is None:
                total = int(res.get("opensearch:totalResults") or 0)
                log.info("scopus %d: %d records", year, total)
                if total > MAX_OFFSET:
                    log.warning("scopus %d exceeds the %d-record paging limit; "
                                "slice the query further to avoid silent truncation",
                                year, MAX_OFFSET)
            entries = res.get("entry") or []
            if not entries or entries[0].get("error"):
                break
            for e in entries:
                yield _entry_to_paper(e)
            start += PER_PAGE
            if start >= min(total, MAX_OFFSET):
                break
