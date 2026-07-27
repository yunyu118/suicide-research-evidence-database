# Suicide Research Evidence Database (SRED)

**An open, reproducible bibliographic infrastructure for scientometric research on suicide and suicide prevention.**

[![CI](https://github.com/OWNER/suicide-research-evidence-database/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/suicide-research-evidence-database/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/Code-MIT-blue.svg)](LICENSE)
[![Data: CC BY 4.0](https://img.shields.io/badge/Data-CC%20BY%204.0-lightgrey.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

---

## What this is

SRED is a deduplicated, classified corpus of suicide-focused scholarship published between 1989 and 2025, together with the complete pipeline that builds it. It adapts the methodology of Perron, Victor & Qi ([2026](https://doi.org/10.1177/10497315261416833)) — who built the Social Work Research Database — from social work to suicide research and prevention.

Three things make it different from a bibliometric extract:

**It is rebuildable by anyone.** Every source is open: PubMed/MEDLINE, Europe PMC, OpenAlex, and NIH iCite. No Web of Science, no Scopus, no institutional subscription. Five commands reproduce the entire database from scratch.

**It handles a field defined by its topic, not its journals.** Social work has 88 disciplinary journals. Suicide research has about five. SRED therefore uses a hybrid design — complete venue-based capture of the specialty journals, plus a title-focused topical sweep across every other venue — and tags each record with its venue tier. That turns the field's dispersion from a methodological obstacle into a measurable quantity.

**It extracts what prevention science actually needs.** Beyond the standard bibliographic fields, every record carries a position on the prevention continuum, the suicide-related outcome studied, the study population, the design, the lethal means addressed, and any social determinants of health engaged. No existing bibliographic database carries these.

## Quick start

```bash
git clone https://github.com/OWNER/suicide-research-evidence-database.git
cd suicide-research-evidence-database
pip install -e ".[dev]"
export SRED_MAILTO="you@example.edu"

python scripts/01_harvest.py --sources openalex_venue,pubmed,europepmc
python scripts/02_integrate.py            # dedup, normalise, screen, QA
python scripts/02b_enrich.py              # citations + NIH Relative Citation Ratio
python scripts/03_classify.py             # 3-stage classification + extraction
python scripts/04_analyze.py              # tables, figures, results.json
python scripts/05_verify.py               # re-derive every claim independently

python -m sred.db.load --engine duckdb --out data/releases/sred.duckdb
```

Already have the release? Skip the build:

```python
import duckdb
con = duckdb.connect("data/releases/sred.duckdb")

con.sql("""
    SELECT publication_year, COUNT(*) AS n,
           ROUND(AVG(CASE WHEN sdoh_focus THEN 1.0 ELSE 0 END) * 100, 1) AS pct_sdoh
    FROM v_analytic_corpus
    WHERE publication_year BETWEEN 1990 AND 2023
    GROUP BY 1 ORDER BY 1
""").show()
```

## How it works

```
 PubMed/MEDLINE ─┐
 Europe PMC ─────┼─► harvest ─► dedupe ─► normalise ─► screen ─► enrich ─► classify ─► analyse
 OpenAlex ───────┤            (DOI →     (ISSN-first  (topical  (iCite     (3-stage +   (tables,
 [Scopus/WoS] ───┘             PMID →     journal      screen,   citations  suicide-     figures,
                               blocked    resolution)  audited)  + RCR)     specific     results.json)
                               fuzzy)                                       extraction)
```

**Deduplication** cascades DOI → PMID → blocked fuzzy title matching, with two guards that matter: records carrying conflicting persistent identifiers never merge regardless of title similarity, and a title match alone is insufficient without corroboration from ISSN, journal string, or first-author surname. Merging is provenance-aware — PubMed wins abstracts and MeSH, OpenAlex wins citations and ORCID.

**Screening** is two-sided. "Suicide" is a productive metaphor in molecular biology, politics, and security studies; a record matching a metaphorical phrase is dropped *unless* it also carries a behavioural-health marker, so a study of psychiatric outcomes among survivors of a suicide attack survives while suicide-gene therapy does not. Every exclusion writes a reason code.

**Classification** is three-stage, following Perron et al.: scientific communication → empirical status → methodology. Rather than an LLM, the default backend uses **distant supervision from human MEDLINE indexing** — NLM PublicationType tags supply human labels for a large share of the corpus at zero annotation cost, which trains a calibrated linear classifier for the remainder and simultaneously provides validation against human coders on tens of thousands of held-out records rather than a hundred. Label provenance is recorded per stage per record, so any result can be re-run restricted to human labels alone.

An **interchangeable LLM backend** (`sred.classify.llm_ollama`) reproduces the Perron design directly with `gpt-oss:20b` via Ollama. Same interface, one flag: `--backend ollama`.

## What's in the box

```
config/          journal list and topical query definition (edit these, not the code)
src/sred/
  sources/       PubMed, Europe PMC, OpenAlex, iCite, + Scopus/WoS stubs
  integrate/     deduplication, journal normalisation, topical screening
  classify/      metadata labels, lexical rules, distant supervision, LLM backend, validation
  analysis/      scientometric measures and publication figures
  db/            PostgreSQL schema + DuckDB loader
scripts/         the six pipeline stages, each runnable standalone
manuscript/      the paper, with every number substituted from results.json at build time
docs/            methods, data dictionary, reproduction guide
tests/           unit tests + a synthetic fixture corpus so CI never touches live APIs
```

## Design decisions worth knowing about

**Authors are not disambiguated.** `n_authors` and author strings are surface forms; ORCID is the only identifier treated as authoritative. Counting distinct author strings will overcount distinct people. This is the same decision, for the same reason, that Perron et al. made: entity resolution done partially produces confidently wrong collaboration networks. See [`docs/data-dictionary.md`](docs/data-dictionary.md).

**Citation counts are open-source counts** (OpenAlex, Europe PMC, iCite). They are systematically *different* from Web of Science figures, not merely smaller, and should not be compared against them directly. iCite additionally supplies the **Relative Citation Ratio**, which is field- and time-normalised and far more interpretable across a corpus spanning 35 years and a dozen disciplines.

**Topic delineation prioritises precision.** A record is included topically when suicide is a *principal* subject — in the title, or flagged by an NLM indexer as a major MeSH topic. A recall-oriented query returns roughly three times as many records, but the extra yield is overwhelmingly studies where suicidality is one outcome among many. Those records are retained and flagged `peripheral` rather than discarded.

**OpenAlex now meters its free tier at 1,000 requests/day.** A full topical sweep needs about 1,200. SRED's specialty-journal channel fits comfortably inside one day; the topical channel is year-sliced and resumable across days. See [`docs/reproducing.md`](docs/reproducing.md).

## Contributing

Issues and pull requests welcome, particularly:

- **Journal list corrections** — a specialty or regional venue we missed (`config/journals_core.yml`)
- **Screening false positives or negatives** — with the `sred_id` so we can trace the decision
- **Extraction validation** — the human coding template is at `data/interim/human_coding_template.csv`
- **Non-English coverage** — the largest known gap, and the one that matters most given where suicide burden falls

Run `pytest -m "not network"` and `ruff check src scripts tests` before opening a PR.

## Citation

If you use SRED, please cite both the software and the article. See [`CITATION.cff`](CITATION.cff).

## Licence

Code MIT. Derived data CC BY 4.0. Underlying metadata originates from PubMed/MEDLINE (public domain, courtesy of the U.S. National Library of Medicine), Europe PMC, OpenAlex (CC0), and NIH iCite (public domain). NLM does not endorse or claim responsibility for any derived work. See [`LICENSE`](LICENSE).

## Acknowledgements

This work adapts the methodological template of the Social Work Research Database:

> Perron, B. E., Victor, B. G., & Qi, Z. (2026). Evolution of social work knowledge production over 35 years: An AI-enabled analysis of trends in empiricism, methodology, collaboration, citation patterns, and output. *Research on Social Work Practice*. https://doi.org/10.1177/10497315261416833
