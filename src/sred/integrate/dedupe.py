"""Stage 2 - Cross-source deduplication.

The same article reaches SRED from up to three channels (PubMed topical,
OpenAlex topical, OpenAlex venue). Naive concatenation would inflate every
count in the paper, so records are collapsed to one canonical row per work.

Matching cascade, strongest evidence first:

1. **DOI** - unambiguous when present. Coverage is high post-2000 and poor
   before, which is exactly why the later stages exist.
2. **PMID** - unambiguous within MEDLINE-indexed literature.
3. **Blocked fuzzy title match** - for records with neither identifier.
   Candidate pairs are blocked on (publication year, first significant title
   token) so the comparison is O(n) rather than O(n^2), then scored with
   Levenshtein-based token-sort ratio. Pairs at or above ``AUTO_ACCEPT`` are
   merged; pairs in the ``REVIEW_BAND`` are written to a review file rather
   than silently merged or silently kept apart.

Merging is field-wise and provenance-aware: when two sources disagree, the
value is taken from the source with the better track record for that field
(see :data:`FIELD_PRIORITY`) rather than arbitrarily by arrival order.
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from collections import defaultdict
from typing import Any, Iterable

from rapidfuzz import fuzz

log = logging.getLogger(__name__)

AUTO_ACCEPT = 90.0        # >= merge automatically (Perron et al. used 90%)
REVIEW_BAND = (80.0, 90.0)  # flagged for manual review

# Which source is authoritative for which field, best first.
FIELD_PRIORITY: dict[str, list[str]] = {
    "abstract": ["pubmed", "openalex"],          # PubMed abstracts are cleaner
    "mesh_terms": ["pubmed", "openalex"],
    "mesh_major_terms": ["pubmed", "openalex"],
    "doc_type_raw": ["pubmed", "openalex"],
    "funders": ["pubmed", "openalex"],
    "cited_by_count": ["openalex", "pubmed"],    # only OpenAlex supplies these
    "authors": ["openalex", "pubmed"],           # OpenAlex carries ORCID + institutions
    "affiliations_raw": ["openalex", "pubmed"],
    "countries": ["openalex", "pubmed"],
    "is_oa": ["openalex", "pubmed"],
    "publisher": ["openalex", "pubmed"],
    "issn_l": ["openalex", "pubmed"],
    "references_count": ["openalex", "pubmed"],
}

_PUNCT = re.compile(r"[^a-z0-9\s]")
_WS = re.compile(r"\s+")
_TITLE_STOP = {"the", "a", "an", "of", "and", "in", "on", "for", "to", "with"}


def title_norm(t: str) -> str:
    """Normalise a title for comparison: fold accents, strip markup and punctuation."""
    if not t:
        return ""
    s = unicodedata.normalize("NFKD", t)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"<[^>]+>", " ", s)          # stray HTML/MathML from publishers
    s = s.replace("&", " and ")             # "self-harm & suicide" == "... and ..."
    s = _PUNCT.sub(" ", s)
    return _WS.sub(" ", s).strip()


def block_key(rec: dict) -> str:
    """Blocking key: publication year + first significant title token.

    Blocking is what makes fuzzy matching tractable. A year-only block is too
    coarse (thousands of comparisons per block); adding the first significant
    token cuts block sizes by roughly two orders of magnitude while keeping
    recall high, because a title's opening content word is rarely the thing
    that differs between two records of the same paper.
    """
    t = title_norm(rec.get("title") or "")
    toks = [w for w in t.split() if w not in _TITLE_STOP and len(w) > 2]
    first = toks[0][:6] if toks else "_"
    y = rec.get("year") or 0
    return f"{y}|{first}"


def _sig(rec: dict) -> str:
    """Stable hash used to assign sred_id when no external identifier exists."""
    basis = f"{title_norm(rec.get('title') or '')}|{rec.get('year')}|{(rec.get('journal_raw') or '').lower()}"
    return hashlib.sha1(basis.encode()).hexdigest()[:16]


def assign_sred_id(rec: dict) -> str:
    if rec.get("doi"):
        return "doi:" + rec["doi"]
    if rec.get("pmid"):
        return "pmid:" + str(rec["pmid"])
    return "sig:" + _sig(rec)


# ---------------------------------------------------------------------------

def _first_author_key(rec: dict) -> str:
    authors = rec.get("authors") or []
    if isinstance(authors, str):
        return ""
    for a in authors:
        if isinstance(a, dict) and a.get("name"):
            parts = title_norm(a["name"]).split()
            return parts[-1] if parts else ""
    return ""


def _corroborated(a: dict, b: dict) -> bool:
    """Second-signal check before merging two records on title similarity alone.

    Accepts if either the venue or the first author agrees. An identical
    ISSN, a near-identical journal string, or a shared first-author surname
    each make it overwhelmingly likely that two same-year, same-title records
    are the same work. Records with no venue and no author information on
    either side are given the benefit of the doubt, because withholding the
    merge there would leave obvious duplicates in the corpus.
    """
    ia, ib = a.get("issn_l"), b.get("issn_l")
    if ia and ib:
        return ia == ib
    ja, jb = title_norm(a.get("journal_raw") or ""), title_norm(b.get("journal_raw") or "")
    if ja and jb:
        return fuzz.token_sort_ratio(ja, jb) >= 88
    fa, fb = _first_author_key(a), _first_author_key(b)
    if fa and fb:
        return fa == fb
    return True


def _merge_pair(base: dict, other: dict) -> dict:
    """Merge ``other`` into ``base`` using per-field source priority."""
    out = dict(base)
    sources = {base.get("source"): base, other.get("source"): other}
    out["source"] = "+".join(sorted({s for s in sources if s}))
    out.setdefault("source_ids", {})
    for r in (base, other):
        if r.get("source") and r.get("source_id"):
            out["source_ids"][r["source"]] = r["source_id"]

    for fld, prio in FIELD_PRIORITY.items():
        chosen = None
        for src in prio:
            cand = sources.get(src)
            if cand is None:
                continue
            v = cand.get(fld)
            if v not in (None, "", [], {}, 0):
                chosen = v
                break
        if chosen is None:
            chosen = base.get(fld) or other.get(fld)
        out[fld] = chosen

    # Scalars: prefer any non-empty value.
    for fld in ("doi", "pmid", "title", "journal_raw", "year", "pub_date",
                "volume", "issue", "pages", "language", "url", "keywords"):
        if not out.get(fld):
            out[fld] = base.get(fld) or other.get(fld)

    # Flags: OR them.
    out["retracted"] = bool(base.get("retracted")) or bool(other.get("retracted"))

    # Venue tier: a core-journal assignment always wins over "dispersed".
    tiers = {base.get("venue_tier"), other.get("venue_tier")}
    for t in ("core_a", "adjacent_b", "dispersed"):
        if t in tiers:
            out["venue_tier"] = t
            break

    # Topic focus: "focused" wins; a venue-channel record inherits focus from
    # its topical twin if it has one.
    foci = {base.get("topic_focus"), other.get("topic_focus")}
    out["topic_focus"] = "focused" if "focused" in foci else (
        "peripheral" if "peripheral" in foci else next(iter(foci - {None}), None))

    out["n_authors"] = max(base.get("n_authors") or 0, other.get("n_authors") or 0)
    return out


def deduplicate(records: Iterable[dict]) -> tuple[list[dict], dict[str, Any]]:
    """Collapse a record stream to unique works.

    Returns ``(deduped_records, report)``. The report carries per-stage counts
    and the list of pairs that landed in the review band, so the manuscript can
    state exactly how many merges were automatic versus flagged.
    """
    by_id: dict[str, dict] = {}
    stats = Counter_ = {"input": 0, "doi_merge": 0, "pmid_merge": 0,
                        "fuzzy_merge": 0, "review_flagged": 0}
    review_pairs: list[dict] = []

    # --- Pass 1: identifier-based collapse (DOI, then PMID) ---------------
    pmid_index: dict[str, str] = {}
    for rec in records:
        stats["input"] += 1
        key = None
        if rec.get("doi"):
            key = "doi:" + rec["doi"]
        elif rec.get("pmid"):
            key = "pmid:" + str(rec["pmid"])

        if key and key in by_id:
            by_id[key] = _merge_pair(by_id[key], rec)
            stats["doi_merge" if key.startswith("doi:") else "pmid_merge"] += 1
            continue

        if key is None:
            key = "sig:" + _sig(rec)
            if key in by_id:
                by_id[key] = _merge_pair(by_id[key], rec)
                stats["fuzzy_merge"] += 1
                continue

        rec = dict(rec)
        rec["sred_id"] = key
        by_id[key] = rec

        # A DOI-keyed record also claims its PMID, so a PubMed-only record of
        # the same work merges instead of surviving as a duplicate.
        if rec.get("pmid"):
            pm = "pmid:" + str(rec["pmid"])
            if pm != key:
                prior = pmid_index.get(pm)
                if prior and prior in by_id and prior != key:
                    by_id[key] = _merge_pair(by_id[key], by_id.pop(prior))
                    stats["pmid_merge"] += 1
                pmid_index[pm] = key

    # Second sweep: PubMed-only rows whose PMID is already claimed by a
    # DOI-keyed row.
    for pm_key in [k for k in by_id if k.startswith("pmid:")]:
        owner = pmid_index.get(pm_key)
        if owner and owner in by_id and owner != pm_key:
            by_id[owner] = _merge_pair(by_id[owner], by_id.pop(pm_key))
            stats["pmid_merge"] += 1

    log.info("identifier pass: %d input -> %d records", stats["input"], len(by_id))

    # --- Pass 2: blocked fuzzy title matching for identifier-less rows ----
    blocks: dict[str, list[str]] = defaultdict(list)
    for k, rec in by_id.items():
        blocks[block_key(rec)].append(k)

    merged_away: set[str] = set()
    for bkey, keys in blocks.items():
        if len(keys) < 2 or len(keys) > 400:   # skip degenerate mega-blocks
            continue
        for i in range(len(keys)):
            ki = keys[i]
            if ki in merged_away:
                continue
            ti = title_norm(by_id[ki].get("title") or "")
            if len(ti) < 15:
                continue
            for j in range(i + 1, len(keys)):
                kj = keys[j]
                if kj in merged_away:
                    continue
                a, b = by_id[ki], by_id[kj]
                # Records carrying conflicting persistent identifiers are
                # different works, however similar their titles.
                if a.get("doi") and b.get("doi") and a["doi"] != b["doi"]:
                    continue
                if a.get("pmid") and b.get("pmid") and str(a["pmid"]) != str(b["pmid"]):
                    continue
                tj = title_norm(b.get("title") or "")
                if len(tj) < 15:
                    continue
                score = fuzz.token_sort_ratio(ti, tj)
                # A matching title alone is not sufficient. Editorials,
                # commentaries, and conference abstracts reuse titles across
                # venues, and generic titles recur within a year. Require
                # corroboration from the venue or the author list before
                # collapsing two records into one.
                if score >= AUTO_ACCEPT and not _corroborated(a, b):
                    stats["review_flagged"] += 1
                    if len(review_pairs) < 5000:
                        review_pairs.append({
                            "score": round(score, 1), "block": bkey,
                            "reason": "title_match_without_corroboration",
                            "a": {"sred_id": ki, "title": a.get("title"),
                                  "journal": a.get("journal_raw"), "year": a.get("year")},
                            "b": {"sred_id": kj, "title": b.get("title"),
                                  "journal": b.get("journal_raw"), "year": b.get("year")},
                        })
                    continue
                if score >= AUTO_ACCEPT:
                    by_id[ki] = _merge_pair(by_id[ki], by_id[kj])
                    merged_away.add(kj)
                    stats["fuzzy_merge"] += 1
                elif REVIEW_BAND[0] <= score < REVIEW_BAND[1]:
                    stats["review_flagged"] += 1
                    if len(review_pairs) < 5000:
                        review_pairs.append({
                            "score": round(score, 1), "block": bkey,
                            "a": {"sred_id": ki, "title": by_id[ki].get("title"),
                                  "journal": by_id[ki].get("journal_raw"),
                                  "year": by_id[ki].get("year")},
                            "b": {"sred_id": kj, "title": by_id[kj].get("title"),
                                  "journal": by_id[kj].get("journal_raw"),
                                  "year": by_id[kj].get("year")},
                        })

    for k in merged_away:
        by_id.pop(k, None)

    out = list(by_id.values())
    report = {
        "input_records": stats["input"],
        "output_records": len(out),
        "duplicates_removed": stats["input"] - len(out),
        "doi_merges": stats["doi_merge"],
        "pmid_merges": stats["pmid_merge"],
        "fuzzy_merges": stats["fuzzy_merge"],
        "review_band_flagged": stats["review_flagged"],
        "auto_accept_threshold": AUTO_ACCEPT,
        "review_band": list(REVIEW_BAND),
        "review_pairs_sample": review_pairs[:500],
    }
    log.info("dedup: %d -> %d (%d removed; %d doi, %d pmid, %d fuzzy, %d flagged)",
             stats["input"], len(out), report["duplicates_removed"],
             stats["doi_merge"], stats["pmid_merge"], stats["fuzzy_merge"],
             stats["review_flagged"])
    return out, report
