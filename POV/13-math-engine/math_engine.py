"""
Math Engine for Hermes — Symbolic & Numerical Computation Backend.

LLM should NEVER do math. This engine provides:
- Symbolic math (SymPy): derivatives, integrals, equation solving, formula derivation
- Numerical math (NumPy/SciPy): linear algebra, optimization, integration, ODEs
- Statistics (SciPy.stats): distributions, tests, regression, probability
- Visualization (matplotlib/plotly): charts, plots, decision surfaces

Usage:
    from math_engine import MathEngine
    engine = MathEngine()
    result = engine.symbolic_derivative("x**2 + sin(x)", "x")
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import scipy.integrate
import scipy.linalg
import scipy.optimize
import scipy.stats
import sympy as sp
from sympy import (
    Eq, Function, Integral, Limit, Matrix, Piecewise, Rational, Symbol,
    Derivative, diff, dsolve, expand, factor, integrate, latex, limit,
    oo, pi, simplify, solve, symbols, E, I, S,
)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class MathResult:
    """Structured result from any math operation."""
    success: bool
    result: Any = None
    latex: str = ""
    steps: list[str] = field(default_factory=list)
    error: str = ""
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class MathEngine:
    """Unified math computation engine for Hermes."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Symbolic ----

    def symbolic_derivative(self, expr: str, var: str = "x", order: int = 1) -> MathResult:
        """Compute symbolic derivative d^n/dx^n of expression."""
        try:
            x = symbols(var)
            f = sp.sympify(expr)
            steps = [f"f({var}) = {latex(f)}"]
            d = f
            for n in range(1, order + 1):
                d = diff(d, x)
                steps.append(f"d^{n}/d{var}^{n} f = {latex(d)}")
            return MathResult(
                success=True,
                result=str(d),
                latex=latex(d),
                steps=steps,
                metadata={"expr": expr, "var": var, "order": order},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def symbolic_integral(self, expr: str, var: str = "x",
                          a: Optional[str] = None, b: Optional[str] = None) -> MathResult:
        """Compute symbolic indefinite or definite integral."""
        try:
            x = symbols(var)
            f = sp.sympify(expr)
            steps = [f"∫ {latex(f)} d{var}"]
            if a is not None and b is not None:
                a_val = sp.sympify(a)
                b_val = sp.sympify(b)
                result = integrate(f, (x, a_val, b_val))
                steps.append(f"= {latex(result)} (definite from {a} to {b})")
            else:
                result = integrate(f, x)
                steps.append(f"= {latex(result)} + C")
            return MathResult(
                success=True,
                result=str(result),
                latex=latex(result),
                steps=steps,
                metadata={"expr": expr, "var": var, "a": a, "b": b},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def solve_equation(self, equation: str, var: str = "x") -> MathResult:
        """Solve equation symbolically. E.g. 'x**2 - 4 = 0' or 'x**2 + y**2 = 1'."""
        try:
            x = symbols(var)
            # Parse: "lhs = rhs" or just "expr"
            if "=" in equation:
                lhs_str, rhs_str = equation.split("=", 1)
                eq = Eq(sp.sympify(lhs_str.strip()), sp.sympify(rhs_str.strip()))
            else:
                eq = Eq(sp.sympify(equation.strip()), 0)
            steps = [f"Equation: {latex(eq)}"]
            solutions = solve(eq, x)
            steps.append(f"Solutions: {latex(solutions)}")
            return MathResult(
                success=True,
                result=[str(s) for s in solutions],
                latex=latex(solutions),
                steps=steps,
                metadata={"equation": equation, "var": var},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def solve_system(self, equations: list[str], variables: list[str]) -> MathResult:
        """Solve system of equations symbolically."""
        try:
            syms = symbols(" ".join(variables))
            if len(variables) == 1:
                syms = (syms,)
            eqs = []
            for eq_str in equations:
                if "=" in eq_str:
                    lhs, rhs = eq_str.split("=", 1)
                    eqs.append(Eq(sp.sympify(lhs.strip()), sp.sympify(rhs.strip())))
                else:
                    eqs.append(Eq(sp.sympify(eq_str.strip()), 0))
            steps = [f"System: {[latex(e) for e in eqs]}"]
            solutions = solve(eqs, syms, dict=True)
            steps.append(f"Solutions: {solutions}")
            return MathResult(
                success=True,
                result=[{str(k): str(v) for k, v in s.items()} for s in solutions],
                latex=latex(solutions),
                steps=steps,
                metadata={"equations": equations, "variables": variables},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def simplify_expression(self, expr: str) -> MathResult:
        """Simplify a symbolic expression."""
        try:
            f = sp.sympify(expr)
            steps = [f"Original: {latex(f)}"]
            s = simplify(f)
            steps.append(f"Simplified: {latex(s)}")
            return MathResult(
                success=True,
                result=str(s),
                latex=latex(s),
                steps=steps,
                metadata={"expr": expr},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def expand_expression(self, expr: str) -> MathResult:
        """Expand a symbolic expression."""
        try:
            f = sp.sympify(expr)
            steps = [f"Original: {latex(f)}"]
            e = expand(f)
            steps.append(f"Expanded: {latex(e)}")
            return MathResult(
                success=True,
                result=str(e),
                latex=latex(e),
                steps=steps,
                metadata={"expr": expr},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def factor_expression(self, expr: str) -> MathResult:
        """Factor a symbolic expression."""
        try:
            f = sp.sympify(expr)
            steps = [f"Original: {latex(f)}"]
            fac = factor(f)
            steps.append(f"Factored: {latex(fac)}")
            return MathResult(
                success=True,
                result=str(fac),
                latex=latex(fac),
                steps=steps,
                metadata={"expr": expr},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def limit_expression(self, expr: str, var: str = "x", point: str = "0",
                         direction: str = "+") -> MathResult:
        """Compute limit of expression as var → point."""
        try:
            x = symbols(var)
            f = sp.sympify(expr)
            p = sp.sympify(point)
            steps = [f"lim_{{{var}→{point}}} {latex(f)}"]
            result = limit(f, x, p, dir=direction)
            steps.append(f"= {latex(result)}")
            return MathResult(
                success=True,
                result=str(result),
                latex=latex(result),
                steps=steps,
                metadata={"expr": expr, "var": var, "point": point, "direction": direction},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def taylor_series(self, expr: str, var: str = "x", point: str = "0",
                      order: int = 5) -> MathResult:
        """Compute Taylor series expansion."""
        try:
            x = symbols(var)
            f = sp.sympify(expr)
            p = sp.sympify(point)
            steps = [f"Taylor series of {latex(f)} around {var}={point}, order {order}"]
            series = sp.series(f, x, p, order + 1).removeO()
            steps.append(f"= {latex(series)}")
            return MathResult(
                success=True,
                result=str(series),
                latex=latex(series),
                steps=steps,
                metadata={"expr": expr, "var": var, "point": point, "order": order},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def solve_ode(self, equation: str, func: str = "y", var: str = "x") -> MathResult:
        """Solve ordinary differential equation symbolically.
        E.g. 'Derivative(y(x), x) - y(x)' for dy/dx = y
        """
        try:
            x = symbols(var)
            y = Function(func)(x)
            eq = Eq(sp.sympify(equation), 0)
            steps = [f"ODE: {latex(eq)} = 0"]
            sol = dsolve(eq, y)
            steps.append(f"Solution: {latex(sol)}")
            return MathResult(
                success=True,
                result=str(sol),
                latex=latex(sol),
                steps=steps,
                metadata={"equation": equation, "func": func, "var": var},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def matrix_operations(self, matrix_str: str, operation: str,
                          **kwargs: Any) -> MathResult:
        """Perform matrix operations: det, inv, eig, rref, transpose, rank.
        matrix_str: '[[1,2],[3,4]]' or '1,2;3,4'
        """
        try:
            M = sp.Matrix(sp.sympify(matrix_str))
            steps = [f"Matrix: {latex(M)}"]
            if operation == "det":
                r = M.det()
                steps.append(f"det = {latex(r)}")
            elif operation == "inv":
                r = M.inv()
                steps.append(f"M⁻¹ = {latex(r)}")
            elif operation == "eig":
                r = M.eigenvals()
                steps.append(f"Eigenvalues: {latex(r)}")
            elif operation == "eigvects":
                r = M.eigenvects()
                steps.append(f"Eigenvectors: {latex(r)}")
            elif operation == "rref":
                r, pivots = M.rref()
                steps.append(f"RREF: {latex(r)}, pivots: {pivots}")
            elif operation == "transpose":
                r = M.T
                steps.append(f"Mᵀ = {latex(r)}")
            elif operation == "rank":
                r = M.rank()
                steps.append(f"rank = {r}")
            elif operation == "charpoly":
                lam = symbols("lambda")
                r = M.charpoly(lam)
                steps.append(f"Characteristic polynomial: {latex(r)}")
            else:
                return MathResult(success=False, error=f"Unknown operation: {operation}")
            return MathResult(
                success=True,
                result=str(r),
                latex=latex(r) if not isinstance(r, int) else str(r),
                steps=steps,
                metadata={"matrix": matrix_str, "operation": operation},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    # ---- Numerical ----

    def numerical_integrate(self, f_str: str, a: float, b: float,
                            method: str = "quad") -> MathResult:
        """Numerically integrate f(x) from a to b."""
        try:
            x = symbols("x")
            f_sym = sp.sympify(f_str)
            f_num = sp.lambdify(x, f_sym, "numpy")
            if method == "quad":
                result, error = scipy.integrate.quad(f_num, a, b)
            elif method == "romberg":
                result = scipy.integrate.romberg(f_num, a, b)
                error = None
            else:
                return MathResult(success=False, error=f"Unknown method: {method}")
            return MathResult(
                success=True,
                result=float(result),
                metadata={"f": f_str, "a": a, "b": b, "method": method, "error_est": float(error) if error else None},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def numerical_optimize(self, f_str: str, bounds: tuple[float, float],
                           minimize: bool = True) -> MathResult:
        """Find minimum or maximum of f(x) in bounds."""
        try:
            x = symbols("x")
            f_sym = sp.sympify(f_str)
            f_num = sp.lambdify(x, f_sym, "numpy")
            if minimize:
                result = scipy.optimize.minimize_scalar(f_num, bounds=bounds, method="bounded")
            else:
                neg_f = lambda x: -f_num(x)
                result = scipy.optimize.minimize_scalar(neg_f, bounds=bounds, method="bounded")
                result.fun = -result.fun
            return MathResult(
                success=result.success,
                result={"x": float(result.x), "f(x)": float(result.fun)},
                metadata={"f": f_str, "bounds": bounds, "minimize": minimize, "iterations": result.nit},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def solve_ode_numerical(self, f_str: str, y0: float, t_span: tuple[float, float],
                            num_points: int = 100) -> MathResult:
        """Numerically solve ODE dy/dt = f(t, y)."""
        try:
            t_sym, y_sym = symbols("t y")
            f_sym = sp.sympify(f_str)
            f_num = sp.lambdify((t_sym, y_sym), f_sym, "numpy")

            t_eval = np.linspace(t_span[0], t_span[1], num_points)
            sol = scipy.integrate.solve_ivp(f_num, t_span, [y0], t_eval=t_eval)
            return MathResult(
                success=sol.success,
                result={"t": sol.t.tolist(), "y": sol.y[0].tolist()},
                metadata={"f": f_str, "y0": y0, "t_span": t_span, "num_points": num_points},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def linear_regression(self, x: list[float], y: list[float]) -> MathResult:
        """Perform linear regression: y = a*x + b."""
        try:
            slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(x, y)
            return MathResult(
                success=True,
                result={
                    "slope": float(slope),
                    "intercept": float(intercept),
                    "r_squared": float(r_value ** 2),
                    "p_value": float(p_value),
                    "std_err": float(std_err),
                },
                metadata={"n": len(x)},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def statistical_test(self, data: list[float], test: str,
                         **kwargs: Any) -> MathResult:
        """Run statistical tests: normality, t-test, chi2, etc."""
        try:
            arr = np.array(data)
            if test == "normality":
                stat, p = scipy.stats.shapiro(arr)
                result = {"test": "Shapiro-Wilk", "statistic": float(stat), "p_value": float(p)}
            elif test == "ttest_1samp":
                popmean = kwargs.get("popmean", 0)
                stat, p = scipy.stats.ttest_1samp(arr, popmean)
                result = {"test": "One-sample t-test", "statistic": float(stat), "p_value": float(p)}
            elif test == "describe":
                desc = scipy.stats.describe(arr)
                result = {
                    "n": int(desc.nobs),
                    "min": float(desc.minmax[0]),
                    "max": float(desc.minmax[1]),
                    "mean": float(desc.mean),
                    "variance": float(desc.variance),
                    "skewness": float(desc.skewness),
                    "kurtosis": float(desc.kurtosis),
                }
            else:
                return MathResult(success=False, error=f"Unknown test: {test}")
            return MathResult(success=True, result=result, metadata={"test": test, "n": len(data)})
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def probability_distribution(self, dist: str, params: dict,
                                 x_values: Optional[list[float]] = None) -> MathResult:
        """Compute PDF/CDF/quantiles for probability distributions."""
        try:
            dist_map = {
                "normal": scipy.stats.norm,
                "t": scipy.stats.t,
                "chi2": scipy.stats.chi2,
                "f": scipy.stats.f,
                "expon": scipy.stats.expon,
                "uniform": scipy.stats.uniform,
                "beta": scipy.stats.beta,
                "gamma": scipy.stats.gamma,
                "lognorm": scipy.stats.lognorm,
                "poisson": scipy.stats.poisson,
                "binom": scipy.stats.binom,
            }
            if dist not in dist_map:
                return MathResult(success=False, error=f"Unknown distribution: {dist}. Available: {list(dist_map.keys())}")

            d = dist_map[dist](**params)
            if x_values:
                pdf_vals = d.pdf(x_values).tolist()
                cdf_vals = d.cdf(x_values).tolist()
                return MathResult(
                    success=True,
                    result={"x": x_values, "pdf": pdf_vals, "cdf": cdf_vals},
                    metadata={"dist": dist, "params": params},
                )
            else:
                return MathResult(
                    success=True,
                    result={
                        "mean": float(d.mean()),
                        "var": float(d.var()),
                        "std": float(d.std()),
                        "median": float(d.median()),
                        "interval_95": [float(d.ppf(0.025)), float(d.ppf(0.975))],
                    },
                    metadata={"dist": dist, "params": params},
                )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def monte_carlo(self, f_str: str, var: str = "x", dist: str = "normal",
                    params: Optional[dict] = None, n_samples: int = 10000) -> MathResult:
        """Monte Carlo simulation: sample from distribution, evaluate f(x)."""
        try:
            if params is None:
                params = {"loc": 0, "scale": 1}
            dist_map = {
                "normal": scipy.stats.norm,
                "lognorm": scipy.stats.lognorm,
                "uniform": scipy.stats.uniform,
                "expon": scipy.stats.expon,
            }
            if dist not in dist_map:
                return MathResult(success=False, error=f"Unknown distribution: {dist}")

            d = dist_map[dist](**params)
            samples = d.rvs(size=n_samples)

            x = symbols(var)
            f_sym = sp.sympify(f_str)
            f_num = sp.lambdify(x, f_sym, "numpy")
            results = f_num(samples)

            return MathResult(
                success=True,
                result={
                    "samples": samples.tolist(),
                    "results": results.tolist(),
                    "mean": float(np.mean(results)),
                    "std": float(np.std(results)),
                    "var_95": float(np.percentile(results, 5)),
                    "var_99": float(np.percentile(results, 1)),
                    "median": float(np.median(results)),
                },
                metadata={"f": f_str, "dist": dist, "params": params, "n_samples": n_samples},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def linear_programming(self, c: list[float], A_ub: list[list[float]],
                           b_ub: list[float], bounds: Optional[list[tuple]] = None,
                           maximize: bool = False) -> MathResult:
        """Solve linear programming problem: min/max c·x subject to A_ub·x ≤ b_ub."""
        try:
            c_arr = np.array(c)
            if maximize:
                c_arr = -c_arr
            A_arr = np.array(A_ub)
            b_arr = np.array(b_ub)
            result = scipy.optimize.linprog(c_arr, A_ub=A_arr, b_ub=b_arr, bounds=bounds)
            obj_val = float(-result.fun) if maximize else float(result.fun)
            return MathResult(
                success=result.success,
                result={
                    "x": result.x.tolist(),
                    "objective": obj_val,
                    "status": result.message,
                },
                metadata={"c": c, "maximize": maximize, "nit": result.nit},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def root_finding(self, f_str: str, a: float, b: float,
                     method: str = "brentq") -> MathResult:
        """Find root of f(x) = 0 in interval [a, b]."""
        try:
            x = symbols("x")
            f_sym = sp.sympify(f_str)
            f_num = sp.lambdify(x, f_sym, "numpy")
            if method == "brentq":
                root = scipy.optimize.brentq(f_num, a, b)
            elif method == "newton":
                root = scipy.optimize.newton(f_num, (a + b) / 2)
            else:
                return MathResult(success=False, error=f"Unknown method: {method}")
            return MathResult(
                success=True,
                result={"root": float(root), "f(root)": float(f_num(root))},
                metadata={"f": f_str, "a": a, "b": b, "method": method},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def interpolate(self, x: list[float], y: list[float], kind: str = "cubic",
                    x_new: Optional[list[float]] = None) -> MathResult:
        """Interpolate data points."""
        try:
            from scipy.interpolate import interp1d
            f = interp1d(x, y, kind=kind, fill_value="extrapolate")
            if x_new is None:
                x_new = np.linspace(min(x), max(x), 200).tolist()
            y_new = f(x_new).tolist()
            return MathResult(
                success=True,
                result={"x": x_new, "y": y_new},
                metadata={"kind": kind, "n_original": len(x)},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))

    def fourier_transform(self, data: list[float], dt: float = 1.0) -> MathResult:
        """Compute FFT of time series data."""
        try:
            arr = np.array(data)
            n = len(arr)
            fft = np.fft.fft(arr)
            freqs = np.fft.fftfreq(n, dt)
            magnitude = np.abs(fft)
            # Only positive frequencies
            pos_mask = freqs >= 0
            return MathResult(
                success=True,
                result={
                    "frequencies": freqs[pos_mask].tolist(),
                    "magnitude": magnitude[pos_mask].tolist(),
                    "phase": np.angle(fft)[pos_mask].tolist(),
                },
                metadata={"n": n, "dt": dt},
            )
        except Exception as e:
            return MathResult(success=False, error=str(e))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    engine = MathEngine()

    if len(sys.argv) < 2:
        print("Usage: python math_engine.py <operation> [args...]")
        print("Operations: derivative, integral, solve, simplify, expand, factor, limit, taylor, ode, matrix, num_integrate, optimize, regression, stats, prob, monte_carlo, lp, root, interpolate, fft")
        sys.exit(1)

    op = sys.argv[1]
    args = sys.argv[2:]

    if op == "derivative":
        r = engine.symbolic_derivative(args[0], args[1] if len(args) > 1 else "x")
    elif op == "integral":
        r = engine.symbolic_integral(args[0], args[1] if len(args) > 1 else "x")
    elif op == "solve":
        r = engine.solve_equation(args[0], args[1] if len(args) > 1 else "x")
    elif op == "simplify":
        r = engine.simplify_expression(args[0])
    elif op == "expand":
        r = engine.expand_expression(args[0])
    elif op == "factor":
        r = engine.factor_expression(args[0])
    elif op == "limit":
        r = engine.limit_expression(args[0], args[1] if len(args) > 1 else "x", args[2] if len(args) > 2 else "0")
    elif op == "taylor":
        r = engine.taylor_series(args[0], args[1] if len(args) > 1 else "x", args[2] if len(args) > 2 else "0", int(args[3]) if len(args) > 3 else 5)
    elif op == "ode":
        r = engine.solve_ode(args[0])
    elif op == "matrix":
        r = engine.matrix_operations(args[0], args[1] if len(args) > 1 else "det")
    else:
        r = MathResult(success=False, error=f"Unknown operation: {op}")

    print(json.dumps({"success": r.success, "result": r.result, "latex": r.latex, "steps": r.steps, "error": r.error}, indent=2, default=str))
