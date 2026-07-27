"""Classifier validation.

SRED validates classification in three independent ways, because the usual
practice - one kappa against a hundred hand-coded abstracts - is too thin a
basis for claims about a corpus of this size.

1. **Held-out human indexing.** A random 20% of MEDLINE-indexed records is
   withheld from training entirely. NLM PublicationType tags are assigned by
   trained human indexers, so agreement on this hold-out is agreement with
   human coders, measured on tens of thousands of records rather than a
   hundred. This is the primary validation.

2. **Temporal generalisation.** Because indexing conventions drift, the model
   is also evaluated under leave-one-decade-out training. A model that only
   works on the decade it was trained on is useless for a database designed to
   be extended forward.

3. **Human verification sample.** A stratified sample is exported in a coding
   template for independent human double-coding by the research team. This is
   what the manuscript reports as the confirmatory kappa, and it is the step
   that requires people rather than machines.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, cohen_kappa_score, confusion_matrix

log = logging.getLogger(__name__)


HUMAN_SOURCES = {"medline", "medline_narrative_review", "medline_systematic_review"}

# Fields that must be blinded before a held-out record is passed to predict().
# Missing one of these leaks the answer and turns validation into a tautology.
_BLIND_KEYS = (
    "meta_is_scientific", "meta_is_empirical", "meta_methodology",
    "label_is_scientific", "label_is_empirical", "label_methodology",
    "label_source_is_scientific", "label_source_is_empirical",
    "label_source_methodology", "rule_is_scientific", "rule_is_empirical",
    "rule_methodology", "review_type",
)


def _truth(rec: dict, stage: str) -> str | None:
    """Human-assigned ground truth for one stage, or None if there is none.

    Reads ``label_*`` rather than ``meta_*`` and normalises NaN explicitly.
    Both details matter: records round-trip through Parquet, which converts
    ``None`` to ``NaN``, and ``NaN is None`` is False - so a naive truth
    extractor silently scores predictions against the string "nan" and reports
    an accuracy worse than chance.
    """
    src = rec.get(f"label_source_{stage}")
    if not isinstance(src, str) or src not in HUMAN_SOURCES:
        return None
    v = rec.get(f"label_{stage}")
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    sv = str(v).strip()
    if sv.lower() in ("nan", "none", ""):
        return None
    return sv


def _blind(rec: dict) -> dict:
    b = dict(rec)
    for k in _BLIND_KEYS:
        b[k] = None
    return b


def holdout_validation(records: list[dict], classifier_factory, test_frac: float = 0.2,
                       seed: int = 20260727) -> dict[str, Any]:
    """Withhold 20% of the human-labelled records per stage; score each stage.

    Two design points, both learned the hard way.

    *Stage-wise sampling.* An earlier version drew a single hold-out from the
    union of all three label sources, so the methodology stage was scored on
    19,328 records of which only a fraction carried a methodology label - the
    remainder were compared against missing values and the reported accuracy
    fell below chance. Each stage now gets its own hold-out drawn from records
    that actually have that stage's label.

    *One fit, not three.* The held-out sets are unioned and a single model is
    trained on the complement. Training three times would triple an already
    expensive fit for no gain, since a record withheld from any stage is
    withheld from training entirely.

    The pool is restricted to labels from human MEDLINE indexing. Scoring
    against rule-derived labels would measure agreement between the model and
    the rules that supervised it, which is circular.
    """
    rng = np.random.default_rng(seed)
    stages = ("is_scientific", "is_empirical", "methodology")

    test_sets: dict[str, list[dict]] = {}
    held_ids: set[int] = set()
    for stage in stages:
        pool = [r for r in records if _truth(r, stage) is not None]
        if len(pool) < 200:
            test_sets[stage] = []
            log.warning("hold-out %s: only %d human-labelled records", stage, len(pool))
            continue
        idx = rng.permutation(len(pool))
        cut = int(len(pool) * (1 - test_frac))
        test = [pool[i] for i in idx[cut:]]
        test_sets[stage] = test
        held_ids.update(id(r) for r in test)

    train = [r for r in records if id(r) not in held_ids]
    log.info("hold-out: training once on %d records, %d withheld across stages",
             len(train), len(held_ids))
    clf = classifier_factory()
    clf.fit(train)

    out: dict[str, Any] = {
        "test_fraction": test_frac, "seed": seed, "n_train": len(train),
        "n_held_out_total": len(held_ids),
        "label_sources_treated_as_human": sorted(HUMAN_SOURCES),
    }

    for stage in stages:
        test = test_sets.get(stage) or []
        if len(test) < 30:
            out[stage] = {"n": len(test), "note": "insufficient human-labelled records"}
            continue
        preds = clf.predict([_blind(r) for r in test])
        y_true, y_pred = [], []
        for t, pr in zip(test, preds):
            tv, pv = _truth(t, stage), pr.get(stage)
            if tv is None or pv is None:
                continue
            y_true.append(tv)
            y_pred.append(str(pv))
        if len(y_true) < 30:
            out[stage] = {"n": len(y_true), "n_held_out": len(test),
                          "note": "model declined to label most held-out records"}
            continue
        labels = sorted(set(y_true) | set(y_pred))
        out[stage] = {
            "n": len(y_true),
            "n_held_out": len(test),
            "coverage_pct": round(len(y_true) / max(len(test), 1) * 100, 2),
            "kappa": round(float(cohen_kappa_score(y_true, y_pred)), 4),
            "accuracy": round(float(np.mean(np.array(y_true) == np.array(y_pred))), 4),
            "report": classification_report(y_true, y_pred, output_dict=True,
                                            zero_division=0),
            "labels": labels,
            "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        }
        log.info("hold-out %-14s n=%-6d kappa=%.3f acc=%.3f (coverage %.0f%%)",
                 stage, out[stage]["n"], out[stage]["kappa"],
                 out[stage]["accuracy"], out[stage]["coverage_pct"])
    return out


def temporal_validation(records: list[dict], classifier_factory) -> dict[str, Any]:
    """Leave-one-decade-out: train on the other decades, test on the held one.

    Indexing conventions and abstract-writing style both drift. A classifier
    that only works on the decade it was trained on is unusable for a database
    designed to be extended forward, so this is the check that matters most for
    SRED's maintainability claim.
    """
    def dec(y):
        if y is None or (isinstance(y, float) and math.isnan(y)):
            return None
        y = int(y)
        return "1990s" if y < 2000 else "2000s" if y < 2010 else \
               "2010s" if y < 2020 else "2020s"

    pool = [r for r in records if _truth(r, "is_empirical") is not None]
    buckets: dict[str, list[dict]] = {}
    for r in pool:
        d = dec(r.get("year"))
        if d:
            buckets.setdefault(d, []).append(r)

    results: dict[str, Any] = {}
    for held, test in sorted(buckets.items()):
        train = [r for r in records if dec(r.get("year")) != held]
        if len(train) < 500 or len(test) < 100:
            continue
        clf = classifier_factory()
        clf.fit(train)
        preds = clf.predict([_blind(r) for r in test])
        yt, yp = [], []
        for t, pr in zip(test, preds):
            tv, pv = _truth(t, "is_empirical"), pr.get("is_empirical")
            if tv is None or pv is None:
                continue
            yt.append(tv)
            yp.append(str(pv))
        if len(yt) < 50:
            continue
        results[held] = {
            "n_train": len(train), "n_test": len(yt),
            "kappa": round(float(cohen_kappa_score(yt, yp)), 4),
            "accuracy": round(float(np.mean(np.array(yt) == np.array(yp))), 4),
        }
        log.info("leave-out %s: kappa=%.3f acc=%.3f (n=%d)", held,
                 results[held]["kappa"], results[held]["accuracy"],
                 results[held]["n_test"])
    return results


def export_human_coding_sample(df: pd.DataFrame, out_path: Path, n: int = 300,
                               seed: int = 20260727) -> Path:
    """Export a stratified sample as a coding template for human double-coding.

    Stratification is by decade x predicted methodology, so the sample covers
    the cells where the model is most likely to be wrong rather than
    over-representing the modal cell (recent quantitative work).
    """
    rng = np.random.default_rng(seed)
    d = df.copy()
    d["_dec"] = pd.cut(d["year"].astype("float"),
                       bins=[1988, 1999, 2009, 2019, 2026],
                       labels=["1990s", "2000s", "2010s", "2020s"])
    d["_stratum"] = (d["_dec"].astype(str) + "|" +
                     d["methodology"].fillna("none").astype(str))

    strata = [s for s in d["_stratum"].unique() if isinstance(s, str)]
    per = max(1, n // max(len(strata), 1))
    picks = []
    for s in strata:
        sub = d[d["_stratum"] == s]
        k = min(per, len(sub))
        if k:
            picks.append(sub.iloc[rng.choice(len(sub), k, replace=False)])
    sample = pd.concat(picks, ignore_index=True) if picks else d.head(0)
    if len(sample) > n:
        sample = sample.iloc[rng.choice(len(sample), n, replace=False)]

    cols = ["sred_id", "doi", "year", "journal_canonical", "title", "abstract",
            "is_scientific", "is_empirical", "methodology", "cls_backend",
            "cls_confidence", "prevention_level", "sdoh_focus"]
    cols = [c for c in cols if c in sample.columns]
    tmpl = sample[cols].copy()
    tmpl = tmpl.rename(columns={
        "is_scientific": "model_is_scientific",
        "is_empirical": "model_is_empirical",
        "methodology": "model_methodology",
    })
    # Blank columns for the human coders.
    for c in ["human_is_scientific", "human_is_empirical", "human_methodology",
              "human_prevention_level", "human_sdoh_focus", "coder_initials",
              "coder_notes"]:
        tmpl[c] = ""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmpl.to_csv(out_path, index=False)
    log.info("human coding template -> %s (%d records, %d strata)",
             out_path.name, len(tmpl), len(strata))
    return out_path


def score_human_coding(csv_path: Path) -> dict[str, Any]:
    """Compute kappa once coders have filled in the template."""
    d = pd.read_csv(csv_path)
    out: dict[str, Any] = {"n_rows": int(len(d))}
    pairs = [("model_is_scientific", "human_is_scientific"),
             ("model_is_empirical", "human_is_empirical"),
             ("model_methodology", "human_methodology")]
    for mcol, hcol in pairs:
        if mcol not in d.columns or hcol not in d.columns:
            continue
        sub = d[[mcol, hcol]].dropna()
        sub = sub[sub[hcol].astype(str).str.strip() != ""]
        if len(sub) < 20:
            out[mcol] = {"n": int(len(sub)), "note": "too few completed rows"}
            continue
        yt = sub[hcol].astype(str).str.strip().str.lower()
        yp = sub[mcol].astype(str).str.strip().str.lower()
        out[mcol] = {"n": int(len(sub)),
                     "kappa": round(float(cohen_kappa_score(yt, yp)), 4),
                     "agreement": round(float((yt == yp).mean()), 4)}
    return out


def write_report(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))
    log.info("validation report -> %s", path.name)
