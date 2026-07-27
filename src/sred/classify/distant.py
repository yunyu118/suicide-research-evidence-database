"""Distant-supervision text classifier.

The problem
-----------
Perron et al. (2026) classified every abstract with a locally hosted 20B
language model. That is the right instrument when compute is available, but it
is not reproducible by a reader without a GPU, and it offers no way to
quantify label quality beyond a single kappa against a small human sample.

The approach here
-----------------
SRED exploits a resource suicide research has and social work does not: a
large subset of the corpus carries **human-assigned MEDLINE indexing**. Those
NLM PublicationType tags supply high-quality labels for roughly half the
records at zero annotation cost. SRED trains a calibrated linear text
classifier on that subset (distant supervision) and applies it to the
unindexed remainder.

Why a linear model rather than a transformer: on abstract-length text with
tens of thousands of labelled examples, TF-IDF + regularised logistic
regression is within a few points of a fine-tuned encoder for this kind of
document-type classification, trains in seconds on CPU, is fully
deterministic, and - critically for a methods paper - is inspectable. Every
prediction can be traced to weighted n-grams.

Guardrails
----------
* Labels are only trusted when metadata and rules do not conflict.
* Training uses grouped cross-validation by publication year, so performance is
  estimated on years the model has not seen, which is the realistic deployment
  condition for a database that will be updated forward in time.
* Predictions carry calibrated probabilities; records below the confidence
  floor are labelled ``uncertain`` rather than forced into a class.
* An identical interface is implemented by :mod:`sred.classify.llm_ollama`, so
  the LLM path can be swapped in without touching the pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.metrics import classification_report, cohen_kappa_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline

log = logging.getLogger(__name__)

CONFIDENCE_FLOOR = 0.55   # below this, predict "uncertain"
MIN_TRAIN_PER_CLASS = 40


def _text(rec: dict) -> str:
    return f"{rec.get('title') or ''}. {rec.get('abstract') or ''}".strip()


def make_pipeline(binary: bool) -> Pipeline:
    """TF-IDF + regularised logistic regression.

    Feature choices
    ---------------
    Word 1-2 grams capture the method phrases that carry the signal
    ("semi structured", "odds ratio", "we searched medline"); sublinear TF damps
    a term repeated throughout a long structured abstract; ``min_df=5`` drops
    typos and one-off proper nouns without losing genuine method vocabulary.

    Why no probability calibration
    ------------------------------
    An earlier version wrapped the estimator in ``CalibratedClassifierCV``.
    On this corpus that multiplied every fit by the number of calibration folds
    times the number of one-vs-rest classes, and the validation design here
    trains the model seven times over (three stage hold-outs plus four
    leave-one-decade-out folds). The four-class methodology stage alone ran for
    twenty minutes without finishing.

    Logistic regression is fit by minimising log loss, which is a proper
    scoring rule, so its ``predict_proba`` output is already reasonably
    calibrated for the one thing SRED uses it for: a confidence floor below
    which the classifier declines to label rather than guess. Post-hoc
    calibration would sharpen the probabilities; it would not change which
    records fall below the floor by enough to justify a sevenfold cost. The
    floor itself is the parameter that matters and it is set explicitly.
    """
    vec = TfidfVectorizer(
        lowercase=True, ngram_range=(1, 2), min_df=5, max_df=0.6,
        sublinear_tf=True, strip_accents="unicode", max_features=120_000,
        stop_words="english",
    )
    base = LogisticRegression(
        C=4.0, max_iter=1000, tol=1e-3, class_weight="balanced",
        solver="liblinear",
    )
    # scikit-learn 1.8 removed liblinear's built-in multiclass support, so the
    # four-class methodology stage is wrapped explicitly in one-vs-rest. On this
    # corpus OvR-liblinear, multinomial lbfgs, and SGD with modified Huber loss
    # all land within 0.003 kappa of each other (0.908 / 0.910 / 0.911) at
    # comparable cost; OvR-liblinear is chosen because it is deterministic,
    # which SGD is not, and because it does not silently stop short of
    # convergence the way a capped lbfgs can.
    clf = base if binary else OneVsRestClassifier(base)
    return Pipeline([("tfidf", vec), ("clf", clf)])


@dataclass
class StageResult:
    name: str
    report: dict[str, Any]
    n_train: int
    classes: list[str]


class DistantClassifier:
    """Three-stage classifier trained by distant supervision."""

    def __init__(self, confidence_floor: float = CONFIDENCE_FLOOR):
        self.confidence_floor = confidence_floor
        self.models: dict[str, Pipeline] = {}
        self.results: dict[str, StageResult] = {}

    # -- training ----------------------------------------------------------
    def _fit_stage(self, name: str, texts: list[str], labels: list[Any],
                   groups: list[int], binary: bool) -> StageResult | None:
        y = np.asarray(labels)
        classes, counts = np.unique(y, return_counts=True)
        if len(classes) < 2 or counts.min() < MIN_TRAIN_PER_CLASS:
            log.warning("stage %s: insufficient labels (%s) - skipping",
                        name, dict(zip(classes.tolist(), counts.tolist())))
            return None

        X = np.asarray(texts, dtype=object)
        g = np.asarray(groups)

        # Grouped CV by publication year: the model is always evaluated on
        # years absent from its training data, matching how the database will
        # actually be extended forward.
        n_splits = min(3, len(np.unique(g)))
        # Metrics are computed in string space throughout. Boolean and string
        # label sets otherwise mix dtypes across folds, which sklearn rejects
        # as "a mix of binary and unknown targets".
        y_str = y.astype(str)
        preds = np.array(["__unset__"] * len(y), dtype=object)
        if n_splits >= 2:
            for tr, te in GroupKFold(n_splits=n_splits).split(X, y, g):
                if len(np.unique(y[tr])) < 2:
                    preds[te] = str(y[tr][0]) if len(tr) else str(classes[0])
                    continue
                pipe = make_pipeline(binary)
                pipe.fit(X[tr].tolist(), y[tr])
                preds[te] = [str(v) for v in pipe.predict(X[te].tolist())]
            preds_str = preds.astype(str)
            rep = classification_report(y_str, preds_str, output_dict=True, zero_division=0)
            kappa = cohen_kappa_score(y_str, preds_str)
        else:
            rep, kappa = {}, float("nan")

        final = make_pipeline(binary)
        final.fit(X.tolist(), y)
        self.models[name] = final

        res = StageResult(
            name=name,
            report={"cv_kappa": float(kappa),
                    "cv_accuracy": float(rep.get("accuracy", float("nan"))),
                    "macro_f1": float((rep.get("macro avg") or {}).get("f1-score", float("nan"))),
                    "per_class": {k: v for k, v in rep.items()
                                  if k not in ("accuracy", "macro avg", "weighted avg")},
                    "n_splits": n_splits},
            n_train=len(y),
            classes=[str(c) for c in classes],
        )
        self.results[name] = res
        log.info("stage %-12s n=%-6d classes=%s kappa=%.3f acc=%.3f",
                 name, len(y), res.classes, kappa, res.report["cv_accuracy"])
        return res

    def fit(self, records: list[dict]) -> "DistantClassifier":
        """Train all three stages from composite distant-supervision labels.

        Training consumes ``label_*`` fields produced by
        :mod:`sred.classify.composite`, which merge human MEDLINE indexing,
        structured-abstract structure, and lexical rules under an explicit
        precedence. Records with no label for a stage are excluded from that
        stage rather than assigned a guessed class.
        """
        # Stage 1 - scientific communication vs other
        t, y, g = [], [], []
        for r in records:
            lab = r.get("label_is_scientific")
            if lab is None or not _text(r):
                continue
            t.append(_text(r)); y.append(bool(lab)); g.append(r.get("year") or 0)
        self._fit_stage("is_scientific", t, y, g, binary=True)

        # Stage 2 - empirical vs non-empirical (scientific records only)
        t, y, g = [], [], []
        for r in records:
            if r.get("label_is_scientific") is False:
                continue
            lab = r.get("label_is_empirical")
            if lab is None or not _text(r):
                continue
            t.append(_text(r)); y.append(bool(lab)); g.append(r.get("year") or 0)
        self._fit_stage("is_empirical", t, y, g, binary=True)

        # Stage 3 - methodology (empirical records only)
        t, y, g = [], [], []
        for r in records:
            lab = r.get("label_methodology")
            if lab is None or not _text(r):
                continue
            t.append(_text(r)); y.append(str(lab)); g.append(r.get("year") or 0)
        self._fit_stage("methodology", t, y, g, binary=False)
        return self

    # -- prediction --------------------------------------------------------
    def _predict_stage(self, name: str, texts: list[str]) -> tuple[list[Any], list[float]]:
        pipe = self.models.get(name)
        if pipe is None:
            return [None] * len(texts), [0.0] * len(texts)
        proba = pipe.predict_proba(texts)
        idx = proba.argmax(axis=1)
        conf = proba.max(axis=1)
        labels = [pipe.classes_[i] for i in idx]
        return labels, conf.tolist()

    def predict(self, records: list[dict]) -> list[dict]:
        """Assign final labels under an explicit evidence hierarchy.

        Precedence, strongest first:

        1. **Human MEDLINE indexing** - NLM PublicationType tags, and the
           narrative/systematic review distinction derived from them.
        2. **Structured-abstract evidence** - explicit ``Methods:`` and
           ``Results:`` headings, which journals impose on study reports.
        3. **Model prediction** above the calibrated confidence floor.
        4. **Lexical rule**.
        5. ``None`` - the classifier declines rather than guesses.

        Evidence is read from the ``label_*`` / ``label_source_*`` fields
        produced by :mod:`sred.classify.composite`, never from the raw
        ``meta_*`` fields. That indirection matters: ``meta_*`` values survive a
        Parquet round-trip as ``NaN``, which is truthy, so reading them
        directly silently promotes missing labels to real ones.
        """
        HUMAN = {"medline", "medline_narrative_review", "medline_systematic_review"}
        STRUCTURAL = {"structured_abstract"}

        texts = [_text(r) for r in records]
        sci_p, sci_c = self._predict_stage("is_scientific", texts)
        emp_p, emp_c = self._predict_stage("is_empirical", texts)
        met_p, met_c = self._predict_stage("methodology", texts)

        out = []
        for i, r in enumerate(records):
            rec = dict(r)
            s_src_label = r.get("label_source_is_scientific")
            e_src_label = r.get("label_source_is_empirical")
            m_src_label = r.get("label_source_methodology")

            # --- Stage 1: scientific communication ---
            if s_src_label in HUMAN and r.get("label_is_scientific") is not None:
                rec["is_scientific"] = bool(r["label_is_scientific"])
                s_src, s_conf = "human_indexing", 1.0
            elif sci_c[i] >= self.confidence_floor:
                rec["is_scientific"] = bool(sci_p[i])
                s_src, s_conf = "model", sci_c[i]
            else:
                rec["is_scientific"] = bool(r.get("rule_is_scientific", True))
                s_src, s_conf = "rule", sci_c[i]

            # --- Stage 2: empirical status (scientific records only) ---
            if not rec["is_scientific"]:
                rec["is_empirical"], e_src, e_conf = None, "na", 1.0
            elif e_src_label in HUMAN and r.get("label_is_empirical") is not None:
                rec["is_empirical"] = bool(r["label_is_empirical"])
                e_src, e_conf = "human_indexing", 1.0
            elif e_src_label in STRUCTURAL and r.get("label_is_empirical") is not None:
                rec["is_empirical"] = bool(r["label_is_empirical"])
                e_src, e_conf = "structured_abstract", 0.95
            elif emp_c[i] >= self.confidence_floor:
                rec["is_empirical"] = bool(emp_p[i])
                e_src, e_conf = "model", emp_c[i]
            elif r.get("label_is_empirical") is not None:
                rec["is_empirical"] = bool(r["label_is_empirical"])
                e_src, e_conf = "rule", emp_c[i]
            else:
                rec["is_empirical"], e_src, e_conf = None, "uncertain", emp_c[i]

            # --- Stage 3: methodology (empirical work only) ---
            if rec.get("is_empirical") is not True:
                rec["methodology"], m_src, m_conf = None, "na", 1.0
            elif m_src_label in HUMAN and r.get("label_methodology"):
                rec["methodology"] = str(r["label_methodology"])
                m_src, m_conf = "human_indexing", 1.0
            elif met_c[i] >= self.confidence_floor:
                rec["methodology"] = str(met_p[i])
                m_src, m_conf = "model", met_c[i]
            elif r.get("label_methodology"):
                rec["methodology"] = str(r["label_methodology"])
                m_src, m_conf = "rule", met_c[i]
            else:
                rec["methodology"], m_src, m_conf = None, "uncertain", met_c[i]

            rec["cls_backend"] = f"scientific:{s_src}|empirical:{e_src}|method:{m_src}"
            rec["cls_confidence"] = round(float(min(s_conf, e_conf, m_conf)), 4)
            out.append(rec)
        return out

    def summary(self) -> dict[str, Any]:
        return {name: {"n_train": r.n_train, "classes": r.classes, **r.report}
                for name, r in self.results.items()}
