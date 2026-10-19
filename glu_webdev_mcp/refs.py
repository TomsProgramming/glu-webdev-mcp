"""Korte, stabiele verwijzingen (@ref) in plaats van lange id's en URL's, om tokens te sparen.

Een Notion-id als 3f169bb8-092d-8006-b102-ff79ad8ff7d6 kost ±25 tokens; de ref @ad8ff7d6
(de laatste 8 hex-tekens) maar een paar. Externe URL's krijgen 8 tekens van hun sha1.
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from .config import CACHE_DIR
from .util import write_atomic

MAX_URL_REFS = 5000


class Refs:
    def __init__(self, path: Path):
        self.path, self.lock, self.dirty = path, threading.Lock(), False
        self.map: dict[str, dict] = {}  # ref → {"id": .., "src": ..} of {"url": ..}
        self.rev: dict[str, str] = {}  # id of url → ref
        self._merge_disk()

    @staticmethod
    def _key(e: dict) -> str:
        return e.get("id") or e.get("url", "")

    def _merge_disk(self):
        """Neemt refs van andere serverprocessen (bv. Claude Desktop + Claude Code) over."""
        try:
            disk = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            return
        for s, e in disk.items():
            if s not in self.map and self._key(e) not in self.rev:
                self.map[s] = e
                self.rev[self._key(e)] = s

    def _add(self, key: str, h: str, entry: dict) -> str:
        for n in range(8, len(h) + 1, 2):  # bij een botsing een langere ref nemen
            s = h[-n:]
            if s not in self.map:
                self.map[s], self.rev[key], self.dirty = entry, s, True
                return s
        return key

    def short(self, full_id: str, src: str | None = None) -> str:
        """Ref voor een Notion-pagina of (met src) een afbeelding."""
        with self.lock:
            s = self.rev.get(full_id)
            if s:
                if src and not self.map[s].get("src"):
                    self.map[s]["src"], self.dirty = src, True
                return s
            entry = {"id": full_id, **({"src": src} if src else {})}
            return self._add(full_id, full_id.replace("-", ""), entry)

    def url(self, url: str) -> str:
        """Ref voor een externe URL."""
        with self.lock:
            return self.rev.get(url) or self._add(url, hashlib.sha1(url.encode()).hexdigest(), {"url": url})

    def resolve(self, s: str) -> dict | None:
        s = s.lower()
        for attempt in range(2):
            if s in self.map:
                return self.map[s]
            hits = [e for e in self.map.values() if e.get("id", "").replace("-", "").endswith(s)]
            if len(hits) == 1:
                return hits[0]
            if attempt == 0:  # misschien net aangemaakt door een ander proces
                with self.lock:
                    self._merge_disk()
        return None

    def save(self):
        with self.lock:
            if not self.dirty:
                return
            self.dirty = False
            self._merge_disk()
            urls = [s for s, e in self.map.items() if "url" in e]
            for s in urls[:max(0, len(urls) - MAX_URL_REFS)]:  # oudste web-links opruimen
                self.rev.pop(self.map.pop(s)["url"], None)
            write_atomic(self.path, json.dumps(self.map, ensure_ascii=False, separators=(",", ":")))


REFS = Refs(CACHE_DIR / "refs.json")
