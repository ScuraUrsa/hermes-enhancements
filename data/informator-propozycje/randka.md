# Typ: randka (v0.1, zatwierdzone przez Filipa 29.10, K77)

Używaj dla: randki we dwoje, wieczoru „tylko my”, rocznicy, niespodzianki. Wyjście z dziećmi to osobny typ
[`wyjscie-rodzinne`](wyjscie-rodzinne.md) (decyzja Filipa 29.10). Wyjazd z noclegiem to typ `wycieczka`.
Tryb domyślny: **Standard**. Szybki: „gdzie dziś na kolację” w znanej okolicy. Głęboki: rocznica,
oświadczyny, niespodzianka z kilkoma elementami.

Plan i uzasadnienie: [plany/research/2026-10-23-randki.md](../../../2026-10-23-randki.md).

## Procedury wspólne (używaj, nie powielaj)

Randka składa się z trzech procedur, które są osobnymi plikami i służą też innym typom (decyzja Filipa 25.10):

| Krok randki | Procedura | Status |
|---|---|---|
| szukanie i ocena lokali, kina, rekreacji | [`miejsca`](miejsca.md): pytania, pola, źródła, bramka godzin i cen | szkic v0.1 |
| dojazd i powrót (auto, parking, taxi, komunikacja, hulajnogi, pociąg; z wyprzedzeniem albo „na już”) | [`trasa`](trasa.md): odcinki wieczoru, opcja + alternatywa, parking, `powrot.ostatni_wygodny`, `kto_prowadzi` | szkic v0.1 (K107, wątek [Zaplanować trasę z A do B](#cmsg_015HTwbUuT8LqRHP4MjSVwTE7Dsaj2bQYvQjEGnVw4z3eM)) |
| przygotowanie do wyjścia (pogoda, z kim i jaka okazja, strój z tego, co mamy, co spakować, rzeczy dla dziecka) | wyjście z domu: `wyjscie.py plan --okazja randka --miejsce … --trasa-json … --dodaj …` → pogoda, strój, lista, `szykuj_od`, `wyjazd` | w budowie (K108, [hermes-enhancements PR #42](https://github.com/ScuraUrsa/hermes-enhancements/pull/42), wątek [Przygotować wyjście z domu](#cmsg_015HTwbUuT8LqRHP4MjSVwTE3hUSyysGvS3zS6xQ8fZ4TV)) |

Ten plik dodaje tylko to, co jest typowe dla randki: okno opieki nad dzieckiem, nastrój, plan wieczoru
z kilku miejsc, historię pary, zgody na działania i podsuwanie pomysłów. Dopóki wyjście z domu nie jest
gotowe, pole „pogoda” wypełniaj jak niżej.

## Pytania startowe (max 3, tylko gdy zmieniają wynik)

Najpierw przeczytaj `kontekst/filip.md` i historię randek (Notion „Randki”, sekcja niżej). Pytaj tylko o to,
czego tam nie ma albo co jest inne niż zwykle. Kolejność ważności:

1. **Kiedy i ile czasu?** Dzień, godzina startu, do której najpóźniej (zależy od opieki nad dzieckiem).
2. **Kto zostaje z dzieckiem?** Domyślnie jedna z babć albo ciocia (lista opiekunów na prywatnej stronie Notion
   [Profil randek](https://app.notion.com/p/403ee453d19e81caa1e5c8af0dd7396c), decyzja Filipa 24.10); opiekunka z serwisu tylko na prośbę; albo dziecko jedzie z nami.
3. **Nastrój i budżet?** Jedno zdanie, np. „spokojnie i blisko, do 300 zł” albo „coś nowego, możemy wydać więcej”.

Gdy brak odpowiedzi, nie czekaj. Domyślne z `kontekst/filip.md`: najbliższy piątek lub sobota 18:00–22:30,
budżet średni na dwie osoby, nastrój „coś nowego, ale bez stresu”, start i powrót **z domu** (chyba że Filip
poda inne miejsce), dojazd do 30 min. Wypisz założenia na górze.

**Gust to waga, nie filtr** (decyzja Filipa 30.10): to, że Ala czegoś nie lubi (np. koncerty), nie dyskwalifikuje
pomysłu ani rzeczy podobnych (operetka, musical, stand-up z muzyką). Pokazuj je w raporcie jako opcje dodatkowe
z krótką adnotacją („Ala zwykle nie lubi koncertów, ale …”), bo może trafić się perełka, zespół albo temat, który
jej podejdzie. Tak samo pomysł podobny do już zrobionego (inne spa, inna sala bilardowa) nie odpada, tylko jest
oznaczony jako „podobne do …”. Wykluczaj tylko twarde przeszkody: zamknięte w terminie, poza sezonem, za daleko,
niezgodne z dietą lub zdrowiem.
Ta sama aktywność w różnych miejscach to normalne (Filip 30.10): bilard, kręgle czy spa wybieraj w miejscu, które
najlepiej pasuje do logistyki danego wieczoru (skąd startujemy, gdzie kolacja, kto prowadzi), z rejestru atrakcji K128.

Ograniczenia zbieraj z profilu, nie pytaj o nie za każdym razem: dieta i alergie obojga, czego nie lubią
(głośno, tłum, horrory…), dostępność (schody, buty na obcasie, pogoda), alkohol (kto prowadzi), reguły
timeplane (np. „po 20:00 tylko rodzina” oznacza, że randka jest w porządku, ale praca nie).

## Pola obowiązkowe (tabela pozycji × pól)

Pozycje: 6–10 kandydatów z różnych kategorii (kolacja, kultura, ruch, warsztat, plener, „w domu”),
z których w raporcie zostają **3 propozycje**: (A) sprawdzona i spokojna, (B) coś nowego, (C) niespodzianka
albo tańsza. Każda propozycja to **plan wieczoru**, nie pojedynczy lokal (np. spektakl 19:00 → kolacja
21:15 obok teatru).

| Pole | Uwagi |
|---|---|
| plan godzinowy | wyjście z domu, dojazd, start, przerwa, koniec, powrót; mieści się w oknie opieki nad dzieckiem |
| miejsce i jego pola | wszystkie pola obowiązkowe z [`miejsca`](miejsca.md) dla każdego miejsca w planie wieczoru |
| menu / repertuar i ceny | przykładowe dania z cenami lub cena biletu; szacunkowy koszt całości na 2 osoby |
| dieta i ograniczenia | czy pasuje do diet i ograniczeń z profilu |
| rezerwacja | jak (link do systemu, telefon), czy są wolne miejsca w terminie, do kiedy trzeba, zadatek, polityka anulowania |
| dojazd | z procedury [`trasa`](trasa.md) (dom → miejsce → miejsce → dom, o godzinach z planu); `kto_prowadzi`, bramka alkoholu, ostatni wygodny powrót |
| atmosfera | głośność, oświetlenie, stolik przy oknie, czy można porozmawiać |
| plan B | konkretny zamiennik w pobliżu na deszcz, brak miejsc lub odwołanie |
| promocje i punkty | Restaurant Week, Fine Dining Week, karty i punkty z profilu zakupowego (K79), vouchery |
| opieka nad dzieckiem | kto, od–do, koszt (opiekunka), czy trzeba zarezerwować |
| historia | czy byliśmy tam już, jak oceniliśmy; nowość czy sprawdzone |
| dlaczego to | jedno zdanie, które łączy propozycję z nastrojem i historią |

Dodatkowo w raporcie raz, nie per pozycja:

| Pole | Uwagi |
|---|---|
| wydarzenia w terminie | lista 5–10 wydarzeń z dnia randki w promieniu dojazdu (koncerty, teatr, stand-up, wystawy, kino, festiwale), z ceną i linkiem do biletu |
| pogoda | prognoza na wieczór (IMGW / Meteo ICM) z datą sprawdzenia; wpływ na plan |
| opcjonalnie: temat rozmowy | jedno pytanie z rotacji „Eight Dates” (Gottman), tylko na prośbę Filipa (domyślnie wyłączone) |

## Źródła domyślne (lokalne najpierw)

| Co | Źródła |
|---|---|
| lokale, oceny, godziny | Google Maps (strona miejsca, opinie, „popularne godziny”); strona i Instagram lokalu (menu, zamknięcia); OpenStreetMap/Overpass jako darmowe uzupełnienie godzin |
| jakość kuchni | [Przewodnik Michelin](https://guide.michelin.com/) (od 2026 selekcja z całej Polski), Gault&Millau Polska (edycja 2026, 251 ocenionych restauracji), lokalne portale miejskie i rankingi |
| rezerwacje | system na stronie lokalu, [MojStolik](https://mojstolik.pl/), [restaurantweek.pl](https://restaurantweek.pl/) (festiwale z menu stałą ceną), telefon |
| wydarzenia | [Going.](https://goingapp.pl/), [eBilet](https://www.ebilet.pl/), [Biletyna](https://biletyna.pl/), [KupBilecik](https://www.kupbilecik.pl/), strony teatrów i filharmonii, miejskie kalendarze wydarzeń, wydarzenia na Facebooku jako sygnał |
| kino | repertuar [Cinema City](https://www.cinema-city.pl/), [Multikino](https://multikino.pl/), [Helios](https://www.helios.pl/) i kin studyjnych; [Filmweb](https://www.filmweb.pl/) do ocen filmu |
| dojazd | Google Maps trasy (auto, komunikacja), jakdojade.pl |
| pogoda | [IMGW](https://meteo.imgw.pl/), [Meteo ICM](https://www.meteo.pl/) |
| opiekunka | kontakty z profilu (rodzina, sprawdzone opiekunki); w razie braku: [niania.pl](https://niania.pl/), [Babysits](https://www.babysits.com/), cenniki np. [kb.pl](https://kb.pl/cenniki/miejskie/opiekunka/slaskie) |
| pomysły | historia randek, lista „chcemy kiedyś”, [ćwiczenie Greater Good](https://ggia.berkeley.edu/practice/exciting_activities_for_couples) (nowe i ekscytujące aktywności), rozmowy z „Eight Dates” |

**Wydarzenia w terminie** (targi, festiwale, jarmarki, wydarzenia hobby, biletowane i z wejściem przy drzwiach): zawsze według wspólnej procedury [`wydarzenia`](wydarzenia.md) (prośba Filipa 4.11, po pominięciu ALEgramy i Targów Mrocznych Unikatów 7–8.11).

Bramka źródeł dla tego typu: każda z 3 propozycji ma co najmniej jedno źródło **pierwotne** (strona lub
system rezerwacji lokalu, strona organizatora) dla godzin i ceny, nie tylko agregator. Opinie z Google to
źródło typu `inne`, nie dowód godzin otwarcia.

## Świeżość

- Godziny otwarcia, wolne stoliki, bilety, repertuar: sprawdzić **w dniu wysłania raportu** i ponownie
  w dniu randki rano (przypomnienie Hermesa, niżej).
- Ceny, menu: 30 dni. Oceny i opinie: 6 miesięcy. Pogoda: 48 h przed.

## Wyjście

Na górze (5 linii): „Proponuję A: <plan w jednym zdaniu>, ok. <kwota> zł, rezerwacja <jak/do kiedy>.
B i C niżej. Opieka: <kto, od–do>. Pogoda: <krótko>.” Dalej:

1. Tabela 3 propozycji (plan godzinowy, koszt na 2 osoby, dojazd, rezerwacja, plan B, link do mapy).
2. Wydarzenia w terminie (lista z linkami do biletów).
3. Założenia i co sprawdzono kiedy.
4. **Kolejne kroki do zatwierdzenia** jako przyciski lub numerowana lista: „1. Zarezerwuj stolik w A na
   19:00”, „2. Kup 2 bilety”, „3. Wpisz do kalendarza i przypomnij”, „4. Napisz do <opieka>”.

Miejsce: Notion „Raporty” (typ `randka`) + wpis w bazie „Randki” ze statusem `propozycja`; krótka wiadomość
w Matrix. Raport **nie trafia do git** (dane prywatne).

## Działania Hermesa po raporcie (zawsze za zgodą Filipa)

Nic nie jest rezerwowane, kupowane ani wysyłane do innych osób bez wyraźnego „tak” Filipa na konkretny
punkt. Zgoda na jeden punkt nie obejmuje innych.

| Działanie | Jak | Zgoda |
|---|---|---|
| wydarzenie w kalendarzu | Google Calendar Filipa (wspólny kalendarz, jeśli jest), z adresem, linkiem do mapy i planem B w opisie | tak, raz na randkę |
| przypomnienia | dzień przed: potwierdź opiekę i rezerwację; w dniu rano: ponowne sprawdzenie godzin, pogody i biletów; 1 h przed wyjściem: czas dojazdu | wchodzi w zgodę na kalendarz |
| rezerwacja stolika | formularz online lub system rezerwacji przez przeglądarkę Hermesa; telefon tylko jako zadanie dla Filipa (timeplane) | tak, osobno |
| zakup biletów | tylko z linkiem do koszyka do zatwierdzenia; płatność zawsze Filip | tak, osobno |
| wiadomość do opiekunki lub rodziny | szkic do zatwierdzenia, wysyła Filip albo Hermes po „wyślij” | tak, osobno |
| zadania dla Filipa | rzeczy, których Hermes nie zrobi (telefon, kwiaty, prezent): zadanie timeplane z linkami | automatycznie (reguła projektu) |

## Historia randek (pamięć)

Baza Notion [Randki](https://app.notion.com/p/e0947a50200345f9937bc76a9c6fbe4b) (prywatna), jeden wiersz na randkę lub propozycję:

| Właściwość | Typ |
|---|---|
| Data | data |
| Status | propozycja / zaplanowana / odbyła się / odwołana |
| Rodzaj | kolacja, kultura, ruch, warsztat, plener, w domu, wyjazd |
| Miejsca | tekst + linki |
| Koszt | liczba (zł) |
| Opieka | kto |
| Ocena Filipa (1–5) i notatka | liczba, tekst |
| Wrócić? | tak / nie / może |
| Raport | link do raportu |

Po randce (następny dzień, 10:00) Hermes pyta w Matrix: „Jak było w <miejsce>? Ocena 1–5 i czy wracamy?”
Odpowiedź aktualizuje wiersz. Lista „chcemy kiedyś” to wiersze ze statusem `pomysł`, dopisywane z rozmów
i linków (np. z K-link-capture).

Import z maili (bilety, rezerwacje) to tylko kandydaci: zakup może być prezentem dla kogoś innego (np. bilety
dla rodziców), wyjazdem rodzinnym albo wyjściem ze znajomymi. Wpisy z Gmaila zaznacz źródłem `Gmail`
i nowe, przyszłe pozycje potwierdź z Filipem, zanim uruchomisz dla nich przypomnienia lub research.

Raport korzysta z historii tak: nie proponuje miejsca ocenionego na 1–2; propozycja A może być sprawdzona
(ocena 4–5), B musi być nowa; unika powtórki tego samego rodzaju trzy razy z rzędu.

## Rejestr szablonów (odtwarzanie randek)

Prywatna baza Notion [Szablony randek](https://app.notion.com/p/9b17eaa07e404c9d9ac34b8290047cc1) (pod Profilem
randek, prośba Filipa 29.10). Jeden wiersz to pomysł, który można powtórzyć w innym terminie; każde wykonanie
to wiersz w Randkach powiązany relacją `Realizacje` ↔ `Szablon`.

| Właściwość | Znaczenie |
|---|---|
| Status | pomysł / sprawdzony / ulubiony / odrzucony |
| Ala | lubi / neutralnie / nie lubi / nie wiadomo (gust partnerki; to waga, nie filtr: „nie lubi” obniża pozycję, ale nie wyklucza, decyzja Filipa 30.10) |
| Rodzaj, Dla kogo | jak w Randkach; `Dla kogo = z Teosiem` to szablony typu `wyjscie-rodzinne` |
| Parametry | co zmienia się przy odtworzeniu, w nawiasach klamrowych: `{pokój}`, `{restauracja}`, `{spektakl}`, `{godzina}` |
| Wariant rozszerzony | jak zrobić z tego dłuższe wyjście (drugi punkt, cały dzień, nocleg) |
| Czas (h), Koszt bazowy (zł), Pora roku, Kiedy, Rezerwacja | do filtrowania pod termin, budżet i okno opieki |
| Odtwarzaj co, Ostatnio, Następna okazja | rytm powtórek; „Następna okazja” to dzień, w którym Hermes proponuje szablon |
| Ocena | średnia z realizacji (1–5) |

Użycie w researchu: krok 1 to zapytanie do rejestru (pora roku i dzień pasują, `Następna okazja` ≤ termin
albo pusta; status `odrzucony` i Ala = „nie lubi” nie wykluczają, tylko trafiają niżej jako opcja dodatkowa). Propozycja A może być odtworzonym szablonem z nowymi
wartościami parametrów; B jest nowa i po raporcie trafia do rejestru jako `pomysł`. Po randce: `Ostatnio`
= data, `Następna okazja` = data + „Odtwarzaj co”, `Ocena` przeliczona. Nowe zainteresowania partnerki
(np. nazwy miejsc, które chce zapamiętać) zapisuj też w CRM kontaktów, pole „Likes / Dislikes” jej karty.

## Cykliczne podsuwanie pomysłów (monitoring)

Blueprint `monitoring` na bazie tego typu, w trybie Szybki:

- **Co 2 tygodnie w czwartek 12:00**: jeśli w kalendarzu nie ma randki w ciągu
  najbliższych 14 dni, Hermes wysyła 3 pomysły na najbliższy weekend (po jednym zdaniu, z ceną i linkiem)
  (co najmniej jeden z rejestru szablonów z `Następna okazja` w tym oknie) i pyta „planujemy?”. „Tak”
  uruchamia pełny research.
- **Alerty wydarzeń**: obserwowani artyści, teatry i festiwale (lista w profilu); nowa data w mieście lub
  start sprzedaży biletów → wiadomość. Festiwale sezonowe (Restaurant Week wiosna i jesień, Noc Muzeów,
  Fine Dining Week) przypominane 2 tygodnie przed startem rezerwacji.
- **Daty stałe**: rocznice, urodziny partnerki (z CRM kontaktów lub profilu) → przypomnienie 3 tygodnie
  wcześniej z propozycją researchu w trybie Głębokim.
- Limit: maks. 1 wiadomość tygodniowo z tego monitoringu, cisza, gdy randka jest już zaplanowana.

## Przypadki testowe (do F3)

1. „Piątek wieczorem, babcia do 23, coś nowego, do 400 zł.”
2. „Rocznica za 3 tygodnie, niespodzianka, budżet bez limitu, ona nie je mięsa.”
3. „Odtwórz escape room z rejestru w przyszły piątek, inny pokój niż ostatnio.”
