"""HTTP met throttling en retries, en de (niet-officiële) publieke Notion API."""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

from .config import SITE, UA, WORKERS

_slots = threading.BoundedSemaphore(WORKERS)


def http(url: str, body: dict | None = None, *, headers: dict | None = None,
         max_bytes: int = 5_000_000, timeout: int = 30):
    """GET (of POST als body is gegeven). Geeft (bytes, content_type, charset).

    Bij een rate limit (429) of serverfout wordt tot 5 keer opnieuw geprobeerd met
    oplopende wachttijd, en wordt een Retry-After-header gerespecteerd.
    """
    hdrs = {"User-Agent": UA, **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    delay = 1.0
    for attempt in range(6):
        try:
            with _slots, urllib.request.urlopen(urllib.request.Request(url, data, hdrs), timeout=timeout) as r:
                return r.read(max_bytes), r.headers.get_content_type(), r.headers.get_content_charset()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 5:
                raise
            wait = e.headers.get("Retry-After")
            time.sleep(min(float(wait) if wait and wait.isdigit() else delay, 30))
        except (urllib.error.URLError, TimeoutError):
            if attempt >= 2:
                raise
            time.sleep(delay)
        delay *= 2
    raise RuntimeError("onbereikbaar")


def api(endpoint: str, body: dict) -> dict:
    """POST naar https://<site>/api/v3/<endpoint>; dezelfde API die de Notion-website gebruikt."""
    return json.loads(http(f"https://{SITE}/api/v3/{endpoint}", body)[0])
