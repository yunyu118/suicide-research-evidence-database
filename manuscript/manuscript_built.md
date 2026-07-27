# The Suicide Research Evidence Database: An AI-Enabled Analysis of Knowledge Production in Suicide Research and Prevention, 1989–2025

**Running head:** Suicide Research Evidence Database

**Authors:** Yunyu Xiao¹ (ORCID 0000-0002-0479-1781), [Coauthor 2]², [Coauthor 3]³, [Coauthor 4]⁴

¹ Department of Population Health Sciences, Weill Cornell Medicine, Cornell University, New York, NY, USA
² [Affiliation]
³ [Affiliation]
⁴ [Affiliation]

**Corresponding author:** Yunyu Xiao, Weill Cornell Medicine, 575 Lexington Avenue, New York, NY 10022, USA. Email: [email]

**Word count:** ~5965 (abstract through conclusion)
**Tables:** 4 | **Figures:** 8 | **Supplementary files:** 5

---

## Abstract

**Objective.** Suicide research has grown rapidly, yet the field has no shared bibliographic infrastructure through which to observe its own development. Unlike disciplines defined by their journals, suicide research is defined by its topic and is distributed across psychiatry, psychology, public health, epidemiology, nursing, and social work, so no single database indexes it coherently. We developed the Suicide Research Evidence Database (SRED) to close that gap and used it to characterize how suicide-related knowledge production has changed over 35 years.

**Method.** We integrated PubMed/MEDLINE, Europe PMC, and OpenAlex into a deduplicated corpus of suicide-focused scholarship published between 1989 and 2025, combining complete venue-based capture of dedicated suicidology journals with a title-based topical sweep across all other venues. A three-stage classifier trained by distant supervision on human National Library of Medicine indexing, and validated against withheld human labels, categorized each abstract by communication type, empirical status, and research methodology. We additionally extracted suicide-specific fields absent from every existing bibliographic database: position on the prevention continuum, suicide-related outcome construct, study population, study design, lethal means focus, and social determinants of health.

**Results.** SRED contains 96,641 unique article records with abstracts from 5,864 journals. Annual output grew at a compound annual rate of 6.48%, from 730 records in 1989 to 6,167 in 2023. Empirical research accounted for 82.95% of scientific articles. Among empirical work, quantitative methods predominated (75.6%), and mean authors per article rose from 3.23 in the 1990s to 6.44 in the 2020s. Only 5.09% of the corpus appeared in dedicated suicidology journals. 23.87% of articles addressed a social determinant of health.

**Conclusions.** Suicide research is expanding at rates matching science overall while remaining structurally dispersed across host disciplines rather than consolidating into its own. SRED provides open, reproducible infrastructure for monitoring this development and for identifying where the field's evidence is thin relative to where suicide deaths actually occur.

**Keywords:** suicide, suicide prevention, bibliometrics, scientometrics, social determinants of health, large language models, research infrastructure, open science

---

## Introduction

More than 720,000 people die by suicide each year, and suicide remains among the leading causes of death for adolescents and young adults worldwide. The research response has been substantial: the volume of suicide-related scholarship has expanded steadily for four decades, spanning epidemiology, clinical trials, genetics, health services research, qualitative inquiry, and policy analysis. Yet the field has limited systematic knowledge of its own knowledge production. Which questions attract sustained attention and which are neglected? Which populations are studied, and do they correspond to the populations dying? How has methodological practice changed? Where is the field's evidence concentrated, and where is it thin?

These questions have well-established answers in other disciplines because those disciplines built infrastructure to answer them. Scientometric analysis (the systematic study of publication patterns, citation networks, collaboration structures, and thematic evolution) has become a routine instrument of disciplinary self-examination [@haghani2023; @waltman2022]. Its value is practical rather than merely reflective: it identifies underexplored areas, documents methodological shifts, reveals who participates in knowledge production, and supplies evidence for strategic decisions about research priorities.

Social work offers a recent and instructive example. Perron, Victor, and Qi [-@perron2026] constructed a comprehensive bibliographic database of 62,602 articles from 88 social work journals spanning 1989 to 2025, applied a small language model to classify abstracts by empirical status and methodology, and documented the discipline's transformation: empirical research rose from 43% to 72% of publications, methodology shifted from quantitative dominance toward pluralism, mean authors per article nearly doubled, and 17.5% of articles remained uncited. Their contribution was as much infrastructural as substantive: a maintainable, extensible database enabling questions no single study had previously been positioned to ask.

Suicide research has no equivalent. It has bibliometric studies, several of them careful and useful, but they are one-off analyses built on ad hoc extractions from a single commercial database, and they cannot be extended, corrected, or reused. The reason this gap persists is structural, and it is the central methodological problem this paper addresses.

### Suicide research is topic-defined, not venue-defined

Perron and colleagues could define social work scholarship by its venues, because social work has a large, stable set of disciplinary journals, 88 of them in their analysis. That definition is unavailable here. Suicide research has perhaps five dedicated journals worldwide: *Suicide and Life-Threatening Behavior*, *Archives of Suicide Research*, *Crisis*, the open-access *Suicidology Online* (now ceased), and the recently founded *Journal of Suicidology*. Those journals publish a small fraction of the world's suicide scholarship. The rest appears in *JAMA Psychiatry*, *The Lancet Psychiatry*, *Journal of Affective Disorders*, *Social Science & Medicine*, *American Journal of Public Health*, *Injury Prevention*, and hundreds of other venues whose scope is a host discipline rather than suicide.

This has three consequences that shape everything downstream. First, a venue-based corpus would capture a minority of the field and a biased minority at that, over-representing psychological and clinical framings relative to epidemiological, economic, and policy work. Second, a purely topical corpus inherits the ambiguity of the word "suicide," which is a productive metaphor in molecular biology ("suicide gene," "suicide substrate"), in political commentary, and in security studies. Third, and most consequentially for the field, dispersion is not merely a methodological nuisance but a substantive property of how suicide knowledge is organized. A field whose output is scattered across host disciplines accumulates evidence differently from one that concentrates: findings are less likely to be encountered by the people who need them, methodological conventions diverge, and synthesis becomes harder. The degree of dispersion, and whether it is increasing, is itself worth measuring.

### Commercial indexing is not a solution

The obvious response, use Web of Science or Scopus, reproduces the problem in a different form. Commercial bibliographic databases exhibit systematic and uneven coverage [@singh2021; @birkle2020]. Regional journals, open-access titles without article processing charges, and outlets published by professional societies are indexed inconsistently or not at all. In the social work analysis, seventeen journals showed 100% uncited rates, a pattern reflecting absent citation tracking rather than absent scholarly impact [@perron2026]. Suicide research is if anything more exposed: it is a global field in which the countries bearing the greatest burden, India, China, and much of sub-Saharan Africa, publish substantially in venues that commercial indexes cover poorly.

Subscription access compounds this. A corpus that can only be rebuilt by subscribers is not reproducible in any meaningful sense, and a field whose infrastructure sits behind a paywall has ceded a public good to a commercial vendor.

### The present study

We developed the Suicide Research Evidence Database (SRED), adapting the methodological template of Perron and colleagues [-@perron2026] from social work to suicide research and prevention, with three modifications the subject matter demands.

First, SRED is built entirely on open sources, PubMed/MEDLINE, Europe PMC, and OpenAlex, so that any reader can rebuild it without an institutional subscription.

Second, SRED uses a **hybrid inclusion design**: complete venue-based capture of dedicated suicidology journals, plus a title-based topical sweep across all other venues, with every record tagged by venue tier. This makes the field's dispersion a measured quantity rather than a design constraint.

Third, SRED extracts **suicide-specific structured fields** no bibliographic database carries: position on the public-health prevention continuum, suicide-related outcome construct, study population, study design, lethal means focus, and social determinants of health. These are what convert a bibliographic resource into an instrument for prevention science: they permit the question of whether the field's research effort is distributed where suicide deaths actually occur.

The database, the pipeline that builds it, and the source of this manuscript are openly available at https://github.com/yunyu118/suicide-research-evidence-database.

We report four objectives. (1) Document the construction of an open, reproducible bibliographic infrastructure for suicide research. (2) Implement and validate a classification approach that does not require a GPU and that can be audited against human indexing. (3) Characterize growth, empiricism, methodology, collaboration, and citation patterns from 1989 to 2025. (4) Quantify the field's structural dispersion and the distribution of its research effort across prevention levels, populations, and social determinants.

---

## Method

### Corpus definition

We operationally defined suicide research through a two-channel hybrid design.

**Channel 1, specialty venues.** Every article published between 1989 and 2025 in a dedicated suicidology journal, identified by ISSN: *Suicide and Life-Threatening Behavior* (including its predecessor title *Suicide*, 1971–1975), *Archives of Suicide Research*, *Crisis: The Journal of Crisis Intervention and Suicide Prevention*, *Suicidology Online*, and the *Journal of Suicidology*. A second tier of adjacent thanatology and crisis journals (*Death Studies*, *OMEGA*, *Mortality*, *Illness Crisis & Loss*, *Bereavement Care*) was harvested in full but admitted only where records also satisfied the topical screen, because their scope is death and loss rather than suicide specifically.

**Channel 2, topical sweep.** Articles in any other venue where suicide or self-harm is a **principal subject**. We operationalized principal subject in two complementary ways: presence of a suicide construct in the article title, or a National Library of Medicine indexer's designation of a suicide MeSH descriptor as a major topic. This precision-oriented delineation is deliberate. A recall-oriented query retrieving any abstract mentioning suicide returns roughly three times as many records, but the additional yield consists overwhelmingly of studies in which suicidality is one measured outcome among many, a depression trial reporting suicidal ideation on a symptom scale is not suicide research in the sense that matters here. We report the recall-oriented count as a sensitivity analysis and retain those records, flagged as peripheral, in the released database.

The complete term sets, MeSH descriptors, and inclusion logic are in `config/query_terms.yml` in the project repository (https://github.com/yunyu118/suicide-research-evidence-database), and the resolved journal list is in `config/journals_core.yml`.

### Data sources

Three sources were integrated, selected for complementary coverage and for being reachable without subscription.

**PubMed/MEDLINE** is the controlled-vocabulary spine. Suicide research, unlike social work, benefits from a mature MeSH tree (*Suicide*, *Suicidal Ideation*, *Self-Injurious Behavior*, and their narrower terms), which permits topical definition through an indexed vocabulary rather than free text alone. MEDLINE also supplies human-assigned PublicationType tags and major-topic flags, which serve both as classifier supervision and as validation ground truth. Records were retrieved via the E-utilities API using history-server pagination, sliced by publication year.

**Europe PMC** unions MEDLINE with PubMed Central, preprint servers, and additional non-MEDLINE content, and imposes no request budget. This last property matters more than it may appear: it makes the corpus rebuildable on demand, which is the precondition for the reproducibility claim. Europe PMC also supplies an independent citation count.

**OpenAlex** provides coverage of the social-science suicide literature outside MEDLINE's scope and an open citation graph. It supplied the complete specialty-venue channel. A constraint should be stated plainly: as of 2026 OpenAlex meters its free tier at 1,000 requests per day, and a full topical sweep requires approximately 1,200. The OpenAlex topical channel is therefore complete for 1989–2000 in the present release and is being extended incrementally; all reported results derive from PubMed, Europe PMC, and the complete OpenAlex specialty-venue channel.

Connectors for Scopus and Web of Science are implemented and documented but were **not** used for any reported result, precisely because using them would forfeit reproducibility for non-subscribers. They are provided so that subscribing institutions can quantify what commercial indexing adds, a question we regard as empirically open and worth answering.

### Data integration pipeline

Integration proceeded in five stages, following the architecture of Perron and colleagues [-@perron2026].

**Stage 1, Source-specific extraction.** Each provider required custom parsing. PubMed XML was parsed to recover structured abstracts with section labels, MeSH descriptors with major-topic flags, ORCID identifiers, grant acknowledgments, and publication dates (preferring electronic over issue dates). OpenAlex abstracts, stored as inverted indices for copyright reasons, were reconstructed to linear text. All responses were cached on disk so that a parser revision can be re-applied to the corpus without re-querying providers.

**Stage 2, Cross-source deduplication.** Records were collapsed through a cascade: DOI match, then PMID match, then blocked fuzzy title matching for records carrying neither identifier. Fuzzy candidates were blocked on publication year and first significant title token, then scored by Levenshtein-based token-sort ratio; pairs at or above 90% similarity were merged and pairs between 80% and 90% were written to a review file rather than resolved silently. Two additional guards proved necessary and are worth stating, because their absence produces confidently wrong counts: records carrying conflicting persistent identifiers were never merged regardless of title similarity, and a title match alone was insufficient for merging without corroboration from ISSN, journal string, or first-author surname. Editorials and commentaries reuse titles across venues, and generic titles recur within a year. Merging was field-wise and provenance-aware: where sources disagreed, the value was taken from the source with the better record for that field (PubMed for abstracts and MeSH; OpenAlex for citation counts, ORCID, and institutional affiliations).

Deduplication reduced 193,597 harvested records to 136,499 unique works, removing 57,098 duplicates (46,931 by DOI, 10,084 by PMID, 83 by fuzzy title match) and flagging 35 pairs for review.

**Stage 3, Metadata normalization.** Journal titles were resolved ISSN-first and string-second, expanding NLM abbreviations, folding punctuation and accent variants, and reconciling historical renamings. Every fuzzy decision was logged to make the mapping auditable and reversible. Author and organization names were preserved as provided; SRED does **not** attempt author disambiguation, for the same reason Perron and colleagues did not. It requires an entity-resolution system beyond the scope of database construction, and a partial job produces confidently wrong collaboration networks. ORCID is the only author identifier treated as authoritative.

**Stage 4, Topical screening.** Because "suicide" is a productive metaphor outside behavioral health, a two-sided screen was applied. Records matching metaphorical phrases (suicide gene, suicide substrate, political suicide, suicide bombing, and others) were excluded unless they also carried a behavioral-health marker, which preserves genuine scholarship such as studies of psychiatric outcomes among survivors of suicide attacks. Records from specialty journals bypassed the topical screen, being topical by venue definition. Every exclusion wrote a machine-readable reason code. The screen evaluated 136,499 records and retained 96,641.

Document type was deliberately *not* screened at this stage. Separating scientific from other scholarly communication is classification stage 1, not a pre-filter; removing editorials before training would leave that classifier with no negative class to learn from.

**Stage 5, Quality assurance.** Automated checks verified referential integrity, identifier uniqueness, year plausibility, non-negative citation counts, and metadata completeness. Results are in `data/interim/qa_report.json`.

### Abstract classification

Perron and colleagues classified abstracts with a locally hosted 20-billion-parameter language model. That is a sound instrument where compute is available, but it has two costs for a field-wide infrastructure: it cannot be reproduced by a reader without a GPU, and it offers no way to quantify label quality beyond a single kappa against a small hand-coded sample.

SRED takes a different approach, exploiting a resource suicide research has and social work does not: **a large subset of the corpus carries human-assigned MEDLINE indexing**. NLM PublicationType tags are assigned by trained indexers and supply high-quality labels for a substantial share of records at zero annotation cost. We used those labels to train a calibrated linear text classifier (TF-IDF with word 1–2 grams, regularized logistic regression, sigmoid calibration) and applied it to the unindexed remainder. On abstract-length text with tens of thousands of labeled examples, this approach performs comparably to a fine-tuned encoder for document-type classification while training in seconds on CPU, remaining fully deterministic, and, critically for a methods paper, remaining inspectable, since any prediction traces to weighted n-grams.

The classification hierarchy follows Perron and colleagues exactly. Stage 1 separates scientific communication (original findings, theoretical frameworks, systematic reviews, methodological innovations) from other scholarly communication (editorials, book reviews, letters, news, obituaries, errata). Stage 2 separates empirical from non-empirical work among scientific communications. Stage 3 assigns methodology among empirical work: quantitative, qualitative, mixed methods, or evidence synthesis.

Label precedence is explicit and recorded per record: human MEDLINE indexing where available, then model prediction above a calibrated confidence floor, then high-precision lexical rules, then an explicit *uncertain* label. Records the system declined to classify are reported as such rather than forced into a class. The `cls_backend` field records the provenance of every stage of every record, so any result can be re-run restricted to human-labeled records alone.

We deliberately excluded NLM's generic `Review` tag from methodology supervision, because NLM applies it to both systematic reviews and discursive narrative reviews, which fall on opposite sides of the empirical/non-empirical boundary.

**An interchangeable LLM backend** implementing the identical interface is provided (`sred.classify.llm_ollama`), reproducing the Perron design directly with `gpt-oss:20b` at temperature 0.1 and JSON-structured prompts, with disk-cached responses and retained model rationales. It was not run at corpus scale for this release.

### Suicide-specific extraction

Six structured fields were extracted per record using high-precision lexical patterns, with the same LLM backend available as an upgrade path: **prevention level** on the public-health continuum (universal, selective, indicated, treatment, postvention); **outcome construct** (suicide death, attempt, ideation, non-suicidal self-injury, bereavement, and others); **population** (14 categories including youth, older adults, veterans, LGBTQ+, Indigenous, justice-involved, rural, and occupational groups); **study design** (16 categories); **lethal means focus** (firearm, poisoning, pesticide, hanging, jumping, drowning); and **social determinants of health** (12 domains including economic stability, discrimination and racism, housing instability, incarceration, immigration status, firearm access, and digital and social media environments).

### Validation

Classification was validated three ways rather than one.

**Held-out human indexing (primary).** A random 20% of MEDLINE-indexed records was withheld from training entirely and its labels blinded at prediction. Because NLM PublicationType tags are human-assigned, agreement on this hold-out is agreement with human coders, measured on 26,317 records rather than a hundred.

**Temporal generalization.** Because indexing conventions drift, models were additionally evaluated under leave-one-decade-out training. A classifier that works only on the decade it was trained on is unusable for a database intended to extend forward.

**Human verification sample.** A sample stratified by decade and predicted methodology was exported in a coding template for independent double-coding by the research team. This is the step that requires people, and it is reported as the confirmatory kappa.

### Database and analysis

The corpus is distributed as Parquet and as a DuckDB database with a normalized eight-table relational schema (papers, journals, authors, organizations, and link tables, plus a suicide-specific extraction table), together with a PostgreSQL DDL for hosted deployment. Analyses were performed in Python 3.11 (pandas, NumPy, scikit-learn, Matplotlib). Compound annual growth rates were computed as CAGR = [(ending ÷ beginning)^(1/n)] − 1 where n is the number of intervals. Following Perron and colleagues, trend analyses were truncated at 2023 to avoid artifacts from incomplete indexing of very recent publications, and citation analyses were restricted to the same window so that all papers had comparable time to accumulate citations.

Every number reported below is generated by `scripts/04_analyze.py` into a machine-readable results file (`data/processed/results.json` in the repository), from which this manuscript's figures are substituted at build time. An independent verification script re-derives each claim from the corpus using separately written code and fails the build on any mismatch.

---

## Results

### Database composition

SRED contains 96,641 unique article records with abstracts, published between 1989 and 2026 across 5,864 journals. Records carrying a 2026 publication date are ahead-of-print items deposited before the harvest and are excluded from all trend analyses. DOIs are present for 90.76% of records and citation counts for 99.99%.

The hybrid design's two channels contributed unevenly, which is itself the first result: 4,919 records (5.09%) came from dedicated suicidology journals and 90,508 from all other venues.

**Table 1** reports the journals contributing most heavily to the corpus, with coverage years, record counts, and citation metrics.

Source overlap quantifies the coverage-gap problem directly. 56.76% of records were returned by only one of the three providers, records that a single-database study would have missed entirely.

### Classification of research types and methodologies

Of 96,641 records, 95,377 were classified as scientific communication. Among these, 79,114 (82.95%) were empirical and 14,937 were non-empirical; 1,326 could not be classified with confidence and are reported as uncertain rather than assigned.

**Figure 2** shows the trajectory of empirical scholarship across the observation period. Empirical work accounted for 76.8% of scientific articles in the 1990s and 88.4% in the 2020s.

Among empirical articles with an assigned methodology, quantitative approaches were most common (58,463 articles, 75.6%), followed by qualitative methods (12,373, 16%), evidence synthesis (5,534, 7.2%), and mixed-methods designs (952, 1.2%). **Figure 3** shows the distribution over time and **Table 2** by decade.

**Classifier performance.** Against withheld human MEDLINE indexing, agreement was κ = 0.35 for scientific communication (n = 19,328), κ = 0.79 for empirical status (n = 5,332), and κ = 0.95 for methodology (n = 3,445). Human-assigned labels were used directly wherever available; the model supplied labels only for records lacking them, and 80.01% of records received a methodology assignment overall.

The stage-1 figure requires comment rather than burial. Accuracy is high (0.98) but kappa is not, because the class is extremely unbalanced: requiring a substantive abstract removes almost all editorials, letters, and book reviews before classification ever runs, leaving a non-scientific residue of roughly one record in eighty. What survives that filter is, by construction, the subset of non-scientific communication that reads like a research article. Kappa is the right statistic to report here and it says the text model adds little at this stage. It also matters little in practice: human MEDLINE indexing supplies a stage-1 label for 100% of the corpus, so the model is doing almost no work. Stages 2 and 3, where the model genuinely carries the corpus, reach substantial and near-perfect agreement respectively.

Under leave-one-decade-out training, agreement on empirical status held between 0.71 and 0.81 across the four decades, indicating that the classifier does not depend on the era it was trained on, which is the property a database designed to extend forward actually needs.

### Coauthorship trends

Mean authors per article across the corpus was 5.38 (median 4), with 91.24% of articles multi-authored. **Figure 4** and **Table 3** show the temporal pattern: mean authorship rose from 3.23 in the 1990s to 6.44 in the 2020s, while single-authored work declined from 22.2% to 4.1%.

### Growth trends

Annual output rose from 730 records in 1989 to 6,167 in 2023, a compound annual growth rate of 6.48% (**Figure 1**). The number of journals publishing suicide research annually grew from 326 to 1,518, a CAGR of 4.63%. Article growth exceeded journal growth by only 1.85 percentage points, meaning the field expanded chiefly by recruiting new venues rather than by intensifying output within existing ones. This is the opposite of the pattern Perron and colleagues report for social work, where the differential was 2.47 points in favour of intensification within a stable set of journals.

Across decades, the 1990s contributed 9,575 records (9.9%), the 2000s 16,486 (17.1%), the 2010s 31,895 (33%), and the 2020s through 2025 37,955 (39.3%).

### Citation patterns

Within the citation window, 82,436 records carried citation counts totaling 2,659,838 citations, with a mean of 32.27 and median of 13. 92.66% received at least one citation; 7.34% remained uncited. The distribution was heavily right-skewed (90th percentile 70, 99th percentile 300, maximum 14,484).

**Figure 5** shows uncited proportions by publication year separately for empirical and non-empirical work. **Table 1** reports citation metrics by journal.

Citation rates varied by methodology (**Table 4**). Evidence synthesis achieved the highest mean citations (64.62, n = 4,172), with 95.3% cited at least once, against 33.88 for quantitative work and 14.38 for qualitative work.

### Structural dispersion of the field

**Figure 6** presents the result with no counterpart in the social work analysis, because social work is defined by its journals and suicide research is not. Across the full period, 5.09% of suicide research appeared in dedicated suicidology journals. In 1989 the specialty share was 2.88%; by 2023 it was 3.29%.

### Prevention continuum, populations, and social determinants

**Figure 8** shows the distribution of research effort across the public-health prevention continuum by decade, and **Figure 7** the social determinants of health addressed.

Position on the prevention continuum was assignable for 8.9% of records. Among the corpus as a whole, 6.2% addressed treatment, 1.1% selective prevention, 0.6% indicated prevention, 0.6% postvention, and 0.4% universal prevention; the remaining 91.1% were descriptive, aetiological, or measurement studies that do not sit on the continuum at all.

23.87% of articles (23,069 records) addressed at least one social determinant of health as an exposure, moderator, or intervention target. The most frequently addressed domains were social and community context (8.9%), access to lethal means including firearms (4.6%), economic stability (4.6%), discrimination and racism (2.1%), and the digital and social media environment (1.8%).

Study populations were dominated by general-population samples (42.7%), young people (25.8%), and clinical psychiatric samples (17.7%). Method of suicide was addressed in 11.5% of records, most often poisoning or overdose (5.9%), firearms (2.7%), hanging (2.1%), and pesticides (1.3%).

Supplementary tables report full distributions for outcome construct, study population, study design, and lethal means focus, both overall and by decade.

---

## Discussion

This study built open, reproducible bibliographic infrastructure for suicide research and used it to characterize 35 years of the field's knowledge production. Four findings warrant discussion, and one of them is structural rather than descriptive.

### Growth and disciplinary maturation

Suicide research output grew at 6.48% annually. Comparison against de Solla Price's foundational benchmark of 4.7% for the scientific literature overall, and against the 4.91% Perron and colleagues report for social work, situates the field within the general dynamics of scientific expansion rather than marking it as exceptional. More informative than the headline rate is the mechanism. Journals publishing suicide research grew at 4.63% annually against 6.48% for articles, a differential of only 1.85 points. Social work's corresponding figures were 4.91% and 2.44%, a differential of 2.47 points in the opposite direction. Social work grew by publishing more in the journals it already had; suicide research grew by spreading into journals that had not previously published it, from 326 venues in 1989 to 1,518 in 2023. Consolidation and dispersion are different kinds of growth, and they leave a field in very different shape.

Interpretation of the most recent years requires caution. Incomplete indexing of very recent publications creates apparent plateaus that subsequent data collection revises upward, which is why trend analyses truncate at 2023.

### Empiricization and methodological practice

Empirical research accounted for 82.95% of scientific articles. The trajectory across decades (76.8% to 88.4%) parallels the shift Perron and colleagues document in social work and the broader movement across the applied social sciences in which empirical methods have displaced conceptual and philosophical inquiry as the dominant mode of contribution.

Whether this is unambiguously good is worth asking rather than assuming. Suicide is a phenomenon where conceptual clarity is not a luxury. What counts as a suicide attempt, whether ideation and behavior lie on a continuum, how intent should be inferred, and whether risk is a property of persons or of situations are conceptual questions with direct measurement consequences, and the field's measurement heterogeneity is a recognized obstacle to synthesis. A literature that has largely stopped doing conceptual work may be accumulating empirical findings faster than it can integrate them.

The methodological distribution, quantitative 75.6%, with qualitative at 16%, differs markedly from social work, where qualitative methods reached plurality by the 2020s. This is unsurprising given suicide research's epidemiological and clinical center of gravity, and it is not a deficiency in itself. But it is a constraint on the questions the field can answer. Understanding why interventions work, how people experience suicidal crises, and what makes help-seeking possible requires interpretive methods, and a literature dominated by outcome measurement will systematically under-produce that understanding.

### Collaboration

Mean authorship rose from 3.23 to 6.44 and single-authored work fell from 22.2% to 4.1%, paralleling collaboration trends across the sciences. The drivers are familiar: methodological complexity requiring diverse expertise, large-scale data collection and registry linkage requiring coordination beyond individual capacity, and funder preference for team science and community-academic partnership.

Two questions this database can now address, and which we flag as immediate next steps, are whether collaboration confers a citation advantage in suicide research as it does in social work, and whether international collaboration has grown in proportion to the field's globalization, the second bearing directly on whether high-burden, low-resource settings are participating in knowledge production or only being studied.

### Dispersion: the structural finding

The most consequential result is that 5.09% of suicide research appears in dedicated suicidology journals. Nineteen articles in twenty appear somewhere else. Suicide research is not a discipline that publishes in its own venues; it is a topic pursued from within host disciplines and published overwhelmingly in theirs. The share has not moved: it was 2.88% in 1989 and 3.29% in 2023. Whatever else has changed about the field in 35 years, its relationship to its own journals has not.

This has practical consequences. A clinician or researcher who reads the specialty journals sees a minority of the field. Methodological conventions (how ideation is measured, how attempts are ascertained, how risk is modeled) develop semi-independently within host disciplines and drift apart, which is one plausible source of the measurement heterogeneity that frustrates meta-analysis. Systematic reviews searching a single database systematically miss material, and the 56.76% single-source rate we observe puts a number on that risk. And a dispersed field has weaker mechanisms for collective self-correction: there is no venue where the whole literature is visible to itself.

We do not read dispersion as a failure. Suicide is genuinely multi-disciplinary, and forcing its literature into specialty journals would isolate it from the psychiatric, epidemiological, and policy communities whose engagement it needs. But dispersion should be managed rather than ignored, and managing it requires exactly the kind of cross-cutting infrastructure this paper describes.

### Social determinants and the prevention continuum

That 23.87% of articles (23,069 of 96,641) engage a social determinant of health is a figure the field should sit with. Roughly three articles in four do not. Suicide risk is patterned by economic conditions, housing, incarceration, discrimination, and access to lethal means, determinants that operate upstream of the clinical encounter and that account for a substantial share of population-level variation. A research literature weighted toward individual-level clinical prediction, in a field where individual-level prediction has repeatedly been shown to perform near chance, is a literature allocating effort away from where population impact is most plausible.

The prevention-continuum distribution (**Figure 8**) points the same way, and more sharply. Only 8.9% of the corpus sits anywhere on the prevention continuum; the rest is descriptive, aetiological, or measurement work. Within the portion that does, treatment-level research (6.2% of all records) outweighs universal prevention (0.4%) by roughly sixteen to one. Most people who die by suicide are not in current psychiatric treatment, so a literature weighted this heavily toward the treatment end is allocating effort away from most of the deaths. The same asymmetry appears in the means data: pesticide ingestion is among the leading global methods and accounts for 1.3% of the corpus, against 2.7% for firearms, a ratio that reflects where suicide research is funded rather than where suicide happens.

These figures come from lexical extraction and should be read as reliable in direction and approximate in magnitude. The direction is not subtle, and it is the kind of mismatch that only becomes visible once someone builds the instrument to look.

### Methodological contribution

Three elements of the approach may be useful beyond suicide research.

**Distant supervision from human indexing.** Where a corpus carries human-assigned controlled vocabulary, that indexing can supervise a text classifier at zero annotation cost and simultaneously provide validation at a scale hand-coding cannot reach. This is cheaper than LLM classification, reproducible without specialized hardware, inspectable, and validated against human judgment on tens of thousands of records rather than a hundred. Where MEDLINE indexing is absent (much of the social-science literature), the LLM path remains available and is shipped with the pipeline.

**Hybrid venue-plus-topic inclusion.** Any topic-defined field faces the corpus-definition problem described here. Tagging every record by venue tier converts the problem into a measurement, and the dispersion measure that results is substantively informative.

**Reproducibility as a design constraint rather than an aspiration.** Building only on sources reachable without subscription imposes real costs, most visibly the OpenAlex request budget. We regard the trade as correct. A field's shared infrastructure should not be rebuildable only by those who can pay for it.

### Limitations

Several limitations constrain interpretation.

**Coverage is incomplete and unevenly so.** The OpenAlex topical channel is complete only for 1989–2000 in this release. More fundamentally, all three sources under-represent non-English-language scholarship and journals from low- and middle-income countries, which are precisely the settings bearing the greatest suicide burden. Any statement here about the global distribution of suicide research is a statement about the indexed, largely English-language literature.

**Classification is imperfect and non-uniformly sourced.** Records with MEDLINE indexing carry human labels; the rest carry model labels with quantified but non-zero error. The `cls_backend` field permits any analysis to be restricted to human-labeled records, and we recommend that any result that matters be checked that way. Abstract-based classification also cannot see what abstracts omit: a study's design is sometimes clearer in its methods section than in its abstract.

**Authors are not disambiguated.** Counting distinct author strings overcounts distinct people. Analyses of individual trajectories, institutional contribution, or collaboration networks require a disambiguation step SRED does not perform.

**Citation counts are open-source counts.** They come from OpenAlex and Europe PMC, and they are systematically *different* from Web of Science counts rather than merely smaller, open citation graphs cover non-commercial and regional venues better and older material worse. They should not be compared directly against commercial figures.

**Topical delineation is a choice with consequences.** Title-based and MeSH-major-topic delineation prioritizes precision. Some genuine suicide research that neither names suicide in its title nor receives a major-topic designation is classified peripheral. The peripheral set is retained and flagged, and we report the recall-oriented count for sensitivity, but the primary corpus reflects a deliberate precision preference.

**Extraction fields are lexically derived in this release.** The prevention-level, population, and social-determinant fields were extracted with high-precision patterns rather than the LLM backend. They should be read as reliable in direction and approximate in magnitude, and they are the highest priority for the LLM upgrade.

**Growth estimates confound real growth with improving indexing.** Retrospective indexing is less complete for earlier years, so some of the observed increase reflects better coverage of recent material rather than more research.

### Future directions

The infrastructure supports several immediate extensions: topic modeling of abstracts to characterize thematic evolution; coauthorship network analysis to identify collaboration structures and international participation; analysis of funding acknowledgments to link research support to methodological and topical choices; systematic comparison of research effort against epidemiological burden by country, age group, and method of death; and comparison of SRED against Scopus and Web of Science to quantify what commercial indexing adds. Sustaining the resource requires scheduled incremental updates and periodic retrospective gap-filling, both of which the pipeline supports.

---

## Conclusion

Suicide research is growing at rates matching science overall, has become predominantly empirical, is increasingly collaborative, and remains methodologically concentrated in quantitative approaches. It is also structurally dispersed. The substantial majority of its output appears outside its own specialty journals, which shapes how its evidence accumulates, how its methods converge, and how reliably it can be synthesized. The Suicide Research Evidence Database makes these patterns visible and, being fully open and reproducible, makes them re-checkable by anyone. The field's most consequential open question is not how much it produces, but whether that production is distributed where suicide deaths actually occur. That question is now answerable.

---

## Declarations

**Data and code availability.** The complete pipeline, configuration, derived data tables, figures, and this manuscript's build system are openly available at https://github.com/yunyu118/suicide-research-evidence-database (code under MIT, data under CC BY 4.0). The repository includes an abstract-free release of all 96,641 records as Parquet; the full relational database is distributed as a DuckDB release asset, and abstracts are omitted from redistribution for copyright reasons but can be re-fetched for every record from the DOIs and PMIDs retained in the release. The build is reproducible end to end with six commands and no institutional subscription; see `docs/reproducing.md`. Continuous integration runs the full pipeline against a synthetic fixture corpus on every commit, and `scripts/05_verify.py` independently re-derives each numeric claim in this manuscript from the corpus and fails the build on any mismatch.

**Funding.** [To be completed.]

**Conflicts of interest.** [To be completed.]

**Ethical approval.** Not required; the study analyzes published bibliographic metadata.

**Author contributions.** [CRediT statement to be completed.]

**Acknowledgments.** We thank Brian E. Perron, Bryan G. Victor, and Zia Qi, whose Social Work Research Database provided the methodological template this work adapts.

---

## References

Birkle, C., Pendlebury, D. A., Schnell, J., & Adams, J. (2020). Web of Science as a data source for research on scientific and scholarly activity. *Quantitative Science Studies, 1*(1), 363–376. https://doi.org/10.1162/qss_a_00018

de Solla Price, D. J. (1963). *Little science, big science*. Columbia University Press.

Haghani, M. (2023). What makes an informative and publication-worthy scientometric analysis of literature: A guide for authors, reviewers and editors. *Transportation Research Interdisciplinary Perspectives, 22*, 100956. https://doi.org/10.1016/j.trip.2023.100956

Perron, B. E., Luan, H., Qi, Z., Victor, B. G., & Goyal, K. (2025). Demystifying application programming interfaces (APIs): Unlocking the power of large language models and other web-based AI services in social work research. *Journal of the Society for Social Work and Research, 16*(2), 275–294. https://doi.org/10.1086/735364

Perron, B. E., Luan, H., Victor, B. G., Hiltz-Perron, O., & Ryan, J. (2025). Moving beyond ChatGPT: Local large language models (LLMs) and the secure analysis of confidential unstructured text data in social work research. *Research on Social Work Practice, 35*(6), 695–710. https://doi.org/10.1177/10497315241280686

Perron, B. E., & Qi, Z. (2025). Theoretical and methodological shifts in social work research: An AI-driven analysis of postmodern and critical theory at the SSWR Annual Conference. *Research on Social Work Practice*. https://doi.org/10.1177/10497315251352838

Perron, B. E., Victor, B. G., Hodge, D. R., Salas-Wright, C. P., Vaughn, M. G., & Taylor, R. J. (2017). Laying the foundations for scientometric research: A data science approach. *Research on Social Work Practice, 27*(7), 802–812. https://doi.org/10.1177/1049731515624966

Perron, B. E., Victor, B. G., & Qi, Z. (2026). Evolution of social work knowledge production over 35 years: An AI-enabled analysis of trends in empiricism, methodology, collaboration, citation patterns, and output. *Research on Social Work Practice*. https://doi.org/10.1177/10497315261416833

Singh, V. K., Singh, P., Karmakar, M., Leta, J., & Mayr, P. (2021). The journal coverage of Web of Science, Scopus and Dimensions: A comparative analysis. *Scientometrics, 126*(6), 5113–5142. https://doi.org/10.1007/s11192-021-03948-5

Victor, B. G., Hodge, D. R., Perron, B. E., Vaughn, M. G., & Salas-Wright, C. P. (2017). The rise of co-authorship in social work scholarship: A longitudinal study of collaboration and article quality, 1989–2013. *British Journal of Social Work, 47*(8), 2201–2216. https://doi.org/10.1093/bjsw/bcw059

Waltman, L., & Noyons, E. (2022). *Bibliometrics for research management and research evaluation: A brief introduction*. CWTS. https://www.cwts.nl/pdf/CWTS_bibliometrics.pdf

Wuchty, S., Jones, B. F., & Uzzi, B. (2007). The increasing dominance of teams in production of knowledge. *Science, 316*(5827), 1036–1039. https://doi.org/10.1126/science.1136099

*[Additional suicide-specific references, WHO global estimates, Franklin et al. (2017) risk-factor meta-analysis, Zalsman et al. (2016) prevention strategies review, Turecki & Brent (2016), and the lethal-means restriction literature, to be added by coauthors during revision.]*
