# Contributing to SRED

Thanks for considering it. SRED is research infrastructure, which means its
value depends on other people finding its mistakes.

## The most useful things you can contribute

**Journal list corrections.** If a dedicated suicidology or crisis-intervention
journal is missing from `config/journals_core.yml`, or one is listed that
shouldn't be, open an issue with the ISSN. Regional and non-English specialty
journals are the known weak spot, and they are exactly the ones commercial
indexes miss.

**Screening errors.** If a record was wrongly excluded or wrongly kept, open an
issue with its `sred_id` and `screen_reason`. Every screening decision writes a
reason code precisely so these are traceable. Metaphorical-use false positives
(a real suicide study dropped as a "suicide gene" paper, or vice versa) are the
most valuable class of report.

**Classification errors.** Same, with `cls_backend` so we can see which evidence
channel produced the label. Systematic patterns matter more than individual
misses — "narrative reviews from the 1990s are consistently classed empirical"
is far more actionable than one wrong record.

**Human coding.** `data/interim/human_coding_template.csv` holds a stratified
sample with blank columns for independent double-coding. Completed coding is
the single highest-value contribution to the project, because it is the one
thing the pipeline cannot generate for itself.

**Non-English coverage.** The largest known gap, and the one that matters most:
the countries bearing the greatest suicide burden publish substantially in
venues none of our sources index well. Concrete proposals here are very welcome.

## Development

```bash
pip install -e ".[dev]"
pytest -m "not network"
ruff check src scripts tests
```

CI runs lint, unit tests, and a full pipeline smoke test on a synthetic fixture
corpus. **Tests never hit live bibliographic APIs** — that would make the build
flaky and be rude to providers. If your change needs new test data, extend
`tests/make_fixture.py`.

## Code conventions

- Configuration belongs in `config/*.yml`, not in code. If you find yourself
  hard-coding a journal, a term, or a threshold, it probably belongs there.
- Every exclusion, merge, and normalisation decision must write a machine-readable
  reason. An unexplained record is a bug even when the outcome is right.
- Comments explain *why*, not *what*. The pipeline is full of decisions that
  look arbitrary until you know what went wrong without them — say what went
  wrong.
- New source connectors implement the `Paper` schema in `src/sred/schema.py` and
  normalise inside the connector, so the integration layer never learns which
  provider a record came from.

## Changing anything that affects published numbers

`scripts/05_verify.py` re-derives every manuscript claim from the corpus using
independently written code. If your change moves a number, the verifier will
fail — that is the point. Re-run:

```bash
python scripts/04_analyze.py
python scripts/05_verify.py
python manuscript/build.py --check
```

and include the diff in `data/processed/results.json` in your pull request, so
reviewers can see exactly what moved and by how much.

## Data releases

Frozen artefacts live in `data/releases/` and are versioned. Never overwrite a
release in place — published results must stay checkable after the upstream
data has moved on. Cut a new one instead, and record the harvest date.

## Reporting security or privacy concerns

SRED handles only published bibliographic metadata, so the surface is small. If
you believe a record contains personal information that should not be
redistributed, email the maintainer rather than opening a public issue.
