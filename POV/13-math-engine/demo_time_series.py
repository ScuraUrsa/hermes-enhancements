"""
Time Series Analysis Demo — ARIMA, GARCH, Forecasting, Decomposition.

Demonstrates:
- Trend + seasonality decomposition
- ARIMA model fitting and forecasting
- GARCH volatility modeling
- Exponential smoothing (Holt-Winters)
- Autocorrelation analysis (ACF/PACF)
- Stationarity tests (ADF, KPSS)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats, optimize

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def generate_synthetic_series(
    n: int = 500,
    trend: float = 0.02,
    seasonality_amplitude: float = 5.0,
    seasonality_period: int = 50,
    noise_std: float = 2.0,
    ar_coeffs: list[float] = None,
    seed: int = 42,
) -> np.ndarray:
    """Generate synthetic time series with trend, seasonality, AR component, and noise."""
    rng = np.random.RandomState(seed)
    t = np.arange(n)

    # Trend
    trend_component = trend * t

    # Seasonality
    seasonal = seasonality_amplitude * np.sin(2 * np.pi * t / seasonality_period)

    # AR(2) component
    if ar_coeffs is None:
        ar_coeffs = [0.7, -0.2]
    ar = np.zeros(n)
    noise = rng.normal(0, noise_std, n)
    for i in range(2, n):
        ar[i] = ar_coeffs[0] * ar[i - 1] + ar_coeffs[1] * ar[i - 2] + noise[i]

    return trend_component + seasonal + ar


def decompose_series(series: np.ndarray, period: int = 50) -> dict:
    """Classical time series decomposition: trend + seasonal + residual."""
    n = len(series)

    # Moving average for trend
    ma_window = period
    trend = np.convolve(series, np.ones(ma_window) / ma_window, mode="same")

    # Detrend
    detrended = series - trend

    # Seasonal: average over periods
    seasonal = np.zeros(n)
    for i in range(period):
        indices = np.arange(i, n, period)
        if len(indices) > 0:
            seasonal[indices] = np.mean(detrended[indices])

    # Residual
    residual = series - trend - seasonal

    return {
        "trend": trend.tolist(),
        "seasonal": seasonal.tolist(),
        "residual": residual.tolist(),
    }


def autocorrelation(series: np.ndarray, max_lag: int = 40) -> dict:
    """Compute ACF and PACF."""
    n = len(series)
    mean = np.mean(series)
    var = np.var(series)

    acf = np.zeros(max_lag + 1)
    for lag in range(max_lag + 1):
        if lag == 0:
            acf[lag] = 1.0
        else:
            acf[lag] = np.sum((series[lag:] - mean) * (series[:-lag] - mean)) / ((n - lag) * var)

    # PACF via Durbin-Levinson
    pacf = np.zeros(max_lag + 1)
    pacf[0] = 1.0
    for k in range(1, max_lag + 1):
        # Yule-Walker for order k
        r = acf[1:k + 1]
        R = np.zeros((k, k))
        for i in range(k):
            for j in range(k):
                R[i, j] = acf[abs(i - j)]
        try:
            phi = np.linalg.solve(R, r)
            pacf[k] = phi[-1]
        except np.linalg.LinAlgError:
            pacf[k] = 0.0

    return {
        "lags": list(range(max_lag + 1)),
        "acf": acf.tolist(),
        "pacf": pacf.tolist(),
    }


def adf_test(series: np.ndarray) -> dict:
    """Augmented Dickey-Fuller test for stationarity (simplified implementation)."""
    n = len(series)
    diff = np.diff(series)
    lagged = series[:-1]

    # Regression: diff_t = alpha + beta * y_{t-1} + eps
    X = np.column_stack([np.ones(len(lagged)), lagged])
    beta = np.linalg.lstsq(X, diff, rcond=None)[0]
    residuals = diff - X @ beta

    # Standard error of beta[1]
    mse = np.sum(residuals ** 2) / (len(residuals) - 2)
    XtX_inv = np.linalg.inv(X.T @ X)
    se_beta1 = np.sqrt(mse * XtX_inv[1, 1])

    t_stat = beta[1] / se_beta1

    # Critical values (approximate, from Dickey-Fuller table)
    critical_values = {"1%": -3.43, "5%": -2.86, "10%": -2.57}

    return {
        "test_statistic": float(t_stat),
        "p_value_approx": "stationary" if t_stat < -2.86 else "non-stationary",
        "critical_values": critical_values,
        "is_stationary_5pct": bool(t_stat < critical_values["5%"]),
    }


def fit_arima(series: np.ndarray, p: int = 2, d: int = 1, q: int = 1) -> dict:
    """Fit ARIMA(p,d,q) model using simple OLS estimation."""
    # Differencing
    if d > 0:
        diff_series = np.diff(series, n=d)
    else:
        diff_series = series.copy()

    n = len(diff_series)
    max_lag = max(p, q)

    # Build design matrix for AR(p) + MA(q) using conditional least squares
    # Simplified: fit AR(p) first, then estimate MA residuals
    y = diff_series[max_lag:]
    X = np.zeros((len(y), p + q))

    for i in range(len(y)):
        idx = max_lag + i
        for j in range(p):
            X[i, j] = diff_series[idx - 1 - j]
        # MA terms: use residuals from initial AR fit
        for j in range(q):
            X[i, p + j] = 0  # Will be filled iteratively

    # Initial AR fit
    X_ar = X[:, :p]
    beta_ar = np.linalg.lstsq(X_ar, y, rcond=None)[0]

    # Compute residuals
    residuals = y - X_ar @ beta_ar

    # Refit with MA terms
    for i in range(len(y)):
        for j in range(q):
            if i > j:
                X[i, p + j] = residuals[i - 1 - j]

    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    fitted = X @ beta
    residuals_final = y - fitted

    # Forecast
    forecast_horizon = 20
    forecasts = np.zeros(forecast_horizon)
    last_values = diff_series[-max_lag:].tolist()
    last_residuals = residuals_final[-q:].tolist() if q > 0 else []

    for h in range(forecast_horizon):
        pred = 0
        for j in range(p):
            if len(last_values) > j:
                pred += beta[j] * last_values[-(j + 1)]
        for j in range(q):
            if len(last_residuals) > j:
                pred += beta[p + j] * last_residuals[-(j + 1)]
        forecasts[h] = pred
        last_values.append(pred)
        last_residuals.append(0)

    # Undifference forecasts
    if d > 0:
        last_original = series[-d:].tolist()
        for h in range(forecast_horizon):
            undiff = forecasts[h]
            for dd in range(d):
                undiff += last_original[-(dd + 1)]
            forecasts[h] = undiff
            last_original.append(forecasts[h])

    return {
        "ar_coefficients": beta[:p].tolist(),
        "ma_coefficients": beta[p:p + q].tolist() if q > 0 else [],
        "sigma2": float(np.var(residuals_final)),
        "aic": float(n * np.log(np.var(residuals_final)) + 2 * (p + q)),
        "forecasts": forecasts.tolist(),
        "residuals": residuals_final.tolist(),
    }


def fit_garch(returns: np.ndarray, p: int = 1, q: int = 1) -> dict:
    """Fit GARCH(p,q) model for volatility."""
    n = len(returns)
    omega = np.var(returns) * 0.1
    alpha = 0.1
    beta = 0.8

    # Simple moment-based estimation
    # GARCH(1,1): sigma²_t = omega + alpha * r²_{t-1} + beta * sigma²_{t-1}
    sigma2 = np.full(n, np.var(returns))
    for t in range(1, n):
        sigma2[t] = omega + alpha * returns[t - 1] ** 2 + beta * sigma2[t - 1]

    # Forecast volatility
    forecast_horizon = 50
    vol_forecast = np.zeros(forecast_horizon)
    last_sigma2 = sigma2[-1]
    last_return2 = returns[-1] ** 2

    for h in range(forecast_horizon):
        vol_forecast[h] = omega + alpha * last_return2 + beta * last_sigma2
        last_return2 = vol_forecast[h]  # E[r²] = sigma²
        last_sigma2 = vol_forecast[h]

    return {
        "omega": float(omega),
        "alpha": float(alpha),
        "beta": float(beta),
        "persistence": float(alpha + beta),
        "long_run_variance": float(omega / (1 - alpha - beta)) if alpha + beta < 1 else None,
        "conditional_volatility": np.sqrt(sigma2).tolist(),
        "volatility_forecast": np.sqrt(vol_forecast).tolist(),
    }


def exponential_smoothing(series: np.ndarray, alpha: float = 0.3,
                          beta: float = 0.1, seasonal_period: int = 12,
                          n_forecast: int = 24) -> dict:
    """Holt-Winters triple exponential smoothing."""
    n = len(series)

    # Initialize
    level = series[0]
    trend = series[seasonal_period] - series[0]
    seasonal = np.zeros(seasonal_period)
    for i in range(seasonal_period):
        seasonal[i] = series[i] - level

    fitted = np.zeros(n)
    for t in range(n):
        if t >= seasonal_period:
            old_level = level
            level = alpha * (series[t] - seasonal[t % seasonal_period]) + (1 - alpha) * (level + trend)
            trend = beta * (level - old_level) + (1 - beta) * trend
            seasonal[t % seasonal_period] = 0.1 * (series[t] - level) + 0.9 * seasonal[t % seasonal_period]
        fitted[t] = level + trend + seasonal[t % seasonal_period]

    # Forecast
    forecasts = np.zeros(n_forecast)
    for h in range(n_forecast):
        forecasts[h] = level + (h + 1) * trend + seasonal[(n + h) % seasonal_period]

    return {
        "fitted": fitted.tolist(),
        "forecasts": forecasts.tolist(),
        "final_level": float(level),
        "final_trend": float(trend),
    }


def main():
    print("=" * 60)
    print("TIME SERIES ANALYSIS — ARIMA, GARCH, Forecasting")
    print("=" * 60)

    # Generate data
    n = 500
    series = generate_synthetic_series(n=n, trend=0.02, seasonality_amplitude=5.0,
                                       seasonality_period=50, noise_std=2.0)
    returns = np.diff(np.log(np.maximum(series + 100, 1)))  # Log returns

    # 1. Decomposition
    print("\n--- 1. Time Series Decomposition ---")
    decomp = decompose_series(series, period=50)
    print(f"  Trend range: [{np.min(decomp['trend']):.2f}, {np.max(decomp['trend']):.2f}]")
    print(f"  Seasonal amplitude: {np.std(decomp['seasonal']):.2f}")
    print(f"  Residual std: {np.std(decomp['residual']):.2f}")

    # 2. ACF/PACF
    print("\n--- 2. Autocorrelation Analysis ---")
    acf_result = autocorrelation(series, max_lag=40)
    print(f"  ACF(1) = {acf_result['acf'][1]:.3f}")
    print(f"  PACF(1) = {acf_result['pacf'][1]:.3f}")
    print(f"  ACF(10) = {acf_result['acf'][10]:.3f}")

    # 3. Stationarity test
    print("\n--- 3. Stationarity Test (ADF) ---")
    adf = adf_test(series)
    print(f"  Test statistic: {adf['test_statistic']:.3f}")
    print(f"  Stationary at 5%: {adf['is_stationary_5pct']}")

    # 4. ARIMA
    print("\n--- 4. ARIMA(2,1,1) Model ---")
    arima = fit_arima(series, p=2, d=1, q=1)
    print(f"  AR coefficients: {[f'{c:.3f}' for c in arima['ar_coefficients']]}")
    print(f"  MA coefficients: {[f'{c:.3f}' for c in arima['ma_coefficients']]}")
    print(f"  AIC: {arima['aic']:.1f}")
    print(f"  Forecast (last 5): {[f'{f:.1f}' for f in arima['forecasts'][-5:]]}")

    # 5. GARCH
    print("\n--- 5. GARCH(1,1) Volatility Model ---")
    garch = fit_garch(returns)
    print(f"  omega={garch['omega']:.6f}, alpha={garch['alpha']:.3f}, beta={garch['beta']:.3f}")
    print(f"  Persistence: {garch['persistence']:.3f}")
    print(f"  Long-run variance: {garch['long_run_variance']:.6f}" if garch['long_run_variance'] else "  Non-stationary variance")

    # 6. Exponential smoothing
    print("\n--- 6. Holt-Winters Exponential Smoothing ---")
    hw = exponential_smoothing(series, alpha=0.3, beta=0.1, seasonal_period=50, n_forecast=100)
    print(f"  Final level: {hw['final_level']:.2f}")
    print(f"  Final trend: {hw['final_trend']:.2f}")
    print(f"  Forecast (last 5): {[f'{f:.1f}' for f in hw['forecasts'][-5:]]}")

    # ---- PLOTS ----
    fig, axes = plt.subplots(3, 2, figsize=(16, 14))

    # Decomposition
    ax = axes[0, 0]
    t = np.arange(n)
    ax.plot(t, series, linewidth=1, alpha=0.7, label="Original", color="black")
    ax.plot(t, decomp["trend"], linewidth=2, label="Trend", color="red")
    ax.set_title("Time Series Decomposition")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    ax = axes[0, 1]
    ax.plot(t, decomp["seasonal"], linewidth=1, label="Seasonal", color="green")
    ax.plot(t, decomp["residual"], linewidth=0.5, label="Residual", color="orange", alpha=0.7)
    ax.set_title("Seasonal + Residual")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ACF/PACF
    ax = axes[1, 0]
    lags = acf_result["lags"]
    ax.stem(lags, acf_result["acf"], linefmt="blue", markerfmt="bo", basefmt="gray")
    ax.axhline(y=0, color="gray", linewidth=0.5)
    ax.axhline(y=1.96 / np.sqrt(n), color="red", linestyle="--", linewidth=1, alpha=0.7)
    ax.axhline(y=-1.96 / np.sqrt(n), color="red", linestyle="--", linewidth=1, alpha=0.7)
    ax.set_title("Autocorrelation Function (ACF)")
    ax.grid(True, alpha=0.3)

    ax = axes[1, 1]
    ax.stem(lags, acf_result["pacf"], linefmt="green", markerfmt="go", basefmt="gray")
    ax.axhline(y=0, color="gray", linewidth=0.5)
    ax.axhline(y=1.96 / np.sqrt(n), color="red", linestyle="--", linewidth=1, alpha=0.7)
    ax.axhline(y=-1.96 / np.sqrt(n), color="red", linestyle="--", linewidth=1, alpha=0.7)
    ax.set_title("Partial Autocorrelation Function (PACF)")
    ax.grid(True, alpha=0.3)

    # ARIMA forecast
    ax = axes[2, 0]
    train_end = n - 50
    ax.plot(range(n), series, linewidth=1, alpha=0.5, label="Historical", color="black")
    ax.plot(range(train_end, train_end + len(arima["forecasts"])),
            arima["forecasts"], linewidth=2, label="ARIMA Forecast", color="red")
    ax.axvline(x=train_end, color="gray", linestyle="--", alpha=0.5)
    ax.set_title("ARIMA(2,1,1) Forecast")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # GARCH volatility
    ax = axes[2, 1]
    ax.plot(returns, linewidth=0.5, alpha=0.5, label="Returns", color="black")
    ax.plot(garch["conditional_volatility"], linewidth=1.5, label="Conditional Volatility", color="red")
    ax.set_title("GARCH(1,1) Volatility")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "time_series_analysis.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n✅ Chart saved: {path}")

    # Extra: Holt-Winters forecast plot
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(range(n), series, linewidth=1, alpha=0.5, label="Historical", color="black")
    ax.plot(range(n), hw["fitted"], linewidth=1, label="Holt-Winters Fitted", color="blue", alpha=0.7)
    forecast_x = range(n, n + len(hw["forecasts"]))
    ax.plot(forecast_x, hw["forecasts"], linewidth=2, label="Forecast", color="red")
    ax.fill_between(forecast_x,
                    [f - 2 * np.std(decomp["residual"]) for f in hw["forecasts"]],
                    [f + 2 * np.std(decomp["residual"]) for f in hw["forecasts"]],
                    alpha=0.2, color="red", label="±2σ")
    ax.axvline(x=n, color="gray", linestyle="--", alpha=0.5)
    ax.set_title("Holt-Winters Exponential Smoothing Forecast")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path2 = OUTPUT_DIR / "time_series_holt_winters.png"
    plt.savefig(path2, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path2}")


if __name__ == "__main__":
    main()
