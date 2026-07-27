"""Composite training labels for distant supervision.

Why this module exists
----------------------
The first real build of SRED exposed a problem that a smaller pilot would have
hidden. NLM PublicationType tags supply excellent labels for *empirical* work -
"Randomized Controlled Trial", "Observational Study", "Meta-Analysis" - but
almost none for *non-empirical* work, because the tags that would signal it
("Editorial", "Comment", "Letter") are attached to items that usually have no
abstract and are therefore removed by the abstract requirement long before
classification. Training stage 2 on MEDLINE tags alone yields a single-class
problem: 15,004 positives and zero negatives.

Rather than abandon the stage or pretend a one-class model is a classifier,
SRED derives training labels from three evidence channels of declining
authority, records which channel produced each label, and validates on each
separately so the reader can discount the weaker ones.

Channel 1 - human MEDLINE indexing (highest authority)
    NLM PublicationType tags assigned by trained indexers.

Channel 2 - structured-abstract sections (high authority, positive class only)
    An abstract that carries explicit ``Methods:`` and ``Results:`` headings is
    reporting a study. Journals impose this structure precisely on empirical
    submissions, so the signal is close to definitional, and it is orthogonal
    to both the MeSH tags and the lexical rules.

Channel 3 - high-precision lexical rules (lowest authority)
    Conceptual and theoretical framing language ("this paper argues", "we
    propose a framework"), used for the negative class only where neither
    higher channel speaks and no empirical marker is present.

The point of separating them is not that channel 3 is unreliable in isolation -
it is reasonably precise - but that a label set is only as trustworthy as its
weakest component, and the reader is entitled to know which claims rest on
which. ``label_source_*`` fields carry that provenance through to the released
data.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any

log = logging.getLogger(__name__)

# Structured-abstract section headings. Matching is deliberately strict:
# heading-plus-colon at a word boundary, not the bare word, so that a sentence
# mentioning "methods" in prose does not count.
_METHODS = re.compile(r"\b(?:Methods?|Methodology|Design|Materials And Methods|"
                      r"Patients And Methods|Subjects And Methods|Procedure)\s*:", re.I)
_RESULTS = re.compile(r"\b(?:Results?|Findings)\s*:", re.I)
_OBJECTIVE = re.compile(r"\b(?:Objectives?|Aims?|Purpose|Background|Introduction)\s*:", re.I)

# Any of these in an abstract is near-conclusive evidence that data were
# analysed, and blocks assignment to the non-empirical class.
_EMPIRICAL_MARKER = re.compile(
    r"\bn\s*=\s*\d|\bp\s*[<>=]\s*0?\.\d|\b95%\s*(?:CI|confidence)|"
    r"\bodds ratio|\bhazard ratio|\bparticipants? were\b|"
    r"\bwe (?:interviewed|surveyed|recruited|enrolled)\b|"
    r"\bdata were (?:collected|analy[sz]ed)\b|\bsample of \d", re.I)


# --- narrative vs systematic review ----------------------------------------
# NLM's `Review` tag is the largest untapped label source in this corpus
# (roughly one record in ten), and it was initially discarded as ambiguous
# because it covers both systematic reviews (empirical evidence synthesis) and
# narrative reviews (non-empirical discussion). The ambiguity is resolvable:
# NLM applies *separate* tags for systematic reviews, meta-analyses, and
# scoping reviews, and systematic work almost always names its method in the
# abstract. A `Review` tag with neither signal is a narrative review, which is
# non-empirical under the Perron et al. definition. This single distinction
# supplies the majority of SRED's negative class for stage 2.
_SYSTEMATIC_TAGS = {"systematic review", "meta-analysis", "scoping review",
                    "network meta-analysis", "umbrella review"}

_SYSTEMATIC_TEXT = re.compile(
    r"\bsystematic(?:ally)? (?:review|search|literature search)\b|"
    r"\bmeta-?analy[sz]|\bPRISMA\b|\bscoping review\b|\bumbrella review\b|"
    r"\bwe searched (?:PubMed|MEDLINE|Embase|PsycINFO|Web of Science|Scopus|CINAHL)\b|"
    r"\b(?:studies|articles|records|trials) were (?:screened|included|identified|retrieved)\b|"
    r"\bpooled (?:effect|estimate|prevalence|odds|OR|risk)\b|"
    r"\binclusion (?:and exclusion )?criteria\b|\bPROSPERO\b|"
    r"\brisk of bias\b|\bheterogeneity was assessed\b", re.I)


def review_signal(doc_type_raw: str | None, abstract: str) -> str | None:
    """Classify a `Review`-tagged record as systematic or narrative.

    Returns ``'systematic'``, ``'narrative'``, or ``None`` when the record is
    not tagged as a review at all.
    """
    tags = {t.strip().lower() for t in
            (doc_type_raw or "").replace(",", ";").split(";") if t.strip()}
    if not tags & {"review"} and not tags & _SYSTEMATIC_TAGS:
        return None
    if tags & _SYSTEMATIC_TAGS:
        return "systematic"
    if _SYSTEMATIC_TEXT.search(abstract or ""):
        return "systematic"
    return "narrative"


def structured_abstract_signal(abstract: str) -> str | None:
    """Return ``'empirical'`` when an abstract is structured as a study report."""
    if not abstract or len(abstract) < 150:
        return None
    if _METHODS.search(abstract) and _RESULTS.search(abstract):
        return "empirical"
    return None


def _clean(v: Any) -> Any:
    """Normalise pandas' NaN back to None.

    Round-tripping records through Parquet turns every ``None`` into ``NaN``,
    and ``NaN`` is *truthy* - so a naive ``if rec.get("meta_methodology")``
    silently accepts tens of thousands of missing labels as real ones. The bug
    is invisible until a class literally named "nan" shows up in the label
    distribution, which is exactly how it was found.
    """
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, str) and v.strip().lower() in ("nan", "none", ""):
        return None
    return v


def composite_labels(rec: dict) -> dict[str, Any]:
    """Derive training labels and their provenance for one record.

    Adds ``label_is_scientific``, ``label_is_empirical``, ``label_methodology``
    and a ``label_source_*`` field for each. A label of ``None`` means no
    channel spoke, and the record is excluded from training for that stage
    rather than assigned a guessed class.
    """
    abstract = rec.get("abstract") or ""
    out: dict[str, Any] = {}

    meta_sci = _clean(rec.get("meta_is_scientific"))
    meta_meth = _clean(rec.get("meta_methodology"))
    rule_meth = _clean(rec.get("rule_methodology"))
    rule_sci = _clean(rec.get("rule_is_scientific"))

    # --- stage 1: scientific communication --------------------------------
    if meta_sci is not None:
        out["label_is_scientific"] = bool(meta_sci)
        out["label_source_is_scientific"] = "medline"
    elif rule_sci is False:
        out["label_is_scientific"] = False
        out["label_source_is_scientific"] = "lexical_rule"
    else:
        out["label_is_scientific"] = None
        out["label_source_is_scientific"] = None

    # --- stage 2: empirical status ----------------------------------------
    meta_emp = _clean(rec.get("meta_is_empirical"))
    struct = structured_abstract_signal(abstract)
    rule_emp = _clean(rec.get("rule_is_empirical"))
    has_marker = bool(_EMPIRICAL_MARKER.search(abstract))
    review = review_signal(rec.get("doc_type_raw"), abstract)
    out["review_type"] = review

    if meta_emp is not None:
        out["label_is_empirical"] = bool(meta_emp)
        out["label_source_is_empirical"] = "medline"
    elif review == "narrative":
        # NLM-tagged review with no systematic method named anywhere.
        out["label_is_empirical"] = False
        out["label_source_is_empirical"] = "medline_narrative_review"
    elif review == "systematic":
        out["label_is_empirical"] = True
        out["label_source_is_empirical"] = "medline_systematic_review"
    elif struct == "empirical":
        out["label_is_empirical"] = True
        out["label_source_is_empirical"] = "structured_abstract"
    elif rule_emp is False and not has_marker and struct is None:
        # Conceptual framing, no study structure, and no statistical or
        # sampling marker anywhere in the abstract.
        out["label_is_empirical"] = False
        out["label_source_is_empirical"] = "lexical_rule"
    else:
        out["label_is_empirical"] = None
        out["label_source_is_empirical"] = None

    # --- stage 3: methodology ---------------------------------------------
    if meta_meth:
        out["label_methodology"] = meta_meth
        out["label_source_methodology"] = "medline"
    elif review == "systematic":
        out["label_methodology"] = "review"
        out["label_source_methodology"] = "medline_systematic_review"
    elif rule_meth and out.get("label_is_empirical") is not False:
        out["label_methodology"] = rule_meth
        out["label_source_methodology"] = "lexical_rule"
    else:
        out["label_methodology"] = None
        out["label_source_methodology"] = None

    return out


def label_report(records: list[dict]) -> dict[str, Any]:
    """Summarise label availability and provenance across the corpus."""
    rep: dict[str, Any] = {}
    for stage in ("is_scientific", "is_empirical", "methodology"):
        lab = [r.get(f"label_{stage}") for r in records]
        src = [r.get(f"label_source_{stage}") for r in records]
        n_lab = sum(1 for v in lab if v is not None)
        by_src: dict[str, int] = {}
        by_class: dict[str, int] = {}
        for v, s in zip(lab, src):
            if v is None:
                continue
            by_src[str(s)] = by_src.get(str(s), 0) + 1
            by_class[str(v)] = by_class.get(str(v), 0) + 1
        rep[stage] = {
            "n_labelled": n_lab,
            "pct_labelled": round(n_lab / max(len(records), 1) * 100, 2),
            "by_source": dict(sorted(by_src.items(), key=lambda kv: -kv[1])),
            "by_class": dict(sorted(by_class.items(), key=lambda kv: -kv[1])),
        }
        log.info("labels %-14s n=%-6d (%.1f%%) sources=%s classes=%s",
                 stage, n_lab, rep[stage]["pct_labelled"], by_src, by_class)
    return rep
