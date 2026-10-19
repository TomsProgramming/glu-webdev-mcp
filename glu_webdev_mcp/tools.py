"""De drie MCP-tools: list_assignments, read en search."""
from __future__ import annotations

import re

from .config import ROOT_ID, SITE
from .paging import paginate
from .refs import REFS
from .search import INDEX
from .store import STORE
from .util import dashed, norm, notion_id_from_url
from .web import notion_image, read_external


def assignments() -> list[dict]:
    return STORE.get(ROOT_ID).get("assignments", [])


def list_assignments(leerjaar: int | None = None) -> str:
    out = []
    for g in assignments():
        if leerjaar and g["groep"] != f"Leerjaar {leerjaar}":
            continue
        out.append(f"## {g['groep']}")
        for it in g["items"]:
            ref = REFS.short(it["id"])
            if g["groep"].startswith("Leerjaar") and it["periode"]:
                naam = f": {it['naam']}" if it["naam"] != it["titel"] else ""
                out.append(f"{it['periode']} {it['type']}{naam} @{ref}")
            else:
                out.append(f"{it['titel']} @{ref}")
    return "\n".join(out) or f"Geen opdrachten gevonden voor leerjaar {leerjaar}."


def resolve(target: str):
    """Wat moet er gelezen worden?

    → ("page", id) | ("img", id, src) | ("url", url) | ("choice", tekst met kandidaten)
    """
    t = target.strip().strip("<>")
    if t.startswith("@"):
        t = t[1:]
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32}", t, re.I):
        return ("page", dashed(t))
    if re.fullmatch(r"[0-9a-f]{8,30}", t, re.I):
        e = REFS.resolve(t)
        if e and e.get("url"):
            return ("url", e["url"])
        if e:
            return ("img", e["id"], e["src"]) if e.get("src") else ("page", e["id"])
        raise LookupError(f"Onbekende ref @{t}; lees de pagina waar hij in stond opnieuw.")
    if re.match(r"https?://", t) or t.startswith("www."):
        url = t if t.startswith("http") else "https://" + t
        nid = notion_id_from_url(url)
        return ("page", nid) if nid else ("url", url)

    # Naam of periode, bv. "4.1 module" of "hoveniers": eerst de opdrachten, dan alle pagina's
    terms = norm(t).split()
    cands: dict[str, str] = {}
    for g in assignments():
        for it in g["items"]:
            if all(x in norm(f"{it['titel']} {g['groep']}") for x in terms):
                cands[it["id"]] = it["titel"]
    if not cands:
        INDEX._load()
        for pid in INDEX.meta:
            title = STORE.title(pid)
            if title and all(x in norm(title) for x in terms):
                cands[pid] = title
    if len(cands) == 1:
        return ("page", next(iter(cands)))
    exact = [pid for pid, title in cands.items() if norm(title) == norm(t)]
    if len(exact) == 1:
        return ("page", exact[0])
    if cands:
        lines = [f"Meerdere pagina's passen bij '{target}', kies een @ref:"]
        lines += [f"- {title} @{REFS.short(pid)}" for pid, title in list(cands.items())[:15]]
        return ("choice", "\n".join(lines))
    raise LookupError(f"Niets gevonden voor '{target}'. Probeer search.")


def read(target: str, section: str | None = None, part: int | None = None):
    r = resolve(target)
    if r[0] == "choice":
        return r[1]
    if r[0] == "img":
        return notion_image(r[1], r[2])
    if r[0] == "url":
        res = read_external(r[1])
        return res if isinstance(res, list) else paginate(res, part, section)
    return paginate(STORE.get(r[1])["md"], part, section)


def search(query: str, limit: int = 8) -> str:
    return INDEX.search(query, max(1, min(int(limit), 30)))


_READ_ONLY = {"readOnlyHint": True, "openWorldHint": True}

TOOLS = [
    {
        "name": "list_assignments",
        "description": "List GLU Web Development assignments per leerjaar, plus other top-level pages. "
                       "Lines: 'periode type: naam @ref'.",
        "inputSchema": {"type": "object", "properties": {
            "leerjaar": {"type": "integer", "description": "1, 2 or 3; omit for all"}}},
        "annotations": _READ_ONLY,
    },
    {
        "name": "read",
        "description": "Read a Notion page, image or any web URL as compact markdown. target: @ref, Notion URL/id, "
                       "assignment name/period ('4.1 module', 'hoveniers') or http(s) URL. Links appear as "
                       "[text](@ref) (pages, web links) or [img: ..](@ref); read the @ref to follow. Long pages: "
                       "use part or section (heading text).",
        "inputSchema": {"type": "object", "properties": {
            "target": {"type": "string"},
            "section": {"type": "string", "description": "only this heading and its subsections"},
            "part": {"type": "integer", "minimum": 1}}, "required": ["target"]},
        "annotations": _READ_ONLY,
    },
    {
        "name": "search",
        "description": "Full-text search across all pages (assignments, subpages, databases). "
                       "Returns pages with @ref, assignment and snippet. All words must match.",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "default": 8}}, "required": ["query"]},
        "annotations": _READ_ONLY,
    },
]

HANDLERS = {"list_assignments": list_assignments, "read": read, "search": search}

INSTRUCTIONS = (f"GLU Web Development curriculum ({SITE}). Find pages with list_assignments or "
                "search, then read them. Follow [title](@ref) links with read(target='@ref').")
