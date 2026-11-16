# Plany Hermesa: jedno miejsce na research, plany i kolejkę

Utworzone 2026-10-22 na prośbę Filipa: wszystkie plany rozwoju i wdrożeń w jednej kolejce, a każdy
przyszły „zrób research” trafia tutaj.

## Co tu jest

| Plik / katalog | Do czego |
|---|---|
| [KOLEJKA.md](KOLEJKA.md) | **Jedna kolejka** wszystkich planów: kolejność, etap, priorytet, następny krok, kto. Tu się zaczyna. |
| [research/](research/) | Nowe wyniki researchu i plany, jeden plik na temat. |
| [infrastruktura/](infrastruktura/README.md) → repo [hermes-workspace/infra](https://github.com/ScuraUrsa/hermes-workspace/tree/claude/project-thread-5906j7/infra) | Co faktycznie stoi na laptopie, workerze lab-ubuntu i VM prod/stage/dev, wolne zasoby, linki do monitoringu, różnice dokumentacja vs stan faktyczny. |
| [decyzje.md](decyzje.md) | Rejestr decyzji Filipa o planach (wdrażamy / obserwujemy / odrzucamy / zamykamy temat). |
| [SZABLON.md](SZABLON.md) | Szablon nowego planu. |

Starsze plany zostały tam, gdzie były (np. `mega-dev/`, `unified-inbox/`, `grok-bot-parity/`), bo inne wątki
mają do nich linki. KOLEJKA.md linkuje do każdego z nich.

## Zasady dla każdego wątku, który robi research albo plan

1. **Gdzie zapisać.** `plany/research/RRRR-MM-DD-<temat>.md` (temat małymi literami, myślniki). Duże tematy
   z załącznikami (obrazki, skrypty): katalog `plany/research/RRRR-MM-DD-<temat>/` z `plan.md` w środku.
2. **Nagłówek pliku** (pierwsze linie, wg [SZABLON.md](SZABLON.md)): tytuł, data, wątek źródłowy (link
   `[tytuł](#cmsg_…)`), status, priorytet, ID w kolejce.
3. **Przed planem wdrożenia sprawdź infrastrukturę.** Przeczytaj [hermes-workspace/infra](https://github.com/ScuraUrsa/hermes-workspace/tree/claude/project-thread-5906j7/infra) (lista kontrolna w [infrastruktura/README.md](infrastruktura/README.md))
   i napisz w planie: na której maszynie to stanie, ile RAM/dysku/CPU/GPU zabierze, czy się mieści i na co
   wpłynie (inne usługi, backup, koszt, limity Ollama/Claude). Jeśli stan w tym pliku jest starszy niż 7 dni
   albo się nie zgadza, sprawdź na żywo (SSH jest dozwolone) i popraw opis hosta w tym repo.
4. **Każdy plan wdrożenia ma fazę utrzymania** (prośba Filipa z 22.10): jaki agent/profil Hermesa będzie
   to utrzymywał i obsługiwał (alerty, aktualizacje, naprawy, raport), z czego czyta stan i kiedy woła
   Filipa. Bez tej fazy plan nie jest kompletny.
5. **Dopisz się do kolejki.** Dodaj wiersz w [KOLEJKA.md](KOLEJKA.md) (nowe ID `K<numer>`, etap `plan`
   albo `czeka na Filipa`) albo zaktualizuj istniejący. Nie przestawiaj kolejności cudzych pozycji bez powodu.
6. **Nie nadpisuj cudzych zmian** (reguła Filipa z 22.10). Wspólnych plików (`KOLEJKA.md`, `decyzje.md`,
   `README.md` i każdego pliku, który edytuje więcej niż jeden wątek) nie zapisuj narzędziem Write/Edit ani `>`.
   Zawsze przez [narzedzia/plik_cas.py](narzedzia/plik_cas.py):
   1. `python3 /mnt/project-files/plany/narzedzia/plik_cas.py wersja KOLEJKA.md` → zapamiętaj sha i od razu
      przeczytaj plik (pracuj na tej wersji, kopię zmienioną zapisz w swoim katalogu roboczym);
   2. `python3 /mnt/project-files/plany/narzedzia/plik_cas.py zapisz KOLEJKA.md <sha> <twoja_kopia>`;
   3. wynik `ODRZUCONE` (kod 3) znaczy, że ktoś zmienił plik w międzyczasie: przeczytaj nową wersję, nanieś na
      nią swoje zmiany (nie kopiuj starej całości) i wróć do kroku 2 z nowym sha.
   W git tak samo: przed pushem `git fetch`; jeśli zdalna gałąź ma nowsze commity niż te, na których
   pracowałeś, najpierw je scal (`git pull --rebase` na własnej gałęzi albo merge), sprawdź wynik, dopiero
   potem push. Nigdy `push --force` na cudze zmiany.
7. **Decyzje Filipa** zapisz w [decyzje.md](decyzje.md) z datą, linkiem i warunkiem powrotu do tematu.
8. Plik ma być samowystarczalny: linki klikalne (Notion, PR, strony), bez sekretów, bez surowych danych
   prywatnych. Język: polski.

## Etapy w kolejce

`pomysł` → `research` → `plan` → `czeka na Filipa` (decyzja, zakup, logowanie) → `w budowie` (PR otwarty)
→ `live` (działa na prod) → `utrzymanie` (ma agenta) · poza ścieżką: `wstrzymane`, `odrzucone`, `scalone z K…`.

Priorytety jak w `hermes-enhancements/docs/chatgpt-ideas`: **P1** teraz, **P2** wkrótce, **P3** bez
pośpiechu, **P4** miło mieć / do decyzji, **P5** zaparkowane.

## Kopia w git

Kopia `plany/` jest w `hermes-enhancements/docs/plany/` (PR [#31](https://github.com/ScuraUrsa/hermes-enhancements/pull/31)),
żeby czytał ją też Hermes. Źródłem prawdy są pliki projektu; kopia idzie przez PR, z zasadą z pkt 6.
