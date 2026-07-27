# SRED human coding protocol

Onboarding and operating manual for research assistants coding the SRED
validation sample. The at-the-desk reference lives in the workbook itself
(START HERE and Codebook tabs); this document covers everything around it:
what the work is for, how the team is organised, what the schedule looks like,
and what quality means here.

---

## 1. What this project is

The Suicide Research Evidence Database (SRED) is a corpus of roughly 97,000
suicide research articles published between 1989 and 2025, assembled from
PubMed, Europe PMC, OpenAlex, and NIH iCite. Every abstract in it has been
classified automatically along three dimensions: what kind of communication it
is, whether it reports data, and what research method it used. The database
also carries suicide-specific fields no bibliographic database contains, such
as where a study sits on the prevention continuum and whether it engages a
social determinant of health.

A classifier did that labelling. Before the results can be published, someone
has to check the classifier against trained human judgement. That is this job.

## 2. What you are being asked to do

Code a stratified sample of **300 abstracts by hand**, blind to the
classifier's answers, so we can measure agreement between machine and human
coding. Two coders do this independently on the identical 300 records; a third
person adjudicates where they differ.

Five questions per record. Three are primary and must be answered for every
record: communication type, empirical status, and research methodology. Two are
secondary and are answered only when the abstract makes the answer clear:
prevention level and whether a social determinant is addressed.

**You will not see the classifier's answers, and you will not see the other
coder's.** This is not a matter of trust; it is what makes the resulting
statistic mean anything. A coder who can see a proposed answer anchors on it,
and the agreement figure then measures compliance rather than judgement.

## 3. Why the design looks the way it does

Two coders rather than one, because a single coder produces no reliability
statistic at all. Two coders rather than three, because the marginal
information from a third is small relative to the cost of calibrating three
people to a common standard, and because a separate adjudicator serves the
disagreement-resolution role more cleanly than a third coder would.

An adjudicator who is not one of the two coders, because someone who has
already committed to an answer is the wrong person to arbitrate their own
disagreement.

A calibration batch before the main batch, because every codebook contains
ambiguities its author did not anticipate, and it is far better to discover
them on 30 records than on 300.

## 4. Roles

| Role | Who | Commitment |
|---|---|---|
| Coder A | RA | ~15 hours across two batches |
| Coder B | RA | ~15 hours across two batches |
| Adjudicator | PI or senior postdoc | ~3 hours |
| Project lead | PI | Calibration meeting, final sign-off |

Coders should not be people who built the classifier or who know its
tendencies. Familiarity with suicide research or health services research
helps; familiarity with the pipeline hurts.

## 5. Schedule

| Step | What happens | Time |
|---|---|---|
| 1. Onboarding | Read this document and both workbook tabs | 45 min |
| 2. Practice | Code 10 records together with the lead, out loud | 1 hour |
| 3. Batch 1 | Each coder independently codes 30 calibration records | 2 hours each |
| 4. Calibration meeting | Compare, resolve, record every decision in the log | 1.5 hours, whole team |
| 5. Batch 2 | Each coder independently codes 270 records | 11 hours each |
| 6. Re-code Batch 1 | Both coders redo the 30 under the settled rules | 1.5 hours each |
| 7. Adjudication | Adjudicator resolves disagreements and flags | 3 hours |
| 8. Scoring | Final kappa computed and written into the manuscript | automated |

Batch 2 should be spread over at least four sittings. Coding accuracy degrades
measurably after about ninety minutes of continuous work, and there is nothing
to be gained by pushing through it.

## 6. What good work looks like

**Consistency beats correctness.** For most records there is a defensible
answer and the question is whether you apply the same rule every time. If you
decide that protocol papers are non-empirical, that decision must hold on
record 7 and record 261 alike.

**Flag rather than guess.** The FLAG column exists so that uncertainty is
recorded rather than hidden inside a confident-looking answer. A flagged record
goes to adjudication regardless of whether the coders happened to agree. There
is no quota and no penalty; an honest flag is more useful to the project than a
coin-flip.

**Never leave a primary field blank.** A blank cannot be scored and is not the
same as "cannot_tell". If you genuinely cannot decide, choose the closest
answer and flag it.

**Abstract only.** Do not open the full text, do not search for the paper, do
not look up the authors. The classifier sees only the title and abstract, so a
fair comparison means you see only the title and abstract. This is the rule
most often broken by conscientious coders trying to be helpful.

**Say so if you drift.** If you realise partway through that you have been
applying a rule inconsistently, tell the lead. Re-coding a batch is cheap.
Publishing a reliability figure nobody believes is not.

## 7. When the codebook does not cover your case

1. Re-read the Codebook tab, including the Boundary note for that question.
2. Check the decision log for a ruling already made.
3. If neither settles it, code your best answer, set FLAG to yes, and describe
   the difficulty in NOTES.
4. Raise it at the next check-in. If it is a rule rather than a one-off, the
   lead records it in the decision log and both coders apply it from then on.

**Do not message the other coder about a specific record.** Coordinating on a
case destroys the independence the whole design rests on. Route everything
through the lead.

## 8. The decision log

Every clarification made after coding begins is written into
`SRED_coding_decision_log.docx`, with the date, the record that prompted it,
the rule adopted, and the reasoning. This exists for three reasons: so both
coders apply the same rule, so a rule adopted in week one is still being
applied in week three, and so the manuscript can describe how the codebook
evolved rather than pretending it sprang fully formed.

If a decision changes how earlier records should have been coded, say so
explicitly in the log. Those records get re-coded.

## 9. A note on the material

You will be reading several hundred abstracts about suicide, including studies
of method, of death, and of bereavement. Most are dry and clinical. Some are
not.

This is worth naming up front rather than discovering at record 140. Take
breaks. Do not code late at night. If the material is affecting you, say so to
the lead, and know in advance that stepping back from the task carries no
consequence for your position on the project. If you would find it useful,
your institution's employee assistance or student counselling service is
available to you, and using it is unremarkable.

If you have personal experience with suicide, that does not disqualify you from
this work and may make you a better coder. It does mean it is worth thinking
in advance about what pace and what schedule will work for you.

## 10. Confidentiality and data handling

The abstracts are published, public material; there is nothing confidential in
the corpus itself. Two handling rules still apply.

**Do not share your workbook with the other coder** at any point before
adjudication is complete.

**Do not open the scoring key.** The file named
`_scoring_key_DO_NOT_SHARE_WITH_CODERS.csv` contains the classifier's answers.
It should never be sent to a coder, and if you receive it by accident, say so
immediately rather than deleting it quietly — we need to know whether the
codes you produced afterwards are still usable.

## 11. Files

| File | Who holds it | Purpose |
|---|---|---|
| `SRED_coding_CoderA.xlsx` | Coder A only | Instructions, codebook, 300 records to code |
| `SRED_coding_CoderB.xlsx` | Coder B only | Identical, independent copy |
| `SRED_coding_decision_log.docx` | Shared, lead maintains | Every rule clarified after coding began |
| `SRED_adjudication.xlsx` | Adjudicator | Generated after coding; disagreements and flags only |
| `_scoring_key_...csv` | Project lead only | Classifier predictions, withheld from coders |

## 12. How the numbers are produced

```bash
# After each batch: reliability between coders + adjudication workbook
python scripts/08_score_coding.py --mode reliability
python scripts/08_score_coding.py --mode reliability --batch 1-calibration

# After the adjudicator fills in the FINAL_ columns
python scripts/08_score_coding.py --mode adjudicate

# The confirmatory figure the manuscript reports
python scripts/08_score_coding.py --mode confirm
```

The output reports Cohen's kappa, percent agreement, the confusion matrix, and
the marginal distribution for each field.

**Read kappa and percent agreement together.** On a field where one category
holds 90% of the records, two coders can agree 92% of the time and still score
a kappa near zero, because chance alone would have produced 90% agreement.
That is a property of the statistic, not a failure of the coders, and the
scoring output says so explicitly when it detects the condition. The manuscript
reports both figures for exactly this reason.

## 13. Rebuilding the workbooks

```bash
python scripts/07_make_coding_workbooks.py                       # two coders, 30 calibration
python scripts/07_make_coding_workbooks.py --coders A B C --calibration 40
```

The generator refuses to run if any model prediction column would reach a
coder. That check is not decorative: the sample file it reads from does contain
those columns, and shipping them would silently invalidate the entire exercise.
