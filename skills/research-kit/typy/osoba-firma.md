# Typ: osoba-firma (v0.1)

Sprawdzenie firmy, wykonawcy, sprzedawcy albo usługi przed umową lub zakupem. Nie dotyczy profilowania osób
prywatnych: tylko działalność gospodarcza i publiczne informacje związane z nią.

## Pytania startowe (max 3)
- Po co sprawdzamy (wykonawca remontu, sprzedawca, pracodawca, usługa)?
- Jaka kwota lub ryzyko wchodzi w grę?

## Pola obowiązkowe
| Pole | Uwagi |
|---|---|
| dane rejestrowe | KRS / CEIDG: forma, data założenia, status, adres, reprezentacja |
| VAT i biała lista | aktywny podatnik VAT, numer konta na białej liście (bez wpisywania numeru do raportu) |
| zaległości i upadłość | KRZ (Krajowy Rejestr Zadłużonych), monitory sądowe |
| opinie | Google, branżowe portale, fora; liczba, rozkład, najnowsze negatywne |
| sygnały ostrzegawcze | świeża firma, zmiany nazwy, brak adresu, ostrzeżenia UOKiK/KNF |
| ceny rynkowe | czy oferta odbiega od rynku |
| umowa | na co uważać w umowie dla tej branży |

## Źródła domyślne
[KRS](https://ekrs.ms.gov.pl), [CEIDG](https://aplikacja.ceidg.gov.pl), [Biała lista VAT](https://www.podatki.gov.pl/wykaz-podatnikow-vat-wyszukiwarka),
[KRZ](https://krz.ms.gov.pl), [UOKiK](https://uokik.gov.pl), [lista ostrzeżeń KNF](https://www.knf.gov.pl/dla_rynku/ostrzezenia_publiczne), opinie.

## Świeżość
Rejestry: dzień raportu. Opinie: 12 miesięcy (starsze tylko jako tło).

## Wyjście
Na górze: „Można / ostrożnie / nie” z jednym zdaniem dlaczego i listą sygnałów ostrzegawczych.
