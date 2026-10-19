"""Kleine hulpfuncties zonder afhankelijkheden binnen het pakket."""
from __future__ import annotations

import os
import re
import sys
import threading
import time
import unicodedata
import urllib.parse
from pathlib import Path

UUID_RE = re.compile(r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}", re.I)
TRACKING_PARAMS = re.compile(r"^(utm_\w+|si|fbclid|gclid|mc_\w+|ref_src)$")


def log(*args):
    """Logt naar stderr; stdout is gereserveerd voor het MCP-protocol."""
    print(*args, file=sys.stderr, flush=True)


def write_atomic(path: Path, text: str):
    """Atomisch schrijven; cachefouten mogen een tool-call nooit laten mislukken."""
    tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, "utf-8")
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:  # Windows: bestand is even open in een ander proces
                time.sleep(0.05 * (attempt + 1))
    except OSError as e:
        log(f"cache: {path.name}: {e}")
    try:
        tmp.unlink()
    except OSError:
        pass


def dashed(i: str) -> str:
    """Notion-id in standaardvorm: 8-4-4-4-12."""
    h = i.replace("-", "").lower()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def plain(segs) -> str:
    """Platte tekst uit Notion rich text ([["tekst", [annotaties]], ...])."""
    return "".join(s[0] for s in segs or [] if s and isinstance(s[0], str))


def norm(s: str) -> str:
    """Lowercase zonder accenten, met gelijke lengte (zodat posities in de tekst blijven kloppen)."""
    return "".join(unicodedata.normalize("NFKD", c)[0] for c in s.lower())


def notion_id_from_url(href: str) -> str | None:
    """Pagina-id uit een Notion-link (absoluut, relatief of met ?p=), anders None."""
    u = urllib.parse.urlparse(href)
    host = (u.netloc or "").lower()
    if href.startswith("/") or host.endswith("notion.site") or host.endswith("notion.so"):
        p = urllib.parse.parse_qs(u.query).get("p")
        ids = UUID_RE.findall(p[0] if p else u.path)
        return dashed(ids[-1]) if ids else None
    return None


def clean_url(url: str) -> str:
    """Pakt Outlook-safelinks uit en haalt trackingparameters weg."""
    u = urllib.parse.urlparse(url)
    if "safelinks.protection.outlook.com" in u.netloc:
        inner = urllib.parse.parse_qs(u.query).get("url")
        if inner:
            return clean_url(inner[0])
    if u.query:
        q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query, keep_blank_values=True)
             if not TRACKING_PARAMS.match(k)]
        u = u._replace(query=urllib.parse.urlencode(q))
    return urllib.parse.urlunparse(u)


def file_name(src: str) -> str:
    """Bestandsnaam uit een URL of Notion-bron als 'attachment:<id>:naam.png'."""
    return urllib.parse.unquote(src.split("?")[0].rstrip("/").split("/")[-1].split(":")[-1])
