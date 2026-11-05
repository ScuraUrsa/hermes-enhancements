# Typ: wyjście rodzinne (v0.1, zatwierdzone przez Filipa 29.10, K126)

Używaj dla wyjść najbliższej rodziny **z dziećmi** na kilka godzin albo cały dzień: „gdzie w sobotę z Teosiem”,
„co robić w niedzielę, jak pada”, „wyjście, z którego my też coś mamy”. Randka we dwoje to typ
[`randka`](randka.md), wyjazd z noclegiem to `wycieczka`. Tryb domyślny: **Standard**. Szybki: „teraz,
w pobliżu, na 2 godziny”. Głęboki: urodziny dziecka, pierwszy raz w nowym typie miejsca, dzień z atrakcją za miastem.

Cel każdej propozycji: **dziecko i rodzice korzystają jednocześnie**. Plac zabaw, przy którym rodzice tylko
stoją, nie wystarcza; szukaj par „dziecko ma X, rodzice mają Y w tym samym czasie i miejscu” (sala zabaw
z dobrą kawiarnią, akwarium + spacer nad morzem, basen + saunarium na zmianę, muzeum kolei + wycieczka
pociągiem, restauracja z kącikiem dla dzieci).

## Procedury wspólne (używaj, nie powielaj)

| Krok | Procedura |
|---|---|
| szukanie i ocena miejsc | [`miejsca`](miejsca.md), w polach „dopasowanie do grupy” zawsze wiek i wzrost dziecka, wózek, przewijak, krzesełko, menu dziecięce |
| dojazd | [`trasa`](trasa.md) z bramką „dziecko”: fotelik, wózek w komunikacji, max. czas jednego odcinka, przesiadki |
| przygotowanie | `wyjscie.py plan --od … --do … --miejsce … --z-dzieckiem [--trasa-json …] [--dodaj …]` (K108): pogoda, strój Teosia i rodziców, długa lista z dzieckiem, `szykuj_od` |
| rejestr pomysłów | baza Notion [Szablony randek](https://app.notion.com/p/9b17eaa07e404c9d9ac34b8290047cc1), filtr „Dla kogo = z Teosiem” (ten sam rejestr co randki) |

Ten plik dodaje tylko to, co typowe dla wyjść z dzieckiem: rytm dnia dziecka, wiek w regulaminach,
korzyść dla rodziców i rotację pomysłów.

## Pytania startowe (max 2, resztę bierz z profilu)

1. **Kiedy i jak długo?** Dzień, od której do której (domyślnie najbliższa sobota albo niedziela, 3–4 h przed
   albo po drzemce).
2. **Czego potrzebujecie wy?** Jedno słowo, np. „odpocząć”, „poruszać się”, „zjeść coś dobrego”, „wyjść z miasta”.

Domyślne: start z domu (Gdańsk), dojazd do 30 min (do 75 min na wyjście całodniowe), budżet do 200 zł
na rodzinę, oboje rodzice. Wiek dziecka liczyć z daty urodzenia w CRM, nie z pamięci.

## Rytm dziecka (bramka planu)

- Drzemka: okno z prywatnego profilu dziecka (Notion). Okno jest zmienne (zależy od dnia i humoru), więc
  traktuj je jako przedział z marginesem i koryguj na bieżąco z tego, co Filip powie w dniu wyjścia. Plan nie
  wypada w drzemkę albo przewiduje drzemkę w wózku lub w aucie (dojazd w tym oknie to plus).
- Posiłki co 3 h, toaleta/przewijak w każdym miejscu, ciepłe miejsce pod dachem przy pogodzie poniżej 5°C lub deszczu.
- Jedna główna atrakcja na wyjście, nie więcej; 30–40% czasu wolne (bieganie, jedzenie, nuda).

## Pola obowiązkowe (tabela pozycji × pól)

Pozycje: 9–12 kandydatów z różnych kategorii (pod dachem, plener, zwierzęta, woda, ruch, kultura, za miastem,
jedzenie), w raporcie **3 propozycje** (Standard) albo **9** (gdy Filip prosi o listę pomysłów).

| Pole | Uwagi |
|---|---|
| co ma dziecko | konkretna atrakcja i czy pasuje do wieku (regulamin: „od 2 lat”, „strefa malucha 1–3”, wzrost) |
| co mają rodzice | kawa, jedzenie, spacer, sauna na zmianę, widok, coś dla siebie; bez tego pozycja odpada |
| godziny i dni | ze strony miejsca, z datą sprawdzenia; poniedziałki, święta (1.11, 11.11) |
| ceny | dorośli, dziecko (często gratis do 3 lub 5 lat), drugi opiekun; łączny koszt rodziny |
| plan godzinowy | wyjście, dojazd, atrakcja, posiłek, powrót; drzemka zaznaczona |
| udogodnienia | wózek, przewijak, krzesełko, szatnia, parking |
| dojazd | z `trasa` |
| plan B | na deszcz, tłok lub zamknięcie |
| historia | czy byliśmy, jak było (rejestr szablonów, pole „Ostatnio” i „Ocena”) |

## Źródła

Jak w [`miejsca`](miejsca.md), a dodatkowo: strony instytucji kultury z zajęciami dla najmłodszych (np.
[GCK Gdynia „Dla dzieci”](https://www.gck.gdynia.pl/dla-dzieci/)), regulaminy sal zabaw i basenów (wiek,
skarpetki, pieluchy do pływania), portal [Visit Gdańsk: atrakcje na niepogodę](https://visitgdansk.com/atrakcje-na-niepogode),
grupy rodziców jako sygnał. Blogi i agregatory to sygnał; godziny i ceny tylko ze strony miejsca.

**Wydarzenia w terminie** (targi, festiwale, jarmarki, wydarzenia hobby, biletowane i z wejściem przy drzwiach): zawsze według wspólnej procedury [`wydarzenia`](wydarzenia.md) (prośba Filipa 4.11, po pominięciu ALEgramy i Targów Mrocznych Unikatów 7–8.11).

## Wyjście

Notion (prywatnie, nie w git): strona raportu pod [Profil randek](https://app.notion.com/p/403ee453d19e81caa1e5c8af0dd7396c)
i wiersze w rejestrze szablonów z „Dla kogo = z Teosiem”. Na górze 3 linie: „Proponuję <A>: <dziecko ma …,
my mamy …>, ok. <kwota> zł, <godziny>.” Dalej tabela, plan B, kroki do zatwierdzenia (bilety, rezerwacja
stolika, wpis do kalendarza). Zakupy i rezerwacje tylko po „tak” Filipa na konkretny punkt (jak w `randka`).

## Pamięć i odtwarzanie

Każdy pomysł to szablon w rejestrze (parametry, wariant rozszerzony, „Odtwarzaj co”). Po wyjściu
Hermes pyta następnego dnia: „Jak było w <miejsce>? Ocena 1–5, wracamy?”, aktualizuje „Ostatnio” i „Ocena”.
Wiek dziecka zmienia dopasowanie: raz na kwartał przejrzyj szablony z „Dla kogo = z Teosiem” i oznacz te,
z których wyrósł, albo te, które właśnie stały się dostępne (np. „od 3 lat”).

## Monitoring

W tym samym cyklu co randki (co 2 tygodnie w czwartek 12:00, max 1 wiadomość tygodniowo): jeśli w weekend
nie ma planu rodzinnego, 2 pomysły z rejestru (jeden sprawdzony, jeden nowy) dopasowane do prognozy pogody.

## Przypadki testowe

1. „Niedziela po południu z Teosiem, pada deszcz, chcemy też odpocząć.”
2. „Sobota cały dzień, wyjedźmy z miasta, do 2 h jazdy.”
3. „Teraz, 2 godziny, w pobliżu, kawa dla nas.”
