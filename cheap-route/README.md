# cheap-route — tani router pytań dla Hermesa

Lokalny ewaluator (llama.cpp, mały model) decyduje przed turą agenta, czy pytanie jest
ogólne i bez prywatnego kontekstu. Takie pytania idą do darmowego kanału (darmowe API,
później chatboty webowe), reszta do Hermesa z narzędziami, pamięcią i subskrypcją.

Plan i stan: folder projektu `free-web-proxy/plan.md` (projekt Hermes_local).

## Etap 1 — ewaluator (ten folder)

```
evaluator/
  prompt.md        system prompt routera (JSON: route, confidence, reason)
  rules.py         twarde reguły, które wymuszają "hermes" bez pytania modelu
  eval_set.jsonl   86 pytań: 44 prawdziwe z sesji Filipa + 24 ogólne + 18 pułapek
  bench_route.py   benchmark przeciwko llama-server (/v1/chat/completions)
```

Uruchomienie na laptopie (llama.cpp już stoi w `D:\hermes\_llamacpp`, model z benchmarku
timeplane):

```powershell
cd D:\hermes\_timeplane_llm
.\serve.ps1 -Model Qwen3.5-4B-Q4_K_M.gguf          # albo gemma-4-E2B-it-Q4_K_M.gguf
cd <ten folder>\evaluator
python bench_route.py --model qwen3.5-4b --runs 2
python bench_route.py --model qwen3.5-4b --no-rules --tag qwen3.5-4b-norules   # sam model
```

Kryterium przyjęcia: **0 fałszywych `free_web`** (żadne pytanie z prywatnym kontekstem nie
wychodzi na zewnątrz) i ≥ 90 % zgodności ogółem. Opuszczone `free_web` kosztują tylko tokeny,
więc próg `confidence` dobieramy pod zero wycieków.

Wymagania: Python 3.10+, `pip install requests`.

## Etap 2 — plugin Hermesa (`plugin/`)

```
plugin/
  plugin.yaml      manifest (hook post_gateway_admission, komenda /route)
  __init__.py      register(ctx): dwa zadania pomocnicze, hook, komenda
  router.py        decyzja (reguły → model → próg), pamięć sesji, dziennik decisions.jsonl
  rules.py         kopia evaluator/rules.py (trzymać w zgodzie)
  prompt.md        kopia evaluator/prompt.md
tests/test_router.py   19 testów zachowania (pytest), bez Hermesa
```

Instalacja na VM: rola Ansible `cheap_route` w repo WOBI (llama-router + plugin + config + klucz z BWS;
`sudo bash ansible/pull.sh --as unity-orchestrator --role active --tags cheap_route`). Ręcznie: skopiować
`plugin/` jako `~/.hermes/plugins/cheap-route/`, llama-server z `--chat-template-kwargs '{"enable_thinking": false}'`,
potem w `config.yaml`:

```yaml
plugins:
  enabled: [cheap-route]
  entries:
    cheap-route:
      settings: {enabled: true, threshold: 0.8, footer: true, platforms: []}
auxiliary:
  cheap_route_router: {provider: custom, base_url: "http://127.0.0.1:8082/v1", model: local, api_key: none,
                       extra_body: {chat_template_kwargs: {enable_thinking: false}}}   # Qwen3.5: bez myślenia
  cheap_route_free:   {provider: gemini, model: gemini-3.6-flash}   # GEMINI_API_KEY w .env/BWS
```

Wersje Hermesa: na forku ≥ 2026-10-12 (merge upstream, hook `post_gateway_admission`) plugin
przechwytuje wiadomość po autoryzacji i komendach. Na starszym Hermesie (prod: v0.20.0, pin a6ede70
w WOBI) używa `pre_gateway_dispatch`: wiadomości wymuszone regułami przechodzą bez zmian, resztę
przejmuje (`skip`), ocenia w wątku, odpowiada przez adapter albo oddaje bramce bez zmian. Na starym
Hermesie ustawienia czyta wprost z `plugins.entries.cheap-route.settings`, a `/route on|off` nie działa.

Zachowanie: reguły wymuszają `hermes` dla wszystkiego osobistego lub z prośbą o działanie, model
decyduje o reszcie; `free_web` tylko przy pewności ≥ próg. Każdy błąd ewaluatora lub darmowego
kanału = zwykła tura Hermesa. Odpowiedź z darmowego kanału ma stopkę; `/route` pokazuje statystyki
z `~/.hermes/plugin-data/cheap-route/decisions.jsonl`, `/route off` wyłącza.
