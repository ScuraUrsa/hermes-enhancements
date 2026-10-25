"""Testy bazy bibliografii (bez sieci: sprawdz_siec podmieniony).

    python3 -m unittest discover -s testy -v     # z katalogu research-kit
"""
import datetime as dt
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "skrypty"))
import bib  # noqa: E402


class Siec:
    """Udawana sieć: url → treść albo kod HTTP."""

    def __init__(self):
        self.strony = {}
        self.wywolania = 0

    def __call__(self, url, etag=None, lm=None):
        self.wywolania += 1
        s = self.strony.get(url, 404)
        if isinstance(s, int):
            return dict(http=s, hash=None, etag=None, lm=None)
        return dict(http=200, hash=bib.hash_tresci(s), etag=None, lm=None)


class TestBib(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.katalog = Path(self.tmp.name)
        self.siec = Siec()
        self._org = bib.sprawdz_siec
        bib.sprawdz_siec = self.siec

    def tearDown(self):
        bib.sprawdz_siec = self._org
        self.tmp.cleanup()

    def baza(self):
        return bib.Baza(self.katalog)

    def cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            kod = bib.main(["--baza", str(self.katalog), *argv])
        return kod, out.getvalue()

    def test_normalizacja(self):
        self.assertEqual(bib.normalizuj("http://www.Example.com/a/?utm_source=x&b=2#frag"),
                         "https://example.com/a?b=2")
        self.assertEqual(bib.normalizuj("example.com/"), "https://example.com")

    def test_nowe_zrodlo_do_otwarcia(self):
        r = bib.ocen(self.baza(), "https://example.com/x")
        self.assertEqual(r["decyzja"], "otworz")

    def test_odrzucone_pomijane_a_po_zmianie_do_sprawdzenia(self):
        u = "https://farm.example/top-10-best-vacuums"
        self.siec.strony[bib.normalizuj(u)] = "<p>stara treść</p>"
        b = self.baza()
        b.zapisz(typ="wizyta", url=bib.normalizuj(u), hash=bib.hash_tresci("<p>stara treść</p>"))
        b.zapisz(typ="ocena", url=bib.normalizuj(u), werdykt="odrzucone", powod="SEO, brak testów")
        self.assertEqual(bib.ocen(self.baza(), u, siec=True)["decyzja"], "pomin")
        self.assertEqual(bib.ocen(self.baza(), u)["decyzja"], "pomin")
        self.siec.strony[bib.normalizuj(u)] = "<p>nowa treść z testem</p>"
        self.assertEqual(bib.ocen(self.baza(), u, siec=True)["decyzja"], "sprawdz-ponownie")

    def test_wymuszenie(self):
        u = "https://farm.example/x"
        b = self.baza()
        b.zapisz(typ="ocena", url=bib.normalizuj(u), werdykt="odrzucone", powod="spam")
        self.assertEqual(bib.ocen(b, u + "#bib-wymus")["decyzja"], "otworz")

    def test_uzyteczne_ze_swieza_notatka(self):
        u = "https://uokik.gov.pl/prawa-konsumenta"
        b = self.baza()
        b.zapisz(typ="ocena", url=bib.normalizuj(u), werdykt="uzyteczne", notatka="14 dni na zwrot online")
        r = bib.ocen(self.baza(), u)
        self.assertEqual(r["decyzja"], "uzyj-notatki")
        self.assertIn("14 dni", r["notatka"])
        self.assertGreater(r["punkty"], 50)

    def test_punkty_domeny_z_historii(self):
        b = self.baza()
        for i in range(3):
            b.zapisz(typ="ocena", url=f"https://zla.example/{i}", werdykt="odrzucone", powod="x")
        self.assertLess(bib.ocen(self.baza(), "https://zla.example/nowy")["punkty"], 50)

    def test_decyzja_wykrywa_zmiane_zrodla(self):
        u1, u2 = "https://kod.example/release", "https://ceny.example/produkt"
        self.siec.strony.update({u1: "wersja 1.0", u2: "cena 100 zł"})
        kod, out = self.cli("decyzja", "dodaj", "K99-1", "--tytul", "Wybór X", "--klasa", "kod",
                            "--zrodla", u1, u2)
        self.assertEqual(kod, 0)
        # świeżo dodana: nic nie jest jeszcze do sprawdzenia
        kod, out = self.cli("sprawdz-decyzje")
        self.assertEqual(out.strip(), "")
        # minął miesiąc i źródło się zmieniło
        b = self.baza()
        zm, _ = None, None
        stare = bib.teraz
        bib.teraz = lambda: stare() + dt.timedelta(days=31)
        try:
            self.siec.strony[u2] = "cena 80 zł"
            kod, out = self.cli("sprawdz-decyzje")
        finally:
            bib.teraz = stare
        self.assertIn("K99-1", out)
        self.assertIn("ceny.example", out)
        self.assertNotIn("kod.example/release:", out)
        self.assertEqual(self.baza().decyzje["K99-1"]["status"], "do-przegladu")

    def test_klasa_na_zywo_co_15_minut(self):
        u = "https://trojmiasto.example/pozar"
        self.siec.strony[u] = "pożar opanowany w 20%"
        self.cli("decyzja", "dodaj", "ALARM-1", "--tytul", "Pożar", "--klasa", "na-zywo", "--zrodla", u)
        stare = bib.teraz
        try:
            bib.teraz = lambda: stare() + dt.timedelta(minutes=10)
            self.assertEqual(self.cli("sprawdz-decyzje")[1].strip(), "")
            bib.teraz = lambda: stare() + dt.timedelta(minutes=16)
            self.siec.strony[u] = "pożar opanowany w 60%"
            self.assertIn("ALARM-1", self.cli("sprawdz-decyzje")[1])
        finally:
            bib.teraz = stare

    def test_zrodlo_znika(self):
        u = "https://znika.example/a"
        self.siec.strony[u] = "jest"
        self.cli("decyzja", "dodaj", "D-1", "--tytul", "T", "--klasa", "na-zywo", "--zrodla", u)
        del self.siec.strony[u]
        stare = bib.teraz
        try:
            bib.teraz = lambda: stare() + dt.timedelta(minutes=20)
            self.assertIn("404", self.cli("sprawdz-decyzje")[1])
        finally:
            bib.teraz = stare

    def test_rejestr_przebiegu_i_wielu_pisarzy(self):
        b = self.baza()
        b.zapisz(typ="ocena", url="https://a.example", werdykt="uzyteczne", przebieg="2026-10-24-x")
        # drugi pisarz (np. kopia z prod) w osobnym pliku
        (self.katalog / "zdarzenia" / "prod.jsonl").write_text(json.dumps(dict(
            t="2026-10-24T10:00:00Z", w="prod", typ="ocena", url="https://b.example", werdykt="odrzucone",
            powod="reklama", przebieg="2026-10-24-x")) + "\n{urwana linia", encoding="utf-8")
        kod, out = self.cli("rejestr", "--przebieg", "2026-10-24-x")
        r = json.loads(out)
        self.assertEqual([z["url"] for z in r["zatwierdzone"]], ["https://a.example"])
        self.assertEqual([z["url"] for z in r["odrzucone"]], ["https://b.example"])

    def test_decyzja_z_raportu(self):
        raport = self.katalog / "raport.md"
        raport.write_text("# T\n\n## W skrócie\n- x https://nie.example\n\n## Źródła\n\n"
                          "1. [A](https://a.example/x) sprawdzono 2026-10-24\n2. https://b.example/y\n",
                          encoding="utf-8")
        self.assertEqual(bib.urls_z_raportu(raport), ["https://a.example/x", "https://b.example/y"])


if __name__ == "__main__":
    unittest.main()
