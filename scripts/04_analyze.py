#!/usr/bin/env python3
"""Analysis - scientometric measures, tables, and figures.

Consumes ``data/processed/sred_classified.parquet`` and writes:

    data/processed/tables/*.csv    every table in the manuscript
    figures/*.png|pdf              every figure in the manuscript
    data/processed/results.json    every number quoted in the manuscript

``results.json`` exists so that no figure in the text is hand-copied. The
manuscript build reads it, which means a re-run of the pipeline cannot leave
stale numbers behind in the prose.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sred.analysis import figures as F  # noqa: E402
from sred.analysis import metrics as M  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
TABLES = PROCESSED / "tables"
FIGURES = ROOT / "figures"
INTERIM = ROOT / "data" / "interim"

# Log directory must exist before logging is configured. Git does not track
# empty directories, so a fresh clone has no logs/ and FileHandler would raise
# FileNotFoundError before the first line of work. This bit CI on the very
# first run, which is exactly what CI is for.
(ROOT / "logs").mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout),
                              logging.FileHandler(ROOT / "logs" / "analyze.log")])
log = logging.getLogger("analyze")


def save_table(df: pd.DataFrame, name: str) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES / f"{name}.csv", index=False)
    log.info("table -> %s.csv (%d rows)", name, len(df))


def main() -> int:
    src = PROCESSED / "sred_classified.parquet"
    if not src.exists():
        log.error("missing %s - run 03_classify.py first", src)
        return 1

    with open(ROOT / "config" / "query_terms.yml") as fh:
        cfg = yaml.safe_load(fh)
    trend_end = int(cfg["date_range"]["trend_end_year"])
    baseline = int(cfg["date_range"]["baseline_year"])
    # Two clocks. trend_end governs anything counted at publication; cite_end
    # governs anything counted afterwards. Conflating them makes recent papers
    # look uninfluential when they are merely recent.
    cite_end = int(cfg["date_range"].get("citation_end_year", trend_end))

    df = pd.read_parquet(src)
    df = df[df["year"].notna()].copy()
    df["year"] = df["year"].astype(int)
    log.info("analysing %d records (%d-%d)", len(df), df["year"].min(), df["year"].max())

    R: dict = {
        "corpus": {
            "n_records": int(len(df)),
            "year_min": int(df["year"].min()),
            "year_max": int(df["year"].max()),
            "n_journals": int(df["journal_canonical"].nunique()),
            "n_specialty_journal_records": int((df["venue_tier"] == "core_a").sum()),
            "n_adjacent_journal_records": int((df["venue_tier"] == "adjacent_b").sum()),
            "n_dispersed_records": int((df["venue_tier"] == "dispersed").sum()),
            "pct_with_doi": round(float(df["doi"].notna().mean() * 100), 2),
            "pct_with_citations": round(float(df["cited_by_count"].notna().mean() * 100), 2),
            "trend_window": [baseline, trend_end],
            "citation_window": [baseline, cite_end],
            "citation_accrual_years_min":
                int(cfg["date_range"].get("citation_accrual_years_min", 0)),
            # Years beyond trend_end are held in the corpus but kept off every
            # trend line. Reporting the count makes that explicit rather than
            # leaving a reader to infer it from a gap in a figure.
            "n_partial_year_records":
                int((df["year"] > trend_end).sum()),
            "partial_years": sorted(int(y) for y in
                                    df.loc[df["year"] > trend_end, "year"].unique()),
        }
    }

    # --- growth -----------------------------------------------------------
    growth = M.growth_by_year(df, trend_end, baseline)
    R["growth"] = M.growth_summary(growth)
    save_table(growth, "t_growth_by_year")
    save_table(M.records_by_decade(df), "t_records_by_decade")
    R["records_by_decade"] = M.records_by_decade(df).to_dict("records")

    # --- empiricism -------------------------------------------------------
    emp_year = M.empiricism_by_year(df, trend_end)
    emp_dec = M.empiricism_by_decade(df)
    save_table(emp_year, "t_empiricism_by_year")
    save_table(emp_dec, "t_empiricism_by_decade")
    R["empiricism_by_decade"] = emp_dec.to_dict("records")
    sci = df[df["is_scientific"] == True]  # noqa: E712
    R["empiricism"] = {
        "n_scientific": int(len(sci)),
        "n_empirical": int((sci["is_empirical"] == True).sum()),  # noqa: E712
        "n_non_empirical": int((sci["is_empirical"] == False).sum()),  # noqa: E712
        "n_unclassified": int(sci["is_empirical"].isna().sum()),
        "pct_empirical": round(float((sci["is_empirical"] == True).mean() * 100), 2),  # noqa: E712
    }

    # --- methodology ------------------------------------------------------
    meth = M.methodology_distribution(df)
    meth_dec = M.methodology_by_decade(df)
    meth_year = M.methodology_by_year(df, trend_end)
    save_table(meth, "t_methodology_overall")
    save_table(meth_dec, "t_methodology_by_decade")
    save_table(meth_year, "t_methodology_by_year")
    R["methodology_overall"] = meth.to_dict("records")
    R["methodology_by_decade"] = meth_dec.to_dict("records")

    # --- collaboration ----------------------------------------------------
    collab = M.collaboration_by_year(df, trend_end)
    collab_dec = M.collaboration_by_decade(df)
    save_table(collab, "t_collaboration_by_year")
    save_table(collab_dec, "t_collaboration_by_decade")
    save_table(M.author_count_distribution(df), "t_author_count_distribution")
    R["collaboration_by_decade"] = collab_dec.to_dict("records")
    valid = df[df["n_authors"] > 0]
    R["collaboration"] = {
        "mean_authors_overall": round(float(valid["n_authors"].mean()), 2),
        "median_authors_overall": float(valid["n_authors"].median()),
        "pct_multi_authored": round(float((valid["n_authors"] > 1).mean() * 100), 2),
        "max_authors": int(valid["n_authors"].max()),
    }

    # --- citations --------------------------------------------------------
    R["citations"] = M.citation_summary(df, cite_end)
    jt = M.citations_by_journal(df, cite_end, min_papers=25)
    save_table(jt, "t_citations_by_journal")
    save_table(jt.head(60), "t1_top_journals")
    cm = M.citations_by_methodology(df, cite_end)
    save_table(cm, "t_citations_by_methodology")
    R["citations_by_methodology"] = cm.to_dict("records")
    unc = M.uncited_by_year(df, cite_end)
    save_table(unc, "t_uncited_by_year")

    spec = df[df["venue_tier"] == "core_a"]
    if len(spec) and spec["cited_by_count"].notna().any():
        R["citations_specialty_vs_dispersed"] = {
            "specialty": M.citation_summary(spec, cite_end),
            "dispersed": M.citation_summary(df[df["venue_tier"] == "dispersed"], cite_end),
        }

    # --- SRED-specific ----------------------------------------------------
    disp = M.dispersion_by_year(df, trend_end)
    save_table(disp, "t_dispersion_by_year")
    R["dispersion"] = {
        "first_year_pct_specialty": float(disp["pct_specialty"].iloc[0]) if len(disp) else None,
        "last_year_pct_specialty": float(disp["pct_specialty"].iloc[-1]) if len(disp) else None,
        "overall_pct_specialty": round(float((df["venue_tier"] == "core_a").mean() * 100), 2),
    }

    for col, multi in [("prevention_level", False), ("outcome_construct", True),
                       ("population", True), ("study_design", True),
                       ("sdoh_domain", True), ("means_focus", True)]:
        dist = M.field_distribution(df, col, multi)
        bydec = M.field_by_decade(df, col, multi)
        save_table(dist, f"t_{col}_overall")
        save_table(bydec, f"t_{col}_by_decade")
        R[f"{col}_overall"] = dist.head(20).to_dict("records")

    if "sdoh_focus" in df.columns:
        sd = df["sdoh_focus"]
        sd = sd.map({True: True, "True": True, "true": True}).fillna(False)
        R["sdoh"] = {
            "pct_sdoh_focused": round(float(sd.mean() * 100), 2),
            "n_sdoh_focused": int(sd.sum()),
        }
        by_dec = df.assign(_sd=sd, _dec=df["year"].apply(M.decade)) \
                   .groupby("_dec")["_sd"].agg(n="count", pct=lambda s: round(s.mean() * 100, 1)) \
                   .reset_index().rename(columns={"_dec": "decade"})
        save_table(by_dec, "t_sdoh_focus_by_decade")
        R["sdoh_by_decade"] = by_dec.to_dict("records")

    ov = M.source_overlap(df)
    save_table(ov, "t_source_overlap")
    R["source_overlap"] = ov.to_dict("records")
    R["single_source_only_pct"] = round(
        float(ov.loc[ov["n_sources"] == 1, "pct"].sum()), 2)

    # --- figures ----------------------------------------------------------
    FIGURES.mkdir(parents=True, exist_ok=True)
    F.fig1_growth(growth, R["growth"], FIGURES)
    F.fig2_empiricism(emp_year, FIGURES)
    F.fig3_methodology(meth_year, FIGURES)
    F.fig4_collaboration(collab, FIGURES)
    F.fig5_uncited(unc, FIGURES)
    F.fig6_dispersion(disp, FIGURES)
    F.fig7_sdoh(M.field_by_decade(df, "sdoh_domain", True), FIGURES)
    F.fig8_prevention(M.field_by_decade(df, "prevention_level", False), FIGURES)

    # --- carry forward upstream reports -----------------------------------
    for name in ("dedup_report", "screen_report", "qa_report",
                 "validation_report", "classifier_summary"):
        p = INTERIM / f"{name}.json"
        if p.exists():
            with contextlib.suppress(json.JSONDecodeError):
                R[name] = json.loads(p.read_text())
    # Convenience roll-ups the manuscript cites directly.
    prev = {r["prevention_level"]: r["pct"] for r in R.get("prevention_level_overall", [])}
    R["prevention_assignable_pct"] = round(100 - prev.get("not_applicable", 0), 1)
    means = {r["means_focus"]: r["pct"] for r in R.get("means_focus_overall", [])}
    R["means_addressed_pct"] = round(100 - means.get("none", 0), 1)

    # Surface the temporal-validation kappa range as a top-level figure so the
    # manuscript can cite it without reaching three levels into a nested report.
    temporal = (R.get("validation_report") or {}).get("temporal") or {}
    ks = [v["kappa"] for v in temporal.values()
          if isinstance(v, dict) and isinstance(v.get("kappa"), (int, float))]
    R["temporal_min"] = min(ks) if ks else None
    R["temporal_max"] = max(ks) if ks else None
    R["temporal_n_folds"] = len(ks)

    # Trim the bulky review-pair sample out of the headline results file.
    if isinstance(R.get("dedup_report"), dict):
        R["dedup_report"].pop("review_pairs_sample", None)

    (PROCESSED / "results.json").write_text(json.dumps(R, indent=2, default=str))
    log.info("wrote results.json")
    print(json.dumps({k: R[k] for k in ("corpus", "growth", "empiricism",
                                        "collaboration", "citations", "dispersion")
                      if k in R}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
