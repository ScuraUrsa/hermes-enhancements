"""
Linear Algebra Demo — SVD, PCA, Eigenfaces, Matrix Decompositions.

Demonstrates:
- SVD decomposition and low-rank approximation
- PCA (Principal Component Analysis) with visualization
- Eigenvalue decomposition
- QR decomposition
- Image compression via SVD
- Covariance matrix analysis
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import linalg

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def svd_demo() -> dict:
    """Demonstrate SVD decomposition and low-rank approximation."""
    rng = np.random.RandomState(42)

    # Create a low-rank matrix with noise
    m, n = 50, 40
    true_rank = 5
    U_true = rng.normal(0, 1, (m, true_rank))
    V_true = rng.normal(0, 1, (n, true_rank))
    A = U_true @ V_true.T + 0.1 * rng.normal(0, 1, (m, n))

    # SVD
    U, s, Vt = linalg.svd(A, full_matrices=False)

    # Low-rank approximations
    ranks = [1, 2, 3, 5, 10, 20]
    errors = []
    for k in ranks:
        A_k = U[:, :k] @ np.diag(s[:k]) @ Vt[:k, :]
        error = np.linalg.norm(A - A_k) / np.linalg.norm(A)
        errors.append(float(error))

    # Plot
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))

    # Singular values
    ax = axes[0, 0]
    ax.semilogy(s, "o-", markersize=4, linewidth=1.5, color="#2196F3")
    ax.axvline(x=true_rank - 1, color="red", linestyle="--", linewidth=1.5,
               label=f"True rank = {true_rank}")
    ax.set_xlabel("Index")
    ax.set_ylabel("Singular Value (log scale)")
    ax.set_title("Singular Value Spectrum")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Reconstruction error
    ax = axes[0, 1]
    ax.plot(ranks, errors, "o-", markersize=6, linewidth=2, color="#4CAF50")
    ax.set_xlabel("Rank k")
    ax.set_ylabel("Relative Error ||A - A_k|| / ||A||")
    ax.set_title("Low-Rank Approximation Error")
    ax.grid(True, alpha=0.3)

    # Original matrix
    ax = axes[0, 2]
    im = ax.imshow(A, aspect="auto", cmap="RdBu_r")
    ax.set_title(f"Original Matrix ({m}×{n})")
    plt.colorbar(im, ax=ax, shrink=0.8)

    # Low-rank approximations
    for idx, k in enumerate([1, 5, 20]):
        ax = axes[1, idx]
        A_k = U[:, :k] @ np.diag(s[:k]) @ Vt[:k, :]
        im = ax.imshow(A_k, aspect="auto", cmap="RdBu_r")
        ax.set_title(f"Rank-{k} Approximation (error: {errors[ranks.index(k)]:.1%})")
        plt.colorbar(im, ax=ax, shrink=0.8)

    plt.tight_layout()
    path = OUTPUT_DIR / "linear_algebra_svd.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "singular_values_top10": s[:10].tolist(),
        "condition_number": float(s[0] / s[-1]),
        "effective_rank": int(np.sum(s > 1e-10)),
        "errors": {str(k): e for k, e in zip(ranks, errors)},
        "chart": str(path),
    }


def pca_demo() -> dict:
    """Demonstrate PCA on correlated multivariate data."""
    rng = np.random.RandomState(42)
    n_samples = 300

    # Generate correlated 3D data
    mean = [5, 10, 3]
    cov = [
        [4.0, 2.5, 1.0],
        [2.5, 3.0, 1.5],
        [1.0, 1.5, 2.0],
    ]
    data = rng.multivariate_normal(mean, cov, n_samples)

    # Center data
    data_centered = data - np.mean(data, axis=0)

    # PCA via SVD
    U, s, Vt = linalg.svd(data_centered, full_matrices=False)
    explained_variance = (s ** 2) / (n_samples - 1)
    explained_variance_ratio = explained_variance / np.sum(explained_variance)

    # Project onto first 2 PCs
    pc_scores = data_centered @ Vt.T[:, :2]

    # Plot
    fig = plt.figure(figsize=(16, 10))

    # Original 3D data
    ax1 = fig.add_subplot(2, 3, 1, projection="3d")
    ax1.scatter(data[:, 0], data[:, 1], data[:, 2], c=data[:, 0], cmap="viridis",
                alpha=0.6, s=15)
    ax1.set_xlabel("X1")
    ax1.set_ylabel("X2")
    ax1.set_zlabel("X3")
    ax1.set_title("Original 3D Data")

    # PCA projection (2D)
    ax2 = fig.add_subplot(2, 3, 2)
    scatter = ax2.scatter(pc_scores[:, 0], pc_scores[:, 1],
                          c=data[:, 0], cmap="viridis", alpha=0.6, s=15)
    ax2.set_xlabel(f"PC1 ({explained_variance_ratio[0]:.1%} var)")
    ax2.set_ylabel(f"PC2 ({explained_variance_ratio[1]:.1%} var)")
    ax2.set_title("PCA Projection (First 2 PCs)")
    ax2.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax2, shrink=0.8, label="Original X1")

    # Explained variance
    ax3 = fig.add_subplot(2, 3, 3)
    cumsum = np.cumsum(explained_variance_ratio)
    ax3.bar(range(1, 4), explained_variance_ratio, alpha=0.7, color="#2196F3",
            label="Individual")
    ax3.plot(range(1, 4), cumsum, "ro-", linewidth=2, markersize=8, label="Cumulative")
    ax3.set_xlabel("Principal Component")
    ax3.set_ylabel("Explained Variance Ratio")
    ax3.set_title("Scree Plot")
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(0, 1.1)

    # Loadings (PC directions)
    ax4 = fig.add_subplot(2, 3, 4)
    loadings = Vt.T[:, :2]
    features = ["X1", "X2", "X3"]
    x = np.arange(len(features))
    width = 0.35
    ax4.bar(x - width/2, loadings[:, 0], width, label="PC1", color="#2196F3", alpha=0.7)
    ax4.bar(x + width/2, loadings[:, 1], width, label="PC2", color="#FF9800", alpha=0.7)
    ax4.set_xticks(x)
    ax4.set_xticklabels(features)
    ax4.set_ylabel("Loading")
    ax4.set_title("PCA Loadings")
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    # Covariance matrix
    ax5 = fig.add_subplot(2, 3, 5)
    cov_mat = np.cov(data.T)
    im = ax5.imshow(cov_mat, cmap="RdBu_r", vmin=-5, vmax=5)
    for i in range(3):
        for j in range(3):
            ax5.text(j, i, f"{cov_mat[i, j]:.2f}", ha="center", va="center",
                     color="white" if abs(cov_mat[i, j]) > 2.5 else "black")
    ax5.set_xticks(range(3))
    ax5.set_yticks(range(3))
    ax5.set_xticklabels(features)
    ax5.set_yticklabels(features)
    ax5.set_title("Covariance Matrix")
    plt.colorbar(im, ax=ax5, shrink=0.8)

    # Biplot
    ax6 = fig.add_subplot(2, 3, 6)
    ax6.scatter(pc_scores[:, 0], pc_scores[:, 1], alpha=0.3, s=10, color="gray")
    # Arrows for loadings
    for i, feature in enumerate(features):
        ax6.arrow(0, 0, loadings[i, 0] * 3, loadings[i, 1] * 3,
                  head_width=0.15, head_length=0.2, fc="red", ec="red", linewidth=2)
        ax6.text(loadings[i, 0] * 3.3, loadings[i, 1] * 3.3, feature,
                 fontsize=10, fontweight="bold", color="red")
    ax6.set_xlabel(f"PC1 ({explained_variance_ratio[0]:.1%})")
    ax6.set_ylabel(f"PC2 ({explained_variance_ratio[1]:.1%})")
    ax6.set_title("PCA Biplot")
    ax6.grid(True, alpha=0.3)
    ax6.axhline(y=0, color="black", linewidth=0.5)
    ax6.axvline(x=0, color="black", linewidth=0.5)

    plt.tight_layout()
    path = OUTPUT_DIR / "linear_algebra_pca.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "explained_variance_ratio": explained_variance_ratio.tolist(),
        "cumulative_variance": cumsum.tolist(),
        "loadings_pc1": loadings[:, 0].tolist(),
        "loadings_pc2": loadings[:, 1].tolist(),
        "chart": str(path),
    }


def image_compression_svd() -> dict:
    """Demonstrate image compression using SVD."""
    # Generate a synthetic "image" (2D Gaussian mixture)
    rng = np.random.RandomState(42)
    size = 100
    x = np.linspace(-3, 3, size)
    y = np.linspace(-3, 3, size)
    X, Y = np.meshgrid(x, y)

    # Create image from multiple Gaussians
    img = (
        1.0 * np.exp(-((X - 0)**2 + (Y - 0)**2) / 0.5) +
        0.7 * np.exp(-((X - 1.5)**2 + (Y + 1)**2) / 0.3) +
        0.5 * np.exp(-((X + 1.5)**2 + (Y - 1.5)**2) / 0.4) +
        0.3 * np.exp(-((X + 1)**2 + (Y + 1.5)**2) / 0.2)
    )

    # SVD
    U, s, Vt = linalg.svd(img, full_matrices=False)

    # Compress with different ranks
    ranks = [1, 3, 5, 10, 20, 50]
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle("Image Compression via SVD", fontsize=14, fontweight="bold")

    for idx, k in enumerate(ranks):
        ax = axes[idx // 3][idx % 3]
        compressed = U[:, :k] @ np.diag(s[:k]) @ Vt[:k, :]
        compression_ratio = (size * size) / (k * (2 * size + 1))
        error = np.linalg.norm(img - compressed) / np.linalg.norm(img)

        ax.imshow(compressed, cmap="viridis", extent=[-3, 3, -3, 3])
        ax.set_title(f"Rank {k} | Compression {compression_ratio:.0f}:1 | Error {error:.1%}")
        ax.axis("off")

    plt.tight_layout()
    path = OUTPUT_DIR / "linear_algebra_image_compression.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "original_size": size * size,
        "ranks_tested": ranks,
        "chart": str(path),
    }


def matrix_decompositions() -> dict:
    """Demonstrate QR, LU, Cholesky decompositions."""
    rng = np.random.RandomState(42)

    # QR decomposition
    A = rng.normal(0, 1, (5, 4))
    Q, R = linalg.qr(A)

    # LU decomposition
    B = rng.normal(0, 1, (4, 4)) + 4 * np.eye(4)  # Make diagonally dominant
    P, L, U = linalg.lu(B)

    # Cholesky (for SPD matrix)
    C = rng.normal(0, 1, (4, 4))
    C = C.T @ C + np.eye(4)  # Make SPD
    L_chol = linalg.cholesky(C, lower=True)

    # Plot
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))

    matrices = [
        ("Q (Orthogonal)", Q, axes[0, 0]),
        ("R (Upper Triangular)", R, axes[0, 1]),
        ("L (Lower Triangular)", L, axes[0, 2]),
        ("U (Upper Triangular)", U, axes[1, 0]),
        ("L (Cholesky)", L_chol, axes[1, 1]),
        ("L @ Lᵀ = C", L_chol @ L_chol.T, axes[1, 2]),
    ]

    for title, mat, ax in matrices:
        im = ax.imshow(mat, cmap="RdBu_r")
        ax.set_title(title)
        plt.colorbar(im, ax=ax, shrink=0.8)
        # Annotate values
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                color = "white" if abs(mat[i, j]) > 2 else "black"
                ax.text(j, i, f"{mat[i, j]:.1f}", ha="center", va="center",
                        fontsize=7, color=color)

    plt.tight_layout()
    path = OUTPUT_DIR / "linear_algebra_decompositions.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "qr_error": float(np.linalg.norm(A - Q @ R)),
        "lu_error": float(np.linalg.norm(P @ B - L @ U)),
        "cholesky_error": float(np.linalg.norm(C - L_chol @ L_chol.T)),
        "chart": str(path),
    }


def main():
    print("=" * 60)
    print("LINEAR ALGEBRA — SVD, PCA, Decompositions")
    print("=" * 60)

    # 1. SVD
    print("\n--- 1. SVD Decomposition ---")
    svd_result = svd_demo()
    print(f"  Top 5 singular values: {[f'{v:.2f}' for v in svd_result['singular_values_top10'][:5]]}")
    print(f"  Condition number: {svd_result['condition_number']:.1f}")
    print(f"  Effective rank: {svd_result['effective_rank']}")
    print(f"Chart: {svd_result['chart']}")

    # 2. PCA
    print("\n--- 2. Principal Component Analysis ---")
    pca_result = pca_demo()
    print(f"  Explained variance: {[f'{v:.1%}' for v in pca_result['explained_variance_ratio']]}")
    print(f"  Cumulative: {[f'{v:.1%}' for v in pca_result['cumulative_variance']]}")
    print(f"Chart: {pca_result['chart']}")

    # 3. Image compression
    print("\n--- 3. Image Compression via SVD ---")
    img_result = image_compression_svd()
    print(f"  Original pixels: {img_result['original_size']}")
    print(f"Chart: {img_result['chart']}")

    # 4. Matrix decompositions
    print("\n--- 4. Matrix Decompositions (QR, LU, Cholesky) ---")
    decomp_result = matrix_decompositions()
    print(f"  QR error: {decomp_result['qr_error']:.2e}")
    print(f"  LU error: {decomp_result['lu_error']:.2e}")
    print(f"  Cholesky error: {decomp_result['cholesky_error']:.2e}")
    print(f"Chart: {decomp_result['chart']}")

    print(f"\n✅ All charts saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
