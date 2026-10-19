"""MCP over stdio (JSON-RPC 2.0, één bericht per regel) plus een kleine CLI om te testen."""
from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import __version__, tools
from .refs import REFS
from .search import INDEX
from .util import log

USAGE = """Gebruik:
  glu-webdev-mcp                    start de MCP-server (stdio); zo start Claude hem
  glu-webdev-mcp list [leerjaar]    opdrachten tonen
  glu-webdev-mcp read <target> [deel]
  glu-webdev-mcp search <zoekterm>
  glu-webdev-mcp warm               alle pagina's ophalen en de zoekindex bouwen
"""

_out_lock = threading.Lock()


def send(msg: dict):
    data = (json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    with _out_lock:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


def call_tool(params: dict) -> dict:
    name, args = params.get("name"), params.get("arguments") or {}
    fn = tools.HANDLERS.get(name)
    if not fn:
        return {"content": [{"type": "text", "text": f"Onbekende tool: {name}"}], "isError": True}
    try:
        res = fn(**{k: v for k, v in args.items() if v is not None})
        return {"content": res if isinstance(res, list) else [{"type": "text", "text": res}]}
    except Exception as e:
        log(f"{name} {args}: {type(e).__name__}: {e}")
        return {"content": [{"type": "text", "text": f"Fout: {e}"}], "isError": True}
    finally:
        REFS.save()


def handle(msg: dict):
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:
        return  # notificatie, bv. notifications/initialized
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "glu-webdev", "version": __version__},
                  "instructions": tools.INSTRUCTIONS}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": tools.TOOLS}
    elif method == "tools/call":
        result = call_tool(params)
    else:
        send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}})
        return
    send({"jsonrpc": "2.0", "id": mid, "result": result})


def serve():
    threading.Thread(target=INDEX.warm, daemon=True).start()  # zoekindex op de achtergrond verversen
    pool = ThreadPoolExecutor(4)  # tool-calls parallel, zodat een trage call de rest niet blokkeert
    for line in sys.stdin.buffer:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
            continue
        for m in msg if isinstance(msg, list) else [msg]:
            pool.submit(handle, m)


def cli(args: list[str]):
    sys.stdout.reconfigure(encoding="utf-8")
    cmd, rest = args[0], args[1:]
    if cmd == "list":
        print(tools.list_assignments(int(rest[0]) if rest else None))
    elif cmd == "read" and rest:
        res = tools.read(rest[0], part=int(rest[1]) if len(rest) > 1 else None)
        print(res if isinstance(res, str) else res[0]["text"] + " [afbeelding]")
    elif cmd == "search" and rest:
        print(tools.search(" ".join(rest)))
    elif cmd == "warm":
        t = time.time()
        INDEX.crawl(force=True)
        print(f"{len(INDEX.meta)} pagina's geïndexeerd in {time.time() - t:.0f}s ({INDEX.errors} niet bereikbaar)")
    else:
        print(USAGE)
    REFS.save()


def main(argv: list[str] | None = None):
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        cli(argv)
    else:
        serve()
