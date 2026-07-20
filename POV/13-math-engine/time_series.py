"""
Time Series Analysis Module — ARIMA, SARIMA, Holt-Winters, Decomposition, Forecasting.

All computations use NumPy/SciPy/statsmodels — LLM NEVER does math.
Integrates with math_engine.py for shared utilities.

Usage:
    from time_series import TimeSeriesAnalyzer
    tsa = TimeSeriesAnalyzer()
    result = tsa.fit_arima(data, order=(2,1,1))
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
from scipy import stats, optimize

try:
    import statsmodels.api as sm
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    from statsmodels.tsa.seasonal import seasonal_decompose
    from statsmodels.tsa.stattools import adfuller, kpss, acf, pacf
    from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class TSResult:
    """Structured result from time series operations."""
    success: bool
    result: Any = None
    error: str = ""
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Time Series Analyzer
# ---------------------------------------------------------------------------

class TimeSeriesAnalyzer:
    """Time series analysis: ARIMA, SARIMA, Holt-Winters, decomposition, forecasting."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if not STATSMODELS_AVAILABLE:
            warnings.warn("statsmodels not available — ARIMA/SARIMA will use fallback implementations.")

    # ------------------------------------------------------------------
    # Data generation
    # ------------------------------------------------------------------

    @staticmethod
    def generate_synthetic_series(
        n: int = 500,
        trend: float = 0.02,
        seasonality_amplitude: float = 5.0,
        seasonality_period: int = 50,
        noise_std: float = 2.0,
        ar_coeffs: Optional[list[float]] = None,
        seed: int = 42,
    ) -> np.ndarray:
        """Generate synthetic time series: trend + seasonality + AR + noise."""
        rng = np.random.RandomState(seed)
        t = np.arange(n)
        trend_component = trend * t
        seasonal = seasonality_amplitude * np.sin(2 * np.pi * t / seasonality_period)
        if ar_coeffs is None:
            ar_coeffs = [0.7, -0.2]
        ar = np.zeros(n)
        noise = rng.normal(0, noise_std, n)
        for i in range(len(ar_coeffs), n):
            ar_val = noise[i]
            for j, c in enumerate(ar_coeffs):
                ar_val += c * ar[i - 1 - j]
            ar[i] = ar_val
        return trend_component + seasonal + ar

    # ------------------------------------------------------------------
    # Decomposition
    # ------------------------------------------------------------------

    def decompose(self, series: np.ndarray, period: int = 50,
                  model: str = "additive") -> TSResult:
        """Decompose time series into trend, seasonal, and residual components.

        Uses statsmodels seasonal_decompose when available, otherwise classical MA.
        """
        try:
            if STATSMODELS_AVAILABLE:
                decomp = seasonal_decompose(series, model=model, period=period, extrapolate_trend="freq")
                return TSResult(
                    success=True,
                    result={
                        "trend": decomp.trend.tolist(),
                        "seasonal": decomp.seasonal.tolist(),
                        "residual": decomp.resid.tolist(),
                    },
                    metadata={"period": period, "model": model, "method": "statsmodels"},
                )
            else:
                # Classical decomposition via moving average
                n = len(series)
                ma_window = period
                trend = np.convolve(series, np.ones(ma_window) / ma_window, mode="same")
                detrended = series - trend
                seasonal = np.zeros(n)
                for i in range(period):
                    indices = np.arange(i, n, period)
                    if len(indices) > 0:
                        seasonal[indices] = np.mean(detrended[indices])
                residual = series - trend - seasonal
                return TSResult(
                    success=True,
                    result={
                        "trend": trend.tolist(),
                        "seasonal": seasonal.tolist(),
                        "residual": residual.tolist(),
                    },
                    metadata={"period": period, "model": model, "method": "classical_ma"},
                )
        except Exception as e:
            return TSResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # ACF / PACF
    # ------------------------------------------------------------------

    def autocorrelation(self, series: np.ndarray, max_lag: int = 40) -> TSResult:
        """Compute ACF and PACF for a time series."""
        try:
            n = len(series)
            if STATSMODELS_AVAILABLE:
                acf_vals = acf(series, nlags=max_lag, fft=True)
                pacf_vals = pacf(series, nlags=max_lag, method="ywm")
            else:
                # Manual ACF
                mean = np.mean(series)
                var = np.var(series)
                acf_vals = np.zeros(max_lag + 1)
                acf_vals[0] = 1.0
                for lag in range(1, max_lag + 1):
                    acf_vals[lag] = np.sum(
                        (series[lag:] - mean) * (series[:-lag] - mean)
                    ) / ((n - lag) * var)
                # Manual PACF via Durbin-Levinson
                pacf_vals = np.zeros(max_lag + 1)
                pacf_vals[0] = 1.0
                for k in range(1, max_lag + 1):
                    r = acf_vals[1:k + 1]
                    R = np.zeros((k, k))
                    for i in range(k):
                        for j in range(k):
                            R[i, j] = acf_vals[abs(i - j)]
                    try:
                        phi = np.linalg.solve(R, r)
                        pacf_vals[k] = phi[-1]
                    except np.linalg.LinAlgError:
                        pacf_vals[k] = 0.0

            return TSResult(
                success=True,
                result={
                    "lags": list(range(max_lag + 1)),
                    "acf": acf_vals.tolist(),
                    "pacf": pacf_vals.tolist(),
                },
                metadata={"max_lag": max_lag, "n": n},
            )
        except Exception as e:
            return TSResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Stationarity tests
    # ------------------------------------------------------------------

    def stationarity_test(self, series: np.ndarray) -> TSResult:
        """Run ADF and KPSS tests for stationarity."""
        try:
            if STATSMODELS_AVAILABLE:
                adf_stat, adf_pvalue, adf_lags, adf_nobs, adf_crit, *_ = adfuller(
                    series, autolag="AIC"
                )
                kpss_stat, kpss_pvalue, kpss_lags, kpss_crit = kpss(series, nlags="auto")
            else:
                # Simplified ADF
                n = len(series)
                diff = np.diff(series)
                lagged = series[:-1]
                X = np.column_stack([np.ones(len(lagged)), lagged])
                beta = np.linalg.lstsq(X, diff, rcond=None)[0]
                residuals = diff - X @ beta
                mse = np.sum(residuals ** 2) / (len(residuals) - 2)
                XtX_inv = np.linalg.inv(X.T @ X)
                se_beta1 = np.sqrt(mse * XtX_inv[1, 1])
                adf_stat = beta[1] / se_beta1
                adf_pvalue = None
                adf_crit = {"1%": -3.43, "5%": -2.86, "10%": -2.57}
                kpss_stat = None
                kpss_pvalue = None
                kpss_crit = {}

            return TSResult(
                success=True,
                result={
                    "adf_statistic": float(adf_stat),
                    "adf_pvalue": float(adf_pvalue) if adf_pvalue is not None else None,
                    "adf_critical_values": {k: float(v) for k, v in adf_crit.items()} if adf_crit else {},
                    "adf_stationary_5pct": bool(adf_pvalue is not None and adf_pvalue < 0.05) if adf_pvalue is not None else None,
                    "kpss_statistic": float(kpss_stat) if kpss_stat is not None else None,
                    "kpss_pvalue": float(kpss_pvalue) if kpss_pvalue is not None else None,
                    "kpss_critical_values": {k: float(v) for k, v in kpss_crit.items()} if kpss_crit else {},
                },
            )
        except Exception as e:
            return TSResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # ARIMA / SARIMA
    # ------------------------------------------------------------------

    def fit_arima(self, series: np.ndarray, order: tuple = (2, 1, 1),
                  forecast_horizon: int = 20) -> TSResult:
        """Fit ARIMA(p,d,q) model and produce forecasts with confidence intervals.

        Uses statsmodels ARIMA when available, otherwise OLS fallback.
        """
        p, d, q = order
        try:
            if STATSMODELS_AVAILABLE:
                model = ARIMA(series, order=(p, d, q))
                fitted = model.fit()
                forecast = fitted.forecast(steps=forecast_horizon)
                forecast_ci = fitted.get_forecast(steps=forecast_horizon).conf_int()
                return TSResult(
                    success=True,
                    result={
                        "ar_coefficients": fitted.arparams.tolist() if hasattr(fitted, 'arparams') else [],
                        "ma_coefficients": fitted.maparams.tolist() if hasattr(fitted, 'maparams') else [],
                        "sigma2": float(fitted.sigma2) if hasattr(fitted, 'sigma2') else None,
                        "aic": float(fitted.aic),
                        "bic": float(fitted.bic),
                        "forecasts": forecast.tolist(),
                        "forecast_lower": forecast_ci[:, 0].tolist(),
                        "forecast_upper": forecast_ci[:, 1].tolist(),
                        "residuals": fitted.resid.tolist(),
                    },
                    metadata={"order": order, "forecast_horizon": forecast_horizon, "method": "statsmodels"},
                )
            else:
                # OLS fallback
                if d > 0:
                    diff_series = np.diff(series, n=d)
                else:
                    diff_series = series.copy()
                n = len(diff_series)
                max_lag = max(p, q)
                y = diff_series[max_lag:]
                X = np.zeros((len(y), p + q))
                for i in range(len(y)):
                    idx = max_lag + i
                    for j in range(p):
                        X[i, j] = diff_series[idx - 1 - j]
                X_ar = X[:, :p]
                beta_ar = np.linalg.lstsq(X_ar, y, rcond=None)[0]
                residuals = y - X_ar @ beta_ar
                for i in range(len(y)):
                    for j in range(q):
                        if i > j:
                            X[i, p + j] = residuals[i - 1 - j]
                beta = np.linalg.lstsq(X, y, rcond=None)[0]
                fitted_vals = X @ beta
                residuals_final = y - fitted_vals
                sigma2 = float(np.var(residuals_final))
                aic = float(n * np.log(sigma2) + 2 * (p + q))

                # Forecast
                forecasts = np.zeros(forecast_horizon)
                last_values = diff_series[-max_lag:].tolist()
                last_residuals = residuals_final[-q:].tolist() if q > 0 else []
                for h in range(forecast_horizon):
                    pred = 0.0
                    for j in range(p):
                        if len(last_values) > j:
                            pred += beta[j] * last_values[-(j + 1)]
                    for j in range(q):
                        if len(last_residuals) > j:
                            pred += beta[p + j] * last_residuals[-(j + 1)]
                    forecasts[h] = pred
                    last_values.append(pred)
                    last_residuals.append(0.0)

                # Undifference
                if d > 0:
                    last_original = series[-d:].tolist()
                    for h in range(forecast_horizon):
                        undiff = forecasts[h]
                        for dd in range(d):
                            undiff += last_original[-(dd + 1)]
                        forecasts[h] = undiff
                        last_original.append(forecasts[h])

                forecast_std = np.sqrt(sigma2) * np.sqrt(np.arange(1, forecast_horizon + 1))
                return TSResult(
                    success=True,
                    result={
                        "ar_coefficients": beta[:p].tolist(),
                        "ma_coefficients": beta[p:p + q].tolist() if q > 0 else [],
                        "sigma2": sigma2,
                        "aic": aic,
                        "bic": float(n * np.log(sigma2) + np.log(n) * (p + q)),
                        "forecasts": forecasts.tolist(),
                        "forecast_lower": (forecasts - 1.96 * forecast_std).tolist(),
                        "forecast_upper": (forecasts + 1.96 * forecast_std).tolist(),
                        "residuals": residuals_final.tolist(),
                    },
                    metadata={"order": order, "forecast_horizon": forecast_horizon, "method": "ols_fallback"},
                )
        except Exception as e:
            return TSResult(success=False, error=str(e))

    def fit_sarima(self, series: np.ndarray, order: tuple = (1, 1, 1),
                   seasonal_order: tuple = (1, 1, 1, 12),
                   forecast_horizon: int = 24) -> TSResult:
        """Fit SARIMA(p,d,q)(P,D,Q,s) model with seasonal component."""
        try:
            if not STATSMODELS_AVAILABLE:
                return TSResult(success=False, error="statsmodels required for SARIMA")
            model = SARIMAX(series, order=order, seasonal_order=seasonal_order,
                           enforce_stationarity=False, enforce_invertibility=False)
            fitted = model.fit(disp=False, maxiter=200)
            forecast = fitted.forecast(steps=forecast_horizon)
            forecast_ci = fitted.get_forecast(steps=forecast_horizon).conf_int()
            return TSResult(
                success=True,
                result={
                    "aic": float(fitted.aic),
                    "bic": float(fitted.bic),
                    "forecasts": forecast.tolist(),
                    "forecast_lower": forecast_ci[:, 0].tolist(),
                    "forecast_upper": forecast_ci[:, 1].tolist(),
                    "residuals": fitted.resid.tolist(),
                    "params": {k: float(v) for k, v in fitted.params.to_dict().items()},
                },
                metadata={"order": order, "seasonal_order": seasonal_order,
                         "forecast_horizon": forecast_horizon, "method": "statsmodels"},
            )
        except Exception as e:
            return TSResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Holt-Winters Exponential Smoothing
    # ------------------------------------------------------------------

    def holt_winters(self, series: np.ndarray, seasonal_period: int = 12,
                     alpha: float = 0.3, beta: float = 0.1, gamma: float = 0.1,
                     n_forecast: int = 24, damped: bool = False,
                     phi: float = 0.98) -> TSResult:
        """Holt-Winters triple exponential smoothing (additive seasonality).

        Implements the full multiplicative update equations from scratch.
        """
        try:
            n = len(series)
            # Initialize level, trend, seasonal
            level = np.mean(series[:seasonal_period])
            trend = (np.mean(series[seasonal_period:2 * seasonal_period]) -
                     np.mean(series[:seasonal_period])) / seasonal_period
            seasonal = np.array([series[i] - level for i in range(seasonal_period)])

            fitted = np.zeros(n)
            level_hist = np.zeros(n)
            trend_hist = np.zeros(n)

            for t in range(n):
                s_idx = t % seasonal_period
                old_level = level
                if t >= seasonal_period:
                    level = alpha * (series[t] - seasonal[s_idx]) + (1 - alpha) * (level + trend)
                    trend = beta * (level - old_level) + (1 - beta) * trend
                    seasonal[s_idx] = gamma * (series[t] - level) + (1 - gamma) * seasonal[s_idx]
                fitted[t] = level + trend + seasonal[s_idx]
                level_hist[t] = level
                trend_hist[t] = trend

            # Forecast
            forecasts = np.zeros(n_forecast)
            fc_level = level
            fc_trend = trend
            for h in range(n_forecast):
                if damped:
                    damp_factor = sum(phi ** k for k in range(1, h + 2))
                    forecasts[h] = fc_level + damp_factor * fc_trend + seasonal[(n + h) % seasonal_period]
                else:
                    forecasts[h] = fc_level + (h + 1) * fc_trend + seasonal[(n + h) % seasonal_period]

            # Confidence intervals based on in-sample residuals
            in_sample_error = series - fitted
            residual_std = np.std(in_sample_error)
            forecast_std = residual_std * np.sqrt(1 + np.arange(1, n_forecast + 1) / n)

            return TSResult(
                success=True,
                result={
                    "fitted": fitted.tolist(),
                    "forecasts": forecasts.tolist(),
                    "forecast_lower": (forecasts - 1.96 * forecast_std).tolist(),
                    "forecast_upper": (forecasts + 1.96 * forecast_std).tolist(),
                    "final_level": float(level),
                    "final_trend": float(trend),
                    "seasonal_factors": seasonal.tolist(),
                    "residual_std": float(residual_std),
                },
                metadata={
                    "seasonal_period": seasonal_period, "alpha": alpha,
                    "beta": beta, "gamma": gamma, "n_forecast": n_forecast,
                    "damped": damped, "method": "from_scratch",
                },
            )
        except Exception as e:
            return TSResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Forecasting with confidence intervals
    # ------------------------------------------------------------------

    def forecast_ensemble(self, series: np.ndarray, methods: Optional[list[str]] = None,
                          forecast_horizon: int = 24) -> TSResult:
        """Ensemble forecast combining ARIMA + Holt-Winters."""
        try:
            if methods is None:
                methods = ["arima", "holt_winters"]

            forecasts_dict = {}
            if "arima" in methods:
                arima_r = self.fit_arima(series, order=(2, 1, 1), forecast_horizon=forecast_horizon)
                if arima_r.success:
                    forecasts_dict["arima"] = arima_r.result["forecasts"]

            if "holt_winters" in methods:
                hw_r = self.holt_winters(series, seasonal_period=12, n_forecast=forecast_horizon)
                if hw_r.success:
                    forecasts_dict["holt_winters"] = hw_r.result["forecasts"]

            if not forecasts_dict:
                return TSResult(success=False, error="No successful forecasts")

            # Ensemble: simple average
            all_forecasts = np.array(list(forecasts_dict.values()))
            ensemble = np.mean(all_forecasts, axis=0)
            ensemble_std = np.std(all_forecasts, axis=0)

            return TSResult(
                success=True,
                result={
                    "ensemble_forecast": ensemble.tolist(),
                    "ensemble_lower": (ensemble - 1.96 * ensemble_std).tolist(),
                    "ensemble_upper": (ensemble + 1.96 * ensemble_std).tolist(),
                    "individual_forecasts": {k: v for k, v in forecasts_dict.items()},
                },
                metadata={"methods": list(forecasts_dict.keys()), "forecast_horizon": forecast_horizon},
            )
        except Exception as e:
            return TSResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Utility: differencing, detrending
    # ------------------------------------------------------------------

    @staticmethod
    def difference(series: np.ndarray, order: int = 1) -> np.ndarray:
        """Apply differencing of given order."""
        result = series.copy()
        for _ in range(order):
            result = np.diff(result)
        return result

    @staticmethod
    def detrend(series: np.ndarray, method: str = "linear") -> np.ndarray:
        """Remove trend from series."""
        n = len(series)
        t = np.arange(n)
        if method == "linear":
            X = np.column_stack([np.ones(n), t])
            beta = np.linalg.lstsq(X, series, rcond=None)[0]
            trend = X @ beta
            return series - trend
        elif method == "moving_average":
            window = max(n // 10, 5)
            trend = np.convolve(series, np.ones(window) / window, mode="same")
            return series - trend
        else:
            raise ValueError(f"Unknown detrend method: {method}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    tsa = TimeSeriesAnalyzer()

    if len(sys.argv) < 2:
        print("Usage: python time_series.py <operation> [args...]")
        print("Operations: generate, decompose, acf, stationarity, arima, sarima, holt_winters, ensemble")
        sys.exit(1)

    op = sys.argv[1]
    series = tsa.generate_synthetic_series(n=200)

    if op == "generate":
        r = {"series": series.tolist()}
    elif op == "decompose":
        r = tsa.decompose(series, period=50)
    elif op == "acf":
        r = tsa.autocorrelation(series, max_lag=20)
    elif op == "stationarity":
        r = tsa.stationarity_test(series)
    elif op == "arima":
        r = tsa.fit_arima(series, order=(2, 1, 1))
    elif op == "sarima":
        r = tsa.fit_sarima(series, order=(1, 1, 1), seasonal_order=(1, 0, 0, 12))
    elif op == "holt_winters":
        r = tsa.holt_winters(series, seasonal_period=12)
    elif op == "ensemble":
        r = tsa.forecast_ensemble(series)
    else:
        r = TSResult(success=False, error=f"Unknown operation: {op}")

    if isinstance(r, TSResult):
        print(json.dumps({"success": r.success, "result": r.result, "error": r.error, "metadata": r.metadata}, indent=2, default=str))
    else:
        print(json.dumps(r, indent=2, default=str))
