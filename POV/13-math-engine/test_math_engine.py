"""
Tests for Math Engine — symbolic, numerical, statistics, optimization.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from math_engine import MathEngine, MathResult


@pytest.fixture
def engine():
    return MathEngine(output_dir="/tmp/math_engine_test")


class TestSymbolic:
    """Symbolic math tests (SymPy)."""

    def test_derivative_simple(self, engine):
        r = engine.symbolic_derivative("x**3", "x")
        assert r.success
        assert "3*x**2" in r.result

    def test_derivative_sin(self, engine):
        r = engine.symbolic_derivative("sin(x)", "x")
        assert r.success
        assert "cos" in r.result.lower()

    def test_derivative_higher_order(self, engine):
        r = engine.symbolic_derivative("x**4", "x", order=2)
        assert r.success
        assert "12*x**2" in r.result

    def test_derivative_invalid(self, engine):
        r = engine.symbolic_derivative("x**2 +", "x")
        assert not r.success

    def test_integral_polynomial(self, engine):
        r = engine.symbolic_integral("x**2", "x")
        assert r.success
        assert "x**3/3" in r.result

    def test_integral_definite(self, engine):
        r = engine.symbolic_integral("x**2", "x", a="0", b="1")
        assert r.success
        assert "1/3" in r.result

    def test_solve_quadratic(self, engine):
        r = engine.solve_equation("x**2 - 4 = 0", "x")
        assert r.success
        assert len(r.result) == 2

    def test_solve_linear(self, engine):
        r = engine.solve_equation("2*x + 3 = 7", "x")
        assert r.success
        assert "2" in r.result[0]

    def test_solve_system(self, engine):
        r = engine.solve_system(["x + y = 5", "x - y = 1"], ["x", "y"])
        assert r.success
        assert len(r.result) == 1
        assert r.result[0]["x"] == "3"
        assert r.result[0]["y"] == "2"

    def test_simplify(self, engine):
        r = engine.simplify_expression("sin(x)**2 + cos(x)**2")
        assert r.success
        assert r.result == "1"

    def test_expand(self, engine):
        r = engine.expand_expression("(x + 1)**3")
        assert r.success
        assert "x**3" in r.result

    def test_factor(self, engine):
        r = engine.factor_expression("x**2 - 1")
        assert r.success
        assert "(x - 1)*(x + 1)" in r.result

    def test_limit(self, engine):
        r = engine.limit_expression("sin(x)/x", "x", "0")
        assert r.success
        assert r.result == "1"

    def test_taylor_sin(self, engine):
        r = engine.taylor_series("sin(x)", "x", "0", order=3)
        assert r.success
        assert "x" in r.result

    def test_ode_simple(self, engine):
        r = engine.solve_ode("Derivative(y(x), x) - y(x)", "y", "x")
        assert r.success
        assert "exp" in r.result.lower()

    def test_matrix_det(self, engine):
        r = engine.matrix_operations("[[1,2],[3,4]]", "det")
        assert r.success
        assert r.result == "-2"

    def test_matrix_inv(self, engine):
        r = engine.matrix_operations("[[1,2],[3,4]]", "inv")
        assert r.success
        assert "-2" in r.result

    def test_matrix_eigenvalues(self, engine):
        r = engine.matrix_operations("[[1,0],[0,2]]", "eig")
        assert r.success


class TestNumerical:
    """Numerical math tests (NumPy/SciPy)."""

    def test_numerical_integrate(self, engine):
        r = engine.numerical_integrate("x**2", 0, 1)
        assert r.success
        assert abs(r.result - 1/3) < 1e-6

    def test_numerical_optimize_min(self, engine):
        r = engine.numerical_optimize("x**2", (-5, 5), minimize=True)
        assert r.success
        assert abs(r.result["x"]) < 1e-4
        assert abs(r.result["f(x)"]) < 1e-4

    def test_numerical_optimize_max(self, engine):
        r = engine.numerical_optimize("-(x-2)**2 + 5", (-10, 10), minimize=False)
        assert r.success
        assert abs(r.result["x"] - 2) < 0.1

    def test_root_finding(self, engine):
        r = engine.root_finding("x**2 - 4", 0, 5)
        assert r.success
        assert abs(r.result["root"] - 2) < 1e-6

    def test_interpolate(self, engine):
        r = engine.interpolate([0, 1, 2, 3], [0, 1, 4, 9])
        assert r.success
        assert len(r.result["x"]) == 200
        assert len(r.result["y"]) == 200

    def test_fft(self, engine):
        r = engine.fourier_transform([1, 0, -1, 0] * 4)
        assert r.success
        assert len(r.result["frequencies"]) > 0
        assert len(r.result["magnitude"]) > 0


class TestStatistics:
    """Statistics tests."""

    def test_linear_regression(self, engine):
        r = engine.linear_regression([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        assert r.success
        assert abs(r.result["slope"] - 2) < 1e-6
        assert abs(r.result["intercept"]) < 1e-6
        assert abs(r.result["r_squared"] - 1) < 1e-6

    def test_statistical_test_normality(self, engine):
        import numpy as np
        rng = np.random.RandomState(42)
        data = rng.normal(0, 1, 100).tolist()
        r = engine.statistical_test(data, "normality")
        assert r.success
        assert "p_value" in r.result

    def test_statistical_test_describe(self, engine):
        r = engine.statistical_test([1, 2, 3, 4, 5], "describe")
        assert r.success
        assert r.result["n"] == 5
        assert r.result["mean"] == 3.0

    def test_probability_distribution_normal(self, engine):
        r = engine.probability_distribution("normal", {"loc": 0, "scale": 1})
        assert r.success
        assert abs(r.result["mean"]) < 1e-6
        assert abs(r.result["std"] - 1) < 1e-6

    def test_probability_distribution_with_x(self, engine):
        r = engine.probability_distribution("normal", {"loc": 0, "scale": 1},
                                            x_values=[-2, -1, 0, 1, 2])
        assert r.success
        assert len(r.result["pdf"]) == 5
        assert len(r.result["cdf"]) == 5

    def test_monte_carlo(self, engine):
        r = engine.monte_carlo("x**2", "x", "normal", {"loc": 0, "scale": 1}, n_samples=5000)
        assert r.success
        assert abs(r.result["mean"] - 1) < 0.1  # E[X²] = 1 for N(0,1)


class TestOptimization:
    """Optimization tests."""

    def test_linear_programming(self, engine):
        # Maximize 3x + 2y subject to x + y ≤ 4, x ≤ 2, y ≤ 3
        r = engine.linear_programming(
            c=[3, 2],
            A_ub=[[1, 1], [1, 0], [0, 1]],
            b_ub=[4, 2, 3],
            maximize=True,
        )
        assert r.success
        assert abs(r.result["x"][0] - 2) < 0.01
        assert abs(r.result["x"][1] - 2) < 0.01
        assert abs(r.result["objective"] - 10) < 0.01


class TestMathResult:
    """MathResult dataclass tests."""

    def test_success_result(self):
        r = MathResult(success=True, result="42", latex="42", steps=["step1"])
        assert r.success
        assert r.result == "42"

    def test_error_result(self):
        r = MathResult(success=False, error="division by zero")
        assert not r.success
        assert r.error == "division by zero"


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_expression(self, engine):
        r = engine.symbolic_derivative("", "x")
        assert not r.success

    def test_division_by_zero_limit(self, engine):
        r = engine.limit_expression("1/x", "x", "0", "+")
        assert r.success
        assert "oo" in r.result  # infinity

    def test_complex_expression(self, engine):
        r = engine.symbolic_derivative("exp(x)*sin(x)", "x")
        assert r.success
        assert "exp" in r.result.lower()

    def test_large_polynomial(self, engine):
        r = engine.expand_expression("(x + 1)**10")
        assert r.success
        assert "x**10" in r.result

    def test_trig_identity(self, engine):
        r = engine.simplify_expression("sin(x)**2 + cos(x)**2")
        assert r.success
        assert r.result == "1"
