#!/usr/bin/env python3
"""
Credit vs ETF — Complete Decision Engine.
==========================================
"Kiedy opłaca się nadpłacać kredyt, a kiedy inwestować w ETF?"

LLM NIGDY nie liczy. Wszystkie obliczenia: NumPy/SciPy.
Generuje: heatmapy decyzyjne, krzywe break-even, Monte Carlo, analizę wrażliwości.

Usage:
  python3 credit_vs_etf.py                    — pełna analiza z wykresami
  python3 credit_vs_etf.py --breakeven         — tylko próg rentowności
  python3 credit_vs_etf.py --scenario NAME     — konkretny scenariusz
  python3 credit_vs_etf.py --monte-carlo       — symulacja Monte Carlo
"""

from __future__ import annotations

import sys
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.optimize import brentq

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CORE MATH — wszystkie wzory wyprowadzone analitycznie, nie przez LLM
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Scenario:
    """Parametry scenariusza kredyt vs ETF."""
    name: str
    mortgage_principal: float      # pozostały kapitał
    mortgage_rate: float           # oprocentowanie roczne
    mortgage_years_left: int       # pozostałe lata
    monthly_overpayment: float     # miesięczna nadpłata
    etf_expected_return: float     # oczekiwany zwrot ETF (rocznie)
    etf_volatility: float          # zmienność ETF (rocznie)
    tax_rate: float                # podatek od zysków kapitałowych (Belka = 0.19)
    inflation: float = 0.03        # inflacja


# Predefiniowane scenariusze (polskie realia 2026)
SCENARIOS = {
    "default": Scenario(
        "Standardowy kredyt 400k PLN", 400_000, 0.07, 25, 1000,
        0.10, 0.18, 0.19, 0.03,
    ),
    "high_rate": Scenario(
        "Wysokie stopy (9%)", 400_000, 0.09, 25, 1000,
        0.10, 0.18, 0.19, 0.03,
    ),
    "low_rate": Scenario(
        "Niskie stopy (4%)", 400_000, 0.04, 25, 1000,
        0.07, 0.15, 0.19, 0.03,
    ),
    "small_loan": Scenario(
        "Mały kredyt 200k PLN", 200_000, 0.07, 20, 800,
        0.10, 0.18, 0.19, 0.03,
    ),
    "big_loan": Scenario(
        "Duży kredyt 800k PLN", 800_000, 0.07, 30, 2000,
        0.10, 0.18, 0.19, 0.03,
    ),
    "aggressive_etf": Scenario(
        "Agresywny ETF (12%)", 400_000, 0.07, 25, 1000,
        0.12, 0.22, 0.19, 0.03,
    ),
    "conservative_etf": Scenario(
        "Konserwatywny ETF (6%)", 400_000, 0.07, 25, 1000,
        0.06, 0.12, 0.19, 0.03,
    ),
    "short_term": Scenario(
        "Krótki horyzont (5 lat)", 400_000, 0.07, 5, 2000,
        0.10, 0.18, 0.19, 0.03,
    ),
}


def monthly_payment(principal: float, annual_rate: float, years: int) -> float:
    """Rata miesięczna (annuitetowa)."""
    r = annual_rate / 12
    n = years * 12
    if r == 0:
        return principal / n
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def remaining_balance(principal: float, annual_rate: float, years_passed: int,
                      total_years: int) -> float:
    """Pozostały kapitał po N latach."""
    payment = monthly_payment(principal, annual_rate, total_years)
    r = annual_rate / 12
    n = years_passed * 12
    if r == 0:
        return max(0, principal - payment * n)
    return principal * (1 + r) ** n - payment * ((1 + r) ** n - 1) / r


def overpay_strategy(scenario: Scenario) -> dict:
    """Strategia nadpłaty: co miesiąc nadpłacamy, zmniejszamy kapitał."""
    r = scenario.mortgage_rate / 12
    n_total = scenario.mortgage_years_left * 12
    balance = scenario.mortgage_principal
    payment = monthly_payment(scenario.mortgage_principal, scenario.mortgage_rate,
                              scenario.mortgage_years_left)
    total_interest = 0.0
    months = 0

    while balance > 0 and months < n_total:
        interest = balance * r
        principal_paid = min(payment + scenario.monthly_overpayment - interest, balance)
        if principal_paid <= 0:
            break
        balance -= principal_paid
        total_interest += interest
        months += 1

    return {
        "months_to_payoff": months,
        "years_to_payoff": months / 12,
        "total_interest_paid": total_interest,
        "total_overpayment": scenario.monthly_overpayment * months,
    }


def invest_strategy(scenario: Scenario) -> dict:
    """Strategia inwestycyjna: nadpłatę inwestujemy w ETF, kredyt spłacamy normalnie."""
    r_etf = scenario.etf_expected_return / 12
    n = scenario.mortgage_years_left * 12
    portfolio = 0.0
    total_invested = 0.0

    for _ in range(n):
        portfolio = portfolio * (1 + r_etf) + scenario.monthly_overpayment
        total_invested += scenario.monthly_overpayment

    # Podatek Belki od zysku
    gain = portfolio - total_invested
    tax = gain * scenario.tax_rate
    net_portfolio = portfolio - tax

    # Pozostały kapitał po normalnej spłacie
    final_balance = remaining_balance(scenario.mortgage_principal, scenario.mortgage_rate,
                                      scenario.mortgage_years_left, scenario.mortgage_years_left)

    return {
        "gross_portfolio": portfolio,
        "net_portfolio": net_portfolio,
        "total_invested": total_invested,
        "capital_gain": gain,
        "tax_paid": tax,
        "final_mortgage_balance": final_balance,
        "net_worth": net_portfolio - final_balance,
    }


def breakeven_rate(mortgage_rate: float, tax_rate: float) -> float:
    """
    Analityczny próg rentowności ETF.
    Wyprowadzenie:
      Nadpłata oszczędza: mortgage_rate (tax-free)
      Inwestycja zarabia: etf_return * (1 - tax_rate)
      Próg: mortgage_rate = etf_return * (1 - tax_rate)
      → etf_return = mortgage_rate / (1 - tax_rate)
    """
    return mortgage_rate / (1 - tax_rate)


def net_worth_difference(scenario: Scenario) -> float:
    """Różnica w majątku netto: inwestowanie - nadpłata."""
    inv = invest_strategy(scenario)
    over = overpay_strategy(scenario)

    # Przy nadpłacie: majątek = 0 (kredyt spłacony) + zaoszczędzone odsetki
    # Przy inwestycji: majątek = portfolio_net - pozostały_kapitał
    over_net = 0.0  # kredyt spłacony

    return inv["net_worth"] - over_net


def monte_carlo_simulation(scenario: Scenario, n_simulations: int = 10_000) -> dict:
    """Monte Carlo: rozkład wyniku netto strategii inwestycyjnej."""
    r_etf_monthly = scenario.etf_expected_return / 12
    vol_monthly = scenario.etf_volatility / np.sqrt(12)
    n_months = scenario.mortgage_years_left * 12

    final_values = np.zeros(n_simulations)

    for i in range(n_simulations):
        returns = np.random.normal(r_etf_monthly, vol_monthly, n_months)
        portfolio = 0.0
        for r in returns:
            portfolio = portfolio * (1 + r) + scenario.monthly_overpayment

        gain = portfolio - scenario.monthly_overpayment * n_months
        tax = max(0, gain * scenario.tax_rate)
        net = portfolio - tax

        final_balance = remaining_balance(scenario.mortgage_principal, scenario.mortgage_rate,
                                          scenario.mortgage_years_left, scenario.mortgage_years_left)
        final_values[i] = net - final_balance

    # Nadpłata — deterministyczna
    over = overpay_strategy(scenario)
    over_net = 0.0

    return {
        "median": float(np.median(final_values)),
        "mean": float(np.mean(final_values)),
        "std": float(np.std(final_values)),
        "p5": float(np.percentile(final_values, 5)),
        "p25": float(np.percentile(final_values, 25)),
        "p75": float(np.percentile(final_values, 75)),
        "p95": float(np.percentile(final_values, 95)),
        "prob_positive": float(np.mean(final_values > over_net)),
        "overpay_net_worth": over_net,
        "values": final_values,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# VISUALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def plot_breakeven_curve():
    """Krzywa progu rentowności: mortgage_rate vs ETF return."""
    fig, ax = plt.subplots(figsize=(10, 6))

    mortgage_rates = np.linspace(0.02, 0.12, 100)
    tax_rates = [0.19, 0.25, 0.30, 0.35]

    for tax in tax_rates:
        breakeven = mortgage_rates / (1 - tax)
        ax.plot(mortgage_rates * 100, breakeven * 100, linewidth=2,
                label=f'Podatek {tax*100:.0f}%')

    ax.fill_between(mortgage_rates * 100, 0, 15, alpha=0.05, color='green')
    ax.fill_between(mortgage_rates * 100, 0, 15, alpha=0.05, color='red',
                    where=(mortgage_rates * 100 > 8))

    ax.set_xlabel('Oprocentowanie kredytu (%)', fontsize=12)
    ax.set_ylabel('Próg rentowności ETF (%)', fontsize=12)
    ax.set_title('Kredyt vs ETF — Próg Rentowności\n'
                 'Powyżej krzywej: inwestuj w ETF | Poniżej krzywej: nadpłacaj kredyt',
                 fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(2, 12)
    ax.set_ylim(0, 18)

    # Adnotacja: Polska 2026
    ax.annotate('Polska 2026\nkredyt 7%, Belka 19%\npróg = 8.64%',
                xy=(7, 8.64), xytext=(4, 12),
                arrowprops=dict(arrowstyle='->', color='black', lw=1.5),
                fontsize=10, bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))

    plt.tight_layout()
    path = OUTPUT_DIR / "credit_vs_etf_breakeven_curve.png"
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    return path


def plot_decision_heatmap():
    """Heatmapa: która strategia wygrywa przy różnych parametrach."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Heatmap 1: mortgage_rate × etf_return
    ax = axes[0]
    mortgage_rates = np.linspace(0.02, 0.12, 50)
    etf_returns = np.linspace(0.04, 0.16, 50)
    Z = np.zeros((len(etf_returns), len(mortgage_rates)))

    for i, er in enumerate(etf_returns):
        for j, mr in enumerate(mortgage_rates):
            s = Scenario("", 400_000, mr, 25, 1000, er, 0.18, 0.19, 0.03)
            Z[i, j] = net_worth_difference(s)

    im = ax.contourf(mortgage_rates * 100, etf_returns * 100, Z / 1000,
                     levels=20, cmap='RdBu_r')
    ax.contour(mortgage_rates * 100, etf_returns * 100, Z / 1000,
               levels=[0], colors='black', linewidths=2, linestyles='--')
    plt.colorbar(im, ax=ax, label='Różnica majątku (tys. PLN)')
    ax.set_xlabel('Oprocentowanie kredytu (%)', fontsize=11)
    ax.set_ylabel('Oczekiwany zwrot ETF (%)', fontsize=11)
    ax.set_title('Kredyt vs ETF — Mapa Decyzyjna\n'
                 'Czerwony = nadpłacaj | Niebieski = inwestuj', fontsize=12)

    # Heatmap 2: monthly_overpayment × years_left
    ax = axes[1]
    overpayments = np.linspace(200, 3000, 50)
    years_left = np.linspace(5, 30, 50)
    Z2 = np.zeros((len(years_left), len(overpayments)))

    for i, yl in enumerate(years_left):
        for j, op in enumerate(overpayments):
            s = Scenario("", 400_000, 0.07, int(yl), op, 0.10, 0.18, 0.19, 0.03)
            Z2[i, j] = net_worth_difference(s)

    im2 = ax.contourf(overpayments / 1000, years_left, Z2 / 1000,
                      levels=20, cmap='RdBu_r')
    ax.contour(overpayments / 1000, years_left, Z2 / 1000,
               levels=[0], colors='black', linewidths=2, linestyles='--')
    plt.colorbar(im2, ax=ax, label='Różnica majątku (tys. PLN)')
    ax.set_xlabel('Miesięczna nadpłata (tys. PLN)', fontsize=11)
    ax.set_ylabel('Pozostałe lata kredytu', fontsize=11)
    ax.set_title('Wpływ wysokości nadpłaty i horyzontu\n'
                 'Czerwony = nadpłacaj | Niebieski = inwestuj', fontsize=12)

    plt.tight_layout()
    path = OUTPUT_DIR / "credit_vs_etf_decision_heatmap.png"
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    return path


def plot_scenario_comparison(scenarios: dict[str, Scenario]):
    """Porównanie wszystkich scenariuszy."""
    names = list(scenarios.keys())
    n = len(names)

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # 1. Net worth difference (bar chart)
    ax = axes[0, 0]
    diffs = [net_worth_difference(s) for s in scenarios.values()]
    colors = ['#2ecc71' if d > 0 else '#e74c3c' for d in diffs]
    bars = ax.bar(range(n), [d / 1000 for d in diffs], color=colors, alpha=0.8)
    ax.axhline(y=0, color='black', linewidth=1)
    ax.set_xticks(range(n))
    ax.set_xticklabels([s.name[:25] for s in scenarios.values()], rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('Różnica majątku (tys. PLN)', fontsize=11)
    ax.set_title('Inwestowanie vs Nadpłata — Różnica w Majątku', fontsize=12)
    for bar, d in zip(bars, diffs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                f'{d/1000:+.0f}k', ha='center', fontsize=8)

    # 2. Break-even rates
    ax = axes[0, 1]
    be_rates = [breakeven_rate(s.mortgage_rate, s.tax_rate) * 100 for s in scenarios.values()]
    etf_returns = [s.etf_expected_return * 100 for s in scenarios.values()]
    x = np.arange(n)
    width = 0.35
    ax.bar(x - width / 2, be_rates, width, label='Próg rentowności', color='orange', alpha=0.8)
    ax.bar(x + width / 2, etf_returns, width, label='Oczekiwany zwrot ETF', color='blue', alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([s.name[:25] for s in scenarios.values()], rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('% rocznie', fontsize=11)
    ax.set_title('Próg Rentowności vs Oczekiwany Zwrot', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, axis='y')

    # 3. Monte Carlo distribution (for default scenario)
    ax = axes[1, 0]
    mc = monte_carlo_simulation(scenarios["default"], n_simulations=10_000)
    ax.hist(mc["values"] / 1000, bins=80, color='steelblue', alpha=0.7, edgecolor='white')
    ax.axvline(x=0, color='red', linewidth=2, linestyle='--', label='Nadpłata (0)')
    ax.axvline(x=mc["median"] / 1000, color='green', linewidth=2, label=f'Mediana: {mc["median"]/1000:+.0f}k')
    ax.set_xlabel('Wartość netto (tys. PLN)', fontsize=11)
    ax.set_ylabel('Liczba symulacji', fontsize=11)
    ax.set_title(f'Monte Carlo (10k symulacji)\n'
                 f'P(inwestycja lepsza) = {mc["prob_positive"]:.1%}', fontsize=12)
    ax.legend(fontsize=9)

    # 4. Sensitivity: ETF return vs volatility
    ax = axes[1, 1]
    etf_range = np.linspace(0.04, 0.16, 30)
    vol_range = [0.10, 0.15, 0.20, 0.25]
    for vol in vol_range:
        diffs = []
        for er in etf_range:
            s = Scenario("", 400_000, 0.07, 25, 1000, er, vol, 0.19, 0.03)
            diffs.append(net_worth_difference(s) / 1000)
        ax.plot(etf_range * 100, diffs, linewidth=2, label=f'Zmienność {vol*100:.0f}%')

    ax.axhline(y=0, color='black', linewidth=1, linestyle='--')
    ax.axvline(x=breakeven_rate(0.07, 0.19) * 100, color='red', linewidth=1.5,
               linestyle=':', label=f'Próg {breakeven_rate(0.07, 0.19)*100:.1f}%')
    ax.set_xlabel('Oczekiwany zwrot ETF (%)', fontsize=11)
    ax.set_ylabel('Różnica majątku (tys. PLN)', fontsize=11)
    ax.set_title('Wrażliwość na zwrot i zmienność ETF', fontsize=12)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "credit_vs_etf_scenarios.png"
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    return path


def plot_monte_carlo_paths(scenario: Scenario, n_paths: int = 50):
    """Wizualizacja ścieżek Monte Carlo."""
    r_etf = scenario.etf_expected_return / 12
    vol = scenario.etf_volatility / np.sqrt(12)
    n_months = scenario.mortgage_years_left * 12
    months = np.arange(n_months + 1)

    fig, ax = plt.subplots(figsize=(12, 6))

    # Symulowane ścieżki
    for _ in range(n_paths):
        returns = np.random.normal(r_etf, vol, n_months)
        portfolio = np.zeros(n_months + 1)
        for t in range(n_months):
            portfolio[t + 1] = portfolio[t] * (1 + returns[t]) + scenario.monthly_overpayment
        ax.plot(months / 12, portfolio / 1000, alpha=0.15, color='blue', linewidth=0.5)

    # Ścieżka oczekiwana (deterministyczna)
    expected = np.zeros(n_months + 1)
    for t in range(n_months):
        expected[t + 1] = expected[t] * (1 + r_etf) + scenario.monthly_overpayment
    ax.plot(months / 12, expected / 1000, 'r-', linewidth=2.5, label='Oczekiwana')

    # Nadpłata — oszczędności
    over = overpay_strategy(scenario)
    ax.axhline(y=0, color='green', linewidth=2, linestyle='--',
               label=f'Nadpłata: kredyt spłacony w {over["years_to_payoff"]:.1f} lat')

    ax.set_xlabel('Lata', fontsize=12)
    ax.set_ylabel('Wartość portfela (tys. PLN)', fontsize=12)
    ax.set_title(f'Monte Carlo — {n_paths} ścieżek ETF vs Nadpłata\n'
                 f'{scenario.name}', fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "credit_vs_etf_monte_carlo_paths.png"
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    return path


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def print_analysis(scenario: Scenario):
    """Wydrukuj pełną analizę dla scenariusza."""
    inv = invest_strategy(scenario)
    over = overpay_strategy(scenario)
    be = breakeven_rate(scenario.mortgage_rate, scenario.tax_rate)
    diff = net_worth_difference(scenario)
    mc = monte_carlo_simulation(scenario, n_simulations=10_000)

    print(f"\n{'='*60}")
    print(f"📊 {scenario.name}")
    print(f"{'='*60}")
    print(f"  Kapitał: {scenario.mortgage_principal:,.0f} PLN")
    print(f"  Oprocentowanie: {scenario.mortgage_rate*100:.1f}%")
    print(f"  Pozostałe lata: {scenario.mortgage_years_left}")
    print(f"  Miesięczna nadpłata: {scenario.monthly_overpayment:,.0f} PLN")
    print(f"  Oczekiwany zwrot ETF: {scenario.etf_expected_return*100:.1f}%")
    print(f"  Zmienność ETF: {scenario.etf_volatility*100:.1f}%")
    print(f"  Podatek: {scenario.tax_rate*100:.0f}%")
    print()

    print(f"  📈 PRÓG RENTOWNOŚCI ETF: {be*100:.2f}%")
    print(f"     (przy oprocentowaniu {scenario.mortgage_rate*100:.1f}% i podatku {scenario.tax_rate*100:.0f}%)")
    print(f"     → ETF musi zarabiać > {be*100:.2f}% rocznie, żeby inwestowanie się opłacało")
    print()

    print(f"  💰 STRATEGIA NADPŁATY:")
    print(f"     Kredyt spłacony w: {over['years_to_payoff']:.1f} lat ({over['months_to_payoff']} mies.)")
    print(f"     Łączne odsetki: {over['total_interest_paid']:,.0f} PLN")
    print(f"     Łączna nadpłata: {over['total_overpayment']:,.0f} PLN")
    print()

    print(f"  📊 STRATEGIA INWESTYCYJNA:")
    print(f"     Portfel brutto: {inv['gross_portfolio']:,.0f} PLN")
    print(f"     Zysk kapitałowy: {inv['capital_gain']:,.0f} PLN")
    print(f"     Podatek Belki: {inv['tax_paid']:,.0f} PLN")
    print(f"     Portfel netto: {inv['net_portfolio']:,.0f} PLN")
    print(f"     Pozostały kredyt: {inv['final_mortgage_balance']:,.0f} PLN")
    print(f"     MAJĄTEK NETTO: {inv['net_worth']:,.0f} PLN")
    print()

    print(f"  ⚖️  RÓŻNICA (inwestowanie - nadpłata): {diff:+,.0f} PLN")
    if diff > 0:
        print(f"     ✅ INWESTUJ w ETF — zyskujesz {diff:,.0f} PLN więcej")
    else:
        print(f"     ❌ NADPŁACAJ kredyt — oszczędzasz {-diff:,.0f} PLN więcej")
    print()

    print(f"  🎲 MONTE CARLO (10,000 symulacji):")
    print(f"     Mediana: {mc['median']:+,.0f} PLN")
    print(f"     Średnia: {mc['mean']:+,.0f} PLN")
    print(f"     Odch. std: {mc['std']:,.0f} PLN")
    print(f"     P5-P95: [{mc['p5']:+,.0f}, {mc['p95']:+,.0f}] PLN")
    print(f"     P(inwestycja lepsza): {mc['prob_positive']:.1%}")
    print()


def main():
    print("=" * 60)
    print("🏦 KREDYT vs ETF — PEŁNA ANALIZA DECYZYJNA")
    print("=" * 60)

    # 1. Próg rentowności
    print(f"\n🔑 KLUCZOWY WZÓR (analityczny):")
    print(f"   Próg rentowności ETF = oprocentowanie_kredytu / (1 - podatek)")
    print(f"   Dla Polski 2026: 7% / (1 - 0.19) = {breakeven_rate(0.07, 0.19)*100:.2f}%")
    print(f"   → Jeśli ETF zarabia > 8.64% rocznie → inwestuj")
    print(f"   → Jeśli ETF zarabia < 8.64% rocznie → nadpłacaj kredyt")

    # 2. Analiza wszystkich scenariuszy
    for name, scenario in SCENARIOS.items():
        print_analysis(scenario)

    # 3. Wykresy
    print("Generowanie wykresów...")
    paths = []

    p = plot_breakeven_curve()
    paths.append(p)
    print(f"  ✅ Krzywa progu rentowności: {p}")

    p = plot_decision_heatmap()
    paths.append(p)
    print(f"  ✅ Heatmapa decyzyjna: {p}")

    p = plot_scenario_comparison(SCENARIOS)
    paths.append(p)
    print(f"  ✅ Porównanie scenariuszy: {p}")

    p = plot_monte_carlo_paths(SCENARIOS["default"])
    paths.append(p)
    print(f"  ✅ Ścieżki Monte Carlo: {p}")

    print(f"\n✅ WSZYSTKIE ANALIZY ZAKOŃCZONE")
    print(f"   Wykresy w: {OUTPUT_DIR}/")


if __name__ == "__main__":
    if "--breakeven" in sys.argv:
        be = breakeven_rate(0.07, 0.19)
        print(f"Próg rentowności ETF: {be*100:.2f}%")
        print(f"Wzór: mortgage_rate / (1 - tax_rate) = 0.07 / 0.81 = {be*100:.2f}%")
    elif "--scenario" in sys.argv:
        idx = sys.argv.index("--scenario")
        name = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "default"
        s = SCENARIOS.get(name, SCENARIOS["default"])
        print_analysis(s)
    elif "--monte-carlo" in sys.argv:
        s = SCENARIOS["default"]
        mc = monte_carlo_simulation(s, n_simulations=50_000)
        print(f"Monte Carlo (50k symulacji):")
        print(f"  Mediana: {mc['median']:+,.0f} PLN")
        print(f"  P(inwestycja lepsza): {mc['prob_positive']:.1%}")
        print(f"  P5-P95: [{mc['p5']:+,.0f}, {mc['p95']:+,.0f}] PLN")
    else:
        main()
