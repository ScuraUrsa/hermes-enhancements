# Typ: decyzja-techniczna (v0.1)

Wybór narzędzia, usługi, biblioteki albo plan wdrożenia w homelabie Hermesa. Raport techniczny trafia do
`plany/research/RRRR-MM-DD-<temat>.md` według `plany/README.md` i `plany/SZABLON.md`, z wierszem w
`plany/KOLEJKA.md` (zapis wspólnych plików tylko przez `plany/narzedzia/plik_cas.py`).

## Pytania startowe (max 3)
- Jaki problem rozwiązujemy i jak poznamy, że działa?
- Na której maszynie ma stać (prod, dev, lab-w01) i ile zasobów wolno zabrać?
- Czy są ograniczenia: koszt, licencja, „nic publicznie”, tylko llama.cpp lokalnie?

## Pola obowiązkowe (tabela opcji × pól)
| Pole | Uwagi |
|---|---|
| co daje | funkcje istotne dla problemu |
| licencja i koszt | z datą cennika |
| popularność i utrzymanie | gwiazdki, ostatni release, liczba opiekunów |
| zasoby | RAM, dysk, CPU/GPU; czy się zmieści (infrastruktura: hermes-workspace/infra) |
| wpływ na inne usługi i backup | |
| bezpieczeństwo | ekspozycja sieciowa (tylko Tailscale), sekrety z Bitwarden |
| faza utrzymania | który agent Hermesa utrzymuje, co monitoruje, kiedy woła Filipa |

## Źródła domyślne
Dokumentacja oficjalna, repo GitHub (README, releases, issues), changelogi, benchmarki niezależne.

## Świeżość
12 miesięcy dla porównań; wersje i ceny sprawdzone w dniu raportu. Klasa decyzji w bibliografii: `kod`.

## Wyjście
Format planu z `plany/SZABLON.md` (sekcje 1–8) plus sekcja „Źródła”. Decyzja Filipa → `plany/decyzje.md`.
