# decision_log — CI: rozszerzenie paths/workflow poza video-digest

- Zadanie: t_01ce6f6c (**t_14166e19** to poprawiona karta z właściwym workspace, praca dostarczona stąd)
- Repo: ScuraUrsa/hermes-enhancements, branch `wt/t_01ce6f6c`, baza: `origin/master` @ d6a407d
- Data: 2026-11-04
- Kontekst (pomiar run77, karta t_793de5ac): `.github/workflows/test.yml` wchodzi na master z PR #44 jako filtr wyłącznie `video-digest/**` — 6 projektów (`cheap-route`, `home-inventory`, `trace-dashboard`, `wyjscie`, `bench`, `skills/research-kit`) nigdy nie dostaje żadnego checka.

## Decyzje

- **D1 — bazą jest origin/master (d6a407d), plik workflow dodany w całości** (treść = wersja z PR #44 rozszerzona o nowe joby). Uziemienie: workflow nie istnieje na masterze; gałąź uziemiona na branchu #44 byłaby zależna od losowo przeglądanej karty, a PR z bazą master daje czytelny diff „finalny stan pliku”. Uwaga dla merge: jeśli #44 wejdzie pierwszy, wystąpi add/add na `.github/workflows/test.yml` — rozwiązać przyjmując wersję z tego PR (superset).

- **D2 — jeden workflow, matrix jobów per projekt (`fail-fast: false`)**. Każdy projekt ma własny, nazwany check (`test (video-digest)`, `test (cheap-route)`, …) — czerwony `trace-dashboard` nie może maskować zielonego `video-digest` ani odwrotnie. Zero `continue-on-error` w pliku. Świadomie NIE zastosowano per-job path filtering (dorny/paths-filter): suite mają 0,15–3 s, filtr zwiększałby złożoność bez mierzalnej oszczędności.

- **D3 — polecenia install/test per projekt zweryfikowane lokalnie (Python 3.11.17, świeży venv, master @ d6a407d), nie założone**:

  | projekt | install | target | wynik lokalnie |
  |---|---|---|---|
  | video-digest | `pip install -e . pytest` | `tests` | 84 pass, 1 skip (4× green CI na PR #44) |
  | cheap-route | `pip install pytest` | `tests` | 19 pass, 0.15 s |
  | trace-dashboard | `pip install pytest` | `tests` | 3 pass, 0.20 s |
  | home-inventory | `pip install pytest` | `.` | 18 pass (test_dom.py), 2.63 s |
  | skills/research-kit | `pip install pytest` | `testy` | 43 pass, 0.30 s |

  Deps: pliki testowe wszystkich projektów spoza video-digest importują wyłącznie stdlib + pytest (+ moduły z roota projektu: `dom`, `dom_web`, `collect`, `wyjscie`, `bib`) — sprawdzone w git show na headach PR #52/#62/#60/#42/#64. `pip install -e .` tylko dla projektów z pyproject.toml (video-digest; bench ma pyproject w PR #6).

- **D4 — guard obecności zamiast bezwarunkowego joba dla `wyjscie/` i `bench/`**: oba katalogi **nie istnieją na masterze** (przychodzą w całości via PR #42 / #6). Job sprawdza `[ -d "$proj" ]` i przy braku kończy się `::notice` + exit 0 (widoczny w logach, odróżnialny od zielonego przebiegu). **Nie jest to continue-on-error ani wyciszenie testów**: każdy suite, który faktycznie wystartuje, normalnie czerwieni job. Od momentu włączenia katalogu na master guard staje się martwy i job odpala zwykłą wersję.

- **D5 — `PYTHONPATH=.` na poziomie job**: testy projektów importują moduły z roota projektu; dla video-digest/bench to bezszkodowy dubel instalacji `-e`.

- **D6 — home-inventory: `pytest .` zamiast sztywnej listy `test_dom.py test_labels_web.py`**: `test_labels_web.py` nie ma na masterze (przychodzi z PR #60); `pytest .` zbiera wszystkie `test_*.py` w projekcie i podbierze go automatycznie, bez przeróbki workflow po merge #60.

- **D7 — `paths:` obejmują 7 katalogów z tabeli pomiaru + `.github/workflows/**`; świadome pominięcia `POV/`, `travel/`, `docs/`** (brak testów — dodanie ich dawałoby skip/noise bez wartości, sprzeczne z kartą).

  | projekt | stan testów na masterze @ d6a407d | source PR |
  |---|---|---|
  | video-digest | 19 plików test*, 84 pass 1 skip | #44 (workflow) |
  | cheap-route | tests/test_router.py, 19 pass | #52 |
  | trace-dashboard | tests/test_collect.py, 3 pass | #62 |
  | home-inventory | test_dom.py, 18 pass; test_labels_web.py dopiero #60 | #60 |
  | wyjscie | brak katalogu na masterze → guard skip | #42 |
  | bench | brak katalogu na masterze → guard skip; bench/tests/test_harness.py + pyproject na #6 | #6 (draft) |
  | skills/research-kit | testy/test_bib.py + testy/test_waliduj_raport.py, 43 pass | #64 |

## Weryfikacja

- Lokalnie (CI-parity: świeży venv python3.11, `pip install pytest`, `PYTHONPATH=.`, dokładne komendy jobów): 19 / 3 / 18 / 43 pass — patrz D3.
- CI (ubuntu-latest): przebieg tego PR — link w opisie PR; `gh pr checks` wklejone do opisu PR po zielonym rozbiegu. Zero `continue-on-error`, zero skracanych/komentowanych asercji.

## Poza zakres / świadome nie-robinia

- Dodać testy: nie (karta o CI; testy przychodzą w PR-ach projektów).
- Maskować czerwienie: nie (D2/D4 to jedyne mechanizmy; guard nie dotyka zbiorów istniejących).
- Per-job path filtering dorny: świadome nie-robienie (D2).
- Dodanie POV/, travel/, docs/ do paths: nie (D7).
- Merge: human gate (Filip) — zgodnie z regułą dostawy.

## Follow-upy

- Po merge #44: rozwiązać add/add na test.yml przyjmując wersję tego PR (D1).
- Gdy suite urosną (np. video-digest > min), wrócić do per-job path filtering jako osobna karta.