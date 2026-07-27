"""Web of Science connector (activatable; unused in published results).

Same rationale as :mod:`sred.sources.scopus`: SRED's headline results use only
sources reachable without a subscription, and this connector exists so that a
subscribing institution can quantify what Clarivate's index adds.

Targets the **Web of Science Starter API**, which most institutional
subscriptions include and which returns the metadata SRED needs. The Expanded
API returns richer author affiliations and full citation networks; if you have
it, set ``WOS_API_FLAVOUR=expanded``.

Activate with ``WOS_API_KEY`` and add ``wos`` to ``01_harvest.py --sources``.
Clarivate's terms prohibit redistribution of retrieved records, so WoS-sourced
rows are excluded from `data/releases/` and participate only in the local
coverage comparison.
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

STARTER = "https://api.clarivate.com/apis/wos-starter/v1/documents"
EXPANDED = "https://wos-api.clarivate.com/api/wos"
PER_PAGE = 50


class WosNotConfigured(RuntimeError):
    """Raised when a Web of Science harvest is requested without credentials."""


def _headers() -> dict[str, str]:
    key = os.environ.get("WOS_API_KEY")
    if not key:
        raise WosNotConfigured(
            "WOS_API_KEY is not set. SRED's published results do not use Web of "
            "Science; set the key only if you are running the commercial-coverage "
            "comparison described in docs/methods.md.")
    return {"X-ApiKey": key, "Accept": "application/json"}


def build_query(terms: list[str], year: int, field: str = "TI") -> str:
    """Web of Science Advanced Search string. ``TI`` = title, ``TS`` = topic."""
    clause = " OR ".join(f'{field}=("{t}")' for t in terms)
    return f"({clause}) AND PY=({year}) AND DT=(Article OR Review)"


def _doc_to_paper(d: dict) -> Paper:
    now = datetime.now(timezone.utc).isoformat()
    src = d.get("source") or {}
    names = ((d.get("names") or {}).get("authors")) or []
    authors = [{"name": a.get("displayName") or a.get("wosStandard"),
                "orcid": a.get("researcherId"), "affiliation": None,
                "position": i + 1}
               for i, a in enumerate(names) if a.get("displayName") or a.get("wosStandard")]

    ids = d.get("identifiers") or {}
    year = src.get("publishYear")
    try:
        year = int(year) if year else None
    except (TypeError, ValueError):
        year = None

    return Paper(
        source="wos",
        source_id=d.get("uid") or "",
        doi=normalize_doi(ids.get("doi")),
        pmid=str(ids.get("pmid")).replace("MEDLINE:", "") if ids.get("pmid") else None,
        title=((d.get("title") or {}).get("value")
               if isinstance(d.get("title"), dict) else d.get("title")) or "",
        abstract="",   # not returned by the Starter API
        journal_raw=src.get("sourceTitle") or "",
        issn_l=ids.get("issn") or ids.get("eissn"),
        year=year,
        pub_date=src.get("publishMonth"),
        volume=src.get("volume"),
        issue=src.get("issue"),
        pages=((src.get("pages") or {}).get("range")
               if isinstance(src.get("pages"), dict) else None),
        doc_type_raw="; ".join(d.get("types") or []),
        n_authors=len(authors),
        authors=authors,
        keywords=((d.get("keywords") or {}).get("authorKeywords")) or [],
        cited_by_count=next((c.get("count") for c in (d.get("citations") or [])
                             if c.get("db") == "WOS"), None),
        citation_source="wos",
        url=(d.get("links") or {}).get("record"),
        harvest_ts=now,
    )


def harvest(terms: list[str], years: range, mailto: str = "",
            field: str = "TI") -> Iterator[Paper]:
    headers = _headers()
    db = os.environ.get("WOS_DB", "WOS")
    for year in years:
        query = build_query(terms, year, field)
        page, total = 1, None
        while True:
            params = {"db": db, "q": query, "limit": str(PER_PAGE), "page": str(page)}
            url = f"{STARTER}?{urllib.parse.urlencode(params)}"
            data = get_json(url, headers=headers, mailto=mailto)
            if total is None:
                total = int((data.get("metadata") or {}).get("total") or 0)
                log.info("wos %d: %d records", year, total)
            hits = data.get("hits") or []
            if not hits:
                break
            for h in hits:
                yield _doc_to_paper(h)
            if page * PER_PAGE >= total:
                break
            page += 1
