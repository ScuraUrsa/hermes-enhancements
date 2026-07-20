# Math Engine — narzędzie matematyczne dla Hermesa

LLM **NIGDY** nie liczy. Ten silnik wykonuje rzeczywistą matematykę:
SymPy dla symboliki, SciPy dla numeryki, Monte Carlo dla symulacji.

## Szybki start

```bash
cd ~/workspace/hermes-enhancements/math-engine

# Pochodna
PYTHONPATH=. python3 -m src.cli solve "oblicz pochodną x**2 * sin(x)"

# Całka
PYTHONPATH=. python3 -m src.cli solve "całka z x**2 + 3*x + 1"

# Równanie
PYTHONPATH=. python3 -m src.cli solve "rozwiąż x**2 - 4 = 0"

# Kredyt vs ETF (kluczowe!)
PYTHONPATH=. python3 -m src.cli mortgage-vs-etf --loan 500000 --rate 7 --etf 8

# Portfel Markowitza
PYTHONPATH=. python3 -m src.cli portfolio

# Wykres
PYTHONPATH=. python3 -m src.cli solve "narysuj wykres sin(x) * exp(-x/5)"

# Klasyfikacja
PYTHONPATH=. python3 -m src.cli classify "całka z x^2 dx"
```

## Testy

```bash
PYTHONPATH=. python3 -m pytest tests/test_engine.py -v
# 37/37 passing
```

## Architektura

```
math-engine/
├── src/
│   ├── engine.py       # Router — klasyfikacja + delegacja
│   ├── symbolic.py     # SymPy: pochodne, całki, równania, granice, szeregi
│   ├── numeric.py      # SciPy: optymalizacja, całkowanie num., miejsca zerowe
│   ├── financial.py    # Kredyt vs ETF, NPV/IRR, portfel Markowitza, amortyzacja
│   ├── probability.py  # Rozkłady, Bayes, Monte Carlo, regresja
│   ├── plotting.py     # matplotlib: 2D, 3D, efficient frontier
│   └── cli.py          # CLI + Hermes tool
├── tests/
│   └── test_engine.py  # 37 testów
└── AGENT_ASSIGNMENTS.md
```

## Kluczowe formuły

### Kredyt vs ETF — próg rentowności

```
ETF_break_even = stopa_kredytu / (1 - podatek_Belki)

Przykład: kredyt 7%, Belka 19%
  → 0.07 / 0.81 = 8.64%

Jeśli ETF zarabia > 8.64% → lepiej inwestować
Jeśli ETF zarabia < 8.64% → lepiej nadpłacać kredyt
```

### Rata kredytu (annuitet)

```
R = K * r * (1+r)^n / ((1+r)^n - 1)
gdzie: r = stopa/12, n = lata*12
```

### Monte Carlo future value

```
FV = initial * ∏(1+r_i) + Σ(monthly * ∏(1+r_j))
gdzie r_i ~ N(μ/12, σ/√12)
```

## Podział pracy

Zobacz `AGENT_ASSIGNMENTS.md` — inne agenty zajmą się:
- Probability & Statistics Deep (rozkłady, MCMC, ANOVA)
- Optimization & ML Math (gradient descent, LP, eigenvalues)
- Visualization & Apps (dashboardy, animacje 3D)
