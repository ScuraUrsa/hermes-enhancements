"""
Hermes Math Tool — Bridge between Hermes Agent and Math Engine.

This tool allows Hermes to delegate ALL mathematical computation to the
math engine instead of trying to compute things in the LLM context.

Usage in Hermes skill:
    from hermes_math_tool import math_tool
    result = math_tool("derivative", expr="x**3 + 2*x**2 - 5*x + 1", var="x")
    result = math_tool("integral", expr="sin(x)*exp(x)", var="x")
    result = math_tool("solve", equation="x**2 - 5*x + 6 = 0")
    result = math_tool("credit_vs_etf", mortgage_principal=400000, mortgage_rate=0.07, ...)
    result = math_tool("monte_carlo_var", initial_value=100000, ...)
    result = math_tool("statistical_test", data=[...], test="normality")
    result = math_tool("optimize", f_str="x**2 + 3*sin(x)", bounds=(-5, 5))
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Ensure we can import from the same directory
_here = Path(__file__).parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from math_engine import MathEngine, MathResult

# Import demo functions
from demo_credit_vs_etf import simulate_strategies
from demo_monte_carlo import (
    estimate_pi, portfolio_var, black_scholes_mc, project_cost_pert, random_walk,
)
from demo_statistics import (
    distribution_gallery, hypothesis_testing_demo, regression_demo,
    bayesian_demo, correlation_analysis,
)
from demo_optimization import (
    function_optimization, linear_programming_demo, portfolio_optimization,
    curve_fitting_demo,
)

_engine = MathEngine(output_dir=str(_here / "output"))


def math_tool(operation: str, **kwargs: Any) -> dict:
    """
    Universal math tool for Hermes.

    Operations:
    -----
    SYMBOLIC:
      derivative(expr, var="x", order=1)
      integral(expr, var="x", a=None, b=None)
      solve(equation, var="x")
      solve_system(equations, variables)
      simplify(expr)
      expand(expr)
      factor(expr)
      limit(expr, var="x", point="0", direction="+")
      taylor(expr, var="x", point="0", order=5)
      ode(equation, func="y", var="x")
      matrix(matrix_str, operation="det")

    NUMERICAL:
      num_integrate(f_str, a, b, method="quad")
      optimize(f_str, bounds, minimize=True)
      ode_numerical(f_str, y0, t_span, num_points=100)
      root_find(f_str, a, b, method="brentq")
      interpolate(x, y, kind="cubic", x_new=None)
      fft(data, dt=1.0)

    STATISTICS:
      linear_regression(x, y)
      statistical_test(data, test="normality")
      probability_distribution(dist, params, x_values=None)
      monte_carlo(f_str, var="x", dist="normal", params=None, n_samples=10000)

    OPTIMIZATION:
      linear_programming(c, A_ub, b_ub, bounds=None, maximize=False)

    DEMOS (high-level):
      credit_vs_etf(mortgage_principal, mortgage_rate, mortgage_years, extra_payment, etf_return, etf_volatility, investment_horizon, n_simulations=500)
      monte_carlo_pi(n_points=100000)
      portfolio_var(initial_value, annual_return, annual_volatility, horizon_days, n_simulations)
      option_price(S0, K, T, r, sigma, n_simulations)
      project_pert(tasks=None, n_simulations=10000)
      random_walk(n_steps=1000, n_paths=20)
      hypothesis_tests()
      regression()
      bayesian()
      correlation()
      function_opt()
      linear_programming_demo()
      portfolio_opt()
      curve_fit()
    """
    try:
        # ---- Symbolic ----
        if operation == "derivative":
            r = _engine.symbolic_derivative(
                kwargs["expr"], kwargs.get("var", "x"), kwargs.get("order", 1))
        elif operation == "integral":
            r = _engine.symbolic_integral(
                kwargs["expr"], kwargs.get("var", "x"),
                kwargs.get("a"), kwargs.get("b"))
        elif operation == "solve":
            r = _engine.solve_equation(
                kwargs["equation"], kwargs.get("var", "x"))
        elif operation == "solve_system":
            r = _engine.solve_system(
                kwargs["equations"], kwargs["variables"])
        elif operation == "simplify":
            r = _engine.simplify_expression(kwargs["expr"])
        elif operation == "expand":
            r = _engine.expand_expression(kwargs["expr"])
        elif operation == "factor":
            r = _engine.factor_expression(kwargs["expr"])
        elif operation == "limit":
            r = _engine.limit_expression(
                kwargs["expr"], kwargs.get("var", "x"),
                kwargs.get("point", "0"), kwargs.get("direction", "+"))
        elif operation == "taylor":
            r = _engine.taylor_series(
                kwargs["expr"], kwargs.get("var", "x"),
                kwargs.get("point", "0"), kwargs.get("order", 5))
        elif operation == "ode":
            r = _engine.solve_ode(
                kwargs["equation"], kwargs.get("func", "y"), kwargs.get("var", "x"))
        elif operation == "matrix":
            r = _engine.matrix_operations(
                kwargs["matrix_str"], kwargs.get("operation", "det"))

        # ---- Numerical ----
        elif operation == "num_integrate":
            r = _engine.numerical_integrate(
                kwargs["f_str"], kwargs["a"], kwargs["b"],
                kwargs.get("method", "quad"))
        elif operation == "optimize":
            r = _engine.numerical_optimize(
                kwargs["f_str"], kwargs["bounds"],
                kwargs.get("minimize", True))
        elif operation == "ode_numerical":
            r = _engine.solve_ode_numerical(
                kwargs["f_str"], kwargs["y0"], kwargs["t_span"],
                kwargs.get("num_points", 100))
        elif operation == "root_find":
            r = _engine.root_finding(
                kwargs["f_str"], kwargs["a"], kwargs["b"],
                kwargs.get("method", "brentq"))
        elif operation == "interpolate":
            r = _engine.interpolate(
                kwargs["x"], kwargs["y"], kwargs.get("kind", "cubic"),
                kwargs.get("x_new"))
        elif operation == "fft":
            r = _engine.fourier_transform(
                kwargs["data"], kwargs.get("dt", 1.0))

        # ---- Statistics ----
        elif operation == "linear_regression":
            r = _engine.linear_regression(kwargs["x"], kwargs["y"])
        elif operation == "statistical_test":
            r = _engine.statistical_test(
                kwargs["data"], kwargs["test"], **{k: v for k, v in kwargs.items() if k not in ("data", "test")})
        elif operation == "probability_distribution":
            r = _engine.probability_distribution(
                kwargs["dist"], kwargs.get("params", {}),
                kwargs.get("x_values"))
        elif operation == "monte_carlo":
            r = _engine.monte_carlo(
                kwargs["f_str"], kwargs.get("var", "x"),
                kwargs.get("dist", "normal"), kwargs.get("params"),
                kwargs.get("n_samples", 10000))

        # ---- Optimization ----
        elif operation == "linear_programming":
            r = _engine.linear_programming(
                kwargs["c"], kwargs["A_ub"], kwargs["b_ub"],
                kwargs.get("bounds"), kwargs.get("maximize", False))

        # ---- High-level Demos ----
        elif operation == "credit_vs_etf":
            result = simulate_strategies(
                kwargs.get("mortgage_principal", 400_000),
                kwargs.get("mortgage_rate", 0.07),
                kwargs.get("mortgage_years", 25),
                kwargs.get("extra_payment", 1000),
                kwargs.get("etf_return", 0.10),
                kwargs.get("etf_volatility", 0.15),
                kwargs.get("investment_horizon", 20),
                kwargs.get("n_simulations", 500),
            )
            return {"success": True, "result": result}

        elif operation == "monte_carlo_pi":
            result = estimate_pi(kwargs.get("n_points", 100_000))
            return {"success": True, "result": result}

        elif operation == "portfolio_var":
            result = portfolio_var(
                kwargs.get("initial_value", 100_000),
                kwargs.get("annual_return", 0.08),
                kwargs.get("annual_volatility", 0.20),
                kwargs.get("horizon_days", 252),
                kwargs.get("n_simulations", 10_000),
            )
            return {"success": True, "result": result}

        elif operation == "option_price":
            result = black_scholes_mc(
                kwargs.get("S0", 100), kwargs.get("K", 105),
                kwargs.get("T", 1.0), kwargs.get("r", 0.05),
                kwargs.get("sigma", 0.20), kwargs.get("n_simulations", 100_000),
            )
            return {"success": True, "result": result}

        elif operation == "project_pert":
            result = project_cost_pert(
                kwargs.get("tasks"), kwargs.get("n_simulations", 10_000))
            return {"success": True, "result": result}

        elif operation == "random_walk":
            result = random_walk(
                kwargs.get("n_steps", 1000), kwargs.get("n_paths", 20))
            return {"success": True, "result": result}

        elif operation == "hypothesis_tests":
            result = hypothesis_testing_demo()
            return {"success": True, "result": result}

        elif operation == "regression":
            result = regression_demo()
            return {"success": True, "result": result}

        elif operation == "bayesian":
            result = bayesian_demo()
            return {"success": True, "result": result}

        elif operation == "correlation":
            result = correlation_analysis()
            return {"success": True, "result": result}

        elif operation == "function_opt":
            result = function_optimization()
            return {"success": True, "result": result}

        elif operation == "linear_programming_demo":
            result = linear_programming_demo()
            return {"success": True, "result": result}

        elif operation == "portfolio_opt":
            result = portfolio_optimization()
            return {"success": True, "result": result}

        elif operation == "curve_fit":
            result = curve_fitting_demo()
            return {"success": True, "result": result}

        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}

        # Convert MathResult to dict
        return {
            "success": r.success,
            "result": r.result,
            "latex": r.latex,
            "steps": r.steps,
            "error": r.error,
            "metadata": r.metadata,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# CLI for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python hermes_math_tool.py <operation> [key=value ...]")
        print("Example: python hermes_math_tool.py derivative expr='x**2+sin(x)' var=x")
        sys.exit(1)

    op = sys.argv[1]
    kwargs = {}
    for arg in sys.argv[2:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            # Try to parse as JSON/number
            try:
                v = json.loads(v)
            except (json.JSONDecodeError, ValueError):
                pass
            kwargs[k] = v

    result = math_tool(op, **kwargs)
    print(json.dumps(result, indent=2, default=str))
