"""Zoekindex: crawlt alle pagina's van de site (op de achtergrond) en zoekt in hun tekst."""
from __future__ import annotations

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import CACHE_DIR, CACHE_TTL, RENDER_VERSION, ROOT_ID, SPACE_ID, WORKERS
from .refs import REFS
from .store import STORE
from .util import log, norm, write_atomic

LOCK_TIMEOUT = 900  # een crawl-lock ouder dan dit (s) is van een gecrasht proces


class Index:
    def __init__(self, root: Path):
        self.path = root / "index.json"
        self.lockfile = root / "crawl.lock"
        self.meta: dict[str, dict] = {}  # pagina-id → {"p": ouder, "g": opdracht}
        self.complete, self.t, self.mtime, self.v = False, 0.0, 0.0, None
        self.running, self.done, self.errors = False, 0, 0
        self.norm: dict[str, tuple[float, str]] = {}
        self._load()

    # -- opslag --

    def _load(self):
        """Leest index.json opnieuw als een (ander) proces hem heeft bijgewerkt."""
        try:
            m = self.path.stat().st_mtime
            if m == self.mtime:
                return
            d = json.loads(self.path.read_text("utf-8"))
            self.meta, self.complete, self.t, self.mtime = d["meta"], d["complete"], d["t"], m
            self.v = d.get("v")
        except (OSError, ValueError, KeyError):
            pass

    def _save(self, complete: bool):
        self.complete, self.v = complete, RENDER_VERSION
        data = {"t": self.t, "v": self.v, "complete": complete, "meta": self.meta}
        write_atomic(self.path, json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        try:
            self.mtime = self.path.stat().st_mtime
        except OSError:
            pass

    def stale(self) -> bool:
        self._load()
        return not self.complete or self.v != RENDER_VERSION or time.time() - self.t > CACHE_TTL

    # -- crawlen --

    def warm(self):
        if self.stale():
            self.crawl()

    def crawl(self, force: bool = False):
        """Breadth-first over alle pagina's in de space. Eén crawler tegelijk, ook over processen heen."""
        try:
            if force:
                self.lockfile.unlink(missing_ok=True)
            elif self.lockfile.exists() and time.time() - self.lockfile.stat().st_mtime < LOCK_TIMEOUT:
                return
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self.lockfile.write_text(str(os.getpid()))
        except OSError:
            return
        self.running, self.done, self.errors = True, 0, 0
        try:
            root = STORE.get(ROOT_ID)
            labels = {it["id"]: (f"{it['periode']} {it['naam']}" if it["periode"] else it["titel"])
                      for g in root.get("assignments", []) for it in g["items"]}
            meta = {ROOT_ID: {"p": None, "g": ""}}
            queue = [ROOT_ID]
            self.t = time.time()
            with ThreadPoolExecutor(WORKERS) as ex:
                while queue:
                    nxt = []
                    for pid, d in zip(queue, ex.map(self._safe_get, queue)):
                        self.done += 1
                        if not d or d.get("space") != SPACE_ID:
                            continue  # niet openbaar, of een pagina buiten deze site
                        for link in d["links"]:
                            if link not in meta:
                                meta[link] = {"p": pid, "g": meta[pid]["g"] or labels.get(link, "")}
                                nxt.append(link)
                    queue = nxt
                    self.meta = meta
                    self._save(complete=False)
                    REFS.save()
                    try:
                        self.lockfile.touch()  # lock blijft geldig zolang de crawl loopt
                    except OSError:
                        pass
            self._save(complete=True)
        finally:
            self.running = False
            try:
                self.lockfile.unlink()
            except OSError:
                pass

    def _safe_get(self, pid):
        try:
            return STORE.get(pid)
        except Exception as e:
            self.errors += 1
            log(f"crawl: {pid}: {e}")
            return None

    # -- zoeken --

    def text(self, pid: str) -> tuple[dict, str] | None:
        d = STORE.peek(pid)
        if not d:
            return None
        cached = self.norm.get(pid)
        if not cached or cached[0] != d["t"]:
            cached = (d["t"], norm(d["title"] + "\n" + d["md"]))
            self.norm[pid] = cached
        return d, cached[1]

    def search(self, query: str, limit: int = 8) -> str:
        self._load()
        if not self.meta and not self.running:
            threading.Thread(target=self.crawl, daemon=True).start()
            time.sleep(0.5)
        terms = [t for t in norm(query).split() if t]
        if not terms:
            return "Lege zoekopdracht."

        hits = []
        for pid in list(self.meta) or list(STORE.docs):
            got = self.text(pid)
            if not got:
                continue
            d, text = got
            if not all(t in text for t in terms):
                continue
            title = norm(d["title"])
            score = sum(min(text.count(t), 20) for t in terms) + (40 if all(t in title for t in terms) else 0)
            hits.append((score, pid, d, text))
        hits.sort(key=lambda h: -h[0])

        status = ""
        if self.running or not self.complete:
            done = self.done or len(self.meta)
            status = f" (index nog bezig: {done} pagina's gedaan, probeer straks opnieuw voor alle resultaten)"
        if not hits:
            return f"Geen treffers voor '{query}'.{status}"
        lines = [f"{len(hits)} treffers voor '{query}'{status}:"]
        for _, pid, d, text in hits[:limit]:
            group = (self.meta.get(pid) or {}).get("g")
            lines.append(f"- [{d['title']}](@{REFS.short(pid)})" + (f" · {group}" if group else "")
                         + snippet(d, text, terms))
        if len(hits) > limit:
            lines.append(f"(+{len(hits) - limit} meer; verhoog limit of verfijn de zoekterm)")
        return "\n".join(lines)


def snippet(d: dict, text: str, terms: list[str]) -> str:
    """±160 tekens rond de eerste treffer in de tekst (niet in de titel), zonder markdown."""
    offset = len(d["title"]) + 1  # positie van de markdown in de genormaliseerde tekst
    body = offset + d["md"].find("\n") + 1  # eerste regel van de markdown is de titel zelf
    pos = min((p for t in terms if (p := text.find(t, body)) >= 0), default=-1)
    if pos < 0:
        return ""
    raw = d["md"][max(0, pos - offset - 60): pos - offset + 100]
    raw = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", raw)
    raw = re.sub(r"[#*>`|]+|\s+", " ", raw)
    return " …" + re.sub(r" {2,}", " ", raw).strip() + "…"


INDEX = Index(CACHE_DIR)
