"""
Numeric Math Solver — NumPy/SciPy wrapper.
Optimization, numerical integration, root finding, ODE solving, interpolation.

LLM NEVER computes — this module does the actual number crunching.
"""

from __future__ import annotations

import re
import numpy as np
from scipy import optimize, integrate, interpolate
from typing import Optional, Any

from .engine import SolveResult, ProblemType


def _parse_function(text: str) -> tuple[str, str]:
    """Extract function expression and variable from text."""
    # Strip bounds info first
    text = re.sub(r'\s+bounds\s+\S+\s+\S+.*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+od\s+\S+\s+do\s+\S+.*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+\[[\d.,\s]+\].*$', '', text)

    # Look for f(x) = ... pattern
    m = re.search(r'f\s*\(\s*(\w+)\s*\)\s*=\s*(.+)', text)
    if m:
        return m.group(2).strip(), m.group(1)

    # Look for expression with variable
    m = re.search(r'([a-zA-Z]\^?\d*\s*[\+\-\*\/\^].+)', text)
    if m:
        expr = m.group(1).strip()
        var_match = re.search(r'\b([a-z])\b', expr)
        var = var_match.group(1) if var_match else 'x'
        return expr, var

    return text, 'x'


def _make_func(expr_str: str, var: str = 'x'):
    """Create a callable function from expression string."""
    # Safe eval with numpy
    namespace = {
        'np': np, 'sin': np.sin, 'cos': np.cos, 'tan': np.tan,
        'exp': np.exp, 'log': np.log, 'log10': np.log10,
        'sqrt': np.sqrt, 'abs': np.abs, 'pi': np.pi, 'e': np.e,
        'arcsin': np.arcsin, 'arccos': np.arccos, 'arctan': np.arctan,
        'sinh': np.sinh, 'cosh': np.cosh, 'tanh': np.tanh,
    }
    # Replace ^ with **
    expr_str = expr_str.replace('^', '**')
    # Replace implicit multiplication like 2x → 2*x
    expr_str = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr_str)

    def func(x_val):
        namespace[var] = x_val
        return eval(expr_str, {"__builtins__": {}}, namespace)

    return func


def optimize_function(text: str) -> SolveResult:
    """Find minimum/maximum of a function."""
    try:
        expr_str, var = _parse_function(text)
        f = _make_func(expr_str, var)

        # Determine if we want min or max
        want_max = any(w in text.lower() for w in ['maksimum', 'maksymal', 'maximum', 'max'])

        steps = [
            f"Funkcja: f({var}) = {expr_str}",
            f"Szukam {'maksimum' if want_max else 'minimum'}",
        ]

        # Try multiple starting points
        best_x, best_val = None, float('inf') if not want_max else float('-inf')
        for start in [-5, -1, 0, 1, 5]:
            try:
                if want_max:
                    res = optimize.minimize_scalar(
                        lambda x: -f(x), bounds=(-100, 100), method='bounded'
                    )
                    val = -res.fun
                else:
                    res = optimize.minimize_scalar(f, bounds=(-100, 100), method='bounded')
                    val = res.fun

                if (want_max and val > best_val) or (not want_max and val < best_val):
                    best_x, best_val = res.x, val
            except Exception:
                continue

        if best_x is None:
            return SolveResult(
                problem_type=ProblemType.NUMERIC_OPTIMIZE,
                input_text=text,
                result=None,
                error="Nie udało się znaleźć optimum.",
            )

        steps.append(f"{'Maksimum' if want_max else 'Minimum'} w x = {best_x:.6f}")
        steps.append(f"Wartość: f({best_x:.6f}) = {best_val:.6f}")

        return SolveResult(
            problem_type=ProblemType.NUMERIC_OPTIMIZE,
            input_text=text,
            result={
                "function": expr_str,
                "variable": var,
                "optimum_type": "max" if want_max else "min",
                "x_optimum": float(best_x),
                "f_optimum": float(best_val),
            },
            steps=steps,
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.NUMERIC_OPTIMIZE,
            input_text=text,
            result=None,
            error=f"Błąd optymalizacji: {e}",
        )


def integrate_numeric(text: str) -> SolveResult:
    """Numerical integration of a function."""
    try:
        expr_str, var = _parse_function(text)
        f = _make_func(expr_str, var)

        # Try to find bounds
        a, b = 0.0, 1.0
        m = re.search(r'\[(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\]', text)
        if m:
            a, b = float(m.group(1)), float(m.group(2))
        else:
            m = re.search(r'od\s+(\d+\.?\d*)\s+do\s+(\d+\.?\d*)', text)
            if m:
                a, b = float(m.group(1)), float(m.group(2))

        steps = [
            f"Funkcja: f({var}) = {expr_str}",
            f"Przedział całkowania: [{a}, {b}]",
        ]

        # Quadrature
        result, error = integrate.quad(f, a, b)
        steps.append(f"Wynik całkowania: {result:.10f}")
        steps.append(f"Szacowany błąd: {error:.2e}")

        # Also try Simpson's rule for comparison
        x_vals = np.linspace(a, b, 1001)
        y_vals = np.array([f(x) for x in x_vals])
        simpson = integrate.simpson(y_vals, x_vals)
        steps.append(f"Metoda Simpsona: {simpson:.10f}")

        return SolveResult(
            problem_type=ProblemType.NUMERIC_INTEGRATE,
            input_text=text,
            result={
                "function": expr_str,
                "bounds": [a, b],
                "quad_result": float(result),
                "quad_error": float(error),
                "simpson_result": float(simpson),
            },
            steps=steps,
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.NUMERIC_INTEGRATE,
            input_text=text,
            result=None,
            error=f"Błąd całkowania numerycznego: {e}",
        )


def find_root(text: str) -> SolveResult:
    """Find root (zero) of a function."""
    try:
        expr_str, var = _parse_function(text)
        f = _make_func(expr_str, var)

        steps = [
            f"Funkcja: f({var}) = {expr_str}",
            "Szukam miejsc zerowych...",
        ]

        # Scan for sign changes
        roots = []
        for start in np.linspace(-10, 10, 50):
            try:
                root = optimize.newton(f, start, tol=1e-10, maxiter=100)
                root = round(root, 8)
                if not any(abs(root - r) < 1e-6 for r in roots):
                    roots.append(root)
            except Exception:
                continue

        roots.sort()

        if not roots:
            return SolveResult(
                problem_type=ProblemType.NUMERIC_ROOT,
                input_text=text,
                result=None,
                error="Nie znaleziono miejsc zerowych w przedziale [-10, 10].",
            )

        for i, r in enumerate(roots):
            steps.append(f"Miejsce zerowe #{i+1}: x = {r:.8f}, f(x) = {f(r):.2e}")

        return SolveResult(
            problem_type=ProblemType.NUMERIC_ROOT,
            input_text=text,
            result={
                "function": expr_str,
                "roots": roots,
                "count": len(roots),
            },
            steps=steps,
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.NUMERIC_ROOT,
            input_text=text,
            result=None,
            error=f"Błąd szukania miejsc zerowych: {e}",
        )
