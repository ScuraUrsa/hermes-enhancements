"""
Optimization Demo — Minima, Maxima, Linear Programming, Curve Fitting.

Demonstrates:
- Function optimization (find global min/max)
- Linear programming (resource allocation)
- Constrained optimization
- Portfolio optimization (Markowitz efficient frontier)
- Curve fitting / parameter estimation
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import optimize, stats

sys.path.insert(0, str(Path(__file__).parent))
from math_engine import MathEngine

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def function_optimization() -> dict:
    """Find global minimum of a complex function with multiple local minima."""
    # Rastrigin function: many local minima, one global at (0,0)
    def rastrigin(x):
        return 10 * len(x) + sum(xi**2 - 10 * np.cos(2 * np.pi * xi) for xi in x)

    # Try multiple starting points
    rng = np.random.RandomState(42)
    best_result = None
    best_fun = float("inf")
    trajectories = []

    for _ in range(20):
        x0 = rng.uniform(-5, 5, 2)
        result = optimize.minimize(rastrigin, x0, method="Nelder-Mead")
        if result.fun < best_fun:
            best_fun = result.fun
            best_result = result

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Surface
    ax = axes[0]
    x = np.linspace(-5.12, 5.12, 200)
    y = np.linspace(-5.12, 5.12, 200)
    X, Y = np.meshgrid(x, y)
    Z = rastrigin([X, Y])

    contour = ax.contourf(X, Y, Z, levels=30, cmap="viridis")
    ax.plot(best_result.x[0], best_result.x[1], "r*", markersize=15, label=f"Minimum at ({best_result.x[0]:.3f}, {best_result.x[1]:.3f})")
    ax.set_xlabel("x₁")
    ax.set_ylabel("x₂")
    ax.set_title("Rastrigin Function — Global Optimization")
    ax.legend()
    plt.colorbar(contour, ax=ax, shrink=0.8)

    # 1D slice
    ax = axes[1]
    x1d = np.linspace(-5.12, 5.12, 500)
    y1d = [rastrigin([xi, 0]) for xi in x1d]
    ax.plot(x1d, y1d, linewidth=2, color="#2196F3")
    ax.axvline(x=0, color="red", linestyle="--", linewidth=1.5, label="Global min (0,0)")
    ax.set_xlabel("x")
    ax.set_ylabel("f(x, 0)")
    ax.set_title("Rastrigin: 1D Slice at y=0")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "optimization_function.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "function": "Rastrigin",
        "minimum": best_result.x.tolist(),
        "value": float(best_result.fun),
        "success": bool(best_result.success),
        "chart": str(path),
    }


def linear_programming_demo() -> dict:
    """Linear programming: optimal resource allocation.

    Problem: Factory produces products A and B.
    - Product A: profit 40 PLN/unit, uses 2h machine + 1h labor
    - Product B: profit 30 PLN/unit, uses 1h machine + 2h labor
    - Available: 100h machine, 80h labor
    - Max demand: A ≤ 40, B ≤ 50
    Maximize profit.
    """
    # Maximize 40A + 30B
    c = [-40, -30]  # Negative for maximization

    # Constraints: A_ub @ x ≤ b_ub
    A_ub = [
        [2, 1],   # 2A + B ≤ 100 (machine)
        [1, 2],   # A + 2B ≤ 80  (labor)
        [1, 0],   # A ≤ 40       (demand A)
        [0, 1],   # B ≤ 50       (demand B)
    ]
    b_ub = [100, 80, 40, 50]

    bounds = [(0, None), (0, None)]

    result = optimize.linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
    profit = -result.fun

    # Plot feasible region
    fig, ax = plt.subplots(figsize=(10, 8))

    A_vals = np.linspace(0, 50, 200)

    # Constraint lines
    B_machine = 100 - 2 * A_vals
    B_labor = (80 - A_vals) / 2
    B_demand_a = np.full_like(A_vals, 50)
    A_demand_b = np.full_like(A_vals, 40)

    ax.plot(A_vals, B_machine, label="2A + B ≤ 100 (Machine)", color="#2196F3")
    ax.plot(A_vals, B_labor, label="A + 2B ≤ 80 (Labor)", color="#FF9800")
    ax.axvline(x=40, label="A ≤ 40 (Demand)", color="#4CAF50", linestyle="--")
    ax.axhline(y=50, label="B ≤ 50 (Demand)", color="#9C27B0", linestyle="--")

    # Feasible region
    A_feasible = np.array([0, 0, 40, 40, 100/3])
    B_feasible = np.array([0, 40, 0, 50, 100/3])
    # Sort by A
    idx = np.argsort(A_feasible)
    A_feasible = A_feasible[idx]
    B_feasible = B_feasible[idx]
    # Clip to constraints
    B_feasible = np.minimum(B_feasible, 100 - 2 * A_feasible)
    B_feasible = np.minimum(B_feasible, (80 - A_feasible) / 2)
    B_feasible = np.minimum(B_feasible, 50)
    B_feasible = np.maximum(B_feasible, 0)

    ax.fill_between(A_feasible, 0, B_feasible, alpha=0.2, color="green", label="Feasible Region")

    # Optimal point
    ax.plot(result.x[0], result.x[1], "r*", markersize=15, label=f"Optimal: A={result.x[0]:.0f}, B={result.x[1]:.0f}, Profit={profit:.0f} PLN")

    # Iso-profit lines
    for p in [800, 1200, 1600, profit]:
        B_iso = (p - 40 * A_vals) / 30
        ax.plot(A_vals, B_iso, "gray", alpha=0.3, linewidth=0.5)

    ax.set_xlim(0, 55)
    ax.set_ylim(0, 55)
    ax.set_xlabel("Product A (units)")
    ax.set_ylabel("Product B (units)")
    ax.set_title("Linear Programming: Factory Production Optimization")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "optimization_linear_programming.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "optimal_A": float(result.x[0]),
        "optimal_B": float(result.x[1]),
        "max_profit": float(profit),
        "slack": {
            "machine": float(100 - (2 * result.x[0] + result.x[1])),
            "labor": float(80 - (result.x[0] + 2 * result.x[1])),
        },
        "chart": str(path),
    }


def portfolio_optimization() -> dict:
    """Markowitz efficient frontier — optimal portfolio allocation."""
    rng = np.random.RandomState(42)

    # Asset parameters (annual)
    n_assets = 5
    asset_names = ["Bonds", "S&P500", "Gold", "Real Estate", "Crypto"]
    returns = np.array([0.04, 0.10, 0.06, 0.08, 0.15])
    volatilities = np.array([0.05, 0.18, 0.15, 0.12, 0.50])

    # Correlation matrix
    corr = np.array([
        [1.00, -0.10, 0.20, 0.15, -0.05],
        [-0.10, 1.00, -0.05, 0.30, 0.20],
        [0.20, -0.05, 1.00, 0.10, 0.05],
        [0.15, 0.30, 0.10, 1.00, 0.10],
        [-0.05, 0.20, 0.05, 0.10, 1.00],
    ])

    cov = np.outer(volatilities, volatilities) * corr

    def portfolio_stats(weights):
        w = np.array(weights)
        port_return = np.dot(w, returns)
        port_vol = np.sqrt(np.dot(w.T, np.dot(cov, w)))
        return port_return, port_vol

    def min_volatility_for_target(target_return):
        """Minimize volatility for a given target return."""
        n = n_assets
        # Constraints: sum(w) = 1, return = target
        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},
            {"type": "eq", "fun": lambda w: np.dot(w, returns) - target_return},
        ]
        bounds = [(0, 1) for _ in range(n)]
        w0 = np.ones(n) / n
        result = optimize.minimize(
            lambda w: np.sqrt(np.dot(w.T, np.dot(cov, w))),
            w0, bounds=bounds, constraints=constraints, method="SLSQP",
        )
        return result

    # Generate efficient frontier
    target_returns = np.linspace(returns.min(), returns.max(), 50)
    frontier_vols = []
    frontier_weights = []

    for target in target_returns:
        result = min_volatility_for_target(target)
        if result.success:
            _, vol = portfolio_stats(result.x)
            frontier_vols.append(vol)
            frontier_weights.append(result.x)
        else:
            frontier_vols.append(None)
            frontier_weights.append(None)

    # Filter valid points
    valid = [(r, v, w) for r, v, w in zip(target_returns, frontier_vols, frontier_weights) if v is not None]
    target_returns = [v[0] for v in valid]
    frontier_vols = [v[1] for v in valid]
    frontier_weights = [v[2] for v in valid]

    # Random portfolios for comparison
    n_random = 5000
    random_weights = rng.dirichlet(np.ones(n_assets), n_random)
    random_returns = np.dot(random_weights, returns)
    random_vols = np.array([np.sqrt(np.dot(w.T, np.dot(cov, w))) for w in random_weights])
    random_sharpe = random_returns / random_vols

    # Max Sharpe ratio
    best_idx = np.argmax(random_sharpe)
    best_w = random_weights[best_idx]

    # Plot
    fig, ax = plt.subplots(figsize=(12, 7))

    scatter = ax.scatter(random_vols * 100, random_returns * 100, c=random_sharpe,
                         cmap="viridis", alpha=0.3, s=5)
    ax.plot(np.array(frontier_vols) * 100, np.array(target_returns) * 100,
            "r-", linewidth=2.5, label="Efficient Frontier")
    ax.scatter(volatilities * 100, returns * 100, c="blue", s=100, zorder=5,
               marker="D", edgecolors="black", linewidth=1)
    ax.scatter(np.sqrt(np.dot(best_w.T, np.dot(cov, best_w))) * 100,
               np.dot(best_w, returns) * 100,
               c="red", s=150, zorder=6, marker="*", edgecolors="black", linewidth=1,
               label="Max Sharpe Ratio")

    for i, name in enumerate(asset_names):
        ax.annotate(name, (volatilities[i] * 100, returns[i] * 100),
                    textcoords="offset points", xytext=(5, 5), fontsize=9)

    ax.set_xlabel("Volatility (%)", fontsize=11)
    ax.set_ylabel("Expected Return (%)", fontsize=11)
    ax.set_title("Markowitz Efficient Frontier — Optimal Portfolio Allocation", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label="Sharpe Ratio", shrink=0.8)

    plt.tight_layout()
    path = OUTPUT_DIR / "optimization_portfolio.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "max_sharpe_weights": {name: float(w) for name, w in zip(asset_names, best_w)},
        "max_sharpe_return": float(np.dot(best_w, returns)),
        "max_sharpe_volatility": float(np.sqrt(np.dot(best_w.T, np.dot(cov, best_w)))),
        "max_sharpe_ratio": float(random_sharpe[best_idx]),
        "chart": str(path),
    }


def curve_fitting_demo() -> dict:
    """Non-linear curve fitting: fit exponential decay to data."""
    rng = np.random.RandomState(42)

    # True model: y = a * exp(-b * x) + c
    a_true, b_true, c_true = 10.0, 0.5, 2.0

    x_data = np.linspace(0, 10, 30)
    y_true = a_true * np.exp(-b_true * x_data) + c_true
    y_data = y_true + rng.normal(0, 0.5, len(x_data))

    def model(x, a, b, c):
        return a * np.exp(-b * x) + c

    # Fit
    popt, pcov = optimize.curve_fit(model, x_data, y_data, p0=[8, 0.3, 1])
    perr = np.sqrt(np.diag(pcov))

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    x_fine = np.linspace(0, 10, 200)
    ax.scatter(x_data, y_data, alpha=0.7, s=30, label="Data", color="#2196F3")
    ax.plot(x_fine, model(x_fine, a_true, b_true, c_true), "g-", linewidth=2, alpha=0.5, label="True model")
    ax.plot(x_fine, model(x_fine, *popt), "r-", linewidth=2, label="Fitted model")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("Non-linear Curve Fitting: Exponential Decay")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Residuals
    ax = axes[1]
    residuals = y_data - model(x_data, *popt)
    ax.scatter(x_data, residuals, alpha=0.7, s=30, color="#FF9800")
    ax.axhline(y=0, color="black", linestyle="--", linewidth=1)
    ax.fill_between(x_data, -2 * np.std(residuals), 2 * np.std(residuals), alpha=0.2, color="red", label="±2σ")
    ax.set_xlabel("x")
    ax.set_ylabel("Residual")
    ax.set_title("Residual Analysis")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "optimization_curve_fit.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "true_params": {"a": a_true, "b": b_true, "c": c_true},
        "fitted_params": {"a": float(popt[0]), "b": float(popt[1]), "c": float(popt[2])},
        "std_errors": {"a": float(perr[0]), "b": float(perr[1]), "c": float(perr[2])},
        "r_squared": float(1 - np.sum(residuals**2) / np.sum((y_data - np.mean(y_data))**2)),
        "chart": str(path),
    }


def main():
    print("=" * 60)
    print("OPTIMIZATION — Minima, LP, Portfolio, Curve Fitting")
    print("=" * 60)

    # 1. Function optimization
    print("\n--- 1. Global Optimization (Rastrigin) ---")
    opt_result = function_optimization()
    print(f"  Minimum at: {opt_result['minimum']}")
    print(f"  f(min) = {opt_result['value']:.6f}")
    print(f"Chart: {opt_result['chart']}")

    # 2. Linear programming
    print("\n--- 2. Linear Programming (Factory) ---")
    lp_result = linear_programming_demo()
    print(f"  Optimal: A={lp_result['optimal_A']:.0f}, B={lp_result['optimal_B']:.0f}")
    print(f"  Max Profit: {lp_result['max_profit']:.0f} PLN")
    print(f"  Slack: Machine={lp_result['slack']['machine']:.0f}h, Labor={lp_result['slack']['labor']:.0f}h")
    print(f"Chart: {lp_result['chart']}")

    # 3. Portfolio optimization
    print("\n--- 3. Portfolio Optimization (Markowitz) ---")
    port_result = portfolio_optimization()
    print(f"  Max Sharpe Ratio: {port_result['max_sharpe_ratio']:.3f}")
    print(f"  Return: {port_result['max_sharpe_return']:.1%}, Vol: {port_result['max_sharpe_volatility']:.1%}")
    print(f"  Weights: {json.dumps(port_result['max_sharpe_weights'], indent=2)}")
    print(f"Chart: {port_result['chart']}")

    # 4. Curve fitting
    print("\n--- 4. Non-linear Curve Fitting ---")
    fit_result = curve_fitting_demo()
    print(f"  True: a={fit_result['true_params']['a']}, b={fit_result['true_params']['b']}, c={fit_result['true_params']['c']}")
    print(f"  Fit:  a={fit_result['fitted_params']['a']:.3f}±{fit_result['std_errors']['a']:.3f}, "
          f"b={fit_result['fitted_params']['b']:.3f}±{fit_result['std_errors']['b']:.3f}, "
          f"c={fit_result['fitted_params']['c']:.3f}±{fit_result['std_errors']['c']:.3f}")
    print(f"  R² = {fit_result['r_squared']:.4f}")
    print(f"Chart: {fit_result['chart']}")

    print(f"\n✅ All charts saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
