"""Topical screening.

A raw suicide query is noisier than a raw social-work journal list, because
"suicide" is a productive metaphor in molecular biology ("suicide gene",
"suicide substrate"), political commentary ("political suicide"), sport
("suicide squeeze"), and security studies ("suicide bombing"). Left unscreened,
these inflate the corpus and distort every trend: suicide-gene therapy papers
alone would add a spurious growth spike through the 1990s and 2000s.

Screening is a two-sided rule rather than a blocklist. A record matching a
metaphorical phrase is removed *unless* it also carries a behavioural-health
marker, which preserves the genuine literature on, say, the mental health of
survivors of suicide bombings. Every exclusion writes a reason code so the
screen is auditable and any individual decision can be revisited.
"""

from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger(__name__)


class Screener:
    def __init__(self, cfg: dict):
        ex = cfg["exclusions"]
        self.metaphor = re.compile(
            "|".join(re.escape(p) for p in ex["metaphorical_phrases"]), re.I)
        self.keep_if_also = re.compile(
            "|".join(re.escape(p) for p in ex["keep_if_also"]), re.I)
        self.non_scientific_types = {t.lower() for t in ex["non_scientific_types"]}
        self.min_abstract = int(ex["min_abstract_chars"])
        self.require_abstract = bool(ex["require_abstract"])
        # A record must mention the construct somewhere to be topical at all.
        self.topic = re.compile(
            r"suicid|self[-\s]?harm|self[-\s]?injur|parasuicide|self[-\s]?poison|"
            r"\bNSSI\b|self[-\s]?mutilat|自杀", re.I)
        self.counts: dict[str, int] = {}

    def _bump(self, reason: str) -> None:
        self.counts[reason] = self.counts.get(reason, 0) + 1

    def screen(self, rec: dict) -> tuple[bool, str]:
        """Return ``(pass, reason_code)`` for one record."""
        title = rec.get("title") or ""
        abstract = rec.get("abstract") or ""
        text = f"{title} {abstract}"
        tier = rec.get("venue_tier")

        # Records from a dedicated suicidology journal are topical by
        # definition; they still face the document-type and abstract screens
        # but not the topical one.
        core_venue = tier == "core_a"

        if self.require_abstract and len(abstract.strip()) < self.min_abstract:
            self._bump("no_or_short_abstract")
            return False, "no_or_short_abstract"

        if rec.get("year") is None:
            self._bump("no_publication_year")
            return False, "no_publication_year"

        # NOTE: document type is deliberately NOT screened here. Separating
        # scientific from other scholarly communication is classification
        # stage 1, not a pre-filter - filtering editorials and commentaries
        # out before training would leave that classifier with no negative
        # class to learn from. The screen's job is topical relevance and
        # minimum metadata; document type is decided downstream.

        if not core_venue:
            if not self.topic.search(text):
                self._bump("no_topical_term")
                return False, "no_topical_term"

            if self.metaphor.search(text) and not self.keep_if_also.search(text):
                self._bump("metaphorical_use")
                return False, "metaphorical_use"

        self._bump("pass")
        return True, "pass"

    def apply(self, records: list[dict]) -> list[dict]:
        out = []
        for r in records:
            ok, reason = self.screen(r)
            r["screen_pass"] = ok
            r["screen_reason"] = reason
            out.append(r)
        n_pass = sum(1 for r in out if r["screen_pass"])
        log.info("screen: %d/%d pass (%s)", n_pass, len(out),
                 ", ".join(f"{k}={v}" for k, v in sorted(self.counts.items())))
        return out

    def report(self) -> dict[str, Any]:
        total = sum(self.counts.values())
        return {"total_evaluated": total,
                "passed": self.counts.get("pass", 0),
                "excluded": total - self.counts.get("pass", 0),
                "by_reason": dict(sorted(self.counts.items(), key=lambda kv: -kv[1]))}
