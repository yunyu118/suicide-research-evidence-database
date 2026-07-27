"""Stage 3 - Metadata normalisation.

Journal titles arrive from providers in mutually inconsistent forms:
punctuation variants ("Health & Social Work" vs "Health and Social Work"),
NLM abbreviations ("Suicide Life Threat Behav"), subtitle presence/absence,
and genuine historical renamings ("Suicide" -> "Suicide and Life-Threatening
Behavior"). Left unresolved, these fragment a single journal into several
apparent venues and corrupt every journal-level statistic.

The resolution strategy is ISSN-first, string-second:

1. **ISSN-L**, when present, is authoritative and resolves renamings for free.
2. Otherwise a normalised title key (lowercased, de-punctuated, expanded
   abbreviations, stop-words removed) is matched exactly.
3. Otherwise fuzzy matching against already-seen canonical titles, above a
   configurable similarity threshold.

Every decision is written to a normalisation log so that the mapping is
auditable and reversible, following Perron et al. (2026).
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from rapidfuzz import fuzz, process

log = logging.getLogger(__name__)

FUZZY_ACCEPT = 93     # >= auto-accept
FUZZY_REVIEW = 85     # [REVIEW, ACCEPT) -> flagged for human review

# Common NLM/ISO abbreviation expansions seen in suicide-research venues.
ABBREV = {
    r"\bj\b": "journal", r"\bint\b": "international", r"\bam\b": "american",
    r"\bbr\b": "british", r"\beur\b": "european", r"\bpsychiatr\b": "psychiatry",
    r"\bpsychol\b": "psychology", r"\bres\b": "research", r"\bbehav\b": "behavior",
    r"\bthreat\b": "threatening", r"\bment\b": "mental", r"\bsoc\b": "social",
    r"\bsci\b": "science", r"\bmed\b": "medicine", r"\bepidemiol\b": "epidemiology",
    r"\bpublic hlth\b": "public health", r"\bhlth\b": "health",
    r"\bcommun\b": "community", r"\bdis\b": "disease", r"\bnerv\b": "nervous",
    r"\bment hlth\b": "mental health", r"\baffect\b": "affective",
    r"\bdisord\b": "disorders", r"\bclin\b": "clinical", r"\badolesc\b": "adolescent",
    r"\bchild\b": "child", r"\bgen\b": "general", r"\bhosp\b": "hospital",
    r"\bassoc\b": "association", r"\bq\b": "quarterly", r"\bstud\b": "studies",
    r"\bprev\b": "prevention", r"\bnurs\b": "nursing", r"\bcrisis interv\b": "crisis intervention",
}

_STOP = {"the", "of", "and", "a", "an", "for", "in", "on", "de", "la", "le", "des"}


def title_key(name: str) -> str:
    """Aggressive normalisation used only as a matching key, never for display."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"\(.*?\)", " ", s)               # trailing "(Online)", "(Print)"
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    for pat, rep in ABBREV.items():
        s = re.sub(pat, rep, s)
    toks = [t for t in s.split() if t and t not in _STOP]
    return " ".join(toks)


class JournalNormalizer:
    """Resolve raw journal strings to canonical titles, ISSN-first."""

    def __init__(self, fuzzy_accept: int = FUZZY_ACCEPT, fuzzy_review: int = FUZZY_REVIEW):
        self.fuzzy_accept = fuzzy_accept
        self.fuzzy_review = fuzzy_review
        self.issn_to_canonical: dict[str, str] = {}
        self.key_to_canonical: dict[str, str] = {}
        self.canonical_counts: Counter[str] = Counter()
        self.decisions: list[dict] = []
        self._display_votes: dict[str, Counter[str]] = defaultdict(Counter)

    # -- learning pass -----------------------------------------------------
    def fit(self, records) -> JournalNormalizer:
        """Learn canonical titles from the corpus.

        The canonical display form for a journal is the *most frequently
        observed full-length* variant, which reliably prefers the expanded
        title over an NLM abbreviation because expanded forms dominate in
        Crossref/OpenAlex metadata while abbreviations appear only in MEDLINE.
        """
        issn_titles: dict[str, Counter[str]] = defaultdict(Counter)
        key_titles: dict[str, Counter[str]] = defaultdict(Counter)

        for r in records:
            raw = (r.get("journal_raw") or "").strip()
            if not raw:
                continue
            issn = (r.get("issn_l") or "").strip() or None
            if issn:
                issn_titles[issn][raw] += 1
            key_titles[title_key(raw)][raw] += 1

        def best(counter: Counter[str]) -> str:
            # Prefer frequent, then longer (expanded over abbreviated).
            return max(counter.items(), key=lambda kv: (kv[1], len(kv[0])))[0]

        for issn, ctr in issn_titles.items():
            self.issn_to_canonical[issn] = best(ctr)
        for k, ctr in key_titles.items():
            if k:
                self.key_to_canonical[k] = best(ctr)

        # An ISSN's canonical title should also claim its own key.
        for canon in self.issn_to_canonical.values():
            self.key_to_canonical.setdefault(title_key(canon), canon)

        log.info("normalizer fitted: %d ISSNs, %d title keys",
                 len(self.issn_to_canonical), len(self.key_to_canonical))
        return self

    # -- application pass --------------------------------------------------
    def resolve(self, journal_raw: str, issn_l: str | None) -> tuple[str, str]:
        """Return (canonical_title, method)."""
        raw = (journal_raw or "").strip()
        if issn_l and issn_l in self.issn_to_canonical:
            return self.issn_to_canonical[issn_l], "issn"
        if not raw:
            return "", "unresolved"

        k = title_key(raw)
        if k in self.key_to_canonical:
            return self.key_to_canonical[k], "exact_key"

        match = process.extractOne(k, self.key_to_canonical.keys(),
                                   scorer=fuzz.token_sort_ratio,
                                   score_cutoff=self.fuzzy_review)
        if match:
            cand_key, score, _ = match
            canon = self.key_to_canonical[cand_key]
            method = "fuzzy_auto" if score >= self.fuzzy_accept else "fuzzy_review"
            self.decisions.append({"raw": raw, "issn_l": issn_l, "canonical": canon,
                                   "score": round(score, 1), "method": method})
            return canon, method

        # Novel journal: register it so later variants can match.
        self.key_to_canonical[k] = raw
        return raw, "new"

    def write_log(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "n_issn_mappings": len(self.issn_to_canonical),
            "n_key_mappings": len(self.key_to_canonical),
            "fuzzy_accept_threshold": self.fuzzy_accept,
            "fuzzy_review_threshold": self.fuzzy_review,
            "n_flagged_for_review": sum(1 for d in self.decisions
                                        if d["method"] == "fuzzy_review"),
            "decisions": self.decisions,
        }
        path.write_text(json.dumps(payload, indent=2))
        log.info("normalisation log -> %s (%d fuzzy decisions, %d flagged)",
                 path.name, len(self.decisions), payload["n_flagged_for_review"])


# ---------------------------------------------------------------------------
# Author name normalisation (used for coauthorship counts, not disambiguation)
# ---------------------------------------------------------------------------

def normalize_author(name: str) -> str:
    """Light normalisation of a personal name for counting purposes.

    SRED deliberately does *not* attempt full author disambiguation, for the
    same reason Perron et al. did not: it requires an entity-resolution system
    beyond the scope of database construction, and a half-done job produces
    confidently wrong collaboration networks. What this function does is
    strip formatting noise so that "Smith, John A." and "John A Smith" collapse
    to one surface form; ORCID remains the only identifier treated as
    authoritative.
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[.,]", " ", s).strip()
    if "," in name:  # "Last, First M"
        last, _, first = name.partition(",")
        s = f"{first.strip()} {last.strip()}"
    s = re.sub(r"\s+", " ", s).strip().title()
    return s
