"""Ruwe Notion-records ophalen: een pagina met alle blokken, databases en rijen die erbij horen."""
from __future__ import annotations

import urllib.error

from .config import SPACE_ID
from .net import api

PAGE_TYPES = {"page", "collection_view_page"}


class Raw:
    """Ruwe records van één pagina: blokken, databases (collection) en database-views."""

    def __init__(self):
        self.t: dict[str, dict] = {"block": {}, "collection": {}, "collection_view": {}}
        self.dead: set[str] = set()  # id's die niet bestaan of niet openbaar zijn
        self.rows: dict[str, list[str]] = {}  # database-blok → rij-id's

    def merge(self, record_map: dict | None):
        for table, entries in (record_map or {}).items():
            store = self.t.get(table)
            if store is None:
                continue
            for k, entry in entries.items():
                v = entry.get("value") if isinstance(entry, dict) else None
                # Nieuw formaat: {"value": {"value": rec, "role": ..}}; oud: {"value": rec, "role": ..}
                rec = v.get("value") if isinstance(v, dict) and "role" in v else v
                if isinstance(rec, dict) and rec.get("id") and rec.get("alive", True):
                    store[k] = rec

    def block(self, i):
        return self.t["block"].get(i)

    def fetch(self, need: dict[str, set[str]]):
        """Haalt ontbrekende records op via syncRecordValuesMain (max 100 per request)."""
        reqs = [{"pointer": {"table": t, "id": i, "spaceId": SPACE_ID}, "version": -1}
                for t, ids in need.items() for i in ids]

        def go(chunk):
            try:
                self.merge(api("syncRecordValuesMain", {"requests": chunk}).get("recordMap"))
            except urllib.error.HTTPError:
                if len(chunk) > 1:  # één ongeldige id laat de hele batch falen: splitsen
                    go(chunk[: len(chunk) // 2])
                    go(chunk[len(chunk) // 2:])

        for n in range(0, len(reqs), 100):
            go(reqs[n:n + 100])
        for t, ids in need.items():
            self.dead.update(i for i in ids if i not in self.t[t])


def mention_ids(b: dict):
    """Id's van @-mentions (pagina's) en embeds van externe objecten in de tekst van een blok."""
    for v in (b.get("properties") or {}).values():
        if not isinstance(v, list):
            continue
        for seg in v:
            for a in (seg[1] if len(seg) > 1 and isinstance(seg[1], list) else []):
                if a and a[0] in ("p", "eoi") and len(a) > 1:
                    yield a[1]


def load_raw(page_id: str) -> Raw:
    """Laadt een pagina in chunks (met cursor) en vult daarna alles aan wat nog ontbreekt."""
    raw, cursor = Raw(), {"stack": []}
    for _ in range(50):
        d = api("loadCachedPageChunkV2", {"page": {"id": page_id}, "limit": 100,
                                          "cursor": cursor, "verticalColumns": False})
        raw.merge(d.get("recordMap"))
        if not d.get("cursors"):
            break
        cursor = d["cursors"][0]
    _complete(raw, page_id)
    return raw


def _complete(raw: Raw, root: str):
    """Vult lazy-loaded blokken, synced blocks, mentions en databaserijen aan."""
    for _ in range(10):
        need: dict[str, set[str]] = {"block": set(), "collection": set(), "collection_view": set()}
        dbs = []
        stack, seen = [root], set()
        while stack:
            bid = stack.pop()
            if bid in seen:
                continue
            seen.add(bid)
            b = raw.block(bid)
            if b is None:
                need["block"].add(bid)
                continue
            need["block"].update(i for i in mention_ids(b) if not raw.block(i))
            t, fmt = b.get("type"), b.get("format") or {}
            if bid == root and b.get("parent_table") == "collection":
                need["collection"].add(b.get("parent_id"))  # databaserij: schema nodig voor de velden
            if t in ("collection_view", "collection_view_page"):
                cid = b.get("collection_id") or (fmt.get("collection_pointer") or {}).get("id")
                vids = b.get("view_ids") or []
                if cid and cid not in raw.t["collection"]:
                    need["collection"].add(cid)
                need["collection_view"].update(v for v in vids[:1] if v not in raw.t["collection_view"])
                dbs.append((b, vids[:1]))
            if bid != root and t in PAGE_TYPES:
                continue  # subpagina's worden apart gelezen
            if t == "alias" and fmt.get("alias_pointer"):
                if not raw.block(fmt["alias_pointer"]["id"]):
                    need["block"].add(fmt["alias_pointer"]["id"])
            if t == "transclusion_reference" and fmt.get("transclusion_reference_pointer"):
                stack.append(fmt["transclusion_reference_pointer"]["id"])  # synced block
            stack.extend(b.get("content") or [])

        # Databaserijen: de publieke queryCollection geeft niets terug, page_sort van de view wel
        for b, vids in dbs:
            view = raw.t["collection_view"].get(vids[0]) if vids else None
            if view and b["id"] not in raw.rows:
                rows = view.get("page_sort") or []
                raw.rows[b["id"]] = rows
                need["block"].update(r for r in rows if not raw.block(r))

        for t in need:
            need[t] = {i for i in need[t] if i and i not in raw.dead}
        if not any(need.values()):
            return
        raw.fetch(need)


def page_of(block_id: str) -> str | None:
    """Zoekt de pagina waar een los blok in staat (voor links naar een blok)."""
    raw = Raw()
    cur = block_id
    for _ in range(12):
        raw.fetch({"block": {cur}})
        b = raw.block(cur)
        if not b:
            return None
        if b.get("type") in PAGE_TYPES or b.get("parent_table") == "collection":
            return cur
        if b.get("parent_table") != "block":
            return None
        cur = b["parent_id"]
    return None
