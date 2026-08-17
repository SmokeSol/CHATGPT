#!/usr/bin/env python3
"""Run Atlas intake with deterministic IRI→URI normalization.

Moroccan official and party sites legitimately publish Arabic path segments.
Python's stdlib HTTP client requires an ASCII request target, so this wrapper
percent-encodes non-ASCII path/query characters before network I/O while
leaving the underlying Atlas source policy and scientific boundaries unchanged.
"""
from __future__ import annotations

from urllib.parse import quote, urlsplit, urlunsplit

import atlas395_intake as intake

_ORIGINAL_FETCH = intake.fetch


def request_uri(url: str) -> str:
    parts = urlsplit(url)
    hostname = parts.hostname or ""
    ascii_hostname = hostname.encode("idna").decode("ascii") if hostname else ""
    if parts.port:
        ascii_netloc = f"{ascii_hostname}:{parts.port}"
    else:
        ascii_netloc = ascii_hostname
    if parts.username:
        userinfo = quote(parts.username, safe="")
        if parts.password:
            userinfo += ":" + quote(parts.password, safe="")
        ascii_netloc = f"{userinfo}@{ascii_netloc}"
    path = quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~")
    query = quote(parts.query, safe="=&;%+,:/?@!$'()*-._~")
    return urlunsplit((parts.scheme, ascii_netloc, path, query, ""))


def fetch_iri(url: str) -> dict:
    result = _ORIGINAL_FETCH(request_uri(url))
    # Preserve the source-facing IRI for auditability; response.final_url stays
    # the actual ASCII URI returned by the HTTP stack.
    result["url"] = url
    return result


intake.fetch = fetch_iri


if __name__ == "__main__":
    intake.main()
