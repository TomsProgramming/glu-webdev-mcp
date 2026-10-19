"""Externe links lezen: websites, GitHub, YouTube en afbeeldingen."""
from __future__ import annotations

import base64
import json
import re
import urllib.parse
from html.parser import HTMLParser

from .config import SPACE_ID
from .net import http
from .refs import REFS
from .util import clean_url, file_name

IMAGE_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp")


class HtmlToMarkdown(HTMLParser):
    """HTML → compacte markdown: alleen de hoofdinhoud, links als [tekst](@ref)."""

    SKIP = {"script", "style", "noscript", "svg", "nav", "header", "footer", "aside", "template",
            "iframe", "button", "select", "dialog", "head", "form"}
    BLOCK = {"p", "div", "section", "article", "main", "tr", "table", "ul", "ol", "dl", "dt", "dd",
             "blockquote", "figure", "figcaption", "hr", "br"}
    CONTAINERS = {"main", "article", "div", "section"}
    MAIN_IDS = {"main", "content", "main-content", "maincontent", "primary", "article", "docs-content"}

    def __init__(self, base: str):
        super().__init__(convert_charrefs=True)
        self.base, self.out, self.skip, self.pre = base, [], 0, 0
        self.title, self.in_title, self.title_done = "", False, False
        self.anchors: list[tuple[int, str | None]] = []
        self.open: dict[str, int] = {}
        self.cands: dict[int, list] = {}  # prioriteit → [tag, niveau, start, eind]

    def _prio(self, tag: str, a: dict) -> int | None:
        """Hoe waarschijnlijk dit element de hoofdinhoud bevat (lager = beter)."""
        if tag == "main":
            return 0
        if a.get("role") == "main":
            return 1
        if (a.get("id") or "").lower() in self.MAIN_IDS:
            return 2
        return 3 if tag == "article" else None

    def handle_starttag(self, tag, attrs):
        if tag == "title" and not self.title_done:
            self.in_title = True
            return
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        a = dict(attrs)
        if tag in self.CONTAINERS:
            lvl = self.open[tag] = self.open.get(tag, 0) + 1
            p = self._prio(tag, a)
            if p is not None and p not in self.cands:
                self.cands[p] = [tag, lvl, len(self.out), None]
        if tag in self.BLOCK:
            self.out.append("\n")
        elif re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n" + "#" * int(tag[1]) + " ")
        elif tag == "li":
            self.out.append("\n- ")
        elif tag in ("td", "th"):
            self.out.append(" | ")
        elif tag == "pre":
            self.pre += 1
            self.out.append("\n```\n")
        elif tag == "code" and not self.pre:
            self.out.append("`")
        elif tag == "a":
            self.anchors.append((len(self.out), a.get("href")))

    def handle_endtag(self, tag):
        if tag == "title" and self.in_title:
            self.in_title, self.title_done = False, True
            return
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if self.open.get(tag):
            for c in self.cands.values():
                if c[0] == tag and c[1] == self.open[tag] and c[3] is None:
                    c[3] = len(self.out)
            self.open[tag] -= 1
        if re.fullmatch(r"h[1-6]", tag) or tag in ("p", "li", "tr"):
            self.out.append("\n")
        elif tag == "pre":
            self.pre = max(0, self.pre - 1)
            self.out.append("\n```\n")
        elif tag == "code" and not self.pre:
            self.out.append("`")
        elif tag == "a" and self.anchors:
            idx, href = self.anchors.pop()
            text = re.sub(r"\s+", " ", "".join(self.out[idx:])).strip()
            if href and text and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                url = clean_url(urllib.parse.urljoin(self.base, href))
                self.out[idx:] = [f"[{text}](@{REFS.url(url)})"]

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.out.append(data if self.pre else re.sub(r"\s+", " ", data))

    def result(self) -> str:
        parts = self.out
        for p in sorted(self.cands):  # beste container met echte inhoud
            _, _, start, end = self.cands[p]
            if len("".join(self.out[start:end]).strip()) > 300:
                parts = self.out[start:end]
                break
        lines, blank, run = [], False, 0
        for line in "".join(parts).split("\n"):
            line = line.rstrip() if line.startswith("    ") else re.sub(r"[ \t]+", " ", line).strip()
            if not line or line in ("-", "|", "`", "``") or _nav_line(line):
                if not blank and lines:
                    lines.append("")
                blank, run = True, 0
                continue
            run = run + 1 if _LINK_ONLY.fullmatch(line) else 0
            if run > 12:  # lange lijsten met alleen links (menu's, sitemaps) inkorten
                if run == 13:
                    lines.append("- …")
                continue
            lines.append(line)
            blank = False
        # lege regels alleen bewaren vóór koppen
        lines = [x for i, x in enumerate(lines) if x or (i + 1 < len(lines) and lines[i + 1].startswith("#"))]
        body = "\n".join(lines).strip()
        title = re.sub(r"\s+", " ", self.title).strip()
        return (f"# {title}\n" if title else "") + body


_LINK = re.compile(r"\[([^\]]*)\]\(@[0-9a-f]+\)")
_LINK_ONLY = re.compile(r"(- )?\[[^\]]*\]\(@[0-9a-f]+\)")


def _nav_line(line: str) -> bool:
    """Regel die vooral uit links bestaat (navigatie, breadcrumbs, tags)."""
    links = _LINK.findall(line)
    if len(links) < 3:
        return False
    # alleen echte tekens tellen, geen spaties en scheidingstekens als | · / ,
    text_len = len(_SEPARATORS.sub("", _LINK.sub(lambda m: m.group(1), line)))
    link_len = len(_SEPARATORS.sub("", "".join(links)))
    return link_len / max(1, text_len) > 0.7


_SEPARATORS = re.compile(r"[\s|·•/,;:\-–—»›>]+")


def html_to_markdown(html: str, base_url: str) -> str:
    p = HtmlToMarkdown(base_url)
    p.feed(html)
    return p.result()


def github(url: str) -> str | None:
    """Repo → bestandslijst + README; bestand → inhoud. None als het geen repo-URL is."""
    m = re.match(r"https?://github\.com/([^/]+)/([^/#?]+?)(?:\.git)?/?(?:(blob|tree)/([^/]+)/?(.*))?$", url)
    if not m:
        return None
    owner, repo, kind, ref, path = m.groups()
    if kind == "blob":
        raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
        return f"# {path}\n```\n{http(raw)[0].decode('utf-8', 'replace')}\n```"
    api_base = f"https://api.github.com/repos/{owner}/{repo}"
    sub = f"/{path}" if kind == "tree" and path else ""
    try:
        items = json.loads(http(f"{api_base}/contents{sub}" + (f"?ref={ref}" if ref else ""))[0])
    except Exception:
        return None
    names = ", ".join(i["name"] + ("/" if i["type"] == "dir" else "") for i in items)
    out = [f"# {owner}/{repo}{sub}\nBestanden: {names}"]
    if not sub:
        try:
            readme = http(f"{api_base}/readme", headers={"Accept": "application/vnd.github.raw"})[0]
            out.append(readme.decode("utf-8", "replace"))
        except Exception:
            pass
    return "\n\n".join(out)


def youtube(url: str) -> str:
    o = json.loads(http("https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(url))[0])
    return f"YouTube-video: {o.get('title')} — {o.get('author_name')}\n{url}\n(transcript niet beschikbaar)"


def read_external(url: str):
    """Markdown-tekst van een webpagina, of een MCP-afbeelding."""
    url = clean_url(url)
    host = urllib.parse.urlparse(url).netloc.lower()
    if host.endswith("github.com"):
        try:
            gh = github(url)
            if gh is not None:
                return gh
        except Exception:
            pass  # val terug op de gewone HTML-pagina
    if host.endswith(("youtube.com", "youtu.be")):
        try:
            return youtube(url)
        except Exception:
            pass
    body, ctype, charset = http(url)
    if ctype.startswith("image/"):
        return image_content(body, ctype, url)
    if ctype == "application/pdf":
        return f"PDF ({len(body) // 1024} KB) kan niet als tekst gelezen worden: {url}"
    text = body.decode(charset or "utf-8", "replace")
    if ctype in ("text/html", "application/xhtml+xml"):
        return html_to_markdown(text, url)
    return text


def image_content(data: bytes, ctype: str, label: str):
    """MCP-content met een afbeelding, zodat Claude hem echt kan bekijken."""
    if ctype not in IMAGE_TYPES:
        return f"Afbeelding in formaat {ctype} kan niet getoond worden: {label}"
    return [{"type": "text", "text": label},
            {"type": "image", "data": base64.b64encode(data).decode(), "mimeType": ctype}]


def notion_image(block_id: str, src: str):
    """Afbeelding uit Notion via de image-proxy (verkleind tot 1000px breed: minder tokens)."""
    url = (f"https://www.notion.so/image/{urllib.parse.quote(src, safe='')}"
           f"?table=block&id={block_id}&spaceId={SPACE_ID}&width=1000&cache=v2")
    body, ctype, _ = http(url, max_bytes=10_000_000)
    return image_content(body, ctype, file_name(src))
