#!/usr/bin/env python3
"""Score human double-coding: reliability, adjudication, and the confirmatory kappa.

Runs in three modes, in the order the project needs them.

``--mode reliability`` (after both coders finish a batch)
    Pairwise Cohen's kappa between the two coders, per field, with percent
    agreement and a confusion matrix. Also emits an adjudication workbook
    containing every record where the coders disagreed **or** either flagged
    uncertainty. Run this after Batch 1 before the calibration meeting, and
    again after Batch 2.

``--mode adjudicate`` (after the adjudicator fills in the workbook)
    Merges the adjudicated decisions over the two coder files to produce the
    consensus human standard.

``--mode confirm`` (once consensus exists)
    Kappa between the consensus human standard and the model's predictions,
    joined from the scoring key. **This is the number the manuscript reports as
    the confirmatory validation.** It is deliberately a separate step from the
    hold-out kappa in ``03_classify.py``: that one measures agreement with NLM
    indexers on tens of thousands of records, this one measures agreement with
    the project's own trained coders on a stratified sample. They answer
    different questions and both belong in the paper.

Notes on interpretation, which the output repeats so nobody has to remember:
kappa is not accuracy. On a field where one category holds 90% of the mass,
two coders can agree 92% of the time and still score kappa near zero, because
chance agreement alone would have got them to 90%. Read kappa alongside the
percent agreement and the marginal distribution, never on its own.

Usage
-----
    python scripts/08_score_coding.py --mode reliability
    python scripts/08_score_coding.py --mode reliability --batch 1-calibration
    python scripts/08_score_coding.py --mode adjudicate
    python scripts/08_score_coding.py --mode confirm
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
CODING = ROOT / "data" / "coding"
INTERIM = ROOT / "data" / "interim"

(ROOT / "logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
log = logging.getLogger("score")

FIELDS = ["Q1_communication_type", "Q2_empirical_status", "Q3_methodology",
          "Q4_prevention_level", "Q5_sdoh_addressed"]

# Human answer -> the model field it is compared against, and the value map.
# Mapping targets are lowercase because both sides pass through _norm(), which
# lowercases. Writing "True" here instead of "true" produced 0.0% agreement on
# both boolean fields while the multiclass field scored normally: a silent,
# field-specific failure that looked like a genuine null result.
CONFIRM_MAP = {
    "Q1_communication_type": ("model_is_scientific",
                              {"scientific": "true", "other_scholarly": "false"}),
    "Q2_empirical_status": ("model_is_empirical",
                            {"empirical": "true", "non_empirical": "false"}),
    "Q3_methodology": ("model_methodology",
                       {"quantitative": "quantitative", "qualitative": "qualitative",
                        "mixed": "mixed", "review": "review"}),
}


def _norm(s: pd.Series) -> pd.Series:
    """Trim and lowercase, and treat blanks as missing rather than as a class."""
    return (s.astype(str).str.strip().str.lower()
            .replace({"nan": np.nan, "none": np.nan, "": np.nan}))


def load_coder(path: Path) -> pd.DataFrame:
    d = pd.read_excel(path, sheet_name="Coding")
    for f in FIELDS + ["FLAG"]:
        if f in d.columns:
            d[f] = _norm(d[f])
    log.info("%s: %d rows, %d coded on Q2", path.name, len(d),
             int(d["Q2_empirical_status"].notna().sum()))
    return d


def agreement(a: pd.Series, b: pd.Series, field: str) -> dict:
    both = a.notna() & b.notna()
    ya, yb = a[both], b[both]
    if len(ya) < 10:
        return {"field": field, "n": int(len(ya)), "note": "too few completed pairs"}
    labels = sorted(set(ya) | set(yb))
    pct = float((ya == yb).mean())
    # Kappa is undefined when both coders used exactly one category; report the
    # agreement instead of a NaN that looks like a failure.
    k = float("nan") if len(labels) < 2 else float(cohen_kappa_score(ya, yb))
    out = {
        "field": field,
        "n_pairs": int(len(ya)),
        "n_incomplete": int((~both).sum()),
        "percent_agreement": round(pct * 100, 2),
        "cohens_kappa": None if np.isnan(k) else round(k, 4),
        "labels": labels,
        "confusion_matrix": confusion_matrix(ya, yb, labels=labels).tolist(),
        "marginal_coder_a": ya.value_counts(normalize=True).round(3).to_dict(),
        "marginal_coder_b": yb.value_counts(normalize=True).round(3).to_dict(),
    }
    out["interpretation"] = _interpret(k, pct, ya)
    return out


def _interpret(k: float, pct: float, y: pd.Series) -> str:
    top = float(y.value_counts(normalize=True).max()) if len(y) else 1.0
    if np.isnan(k):
        return ("Kappa undefined: only one category was used. Percent agreement "
                f"is {pct*100:.1f}%, which reflects a degenerate distribution "
                "rather than demonstrated reliability.")
    band = ("poor" if k < 0.20 else "fair" if k < 0.40 else "moderate"
            if k < 0.60 else "substantial" if k < 0.80 else "almost perfect")
    note = f"kappa {k:.2f} ({band}), {pct*100:.1f}% agreement"
    if top > 0.85 and k < 0.60:
        note += (f". Caution: the modal category holds {top*100:.0f}% of the mass, "
                 "so chance agreement is high and kappa is harsh here. Report both "
                 "figures and say which is which.")
    return note


def write_adjudication(a: pd.DataFrame, b: pd.DataFrame, out: Path) -> int:
    disagree = pd.Series(False, index=a.index)
    reasons: list[list[str]] = [[] for _ in range(len(a))]
    for f in FIELDS:
        if f not in a.columns or f not in b.columns:
            continue
        d = (a[f].notna() | b[f].notna()) & (a[f].fillna("~") != b[f].fillna("~"))
        disagree |= d
        for i in np.where(d)[0]:
            reasons[i].append(f.split("_")[0])
    flagged = (a.get("FLAG", pd.Series(dtype=object)).eq("yes")
               | b.get("FLAG", pd.Series(dtype=object)).eq("yes"))
    flagged = flagged.reindex(a.index, fill_value=False)
    for i in np.where(flagged & ~disagree)[0]:
        reasons[i].append("flagged")
    take = disagree | flagged

    cols = ["row", "batch", "sred_id", "year", "journal", "title", "abstract"]
    adj = a.loc[take, [c for c in cols if c in a.columns]].copy()
    adj["why"] = [", ".join(r) for i, r in enumerate(reasons) if take.iloc[i]]
    for f in FIELDS:
        if f in a.columns:
            adj[f"A_{f}"] = a.loc[take, f].values
            adj[f"B_{f}"] = b.loc[take, f].values
            adj[f"FINAL_{f}"] = ""
    adj["A_notes"] = a.loc[take, "NOTES"].values if "NOTES" in a.columns else ""
    adj["B_notes"] = b.loc[take, "NOTES"].values if "NOTES" in b.columns else ""
    adj["adjudicator_rationale"] = ""

    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        adj.to_excel(xl, sheet_name="Adjudication", index=False)
    log.info("adjudication workbook -> %s (%d of %d records need a decision)",
             out.name, len(adj), len(a))
    return len(adj)


def mode_reliability(args) -> int:
    a = load_coder(CODING / f"SRED_coding_Coder{args.coders[0]}.xlsx")
    b = load_coder(CODING / f"SRED_coding_Coder{args.coders[1]}.xlsx")
    if len(a) != len(b) or not (a["sred_id"].values == b["sred_id"].values).all():
        log.error("coder files are not row-aligned; regenerate them with "
                  "07_make_coding_workbooks.py and do not re-sort")
        return 1

    if args.batch:
        keep = a["batch"].astype(str) == args.batch
        a, b = a[keep].reset_index(drop=True), b[keep].reset_index(drop=True)
        log.info("restricted to batch %s (%d records)", args.batch, len(a))

    report = {"coders": args.coders, "batch": args.batch or "all",
              "n_records": int(len(a)), "fields": {}}
    for f in FIELDS:
        if f in a.columns and f in b.columns:
            r = agreement(a[f], b[f], f)
            report["fields"][f] = r
            log.info("%-24s %s", f, r.get("interpretation", r.get("note", "")))

    n_adj = write_adjudication(a, b, CODING / "SRED_adjudication.xlsx")
    report["n_needing_adjudication"] = n_adj
    (CODING / "reliability_report.json").write_text(json.dumps(report, indent=2, default=str))
    log.info("reliability report -> reliability_report.json")
    return 0


def mode_adjudicate(args) -> int:
    adj_path = CODING / "SRED_adjudication.xlsx"
    if not adj_path.exists():
        log.error("missing %s - run --mode reliability first", adj_path.name)
        return 1
    adj = pd.read_excel(adj_path, sheet_name="Adjudication")
    a = load_coder(CODING / f"SRED_coding_Coder{args.coders[0]}.xlsx")
    b = load_coder(CODING / f"SRED_coding_Coder{args.coders[1]}.xlsx")

    consensus = a[["row", "batch", "sred_id", "year", "journal", "title"]].copy()
    unresolved = 0
    for f in FIELDS:
        if f not in a.columns:
            continue
        # Where the coders agreed, that value is the consensus. Where they did
        # not, the adjudicator's FINAL_ value governs.
        vals = a[f].where(a[f] == b[f])
        final = adj.set_index("sred_id").get(f"FINAL_{f}")
        if final is not None:
            final = _norm(final)
            mapped = a["sred_id"].map(final)
            vals = mapped.where(mapped.notna(), vals)
        consensus[f] = vals
        miss = int(vals.isna().sum())
        unresolved += miss
        log.info("%-24s consensus for %d/%d records (%d unresolved)",
                 f, len(vals) - miss, len(vals), miss)

    out = CODING / "human_consensus.csv"
    consensus.to_csv(out, index=False)
    log.info("consensus -> %s", out.name)
    if unresolved:
        log.warning("%d field-records remain unresolved; fill the FINAL_ columns "
                    "in %s and re-run", unresolved, adj_path.name)
    return 0


def mode_confirm(args) -> int:
    cons_path = CODING / "human_consensus.csv"
    key_path = CODING / "_scoring_key_DO_NOT_SHARE_WITH_CODERS.csv"
    for p in (cons_path, key_path):
        if not p.exists():
            log.error("missing %s", p.name)
            return 1

    cons = pd.read_csv(cons_path)
    key = pd.read_csv(key_path)
    m = cons.merge(key, on="sred_id", how="inner", validate="one_to_one")
    log.info("joined %d records to the scoring key", len(m))

    report = {"n_records": int(len(m)), "fields": {}}
    for human_field, (model_field, mapping) in CONFIRM_MAP.items():
        if human_field not in m.columns or model_field not in m.columns:
            continue
        h = _norm(_norm(m[human_field]).map(mapping))
        k = _norm(m[model_field].astype(str))
        both = h.notna() & k.notna()
        if both.sum() < 20:
            report["fields"][human_field] = {"n": int(both.sum()),
                                             "note": "too few comparable records"}
            continue
        yh, yk = h[both].astype(str), k[both].astype(str)
        labels = sorted(set(yh) | set(yk))
        kap = float(cohen_kappa_score(yh, yk)) if len(labels) > 1 else float("nan")
        pct = float((yh == yk).mean())
        report["fields"][human_field] = {
            "model_field": model_field,
            "n": int(both.sum()),
            "percent_agreement": round(pct * 100, 2),
            "cohens_kappa": None if np.isnan(kap) else round(kap, 4),
            "labels": labels,
            "confusion_matrix": confusion_matrix(yh, yk, labels=labels).tolist(),
            "interpretation": _interpret(kap, pct, yh),
        }
        log.info("%-24s vs %-22s %s", human_field, model_field,
                 report["fields"][human_field]["interpretation"])

    out = INTERIM / "confirmatory_kappa.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    log.info("confirmatory report -> %s", out)
    log.info("These are the figures to quote in the manuscript's validation "
             "paragraph, alongside the hold-out kappas against NLM indexing.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["reliability", "adjudicate", "confirm"],
                    default="reliability")
    ap.add_argument("--coders", nargs=2, default=["A", "B"])
    ap.add_argument("--batch", default=None,
                    help="restrict to one batch, e.g. 1-calibration")
    args = ap.parse_args()
    return {"reliability": mode_reliability, "adjudicate": mode_adjudicate,
            "confirm": mode_confirm}[args.mode](args)


if __name__ == "__main__":
    raise SystemExit(main())
