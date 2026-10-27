"""MCP server (stdio) for Claude Desktop on Filip's PC: "summarise <YouTube link>"
in any Claude Desktop chat runs ytdigest on the Hermes VM and returns the report.

No dependencies beyond the standard library, so it runs with any Python 3.9+ on
Windows. It talks to `ytdigest serve` over Tailscale; nothing is public.

Claude Desktop config (claude_desktop_config.json):
  "mcpServers": {"youtube-digest": {
     "command": "python", "args": ["C:\\\\path\\\\to\\\\mcp_bridge.py"],
     "env": {"YTDIGEST_URL": "http://<tailscale-ip>:8765", "YTDIGEST_TOKEN": "<from Bitwarden>"}}}
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request

TOOLS = [
    {"name": "digest_youtube_video",
     "description": "Have Hermes watch a YouTube video (transcript, key frames) and write the full report "
                    "(summary, what was said and shown, key points, how to use it, tags, transcript) to Notion. "
                    "Waits up to wait_seconds for the report and returns it as Markdown with the Notion link.",
     "inputSchema": {"type": "object", "properties": {
         "url": {"type": "string", "description": "YouTube link or video id"},
         "wait_seconds": {"type": "integer", "default": 600}}, "required": ["url"]}},
    {"name": "get_youtube_report",
     "description": "Return the existing Hermes report for a YouTube video (status, Notion link, Markdown).",
     "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
]


def _http(method: str, path: str, params: dict) -> dict:
    base = os.environ.get("YTDIGEST_URL", "http://127.0.0.1:8765").rstrip("/")
    params = {**params, "token": os.environ.get("YTDIGEST_TOKEN", "")}
    if method == "GET":
        req = urllib.request.Request(f"{base}{path}?{urllib.parse.urlencode(params)}")
    else:
        req = urllib.request.Request(f"{base}{path}", data=json.dumps(params).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def _text(rep: dict) -> str:
    if rep.get("report_md"):
        return rep["report_md"] + (f"\n\nNotion: {rep['notion_url']}" if rep.get("notion_url") else "")
    return f"status: {rep.get('status')}" + (f", error: {rep['error']}" if rep.get("error") else "")


def call(name: str, args: dict) -> str:
    url = args["url"]
    if name == "get_youtube_report":
        return _text(_http("GET", "/report", {"url": url}))
    rep = _http("GET", "/report", {"url": url})
    if rep.get("status") not in ("done", "artistic"):
        _http("POST", "/digest", {"url": url})
        # `wait_seconds` absent means "the default 10 minutes"; an explicit 0 (or a
        # negative value) means "queue it and answer right away, do not poll".
        raw_wait = args.get("wait_seconds")
        deadline = time.time() + (600 if raw_wait is None else int(raw_wait))
        while time.time() < deadline:
            time.sleep(15)
            rep = _http("GET", "/report", {"url": url})
            if rep.get("status") in ("done", "artistic", "failed"):
                break
    if rep.get("status") not in ("done", "artistic", "failed"):
        return "Hermes is still working on it; ask again with get_youtube_report in a few minutes."
    return _text(rep)


def main() -> None:
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        mid, method = msg.get("id"), msg.get("method")
        if mid is None:  # notification
            continue
        if method == "initialize":
            result = {"protocolVersion": msg.get("params", {}).get("protocolVersion", "2025-06-18"),
                      "capabilities": {"tools": {}}, "serverInfo": {"name": "youtube-digest", "version": "0.1"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            p = msg.get("params") or {}
            try:
                result = {"content": [{"type": "text", "text": call(p.get("name"), p.get("arguments") or {})}]}
            except Exception as exc:
                result = {"content": [{"type": "text", "text": f"error: {exc}"}], "isError": True}
        elif method == "ping":
            result = {}
        else:
            print(json.dumps({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found"}}), flush=True)
            continue
        print(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}), flush=True)


if __name__ == "__main__":
    main()
