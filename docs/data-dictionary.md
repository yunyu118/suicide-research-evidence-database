# SRED data dictionary

Applies to `data/processed/sred_classified.parquet` and the `papers` /
`paper_extraction` tables of `data/releases/sred.duckdb`.

## Identity and provenance

| Field | Type | Notes |
|---|---|---|
| `sred_id` | text | Primary key. `doi:<doi>`, `pmid:<pmid>`, or `sig:<hash>` for records with neither identifier. Stable across builds *given the same identifiers*; a record that acquires a DOI upstream will change key, which is why `source_ids` is retained. |
| `doi` | text | Lowercased, bare (no `https://doi.org/` prefix). `NULL` when absent or malformed. |
| `pmid` | text | PubMed identifier. |
| `source` | text | Every provider that returned this work, `+`-joined (e.g. `europepmc+pubmed`). A single value means exactly one source had it — the coverage-gap signal. |
| `source_ids` | json | Provider → native identifier. |
| `harvest_ts` | timestamp | When this record was retrieved. |
| `schema_version` | text | Semantic version of the record schema. |

## Bibliographic

| Field | Type | Notes |
|---|---|---|
| `title`, `abstract` | text | Structured PubMed abstracts keep their section labels (`Background:`, `Methods:`). OpenAlex abstracts are reconstructed from the inverted index. |
| `journal_raw` | text | Journal string exactly as the provider supplied it, preserved for audit. |
| `journal_canonical` | text | After ISSN-first normalisation. **Use this for all journal-level analysis.** |
| `issn_l`, `publisher` | text | |
| `year`, `pub_date` | int, date | `year` is the analytic field. Electronic publication date is preferred over issue date. |
| `volume`, `issue`, `pages` | text | |
| `doc_type_raw` | text | Provider document type(s), `;`-joined. NLM PublicationType for PubMed; a single coarse `type` for OpenAlex. |
| `language`, `is_oa`, `url`, `retracted` | | |
| `n_authors` | int | Author count. See the disambiguation caveat below. |
| `authors` | json | List of `{name, orcid, affiliation, position}`. |
| `affiliations_raw`, `countries`, `funders` | json | As provided; no entity resolution. |
| `mesh_terms` | json | All MeSH descriptors. |
| `mesh_major_terms` | json | Descriptors NLM flagged `MajorTopicYN="Y"` — a human indexer's judgement that the concept is a *principal* subject. |
| `references_count`, `cited_by_count` | int | |
| `citation_source` | text | `openalex` or `europepmc`. The two disagree; see `docs/methods.md`. |

## Inclusion

| Field | Values | Notes |
|---|---|---|
| `venue_tier` | `core_a`, `adjacent_b`, `dispersed` | `core_a` = dedicated suicidology journal (included by venue). `adjacent_b` = thanatology/crisis journal (topical screen still applies). `dispersed` = any other venue, entered topically. |
| `topic_focus` | `focused`, `peripheral`, `venue_only` | `focused` = suicide is a principal subject (in the title, or a suicide MeSH descriptor flagged major). `peripheral` = suicide is mentioned but not the subject — a depression trial reporting suicidal ideation among many outcomes. `venue_only` = entered through the specialty-journal channel. |
| `screen_pass` | bool | Survived the topical screen. |
| `screen_reason` | text | `pass`, `metaphorical_use`, `no_topical_term`, `no_or_short_abstract`, `no_publication_year`. |

## Classification

Three stages, following Perron, Victor & Qi (2026).

| Field | Values | Notes |
|---|---|---|
| `is_scientific` | bool | Stage 1. False for editorials, letters, book reviews, news, obituaries, errata. |
| `is_empirical` | bool / null | Stage 2, defined only where `is_scientific`. `NULL` = the classifier declined rather than guessed. |
| `methodology` | `quantitative`, `qualitative`, `mixed`, `review` / null | Stage 3, defined only where `is_empirical`. |
| `cls_backend` | text | Provenance per stage, e.g. `scientific:metadata\|empirical:model\|method:rule`. Lets you restrict any analysis to human-indexed labels alone. |
| `cls_confidence` | numeric | Minimum calibrated probability across stages. `1.0` where every stage came from human MEDLINE indexing. |

## Suicide-specific extraction

No existing bibliographic database carries these fields. They are what makes
SRED usable for prevention science rather than for bibliometrics alone.

| Field | Values |
|---|---|
| `prevention_level` | `universal`, `selective`, `indicated`, `treatment`, `postvention`, `not_applicable` |
| `outcome_construct` | multi-label: `suicide_death`, `suicide_attempt`, `suicidal_ideation`, `non_suicidal_self_injury`, `self_harm_undifferentiated`, `suicide_risk_composite`, `suicide_bereavement`, `attitudes_or_stigma`, `service_use_or_care_process`, `not_specified` |
| `population` | multi-label: `general_population`, `youth_adolescent`, `older_adult`, `veteran_military`, `clinical_psychiatric`, `primary_care`, `justice_involved`, `lgbtq`, `indigenous`, `racial_ethnic_minority`, `rural`, `occupational`, `perinatal`, `other` |
| `study_design` | multi-label: `rct`, `quasi_experimental`, `cohort_prospective`, `case_control`, `cross_sectional`, `ecological_timeseries`, `registry_linkage`, `psychological_autopsy`, `qualitative_interview`, `qualitative_other`, `mixed_methods`, `systematic_review_meta_analysis`, `scoping_narrative_review`, `simulation_modelling`, `psychometric`, `other` |
| `sdoh_focus` | bool |
| `sdoh_domain` | multi-label: `economic_stability`, `education_access`, `healthcare_access`, `neighborhood_environment`, `social_community_context`, `discrimination_racism`, `housing_homelessness`, `food_insecurity`, `incarceration`, `immigration_status`, `firearm_access_means`, `digital_social_media`, `none` |
| `means_focus` | multi-label: `firearm`, `poisoning_overdose`, `pesticide`, `hanging`, `jumping`, `drowning`, `other`, `none` |
| `geography` | ISO-3166 alpha-2, `multi`, or `not_specified` |

## Four things to know before you analyse

**Authors are not disambiguated.** `n_authors` and `authors` are surface forms.
ORCID is the only identifier treated as authoritative. Counting distinct author
strings will substantially overcount distinct people — name variants, middle
initials, and changed names all fragment one person into several. Any analysis
of individual scholarly trajectories or collaboration networks needs a
disambiguation step SRED does not perform. This is the same decision, for the
same reason, that Perron et al. made.

**Citation counts are open-source counts.** They come from OpenAlex and Europe
PMC, not Web of Science or Scopus. They are systematically *different*, not
merely smaller: open citation graphs cover non-commercial and regional venues
better and older material worse. Do not compare SRED citation figures directly
against Web of Science figures.

**Multi-label fields are stored as JSON strings** in Parquet and as arrays in
DuckDB. Percentages for multi-label fields use the record count as the
denominator, so they sum to more than 100.

**Classification is not uniformly sourced.** Records with MEDLINE indexing carry
human labels; the rest carry model labels. Both are marked in `cls_backend`. If
a result matters, re-run it restricted to `cls_backend LIKE '%metadata%'` and
confirm the direction holds.
