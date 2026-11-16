# Typ: wycieczka (v0.2, wątek K78 „Planowanie wycieczek”, 2026-10-23)

Wyjazdy: weekend, urlop, city break, wyjazd z dzieckiem, objazd kilku miast. Uzasadnienie i źródła:
[plany/research/2026-10-23-planowanie-wycieczek.md](../../../2026-10-23-planowanie-wycieczek.md).

**Tryb domyślny: Głęboki** (Szybki tylko dla pojedynczego pytania, np. „jak dojechać z lotniska”).
**Zasada nadrzędna:** każda cena, godzina, rozkład i przepis pochodzi ze źródła sprawdzonego w tym biegu
(link + data sprawdzenia). Wiedza modelu służy tylko do wymyślania kandydatów, nigdy jako fakt
(w benchmarku [TravelPlanner](https://arxiv.org/pdf/2402.01622) GPT‑4 z narzędziami zrobił poprawny plan w 0,6%
przypadków; główne błędy: zmyślone dane, niekompletne informacje, przekroczony budżet).

## Pytania startowe (max 3, tylko gdy zmieniają wynik)

Kolejność ważności. Bez odpowiedzi: wartości z `kontekst/filip.md`, wypisane jako założenia na górze raportu.

1. **Kiedy i skąd?** Daty (sztywne czy elastyczne ±N dni), miasto startowe, czy są już kupione bilety lub noclegi.
2. **Kto jedzie?** Liczba osób, wiek dziecka (wózek, drzemki, fotelik), ograniczenia (zdrowie, dieta, zwierzę).
3. **Budżet i styl?** Kwota łączna lub na dzień; tempo (spokojnie / intensywnie); priorytety (natura, historia,
   plaża, jedzenie, aktywność); auto czy transport publiczny.

Nie pytać o rzeczy, które da się sprawdzić (pogoda, ceny, odległości).

## Cykl życia wyjazdu (research nie kończy się na raporcie)

| Etap | Kiedy | Co robi Hermes | Wynik |
|---|---|---|---|
| A. Plan | na prośbę | pełny research wg pól poniżej | raport + plan dzień po dniu z wariantami |
| B. Rezerwacje | po decyzji Filipa | lista „co zarezerwować, gdzie, do kiedy” z linkami; rezerwuje tylko za zgodą (przeglądarka, akceptacja przed płatnością) | tracker rezerwacji |
| C. Obserwacja cen | od planu do zakupu / do końca darmowego anulowania | monitoring lotów i noclegów (sekcja „Śledzenie cen”) | alert w Matrix przy progu |
| D. Przed wyjazdem | T‑30, T‑7, T‑2, T‑1 | dokumenty, EKUZ, ubezpieczenie, odprawa online, prognoza, strajki, ostrzeżenia MSZ, pakowanie | zadania timeplane dla Filipa + krótkie przypomnienia |
| E. W trakcie | codziennie rano | prognoza na dziś → wybór wariantu A/B/C dnia, godziny otwarcia na dziś, zmiany rozkładów | wiadomość „plan na dziś” z linkami do Map |
| F. Po powrocie | T+1 do T+7 | rozliczenie budżetu (plan vs faktycznie), reklamacje (opóźnienia lotów), feedback do skilla | `ewaluacje/wycieczka/feedback.jsonl` |

Każde zadanie, które Filip musi zrobić sam (wniosek o dowód dziecka, EKUZ, płatność, odprawa wymagająca jego
logowania), idzie jako zadanie timeplane wg reguły projektu (opis, dlaczego, kryterium „gotowe”, kroki z
linkami, link do wątku).

## Pola obowiązkowe

Każde pole: wartość + źródło (numer z rejestru) + data sprawdzenia, albo „nie znaleziono” z tym, co sprawdzono,
i linkiem do ręcznego sprawdzenia.

### 1. Transport (tabela: odcinek × 2–3 opcje)

Odcinki: dom → lotnisko/dworzec, przelot/przejazd główny, przylot → nocleg (także nocą!), między miejscami,
lokalnie na miejscu, powrót.

| Pole | Uwagi |
|---|---|
| środek, przewoźnik, numer lotu/pociągu | konkretne połączenie, nie „jest autobus” |
| godzina odjazdu i przyjazdu, czas podróży | z rozkładu na **ten dzień tygodnia** (rozkłady sezonowe, niedziele, święta) |
| cena łączna dla całej grupy | z bagażem, miejscami obok siebie, dzieckiem; waluta + przeliczenie na zł |
| ostatni kurs dnia | krytyczne przy późnym przylocie |
| jak kupić bilet | aplikacja / automat / u kierowcy; czy trzeba kasować |
| bagaż i dziecko | limity bagażu, wózek, fotelik (taksówka, wynajem auta) |
| ryzyka transportu | strajki w terminie, przesiadka < 60 min, ostatni prom |
| auto (jeśli dotyczy) | winiety/autostrady, strefy ZTL i niskiej emisji, parkingi i ceny |

### 2. Noclegi (3 kandydatów na każde miejsce: najlepszy, tańszy, wygodny z dzieckiem)

| Pole | Uwagi |
|---|---|
| nazwa, dzielnica, link | dzielnica z uzasadnieniem (dojazd, hałas, bezpieczeństwo) |
| cena za cały pobyt z opłatami | z opłatą turystyczną (city tax), sprzątaniem, śniadaniem |
| zasady anulowania | **data, do której anulowanie jest darmowe** (wchodzi do trackera) |
| ocena i liczba opinii | min. 2 serwisy; typowe skargi z opinii 1–3★ |
| nocleg dla dziecka | łóżeczko, dostawka, winda/schody, kuchnia, pralka |
| zameldowanie | godziny check‑in/out, późny przyjazd, przechowalnia bagażu |
| odległość pieszo/komunikacją do głównych punktów | link do Map |

### 3. Plan dzień po dniu

Każdy dzień ma wariant **A (ładna pogoda), B (zmienna), C (deszcz/upał)** albo co najmniej kotwicę i plan B.

| Pole | Uwagi |
|---|---|
| harmonogram godzinowy | z czasami dojazdów między punktami (z Map/rozkładu, nie z głowy) |
| bufor i odpoczynek | min. 20% dnia wolne; z dzieckiem drzemka i plac zabaw |
| suma: czas w transporcie / zwiedzanie / wolne | kontrola wykonalności (patrz „Bramki”) |
| posiłki w planie dnia | 1–2 konkretne miejsca na obiad przy trasie, ceny orientacyjne, godziny kuchni |
| link do trasy dnia | Google Maps `dir/?api=1`, max 9 punktów (3 na telefonie: dzielić na odcinki) |
| „więcej niż zdążymy” | lista dodatkowych opcji do wyboru, oznaczonych jako opcjonalne |

### 4. Atrakcje (tabela: atrakcja × pola)

| Pole | Uwagi |
|---|---|
| priorytet atrakcji | must‑see / warto / jeśli czas |
| godziny otwarcia **w dniu planowanej wizyty** | dni zamknięcia (np. poniedziałki), sezon, ostatnie wejście |
| bilet normalny / dziecko / rodzinny / darmowe dni | link do zakupu; czy rezerwacja z wyprzedzeniem jest konieczna |
| czas zwiedzania | |
| dostępność z wózkiem, atrakcyjność dla dziecka | |
| kąpiel (jeśli dotyczy) | plaża/kąpielisko: dojście, cień, ratownik, temperatura wody, opłaty za leżaki |

### 5. Pogoda i sezon

| Pole | Uwagi |
|---|---|
| klimat dla tych dat | średnie z ostatnich 10 lat dla dokładnego okresu (temp. min/max, dni z opadem, woda) |
| prognoza pogody | dopiero od ok. T‑10; w etapie E codziennie |
| sezon i tłumy | tłumy, ceny, sezonowe zamknięcia, rozkłady poza sezonem |
| wydarzenia i święta w terminie | święta lokalne, festiwale, mecze, targi (podbijają ceny noclegów), **strajki transportu** |

### 6. Formalności i bezpieczeństwo

| Pole | Uwagi |
|---|---|
| ostrzeżenia MSZ dla kraju | poziom i data z [Odyseusz / Informacje dla podróżujących](https://odyseusz.gov.pl/); propozycja rejestracji podróży w Odyseuszu |
| dokumenty dla każdej osoby | UE/Schengen: dowód lub paszport; poza: paszport + wymagana ważność; wizy, e‑zezwolenia (np. UK ETA, także dla dzieci); **ważność dokumentów sprawdzona względem dat wyjazdu** |
| dziecko: dokument i zgody | [dowód dziecka](https://www.gov.pl/web/gov/uzyskaj-dowod-osobisty-dla-dziecka-lub-podopiecznego) (do 30 dni wyrobienia), zgoda drugiego rodzica, gdy jedzie jeden ([Straż Graniczna](https://www.strazgraniczna.pl/pl/pozostale-informacje/kampanie-spoleczno-informacyjn/podrozuj-bezpiecznie-straz-gra/14480,Podrozuj-bezpiecznie-Straz-Graniczna-w-trosce-o-najmlodszych.html)) |
| zdrowie i opieka medyczna | [EKUZ](https://www.nfz.gov.pl/dla-pacjenta/nasze-zdrowie-w-ue/leczenie-w-krajach-unii-europejskiej-i-efta/wypoczynek-w-panstwach-czlonkowskich-ueefta-ekuz/) (tylko publiczne placówki, bez transportu do Polski), szczepienia, apteka i szpital pediatryczny przy noclegu |
| ubezpieczenie podróżne | co musi obejmować (koszty leczenia, transport do kraju, ratownictwo, sporty, bagaż, rezygnacja); czy Filip ma polisę z karty/konta (profil z K79) |
| pieniądze i łączność | waluta, płatność kartą/gotówką, napiwki, roaming (UE bez dopłat, poza UE sprawdzić), gniazdka |
| przepisy lokalne | opłata turystyczna, zakazy (np. kąpiel, picie w miejscach publicznych), numer alarmowy |

### 7. Budżet i rezerwacje

| Pole | Uwagi |
|---|---|
| budżet w kategoriach | tabela jak niżej, suma vs budżet z briefu |
| tracker rezerwacji i terminów | tabela z pkt 8, każdy wiersz z datą „do kiedy” |

Budżet: tabela kategorii (transport, noclegi, atrakcje, jedzenie, lokalny transport, ubezpieczenie, rezerwa 10%):
kwota planowana, źródło ceny, data. Suma ma się zmieścić w budżecie z briefu; jeśli nie, raport mówi to w
pierwszych 5 liniach i proponuje, co wyciąć.

### 8. Tracker rezerwacji i terminów

| Co | Gdzie (link) | Do kiedy zarezerwować | Darmowe anulowanie do | Status |
|---|---|---|---|---|

Terminy liczone od dat wyjazdu (np. bilety wstępu z limitem miejsc, odprawa online, wniosek o dokument).

## Bramki typu (dodatkowe do bramek rdzenia)

1. **Wykonalność dnia:** suma czasów (transport + zwiedzanie + posiłki) ≤ dostępny czas minus 20% bufora; żaden
   punkt nie jest odwiedzany poza godzinami otwarcia; ostatni kurs powrotny istnieje.
2. **Spójność logistyki:** przyjazd do noclegu w godzinach zameldowania (albo potwierdzony późny check‑in);
   kolejny dzień zaczyna się tam, gdzie skończył się poprzedni.
3. **Budżet:** suma z tabeli budżetu ≤ budżet z briefu.
4. **Dziecko:** każdy dzień ma przerwę i dostęp do toalety/jedzenia; dokument dziecka ważny.
5. **Świeżość** (niżej) spełniona dla zwycięskich opcji w dniu wysłania raportu.

## Źródła domyślne

| Obszar | Źródła (pierwsze = pierwotne) |
|---|---|
| loty | strona przewoźnika (cena końcowa), [Google Flights](https://www.google.com/travel/flights), Skyscanner, Kiwi; okazje: Fly4free |
| pociągi, autobusy, promy | strony przewoźników (Trenitalia, Italo, FlixBus, Jadrolinija itd.), [Rome2rio](https://www.rome2rio.com) tylko jako mapa opcji, rozkłady w [Transitous](https://transitous.org) |
| noclegi | Booking, Airbnb, strona obiektu (często taniej bez prowizji), Google Hotels do porównania |
| atrakcje | oficjalna strona atrakcji (godziny, bilety), Google Maps (godziny, oceny, „popularne godziny”), lokalna informacja turystyczna |
| pogoda | [Open‑Meteo Historical](https://open-meteo.com/en/docs/historical-weather-api) (klimat z 10 lat), prognoza Open‑Meteo; woda: Open‑Meteo Marine |
| formalności | [Odyseusz MSZ](https://odyseusz.gov.pl/), gov.pl (dokumenty), [NFZ EKUZ](https://www.nfz.gov.pl/dla-pacjenta/nasze-zdrowie-w-ue/leczenie-w-krajach-unii-europejskiej-i-efta/wypoczynek-w-panstwach-czlonkowskich-ueefta-ekuz/), [Rzecznik Finansowy: ubezpieczenia](https://rf.gov.pl/edukacja/baza-wiedzy/najczestsze-pytania-i-odpowiedzi-faq/ubezpieczenie-turystyczne-w-pytaniach-i-odpowiedziach/), Your Europe |
| wydarzenia, strajki, święta | lokalne kalendarze wydarzeń, kalendarz strajków kraju (np. Włochy: ministerstwo transportu), święta państwowe |
| opinie i praktyka | fora i grupy podróżnicze, blogi z ostatnich 12 miesięcy (tylko jako sygnał, potwierdzić w źródle pierwotnym) |

Progi rejestru: min. 30% źródeł oficjalnych (przewoźnik, atrakcja, urząd); żadna cena tylko z agregatora bez
sprawdzenia u sprzedawcy dla zwycięskiej opcji.

## Świeżość

| Dane | Limit |
|---|---|
| ceny lotów i noclegów | 3 dni (zwycięzca: w dniu wysłania) |
| rozkłady i godziny otwarcia | 30 dni i zawsze dla konkretnego dnia wizyty; w etapie E w dniu wizyty |
| ostrzeżenia MSZ, strajki | 7 dni przed wyjazdem i T‑1 |
| przepisy (dokumenty, wizy, e‑zezwolenia) | 90 dni i T‑30 |

## Śledzenie cen (monitoring)

Uruchamiane po etapie A dla opcji, które Filip wybrał, a jeszcze nie kupił.

| Co | Jak | Próg alertu |
|---|---|---|
| loty | 1) Śledzenie cen w Google Flights na koncie Google Filipa (maile o spadkach trafiają do Gmaila, Hermes je czyta); 2) własny cron Hermesa: `fast-flights` (Google Flights) i `ryanair-py` (Ryanair) raz dziennie, wynik do `ceny.jsonl` | spadek ≥ 10% albo poniżej kwoty z briefu; prognoza wzrostu z Google Flights |
| noclegi | rezerwacja z darmowym anulowaniem, potem co 2–3 dni sprawdzenie tej samej daty przez przeglądarkę Hermesa | taniej o ≥ 10% przy tych samych warunkach → propozycja: zarezerwuj nowy, anuluj stary (za zgodą) |
| bilety z limitem | sprawdzenie otwarcia sprzedaży | sprzedaż otwarta / kończą się miejsca |

Koniec monitoringu: zakup, koniec darmowego anulowania albo T‑2. Alert zawsze z linkiem do zakupu i ceną sprzed.

## Eksport

| Dokąd | Format | Uwagi |
|---|---|---|
| kalendarz | plik `.ics` z wydarzeniami (przeloty, zameldowania, rezerwacje, terminy anulowania, zadania T‑30…T‑1), w opisie link do raportu | zapis bezpośredni tylko do osobnego kalendarza „Wyjazdy” (decyzja Filipa); pozostałe kalendarze Filipa są tylko do odczytu |
| mapy | link Google Maps na każdy dzień (`/maps/dir/?api=1&…&waypoints=…`) + plik CSV/KML wszystkich punktów do importu w Google My Maps (warstwy: noclegi, atrakcje, jedzenie, transport) | punkty z nazwą i adresem, nie tylko współrzędne |
| na telefon offline | PDF „segregator” (plan dni, rezerwacje, kontakty awaryjne, kopie kart pokładowych) w Matrix | |
| Notion | strona raportu w bazie raportów (wg K76 §4.6) | |

## Wyjście (wg [standardu raportu K80](../szablony/standard-raportu.md))

„W skrócie” ze stałymi etykietami:

- **Rekomendacja:** Jedziemy X–Y do Z. Dojazd … za … zł, nocleg … za … zł (darmowe anulowanie do …); razem ok. … zł z rezerwą.
- **Dlaczego:** najważniejsze 1–2 powody (czas dojazdu, cena, wygoda z dzieckiem).
- **Alternatywa:** druga opcja (inny nocleg/dojazd/termin) i kiedy ją wybrać.
- **Pewność:** wysoka | średnia | niska (np. średnia, bo ceny lotów zmienne).
- **Teraz zrób:** 1) … do dnia …, 2) … (linki do zakupu/rezerwacji).

„Porównanie”: min. 2 warianty (np. dojazd lub nocleg) z kolumną „koszt”. W „Szczegółach” jako `###`: tracker
rezerwacji, plan dzień po dniu (A/B/C), atrakcje, noclegi, transport, formalności, pogoda, budżet. „Pokrycie
pól” ma wiersz dla każdego pola z tabel powyżej (pola „jeśli dotyczy” wypełnić „nie dotyczy”). Pliki: `.ics`,
CSV/KML, PDF.

## Lekcje z planu Bergamo/Como/Zadar (sierpień 2026)

Źródło: przegląd sesji [A09](https://app.notion.com/p/3faee453d19e813db3bdcc7f9fbbb8bb) i strona w
[Bazie wiedzy](https://app.notion.com/p/3f0ee453d19e81969620cbcf6f06bcfb).

| Co poszło źle | Reguła w tym typie |
|---|---|
| Podagent w 1 minutę napisał 27 KB planu „na oko” i założył dzienny przejazd Como → Zadar; realnie był to nocny FlixBus 16:30 → 06:00 (inny dzień przyjazdu, jedna noc bez hotelu) | Fakt tylko ze źródła z tego biegu; bramka „spójność logistyki” sprawdza noce w drodze i dzień przyjazdu |
| Lotu Ryanair BGY → ZAD nie dało się sprawdzić (API 409), a wynik i tak trafił do planu | Pole „nie znaleziono” z linkiem do ręcznego sprawdzenia + `[niezweryfikowane]`; zapasowe źródło (Google Flights) |
| Filip prosił o prompt, dostał plan | Krok 1 (brief): ustalić, co jest produktem (plan, prompt, lista opcji) |
| Plan został jako plik na VM w katalogu repo (w `.gitignore`), a w Notion zostało streszczenie pierwszej, błędnej wersji (zły termin 02.09, dzienny przejazd) | Jedno miejsce docelowe (Notion + PDF na telefon); przy poprawce aktualizować to samo miejsce, starą wersję oznaczyć jako nieaktualną |
| Ta sama sesja zeszła potem na zmiany systemu i urosła do 14,6 mln tokenów | Research wyjazdu w osobnej sesji/karcie, zamykanej po dostarczeniu; etapy C–F jako osobne crony |
| Rezerwacje willi (Balbianello, Carlotta) zostawione „do potwierdzenia na miejscu” | Tracker rezerwacji z datą „do kiedy”; bilety z limitem miejsc sprawdzane w etapie A |
| Ceny „orientacyjne, stan sierpień” | Limity świeżości i ponowne sprawdzenie zwycięzców w dniu wysłania |
| Dobre: główna sesja poprawiła plan z PDF‑ów rozkładów Navigazione Laghi i API FlixBus | Rozkłady przewoźników (także PDF) są źródłem pierwotnym; agregatory tylko do mapy opcji |

## Ewaluacje (F3)

1. **Powtórka Bergamo/Como/Zadar** (1–9.09, przylot 22–23 do BGY, z wariantami pogodowymi): porównanie z
   planem z 28.08 (plik `plan-wycieczka-wlochy-zadar.md`); oceniane: zweryfikowane ceny i godziny, wykonalność
   dni, ostatnie kursy, kąpiele; test zaliczony tylko, jeśli Como → Zadar wychodzi jako przejazd nocny.
2. **Weekend w Polsce z dzieckiem** samochodem, budżet 1 500 zł: noclegi z łóżeczkiem, plan B na deszcz.
3. **City break poza UE** (np. Londyn): e‑zezwolenia dla każdej osoby, roaming, waluta, ubezpieczenie.

Rubryka: kompletność pól, fakty ze źródłem i datą, wykonalność (bramki), zgodność z budżetem, „czy Filip musiał
czegoś szukać sam”.
