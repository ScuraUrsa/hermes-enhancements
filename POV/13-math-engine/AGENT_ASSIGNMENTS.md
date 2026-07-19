# Math Engine — Agent Assignments

Każdy agent wpisuje swój obszar poniżej. **Nie dublujemy się.**
Wspólne repo: `ScuraUrsa/hermes-enhancements/POV/13-math-engine/`

| Agent ID | Obszar | Status |
|----------|--------|--------|
| **GŁÓWNY** (Coder, deepseek-v4-pro) | **Teoria gier + Teoria decyzji + Badania operacyjne** — Nash equilibrium, mixed strategies, decision trees, expected utility, linear programming, simplex, transport problem, knapsack, game theory demo app | 🔄 W trakcie |
| (inny agent) | **Core Engine rozbudowa** — algebra liniowa, równania różniczkowe, transformaty (Laplace, Fourier) | ⬜ |
| (inny agent) | **Szeregi czasowe + Prognozowanie** — ARIMA, exponential smoothing, trend analysis, sezonowość | ⬜ |
| (inny agent) | **Credit vs ETF fix + Monte Carlo rozbudowa** — naprawić timeout, dodać VaR, stress testing | ⬜ |
| (inny agent) | **Geometria + Fraktale + Wizualizacje 3D** — Mandelbrot, Julia sets, 3D surfaces, topologia | ⬜ |

## Zasady
1. Wpisz swój obszar przed rozpoczęciem pracy
2. Nie wchodź w obszar innego agenta
3. Commituj do `POV/13-math-engine/` w repo `ScuraUrsa/hermes-enhancements`
4. Każdy moduł: plik .py + test_*.py + generuje wykresy do `output/`
5. Wszystkie obliczenia przez math_engine.py — LLM NIE LICZY
