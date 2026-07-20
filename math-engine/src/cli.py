"""
Math Engine — Hermes CLI tool.
Usage:
    python -m math_engine.src.cli solve "oblicz pochodną x^2 * sin(x)"
    python -m math_engine.src.cli solve "kredyt 500000 PLN 7% vs ETF 8%"
    python -m math_engine.src.cli solve "rozwiąż x^2 - 4 = 0"
    python -m math_engine.src.cli solve "narysuj wykres sin(x) * exp(-x/5)"
    python -m math_engine.src.cli mortgage-vs-etf --loan 500000 --rate 7 --etf 8
    python -m math_engine.src.cli classify "całka z x^2 dx"
"""

from __future__ import annotations

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.engine import MathEngine, ProblemType


def cmd_solve(args):
    """Solve a math problem from natural language."""
    engine = MathEngine(output_dir=args.output)
    result = engine.solve(args.problem)

    if args.json:
        print(json.dumps({
            "type": result.problem_type.name,
            "input": result.input_text,
            "result": result.result,
            "steps": result.steps,
            "plot_path": result.plot_path,
            "error": result.error,
        }, indent=2, ensure_ascii=False, default=str))
        return

    print(f"📐 Problem: {result.problem_type.name}")
    print(f"📝 Input: {result.input_text}")
    print()

    if result.error:
        print(f"❌ Błąd: {result.error}")
        return

    if result.steps:
        print("📊 Kroki:")
        for step in result.steps:
            print(f"   {step}")

    if result.latex:
        print(f"\n📐 LaTeX: {result.latex}")

    if result.plot_path:
        print(f"\n📈 Wykres: {result.plot_path}")

    if result.result and isinstance(result.result, dict):
        print(f"\n📋 Wynik:")
        for k, v in result.result.items():
            if k not in ("all_values", "all_portfolios", "schedule", "x", "y", "y_pred"):
                print(f"   {k}: {v}")


def cmd_mortgage_vs_etf(args):
    """Dedicated mortgage vs ETF analysis."""
    from src.financial import mortgage_vs_etf_analysis, mortgage_vs_etf
    from src.plotting import plot_mortgage_vs_etf

    analysis = mortgage_vs_etf_analysis(
        loan=args.loan,
        mortgage_rate=args.rate / 100,
        mortgage_years=args.years,
        etf_return=args.etf / 100,
        etf_volatility=args.volatility / 100,
    )

    # Generate plot
    plot_path = plot_mortgage_vs_etf(analysis, args.output)

    if args.json:
        print(json.dumps(analysis, indent=2, ensure_ascii=False, default=str))
        return

    print("=== KREDYT vs ETF ===")
    print(f"Kredyt: {args.loan:,.0f} PLN, {args.rate}%, {args.years} lat")
    print(f"Rata: {analysis['mortgage']['monthly_payment']:,.2f} PLN/mies.")
    print(f"ETF: {args.etf}% zwrot, {args.volatility}% zmienność")
    print()
    print(f"Próg rentowności ETF: {analysis['break_even_etf_return']}%")
    print()

    for r in analysis["comparison"]:
        emoji = "📈" if r["verdict"] == "ETF" else "🏠"
        print(f"{emoji} Nadpłata {r['overpayment_pct']*100:.0f}% raty: {r['verdict']} "
              f"(netto: {r['net_benefit_b_minus_a']:+,.0f} PLN)")

    print(f"\n📈 Wykres: {plot_path}")


def cmd_classify(args):
    """Classify a problem without solving."""
    engine = MathEngine()
    ptype = engine.classify(args.problem)
    print(f"📝 Input: {args.problem}")
    print(f"🏷️  Type: {ptype.name}")


def cmd_portfolio(args):
    """Portfolio optimization."""
    from src.financial import portfolio_optimization
    from src.plotting import plot_efficient_frontier

    result = portfolio_optimization("portfolio")
    if result.error:
        print(f"❌ {result.error}")
        return

    for step in result.steps:
        print(step)

    # Generate plot
    data = result.result
    plot_path = plot_efficient_frontier(
        np.array(data["all_portfolios"]["returns"]),
        np.array(data["all_portfolios"]["vols"]),
        np.array(data["all_portfolios"]["sharpe"]),
        best_idx=np.argmax(data["all_portfolios"]["sharpe"]),
        min_vol_idx=np.argmin(data["all_portfolios"]["vols"]),
        output_dir=args.output,
    )
    print(f"\n📈 Wykres: {plot_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Math Engine — narzędzie matematyczne dla Hermesa",
    )
    subparsers = parser.add_subparsers(dest="command", help="Komendy")

    # solve
    p_solve = subparsers.add_parser("solve", help="Rozwiąż problem matematyczny")
    p_solve.add_argument("problem", help="Opis problemu (np. 'pochodna x^2')")
    p_solve.add_argument("--json", action="store_true", help="JSON output")
    p_solve.add_argument("--output", default="/tmp/math-engine", help="Katalog na wykresy")

    # mortgage-vs-etf
    p_mve = subparsers.add_parser("mortgage-vs-etf", help="Kredyt vs ETF")
    p_mve.add_argument("--loan", type=float, default=500000, help="Kwota kredytu (PLN)")
    p_mve.add_argument("--rate", type=float, default=7, help="Oprocentowanie kredytu (%)")
    p_mve.add_argument("--years", type=int, default=25, help="Okres (lata)")
    p_mve.add_argument("--etf", type=float, default=8, help="Oczekiwany zwrot ETF (%)")
    p_mve.add_argument("--volatility", type=float, default=15, help="Zmienność ETF (%)")
    p_mve.add_argument("--json", action="store_true", help="JSON output")
    p_mve.add_argument("--output", default="/tmp/math-engine", help="Katalog na wykresy")

    # classify
    p_classify = subparsers.add_parser("classify", help="Sklasyfikuj problem")
    p_classify.add_argument("problem", help="Opis problemu")

    # portfolio
    p_port = subparsers.add_parser("portfolio", help="Optymalizacja portfela")
    p_port.add_argument("--output", default="/tmp/math-engine", help="Katalog na wykresy")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "solve":
        cmd_solve(args)
    elif args.command == "mortgage-vs-etf":
        cmd_mortgage_vs_etf(args)
    elif args.command == "classify":
        cmd_classify(args)
    elif args.command == "portfolio":
        cmd_portfolio(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    import numpy as np  # for portfolio plot
    main()
