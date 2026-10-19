"""Cache van gerenderde pagina's: in het geheugen en op schijf (<cache>/docs/<id>.json)."""
from __future__ import annotations

import json
import threading
import time
import urllib.error
from pathlib import Path

from .config import CACHE_DIR, CACHE_TTL, RENDER_VERSION, ROOT_ID
from .notion import PAGE_TYPES, load_raw, page_of
from .render import Renderer, parse_assignments
from .util import write_atomic


class Store:
    def __init__(self, root: Path):
        self.dir = root / "docs"
        self.docs: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.inflight: dict[str, threading.Lock] = {}

    def peek(self, pid: str) -> dict | None:
        """Pagina uit de cache (ook als die verouderd is), zonder netwerk."""
        d = self.docs.get(pid)
        if d is None:
            try:
                d = json.loads((self.dir / f"{pid}.json").read_text("utf-8"))
                self.docs[pid] = d
            except (OSError, ValueError):
                return None
        return d

    def title(self, pid: str) -> str | None:
        d = self.peek(pid)
        return d["title"] if d else None

    @staticmethod
    def fresh(d: dict | None) -> bool:
        return bool(d) and d.get("v") == RENDER_VERSION and time.time() - d["t"] < CACHE_TTL

    def get(self, pid: str) -> dict:
        """Pagina uit de cache, of vers ophalen als die ontbreekt of verouderd is."""
        d = self.peek(pid)
        if self.fresh(d):
            return d
        with self.lock:
            lk = self.inflight.setdefault(pid, threading.Lock())
        with lk:  # voorkomt dubbel ophalen bij gelijktijdige calls
            d2 = self.docs.get(pid)
            if d2 is not d and self.fresh(d2):
                return d2
            try:
                new = self.build(pid)
            except Exception:
                if d:
                    return d  # liever verouderd dan niets (bv. offline)
                raise
            data = json.dumps(new, ensure_ascii=False, separators=(",", ":"))
            for key in {pid, new["id"]}:
                self.docs[key] = new
                write_atomic(self.dir / f"{key}.json", data)
            return new

    def build(self, pid: str) -> dict:
        try:
            raw = load_raw(pid)
        except urllib.error.HTTPError as e:
            if e.code not in (400, 404):
                raise
            raw = None
        b = raw.block(pid) if raw else None
        if b is None or (b.get("type") not in PAGE_TYPES and b.get("parent_table") != "collection"):
            page = page_of(pid)  # id van een los blok: lees de pagina eromheen
            if not page or page == pid:
                raise LookupError("pagina niet gevonden of niet openbaar")
            return self.build(page)
        r = Renderer(raw, pid, self.title)
        title, md = r.run()
        doc = {"id": pid, "title": title, "md": md, "links": r.links, "space": b.get("space_id"),
               "t": time.time(), "v": RENDER_VERSION}
        if pid == ROOT_ID:
            doc["assignments"] = parse_assignments(raw, ROOT_ID)
        return doc


STORE = Store(CACHE_DIR)
