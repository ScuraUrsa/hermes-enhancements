#!/usr/bin/env python3
"""Walidator raportu research-kit (standard raportów K80 v1).

    python3 waliduj_raport.py raport.md                 # albo katalog przebiegu z raport.md (i zrodla.json)
    python3 waliduj_raport.py raport.md --json          # wynik maszynowy dla Hermesa
    python3 waliduj_raport.py raport.md --sprawdz-linki # dodatkowo sprawdza każdy link przez HTTP
    python3 waliduj_raport.py raport.md --typy-dir ../typy   # pokrycie pól wg pliku typu
    python3 waliduj_raport.py raport.md --dzis 2026-10-23    # data odniesienia (domyślnie dziś)

Kod wyjścia: 0 brak błędów (uwagi są dozwolone), 1 są błędy, 2 nie da się przeczytać pliku.
Zasady opisuje szablony/standard-raportu.md. Tylko biblioteka standardowa.
"""
import argparse
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

SEKCJE = ["W skrócie", "Założenia", "Porównanie", "Szczegóły", "Ryzyka", "Kolejne kroki",
          "Pewność i metoda", "Pokrycie pól", "Źródła"]
SEKCJE_OPCJONALNE = ["Załączniki"]
NAGLOWEK = ["Typ", "Tryb", "Na dzień", "Zlecenie", "Autor", "Status"]
STATUSY = {"szkic", "gotowy", "nieaktualny"}

# min. źródeł, min. domen, max słów treści (bez Pokrycia i Źródeł), min. wierszy porównania
TRYBY = {
    "szybki": dict(zrodla=3, domeny=2, slowa=800, wiersze=1),
    "standard": dict(zrodla=8, domeny=4, slowa=2500, wiersze=2),
    "głęboki": dict(zrodla=15, domeny=6, slowa=6000, wiersze=3),
}

# swiezosc_cen: max wiek (dni) daty sprawdzenia źródeł typu sklep/cennik; swiezosc: wiek publikacji
# pozostałych (uwaga); oficjalne: min. udział źródeł oficjalnych; wiersze: min. wierszy porównania;
# kolumny: fragmenty nazw kolumn wymagane w tabeli porównania
TYPY = {
    "wiedza": dict(swiezosc_cen=None, swiezosc=1095, oficjalne=0.3, wiersze=1, kolumny=[]),
    "decyzja-techniczna": dict(swiezosc_cen=30, swiezosc=365, oficjalne=0.3, wiersze=2, kolumny=["koszt"]),
    "zakupy": dict(swiezosc_cen=7, swiezosc=365, oficjalne=0.0, wiersze=3, kolumny=["cena"]),
    "wycieczka": dict(swiezosc_cen=3, swiezosc=365, oficjalne=0.0, wiersze=2, kolumny=["koszt"]),
    "randka": dict(swiezosc_cen=7, swiezosc=365, oficjalne=0.0, wiersze=3, kolumny=["koszt"]),
    "osoba-firma": dict(swiezosc_cen=None, swiezosc=365, oficjalne=0.3, wiersze=1, kolumny=[]),
    "zdrowie-prawo-finanse": dict(swiezosc_cen=None, swiezosc=365, oficjalne=0.5, wiersze=1, kolumny=[]),
    "monitoring": dict(swiezosc_cen=7, swiezosc=30, oficjalne=0.0, wiersze=1, kolumny=[]),
}
TYPY_ZRODEL = {"oficjalne", "dokumentacja", "nauka", "sklep", "cennik", "test", "prasa", "forum", "inne"}
OFICJALNE = {"oficjalne", "dokumentacja", "nauka"}
CENOWE = {"sklep", "cennik"}

# Skala prawdopodobieństwa wg ICD 203 (kolejność: dłuższe frazy najpierw)
SKALA = [
    ("bardzo mało prawdopodobne", 5, 20), ("mało prawdopodobne", 20, 45), ("bardzo prawdopodobne", 80, 95),
    ("mniej więcej równe szanse", 45, 55), ("prawie wykluczone", 1, 5), ("prawie pewne", 95, 99),
    ("prawdopodobne", 55, 80),
]
RE_SKALA = re.compile(r"\b(?:bardzo |mało |bardzo mało )?prawdopodobn\w*|\bprawie (?:wykluczone|pewne|na pewno)\b"
                      r"|\bmniej więcej równe szanse\b|\d{1,3}\s?%", re.I)
RE_MGLISTE = re.compile(r"\b(chyba|raczej|zapewne|być może|niewykluczone|możliwe, że|pewnie|ewentualnie)\b", re.I)
POZIOMY = r"(wysoka|średnia|niska)"

RE_CYTAT = re.compile(r"(?<![\]\w])\[(\d+(?:\s*[,–-]\s*\d+)*)\](?!\()")
RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
RE_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")
RE_ZRODLO = re.compile(r"^- \[(\d+)\]\s+(.*)$")
RE_PLACEHOLDER = re.compile(r"<(?!https?://|!--|/?(?:br|b|i|u|sup|sub|details|summary)\b)[^<>\n]{2,120}>"
                            r"|\bTODO\b|\bXXX\b|\{\{")
RE_SEKRET = re.compile(r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_\w{20,}|sk-[A-Za-z0-9_-]{20,}|xox[bpa]-[\w-]{10,}"
                       r"|AKIA[0-9A-Z]{16})\b|\b(?:hasło|password|pin)\s*[:=]\s*\S+", re.I)
RE_IBAN = re.compile(r"\bPL\s?\d{2}(?:\s?\d{4}){6}\b")
RE_KARTA = re.compile(r"(?<!\d)\d{4}(?:[ -]?\d{4}){2,3}(?:[ -]?\d{1,3})?(?!\d)")
RE_PESEL = re.compile(r"(?<!\d)\d{11}(?!\d)")


class Wynik:
    def __init__(self):
        self.bledy, self.uwagi, self.stat = [], [], {}

    def blad(self, msg):
        self.bledy.append(msg)

    def uwaga(self, msg):
        self.uwagi.append(msg)


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"^\d+[.)]\s*", "", s.strip())).lower()


def data(s):
    try:
        return dt.date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def bez_kodu_i_komentarzy(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.sub(r"```.*?```", "", text, flags=re.S)


def podziel(text):
    """Zwraca (tytuł, linie nagłówka, [(nazwa sekcji, treść)])."""
    tytul, naglowek, sekcje, biezaca, bufor = None, [], [], None, []
    for linia in text.splitlines():
        if linia.startswith("# ") and tytul is None and biezaca is None:
            tytul = linia[2:].strip()
        elif linia.startswith("## "):
            if biezaca is not None:
                sekcje.append((biezaca, "\n".join(bufor)))
            biezaca, bufor = linia[3:].strip(), []
        elif biezaca is None:
            naglowek.append(linia)
        else:
            bufor.append(linia)
    if biezaca is not None:
        sekcje.append((biezaca, "\n".join(bufor)))
    return tytul, naglowek, sekcje


def pozycje_listy(tresc):
    return [l.strip() for l in tresc.splitlines() if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", l)]


def tabele(tresc):
    """Wszystkie tabele markdown: [(nagłówek, wiersze)]."""
    bloki, biezacy = [], []
    for l in tresc.splitlines() + [""]:
        if l.strip().startswith("|"):
            biezacy.append(l.strip())
        elif biezacy:
            bloki.append(biezacy)
            biezacy = []

    def komorki(l):
        l = l.replace("\\|", "\x00").strip().strip("|")
        return [c.strip().replace("\x00", "|") for c in l.split("|")]
    return [(komorki(b[0]), [komorki(l) for l in b[2:]])
            for b in bloki if len(b) >= 2 and re.match(r"^\|?\s*:?-{3,}", b[1])]


def tabela(tresc):
    """Pierwsza tabela markdown: (nagłówek, wiersze) albo (None, [])."""
    t = tabele(tresc)
    return t[0] if t else (None, [])


def klucz_pola(s):
    s = re.sub(r"\(.*?\)", "", s.replace("**", "").replace("`", ""))
    s = re.sub(r"[„”\"“]", "", s)
    return re.sub(r"\s+", " ", s).strip(" .:;,-").lower()


def to_samo_pole(a, b):
    a, b = klucz_pola(a), klucz_pola(b)
    return a == b or (min(len(a), len(b)) >= 8 and (a.startswith(b) or b.startswith(a)))


def numery(cytat):
    out = set()
    for czesc in re.split(r"\s*,\s*", cytat):
        if re.search(r"[–-]", czesc):
            a, b = [int(x) for x in re.split(r"\s*[–-]\s*", czesc)]
            out.update(range(a, b + 1))
        else:
            out.add(int(czesc))
    return out


def luhn(cyfry):
    suma = 0
    for i, c in enumerate(reversed(cyfry)):
        d = int(c)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        suma += d
    return suma % 10 == 0


def pesel_ok(s):
    wagi = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
    return (10 - sum(int(a) * w for a, w in zip(s, wagi)) % 10) % 10 == int(s[10])


def domena(url):
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def pola_typu(typy_dir, typ):
    plik = Path(typy_dir) / f"{typ}.md"
    if not plik.is_file():
        return None
    _, _, sekcje = podziel(plik.read_text(encoding="utf-8"))
    for nazwa, tresc in sekcje:
        if norm(nazwa).startswith("pola obowiązkowe"):
            pola = [w[0] for _, wiersze in tabele(tresc) for w in wiersze if w and w[0]]
            return [p for p in pola if not klucz_pola(p).startswith("opcjonalnie")]
    return None


def sprawdz_link(url, timeout=10):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0 research-kit/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        if e.code in (403, 405, 501):  # część serwerów nie obsługuje HEAD
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 research-kit/1"})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.status
            except urllib.error.HTTPError as e2:
                return e2.code
            except Exception:
                return None
        return e.code
    except Exception:
        return None


def waliduj(text, dzis=None, typy_dir=None, rejestr_urls=None, sprawdzaj_linki=False):
    w = Wynik()
    dzis = dzis or dt.date.today()
    czysty = bez_kodu_i_komentarzy(text)
    tytul, naglowek, sekcje = podziel(czysty)

    # 1. Tytuł i nagłówek
    if not tytul:
        w.blad("Brak tytułu (pierwsza linia „# …”).")
    meta = {}
    for l in naglowek:
        m = re.match(r"^\s*-\s+\*\*([^*:]+):\*\*\s*(.*)$", l)
        if m:
            meta[m.group(1).strip()] = m.group(2).strip()
    for k in NAGLOWEK:
        if not meta.get(k):
            w.blad(f"Nagłówek: brak pola „{k}”.")
    typ = meta.get("Typ", "").lower()
    tryb = meta.get("Tryb", "").lower().replace("gleboki", "głęboki")
    if typ and typ not in TYPY:
        w.blad(f"Nagłówek: nieznany typ „{typ}” (dozwolone: {', '.join(TYPY)}).")
    if tryb and tryb not in TRYBY:
        w.blad(f"Nagłówek: nieznany tryb „{tryb}” (dozwolone: {', '.join(TRYBY)}).")
    na_dzien = data(meta.get("Na dzień"))
    if meta.get("Na dzień") and not na_dzien:
        w.blad("Nagłówek: „Na dzień” nie jest datą RRRR-MM-DD.")
    if na_dzien and na_dzien > dzis:
        w.blad(f"Nagłówek: „Na dzień” {na_dzien} jest w przyszłości.")
    if meta.get("Status") and meta["Status"].lower() not in STATUSY:
        w.uwaga(f"Nagłówek: status „{meta['Status']}” spoza listy {sorted(STATUSY)}.")
    if meta.get("Zlecenie") and not RE_LINK.search(meta["Zlecenie"]):
        w.uwaga("Nagłówek: „Zlecenie” bez klikalnego linku.")
    pt = TYPY.get(typ, TYPY["wiedza"])
    pm = TRYBY.get(tryb, TRYBY["standard"])
    odniesienie = na_dzien or dzis

    # 2. Sekcje: komplet i kolejność
    nazwy = [norm(n) for n, _ in sekcje]
    wymagane = [norm(s) for s in SEKCJE]
    for s in SEKCJE:
        if norm(s) not in nazwy:
            w.blad(f"Brak sekcji „## {s}”.")
    obecne = [n for n in nazwy if n in wymagane]
    if obecne != sorted(obecne, key=wymagane.index):
        w.blad("Sekcje w złej kolejności; wymagana: " + " → ".join(SEKCJE) + ".")
    for n, _ in sekcje:
        if norm(n) not in wymagane and norm(n) not in [norm(x) for x in SEKCJE_OPCJONALNE]:
            w.uwaga(f"Nieznana sekcja „## {n}”: przenieś ją jako „###” do Szczegółów.")
    sek = {norm(n): t for n, t in sekcje}

    # 3. W skrócie (BLUF)
    skrot = sek.get(norm("W skrócie"), "")
    linie = [l for l in skrot.splitlines() if l.strip()]
    if skrot or norm("W skrócie") in sek:
        if len(linie) > 5:
            w.blad(f"„W skrócie” ma {len(linie)} linii (max 5).")
        if len(skrot.strip()) > 600:
            w.blad(f"„W skrócie” ma {len(skrot.strip())} znaków (max 600).")
        if not linie or not re.match(r"^(?:- )?\*\*(Rekomendacja|Odpowiedź|Decyzja):\*\*", linie[0].strip()):
            w.blad("„W skrócie”: pierwsza linia musi zaczynać się od „- **Rekomendacja:**”, „- **Odpowiedź:**” "
                   "albo „- **Decyzja:**”.")
        m = re.search(r"\*\*Pewność:\*\*\s*" + POZIOMY, skrot, re.I)
        if not m:
            w.blad("„W skrócie”: brak linii **Pewność:** wysoka | średnia | niska.")
        pewnosc_skrot = m.group(1).lower() if m else None
        if not RE_CYTAT.search(skrot) and not RE_LINK.search(skrot):
            w.uwaga("„W skrócie”: brak cytatu [n] ani linku przy odpowiedzi.")
    else:
        pewnosc_skrot = None

    # 4. Założenia
    if norm("Założenia") in sek and not pozycje_listy(sek[norm("Założenia")]):
        w.blad("„Założenia”: brak listy (jeśli nie ma, wpisz „- Brak założeń.”).")

    # 5. Porównanie
    if norm("Porównanie") in sek:
        nagl, wiersze = tabela(sek[norm("Porównanie")])
        min_w = max(pt["wiersze"], pm["wiersze"])
        if nagl is None:
            w.blad("„Porównanie”: brak tabeli markdown.")
        else:
            if len(wiersze) < min_w:
                w.blad(f"„Porównanie”: {len(wiersze)} wierszy, wymagane min. {min_w} (typ {typ or '?'}, tryb {tryb or '?'}).")
            for i, r in enumerate(wiersze, 1):
                if len(r) != len(nagl):
                    w.blad(f"„Porównanie”: wiersz {i} ma {len(r)} komórek, nagłówek {len(nagl)}.")
                tekst = " ".join(r).lower()
                if not RE_CYTAT.search(" ".join(r)) and "nie znaleziono" not in tekst and "n/d" not in tekst:
                    w.uwaga(f"„Porównanie”: wiersz {i} bez cytatu [n].")
            naglowki = " ".join(nagl).lower()
            for k in pt["kolumny"]:
                if k not in naglowki:
                    w.blad(f"„Porównanie”: typ {typ} wymaga kolumny zawierającej „{k}”.")

    # 6. Ryzyka: każde ze słowem ze skali
    if norm("Ryzyka") in sek:
        poz = pozycje_listy(sek[norm("Ryzyka")])
        if not poz:
            w.blad("„Ryzyka”: brak listy ryzyk.")
        for p in poz:
            if not RE_SKALA.search(p):
                w.blad(f"„Ryzyka”: bez słowa ze skali prawdopodobieństwa: „{p[:70]}…”.")

    # 7. Kolejne kroki: link + kto
    if norm("Kolejne kroki") in sek:
        poz = pozycje_listy(sek[norm("Kolejne kroki")])
        if not poz:
            w.blad("„Kolejne kroki”: brak listy kroków.")
        for p in poz:
            linki = [u for _, u in RE_LINK.findall(p)]
            if not any(u.startswith(("http://", "https://", "#cmsg_", "notion://")) for u in linki):
                w.blad(f"„Kolejne kroki”: krok bez klikalnego linku: „{p[:70]}…”.")
            if not re.search(r"\bkto:\s*\S", p, re.I):
                w.blad(f"„Kolejne kroki”: krok bez „Kto: …”: „{p[:70]}…”.")

    # 8. Pewność i metoda
    if norm("Pewność i metoda") in sek:
        t = sek[norm("Pewność i metoda")]
        m = re.search(r"Ogólna pewność:\**\s*" + POZIOMY, t, re.I)
        if not m:
            w.blad("„Pewność i metoda”: brak „Ogólna pewność: wysoka | średnia | niska”.")
        elif pewnosc_skrot and m.group(1).lower() != pewnosc_skrot:
            w.uwaga(f"Pewność w „W skrócie” ({pewnosc_skrot}) różni się od ogólnej ({m.group(1).lower()}).")
        if not re.search(r"Metoda:", t):
            w.uwaga("„Pewność i metoda”: brak linii „Metoda:”.")

    # 9. Pokrycie pól
    if norm("Pokrycie pól") in sek:
        nagl, wiersze = tabela(sek[norm("Pokrycie pól")])
        if nagl is None or not wiersze:
            w.blad("„Pokrycie pól”: brak tabeli Pole | Status | Uwagi.")
        else:
            for r in wiersze:
                status = (r[1] if len(r) > 1 else "").strip().lower()
                if status not in {"✓", "częściowo", "nie znaleziono", "n/d"}:
                    w.blad(f"„Pokrycie pól”: pole „{r[0]}” ma status „{status}” (dozwolone: ✓, częściowo, "
                           "nie znaleziono, n/d).")
                if status == "nie znaleziono" and not RE_LINK.search(" ".join(r)):
                    w.uwaga(f"„Pokrycie pól”: „{r[0]}” nie znaleziono, a brak linku, gdzie sprawdzić.")
            ile_brak = sum(1 for r in wiersze if len(r) > 1 and r[1].strip().lower() == "nie znaleziono")
            w.stat["pola_nie_znaleziono"] = ile_brak
            if typy_dir and typ:
                pola = pola_typu(typy_dir, typ)
                if pola is None:
                    w.uwaga(f"Brak pliku typu {typ}.md albo tabeli „Pola obowiązkowe” w {typy_dir}; pokrycie nie sprawdzone.")
                else:
                    for p in pola:
                        if not any(to_samo_pole(p, r[0]) for r in wiersze):
                            w.blad(f"„Pokrycie pól”: brak pola obowiązkowego typu: „{p}”.")

    # 10. Źródła
    zrodla = {}
    tz = sek.get(norm("Źródła"), "")
    tz = tz.split("\n### ")[0]  # „### Odrzucone” nie liczy się do źródeł
    for l in tz.splitlines():
        m = RE_ZRODLO.match(l.strip())
        if not m:
            if re.match(r"^- \[\d", l.strip()):
                w.blad(f"„Źródła”: zły format linii: „{l.strip()[:70]}…”.")
            continue
        n, reszta = int(m.group(1)), m.group(2)
        if n in zrodla:
            w.blad(f"„Źródła”: numer [{n}] powtórzony.")
        link = RE_LINK.search(reszta)
        typ_z = re.search(r"typ:\s*([\wąćęłńóśźż-]+)", reszta, re.I)
        opubl = re.search(r"opubl\.?:\s*(\d{4}-\d{2}-\d{2}|brak)", reszta, re.I)
        sprawdz = re.search(r"sprawdz\.?:\s*(\d{4}-\d{2}-\d{2})", reszta, re.I)
        z = dict(url=link.group(2) if link else None, typ=typ_z.group(1).lower() if typ_z else None,
                 opubl=opubl.group(1) if opubl else None, sprawdz=sprawdz.group(1) if sprawdz else None)
        zrodla[n] = z
        if not z["url"] or not z["url"].startswith(("http://", "https://")):
            w.blad(f"Źródło [{n}]: brak linku [Tytuł](https://…).")
        if not z["typ"]:
            w.blad(f"Źródło [{n}]: brak „typ: …”.")
        elif z["typ"] not in TYPY_ZRODEL:
            w.blad(f"Źródło [{n}]: nieznany typ „{z['typ']}” (dozwolone: {', '.join(sorted(TYPY_ZRODEL))}).")
        if not z["opubl"]:
            w.blad(f"Źródło [{n}]: brak „opubl.: RRRR-MM-DD” (albo „opubl.: brak”).")
        if not z["sprawdz"]:
            w.blad(f"Źródło [{n}]: brak „sprawdz.: RRRR-MM-DD”.")
        ds = data(z["sprawdz"])
        if z["sprawdz"] and not ds:
            w.blad(f"Źródło [{n}]: zła data sprawdzenia „{z['sprawdz']}”.")
        if ds and ds > odniesienie:
            w.blad(f"Źródło [{n}]: data sprawdzenia {ds} późniejsza niż „Na dzień” {odniesienie}.")
        if ds and z["typ"] in CENOWE and pt["swiezosc_cen"] is not None and (odniesienie - ds).days > pt["swiezosc_cen"]:
            w.blad(f"Źródło [{n}] ({z['typ']}): cena sprawdzona {ds}, starsza niż {pt['swiezosc_cen']} dni "
                   f"dla typu {typ}; sprawdź ponownie.")
        do = data(z["opubl"]) if z["opubl"] and z["opubl"] != "brak" else None
        if do and z["typ"] not in CENOWE and (odniesienie - do).days > pt["swiezosc"]:
            w.uwaga(f"Źródło [{n}]: opublikowane {do}, starsze niż {pt['swiezosc']} dni; czy nadal aktualne?")

    # Cytaty w treści (bez sekcji Źródła)
    tresc = "\n".join(t for n, t in sekcje if norm(n) != norm("Źródła"))
    cytowania = []
    for m in RE_CYTAT.finditer(tresc):
        try:
            cytowania.extend(numery(m.group(1)))
        except ValueError:
            w.blad(f"Zły cytat „[{m.group(1)}]”.")
    for n in sorted(set(cytowania) - set(zrodla)):
        w.blad(f"Cytat [{n}] nie ma pozycji w „Źródłach”.")
    for n in sorted(set(zrodla) - set(cytowania)):
        w.uwaga(f"Źródło [{n}] nie jest nigdzie cytowane.")

    domeny = {domena(z["url"]) for z in zrodla.values() if z["url"]}
    oficjalne = sum(1 for z in zrodla.values() if z["typ"] in OFICJALNE)
    if len(zrodla) < pm["zrodla"]:
        w.blad(f"Za mało źródeł: {len(zrodla)} (tryb {tryb or 'standard'} wymaga {pm['zrodla']}).")
    if len(domeny) < pm["domeny"]:
        w.blad(f"Za mało różnych domen: {len(domeny)} (tryb {tryb or 'standard'} wymaga {pm['domeny']}).")
    if zrodla and oficjalne / len(zrodla) < pt["oficjalne"]:
        w.blad(f"Za mało źródeł oficjalnych/pierwotnych: {oficjalne}/{len(zrodla)} "
               f"(typ {typ} wymaga {int(pt['oficjalne'] * 100)}%).")
    if len(cytowania) >= 8:
        n_max = max(set(cytowania), key=cytowania.count)
        udzial = cytowania.count(n_max) / len(cytowania)
        if udzial > 0.25:
            w.uwaga(f"Źródło [{n_max}] to {int(udzial * 100)}% cytowań (max 25%); dodaj niezależne potwierdzenie.")
    if rejestr_urls is not None:
        for n, z in zrodla.items():
            if z["url"] and z["url"] not in rejestr_urls:
                w.uwaga(f"Źródło [{n}] nie występuje w rejestrze zrodla.json.")

    # 11. Język pewności (ICD 203)
    for zd in re.split(r"(?<=[.!?])\s+|\n", tresc):
        if RE_SKALA.search(zd) and re.search(r"\bpewnoś", zd, re.I) and "**Pewność:**" not in zd:
            w.uwaga(f"Prawdopodobieństwo i pewność w jednym zdaniu (ICD 203 każe je rozdzielać): „{zd.strip()[:70]}…”.")
    mgliste = sorted({m.group(1).lower() for m in RE_MGLISTE.finditer(tresc)})
    if mgliste:
        w.uwaga("Mgliste słowa zamiast skali: " + ", ".join(mgliste) + ".")
    w.stat["niezweryfikowane"] = len(re.findall(r"\[niezweryfikowane\]", tresc, re.I))

    # 12. Długość i czytelność
    bez_dod = "\n".join(t for n, t in sekcje if norm(n) not in {norm("Źródła"), norm("Pokrycie pól")})
    slowa = len(re.findall(r"\w+", bez_dod))
    w.stat["slowa"] = slowa
    w.stat["minuty_czytania"] = round(slowa / 200, 1)
    if slowa > pm["slowa"]:
        w.blad(f"Raport ma {slowa} słów (tryb {tryb or 'standard'}: max {pm['slowa']}); przenieś szczegóły do załączników.")
    for akapit in re.split(r"\n\s*\n", czysty):
        if len(akapit) > 2000 and not akapit.lstrip().startswith("|"):
            w.uwaga(f"Akapit ma {len(akapit)} znaków (Notion przyjmuje max 2000 w jednym bloku): „{akapit.strip()[:50]}…”.")
    gole = [u for u in re.findall(r"(?<![(<])https?://[^\s)>\]]+", tresc)]
    if gole:
        w.uwaga(f"Gołe adresy URL w treści ({len(gole)}); użyj [opis](url).")

    # 13. Pozostałości szablonu i dane prywatne (w całym tekście, z komentarzami usuniętymi)
    for m in RE_PLACEHOLDER.finditer(czysty):
        w.blad(f"Pozostałość szablonu: „{m.group(0)[:60]}”.")
        break
    if RE_SEKRET.search(text):
        w.blad("Wygląda na sekret (token, hasło, klucz API). Usuń; sekrety tylko w Bitwarden.")
    if RE_IBAN.search(text):
        w.blad("Wygląda na numer konta IBAN. Usuń z raportu.")
    for m in RE_KARTA.finditer(text):
        cyfry = re.sub(r"\D", "", m.group(0))
        if 13 <= len(cyfry) <= 19 and luhn(cyfry):
            w.blad("Wygląda na numer karty płatniczej. Usuń z raportu.")
            break
    for m in RE_PESEL.finditer(text):
        if pesel_ok(m.group(0)):
            w.uwaga("Ciąg 11 cyfr z poprawną sumą kontrolną PESEL; upewnij się, że to nie dane osobowe.")
            break

    # 14. Linki (opcjonalnie, sieć)
    if sprawdzaj_linki:
        urls = sorted({u for _, u in RE_LINK.findall(czysty) if u.startswith(("http://", "https://"))})
        for u in urls:
            kod = sprawdz_link(u)
            if kod in (404, 410):
                w.blad(f"Martwy link ({kod}): {u}")
            elif kod is None or kod >= 400:
                w.uwaga(f"Link nie odpowiada poprawnie ({kod or 'brak odpowiedzi'}): {u}")
        w.stat["linki_sprawdzone"] = len(urls)

    w.stat.update(zrodla=len(zrodla), domeny=len(domeny), oficjalne=oficjalne, cytowania=len(cytowania),
                  typ=typ or None, tryb=tryb or None)
    return w


def main(argv=None):
    ap = argparse.ArgumentParser(description="Walidator raportu research-kit (standard K80).")
    ap.add_argument("sciezka", help="raport.md albo katalog przebiegu z raport.md")
    ap.add_argument("--json", action="store_true", help="wynik jako JSON")
    ap.add_argument("--sprawdz-linki", action="store_true", help="sprawdź linki przez HTTP")
    ap.add_argument("--typy-dir", help="katalog z plikami typów (domyślnie ../typy obok skryptu)")
    ap.add_argument("--dzis", help="data odniesienia RRRR-MM-DD (domyślnie dziś)")
    a = ap.parse_args(argv)

    p = Path(a.sciezka)
    raport = p / "raport.md" if p.is_dir() else p
    try:
        text = raport.read_text(encoding="utf-8")
    except OSError as e:
        print(f"Nie mogę przeczytać {raport}: {e}", file=sys.stderr)
        return 2
    rejestr = None
    if p.is_dir() and (p / "zrodla.json").is_file():
        rejestr = set(re.findall(r"https?://[^\s\"']+", (p / "zrodla.json").read_text(encoding="utf-8")))
    typy_dir = a.typy_dir or (Path(__file__).resolve().parent.parent / "typy")
    dzis = data(a.dzis) if a.dzis else None
    w = waliduj(text, dzis=dzis, typy_dir=typy_dir if Path(typy_dir).is_dir() else None,
                rejestr_urls=rejestr, sprawdzaj_linki=a.sprawdz_linki)

    if a.json:
        print(json.dumps(dict(plik=str(raport), ok=not w.bledy, bledy=w.bledy, uwagi=w.uwagi,
                              statystyki=w.stat), ensure_ascii=False, indent=2))
    else:
        for b in w.bledy:
            print(f"BŁĄD   {b}")
        for u in w.uwagi:
            print(f"UWAGA  {u}")
        s = w.stat
        print(f"\n{'OK' if not w.bledy else 'NIE PRZESZEDŁ'}: {len(w.bledy)} błędów, {len(w.uwagi)} uwag · "
              f"{s.get('slowa')} słów (~{s.get('minuty_czytania')} min) · źródła {s.get('zrodla')}, "
              f"domeny {s.get('domeny')}, oficjalne {s.get('oficjalne')} · [niezweryfikowane] {s.get('niezweryfikowane')}")
    return 1 if w.bledy else 0


if __name__ == "__main__":
    sys.exit(main())
