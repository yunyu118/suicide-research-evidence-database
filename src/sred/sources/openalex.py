"""OpenAlex connector.

OpenAlex supplies two things PubMed cannot: (a) coverage of the
social-science and social-work suicide literature that is outside MEDLINE's
scope, and (b) an open citation graph, which is SRED's substitute for the
proprietary citation counts Perron et al. drew from Web of Science and
Crossref.

Two harvest channels are used:
  * `venue` - every work published in a core specialty journal (Tier A/B),
    filtered by ISSN. This is the venue-based half of SRED's hybrid design.
  * `topic` - works whose title or abstract matches the suicide term set,
    across all venues. This is the dispersed half.

OpenAlex stores abstracts as an inverted index for copyright reasons; we
reconstruct linear text from it.
"""

from __future__ import annotations

import logging
import urllib.parse
from collections.abc import Iterator
from datetime import datetime, timezone

from ..http import get_json
from ..schema import Paper, normalize_doi

log = logging.getLogger(__name__)

API = "https://api.openalex.org"
PER_PAGE = 200

# OpenAlex `type` values that are not primary scientific communication.
NON_SCIENTIFIC_TYPES = {
    "editorial", "letter", "erratum", "paratext", "peer-review", "grant",
    "retraction", "review-of-book", "book-review", "other", "libguides",
    "supplementary-materials",
}


def invert_abstract(inv: dict[str, list[int]] | None) -> str:
    """Reconstruct linear abstract text from OpenAlex's inverted index."""
    if not inv:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort(key=lambda t: t[0])
    return " ".join(w for _, w in positions).strip()


def _page(url: str, mailto: str) -> Iterator[dict]:
    """Cursor-paginate an OpenAlex endpoint, yielding raw work dicts."""
    cursor = "*"
    seen = 0
    while cursor:
        full = f"{url}&per-page={PER_PAGE}&cursor={urllib.parse.quote(cursor)}&mailto={mailto}"
        data = get_json(full, mailto=mailto)
        results = data.get("results", [])
        if not results:
            return
        for r in results:
            seen += 1
            yield r
        cursor = (data.get("meta") or {}).get("next_cursor")
        if seen and seen % 5000 == 0:
            log.info("openalex: %d records paged", seen)


def to_paper(w: dict, venue_tier: str = "dispersed",
             focus: str | None = None) -> Paper:
    """Map an OpenAlex Work to the canonical SRED schema."""
    now = datetime.now(timezone.utc).isoformat()
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}

    authors: list[dict] = []
    affs: list[str] = []
    countries: set[str] = set()
    for i, a in enumerate(w.get("authorships") or []):
        au = a.get("author") or {}
        name = au.get("display_name") or ""
        if not name:
            continue
        inst_names = [inst.get("display_name") for inst in (a.get("institutions") or [])
                      if inst.get("display_name")]
        affs.extend(inst_names)
        for inst in (a.get("institutions") or []):
            if inst.get("country_code"):
                countries.add(inst["country_code"])
        for c in (a.get("countries") or []):
            countries.add(c)
        orcid = (au.get("orcid") or "").replace("https://orcid.org/", "") or None
        authors.append({"name": name, "orcid": orcid,
                        "affiliation": inst_names[0] if inst_names else None,
                        "position": i + 1})

    ids = w.get("ids") or {}
    pmid = (ids.get("pmid") or "").rsplit("/", 1)[-1] or None

    kw = [k.get("display_name") for k in (w.get("keywords") or []) if k.get("display_name")]
    if not kw:
        kw = [c.get("display_name") for c in (w.get("concepts") or [])[:8]
              if c.get("display_name")]

    funders = sorted({(f.get("display_name") or f.get("funder_display_name"))
                      for f in (w.get("funders") or [])
                      if (f.get("display_name") or f.get("funder_display_name"))})

    return Paper(
        source="openalex",
        source_id=(w.get("id") or "").rsplit("/", 1)[-1],
        doi=normalize_doi(w.get("doi")),
        pmid=pmid,
        title=(w.get("display_name") or "").strip(),
        abstract=invert_abstract(w.get("abstract_inverted_index")),
        journal_raw=(src.get("display_name") or "").strip(),
        issn_l=src.get("issn_l"),
        publisher=src.get("host_organization_name"),
        year=w.get("publication_year"),
        pub_date=w.get("publication_date"),
        volume=(w.get("biblio") or {}).get("volume"),
        issue=(w.get("biblio") or {}).get("issue"),
        pages="-".join(x for x in [(w.get("biblio") or {}).get("first_page"),
                                   (w.get("biblio") or {}).get("last_page")] if x) or None,
        doc_type_raw=w.get("type"),
        language=w.get("language"),
        is_oa=(w.get("open_access") or {}).get("is_oa"),
        n_authors=len(authors),
        authors=authors,
        affiliations_raw=sorted(set(affs)),
        countries=sorted(countries),
        funders=funders,
        mesh_terms=[m.get("descriptor_name") for m in (w.get("mesh") or [])
                    if m.get("descriptor_name")],
        mesh_major_terms=[m.get("descriptor_name") for m in (w.get("mesh") or [])
                          if m.get("descriptor_name") and m.get("is_major_topic")],
        topic_focus=focus,
        keywords=[k for k in kw if k],
        references_count=w.get("referenced_works_count"),
        cited_by_count=w.get("cited_by_count"),
        citation_source="openalex",
        url=w.get("id"),
        retracted=bool(w.get("is_retracted")),
        venue_tier=venue_tier,
        harvest_ts=now,
    )


SELECT = ",".join([
    "id", "doi", "ids", "display_name", "publication_year", "publication_date",
    "type", "language", "primary_location", "open_access", "authorships",
    "cited_by_count", "biblio", "is_retracted", "abstract_inverted_index",
    "referenced_works_count", "concepts", "keywords", "mesh", "funders",
    "is_paratext", "topics", "counts_by_year",
])


def harvest_venue(issn_l: str, tier: str, start: str, end: str,
                  mailto: str = "") -> Iterator[Paper]:
    """All works published in one journal (venue-based channel)."""
    f = (f"locations.source.issn:{issn_l},"
         f"from_publication_date:{start},to_publication_date:{end}")
    url = f"{API}/works?filter={urllib.parse.quote(f, safe=':,')}&select={SELECT}"
    for w in _page(url, mailto):
        yield to_paper(w, venue_tier=tier)


def harvest_topic(terms: list[str], start: str, end: str, types: list[str],
                  mailto: str = "", year_slice: bool = True,
                  field: str = "title", require_abstract: bool = True) -> Iterator[Paper]:
    """Suicide-focused works across all venues (topical channel).

    ``field`` controls topic delineation:

    ``title``
        The suicide construct must appear in the **title**. This is the
        standard precision-oriented operationalisation of topical focus in
        bibliometrics: it identifies work *about* suicide rather than work
        that merely measures suicidality among many outcomes. This is SRED's
        primary analytic definition.
    ``title_and_abstract``
        Recall-oriented. Retrieves the peripheral literature as well and is
        used only for the coverage/sensitivity analysis, because roughly two
        thirds of its yield mentions suicide without studying it.

    OpenAlex limits deep pagination, so queries are sliced by publication
    year; each slice stays inside the limit and a failure costs one year.
    """
    q = " OR ".join(terms)
    y0, y1 = int(start[:4]), int(end[:4])
    spans = [(f"{y}-01-01", f"{y}-12-31") for y in range(y0, y1 + 1)] if year_slice \
        else [(start, end)]
    abstract_filter = ",has_abstract:true" if require_abstract else ""
    for s, e in spans:
        f = (f"{field}.search:{q},"
             f"type:{'|'.join(types)}{abstract_filter},"
             f"from_publication_date:{s},to_publication_date:{e}")
        url = f"{API}/works?filter={urllib.parse.quote(f, safe=':,|')}&select={SELECT}"
        n = 0
        for w in _page(url, mailto):
            n += 1
            yield to_paper(w, venue_tier="dispersed", focus="focused")
        log.info("openalex topic %s: %d records", s[:4], n)


def resolve_source(issn_or_title: str, mailto: str = "") -> dict | None:
    """Look up an OpenAlex source by ISSN, falling back to title search."""
    try:
        d = get_json(f"{API}/sources/issn:{issn_or_title}?mailto={mailto}", mailto=mailto)
        if d.get("id"):
            return d
    except Exception:  # noqa: BLE001
        pass
    try:
        d = get_json(
            f"{API}/sources?search={urllib.parse.quote(issn_or_title)}"
            f"&per-page=5&mailto={mailto}", mailto=mailto)
        for r in d.get("results", []):
            if r.get("type") == "journal":
                return r
    except Exception:  # noqa: BLE001
        pass
    return None
