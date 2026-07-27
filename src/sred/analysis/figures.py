"""Publication figures.

Deliberately plain: greyscale-safe, no chartjunk, no gridline clutter, and
readable at single-column width in print. Journals in this area still print in
black and white, so every series is distinguishable by marker and line style
as well as by colour.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

log = logging.getLogger(__name__)

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.labelsize": 9,
    "legend.frameon": False, "legend.fontsize": 8,
    "xtick.labelsize": 8, "ytick.labelsize": 8,
    "lines.linewidth": 1.6, "lines.markersize": 4,
})

INK = "#1a1a1a"
GREY = "#7a7a7a"
STYLES = [
    {"color": "#1a1a1a", "marker": "o", "ls": "-"},
    {"color": "#7a7a7a", "marker": "s", "ls": "--"},
    {"color": "#4a4a4a", "marker": "^", "ls": "-."},
    {"color": "#a5a5a5", "marker": "D", "ls": ":"},
    {"color": "#2f2f2f", "marker": "v", "ls": (0, (3, 1, 1, 1))},
]


def _save(fig, out: Path, name: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{name}.png"
    fig.savefig(p)
    fig.savefig(out / f"{name}.pdf")
    plt.close(fig)
    log.info("figure -> %s", p.name)
    return p


def fig1_growth(growth: pd.DataFrame, summary: dict, out: Path) -> Path:
    """Annual article records and active journals, with fitted CAGR."""
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    ax.plot(growth["year"], growth["n_articles"], color=INK, marker="o",
            label="Article records with abstracts")

    y0 = summary.get("articles_first")
    r = (summary.get("article_cagr_pct") or 0) / 100.0
    yrs = growth["year"].to_numpy()
    if y0:
        ax.plot(yrs, y0 * (1 + r) ** (yrs - yrs.min()), color=GREY, ls="--",
                lw=1.2, label=f"CAGR fit ({summary.get('article_cagr_pct')}%/yr)")

    ax.set_xlabel("Publication year")
    ax.set_ylabel("Article records")
    ax.set_ylim(bottom=0)

    ax2 = ax.twinx()
    ax2.plot(growth["year"], growth["n_journals"], color=GREY, marker="s",
             ls=":", label=f"Active journals (CAGR {summary.get('journal_cagr_pct')}%/yr)")
    ax2.set_ylabel("Active journals", color=GREY)
    ax2.tick_params(axis="y", colors=GREY)
    ax2.spines["top"].set_visible(False)
    ax2.set_ylim(bottom=0)

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left")
    ax.set_title("Growth in suicide research output and publishing venues")
    return _save(fig, out, "fig1_growth")


def fig2_empiricism(emp: pd.DataFrame, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    ax.plot(emp["year"], emp["pct_empirical"], color=INK, marker="o",
            label="Empirical")
    ax.plot(emp["year"], 100 - emp["pct_empirical"], color=GREY, marker="s",
            ls="--", label="Non-empirical")
    ax.axhline(50, color="#cccccc", lw=0.8, zorder=0)
    ax.set_xlabel("Publication year")
    ax.set_ylabel("Percentage of scientific articles")
    ax.set_ylim(0, 100)
    ax.legend(loc="center right")
    ax.set_title("Evolution of empirical and non-empirical suicide scholarship")
    return _save(fig, out, "fig2_empiricism")


def fig3_methodology(meth_year: pd.DataFrame, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    order = ["quantitative", "qualitative", "mixed", "review"]
    labels = {"quantitative": "Quantitative", "qualitative": "Qualitative",
              "mixed": "Mixed methods", "review": "Evidence synthesis"}
    for i, m in enumerate(order):
        sub = meth_year[meth_year["methodology"] == m].sort_values("year")
        if sub.empty:
            continue
        st = STYLES[i % len(STYLES)]
        ax.plot(sub["year"], sub["pct"], color=st["color"], marker=st["marker"],
                ls=st["ls"], label=labels.get(m, m))
    ax.set_xlabel("Publication year")
    ax.set_ylabel("Percentage of empirical articles")
    ax.set_ylim(0, 100)
    ax.legend(loc="upper right", ncol=2)
    ax.set_title("Distribution of research methodologies in empirical suicide research")
    return _save(fig, out, "fig3_methodology")


def fig4_collaboration(collab: pd.DataFrame, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    ax.plot(collab["year"], collab["mean_authors"], color=INK, marker="o",
            label="Mean authors per article")
    ax.set_xlabel("Publication year")
    ax.set_ylabel("Mean authors per article")
    ax.set_ylim(bottom=0)

    ax2 = ax.twinx()
    ax2.plot(collab["year"], collab["pct_single_authored"], color=GREY,
             marker="s", ls="--", label="Single-authored (%)")
    ax2.set_ylabel("Single-authored articles (%)", color=GREY)
    ax2.tick_params(axis="y", colors=GREY)
    ax2.spines["top"].set_visible(False)
    ax2.set_ylim(0, 100)

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="center right")
    ax.set_title("Trends in collaborative authorship in suicide research")
    return _save(fig, out, "fig4_collaboration")


def fig5_uncited(unc: pd.DataFrame, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    for i, (label, flag) in enumerate([("Empirical", True), ("Non-empirical", False)]):
        sub = unc[unc["is_empirical"] == flag].sort_values("year")
        if sub.empty:
            continue
        st = STYLES[i]
        ax.plot(sub["year"], sub["pct_uncited"], color=st["color"],
                marker=st["marker"], ls=st["ls"], label=label)
    ax.set_xlabel("Publication year")
    ax.set_ylabel("Articles never cited (%)")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left")
    ax.set_title("Percentage of suicide research articles never cited, by publication year")
    return _save(fig, out, "fig5_uncited")


def fig6_dispersion(disp: pd.DataFrame, out: Path) -> Path:
    """SRED-specific: concentration of the field in its specialty journals."""
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    ax.fill_between(disp["year"], 0, disp["pct_specialty"],
                    color="#d9d9d9", label="Dedicated suicidology journals")
    ax.fill_between(disp["year"], disp["pct_specialty"], 100,
                    color="#f5f5f5", edgecolor="#9a9a9a", linewidth=0.6,
                    label="All other journals")
    ax.plot(disp["year"], disp["pct_specialty"], color=INK, marker="o")
    ax.set_xlabel("Publication year")
    ax.set_ylabel("Share of suicide research output (%)")
    ax.set_ylim(0, 100)
    ax.legend(loc="upper right")
    ax.set_title("Dispersion of suicide research beyond its specialty journals")
    return _save(fig, out, "fig6_dispersion")


def fig7_sdoh(sdoh_dec: pd.DataFrame, out: Path, top_n: int = 8) -> Path:
    """SRED-specific: growth of social-determinants framings over time."""
    d = sdoh_dec[sdoh_dec["sdoh_domain"] != "none"].copy()
    if d.empty:
        fig, ax = plt.subplots(figsize=(6.5, 3.6))
        ax.text(0.5, 0.5, "No SDoH labels available", ha="center", va="center")
        return _save(fig, out, "fig7_sdoh")

    top = (d.groupby("sdoh_domain")["n"].sum()
             .sort_values(ascending=False).head(top_n).index.tolist())
    decades = [x for x in ["1990s", "2000s", "2010s", "2020s"]
               if x in set(d["decade"])]
    pivot = (d[d["sdoh_domain"].isin(top)]
             .pivot_table(index="sdoh_domain", columns="decade", values="pct",
                          aggfunc="first")
             .reindex(index=top, columns=decades).fillna(0))

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    x = np.arange(len(top))
    w = 0.8 / max(len(decades), 1)
    greys = ["#111111", "#4d4d4d", "#8a8a8a", "#c4c4c4"]
    for i, dec in enumerate(decades):
        ax.barh(x + i * w, pivot[dec].to_numpy(), height=w,
                color=greys[i % len(greys)], label=dec)
    ax.set_yticks(x + w * (len(decades) - 1) / 2)
    ax.set_yticklabels([t.replace("_", " ").title() for t in top])
    ax.invert_yaxis()
    ax.set_xlabel("Percentage of articles in decade")
    ax.legend(title="Decade", loc="lower right")
    ax.set_title("Social determinants of health addressed in suicide research")
    return _save(fig, out, "fig7_sdoh")


def fig8_prevention(prev_dec: pd.DataFrame, out: Path) -> Path:
    """SRED-specific: where the field sits on the prevention continuum."""
    order = ["universal", "selective", "indicated", "treatment", "postvention",
             "not_applicable"]
    d = prev_dec[prev_dec["prevention_level"].isin(order)].copy()
    if d.empty:
        fig, ax = plt.subplots(figsize=(6.5, 3.6))
        ax.text(0.5, 0.5, "No prevention-level labels", ha="center", va="center")
        return _save(fig, out, "fig8_prevention")

    decades = [x for x in ["1990s", "2000s", "2010s", "2020s"] if x in set(d["decade"])]
    pivot = (d.pivot_table(index="decade", columns="prevention_level",
                           values="pct", aggfunc="first")
             .reindex(index=decades, columns=order).fillna(0))

    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    bottom = np.zeros(len(decades))
    greys = ["#111111", "#3d3d3d", "#6b6b6b", "#9a9a9a", "#c4c4c4", "#eeeeee"]
    for i, lvl in enumerate(order):
        vals = pivot[lvl].to_numpy()
        ax.bar(decades, vals, bottom=bottom, color=greys[i],
               label=lvl.replace("_", " ").title(),
               edgecolor="white", linewidth=0.5)
        bottom += vals
    ax.set_ylabel("Percentage of articles")
    ax.set_xlabel("Decade")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), title="Prevention level")
    ax.set_title("Position of suicide research on the prevention continuum")
    return _save(fig, out, "fig8_prevention")
