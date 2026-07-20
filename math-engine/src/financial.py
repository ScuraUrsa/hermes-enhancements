"""
Financial Math Solver — mortgage, ETF, NPV, IRR, portfolio optimization.
The core "kredyt vs ETF" analysis lives here.

LLM NEVER computes — this module does the actual financial math.
"""

from __future__ import annotations

import re
import math
import numpy as np
from scipy import optimize
from typing import Optional, Any
from dataclasses import dataclass, field

from .engine import SolveResult, ProblemType


# ═══════════════════════════════════════════════════════════
# MORTGAGE MATH
# ═══════════════════════════════════════════════════════════

@dataclass
class MortgageParams:
    """Parameters for mortgage analysis."""
    loan_amount: float          # kwota kredytu (PLN)
    annual_rate: float          # oprocentowanie roczne (np. 0.07 = 7%)
    years: int                  # okres kredytowania
    monthly_payment: Optional[float] = None  # obliczane
    total_cost: Optional[float] = None
    total_interest: Optional[float] = None


def calculate_mortgage(loan: float, annual_rate: float, years: int) -> MortgageParams:
    """Calculate monthly payment and total cost for a mortgage."""
    monthly_rate = annual_rate / 12
    n_payments = years * 12

    if monthly_rate == 0:
        monthly_payment = loan / n_payments
    else:
        monthly_payment = loan * (monthly_rate * (1 + monthly_rate) ** n_payments) / \
                          ((1 + monthly_rate) ** n_payments - 1)

    total_cost = monthly_payment * n_payments
    total_interest = total_cost - loan

    return MortgageParams(
        loan_amount=loan,
        annual_rate=annual_rate,
        years=years,
        monthly_payment=round(monthly_payment, 2),
        total_cost=round(total_cost, 2),
        total_interest=round(total_interest, 2),
    )


def amortization_schedule(loan: float, annual_rate: float, years: int,
                           overpayments: list[tuple[int, float]] = None) -> list[dict]:
    """Generate full amortization schedule with optional overpayments.
    overpayments: list of (month_number, amount) tuples.
    """
    monthly_rate = annual_rate / 12
    n_payments = years * 12
    balance = loan
    standard_payment = calculate_mortgage(loan, annual_rate, years).monthly_payment

    overpayment_map = {}
    if overpayments:
        overpayment_map = {m: amt for m, amt in overpayments}

    schedule = []
    total_interest_paid = 0
    month = 0

    while balance > 0 and month < n_payments * 2:  # safety limit
        month += 1
        interest = balance * monthly_rate
        principal = standard_payment - interest
        extra = overpayment_map.get(month, 0)

        balance -= (principal + extra)
        total_interest_paid += interest

        if balance < 0:
            balance = 0

        schedule.append({
            "month": month,
            "payment": round(standard_payment + extra, 2),
            "interest": round(interest, 2),
            "principal": round(principal, 2),
            "extra": extra,
            "balance": round(balance, 2),
        })

        if balance <= 0:
            break

    return schedule


# ═══════════════════════════════════════════════════════════
# ETF / INVESTMENT MATH
# ═══════════════════════════════════════════════════════════

@dataclass
class InvestmentParams:
    """Parameters for investment analysis."""
    initial: float              # wpłata początkowa
    monthly: float              # miesięczna wpłata
    annual_return: float        # oczekiwany roczny zwrot (np. 0.08 = 8%)
    volatility: float            # roczna zmienność (np. 0.15 = 15%)
    years: int                  # horyzont inwestycyjny
    tax_rate: float = 0.19      # podatek Belki (19% w Polsce)


def future_value_monte_carlo(
    initial: float, monthly: float, annual_return: float,
    volatility: float, years: int, n_simulations: int = 10000
) -> dict:
    """Monte Carlo simulation of investment future value."""
    monthly_return = annual_return / 12
    monthly_vol = volatility / math.sqrt(12)
    n_months = years * 12

    final_values = np.zeros(n_simulations)

    for i in range(n_simulations):
        returns = np.random.normal(monthly_return, monthly_vol, n_months)
        balance = initial
        for r in returns:
            balance = balance * (1 + r) + monthly
        final_values[i] = balance

    final_values.sort()

    return {
        "median": float(np.median(final_values)),
        "mean": float(np.mean(final_values)),
        "std": float(np.std(final_values)),
        "p10": float(np.percentile(final_values, 10)),
        "p25": float(np.percentile(final_values, 25)),
        "p50": float(np.percentile(final_values, 50)),
        "p75": float(np.percentile(final_values, 75)),
        "p90": float(np.percentile(final_values, 90)),
        "min": float(final_values[0]),
        "max": float(final_values[-1]),
        "all_values": final_values.tolist(),
    }


def future_value_deterministic(
    initial: float, monthly: float, annual_return: float, years: int
) -> float:
    """Deterministic future value calculation."""
    monthly_rate = annual_return / 12
    n_months = years * 12

    # FV of initial
    fv_initial = initial * (1 + monthly_rate) ** n_months

    # FV of monthly contributions (annuity)
    if monthly_rate == 0:
        fv_monthly = monthly * n_months
    else:
        fv_monthly = monthly * ((1 + monthly_rate) ** n_months - 1) / monthly_rate

    return fv_initial + fv_monthly


# ═══════════════════════════════════════════════════════════
# MORTGAGE VS ETF — THE CORE ANALYSIS
# ═══════════════════════════════════════════════════════════

def mortgage_vs_etf_analysis(
    loan: float = 500000,
    mortgage_rate: float = 0.07,
    mortgage_years: int = 25,
    etf_return: float = 0.08,
    etf_volatility: float = 0.15,
    tax_rate: float = 0.19,
    n_simulations: int = 5000,
) -> dict:
    """
    Core analysis: should I overpay mortgage or invest in ETF?

    Scenario A: Overpay mortgage — save on interest
    Scenario B: Invest the overpayment amount in ETF

    Returns detailed comparison with break-even analysis.
    """
    # Calculate base mortgage
    base = calculate_mortgage(loan, mortgage_rate, mortgage_years)
    monthly_payment = base.monthly_payment

    # We analyze different overpayment amounts
    overpayment_pcts = [0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 1.5, 2.0]
    results = []

    for op_pct in overpayment_pcts:
        op_monthly = monthly_payment * op_pct

        # Scenario A: Overpay mortgage
        schedule_a = amortization_schedule(loan, mortgage_rate, mortgage_years,
                                           overpayments=[(m, op_monthly) for m in range(1, mortgage_years * 12 + 1)])
        months_a = len(schedule_a)
        total_paid_a = sum(s["payment"] for s in schedule_a)
        interest_saved = base.total_cost - total_paid_a

        # Scenario B: Invest the overpayment amount
        fv_b = future_value_monte_carlo(
            initial=0, monthly=op_monthly, annual_return=etf_return,
            volatility=etf_volatility, years=mortgage_years, n_simulations=n_simulations
        )

        # After tax
        gain_b = fv_b["median"] - (op_monthly * mortgage_years * 12)
        tax_b = max(0, gain_b * tax_rate)
        net_b = fv_b["median"] - tax_b

        # Net benefit: B - A
        net_benefit = net_b - interest_saved

        results.append({
            "overpayment_pct": op_pct,
            "overpayment_monthly": round(op_monthly, 2),
            "scenario_a_interest_saved": round(interest_saved, 2),
            "scenario_a_months_earlier": mortgage_years * 12 - months_a,
            "scenario_b_median_fv": round(fv_b["median"], 2),
            "scenario_b_p10_fv": round(fv_b["p10"], 2),
            "scenario_b_p90_fv": round(fv_b["p90"], 2),
            "scenario_b_net_after_tax": round(net_b, 2),
            "net_benefit_b_minus_a": round(net_benefit, 2),
            "verdict": "ETF" if net_benefit > 0 else "NADPŁACAJ",
        })

    # Find break-even ETF return
    break_even = _find_break_even_return(
        loan, mortgage_rate, mortgage_years, monthly_payment * 0.5, tax_rate
    )

    return {
        "mortgage": {
            "loan": loan,
            "rate": mortgage_rate,
            "years": mortgage_years,
            "monthly_payment": monthly_payment,
            "total_cost": base.total_cost,
            "total_interest": base.total_interest,
        },
        "etf_params": {
            "expected_return": etf_return,
            "volatility": etf_volatility,
            "tax_rate": tax_rate,
        },
        "comparison": results,
        "break_even_etf_return": break_even,
        "summary": _summarize_comparison(results, break_even),
    }


def _find_break_even_return(
    loan: float, mortgage_rate: float, years: int,
    overpayment_monthly: float, tax_rate: float
) -> float:
    """Find the ETF return rate at which investing equals overpaying.

    Analytical solution: overpaying mortgage saves `mortgage_rate` (after-tax).
    Investing earns `etf_return * (1 - tax_rate)` after tax.
    Break-even: etf_return * (1 - tax_rate) = mortgage_rate
    → etf_return = mortgage_rate / (1 - tax_rate)
    """
    break_even = mortgage_rate / (1 - tax_rate)
    return round(break_even * 100, 2)  # as percentage


def _summarize_comparison(results: list[dict], break_even: float) -> str:
    """Generate human-readable summary."""
    best = max(results, key=lambda r: r["net_benefit_b_minus_a"])
    worst = min(results, key=lambda r: r["net_benefit_b_minus_a"])

    lines = [
        f"Próg rentowności ETF: {break_even}% rocznie",
        f"Jeśli ETF zarabia > {break_even}% → lepiej inwestować",
        f"Jeśli ETF zarabia < {break_even}% → lepiej nadpłacać kredyt",
        "",
        f"Najlepszy scenariusz: nadpłata {best['overpayment_pct']*100:.0f}% raty → {best['verdict']}",
        f"  Zysk netto: {best['net_benefit_b_minus_a']:,.0f} PLN",
        f"Najgorszy scenariusz: nadpłata {worst['overpayment_pct']*100:.0f}% raty → {worst['verdict']}",
        f"  Strata netto: {worst['net_benefit_b_minus_a']:,.0f} PLN",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# SOLVER INTERFACES (called by engine)
# ═══════════════════════════════════════════════════════════

def mortgage_analysis(text: str) -> SolveResult:
    """Parse mortgage parameters from text and compute."""
    try:
        # Extract numbers
        nums = re.findall(r'(\d[\d\s]*\d+)\s*(?:PLN|zł|tys|k)', text)
        loan = 500000
        rate = 0.07
        years = 25

        m = re.search(r'(\d[\d\s]*)\s*(?:PLN|zł)', text)
        if m:
            loan = float(m.group(1).replace(' ', ''))

        m = re.search(r'(\d+\.?\d*)\s*%', text)
        if m:
            rate = float(m.group(1)) / 100

        m = re.search(r'(\d+)\s*(?:lat|years|rok)', text)
        if m:
            years = int(m.group(1))

        result = calculate_mortgage(loan, rate, years)

        steps = [
            f"Kwota kredytu: {loan:,.0f} PLN",
            f"Oprocentowanie: {rate*100:.1f}%",
            f"Okres: {years} lat ({years*12} miesięcy)",
            f"",
            f"Miesięczna rata: {result.monthly_payment:,.2f} PLN",
            f"Całkowity koszt: {result.total_cost:,.2f} PLN",
            f"Odsetki łącznie: {result.total_interest:,.2f} PLN",
            f"Stosunek odsetki/kwota: {result.total_interest/loan*100:.1f}%",
        ]

        return SolveResult(
            problem_type=ProblemType.FINANCIAL_MORTGAGE,
            input_text=text,
            result={
                "loan": loan,
                "rate": rate,
                "years": years,
                "monthly_payment": result.monthly_payment,
                "total_cost": result.total_cost,
                "total_interest": result.total_interest,
            },
            steps=steps,
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.FINANCIAL_MORTGAGE,
            input_text=text,
            result=None,
            error=f"Błąd analizy kredytu: {e}",
        )


def mortgage_vs_etf(text: str) -> SolveResult:
    """Full mortgage vs ETF comparison."""
    try:
        # Default parameters
        loan = 500000
        mortgage_rate = 0.07
        years = 25
        etf_return = 0.08
        etf_vol = 0.15

        # Parse from text
        m = re.search(r'(\d[\d\s]*)\s*(?:PLN|zł)', text)
        if m:
            loan = float(m.group(1).replace(' ', ''))

        rates = re.findall(r'(\d+\.?\d*)\s*%', text)
        if len(rates) >= 1:
            mortgage_rate = float(rates[0]) / 100
        if len(rates) >= 2:
            etf_return = float(rates[1]) / 100

        m = re.search(r'(\d+)\s*(?:lat|years|rok)', text)
        if m:
            years = int(m.group(1))

        analysis = mortgage_vs_etf_analysis(
            loan=loan, mortgage_rate=mortgage_rate, mortgage_years=years,
            etf_return=etf_return, etf_volatility=etf_vol,
        )

        steps = [
            f"=== KREDYT vs ETF ===",
            f"Kredyt: {loan:,.0f} PLN, {mortgage_rate*100:.1f}%, {years} lat",
            f"Rata: {analysis['mortgage']['monthly_payment']:,.2f} PLN/mies.",
            f"ETF: {etf_return*100:.1f}% oczekiwany zwrot, {etf_vol*100:.0f}% zmienność",
            f"",
            f"Próg rentowności ETF: {analysis['break_even_etf_return']}%",
            f"",
        ]

        for r in analysis["comparison"]:
            emoji = "📈" if r["verdict"] == "ETF" else "🏠"
            steps.append(
                f"{emoji} Nadpłata {r['overpayment_pct']*100:.0f}% raty ({r['overpayment_monthly']:,.0f} PLN): "
                f"{r['verdict']} (netto: {r['net_benefit_b_minus_a']:+,.0f} PLN)"
            )

        steps.append("")
        steps.append(analysis["summary"])

        return SolveResult(
            problem_type=ProblemType.FINANCIAL_MORTGAGE_VS_ETF,
            input_text=text,
            result=analysis,
            steps=steps,
        )
    except Exception as e:
        import traceback
        return SolveResult(
            problem_type=ProblemType.FINANCIAL_MORTGAGE_VS_ETF,
            input_text=text,
            result=None,
            error=f"Błąd analizy: {e}\n{traceback.format_exc(limit=2)}",
        )


def npv_irr_analysis(text: str) -> SolveResult:
    """NPV and IRR calculation."""
    try:
        # Parse cash flows from text — handle negative numbers with spaces
        # Match patterns like "-1000 500 500 500" or "1000, 500, 500"
        nums = re.findall(r'(-?\d[\d\s]*\d+)(?=\s|$|,)', text)
        if not nums:
            nums = re.findall(r'(-?\d+)', text)
        cash_flows = [float(n.replace(' ', '')) for n in nums]

        if len(cash_flows) < 2:
            return SolveResult(
                problem_type=ProblemType.FINANCIAL_NPV_IRR,
                input_text=text,
                result=None,
                error="Potrzebuję co najmniej 2 przepływów pieniężnych.",
            )

        # Discount rate
        rate = 0.08
        m = re.search(r'(\d+\.?\d*)\s*%\s*(?:stopa|dyskont|discount)', text)
        if m:
            rate = float(m.group(1)) / 100

        # NPV
        npv = sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))

        # IRR
        try:
            irr = optimize.newton(
                lambda r: sum(cf / (1 + r) ** t for t, cf in enumerate(cash_flows)),
                0.1, maxiter=100
            )
        except Exception:
            irr = None

        steps = [
            f"Przepływy: {cash_flows}",
            f"Stopa dyskontowa: {rate*100:.1f}%",
            f"",
            f"NPV = {npv:,.2f}",
            f"IRR = {irr*100:.2f}%" if irr else "IRR: nie udało się obliczyć",
        ]

        return SolveResult(
            problem_type=ProblemType.FINANCIAL_NPV_IRR,
            input_text=text,
            result={
                "cash_flows": cash_flows,
                "discount_rate": rate,
                "npv": round(npv, 2),
                "irr": round(irr, 4) if irr else None,
            },
            steps=steps,
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.FINANCIAL_NPV_IRR,
            input_text=text,
            result=None,
            error=f"Błąd NPV/IRR: {e}",
        )


def portfolio_optimization(text: str) -> SolveResult:
    """Simple Markowitz portfolio optimization."""
    try:
        # Default: 3 assets
        returns = np.array([0.08, 0.12, 0.06])  # expected returns
        vols = np.array([0.15, 0.25, 0.10])     # volatilities
        corr = np.array([
            [1.0, 0.3, 0.5],
            [0.3, 1.0, 0.1],
            [0.5, 0.1, 1.0],
        ])

        # Covariance matrix
        cov = np.outer(vols, vols) * corr

        # Generate random portfolios
        n_portfolios = 5000
        n_assets = len(returns)
        weights = np.random.dirichlet(np.ones(n_assets), n_portfolios)

        port_returns = weights @ returns
        port_vols = np.sqrt(np.sum(weights * (weights @ cov), axis=1))
        port_sharpe = (port_returns - 0.03) / port_vols  # risk-free = 3%

        # Best Sharpe
        best_idx = np.argmax(port_sharpe)
        best_w = weights[best_idx]

        # Min volatility
        min_vol_idx = np.argmin(port_vols)
        min_vol_w = weights[min_vol_idx]

        steps = [
            "=== OPTYMALIZACJA PORTFELA (Markowitz) ===",
            f"Aktywa: {n_assets}",
            f"Oczekiwane zwroty: {returns}",
            f"Zmienności: {vols}",
            f"",
            f"Portfel o max Sharpe:",
            f"  Wagi: {[f'{w:.1%}' for w in best_w]}",
            f"  Zwrot: {port_returns[best_idx]:.2%}",
            f"  Ryzyko: {port_vols[best_idx]:.2%}",
            f"  Sharpe: {port_sharpe[best_idx]:.2f}",
            f"",
            f"Portfel o min ryzyku:",
            f"  Wagi: {[f'{w:.1%}' for w in min_vol_w]}",
            f"  Zwrot: {port_returns[min_vol_idx]:.2%}",
            f"  Ryzyko: {port_vols[min_vol_idx]:.2%}",
        ]

        return SolveResult(
            problem_type=ProblemType.FINANCIAL_PORTFOLIO,
            input_text=text,
            result={
                "n_assets": n_assets,
                "max_sharpe_weights": best_w.tolist(),
                "max_sharpe_return": float(port_returns[best_idx]),
                "max_sharpe_vol": float(port_vols[best_idx]),
                "max_sharpe_ratio": float(port_sharpe[best_idx]),
                "min_vol_weights": min_vol_w.tolist(),
                "min_vol_return": float(port_returns[min_vol_idx]),
                "min_vol_vol": float(port_vols[min_vol_idx]),
                "all_portfolios": {
                    "returns": port_returns.tolist(),
                    "vols": port_vols.tolist(),
                    "sharpe": port_sharpe.tolist(),
                },
            },
            steps=steps,
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.FINANCIAL_PORTFOLIO,
            input_text=text,
            result=None,
            error=f"Błąd optymalizacji portfela: {e}",
        )


def amortization_schedule_solver(text: str) -> SolveResult:
    """Generate amortization schedule."""
    try:
        loan = 500000
        rate = 0.07
        years = 25

        m = re.search(r'(\d[\d\s]*)\s*(?:PLN|zł)', text)
        if m:
            loan = float(m.group(1).replace(' ', ''))

        rates = re.findall(r'(\d+\.?\d*)\s*%', text)
        if rates:
            rate = float(rates[0]) / 100

        m = re.search(r'(\d+)\s*(?:lat|years|rok)', text)
        if m:
            years = int(m.group(1))

        schedule = amortization_schedule(loan, rate, years)

        steps = [
            f"Harmonogram spłat: {loan:,.0f} PLN, {rate*100:.1f}%, {years} lat",
            f"Liczba rat: {len(schedule)}",
            f"",
        ]

        # Show first 5 and last 3 payments
        for s in schedule[:5]:
            steps.append(f"Miesiąc {s['month']:3d}: rata {s['payment']:,.2f} | "
                        f"odsetki {s['interest']:,.2f} | kapitał {s['principal']:,.2f} | "
                        f"pozostało {s['balance']:,.2f}")

        if len(schedule) > 8:
            steps.append("...")
            for s in schedule[-3:]:
                steps.append(f"Miesiąc {s['month']:3d}: rata {s['payment']:,.2f} | "
                            f"odsetki {s['interest']:,.2f} | kapitał {s['principal']:,.2f} | "
                            f"pozostało {s['balance']:,.2f}")

        total_paid = sum(s["payment"] for s in schedule)
        total_interest = sum(s["interest"] for s in schedule)
        steps.append(f"")
        steps.append(f"Suma wpłat: {total_paid:,.2f} PLN")
        steps.append(f"Suma odsetek: {total_interest:,.2f} PLN")

        return SolveResult(
            problem_type=ProblemType.FINANCIAL_AMORTIZATION,
            input_text=text,
            result={
                "loan": loan,
                "rate": rate,
                "years": years,
                "n_payments": len(schedule),
                "total_paid": round(total_paid, 2),
                "total_interest": round(total_interest, 2),
                "schedule": schedule,
            },
            steps=steps,
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.FINANCIAL_AMORTIZATION,
            input_text=text,
            result=None,
            error=f"Błąd harmonogramu: {e}",
        )
