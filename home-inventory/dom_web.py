#!/usr/bin/env python3
"""dom_web: the page a QR label opens. Read-only view of one place from dom.py: its path, what lies there (with
sector and expiry), what is inside it (shelves, drawers, boxes, each with its own code).

Standard library only. Listens on 127.0.0.1 (default port 8795); publish it on the tailnet only, e.g.
`tailscale serve --bg --set-path /dom http://127.0.0.1:8795`. Works with or without the /dom prefix in the path.

  dom_web.py [--port 8795] [--host 127.0.0.1]
  GET /dom/            every coded place
  GET /dom/D007        one place
  GET /dom/D007.json   the same as JSON
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dom  # noqa: E402

PREFIX = os.environ.get("DOM_WEB_PREFIX", "/dom")

CSS = """
:root { --bg:#fff; --fg:#111; --mut:#666; --line:#ddd; --warn:#b45309; --bad:#b91c1c; --acc:#1d4ed8; }
@media (prefers-color-scheme: dark) { :root { --bg:#111; --fg:#eee; --mut:#999; --line:#333; --warn:#f59e0b;
  --bad:#f87171; --acc:#93c5fd; } }
* { box-sizing: border-box; }
body { margin:0; padding:16px; font:16px/1.4 system-ui, sans-serif; background:var(--bg); color:var(--fg); }
main { max-width: 640px; margin: 0 auto; }
h1 { font-size: 1.3rem; margin: 0 0 4px; }
.code { font-weight:700; color:var(--acc); }
.path, .mut { color: var(--mut); font-size: .9rem; }
h2 { font-size: 1rem; margin: 20px 0 6px; }
ul { list-style:none; padding:0; margin:0; }
li { padding: 8px 0; border-bottom: 1px solid var(--line); }
a { color: var(--acc); text-decoration: none; }
.soon { color: var(--warn); } .gone { color: var(--bad); }
"""


def esc(x) -> str:
    return html.escape(str(x))


def doc(title: str, body: str) -> bytes:
    return (f'<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width, initial-scale=1"><title>{esc(title)}</title><style>{CSS}</style></head>'
            f"<body><main>{body}</main></body></html>").encode()


def place_view(con, code: str) -> tuple[int, dict]:
    places = dom.place_rows(con)
    row = con.execute("SELECT id FROM places WHERE code=?", (code,)).fetchone()
    if row is None:
        return 404, {"error": f"Nie ma miejsca z kodem {code}."}
    pid = row["id"]
    here = dom.subtree_ids(places, pid)
    stock = [r for r in con.execute(dom.STOCK_SQL).fetchall() if r["place_id"] in here]
    stock.sort(key=lambda r: (r["expires"] or "9999", r["name"]))
    kids = sorted((p for p in places.values() if p["parent_id"] == pid),
                  key=lambda p: (p["pos"] if p["pos"] is not None else 10**6, p["name"]))
    return 200, {
        "code": code, "path": dom.place_path(places, pid), "note": places[pid]["note"],
        "items": [dict(dom.batch_dict(places, r), here=r["place_id"] == pid,
                       where=dom.where_txt(places, r)) for r in stock],
        "inside": [{"name": dom.place_label(places, k), "code": k["code"],
                    "items": sum(1 for r in stock if r["place_id"] in dom.subtree_ids(places, k["id"]))} for k in kids],
    }


def place_html(v: dict) -> bytes:
    items = []
    for it in v["items"]:
        exp = ""
        if it["expires"]:
            cls = "gone" if it["days_left"] < 0 else "soon" if it["days_left"] <= 3 else "mut"
            exp = f' <span class="{cls}">· do {esc(dom.fmt_date(it["expires"]))}</span>'
        spot = "" if it["here"] else f'<div class="mut">{esc(it["where"])}</div>'
        sector = " ".join(x for x in (dom.SIDE_TXT.get(it["side"] or ""), dom.DEPTH_TXT.get(it["depth"] or "")) if x)
        items.append(f'<li>{esc(it["item"])} <span class="mut">{esc(dom.fmt_qty(it["qty"]))} {esc(it["unit"])}'
                     f'{(", " + esc(sector)) if sector else ""}</span>{exp}{spot}</li>')
    kids = []
    for k in v["inside"]:
        name = esc(k["name"])
        link = f'<a href="{PREFIX}/{k["code"]}">{name}</a> <span class="code">{k["code"]}</span>' if k["code"] else name
        kids.append(f'<li>{link} <span class="mut">· {k["items"]} poz.</span></li>')
    body = (f'<h1><span class="code">{esc(v["code"])}</span> {esc(v["path"].split(" → ")[-1])}</h1>'
            f'<div class="path">{esc(v["path"])}</div>'
            + (f'<p class="mut">{esc(v["note"])}</p>' if v["note"] else "")
            + f'<h2>Co tu leży ({len(v["items"])})</h2>'
            + (f"<ul>{''.join(items)}</ul>" if items else '<p class="mut">Nic w spisie.</p>')
            + (f'<h2>W środku</h2><ul>{"".join(kids)}</ul>' if kids else "")
            + f'<p class="mut"><a href="{PREFIX}/">Wszystkie kody</a></p>')
    return doc(f'{v["code"]} {v["path"]}', body)


def index_html(con) -> bytes:
    places = dom.place_rows(con)
    rows = sorted((r for r in places.values() if r["code"]), key=lambda r: r["code"])
    lis = "".join(f'<li><a href="{PREFIX}/{r["code"]}"><span class="code">{r["code"]}</span> '
                  f'{esc(dom.place_path(places, r["id"]))}</a></li>' for r in rows)
    return doc("Kody miejsc", f"<h1>Kody miejsc</h1>" + (f"<ul>{lis}</ul>" if lis else
                                                          '<p class="mut">Brak kodów: dom code "..." --sub</p>'))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = unquote(urlsplit(self.path).path)
        if path.startswith(PREFIX):
            path = path[len(PREFIX):]
        key = path.strip("/")
        want_json = key.endswith(".json")
        key = key[:-5] if want_json else key
        con = dom.connect()
        try:
            if not key:
                status, body, ctype = 200, index_html(con), "text/html; charset=utf-8"
            else:
                code = dom.code_of(key)
                status, v = place_view(con, code) if code else (404, {"error": "Zły kod."})
                if want_json:
                    body, ctype = json.dumps(v, ensure_ascii=False).encode(), "application/json"
                elif status == 200:
                    body, ctype = place_html(v), "text/html; charset=utf-8"
                else:
                    body, ctype = doc("Nie ma", f'<h1>{esc(v["error"])}</h1><p><a href="{PREFIX}/">Wszystkie kody</a></p>'), \
                        "text/html; charset=utf-8"
        finally:
            con.close()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # quiet; systemd journal gets errors only
        pass


def main() -> int:
    p = argparse.ArgumentParser(prog="dom_web")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8795)
    a = p.parse_args()
    dom.connect().close()  # create/migrate the DB before serving
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
