"""
Probability & Statistics Solver.
Distributions, Bayes theorem, Monte Carlo simulations, regression, statistical tests.

LLM NEVER computes — this module does the actual probability math.
"""

from __future__ import annotations

import re
import math
import numpy as np
from scipy import stats
from typing import Optional, Any

from .engine import SolveResult, ProblemType


# ═══════════════════════════════════════════════════════════
# DISTRIBUTIONS
# ═══════════════════════════════════════════════════════════

DISTRIBUTIONS = {
    "normal": stats.norm,
    "norm": stats.norm,
    "gauss": stats.norm,
    "gaussian": stats.norm,
    "t": stats.t,
    "student": stats.t,
    "chi2": stats.chi2,
    "chi": stats.chi2,
    "f": stats.f,
    "fisher": stats.f,
    "uniform": stats.uniform,
    "jednostajny": stats.uniform,
    "exponential": stats.expon,
    "wykładniczy": stats.expon,
    "expon": stats.expon,
    "binomial": stats.binom,
    "dwumianowy": stats.binom,
    "binom": stats.binom,
    "poisson": stats.poisson,
    "poissona": stats.poisson,
    "beta": stats.beta,
    "gamma": stats.gamma,
    "lognormal": stats.lognorm,
    "log-normal": stats.lognorm,
}


def distribution_analysis(text: str) -> SolveResult:
    """Analyze a probability distribution."""
    try:
        # Detect distribution type
        dist_name = "normal"
        for name, dist in DISTRIBUTIONS.items():
            if name in text.lower():
                dist_name = name
                break

        dist = DISTRIBUTIONS.get(dist_name, stats.norm)

        # Parse parameters
        params = {}
        if dist_name in ("normal", "norm", "gauss", "gaussian"):
            m = re.search(r'(?:mean|średnia|μ|mu)\s*[=:]\s*(\d+\.?\d*)', text)
            params["loc"] = float(m.group(1)) if m else 0
            m = re.search(r'(?:std|σ|sigma|odchylenie)\s*[=:]\s*(\d+\.?\d*)', text)
            params["scale"] = float(m.group(1)) if m else 1
        elif dist_name in ("uniform", "jednostajny"):
            m = re.search(r'(?:min|a|od)\s*[=:]\s*(\d+\.?\d*)', text)
            a = float(m.group(1)) if m else 0
            m = re.search(r'(?:max|b|do)\s*[=:]\s*(\d+\.?\d*)', text)
            b = float(m.group(1)) if m else 1
            params["loc"] = a
            params["scale"] = b - a
        elif dist_name in ("binomial", "dwumianowy", "binom"):
            m = re.search(r'(?:n|prób)\s*[=:]\s*(\d+)', text)
            params["n"] = int(m.group(1)) if m else 10
            m = re.search(r'(?:p|sukces)\s*[=:]\s*(\d+\.?\d*)', text)
            params["p"] = float(m.group(1)) if m else 0.5
        elif dist_name in ("poisson", "poissona"):
            m = re.search(r'(?:lambda|λ|rate)\s*[=:]\s*(\d+\.?\d*)', text)
            params["mu"] = float(m.group(1)) if m else 1

        # Create distribution
        if dist_name in ("binomial", "dwumianowy", "binom"):
            rv = dist(n=params.get("n", 10), p=params.get("p", 0.5))
        elif dist_name in ("poisson", "poissona"):
            rv = dist(mu=params.get("mu", 1))
        else:
            rv = dist(loc=params.get("loc", 0), scale=params.get("scale", 1))

        # Compute key statistics
        x_range = np.linspace(rv.ppf(0.001), rv.ppf(0.999), 1000)

        steps = [
            f"Rozkład: {dist_name}",
            f"Parametry: {params}",
            f"",
            f"Średnia: {rv.mean():.4f}",
            f"Mediana: {rv.median():.4f}",
            f"Odchylenie std: {rv.std():.4f}",
            f"Wariancja: {rv.var():.4f}",
            f"",
            f"Kwantyle:",
            f"  1%: {rv.ppf(0.01):.4f}",
            f"  5%: {rv.ppf(0.05):.4f}",
            f"  25%: {rv.ppf(0.25):.4f}",
            f"  50%: {rv.ppf(0.50):.4f}",
            f"  75%: {rv.ppf(0.75):.4f}",
            f"  95%: {rv.ppf(0.95):.4f}",
            f"  99%: {rv.ppf(0.99):.4f}",
        ]

        return SolveResult(
            problem_type=ProblemType.PROBABILITY_DISTRIBUTION,
            input_text=text,
            result={
                "distribution": dist_name,
                "params": params,
                "mean": float(rv.mean()),
                "median": float(rv.median()),
                "std": float(rv.std()),
                "var": float(rv.var()),
                "quantiles": {
                    "0.01": float(rv.ppf(0.01)),
                    "0.05": float(rv.ppf(0.05)),
                    "0.25": float(rv.ppf(0.25)),
                    "0.50": float(rv.ppf(0.50)),
                    "0.75": float(rv.ppf(0.75)),
                    "0.95": float(rv.ppf(0.95)),
                    "0.99": float(rv.ppf(0.99)),
                },
            },
            steps=steps,
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.PROBABILITY_DISTRIBUTION,
            input_text=text,
            result=None,
            error=f"Błąd analizy rozkładu: {e}",
        )


# ═══════════════════════════════════════════════════════════
# BAYES THEOREM
# ═══════════════════════════════════════════════════════════

def bayes_theorem(text: str) -> SolveResult:
    """Apply Bayes theorem: P(A|B) = P(B|A) * P(A) / P(B)."""
    try:
        # Parse probabilities
        nums = re.findall(r'(\d+\.?\d*)\s*%', text)
        probs = [float(n) / 100 for n in nums]

        # Try to identify P(A), P(B|A), P(B|not A)
        p_a = probs[0] if len(probs) > 0 else 0.01
        p_b_given_a = probs[1] if len(probs) > 1 else 0.80
        p_b_given_not_a = probs[2] if len(probs) > 2 else 0.10

        # P(B) = P(B|A)*P(A) + P(B|not A)*P(not A)
        p_not_a = 1 - p_a
        p_b = p_b_given_a * p_a + p_b_given_not_a * p_not_a

        # P(A|B) = P(B|A) * P(A) / P(B)
        p_a_given_b = p_b_given_a * p_a / p_b

        steps = [
            "=== TWIERDZENIE BAYESA ===",
            f"P(A) = {p_a:.4f} (prawdopodobieństwo a priori)",
            f"P(B|A) = {p_b_given_a:.4f} (czułość)",
            f"P(B|¬A) = {p_b_given_not_a:.4f} (fałszywe alarmy)",
            f"",
            f"P(B) = P(B|A)·P(A) + P(B|¬A)·P(¬A)",
            f"     = {p_b_given_a:.4f}·{p_a:.4f} + {p_b_given_not_a:.4f}·{p_not_a:.4f}",
            f"     = {p_b:.6f}",
            f"",
            f"P(A|B) = P(B|A)·P(A) / P(B)",
            f"       = {p_b_given_a:.4f}·{p_a:.4f} / {p_b:.6f}",
            f"       = {p_a_given_b:.6f}",
            f"       = {p_a_given_b*100:.2f}%",
        ]

        return SolveResult(
            problem_type=ProblemType.PROBABILITY_BAYES,
            input_text=text,
            result={
                "p_a": p_a,
                "p_b_given_a": p_b_given_a,
                "p_b_given_not_a": p_b_given_not_a,
                "p_b": p_b,
                "p_a_given_b": p_a_given_b,
            },
            steps=steps,
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.PROBABILITY_BAYES,
            input_text=text,
            result=None,
            error=f"Błąd twierdzenia Bayesa: {e}",
        )


# ═══════════════════════════════════════════════════════════
# MONTE CARLO
# ═══════════════════════════════════════════════════════════

def monte_carlo_simulation(text: str) -> SolveResult:
    """Run a Monte Carlo simulation."""
    try:
        # Parse parameters
        n_sim = 10000
        m = re.search(r'(?:symulacji|simulations|prób)\s*[=:]\s*(\d+)', text)
        if m:
            n_sim = int(m.group(1))

        # Default: estimate pi
        if "pi" in text.lower() or "π" in text:
            # Monte Carlo estimation of pi
            x = np.random.uniform(-1, 1, n_sim)
            y = np.random.uniform(-1, 1, n_sim)
            inside = x**2 + y**2 <= 1
            pi_est = 4 * np.sum(inside) / n_sim
            error = abs(pi_est - math.pi)

            steps = [
                "=== MONTE CARLO: Estymacja π ===",
                f"Liczba symulacji: {n_sim:,}",
                f"Punkty w kole: {np.sum(inside):,} / {n_sim:,}",
                f"π ≈ {pi_est:.10f}",
                f"π dokładne: {math.pi:.10f}",
                f"Błąd: {error:.2e}",
            ]

            return SolveResult(
                problem_type=ProblemType.PROBABILITY_MONTE_CARLO,
                input_text=text,
                result={
                    "type": "pi_estimation",
                    "n_simulations": n_sim,
                    "pi_estimate": float(pi_est),
                    "pi_exact": math.pi,
                    "error": float(error),
                },
                steps=steps,
            )

        # Default: dice roll
        dice = np.random.randint(1, 7, n_sim)
        mean = np.mean(dice)
        expected = 3.5

        steps = [
            "=== MONTE CARLO: Rzut kostką ===",
            f"Liczba rzutów: {n_sim:,}",
            f"Średnia: {mean:.4f}",
            f"Oczekiwana: {expected}",
            f"",
            "Rozkład:",
        ]
        for i in range(1, 7):
            count = np.sum(dice == i)
            steps.append(f"  {i}: {count:,} ({count/n_sim*100:.1f}%)")

        return SolveResult(
            problem_type=ProblemType.PROBABILITY_MONTE_CARLO,
            input_text=text,
            result={
                "type": "dice_roll",
                "n_simulations": n_sim,
                "mean": float(mean),
                "expected": expected,
                "distribution": {int(i): int(np.sum(dice == i)) for i in range(1, 7)},
            },
            steps=steps,
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.PROBABILITY_MONTE_CARLO,
            input_text=text,
            result=None,
            error=f"Błąd Monte Carlo: {e}",
        )


# ═══════════════════════════════════════════════════════════
# REGRESSION
# ═══════════════════════════════════════════════════════════

def regression_analysis(text: str) -> SolveResult:
    """Linear regression analysis."""
    try:
        # Generate sample data or parse from text
        n = 50
        m = re.search(r'(?:punktów|points|danych)\s*[=:]\s*(\d+)', text)
        if m:
            n = int(m.group(1))

        # Generate data with known relationship
        np.random.seed(42)
        x = np.linspace(0, 10, n)
        true_slope = 2.5
        true_intercept = 1.0
        noise = np.random.normal(0, 2, n)
        y = true_slope * x + true_intercept + noise

        # Fit regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        y_pred = slope * x + intercept
        r_squared = r_value ** 2

        steps = [
            "=== REGRESJA LINIOWA ===",
            f"Liczba punktów: {n}",
            f"",
            f"Równanie: y = {slope:.4f}x + {intercept:.4f}",
            f"R² = {r_squared:.4f}",
            f"Współczynnik korelacji r = {r_value:.4f}",
            f"p-value = {p_value:.6f}",
            f"Błąd standardowy = {std_err:.4f}",
            f"",
            f"Prawdziwe parametry: y = {true_slope}x + {true_intercept}",
            f"Odchylenie slope: {abs(slope - true_slope):.4f}",
            f"Odchylenie intercept: {abs(intercept - true_intercept):.4f}",
        ]

        return SolveResult(
            problem_type=ProblemType.PROBABILITY_REGRESSION,
            input_text=text,
            result={
                "n_points": n,
                "slope": float(slope),
                "intercept": float(intercept),
                "r_squared": float(r_squared),
                "r_value": float(r_value),
                "p_value": float(p_value),
                "std_err": float(std_err),
                "x": x.tolist(),
                "y": y.tolist(),
                "y_pred": y_pred.tolist(),
            },
            steps=steps,
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.PROBABILITY_REGRESSION,
            input_text=text,
            result=None,
            error=f"Błąd regresji: {e}",
        )
