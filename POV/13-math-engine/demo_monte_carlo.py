"""
Monte Carlo Simulation Demo — Risk Analysis & Probability.

Demonstrates:
- Monte Carlo integration (π estimation)
- Value at Risk (VaR) for portfolio
- Option pricing (European call via Black-Scholes + MC)
- Project cost estimation (PERT)
- Random walk / Brownian motion
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent))
from math_engine import MathEngine

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def estimate_pi(n_points: int = 100_000) -> dict:
    """Estimate π using Monte Carlo (circle in square)."""
    rng = np.random.RandomState(42)
    x = rng.uniform(-1, 1, n_points)
    y = rng.uniform(-1, 1, n_points)
    inside = (x**2 + y**2) <= 1
    pi_est = 4 * np.sum(inside) / n_points

    # Convergence plot
    cumulative = 4 * np.cumsum(inside) / np.arange(1, n_points + 1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Scatter
    colors = np.where(inside, "#2196F3", "#FF9800")
    ax1.scatter(x[::50], y[::50], c=colors[::50], s=1, alpha=0.6)
    circle = plt.Circle((0, 0), 1, fill=False, color="white", linewidth=2)
    ax1.add_patch(circle)
    ax1.set_aspect("equal")
    ax1.set_title(f"Monte Carlo π ≈ {pi_est:.6f} (true: {np.pi:.6f})", fontsize=11)
    ax1.set_xlim(-1.1, 1.1)
    ax1.set_ylim(-1.1, 1.1)

    # Convergence
    ax2.plot(cumulative, linewidth=1, color="#2196F3")
    ax2.axhline(y=np.pi, color="red", linestyle="--", linewidth=1.5, label=f"π = {np.pi:.6f}")
    ax2.set_xlabel("Number of points")
    ax2.set_ylabel("π estimate")
    ax2.set_title("Convergence of Monte Carlo π")
    ax2.legend()
    ax2.set_xscale("log")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "monte_carlo_pi.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "pi_estimate": float(pi_est),
        "error": float(abs(pi_est - np.pi)),
        "n_points": n_points,
        "chart": str(path),
    }


def portfolio_var(
    initial_value: float = 100_000,
    annual_return: float = 0.08,
    annual_volatility: float = 0.20,
    horizon_days: int = 252,
    n_simulations: int = 10_000,
    confidence_levels: list[float] = None,
) -> dict:
    """Compute Value at Risk (VaR) and Conditional VaR for a portfolio."""
    if confidence_levels is None:
        confidence_levels = [0.95, 0.99]

    rng = np.random.RandomState(42)
    daily_return = annual_return / 252
    daily_vol = annual_volatility / np.sqrt(252)

    # Geometric Brownian Motion
    returns = rng.normal(daily_return, daily_vol, (horizon_days, n_simulations))
    price_paths = initial_value * np.exp(np.cumsum(returns, axis=0))

    final_values = price_paths[-1, :]
    returns_total = (final_values / initial_value) - 1

    var_results = {}
    for cl in confidence_levels:
        var = np.percentile(returns_total, (1 - cl) * 100)
        cvar = np.mean(returns_total[returns_total <= var])
        var_results[f"VaR_{cl:.0%}"] = {
            "return": f"{var:.2%}",
            "value": float(initial_value * var),
            "CVaR_return": f"{cvar:.2%}",
            "CVaR_value": float(initial_value * cvar),
        }

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Paths
    ax1 = axes[0]
    for i in range(min(100, n_simulations)):
        ax1.plot(price_paths[:, i], linewidth=0.5, alpha=0.3, color="#2196F3")
    ax1.plot(np.mean(price_paths, axis=1), linewidth=2, color="red", label="Mean")
    ax1.set_xlabel("Trading Days")
    ax1.set_ylabel("Portfolio Value (PLN)")
    ax1.set_title(f"Monte Carlo: {n_simulations} Price Paths")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Return distribution
    ax2 = axes[1]
    ax2.hist(returns_total * 100, bins=100, density=True, alpha=0.7, color="#4CAF50")
    for cl in confidence_levels:
        var_val = np.percentile(returns_total, (1 - cl) * 100) * 100
        ax2.axvline(x=var_val, color="red", linestyle="--", linewidth=1.5,
                    label=f"VaR {cl:.0%} = {var_val:.1f}%")
    ax2.set_xlabel("Return (%)")
    ax2.set_ylabel("Density")
    ax2.set_title("Distribution of Returns")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "monte_carlo_var.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "initial_value": initial_value,
        "mean_return": f"{np.mean(returns_total):.2%}",
        "std_return": f"{np.std(returns_total):.2%}",
        "var": var_results,
        "chart": str(path),
    }


def black_scholes_mc(
    S0: float = 100,
    K: float = 105,
    T: float = 1.0,
    r: float = 0.05,
    sigma: float = 0.20,
    n_simulations: int = 100_000,
) -> dict:
    """Price European call option using Monte Carlo + Black-Scholes analytic."""
    rng = np.random.RandomState(42)

    # MC
    Z = rng.normal(0, 1, n_simulations)
    ST = S0 * np.exp((r - 0.5 * sigma**2) * T + sigma * np.sqrt(T) * Z)
    payoff = np.maximum(ST - K, 0)
    mc_price = np.exp(-r * T) * np.mean(payoff)
    mc_std = np.exp(-r * T) * np.std(payoff) / np.sqrt(n_simulations)

    # Black-Scholes analytic
    d1 = (np.log(S0 / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    bs_price = S0 * stats.norm.cdf(d1) - K * np.exp(-r * T) * stats.norm.cdf(d2)

    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.hist(payoff, bins=100, density=True, alpha=0.7, color="#2196F3")
    ax1.axvline(x=np.mean(payoff), color="red", linestyle="--", linewidth=2,
                label=f"Mean Payoff = {np.mean(payoff):.2f}")
    ax1.set_xlabel("Payoff at Expiry")
    ax1.set_ylabel("Density")
    ax1.set_title("Distribution of Option Payoffs")
    ax1.legend()

    # Convergence
    cumulative = np.exp(-r * T) * np.cumsum(payoff) / np.arange(1, n_simulations + 1)
    ax2.plot(cumulative, linewidth=1, color="#2196F3", label="MC Estimate")
    ax2.axhline(y=bs_price, color="red", linestyle="--", linewidth=1.5,
                label=f"BS Analytic = {bs_price:.4f}")
    ax2.fill_between(
        range(n_simulations),
        cumulative - 1.96 * mc_std * np.sqrt(n_simulations) / np.sqrt(np.arange(1, n_simulations + 1)),
        cumulative + 1.96 * mc_std * np.sqrt(n_simulations) / np.sqrt(np.arange(1, n_simulations + 1)),
        alpha=0.2, color="blue",
    )
    ax2.set_xlabel("Number of Simulations")
    ax2.set_ylabel("Option Price")
    ax2.set_title("Convergence to Black-Scholes Price")
    ax2.legend()
    ax2.set_xscale("log")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "monte_carlo_option.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "mc_price": float(mc_price),
        "mc_std_error": float(mc_std),
        "mc_ci_95": [float(mc_price - 1.96 * mc_std), float(mc_price + 1.96 * mc_std)],
        "bs_price": float(bs_price),
        "error": float(abs(mc_price - bs_price)),
        "chart": str(path),
    }


def project_cost_pert(
    tasks: list[dict] = None,
    n_simulations: int = 10_000,
) -> dict:
    """PERT (Program Evaluation and Review Technique) — project cost/time estimation."""
    if tasks is None:
        tasks = [
            {"name": "Design", "optimistic": 5, "most_likely": 8, "pessimistic": 15},
            {"name": "Development", "optimistic": 15, "most_likely": 25, "pessimistic": 40},
            {"name": "Testing", "optimistic": 8, "most_likely": 12, "pessimistic": 20},
            {"name": "Deployment", "optimistic": 2, "most_likely": 4, "pessimistic": 8},
        ]

    rng = np.random.RandomState(42)
    total_durations = np.zeros(n_simulations)

    for task in tasks:
        # Beta-PERT: mean = (o + 4m + p) / 6, std = (p - o) / 6
        mean = (task["optimistic"] + 4 * task["most_likely"] + task["pessimistic"]) / 6
        std = (task["pessimistic"] - task["optimistic"]) / 6
        # Use beta distribution scaled to [o, p]
        alpha = ((mean - task["optimistic"]) / (task["pessimistic"] - task["optimistic"])) * 4 + 1
        beta_param = ((task["pessimistic"] - mean) / (task["pessimistic"] - task["optimistic"])) * 4 + 1
        samples = rng.beta(alpha, beta_param, n_simulations)
        samples = task["optimistic"] + samples * (task["pessimistic"] - task["optimistic"])
        total_durations += samples

    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.hist(total_durations, bins=80, density=True, alpha=0.7, color="#2196F3")
    ax1.axvline(x=np.mean(total_durations), color="red", linestyle="--", linewidth=2,
                label=f"Mean = {np.mean(total_durations):.1f} days")
    ax1.axvline(x=np.percentile(total_durations, 50), color="orange", linestyle="--", linewidth=2,
                label=f"Median (P50) = {np.percentile(total_durations, 50):.1f} days")
    ax1.axvline(x=np.percentile(total_durations, 80), color="green", linestyle="--", linewidth=2,
                label=f"P80 = {np.percentile(total_durations, 80):.1f} days")
    ax1.axvline(x=np.percentile(total_durations, 95), color="purple", linestyle="--", linewidth=2,
                label=f"P95 = {np.percentile(total_durations, 95):.1f} days")
    ax1.set_xlabel("Total Duration (days)")
    ax1.set_ylabel("Density")
    ax1.set_title("PERT: Project Duration Distribution")
    ax1.legend(fontsize=8)

    # Cumulative probability
    sorted_durations = np.sort(total_durations)
    cumulative_prob = np.arange(1, n_simulations + 1) / n_simulations
    ax2.plot(sorted_durations, cumulative_prob, linewidth=2, color="#2196F3")
    ax2.axhline(y=0.50, color="orange", linestyle="--", alpha=0.5)
    ax2.axhline(y=0.80, color="green", linestyle="--", alpha=0.5)
    ax2.axhline(y=0.95, color="purple", linestyle="--", alpha=0.5)
    ax2.set_xlabel("Duration (days)")
    ax2.set_ylabel("Cumulative Probability")
    ax2.set_title("Probability of Completing By Date")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "monte_carlo_pert.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "mean_days": float(np.mean(total_durations)),
        "std_days": float(np.std(total_durations)),
        "p50": float(np.percentile(total_durations, 50)),
        "p80": float(np.percentile(total_durations, 80)),
        "p90": float(np.percentile(total_durations, 90)),
        "p95": float(np.percentile(total_durations, 95)),
        "p99": float(np.percentile(total_durations, 99)),
        "chart": str(path),
    }


def random_walk(n_steps: int = 1000, n_paths: int = 20) -> dict:
    """Generate and visualize random walks / Brownian motion."""
    rng = np.random.RandomState(42)
    steps = rng.normal(0, 1, (n_steps, n_paths))
    paths = np.cumsum(steps, axis=0)

    fig, ax = plt.subplots(figsize=(12, 5))
    for i in range(n_paths):
        ax.plot(paths[:, i], linewidth=0.8, alpha=0.7)
    ax.set_xlabel("Step")
    ax.set_ylabel("Position")
    ax.set_title(f"Random Walks (Brownian Motion) — {n_paths} paths, {n_steps} steps")
    ax.grid(True, alpha=0.3)

    # Add expected envelope (±2σ)
    x = np.arange(n_steps)
    ax.fill_between(x, -2 * np.sqrt(x + 1), 2 * np.sqrt(x + 1), alpha=0.1, color="red",
                    label="±2σ envelope")
    ax.legend()

    plt.tight_layout()
    path = OUTPUT_DIR / "monte_carlo_random_walk.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "n_steps": n_steps,
        "n_paths": n_paths,
        "final_positions_mean": float(np.mean(paths[-1, :])),
        "final_positions_std": float(np.std(paths[-1, :])),
        "chart": str(path),
    }


def main():
    print("=" * 60)
    print("MONTE CARLO SIMULATIONS — Risk & Probability")
    print("=" * 60)

    # 1. π estimation
    print("\n--- 1. Estimating π ---")
    pi_result = estimate_pi(100_000)
    print(f"π ≈ {pi_result['pi_estimate']:.6f} (error: {pi_result['error']:.2e})")
    print(f"Chart: {pi_result['chart']}")

    # 2. Portfolio VaR
    print("\n--- 2. Portfolio Value at Risk ---")
    var_result = portfolio_var(100_000, 0.08, 0.20, 252, 10_000)
    print(f"Mean Return: {var_result['mean_return']}")
    print(f"VaR 95%: {var_result['var']['VaR_95%']['value']:,.0f} PLN ({var_result['var']['VaR_95%']['return']})")
    print(f"VaR 99%: {var_result['var']['VaR_99%']['value']:,.0f} PLN ({var_result['var']['VaR_99%']['return']})")
    print(f"Chart: {var_result['chart']}")

    # 3. Option pricing
    print("\n--- 3. European Call Option Pricing ---")
    option_result = black_scholes_mc(S0=100, K=105, T=1.0, r=0.05, sigma=0.20)
    print(f"MC Price: {option_result['mc_price']:.4f} ± {option_result['mc_std_error']:.4f}")
    print(f"BS Price: {option_result['bs_price']:.4f}")
    print(f"Error: {option_result['error']:.6f}")
    print(f"Chart: {option_result['chart']}")

    # 4. PERT
    print("\n--- 4. Project Cost Estimation (PERT) ---")
    pert_result = project_cost_pert()
    print(f"Mean: {pert_result['mean_days']:.1f} days")
    print(f"P50: {pert_result['p50']:.1f} | P80: {pert_result['p80']:.1f} | P95: {pert_result['p95']:.1f}")
    print(f"Chart: {pert_result['chart']}")

    # 5. Random walk
    print("\n--- 5. Random Walk / Brownian Motion ---")
    rw_result = random_walk(1000, 30)
    print(f"Final positions: mean={rw_result['final_positions_mean']:.2f}, std={rw_result['final_positions_std']:.2f}")
    print(f"Chart: {rw_result['chart']}")

    print(f"\n✅ All charts saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
