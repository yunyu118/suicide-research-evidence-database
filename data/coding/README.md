# SRED human coding — folder guide

Everything needed to run the double-coding validation, and the order to use it in.

## Before you send anything

The one irreversible mistake in this folder is sending a coder a file that
contains the classifier's answers. Check the filename before every send.

| Send to coders | Never send to coders |
|---|---|
| `SRED_coding_CoderA.xlsx` → Coder A only | `_scoring_key_DO_NOT_SHARE_WITH_CODERS.csv` |
| `SRED_coding_CoderB.xlsx` → Coder B only | `human_consensus.csv` (once it exists) |
| `SRED_coding_protocol.docx` → both | `reliability_report.json` (mid-project) |

Coder A must not receive Coder B's workbook and vice versa. Independence is
what the whole exercise measures.

## The files

**`SRED_coding_protocol.docx`** — the onboarding manual. Send with the offer or
on day one. Covers what the project is, why the design is what it is, the
schedule, what good work looks like, and a note on the material itself.

**`SRED_coding_CoderA.xlsx` / `CoderB.xlsx`** — the working files. Three tabs:
*START HERE* (read first), *Codebook* (keep open while coding), *Coding* (300
records, dropdown-validated, calibration batch shaded green). Model predictions
are stripped; the generator refuses to run if any would leak through.

**`SRED_coding_decision_log.docx`** — maintained by the lead, not the coders.
Every rule clarified after coding began, with date, prompting record, rule,
reasoning, and whether earlier records need re-coding. Cite it in the
manuscript: reviewers want to know whether the codebook was fixed in advance or
evolved, and showing how it evolved is more credible than implying it did not.

**`_scoring_key_DO_NOT_SHARE_WITH_CODERS.csv`** — the classifier's predictions,
held back for scoring. Project lead only.

Generated later by the scoring script: `SRED_adjudication.xlsx` (disagreements
and flags only), `human_consensus.csv`, `reliability_report.json`.

## The workflow

```bash
# 1. Generate the workbooks (already done; re-run only to change the design)
python scripts/07_make_coding_workbooks.py

# 2. Both coders finish Batch 1 (30 calibration records). Then:
python scripts/08_score_coding.py --mode reliability --batch 1-calibration
#    -> reliability_report.json + SRED_adjudication.xlsx
#    Hold the calibration meeting. Record every ruling in the decision log.
#    Both coders re-code Batch 1 under the settled rules.

# 3. Both coders finish Batch 2 (270 records). Then:
python scripts/08_score_coding.py --mode reliability
#    -> inter-rater kappa on all 300, and the full adjudication workbook

# 4. Adjudicator fills the FINAL_ columns in SRED_adjudication.xlsx. Then:
python scripts/08_score_coding.py --mode adjudicate
#    -> human_consensus.csv

# 5. The number that goes in the paper:
python scripts/08_score_coding.py --mode confirm
#    -> data/interim/confirmatory_kappa.json
```

## Reading the output

Kappa and percent agreement are reported together, and both belong in the
manuscript. On a field where one category holds most of the records, two coders
can agree 92% of the time and still score a kappa near zero, because chance
agreement alone would have reached 90%. That is a property of the statistic,
not a failure of the coders. The scoring output detects this condition and says
so in plain language rather than leaving you to notice.

Conventional bands for kappa: below 0.20 poor, 0.20–0.40 fair, 0.40–0.60
moderate, 0.60–0.80 substantial, above 0.80 almost perfect. Treat them as rough
guides, not thresholds to be cleared.

## If reliability comes back low

Look at the confusion matrix before concluding anything about the coders.

**Concentrated in one cell** — two categories are being confused with each
other. The definition separating them needs sharpening, and one clarification
in the decision log usually fixes it.

**Scattered across the matrix** — the question itself is underspecified, or the
coders were not calibrated on it. More training will not help; a better
definition will.

**One coder's marginals differ sharply from the other's** — one is applying a
systematically different threshold. This is the most fixable case and the most
important to catch early, which is why Batch 1 exists.

## Rebuilding

```bash
python scripts/07_make_coding_workbooks.py --coders A B C --calibration 40
```

Re-running overwrites the workbooks, so do it before coding starts, never
during. The record order is shuffled with a fixed seed, so a rebuild reproduces
the same order unless you change `--seed`.
