"""Scientometric measures.

Every function takes the screened SRED dataframe and returns tidy frames ready
for tabulation or plotting. Definitions follow Perron, Victor & Qi (2026) so
that SRED's results are directly comparable to theirs, with two deliberate
departures noted inline: the treatment of the recent-year boundary, and the
separation of specialty from dispersed venues.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def cagr(begin: float, end: float, n_years: int) -> float:
    """Compound annual growth rate, as a percentage.

    CAGR = [(ending / beginning)^(1/n)] - 1, following Perron et al. (2017).
    ``n_years`` is the number of *intervals*, i.e. last year minus first year,
    not the count of years observed - an off-by-one here inflates the rate by
    roughly 3% relative at a 35-year span.
    """
    if begin <= 0 or end <= 0 or n_years <= 0:
        return float("nan")
    return ((end / begin) ** (1.0 / n_years) - 1.0) * 100.0


def decade(year: int | float | None) -> str | None:
    if year is None or (isinstance(year, float) and np.isnan(year)):
        return None
    y = int(year)
    if y < 2000:
        return "1990s" if y >= 1990 else "1989"
    if y < 2010:
        return "2000s"
    if y < 2020:
        return "2010s"
    return "2020s"


# ---------------------------------------------------------------------------
# Growth
# ---------------------------------------------------------------------------

def growth_by_year(df: pd.DataFrame, trend_end: int = 2023,
                   baseline: int = 1989) -> pd.DataFrame:
    """Annual record and active-journal counts within the trend window."""
    d = df[(df["year"] >= baseline) & (df["year"] <= trend_end)]
    g = (d.groupby("year")
           .agg(n_articles=("sred_id", "count"),
                n_journals=("journal_canonical", "nunique"))
           .reset_index())
    return g


def growth_summary(g: pd.DataFrame) -> dict:
    if g.empty:
        return {}
    first, last = int(g["year"].min()), int(g["year"].max())
    n = last - first
    a0 = int(g.loc[g["year"] == first, "n_articles"].iloc[0])
    a1 = int(g.loc[g["year"] == last, "n_articles"].iloc[0])
    j0 = int(g.loc[g["year"] == first, "n_journals"].iloc[0])
    j1 = int(g.loc[g["year"] == last, "n_journals"].iloc[0])
    return {
        "first_year": first, "last_year": last, "n_intervals": n,
        "articles_first": a0, "articles_last": a1,
        "journals_first": j0, "journals_last": j1,
        "article_cagr_pct": round(cagr(a0, a1, n), 2),
        "journal_cagr_pct": round(cagr(j0, j1, n), 2),
        "cagr_differential_pp": round(cagr(a0, a1, n) - cagr(j0, j1, n), 2),
        "total_articles_in_window": int(g["n_articles"].sum()),
    }


def records_by_decade(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["decade"] = d["year"].apply(decade)
    out = (d.groupby("decade")
             .agg(n=("sred_id", "count"))
             .reset_index())
    out["pct"] = (out["n"] / out["n"].sum() * 100).round(1)
    order = ["1989", "1990s", "2000s", "2010s", "2020s"]
    out["_o"] = out["decade"].apply(lambda x: order.index(x) if x in order else 99)
    return out.sort_values("_o").drop(columns="_o").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Empiricism and methodology
# ---------------------------------------------------------------------------

def empiricism_by_year(df: pd.DataFrame, trend_end: int = 2023) -> pd.DataFrame:
    d = df[(df["is_scientific"]) & (df["year"] <= trend_end) & df["is_empirical"].notna()]
    g = (d.groupby("year")["is_empirical"]
           .agg(n_total="count", n_empirical="sum").reset_index())
    g["pct_empirical"] = (g["n_empirical"] / g["n_total"] * 100).round(2)
    return g


def empiricism_by_decade(df: pd.DataFrame) -> pd.DataFrame:
    d = df[(df["is_scientific"]) & df["is_empirical"].notna()].copy()
    d["decade"] = d["year"].apply(decade)
    g = (d.groupby("decade")["is_empirical"]
           .agg(n_total="count", n_empirical="sum").reset_index())
    g["pct_empirical"] = (g["n_empirical"] / g["n_total"] * 100).round(1)
    order = ["1989", "1990s", "2000s", "2010s", "2020s"]
    g["_o"] = g["decade"].apply(lambda x: order.index(x) if x in order else 99)
    return g.sort_values("_o").drop(columns="_o").reset_index(drop=True)


def methodology_distribution(df: pd.DataFrame) -> pd.DataFrame:
    d = df[(df["is_empirical"] == True) & df["methodology"].notna()]  # noqa: E712
    g = d["methodology"].value_counts().rename_axis("methodology").reset_index(name="n")
    g["pct"] = (g["n"] / g["n"].sum() * 100).round(1)
    return g


def methodology_by_decade(df: pd.DataFrame) -> pd.DataFrame:
    d = df[(df["is_empirical"] == True) & df["methodology"].notna()].copy()  # noqa: E712
    d["decade"] = d["year"].apply(decade)
    g = (d.groupby(["decade", "methodology"]).size()
           .rename("n").reset_index())
    tot = g.groupby("decade")["n"].transform("sum")
    g["pct"] = (g["n"] / tot * 100).round(1)
    order = ["1989", "1990s", "2000s", "2010s", "2020s"]
    g["_o"] = g["decade"].apply(lambda x: order.index(x) if x in order else 99)
    return g.sort_values(["_o", "methodology"]).drop(columns="_o").reset_index(drop=True)


def methodology_by_year(df: pd.DataFrame, trend_end: int = 2023) -> pd.DataFrame:
    d = df[(df["is_empirical"] == True) & df["methodology"].notna() &  # noqa: E712
           (df["year"] <= trend_end)]
    g = d.groupby(["year", "methodology"]).size().rename("n").reset_index()
    tot = g.groupby("year")["n"].transform("sum")
    g["pct"] = (g["n"] / tot * 100).round(2)
    return g


# ---------------------------------------------------------------------------
# Collaboration
# ---------------------------------------------------------------------------

def collaboration_by_year(df: pd.DataFrame, trend_end: int = 2023) -> pd.DataFrame:
    d = df[(df["n_authors"] > 0) & (df["year"] <= trend_end)]
    g = (d.groupby("year")["n_authors"]
           .agg(mean_authors="mean", median_authors="median", n="count").reset_index())
    single = d.assign(single=d["n_authors"] == 1).groupby("year")["single"].mean()
    g["pct_single_authored"] = (g["year"].map(single) * 100).round(2)
    g["pct_multi_authored"] = (100 - g["pct_single_authored"]).round(2)
    g["mean_authors"] = g["mean_authors"].round(2)
    return g


def collaboration_by_decade(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["n_authors"] > 0].copy()
    d["decade"] = d["year"].apply(decade)
    g = (d.groupby("decade")["n_authors"]
           .agg(mean_authors="mean", median_authors="median", n="count").reset_index())
    single = d.assign(s=d["n_authors"] == 1).groupby("decade")["s"].mean()
    g["pct_single_authored"] = (g["decade"].map(single) * 100).round(1)
    g["pct_multi_authored"] = (100 - g["pct_single_authored"]).round(1)
    g["mean_authors"] = g["mean_authors"].round(2)
    order = ["1989", "1990s", "2000s", "2010s", "2020s"]
    g["_o"] = g["decade"].apply(lambda x: order.index(x) if x in order else 99)
    return g.sort_values("_o").drop(columns="_o").reset_index(drop=True)


def author_count_distribution(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["n_authors"] > 0]
    g = d["n_authors"].value_counts().rename_axis("n_authors").reset_index(name="n")
    g["pct"] = (g["n"] / g["n"].sum() * 100).round(1)
    return g.sort_values("n_authors").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Citations
# ---------------------------------------------------------------------------

def citation_summary(df: pd.DataFrame, trend_end: int = 2023) -> dict:
    """Overall citation distribution within the citation window.

    Recent years are excluded so that every paper has had comparable time to
    accumulate citations, following Perron et al.
    """
    d = df[(df["year"] <= trend_end) & df["cited_by_count"].notna()]
    c = d["cited_by_count"].astype(float)
    if c.empty:
        return {}
    return {
        "n_papers": int(len(c)),
        "total_citations": int(c.sum()),
        "mean_citations": round(float(c.mean()), 2),
        "median_citations": float(c.median()),
        "pct_uncited": round(float((c == 0).mean() * 100), 2),
        "pct_cited_at_least_once": round(float((c > 0).mean() * 100), 2),
        "p90": float(c.quantile(0.90)),
        "p99": float(c.quantile(0.99)),
        "max": int(c.max()),
    }


def citations_by_journal(df: pd.DataFrame, trend_end: int = 2023,
                         min_papers: int = 25) -> pd.DataFrame:
    d = df[(df["year"] <= trend_end) & df["cited_by_count"].notna()].copy()
    d["cited_by_count"] = d["cited_by_count"].astype(float)
    g = (d.groupby("journal_canonical")
           .agg(n_papers=("sred_id", "count"),
                mean_citations=("cited_by_count", "mean"),
                median_citations=("cited_by_count", "median"),
                total_citations=("cited_by_count", "sum"),
                first_year=("year", "min"), last_year=("year", "max"))
           .reset_index())
    unc = d.assign(u=d["cited_by_count"] == 0).groupby("journal_canonical")["u"].mean()
    g["pct_uncited"] = (g["journal_canonical"].map(unc) * 100).round(2)
    g["mean_citations"] = g["mean_citations"].round(2)
    g["total_citations"] = g["total_citations"].astype(int)
    g = g[g["n_papers"] >= min_papers]
    return g.sort_values("n_papers", ascending=False).reset_index(drop=True)


def citations_by_methodology(df: pd.DataFrame, trend_end: int = 2023) -> pd.DataFrame:
    d = df[(df["year"] <= trend_end) & df["cited_by_count"].notna() &
           df["methodology"].notna()].copy()
    d["cited_by_count"] = d["cited_by_count"].astype(float)
    g = (d.groupby("methodology")
           .agg(n=("sred_id", "count"),
                mean_citations=("cited_by_count", "mean"),
                median_citations=("cited_by_count", "median")).reset_index())
    unc = d.assign(u=d["cited_by_count"] == 0).groupby("methodology")["u"].mean()
    g["pct_uncited"] = (g["methodology"].map(unc) * 100).round(2)
    g["pct_cited"] = (100 - g["pct_uncited"]).round(2)
    g["mean_citations"] = g["mean_citations"].round(2)
    return g.sort_values("mean_citations", ascending=False).reset_index(drop=True)


def uncited_by_year(df: pd.DataFrame, trend_end: int = 2023) -> pd.DataFrame:
    d = df[(df["year"] <= trend_end) & df["cited_by_count"].notna()].copy()
    d["uncited"] = d["cited_by_count"].astype(float) == 0
    g = d.groupby(["year", "is_empirical"])["uncited"].agg(
        pct_uncited=lambda s: round(s.mean() * 100, 2), n="count").reset_index()
    return g


# ---------------------------------------------------------------------------
# SRED-specific: venue dispersion, prevention level, SDoH
# ---------------------------------------------------------------------------

def dispersion_by_year(df: pd.DataFrame, trend_end: int = 2023) -> pd.DataFrame:
    """Share of suicide scholarship appearing in dedicated suicidology venues.

    This has no counterpart in Perron et al., because social work is defined by
    its journals. Suicide research is not, and the degree to which the field's
    output concentrates in - or escapes - its specialty journals is the single
    most consequential structural fact about how its knowledge is organised.
    """
    d = df[df["year"] <= trend_end].copy()
    d["in_specialty"] = d["venue_tier"] == "core_a"
    g = d.groupby("year")["in_specialty"].agg(n_total="count", n_specialty="sum").reset_index()
    g["pct_specialty"] = (g["n_specialty"] / g["n_total"] * 100).round(2)
    g["pct_dispersed"] = (100 - g["pct_specialty"]).round(2)
    return g


def _explode_json_list(df: pd.DataFrame, col: str) -> pd.Series:
    import json as _json

    def parse(v):
        if isinstance(v, list):
            return v
        if isinstance(v, str) and v.startswith("["):
            try:
                return _json.loads(v)
            except Exception:  # noqa: BLE001
                return []
        return [v] if v else []

    return df[col].apply(parse)


def field_distribution(df: pd.DataFrame, col: str, multi: bool = True) -> pd.DataFrame:
    """Frequency table for a scalar or multi-label extraction field."""
    if col not in df.columns:
        return pd.DataFrame(columns=[col, "n", "pct"])
    if multi:
        s = _explode_json_list(df, col).explode().dropna()
    else:
        s = df[col].dropna()
    g = s.value_counts().rename_axis(col).reset_index(name="n")
    denom = len(df) if multi else int(g["n"].sum())
    g["pct"] = (g["n"] / max(denom, 1) * 100).round(1)
    return g


def field_by_decade(df: pd.DataFrame, col: str, multi: bool = True) -> pd.DataFrame:
    d = df.copy()
    d["decade"] = d["year"].apply(decade)
    rows = []
    for dec, sub in d.groupby("decade"):
        g = field_distribution(sub, col, multi)
        g["decade"] = dec
        g["denominator"] = len(sub)
        rows.append(g)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    order = ["1989", "1990s", "2000s", "2010s", "2020s"]
    out["_o"] = out["decade"].apply(lambda x: order.index(x) if x in order else 99)
    return out.sort_values(["_o", "n"], ascending=[True, False]).drop(columns="_o").reset_index(drop=True)


def source_overlap(df: pd.DataFrame) -> pd.DataFrame:
    """How many records each provider contributed, alone and in combination.

    This is the coverage-gap evidence: a record found by only one source is a
    record that a single-database study would have missed entirely.
    """
    g = df["source"].value_counts().rename_axis("source_combination").reset_index(name="n")
    g["pct"] = (g["n"] / g["n"].sum() * 100).round(2)
    g["n_sources"] = g["source_combination"].str.count(r"\+") + 1
    return g
