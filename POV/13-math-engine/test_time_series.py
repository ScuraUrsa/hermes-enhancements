"""
Tests for Time Series Analysis Module.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from time_series import TimeSeriesAnalyzer, TSResult


@pytest.fixture
def tsa():
    return TimeSeriesAnalyzer(output_dir="/tmp/ts_test")


@pytest.fixture
def sample_series(tsa):
    return tsa.generate_synthetic_series(n=200, trend=0.02, seasonality_amplitude=5.0,
                                         seasonality_period=50, noise_std=2.0, seed=42)


@pytest.fixture
def simple_series():
    """Simple linear trend + noise for basic tests."""
    rng = np.random.RandomState(42)
    t = np.arange(100)
    return 0.5 * t + rng.normal(0, 1, 100)


class TestDataGeneration:
    """Tests for synthetic data generation."""

    def test_generate_returns_correct_length(self, tsa):
        series = tsa.generate_synthetic_series(n=300)
        assert len(series) == 300

    def test_generate_is_reproducible(self, tsa):
        s1 = tsa.generate_synthetic_series(n=100, seed=42)
        s2 = tsa.generate_synthetic_series(n=100, seed=42)
        np.testing.assert_array_equal(s1, s2)

    def test_generate_different_seeds_differ(self, tsa):
        s1 = tsa.generate_synthetic_series(n=100, seed=1)
        s2 = tsa.generate_synthetic_series(n=100, seed=2)
        assert not np.allclose(s1, s2)

    def test_generate_has_finite_values(self, tsa):
        series = tsa.generate_synthetic_series(n=200)
        assert np.all(np.isfinite(series))


class TestDecomposition:
    """Tests for time series decomposition."""

    def test_decompose_success(self, tsa, sample_series):
        result = tsa.decompose(sample_series, period=50)
        assert result.success
        assert "trend" in result.result
        assert "seasonal" in result.result
        assert "residual" in result.result

    def test_decompose_correct_lengths(self, tsa, sample_series):
        result = tsa.decompose(sample_series, period=50)
        n = len(sample_series)
        assert len(result.result["trend"]) == n
        assert len(result.result["seasonal"]) == n
        assert len(result.result["residual"]) == n

    def test_decompose_residual_plus_components_equals_original(self, tsa, sample_series):
        result = tsa.decompose(sample_series, period=50)
        trend = np.array(result.result["trend"])
        seasonal = np.array(result.result["seasonal"])
        residual = np.array(result.result["residual"])
        # Sum should approximate original (ignoring NaN at edges from MA)
        valid = ~np.isnan(trend) & ~np.isnan(seasonal) & ~np.isnan(residual)
        reconstructed = trend[valid] + seasonal[valid] + residual[valid]
        original = sample_series[valid]
        np.testing.assert_allclose(reconstructed, original, rtol=1e-5, atol=1e-5)

    def test_decompose_different_periods(self, tsa, sample_series):
        r1 = tsa.decompose(sample_series, period=20)
        r2 = tsa.decompose(sample_series, period=50)
        assert r1.success and r2.success
        # Different periods should give different seasonal components
        s1 = np.nan_to_num(np.array(r1.result["seasonal"]))
        s2 = np.nan_to_num(np.array(r2.result["seasonal"]))
        assert not np.allclose(s1, s2)


class TestAutocorrelation:
    """Tests for ACF/PACF computation."""

    def test_acf_success(self, tsa, sample_series):
        result = tsa.autocorrelation(sample_series, max_lag=20)
        assert result.success
        assert "acf" in result.result
        assert "pacf" in result.result

    def test_acf_lag_zero_is_one(self, tsa, sample_series):
        result = tsa.autocorrelation(sample_series, max_lag=20)
        assert abs(result.result["acf"][0] - 1.0) < 1e-10
        assert abs(result.result["pacf"][0] - 1.0) < 1e-10

    def test_acf_values_between_minus_one_and_one(self, tsa, sample_series):
        result = tsa.autocorrelation(sample_series, max_lag=20)
        acf_vals = result.result["acf"][1:]  # Skip lag 0
        assert all(-1.0 <= v <= 1.0 for v in acf_vals)

    def test_acf_correct_length(self, tsa, sample_series):
        result = tsa.autocorrelation(sample_series, max_lag=15)
        assert len(result.result["lags"]) == 16
        assert len(result.result["acf"]) == 16
        assert len(result.result["pacf"]) == 16

    def test_white_noise_acf_near_zero(self, tsa):
        rng = np.random.RandomState(42)
        white_noise = rng.randn(500)
        result = tsa.autocorrelation(white_noise, max_lag=10)
        # For white noise, ACF at lag > 0 should be small
        for lag in range(1, 11):
            assert abs(result.result["acf"][lag]) < 0.3


class TestStationarity:
    """Tests for stationarity tests."""

    def test_stationarity_test_success(self, tsa, sample_series):
        result = tsa.stationarity_test(sample_series)
        assert result.success
        assert "adf_statistic" in result.result

    def test_stationarity_on_random_walk(self, tsa):
        rng = np.random.RandomState(42)
        rw = np.cumsum(rng.randn(200))
        result = tsa.stationarity_test(rw)
        assert result.success
        # Random walk should be non-stationary
        if result.result["adf_stationary_5pct"] is not None:
            assert not result.result["adf_stationary_5pct"]

    def test_stationarity_on_stationary_series(self, tsa):
        rng = np.random.RandomState(42)
        stationary = rng.randn(200)
        result = tsa.stationarity_test(stationary)
        assert result.success
        if result.result["adf_stationary_5pct"] is not None:
            assert result.result["adf_stationary_5pct"]


class TestARIMA:
    """Tests for ARIMA model fitting."""

    def test_fit_arima_success(self, tsa, sample_series):
        result = tsa.fit_arima(sample_series, order=(2, 1, 1), forecast_horizon=20)
        assert result.success
        assert "forecasts" in result.result
        assert "aic" in result.result

    def test_fit_arima_forecast_length(self, tsa, sample_series):
        result = tsa.fit_arima(sample_series, order=(2, 1, 1), forecast_horizon=30)
        assert len(result.result["forecasts"]) == 30
        assert len(result.result["forecast_lower"]) == 30
        assert len(result.result["forecast_upper"]) == 30

    def test_fit_arima_confidence_intervals_contain_forecast(self, tsa, sample_series):
        result = tsa.fit_arima(sample_series, order=(2, 1, 1), forecast_horizon=20)
        for fc, lo, hi in zip(result.result["forecasts"],
                              result.result["forecast_lower"],
                              result.result["forecast_upper"]):
            assert lo <= fc <= hi

    def test_fit_arima_different_orders(self, tsa, sample_series):
        r1 = tsa.fit_arima(sample_series, order=(1, 0, 0), forecast_horizon=10)
        r2 = tsa.fit_arima(sample_series, order=(2, 1, 1), forecast_horizon=10)
        assert r1.success and r2.success
        # Different orders should give different AIC
        assert r1.result["aic"] != r2.result["aic"]

    def test_fit_arima_residuals_length(self, tsa, sample_series):
        result = tsa.fit_arima(sample_series, order=(2, 1, 1))
        assert len(result.result["residuals"]) > 0


class TestSARIMA:
    """Tests for SARIMA model fitting."""

    def test_fit_sarima_success(self, tsa, sample_series):
        result = tsa.fit_sarima(sample_series, order=(1, 1, 1),
                                seasonal_order=(1, 0, 0, 12), forecast_horizon=12)
        assert result.success
        assert "forecasts" in result.result

    def test_fit_sarima_forecast_length(self, tsa, sample_series):
        result = tsa.fit_sarima(sample_series, order=(1, 1, 1),
                                seasonal_order=(1, 0, 0, 12), forecast_horizon=24)
        assert len(result.result["forecasts"]) == 24

    def test_fit_sarima_has_confidence_intervals(self, tsa, sample_series):
        result = tsa.fit_sarima(sample_series, order=(1, 1, 1),
                                seasonal_order=(1, 0, 0, 12), forecast_horizon=10)
        assert "forecast_lower" in result.result
        assert "forecast_upper" in result.result


class TestHoltWinters:
    """Tests for Holt-Winters exponential smoothing."""

    def test_holt_winters_success(self, tsa, sample_series):
        result = tsa.holt_winters(sample_series, seasonal_period=50, n_forecast=30)
        assert result.success
        assert "forecasts" in result.result
        assert "fitted" in result.result

    def test_holt_winters_forecast_length(self, tsa, sample_series):
        result = tsa.holt_winters(sample_series, seasonal_period=50, n_forecast=40)
        assert len(result.result["forecasts"]) == 40

    def test_holt_winters_fitted_length(self, tsa, sample_series):
        result = tsa.holt_winters(sample_series, seasonal_period=50)
        assert len(result.result["fitted"]) == len(sample_series)

    def test_holt_winters_confidence_intervals(self, tsa, sample_series):
        result = tsa.holt_winters(sample_series, seasonal_period=50, n_forecast=20)
        for fc, lo, hi in zip(result.result["forecasts"],
                              result.result["forecast_lower"],
                              result.result["forecast_upper"]):
            assert lo <= fc <= hi

    def test_holt_winters_damped(self, tsa, sample_series):
        r1 = tsa.holt_winters(sample_series, seasonal_period=50, n_forecast=20, damped=False)
        r2 = tsa.holt_winters(sample_series, seasonal_period=50, n_forecast=20, damped=True, phi=0.9)
        assert r1.success and r2.success
        # Damped should give different forecasts
        assert not np.allclose(r1.result["forecasts"], r2.result["forecasts"])

    def test_holt_winters_seasonal_factors_length(self, tsa, sample_series):
        result = tsa.holt_winters(sample_series, seasonal_period=12)
        assert len(result.result["seasonal_factors"]) == 12


class TestEnsemble:
    """Tests for ensemble forecasting."""

    def test_forecast_ensemble_success(self, tsa, sample_series):
        result = tsa.forecast_ensemble(sample_series, forecast_horizon=20)
        assert result.success
        assert "ensemble_forecast" in result.result
        assert "individual_forecasts" in result.result

    def test_forecast_ensemble_length(self, tsa, sample_series):
        result = tsa.forecast_ensemble(sample_series, forecast_horizon=30)
        assert len(result.result["ensemble_forecast"]) == 30

    def test_forecast_ensemble_confidence(self, tsa, sample_series):
        result = tsa.forecast_ensemble(sample_series, forecast_horizon=20)
        for fc, lo, hi in zip(result.result["ensemble_forecast"],
                              result.result["ensemble_lower"],
                              result.result["ensemble_upper"]):
            assert lo <= fc <= hi

    def test_forecast_ensemble_specific_methods(self, tsa, sample_series):
        result = tsa.forecast_ensemble(sample_series, methods=["arima"], forecast_horizon=10)
        assert result.success
        assert "arima" in result.result["individual_forecasts"]


class TestUtility:
    """Tests for utility functions."""

    def test_difference_order_1(self, tsa, simple_series):
        diff = tsa.difference(simple_series, order=1)
        assert len(diff) == len(simple_series) - 1

    def test_difference_order_2(self, tsa, simple_series):
        diff = tsa.difference(simple_series, order=2)
        assert len(diff) == len(simple_series) - 2

    def test_detrend_linear(self, tsa, simple_series):
        detrended = tsa.detrend(simple_series, method="linear")
        assert len(detrended) == len(simple_series)
        # Detrended series should have mean near zero
        assert abs(np.mean(detrended)) < 1e-5

    def test_detrend_moving_average(self, tsa, simple_series):
        detrended = tsa.detrend(simple_series, method="moving_average")
        assert len(detrended) == len(simple_series)


class TestTSResult:
    """Tests for TSResult dataclass."""

    def test_success_result(self):
        r = TSResult(success=True, result={"value": 42})
        assert r.success
        assert r.result["value"] == 42

    def test_error_result(self):
        r = TSResult(success=False, error="something went wrong")
        assert not r.success
        assert r.error == "something went wrong"

    def test_metadata(self):
        r = TSResult(success=True, result={}, metadata={"key": "val"})
        assert r.metadata["key"] == "val"
