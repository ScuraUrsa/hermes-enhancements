# POV #13 — Math Engine for Hermes

**LLM nie powinien liczyć. To robi Math Engine.**

## Problem

LLM-y (nawet najlepsze) popełniają błędy w obliczeniach matematycznych. Nie mają deterministycznego silnika — "liczą" przez generowanie tokenów, co prowadzi do:
- Błędów arytmetycznych (szczególnie przy dużych liczbach)
- Nieprawidłowych wzorów
- Halucynacji w statystyce i prawdopodobieństwie
- Niemożności wykonania złożonych symulacji (Monte Carlo, optymalizacja)

## Rozwiązanie

**Math Engine** — dedykowany silnik matematyczny, który Hermes wywołuje jako narzędzie. LLM tylko formułuje problem i interpretuje wyniki. Wszelkie obliczenia wykonuje Python + SymPy + NumPy + SciPy.

## Architektura

```
POV/13-math-engine/
├── math_engine.py          # Core engine (SymPy, NumPy, SciPy)
├── hermes_math_tool.py     # Bridge: Hermes ↔ Math Engine
├── test_math_engine.py     # 38 testów jednostkowych
├── demo_credit_vs_etf.py   # Demo: nadpłata kredytu vs ETF
├── demo_monte_carlo.py     # Demo: Monte Carlo, VaR, opcje
├── demo_statistics.py      # Demo: statystyka, testy, Bayes
├── demo_optimization.py    # Demo: optymalizacja, LP, portfel
├── output/                 # Wygenerowane wykresy (PNG)
├── requirements.txt        # Zależności
└── README.md               # Ten plik
```

## Możliwości

### Symboliczne (SymPy)
- Pochodne, całki (oznaczone i nieoznaczone)
- Rozwiązywanie równań i układów równań
- Upraszczanie, rozwijanie, faktoryzacja wyrażeń
- Granice, szeregi Taylora
- Równania różniczkowe zwyczajne
- Algebra macierzy (det, inv, eig, rref, rank)

### Numeryczne (NumPy/SciPy)
- Całkowanie numeryczne
- Znajdowanie miejsc zerowych
- Optymalizacja (minima/maksima)
- Rozwiązywanie ODE numerycznie
- Interpolacja
- FFT (transformata Fouriera)

### Statystyka i prawdopodobieństwo
- Rozkłady prawdopodobieństwa (PDF, CDF, kwantyle)
- Testy statystyczne (t-test, Shapiro-Wilk, chi², ANOVA)
- Regresja liniowa i wielomianowa
- Wnioskowanie bayesowskie
- Monte Carlo (całkowanie, symulacje)

### Optymalizacja
- Programowanie liniowe
- Optymalizacja nieliniowa
- Optymalizacja portfela (Markowitz)
- Dopasowanie krzywych (curve fitting)

## Demo apki

Każda demo apka generuje wykresy i wypisuje wyniki do konsoli.

### 1. Credit vs ETF
```bash
python3 demo_credit_vs_etf.py
# Z parametrami:
python3 demo_credit_vs_etf.py '{"mortgage_principal": 500000, "mortgage_rate": 0.08, "etf_return": 0.12}'
```
Generuje:
- Heatmapę: przy jakich stopach ETF wygrywa z nadpłatą kredytu
- Krzywą breakeven: jaki zwrot z ETF jest potrzebny
- Ścieżki net worth w czasie

### 2. Monte Carlo
```bash
python3 demo_monte_carlo.py
```
Generuje:
- Estymację π metodą Monte Carlo
- Value at Risk (VaR) dla portfela
- Wycenę opcji europejskiej (MC vs Black-Scholes)
- Estymację czasu projektu (PERT)
- Random walk / Brownian motion

### 3. Statystyka
```bash
python3 demo_statistics.py
```
Generuje:
- Galerię rozkładów prawdopodobieństwa
- Testy hipotez (t-test, ANOVA, chi², Shapiro-Wilk)
- Regresję liniową i wielomianową
- Wnioskowanie bayesowskie (coin flip, A/B test)
- Macierz korelacji

### 4. Optymalizacja
```bash
python3 demo_optimization.py
```
Generuje:
- Globalną optymalizację funkcji Rastrigina
- Programowanie liniowe (fabryka)
- Efficient frontier Markowitza
- Dopasowanie krzywej wykładniczej

## Integracja z Hermesem

```python
from hermes_math_tool import math_tool

# Symboliczne
math_tool("derivative", expr="x**3 + sin(x)", var="x")
math_tool("integral", expr="exp(-x**2)", var="x", a="0", b="oo")
math_tool("solve", equation="x**2 - 5*x + 6 = 0")

# Statystyka
math_tool("statistical_test", data=[1,2,3,4,5], test="normality")
math_tool("linear_regression", x=[1,2,3,4,5], y=[2,4,6,8,10])

# Demo wysokopoziomowe
math_tool("credit_vs_etf", mortgage_principal=400000, mortgage_rate=0.07, etf_return=0.10)
math_tool("portfolio_var", initial_value=100000, annual_volatility=0.20)
math_tool("option_price", S0=100, K=105, T=1.0, sigma=0.20)
```

## Testy

```bash
python3 -m pytest test_math_engine.py -v
# 38 testów, wszystkie przechodzą
```

## Zasada działania

1. Hermes dostaje pytanie matematyczne od użytkownika
2. Hermes **NIE liczy sam** — formułuje problem jako wywołanie `math_tool()`
3. Math Engine wykonuje obliczenia w Pythonie (SymPy/NumPy/SciPy)
4. Wynik wraca do Hermesa jako JSON z LaTeX-em i krokami
5. Hermes interpretuje wynik i prezentuje użytkownikowi

## Wymagania

- Python 3.10+
- sympy, numpy, scipy, matplotlib, pytest
- `pip install -r requirements.txt`

## Status

✅ Core engine: 38 testów
✅ 4 demo apki z wykresami
✅ Hermes integration tool
✅ AGENT_ASSIGNMENTS.md dla innych agentów

## Następne kroki (dla innych agentów)

- Algebra liniowa zaawansowana (SVD, PCA, dekompozycje)
- Równania różniczkowe cząstkowe (PDE)
- Szeregi czasowe i prognozowanie (ARIMA, GARCH)
- Teoria gier i teoria decyzji
- Geometria, topologia, fraktale, wizualizacje 3D
- Machine learning math (gradient descent, backpropagation)
