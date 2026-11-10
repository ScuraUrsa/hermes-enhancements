# decision_log — merge-readiness 24 PR (run 77, karta t_793de5ac)

Data: 2026-11-04 UTC · Autor: reviewer · Zakres: read-only wobec cudzych PR-ów

## Kontekst decyzji

Na boardzie leżało 24 otwarte PR-y w `ScuraUrsa/hermes-enhancements`, w większości dostawa C2 (testy hermetyczne `video-digest`) z drugiej połowy października. Karty źródłowe są `blocked`, więc nikt nie wiedział, co z czym się dubluje, a gotowa praca leżała 11–25 dni. Celem było **jednoznaczne rozstrzygnięcie**, nie kolejny PR z testami.

## Decyzje

### D1 — „wchłonięte przez #48" mierzone treścią, nie ścieżkami

**Decyzja:** za superseded (koszyk C) uznaję PR tylko wtedy, gdy (a) występuje w historii `git log --merges pr48` **oraz** (b) jego dodane linie występują w blobach `pr48:<ścieżka>` (próg 98 %).
**Dlaczego nie po ścieżkach:** #55 ma `video-digest/tests/test_config.py`, które jest też w #48 — naiwne „te same pliki = duplikat" zakwalifikowałoby #55 do close, a #55 ma 30 testów, których w #48 nie ma (8 testów #48 vs 30 testów #55, nazwy rozłączne).
**Wynik:** 9 PR-ów z historią merge'y (100 % / 98 % pokrycia linii), a #55 zostaje w koszyku B.

### D2 — #44 przed #48, mimo że #48 jest większy

**Decyzja:** pierwszy w kolejności jest PR z workflow CI, nie bundle.
**Dlaczego:** `on: push: branches: [master]` + `paths: video-digest/**` sprawia, że każdy kolejny merge dotykający `video-digest/` jest weryfikowany na masterze **po fakcie**. Wejście #44 na końcu oznaczałoby, że 5 merge'y wchodzi bez żadnej siatki. #44 nie zmienia testów (84 pass przed i po), więc koszt wejścia pierwszego = 0.
**Odrzucona alternatywa:** „najpierw wszystkie zielone projektowe, potem CI" — dawało krótszy czas do pierwszego merge'a, ale pozbawiało 5 kolejnych merge'y bramki.

### D3 — #37 (`[high risk]`) → close, nie merge

**Decyzja:** mimo etykiety „high risk" #37 idzie do koszyka C.
**Dlaczego:** 407/407 dodanych linii `test_backlog.py` jest w #48, a #48 ma zmierzony przebieg (419 pass). Osobny merge #37 to duplikat + ryzyko konfliktowe bez zysku. Ryzyko „high" zostało już przetrawione w #48.

### D4 — #55 nie zamykam, mimo że częściowo dubluje

**Decyzja:** koszyk B (rework), nie C.
**Dlaczego:** 30 testów #55 kontra 8 w #48, nazwy rozłączne — realna dodatkowa wartość (unit-testy `deep_merge`, `read_file`, `defaults`). Ale na `master + #48` plik daje **8 failed + 5 errors**, więc nie jest merge'owalny bez przepisania. Zamknięcie zgubiłoby pokrycie; merge w obecnej formie dałby czerwony master.

### D5 — #32 → B, a jego test „venv ma backendy ASR" traktuję jako defekt, nie jako wymóg środowiska

**Decyzja:** #32 wymaga reworku (rebase + unia w `cli.py`/`config.py` + `skipif` na brak backendu), a nie „merge, bo lokalnie prawie zielono".
**Dlaczego:** test asertuje stan konkretnej maszyny, a workflow z #44 instaluje tylko `pip install -e . pytest` — po merge'u #44 ten test byłby wiecznie czerwony. To ta sama klasa błędu co naruszenia hermetyczności z koszyka C, więc nie może wejść jako „known flake".

### D6 — #49 (docs API.md) → A, ale ostatni w obszarze `video-digest`

**Decyzja:** merge'owalny od razu (0 konfliktów, docs only), ale w kolejności **po #48**.
**Dlaczego:** API.md powstał 2026-10-28 z bazy `37513c4`, a #48 dokłada zmiany w `cli.py` i `mcp_bridge.py`. Wejście po #48 pozwala jednym diffem sprawdzić dokument vs realne `--help`.

### D7 — #63 (bash mutujący `~/.claude/settings.json`) → A, ale dopiero po dowodzie

**Decyzja:** nie przenoszę do D; zamiast tego uruchomiłem installer dwukrotnie w sandboxie (`CLAUDE_CONFIG_DIR`, `BIB_DIR` w `/tmp`).
**Dlaczego:** PR dotyka pliku konfiguracyjnego użytkownika, więc „wygląda na idempotentny" nie wystarcza. Dowód: `rc=0` ×2, `settings.json` bit w bit identyczny po drugim runie, hooki `PreToolUse`/`PostToolUse` wpięte raz (dedupe po `bib_hook.py`), złe JSON-y zostawione nietknięte.

### D8 — zamknięcia koszyka C dopiero po merge'u #48

**Decyzja:** 9 PR-ów close'ujemy **po** wejściu #48, nie teraz, nie razem z digestem.
**Dlaczego:** dopóki #48 jest poza masterem, te gałęzie są jedynym miejscem, gdzie ta praca istnieje. Zamknięcie przed merge'em #48 zamieniłoby ryzyko konfliktowe na ryzyko utraty pracy.

### D9 — brak CI wyjaśniony dowodem strukturalnym, nie domysłem

**Decyzja:** przyczyną jest brak `.github/` w drzewie gałęzi PR (`origin/master` ma 0 plików `.github/`, workflow tylko w `pr44`), a nie brak runnera.
**Dlaczego:** `runs-on: ubuntu-latest` + 4 zakończone runy (2 success, 2 failure, ostatni success 2026-10-27T01:12:00, 45 s) dowodzą, że runner działa. Hipoteza „lab runners offline" (aktualna dla innego repo/workflow) zostałaby tu błędnie przeniesiona.
**Skutek uboczny zapisany jako dług:** filtr `paths:` pokrywa tylko `video-digest/**`, więc 7 projektów nigdy nie dostanie CI.

## Czego nie zrobiono

0 merge'y, 0 close'ów, 0 rebase'ów, 0 pushy do cudzych gałęzi, 0 linii kodu produktu. Potwierdzone: 24 otwarte PR przed i po, `headRefOid` każdego PR-a bez zmian, wszystkie 24 `MERGEABLE`.

## Pliki

- `docs/reviews/merge-readiness-hermes-enhancements-2026-11-04.md` — digest (tabela 24/24 + kolejność + dowód CI)
- `docs/reviews/decision_log_merge_readiness_run77_t_793de5ac.md` — ten plik
