# Typ: monitoring (v0.1)

Cykliczne śledzenie: ceny, promocje, wydarzenia, nowości, sytuacje na żywo. Pierwszy przebieg to zwykły
research typu bazowego (zakupy, wycieczka, wiedza…); ten plik opisuje kolejne przebiegi.

## Pytania startowe (max 3)
- Co śledzić i jaki jest próg alertu (cena ≤ X, nowa data, zmiana statusu)?
- Jak często i do kiedy?

## Jak to działa
1. Źródła śledzone rejestruj jako decyzję w bibliografii z właściwą klasą zmienności:
   `bib.py decyzja dodaj <ID> --tytul … --klasa na-zywo|krytyczna|ceny|news|zwykla|kod --zrodla URL…`.
   Klasy: `na-zywo` 15 min (sytuacja dynamiczna, np. pożar), `krytyczna` 1 h (sytuacje krytyczne i awaryjne),
   `ceny`/`news` 1 dzień, `zwykla` 7 dni, `kod` 30 dni.
2. Cron Hermesa `bib-sprawdz-decyzje` (bez tokenów, co 15 min) pobiera tylko źródła, którym minął czas klasy,
   i pisze do Filipa tylko wtedy, gdy coś się zmieniło.
3. Gdy próg wymaga zrozumienia treści (np. „czy pożar jest opanowany”), dopiero zmiana źródła uruchamia agenta,
   który czyta nowe treści i pisze krótki raport „było × jest × zmiana”.

## Pola obowiązkowe
| Pole | Uwagi |
|---|---|
| było | stan z poprzedniego przebiegu, z datą |
| jest | stan teraz, z datą i źródłem |
| zmiana | co się zmieniło i czy przekracza próg |
| co zrobić | krok z linkiem albo „nic” |

## Wyjście
Wiadomość Matrix (max 5 linii) tylko przy zmianie; pełny raport tylko na prośbę albo przy przekroczeniu progu.
