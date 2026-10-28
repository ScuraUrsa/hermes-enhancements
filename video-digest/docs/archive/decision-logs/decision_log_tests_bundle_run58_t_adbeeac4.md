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
  Żadna fixture nie czyta `~/.hermes/...` — izolacja z #46/#47 została.
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
- Testy hermetyczne: żadnej sieci, żadnego `~/.hermes`, żadnych kluczy API. `socket.socket` jest twardo
  blokowany w testach mostu MCP i `discover_network.py`.

**Pomiar (ten sam interpreter `/home/ubuntu/crewai-orchestrator/.venv/bin/python`, pytest 9.1.1).**

| | testy | TOTAL coverage |
|---|---|---|
| PRZED (`origin/master` = `721140b`) | 84 passed, 1 skipped, 15,9 s | 2286 stmt / 827 miss / **64 %** |
| PO (bundle `wt/tests-bundle-run58`) | **416 passed, 1 skipped, 23,9 s** | 2308 stmt / 290 miss / **87 %** |

Po: `notion.py` 23 % (nie ruszane — poza zakresem karty, PR #36), `transcript.py` 63 %, `fetch.py` 71 %,
`server.py` 76 %, `compare.py` 76 %, `gate.py` 77 %. 100 %: `discover.py`, `gemini.py`, `llm.py`,
`mcp_bridge.py`, `report.py`, `topics.py`, `vision.py`.

**Higiena.** `git diff --diff-filter=D origin/master --name-only` → puste (nic nie usunięte);
`git diff --name-only origin/master | grep -v '^video-digest/'` → puste (zero zmian poza `video-digest/`).
Zero `push --force`, zero merge'y do `master`, zero sekretów.

**Następne kroki.** Merge tylko Filip (brama człowieka — PR czeka na `master`). Po merge'u #44 (workflow)
każdy kolejny PR dostanie realne checks. Kandydaci do następnej rundy pokrycia: `notion.py` (PR #36,
wymaga decyzji o fixach produkcyjnych) i `transcript.py` 63 %.
