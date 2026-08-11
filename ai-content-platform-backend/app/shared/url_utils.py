"""URL normalization and hashing for deduplication.

Strips tracking parameters (UTM, fbclid, etc.), lowercases the host,
removes trailing slashes, and sorts remaining query parameters so that
two URLs pointing at the same page produce the same canonical form and
SHA-256 hash.
"""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

_TRACKING_PARAMS: frozenset[str] = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "gclsrc", "dclid", "msclkid",
    "mc_cid", "mc_eid", "ref", "source", "sref",
    "_ga", "_gl", "hss_channel",
})


def normalize_url(raw_url: str) -> str:
    """Return a canonical URL suitable for dedup comparison."""
    parsed = urlparse(raw_url.strip())

    scheme = (parsed.scheme or "https").lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    path = parsed.path.rstrip("/") or "/"

    if port and ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        port = None

    netloc = host
    if port:
        netloc = f"{host}:{port}"

    params = parse_qs(parsed.query, keep_blank_values=False)
    filtered = {
        k: sorted(v)
        for k, v in sorted(params.items(), key=lambda item: item[0])
        if k.lower() not in _TRACKING_PARAMS
    }
    sorted_query = urlencode(filtered, doseq=True) if filtered else ""

    canonical = urlunparse((scheme, netloc, path, "", sorted_query, ""))
    return canonical


def hash_url(url: str) -> str:
    """Return the SHA-256 hex digest of a normalized URL."""
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


def hash_content(text: str) -> str:
    """Return the SHA-256 hex digest of article content for content-level dedup."""
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
