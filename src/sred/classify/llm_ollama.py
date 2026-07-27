"""Local LLM classifier (Ollama / llama.cpp backend).

This module is the direct analogue of the ``gpt-oss:20b`` classification stage
in Perron, Victor & Qi (2026), and it implements the same interface as
:class:`sred.classify.distant.DistantClassifier` so the two are
interchangeable:

    from sred.classify.llm_ollama import OllamaClassifier
    clf = OllamaClassifier(model="gpt-oss:20b")
    labelled = clf.predict(records)

It is *not* run in the cloud build, because a 20B model over 100k abstracts is
not something to do on a shared CPU. It is shipped so that the classification
can be upgraded on any machine with a GPU and Ollama installed, and so that
the LLM and distant-supervision label sets can be compared head to head on the
same corpus - a comparison the manuscript reports on a stratified sample.

Design notes
------------
* Temperature 0.1 and a JSON schema in the prompt, following Perron et al.
* One call per record per stage, with the hierarchy short-circuiting: a record
  judged non-scientific is never sent to the methodology prompt. On this
  corpus that removes roughly a fifth of all calls.
* Responses are cached on disk keyed by (model, prompt hash), so re-running
  after a crash costs nothing and a prompt edit invalidates only what changed.
* Every response retains the model's free-text ``rationale``, which is what
  makes disagreement with the metadata labels auditable rather than mysterious.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import urllib.request
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger(__name__)

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "gpt-oss:20b"

SYSTEM = (
    "You are a research methodologist coding bibliographic abstracts for a "
    "scientometric database of suicide research. You answer only with a single "
    "JSON object. You never guess: when an abstract does not contain enough "
    "information to decide, you return the value \"uncertain\"."
)

STAGE_PROMPTS: dict[str, str] = {
    "is_scientific": """Classify this record as SCIENTIFIC COMMUNICATION or OTHER SCHOLARLY COMMUNICATION.

SCIENTIFIC COMMUNICATION presents original research findings, a theoretical
framework, a systematic review, or a methodological innovation that
contributes to the knowledge base.

OTHER SCHOLARLY COMMUNICATION includes editorials, book reviews, letters to
the editor, news items, obituaries, corrections, and conference matter. These
serve professional functions but present no original scientific contribution.

TITLE: {title}
ABSTRACT: {abstract}

Respond with JSON only:
{{"label": "scientific" | "other", "confidence": 0.0-1.0, "rationale": "one sentence"}}""",

    "is_empirical": """Classify this record as EMPIRICAL or NON-EMPIRICAL.

EMPIRICAL: the abstract describes collecting and analysing data (original or
secondary, quantitative or qualitative) to answer a research question. Formal
evidence syntheses count as empirical.

NON-EMPIRICAL: theoretical or conceptual work, narrative discussion of a
literature without systematic method, practice commentary, or methodological
argument that analyses no data.

TITLE: {title}
ABSTRACT: {abstract}

Respond with JSON only:
{{"label": "empirical" | "non_empirical" | "uncertain", "confidence": 0.0-1.0, "rationale": "one sentence"}}""",

    "methodology": """Classify the RESEARCH METHODOLOGY of this empirical study.

quantitative - numeric data analysed with statistical methods
qualitative  - textual, visual, or observational data analysed interpretively
mixed        - genuine integration of both traditions in one study
review       - systematic review, meta-analysis, or scoping review

TITLE: {title}
ABSTRACT: {abstract}

Respond with JSON only:
{{"label": "quantitative" | "qualitative" | "mixed" | "review" | "uncertain", "confidence": 0.0-1.0, "rationale": "one sentence"}}""",

    "extraction": """Extract structured fields for this suicide-research record.
Use "not_specified" / empty lists when the abstract does not say. Do not infer
beyond the text.

TITLE: {title}
ABSTRACT: {abstract}

Respond with JSON only:
{{"prevention_level": "universal|selective|indicated|treatment|postvention|not_applicable",
  "outcome_construct": ["suicide_death"|"suicide_attempt"|"suicidal_ideation"|"non_suicidal_self_injury"|"self_harm_undifferentiated"|"suicide_risk_composite"|"suicide_bereavement"|"attitudes_or_stigma"|"service_use_or_care_process"|"not_specified"],
  "population": ["general_population"|"youth_adolescent"|"older_adult"|"veteran_military"|"clinical_psychiatric"|"primary_care"|"justice_involved"|"lgbtq"|"indigenous"|"racial_ethnic_minority"|"rural"|"occupational"|"perinatal"|"other"],
  "study_design": ["rct"|"quasi_experimental"|"cohort_prospective"|"case_control"|"cross_sectional"|"ecological_timeseries"|"registry_linkage"|"psychological_autopsy"|"qualitative_interview"|"qualitative_other"|"mixed_methods"|"systematic_review_meta_analysis"|"scoping_narrative_review"|"simulation_modelling"|"psychometric"|"other"],
  "sdoh_focus": true|false,
  "sdoh_domain": ["economic_stability"|"education_access"|"healthcare_access"|"neighborhood_environment"|"social_community_context"|"discrimination_racism"|"housing_homelessness"|"food_insecurity"|"incarceration"|"immigration_status"|"firearm_access_means"|"digital_social_media"|"none"],
  "means_focus": ["firearm"|"poisoning_overdose"|"pesticide"|"hanging"|"jumping"|"drowning"|"other"|"none"],
  "geography": "ISO-3166 alpha-2 code, or multi, or not_specified",
  "rationale": "one sentence"}}""",
}


class OllamaClassifier:
    """Drop-in replacement for :class:`DistantClassifier` backed by a local LLM."""

    def __init__(self, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST,
                 temperature: float = 0.1, cache_dir: str | Path | None = None,
                 timeout: int = 180):
        self.model = model
        self.host = host.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.n_calls = 0
        self.n_cached = 0

    # -- plumbing ----------------------------------------------------------
    def _cache_path(self, key: str) -> Path | None:
        if not self.cache_dir:
            return None
        h = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / h[:2] / f"{h}.json.gz"

    def _generate(self, prompt: str) -> dict[str, Any]:
        key = f"{self.model}|{self.temperature}|{prompt}"
        cp = self._cache_path(key)
        if cp and cp.exists():
            self.n_cached += 1
            with gzip.open(cp, "rt", encoding="utf-8") as fh:
                return json.load(fh)

        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "system": SYSTEM,
            "stream": False,
            "format": "json",
            "options": {"temperature": self.temperature, "top_p": 0.9,
                        "num_predict": 400},
        }).encode()
        req = urllib.request.Request(
            f"{self.host}/api/generate", data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode())
        self.n_calls += 1

        parsed = _extract_json(body.get("response") or "")
        if cp:
            cp.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(cp, "wt", encoding="utf-8") as fh:
                json.dump(parsed, fh)
        return parsed

    def _stage(self, stage: str, rec: dict) -> dict[str, Any]:
        prompt = STAGE_PROMPTS[stage].format(
            title=(rec.get("title") or "")[:600],
            abstract=(rec.get("abstract") or "")[:6000])
        try:
            return self._generate(prompt)
        except Exception as e:  # noqa: BLE001
            log.warning("ollama %s failed for %s: %s", stage, rec.get("sred_id"), e)
            return {"label": "uncertain", "confidence": 0.0, "rationale": f"error: {e}"}

    # -- public API --------------------------------------------------------
    def fit(self, records: Iterable[dict]) -> "OllamaClassifier":
        """No-op: an LLM classifier is zero-shot. Present for interface parity."""
        return self

    def predict(self, records: list[dict], extract: bool = True) -> list[dict]:
        out = []
        for rec in records:
            r = dict(rec)

            s = self._stage("is_scientific", rec)
            r["is_scientific"] = (s.get("label") == "scientific")
            confs = [float(s.get("confidence") or 0)]
            rationales = {"is_scientific": s.get("rationale")}

            if r["is_scientific"]:
                e = self._stage("is_empirical", rec)
                lab = e.get("label")
                r["is_empirical"] = True if lab == "empirical" else (
                    False if lab == "non_empirical" else None)
                confs.append(float(e.get("confidence") or 0))
                rationales["is_empirical"] = e.get("rationale")

                if r["is_empirical"] is True:
                    m = self._stage("methodology", rec)
                    r["methodology"] = (m.get("label")
                                        if m.get("label") in
                                        {"quantitative", "qualitative", "mixed", "review"}
                                        else None)
                    confs.append(float(m.get("confidence") or 0))
                    rationales["methodology"] = m.get("rationale")
                else:
                    r["methodology"] = None
            else:
                r["is_empirical"] = None
                r["methodology"] = None

            if extract and r["is_scientific"]:
                x = self._stage("extraction", rec)
                for k in ("prevention_level", "outcome_construct", "population",
                          "study_design", "sdoh_focus", "sdoh_domain",
                          "means_focus", "geography"):
                    if k in x:
                        r[k] = x[k]
                rationales["extraction"] = x.get("rationale")

            r["cls_backend"] = f"ollama:{self.model}"
            r["cls_confidence"] = round(min(confs) if confs else 0.0, 4)
            r["cls_rationale"] = rationales
            out.append(r)
        return out

    def summary(self) -> dict[str, Any]:
        return {"backend": "ollama", "model": self.model,
                "temperature": self.temperature,
                "api_calls": self.n_calls, "cache_hits": self.n_cached}


_JSON_RE = re.compile(r"\{.*\}", re.S)


def _extract_json(text: str) -> dict[str, Any]:
    """Parse a JSON object out of a model response, tolerating stray prose."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _JSON_RE.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {"label": "uncertain", "confidence": 0.0,
            "rationale": "unparseable response"}
