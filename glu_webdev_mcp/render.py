"""Notion-blokken → compacte markdown, en de opdrachtenlijst uit de hoofdpagina."""
from __future__ import annotations

import re
from typing import Callable

from .notion import PAGE_TYPES, Raw
from .refs import REFS
from .util import clean_url, file_name, notion_id_from_url, plain

HEADINGS = {"header": 2, "sub_header": 3, "sub_sub_header": 4, "header_4": 5}
SKIP_TYPES = {"divider", "table_of_contents", "breadcrumb", "copy_indicator", "button", "link_to_page"}
MEDIA_TYPES = {"video", "embed", "maps", "bookmark", "file", "pdf", "audio", "figma", "codepen",
               "drive", "gist", "tweet", "external_object_instance"}
SKIP_PROP_TYPES = {"person", "created_by", "last_edited_by", "created_time", "last_edited_time",
                   "formula", "rollup", "button", "verification", "unique_id"}

LEERJAAR_RE = re.compile(r"^leerjaar\s*(\d+)$", re.I)
PERIODE_RE = re.compile(r"\b(\d+\.\d+)\b")
PREFIX_RE = re.compile(r"^((module\s*)?\d+\.\d+\s*[-:]\s*)?((module|ontwikkelweek)\b\s*[-:]?\s*)?", re.I)


def fmt_date(d: dict) -> str:
    s = d.get("start_date", "")
    if d.get("start_time"):
        s += " " + d["start_time"]
    if d.get("end_date"):
        s += " – " + d["end_date"]
    return s


def _props(b: dict | None) -> dict:
    return (b or {}).get("properties") or {}


def _fmt(b: dict | None) -> dict:
    return (b or {}).get("format") or {}


class Renderer:
    """Zet één pagina om naar markdown en verzamelt de Notion-pagina's waarnaar gelinkt wordt.

    title_lookup geeft de titel van een pagina die niet in `raw` zit (bv. uit de cache).
    """

    def __init__(self, raw: Raw, root: str, title_lookup: Callable[[str], str | None] = lambda _: None):
        self.raw, self.root, self.title_lookup = raw, root, title_lookup
        self.out: list[str] = []
        self.links: list[str] = []
        self._linkset: set[str] = set()

    # -- tekst --

    def collection_id(self, b: dict) -> str | None:
        return b.get("collection_id") or (_fmt(b).get("collection_pointer") or {}).get("id")

    def title_of(self, b: dict | None) -> str:
        if not b:
            return ""
        if b.get("type") == "collection_view_page":
            coll = self.raw.t["collection"].get(self.collection_id(b)) or {}
            return plain(coll.get("name")) or "Database"
        return plain(_props(b).get("title")).strip()

    def page_ref(self, pid: str, title: str | None = None) -> str:
        if pid not in self._linkset:
            self._linkset.add(pid)
            self.links.append(pid)
        if title is None:
            title = self.title_of(self.raw.block(pid)) or self.title_lookup(pid) or "pagina"
        return f"[{title}](@{REFS.short(pid)})"

    def link(self, text: str, href: str) -> str:
        nid = notion_id_from_url(href)
        if nid:
            return self.page_ref(nid, text.strip() or None)
        if href.startswith("/"):
            href = "https://www.notion.so" + href
        url = clean_url(href)
        t = text.strip()
        return url if not t or t in (href, url) else f"[{t}]({url})"

    def rich(self, segs) -> str:
        """Notion rich text → markdown (vet, code, doorhalen, links, mentions, datums)."""
        parts = []
        for seg in segs or []:
            if not seg:
                continue
            text = seg[0] if isinstance(seg[0], str) else ""
            anns = seg[1] if len(seg) > 1 and isinstance(seg[1], list) else []
            ann = {a[0]: (a[1] if len(a) > 1 else True) for a in anns if a}
            if "p" in ann:  # mention van een pagina
                parts.append(self.page_ref(ann["p"]))
            elif "lm" in ann and isinstance(ann["lm"], dict):  # link mention
                parts.append(self.link(ann["lm"].get("title") or "", ann["lm"].get("href") or ""))
            elif "eoi" in ann:  # extern object (bv. GitHub-repo)
                url = _fmt(self.raw.block(ann["eoi"])).get("original_url")
                if url:
                    parts.append(clean_url(url))
            elif "d" in ann and isinstance(ann["d"], dict):
                parts.append(fmt_date(ann["d"]))
            elif "e" in ann:
                parts.append(f"${ann['e']}$")
            elif "u" in ann:  # gebruikers-mention: weglaten
                continue
            elif text:
                if "c" in ann:
                    text = f"`{text}`"
                elif "b" in ann and text.strip():
                    lead, core, trail = re.match(r"(\s*)(.*?)(\s*)$", text, re.S).groups()
                    text = f"{lead}**{core}**{trail}"
                if "s" in ann:
                    text = f"~~{text}~~"
                if "a" in ann and isinstance(ann["a"], str):
                    text = self.link(text, ann["a"])
                parts.append(text)
        return "".join(parts).replace("****", "")

    # -- blokken --

    def run(self) -> tuple[str, str]:
        b = self.raw.block(self.root)
        title = self.title_of(b) or "Zonder titel"
        self.out.append(f"# {title}")
        if b.get("parent_table") == "collection":
            self.row_props(b)
        if b.get("type") == "collection_view_page":
            self.collection(b, 0, inline=False)
        else:
            self.children(b.get("content"), 0)
        md = re.sub(r"\n{3,}", "\n\n", "\n".join(line.rstrip() for line in self.out)).strip()
        return title, md

    def line(self, s: str):
        self.out.append(s)

    def children(self, ids, depth: int):
        n = 0
        for cid in ids or []:
            b = self.raw.block(cid)
            if not b:
                continue
            n = n + 1 if b.get("type") == "numbered_list" else 0
            self.block(b, depth, n)

    def prefixed(self, ids, depth: int, prefix: str):
        """Kinderen renderen met een prefix per regel (voor quotes en callouts)."""
        saved, self.out = self.out, []
        self.children(ids, 0)
        sub, self.out = self.out, saved
        ind = "  " * depth
        self.out.extend(f"{ind}{prefix}{line}" for line in sub)

    def block(self, b: dict, depth: int, n: int = 0):
        t = b.get("type")
        if t in SKIP_TYPES:
            return
        ind = "  " * depth
        props, fmt, kids = _props(b), _fmt(b), b.get("content")
        txt = self.rich(props.get("title"))

        if t in PAGE_TYPES:
            self.line(ind + self.page_ref(b["id"]))
        elif t == "alias":
            p = fmt.get("alias_pointer")
            if p:
                self.line(ind + self.page_ref(p["id"]))
        elif t in HEADINGS:
            head = re.sub(r"\s+", " ", txt.replace("**", "")).strip()
            if head:
                self.line("#" * HEADINGS[t] + " " + head)
            self.children(kids, depth)
        elif t in ("bulleted_list", "toggle"):
            if txt.strip() or kids:
                self.line(f"{ind}- {txt}")
                self.children(kids, depth + 1)
        elif t == "numbered_list":
            self.line(f"{ind}{n}. {txt}")
            self.children(kids, depth + 1)
        elif t == "to_do":
            done = "x" if plain(props.get("checked")) == "Yes" else " "
            self.line(f"{ind}- [{done}] {txt}")
            self.children(kids, depth + 1)
        elif t == "quote":
            self.line(f"{ind}> {txt}")
            self.prefixed(kids, depth, "> ")
        elif t == "callout":
            icon = fmt.get("page_icon") or ""
            icon = icon + " " if icon and len(icon) <= 4 else ""  # emoji wel, plaatjes-URL's niet
            self.line(f"{ind}> {icon}{txt}")
            self.prefixed(kids, depth, "> ")
        elif t == "code":
            lang = plain(props.get("language")).lower()
            lang = "" if lang == "plain text" else lang
            code = plain(props.get("title"))
            self.line(f"{ind}```{lang}\n{code}\n{ind}```")
        elif t == "equation":
            self.line(f"{ind}$$ {plain(props.get('title'))} $$")
        elif t in ("column_list", "column", "transclusion_container"):
            self.children(kids, depth)
        elif t == "transclusion_reference":  # synced block: inhoud van het origineel tonen
            p = fmt.get("transclusion_reference_pointer")
            target = self.raw.block(p["id"]) if p else None
            if target:
                self.children(target.get("content"), depth)
        elif t == "tab":
            for cid in kids or []:
                c = self.raw.block(cid)
                if c:
                    self.line(f"{ind}**{self.rich(_props(c).get('title'))}**")
                    self.children(c.get("content"), depth)
        elif t == "table":
            self.table(b, ind)
        elif t == "collection_view":
            self.collection(b, depth, inline=True)
        elif t == "image":
            src = plain(props.get("source")) or fmt.get("display_source") or ""
            cap = self.rich(props.get("caption")) or file_name(src) or "afbeelding"
            self.line(f"{ind}[img: {cap}](@{REFS.short(b['id'], src)})")
        elif t in MEDIA_TYPES:
            self.media(t, props, fmt, ind)
        elif txt.strip() or kids:  # tekst en onbekende types
            if txt.strip():
                self.line(ind + txt)
            self.children(kids, depth + 1 if txt.strip() else depth)

    def media(self, t: str, props: dict, fmt: dict, ind: str):
        src = (plain(props.get("link")) or plain(props.get("source")) or fmt.get("original_url")
               or fmt.get("display_source") or "")
        name = (plain(props.get("title")) or fmt.get("link_title") or self.rich(props.get("caption"))
                or file_name(src) or t)
        hosted = src.startswith("attachment:") or "amazonaws.com" in src or "notion-static" in src
        label = "" if t == "bookmark" else f"{t}: "
        nid = notion_id_from_url(src) if src.startswith(("http", "/")) and not hosted else None
        if nid:
            self.line(ind + self.page_ref(nid, plain(props.get("title")) or None))
        elif src.startswith("http") and not hosted:
            url = clean_url(src)
            self.line(f"{ind}[{label}{name}]({url})" if name != url else f"{ind}{url}")
        else:  # bestand dat bij Notion zelf staat: alleen de naam (de URL vereist een login)
            self.line(f"{ind}[{label}{name}]")

    @staticmethod
    def cell(s: str) -> str:
        return s.replace("\n", " / ").replace("|", "\\|").strip()

    def table(self, b: dict, ind: str):
        cols = _fmt(b).get("table_block_column_order") or []
        rows = [r for r in (self.raw.block(i) for i in b.get("content") or []) if r]
        if not cols or not rows:
            return
        for k, r in enumerate(rows):
            p = _props(r)
            self.line(ind + "|" + "|".join(self.cell(self.rich(p.get(c))) for c in cols) + "|")
            if k == 0:
                self.line(ind + "|" + "|".join("-" * len(cols)) + "|")

    def prop_value(self, val, ptype: str) -> str:
        if ptype in SKIP_PROP_TYPES or not val:
            return ""
        if ptype == "checkbox":
            return "✓" if plain(val) == "Yes" else ""
        if ptype == "file":
            return ", ".join(s[0] for s in val if s)
        if ptype in ("select", "multi_select", "status"):
            return plain(val)
        return self.rich(val)

    def row_props(self, b: dict):
        """Velden van een databaserij als 'Naam: waarde'-regels."""
        schema = (self.raw.t["collection"].get(b.get("parent_id")) or {}).get("schema") or {}
        for pid, val in _props(b).items():
            s = schema.get(pid) or {}
            if pid == "title" or not s:
                continue
            v = self.prop_value(val, s.get("type", "text")).replace("\n", " / ")
            if v.strip():
                self.line(f"{s.get('name', pid)}: {v}")

    def collection(self, b: dict, depth: int, inline: bool):
        """Database als markdown-tabel (titel + max. 5 zichtbare kolommen)."""
        ind = "  " * depth
        coll = self.raw.t["collection"].get(self.collection_id(b)) or {}
        schema = coll.get("schema") or {}
        view = self.raw.t["collection_view"].get((b.get("view_ids") or [None])[0]) or {}
        if inline:
            self.line(f"{ind}**{plain(coll.get('name')) or 'Database'}**")
        visible = [p["property"] for p in _fmt(view).get("table_properties") or [] if p.get("visible", True)]
        order = visible or list(schema)
        cols = ["title"] + [p for p in order if p != "title" and p in schema
                            and schema[p].get("type") not in SKIP_PROP_TYPES][:5]
        rows = [r for r in (self.raw.block(i) for i in self.raw.rows.get(b["id"], [])) if r]
        if not rows:
            self.line(f"{ind}(geen openbare rijen)")
            return
        self.line(ind + "|" + "|".join(schema.get(c, {}).get("name", c) for c in cols) + "|")
        self.line(ind + "|" + "|".join("-" * len(cols)) + "|")
        for r in rows:
            p = _props(r)
            title = plain(p.get("title")).strip() or "—"
            cells = [self.page_ref(r["id"], title) if r.get("content") else title]
            cells += [self.prop_value(p.get(c), schema[c].get("type", "text")) for c in cols[1:]]
            self.line(ind + "|" + "|".join(self.cell(c) for c in cells) + "|")


def parse_assignments(raw: Raw, root_id: str) -> list[dict]:
    """Opdrachten per leerjaar uit de kolommen van de hoofdpagina; overige pagina's per kop.

    Op de hoofdpagina staat elk leerjaar in een kolom: een tekstblok "Leerjaar N" gevolgd
    door de opdrachtpagina's. Pagina's buiten de kolommen vallen onder de kop erboven.
    """
    groups: dict[str, list[dict]] = {}

    def item(b):
        if b.get("type") == "alias" and _fmt(b).get("alias_pointer"):
            b = raw.block(_fmt(b)["alias_pointer"]["id"]) or {}
        if b.get("type") not in PAGE_TYPES:
            return None
        title = plain(_props(b).get("title")).strip()
        lower, per = title.lower(), PERIODE_RE.search(title)
        kind = "module" if "module" in lower else "ontwikkelweek" if "ontwikkelweek" in lower else "overig"
        return {"id": b["id"], "titel": title, "naam": PREFIX_RE.sub("", title).strip() or title,
                "periode": per.group(1) if per else None, "type": kind}

    current = "Overig"
    for cid in (raw.block(root_id) or {}).get("content", []):
        b = raw.block(cid)
        if not b:
            continue
        if b["type"] in HEADINGS:
            current = plain(_props(b).get("title")).strip() or current
        elif b["type"] == "column_list":
            for col in filter(None, map(raw.block, b.get("content", []))):
                leerjaar = None
                for x in filter(None, map(raw.block, col.get("content", []))):
                    m = LEERJAAR_RE.match(plain(_props(x).get("title")).strip())
                    if x["type"] == "text" and m:
                        leerjaar = f"Leerjaar {m.group(1)}"
                    elif leerjaar and (it := item(x)):
                        groups.setdefault(leerjaar, []).append(it)
            current = "Overig"
        elif it := item(b):
            groups.setdefault(current, []).append(it)

    ordered = sorted((g for g in groups if g.startswith("Leerjaar")), key=lambda g: int(g.split()[-1]))
    ordered += [g for g in groups if not g.startswith("Leerjaar")]
    return [{"groep": g, "items": groups[g]} for g in ordered]
