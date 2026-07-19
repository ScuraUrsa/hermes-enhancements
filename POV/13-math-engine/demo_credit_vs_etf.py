"""
Credit vs ETF — Interactive Decision Demo.

"When should I overpay my mortgage vs invest in an ETF?"

This demo computes the net worth difference between two strategies:
1. Overpay mortgage (reduce principal → less interest)
2. Invest the same amount in ETF (compound growth)

Generates decision heatmaps showing which strategy wins at different parameters.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Add parent to path for math_engine import
sys.path.insert(0, str(Path(__file__).parent))
from math_engine import MathEngine

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def mortgage_balance(principal: float, annual_rate: float, years: int,
                     monthly_payment: float) -> float:
    """Compute remaining mortgage balance after `years`."""
    monthly_rate = annual_rate / 12
    n_payments = years * 12
    # Standard amortization formula
    if monthly_rate == 0:
        return max(0, principal - monthly_payment * n_payments)
    growth = (1 + monthly_rate) ** n_payments
    balance = principal * growth - monthly_payment * (growth - 1) / monthly_rate
    return max(0, balance)


def monthly_payment_for_principal(principal: float, annual_rate: float,
                                  total_years: int) -> float:
    """Compute fixed monthly payment for a fully amortizing loan."""
    monthly_rate = annual_rate / 12
    n = total_years * 12
    if monthly_rate == 0:
        return principal / n
    return principal * monthly_rate * (1 + monthly_rate) ** n / ((1 + monthly_rate) ** n - 1)


def simulate_strategies(
    mortgage_principal: float,
    mortgage_rate: float,
    mortgage_years: int,
    extra_payment: float,
    etf_return: float,
    etf_volatility: float,
    investment_horizon: int,
    n_simulations: int = 1000,
) -> dict:
    """
    Simulate two strategies:
    A: Overpay mortgage with `extra_payment`/month
    B: Invest `extra_payment`/month in ETF

    Returns net worth difference (B - A) statistics.
    """
    monthly_payment = monthly_payment_for_principal(
        mortgage_principal, mortgage_rate, mortgage_years
    )

    # Strategy A: Overpay
    # Each month: pay monthly_payment + extra_payment
    # Mortgage paid off faster → then invest freed cash flow in ETF
    balance_a = mortgage_principal
    month = 0
    total_months = investment_horizon * 12
    etf_balance_a = 0.0
    monthly_etf_return = etf_return / 12

    while month < total_months:
        if balance_a > 0:
            interest = balance_a * mortgage_rate / 12
            total_pay = min(monthly_payment + extra_payment, balance_a + interest)
            principal_pay = total_pay - interest
            balance_a -= principal_pay
        else:
            # Mortgage paid off — invest freed cash flow
            etf_balance_a *= (1 + monthly_etf_return)
            etf_balance_a += monthly_payment + extra_payment
        month += 1

    # Strategy B: Invest extra in ETF, pay minimum mortgage
    balance_b = mortgage_principal
    etf_balance_b = 0.0
    rng = np.random.RandomState(42)

    # Monte Carlo for ETF returns
    all_diffs = []
    for sim in range(n_simulations):
        bal_b = mortgage_principal
        etf_b = 0.0
        for m in range(total_months):
            # Mortgage
            if bal_b > 0:
                interest = bal_b * mortgage_rate / 12
                total_pay = min(monthly_payment, bal_b + interest)
                principal_pay = total_pay - interest
                bal_b -= principal_pay
            # ETF
            monthly_ret = rng.normal(monthly_etf_return, etf_volatility / np.sqrt(12))
            etf_b *= (1 + monthly_ret)
            etf_b += extra_payment
        # Net worth = -mortgage_balance + etf_balance
        nw_a = -balance_a + etf_balance_a
        nw_b = -bal_b + etf_b
        all_diffs.append(nw_b - nw_a)

    diffs = np.array(all_diffs)
    return {
        "strategy_a_net_worth": float(-balance_a + etf_balance_a),
        "strategy_b_mean_net_worth": float(np.mean([-balance_a + etf_balance_a + d for d in diffs])),
        "difference_mean": float(np.mean(diffs)),
        "difference_std": float(np.std(diffs)),
        "difference_p5": float(np.percentile(diffs, 5)),
        "difference_p95": float(np.percentile(diffs, 95)),
        "prob_etf_wins": float(np.mean(diffs > 0)),
        "mortgage_paid_off_month_a": int((mortgage_principal - balance_a) / (monthly_payment + extra_payment)) if balance_a <= 0 else total_months,
    }


def generate_heatmap(
    mortgage_principal: float = 400_000,
    mortgage_rate: float = 0.07,
    mortgage_years: int = 25,
    extra_payment: float = 1000,
    investment_horizon: int = 20,
):
    """Generate heatmap: ETF return vs Mortgage rate → which strategy wins."""
    etf_returns = np.linspace(0.03, 0.15, 7)
    mortgage_rates = np.linspace(0.03, 0.12, 6)
    volatilities = [0.10, 0.15, 0.20]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(
        f"Overpay Mortgage vs Invest ETF\n"
        f"Mortgage: {mortgage_principal:,.0f} PLN, {mortgage_years}y, Extra: {extra_payment:,.0f} PLN/mo, Horizon: {investment_horizon}y",
        fontsize=12, fontweight="bold",
    )

    for idx, vol in enumerate(volatilities):
        ax = axes[idx]
        data = np.zeros((len(mortgage_rates), len(etf_returns)))

        for i, mr in enumerate(mortgage_rates):
            for j, er in enumerate(etf_returns):
                result = simulate_strategies(
                    mortgage_principal, mr, mortgage_years,
                    extra_payment, er, vol, investment_horizon,
                    n_simulations=200,
                )
                data[i, j] = result["prob_etf_wins"]

        im = ax.imshow(data, aspect="auto", origin="lower", cmap="RdYlGn",
                       vmin=0, vmax=1)
        ax.set_xticks(range(len(etf_returns)))
        ax.set_xticklabels([f"{r:.0%}" for r in etf_returns], rotation=45, fontsize=8)
        ax.set_yticks(range(len(mortgage_rates)))
        ax.set_yticklabels([f"{r:.0%}" for r in mortgage_rates], fontsize=8)
        ax.set_xlabel("ETF Annual Return", fontsize=9)
        ax.set_ylabel("Mortgage Rate", fontsize=9)
        ax.set_title(f"ETF Volatility = {vol:.0%}", fontsize=10)

        # Annotate cells
        for i in range(len(mortgage_rates)):
            for j in range(len(etf_returns)):
                color = "white" if data[i, j] < 0.3 or data[i, j] > 0.7 else "black"
                ax.text(j, i, f"{data[i, j]:.0%}", ha="center", va="center",
                        fontsize=7, color=color)

    plt.colorbar(im, ax=axes, label="Probability ETF Wins", shrink=0.8)
    plt.tight_layout()
    path = OUTPUT_DIR / "credit_vs_etf_heatmap.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Heatmap saved: {path}")
    return path


def generate_breakeven_curve(
    mortgage_principal: float = 400_000,
    mortgage_rate: float = 0.07,
    mortgage_years: int = 25,
    investment_horizon: int = 20,
):
    """Generate breakeven curve: what ETF return is needed to beat overpaying?"""
    extra_payments = np.linspace(200, 5000, 15)
    volatilities = [0.10, 0.15, 0.20]

    fig, ax = plt.subplots(figsize=(10, 6))

    for vol in volatilities:
        breakeven_returns = []
        for extra in extra_payments:
            # Binary search for breakeven ETF return
            lo, hi = 0.01, 0.25
            for _ in range(12):
                mid = (lo + hi) / 2
                result = simulate_strategies(
                    mortgage_principal, mortgage_rate, mortgage_years,
                    extra, mid, vol, investment_horizon,
                    n_simulations=100,
                )
                if result["prob_etf_wins"] > 0.5:
                    hi = mid
                else:
                    lo = mid
            breakeven_returns.append((lo + hi) / 2)
        ax.plot(extra_payments, [r * 100 for r in breakeven_returns],
                label=f"Volatility {vol:.0%}", linewidth=2)

    ax.axhline(y=mortgage_rate * 100, color="red", linestyle="--",
               label=f"Mortgage Rate ({mortgage_rate:.1%})", linewidth=2)
    ax.set_xlabel("Extra Payment (PLN/month)", fontsize=11)
    ax.set_ylabel("Breakeven ETF Return (%)", fontsize=11)
    ax.set_title(
        f"What ETF return do you need to beat overpaying?\n"
        f"Mortgage: {mortgage_principal:,.0f} PLN, {mortgage_rate:.1%}, {mortgage_years}y, Horizon: {investment_horizon}y",
        fontsize=12, fontweight="bold",
    )
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(extra_payments[0], extra_payments[-1])

    plt.tight_layout()
    path = OUTPUT_DIR / "credit_vs_etf_breakeven.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Breakeven curve saved: {path}")
    return path


def generate_net_worth_paths(
    mortgage_principal: float = 400_000,
    mortgage_rate: float = 0.07,
    mortgage_years: int = 25,
    extra_payment: float = 1000,
    etf_return: float = 0.10,
    etf_volatility: float = 0.15,
    investment_horizon: int = 25,
):
    """Generate net worth paths over time for both strategies."""
    monthly_payment = monthly_payment_for_principal(
        mortgage_principal, mortgage_rate, mortgage_years
    )
    total_months = investment_horizon * 12
    months = np.arange(total_months + 1)

    # Strategy A: Overpay
    nw_a = np.zeros(total_months + 1)
    balance_a = mortgage_principal
    etf_a = 0.0
    monthly_etf = etf_return / 12

    for m in range(1, total_months + 1):
        if balance_a > 0:
            interest = balance_a * mortgage_rate / 12
            total_pay = min(monthly_payment + extra_payment, balance_a + interest)
            principal_pay = total_pay - interest
            balance_a -= principal_pay
        else:
            etf_a *= (1 + monthly_etf)
            etf_a += monthly_payment + extra_payment
        nw_a[m] = -balance_a + etf_a

    # Strategy B: Invest
    nw_b = np.zeros(total_months + 1)
    balance_b = mortgage_principal
    etf_b = 0.0

    for m in range(1, total_months + 1):
        if balance_b > 0:
            interest = balance_b * mortgage_rate / 12
            total_pay = min(monthly_payment, balance_b + interest)
            principal_pay = total_pay - interest
            balance_b -= principal_pay
        etf_b *= (1 + monthly_etf)
        etf_b += extra_payment
        nw_b[m] = -balance_b + etf_b

    fig, ax = plt.subplots(figsize=(12, 6))
    years = months / 12

    ax.plot(years, nw_a / 1000, label="Strategy A: Overpay Mortgage", linewidth=2, color="#2196F3")
    ax.plot(years, nw_b / 1000, label="Strategy B: Invest in ETF", linewidth=2, color="#4CAF50")
    ax.fill_between(years, nw_a / 1000, nw_b / 1000,
                    where=(nw_b >= nw_a), color="green", alpha=0.1, label="ETF Wins")
    ax.fill_between(years, nw_a / 1000, nw_b / 1000,
                    where=(nw_b < nw_a), color="blue", alpha=0.1, label="Overpay Wins")

    ax.axhline(y=0, color="gray", linestyle=":", alpha=0.5)
    ax.set_xlabel("Years", fontsize=11)
    ax.set_ylabel("Net Worth (k PLN)", fontsize=11)
    ax.set_title(
        f"Net Worth Over Time: Overpay vs Invest\n"
        f"Mortgage: {mortgage_principal:,.0f} PLN @ {mortgage_rate:.1%}, "
        f"Extra: {extra_payment:,.0f} PLN/mo, ETF: {etf_return:.1%}",
        fontsize=12, fontweight="bold",
    )
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, investment_horizon)

    plt.tight_layout()
    path = OUTPUT_DIR / "credit_vs_etf_paths.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Net worth paths saved: {path}")
    return path


def main():
    print("=" * 60)
    print("CREDIT VS ETF — Decision Analysis")
    print("=" * 60)

    # Default parameters (Polish mortgage market, 2026)
    params = {
        "mortgage_principal": 400_000,
        "mortgage_rate": 0.07,
        "mortgage_years": 25,
        "extra_payment": 1000,
        "etf_return": 0.10,
        "etf_volatility": 0.15,
        "investment_horizon": 20,
    }

    # Override from command line
    if len(sys.argv) > 1:
        try:
            params.update(json.loads(sys.argv[1]))
        except json.JSONDecodeError:
            print(f"Usage: python {Path(__file__).name} '{{\"mortgage_principal\": 400000, ...}}'")
            print(f"Using defaults: {json.dumps(params, indent=2)}")

    print(f"\nParameters: {json.dumps(params, indent=2)}")

    # Run simulation
    print("\n--- Monte Carlo Simulation ---")
    result = simulate_strategies(**params, n_simulations=500)

    print(f"\nStrategy A (Overpay): Net Worth = {result['strategy_a_net_worth']:,.0f} PLN")
    print(f"Strategy B (ETF):     Mean Net Worth = {result['strategy_b_mean_net_worth']:,.0f} PLN")
    print(f"Difference (B - A):   Mean = {result['difference_mean']:,.0f} PLN")
    print(f"                      Std  = {result['difference_std']:,.0f} PLN")
    print(f"                      5th  = {result['difference_p5']:,.0f} PLN")
    print(f"                      95th = {result['difference_p95']:,.0f} PLN")
    print(f"Probability ETF Wins: {result['prob_etf_wins']:.1%}")

    # Generate charts
    print("\n--- Generating Charts ---")
    generate_heatmap(**{k: params[k] for k in ["mortgage_principal", "mortgage_rate", "mortgage_years", "extra_payment", "investment_horizon"]})
    generate_breakeven_curve(**{k: params[k] for k in ["mortgage_principal", "mortgage_rate", "mortgage_years", "investment_horizon"]})
    generate_net_worth_paths(**params)

    # Decision summary
    print("\n--- Decision Summary ---")
    if result["prob_etf_wins"] > 0.7:
        print("✅ STRONG ETF: Investing in ETF is very likely to beat overpaying.")
    elif result["prob_etf_wins"] > 0.5:
        print("🟡 SLIGHT ETF: ETF has a small edge, but it's close.")
    elif result["prob_etf_wins"] > 0.3:
        print("🟠 SLIGHT OVERPAY: Overpaying has a small edge.")
    else:
        print("🔴 STRONG OVERPAY: Overpaying the mortgage is very likely better.")

    print(f"\nKey insight: With mortgage rate {params['mortgage_rate']:.1%} and ETF return {params['etf_return']:.1%}, "
          f"the {'ETF' if params['etf_return'] > params['mortgage_rate'] else 'mortgage'} has the mathematical edge, "
          f"but volatility ({params['etf_volatility']:.0%}) creates uncertainty.")
    print(f"\nAll charts saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
