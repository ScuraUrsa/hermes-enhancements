"""Testy walidatora: przykład przechodzi, każda zepsuta wersja daje oczekiwany błąd.

    python3 -m unittest discover -s testy -v     # z katalogu research-kit
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "skrypty"))
import waliduj_raport as wr  # noqa: E402

PRZYKLAD = (KIT / "przyklady" / "zakupy-przyklad.md").read_text(encoding="utf-8")
DZIS = dt.date(2026, 10, 23)


def wynik(text, typy=True):
    return wr.waliduj(text, dzis=DZIS, typy_dir=KIT / "typy" if typy else None)


class TestPrzyklad(unittest.TestCase):
    def test_przyklad_przechodzi(self):
        w = wynik(PRZYKLAD)
        self.assertEqual(w.bledy, [])
        self.assertEqual(w.stat["zrodla"], 10)

    def test_szablon_nie_przechodzi(self):
        w = wynik((KIT / "szablony" / "raport.md").read_text(encoding="utf-8"))
        self.assertTrue(any("Pozostałość szablonu" in b for b in w.bledy))


class TestBledy(unittest.TestCase):
    def zepsuj(self, stare, nowe, oczekiwany, typy=True):
        self.assertIn(stare, PRZYKLAD)
        w = wynik(PRZYKLAD.replace(stare, nowe, 1), typy)
        self.assertTrue(any(oczekiwany in b for b in w.bledy), f"brak „{oczekiwany}” w {w.bledy}")

    def test_brak_sekcji(self):
        self.zepsuj("## Założenia", "## Hipotezy", "Brak sekcji „## Założenia”")

    def test_kolejnosc(self):
        a = PRZYKLAD.index("## Ryzyka")
        b = PRZYKLAD.index("## Kolejne kroki")
        c = PRZYKLAD.index("## Pewność i metoda")
        tekst = PRZYKLAD[:a] + PRZYKLAD[b:c] + PRZYKLAD[a:b] + PRZYKLAD[c:]
        self.assertTrue(any("kolejności" in b for b in wynik(tekst).bledy))

    def test_skrot_za_dlugi(self):
        self.zepsuj("- **Teraz zrób:**", "- Linia dodatkowa.\n- **Teraz zrób:**", "max 5")

    def test_skrot_bez_rekomendacji(self):
        self.zepsuj("- **Rekomendacja:** kup", "- Kup", "pierwsza linia")

    def test_skrot_bez_pewnosci(self):
        self.zepsuj("**Pewność:** średnia", "**Pewnie:** średnia", "**Pewność:**")

    def test_cytat_bez_zrodla(self):
        self.zepsuj("[4] [5].", "[4] [11].", "Cytat [11]")

    def test_za_malo_wierszy_porownania(self):
        self.zepsuj("| Odkurzacz C (premium) |", "Odkurzacz C (premium) |", "wymagane min. 3")

    def test_brak_kolumny_cena(self):
        self.zepsuj("| Cena z dostawą |", "| Koszt z dostawą |", "„cena”")

    def test_ryzyko_bez_skali(self):
        self.zepsuj("prawdopodobne, bo kod", "raczej tak, bo kod", "skali prawdopodobieństwa")

    def test_krok_bez_linku(self):
        self.zepsuj("[porównywarce](https://ceny.example/odkurzacz-c)", "porównywarce", "bez klikalnego linku")

    def test_krok_bez_kto(self):
        self.zepsuj("Kto: Hermes.", "Hermes.", "Kto: …")

    def test_brak_ogolnej_pewnosci(self):
        self.zepsuj("**Ogólna pewność:** średnia", "**Ogólnie:** średnia", "Ogólna pewność")

    def test_zly_status_pokrycia(self):
        self.zepsuj("| wyniki testów | ✓ |", "| wyniki testów | tak |", "ma status „tak”")

    def test_brak_pola_typu(self):
        self.zepsuj("| ryzyko sprzedawcy | n/d | sklepy, nie marketplace |\n", "", "ryzyko sprzedawcy")

    def test_zrodlo_bez_daty(self):
        self.zepsuj(" · sprawdz.: 2026-10-22", "", "brak „sprawdz.:")

    def test_stara_cena(self):
        self.zepsuj("sprawdz.: 2026-10-22", "sprawdz.: 2026-10-01", "starsza niż 7 dni")

    def test_zly_typ_zrodla(self):
        self.zepsuj("typ: forum", "typ: blog", "nieznany typ „blog”")

    def test_za_malo_zrodel_glebokie(self):
        self.zepsuj("**Tryb:** standard", "**Tryb:** głęboki", "Za mało źródeł")

    def test_oficjalne_dla_prawa(self):
        self.zepsuj("**Typ:** zakupy", "**Typ:** zdrowie-prawo-finanse", "oficjalnych", typy=False)

    def test_karta_platnicza(self):
        self.zepsuj("## Założenia\n", "## Założenia\n\nKarta 4111 1111 1111 1111.\n", "karty płatniczej")

    def test_iban(self):
        self.zepsuj("## Założenia\n", "## Założenia\n\nPL61 1090 1014 0000 0712 1981 2874\n", "IBAN")

    def test_sekret(self):
        self.zepsuj("## Założenia\n", "## Założenia\n\nhasło: Tajne123\n", "sekret")

    def test_przyszla_data(self):
        self.zepsuj("**Na dzień:** 2026-10-23", "**Na dzień:** 2026-12-01", "w przyszłości")

    def test_za_dlugi(self):
        dlugi = PRZYKLAD.replace("### Typowe wady", "### Długo\n\n" + "słowo " * 2600 + "\n\n### Typowe wady")
        self.assertTrue(any("słów" in b for b in wynik(dlugi).bledy))


class TestUwagi(unittest.TestCase):
    def test_mgliste_slowa(self):
        w = wynik(PRZYKLAD.replace("najlepszy wynik", "chyba najlepszy wynik"))
        self.assertTrue(any("Mgliste" in u for u in w.uwagi))

    def test_pewnosc_i_prawdopodobienstwo_w_zdaniu(self):
        w = wynik(PRZYKLAD.replace("- Budżet do 1 500 zł", "- To prawdopodobne, pewność wysoka. Budżet do 1 500 zł"))
        self.assertTrue(any("ICD 203" in u for u in w.uwagi))

    def test_gole_url(self):
        w = wynik(PRZYKLAD.replace("W Sklepie B ten", "Zobacz https://sklep-b.example/x. W Sklepie B ten"))
        self.assertTrue(any("Gołe adresy" in u for u in w.uwagi))


class TestPomocnicze(unittest.TestCase):
    def test_numery(self):
        self.assertEqual(wr.numery("2, 4–6"), {2, 4, 5, 6})

    def test_daty_nie_sa_karta(self):
        w = wynik(PRZYKLAD.replace("## Założenia\n", "## Założenia\n\n2026-10-23 2026-10-24 2026-10-25\n"))
        self.assertFalse(any("karty" in b for b in w.bledy))

    def test_pole_z_formatowaniem(self):
        self.assertTrue(wr.to_samo_pole("**historia ceny** (min. 90 dni)", "historia ceny"))


if __name__ == "__main__":
    unittest.main()
