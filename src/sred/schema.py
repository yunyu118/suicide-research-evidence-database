"""Canonical SRED record schema.

Every source connector emits dictionaries conforming to :data:`PAPER_FIELDS`.
Normalisation to this shape happens *inside* each connector, so the
integration layer never has to know which provider a record came from.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "1.0.0"

# --- papers -----------------------------------------------------------------
PAPER_FIELDS = [
    "sred_id",            # stable SRED identifier, assigned at integration
    "source",             # provider this record came from
    "source_id",          # provider-native id (PMID, OpenAlex W-id, ...)
    "doi",                # lowercased, bare (no https://doi.org/ prefix)
    "pmid",
    "title",
    "abstract",
    "journal_raw",        # journal name exactly as provided by the source
    "journal_canonical",  # after normalisation
    "issn_l",
    "publisher",
    "year",
    "pub_date",
    "volume",
    "issue",
    "pages",
    "doc_type_raw",       # provider document type string
    "language",
    "is_oa",
    "n_authors",
    "authors",            # list[dict] -> {name, orcid, affiliation, position}
    "affiliations_raw",
    "countries",
    "funders",
    "mesh_terms",
    "mesh_major_terms",
    "topic_focus",       # focused | peripheral | venue_only
    "keywords",
    "references_count",
    "cited_by_count",
    "citation_source",
    "url",
    "retracted",
    # --- venue tiering (SRED-specific) ---
    "venue_tier",         # core_a | adjacent_b | dispersed
    # --- screening ---
    "screen_pass",
    "screen_reason",
    # --- classification (populated downstream) ---
    "is_scientific",
    "is_empirical",
    "methodology",
    "cls_confidence",
    "cls_backend",
    # --- suicide-specific extraction ---
    "prevention_level",
    "outcome_construct",
    "population",
    "study_design",
    "sdoh_focus",
    "sdoh_domain",
    "means_focus",
    "geography",
    # --- provenance ---
    "harvest_ts",
    "schema_version",
]


@dataclass
class Paper:
    """A single SRED bibliographic record."""

    source: str
    source_id: str
    title: str = ""
    abstract: str = ""
    doi: str | None = None
    pmid: str | None = None
    journal_raw: str = ""
    journal_canonical: str = ""
    issn_l: str | None = None
    publisher: str | None = None
    year: int | None = None
    pub_date: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    doc_type_raw: str | None = None
    language: str | None = None
    is_oa: bool | None = None
    n_authors: int = 0
    authors: list[dict[str, Any]] = field(default_factory=list)
    affiliations_raw: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    funders: list[str] = field(default_factory=list)
    mesh_terms: list[str] = field(default_factory=list)
    mesh_major_terms: list[str] = field(default_factory=list)
    topic_focus: str | None = None
    keywords: list[str] = field(default_factory=list)
    references_count: int | None = None
    cited_by_count: int | None = None
    citation_source: str | None = None
    url: str | None = None
    retracted: bool = False
    venue_tier: str = "dispersed"
    screen_pass: bool | None = None
    screen_reason: str | None = None
    sred_id: str | None = None
    harvest_ts: str | None = None
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_doi(doi: str | None) -> str | None:
    """Strip URL prefixes and lowercase. Returns None for junk values."""
    if not doi:
        return None
    d = str(doi).strip().lower()
    for pre in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/",
                "http://dx.doi.org/", "doi:"):
        if d.startswith(pre):
            d = d[len(pre):]
    d = d.strip().rstrip(".")
    if not d.startswith("10.") or len(d) < 7:
        return None
    return d
