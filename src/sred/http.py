"""Shared HTTP layer: polite rate limiting, retry with backoff, on-disk cache.

Every SRED source connector goes through :func:`get_json` / :func:`get_text`
so that (a) rate limits are honoured per host, (b) transient failures do not
lose a multi-hour harvest, and (c) a re-run of the pipeline replays from
cache rather than re-hitting the provider. Cache keys are the full request
URL; the cache is content-addressed and safe to delete at any time.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

USER_AGENT = (
    "SRED/1.0 (Suicide Research Evidence Database; "
    "+https://github.com/SRED-project; mailto:{mailto})"
)

# Provider-declared polite-pool rates (requests per second).
_HOST_RATE = {
    "api.openalex.org": 4.0,
    "eutils.ncbi.nlm.nih.gov": 2.5,   # 3/s without a key; stay under
    "api.crossref.org": 8.0,
    "doaj.org": 1.5,
    "icite.od.nih.gov": 4.0,
    "api.elsevier.com": 5.0,
    "api.clarivate.com": 1.0,
}
_DEFAULT_RATE = 2.0

_last_call: dict[str, float] = {}
_lock = threading.Lock()


def _throttle(host: str) -> None:
    rate = _HOST_RATE.get(host, _DEFAULT_RATE)
    min_gap = 1.0 / rate
    with _lock:
        prev = _last_call.get(host, 0.0)
        wait = min_gap - (time.monotonic() - prev)
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.monotonic()


class HttpCache:
    """Gzipped, URL-keyed response cache on the local filesystem."""

    def __init__(self, root: Path | str, enabled: bool = True):
        self.root = Path(root)
        self.enabled = enabled
        if enabled:
            self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, url: str) -> Path:
        h = hashlib.sha256(url.encode()).hexdigest()
        return self.root / h[:2] / f"{h}.json.gz"

    def get(self, url: str) -> str | None:
        if not self.enabled:
            return None
        p = self._path(url)
        if p.exists():
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                return fh.read()
        return None

    def put(self, url: str, body: str) -> None:
        if not self.enabled:
            return
        p = self._path(url)
        p.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(p, "wt", encoding="utf-8") as fh:
            fh.write(body)


_cache = HttpCache(Path(__file__).resolve().parents[2] / "data" / "raw" / "_httpcache")


def set_cache(root: Path | str, enabled: bool = True) -> None:
    global _cache
    _cache = HttpCache(root, enabled)


def get_text(
    url: str,
    *,
    mailto: str = "",
    headers: dict[str, str] | None = None,
    max_retries: int = 6,
    use_cache: bool = True,
    timeout: int = 90,
) -> str:
    """GET a URL, returning the decoded body. Retries with jittered backoff."""
    if use_cache:
        hit = _cache.get(url)
        if hit is not None:
            return hit

    host = urllib.parse.urlsplit(url).netloc
    hdrs = {"User-Agent": USER_AGENT.format(mailto=mailto or "unset"),
            "Accept": "application/json"}
    if headers:
        hdrs.update(headers)

    last_err: Exception | None = None
    for attempt in range(max_retries):
        _throttle(host)
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                text = body.decode("utf-8", errors="replace")
            if use_cache:
                _cache.put(url, text)
            return text
        except urllib.error.HTTPError as e:
            last_err = e
            # 4xx other than 429 are not worth retrying. 413/414 in particular
            # mean the request itself is too large - retrying it unchanged can
            # only fail again, and the caller needs to shrink the batch.
            if e.code in (400, 401, 403, 404, 413, 414) and e.code != 429:
                log.warning("HTTP %s (no retry): %s", e.code, url[:160])
                raise
            sleep = min(180, (5 ** min(attempt, 3)) + random.random() * 3) if e.code == 429 \
                else min(60, (2 ** attempt) + random.random() * 2)
            log.warning("HTTP %s, retry %d in %.1fs: %s", e.code, attempt + 1, sleep, url[:120])
            time.sleep(sleep)
        except Exception as e:  # noqa: BLE001 - network layer is intentionally broad
            last_err = e
            sleep = min(60, (2 ** attempt) + random.random() * 2)
            log.warning("%s, retry %d in %.1fs: %s", type(e).__name__, attempt + 1, sleep, url[:120])
            time.sleep(sleep)

    raise RuntimeError(f"exhausted retries for {url}: {last_err}")


class TransientAPIError(RuntimeError):
    """Provider returned an error *body* (often with HTTP 200) that is retryable."""


# Error strings that providers return in-band and that warrant a retry.
_SOFT_ERRORS = ("rate limit", "insufficient budget", "too many requests",
                "service unavailable", "try again")


def get_json(url: str, *, soft_retries: int = 5, **kw: Any) -> Any:
    """GET and parse JSON, retrying on in-band (HTTP 200) provider errors.

    OpenAlex in particular signals budget/rate exhaustion with a 200 response
    whose body is ``{"error": "Rate limit exceeded", ...}``. Treating that as
    success would silently truncate a harvest, so it is detected explicitly
    and the cache entry is discarded before retrying.
    """
    for attempt in range(soft_retries):
        text = get_text(url, **kw)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            _cache.put(url, "")  # poison the bad cache entry
            raise
        err = data.get("error") if isinstance(data, dict) else None
        if err and any(s in str(err).lower() + str(data.get("message", "")).lower()
                       for s in _SOFT_ERRORS):
            # Do not let the bad body persist in cache.
            p = _cache._path(url)
            if p.exists():
                p.unlink()
            sleep = min(240, 10 * (attempt + 1) ** 2 + random.random() * 5)
            log.warning("soft error '%s', retry %d in %.0fs", str(err)[:60], attempt + 1, sleep)
            time.sleep(sleep)
            continue
        if err:
            raise RuntimeError(f"API error for {url[:140]}: {err} {data.get('message', '')[:200]}")
        return data
    raise TransientAPIError(f"soft-error retries exhausted for {url[:140]}")
