"""
Time Series Analysis Demo — ARIMA, SARIMA, Holt-Winters, Decomposition, Forecasting.

Generates comprehensive plots to output/ directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from time_series import TimeSeriesAnalyzer

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def main():
    print("=" * 60)
    print("TIME SERIES ANALYSIS DEMO")
    print("=" * 60)

    tsa = TimeSeriesAnalyzer()

    # ------------------------------------------------------------------
    # 1. Generate synthetic data
    # ------------------------------------------------------------------
    print("\n--- 1. Generating synthetic time series ---")
    n = 500
    series = tsa.generate_synthetic_series(
        n=n, trend=0.02, seasonality_amplitude=5.0,
        seasonality_period=50, noise_std=2.0, seed=42,
    )
    print(f"  Length: {n}, Mean: {np.mean(series):.2f}, Std: {np.std(series):.2f}")

    # Also generate a monthly sales-like series
    n_monthly = 120
    t_monthly = np.arange(n_monthly)
    sales_trend = 100 + 0.5 * t_monthly
    sales_seasonal = 20 * np.sin(2 * np.pi * t_monthly / 12)
    sales_noise = np.random.RandomState(123).normal(0, 8, n_monthly)
    sales_series = sales_trend + sales_seasonal + sales_noise

    # ------------------------------------------------------------------
    # 2. Decomposition
    # ------------------------------------------------------------------
    print("\n--- 2. Time Series Decomposition ---")
    decomp = tsa.decompose(series, period=50)
    if decomp.success:
        d = decomp.result
        print(f"  Trend range: [{np.nanmin(d['trend']):.2f}, {np.nanmax(d['trend']):.2f}]")
        print(f"  Seasonal std: {np.nanstd(d['seasonal']):.2f}")
        print(f"  Residual std: {np.nanstd(d['residual']):.2f}")
    else:
        print(f"  ERROR: {decomp.error}")

    # ------------------------------------------------------------------
    # 3. ACF / PACF
    # ------------------------------------------------------------------
    print("\n--- 3. Autocorrelation Analysis ---")
    acf_result = tsa.autocorrelation(series, max_lag=40)
    if acf_result.success:
        print(f"  ACF(1) = {acf_result.result['acf'][1]:.3f}")
        print(f"  PACF(1) = {acf_result.result['pacf'][1]:.3f}")
        print(f"  ACF(10) = {acf_result.result['acf'][10]:.3f}")

    # ------------------------------------------------------------------
    # 4. Stationarity tests
    # ------------------------------------------------------------------
    print("\n--- 4. Stationarity Tests ---")
    stat_test = tsa.stationarity_test(series)
    if stat_test.success:
        print(f"  ADF statistic: {stat_test.result['adf_statistic']:.3f}")
        print(f"  ADF p-value: {stat_test.result['adf_pvalue']}")
        print(f"  Stationary at 5%: {stat_test.result['adf_stationary_5pct']}")

    # ------------------------------------------------------------------
    # 5. ARIMA
    # ------------------------------------------------------------------
    print("\n--- 5. ARIMA(2,1,1) Model ---")
    arima = tsa.fit_arima(series, order=(2, 1, 1), forecast_horizon=50)
    if arima.success:
        print(f"  AIC: {arima.result['aic']:.1f}")
        print(f"  BIC: {arima.result['bic']:.1f}")
        print(f"  Forecast (last 5): {[f'{f:.1f}' for f in arima.result['forecasts'][-5:]]}")

    # ------------------------------------------------------------------
    # 6. SARIMA (monthly sales)
    # ------------------------------------------------------------------
    print("\n--- 6. SARIMA(1,1,1)(1,0,0,12) on Monthly Sales ---")
    sarima = tsa.fit_sarima(sales_series, order=(1, 1, 1),
                            seasonal_order=(1, 0, 0, 12), forecast_horizon=24)
    if sarima.success:
        print(f"  AIC: {sarima.result['aic']:.1f}")
        print(f"  Forecast (last 5): {[f'{f:.1f}' for f in sarima.result['forecasts'][-5:]]}")
    else:
        print(f"  SARIMA note: {sarima.error}")

    # ------------------------------------------------------------------
    # 7. Holt-Winters
    # ------------------------------------------------------------------
    print("\n--- 7. Holt-Winters Exponential Smoothing ---")
    hw = tsa.holt_winters(series, seasonal_period=50, alpha=0.3, beta=0.1,
                          gamma=0.1, n_forecast=100)
    if hw.success:
        print(f"  Final level: {hw.result['final_level']:.2f}")
        print(f"  Final trend: {hw.result['final_trend']:.2f}")
        print(f"  Forecast (last 5): {[f'{f:.1f}' for f in hw.result['forecasts'][-5:]]}")

    # Also Holt-Winters on sales data
    hw_sales = tsa.holt_winters(sales_series, seasonal_period=12, alpha=0.4,
                                beta=0.1, gamma=0.2, n_forecast=24)
    if hw_sales.success:
        print(f"  Sales HW final level: {hw_sales.result['final_level']:.2f}")

    # ------------------------------------------------------------------
    # 8. Ensemble forecast
    # ------------------------------------------------------------------
    print("\n--- 8. Ensemble Forecast ---")
    ensemble = tsa.forecast_ensemble(series, forecast_horizon=50)
    if ensemble.success:
        print(f"  Methods: {list(ensemble.result['individual_forecasts'].keys())}")
        print(f"  Ensemble (last 5): {[f'{f:.1f}' for f in ensemble.result['ensemble_forecast'][-5:]]}")

    # ==================================================================
    # PLOTS
    # ==================================================================

    # --- Plot 1: Decomposition (4 panels) ---
    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
    t = np.arange(n)

    axes[0].plot(t, series, linewidth=1, color="black")
    axes[0].set_ylabel("Original")
    axes[0].set_title("Time Series Decomposition", fontsize=14, fontweight="bold")
    axes[0].grid(True, alpha=0.3)

    if decomp.success:
        axes[1].plot(t, decomp.result["trend"], linewidth=1.5, color="red")
        axes[1].set_ylabel("Trend")
        axes[1].grid(True, alpha=0.3)

        axes[2].plot(t, decomp.result["seasonal"], linewidth=1, color="green")
        axes[2].set_ylabel("Seasonal")
        axes[2].grid(True, alpha=0.3)

        axes[3].plot(t, decomp.result["residual"], linewidth=0.5, color="orange")
        axes[3].set_ylabel("Residual")
        axes[3].set_xlabel("Time")
        axes[3].grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "time_series_decomposition.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n✅ Chart saved: {path}")

    # --- Plot 2: ACF + PACF ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    if acf_result.success:
        lags = acf_result.result["lags"]
        conf = 1.96 / np.sqrt(n)

        ax1.stem(lags, acf_result.result["acf"], linefmt="blue", markerfmt="bo", basefmt="gray")
        ax1.axhline(y=0, color="gray", linewidth=0.5)
        ax1.axhline(y=conf, color="red", linestyle="--", linewidth=1, alpha=0.7)
        ax1.axhline(y=-conf, color="red", linestyle="--", linewidth=1, alpha=0.7)
        ax1.set_title("Autocorrelation Function (ACF)", fontweight="bold")
        ax1.set_xlabel("Lag")
        ax1.grid(True, alpha=0.3)

        ax2.stem(lags, acf_result.result["pacf"], linefmt="green", markerfmt="go", basefmt="gray")
        ax2.axhline(y=0, color="gray", linewidth=0.5)
        ax2.axhline(y=conf, color="red", linestyle="--", linewidth=1, alpha=0.7)
        ax2.axhline(y=-conf, color="red", linestyle="--", linewidth=1, alpha=0.7)
        ax2.set_title("Partial Autocorrelation Function (PACF)", fontweight="bold")
        ax2.set_xlabel("Lag")
        ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "time_series_acf_pacf.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path}")

    # --- Plot 3: ARIMA Forecast with Confidence Intervals ---
    fig, ax = plt.subplots(figsize=(14, 5))

    train_end = n - 50
    ax.plot(range(n), series, linewidth=1, alpha=0.5, label="Historical", color="black")
    if arima.success:
        fc_x = range(train_end, train_end + len(arima.result["forecasts"]))
        ax.plot(fc_x, arima.result["forecasts"], linewidth=2, label="ARIMA Forecast", color="red")
        ax.fill_between(fc_x, arima.result["forecast_lower"], arima.result["forecast_upper"],
                        alpha=0.2, color="red", label="95% CI")
    ax.axvline(x=train_end, color="gray", linestyle="--", alpha=0.5, label="Forecast start")
    ax.set_title("ARIMA(2,1,1) Forecast with 95% Confidence Intervals", fontweight="bold")
    ax.set_xlabel("Time")
    ax.set_ylabel("Value")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "time_series_arima_forecast.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path}")

    # --- Plot 4: SARIMA Monthly Sales Forecast ---
    fig, ax = plt.subplots(figsize=(14, 5))

    ax.plot(range(n_monthly), sales_series, linewidth=1, alpha=0.5, label="Historical Sales", color="black")
    if sarima.success:
        fc_x = range(n_monthly, n_monthly + len(sarima.result["forecasts"]))
        ax.plot(fc_x, sarima.result["forecasts"], linewidth=2, label="SARIMA Forecast", color="blue")
        ax.fill_between(fc_x, sarima.result["forecast_lower"], sarima.result["forecast_upper"],
                        alpha=0.2, color="blue", label="95% CI")
    ax.axvline(x=n_monthly, color="gray", linestyle="--", alpha=0.5)
    ax.set_title("SARIMA(1,1,1)(1,0,0,12) Monthly Sales Forecast", fontweight="bold")
    ax.set_xlabel("Month")
    ax.set_ylabel("Sales")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "time_series_sarima_sales.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path}")

    # --- Plot 5: Holt-Winters Forecast ---
    fig, ax = plt.subplots(figsize=(14, 5))

    ax.plot(range(n), series, linewidth=1, alpha=0.5, label="Historical", color="black")
    if hw.success:
        ax.plot(range(n), hw.result["fitted"], linewidth=1, label="Holt-Winters Fitted", color="blue", alpha=0.7)
        fc_x = range(n, n + len(hw.result["forecasts"]))
        ax.plot(fc_x, hw.result["forecasts"], linewidth=2, label="Forecast", color="red")
        ax.fill_between(fc_x, hw.result["forecast_lower"], hw.result["forecast_upper"],
                        alpha=0.2, color="red", label="95% CI")
    ax.axvline(x=n, color="gray", linestyle="--", alpha=0.5)
    ax.set_title("Holt-Winters Exponential Smoothing Forecast", fontweight="bold")
    ax.set_xlabel("Time")
    ax.set_ylabel("Value")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "time_series_holt_winters_forecast.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path}")

    # --- Plot 6: Holt-Winters on Sales Data ---
    fig, ax = plt.subplots(figsize=(14, 5))

    ax.plot(range(n_monthly), sales_series, linewidth=1, alpha=0.5, label="Historical Sales", color="black")
    if hw_sales.success:
        ax.plot(range(n_monthly), hw_sales.result["fitted"], linewidth=1, label="HW Fitted", color="green", alpha=0.7)
        fc_x = range(n_monthly, n_monthly + len(hw_sales.result["forecasts"]))
        ax.plot(fc_x, hw_sales.result["forecasts"], linewidth=2, label="HW Forecast", color="darkgreen")
        ax.fill_between(fc_x, hw_sales.result["forecast_lower"], hw_sales.result["forecast_upper"],
                        alpha=0.2, color="green", label="95% CI")
    ax.axvline(x=n_monthly, color="gray", linestyle="--", alpha=0.5)
    ax.set_title("Holt-Winters: Monthly Sales Forecast (seasonal_period=12)", fontweight="bold")
    ax.set_xlabel("Month")
    ax.set_ylabel("Sales")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "time_series_sales_hw.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path}")

    # --- Plot 7: Ensemble Forecast ---
    fig, ax = plt.subplots(figsize=(14, 5))

    ax.plot(range(n), series, linewidth=1, alpha=0.5, label="Historical", color="black")
    if ensemble.success:
        fc_x = range(n, n + len(ensemble.result["ensemble_forecast"]))
        ax.plot(fc_x, ensemble.result["ensemble_forecast"], linewidth=2.5, label="Ensemble Forecast", color="purple")
        ax.fill_between(fc_x, ensemble.result["ensemble_lower"], ensemble.result["ensemble_upper"],
                        alpha=0.2, color="purple", label="95% CI")
        # Plot individual forecasts
        colors = {"arima": "red", "holt_winters": "blue"}
        for method, fc in ensemble.result["individual_forecasts"].items():
            ax.plot(fc_x, fc, linewidth=1, linestyle="--", alpha=0.6,
                    color=colors.get(method, "gray"), label=f"{method}")
    ax.axvline(x=n, color="gray", linestyle="--", alpha=0.5)
    ax.set_title("Ensemble Forecast (ARIMA + Holt-Winters)", fontweight="bold")
    ax.set_xlabel("Time")
    ax.set_ylabel("Value")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "time_series_ensemble.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path}")

    # --- Plot 8: Summary dashboard ---
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)

    # Decomposition
    ax = fig.add_subplot(gs[0, 0])
    ax.plot(t, series, linewidth=0.8, alpha=0.7, color="black")
    if decomp.success:
        ax.plot(t, decomp.result["trend"], linewidth=1.5, color="red")
    ax.set_title("Decomposition", fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # ACF
    ax = fig.add_subplot(gs[0, 1])
    if acf_result.success:
        ax.stem(acf_result.result["lags"][:30], acf_result.result["acf"][:30],
                linefmt="blue", markerfmt="bo", basefmt="gray")
    ax.axhline(y=0, color="gray", linewidth=0.5)
    ax.set_title("ACF", fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # PACF
    ax = fig.add_subplot(gs[0, 2])
    if acf_result.success:
        ax.stem(acf_result.result["lags"][:30], acf_result.result["pacf"][:30],
                linefmt="green", markerfmt="go", basefmt="gray")
    ax.axhline(y=0, color="gray", linewidth=0.5)
    ax.set_title("PACF", fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # ARIMA
    ax = fig.add_subplot(gs[1, 0])
    ax.plot(range(n), series, linewidth=0.8, alpha=0.5, color="black")
    if arima.success:
        fc_x = range(train_end, train_end + len(arima.result["forecasts"]))
        ax.plot(fc_x, arima.result["forecasts"], linewidth=1.5, color="red")
    ax.axvline(x=train_end, color="gray", linestyle="--", alpha=0.5)
    ax.set_title("ARIMA Forecast", fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # SARIMA Sales
    ax = fig.add_subplot(gs[1, 1])
    ax.plot(range(n_monthly), sales_series, linewidth=0.8, alpha=0.5, color="black")
    if sarima.success:
        fc_x = range(n_monthly, n_monthly + len(sarima.result["forecasts"]))
        ax.plot(fc_x, sarima.result["forecasts"], linewidth=1.5, color="blue")
    ax.axvline(x=n_monthly, color="gray", linestyle="--", alpha=0.5)
    ax.set_title("SARIMA Sales Forecast", fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # Holt-Winters
    ax = fig.add_subplot(gs[1, 2])
    ax.plot(range(n), series, linewidth=0.8, alpha=0.5, color="black")
    if hw.success:
        ax.plot(range(n), hw.result["fitted"], linewidth=0.8, color="blue", alpha=0.5)
        fc_x = range(n, n + len(hw.result["forecasts"]))
        ax.plot(fc_x, hw.result["forecasts"], linewidth=1.5, color="red")
    ax.axvline(x=n, color="gray", linestyle="--", alpha=0.5)
    ax.set_title("Holt-Winters Forecast", fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # Ensemble
    ax = fig.add_subplot(gs[2, 0])
    ax.plot(range(n), series, linewidth=0.8, alpha=0.5, color="black")
    if ensemble.success:
        fc_x = range(n, n + len(ensemble.result["ensemble_forecast"]))
        ax.plot(fc_x, ensemble.result["ensemble_forecast"], linewidth=1.5, color="purple")
    ax.axvline(x=n, color="gray", linestyle="--", alpha=0.5)
    ax.set_title("Ensemble Forecast", fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # Sales HW
    ax = fig.add_subplot(gs[2, 1])
    ax.plot(range(n_monthly), sales_series, linewidth=0.8, alpha=0.5, color="black")
    if hw_sales.success:
        fc_x = range(n_monthly, n_monthly + len(hw_sales.result["forecasts"]))
        ax.plot(fc_x, hw_sales.result["forecasts"], linewidth=1.5, color="darkgreen")
    ax.axvline(x=n_monthly, color="gray", linestyle="--", alpha=0.5)
    ax.set_title("Sales HW Forecast", fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # Residuals
    ax = fig.add_subplot(gs[2, 2])
    if arima.success:
        ax.plot(arima.result["residuals"], linewidth=0.5, color="orange")
    ax.axhline(y=0, color="gray", linewidth=0.5)
    ax.set_title("ARIMA Residuals", fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.3)

    fig.suptitle("Time Series Analysis Dashboard", fontsize=16, fontweight="bold", y=1.01)
    plt.tight_layout()
    path = OUTPUT_DIR / "time_series_dashboard.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path}")

    print("\n" + "=" * 60)
    print("TIME SERIES DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
