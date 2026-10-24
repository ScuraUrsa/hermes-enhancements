# Typ: zakupy (v1, K79)

Plik typu dla `research-kit` (`typy/zakupy.md`). Zastępuje szkic z K76. Ładuj tylko dla typu `zakupy`.
Obejmuje: wybór rzeczy do kupienia, cenę po wszystkich rabatach, punktach i cashbacku, moment zakupu,
plan zakupowy i opcjonalny monitoring. Nie obejmuje zakupów spożywczych na co dzień (to lista zakupów)
ani inwestycji (typ `zdrowie-prawo-finanse`).

## 0. Kontekst, który czytasz przed startem

1. `kontekst/filip.md` (miasto, preferencje, budżety domyślne).
2. **Profil zakupowy** (prywatna strona Notion „Profil zakupowy Filipa”): gdzie Filip ma konto, karty,
   programy, salda punktów z datą, aktywne abonamenty (Allegro Smart!, Prime itp.). Nie kopiuj go do raportu
   w całości; użyj tylko pozycji, które zmieniają cenę lub wybór sklepu.
3. Kalendarz promocji (sekcja 6 tego pliku) i otwarte monitoringi (`~/.hermes/price-watches/`).

Nigdy nie wpisuj do raportu numerów kart, loginów ani kodów jednorazowych. Kody rabatowe publiczne mogą być.

## 1. Pytania startowe (max 3, tylko gdy zmieniają wynik)

| Pytanie | Domyślnie, gdy brak odpowiedzi |
|---|---|
| Budżet i do kiedy potrzebne? | budżet: rozsądna środkowa półka kategorii; termin: bez pośpiechu (wolno czekać do 30 dni na promocję) |
| Co jest konieczne, a co miłe? Nowy, używany, odnowiony? | nowy lub odnowiony z gwarancją ≥ 12 mies.; używany tylko dla sprzętu enterprise/hobby |
| Kupić teraz czy poczekać na promocję? | jeśli w ciągu 30 dni jest duża akcja (sekcja 6) i rzecz nie jest pilna: plan „czekaj do X, kup, jeśli cena ≤ Y” |

## 2. Tryb

- Szybki: zakup do 200 zł albo uzupełnienie (ten sam produkt co ostatnio).
- Standard: 200–2 000 zł.
- Głęboki: powyżej 2 000 zł, sprzęt na lata (AGD, laptop, samochodowe), zakup z finansowaniem.

## 3. Pola obowiązkowe (tabela pozycji × pól)

Pozycje: 5–10 kandydatów z rynku, w raporcie 3: **najlepszy**, **tańszy**, **premium** (+ ewentualnie
„używany/odnowiony”, jeśli realnie tańszy o ≥ 25%).

| Pole | Jak wypełnić | Źródło minimalne |
|---|---|---|
| model, wariant, kod producenta (EAN/MPN) | dokładnie, żeby ceny dotyczyły tego samego | strona producenta |
| parametry vs kryteria Filipa | tabela; „must-have” spełnione tak/nie | producent + test |
| wyniki testów | min. 2 niezależne testy (nie opinie w sklepie); dla PL brak → RTINGS/Wirecutter | test |
| typowe wady i awarie | recenzje 1–2★, fora, wątki zwrotów; min. 1 źródło | forum |
| **cena w min. 3 sklepach**, z dostawą, z datą i godziną sprawdzenia | link do oferty, nie do kategorii | sklep |
| **najniższa cena z 30 dni** (Omnibus) przy każdej „promocji” | sklep musi ją pokazać; brak = flaga | sklep |
| **historia ceny** (min. 90 dni) | Ceneo „Historia cen”, Skąpiec, wykres Pepper; gdy niedostępne: „sprawdź ręcznie” + link | Ceneo/Pepper |
| **cena efektywna Filipa** | cena − kod − cashback − wartość punktów + dostawa (wzór w §4) | profil + regulaminy |
| gwarancja, zwrot, serwis w PL | długość, kto realizuje (producent/sklep), czas zwrotu | sklep/producent |
| dostępność i czas dostawy | w magazynie / na zamówienie; dostawa do paczkomatu | sklep |
| koszt posiadania | eksploatacja, prąd, abonament, części | producent/test |
| ryzyko sprzedawcy | marketplace: oceny sprzedawcy, czas na rynku, „sprzedawca zagraniczny” | Allegro/Amazon |

## 4. Cena efektywna (wzór, licz zawsze)

```
cena_efektywna = cena_oferty + dostawa
               − kod_rabatowy
               − cashback_sklepu (Goodie, LetyShops, oferty banku)      [tylko jeśli łączy się z kodem]
               − cashback_karty (np. Karta XTB 1%)                      [tylko jeśli płacisz tą kartą]
               − wartość_punktów_zdobytych (RevPoints, Smart! Monety…) × wycena_punktu
               + koszt_abonamentu_przypisany (np. Smart! jeśli kupujesz go tylko pod ten zakup)
```

Zasady: (1) pokaż wzór z liczbami dla zwycięzcy; (2) wycena punktu z datą i źródłem, a gdy nie da się jej
ustalić, policz z 0 i napisz to; (3) sprawdź łączenie: większość cashbacków nie działa z kodami spoza ich
listy i przy blokerach reklam; (4) cashback to pieniądz „później” (zwykle 30–90 dni), pokaż to.

## 5. Źródła domyślne (PL najpierw)

| Cel | Źródła |
|---|---|
| porównanie cen i historia | [Ceneo](https://www.ceneo.pl) (historia cen na karcie produktu), [Skąpiec](https://www.skapiec.pl), [Allegro](https://allegro.pl) (najniższa cena z 30 dni przy ofercie) |
| promocje, kody, błędy cenowe | [Pepper.pl](https://www.pepper.pl) (temperatura = głosy społeczności; >200° „gorące”), kanał RSS [pepper.pl/rss/nowe](https://www.pepper.pl/rss/nowe), alerty słów kluczowych na koncie Pepper |
| testy | Optimum/Benchmark.pl/PurePC/Chip.pl (PL), [RTINGS](https://www.rtings.com), Wirecutter, Which? |
| sklepy | sklep producenta, x-kom, Media Expert, RTV Euro AGD, MediaMarkt, morele, Komputronik, Amazon.pl, Allegro |
| cashback | Goodie, LetyShops, oferty w aplikacji banku (Pekao, Revolut „Sklepy”) |
| profil Filipa | Notion „Profil zakupowy Filipa”, Gmail (newslettery i podsumowania punktów) |
| prawo konsumenta | [UOKiK](https://uokik.gov.pl), [Europejskie Centrum Konsumenckie](https://konsument.gov.pl) |

Uwaga techniczna: Ceneo blokuje roboty na części stron, a Allegro i x-kom bywają za Cloudflare. Najpierw
`web_extract`, potem przeglądarka Hermesa i `blocked-page-recovery`; gdy dalej nie działa, pole „sprawdź
ręcznie” z linkiem do konkretnej strony (nie do wyszukiwarki).

## 6. Kalendarz promocji (aktualizuj co kwartał)

| Kiedy | Akcja | Uwagi |
|---|---|---|
| 11.11 | Dzień Singla (AliExpress, część sklepów PL) | |
| 27.11.2026 | **Black Friday**; Black Week ok. 23–30.11; Cyber Monday 30.11.2026 | sklepy często podnoszą ceny wcześniej: sprawdź 30-dniowe minimum i historię |
| 6.12 | Mikołajki | |
| 26.12–styczeń | wyprzedaże poświąteczne | odzież, AGD z ekspozycji |
| maj | Allegro Smart! Weeks (2026: 11–20.05), często tańszy pakiet Smart! | |
| lipiec | Amazon Prime Day | |
| sierpień–wrzesień | powrót do szkoły (elektronika) | |
| **31.10.2026 / 31.12.2026** | koniec zbierania żappsów / ostatni dzień na ich wydanie | dotyczy Filipa (Żappka) |

## 7. Bramki typu (oprócz bramek trybu)

- Cena zwycięzcy sprawdzona w dniu wysłania raportu (świeżość 24 h dla rekomendacji „kup teraz”, 7 dni dla reszty).
- Każda „promocja” ma najniższą cenę z 30 dni albo flagę „sklep nie pokazuje”.
- Min. 3 sklepy dla zwycięzcy; min. 2 testy niezależne (Standard i Głęboki).
- Cena efektywna policzona wzorem z §4 dla zwycięzcy i dla tańszej opcji.
- Brak numerów kart i danych logowania w raporcie (walidator: regex numerów kart i IBAN).

## 8. Wyjście

Na górze (5 linii):
> **Kup X w sklepie Y za Z zł** (cena efektywna W zł: kod …, cashback …, punkty …). Teraz / czekaj do D, bo …
> Tańsza opcja: … Premium: … Pewność: wysoka/średnia/niska.

Dalej: tabela 3 opcji, historia ceny (1 zdanie + link), **plan zakupu** (gdzie, kiedy, czym zapłacić, przez
jaki cashback wejść, jakie punkty wykorzystać lub zebrać, termin zwrotu), ryzyka, źródła.
Na końcu propozycja monitoringu: „Mam pilnować ceny? Próg: …, sklepy: …, do: …” → po zgodzie skill
`product-price-monitor` (blueprint `price-watch`) zapisuje kontrakt w `~/.hermes/price-watches/`.

Zakupu nie wykonuje research. Koszyk lub zamówienie robi agent zakupów tylko po wyraźnej akceptacji Filipa.
