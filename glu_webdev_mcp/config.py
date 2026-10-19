"""Instellingen. Alles is te overschrijven met omgevingsvariabelen (zie README)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _default_cache_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "glu-webdev-mcp"


# De Notion-site die gelezen wordt
SITE = os.environ.get("GLU_SITE", "gluwebdev.notion.site")
SPACE_ID = os.environ.get("GLU_SPACE_ID", "0216a67a-859e-4730-996f-5d51b31fa395")
ROOT_ID = os.environ.get("GLU_ROOT_PAGE", "b8d9ced7-98b7-41d3-a375-fcafbb470a43")  # "Web Development"

CACHE_DIR = Path(os.environ.get("GLU_CACHE_DIR") or _default_cache_dir())
CACHE_TTL = float(os.environ.get("GLU_CACHE_HOURS", "12")) * 3600
MAX_CHARS = int(os.environ.get("GLU_MAX_CHARS", "12000"))
WORKERS = int(os.environ.get("GLU_WORKERS", "3"))  # hoger = sneller, maar Notion geeft dan 429's

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"

# Ophogen als de markdown-output verandert: de oude cache wordt dan automatisch vervangen
RENDER_VERSION = 2
