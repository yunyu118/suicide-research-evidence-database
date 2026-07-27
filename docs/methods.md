# SRED methods notes

Supplements the manuscript with the decisions that shaped the build and the
reasons behind them. Where a choice cost something, that cost is stated.

## Why a hybrid corpus definition

Perron, Victor & Qi (2026) defined social work scholarship by venue: 88
disciplinary journals, everything they published. The definition works because
social work owns a large, stable set of journals.

Suicide research does not. There are roughly five dedicated suicidology
journals worldwide, and together they publish a minority of the field's output.
A venue-based corpus would be small and biased toward clinical and
psychological framings; a purely topical corpus inherits the ambiguity of the
word "suicide."

SRED therefore runs two channels and labels every record with which one caught
it:

| Tier | Definition | Inclusion rule |
|---|---|---|
| `core_a` | Dedicated suicidology journal | Everything published, 1989–2025 |
| `adjacent_b` | Thanatology / crisis journal | Harvested in full; admitted only if topically relevant |
| `dispersed` | Any other venue | Admitted only if suicide is a *principal* subject |

The dispersion measure that falls out of this — what share of the field appears
in its own journals, and how that has moved — has no counterpart in the social
work analysis, because the question cannot arise there.

## Precision over recall in topic delineation

A record enters the dispersed tier when suicide is a **principal** subject:
the construct appears in the title, or an NLM indexer flagged a suicide MeSH
descriptor as a major topic.

The alternative — any abstract mentioning suicide — returns roughly three times
as many records. We checked what the extra yield looks like, and it is
overwhelmingly studies where suicidality is one measured outcome among many: a
depression trial reporting ideation on a symptom scale, a cohort study listing
suicide among causes of death. Including them would triple the corpus while
diluting it, and would make "growth in suicide research" partly a measure of
growth in psychiatric outcome measurement.

Those records are retained and flagged `peripheral` rather than discarded, so
anyone who wants the recall-oriented corpus can have it.

## The two-sided metaphor screen

"Suicide" is productive outside behavioral health: suicide genes, suicide
substrates, political suicide, suicide squeezes, suicide bombings. A blocklist
would remove the genuine literature on psychiatric outcomes among survivors of
suicide attacks along with the molecular biology.

The screen is therefore two-sided: a metaphor match excludes a record *unless*
it also carries a behavioral-health marker. Every exclusion writes a reason
code, so the screen is auditable rather than a black box.

Records from `core_a` venues bypass the topical screen entirely — they are
topical by definition.

## Deduplication guards that turned out to matter

The DOI → PMID → fuzzy-title cascade is standard. Two guards are not, and both
were added after the first full build produced counts that were visibly wrong:

**Conflicting identifiers block a merge.** Two records that each carry a DOI and
disagree are different works, however similar their titles. Same for PMIDs.
Without this, same-year same-title records — common for conference abstracts and
serial publications — collapse into one.

**A title match alone is insufficient.** Merging additionally requires
corroboration from ISSN, journal string, or first-author surname. Editorials and
commentaries reuse titles across venues, and generic titles ("Suicide
prevention") recur within a year. On the fixture corpus, adding this guard took
fuzzy merges from 161 to 0 — every one of the 161 had been wrong.

Merging is provenance-aware rather than first-wins: PubMed supplies abstracts
and MeSH, OpenAlex supplies citations, ORCID, and institutional affiliations.

## Distant supervision, and the label-source problem it exposed

The plan was to supervise the classifier entirely with NLM PublicationType
tags — human-assigned labels, free, at scale. It worked for the positive class
and failed for the negative one, for a reason worth recording:

**The tags that would signal non-empirical work are attached to items that have
no abstract.** Editorials, letters, and comments are removed by the abstract
requirement long before classification. Training stage 2 on MEDLINE tags alone
gave 15,004 positives and zero negatives — not a hard problem, a degenerate one.

The fix was to find a negative class that survives the abstract requirement.
NLM's `Review` tag covers roughly one record in ten and was initially discarded
as ambiguous, since it spans systematic reviews (empirical synthesis) and
narrative reviews (non-empirical discussion). But the ambiguity is resolvable:
NLM applies *separate* tags for systematic reviews, meta-analyses, and scoping
reviews, and systematic work names its method in the abstract. A `Review` tag
with neither signal is a narrative review. That single distinction supplied
7,218 negatives and brought the stage-2 label set to 14.5% negative — trainable,
and plausible for this literature.

Label provenance is recorded per record in `label_source_*` and carried through
to `cls_backend`, so any result can be re-run restricted to human labels alone.

## Two bugs worth documenting

**NaN is truthy.** Records round-trip through Parquet between pipeline stages,
and Parquet turns `None` into `NaN`. `NaN is None` is False and `bool(NaN)` is
True, so `if rec.get("meta_methodology"):` silently accepted 77,894 missing
labels as real ones. The symptom was a class literally named `nan` in the label
distribution. Every label read now goes through an explicit `_clean()`.

**Hold-out sampling must be stage-wise.** The first validation drew one hold-out
from the union of all three label sources and scored every stage on it. The
methodology stage was therefore scored on 19,328 records of which only a
fraction had a methodology label; the rest were compared against missing values,
and reported accuracy came out at 0.208 — below chance for four classes. Each
stage now draws its own hold-out from records that actually carry that stage's
label.

Both bugs produced *plausible-looking* numbers before they were caught, which is
the argument for `scripts/05_verify.py`.

## Why iCite

Half the corpus arrives through PubMed alone, and PubMed supplies no citation
counts. Restricting citation analysis to the OpenAlex/Europe PMC subset would
bias it toward well-indexed, high-profile venues — precisely the bias the
citation analysis exists to detect. iCite covers every MEDLINE record, is free
and unmetered, and lifted citation coverage from 50.4% to 99.99%.

It also supplies the Relative Citation Ratio, which is field- and
time-normalised. Raw counts are close to uninterpretable across a corpus
spanning 35 years and a dozen disciplines: a 1991 psychological autopsy and a
2021 machine-learning paper differ in citation potential by an order of
magnitude for reasons having nothing to do with quality.

## What was deliberately not done

**Author disambiguation.** Entity resolution done partially produces
confidently wrong collaboration networks. ORCID is the only identifier treated
as authoritative. Same decision, same reason, as Perron et al.

**Scopus and Web of Science.** Connectors are implemented and documented but
supply no published result. A corpus rebuildable only by subscribers is not
reproducible. They exist so subscribing institutions can measure what
commercial indexing adds, which we regard as an open empirical question.

**LLM classification at corpus scale.** The Ollama backend is implemented,
interface-compatible, and cached, but a 20B model over ~97,000 abstracts is not
a cloud-CPU job. It is the intended upgrade path, and the highest-value one for
the suicide-specific extraction fields, which are lexically derived in this
release and should be read as reliable in direction and approximate in
magnitude.
