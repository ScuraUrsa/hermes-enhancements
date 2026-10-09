"""Tiny HTTP endpoint for one-click use (phone share sheet, browser bookmark).

  POST /digest  {"url": "...", "token": "..."}        -> 202, runs now (priority 100)
  GET  /digest?url=...&token=...                      -> same, for bookmarklets
  POST /queue   {"url": "...", "token": "..."}        -> 202, backlog priority
  GET  /health

Bind it to localhost or the Tailscale address only (never 0.0.0.0): Filip's
"nothing public" rule. The token comes from env YTDIGEST_TOKEN.
"""

from __future__ import annotations

import hmac
import html
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import fetch, pipeline
from .queue import BACKLOG_PRIORITY, USER_PRIORITY, Queue

_lock = threading.Lock()


def make_handler(cfg: dict, q_path, notify=None):
    token = os.environ.get("YTDIGEST_TOKEN", "")
    if not token:
        raise SystemExit("set YTDIGEST_TOKEN before starting the server")

    def run_now(vid: str, url: str) -> None:
        with _lock:  # one heavy job at a time on the 8 GB VM
            q = Queue(q_path)
            q.add(vid, url, priority=USER_PRIORITY, account="ręcznie")
            row = q.next(min_priority=USER_PRIORITY)
            if not row:
                return
            res = pipeline.safe_process(row["url"], cfg, account=row["account"], tag="manual")
            q.finish(row["video_id"], res)
            if notify:
                notify(res)

    class H(BaseHTTPRequestHandler):
        def _reply(self, code: int, body: dict) -> None:
            if "text/html" in (self.headers.get("Accept") or ""):  # bookmarklet opens a tab
                msg = {202: "Hermes ogląda ten film. Raport pojawi się w Notion (Raporty wideo)."}.get(code, body.get("error", ""))
                data = (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                        f"<body style='font:18px sans-serif;padding:2em'><p>{html.escape(str(msg))}</p>"
                        f"<script>setTimeout(()=>window.close(),2500)</script>").encode()
                ctype = "text/html; charset=utf-8"
            else:
                data = json.dumps(body, ensure_ascii=False).encode()
                ctype = "application/json; charset=utf-8"
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _handle(self, params: dict, path: str) -> None:
            if path == "/health":
                return self._reply(200, {"ok": True})
            if not hmac.compare_digest(str(params.get("token", "")), token):
                return self._reply(401, {"error": "bad token"})
            try:
                vid = fetch.video_id(str(params.get("url", "")))
            except ValueError as exc:
                return self._reply(400, {"error": str(exc)})
            url = fetch.watch_url(vid)
            if path == "/digest":
                threading.Thread(target=run_now, args=(vid, url), daemon=True).start()
                return self._reply(202, {"queued": vid, "priority": "now"})
            if path == "/queue":
                Queue(q_path).add(vid, url, priority=BACKLOG_PRIORITY + 20, account="ręcznie")
                return self._reply(202, {"queued": vid, "priority": "backlog"})
            return self._reply(404, {"error": "unknown path"})

        def do_GET(self):  # noqa: N802
            u = urlparse(self.path)
            self._handle({k: v[0] for k, v in parse_qs(u.query).items()}, u.path)

        def do_POST(self):  # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                body = {}
            if not body.get("token"):
                auth = self.headers.get("Authorization", "")
                body["token"] = auth.removeprefix("Bearer ").strip()
            self._handle(body, urlparse(self.path).path)

        def log_message(self, fmt, *args):  # quieter journal
            pass

    return H


def serve(cfg: dict, q_path, host: str, port: int, notify=None) -> None:
    if host in ("0.0.0.0", "::"):
        raise SystemExit("refusing to listen on all interfaces; use 127.0.0.1 or the Tailscale IP")
    ThreadingHTTPServer((host, port), make_handler(cfg, q_path, notify)).serve_forever()
