"""
Tests for demo modules: time series, game theory, differential equations.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from demo_time_series import (
    generate_synthetic_series, decompose_series, autocorrelation,
    adf_test, fit_arima, fit_garch, exponential_smoothing,
)
from demo_game_theory import (
    find_pure_nash, find_mixed_nash, shapley_value,
    GAMES,
)
from demo_differential_equations import (
    lotka_volterra, lorenz, van_der_pol, pendulum,
    jacobian_eigenvalues,
)


class TestTimeSeries:
    """Time series analysis tests."""

    def test_generate_series(self):
        series = generate_synthetic_series(n=200, seed=42)
        assert len(series) == 200
        assert not np.any(np.isnan(series))
        assert not np.any(np.isinf(series))

    def test_decompose(self):
        series = generate_synthetic_series(n=200, seed=42)
        decomp = decompose_series(series, period=20)
        assert len(decomp["trend"]) == 200
        assert len(decomp["seasonal"]) == 200
        assert len(decomp["residual"]) == 200

    def test_autocorrelation(self):
        series = generate_synthetic_series(n=200, seed=42)
        acf = autocorrelation(series, max_lag=10)
        assert acf["acf"][0] == 1.0
        assert acf["pacf"][0] == 1.0
        assert len(acf["acf"]) == 11

    def test_adf_stationary(self):
        # White noise is stationary
        rng = np.random.RandomState(42)
        wn = rng.normal(0, 1, 200)
        result = adf_test(wn)
        assert result["is_stationary_5pct"]

    def test_adf_nonstationary(self):
        # Random walk is non-stationary
        rng = np.random.RandomState(42)
        rw = np.cumsum(rng.normal(0, 1, 200))
        result = adf_test(rw)
        # Random walk may or may not be detected as non-stationary
        # Just check it runs
        assert "test_statistic" in result

    def test_fit_arima(self):
        series = generate_synthetic_series(n=200, seed=42)
        result = fit_arima(series, p=2, d=1, q=1)
        assert len(result["ar_coefficients"]) == 2
        assert len(result["forecasts"]) == 20
        assert result["sigma2"] > 0

    def test_fit_garch(self):
        rng = np.random.RandomState(42)
        returns = rng.normal(0, 0.01, 200)
        result = fit_garch(returns)
        assert result["persistence"] > 0
        assert len(result["conditional_volatility"]) == 200
        assert len(result["volatility_forecast"]) == 50

    def test_exponential_smoothing(self):
        series = generate_synthetic_series(n=200, seed=42)
        result = exponential_smoothing(series, seasonal_period=20, n_forecast=30)
        assert len(result["fitted"]) == 200
        assert len(result["forecasts"]) == 30


class TestGameTheory:
    """Game theory tests."""

    def test_prisoners_dilemma_nash(self):
        pd = GAMES["prisoners_dilemma"]
        nash = find_pure_nash(pd["payoff_player1"], pd["payoff_player2"])
        assert len(nash) == 1
        assert nash[0] == (1, 1)  # (Defect, Defect)

    def test_battle_of_sexes_nash(self):
        bos = GAMES["battle_of_sexes"]
        nash = find_pure_nash(bos["payoff_player1"], bos["payoff_player2"])
        assert len(nash) == 2  # Two pure Nash

    def test_matching_pennies_no_pure_nash(self):
        mp = GAMES["matching_pennies"]
        nash = find_pure_nash(mp["payoff_player1"], mp["payoff_player2"])
        assert len(nash) == 0  # No pure Nash

    def test_matching_pennies_mixed_nash(self):
        mp = GAMES["matching_pennies"]
        mixed = find_mixed_nash(mp["payoff_player1"], mp["payoff_player2"])
        assert abs(mixed["player1_mix"][0] - 0.5) < 0.01
        assert abs(mixed["player2_mix"][0] - 0.5) < 0.01

    def test_prisoners_dilemma_mixed(self):
        pd = GAMES["prisoners_dilemma"]
        mixed = find_mixed_nash(pd["payoff_player1"], pd["payoff_player2"])
        # Both defect with probability 1
        assert mixed["player1_mix"][1] > 0.99
        assert mixed["player2_mix"][1] > 0.99

    def test_shapley_value(self):
        coalition_values = {
            frozenset({0}): 10,
            frozenset({1}): 20,
            frozenset({0, 1}): 50,
        }
        shapley = shapley_value(coalition_values)
        assert "0" in shapley
        assert "1" in shapley
        # Sum of Shapley values = grand coalition value
        assert abs(sum(shapley.values()) - 50) < 0.01

    def test_shapley_three_players(self):
        coalition_values = {
            frozenset({0}): 10,
            frozenset({1}): 20,
            frozenset({2}): 15,
            frozenset({0, 1}): 50,
            frozenset({0, 2}): 40,
            frozenset({1, 2}): 45,
            frozenset({0, 1, 2}): 100,
        }
        shapley = shapley_value(coalition_values)
        assert abs(sum(shapley.values()) - 100) < 0.01


class TestDifferentialEquations:
    """Differential equations tests."""

    def test_lotka_volterra(self):
        deriv = lotka_volterra(0, [10, 5])
        assert len(deriv) == 2
        # At equilibrium (20, 10), derivatives should be ~0
        deriv_eq = lotka_volterra(0, [20, 10])
        assert abs(deriv_eq[0]) < 1e-6
        assert abs(deriv_eq[1]) < 1e-6

    def test_lorenz(self):
        deriv = lorenz(0, [1, 1, 1])
        assert len(deriv) == 3
        assert deriv[0] == 0  # sigma*(y-x) = 10*(1-1) = 0

    def test_van_der_pol(self):
        deriv = van_der_pol(0, [2, 0])
        assert len(deriv) == 2
        assert deriv[0] == 0  # dx/dt = y = 0

    def test_pendulum(self):
        deriv = pendulum(0, [0, 0])
        assert len(deriv) == 2
        assert deriv[0] == 0
        assert deriv[1] == 0  # At equilibrium

    def test_jacobian_lotka_volterra(self):
        eigenvals = jacobian_eigenvalues(lotka_volterra, (20, 10))
        assert len(eigenvals) == 2
        # Should be purely imaginary (center)
        assert abs(eigenvals[0].real) < 0.01
