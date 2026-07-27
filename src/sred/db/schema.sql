-- Suicide Research Evidence Database (SRED) - relational schema
--
-- Mirrors the eight-table PostgreSQL/Supabase design of Perron, Victor & Qi
-- (2026), extended with the tables suicide research needs and social work
-- does not: a venue-tier registry that distinguishes specialty from dispersed
-- publication, and a structured extraction table for prevention level,
-- outcome construct, population, and social-determinant focus.
--
-- Designed for PostgreSQL 14+. Also runs on DuckDB with the GENERATED and
-- extension clauses removed (see db/load.py --engine duckdb).

BEGIN;

-- ---------------------------------------------------------------------------
-- Reference tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS journals (
    journal_id        SERIAL PRIMARY KEY,
    canonical_name    TEXT NOT NULL UNIQUE,
    issn_l            TEXT,
    issn_print        TEXT,
    issn_electronic   TEXT,
    publisher         TEXT,
    society           TEXT,
    founded_year      INT,
    ceased_year       INT,
    -- core_a    = dedicated suicidology journal (venue-based inclusion)
    -- adjacent_b= thanatology / crisis journal (topical inclusion applies)
    -- dispersed = any other venue, entered topically
    venue_tier        TEXT NOT NULL DEFAULT 'dispersed'
                      CHECK (venue_tier IN ('core_a', 'adjacent_b', 'dispersed')),
    in_web_of_science BOOLEAN,
    in_scopus         BOOLEAN,
    in_medline        BOOLEAN,
    in_doaj           BOOLEAN,
    notes             TEXT
);

CREATE INDEX IF NOT EXISTS idx_journals_issn ON journals (issn_l);
CREATE INDEX IF NOT EXISTS idx_journals_tier ON journals (venue_tier);

CREATE TABLE IF NOT EXISTS authors (
    author_id         SERIAL PRIMARY KEY,
    display_name      TEXT NOT NULL,
    normalized_name   TEXT NOT NULL,
    orcid             TEXT,
    openalex_author_id TEXT,
    -- Author disambiguation is deliberately NOT performed at load time; see
    -- the limitations section of the manuscript. ORCID is the only identifier
    -- treated as authoritative, and normalized_name is a surface form, not an
    -- identity claim.
    is_disambiguated  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_authors_norm ON authors (normalized_name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_authors_orcid
    ON authors (orcid) WHERE orcid IS NOT NULL;

CREATE TABLE IF NOT EXISTS organizations (
    org_id            SERIAL PRIMARY KEY,
    display_name      TEXT NOT NULL,
    normalized_name   TEXT NOT NULL,
    ror_id            TEXT,
    country_code      TEXT,
    org_type          TEXT
);

CREATE INDEX IF NOT EXISTS idx_orgs_norm ON organizations (normalized_name);

-- ---------------------------------------------------------------------------
-- Core bibliographic table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS papers (
    sred_id           TEXT PRIMARY KEY,
    doi               TEXT,
    pmid              TEXT,
    title             TEXT NOT NULL,
    abstract          TEXT,
    journal_id        INT REFERENCES journals (journal_id),
    journal_raw       TEXT,
    publication_year  INT,
    publication_date  DATE,
    volume            TEXT,
    issue             TEXT,
    pages             TEXT,
    doc_type_raw      TEXT,
    language          TEXT,
    is_open_access    BOOLEAN,
    n_authors         INT NOT NULL DEFAULT 0,
    references_count  INT,
    cited_by_count    INT,
    citation_source   TEXT,
    url               TEXT,
    is_retracted      BOOLEAN NOT NULL DEFAULT FALSE,

    -- provenance
    sources           TEXT[],          -- every provider that returned this work
    source_ids        JSONB,           -- provider -> native identifier
    harvest_ts        TIMESTAMPTZ,
    schema_version    TEXT,

    -- inclusion
    venue_tier        TEXT CHECK (venue_tier IN ('core_a', 'adjacent_b', 'dispersed')),
    topic_focus       TEXT CHECK (topic_focus IN ('focused', 'peripheral', 'venue_only')),
    screen_pass       BOOLEAN,
    screen_reason     TEXT,

    -- three-stage classification (Perron et al. parallel)
    is_scientific     BOOLEAN,
    is_empirical      BOOLEAN,
    methodology       TEXT CHECK (methodology IN
                        ('quantitative', 'qualitative', 'mixed', 'review')),
    cls_backend       TEXT,
    cls_confidence    NUMERIC(6, 4),

    CONSTRAINT chk_year CHECK (publication_year IS NULL
                               OR publication_year BETWEEN 1900 AND 2100),
    CONSTRAINT chk_citations CHECK (cited_by_count IS NULL OR cited_by_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_papers_year     ON papers (publication_year);
CREATE INDEX IF NOT EXISTS idx_papers_journal  ON papers (journal_id);
CREATE INDEX IF NOT EXISTS idx_papers_tier     ON papers (venue_tier);
CREATE INDEX IF NOT EXISTS idx_papers_method   ON papers (methodology);
CREATE INDEX IF NOT EXISTS idx_papers_empirical ON papers (is_empirical);
CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_doi  ON papers (doi)  WHERE doi  IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_pmid ON papers (pmid) WHERE pmid IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Link tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS paper_authors (
    sred_id           TEXT NOT NULL REFERENCES papers (sred_id) ON DELETE CASCADE,
    author_id         INT  NOT NULL REFERENCES authors (author_id) ON DELETE CASCADE,
    author_position   INT  NOT NULL,
    is_first          BOOLEAN GENERATED ALWAYS AS (author_position = 1) STORED,
    raw_affiliation   TEXT,
    PRIMARY KEY (sred_id, author_position)
);

CREATE INDEX IF NOT EXISTS idx_pa_author ON paper_authors (author_id);

CREATE TABLE IF NOT EXISTS author_affiliations (
    sred_id           TEXT NOT NULL REFERENCES papers (sred_id) ON DELETE CASCADE,
    author_id         INT  NOT NULL REFERENCES authors (author_id) ON DELETE CASCADE,
    org_id            INT  REFERENCES organizations (org_id),
    country_code      TEXT,
    PRIMARY KEY (sred_id, author_id, org_id)
);

CREATE TABLE IF NOT EXISTS paper_mesh (
    sred_id           TEXT NOT NULL REFERENCES papers (sred_id) ON DELETE CASCADE,
    descriptor        TEXT NOT NULL,
    is_major_topic    BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (sred_id, descriptor)
);

CREATE INDEX IF NOT EXISTS idx_mesh_desc ON paper_mesh (descriptor);

CREATE TABLE IF NOT EXISTS paper_funders (
    sred_id           TEXT NOT NULL REFERENCES papers (sred_id) ON DELETE CASCADE,
    funder_name       TEXT NOT NULL,
    PRIMARY KEY (sred_id, funder_name)
);

-- ---------------------------------------------------------------------------
-- SRED-specific extraction
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS paper_extraction (
    sred_id           TEXT PRIMARY KEY REFERENCES papers (sred_id) ON DELETE CASCADE,
    prevention_level  TEXT CHECK (prevention_level IN
                        ('universal', 'selective', 'indicated', 'treatment',
                         'postvention', 'not_applicable')),
    outcome_construct TEXT[],
    population        TEXT[],
    study_design      TEXT[],
    sdoh_focus        BOOLEAN,
    sdoh_domain       TEXT[],
    means_focus       TEXT[],
    geography         TEXT,
    extraction_backend TEXT,
    extraction_confidence NUMERIC(6, 4)
);

CREATE INDEX IF NOT EXISTS idx_extract_prev  ON paper_extraction (prevention_level);
CREATE INDEX IF NOT EXISTS idx_extract_sdoh  ON paper_extraction (sdoh_focus);

-- ---------------------------------------------------------------------------
-- Convenience views
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_analytic_corpus AS
SELECT p.*, j.canonical_name AS journal, j.venue_tier AS journal_tier,
       e.prevention_level, e.sdoh_focus, e.sdoh_domain, e.population,
       e.outcome_construct, e.study_design, e.means_focus
FROM papers p
LEFT JOIN journals j ON j.journal_id = p.journal_id
LEFT JOIN paper_extraction e ON e.sred_id = p.sred_id
WHERE p.screen_pass IS TRUE
  AND p.is_scientific IS TRUE;

CREATE OR REPLACE VIEW v_annual_output AS
SELECT publication_year AS year,
       COUNT(*)                                            AS n_articles,
       COUNT(DISTINCT journal_id)                          AS n_journals,
       AVG(n_authors)::NUMERIC(6, 2)                       AS mean_authors,
       AVG((is_empirical)::INT)::NUMERIC(6, 4)             AS prop_empirical,
       AVG((cited_by_count = 0)::INT)::NUMERIC(6, 4)       AS prop_uncited
FROM v_analytic_corpus
GROUP BY publication_year
ORDER BY publication_year;

COMMIT;
