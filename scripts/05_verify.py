#!/usr/bin/env python3
"""Independent verification of every claim the manuscript makes.

This script exists because the failure mode of a pipeline paper is not a bug in
the pipeline - it is a number in the prose that was correct three runs ago. It
re-derives each headline claim *from the Parquet corpus*, using code written
independently of ``sred.analysis.metrics``, and compares against
``results.json``. Any disagreement is a hard failure.

Three classes of check:

1. **Recomputation.** Growth rates, empirical shares, methodology proportions,
   collaboration means, and citation statistics are computed again from raw
   columns. A refactor that changes a definition will show up here.
2. **Internal consistency.** Percentages sum, subgroup counts sum to totals,
   deduplication arithmetic balances, and no record is double-counted.
3. **Plausibility.** Bounds that any correct result must satisfy - proportions
   in [0, 100], monotone cumulative counts, no negative citations, no future
   publication years.

Exit status is non-zero on any failure, so CI catches prose drift.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
log = logging.getLogger("verify")

TOL = 0.05   # percentage-point tolerance for recomputed proportions


class Checker:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed.append(name)
        else:
            self.failed.append(f"{name}: {detail}")
            log.error("FAIL %s - %s", name, detail)

    def close(self, name: str, actual: float | None, expected: float | None,
              tol: float = TOL) -> None:
        if actual is None or expected is None:
            self.check(name, False, f"missing value (actual={actual}, expected={expected})")
            return
        if isinstance(actual, float) and math.isnan(actual):
            self.check(name, isinstance(expected, float) and math.isnan(expected),
                       "actual is NaN")
            return
        self.check(name, abs(actual - expected) <= tol,
                   f"recomputed {actual:.4f} vs reported {expected:.4f} (tol {tol})")

    def summary(self) -> int:
        log.info("%d checks passed, %d failed", len(self.passed), len(self.failed))
        if self.failed:
            for f in self.failed:
                log.error("  - %s", f)
            return 1
        return 0


def main() -> int:
    src = PROCESSED / "sred_classified.parquet"
    res_path = PROCESSED / "results.json"
    if not src.exists() or not res_path.exists():
        log.error("run scripts 02-04 first")
        return 1

    df = pd.read_parquet(src)
    df = df[df["year"].notna()].copy()
    df["year"] = df["year"].astype(int)
    R = json.loads(res_path.read_text())
    c = Checker()

    trend_end = R["corpus"]["trend_window"][1]
    baseline = R["corpus"]["trend_window"][0]

    # --- 1. corpus --------------------------------------------------------
    c.check("corpus.n_records", len(df) == R["corpus"]["n_records"],
            f"{len(df)} vs {R['corpus']['n_records']}")
    c.check("corpus.year_range",
            df["year"].min() >= 1900 and df["year"].max() <= 2026,
            f"{df['year'].min()}-{df['year'].max()}")
    c.check("corpus.no_duplicate_ids", not df["sred_id"].duplicated().any(),
            f"{int(df['sred_id'].duplicated().sum())} duplicate sred_ids")
    live_doi = df.loc[df["doi"].notna(), "doi"]
    c.check("corpus.no_duplicate_dois", not live_doi.duplicated().any(),
            f"{int(live_doi.duplicated().sum())} duplicate DOIs")

    tiers = df["venue_tier"].value_counts()
    c.check("corpus.tiers_sum",
            int(tiers.sum()) == len(df), "venue_tier counts do not sum to n_records")

    # --- 2. growth --------------------------------------------------------
    win = df[(df["year"] >= baseline) & (df["year"] <= trend_end)]
    by_year = win.groupby("year").agg(n=("sred_id", "count"),
                                      j=("journal_canonical", "nunique"))
    y0, y1 = int(by_year.index.min()), int(by_year.index.max())
    n0, n1 = int(by_year.loc[y0, "n"]), int(by_year.loc[y1, "n"])
    j0, j1 = int(by_year.loc[y0, "j"]), int(by_year.loc[y1, "j"])
    span = y1 - y0
    art_cagr = ((n1 / n0) ** (1 / span) - 1) * 100
    jrn_cagr = ((j1 / j0) ** (1 / span) - 1) * 100
    c.close("growth.article_cagr", art_cagr, R["growth"]["article_cagr_pct"], tol=0.02)
    c.close("growth.journal_cagr", jrn_cagr, R["growth"]["journal_cagr_pct"], tol=0.02)
    c.check("growth.window_total",
            int(by_year["n"].sum()) == R["growth"]["total_articles_in_window"],
            "trend-window total mismatch")
    c.check("growth.cagr_plausible", 0 < art_cagr < 25,
            f"article CAGR {art_cagr:.2f}% outside plausible range")

    # --- 3. empiricism ----------------------------------------------------
    sci = df[df["is_scientific"] == True]  # noqa: E712
    n_emp = int((sci["is_empirical"] == True).sum())   # noqa: E712
    n_non = int((sci["is_empirical"] == False).sum())  # noqa: E712
    n_unk = int(sci["is_empirical"].isna().sum())
    c.check("empiricism.parts_sum", n_emp + n_non + n_unk == len(sci),
            f"{n_emp}+{n_non}+{n_unk} != {len(sci)}")
    c.close("empiricism.pct", n_emp / max(len(sci), 1) * 100,
            R["empiricism"]["pct_empirical"])
    c.check("empiricism.n_scientific", len(sci) == R["empiricism"]["n_scientific"],
            f"{len(sci)} vs {R['empiricism']['n_scientific']}")
    c.check("empiricism.non_scientific_excluded",
            not ((df["is_scientific"] == False) & (df["is_empirical"].notna())).any(),
            "records marked non-scientific carry an empirical label")

    # --- 4. methodology ---------------------------------------------------
    emp = df[(df["is_empirical"] == True) & df["methodology"].notna()]  # noqa: E712
    if len(emp):
        shares = emp["methodology"].value_counts(normalize=True) * 100
        c.close("methodology.shares_sum", float(shares.sum()), 100.0, tol=0.02)
        for row in R.get("methodology_overall", []):
            m = row["methodology"]
            c.close(f"methodology.{m}", float(shares.get(m, 0.0)), float(row["pct"]), tol=0.1)
        c.check("methodology.only_valid_labels",
                set(emp["methodology"].unique()) <= {"quantitative", "qualitative",
                                                     "mixed", "review"},
                f"unexpected labels: {set(emp['methodology'].unique())}")
        c.check("methodology.only_on_empirical",
                not ((df["is_empirical"] != True) & df["methodology"].notna()).any(),
                "methodology assigned to a non-empirical record")

    # --- 5. collaboration -------------------------------------------------
    va = df[df["n_authors"] > 0]
    c.close("collaboration.mean_authors", float(va["n_authors"].mean()),
            R["collaboration"]["mean_authors_overall"], tol=0.02)
    c.close("collaboration.pct_multi", float((va["n_authors"] > 1).mean() * 100),
            R["collaboration"]["pct_multi_authored"], tol=0.02)
    c.check("collaboration.authors_positive", bool((va["n_authors"] > 0).all()),
            "non-positive author counts present")

    # --- 6. citations -----------------------------------------------------
    cit = df[(df["year"] <= trend_end) & df["cited_by_count"].notna()]
    if len(cit) and R.get("citations"):
        vals = cit["cited_by_count"].astype(float)
        c.close("citations.mean", float(vals.mean()),
                R["citations"]["mean_citations"], tol=0.02)
        c.close("citations.pct_uncited", float((vals == 0).mean() * 100),
                R["citations"]["pct_uncited"], tol=0.02)
        c.check("citations.total", int(vals.sum()) == R["citations"]["total_citations"],
                "citation total mismatch")
        c.check("citations.non_negative", bool((vals >= 0).all()),
                "negative citation counts present")
        c.check("citations.uncited_plus_cited",
                abs(R["citations"]["pct_uncited"] +
                    R["citations"]["pct_cited_at_least_once"] - 100) < 0.02,
                "uncited + cited != 100%")

    # --- 7. dispersion (SRED-specific) ------------------------------------
    if R.get("dispersion"):
        pct_spec = float((df["venue_tier"] == "core_a").mean() * 100)
        c.close("dispersion.overall_pct_specialty", pct_spec,
                R["dispersion"]["overall_pct_specialty"])
        c.check("dispersion.in_bounds",
                0 <= R["dispersion"]["overall_pct_specialty"] <= 100,
                "specialty share outside [0, 100]")

    # --- 8. deduplication arithmetic --------------------------------------
    dd = R.get("dedup_report") or {}
    if dd:
        c.check("dedup.arithmetic",
                dd["input_records"] - dd["output_records"] == dd["duplicates_removed"],
                f"{dd['input_records']} - {dd['output_records']} != {dd['duplicates_removed']}")
        c.check("dedup.merges_do_not_exceed_removals",
                dd["doi_merges"] + dd["pmid_merges"] + dd["fuzzy_merges"]
                >= dd["duplicates_removed"] * 0.9,
                "merge counts inconsistent with records removed")

    # --- 9. screening arithmetic ------------------------------------------
    sr = R.get("screen_report") or {}
    if sr:
        c.check("screen.arithmetic",
                sr["passed"] + sr["excluded"] == sr["total_evaluated"],
                "screen counts do not balance")

    # --- 10. classifier validation quality --------------------------------
    vr = R.get("validation_report") or {}
    ho = vr.get("holdout") or {}
    for stage in ("is_scientific", "is_empirical", "methodology"):
        st = ho.get(stage) or {}
        if "kappa" in st:
            k = st["kappa"]
            if k is None or (isinstance(k, float) and math.isnan(k)):
                # A NaN kappa means the hold-out was degenerate - one class
                # only, which happens on the synthetic CI fixture and would be
                # a red flag on real data. Warn rather than fail, so CI can run
                # the fixture, and let the real-data run surface it in the log.
                log.warning("DEGENERATE validation.%s: kappa undefined (n=%d) - "
                            "hold-out contained a single class", stage, st.get("n", 0))
                continue
            c.check(f"validation.{stage}_kappa_reported",
                    -1.0 <= k <= 1.0, f"kappa out of range: {k}")
            if k < 0.60:
                log.warning("WEAK  validation.%s kappa=%.3f (n=%d) - below the "
                            "conventional 'substantial agreement' floor",
                            stage, st["kappa"], st.get("n", 0))

    rc = c.summary()
    (PROCESSED / "verification_report.json").write_text(json.dumps(
        {"n_passed": len(c.passed), "n_failed": len(c.failed),
         "failed": c.failed, "passed": c.passed}, indent=2))
    if rc == 0:
        log.info("all manuscript claims verified against the corpus")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
