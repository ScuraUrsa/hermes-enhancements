# Decision log: video-digest (tests bundle, 2026-10-28)

**Zadanie.** Karta `t_adbeeac4` (C2 run58): `ScuraUrsa/hermes-enhancements` miało 16 otwartych PR-ów,
z czego 9 to agentowe PR-y testowe C2/C4. Wszystkie `MERGEABLE / CLEAN`, ale `gh pr checks` zwraca
„no checks reported” (`origin/master` nie ma `.github/workflows` — workflow żyje tylko w PR #44, który
czeka na decyzję Filipa). Efekt: 9 osobnych, niesprawdzalnych decyzji dla człowieka i pokrycie testami
`ytdigest` nigdy nie dociera na `master`. Cel: **jeden** PR „tests bundle” zamiast 9.

**Punkt startowy.** Worktree był na `37513c4`, ale `origin/master` posunął się do `721140b`
(64 commity; `37513c4` jest przodkiem `721140b`). Zamiast rebase'ować stare gałęzie — `git reset --hard
origin/master` i merge każdej gałęzi na aktualny master. Baseline na czystym `origin/master`:
**84 passed, 1 skipped, 15,9 s**, TOTAL coverage **64 %** (2286 stmt / 827 miss).

**Decyzje.**

- Kolejność merge'y zgodna z kartą: najpierw #46, bo zmienia globalne rozwiązywanie configu
  (`config_path()`, `HERMES_REAL_HOME`), więc każda następna gałąź musi być walidowana na nim.
- `git merge --no-ff` dla wszystkich 9 gałęzi — historia zachowuje proweniencję gałęzi i numer PR-a
  w temacie commita, więc `git log --grep '#38'` nadal działa po skonsolidowaniu.
- **Hotspot `tests/conftest.py` rozwiązany addytywnie, bez osłabiania izolacji.** Dwa realne zderzenia:
  - `routing.load()` czyta `vbench/routing.json` (plik pojawił się na masterze *po* wycięciu gałęzi).
    Fixture z #46 (`routing_file=""`) zaczęła przez to widzieć `ollama-cloud:gemma3:12b` zamiast
    domyślnego `gemma4:31b` → `test_pipeline.py::test_retired_vision_model_falls_back` czerwony.
    Rozwiązanie: `cfg["routing_file"]` wskazuje nieistniejącą ścieżkę w `tmp_path` — nadal czyste
    `DEFAULTS`, zero plików operatora.
  - #47 (`test_config_isolation.py`) wymaga, by `YTDIGEST_CONFIG` wskazywał **istniejący** plik
    (`config_path()` musi rozwiązać się w `tmp_path`), a #46 chciał ścieżki nieistniejącej.
    Rozwiązanie: fixture zapisuje **pusty** `config.yaml` w `tmp_path`. Oba niezmienniki trzymają:
    `config_path()` zatrzymuje się w `tmp_path`, a `load()` zwraca czyste `DEFAULTS`.
- **Co fixture `cfg` wymusza naprawdę** (patrz poprawka D1 w sekcji „Rework R1” — pierwsza wersja tego
  akapitu obiecywała więcej, niż kod robił): `topic_routes` = `{}`, `processed_playlist` =
  `{"enabled": False}`, `google_accounts_dir` i `cookies_file` w `tmp_path`, `routing_file` =
  nieistniejąca ścieżka w `tmp_path`, `YTDIGEST_CONFIG` = pusty `config.yaml` w `tmp_path`,
  `YTDIGEST_DATA_DIR` w `tmp_path`. **Nie** wystarcza `HERMES_REAL_HOME`: `DEFAULTS` w `config.py`
  liczy `HERMES_HOME` w momencie importu, więc ścieżki do kont i cookies trzeba nadpisać jawnie.
  Od R1 dochodzi autouse strażnik `_no_external_network` (odrzuca `connect`/`connect_ex`/`getaddrinfo`
  na nie-loopback, także wtedy gdy kod produkcyjny połknie wyjątek).
- **Zmiany produkcyjne tylko takie, które przyszły z gałęziami** (karta pkt 5), każda z testem, który
  bez niej jest czerwony — dowód przez `git checkout origin/master -- <plik>` i uruchomienie testów:

  | plik | zmiana (z gałęzi) | test czerwony bez zmiany |
  |---|---|---|
  | `ytdigest/config.py` (#46) | `config_path()`: `YTDIGEST_CONFIG` → … → `./config.yaml`, `load(overrides=)` | 4× `tests/test_config.py::test_precedence_defaults_file_overrides`, `::test_ytdigest_home_fallback`, `::test_env_read_at_call_time`, `::test_missing_pyyaml_without_config_file_means_clean_defaults` |
  | `ytdigest/cli.py` (#38) | czytelny błąd configu zamiast tracebacka, `re-render` bez `bundles/` | `test_cli_main.py::test_main_reports_config_error_without_traceback`, `::test_main_reports_malformed_config_without_traceback`, `test_cli_commands.py::test_rerender_without_bundles_dir_is_clean` |
  | `ytdigest/gemini.py` (#39) | `JSONDecodeError` → kontrolowany `llm.LLMError` | `tests/test_gemini.py::test_malformed_json_from_model_is_a_controlled_llm_error` |
  | `ytdigest/mcp_bridge.py` (#45) | jawne `wait_seconds=0` znaczy „nie czekaj” | `tests/test_mcp_bridge.py::test_digest_wait_seconds_zero_returns_immediately_without_polling` |

- **Nie wciągnięte** (zgodnie z kartą): #44 (CI workflow — osobna decyzja Filipa), #36 (testy + realne
  fixy `notion.py` — `notion.py` poza listą dozwolonych plików produkcyjnych), #32 (`wt/c4-local-asr-restore`
  — zmiana produkcyjna ASR), #42/#43 (wyjście/home-inventory), #28 (renovate). Żaden PR nie został
  zamknięty — po merge'u bundle'a Filip może je zamknąć sam.
- Testy hermetyczne: żadnej sieci, żadnego `~/.hermes`, żadnych kluczy API. Od R1 pilnuje tego
  **jeden autouse strażnik w `tests/conftest.py`** (`_no_external_network`) dla całego suite, nie tylko
  w modułach mostu MCP / `discover_network` / `backlog` / `transcript` / `llm_client`.

**Pomiar (ten sam interpreter `/home/ubuntu/crewai-orchestrator/.venv/bin/python`, Python 3.11.17,
pytest 9.1.1, clean-room `git archive` — nie brudny worktree; komenda
`python -m pytest tests -q --cov=ytdigest --cov-report=term` uruchamiana w `video-digest/`).**

| | SHA + timestamp pomiaru | testy | TOTAL coverage |
|---|---|---|---|
| PRZED | `origin/master` = `721140b` @ 2026-10-28T11:15:46Z | 84 passed, 1 skipped, 16,4 s | 2286 stmt / 827 miss / **64 %** |
| PO (R1) | `wt/tests-bundle-run58` = `d72dbe6` @ 2026-10-28T11:18:28Z | **419 passed, 1 skipped, 20,1 s** | 2308 stmt / 290 miss / **87 %** |

Uwaga do wcześniejszej wersji tego dokumentu: PRZED było podane jako „827 miss” bez SHA i czasu, a recenzja
zmierzyła 816 miss na tym samym masterze. Pomiar powtórzony dwukrotnie na czystym `721140b` daje **827**
(2286/827, 84 passed) — liczby 816 nie udało się odtworzyć; różnica 11 statementów to najpewniej inny
sposób złożenia przebiegu po stronie recenzji (np. sklejony `.coverage`), bo liczba statementów i testów
się zgadza. Żeby uniknąć tej klasy rozjazdu, oba wiersze pochodzą z **jednego** clean-roomu, jednej
komendy i mają SHA + timestamp; wszystkie liczby „po” w tym dokumencie i w opisie PR pochodzą z przebiegu
`d72dbe6`.

Po: `notion.py` 23 % (nie ruszane — poza zakresem karty, PR #36), `transcript.py` 63 %, `fetch.py` 71 %,
`server.py` 76 %, `compare.py` 76 %, `gate.py` 77 %. 100 %: `discover.py`, `gemini.py`, `llm.py`,
`mcp_bridge.py`, `report.py`, `topics.py`, `vision.py`, `youtube.py`.

**Higiena.** `git diff --diff-filter=D origin/master --name-only` → puste (nic nie usunięte);
`git diff --name-only origin/master | grep -v '^video-digest/'` → puste (zero zmian poza `video-digest/`).
Zero `push --force`, zero merge'y do `master`, zero sekretów.

## Rework R1 (recenzja: 1 defekt blokujący + 2 drobne)

**D1 (blokujący) — `cfg` zgubił neutralizację z `origin/master`.** Rozwiązując hotspot `conftest.py`
wersja z bundle'a upuściła dwie linie mastera: `c["topic_routes"] = {}` oraz
`c["processed_playlist"] = {"enabled": False}`. Skutek: `cfg["processed_playlist"]` wracał do `DEFAULTS`
(`enabled: True`, `account: fjkazmierczak`), a `google_accounts_dir` / `cookies_file` wskazywały realne
`~/.hermes/...`. `pipeline.process` po statusie `done` wołał `youtube.add_to_playlist` →
`backlog.token_for`, a to **preferuje `GOOGLE_<ALIAS>_TOKEN_JSON` z env** nad plikiem z
`google_accounts_dir` — czyli sięgało po realny token Filipa i mierzyło w jego prawdziwą playlistę
„Przetworzone przez Hermesa”. Wyjątek z sieci był połykany przez `except Exception` w kroku playlisty,
więc testy przechodziły „zielono”, używając realnych credentiali. Akapit „żadna fixture nie czyta
`~/.hermes/...`” w tym dokumencie był w tej wersji nieprawdziwy — dlatego został przepisany wyżej.

Naprawa (bez zmian produkcyjnych — tylko testy i ten dokument):

1. `cfg` przywraca `topic_routes = {}` i `processed_playlist = {"enabled": False}` oraz jawnie kieruje
   `google_accounts_dir` i `cookies_file` (szablon `{account}`) do `tmp_path`. Samo `HERMES_REAL_HOME`
   nie wystarcza: `config.DEFAULTS` liczy `HERMES_HOME` przy imporcie, więc ścieżki są już „wypieczone”.
   Zbiór kluczy się nie zmienia — `assert set(c) == set(config.DEFAULTS)` dalej przechodzi.
2. Autouse strażnik `_no_external_network` w `tests/conftest.py`: odrzuca `socket.connect`,
   `socket.connect_ex` i `socket.getaddrinfo` na nie-loopback, **zbiera** próby i failuje test w teardownie
   — właśnie dlatego, że kod produkcyjny połyka błędy sieci. Loopback (`127.0.0.1`, `::1`, `localhost`)
   zostaje otwarty dla `tests/test_server.py`.
3. Hermetyczne pokrycie ścieżek, które wcześniej „pokrywał” wyłącznie realny ruch:
   `test_processed_playlist_step_runs_through_the_fake`,
   `test_processed_playlist_failure_does_not_fail_the_run` (oba w `tests/test_pipeline.py`) i
   `test_call_maps_http_errors` (`tests/test_topics_cleanup_youtube.py`, mapowanie 200 / 403-insufficient /
   4xx i timeout 30 s w `youtube._call`). Dzięki temu `youtube.py` ma **100 %** (0 miss) bez ani jednego
   pakietu w sieć.

**Dowody (wszystkie przebiegi w clean-roomie, socket zablokowany strażnikiem).**

| krok | komenda | wynik |
|---|---|---|
| RED (strażnik, `cfg` jeszcze nie naprawiony, `352ddc1`) | `pytest tests/test_pipeline.py -q` | `8 passed, **6 errors**` — `socket.getaddrinfo -> ('oauth2.googleapis.com', 443)` w `test_gemini_url_path`, `test_gemini_is_off_by_default`, `test_falls_back_to_frames_when_gemini_fails`, `test_retired_vision_model_falls_back`, `test_all_frames_failing_marks_run_degraded`, `test_refused_download_marks_run_degraded` |
| GREEN (po naprawie `cfg`, `ca78da5`) | `pytest tests/test_pipeline.py -q` | `8 passed`, zero prób sieci |
| pełny suite (`d72dbe6`) | `pytest tests -q --cov=ytdigest --cov-report=term` | `419 passed, 1 skipped, 20,1 s`, strażnik nie zebrał **żadnej** próby |
| negative control (`d72dbe6` minus dwie linie neutralizujące, clean-room) | `pytest tests/test_pipeline.py -q` | `10 passed, **6 errors**` z tym samym hostem — strażnik nie jest pusty i złapałby regresję |
| niezależny probe `sitecustomize.py` (loguje i blokuje `getaddrinfo`/`connect`), **strażnik wyłączony**, `cfg` naprawiony, cały suite | `PYTHONPATH=probe pytest tests -q` | **0 prób sieci** — izolację trzyma sam `cfg`, nie tylko strażnik |
| ten sam probe, **strażnik wyłączony**, `cfg` bez neutralizacji (kontrola) | `PYTHONPATH=probe pytest tests -q` | **6 prób**, wszystkie `getaddrinfo oauth2.googleapis.com:443` — dokładnie pomiar z recenzji |

**m1 — proweniencja pomiaru.** Baseline ma teraz SHA + timestamp + komendę + wersje (tabela wyżej);
`827 miss` odtworzone dwukrotnie na czystym `721140b`, liczba `816` z recenzji nieodtwarzalna (opis wyżej).

**m2 — jedna liczba „po”.** Wszystkie wystąpienia liczb „po” w tym dokumencie i w opisie PR pochodzą
z jednego przebiegu `d72dbe6`: **419 passed, 1 skipped, 20,1 s; 2308 stmt / 290 miss / 87 %**.

Zakres R1: wyłącznie `video-digest/tests/` + ten dokument — `git diff --stat 352ddc1..d72dbe6`:
`tests/conftest.py`, `tests/test_pipeline.py`, `tests/test_topics_cleanup_youtube.py`,
`docs/archive/decision-logs/decision_log_tests_bundle_run58_t_adbeeac4.md`. Zero zmian w `ytdigest/`.

**Następne kroki.** Merge tylko Filip (brama człowieka — PR czeka na `master`). Po merge'u #44 (workflow)
każdy kolejny PR dostanie realne checks. Kandydaci do następnej rundy pokrycia: `notion.py` (PR #36,
wymaga decyzji o fixach produkcyjnych) i `transcript.py` 63 %.
