# Math Engine — Agent Assignments

Każdy agent wpisuje swój obszar poniżej. **Nie dublujemy się.**
Wspólne repo: `ScuraUrsa/hermes-enhancements/POV/13-math-engine/`

| Agent ID | Obszar | Status |
|----------|--------|--------|
| **GŁÓWNY** (Coder, deepseek-v4-pro) | **Core Engine + Credit vs ETF + Monte Carlo + Statistics + Optimization + Time Series + Game Theory + Differential Equations + Linear Algebra** — 7 demo apps, 58 testów, hermes_math_tool.py | ✅ Done |
| (inny agent) | **differential_eq.py + ml_math.py** — równania różniczkowe, machine learning math | 🔄 W trakcie |
| (inny agent) | **Wolny** — Geometria, fraktale, wizualizacje 3D | ⬜ |
| (inny agent) | **Wolny** — Teoria informacji, entropia, kompresja | ⬜ |

## Zasady
1. Wpisz swój obszar przed rozpoczęciem pracy
2. Nie wchodź w obszar innego agenta
3. Commituj do `POV/13-math-engine/` w repo `ScuraUrsa/hermes-enhancements`
4. Każdy moduł: plik .py + test_*.py + generuje wykresy do `output/`
5. Wszystkie obliczenia przez math_engine.py — LLM NIE LICZY

## Architektura (stan faktyczny)
```
POV/13-math-engine/
├── AGENT_ASSIGNMENTS.md          # Ten plik
├── README.md                     # Dokumentacja
├── math_engine.py                # Core engine (SymPy, NumPy, SciPy)
├── hermes_math_tool.py           # Hermes integration
├── test_math_engine.py           # 38 testów core engine
├── test_demos.py                 # 20 testów demo modułów
├── demo_credit_vs_etf.py         # Nadpłata kredytu vs ETF
├── demo_monte_carlo.py           # Monte Carlo, VaR, opcje
├── demo_statistics.py            # Statystyka, testy, Bayes
├── demo_optimization.py          # Optymalizacja, LP, portfel
├── demo_time_series.py           # ARIMA, GARCH, Holt-Winters
├── demo_game_theory.py           # Nash, mixed strategies, Shapley
├── demo_differential_equations.py # Lotka-Volterra, Lorenz, Van der Pol
├── demo_linear_algebra.py        # SVD, PCA, dekompozycje
├── differential_eq.py            # (inny agent)
├── ml_math.py                    # (inny agent)
├── output/                       # 20+ wykresów PNG
└── requirements.txt
```

## Stan — GŁÓWNY agent DONE ✅
- ✅ Core engine: 38 testów (SymPy + NumPy + SciPy)
- ✅ 7 demo apps z wykresami
- ✅ Hermes integration tool
- ✅ 58 testów łącznie (wszystkie przechodzą)
- ✅ Commity na GitHub
