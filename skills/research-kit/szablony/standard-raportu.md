# Standard raportów research-kit (v1, K80)

Jeden format raportu dla wszystkich typów researchu (wiedza, decyzja techniczna, zakupy, wycieczka, randka,
osoba/firma, zdrowie/prawo/finanse, monitoring), dla Hermesa i Claude Code. Ładuj w kroku 6 (pisanie).
Szablon do wypełnienia: [raport.md](raport.md). Sprawdza go [../skrypty/waliduj_raport.py](../skrypty/waliduj_raport.py).

Spis: 1. Zasady · 2. Sekcje · 3. Skala pewności · 4. Źródła i cytaty · 5. Formaty i długość ·
6. Co sprawdza walidator · 7. Parametry typów

## 1. Zasady

1. **Najpierw odpowiedź** (BLUF, „bottom line up front”): pierwsze 5 linii wystarczą, żeby podjąć decyzję.
   Reszta raportu to dowód i szczegóły.
2. **Bez szukania:** każdy fakt ma cytat [n] z klikalnym źródłem i datą; każde pole obowiązkowe typu jest
   wypełnione albo oznaczone „nie znaleziono” z linkiem, gdzie sprawdzić ręcznie.
3. **Stała skala pewności** (§3) zamiast „chyba”, „raczej”, „być może”.
4. **Te same nagłówki w tej samej kolejności** w każdym raporcie; różnice typów są w treści tabel i w
   podsekcjach `###` „Szczegółów”.
5. **Każdy krok ma link i właściciela** (Filip albo Hermes) oraz termin, jeśli jest.
6. **Bez danych wrażliwych:** żadnych numerów kart, IBAN, haseł, tokenów, loginów, kodów jednorazowych.

## 2. Sekcje (kolejność obowiązkowa)

| # | Nagłówek | Co zawiera | Reguła |
|---|---|---|---|
| — | `# Tytuł` + nagłówek | pytanie albo decyzja; pola: Typ, Tryb, Na dzień, Zlecenie (link), Autor, Status | wszystkie pola obowiązkowe |
| 1 | `## W skrócie` | lista: **Rekomendacja/Odpowiedź/Decyzja**, **Dlaczego**, **Alternatywa**, **Pewność**, **Teraz zrób** | max 5 linii i 600 znaków; pierwsza linia z etykietą; Pewność: wysoka/średnia/niska |
| 2 | `## Założenia` | czego Filip nie powiedział, a co zmienia wynik; jak wynik się zmieni | min. 1 pozycja albo „Brak założeń.” |
| 3 | `## Porównanie` | tabela pozycji × kryteriów (dla „wiedzy”: twierdzenie × pewność × źródła; dla monitoringu: było × jest × zmiana) | min. wierszy wg typu i trybu (§7); kolumna z ceną/kosztem dla typów kupowych; każdy wiersz z [n] |
| 4 | `## Szczegóły` | podsekcje `###` wg pliku typu (plan dnia, gdzie kupić, jak to działa…) | fakty z [n]; wiedza modelu bez źródła oznaczona `[niezweryfikowane]` |
| 5 | `## Ryzyka` | co może pójść źle, jak bardzo prawdopodobne, co wtedy | każde ryzyko ze słowem ze skali (§3) |
| 6 | `## Kolejne kroki` | numerowana lista `[ ]` | każdy krok: link, „Kto: …”, termin jeśli jest |
| 7 | `## Pewność i metoda` | Ogólna pewność, uzasadnienie, metoda (tryb, ile źródeł przejrzanych/odrzuconych, co sprawdzono ponownie, czego nie) | „Ogólna pewność:” zgodna z „W skrócie” |
| 8 | `## Pokrycie pól` | tabela Pole · Status · Uwagi dla każdego pola obowiązkowego z `typy/<typ>.md` | status: ✓, częściowo, nie znaleziono, n/d; nazwa pola skopiowana z pliku typu |
| 9 | `## Źródła` | numerowana lista źródeł (§4); opcjonalnie `### Odrzucone` z powodem | progi trybu i typu (§4, §7) |
| — | `## Załączniki` (opcjonalnie) | linki do plików: `.ics`, CSV/KML, PDF, notatki z przebiegu | — |

Typy dopisują własne podsekcje tylko jako `###` w „Szczegółach”. Plik typu w sekcji „Wyjście” mówi, co
wpisać w 5 liniach „W skrócie”, ale etykiety (**Rekomendacja:** … **Teraz zrób:**) zostają, żeby eksport do
Matrix i Notion działał tak samo dla każdego typu. Przykład dla zakupów: `- **Rekomendacja:** kup X w Y za
Z zł (cena efektywna W zł: kod …, punkty …), teraz, bo …`.

## 3. Skala pewności (wg ICD 203)

Dwie osobne miary, jak w [ICD 203](https://www.dni.gov/files/documents/ICD/ICD-203.pdf) (standard analityczny
wywiadu USA, [skala w taksonomii MISP](https://eugit.opencloud.lu/MISP/misp-taxonomies/commit/26ac124fe96a6cee9001c9c332cb9cc7328e7f09),
[poziomy pewności wg CIS](https://www.cisecurity.org/ms-isac/services/words-of-estimative-probability-analytic-confidences-and-structured-analytic-techniques)):

**a) Prawdopodobieństwo zdarzenia** (czy coś się stanie / jest prawdą). Używaj tylko tych słów:

| Słowo w raporcie | Przedział | ICD 203 |
|---|---|---|
| prawie wykluczone | 1–5% | almost no chance / remote |
| bardzo mało prawdopodobne | 5–20% | very unlikely |
| mało prawdopodobne | 20–45% | unlikely |
| mniej więcej równe szanse | 45–55% | roughly even chance |
| prawdopodobne (prawdopodobnie) | 55–80% | likely |
| bardzo prawdopodobne | 80–95% | very likely |
| prawie pewne (prawie na pewno) | 95–99% | almost certain |

Można dopisać liczbę: „prawdopodobne (ok. 70%)”.

**b) Pewność oceny** (jak mocne są dowody pod wnioskiem):

| Poziom | Kiedy |
|---|---|
| **wysoka** | wiele niezależnych, wiarygodnych źródeł (w tym oficjalne/pierwotne), zgodnych ze sobą; kluczowe twierdzenia zweryfikowane ponownie. Nadal nie znaczy „pewnik”. |
| **średnia** | źródła wiarygodne i wniosek sensowny, ale za mało potwierdzeń, część sprzeczna albo ważne pole „częściowo”. |
| **niska** | źródeł mało, są słabe, fragmentaryczne albo sprzeczne; wniosek to najlepsza dostępna hipoteza. |

Zasady: nie łącz obu miar w jednym zdaniu (ICD 203), bo czytelnik myli „prawdopodobne” z „pewne”; pisz
„Cena spadnie przed Black Friday: mało prawdopodobne.” i osobno „Pewność: średnia, bo…”. Słowa „chyba”,
„raczej”, „być może”, „zapewne”, „niewykluczone” zastępuj słowem ze skali.

## 4. Źródła i cytaty

- Cytat w tekście: `[n]`, kilka: `[2] [5]` albo `[2, 5]`, zakres `[2–4]`. Numer musi istnieć w „Źródłach”.
- Linia źródła (walidator ją parsuje):
  `- [n] [Tytuł](https://adres) · wydawca · typ: <typ> · opubl.: RRRR-MM-DD|brak · sprawdz.: RRRR-MM-DD`,
  opcjonalnie `· cytat: „…”` (dosłowny fragment, który potwierdza twierdzenie).
- Typy źródeł: `oficjalne` (urząd, producent, regulamin, przepis), `dokumentacja`, `nauka`, `test`
  (niezależny test/recenzja), `prasa`, `sklep`, `cennik`, `forum`, `inne`. Oficjalne/pierwotne =
  oficjalne + dokumentacja + nauka.
- Progi trybu: Szybki 3 źródła / 2 domeny, Standard 8 / 4, Głęboki 15 / 6 (z planu K76 §4.3).
- Jedno źródło nie powinno mieć więcej niż 25% cytowań (walidator ostrzega).
- Ceny (`sklep`, `cennik`) nie starsze niż limit typu (§7) względem „Na dzień”.
- Link prowadzi do konkretnej strony (oferty, artykułu, paragrafu), nie do wyszukiwarki ani strony głównej.

## 5. Formaty i długość

Źródłem prawdy jest zawsze `raport.md`, który przeszedł walidator. Inne formaty robi
[../skrypty/eksport_raportu.py](../skrypty/eksport_raportu.py).

| Format | Kiedy | Jak | Limit |
|---|---|---|---|
| **Markdown** (`raport.md`) | zawsze | szablon | Szybki ≤ 800 słów, Standard ≤ 2 500, Głęboki ≤ 6 000 (bez „Pokrycia” i „Źródeł”); ok. 200 słów = 1 min czytania |
| **Notion** (baza „Raporty”) | typy nietechniczne (decyzja K76 nr 2) | `eksport_raportu.py notion` daje tytuł, właściwości (Typ, Tryb, Na dzień, Status, Autor, Pewność, Zlecenie) i treść md do narzędzia Notion | akapit ≤ 2 000 znaków (limit bloku tekstu w [API Notion](https://developers.notion.com/reference/request-limits)); tabele zostają tabelami |
| **plany/** | decyzje techniczne i plany wdrożeń | `plany/research/RRRR-MM-DD-<temat>.md` wg [plany/README.md](../../../../README.md) | jak Markdown |
| **Wiadomość Matrix** | po każdym raporcie | `eksport_raportu.py matrix --link <url> --json` (body + `formatted_body` HTML) | ≤ 1 000 znaków: tytuł, 5 linii „W skrócie”, max 3 kroki, link; limit zdarzenia Matrix to 64 KiB, ale wiadomość ma się zmieścić na ekranie telefonu |
| **PDF** | Głęboki, wyjazd (wydruk), na prośbę | `eksport_raportu.py pdf` (pandoc → HTML → Chromium, A4) | jak Markdown |

Gdy raport przekracza limit słów: przenieś szczegóły do plików w `## Załączniki` (np. pełna lista
kandydatów, plan dzień po dniu jako osobny plik), a w raporcie zostaw podsumowanie.

## 6. Co sprawdza walidator

`python3 skrypty/waliduj_raport.py <raport.md | katalog przebiegu> [--json] [--sprawdz-linki] [--typy-dir typy]`

Kod 0 = brak błędów (uwagi dozwolone), 1 = błędy (wróć do kroku, który je naprawia), 2 = brak pliku.

| Obszar | Błąd (blokuje) | Uwaga (do decyzji autora) |
|---|---|---|
| Nagłówek | brak pola; nieznany typ/tryb; zła albo przyszła data | status spoza listy; Zlecenie bez linku |
| Sekcje | brak sekcji; zła kolejność | nieznana sekcja `##` |
| W skrócie | > 5 linii lub > 600 znaków; brak etykiety w 1. linii; brak „Pewność:” | brak cytatu/linku |
| Założenia | brak listy | — |
| Porównanie | brak tabeli; za mało wierszy; zła liczba komórek; brak kolumny ceny/kosztu | wiersz bez [n] |
| Ryzyka | ryzyko bez słowa ze skali | — |
| Kolejne kroki | krok bez linku; bez „Kto:” | — |
| Pewność i metoda | brak „Ogólna pewność:” | niezgodna z „W skrócie”; brak „Metoda:” |
| Pokrycie pól | zły status; brak pola z pliku typu | „nie znaleziono” bez linku |
| Źródła | zły format; brak linku, typu, dat; cytat bez źródła; za mało źródeł, domen, oficjalnych; za stara cena; data sprawdzenia po „Na dzień” | źródło niecytowane; > 25% cytowań; stara publikacja; brak w `zrodla.json` |
| Język | — | „chyba/raczej/być może…”; prawdopodobieństwo i pewność w jednym zdaniu |
| Długość | ponad limit słów trybu | akapit > 2 000 znaków; gołe URL |
| Prywatność | numer karty (Luhn), IBAN PL, hasło/token/klucz API | 11 cyfr z sumą PESEL |
| Szablon | pozostałe `<…>`, `TODO`, `XXX`, `{{` | — |
| Linki (`--sprawdz-linki`) | 404/410 | inne błędy HTTP, brak odpowiedzi |

## 7. Parametry typów

| Typ | Min. wierszy porównania | Wymagana kolumna | Ceny ≤ dni | Publikacje ≤ dni (uwaga) | Min. oficjalnych |
|---|---|---|---|---|---|
| wiedza | 1 | — | — | 1 095 | 30% |
| decyzja-techniczna | 2 | koszt | 30 | 365 | 30% |
| zakupy | 3 | cena | 7 | 365 | — |
| wycieczka | 2 | koszt | 3 | 365 | — |
| randka | 3 | koszt | 7 | 365 | — |
| osoba-firma | 1 | — | — | 365 | 30% |
| zdrowie-prawo-finanse | 1 | — | — | 365 | 50% |
| monitoring | 1 | — | 7 | 30 | — |

Tryb podnosi minimum wierszy (Standard 2, Głęboki 3). Ostrzejsze bramki z plików typów (np. cena zwycięzcy
z dnia wysłania w zakupach, godziny otwarcia ≤ 30 dni w wycieczkach) sprawdza krok 7 procedury; walidator
pilnuje progów wspólnych. Zmiana progów: PR do `TYPY` w walidatorze i do tej tabeli (zawsze razem).
