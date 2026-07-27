#!/usr/bin/env python3
"""Load the processed corpus into a relational database.

Two engines are supported and they serve different audiences:

``duckdb`` (default)
    Zero-configuration, single-file, and reads the Parquet outputs directly.
    This is what a reader who clones the repository should use - the whole
    database materialises in under a minute with no server to install.

``postgres``
    For the hosted deployment, matching the PostgreSQL/Supabase architecture
    Perron et al. describe. Use when the database backs a web front end or
    needs concurrent writers for incremental updates.

Usage
-----
    python -m sred.db.load --engine duckdb --out data/releases/sred.duckdb
    python -m sred.db.load --engine postgres --dsn postgresql://user@host/sred
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from sred.integrate.normalize import normalize_author  # noqa: E402

log = logging.getLogger("db.load")

PROCESSED = ROOT / "data" / "processed"


def _jload(v, default):
    if isinstance(v, (list, dict)):
        return v
    if isinstance(v, str) and v.strip().startswith(("[", "{")):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return default
    return default


def build_frames(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Explode the flat analytic table into the normalised relational model."""
    # --- journals ---------------------------------------------------------
    jt = (df.groupby("journal_canonical")
            .agg(issn_l=("issn_l", lambda s: s.dropna().iloc[0] if s.notna().any() else None),
                 publisher=("publisher", lambda s: s.dropna().iloc[0] if s.notna().any() else None),
                 venue_tier=("venue_tier", lambda s: ("core_a" if (s == "core_a").any()
                                                      else "adjacent_b" if (s == "adjacent_b").any()
                                                      else "dispersed")),
                 founded_year=("year", "min"))
            .reset_index()
            .rename(columns={"journal_canonical": "canonical_name"}))
    jt = jt[jt["canonical_name"].astype(str).str.len() > 0].reset_index(drop=True)
    jt.insert(0, "journal_id", range(1, len(jt) + 1))
    jmap = dict(zip(jt["canonical_name"], jt["journal_id"]))

    # --- papers -----------------------------------------------------------
    papers = pd.DataFrame({
        "sred_id": df["sred_id"],
        "doi": df["doi"],
        "pmid": df["pmid"],
        "title": df["title"],
        "abstract": df["abstract"],
        "journal_id": df["journal_canonical"].map(jmap),
        "journal_raw": df["journal_raw"],
        "publication_year": df["year"],
        "publication_date": df.get("pub_date"),
        "volume": df.get("volume"),
        "issue": df.get("issue"),
        "pages": df.get("pages"),
        "doc_type_raw": df.get("doc_type_raw"),
        "language": df.get("language"),
        "is_open_access": df.get("is_oa"),
        "n_authors": df["n_authors"].fillna(0).astype(int),
        "references_count": df.get("references_count"),
        "cited_by_count": df.get("cited_by_count"),
        "citation_source": df.get("citation_source"),
        "url": df.get("url"),
        "is_retracted": df.get("retracted", False),
        "sources": df["source"],
        "source_ids": df.get("source_ids"),
        "harvest_ts": df.get("harvest_ts"),
        "schema_version": df.get("schema_version"),
        "venue_tier": df["venue_tier"],
        "topic_focus": df.get("topic_focus"),
        "screen_pass": df.get("screen_pass"),
        "screen_reason": df.get("screen_reason"),
        "is_scientific": df.get("is_scientific"),
        "is_empirical": df.get("is_empirical"),
        "methodology": df.get("methodology"),
        "cls_backend": df.get("cls_backend"),
        "cls_confidence": df.get("cls_confidence"),
    })

    # --- authors + paper_authors -----------------------------------------
    auth_rows, link_rows = [], []
    seen: dict[str, int] = {}
    next_id = 1
    for sred_id, raw in zip(df["sred_id"], df["authors"]):
        for a in _jload(raw, []):
            name = (a or {}).get("name")
            if not name:
                continue
            norm = normalize_author(name)
            orcid = a.get("orcid")
            key = f"orcid:{orcid}" if orcid else f"name:{norm.lower()}"
            aid = seen.get(key)
            if aid is None:
                aid = next_id
                next_id += 1
                seen[key] = aid
                auth_rows.append({"author_id": aid, "display_name": name,
                                  "normalized_name": norm, "orcid": orcid,
                                  "openalex_author_id": None,
                                  "is_disambiguated": bool(orcid)})
            link_rows.append({"sred_id": sred_id, "author_id": aid,
                              "author_position": int(a.get("position") or 0) or 1,
                              "raw_affiliation": a.get("affiliation")})

    authors = pd.DataFrame(auth_rows)
    paper_authors = pd.DataFrame(link_rows)
    if not paper_authors.empty:
        paper_authors = paper_authors.drop_duplicates(
            subset=["sred_id", "author_position"], keep="first")

    # --- mesh -------------------------------------------------------------
    mesh_rows = []
    for sred_id, m_all, m_maj in zip(df["sred_id"], df.get("mesh_terms", ""),
                                     df.get("mesh_major_terms", "")):
        major = set(_jload(m_maj, []))
        for d in _jload(m_all, []):
            if d:
                mesh_rows.append({"sred_id": sred_id, "descriptor": d,
                                  "is_major_topic": d in major})
    paper_mesh = pd.DataFrame(mesh_rows).drop_duplicates(subset=["sred_id", "descriptor"]) \
        if mesh_rows else pd.DataFrame(columns=["sred_id", "descriptor", "is_major_topic"])

    # --- funders ----------------------------------------------------------
    fund_rows = []
    for sred_id, f in zip(df["sred_id"], df.get("funders", "")):
        for name in _jload(f, []):
            if name:
                fund_rows.append({"sred_id": sred_id, "funder_name": name})
    paper_funders = pd.DataFrame(fund_rows).drop_duplicates() if fund_rows \
        else pd.DataFrame(columns=["sred_id", "funder_name"])

    # --- extraction -------------------------------------------------------
    extraction = pd.DataFrame({
        "sred_id": df["sred_id"],
        "prevention_level": df.get("prevention_level"),
        "outcome_construct": df.get("outcome_construct"),
        "population": df.get("population"),
        "study_design": df.get("study_design"),
        "sdoh_focus": df.get("sdoh_focus"),
        "sdoh_domain": df.get("sdoh_domain"),
        "means_focus": df.get("means_focus"),
        "geography": df.get("geography"),
        "extraction_backend": df.get("cls_backend"),
        "extraction_confidence": df.get("cls_confidence"),
    })

    return {"journals": jt, "papers": papers, "authors": authors,
            "paper_authors": paper_authors, "paper_mesh": paper_mesh,
            "paper_funders": paper_funders, "paper_extraction": extraction}


def load_duckdb(frames: dict[str, pd.DataFrame], out: Path) -> None:
    import duckdb

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = duckdb.connect(str(out))
    for name, frame in frames.items():
        con.register(f"_{name}", frame)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM _{name}")
        con.unregister(f"_{name}")
        log.info("duckdb: %-18s %7d rows", name, len(frame))

    con.execute("""
        CREATE VIEW v_analytic_corpus AS
        SELECT p.*, j.canonical_name AS journal, j.venue_tier AS journal_tier,
               e.prevention_level, e.sdoh_focus, e.sdoh_domain, e.population,
               e.outcome_construct, e.study_design, e.means_focus
        FROM papers p
        LEFT JOIN journals j USING (journal_id)
        LEFT JOIN paper_extraction e USING (sred_id)
        WHERE p.screen_pass AND p.is_scientific;
    """)
    con.execute("""
        CREATE VIEW v_annual_output AS
        SELECT publication_year AS year, COUNT(*) AS n_articles,
               COUNT(DISTINCT journal_id) AS n_journals,
               ROUND(AVG(n_authors), 2) AS mean_authors,
               ROUND(AVG(CASE WHEN is_empirical THEN 1.0 ELSE 0.0 END), 4) AS prop_empirical
        FROM v_analytic_corpus GROUP BY 1 ORDER BY 1;
    """)
    con.close()
    log.info("duckdb written -> %s (%.1f MB)", out, out.stat().st_size / 1e6)


def load_postgres(frames: dict[str, pd.DataFrame], dsn: str) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(dsn)
    ddl = (Path(__file__).parent / "schema.sql").read_text()
    with engine.begin() as con:
        con.execute(text(ddl))
    order = ["journals", "authors", "papers", "paper_authors", "paper_mesh",
             "paper_funders", "paper_extraction"]
    for name in order:
        frames[name].to_sql(name, engine, if_exists="append", index=False,
                            method="multi", chunksize=5000)
        log.info("postgres: %-18s %7d rows", name, len(frames[name]))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["duckdb", "postgres"], default="duckdb")
    ap.add_argument("--src", default=str(PROCESSED / "sred_classified.parquet"))
    ap.add_argument("--out", default=str(ROOT / "data" / "releases" / "sred.duckdb"))
    ap.add_argument("--dsn", default="")
    args = ap.parse_args()

    df = pd.read_parquet(args.src)
    log.info("loaded %d records from %s", len(df), Path(args.src).name)
    frames = build_frames(df)

    if args.engine == "duckdb":
        load_duckdb(frames, Path(args.out))
    else:
        if not args.dsn:
            log.error("--dsn required for postgres")
            return 1
        load_postgres(frames, args.dsn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
