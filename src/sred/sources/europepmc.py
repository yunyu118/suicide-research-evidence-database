"""Europe PMC connector.

Europe PMC is SRED's third independent channel and it earns its place for
three reasons:

1. **No request budget.** OpenAlex enforces a hard daily credit ceiling, which
   makes it unsuitable as a sole backbone for a 100k-record harvest. Europe
   PMC imposes only a politeness rate limit, so the corpus can be rebuilt from
   scratch on demand - a precondition for the reproducibility claim SRED makes.
2. **Coverage beyond MEDLINE.** Europe PMC unions MEDLINE with PubMed Central,
   preprint servers (PPR), Agricola, and patent literature, so it surfaces
   suicide scholarship - particularly preprints and non-indexed regional
   journals - that a PubMed-only harvest misses.
3. **An independent citation count** (``citedByCount``), which lets SRED
   triangulate citation impact across two open sources rather than trusting
   one, and quantify how far they disagree.

Pagination uses ``cursorMark``, which is stable under concurrent index
updates; ``page``-based paging is not, and silently drops records on a corpus
this size.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Iterator

from ..http import get_json
from ..schema import Paper, normalize_doi
from .pubmed import classify_focus

log = logging.getLogger(__name__)

API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
PAGE_SIZE = 100   # `core` resultType payloads are large; 100 keeps them sane

NON_SCIENTIFIC_PT = {
    "editorial", "letter", "comment", "published erratum", "news",
    "newspaper article", "biography", "obituary", "bibliography",
    "historical article", "congress", "interview", "retraction of publication",
}


def build_query(terms: list[str], start_year: int, end_year: int,
                field: str = "TITLE", require_abstract: bool = True) -> str:
    """Compose a Europe PMC query string.

    ``field`` is ``TITLE`` for the precision-oriented delineation SRED uses as
    its primary definition, or ``ABSTRACT``/``TITLE_ABS`` for recall analyses.
    """
    clause = " OR ".join(f'{field}:"{t}"' for t in terms)
    q = f"({clause}) AND (PUB_YEAR:[{start_year} TO {end_year}])"
    if require_abstract:
        q += " AND (HAS_ABSTRACT:Y)"
    return q


def _search(query: str, cursor: str, mailto: str) -> dict:
    params = {
        "query": query, "format": "json", "pageSize": str(PAGE_SIZE),
        "resultType": "core", "cursorMark": cursor, "email": mailto,
    }
    return get_json(f"{API}?{urllib.parse.urlencode(params)}", mailto=mailto)


def _authors(rec: dict) -> tuple[list[dict], list[str]]:
    authors, affs = [], []
    lst = ((rec.get("authorList") or {}).get("author")) or []
    for i, a in enumerate(lst):
        name = a.get("fullName") or a.get("collectiveName") or ""
        if not name:
            first, last = a.get("firstName"), a.get("lastName")
            name = " ".join(x for x in (first, last) if x)
        if not name:
            continue
        aff_list = [x.get("affiliation") for x in
                    ((a.get("authorAffiliationDetailsList") or {}).get("authorAffiliation") or [])
                    if x.get("affiliation")]
        if a.get("affiliation"):
            aff_list.append(a["affiliation"])
        affs.extend(aff_list)
        orcid = ((a.get("authorId") or {}).get("value")
                 if (a.get("authorId") or {}).get("type") == "ORCID" else None)
        authors.append({"name": name, "orcid": orcid,
                        "affiliation": aff_list[0] if aff_list else None,
                        "position": i + 1})
    return authors, affs


def to_paper(rec: dict) -> Paper:
    now = datetime.now(timezone.utc).isoformat()
    ji = rec.get("journalInfo") or {}
    journal = (ji.get("journal") or {})
    authors, affs = _authors(rec)

    pub_types = [str(t).lower() for t in
                 ((rec.get("pubTypeList") or {}).get("pubType") or [])]
    kw = list((rec.get("keywordList") or {}).get("keyword") or [])

    year = rec.get("pubYear")
    try:
        year = int(year) if year else None
    except (TypeError, ValueError):
        year = None

    title = (rec.get("title") or "").strip().rstrip(".")
    mesh_major = [m.get("descriptorName") for m in
                  ((rec.get("meshHeadingList") or {}).get("meshHeading") or [])
                  if m.get("majorTopic_YN") == "Y" and m.get("descriptorName")]

    return Paper(
        source="europepmc",
        source_id=str(rec.get("id") or ""),
        doi=normalize_doi(rec.get("doi")),
        pmid=str(rec.get("pmid")) if rec.get("pmid") else None,
        title=title,
        abstract=re.sub(r"<[^>]+>", " ", rec.get("abstractText") or "").strip(),
        journal_raw=(journal.get("title") or "").strip(),
        issn_l=journal.get("issn") or journal.get("essn"),
        year=year,
        pub_date=rec.get("firstPublicationDate") or rec.get("electronicPublicationDate"),
        volume=ji.get("volume"),
        issue=ji.get("issue"),
        pages=rec.get("pageInfo"),
        doc_type_raw="; ".join(pub_types),
        language=rec.get("language"),
        is_oa=(rec.get("isOpenAccess") == "Y"),
        n_authors=len(authors),
        authors=authors,
        affiliations_raw=sorted({a for a in affs if a}),
        mesh_major_terms=mesh_major,
        topic_focus=classify_focus(title, mesh_major),
        keywords=[k for k in kw if k],
        cited_by_count=rec.get("citedByCount"),
        citation_source="europepmc",
        url=(f"https://europepmc.org/article/{rec.get('source')}/{rec.get('id')}"
             if rec.get("source") and rec.get("id") else None),
        retracted=any("retract" in p for p in pub_types),
        harvest_ts=now,
    )


def harvest(terms: list[str], start_year: int, end_year: int,
            mailto: str = "", field: str = "TITLE",
            require_abstract: bool = True) -> Iterator[Paper]:
    """Harvest one year slice of the Europe PMC topical corpus."""
    query = build_query(terms, start_year, end_year, field, require_abstract)
    cursor, seen, guard = "*", 0, 0
    while True:
        data = _search(query, cursor, mailto)
        results = (data.get("resultList") or {}).get("result") or []
        if not results:
            return
        for r in results:
            seen += 1
            yield to_paper(r)
        nxt = data.get("nextCursorMark")
        if not nxt or nxt == cursor:
            log.info("europepmc %s-%s: %d records", start_year, end_year, seen)
            return
        cursor = nxt
        guard += 1
        if guard > 20000:  # pathological-loop backstop
            log.error("europepmc cursor guard tripped at %d records", seen)
            return
