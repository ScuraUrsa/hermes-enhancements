#!/usr/bin/env python3
"""dom_labels: printable QR labels for dom.py places (boxes, furniture, shelves) and QR business cards.

Idea from Homebox's label maker: every place gets a short code (dom code ... -> D007); the label shows a QR code with
the URL of its page (dom_web.py), the code in big letters (Filip can just say "co jest w D007") and the path.
Business cards carry a vCard QR: a phone camera saves the contact without any app.

Standard library only: QR codes come from dom_qr.py next to this file.
Output is one HTML page with exact millimetre sizes; print it from a browser at 100% scale (no "fit to page").

  dom_labels.py labels D001 D004            labels for these codes
  dom_labels.py labels --where "Pokój Teosia" [--assign]   every coded place under it (--assign: give codes first)
  dom_labels.py labels --all --size 70x37 --cols 3 --rows 8 --out naklejki.html
  dom_labels.py card --name "Filip Kaźmierczak" --phone "+48 ..." --email ... [--title ...] [--org ...]
                     [--url ...] [--count 10] --out wizytowki.html
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dom  # noqa: E402
import dom_qr  # noqa: E402

# the scan page (dom_web.py) behind `tailscale serve`; reachable from Filip's phone and PC on the tailnet
DEFAULT_BASE = os.environ.get("DOM_LABEL_URL", "https://hermes-vm-1.tail5c846a.ts.net/dom")

PAGE = """<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>{title}</title><style>
@page {{ size: A4; margin: {mt}mm {ml}mm; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "DejaVu Sans", Arial, sans-serif; color: #000; background: #fff; }}
.sheet {{ display: grid; grid-template-columns: repeat({cols}, {w}mm); grid-auto-rows: {h}mm; gap: {gap}mm; }}
.sheet + .sheet {{ break-before: page; }}
.cell {{ width: {w}mm; height: {h}mm; overflow: hidden; display: flex; align-items: center; gap: 2mm; padding: 2mm;
        {outline} }}
.cell svg {{ flex: none; width: {qr}mm; height: {qr}mm; }}
.txt {{ min-width: 0; line-height: 1.15; }}
.code {{ font-size: {code_pt}pt; font-weight: 700; letter-spacing: .5pt; }}
.path {{ font-size: {path_pt}pt; }}
.card .name {{ font-size: 12pt; font-weight: 700; }}
.card .line {{ font-size: 7.5pt; }}
@media screen {{ body {{ padding: 8mm; background: #eee; }} .sheet {{ background: #fff; padding: 4mm; }} }}
</style></head><body>
{sheets}
</body></html>"""


def qr_svg(data: str, error: str = "m") -> str:
    m = dom_qr.encode(data, error.upper())
    n = len(m) + 2  # one-module border, as before
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" shape-rendering="crispEdges">'
            f'<rect width="{n}" height="{n}" fill="#fff"/>{dom_qr.svg_path(m, 1, 1, 1)}</svg>')


def vcard_data(name: str, displayname: str, phone=None, email=None, url=None, org=None, title=None) -> str:
    def esc(v: str) -> str:
        return v.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")

    lines = ["BEGIN:VCARD", "VERSION:3.0", f"N:{name}", f"FN:{esc(displayname)}"]
    for key, val in (("ORG", org), ("TITLE", title), ("TEL", phone), ("EMAIL", email), ("URL", url)):
        if val:
            lines.append(f"{key}:{esc(val)}")
    return "\r\n".join(lines + ["END:VCARD"])


def page(cells: list[str], title: str, w: float, h: float, cols: int, rows: int, gap: float, qr: float,
         code_pt: float, path_pt: float, outline: bool, margins: tuple[float, float]) -> str:
    per = cols * rows
    sheets = ["<div class=\"sheet\">" + "".join(cells[i:i + per]) + "</div>" for i in range(0, len(cells), per)]
    return PAGE.format(title=html.escape(title), w=w, h=h, cols=cols, gap=gap, qr=qr, code_pt=code_pt,
                       path_pt=path_pt, outline="outline: .2mm dashed #999;" if outline else "",
                       mt=margins[0], ml=margins[1], sheets="\n".join(sheets))


def dom_json(*argv) -> list[dict]:
    code, out = dom.run(["--json", *argv])
    if code != 0:
        raise SystemExit(json.loads(out).get("error", out))
    return json.loads(out)["data"]


def place_cells(entries: list[dict], base: str, qr: float) -> list[str]:
    cells = []
    for e in entries:
        url = f"{base.rstrip('/')}/{e['code']}"
        cells.append(f'<div class="cell">{qr_svg(url)}<div class="txt"><div class="code">{e["code"]}</div>'
                     f'<div class="path">{html.escape(e["path"])}</div></div></div>')
    return cells


def cmd_labels(a) -> str:
    if a.where:
        if a.assign:
            dom_json("code", a.where, "--sub")
        con = dom.connect()
        try:
            prefix = dom.place_path(dom.place_rows(con), dom.resolve_place(con, a.where), pretty=False)
        except dom.DomError as e:
            raise SystemExit(str(e))
        finally:
            con.close()
        everything = dom_json("code", "--list")
        entries = [e for e in everything if e["full_path"] == prefix or e["full_path"].startswith(prefix + " > ")]
    else:
        everything = {e["code"]: e for e in dom_json("code", "--list")}
        if a.all:
            entries = list(everything.values())
        else:
            wanted = [dom.code_of(c) or c for c in a.codes]
            missing = [c for c in wanted if c not in everything]
            if missing:
                raise SystemExit("Brak kodów: " + ", ".join(missing) + " (nadaj: dom code \"...\")")
            entries = [everything[c] for c in wanted]
    if not entries:
        raise SystemExit("Nic do wydruku: te miejsca nie mają kodów (dom code \"...\" --sub).")
    entries = [e for e in entries for _ in range(a.copies)]
    w, h = (float(x) for x in a.size.lower().split("x"))
    qr = min(h - 4, w * 0.45)
    return page(place_cells(entries, a.base, qr), "Naklejki dom", w, h, a.cols, a.rows, a.gap, qr,
                code_pt=max(9, min(18, h * 0.42)), path_pt=max(6, min(9, h * 0.2)), outline=a.outline,
                margins=(a.margin_top, a.margin_left))


def cmd_card(a) -> str:
    parts = a.name.split()
    vcard = vcard_data(
        name=f"{parts[-1]};{' '.join(parts[:-1])}" if len(parts) > 1 else a.name, displayname=a.name,
        phone=a.phone, email=a.email, url=a.url, org=a.org, title=a.title)
    lines = [x for x in (a.title, a.org, a.phone, a.email, a.url) if x]
    w, h, qr = 85.0, 55.0, 30.0
    cell = (f'<div class="cell card">{qr_svg(vcard, error="l")}<div class="txt"><div class="name">'
            f'{html.escape(a.name)}</div>' + "".join(f'<div class="line">{html.escape(x)}</div>' for x in lines)
            + "</div></div>")
    return page([cell] * a.count, "Wizytówki", w, h, 2, 5, 0, qr, 0, 0, outline=True, margins=(10, 15))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="dom_labels", description="Naklejki QR dla miejsc z dom.py i wizytówki z vCard.")
    sub = p.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("labels", help="naklejki z kodami miejsc")
    x.add_argument("codes", nargs="*", help="D001 D004 ... (albo --where / --all)")
    x.add_argument("--where", help="wszystkie miejsca z kodem w tym miejscu (z nim samym)")
    x.add_argument("--assign", action="store_true", help="z --where: najpierw nadaj brakujące kody (dom code --sub)")
    x.add_argument("--all", action="store_true")
    x.add_argument("--size", default="70x37", help="naklejka w mm, SZERxWYS (domyślnie arkusz A4 3x8: 70x37)")
    x.add_argument("--cols", type=int, default=3)
    x.add_argument("--rows", type=int, default=8)
    x.add_argument("--gap", type=float, default=0)
    x.add_argument("--margin-top", type=float, default=0.5)
    x.add_argument("--margin-left", type=float, default=0)
    x.add_argument("--copies", type=int, default=1)
    x.add_argument("--outline", action="store_true", help="przerywana ramka do cięcia (zwykły papier)")
    x.add_argument("--base", default=DEFAULT_BASE, help="adres strony skanu (dom_web.py)")
    x.add_argument("--out", default="-")
    x = sub.add_parser("card", help="wizytówki 85x55 mm z kodem vCard (A4, 10 sztuk)")
    x.add_argument("--name", required=True)
    x.add_argument("--phone")
    x.add_argument("--email")
    x.add_argument("--url")
    x.add_argument("--org")
    x.add_argument("--title")
    x.add_argument("--count", type=int, default=10)
    x.add_argument("--out", default="-")
    if argv is None:
        argv = sys.argv[1:]
    # dom.py's --db/DOM_DB select the database; pass --db through
    a, rest = p.parse_known_args(argv)
    if rest:
        if len(rest) == 2 and rest[0] == "--db":
            os.environ["DOM_DB"] = rest[1]
        else:
            p.error("nieznane argumenty: " + " ".join(rest))
    out = cmd_labels(a) if a.cmd == "labels" else cmd_card(a)
    if a.out == "-":
        sys.stdout.write(out)
    else:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(out)
        print(f"Zapisałem {a.out}. Drukuj w przeglądarce w skali 100% (bez dopasowania do strony).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
