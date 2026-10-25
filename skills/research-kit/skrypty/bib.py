#!/usr/bin/env python3
"""Baza bibliografii research-kit: pamięć każdego linku, który agent otworzył albo ocenił.

Bez tokenów: wszystko liczy ten skrypt (biblioteka standardowa), model dostaje tylko werdykt.

    bib.py ocen URL [URL...] [--siec] [--json]     # warto otwierać? otworz | pomin | uzyj-notatki | sprawdz-ponownie
    bib.py wizyta URL [--tytul T] [--tresc-plik F] [--narzedzie web_extract]   # zapis otwarcia (robią to haki)
    bib.py ocena URL --werdykt uzyteczne|neutralne|odrzucone [--powod P] [--notatka N] [--temat T] [--przebieg ID]
    bib.py historia URL                            # wszystko, co wiemy o linku
    bib.py decyzja dodaj ID --tytul T [--link L] [--klasa zwykla] (--zrodla URL... | --z-raportu raport.md)
    bib.py decyzja lista [--status aktualna]       # decyzje i ich źródła
    bib.py decyzja status ID aktualna|do-przegladu|nieaktualna|zamknieta [--powod P]
    bib.py sprawdz-decyzje [--json] [--limit 40]   # źródła decyzji, którym minął czas klasy; pusto = bez zmian
    bib.py rejestr --przebieg ID [-o zrodla.json]  # rejestr źródeł przebiegu research-kit (krok 4)
    bib.py statystyki

Baza: katalog z dziennikami zdarzeń `zdarzenia/<pisarz>.jsonl` (każda maszyna i sesja pisze do swojego pliku,
więc kopie z prod i z wątków Claude łączy się zwykłym kopiowaniem plików). Położenie: --baza, zmienna BIB_DIR,
albo ~/.hermes/bibliografia (gdy jest ~/.hermes), albo ~/.bibliografia.

Klasy zmienności (jak często sprawdzać źródła decyzji), zasada Filipa z 2026-10-24:
na-zywo 15 min (sytuacja dynamiczna, np. pożar), krytyczna 60 min (sytuacje krytyczne i awaryjne),
ceny 1 dzień, news 1 dzień, zwykla 7 dni, kod 30 dni.
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import html
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

KLASY_MIN = {"na-zywo": 15, "krytyczna": 60, "ceny": 1440, "news": 1440, "zwykla": 7 * 1440, "kod": 30 * 1440}
WERDYKTY = ("uzyteczne", "neutralne", "odrzucone")
STATUSY = ("aktualna", "do-przegladu", "nieaktualna", "zamknieta")
WYMUS = "bib-wymus"  # fragment #bib-wymus w URL omija blokadę odrzuconego linku

# Odrzucone wracają do sprawdzenia bez sieci po tym czasie (z siecią: gdy strona się zmieniła).
PONOW_ODRZUCONE_DNI = 180
# Notatka z użytecznego źródła wystarcza, jeśli ocena jest młodsza niż świeżość jego klasy.
# HTTP: krótki limit, żeby haki nie spowalniały agenta; 2 MB wystarczy na hash treści strony.
TIMEOUT_S = 8
MAX_POBRANIE = 2 * 1024 * 1024
UA = "Mozilla/5.0 (X11; Linux x86_64) research-kit-bib/1.0"

ZAUFANE_KONCOWKI = (".gov.pl", ".gov", ".edu", ".edu.pl", ".europa.eu", ".int")
ZAUFANE_DOMENY = {"github.com", "docs.python.org", "arxiv.org", "wikipedia.org", "who.int", "isap.sejm.gov.pl",
                  "uokik.gov.pl", "nfz.gov.pl", "knf.gov.pl", "ceneo.pl", "rtings.com", "anthropic.com"}
# Wzorce farm treści SEO i agregatorów bez własnej wiedzy (obniżają punkty, nie blokują).
PODEJRZANE = re.compile(r"(top-?\d+-best|best-\d+|-vs-.*-vs-|coupon|promo-?code|review-?site|listicle)", re.I)
SMIECI_QS = re.compile(r"^(utm_.*|fbclid|gclid|dclid|msclkid|mc_[ce]id|ref|ref_src|igshid|_hs.*|yclid|spm)$", re.I)


# ---------------------------------------------------------------- narzędzia
def teraz():
    return dt.datetime.now(dt.timezone.utc)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def z_iso(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) if s else None


def normalizuj(url):
    """Jeden klucz dla tej samej strony: bez fragmentu, śmieciowych parametrów, www i końcowego ukośnika."""
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    port = f":{p.port}" if p.port and p.port not in (80, 443) else ""
    sciezka = re.sub(r"/+$", "", p.path) or ""
    qs = urlencode(sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not SMIECI_QS.match(k)))
    return urlunsplit(("https", host + port, sciezka, qs, ""))


def domena(url):
    return urlsplit(normalizuj(url)).hostname or ""


def hash_tresci(tekst):
    """Hash samego tekstu (bez tagów, skryptów, liczb typu znaczniki czasu), żeby reklamy i zegary nie dawały zmian."""
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", tekst)
    t = html.unescape(re.sub(r"(?s)<[^>]+>", " ", t))
    t = re.sub(r"\b\d{1,2}:\d{2}(:\d{2})?\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return hashlib.sha256(t.encode("utf-8", "ignore")).hexdigest()[:20]


def katalog_bazy(arg=None):
    if arg:
        return Path(arg).expanduser()
    if os.environ.get("BIB_DIR"):
        return Path(os.environ["BIB_DIR"]).expanduser()
    hermes = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
    return hermes / "bibliografia" if hermes.is_dir() else Path("~/.bibliografia").expanduser()


def pisarz():
    w = os.environ.get("BIB_WRITER") or socket.gethostname() or "host"
    return re.sub(r"[^A-Za-z0-9._-]", "_", w)[:60]


# ---------------------------------------------------------------- baza
class Baza:
    def __init__(self, katalog):
        self.katalog = Path(katalog)
        self.zdarzenia = self.katalog / "zdarzenia"
        self.urls = {}
        self.decyzje = {}
        self._wczytaj()

    def _wczytaj(self):
        if not self.zdarzenia.is_dir():
            return
        wszystkie = []
        for f in sorted(self.zdarzenia.glob("*.jsonl")):
            with open(f, encoding="utf-8") as fh:
                for linia in fh:
                    try:
                        wszystkie.append(json.loads(linia))
                    except ValueError:
                        continue  # urwana linia po awarii: pomijamy, reszta dziennika jest cała
        wszystkie.sort(key=lambda z: z.get("t", ""))
        for z in wszystkie:
            self._zastosuj(z)

    def _url(self, url):
        return self.urls.setdefault(url, dict(url=url, pierwsza=None, wizyty=0, ostatnia_wizyta=None, hash=None,
                                              etag=None, lm=None, tytul="", werdykt=None, powod="", notatka="",
                                              data_oceny=None, hash_oceny=None, tematy=[], decyzje=[],
                                              ostatnie_sprawdzenie=None, http=None))

    def _zastosuj(self, z):
        typ, t = z.get("typ"), z.get("t")
        if typ in ("wizyta", "ocena", "sprawdzenie", "zrodlo_decyzji") and z.get("url"):
            u = self._url(z["url"])
            u["pierwsza"] = u["pierwsza"] or t
        if typ == "wizyta":
            u["wizyty"] += 1
            u["ostatnia_wizyta"] = t
            for k in ("hash", "etag", "lm"):
                u[k] = z.get(k) or u[k]
            u["tytul"] = z.get("tytul") or u["tytul"]
        elif typ == "ocena":
            u.update(werdykt=z["werdykt"], powod=z.get("powod", ""), notatka=z.get("notatka") or u["notatka"],
                     data_oceny=t, hash_oceny=u["hash"])
            if z.get("temat") and z["temat"] not in u["tematy"]:
                u["tematy"].append(z["temat"])
            if z.get("przebieg"):
                u.setdefault("przebiegi", [])
                if z["przebieg"] not in u["przebiegi"]:
                    u["przebiegi"].append(z["przebieg"])
        elif typ == "sprawdzenie":
            u["ostatnie_sprawdzenie"] = t
            u["http"] = z.get("http")
            for k in ("hash", "etag", "lm"):
                u[k] = z.get(k) or u[k]
        elif typ == "decyzja":
            d = self.decyzje.setdefault(z["id"], dict(id=z["id"], zrodla={}, status="aktualna", historia=[]))
            d.update({k: z[k] for k in ("tytul", "link", "klasa") if z.get(k)})
            d.setdefault("utworzona", t)
        elif typ == "zrodlo_decyzji":
            d = self.decyzje.get(z["id"])
            if d is not None:
                d["zrodla"][z["url"]] = dict(hash=z.get("hash"), etag=z.get("etag"), lm=z.get("lm"), od=t)
                if z["id"] not in u["decyzje"]:
                    u["decyzje"].append(z["id"])
        elif typ == "decyzja_status":
            d = self.decyzje.get(z["id"])
            if d is not None:
                d["status"] = z["status"]
                d["historia"].append(dict(t=t, status=z["status"], powod=z.get("powod", "")))
        elif typ == "zrodlo_zmiana":
            d = self.decyzje.get(z["id"])
            if d is not None and z["url"] in d["zrodla"]:
                d["zrodla"][z["url"]].update(hash=z.get("hash"), etag=z.get("etag"), lm=z.get("lm"))

    def zapisz(self, **zdarzenie):
        zdarzenie = {"t": iso(teraz()), "w": pisarz(), **{k: v for k, v in zdarzenie.items() if v not in (None, "")}}
        self.zdarzenia.mkdir(parents=True, exist_ok=True)
        plik = self.zdarzenia / f"{pisarz()}.jsonl"
        linia = json.dumps(zdarzenie, ensure_ascii=False) + "\n"
        with open(plik, "a", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            fh.write(linia)
            fh.flush()
            fcntl.flock(fh, fcntl.LOCK_UN)
        self._zastosuj(zdarzenie)
        return zdarzenie

    def statystyki_domeny(self, dom):
        s = dict(uzyteczne=0, neutralne=0, odrzucone=0)
        for u in self.urls.values():
            if u["werdykt"] and domena(u["url"]) == dom:
                s[u["werdykt"]] += 1
        return s


# ---------------------------------------------------------------- sieć (beztokenowe sprawdzenie zmian)
def sprawdz_siec(url, etag=None, lm=None):
    """Zwraca dict(http, hash, etag, lm, zmiana_wg_naglowkow). Najpierw warunkowe GET (304 = bez zmian)."""
    naglowki = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
    if etag:
        naglowki["If-None-Match"] = etag
    if lm:
        naglowki["If-Modified-Since"] = lm
    req = urllib.request.Request(url, headers=naglowki)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            dane = r.read(MAX_POBRANIE)
            kod = r.headers.get_content_charset() or "utf-8"
            return dict(http=r.status, hash=hash_tresci(dane.decode(kod, "ignore")),
                        etag=r.headers.get("ETag"), lm=r.headers.get("Last-Modified"))
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return dict(http=304, hash=None, etag=etag, lm=lm)
        return dict(http=e.code, hash=None, etag=None, lm=None)
    except Exception as e:  # sieć, DNS, TLS, timeout: nie wiemy, nie zgadujemy
        return dict(http=0, hash=None, etag=None, lm=None, blad=type(e).__name__)


def zmienione(stan, wynik):
    """True/False/None (nie wiadomo) względem zapamiętanego stanu dict(hash, etag, lm)."""
    if wynik["http"] == 304:
        return False
    if wynik["http"] in (404, 410):
        return True
    if not wynik.get("hash"):
        return None
    if stan.get("hash"):
        return wynik["hash"] != stan["hash"]
    if stan.get("etag") and wynik.get("etag"):
        return wynik["etag"] != stan["etag"]
    return None


# ---------------------------------------------------------------- ocena „warto otwierać?”
def klasa_url(url):
    d = domena(url)
    if d.endswith(("github.com", "gitlab.com", "pypi.org", "npmjs.com")) or "/docs" in url:
        return "kod"
    if any(k in d for k in ("ceneo", "allegro", "skapiec", "pepper", "booking", "skyscanner", "x-kom", "mediaexpert")):
        return "ceny"
    if any(k in d for k in ("news", "wiadomosci", "tvn24", "onet", "wp.pl", "trojmiasto", "rmf24", "pap.pl")):
        return "news"
    return "zwykla"


def punkty(baza, url):
    d = domena(url)
    p = 50
    if d.endswith(ZAUFANE_KONCOWKI) or any(d == z or d.endswith("." + z) for z in ZAUFANE_DOMENY):
        p += 20
    if PODEJRZANE.search(url):
        p -= 20
    s = baza.statystyki_domeny(d)
    ocen = sum(s.values())
    if ocen:
        p += round(30 * (s["uzyteczne"] - s["odrzucone"]) / ocen)
    return max(0, min(100, p))


def ocen(baza, url, siec=False, zapisuj=True):
    wymus = WYMUS in url
    n = normalizuj(url)
    u = baza.urls.get(n)
    wynik = dict(url=n, punkty=punkty(baza, n), klasa=klasa_url(n))
    if wymus:
        return dict(wynik, decyzja="otworz", powod="wymuszone (#bib-wymus)")
    if not u:
        return dict(wynik, decyzja="otworz", powod="nowe źródło")
    wynik.update(werdykt=u["werdykt"], data_oceny=u["data_oceny"], wizyty=u["wizyty"],
                 ostatnio=u["ostatnia_wizyta"] or u["data_oceny"], powod_oceny=u["powod"])
    wiek_oceny = (teraz() - z_iso(u["data_oceny"])) if u["data_oceny"] else None

    if u["werdykt"] == "odrzucone":
        if siec:
            r = sprawdz_siec(n, u["etag"], u["lm"])
            if zapisuj and r["http"]:
                baza.zapisz(typ="sprawdzenie", url=n, http=r["http"], hash=r.get("hash"), etag=r.get("etag"), lm=r.get("lm"))
            zm = zmienione(dict(hash=u["hash_oceny"], etag=u["etag"], lm=u["lm"]), r)
            if zm:
                return dict(wynik, decyzja="sprawdz-ponownie", powod="odrzucone, ale strona zmieniła się od oceny")
            if zm is None and r["http"] == 0:
                return dict(wynik, decyzja="pomin", powod=f"odrzucone ({u['powod'] or 'bez powodu'}); nie udało się sprawdzić zmian")
        elif wiek_oceny and wiek_oceny.days >= PONOW_ODRZUCONE_DNI:
            return dict(wynik, decyzja="sprawdz-ponownie", powod=f"odrzucone ponad {PONOW_ODRZUCONE_DNI} dni temu")
        return dict(wynik, decyzja="pomin", powod=f"odrzucone {u['data_oceny'][:10]}: {u['powod'] or 'bez powodu'}")

    if u["werdykt"] == "uzyteczne":
        swiezosc = dt.timedelta(minutes=KLASY_MIN[wynik["klasa"]])
        if u["notatka"] and wiek_oceny is not None and wiek_oceny < swiezosc:
            return dict(wynik, decyzja="uzyj-notatki", notatka=u["notatka"],
                        powod=f"użyteczne, ocenione {u['data_oceny'][:10]}, notatka świeża dla klasy {wynik['klasa']}")
        return dict(wynik, decyzja="sprawdz-ponownie", powod=f"użyteczne, ale starsze niż świeżość klasy {wynik['klasa']}")

    if u["werdykt"] == "neutralne":
        return dict(wynik, decyzja="otworz", powod=f"wcześniej neutralne ({u['data_oceny'][:10]}), otwórz tylko gdy brak lepszych")
    return dict(wynik, decyzja="otworz", powod=f"widziane {u['wizyty']}×, bez oceny")


# ---------------------------------------------------------------- decyzje
def urls_z_raportu(sciezka):
    tekst = Path(sciezka).read_text(encoding="utf-8")
    m = re.search(r"(?ms)^##\s+Źródła\s*$(.*?)(^##\s|\Z)", tekst)
    czesc = m.group(1) if m else tekst
    return sorted({normalizuj(u.rstrip(").,>]")) for u in re.findall(r"https?://[^\s)\]>\"']+", czesc)})


def sprawdz_decyzje(baza, limit=40):
    """Źródła aktualnych decyzji, którym minął czas klasy: pobierz, porównaj, oznacz decyzję do przeglądu."""
    zmiany, sprawdzone = [], 0
    for d in sorted(baza.decyzje.values(), key=lambda d: KLASY_MIN.get(d.get("klasa", "zwykla"), 10080)):
        if d["status"] != "aktualna":
            continue
        okres = dt.timedelta(minutes=KLASY_MIN.get(d.get("klasa", "zwykla"), 10080))
        zmienione_zrodla = []
        for url, stan in d["zrodla"].items():
            u = baza.urls.get(url, {})
            ostatnio = z_iso(u.get("ostatnie_sprawdzenie")) or z_iso(stan.get("od"))
            if ostatnio and teraz() - ostatnio < okres:
                continue
            if sprawdzone >= limit:
                break
            sprawdzone += 1
            r = sprawdz_siec(url, stan.get("etag"), stan.get("lm"))
            baza.zapisz(typ="sprawdzenie", url=url, http=r["http"], hash=r.get("hash"), etag=r.get("etag"), lm=r.get("lm"))
            if zmienione(stan, r):
                powod = "zniknęło (HTTP %d)" % r["http"] if r["http"] in (404, 410) else "treść się zmieniła"
                zmienione_zrodla.append(dict(url=url, powod=powod))
                baza.zapisz(typ="zrodlo_zmiana", id=d["id"], url=url, hash=r.get("hash"), etag=r.get("etag"), lm=r.get("lm"))
            elif not stan.get("hash") and r.get("hash"):
                baza.zapisz(typ="zrodlo_zmiana", id=d["id"], url=url, hash=r["hash"], etag=r.get("etag"), lm=r.get("lm"))
        if zmienione_zrodla:
            baza.zapisz(typ="decyzja_status", id=d["id"], status="do-przegladu",
                        powod="; ".join(f"{z['url']}: {z['powod']}" for z in zmienione_zrodla)[:500])
            zmiany.append(dict(id=d["id"], tytul=d.get("tytul", ""), link=d.get("link", ""),
                               klasa=d.get("klasa", "zwykla"), zrodla=zmienione_zrodla))
    return zmiany, sprawdzone


# ---------------------------------------------------------------- CLI
def wypisz(obj, jako_json):
    if jako_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
        return
    for r in obj if isinstance(obj, list) else [obj]:
        print(f"{r['decyzja']:<17} {r['punkty']:>3}  {r['url']}  ({r['powod']})")
        if r.get("notatka"):
            print(f"{'':<22}notatka: {r['notatka']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Baza bibliografii research-kit (beztokenowa).")
    ap.add_argument("--baza", help="katalog bazy (domyślnie BIB_DIR, ~/.hermes/bibliografia albo ~/.bibliografia)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ocen", help="czy warto otwierać linki")
    s.add_argument("urls", nargs="+")
    s.add_argument("--siec", action="store_true", help="dla odrzuconych sprawdź przez HTTP, czy strona się zmieniła")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("wizyta", help="zapisz otwarcie linku")
    s.add_argument("url")
    s.add_argument("--tytul")
    s.add_argument("--tresc-plik", help="plik z treścią strony (do hasha zmian)")
    s.add_argument("--narzedzie")

    s = sub.add_parser("ocena", help="zapisz werdykt o źródle")
    s.add_argument("url")
    s.add_argument("--werdykt", required=True, choices=WERDYKTY)
    s.add_argument("--powod")
    s.add_argument("--notatka", help="1–3 zdania do ponownego użycia bez otwierania strony")
    s.add_argument("--temat")
    s.add_argument("--przebieg", help="ID przebiegu research-kit (nazwa katalogu)")

    s = sub.add_parser("historia")
    s.add_argument("url")

    s = sub.add_parser("decyzja", help="śledzenie źródeł decyzji")
    dsub = s.add_subparsers(dest="dcmd", required=True)
    d = dsub.add_parser("dodaj")
    d.add_argument("id")
    d.add_argument("--tytul", required=True)
    d.add_argument("--link")
    d.add_argument("--klasa", default="zwykla", choices=sorted(KLASY_MIN))
    g = d.add_mutually_exclusive_group(required=True)
    g.add_argument("--zrodla", nargs="+")
    g.add_argument("--z-raportu", help="raport.md: bierze linki z sekcji Źródła")
    d.add_argument("--bez-sieci", action="store_true", help="nie pobieraj stanu bazowego teraz")
    d = dsub.add_parser("lista")
    d.add_argument("--status", choices=STATUSY)
    d.add_argument("--json", action="store_true")
    d = dsub.add_parser("status")
    d.add_argument("id")
    d.add_argument("status", choices=STATUSY)
    d.add_argument("--powod")

    s = sub.add_parser("sprawdz-decyzje", help="sprawdź źródła decyzji, którym minął czas klasy")
    s.add_argument("--json", action="store_true")
    s.add_argument("--limit", type=int, default=40, help="max źródeł na jedno uruchomienie")

    s = sub.add_parser("rejestr", help="rejestr źródeł przebiegu (zrodla.json)")
    s.add_argument("--przebieg", required=True)
    s.add_argument("-o", "--wyjscie")

    sub.add_parser("statystyki")

    a = ap.parse_args(argv)
    baza = Baza(katalog_bazy(a.baza))

    if a.cmd == "ocen":
        wypisz([ocen(baza, u, siec=a.siec) for u in a.urls], a.json)
    elif a.cmd == "wizyta":
        h = None
        if a.tresc_plik:
            h = hash_tresci(Path(a.tresc_plik).read_text(encoding="utf-8", errors="ignore"))
        baza.zapisz(typ="wizyta", url=normalizuj(a.url), tytul=(a.tytul or "")[:200], hash=h, narzedzie=a.narzedzie)
    elif a.cmd == "ocena":
        baza.zapisz(typ="ocena", url=normalizuj(a.url), werdykt=a.werdykt, powod=(a.powod or "")[:300],
                    notatka=(a.notatka or "")[:600], temat=a.temat, przebieg=a.przebieg)
        print(f"zapisane: {a.werdykt} {normalizuj(a.url)}")
    elif a.cmd == "historia":
        u = baza.urls.get(normalizuj(a.url))
        print(json.dumps(u or {"url": normalizuj(a.url), "znane": False}, ensure_ascii=False, indent=2))
    elif a.cmd == "decyzja" and a.dcmd == "dodaj":
        zrodla = a.zrodla and [normalizuj(u) for u in a.zrodla] or urls_z_raportu(a.z_raportu)
        if not zrodla:
            print("brak źródeł: decyzja bez źródeł nie ma czego śledzić", file=sys.stderr)
            return 2
        baza.zapisz(typ="decyzja", id=a.id, tytul=a.tytul, link=a.link, klasa=a.klasa)
        for url in zrodla:
            r = {} if a.bez_sieci else sprawdz_siec(url)
            if r.get("http"):
                baza.zapisz(typ="sprawdzenie", url=url, http=r["http"], hash=r.get("hash"), etag=r.get("etag"), lm=r.get("lm"))
            baza.zapisz(typ="zrodlo_decyzji", id=a.id, url=url, hash=r.get("hash"), etag=r.get("etag"), lm=r.get("lm"))
        print(f"decyzja {a.id}: {len(zrodla)} źródeł, klasa {a.klasa} (co {KLASY_MIN[a.klasa]} min)")
    elif a.cmd == "decyzja" and a.dcmd == "lista":
        lista = [d for d in baza.decyzje.values() if not a.status or d["status"] == a.status]
        if a.json:
            print(json.dumps(lista, ensure_ascii=False, indent=2))
        for d in [] if a.json else lista:
            print(f"{d['id']:<14} {d['status']:<13} {d.get('klasa', 'zwykla'):<9} {len(d['zrodla']):>3} źr.  {d.get('tytul', '')}")
    elif a.cmd == "decyzja" and a.dcmd == "status":
        if a.id not in baza.decyzje:
            print(f"nie ma decyzji {a.id}", file=sys.stderr)
            return 2
        baza.zapisz(typ="decyzja_status", id=a.id, status=a.status, powod=a.powod)
    elif a.cmd == "sprawdz-decyzje":
        zmiany, _ = sprawdz_decyzje(baza, a.limit)
        if a.json:
            print(json.dumps(zmiany, ensure_ascii=False, indent=2))
        else:  # pusto = cicho (cron no_agent Hermesa nic nie wysyła)
            for z in zmiany:
                print(f"⚠️ Decyzja {z['id']} „{z['tytul']}” do przeglądu: zmieniły się źródła ({z['klasa']}).")
                for s_ in z["zrodla"]:
                    print(f"   • {s_['url']}: {s_['powod']}")
                if z["link"]:
                    print(f"   Decyzja: {z['link']}")
    elif a.cmd == "rejestr":
        lista = [dict(url=u["url"], tytul=u["tytul"], werdykt=u["werdykt"], powod=u["powod"],
                      data=(u["data_oceny"] or "")[:10], domena=domena(u["url"]))
                 for u in baza.urls.values() if a.przebieg in u.get("przebiegi", [])]
        wynik = dict(przebieg=a.przebieg, zatwierdzone=[z for z in lista if z["werdykt"] != "odrzucone"],
                     odrzucone=[z for z in lista if z["werdykt"] == "odrzucone"])
        tekst = json.dumps(wynik, ensure_ascii=False, indent=2)
        Path(a.wyjscie).write_text(tekst + "\n", encoding="utf-8") if a.wyjscie else print(tekst)
    elif a.cmd == "statystyki":
        w = {k: sum(1 for u in baza.urls.values() if u["werdykt"] == k) for k in WERDYKTY}
        print(json.dumps(dict(baza=str(baza.katalog), linki=len(baza.urls), werdykty=w,
                              bez_oceny=sum(1 for u in baza.urls.values() if not u["werdykt"]),
                              decyzje={s_: sum(1 for d in baza.decyzje.values() if d["status"] == s_) for s_ in STATUSY}),
                         ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
