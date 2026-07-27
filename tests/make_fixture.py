#!/usr/bin/env python3
"""Generate a synthetic fixture corpus for CI.

CI must exercise the whole pipeline - integrate, classify, analyse - without
touching PubMed, Europe PMC, or OpenAlex. Depending on live bibliographic APIs
would make the build flaky, slow, and rude to the providers.

The fixture is synthetic but *structurally faithful*: it contains cross-source
duplicates, journal-name variants, records missing DOIs, metaphorical false
positives that the screen must reject, editorials the first classification
stage must reject, and enough labelled records per class for the distant
classifier to train. Numbers here are not meaningful; structure is.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "fixture"

SEED = 20260727

JOURNALS = [
    ("Suicide and Life-Threatening Behavior", "0363-0234", "core_a"),
    ("Suicide Life Threat Behav", "0363-0234", "core_a"),          # abbreviation variant
    ("Archives of Suicide Research", "1381-1118", "core_a"),
    ("Crisis", "0227-5910", "core_a"),
    ("Death Studies", "0748-1187", "adjacent_b"),
    ("Journal of Affective Disorders", "0165-0327", "dispersed"),
    ("Social Science & Medicine", "0277-9536", "dispersed"),
    ("Social Science and Medicine", "0277-9536", "dispersed"),     # punctuation variant
    ("BMC Psychiatry", "1471-244X", "dispersed"),
]

QUANT = ("We analysed data from a national survey of {n} respondents. Logistic "
         "regression estimated odds ratios with 95% confidence intervals. "
         "Suicidal ideation was associated with unemployment (OR 1.8, p < 0.01). "
         "Prevalence of suicide attempt was {p}%.")
QUAL = ("We conducted semi-structured interviews with {n} participants bereaved "
        "by suicide. Transcripts were analysed using thematic analysis. Emergent "
        "themes described stigma, isolation, and help-seeking. Participants "
        "described lived experience of loss over several years.")
MIXED = ("This mixed-methods study combined a survey of {n} adolescents with "
         "focus groups. Quantitative and qualitative strands were integrated in "
         "a convergent parallel design examining self-harm and school climate.")
REVIEW = ("We searched MEDLINE, Embase, and PsycINFO following PRISMA. {n} studies "
          "were screened and included. Pooled odds ratios for safety planning "
          "interventions were computed. Inclusion and exclusion criteria are reported.")
THEORY = ("This paper argues that suicide risk assessment rests on a conceptual "
          "framework that cannot support the predictive claims made for it. We "
          "propose a theoretical framework grounded in social determinants of health "
          "and consider its implications for practice and policy.")
EDITORIAL = ("In this issue we are pleased to introduce a special section. The "
             "editors welcome contributions on suicide prevention research and "
             "reflect on the direction of the field over the coming years.")
METAPHOR = ("We engineered a suicide gene construct driving apoptosis in tumour "
            "cells. The suicide substrate inhibited enzyme activity in vitro across "
            "several cell lines, with dose-dependent effects on viability.")

SPECS = [
    (QUANT, "Journal Article; Observational Study", True, "quantitative", 0.30),
    (QUANT, "Journal Article; Randomized Controlled Trial", True, "quantitative", 0.10),
    (QUAL, "Journal Article; Qualitative Research", True, "qualitative", 0.18),
    (MIXED, "Journal Article", True, None, 0.06),
    (REVIEW, "Journal Article; Meta-Analysis", True, "review", 0.08),
    (THEORY, "Journal Article", False, None, 0.16),
    (EDITORIAL, "Editorial", None, None, 0.08),
    (METAPHOR, "Journal Article", True, "quantitative", 0.04),
]

TITLES = [
    "Suicidal ideation among {pop}", "Suicide attempts in {pop}",
    "Self-harm and {pop}: a study", "Firearm access and suicide among {pop}",
    "Safety planning for {pop}", "Suicide bereavement in {pop}",
    "Non-suicidal self-injury among {pop}", "Suicide rates and unemployment in {pop}",
]
POPS = ["veterans", "adolescents", "older adults", "rural communities",
        "sexual minority youth", "prisoners", "farmers", "psychiatric inpatients",
        "Indigenous communities", "perinatal women"]


def main() -> int:
    rng = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()

    weights = [s[4] for s in SPECS]
    records = []
    doi_pool: list[str] = []

    for year in range(1990, 2025):
        # Exponential-ish growth so the CAGR machinery has something to fit.
        n = int(30 * (1.05 ** (year - 1990)))
        for i in range(n):
            body, doctype, empirical, method, _ = rng.choices(SPECS, weights=weights)[0]
            journal, issn, tier = rng.choice(JOURNALS)
            pop = rng.choice(POPS)
            title = rng.choice(TITLES).format(pop=pop)
            if body is METAPHOR:
                title = "Suicide gene therapy for glioma"
            elif body is EDITORIAL:
                title = "Editorial: the future of suicide prevention research"

            abstract = body.format(n=rng.randint(40, 8000), p=round(rng.uniform(1, 25), 1))
            abstract += (" Further detail on procedures, measures, and analytic strategy "
                         "is reported in the full text. ") * 2

            has_doi = rng.random() < (0.35 if year < 2000 else 0.95)
            doi = f"10.{rng.randint(1000, 9999)}/sred.{year}.{i}" if has_doi else None
            if doi:
                doi_pool.append(doi)
            nauth = max(1, min(30, int(rng.lognormvariate(0.5 + (year - 1990) * 0.03, 0.6))))

            records.append({
                "source": "fixture_a", "source_id": f"a{year}{i}",
                "doi": doi, "pmid": str(10_000_000 + len(records)),
                "title": title, "abstract": abstract,
                "journal_raw": journal, "issn_l": issn,
                "year": year, "pub_date": f"{year}-06-15",
                "doc_type_raw": doctype, "language": "en",
                "n_authors": nauth,
                "authors": [{"name": f"Author {j} Surname{rng.randint(1, 400)}",
                             "orcid": None, "affiliation": "Some University",
                             "position": j + 1} for j in range(nauth)],
                "affiliations_raw": ["Some University"], "countries": ["US"],
                "funders": ["National Institute of Mental Health"] if rng.random() < 0.3 else [],
                "mesh_terms": ["Suicide", "Humans"], "mesh_major_terms": ["Suicide"],
                "topic_focus": "focused",
                "keywords": ["suicide"],
                "references_count": rng.randint(10, 90),
                "cited_by_count": max(0, int(rng.lognormvariate(1.6, 1.4)) - (1 if rng.random() < 0.18 else 0)),
                "citation_source": "fixture", "url": None, "retracted": False,
                "venue_tier": tier, "harvest_ts": now, "schema_version": "1.0.0",
            })

    # Cross-source duplicates: ~15% of DOI-bearing records reappear from a
    # second provider with a differently-cased title and a citation count.
    dupes = []
    for r in records:
        if r["doi"] and rng.random() < 0.15:
            d = dict(r)
            d["source"] = "fixture_b"
            d["source_id"] = "b" + r["source_id"]
            d["title"] = r["title"].upper()
            d["cited_by_count"] = r["cited_by_count"] + rng.randint(0, 3)
            d["abstract"] = r["abstract"][:400]
            dupes.append(d)
    records.extend(dupes)

    path = OUT / "fixture_corpus.ndjson"
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    path.with_suffix(".done").write_text(str(len(records)))
    print(f"fixture: {len(records)} records ({len(dupes)} synthetic duplicates) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
