# trace-dashboard

Minimalistyczny dashboard: **Twój prompt → wątki Claude i sesje Hermesa → commity i PR-y → efekt**,
z tokenami i kosztem każdego kroku, per provider (Anthropic, Ollama Cloud, lokalny llama.cpp, Gemini).

Działa na prod jako usługa WOBI (rola `trace_dashboard`), tylko w tailnecie:
`https://hermes-vm-1.<tailnet>.ts.net:8444/`.

## Co pokazuje

- Lista "promptów" (źródeł pracy): wątek w projekcie Claude, rozmowa z Hermesem (CLI, Matrix, API), zadanie kanban
  od Ciebie, praca autonomiczna (planner, CI watchdog, sondy limitu Claude), cron. Dla każdego: stan, PR-y scalone /
  wszystkie, commity, tokeny, koszt i pasek podziału kosztu na providerów.
- Po kliknięciu: treść prompta, kroki (gdzie i dlaczego wykonano pracę, provider, model, tokeny, koszt i podstawa
  wyliczenia), zmiany w repozytoriach (PR-y z commitami, luźne commity) i efekt.
- Filtry: tekst, źródło, okres, "tylko ze zmianami w repo". Sortowanie po każdej kolumnie.

## Jak zmiana jest wiązana z promptem

| Krok | Powiązanie |
|---|---|
| wątek Claude → prompt | korzeń wątku w projekcie (wiadomość od Ciebie albo od koordynatora) |
| wątek Claude → PR | gałąź PR = gałąź sesji wątku (`claude/project-thread-*`), albo link do wątku / `session_…` w opisie PR |
| wątek Claude → commit | trailer `Claude-Session: …/session_…` albo commit należy do takiego PR |
| rozmowa Hermesa → subagenci | `parent_session_id` |
| rozmowa Hermesa → zadanie kanban | `tasks.session_id` (sesja, która utworzyła zadanie) |
| zadanie kanban → sesje workera | `worker_session_id` przebiegu, `t_xxxxxxxx` w tytule/cwd sesji, albo profil + okno czasu przebiegu |
| zadanie kanban → Claude Code | `task_id` w `claude_runs.jsonl` |
| zadanie kanban → PR / commit | gałąź `wt/t_xxxxxxxx` albo `t_xxxxxxxx` w tytule/opisie PR lub w commicie |

Konwencja na przyszłość, żeby nic nie wypadło: commity z Claude mają trailer `Claude-Session:`, PR-y z projektu mają
link do wątku w opisie, a workerzy Hermesa wpisują `t_xxxxxxxx` w commit (cc_run.py już o to prosi).

## Skąd koszt

| Provider | Jak liczony |
|---|---|
| Anthropic | koszt zgłoszony przez Claude Code / claude.ai = cena API zużytych tokenów (Ty płacisz abonament, to równoważnik) |
| Ollama Cloud | tokeny × cennik modelu z `~/.hermes/autonomy/budget.json` (`prices_per_mtok`, ten sam co `budget.py`), [wejście, cache, wyjście] za 1M; też równoważnik, płacisz abonament Pro |
| llama.cpp lokalnie, Gemini free | 0 |

Sesja Hermesa może używać kilku modeli (główny + zadania pomocnicze, np. router cheap-route): koszt liczony per
model z tabeli `session_model_usage`. Koordynator projektu Claude to osobna pozycja "narzut wspólny". Cennik i
etykiety: [`pricing.json`](pricing.json).

## Dane wejściowe

- `~/.hermes/state.db` i `~/.hermes/profiles/*/state.db` na prod; sesje z dev przez SSH (`collect.py --dump-hermes`
  uruchomiony zdalnie, gdy dev odpowiada);
- `~/.hermes/kanban-dev.db` (kopia tablicy z dev, odświeżana co minutę);
- `~/.hermes/autonomy/claude_runs.jsonl` z prod i dev;
- GitHub: PR-y i commity repozytoriów ScuraUrsa (token `GITHUB_TOKEN` z Bitwardena, tylko w pamięci procesu),
  z cache ETag w `~/.hermes/trace-dashboard/github-cache.json`;
- `claude_threads.json`: wątki projektu Claude z użyciem tokenów, eksportowane przez wątek dashboardu w projekcie
  Claude do osieroconej gałęzi prywatnego repo `hermes-default-workspace` (to repo jest publiczne, więc treści
  promptów tu nie trafiają).

## Uruchamianie ręczne

```bash
bash run.sh                       # jeden przebieg na prod (to samo robi trace-dashboard-collect.timer)
python3 collect.py --help         # wszystkie wejścia jako opcje
python3 -m pytest -q tests        # testy powiązań i cen na syntetycznych danych
```
