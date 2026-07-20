"""
Symbolic Math Solver — SymPy wrapper.
All symbolic operations: derivatives, integrals, equations, limits, series, Laplace.

LLM NEVER computes — this module does the actual math.
"""

from __future__ import annotations

import re
import sympy as sp
from sympy import symbols, Symbol, Function, latex, simplify, expand, factor
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
from typing import Optional, Any

from .engine import SolveResult, ProblemType

TRANSFORMS = standard_transformations + (implicit_multiplication_application,)

# Common variable names
VAR_NAMES = ['x', 'y', 'z', 't', 'n', 'k', 'a', 'b', 'c', 'r', 's', 'theta', 'phi']


def _parse_expr(text: str) -> tuple[sp.Expr, dict[str, Symbol]]:
    """Parse a math expression from text, extracting variables."""
    expr_str = text

    # Strip natural language
    for prefix in ['oblicz pochodną ', 'oblicz całkę ', 'rozwiąż ', 'uprość ',
                   'oblicz granicę ', 'granica ', 'differentiate ', 'integrate ', 'solve ',
                   'simplify ', 'limit of ', 'pochodna z ', 'całka z ']:
        if text.lower().startswith(prefix):
            expr_str = text[len(prefix):]
            break

    # Also strip trailing "przy x→0", "przy x->0", "as x→0" etc.
    expr_str = re.sub(r'\s+(?:przy|as|when|dla)\s+\w+\s*.\s*\S+.*$', '', expr_str, flags=re.IGNORECASE)

    # Also strip "od X do Y" (for numeric integration)
    expr_str = re.sub(r'\s+od\s+\S+\s+do\s+\S+.*$', '', expr_str, flags=re.IGNORECASE)

    # Remove trailing question marks, dots
    expr_str = expr_str.strip().rstrip('?.').strip()

    # If empty, try to find math expression
    if not expr_str:
        expr_str = text

    # Normalize: ^ → **, implicit multiplication 2x → 2*x
    expr_str = expr_str.replace('^', '**')
    expr_str = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr_str)

    # Create symbols for common variables
    local_dict = {}
    for v in VAR_NAMES:
        local_dict[v] = symbols(v)

    try:
        expr = parse_expr(expr_str, local_dict=local_dict, transformations=TRANSFORMS)
        return expr, local_dict
    except Exception:
        # Try extracting just the math part — but don't recurse on same text
        math_match = re.search(r'([a-zA-Z]\**\d*\s*[\+\-\*\/]\s*.+)', text)
        if math_match:
            extracted = math_match.group(1).strip()
            if extracted != expr_str:
                return _parse_expr(extracted)
        raise ValueError(f"Nie potrafię sparsować wyrażenia: {expr_str}")


def _find_variable(expr: sp.Expr, local_dict: dict) -> Symbol:
    """Find the main variable in an expression."""
    free_syms = list(expr.free_symbols)
    if free_syms:
        return free_syms[0]
    # Default to x
    return local_dict.get('x', symbols('x'))


def differentiate(text: str) -> SolveResult:
    """Compute derivative of an expression."""
    try:
        expr, local_dict = _parse_expr(text)
        var = _find_variable(expr, local_dict)

        steps = [
            f"Wyrażenie: ${latex(expr)}$",
            f"Zmienna: ${latex(var)}$",
        ]

        # First derivative
        deriv = sp.diff(expr, var)
        steps.append(f"Pierwsza pochodna: ${latex(deriv)}$")

        # Simplify
        deriv_simplified = simplify(deriv)
        if deriv_simplified != deriv:
            steps.append(f"Po uproszczeniu: ${latex(deriv_simplified)}$")

        # Second derivative
        deriv2 = sp.diff(expr, var, 2)
        steps.append(f"Druga pochodna: ${latex(deriv2)}$")

        return SolveResult(
            problem_type=ProblemType.SYMBOLIC_DIFF,
            input_text=text,
            result={
                "expression": str(expr),
                "variable": str(var),
                "first_derivative": str(deriv_simplified),
                "second_derivative": str(deriv2),
            },
            steps=steps,
            latex=latex(deriv_simplified),
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.SYMBOLIC_DIFF,
            input_text=text,
            result=None,
            error=f"Błąd różniczkowania: {e}",
        )


def integrate(text: str) -> SolveResult:
    """Compute indefinite and definite integral."""
    try:
        expr, local_dict = _parse_expr(text)
        var = _find_variable(expr, local_dict)

        steps = [
            f"Wyrażenie: ${latex(expr)}$",
            f"Zmienna całkowania: ${latex(var)}$",
        ]

        # Indefinite integral
        indef = sp.integrate(expr, var)
        steps.append(f"Całka nieoznaczona: $\\int {latex(expr)} \\, d{var} = {latex(indef)} + C$")

        # Try definite from 0 to 1 as example
        try:
            defin = sp.integrate(expr, (var, 0, 1))
            steps.append(f"Całka oznaczona [0,1]: $\\int_0^1 {latex(expr)} \\, d{var} = {latex(defin)}$")
            defin_val = float(defin.evalf())
            steps.append(f"Wartość numeryczna: {defin_val:.6f}")
        except Exception:
            defin = None
            defin_val = None

        return SolveResult(
            problem_type=ProblemType.SYMBOLIC_INTEGRATE,
            input_text=text,
            result={
                "expression": str(expr),
                "variable": str(var),
                "indefinite_integral": str(indef),
                "definite_01": str(defin) if defin else None,
                "definite_01_value": defin_val,
            },
            steps=steps,
            latex=latex(indef),
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.SYMBOLIC_INTEGRATE,
            input_text=text,
            result=None,
            error=f"Błąd całkowania: {e}",
        )


def solve_equation(text: str) -> SolveResult:
    """Solve an equation or system of equations."""
    try:
        # Check for equation with =
        if '=' in text:
            parts = text.split('=')
            left = _parse_expr(parts[0])[0]
            right = _parse_expr(parts[1])[0]
            eq = sp.Eq(left, right)
        else:
            expr, _ = _parse_expr(text)
            eq = sp.Eq(expr, 0)

        var = _find_variable(eq.lhs, {v: symbols(v) for v in VAR_NAMES})

        steps = [
            f"Równanie: ${latex(eq)}$",
            f"Zmienna: ${latex(var)}$",
        ]

        solutions = sp.solve(eq, var)
        steps.append(f"Rozwiązania: {solutions}")

        # Numerical approximations
        num_solutions = []
        for sol in solutions:
            try:
                num_solutions.append(float(sol.evalf()))
            except Exception:
                num_solutions.append(str(sol))

        if num_solutions:
            steps.append(f"Przybliżenia numeryczne: {num_solutions}")

        return SolveResult(
            problem_type=ProblemType.SYMBOLIC_SOLVE,
            input_text=text,
            result={
                "equation": str(eq),
                "variable": str(var),
                "solutions": [str(s) for s in solutions],
                "numerical": num_solutions,
            },
            steps=steps,
            latex=latex(eq),
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.SYMBOLIC_SOLVE,
            input_text=text,
            result=None,
            error=f"Błąd rozwiązywania: {e}",
        )


def simplify_expr(text: str) -> SolveResult:
    """Simplify a mathematical expression."""
    try:
        expr, _ = _parse_expr(text)

        steps = [f"Oryginalne wyrażenie: ${latex(expr)}$"]

        simplified = simplify(expr)
        steps.append(f"Po uproszczeniu: ${latex(simplified)}$")

        expanded = expand(expr)
        if expanded != expr and expanded != simplified:
            steps.append(f"Po rozwinięciu: ${latex(expanded)}$")

        factored = factor(expr)
        if factored != expr and factored != simplified:
            steps.append(f"Po rozłożeniu na czynniki: ${latex(factored)}$")

        return SolveResult(
            problem_type=ProblemType.SYMBOLIC_SIMPLIFY,
            input_text=text,
            result={
                "original": str(expr),
                "simplified": str(simplified),
                "expanded": str(expanded),
                "factored": str(factored),
            },
            steps=steps,
            latex=latex(simplified),
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.SYMBOLIC_SIMPLIFY,
            input_text=text,
            result=None,
            error=f"Błąd upraszczania: {e}",
        )


def compute_limit(text: str) -> SolveResult:
    """Compute a limit."""
    try:
        expr, local_dict = _parse_expr(text)
        var = _find_variable(expr, local_dict)

        # Try to find limit point
        limit_point = 0  # default
        for pattern in [r'→\s*(\d+|∞|oo|inf)', r'->\s*(\d+|∞|oo|inf)',
                        r'x\s*=\s*(\d+)', r'at\s+(\d+)']:
            m = re.search(pattern, text)
            if m:
                val = m.group(1)
                if val in ('∞', 'oo', 'inf'):
                    limit_point = sp.oo
                else:
                    limit_point = int(val)
                break

        steps = [
            f"Wyrażenie: ${latex(expr)}$",
            f"Granica przy ${var} \\to {limit_point}$",
        ]

        result = sp.limit(expr, var, limit_point)
        steps.append(f"Wynik: ${latex(result)}$")

        try:
            num_val = float(result.evalf())
            steps.append(f"Wartość numeryczna: {num_val:.6f}")
        except Exception:
            pass

        return SolveResult(
            problem_type=ProblemType.SYMBOLIC_LIMIT,
            input_text=text,
            result={
                "expression": str(expr),
                "variable": str(var),
                "limit_point": str(limit_point),
                "result": str(result),
            },
            steps=steps,
            latex=latex(result),
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.SYMBOLIC_LIMIT,
            input_text=text,
            result=None,
            error=f"Błąd obliczania granicy: {e}",
        )


def taylor_series(text: str) -> SolveResult:
    """Compute Taylor series expansion."""
    try:
        expr, local_dict = _parse_expr(text)
        var = _find_variable(expr, local_dict)

        # Default: around 0, order 5
        point = 0
        order = 5

        m = re.search(r'order\s*[=:]\s*(\d+)', text)
        if m:
            order = int(m.group(1))

        m = re.search(r'(?:around|at|point)\s*[=:]\s*(\d+)', text)
        if m:
            point = int(m.group(1))

        steps = [
            f"Funkcja: ${latex(expr)}$",
            f"Szereg Taylora rzędu {order} wokół {point}",
        ]

        series = sp.series(expr, var, point, order + 1).removeO()
        steps.append(f"Szereg: ${latex(series)}$")

        return SolveResult(
            problem_type=ProblemType.SYMBOLIC_SERIES,
            input_text=text,
            result={
                "expression": str(expr),
                "variable": str(var),
                "order": order,
                "point": point,
                "series": str(series),
            },
            steps=steps,
            latex=latex(series),
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.SYMBOLIC_SERIES,
            input_text=text,
            result=None,
            error=f"Błąd szeregu Taylora: {e}",
        )
