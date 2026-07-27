"""Deduplication behaviour.

These tests encode the decisions that matter for the published counts: that
the same work arriving from three providers collapses to one row, that two
genuinely different papers with similar titles do not collapse, and that
merging prefers the better source per field rather than whichever record
happened to arrive first.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sred.integrate.dedupe import block_key, deduplicate, title_norm  # noqa: E402


def rec(**kw):
    base = {"source": "pubmed", "source_id": "1", "title": "T", "abstract": "A" * 200,
            "year": 2010, "journal_raw": "J", "n_authors": 1, "authors": [],
            "venue_tier": "dispersed", "doi": None, "pmid": None,
            "cited_by_count": None, "mesh_terms": [], "retracted": False}
    base.update(kw)
    return base


def test_title_norm_folds_accents_punctuation_and_markup():
    a = title_norm("Suicide, self-harm & <i>ideation</i>: a review")
    b = title_norm("Suicide self harm and ideation a review")
    assert a == b


def test_identical_doi_merges_across_sources():
    rs = [
        rec(source="pubmed", doi="10.1000/abc", title="Suicide risk in veterans"),
        rec(source="openalex", doi="10.1000/abc", title="Suicide Risk in Veterans",
            cited_by_count=42),
    ]
    out, report = deduplicate(rs)
    assert len(out) == 1
    assert report["duplicates_removed"] == 1
    assert out[0]["cited_by_count"] == 42, "OpenAlex must win the citation field"
    assert "pubmed" in out[0]["source"] and "openalex" in out[0]["source"]


def test_pmid_links_a_doi_bearing_record_to_a_doi_less_one():
    rs = [
        rec(source="openalex", doi="10.1/x", pmid="12345", title="Means restriction"),
        rec(source="pubmed", doi=None, pmid="12345", title="Means restriction",
            abstract="B" * 300),
    ]
    out, _ = deduplicate(rs)
    assert len(out) == 1
    assert out[0]["doi"] == "10.1/x"
    assert out[0]["abstract"].startswith("B"), "PubMed must win the abstract field"


def test_conflicting_dois_are_never_merged():
    """Two records that each carry a DOI and disagree are different works,
    however similar their titles."""
    rs = [
        rec(source="a", doi="10.1/one", title="Suicide prevention in schools"),
        rec(source="b", doi="10.1/two", title="Suicide prevention in schools"),
    ]
    out, _ = deduplicate(rs)
    assert len(out) == 2


def test_fuzzy_merge_for_identifierless_records():
    rs = [
        rec(source="a", title="Suicidal ideation among rural adolescents in China"),
        rec(source="b", title="Suicidal Ideation Among Rural Adolescents in China."),
    ]
    out, report = deduplicate(rs)
    assert len(out) == 1
    assert report["fuzzy_merges"] >= 1


def test_distinct_papers_with_similar_titles_survive_separately():
    rs = [
        rec(source="a", title="Suicide rates in Japan 1990 to 2000"),
        rec(source="b", title="Homicide rates in Norway 2001 to 2015", year=2016),
    ]
    out, _ = deduplicate(rs)
    assert len(out) == 2


def test_core_venue_tier_survives_merge_with_dispersed():
    rs = [
        rec(source="openalex", doi="10.1/z", venue_tier="core_a"),
        rec(source="pubmed", doi="10.1/z", venue_tier="dispersed"),
    ]
    out, _ = deduplicate(rs)
    assert out[0]["venue_tier"] == "core_a"


def test_focused_topic_flag_wins_over_peripheral():
    rs = [
        rec(source="a", doi="10.1/f", topic_focus="peripheral"),
        rec(source="b", doi="10.1/f", topic_focus="focused"),
    ]
    out, _ = deduplicate(rs)
    assert out[0]["topic_focus"] == "focused"


def test_block_key_groups_same_work_and_separates_different_years():
    a = rec(title="The epidemiology of self-harm", year=2001)
    b = rec(title="Epidemiology of self harm", year=2001)
    c = rec(title="The epidemiology of self-harm", year=2002)
    assert block_key(a) == block_key(b)
    assert block_key(a) != block_key(c)


def test_report_counts_are_internally_consistent():
    rs = [rec(source="a", doi=f"10.1/{i % 7}") for i in range(21)]
    out, report = deduplicate(rs)
    assert report["input_records"] == 21
    assert report["output_records"] == len(out)
    assert report["duplicates_removed"] == 21 - len(out)


@pytest.mark.parametrize("n", [0, 1])
def test_degenerate_inputs(n):
    out, report = deduplicate([rec(doi="10.1/a")] * n)
    assert len(out) == n
