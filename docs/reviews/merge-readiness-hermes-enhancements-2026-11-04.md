# Merge-readiness 24 otwartych PR — `ScuraUrsa/hermes-enhancements`

**Data pomiaru:** 2026-11-04 (UTC), run 77, karta `t_793de5ac`
**Baza:** `origin/master` = `d6a407d` (2026-11-01T12:45:48+01:00)
**Liczba otwartych PR w chwili pomiaru:** 24 (`gh pr list --state open`)
**Charakter karty:** read-only wobec cudzych PR-ów. 0 merge, 0 close, 0 rebase, 0 push do gałęzi innych kart.

---

## 1. Werdykt w skrócie

| Koszyk | Znaczenie | PR-y | Ile |
|---|---|---|---|
| **A** | merge teraz — brak konfliktu, testy zielone na dzisiejszym masterze | #44, #48, #54, #36, #49, #52, #62, #60, #64, #42, #63, #28 | **12** |
| **B** | merge **po #48**, wymaga rebase/przepisania (konflikt + dryf kontraktu) | #55, #32 | **2** |
| **C** | superseded przez #48 → **close** (dopiero po merge'u #48) | #33, #37, #38, #39, #40, #41, #45, #46, #47 | **9** |
| **D** | nie merge'ować — draft / wymaga review kodu i CI | #6 | **1** |

Suma: 24/24. Zero pominiętych.

Po wykonaniu planu: **12 merge'y + 9 close'ów + 2 reworki** → z 24 otwartych PR zostaje 0 (2 wracają jako zrebase'owane).

**Najstarszy PR rekomendowany do merge'a:** #28 „chore: Configure Renovate" (utworzony 2026-10-18, 16 dni).
**Najstarszy PR w ogóle:** #6 „hbench" (2026-10-09, 25 dni) — **draft**, koszyk D, nie do merge'a.
**Kolejność bezwzględna:** #44 → #48 (reszta koszyka A dowolnie, bez konfliktów).

---

## 2. Dlaczego 23 z 24 PR-ów nie mają żadnego checka CI — dowód, nie hipoteza

To **nie** jest brak runnera i **nie** jest „checki dopiero po merge'u". Przyczyna jest strukturalna i weryfikowalna:

1. **Na `master` nie ma ani jednego pliku `.github/`.**

   ```console
   $ git ls-tree -r --name-only origin/master | grep -c '^\.github/'
   0
   ```

2. **Workflow istnieje tylko w gałęzi PR #44.** `git ls-tree -r --name-only pr<N> | grep -c '^\.github/workflows/'` → `1` **wyłącznie dla pr44**, `0` dla pozostałych 23 gałęzi.

3. Workflow z #44 (`.github/workflows/test.yml`, 42 linie) ma wyzwalacze:

   ```yaml
   on:
     pull_request:
       branches: [master]
       paths:
         - 'video-digest/**'
         - '.github/workflows/**'
     push:
       branches: [master]
       paths:
         - 'video-digest/**'
         - '.github/workflows/**'
   ```

   `runs-on: ubuntu-latest`, `timeout-minutes: 15`, `setup-python 3.11`, `pip install -e . pytest`.

4. **Runner działa** — to nie jest problem infrastruktury. Wszystkie 4 runy tego workflow (wszystkie na gałęzi `wt/ci-hermes-enhancements`) się wykonały:

   | run id | branch | status | conclusion | created (UTC) | sha |
   |---|---|---|---|---|---|
   | 40431143208 | wt/ci-hermes-enhancements | completed | success | 2026-10-27T01:12:00 | 9c82f501 |
   | 40431026130 | wt/ci-hermes-enhancements | completed | failure | 2026-10-27T01:10:50 | ce5ee060 |
   | 40430694712 | wt/ci-hermes-enhancements | completed | success | 2026-10-27T01:07:35 | d6fc2323 |
   | 40430530997 | wt/ci-hermes-enhancements | completed | failure | 2026-10-27T01:06:00 | 093623a4 |

   `gh pr checks 44` → `test  pass  45s`. To GitHub-hosted runner, nie lab.

**Wniosek:** check pojawia się tylko wtedy, gdy plik workflow jest w drzewie gałęzi PR. Gałęzie 23 pozostałych PR-ów powstały przed #44 i nie zawierają `.github/`, więc GitHub nie ma czego uruchomić (`statusCheckRollup` = puste, nie „queued"). #44 jest checkiem `SUCCESS`, bo to jedyna gałąź z workflow.

**Skutek uboczny, który trzeba znać przed merge'em #44:** filtr `paths:` obejmuje wyłącznie `video-digest/**` i `.github/workflows/**`. Po merge'u #44 PR-y z `cheap-route/`, `home-inventory/`, `trace-dashboard/`, `wyjscie/`, `bench/`, `skills/` **nadal nie dostaną CI** — nie z powodu błędu, tylko z definicji filtra. To dług do zaadresowania osobną kartą (rozszerzenie `paths:`), a nie powód do blokowania #44.

**Drugi skutek:** `push: branches: [master]` + `paths: video-digest/**` oznacza, że **każdy merge PR-a dotykającego `video-digest/` uruchomi testy na `master` po merge'u**. To jest realna bramka post-merge i główny argument, żeby #44 wszedł pierwszy.

---

## 3. Metodyka (żeby liczby było można odtworzyć)

- Konflikty: `git merge-base` + `git merge-tree` (git 2.34, bez `--write-tree`) na parach PR-ów, oraz **trójdrożny merge per plik** (`git merge-file -p --stdout ours base theirs`) — 16 PR-ów dotykających `video-digest/` = 120 par.
- Dryf względem bazy: `git rev-list --left-right --count origin/master...pr<N>`.
- Zieloność: świeży `git worktree` **od `origin/master`**, `git merge --no-ff pr<N>`, potem rzeczywisty przebieg `python -m pytest` w `video-digest/` (albo w katalogu projektu), venv `/home/ubuntu/crewai-orchestrator/.venv` (Python 3.11, pytest 9.1.1), `PYTHONPATH=.`.
- „Wchłonięcie" przez #48: nie po nazwach plików, tylko po **treści** — dla każdego pliku PR-a liczone były dodane linie i sprawdzane, czy występują w blobie `pr48:<ścieżka>`. Same zestawy ścieżek są mylące (np. #55 ma `test_config.py`, które występuje też w #48, ale z inną treścią).
- Uwaga na pułapkę: lokalny ref `master` w tym worktree jest **stary** (`37513c4`, 2026-10-11). Wszystkie pomiary robione względem `origin/master` = `d6a407d`. Diff względem starego `master` pokazuje ~30 fałszywych „dodań" w każdym PR (re-import kodu, który master dodał później).

Stan `master` bez żadnego PR-a (baseline): **84 passed, 1 skipped** (27.9 s).

---

## 4. Tabela 24/24

Legenda koszyków: **A** merge teraz, **B** po #48 + rework, **C** close po #48, **D** nie merge'ować.
`CI` = `statusCheckRollup` z GitHuba. `Test` = wynik rzeczywistego przebiegu pytest na stacku `master + ten PR` (albo `master + #48 + ten PR`, gdzie zaznaczono).

| # | Tytuł (skrót) | Wiek | Pliki | +/− | CI | Test na merge'u | Konflikt z #48 | Koszyk |
|---|---|---|---|---|---|---|---|---|
| 44 | CI: hermetic video-digest test workflow | 7 d | 2 | +48/0 | **test: SUCCESS** | 84 pass, 1 skip | nie | **A** (1.) |
| 48 | consolidate 9 hermetic test branches (C2/C4 bundle) | 6 d | 23 | +5235/−17 | brak | **419 pass, 1 skip** | — (to on) | **A** (2.) |
| 54 | [low risk] hermetic tests `youtube.py` | 4 d | 2 | +512/0 | brak | sam: 108 pass; z #48: **443 pass** | nie | **A** (3.) |
| 36 | hermetic Notion contract tests (42) | 9 d | 2 | +668/−4 | brak | sam: 127 pass; z #48: **462 pass** | nie | **A** (4.) |
| 49 | docs(video-digest): API.md (CLI, MCP, HTTP, manifest) | 6 d | 1 | +241/0 | brak | docs only; stack A: **486 pass** | nie | **A** (5.) |
| 52 | cheap-route: evaluator works on Hermes v0.20 | 5 d | 2 | +86/−10 | brak | **20 pass** (cheap-route) | nie | **A** |
| 62 | trace-dashboard: share view, filter, phone layout | 2 d | 4 | +373/−16 | brak | **6 pass** (trace-dashboard) | nie | **A** |
| 60 | home-inventory: circle photo, voice, QR, vCard | 3 d | 8 | +1100/−6 | brak | **25 pass, 2 skip** | nie | **A** |
| 64 | research-kit: `local_extract` plugin (K136) | 0 d | 4 | +249/0 | brak | **43 pass, 1 skip** | nie | **A** |
| 42 | wyjscie: procedura wyjścia z domu | 9 d | 5 | +920/0 | brak | **17 pass** | nie | **A** |
| 63 | research-kit: installer hooków bibliografii | 0 d | 1 | +39/0 | brak | smoke: rc=0 ×2, **idempotentny** | nie | **A** |
| 28 | chore: Configure Renovate | 16 d | 1 | +6/0 | brak | config only, 1 plik | nie | **A** |
| 55 | hermetic tests `config.py` (89% → 100%) | 4 d | 1 | +320/0 | brak | sam: 119 pass; **z #48: 8 failed + 5 errors** | **add/add `tests/test_config.py`** | **B** |
| 32 | C4: local Whisper ASR restore (`--check-asr`) | 10 d | 8 | +294/−2 | brak | **1 failed**, 100 pass (`test_asr_probe`) | **`cli.py`, `config.py`** | **B** |
| 33 | hermetic transcript routing contract | 10 d | 1 | +434/0 | brak | 100 % linii w #48 | brak (zawarty) | **C** |
| 37 | [high risk] hermetic tests `backlog.py` | 9 d | 1 | +599/0 | brak | 100 % linii w #48 | brak (zawarty) | **C** |
| 38 | hermetic CLI coverage `cli.py` | 9 d | 3 | +864/−2 | brak | 100 % linii w #48 | brak (zawarty) | **C** |
| 39 | hermetic `gemini.py` + `vision.py` | 9 d | 3 | +687/−1 | brak | 100 % linii w #48 | brak (zawarty) | **C** |
| 40 | hermetic `uploads_since` (discover network) | 9 d | 1 | +471/0 | brak | 100 % linii w #48 | brak (zawarty) | **C** |
| 41 | hermetic `llm.py` contract suite | 9 d | 2 | +564/0 | brak | 100 % linii w #48 | brak (zawarty) | **C** |
| 45 | hermetic contract tests MCP bridge | 7 d | 3 | +654/−1 | brak | 100 % linii w #48 | brak (zawarty) | **C** |
| 46 | hermetic test suite (no operator HOME state) | 7 d | 5 | +157/−12 | brak | 98 % linii w #48 (3 linie `conftest.py` = własna rezolucja #48) | brak (zawarty) | **C** |
| 47 | hermetic tests `report.py` | 7 d | 3 | +464/−1 | brak | 100 % linii w #48 | brak (zawarty) | **C** |
| 6 | hbench: benchmark frameworków × providerów | 25 d | 40 | +2164/0 | brak | **11 pass** (bench) | nie | **D** |

---

## 5. Kolejność merge'a i uzasadnienie

### Krok 1 — #44 (CI), potem #48 (bundle)

`gh pr merge --squash 44` → `gh pr merge --squash 48`.

**Dlaczego #44 pierwszy, choć #48 jest ważniejszy:** #44 nie zmienia kodu testów (na stacku `master + #44` nadal 84 pass, 1 skip — czyli nic nie psuje), a jego `push: branches: [master]` sprawia, że **każdy następny merge dotykający `video-digest/` jest automatycznie weryfikowany na masterze po fakcie**. Wchodząc pierwszy, #44 zamienia 23 PR-y „bez CI" w 5 PR-ów z post-merge gate'em.

**Dlaczego #48 drugi:** wchłania 9 gałęzi (patrz §6). Na dzisiejszym masterze (`d6a407d`, 19 commitów przed bazą #48) merge jest czysty i daje **419 passed, 1 skipped** w 20,2 s. Rozbicie na 9 osobnych merge'y nie ma sensu: te same pliki, ten sam `conftest.py`, 6 par konfliktów w środku (m.in. `#46 × #47` na `conftest.py` — konflikt, który #48 już rozwiązał).

### Krok 2 — #54, #36, #49 (ten sam obszar, kolejność dowolna)

| Stack (na `master`) | Wynik |
|---|---|
| `+48` | 419 pass, 1 skip |
| `+48+54` | 443 pass, 1 skip |
| `+48+36` | 462 pass, 1 skip |
| `+48+54+36+49` | **486 pass, 1 skip** (24,7 s) |

- #54 (testy `youtube.py`, 512 linii) jest niezależny od #48 — sam na masterze 108 pass — ale wchodzi po nim, bo oba dokładają pliki do `video-digest/tests/` i po #48 nie ma już żadnej niewiadomej w `conftest.py`.
- #36 (Notion, 668 linii) — 127 pass sam, 462 pass z #48. Bez konfliktu.
- #49 to wyłącznie `video-digest/docs/API.md` (+241). Zero kodu, zero konfliktu; wchodzi ostatni w tym obszarze, żeby dokument opisywał stan po #48 (API.md powstał 2026-10-28 z bazy `37513c4`, a #48 dokłada m.in. zmiany w `cli.py`/`mcp_bridge.py` — po merge'u warto przejrzeć §1 i §3 dokumentu pod kątem dryfu).

### Krok 3 — projekty niezależne (dowolna kolejność, 0 konfliktów)

#52 (cheap-route, 20 pass) · #62 (trace-dashboard, 6 pass) · #60 (home-inventory, 25 pass / 2 skip) · #64 (research-kit plugin, 43 pass / 1 skip) · #42 (wyjscie, 17 pass) · #63 (installer, smoke OK) · #28 (renovate.json, 6 linii).

Każdy z nich: 0 konfliktów z pozostałymi 23 PR-ami i z `origin/master` (sprawdzone parami), własny katalog, testy zielone na świeżym worktree od `origin/master`.

**#63 — co konkretnie sprawdzono** (bo to bash mutujący `~/.claude/settings.json`): uruchomiony dwukrotnie z `CLAUDE_CONFIG_DIR=/tmp/...` i `BIB_DIR=/tmp/...`; `rc=0` w obu razach, `settings.json` **identyczny po drugim runie** (`sha256` 391c96b994fe), hooki wpięte poprawnie: `PreToolUse: WebFetch`, `PostToolUse: WebFetch|WebSearch`, pliki `bib.py` + `bib_hook.py` skopiowane do `${CLAUDE_CONFIG_DIR}/bib-hook/`. Skrypt nie może wywalić setupu (`exit 0` na każdym błędzie) i zostawia nietknięty `settings.json`, jeśli ten nie jest poprawnym JSON-em.

### Krok 4 — #55 i #32 (koszyk B): **nie merge'ować w tej postaci**

Szczegóły w §7. Oba wymagają rebase po #48, więc wchodzą dopiero, gdy #48 jest na masterze.

### Krok 5 — 9 close'ów (koszyk C), dopiero po merge'u #48

`gh pr close <N>` dla #33, #37, #38, #39, #40, #41, #45, #46, #47. **Nie wcześniej** — dopóki #48 nie jest w masterze, te PR-y są jedynym miejscem, gdzie ta praca istnieje.

---

## 6. Koszyk C — dowód, że to duplikaty, nie „podobne PR-y"

Źródło twarde: historia merge'y w #48 (nie heurystyka plikowa):

```console
$ git log --merges --oneline pr48
… Merge pull request #45 … Merge pull request #33 … Merge pull request #39 …
… Merge pull request #38 … Merge pull request #40 … Merge pull request #37 …
… Merge pull request #47 … Merge pull request #41 … Merge pull request #46 …
```

9 gałęzi, wszystkie 9 PR-y z koszyka C. Dodatkowo kontrola treściowa (dodane linie vs blob `pr48:`): #33, #37, #38, #39, #40, #41, #45, #47 — **100 % dodanych linii obecne w #48**; #46 — **118/121 (98 %)**, a brakujące 3 linie to `conftest.py`, gdzie #48 ma własną, świadomą rezolucję konfliktu `#46 × #47`.

Znaczenie praktyczne:

- **#37 („[high risk]") przestaje być ryzykiem** — jego 407 linii testów `backlog.py` jest w #48 w całości, przetestowane w przebiegu 419 pass. Osobny merge #37 to duplikat z wysokim ryzykiem konfliktowym.
- **#46 jest już w #48 wraz z poprawką**, której sam nie ma (izolacja `conftest.py` po kolizji z #47).
- Zamykanie tych PR-ów **nie traci pracy** — traci tylko 9 otwartych kart na boardzie.

---

## 7. Koszyk B — co dokładnie trzeba poprawić

### #55 „hermetic tests `ytdigest/config.py` (89 % → 100 %)"

**Stan:** sam na `master` → 119 pass, 1 skip. Na `master + #48` → **8 failed, 5 errors** (przebieg samego pliku `test_config.py`, bez równoległego oryginału).

**Dwa niezależne problemy:**

1. **Konflikt add/add** na `video-digest/tests/test_config.py` — plik powstał w #46 (jest w #48, 8 testów) i niezależnie w #55 (30 testów). `merge-tree` zgłasza konflikt już przy samej próbie merge'a `master + #48 + #55`:

   ```console
   $ git merge pr55   # na worktree z master+#48
   CONFLICT (add/add): video-digest/tests/test_config.py
   ```

2. **Dryf kontraktu, nie mechanika.** Po #48 `config.load()` ma sygnaturę `load(path=None, overrides=None)` i `config_path()` może zwracać `None`; #55 testuje starszy kontrakt. Realne błędy z przebiegu:

   ```text
   E  AssertionError: test touched the operator home: ['/home/ubuntu/.hermes/ytdigest/config.yaml']
   E  assert None == PosixPath('.../home/.hermes/ytdigest/config.yaml')
   #   test_config_path_falls_back_to_hermes_home
   E  assert PosixPath('/home/ubuntu/.hermes/ytdigest/config.yaml') == PosixPath('.../config.yaml')
   #   test_config_path_empty_env_var_is_ignored
   ```

   Pierwszy błąd to złapanie przez guard hermetyczności z #47: testy #55 **czytają prawdziwy katalog operatora**, gdy działają w kontekście nowego `conftest.py`. To dokładnie ta klasa defektu, którą #48 likwiduje.

**Wymagany rework (przypisać coderowi):**
- rebase na master po merge'u #48;
- rozdzielić pliki: zachować 8 testów precedencji z #48, dołożyć z #55 tylko to, czego nie ma (`deep_merge` ×5, `read_file` ×6, `defaults` ×2);
- przepisać 8 testów `config_path_*`/`load_*` na nową sygnaturę (`None` jako brak kandydata, `overrides`);
- naprawić hermetyczność: żaden test nie może dotykać `~/.hermes/ytdigest/` (guard z #47 ma przechodzić).

### #32 „C4: local Whisper ASR restore — `--check-asr`"

**Stan:** sam na `master` → **1 failed**, 100 pass, 1 skip.

```text
FAILED tests/test_asr_probe.py::test_this_venv_has_the_local_asr_backends
```

Test **asertuje stan konkretnej maszyny** (obecność `onnx-asr`/parakeet w venv), a workflow z #44 instaluje tylko `pip install -e . pytest` — czyli ten test **zawsze padnie w CI**, niezależnie od jakości kodu. To defekt hermetyczności tego samego rodzaju co w koszyku C, tylko odwrócony: zamiast stubować backend, sprawdza, czy backend jest zainstalowany.

**Konflikt z #48** (2 hunki, mechanicznie małe, ale semantyczne):

- `video-digest/ytdigest/cli.py` — #32 dodaje gałąź `--check-asr` przed `config.load()`, #48 opakowuje `config.load()` w `try/except` („config error: …" → `return 2`). Rezolucja: **unia** — `try/except` wokół `load()` i zachowana gałąź `--check-asr` w środku.
- `video-digest/ytdigest/config.py` — #32 dodaje `os.environ.setdefault("HF_HOME", …)` i `load(path)`, #48 zmienia sygnaturę na `load(path, overrides)` z rozwiązywaniem ścieżki w czasie wywołania. Rezolucja: nowa sygnatura + `HF_HOME` guard.

**Wymagany rework:**
- rebase na master po #48 i ręczna rezolucja obu hunków (unia, nie „ours");
- `test_this_venv_has_the_local_asr_backends` → `pytest.importorskip`/`skipif` gdy backend nieobecny (albo przenieść do markera „integration"), inaczej CI z #44 będzie czerwone na zawsze;
- przejrzeć `test_degradation.py` pod tym samym kątem (czy nie zakłada obecności modeli).

---

## 8. Koszyk D

**#6 „hbench"** — 25 dni, **draft**, 118 commitów za masterem, 40 plików / +2164 linii. Harness przechodzi (11 pass, 4,0 s), więc to nie jest martwy kod, ale: (a) draft = autor sam nie uznał go za gotowy, (b) 118 commitów dryfu przy 40 nowych plikach oznacza, że `bench/providers.toml` i taski opisują rzeczywistość z 2026-10-09, (c) wzorzec `results/` bez ani jednego wyniku. Rekomendacja: **nie merge'ować**; albo zamknąć jako eksperyment (wyniki są w `RESULTS-2026-10-09.md`), albo wskrzesić osobną kartą z rebase i realnym przebiegiem.

---

## 9. Czego ta karta nie zrobiła (i jak to potwierdzono)

- **0 merge'y, 0 close'ów, 0 rebase'ów, 0 pushy do cudzych gałęzi.** Wszystkie 24 gałęzie nietknięte; `headRefOid` każdego PR-a porównany z zapisem sprzed pracy — bez zmian. Liczba otwartych PR przed i po: **24**.
- Nie powstało żadne zadanie „merge stranded …" (poza zakresem karty).
- Nie napisano ani jednej linii kodu produktu ani testu.

Wszystkie przebiegi testów wykonano w **tymczasowych worktree** (`/tmp/rv77/wt/*`) utworzonych z `origin/master`, nie w gałęziach PR-ów. Gałęzie `pr<N>` były wyłącznie czytane (`git show`, `git merge` do worktree tymczasowego).

---

## 10. Ryzyka i dług, których ten digest nie usuwa

1. **Filtr `paths:` w workflow z #44 pokrywa tylko `video-digest/**`** — 7 projektów (`cheap-route`, `home-inventory`, `trace-dashboard`, `wyjscie`, `bench`, `skills`, oraz przyszłe) pozostaje bez CI. Osobna karta.
2. **23 PR-y nie mają historii CI** — zieloność jest tu zmierzona lokalnie w venv Python 3.11 z `PYTHONPATH=.`, a nie w środowisku GitHub-hosted. Różnica jest realna (patrz #32), więc pierwszy przebieg po merge'u #44 może ujawnić rozjazdy zależności.
3. **#49 (API.md) opisuje stan sprzed #48** — po merge'u #48 warto zrobić szybki diff dokument vs `--help`.
4. **Wiek długu:** 6 PR-ów ma ≥9 dni i bazę z `37513c4` (2026-10-11). Im później merge, tym więcej commitów mastera do przetrawienia — ale wszystkie 24 merge'ują się dziś bez konfliktu, więc kolejność z §5 jest bezpieczna.
