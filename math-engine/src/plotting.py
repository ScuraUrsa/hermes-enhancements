"""
Plotting Engine — matplotlib + plotly.
Function plots, 3D surfaces, heatmaps, financial charts.

LLM NEVER computes — this module generates actual plots.
"""

from __future__ import annotations

import os
import numpy as np
from typing import Optional

from .engine import SolveResult, ProblemType

# Non-interactive backend for headless
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def plot_function(text: str, output_dir: str = "/tmp/math-engine") -> SolveResult:
    """Plot a 2D function."""
    try:
        import re

        # Parse function
        m = re.search(r'f\s*\(\s*(\w+)\s*\)\s*=\s*(.+)', text)
        if m:
            expr_str = m.group(2).strip()
            var = m.group(1)
        else:
            # Strip prefix words
            expr_str = text
            for prefix in ['narysuj wykres ', 'narysuj ', 'wykres ', 'plot ', 'draw ']:
                if text.lower().startswith(prefix):
                    expr_str = text[len(prefix):]
                    break
            # Try to find variable
            var_match = re.search(r'\b([a-z])\b', expr_str)
            var = var_match.group(1) if var_match else 'x'

        # Parse range
        x_min, x_max = -5, 5
        m = re.search(r'\[(\-?\d+\.?\d*)\s*,\s*(\-?\d+\.?\d*)\]', text)
        if m:
            x_min, x_max = float(m.group(1)), float(m.group(2))

        # Create function
        expr_str = expr_str.replace('^', '**')
        expr_str = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr_str)

        namespace = {
            'np': np, 'sin': np.sin, 'cos': np.cos, 'tan': np.tan,
            'exp': np.exp, 'log': np.log, 'sqrt': np.sqrt, 'abs': np.abs,
            'pi': np.pi, 'e': np.e,
        }

        def f(x_val):
            namespace[var] = x_val
            return eval(expr_str, {"__builtins__": {}}, namespace)

        # Generate plot
        x = np.linspace(x_min, x_max, 1000)
        y = np.array([f(xi) for xi in x])

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(x, y, 'b-', linewidth=2, label=f'f({var}) = {expr_str}')
        ax.axhline(y=0, color='k', linewidth=0.5)
        ax.axvline(x=0, color='k', linewidth=0.5)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=12)
        ax.set_xlabel(var, fontsize=12)
        ax.set_ylabel(f'f({var})', fontsize=12)
        ax.set_title(f'Wykres funkcji f({var}) = {expr_str}', fontsize=14)

        path = os.path.join(output_dir, "plot_function.png")
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()

        return SolveResult(
            problem_type=ProblemType.PLOT_FUNCTION,
            input_text=text,
            result={
                "function": expr_str,
                "variable": var,
                "x_range": [x_min, x_max],
                "plot_path": path,
            },
            steps=[f"Wykres zapisany: {path}"],
            plot_path=path,
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.PLOT_FUNCTION,
            input_text=text,
            result=None,
            error=f"Błąd rysowania: {e}",
        )


def plot_3d(text: str, output_dir: str = "/tmp/math-engine") -> SolveResult:
    """Plot a 3D surface."""
    try:
        import re

        # Default: saddle surface
        expr_str = "x**2 - y**2"
        m = re.search(r'f\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)\s*=\s*(.+)', text)
        if m:
            expr_str = m.group(3).strip()

        expr_str = expr_str.replace('^', '**')
        expr_str = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr_str)

        namespace = {
            'np': np, 'sin': np.sin, 'cos': np.cos, 'tan': np.tan,
            'exp': np.exp, 'log': np.log, 'sqrt': np.sqrt, 'abs': np.abs,
            'pi': np.pi, 'e': np.e,
        }

        def f(x_val, y_val):
            namespace['x'] = x_val
            namespace['y'] = y_val
            return eval(expr_str, {"__builtins__": {}}, namespace)

        # Generate surface
        x = np.linspace(-5, 5, 100)
        y = np.linspace(-5, 5, 100)
        X, Y = np.meshgrid(x, y)
        Z = f(X, Y)

        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection='3d')
        surf = ax.plot_surface(X, Y, Z, cmap='viridis', alpha=0.8, linewidth=0)
        fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5)
        ax.set_xlabel('x', fontsize=12)
        ax.set_ylabel('y', fontsize=12)
        ax.set_zlabel('f(x,y)', fontsize=12)
        ax.set_title(f'Powierzchnia 3D: f(x,y) = {expr_str}', fontsize=14)

        path = os.path.join(output_dir, "plot_3d.png")
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()

        return SolveResult(
            problem_type=ProblemType.PLOT_3D,
            input_text=text,
            result={
                "function": expr_str,
                "plot_path": path,
            },
            steps=[f"Wykres 3D zapisany: {path}"],
            plot_path=path,
        )
    except Exception as e:
        return SolveResult(
            problem_type=ProblemType.PLOT_3D,
            input_text=text,
            result=None,
            error=f"Błąd rysowania 3D: {e}",
        )


def plot_mortgage_vs_etf(
    analysis: dict,
    output_dir: str = "/tmp/math-engine"
) -> str:
    """Generate mortgage vs ETF comparison chart."""
    comparison = analysis["comparison"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Left: bar chart
    ax = axes[0]
    pcts = [r["overpayment_pct"] * 100 for r in comparison]
    benefits = [r["net_benefit_b_minus_a"] for r in comparison]
    colors = ['#2ecc71' if b > 0 else '#e74c3c' for b in benefits]

    bars = ax.bar(pcts, benefits, color=colors, edgecolor='white', linewidth=0.5)
    ax.axhline(y=0, color='black', linewidth=0.8)
    ax.set_xlabel('Nadpłata (% raty)', fontsize=12)
    ax.set_ylabel('Zysk netto ETF vs nadpłata (PLN)', fontsize=12)
    ax.set_title('Kredyt vs ETF — porównanie', fontsize=14)
    ax.grid(axis='y', alpha=0.3)

    # Add value labels
    for bar, val in zip(bars, benefits):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                f'{val:+,.0f}', ha='center', va='bottom' if val > 0 else 'top',
                fontsize=9, fontweight='bold')

    # Right: break-even line
    ax = axes[1]
    etf_returns = np.linspace(0.01, 0.20, 100)
    # Simplified: net benefit as function of ETF return
    base_benefit = benefits[len(benefits)//2]  # middle overpayment
    scaled = [(r - 0.08) / 0.08 * base_benefit * 2 for r in etf_returns]

    ax.plot(etf_returns * 100, scaled, 'b-', linewidth=2)
    ax.axhline(y=0, color='red', linestyle='--', linewidth=1, label='Próg rentowności')
    ax.axvline(x=analysis["break_even_etf_return"], color='green', linestyle='--',
              linewidth=1, label=f'ETF = {analysis["break_even_etf_return"]}%')
    ax.set_xlabel('Zwrot ETF (% rocznie)', fontsize=12)
    ax.set_ylabel('Zysk netto (PLN)', fontsize=12)
    ax.set_title('Próg rentowności ETF', fontsize=14)
    ax.legend()
    ax.grid(alpha=0.3)

    plt.tight_layout()
    path = os.path.join(output_dir, "mortgage_vs_etf.png")
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    return path


def plot_efficient_frontier(
    returns: np.ndarray,
    vols: np.ndarray,
    sharpe: np.ndarray,
    best_idx: int,
    min_vol_idx: int,
    output_dir: str = "/tmp/math-engine"
) -> str:
    """Plot Markowitz efficient frontier."""
    fig, ax = plt.subplots(figsize=(10, 7))

    scatter = ax.scatter(vols * 100, returns * 100, c=sharpe, cmap='viridis',
                         alpha=0.5, s=10)
    plt.colorbar(scatter, ax=ax, label='Sharpe Ratio')

    # Mark special portfolios
    ax.scatter(vols[best_idx] * 100, returns[best_idx] * 100,
              color='red', s=200, marker='*', edgecolors='white',
              linewidth=1.5, label='Max Sharpe', zorder=5)
    ax.scatter(vols[min_vol_idx] * 100, returns[min_vol_idx] * 100,
              color='blue', s=200, marker='*', edgecolors='white',
              linewidth=1.5, label='Min Volatility', zorder=5)

    ax.set_xlabel('Ryzyko (volatility %)', fontsize=12)
    ax.set_ylabel('Oczekiwany zwrot (%)', fontsize=12)
    ax.set_title('Markowitz Efficient Frontier', fontsize=14)
    ax.legend()
    ax.grid(alpha=0.3)

    plt.tight_layout()
    path = os.path.join(output_dir, "efficient_frontier.png")
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    return path
