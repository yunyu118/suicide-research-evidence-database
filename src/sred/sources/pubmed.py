"""PubMed / NCBI E-utilities connector.

PubMed is SRED's controlled-vocabulary spine. Unlike social work, suicide
research has a mature MeSH tree (Suicide, Suicidal Ideation, Self-Injurious
Behavior), which lets us define the topical corpus with an indexed vocabulary
rather than free-text alone. We additionally harvest MeSH descriptors and
PublicationType, which serve as the metadata channel of SRED's hybrid
classifier and as the gold-standard anchor for classifier validation.

Strategy
--------
1. ESearch with `usehistory=y` to place the full result set on the NCBI
   history server, avoiding the 10,000-record retstart ceiling.
2. EFetch in batches of 200 against the WebEnv/QueryKey, in XML.
3. Parse to the canonical SRED schema.

Year-sliced queries are used so that a failure mid-harvest costs at most one
year of work and so that each slice stays comfortably inside NCBI limits.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import datetime, timezone

from ..http import get_text
from ..schema import Paper, normalize_doi

log = logging.getLogger(__name__)

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Document types PubMed labels that are not primary scientific communication.
NON_SCIENTIFIC_PT = {
    "Editorial", "Letter", "Comment", "Published Erratum", "Retraction of Publication",
    "Retracted Publication", "News", "Newspaper Article", "Biography", "Obituary",
    "Bibliography", "Directory", "Interview", "Video-Audio Media", "Webcasts",
    "Portrait", "Historical Article", "Congress", "Legal Case", "Patient Education Handout",
}

# PublicationType -> methodology hint, used by the metadata classifier.
PT_METHOD_HINTS = {
    "Randomized Controlled Trial": "quantitative",
    "Clinical Trial": "quantitative",
    "Controlled Clinical Trial": "quantitative",
    "Clinical Trial, Phase I": "quantitative",
    "Clinical Trial, Phase II": "quantitative",
    "Clinical Trial, Phase III": "quantitative",
    "Pragmatic Clinical Trial": "quantitative",
    "Observational Study": "quantitative",
    "Multicenter Study": "quantitative",
    "Comparative Study": "quantitative",
    "Twin Study": "quantitative",
    "Validation Study": "quantitative",
    "Evaluation Study": "quantitative",
    "Meta-Analysis": "review",
    "Systematic Review": "review",
    "Scoping Review": "review",
    "Review": "review",
    "Qualitative Research": "qualitative",
}


def build_query(cfg: dict) -> str:
    """Compose the PubMed topical query from config/query_terms.yml."""
    pm = cfg["pubmed"]
    mesh = " OR ".join(f'"{t}"[MeSH Terms]' for t in pm["mesh_terms"])
    tiab = " OR ".join(f'"{t}"[Title/Abstract]' for t in pm["title_abstract_terms"])
    return f"(({mesh}) OR ({tiab}))"


def esearch_year(query: str, year: int, api_key: str = "", mailto: str = "") -> tuple[str, str, int]:
    """Run ESearch for one publication year. Returns (WebEnv, QueryKey, count)."""
    params = {
        "db": "pubmed",
        "term": query,
        "usehistory": "y",
        "retmax": "0",
        "datetype": "pdat",
        "mindate": str(year),
        "maxdate": str(year),
        "tool": "SRED",
        "email": mailto,
    }
    if api_key:
        params["api_key"] = api_key
    url = f"{EUTILS}/esearch.fcgi?" + urllib.parse.urlencode(params)
    xml = get_text(url, mailto=mailto)
    root = ET.fromstring(xml)
    count = int(root.findtext("Count") or 0)
    return root.findtext("WebEnv") or "", root.findtext("QueryKey") or "", count


def efetch_batch(webenv: str, query_key: str, retstart: int, retmax: int,
                 api_key: str = "", mailto: str = "") -> str:
    params = {
        "db": "pubmed", "WebEnv": webenv, "query_key": query_key,
        "retstart": str(retstart), "retmax": str(retmax),
        "retmode": "xml", "tool": "SRED", "email": mailto,
    }
    if api_key:
        params["api_key"] = api_key
    return get_text(f"{EUTILS}/efetch.fcgi?" + urllib.parse.urlencode(params), mailto=mailto)


# ---------------------------------------------------------------------------
# XML parsing
# ---------------------------------------------------------------------------

# MeSH descriptors that mark suicide/self-harm as a principal subject.
SUICIDE_MESH = {
    "Suicide", "Suicide, Attempted", "Suicide, Completed", "Suicidal Ideation",
    "Suicide Prevention", "Self-Injurious Behavior", "Self Mutilation",
    "Assisted Suicide", "Suicide, Assisted",
}

_TITLE_FOCUS = re.compile(
    r"\bsuicid|self[-\s]?harm|self[-\s]?injur|parasuicide|self[-\s]?poison|"
    r"\bNSSI\b|self[-\s]?destructive|self[-\s]?mutilat", re.I)


def classify_focus(title: str, mesh_major: list[str]) -> str:
    """Focused vs peripheral topical relevance.

    A record is *focused* when suicide/self-harm is a principal subject:
    either it appears in the title, or NLM flagged a suicide MeSH descriptor
    as a major topic. Otherwise the record merely *mentions* suicide (e.g. a
    depression trial reporting suicidal ideation as one of many outcomes) and
    is *peripheral*. SRED's primary analytic corpus is the focused set; the
    peripheral set is retained and reported separately.
    """
    if _TITLE_FOCUS.search(title or ""):
        return "focused"
    if any(m in SUICIDE_MESH for m in mesh_major):
        return "focused"
    return "peripheral"


def _text(el: ET.Element | None) -> str:
    """Flatten an element's text including inline markup (<i>, <sup>, ...)."""
    if el is None:
        return ""
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def _abstract(article: ET.Element) -> str:
    """Reassemble structured abstracts, preserving section labels."""
    node = article.find(".//Abstract")
    if node is None:
        return ""
    parts: list[str] = []
    for seg in node.findall("AbstractText"):
        label = seg.get("Label") or seg.get("NlmCategory") or ""
        body = _text(seg)
        if not body:
            continue
        parts.append(f"{label.strip().title()}: {body}" if label else body)
    return " ".join(parts).strip()


def _pubdate(article: ET.Element) -> tuple[int | None, str | None]:
    """Best available publication date. Prefers electronic, falls back to journal."""
    for path in (".//ArticleDate", ".//Journal/JournalIssue/PubDate",
                 ".//PubMedPubDate[@PubStatus='pubmed']"):
        node = article.find(path)
        if node is None:
            continue
        y = node.findtext("Year")
        if not y:
            # MedlineDate e.g. "1998 Nov-Dec" or "1999-2000"
            md = node.findtext("MedlineDate") or ""
            m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", md)
            if not m:
                continue
            return int(m.group(1)), m.group(1)
        mo = (node.findtext("Month") or "01")[:3]
        months = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05",
                  "Jun": "06", "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10",
                  "Nov": "11", "Dec": "12"}
        mo = months.get(mo, mo if mo.isdigit() else "01").zfill(2)
        d = (node.findtext("Day") or "01").zfill(2)
        return int(y), f"{y}-{mo}-{d}"
    return None, None


def parse_efetch(xml: str) -> Iterator[Paper]:
    """Yield :class:`Paper` records from a PubmedArticleSet XML payload."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        log.error("efetch XML parse failure: %s", e)
        return

    now = datetime.now(timezone.utc).isoformat()

    for rec in root.iter("PubmedArticle"):
        art = rec.find(".//Article")
        if art is None:
            continue

        pmid = rec.findtext(".//PMID") or ""
        year, pdate = _pubdate(rec)

        doi = None
        for aid in rec.iterfind(".//ArticleId"):
            if aid.get("IdType") == "doi":
                doi = normalize_doi(_text(aid))
        if not doi:
            for eloc in art.iterfind("ELocationID"):
                if eloc.get("EIdType") == "doi":
                    doi = normalize_doi(_text(eloc))

        # Authors
        authors: list[dict] = []
        affs: list[str] = []
        for i, a in enumerate(art.iterfind(".//AuthorList/Author")):
            last, fore = a.findtext("LastName"), a.findtext("ForeName")
            coll = a.findtext("CollectiveName")
            name = coll if coll else " ".join(x for x in (fore, last) if x)
            if not name:
                continue
            orcid = None
            for ident in a.iterfind("Identifier"):
                if ident.get("Source") == "ORCID":
                    orcid = re.sub(r"^.*?(\d{4}-\d{4}-\d{4}-[\dXx]{4}).*$", r"\1", _text(ident))
            aff = [_text(x) for x in a.iterfind(".//Affiliation")]
            affs.extend(aff)
            authors.append({"name": name, "orcid": orcid,
                            "affiliation": aff[0] if aff else None, "position": i + 1})

        pub_types = [_text(pt) for pt in art.iterfind(".//PublicationTypeList/PublicationType")]

        # MeSH descriptors, split by major-topic status. A descriptor flagged
        # MajorTopicYN="Y" (on the descriptor or any of its qualifiers) means
        # NLM indexers judged it a *principal* subject of the paper. This is
        # the controlled-vocabulary analogue of a title-based topical screen
        # and is what SRED uses to separate focused from peripheral records.
        mesh: list[str] = []
        mesh_major: list[str] = []
        for mh in rec.iterfind(".//MeshHeadingList/MeshHeading"):
            dn = mh.find("DescriptorName")
            if dn is None:
                continue
            name = _text(dn)
            mesh.append(name)
            is_major = dn.get("MajorTopicYN") == "Y" or any(
                q.get("MajorTopicYN") == "Y" for q in mh.iterfind("QualifierName"))
            if is_major:
                mesh_major.append(name)
        kw = [_text(k) for k in rec.iterfind(".//KeywordList/Keyword")]
        funders = sorted({_text(g.find("Agency")) for g in rec.iterfind(".//GrantList/Grant")
                          if g.find("Agency") is not None})

        journal = art.find("Journal")
        issn_l = None
        if journal is not None:
            for iss in journal.iterfind("ISSN"):
                issn_l = _text(iss)
                if iss.get("IssnType") == "Print":
                    break

        pag = art.findtext(".//Pagination/MedlinePgn") or art.findtext(".//Pagination/StartPage")

        yield Paper(
            source="pubmed",
            source_id=pmid,
            pmid=pmid,
            doi=doi,
            title=_text(art.find("ArticleTitle")),
            abstract=_abstract(rec),
            journal_raw=_text(journal.find("Title")) if journal is not None else "",
            issn_l=issn_l,
            year=year,
            pub_date=pdate,
            volume=art.findtext(".//JournalIssue/Volume"),
            issue=art.findtext(".//JournalIssue/Issue"),
            pages=pag,
            doc_type_raw="; ".join(pub_types),
            language=art.findtext(".//Language"),
            n_authors=len(authors),
            authors=authors,
            affiliations_raw=sorted(set(affs)),
            funders=funders,
            mesh_terms=mesh,
            mesh_major_terms=mesh_major,
            topic_focus=classify_focus(_text(art.find("ArticleTitle")), mesh_major),
            keywords=kw,
            retracted=any("Retract" in p for p in pub_types),
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
            harvest_ts=now,
        )


def harvest(cfg: dict, years: range, api_key: str = "", mailto: str = "",
            batch: int = 200) -> Iterator[Paper]:
    """Harvest the full PubMed topical corpus, one publication year at a time."""
    query = build_query(cfg)
    for year in years:
        webenv, qkey, count = esearch_year(query, year, api_key, mailto)
        log.info("pubmed %d: %d records", year, count)
        if not count:
            continue
        for start in range(0, count, batch):
            xml = efetch_batch(webenv, qkey, start, batch, api_key, mailto)
            yielded = 0
            for paper in parse_efetch(xml):
                yielded += 1
                yield paper
            if yielded == 0:
                log.warning("pubmed %d offset %d returned 0 parsed records", year, start)
