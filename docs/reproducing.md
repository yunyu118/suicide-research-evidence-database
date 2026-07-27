# Reproducing SRED

Every number in the manuscript is produced by the five commands below. No step
requires a paid database subscription, an API key, or a GPU.

## Requirements

- Python 3.10+
- ~8 GB free disk for the raw harvest and HTTP cache
- Network access to `eutils.ncbi.nlm.nih.gov`, `www.ebi.ac.uk`, and
  `api.openalex.org`

```bash
git clone https://github.com/OWNER/suicide-research-evidence-database.git
cd suicide-research-evidence-database
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export SRED_MAILTO="you@example.edu"      # required by provider polite-pool policies
```

## The pipeline

```bash
# 1. Harvest. Resumable: each year/journal writes its own shard plus a .done
#    marker, so an interrupted run picks up where it stopped.
python scripts/01_harvest.py --sources openalex_venue,pubmed,europepmc

# 2. Deduplicate, normalise journal names, apply the topical screen, run QA.
python scripts/02_integrate.py

# 3. Classify abstracts and extract suicide-specific fields.
python scripts/03_classify.py                  # distant supervision (default)
python scripts/03_classify.py --backend ollama # local LLM, see below

# 4. Compute every measure, write every table, render every figure.
python scripts/04_analyze.py

# 5. Build the released database.
python -m sred.db.load --engine duckdb --out data/releases/sred.duckdb
```

Expect roughly 45–90 minutes for a cold harvest and under five minutes for
steps 2–5.

## Rate limits, and the one that will bite you

**PubMed.** 3 requests/second unlimited. Set `NCBI_API_KEY` to raise it to 10/s.

**Europe PMC.** No published request budget. This is why SRED treats Europe PMC
as its rebuildable backbone rather than a supplement.

**OpenAlex.** As of 2026, OpenAlex meters its free tier at **1,000 requests per
day**. A full topical sweep of the suicide literature needs roughly 1,200, so it
cannot be completed in a single day on the free tier. SRED handles this three
ways, and you should pick deliberately:

1. The **specialty-journal channel** (`openalex_venue`) costs about 250 requests
   and completes in one day. This is the channel SRED depends on.
2. The **topical channel** (`openalex_topic`) is sliced by year and resumable.
   Re-run it on consecutive days; completed years are skipped.
3. If you hold an OpenAlex premium key, set `OPENALEX_API_KEY` and the ceiling
   lifts.

The v1.0 release was built with the OpenAlex topical channel complete only for
1989–2000. PubMed and Europe PMC cover 1989–2025 in full, and every headline
result is computed from those two plus the complete specialty-journal channel.
`data/interim/qa_report.json` records exactly which channels contributed.

## Optional: LLM classification

To reproduce the Perron et al. classification design directly:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gpt-oss:20b
python scripts/03_classify.py --backend ollama --model gpt-oss:20b --limit 500  # pilot first
python scripts/03_classify.py --backend ollama --model gpt-oss:20b
```

Responses are cached on disk by prompt hash, so an interrupted run resumes for
free and editing one prompt invalidates only that stage. Budget roughly 8–20
hours on a single consumer GPU for the full corpus.

## Optional: Scopus and Web of Science

Connectors exist as activatable stubs at `src/sred/sources/scopus.py` and
`src/sred/sources/wos.py`. Supply `SCOPUS_API_KEY` / `WOS_API_KEY` and add the
channel to `--sources`. These are **not** used for any published result: SRED's
reproducibility claim depends on every source being reachable without an
institutional subscription. They exist so that a subscribing institution can
quantify what commercial indexing adds — which is itself a finding worth
reporting.

## Verifying a build

```bash
pytest -m "not network"
python scripts/05_verify.py     # re-derives every manuscript claim from the data
```

`scripts/05_verify.py` recomputes each numeric claim in the manuscript directly
from `sred_classified.parquet` and fails loudly on any mismatch. It is wired
into CI, which means the prose cannot drift from the data without the build
going red.

## Determinism

The pipeline is deterministic given a fixed harvest. Random seeds are fixed at
`20260727` for the hold-out split, the human-coding sample, and the fixture
generator. The one genuine source of run-to-run variation is upstream: providers
add records, correct metadata, and update citation counts continuously. Each
release therefore pins a harvest date, and `data/releases/` keeps the frozen
Parquet and DuckDB artefacts so published results remain checkable after the
upstream data has moved on.
