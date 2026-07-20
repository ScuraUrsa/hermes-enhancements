# Math Engine — Agent Assignments

Każdy agent wpisuje swój obszar poniżej. **Nie dublujemy się.**
Wspólne repo: `ScuraUrsa/hermes-enhancements/math-engine/`

| Agent ID | Obszar | Status |
|----------|--------|--------|
| **GŁÓWNY** (Coder, deepseek-v4-pro) | **Math Engine Core + Symbolic + Numeric + Financial + CLI** — routing, SymPy, SciPy, kredyt vs ETF, Monte Carlo, plotting, Streamlit apps, Hermes tool | 🔄 W trakcie |
| deleg_??? | **Probability & Statistics Deep** — rozkłady, Bayes, MCMC, regresja, testy statystyczne, ANOVA | ⬜ |
| deleg_??? | **Optimization & ML Math** — gradient descent, constrained optimization, linear programming, eigenvalues | ⬜ |
| deleg_??? | **Visualization & Apps** — zaawansowane dashboardy, animacje 3D, interaktywne wizualizacje | ⬜ |

## Zasady
1. Wpisz swój obszar przed rozpoczęciem pracy
2. Nie wchodź w obszar innego agenta
3. Commituj do `math-engine/` w repo `ScuraUrsa/hermes-enhancements`
4. LLM NIGDY nie liczy — zawsze deleguje do narzędzia
5. Każdy solver zwraca: wynik + kroki pośrednie + wykres (jeśli dotyczy)

## Architektura
```
math-engine/
├── AGENT_ASSIGNMENTS.md
├── README.md
├── src/
│   ├── __init__.py
│   ├── engine.py          # Router — wykrywa typ problemu
│   ├── symbolic.py        # SymPy wrapper
│   ├── numeric.py         # NumPy/SciPy wrapper
│   ├── financial.py       # Kredyt vs ETF, NPV, IRR, portfel
│   ├── probability.py     # Rozkłady, Monte Carlo, Bayes
│   ├── plotting.py        # matplotlib/plotly
│   └── cli.py             # CLI + Hermes tool
├── apps/
│   ├── mortgage_vs_etf.py # Streamlit: kredyt vs inwestycja
│   ├── portfolio_opt.py   # Streamlit: optymalizacja portfela
│   └── monte_carlo.py     # Streamlit: symulacje Monte Carlo
├── tests/
│   └── test_engine.py
└── data/
```

## Stan
- [ ] Math Engine Core (router)
- [ ] Symbolic Solver (SymPy)
- [ ] Numeric Solver (SciPy)
- [ ] Financial Math
- [ ] Probability & Statistics
- [ ] Plotting Engine
- [ ] Streamlit Apps
- [ ] CLI + Hermes Tool
- [ ] Testy
