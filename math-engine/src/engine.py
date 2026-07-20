"""
Math Engine — problem type detection and routing.
LLM NEVER computes. This engine classifies the problem and delegates to the right solver.

Usage:
    from math_engine.src.engine import MathEngine
    engine = MathEngine()
    result = engine.solve("oblicz pochodną x^2 * sin(x)")
    # → routes to symbolic.differentiate()
"""

from __future__ import annotations

import re
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto


class ProblemType(Enum):
    SYMBOLIC_DIFF = auto()       # pochodna
    SYMBOLIC_INTEGRATE = auto()  # całka
    SYMBOLIC_SOLVE = auto()      # równanie
    SYMBOLIC_SIMPLIFY = auto()   # uproszczenie
    SYMBOLIC_LIMIT = auto()      # granica
    SYMBOLIC_SERIES = auto()     # szereg Taylora
    SYMBOLIC_LAPLACE = auto()    # transformata Laplace'a
    NUMERIC_OPTIMIZE = auto()    # optymalizacja
    NUMERIC_INTEGRATE = auto()   # całkowanie numeryczne
    NUMERIC_ROOT = auto()        # miejsce zerowe
    NUMERIC_INTERPOLATE = auto() # interpolacja
    NUMERIC_ODE = auto()         # równanie różniczkowe
    FINANCIAL_MORTGAGE = auto()  # kredyt hipoteczny
    FINANCIAL_MORTGAGE_VS_ETF = auto()  # kredyt vs ETF
    FINANCIAL_NPV_IRR = auto()   # NPV/IRR
    FINANCIAL_PORTFOLIO = auto() # optymalizacja portfela
    FINANCIAL_AMORTIZATION = auto()  # harmonogram spłat
    PROBABILITY_DISTRIBUTION = auto()  # rozkład
    PROBABILITY_BAYES = auto()   # twierdzenie Bayesa
    PROBABILITY_MONTE_CARLO = auto()  # Monte Carlo
    PROBABILITY_REGRESSION = auto()   # regresja
    PROBABILITY_TEST = auto()    # test statystyczny
    PLOT_FUNCTION = auto()       # wykres funkcji
    PLOT_3D = auto()             # wykres 3D
    PLOT_HEATMAP = auto()        # heatmapa
    UNKNOWN = auto()


@dataclass
class SolveResult:
    """Unified result from any solver."""
    problem_type: ProblemType
    input_text: str
    result: Any                    # główny wynik (liczba, wyrażenie, dict)
    steps: list[str] = field(default_factory=list)  # kroki pośrednie
    plot_path: Optional[str] = None  # ścieżka do wykresu
    latex: Optional[str] = None      # wynik w LaTeX
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


# ─── Pattern matching ──────────────────────────────────────

PATTERNS: list[tuple[re.Pattern, ProblemType, int]] = []

def _p(pattern: str, ptype: ProblemType, priority: int = 0):
    PATTERNS.append((re.compile(pattern, re.IGNORECASE), ptype, priority))

# Symbolic
_p(r'\bpochodn[ąa]\b|differentiate|d/dx|∂/∂x', ProblemType.SYMBOLIC_DIFF, 10)
_p(r'\bcałk[ęa]\b|∫|integrate|całkuj|całkowanie', ProblemType.SYMBOLIC_INTEGRATE, 10)
_p(r'\brozwiąż\b|solve|równanie|equation|pierwiastki', ProblemType.SYMBOLIC_SOLVE, 8)
_p(r'\bupro[śs]ć\b|simplify|uproszczenie', ProblemType.SYMBOLIC_SIMPLIFY, 8)
_p(r'\bgranic[ęa]\b|limit|limes|lim\b', ProblemType.SYMBOLIC_LIMIT, 8)
_p(r'\bszereg\b|taylor|maclaurin|series', ProblemType.SYMBOLIC_SERIES, 7)
_p(r'\blaplace|transformata\s+laplace', ProblemType.SYMBOLIC_LAPLACE, 7)

# Numeric
_p(r'\b(optymaliz|minimum|maksimum|minimaliz|maksymaliz|znajdź\s+min|znajdź\s+max)\b', ProblemType.NUMERIC_OPTIMIZE, 9)
_p(r'\bcałk[ęa]\s+numeryczn|numeryczne\s+całkowanie|quad|simpson', ProblemType.NUMERIC_INTEGRATE, 12)
_p(r'\bmiejsce\s+zerowe|pierwiastek\s+funkcji|root\s+finding|fzero', ProblemType.NUMERIC_ROOT, 8)
_p(r'\binterpol|spline|wielomian\s+interpolacyjny', ProblemType.NUMERIC_INTERPOLATE, 7)
_p(r'\brównanie\s+różniczkowe|ode\b|rk4|runge.kutta|euler', ProblemType.NUMERIC_ODE, 7)

# Financial
_p(r'\bkredyt\s+.*\bvs\s+etf|nadpłac[ae]ć\s+kredyt|kredyt\s+czy\s+inwest|inwestować\s+czy\s+nadpłac|etf\s+vs\s+kredyt', ProblemType.FINANCIAL_MORTGAGE_VS_ETF, 15)
_p(r'\bkredyt\s+hipoteczny|rata\s+kredytu|miesięczna\s+rata|zdolność\s+kredytowa', ProblemType.FINANCIAL_MORTGAGE, 12)
_p(r'\bnpv\b|irr\b|wartość\s+bieżąca|wewnętrzna\s+stopa\s+zwrotu|discount', ProblemType.FINANCIAL_NPV_IRR, 10)
_p(r'\bportfel|markowitz|sharpe|alokacja\s+aktywów|dywersyfikacja|efficient\s+frontier', ProblemType.FINANCIAL_PORTFOLIO, 10)
_p(r'\bharmonogram\s+spłat|amortyzacj|raty\s+malejące|raty\s+równe', ProblemType.FINANCIAL_AMORTIZATION, 9)

# Probability
_p(r'\brozkład\b|distribution|pdf|cdf|gęstość\s+prawdopodobieństwa', ProblemType.PROBABILITY_DISTRIBUTION, 10)
_p(r'\bbayes|prawdopodobieństwo\s+warunkowe|twierdzenie\s+bayesa|prior|posterior', ProblemType.PROBABILITY_BAYES, 10)
_p(r'\bmonte\s+carlo|symulacj[ae]\b|próbkowanie|sampling', ProblemType.PROBABILITY_MONTE_CARLO, 9)
_p(r'\bregresj[ae]\b|linia\s+trendu|least\s+squares|dopasow', ProblemType.PROBABILITY_REGRESSION, 9)
_p(r'\bt.test|anova|chi.kwadrat|test\s+statystyczny|hipotez[ae]|p.value', ProblemType.PROBABILITY_TEST, 8)

# Plotting
_p(r'\bwykres\s+3d\b|3d\s+plot|surface|powierzchni', ProblemType.PLOT_3D, 10)
_p(r'\bheatmap|mapa\s+ciepła|kontur', ProblemType.PLOT_HEATMAP, 9)
_p(r'\bwykres\b|narysuj|plot|chart|graficznie|wizualiz', ProblemType.PLOT_FUNCTION, 5)


class MathEngine:
    """Routes math problems to appropriate solvers."""

    def __init__(self, output_dir: str = "/tmp/math-engine"):
        self.output_dir = output_dir
        import os
        os.makedirs(output_dir, exist_ok=True)

    def classify(self, text: str) -> ProblemType:
        """Classify problem type from natural language text."""
        best_type = ProblemType.UNKNOWN
        best_priority = -1

        for pattern, ptype, priority in PATTERNS:
            if pattern.search(text) and priority > best_priority:
                best_type = ptype
                best_priority = priority

        return best_type

    def solve(self, text: str, **kwargs) -> SolveResult:
        """Classify and solve a math problem."""
        ptype = self.classify(text)

        if ptype == ProblemType.UNKNOWN:
            return SolveResult(
                problem_type=ptype,
                input_text=text,
                result=None,
                error=f"Nie potrafię sklasyfikować problemu. Spróbuj opisać go bardziej precyzyjnie.\n"
                      f"Dostępne kategorie: pochodne, całki, równania, optymalizacja, "
                      f"kredyty, inwestycje, prawdopodobieństwo, statystyka, wykresy.",
            )

        # Route to solver
        solver_map: dict[ProblemType, Callable] = {
            # Symbolic
            ProblemType.SYMBOLIC_DIFF: self._solve_symbolic_diff,
            ProblemType.SYMBOLIC_INTEGRATE: self._solve_symbolic_integrate,
            ProblemType.SYMBOLIC_SOLVE: self._solve_symbolic_solve,
            ProblemType.SYMBOLIC_SIMPLIFY: self._solve_symbolic_simplify,
            ProblemType.SYMBOLIC_LIMIT: self._solve_symbolic_limit,
            ProblemType.SYMBOLIC_SERIES: self._solve_symbolic_series,
            # Numeric
            ProblemType.NUMERIC_OPTIMIZE: self._solve_numeric_optimize,
            ProblemType.NUMERIC_INTEGRATE: self._solve_numeric_integrate,
            ProblemType.NUMERIC_ROOT: self._solve_numeric_root,
            # Financial
            ProblemType.FINANCIAL_MORTGAGE: self._solve_financial_mortgage,
            ProblemType.FINANCIAL_MORTGAGE_VS_ETF: self._solve_financial_mortgage_vs_etf,
            ProblemType.FINANCIAL_NPV_IRR: self._solve_financial_npv_irr,
            ProblemType.FINANCIAL_PORTFOLIO: self._solve_financial_portfolio,
            ProblemType.FINANCIAL_AMORTIZATION: self._solve_financial_amortization,
            # Probability
            ProblemType.PROBABILITY_DISTRIBUTION: self._solve_probability_distribution,
            ProblemType.PROBABILITY_BAYES: self._solve_probability_bayes,
            ProblemType.PROBABILITY_MONTE_CARLO: self._solve_probability_monte_carlo,
            ProblemType.PROBABILITY_REGRESSION: self._solve_probability_regression,
            # Plotting
            ProblemType.PLOT_FUNCTION: self._solve_plot_function,
            ProblemType.PLOT_3D: self._solve_plot_3d,
        }

        solver = solver_map.get(ptype)
        if solver is None:
            return SolveResult(
                problem_type=ptype,
                input_text=text,
                result=None,
                error=f"Kategoria {ptype.name} nie ma jeszcze zaimplementowanego solvera.",
            )

        try:
            return solver(text, **kwargs)
        except Exception as e:
            import traceback
            return SolveResult(
                problem_type=ptype,
                input_text=text,
                result=None,
                error=f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}",
            )

    # ─── Symbolic solvers ───────────────────────────────────

    def _solve_symbolic_diff(self, text: str, **kwargs) -> SolveResult:
        from .symbolic import differentiate
        return differentiate(text)

    def _solve_symbolic_integrate(self, text: str, **kwargs) -> SolveResult:
        from .symbolic import integrate
        return integrate(text)

    def _solve_symbolic_solve(self, text: str, **kwargs) -> SolveResult:
        from .symbolic import solve_equation
        return solve_equation(text)

    def _solve_symbolic_simplify(self, text: str, **kwargs) -> SolveResult:
        from .symbolic import simplify_expr
        return simplify_expr(text)

    def _solve_symbolic_limit(self, text: str, **kwargs) -> SolveResult:
        from .symbolic import compute_limit
        return compute_limit(text)

    def _solve_symbolic_series(self, text: str, **kwargs) -> SolveResult:
        from .symbolic import taylor_series
        return taylor_series(text)

    # ─── Numeric solvers ────────────────────────────────────

    def _solve_numeric_optimize(self, text: str, **kwargs) -> SolveResult:
        from .numeric import optimize_function
        return optimize_function(text)

    def _solve_numeric_integrate(self, text: str, **kwargs) -> SolveResult:
        from .numeric import integrate_numeric
        return integrate_numeric(text)

    def _solve_numeric_root(self, text: str, **kwargs) -> SolveResult:
        from .numeric import find_root
        return find_root(text)

    # ─── Financial solvers ──────────────────────────────────

    def _solve_financial_mortgage(self, text: str, **kwargs) -> SolveResult:
        from .financial import mortgage_analysis
        return mortgage_analysis(text)

    def _solve_financial_mortgage_vs_etf(self, text: str, **kwargs) -> SolveResult:
        from .financial import mortgage_vs_etf
        return mortgage_vs_etf(text)

    def _solve_financial_npv_irr(self, text: str, **kwargs) -> SolveResult:
        from .financial import npv_irr_analysis
        return npv_irr_analysis(text)

    def _solve_financial_portfolio(self, text: str, **kwargs) -> SolveResult:
        from .financial import portfolio_optimization
        return portfolio_optimization(text)

    def _solve_financial_amortization(self, text: str, **kwargs) -> SolveResult:
        from .financial import amortization_schedule_solver
        return amortization_schedule_solver(text)

    # ─── Probability solvers ────────────────────────────────

    def _solve_probability_distribution(self, text: str, **kwargs) -> SolveResult:
        from .probability import distribution_analysis
        return distribution_analysis(text)

    def _solve_probability_bayes(self, text: str, **kwargs) -> SolveResult:
        from .probability import bayes_theorem
        return bayes_theorem(text)

    def _solve_probability_monte_carlo(self, text: str, **kwargs) -> SolveResult:
        from .probability import monte_carlo_simulation
        return monte_carlo_simulation(text)

    def _solve_probability_regression(self, text: str, **kwargs) -> SolveResult:
        from .probability import regression_analysis
        return regression_analysis(text)

    # ─── Plotting solvers ───────────────────────────────────

    def _solve_plot_function(self, text: str, **kwargs) -> SolveResult:
        from .plotting import plot_function
        return plot_function(text, self.output_dir)

    def _solve_plot_3d(self, text: str, **kwargs) -> SolveResult:
        from .plotting import plot_3d
        return plot_3d(text, self.output_dir)
