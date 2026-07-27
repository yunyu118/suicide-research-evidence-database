"""NIH iCite connector - citation enrichment.

Roughly half the SRED corpus reaches us through PubMed alone, and PubMed
supplies no citation counts. Leaving those records blank would restrict every
citation analysis to the subset of the literature that happens to be indexed
in OpenAlex or Europe PMC - a subset that is systematically biased toward
better-indexed, higher-profile venues, which is precisely the bias the citation
analysis is trying to measure.

NIH's iCite closes the gap. It is free, unauthenticated, unmetered, accepts
1,000 PMIDs per request, and covers every MEDLINE record.

It also supplies something the raw counts cannot: the **Relative Citation Ratio
(RCR)**, a field- and time-normalised measure of influence benchmarked against
the co-citation network of each article [@hutchins2016]. Raw citation counts
are close to uninterpretable across a corpus like this one, where a 1991
psychological autopsy study and a 2021 machine-learning paper sit in the same
table: they differ in citation potential by an order of magnitude for reasons
having nothing to do with quality. RCR is scaled so that 1.0 is the NIH-funded
median, which makes cross-era and cross-subfield comparison meaningful.

Fields retrieved: citation_count, RCR, NIH percentile, expected citations per
year, field citation rate, clinical-article citation count, and the
human/animal/molecular-cellular research-level triple.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator

from ..http import get_json

log = logging.getLogger(__name__)

API = "https://icite.od.nih.gov/api/pubs"

# iCite documents a 1,000-PMID ceiling, but the endpoint is a GET and its
# gateway rejects long URLs with HTTP 413 well before that. 50 PMIDs keeps the
# URL under ~800 bytes, comfortably inside every proxy limit we have seen.
BATCH = 50

# `citations_per_year` and `cited_by_clin` are omitted deliberately: both return
# nested arrays that inflate the response by an order of magnitude, and neither
# is used in the analysis. Clinical-citation *counts* come from the summary
# fields instead.
FIELDS = [
    "pmid", "year", "citation_count", "relative_citation_ratio",
    "nih_percentile", "expected_citations_per_year", "field_citation_rate",
    "is_clinical", "is_research_article", "human", "animal",
    "molecular_cellular", "apt",
]


def _chunks(items: list[str], n: int) -> Iterator[list[str]]:
    for i in range(0, len(items), n):
        yield items[i:i + n]


def fetch(pmids: Iterable[str], mailto: str = "") -> dict[str, dict]:
    """Return ``{pmid: metrics}`` for every PMID iCite recognises.

    PMIDs absent from iCite (non-MEDLINE records, very recent deposits) are
    simply missing from the result. Callers must treat absence as "unknown",
    not as zero citations - conflating the two is how uncited-rate statistics
    get silently inflated.
    """
    ids = [str(p) for p in pmids if p]
    ids = list(dict.fromkeys(ids))          # de-dup, preserve order
    out: dict[str, dict] = {}
    if not ids:
        return out

    n_batches = (len(ids) + BATCH - 1) // BATCH
    for i, chunk in enumerate(_chunks(ids, BATCH), 1):
        url = (f"{API}?pmids={','.join(chunk)}"
               f"&fl={','.join(FIELDS)}&format=json")
        try:
            data = get_json(url, mailto=mailto)
        except Exception as e:  # noqa: BLE001
            # Halve the batch and retry rather than losing 50 records to one
            # oversized request. Two halves of a 413 batch almost always both
            # succeed; if they do not, the recursion bottoms out at singletons.
            log.warning("icite batch %d/%d failed (%s); splitting",
                        i, n_batches, str(e)[:100])
            if len(chunk) > 1:
                mid = len(chunk) // 2
                out.update(fetch(chunk[:mid], mailto=mailto))
                out.update(fetch(chunk[mid:], mailto=mailto))
            continue
        for rec in (data.get("data") or []):
            pmid = str(rec.get("pmid") or "")
            if pmid:
                out[pmid] = rec
        if i % 20 == 0 or i == n_batches:
            log.info("icite: %d/%d batches, %d records resolved",
                     i, n_batches, len(out))
    return out


def enrich(records: list[dict], mailto: str = "",
           overwrite: bool = False) -> tuple[list[dict], dict]:
    """Attach iCite metrics to records, filling citation gaps.

    ``overwrite=False`` (the default) fills only records with no citation count,
    preserving OpenAlex and Europe PMC values where they exist so that the
    provenance recorded in ``citation_source`` stays meaningful. RCR and the
    other normalised measures are attached to *every* matched record regardless,
    because no other source supplies them.
    """
    need = [r for r in records
            if r.get("pmid") and (overwrite or r.get("cited_by_count") is None)]
    all_pmids = [r["pmid"] for r in records if r.get("pmid")]
    log.info("icite: %d records carry a PMID, %d need a citation count",
             len(all_pmids), len(need))

    metrics = fetch(all_pmids, mailto=mailto)

    n_filled = n_rcr = 0
    for r in records:
        pmid = str(r.get("pmid") or "")
        m = metrics.get(pmid)
        if not m:
            continue
        cc = m.get("citation_count")
        if cc is not None and (overwrite or r.get("cited_by_count") is None):
            r["cited_by_count"] = int(cc)
            r["citation_source"] = "icite"
            n_filled += 1
        rcr = m.get("relative_citation_ratio")
        if rcr is not None:
            r["relative_citation_ratio"] = float(rcr)
            n_rcr += 1
        for src, dst in [("nih_percentile", "nih_percentile"),
                         ("field_citation_rate", "field_citation_rate"),
                         ("expected_citations_per_year", "expected_citations_per_year"),
                         ("cited_by_clin", "n_clinical_citations"),
                         ("is_clinical", "is_clinical"),
                         ("human", "research_level_human"),
                         ("animal", "research_level_animal"),
                         ("molecular_cellular", "research_level_molecular")]:
            if m.get(src) is not None:
                r[dst] = m[src]
        if isinstance(m.get("cited_by_clin"), list):
            r["n_clinical_citations"] = len(m["cited_by_clin"])

    report = {
        "pmids_submitted": len(all_pmids),
        "pmids_resolved": len(metrics),
        "citation_counts_filled": n_filled,
        "rcr_attached": n_rcr,
        "resolution_rate_pct": round(len(metrics) / max(len(all_pmids), 1) * 100, 2),
    }
    log.info("icite enrichment: %s", report)
    return records, report
