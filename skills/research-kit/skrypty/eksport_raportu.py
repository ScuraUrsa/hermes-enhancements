#!/usr/bin/env python3
"""Eksport raportu research-kit (standard K80) do formatów dostarczenia.

    python3 eksport_raportu.py matrix raport.md --link URL [--json]   # krótka wiadomość (≤ 1000 znaków)
    python3 eksport_raportu.py notion raport.md                      # JSON: tytuł, właściwości, treść md
    python3 eksport_raportu.py pdf raport.md -o raport.pdf            # pandoc → HTML → Chromium (A4)

Źródłem prawdy jest zawsze raport.md, który przeszedł waliduj_raport.py. Tylko biblioteka standardowa
(PDF wymaga pandoc i Chromium albo weasyprint).
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from waliduj_raport import RE_CYTAT, RE_LINK, bez_kodu_i_komentarzy, norm, podziel, pozycje_listy  # noqa: E402

LIMIT_MATRIX = 1000
CSS = """@page { size: A4; margin: 18mm 16mm; }
body { font: 10.5pt/1.45 "DejaVu Sans", Arial, sans-serif; color: #111; }
h1 { font-size: 17pt; margin: 0 0 4mm; } h2 { font-size: 13pt; margin: 6mm 0 2mm; border-bottom: 1px solid #ccc; }
h3 { font-size: 11pt; } table { border-collapse: collapse; width: 100%; font-size: 9pt; margin: 2mm 0; }
th, td { border: 1px solid #bbb; padding: 3px 5px; vertical-align: top; } th { background: #f0f0f0; }
a { color: #0645ad; text-decoration: none; } h2#w-skrócie + p { background: #f6f8fa; padding: 3mm; }"""


def wczytaj(sciezka):
    text = Path(sciezka).read_text(encoding="utf-8")
    tytul, naglowek, sekcje = podziel(bez_kodu_i_komentarzy(text))
    meta = {}
    for l in naglowek:
        m = re.match(r"^\s*-\s+\*\*([^*:]+):\*\*\s*(.*)$", l)
        if m:
            meta[m.group(1).strip()] = m.group(2).strip()
    return text, tytul, meta, {norm(n): t for n, t in sekcje}


def matrix(sciezka, link=None):
    _, tytul, _, sek = wczytaj(sciezka)
    skrot = [l.strip() for l in sek.get(norm("W skrócie"), "").splitlines() if l.strip()]
    kroki = pozycje_listy(sek.get(norm("Kolejne kroki"), ""))[:3]

    def czysc(s):
        return re.sub(r"\s{2,}", " ", RE_CYTAT.sub("", s)).replace(" .", ".").strip()

    md = [f"**{tytul}**", ""] + [czysc(re.sub(r"^- ", "", l)) for l in skrot]
    if kroki:
        md += ["", "Kroki:"] + [f"{i}. " + czysc(re.sub(r"^(?:[-*+]|\d+[.)])\s*(?:\[[ x]\]\s*)?", "", k))
                                for i, k in enumerate(kroki, 1)]
    if link:
        md += ["", f"Pełny raport: [{tytul}]({link})"]
    body_md = "\n".join(md)
    plain = RE_LINK.sub(lambda m: f"{m.group(1)} ({m.group(2)})", body_md).replace("**", "")

    def do_html(linia):
        h = html.escape(linia, quote=False)
        h = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", h)
        return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>', h)
    formatted = "<br>".join(do_html(l) for l in md)
    if len(plain) > LIMIT_MATRIX:
        print(f"UWAGA: wiadomość ma {len(plain)} znaków (limit standardu {LIMIT_MATRIX}); skróć „W skrócie”.",
              file=sys.stderr)
    return dict(msgtype="m.text", body=plain, format="org.matrix.custom.html", formatted_body=formatted)


def notion(sciezka):
    text, tytul, meta, _ = wczytaj(sciezka)
    tresc = re.sub(r"<!--.*?-->\n?", "", text, flags=re.S)
    tresc = re.sub(r"^# .*\n", "", tresc, count=1).lstrip()
    pewnosc = re.search(r"\*\*Pewność:\*\*\s*(wysoka|średnia|niska)", text, re.I)
    wlasciwosci = {
        "Typ": meta.get("Typ"), "Tryb": meta.get("Tryb"), "Na dzień": meta.get("Na dzień"),
        "Status": meta.get("Status"), "Autor": meta.get("Autor"),
        "Pewność": pewnosc.group(1).lower() if pewnosc else None, "Zlecenie": meta.get("Zlecenie"),
    }
    dlugie = [a[:40] for a in re.split(r"\n\s*\n", tresc) if len(a) > 2000 and not a.lstrip().startswith("|")]
    return dict(tytul=tytul, wlasciwosci=wlasciwosci, tresc_md=tresc, akapity_ponad_2000_znakow=dlugie)


def pdf(sciezka, wyjscie):
    if not shutil.which("pandoc"):
        sys.exit("Brak pandoc. Zainstaluj (apt install pandoc) albo użyj LibreOffice/Stirling-PDF (K70).")
    _, tytul, _, _ = wczytaj(sciezka)
    with tempfile.TemporaryDirectory() as tmp:
        css = Path(tmp) / "raport.css"
        css.write_text(CSS, encoding="utf-8")
        strona = Path(tmp) / "raport.html"
        subprocess.run(["pandoc", str(sciezka), "-f", "gfm", "-s", "--embed-resources", "-c", str(css),
                        "--metadata", f"title={tytul}", "-V", "lang=pl", "-o", str(strona)], check=True)
        # pandoc dodaje własny tytuł, a raport ma już „# …”
        h = strona.read_text(encoding="utf-8")
        strona.write_text(re.sub(r'<header id="title-block-header">.*?</header>', "", h, flags=re.S), encoding="utf-8")
        chrom = next((c for c in [os.environ.get("CHROMIUM"), shutil.which("chromium"), shutil.which("chromium-browser"),
                                  shutil.which("google-chrome"),
                                  *sorted(map(str, Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome")))]
                      if c and Path(c).exists()), None)
        if chrom:
            subprocess.run([chrom, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                            f"--print-to-pdf={Path(wyjscie).resolve()}", strona.as_uri()],
                           check=True, capture_output=True)
        elif shutil.which("weasyprint"):
            subprocess.run(["weasyprint", str(strona), str(wyjscie)], check=True)
        else:
            sys.exit("Brak Chromium i weasyprint; ustaw zmienną CHROMIUM na ścieżkę przeglądarki.")
    print(f"PDF: {wyjscie}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Eksport raportu research-kit.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("matrix")
    m.add_argument("raport")
    m.add_argument("--link", help="link do pełnego raportu (Notion albo plik)")
    m.add_argument("--json", action="store_true", help="treść zdarzenia m.room.message")
    n = sub.add_parser("notion")
    n.add_argument("raport")
    p = sub.add_parser("pdf")
    p.add_argument("raport")
    p.add_argument("-o", "--wyjscie", default=None)
    a = ap.parse_args(argv)

    if a.cmd == "matrix":
        tresc = matrix(a.raport, a.link)
        print(json.dumps(tresc, ensure_ascii=False, indent=2) if a.json else tresc["body"])
    elif a.cmd == "notion":
        print(json.dumps(notion(a.raport), ensure_ascii=False, indent=2))
    else:
        pdf(a.raport, a.wyjscie or str(Path(a.raport).with_suffix(".pdf")))


if __name__ == "__main__":
    main()
