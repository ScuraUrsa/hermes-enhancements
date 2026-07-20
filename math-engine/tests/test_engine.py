"""
Math Engine — testy jednostkowe.
Uruchom: PYTHONPATH=. python3 -m pytest tests/test_engine.py -v
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.engine import MathEngine, ProblemType, SolveResult


@pytest.fixture
def engine():
    return MathEngine(output_dir=tempfile.mkdtemp())


class TestClassification:
    def test_classify_derivative(self, engine):
        assert engine.classify("oblicz pochodną x^2") == ProblemType.SYMBOLIC_DIFF
        assert engine.classify("differentiate sin(x)") == ProblemType.SYMBOLIC_DIFF
        assert engine.classify("d/dx of x^3") == ProblemType.SYMBOLIC_DIFF

    def test_classify_integral(self, engine):
        assert engine.classify("oblicz całkę x^2") == ProblemType.SYMBOLIC_INTEGRATE
        assert engine.classify("∫ x dx") == ProblemType.SYMBOLIC_INTEGRATE
        assert engine.classify("całkowanie numeryczne") == ProblemType.SYMBOLIC_INTEGRATE

    def test_classify_equation(self, engine):
        assert engine.classify("rozwiąż równanie x^2 = 4") == ProblemType.SYMBOLIC_SOLVE

    def test_classify_mortgage_vs_etf(self, engine):
        assert engine.classify("kredyt vs etf 500000 7%") == ProblemType.FINANCIAL_MORTGAGE_VS_ETF
        assert engine.classify("czy nadpłacać kredyt czy inwestować w ETF") == ProblemType.FINANCIAL_MORTGAGE_VS_ETF

    def test_classify_mortgage(self, engine):
        assert engine.classify("kredyt hipoteczny 500000 na 7%") == ProblemType.FINANCIAL_MORTGAGE

    def test_classify_npv(self, engine):
        assert engine.classify("oblicz NPV dla przepływów") == ProblemType.FINANCIAL_NPV_IRR

    def test_classify_portfolio(self, engine):
        assert engine.classify("optymalizacja portfela Markowitz") == ProblemType.FINANCIAL_PORTFOLIO

    def test_classify_distribution(self, engine):
        assert engine.classify("rozkład normalny średnia 0 sigma 1") == ProblemType.PROBABILITY_DISTRIBUTION

    def test_classify_bayes(self, engine):
        assert engine.classify("twierdzenie Bayesa P(A)=0.01") == ProblemType.PROBABILITY_BAYES

    def test_classify_monte_carlo(self, engine):
        assert engine.classify("symulacja Monte Carlo") == ProblemType.PROBABILITY_MONTE_CARLO

    def test_classify_regression(self, engine):
        assert engine.classify("regresja liniowa") == ProblemType.PROBABILITY_REGRESSION

    def test_classify_plot(self, engine):
        assert engine.classify("narysuj wykres sin(x)") == ProblemType.PLOT_FUNCTION

    def test_classify_3d(self, engine):
        assert engine.classify("wykres 3d powierzchni") == ProblemType.PLOT_3D

    def test_classify_unknown(self, engine):
        assert engine.classify("jaki jest sens życia") == ProblemType.UNKNOWN


class TestSymbolic:
    def test_derivative(self, engine):
        result = engine.solve("oblicz pochodną x**2 * sin(x)")
        assert result.problem_type == ProblemType.SYMBOLIC_DIFF
        assert result.error is None
        assert result.result is not None
        assert "first_derivative" in result.result

    def test_integral(self, engine):
        result = engine.solve("całka z x**2 + 3*x + 1")
        assert result.problem_type == ProblemType.SYMBOLIC_INTEGRATE
        assert result.error is None
        assert "indefinite_integral" in result.result

    def test_solve_equation(self, engine):
        result = engine.solve("rozwiąż x**2 - 4 = 0")
        assert result.problem_type == ProblemType.SYMBOLIC_SOLVE
        assert result.error is None
        assert len(result.result["solutions"]) == 2

    def test_simplify(self, engine):
        result = engine.solve("uprość (x+1)**2 - x**2")
        assert result.problem_type == ProblemType.SYMBOLIC_SIMPLIFY
        assert result.error is None

    def test_limit(self, engine):
        result = engine.solve("granica sin(x)/x at 0")
        assert result.problem_type == ProblemType.SYMBOLIC_LIMIT
        assert result.error is None

    def test_taylor(self, engine):
        result = engine.solve("szereg Taylora exp(x) rzędu 5")
        assert result.problem_type == ProblemType.SYMBOLIC_SERIES
        assert result.error is None


class TestNumeric:
    def test_optimize(self, engine):
        result = engine.solve("znajdź minimum x**2 + 2*x + 1")
        assert result.problem_type == ProblemType.NUMERIC_OPTIMIZE
        assert result.error is None

    def test_integrate_numeric(self, engine):
        result = engine.solve("całka numeryczna x**2 bounds 0 1")
        assert result.problem_type == ProblemType.NUMERIC_INTEGRATE
        assert result.error is None

    def test_root(self, engine):
        result = engine.solve("miejsce zerowe x**2 - 4")
        assert result.problem_type == ProblemType.NUMERIC_ROOT
        assert result.error is None


class TestFinancial:
    def test_mortgage(self, engine):
        result = engine.solve("kredyt hipoteczny 500000 PLN 7% 25 lat")
        assert result.problem_type == ProblemType.FINANCIAL_MORTGAGE
        assert result.error is None
        assert result.result["monthly_payment"] > 0

    def test_mortgage_vs_etf(self, engine):
        result = engine.solve("kredyt 500000 7% vs ETF 8% 25 lat")
        assert result.problem_type == ProblemType.FINANCIAL_MORTGAGE_VS_ETF
        assert result.error is None
        assert "comparison" in result.result
        assert result.result["break_even_etf_return"] > 0

    def test_npv_irr(self, engine):
        result = engine.solve("NPV -1000, 500, 500, 500 stopa 8%")
        assert result.problem_type == ProblemType.FINANCIAL_NPV_IRR
        assert result.error is None

    def test_portfolio(self, engine):
        result = engine.solve("optymalizacja portfela Markowitz")
        assert result.problem_type == ProblemType.FINANCIAL_PORTFOLIO
        assert result.error is None

    def test_amortization(self, engine):
        result = engine.solve("harmonogram spłat kredytu 500000 7% 25 lat")
        assert result.problem_type == ProblemType.FINANCIAL_AMORTIZATION
        assert result.error is None


class TestProbability:
    def test_distribution(self, engine):
        result = engine.solve("rozkład normalny średnia 0 sigma 1")
        assert result.problem_type == ProblemType.PROBABILITY_DISTRIBUTION
        assert result.error is None

    def test_bayes(self, engine):
        result = engine.solve("Bayes P(A)=1% P(B|A)=80% P(B|~A)=10%")
        assert result.problem_type == ProblemType.PROBABILITY_BAYES
        assert result.error is None
        assert 0 < result.result["p_a_given_b"] < 1

    def test_monte_carlo(self, engine):
        result = engine.solve("Monte Carlo estymacja pi")
        assert result.problem_type == ProblemType.PROBABILITY_MONTE_CARLO
        assert result.error is None

    def test_regression(self, engine):
        result = engine.solve("regresja liniowa 50 punktów")
        assert result.problem_type == ProblemType.PROBABILITY_REGRESSION
        assert result.error is None
        assert result.result["r_squared"] > 0


class TestPlotting:
    def test_plot_function(self, engine):
        result = engine.solve("narysuj wykres sin(x) * exp(-x/5)")
        assert result.problem_type == ProblemType.PLOT_FUNCTION
        assert result.error is None
        assert result.plot_path is not None
        assert os.path.exists(result.plot_path)

    def test_plot_3d(self, engine):
        result = engine.solve("wykres 3d x**2 - y**2")
        assert result.problem_type == ProblemType.PLOT_3D
        assert result.error is None
        assert result.plot_path is not None
        assert os.path.exists(result.plot_path)


class TestEdgeCases:
    def test_unknown_problem(self, engine):
        result = engine.solve("jaki jest sens życia")
        assert result.problem_type == ProblemType.UNKNOWN
        assert result.error is not None

    def test_empty_input(self, engine):
        result = engine.solve("")
        assert result.problem_type == ProblemType.UNKNOWN

    def test_gibberish(self, engine):
        result = engine.solve("asdfghjkl12345")
        assert result.problem_type == ProblemType.UNKNOWN
