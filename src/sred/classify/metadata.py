"""Metadata-derived labels from provider indexing.

NLM's PublicationType vocabulary is assigned by trained human indexers, which
makes it the highest-quality label source available at scale. SRED treats a
subset of those tags as near-gold labels for the three-stage classification,
and uses them to supervise a text model that generalises to the ~40% of the
corpus with no MEDLINE indexing (see :mod:`sred.classify.distant`).

Only unambiguous tags are used. ``Review`` is deliberately excluded from the
methodology mapping because NLM applies it to both systematic reviews and
discursive narrative reviews, which fall on opposite sides of the
empirical/non-empirical boundary in Perron et al.'s scheme.
"""

from __future__ import annotations

from typing import Any

# --- Stage 1: scientific communication ------------------------------------
NON_SCIENTIFIC_PT = {
    "editorial", "letter", "comment", "published erratum", "erratum",
    "retraction of publication", "retracted publication", "news",
    "newspaper article", "biography", "obituary", "bibliography",
    "directory", "interview", "video-audio media", "webcasts", "portrait",
    "legal case", "patient education handout", "address", "autobiography",
    "personal narrative", "congress", "introductory journal article",
    "book review", "paratext", "peer-review", "festschrift",
}

# --- Stage 2/3: empirical status and methodology --------------------------
# Each tag maps to (is_empirical, methodology). None = no evidence.
PT_LABELS: dict[str, tuple[bool | None, str | None]] = {
    # Quantitative designs
    "randomized controlled trial": (True, "quantitative"),
    "clinical trial": (True, "quantitative"),
    "controlled clinical trial": (True, "quantitative"),
    "clinical trial, phase i": (True, "quantitative"),
    "clinical trial, phase ii": (True, "quantitative"),
    "clinical trial, phase iii": (True, "quantitative"),
    "clinical trial, phase iv": (True, "quantitative"),
    "pragmatic clinical trial": (True, "quantitative"),
    "equivalence trial": (True, "quantitative"),
    "adaptive clinical trial": (True, "quantitative"),
    "observational study": (True, "quantitative"),
    "comparative study": (True, "quantitative"),
    "multicenter study": (True, "quantitative"),
    "twin study": (True, "quantitative"),
    "validation study": (True, "quantitative"),
    "evaluation study": (True, "quantitative"),
    "clinical study": (True, "quantitative"),
    # Evidence synthesis
    "meta-analysis": (True, "review"),
    "systematic review": (True, "review"),
    "scoping review": (True, "review"),
    # Qualitative
    "qualitative research": (True, "qualitative"),
    # Non-empirical
    "review": (None, None),          # ambiguous by design; see module docstring
    "editorial": (False, None),
    "comment": (False, None),
    "letter": (False, None),
    "historical article": (False, None),
    "lecture": (False, None),
    "practice guideline": (False, None),
    "guideline": (False, None),
    "consensus development conference": (False, None),
    "case reports": (True, "qualitative"),
}


def metadata_labels(rec: dict) -> dict[str, Any]:
    """Derive label evidence from a record's provider metadata.

    Returns a dict with ``meta_is_scientific``, ``meta_is_empirical``,
    ``meta_methodology`` and ``meta_source``. Any value may be ``None``,
    meaning "this record's metadata carries no evidence" - which is the
    common case for the non-MEDLINE portion of the corpus and precisely why
    the downstream text model exists.
    """
    raw = (rec.get("doc_type_raw") or "").lower()
    tags = {t.strip() for t in raw.replace(",", ";").split(";") if t.strip()}
    # OpenAlex uses a single coarse `type`; keep it as one tag.
    if not tags and raw:
        tags = {raw}

    is_scientific: bool | None = None
    if tags:
        is_scientific = not any(t in NON_SCIENTIFIC_PT for t in tags)

    empirical: bool | None = None
    methodology: str | None = None
    # Strongest evidence wins: an explicit design tag beats a generic one.
    priority = ["meta-analysis", "systematic review", "scoping review",
                "randomized controlled trial", "qualitative research",
                "clinical trial", "controlled clinical trial", "pragmatic clinical trial",
                "observational study", "validation study", "evaluation study",
                "comparative study", "multicenter study", "twin study",
                "case reports", "editorial", "comment", "letter"]
    for tag in priority:
        if tag in tags and tag in PT_LABELS:
            e, m = PT_LABELS[tag]
            if empirical is None:
                empirical = e
            if methodology is None:
                methodology = m
            if empirical is not None and methodology is not None:
                break

    has_mesh = bool(rec.get("mesh_terms"))
    return {
        "meta_is_scientific": is_scientific,
        "meta_is_empirical": empirical,
        "meta_methodology": methodology,
        "meta_source": "medline" if has_mesh else ("provider_type" if tags else None),
    }
