#!/usr/bin/env python3
"""Stage 4 (part 2) - Abstract classification and suicide-specific extraction.

Runs the three-stage classification (scientific communication -> empirical ->
methodology) plus SRED's suicide-specific extraction fields, then validates.

Backends
--------
``--backend distant`` (default)
    Metadata + lexical rules + a distantly supervised text model. Runs on CPU
    in minutes and is what the cloud build uses.
``--backend ollama``
    Local LLM, the direct analogue of Perron et al.'s gpt-oss:20b stage.
    Requires a running Ollama server. Use ``--limit`` to pilot it before
    committing to a full run.

Outputs
-------
    data/processed/sred_classified.parquet
    data/interim/classifier_summary.json
    data/interim/validation_report.json
    data/interim/human_coding_template.csv
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sred.classify import validate as V  # noqa: E402
from sred.classify.composite import composite_labels, label_report  # noqa: E402
from sred.classify.distant import DistantClassifier  # noqa: E402
from sred.classify.metadata import metadata_labels  # noqa: E402
from sred.classify.rules import rule_labels  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
INTERIM = ROOT / "data" / "interim"

# Log directory must exist before logging is configured. Git does not track
# empty directories, so a fresh clone has no logs/ and FileHandler would raise
# FileNotFoundError before the first line of work. This bit CI on the very
# first run, which is exactly what CI is for.
(ROOT / "logs").mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout),
                              logging.FileHandler(ROOT / "logs" / "classify.log")])
log = logging.getLogger("classify")


LABEL_CACHE = PROCESSED / "sred_labelled.parquet"


def enrich_labels(records: list[dict], use_cache: bool = True) -> tuple[list[dict], dict]:
    """Attach metadata, rule, and composite label evidence.

    The rule pass runs several dozen regular expressions over every abstract and
    costs minutes on a corpus this size, so the result is cached. Delete
    ``data/processed/sred_labelled.parquet`` after editing rules or the
    composite logic to force a recompute.
    """
    # Only the expensive part is cached - the regex battery over every
    # abstract. Composite label logic is cheap and evolves often, so it is
    # always recomputed on top of the cache; otherwise a change to the
    # labelling rules would silently have no effect.
    cached_hit = False
    if use_cache and LABEL_CACHE.exists():
        cached = pd.read_parquet(LABEL_CACHE)
        if len(cached) == len(records):
            log.info("reusing cached metadata/rule evidence (%d records)", len(cached))
            records = cached.to_dict("records")
            cached_hit = True
        else:
            log.info("label cache size mismatch (%d vs %d); recomputing",
                     len(cached), len(records))

    if not cached_hit:
        for r in records:
            r.update(metadata_labels(r))
            r.update(rule_labels(r.get("title"), r.get("abstract")))

    for r in records:
        r.update(composite_labels(r))

    rep = label_report(records)
    if cached_hit:
        return records, rep
    try:
        frame = pd.DataFrame(records)
        for col in frame.columns:
            if frame[col].apply(lambda v: isinstance(v, (list, dict))).any():
                frame[col] = frame[col].apply(
                    lambda v: json.dumps(v, ensure_ascii=False)
                    if isinstance(v, (list, dict)) else v)
        frame.to_parquet(LABEL_CACHE, index=False)
        log.info("cached label evidence -> %s", LABEL_CACHE.name)
    except Exception as e:  # noqa: BLE001
        log.warning("could not cache label evidence: %s", e)
    return records, rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["distant", "ollama"], default="distant")
    ap.add_argument("--model", default="gpt-oss:20b")
    ap.add_argument("--limit", type=int, default=0, help="classify only N records (pilot)")
    ap.add_argument("--skip-validation", action="store_true")
    ap.add_argument("--no-label-cache", action="store_true",
                    help="recompute label evidence instead of reusing the cache")
    args = ap.parse_args()

    src = PROCESSED / "sred_screened.parquet"
    if not src.exists():
        log.error("missing %s - run 02_integrate.py first", src)
        return 1
    df = pd.read_parquet(src)
    log.info("loaded %d screened records", len(df))

    records = df.to_dict("records")
    if args.limit:
        records = records[: args.limit]
        log.info("pilot mode: %d records", len(records))

    records, label_rep = enrich_labels(records, use_cache=not args.no_label_cache)

    if args.backend == "ollama":
        from sred.classify.llm_ollama import OllamaClassifier
        clf = OllamaClassifier(model=args.model,
                               cache_dir=ROOT / "data" / "raw" / "_llmcache")
        factory = lambda: OllamaClassifier(  # noqa: E731
            model=args.model, cache_dir=ROOT / "data" / "raw" / "_llmcache")
    else:
        clf = DistantClassifier()
        factory = DistantClassifier

    # --- validation (before fitting on everything, to keep it honest) ------
    report: dict = {"backend": args.backend}
    report["label_availability"] = label_rep
    if not args.skip_validation and args.backend == "distant":
        log.info("running held-out validation against human MEDLINE indexing")
        report["holdout"] = V.holdout_validation(records, factory)
        log.info("running leave-one-decade-out temporal validation")
        report["temporal"] = V.temporal_validation(records, factory)

    # --- fit + predict on the full corpus ---------------------------------
    clf.fit(records)
    labelled = clf.predict(records)
    report["training_summary"] = clf.summary()

    out = pd.DataFrame(labelled)
    drop = [c for c in out.columns if c.startswith("_")]
    out = out.drop(columns=drop, errors="ignore")
    for col in out.columns:
        if out[col].apply(lambda v: isinstance(v, (list, dict))).any():
            out[col] = out[col].apply(
                lambda v: json.dumps(v, ensure_ascii=False)
                if isinstance(v, (list, dict)) else v)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_parquet(PROCESSED / "sred_classified.parquet", index=False)
    log.info("wrote sred_classified.parquet (%d rows)", len(out))

    # --- coverage summary --------------------------------------------------
    def pct(mask) -> float:
        return round(float(mask.mean() * 100), 2)

    report["label_coverage"] = {
        "n_records": int(len(out)),
        "pct_scientific": pct(out["is_scientific"] == True),        # noqa: E712
        "pct_empirical_of_scientific": round(float(
            (out.loc[out["is_scientific"] == True, "is_empirical"] == True).mean() * 100), 2),  # noqa: E712
        "pct_methodology_assigned": pct(out["methodology"].notna()),
        "pct_empirical_uncertain": pct(
            (out["is_scientific"] == True) & out["is_empirical"].isna()),  # noqa: E712
        "backend_mix": out["cls_backend"].value_counts().head(12).to_dict(),
    }

    V.write_report(report, INTERIM / "validation_report.json")
    (INTERIM / "classifier_summary.json").write_text(
        json.dumps(report.get("training_summary", {}), indent=2, default=str))

    V.export_human_coding_sample(out, INTERIM / "human_coding_template.csv", n=300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
