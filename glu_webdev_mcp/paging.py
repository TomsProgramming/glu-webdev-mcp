"""Lange teksten opdelen in delen, of alleen één sectie teruggeven."""
from __future__ import annotations

import re

from .config import MAX_CHARS
from .util import norm

_HEADING = re.compile(r"(#{1,6}) (.+)")


def headings(md: str):
    for line in md.split("\n"):
        m = _HEADING.match(line)
        if m:
            yield len(m.group(1)), m.group(2).strip()


def section_of(md: str, section: str, limit: int = MAX_CHARS) -> str | None:
    """De kop die `section` bevat, met alles eronder tot de volgende kop van hetzelfde niveau."""
    lines, key = md.split("\n"), norm(section)
    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if m and key in norm(m.group(2)):
            lvl, out = len(m.group(1)), [line]
            for nxt in lines[i + 1:]:
                m2 = re.match(r"(#{1,6}) ", nxt)
                if m2 and len(m2.group(1)) <= lvl:
                    break
                out.append(nxt)
            return "\n".join(out)
    for i, line in enumerate(lines):  # geen kop gevonden: vanaf de eerste regel met de tekst
        if key in norm(line):
            return "\n".join(lines[i:])[:limit]
    return None


def split_parts(md: str, limit: int = MAX_CHARS) -> list[str]:
    """Splitst op regelgrenzen, bij voorkeur vlak voor een kop."""
    parts, cur, size = [], [], 0
    for line in md.split("\n"):
        while len(line) > limit:
            parts.append(line[:limit])
            line = line[limit:]
        if cur and (size + len(line) > limit or (line.startswith("#") and size > limit * 0.7)):
            parts.append("\n".join(cur))
            cur, size = [], 0
        cur.append(line)
        size += len(line) + 1
    if cur:
        parts.append("\n".join(cur))
    return parts


def paginate(md: str, part: int | None = None, section: str | None = None, limit: int = MAX_CHARS) -> str:
    if section:
        sec = section_of(md, section, limit)
        if sec is None:
            koppen = "\n".join(f"{'#' * lvl} {h}" for lvl, h in headings(md))
            return f"Sectie '{section}' niet gevonden. Koppen:\n{koppen}"
        md = sec
    if len(md) <= limit:
        return md
    parts = split_parts(md, limit)
    n = min(max(part or 1, 1), len(parts))
    text = f"[deel {n}/{len(parts)}]\n{parts[n - 1]}"
    if n == 1:  # inhoudsopgave, zodat Claude gericht een deel of sectie kan opvragen
        where: dict[str, int] = {}
        for i, p in enumerate(parts, 1):
            for lvl, h in headings(p):
                if lvl <= 3:
                    where.setdefault(h, i)
        if where:
            text += "\n\n[koppen → deel: " + "; ".join(f"{h} → {i}" for h, i in where.items()) + "]"
    if n < len(parts):
        text += f"\n[vervolg: part={n + 1}]"
    return text
