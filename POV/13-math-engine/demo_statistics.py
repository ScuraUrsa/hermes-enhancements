"""
Statistics & Probability Demo — Distributions, Tests, Regression, Bayes.

Demonstrates:
- Distribution fitting & visualization
- Hypothesis testing (t-test, chi-square, ANOVA)
- Linear & polynomial regression
- Bayesian inference (coin flip, A/B testing)
- Correlation analysis
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


def distribution_gallery() -> dict:
    """Generate a gallery of common probability distributions."""
    distributions = [
        ("Normal(0,1)", stats.norm(loc=0, scale=1), -4, 4),
        ("Normal(2,0.5)", stats.norm(loc=2, scale=0.5), 0, 4),
        ("t(df=3)", stats.t(df=3), -4, 4),
        ("Chi²(df=4)", stats.chi2(df=4), 0, 15),
        ("Exponential(λ=1)", stats.expon(scale=1), 0, 5),
        ("Beta(2,5)", stats.beta(a=2, b=5), 0, 1),
        ("Gamma(2,2)", stats.gamma(a=2, scale=2), 0, 15),
        ("Lognormal(0,0.5)", stats.lognorm(s=0.5, scale=1), 0, 4),
        ("Poisson(λ=5)", stats.poisson(mu=5), 0, 15),
        ("Binomial(n=20,p=0.3)", stats.binom(n=20, p=0.3), 0, 15),
    ]

    fig, axes = plt.subplots(2, 5, figsize=(20, 8))
    fig.suptitle("Probability Distribution Gallery", fontsize=14, fontweight="bold")

    for idx, (name, dist, xmin, xmax) in enumerate(distributions):
        ax = axes[idx // 5][idx % 5]
        x = np.linspace(xmin, xmax, 500)
        if "Poisson" in name or "Binomial" in name:
            x_int = np.arange(int(xmin), int(xmax) + 1)
            ax.bar(x_int, dist.pmf(x_int), alpha=0.7, color="#2196F3", width=0.6)
        else:
            ax.plot(x, dist.pdf(x), linewidth=2, color="#2196F3")
            ax.fill_between(x, dist.pdf(x), alpha=0.2, color="#2196F3")
        ax.set_title(name, fontsize=9)
        ax.set_xlim(xmin, xmax)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "statistics_distributions.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {"n_distributions": len(distributions), "chart": str(path)}


def hypothesis_testing_demo() -> dict:
    """Demonstrate common hypothesis tests with synthetic data."""
    rng = np.random.RandomState(42)

    results = {}

    # 1. One-sample t-test
    data = rng.normal(102, 15, 50)  # Mean should be ~102
    t_stat, p_val = stats.ttest_1samp(data, 100)
    results["ttest_1samp"] = {
        "description": "Is the mean different from 100?",
        "t_statistic": float(t_stat),
        "p_value": float(p_val),
        "significant_05": bool(p_val < 0.05),
        "sample_mean": float(np.mean(data)),
    }

    # 2. Two-sample t-test
    group_a = rng.normal(100, 15, 40)
    group_b = rng.normal(110, 15, 40)  # Different mean
    t_stat, p_val = stats.ttest_ind(group_a, group_b)
    results["ttest_ind"] = {
        "description": "Are groups A and B different?",
        "t_statistic": float(t_stat),
        "p_value": float(p_val),
        "significant_05": bool(p_val < 0.05),
        "mean_a": float(np.mean(group_a)),
        "mean_b": float(np.mean(group_b)),
    }

    # 3. Chi-square test of independence
    observed = np.array([[30, 20, 10], [15, 25, 20]])
    chi2, p_val, dof, expected = stats.chi2_contingency(observed)
    results["chi2"] = {
        "description": "Is there association between rows and columns?",
        "chi2": float(chi2),
        "p_value": float(p_val),
        "dof": int(dof),
        "significant_05": bool(p_val < 0.05),
    }

    # 4. ANOVA
    g1 = rng.normal(100, 10, 30)
    g2 = rng.normal(105, 10, 30)
    g3 = rng.normal(115, 10, 30)
    f_stat, p_val = stats.f_oneway(g1, g2, g3)
    results["anova"] = {
        "description": "Are all three groups the same?",
        "f_statistic": float(f_stat),
        "p_value": float(p_val),
        "significant_05": bool(p_val < 0.05),
        "means": [float(np.mean(g1)), float(np.mean(g2)), float(np.mean(g3))],
    }

    # 5. Normality test
    normal_data = rng.normal(0, 1, 100)
    uniform_data = rng.uniform(0, 1, 100)
    shapiro_normal = stats.shapiro(normal_data)
    shapiro_uniform = stats.shapiro(uniform_data)
    results["normality"] = {
        "normal_data_p": float(shapiro_normal.pvalue),
        "normal_is_normal": bool(shapiro_normal.pvalue > 0.05),
        "uniform_data_p": float(shapiro_uniform.pvalue),
        "uniform_is_normal": bool(shapiro_uniform.pvalue > 0.05),
    }

    # Plot
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # t-test visualization
    ax = axes[0, 0]
    ax.hist(group_a, bins=15, alpha=0.5, label=f"Group A (μ={np.mean(group_a):.1f})", color="#2196F3")
    ax.hist(group_b, bins=15, alpha=0.5, label=f"Group B (μ={np.mean(group_b):.1f})", color="#FF9800")
    ax.axvline(x=np.mean(group_a), color="#2196F3", linewidth=2)
    ax.axvline(x=np.mean(group_b), color="#FF9800", linewidth=2)
    ax.set_title(f"Two-Sample t-test: p={p_val:.4f} {'*' if p_val < 0.05 else 'ns'}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # ANOVA
    ax = axes[0, 1]
    positions = [1, 2, 3]
    ax.boxplot([g1, g2, g3], positions=positions, widths=0.5)
    ax.scatter(np.ones(30), g1, alpha=0.3, s=10)
    ax.scatter(np.ones(30) * 2, g2, alpha=0.3, s=10)
    ax.scatter(np.ones(30) * 3, g3, alpha=0.3, s=10)
    ax.set_xticklabels(["G1", "G2", "G3"])
    ax.set_title(f"ANOVA: F={f_stat:.2f}, p={p_val:.4f} {'*' if p_val < 0.05 else 'ns'}")
    ax.grid(True, alpha=0.3)

    # QQ plot
    ax = axes[1, 0]
    stats.probplot(normal_data, dist="norm", plot=ax)
    ax.set_title("Q-Q Plot: Normal Data")

    # Chi-square
    ax = axes[1, 1]
    x_pos = np.arange(len(observed[0]))
    width = 0.35
    ax.bar(x_pos - width/2, observed[0], width, label="Row 1", color="#2196F3")
    ax.bar(x_pos + width/2, observed[1], width, label="Row 2", color="#FF9800")
    ax.set_title(f"Chi²: χ²={chi2:.2f}, p={p_val:.4f}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "statistics_hypothesis_tests.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {"tests": results, "chart": str(path)}


def regression_demo() -> dict:
    """Demonstrate linear and polynomial regression."""
    rng = np.random.RandomState(42)

    # Generate data with noise
    n = 50
    x = np.linspace(0, 10, n)
    y_true = 2.5 * x + 5 + 3 * np.sin(x)  # Linear + sinusoidal
    y = y_true + rng.normal(0, 3, n)

    # Linear regression
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    y_pred_linear = slope * x + intercept

    # Polynomial regression (degree 3)
    coeffs = np.polyfit(x, y, 3)
    y_pred_poly = np.polyval(coeffs, x)

    # R² for polynomial
    ss_res = np.sum((y - y_pred_poly) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2_poly = 1 - ss_res / ss_tot

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    ax.scatter(x, y, alpha=0.6, s=30, label="Data", color="#2196F3")
    ax.plot(x, y_true, linewidth=2, color="green", alpha=0.5, label="True function")
    ax.plot(x, y_pred_linear, linewidth=2, color="red", label=f"Linear (R²={r_value**2:.3f})")
    ax.plot(x, y_pred_poly, linewidth=2, color="orange", label=f"Poly deg=3 (R²={r2_poly:.3f})")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("Regression: Linear vs Polynomial")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Residuals
    ax = axes[1]
    ax.scatter(x, y - y_pred_linear, alpha=0.6, s=30, label="Linear residuals", color="red")
    ax.scatter(x, y - y_pred_poly, alpha=0.6, s=30, label="Poly residuals", color="orange")
    ax.axhline(y=0, color="black", linestyle="--", linewidth=1)
    ax.set_xlabel("x")
    ax.set_ylabel("Residual")
    ax.set_title("Residual Analysis")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "statistics_regression.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "linear": {
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": float(r_value ** 2),
            "p_value": float(p_value),
        },
        "polynomial_deg3": {
            "coefficients": coeffs.tolist(),
            "r_squared": float(r2_poly),
        },
        "chart": str(path),
    }


def bayesian_demo() -> dict:
    """Bayesian inference: coin flip and A/B testing."""
    rng = np.random.RandomState(42)

    # Coin flip: Beta-Binomial conjugate
    # Prior: Beta(1,1) = uniform
    # Observe: 7 heads out of 10 flips
    n_flips = 10
    n_heads = 7

    theta = np.linspace(0, 1, 500)
    prior = stats.beta.pdf(theta, 1, 1)
    posterior = stats.beta.pdf(theta, 1 + n_heads, 1 + n_flips - n_heads)
    likelihood = theta**n_heads * (1 - theta)**(n_flips - n_heads)
    likelihood /= np.trapz(likelihood, theta)  # Normalize

    # A/B testing: Beta-Binomial
    # A: 30 conversions / 100 visitors
    # B: 40 conversions / 100 visitors
    n_sim = 100_000
    a_samples = rng.beta(1 + 30, 1 + 70, n_sim)
    b_samples = rng.beta(1 + 40, 1 + 60, n_sim)
    prob_b_better = np.mean(b_samples > a_samples)

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Coin flip
    ax = axes[0]
    ax.plot(theta, prior, linewidth=2, label="Prior: Beta(1,1)", color="gray", linestyle="--")
    ax.plot(theta, likelihood, linewidth=2, label=f"Likelihood: {n_heads}/{n_flips} heads", color="green", alpha=0.7)
    ax.plot(theta, posterior, linewidth=2, label=f"Posterior: Beta({1+n_heads},{1+n_flips-n_heads})", color="#2196F3")
    ax.axvline(x=0.5, color="red", linestyle=":", alpha=0.5, label="Fair coin")
    ax.set_xlabel("θ (probability of heads)")
    ax.set_ylabel("Density")
    ax.set_title("Bayesian Coin Flip")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # A/B test
    ax = axes[1]
    ax.hist(a_samples, bins=100, alpha=0.5, density=True, label=f"A: 30/100", color="#2196F3")
    ax.hist(b_samples, bins=100, alpha=0.5, density=True, label=f"B: 40/100", color="#FF9800")
    ax.axvline(x=np.mean(a_samples), color="#2196F3", linewidth=2)
    ax.axvline(x=np.mean(b_samples), color="#FF9800", linewidth=2)
    ax.set_xlabel("Conversion Rate")
    ax.set_ylabel("Density")
    ax.set_title(f"A/B Test: P(B > A) = {prob_b_better:.1%}")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "statistics_bayesian.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "coin_flip": {
            "prior": "Beta(1,1)",
            "posterior": f"Beta({1+n_heads},{1+n_flips-n_heads})",
            "posterior_mean": float((1 + n_heads) / (2 + n_flips)),
            "credible_interval_95": [
                float(stats.beta.ppf(0.025, 1 + n_heads, 1 + n_flips - n_heads)),
                float(stats.beta.ppf(0.975, 1 + n_heads, 1 + n_flips - n_heads)),
            ],
        },
        "ab_test": {
            "prob_b_better": float(prob_b_better),
            "expected_lift": float(np.mean(b_samples - a_samples) / np.mean(a_samples)),
        },
        "chart": str(path),
    }


def correlation_analysis() -> dict:
    """Correlation matrix and pairplot for multivariate data."""
    rng = np.random.RandomState(42)
    n = 200

    # Generate correlated data
    x1 = rng.normal(0, 1, n)
    x2 = 0.7 * x1 + rng.normal(0, 0.5, n)
    x3 = -0.4 * x1 + 0.3 * x2 + rng.normal(0, 0.8, n)
    x4 = rng.normal(0, 1, n)  # Independent

    data = np.column_stack([x1, x2, x3, x4])
    labels = ["Height", "Weight", "BMI", "Age"]

    corr = np.corrcoef(data.T)

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_yticklabels(labels)
    ax.set_title("Correlation Matrix", fontsize=12, fontweight="bold")

    for i in range(len(labels)):
        for j in range(len(labels)):
            color = "white" if abs(corr[i, j]) > 0.5 else "black"
            ax.text(j, i, f"{corr[i, j]:.2f}", ha="center", va="center", color=color, fontsize=10)

    plt.colorbar(im, ax=ax, shrink=0.8)
    plt.tight_layout()
    path = OUTPUT_DIR / "statistics_correlation.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "correlation_matrix": {labels[i]: {labels[j]: float(corr[i, j]) for j in range(len(labels))} for i in range(len(labels))},
        "chart": str(path),
    }


def main():
    print("=" * 60)
    print("STATISTICS & PROBABILITY — Comprehensive Demo")
    print("=" * 60)

    # 1. Distribution gallery
    print("\n--- 1. Distribution Gallery ---")
    dist_result = distribution_gallery()
    print(f"Generated {dist_result['n_distributions']} distributions")
    print(f"Chart: {dist_result['chart']}")

    # 2. Hypothesis testing
    print("\n--- 2. Hypothesis Testing ---")
    test_result = hypothesis_testing_demo()
    for test_name, test_data in test_result["tests"].items():
        if "description" in test_data:
            sig = "✓ SIGNIFICANT" if test_data.get("significant_05") else "✗ not significant"
            print(f"  {test_name}: {test_data['description']} → {sig} (p={test_data.get('p_value', 'N/A'):.4f})")
        else:
            print(f"  {test_name}: {json.dumps(test_data)}")
    print(f"Chart: {test_result['chart']}")

    # 3. Regression
    print("\n--- 3. Regression Analysis ---")
    reg_result = regression_demo()
    print(f"  Linear: R²={reg_result['linear']['r_squared']:.4f}, p={reg_result['linear']['p_value']:.4f}")
    print(f"  Polynomial (deg 3): R²={reg_result['polynomial_deg3']['r_squared']:.4f}")
    print(f"Chart: {reg_result['chart']}")

    # 4. Bayesian
    print("\n--- 4. Bayesian Inference ---")
    bayes_result = bayesian_demo()
    print(f"  Coin flip: posterior mean = {bayes_result['coin_flip']['posterior_mean']:.3f}")
    print(f"  A/B test: P(B > A) = {bayes_result['ab_test']['prob_b_better']:.1%}")
    print(f"Chart: {bayes_result['chart']}")

    # 5. Correlation
    print("\n--- 5. Correlation Analysis ---")
    corr_result = correlation_analysis()
    print(f"Chart: {corr_result['chart']}")

    print(f"\n✅ All charts saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
