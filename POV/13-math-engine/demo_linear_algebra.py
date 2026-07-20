"""
Linear Algebra Demo — Eigenvalues, SVD, PCA, Least Squares, Decompositions.

Generates comprehensive plots to output/:
- Eigenvalue visualization
- SVD low-rank approximation
- PCA on synthetic data
- Least squares fitting
- Matrix decompositions (LU, QR)
- Condition number analysis
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from linear_algebra import LinearAlgebra

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

la = LinearAlgebra()


def demo_eigenvalues():
    """Demonstrate eigenvalue decomposition on various matrices."""
    print("\n--- 1. Eigenvalues & Eigenvectors ---")

    # Symmetric matrix
    A_sym = np.array([[4, 1, 1],
                       [1, 3, 2],
                       [1, 2, 5]], dtype=float)
    r = la.eigen_symmetric(A_sym)
    evals = np.array(r.result["eigenvalues"])
    evecs = np.array(r.result["eigenvectors"])
    print(f"  Symmetric 3×3: eigenvalues = {evals.round(4).tolist()}")
    print(f"  Trace check: sum(evals)={evals.sum():.4f}, trace(A)={np.trace(A_sym):.4f}")

    # Non-symmetric matrix
    A_nonsym = np.array([[0, 1],
                          [-2, -3]], dtype=float)
    r2 = la.eigen(A_nonsym)
    evals2 = np.array(r2.result["eigenvalues"])
    print(f"  Non-symmetric 2×2: eigenvalues = {[complex(v).real.round(4) + 1j*complex(v).imag.round(4) for v in evals2]}")

    # Hilbert matrix (ill-conditioned)
    H = la.hilbert_matrix(5)
    r3 = la.eigen_symmetric(H)
    evals3 = np.array(r3.result["eigenvalues"])
    cond = la.condition_number(H)
    print(f"  Hilbert 5×5: cond={cond.result:.2e}, λ_min={evals3.min():.2e}, λ_max={evals3.max():.4f}")

    return A_sym, evals, evecs, H, evals3


def demo_svd():
    """Demonstrate SVD and low-rank approximation."""
    print("\n--- 2. SVD & Low-Rank Approximation ---")

    # Create a rank-3 matrix with noise
    rng = np.random.RandomState(42)
    m, n = 50, 40
    U_true = rng.randn(m, 3)
    V_true = rng.randn(n, 3)
    A_clean = U_true @ V_true.T
    A_noisy = A_clean + 0.1 * rng.randn(m, n)

    r = la.svd(A_noisy)
    S = np.array(r.result["S"])
    print(f"  Shape: {A_noisy.shape}, singular values: {S[:6].round(4).tolist()}...")
    print(f"  Effective rank (σ > 1e-10): {r.metadata['rank']}")

    # Low-rank approximations
    U = np.array(r.result["U"])
    Vt = np.array(r.result["Vt"])
    errors = []
    for k in range(1, 11):
        A_k = U[:, :k] @ np.diag(S[:k]) @ Vt[:k, :]
        err = np.linalg.norm(A_noisy - A_k, "fro") / np.linalg.norm(A_noisy, "fro")
        errors.append(float(err))

    return A_noisy, U, S, Vt, errors


def demo_pca():
    """Demonstrate PCA on synthetic correlated data."""
    print("\n--- 3. PCA ---")

    rng = np.random.RandomState(42)
    n_samples = 200

    # Generate correlated 3D data
    mean = [5, 10, 15]
    cov = [[3.0, 2.0, 1.0],
           [2.0, 4.0, 1.5],
           [1.0, 1.5, 2.0]]
    data = rng.multivariate_normal(mean, cov, n_samples)

    r = la.pca(data, n_components=2, standardize=True)
    projected = np.array(r.result["projected_data"])
    components = np.array(r.result["components"])
    evr = r.result["explained_variance_ratio"]

    print(f"  Data shape: {data.shape}")
    print(f"  Explained variance ratio: PC1={evr[0]:.3f}, PC2={evr[1]:.3f}")
    print(f"  Cumulative: {sum(evr):.3f}")

    return data, projected, components, evr


def demo_least_squares():
    """Demonstrate least squares fitting."""
    print("\n--- 4. Least Squares ---")

    rng = np.random.RandomState(42)
    n = 50

    # True model: y = 2 + 3x - 1.5x² + noise
    x = np.linspace(-3, 3, n)
    y_true = 2 + 3 * x - 1.5 * x**2
    y = y_true + rng.normal(0, 2, n)

    # Design matrix for quadratic fit
    A = np.column_stack([np.ones(n), x, x**2])
    r = la.least_squares(A, y)
    coeffs = np.array(r.result["x"])
    y_pred = A @ coeffs

    print(f"  Fitted coefficients: {coeffs.round(4).tolist()}")
    print(f"  True coefficients: [2, 3, -1.5]")
    print(f"  Residual norm: {r.result['residual_norm']:.4f}")

    # Also via normal equations
    r2 = la.solve_least_squares_normal(A, y)
    coeffs2 = np.array(r2.result["x"])
    print(f"  Normal eq coefficients: {coeffs2.round(4).tolist()}")

    return x, y, y_true, y_pred, coeffs


def demo_decompositions():
    """Demonstrate LU and QR decompositions."""
    print("\n--- 5. Matrix Decompositions ---")

    A = np.array([[2, -1, 1],
                   [3, 3, 9],
                   [3, 3, 5]], dtype=float)

    # LU
    r_lu = la.lu_decomposition(A)
    P = np.array(r_lu.result["P"])
    L = np.array(r_lu.result["L"])
    U = np.array(r_lu.result["U"])
    recon_lu = P @ L @ U
    lu_err = np.linalg.norm(A - recon_lu)
    print(f"  LU: ||A - PLU|| = {lu_err:.2e}")

    # QR
    r_qr = la.qr_decomposition(A)
    Q = np.array(r_qr.result["Q"])
    R = np.array(r_qr.result["R"])
    recon_qr = Q @ R
    qr_err = np.linalg.norm(A - recon_qr)
    print(f"  QR: ||A - QR|| = {qr_err:.2e}")

    # Matrix info
    info = la.matrix_info(A)
    print(f"  Rank: {info.result['rank']}, Det: {info.result['det']:.4f}")
    print(f"  Condition number: {info.result['condition_number']:.4f}")

    return A, L, U, Q, R


def demo_linear_system():
    """Demonstrate solving linear systems."""
    print("\n--- 6. Solving Linear Systems ---")

    A = np.array([[3, 2, -1],
                   [2, -2, 4],
                   [-1, 0.5, -1]], dtype=float)
    b = np.array([1, -2, 0], dtype=float)

    r = la.solve(A, b)
    x = np.array(r.result["x"])
    print(f"  Solution x = {x.round(4).tolist()}")
    print(f"  Residual ||Ax-b|| = {r.result['residual']:.2e}")

    # Verify
    b_check = A @ x
    print(f"  Verification: Ax = {b_check.round(4).tolist()}, expected b = {b.tolist()}")

    return A, b, x


# ---- PLOTS ----

def main():
    print("=" * 60)
    print("LINEAR ALGEBRA — Eigenvalues, SVD, PCA, Least Squares")
    print("=" * 60)

    # Run all demos
    A_sym, evals, evecs, H, evals_h = demo_eigenvalues()
    A_noisy, U_svd, S_svd, Vt_svd, svd_errors = demo_svd()
    data_pca, projected, components, evr = demo_pca()
    x_ls, y_ls, y_true, y_pred, coeffs = demo_least_squares()
    A_dec, L, U_dec, Q, R = demo_decompositions()
    A_sys, b_sys, x_sol = demo_linear_system()

    # ---- FIGURE ----
    fig = plt.figure(figsize=(20, 16))

    # 1. Eigenvalue spectrum
    ax1 = fig.add_subplot(3, 4, 1)
    colors = ["#2196F3", "#4CAF50", "#FF9800", "#E91E63", "#9C27B0"]
    ax1.bar(range(len(evals)), evals, color=colors[:len(evals)], edgecolor="white")
    ax1.axhline(y=0, color="black", linewidth=0.5)
    ax1.set_title("Eigenvalues (Symmetric 3×3)")
    ax1.set_ylabel("λ")
    ax1.grid(True, alpha=0.3)

    # 2. Eigenvectors as arrows
    ax2 = fig.add_subplot(3, 4, 2)
    origin = np.zeros(2)
    for i in range(min(3, evecs.shape[1])):
        ax2.arrow(0, 0, evecs[0, i], evecs[1, i],
                  head_width=0.1, head_length=0.1, fc=colors[i], ec=colors[i],
                  linewidth=2, label=f"v{i+1} (λ={evals[i]:.2f})")
    ax2.set_xlim(-1.2, 1.2)
    ax2.set_ylim(-1.2, 1.2)
    ax2.set_aspect("equal")
    ax2.set_title("Eigenvectors (first 2 coords)")
    ax2.legend(fontsize=7)
    ax2.grid(True, alpha=0.3)

    # 3. Hilbert matrix eigenvalues
    ax3 = fig.add_subplot(3, 4, 3)
    ax3.semilogy(range(1, len(evals_h) + 1), evals_h, "o-", color="#E91E63", markersize=8)
    ax3.set_title("Hilbert 5×5 Eigenvalues (log)")
    ax3.set_xlabel("Index")
    ax3.set_ylabel("λ (log scale)")
    ax3.grid(True, alpha=0.3)

    # 4. SVD singular values
    ax4 = fig.add_subplot(3, 4, 4)
    ax4.semilogy(range(1, len(S_svd) + 1), S_svd, "o-", color="#2196F3", markersize=4)
    ax4.axhline(y=1e-10, color="red", linestyle="--", alpha=0.5, label="ε=1e-10")
    ax4.set_title("Singular Values (log)")
    ax4.set_xlabel("Index")
    ax4.set_ylabel("σ (log scale)")
    ax4.legend(fontsize=7)
    ax4.grid(True, alpha=0.3)

    # 5. SVD low-rank approximation error
    ax5 = fig.add_subplot(3, 4, 5)
    ax5.plot(range(1, 11), svd_errors, "o-", color="#4CAF50", linewidth=2, markersize=6)
    ax5.axvline(x=3, color="red", linestyle="--", alpha=0.5, label="True rank=3")
    ax5.set_title("SVD Low-Rank Approx Error")
    ax5.set_xlabel("Rank k")
    ax5.set_ylabel("Relative Frobenius error")
    ax5.legend(fontsize=7)
    ax5.grid(True, alpha=0.3)

    # 6. PCA: original 3D data (2 projections)
    ax6 = fig.add_subplot(3, 4, 6)
    ax6.scatter(data_pca[:, 0], data_pca[:, 1], c=data_pca[:, 2],
                cmap="viridis", alpha=0.6, s=20)
    ax6.set_xlabel("Feature 1")
    ax6.set_ylabel("Feature 2")
    ax6.set_title("Original Data (colored by Feature 3)")
    ax6.grid(True, alpha=0.3)

    # 7. PCA: projected 2D
    ax7 = fig.add_subplot(3, 4, 7)
    ax7.scatter(projected[:, 0], projected[:, 1], alpha=0.6, s=20, color="#2196F3")
    ax7.set_xlabel(f"PC1 ({evr[0]:.1%} var)")
    ax7.set_ylabel(f"PC2 ({evr[1]:.1%} var)")
    ax7.set_title("PCA Projection (2D)")
    ax7.grid(True, alpha=0.3)

    # 8. PCA: explained variance
    ax8 = fig.add_subplot(3, 4, 8)
    sv_pca = np.array(la.pca(data_pca, n_components=3).result["singular_values"])
    total_var = np.sum(sv_pca ** 2)
    evr_all = (sv_pca ** 2) / total_var
    ax8.bar(["PC1", "PC2", "PC3"], evr_all, color=["#2196F3", "#4CAF50", "#FF9800"])
    ax8.set_title("Explained Variance Ratio")
    ax8.set_ylabel("Ratio")
    ax8.grid(True, alpha=0.3)

    # 9. Least squares fit
    ax9 = fig.add_subplot(3, 4, 9)
    ax9.scatter(x_ls, y_ls, alpha=0.5, s=20, label="Data", color="#2196F3")
    ax9.plot(x_ls, y_true, linewidth=2, color="green", alpha=0.5, label="True")
    ax9.plot(x_ls, y_pred, linewidth=2, color="red", label=f"Fit: {coeffs[0]:.2f}+{coeffs[1]:.2f}x+{coeffs[2]:.2f}x²")
    ax9.set_xlabel("x")
    ax9.set_ylabel("y")
    ax9.set_title("Least Squares Quadratic Fit")
    ax9.legend(fontsize=7)
    ax9.grid(True, alpha=0.3)

    # 10. LU decomposition visualization
    ax10 = fig.add_subplot(3, 4, 10)
    im10 = ax10.imshow(L, cmap="RdBu_r", aspect="auto")
    ax10.set_title("L (Lower Triangular)")
    plt.colorbar(im10, ax=ax10, shrink=0.8)

    # 11. U decomposition visualization
    ax11 = fig.add_subplot(3, 4, 11)
    im11 = ax11.imshow(U_dec, cmap="RdBu_r", aspect="auto")
    ax11.set_title("U (Upper Triangular)")
    plt.colorbar(im11, ax=ax11, shrink=0.8)

    # 12. QR: R matrix
    ax12 = fig.add_subplot(3, 4, 12)
    im12 = ax12.imshow(R, cmap="RdBu_r", aspect="auto")
    ax12.set_title("R (Upper Triangular from QR)")
    plt.colorbar(im12, ax=ax12, shrink=0.8)

    plt.tight_layout()
    path = OUTPUT_DIR / "linear_algebra_demo.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n✅ Chart saved: {path}")

    # ---- Additional figure: Condition number & Hilbert ----
    fig2, axes2 = plt.subplots(1, 2, figsize=(12, 5))

    # Condition number vs matrix size for Hilbert
    sizes = range(2, 11)
    conds = []
    for s in sizes:
        H_s = la.hilbert_matrix(s)
        conds.append(la.condition_number(H_s).result)

    ax = axes2[0]
    ax.semilogy(list(sizes), conds, "o-", color="#E91E63", linewidth=2, markersize=8)
    ax.set_title("Hilbert Matrix: Condition Number vs Size")
    ax.set_xlabel("Matrix size n")
    ax.set_ylabel("Condition number κ (log)")
    ax.grid(True, alpha=0.3)

    # Solution to linear system
    ax = axes2[1]
    ax.bar(["x₁", "x₂", "x₃"], x_sol, color=["#2196F3", "#4CAF50", "#FF9800"])
    ax.axhline(y=0, color="black", linewidth=0.5)
    ax.set_title(f"Solution to Ax=b (residual={la.solve(A_sys, b_sys).result['residual']:.2e})")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path2 = OUTPUT_DIR / "linear_algebra_extra.png"
    plt.savefig(path2, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path2}")

    print(f"\n✅ All linear algebra charts saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
