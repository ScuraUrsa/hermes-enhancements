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
  eval_set.jsonl   83 pytania: 44 prawdziwe z sesji Filipa + 24 ogólne + 15 pułapek
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
