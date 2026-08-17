#!/usr/bin/env python3
"""Transport-only reliability wrapper for E_reason historical roster recovery.

This deliberately does not alter source selection, cutoffs, parsing, matching,
preregistered gates, or any predictive logic. It only retries transient
web.archive.org failures and gives archive reads a larger timeout budget.
"""
from __future__ import annotations

import runpy
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

ORIGINAL_GET = requests.sessions.Session.get
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def resilient_get(self: requests.Session, url: str, *args, **kwargs):
    host = (urlparse(str(url)).hostname or "").lower()
    if host != "web.archive.org":
        return ORIGINAL_GET(self, url, *args, **kwargs)

    timeout = kwargs.get("timeout")
    if isinstance(timeout, tuple) and len(timeout) == 2:
        kwargs["timeout"] = (max(float(timeout[0]), 10.0), max(float(timeout[1]), 65.0))
    elif timeout is None:
        kwargs["timeout"] = (10, 65)
    else:
        kwargs["timeout"] = max(float(timeout), 65.0)

    last_exc: Exception | None = None
    for attempt in range(5):
        try:
            response = ORIGINAL_GET(self, url, *args, **kwargs)
            if response.status_code not in RETRYABLE_STATUS:
                return response
            if attempt == 4:
                return response
            response.close()
            last_exc = requests.HTTPError(f"retryable HTTP {response.status_code}")
        except (requests.ConnectTimeout, requests.ReadTimeout, requests.ConnectionError) as exc:
            last_exc = exc
            if attempt == 4:
                raise
        time.sleep(min(10, 2 ** attempt))
    if last_exc:
        raise last_exc
    raise RuntimeError("unreachable retry state")


requests.sessions.Session.get = resilient_get
TARGET = Path(__file__).with_name("e_reason_build_historical_rosters.py")
runpy.run_path(str(TARGET), run_name="__main__")
