"""Topical screening and lexical classification rules.

The screening tests exist because the single largest threat to a topic-defined
suicide corpus is the metaphorical use of the word. A screen that quietly
admits suicide-gene-therapy papers would inflate the 1990s and 2000s and
manufacture a growth story that is not real.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sred.classify.metadata import metadata_labels  # noqa: E402
from sred.classify.rules import rule_labels  # noqa: E402
from sred.integrate.screen import Screener  # noqa: E402


@pytest.fixture(scope="module")
def screener():
    with open(ROOT / "config" / "query_terms.yml") as fh:
        return Screener(yaml.safe_load(fh))


def rec(title, abstract, **kw):
    base = {"title": title, "abstract": abstract, "year": 2015,
            "venue_tier": "dispersed", "doc_type_raw": "article"}
    base.update(kw)
    return base


PAD = " Methods and results are described in detail across several cohorts. " * 4


def test_metaphorical_suicide_gene_is_excluded(screener):
    ok, reason = screener.screen(rec(
        "Suicide gene therapy for glioma",
        "We engineered a suicide gene construct driving apoptosis in tumour cells." + PAD))
    assert ok is False
    assert reason == "metaphorical_use"


def test_political_suicide_is_excluded(screener):
    ok, reason = screener.screen(rec(
        "Political suicide: party strategy after the referendum",
        "This analysis considers why the manoeuvre amounted to political suicide." + PAD))
    assert ok is False
    assert reason == "metaphorical_use"


def test_suicide_bombing_survivors_are_retained(screener):
    """The two-sided rule: a metaphor-adjacent phrase plus a behavioural-health
    marker is genuine suicide-relevant scholarship, not a false positive."""
    ok, reason = screener.screen(rec(
        "Mental health of survivors of a suicide bombing",
        "We assessed post-traumatic stress and suicidal ideation among survivors "
        "of a suicide attack, using validated psychiatric measures." + PAD))
    assert ok is True, reason


def test_genuine_suicide_research_passes(screener):
    ok, reason = screener.screen(rec(
        "Suicide attempts among sexual minority adolescents",
        "We analysed data from a national survey to estimate the prevalence of "
        "suicide attempts among sexual minority adolescents." + PAD))
    assert ok is True, reason


def test_short_abstract_is_excluded(screener):
    ok, reason = screener.screen(rec("Suicidal ideation in later life", "Too short."))
    assert ok is False
    assert reason == "no_or_short_abstract"


def test_core_venue_record_bypasses_the_topical_screen(screener):
    """An article in a dedicated suicidology journal is topical by definition,
    even when its abstract never uses the word."""
    ok, reason = screener.screen(rec(
        "Editorial board changes and the future of the field",
        "This paper considers how the field's institutions have evolved and what "
        "that means for research priorities over the coming decade." + PAD,
        venue_tier="core_a", doc_type_raw="article"))
    assert ok is True, reason


def test_missing_year_is_excluded(screener):
    ok, reason = screener.screen(rec("Suicide rates", "Suicide rates rose." + PAD, year=None))
    assert ok is False
    assert reason == "no_publication_year"


# --- rules ------------------------------------------------------------------

def test_rules_detect_qualitative_design():
    out = rule_labels("Experiences of suicide bereavement",
                      "We conducted semi-structured interviews with 22 bereaved "
                      "relatives and analysed transcripts using thematic analysis.")
    assert out["rule_methodology"] == "qualitative"
    assert out["rule_is_empirical"] is True


def test_rules_detect_evidence_synthesis_over_statistics():
    """A meta-analysis reports pooled statistics; it is still a review."""
    out = rule_labels("Interventions for self-harm: a systematic review",
                      "We searched MEDLINE and Embase. Studies were screened following "
                      "PRISMA. Pooled odds ratios were computed with 95% confidence intervals.")
    assert out["rule_methodology"] == "review"


def test_rules_detect_mixed_methods():
    out = rule_labels("A mixed-methods evaluation of a crisis line",
                      "This mixed-methods study combined survey data with focus groups.")
    assert out["rule_methodology"] == "mixed"


def test_rules_flag_non_empirical_conceptual_work():
    out = rule_labels("Rethinking suicide risk assessment",
                      "This paper argues that risk stratification rests on a conceptual "
                      "framework that cannot support the predictive claims made for it.")
    assert out["rule_is_empirical"] is False


def test_extraction_identifies_firearm_means_and_sdoh():
    out = rule_labels("Firearm access and suicide among veterans",
                      "We examined whether safe storage practices and neighbourhood "
                      "deprivation moderate the association between gun ownership and "
                      "suicide death among veterans.")
    assert "firearm" in out["means_focus"]
    assert out["sdoh_focus"] is True
    assert "veteran_military" in out["population"]
    assert "suicide_death" in out["outcome_construct"]


def test_extraction_identifies_prevention_level():
    out = rule_labels("Safety planning after an emergency department visit",
                      "Patients received a safety planning intervention and follow-up "
                      "caring contacts after presenting with a suicide attempt.")
    assert out["prevention_level"] == "indicated"


# --- metadata ---------------------------------------------------------------

def test_metadata_maps_rct_to_quantitative_empirical():
    out = metadata_labels({"doc_type_raw": "Journal Article; Randomized Controlled Trial",
                           "mesh_terms": ["Suicide"]})
    assert out["meta_is_empirical"] is True
    assert out["meta_methodology"] == "quantitative"
    assert out["meta_source"] == "medline"


def test_metadata_marks_editorials_non_scientific():
    out = metadata_labels({"doc_type_raw": "Editorial", "mesh_terms": []})
    assert out["meta_is_scientific"] is False


def test_ambiguous_review_tag_yields_no_methodology_label():
    """NLM's `Review` covers systematic and narrative reviews alike, so it must
    not be allowed to supervise the methodology classifier."""
    out = metadata_labels({"doc_type_raw": "Journal Article; Review", "mesh_terms": ["Suicide"]})
    assert out["meta_methodology"] is None


def test_meta_analysis_maps_to_review():
    out = metadata_labels({"doc_type_raw": "Meta-Analysis; Journal Article",
                           "mesh_terms": ["Suicide"]})
    assert out["meta_methodology"] == "review"
    assert out["meta_is_empirical"] is True
