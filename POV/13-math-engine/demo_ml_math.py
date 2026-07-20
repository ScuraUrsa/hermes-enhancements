"""
Machine Learning Math Demo — Gradient Descent, Logistic Regression, SVM, K-Means, Backpropagation.

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
from ml_math import MLMath

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def main():
    print("=" * 60)
    print("MACHINE LEARNING MATH DEMO")
    print("=" * 60)

    ml = MLMath()

    # ==================================================================
    # 1. GRADIENT DESCENT
    # ==================================================================
    print("\n--- 1. Gradient Descent (Batch, Stochastic, Mini-Batch) ---")

    # Batch: minimize f(x,y) = (x-3)^2 + (y+2)^2
    f_batch = lambda w: float((w[0] - 3) ** 2 + (w[1] + 2) ** 2)
    grad_batch = lambda w: np.array([2 * (w[0] - 3), 2 * (w[1] + 2)])

    gd_batch = ml.gradient_descent(f_batch, grad_batch, np.array([0.0, 0.0]),
                                   learning_rate=0.1, max_iter=200, method="batch")
    if gd_batch.success:
        print(f"  Batch GD: x* = {gd_batch.result['x_opt']}, f* = {gd_batch.result['f_opt']:.6f}, "
              f"iters = {gd_batch.result['iterations']}")

    # Stochastic/mini-batch: linear regression
    rng = np.random.RandomState(42)
    X_lr = rng.randn(200, 1) * 2
    y_lr = 3.0 * X_lr.flatten() + 1.0 + rng.randn(200) * 0.5

    def loss_fn(w, X, y):
        pred = X @ w[1:] + w[0]
        return float(np.mean((pred - y) ** 2))

    def grad_loss_fn(w, X, y):
        n = len(X)
        pred = X @ w[1:] + w[0]
        err = pred - y
        dw0 = np.array([2 * np.mean(err)])
        dw1 = 2 * X.T @ err / n
        return np.concatenate([dw0, dw1])

    gd_sgd = ml.gradient_descent(
        f_batch, grad_batch, np.array([0.0, 0.0]),
        learning_rate=0.01, max_iter=500, method="stochastic",
        data=(X_lr, y_lr), loss_fn=loss_fn, grad_loss_fn=grad_loss_fn,
    )
    if gd_sgd.success:
        print(f"  SGD: w* = {gd_sgd.result['x_opt']}, loss = {gd_sgd.result['f_opt']:.6f}, "
              f"iters = {gd_sgd.result['iterations']}")

    gd_mb = ml.gradient_descent(
        f_batch, grad_batch, np.array([0.0, 0.0]),
        learning_rate=0.01, max_iter=500, method="mini-batch",
        batch_size=32, data=(X_lr, y_lr),
        loss_fn=loss_fn, grad_loss_fn=grad_loss_fn,
    )
    if gd_mb.success:
        print(f"  Mini-batch: w* = {gd_mb.result['x_opt']}, loss = {gd_mb.result['f_opt']:.6f}, "
              f"iters = {gd_mb.result['iterations']}")

    # ==================================================================
    # 2. LOGISTIC REGRESSION
    # ==================================================================
    print("\n--- 2. Logistic Regression (from scratch) ---")

    X_cls, y_cls = ml.make_classification(300, separable=True, seed=42)
    lr_model = ml.logistic_regression(X_cls, y_cls, learning_rate=0.1, max_iter=5000)
    if lr_model.success:
        print(f"  Accuracy: {lr_model.result['accuracy']:.3f}")
        print(f"  Weights: {[f'{w:.3f}' for w in lr_model.result['weights']]}")
        print(f"  Iterations: {lr_model.result['iterations']}")

    # Decision boundary
    db = ml.logistic_decision_boundary(X_cls, y_cls, np.array(lr_model.result["weights"]))
    if db.success:
        print(f"  Decision boundary computed: grid {len(db.result['Z'])}x{len(db.result['Z'][0])}")

    # ==================================================================
    # 3. SVM (Linear + Kernel)
    # ==================================================================
    print("\n--- 3. SVM (Linear Separable + Kernel Trick) ---")

    # Linear SVM
    X_svm, y_svm_raw = ml.make_classification(200, separable=True, seed=42)
    y_svm = np.where(y_svm_raw == 0, -1, 1)

    svm_lin = ml.svm_linear(X_svm, y_svm, C=1.0, learning_rate=0.001, max_iter=5000)
    if svm_lin.success:
        print(f"  Linear SVM accuracy: {svm_lin.result['accuracy']:.3f}")
        print(f"  Support vectors: {svm_lin.result['n_support_vectors']}")
        print(f"  Weights: {[f'{w:.3f}' for w in svm_lin.result['weights']]}")

    # Kernel SVM (RBF)
    X_nonsep, y_nonsep_raw = ml.make_classification(200, separable=False, seed=42)
    y_nonsep = np.where(y_nonsep_raw == 0, -1, 1)

    svm_rbf = ml.svm_kernel(X_nonsep, y_nonsep, kernel="rbf", gamma=0.5, C=1.0)
    if svm_rbf.success:
        print(f"  RBF SVM accuracy: {svm_rbf.result['accuracy']:.3f}")
        print(f"  Support vectors: {svm_rbf.result['n_support_vectors']}")

    # SVM decision boundary
    svm_db = ml.svm_decision_boundary(X_svm, y_svm, np.array(svm_lin.result["weights"]))
    if svm_db.success:
        print(f"  SVM decision boundary computed")

    # ==================================================================
    # 4. K-MEANS CLUSTERING
    # ==================================================================
    print("\n--- 4. K-Means Clustering + Elbow Method ---")

    X_km, y_km_true = ml.make_blobs(300, centers=3, cluster_std=1.2, seed=42)
    km = ml.kmeans(X_km, k=3, n_init=10, seed=42)
    if km.success:
        print(f"  K=3 inertia: {km.result['inertia']:.1f}")
        print(f"  Iterations: {km.result['iterations']}")
        print(f"  Centroids: {[[f'{c:.1f}' for c in ct] for ct in km.result['centroids']]}")

    # Elbow method
    elbow = ml.kmeans_elbow(X_km, k_range=(1, 11), n_init=5, seed=42)
    if elbow.success:
        print(f"  Elbow inertias: {[f'{v:.0f}' for v in elbow.result['inertias']]}")

    # ==================================================================
    # 5. BACKPROPAGATION MATH
    # ==================================================================
    print("\n--- 5. Backpropagation Math (Chain Rule via SymPy) ---")

    bp_math = ml.backpropagation_math(
        expr="sigmoid(w1*x1 + w2*x2 + b)",
        variables=["w1", "w2", "b"],
    )
    if bp_math.success:
        print(f"  Expression: {bp_math.result['expression']}")
        for var, grad in bp_math.result["gradients"].items():
            print(f"  ∂f/∂{var} = {grad['simplified']}")

    # Neural network gradients
    nn_grad = ml.neural_network_gradients(layer_sizes=[2, 3, 1])
    if nn_grad.success:
        print(f"  NN output: {nn_grad.result['output']:.4f}, target: {nn_grad.result['target']}")
        print(f"  Loss: {nn_grad.result['loss']:.6f}")
        print(f"  Weight gradients shape: {[np.array(g).shape for g in nn_grad.result['weight_gradients']]}")

    # ==================================================================
    # PLOTS
    # ==================================================================

    # --- Plot 1: Gradient Descent Convergence ---
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Batch GD: contour + path
    ax = axes[0]
    x_vals = np.linspace(-1, 5, 100)
    y_vals = np.linspace(-5, 1, 100)
    Xg, Yg = np.meshgrid(x_vals, y_vals)
    Zg = (Xg - 3) ** 2 + (Yg + 2) ** 2
    ax.contour(Xg, Yg, Zg, levels=20, cmap="viridis", alpha=0.6)
    if gd_batch.success:
        hist = np.array(gd_batch.result["history"])
        ax.plot(hist[:, 0], hist[:, 1], "ro-", markersize=3, linewidth=1, label="Batch GD path")
        ax.plot(hist[-1, 0], hist[-1, 1], "r*", markersize=15, label="Optimum")
    ax.set_title("Batch Gradient Descent", fontweight="bold")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Loss curves
    ax = axes[1]
    if gd_batch.success:
        ax.plot(gd_batch.result["losses"], linewidth=1.5, label="Batch GD", color="blue")
    if gd_sgd.success:
        ax.plot(gd_sgd.result["losses"], linewidth=0.8, alpha=0.7, label="SGD", color="orange")
    if gd_mb.success:
        ax.plot(gd_mb.result["losses"], linewidth=0.8, alpha=0.7, label="Mini-Batch", color="green")
    ax.set_title("Loss Convergence", fontweight="bold")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Loss")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_yscale("log")

    # Linear regression fit
    ax = axes[2]
    ax.scatter(X_lr.flatten(), y_lr, alpha=0.4, s=10, color="gray")
    x_line = np.linspace(X_lr.min(), X_lr.max(), 100).reshape(-1, 1)
    if gd_mb.success:
        w = gd_mb.result["x_opt"]
        y_line = x_line.flatten() * w[1] + w[0]
        ax.plot(x_line, y_line, "r-", linewidth=2, label="Mini-Batch fit")
    ax.set_title("Linear Regression (Mini-Batch GD)", fontweight="bold")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "ml_gradient_descent.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n✅ Chart saved: {path}")

    # --- Plot 2: Logistic Regression Decision Boundary ---
    fig, ax = plt.subplots(figsize=(8, 7))

    if lr_model.success and db.success:
        xx = np.array(db.result["xx"])
        yy = np.array(db.result["yy"])
        Z = np.array(db.result["Z"])
        ax.contourf(xx, yy, Z, levels=20, cmap="RdBu", alpha=0.6)
        cs = ax.contour(xx, yy, Z, levels=[0.5], colors="black", linewidths=2)
        ax.clabel(cs, fmt="Decision boundary")

    # Scatter data
    ax.scatter(X_cls[y_cls == 0, 0], X_cls[y_cls == 0, 1],
               c="blue", edgecolors="k", alpha=0.7, label="Class 0", s=40)
    ax.scatter(X_cls[y_cls == 1, 0], X_cls[y_cls == 1, 1],
               c="red", edgecolors="k", alpha=0.7, label="Class 1", s=40)

    # Mark misclassified
    if lr_model.success:
        preds = np.array(lr_model.result["predictions"])
        mis = preds != y_cls
        if np.any(mis):
            ax.scatter(X_cls[mis, 0], X_cls[mis, 1],
                       facecolors="none", edgecolors="yellow", s=100, linewidths=2, label="Misclassified")

    ax.set_title("Logistic Regression — Decision Boundary", fontweight="bold", fontsize=14)
    ax.set_xlabel("Feature 1")
    ax.set_ylabel("Feature 2")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "ml_logistic_regression.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path}")

    # --- Plot 3: SVM Linear + Kernel ---
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Linear SVM
    ax = axes[0]
    if svm_lin.success and svm_db.success:
        xx = np.array(svm_db.result["xx"])
        yy = np.array(svm_db.result["yy"])
        Z = np.array(svm_db.result["Z"])
        ax.contourf(xx, yy, Z, levels=[-10, 0, 10], colors=["#ffcccc", "#ccccff"], alpha=0.5)
        ax.contour(xx, yy, Z, levels=[-1, 0, 1], colors=["red", "black", "blue"],
                   linestyles=["--", "-", "--"], linewidths=[1, 2, 1])

    ax.scatter(X_svm[y_svm == -1, 0], X_svm[y_svm == -1, 1],
               c="blue", edgecolors="k", alpha=0.7, label="Class -1", s=40)
    ax.scatter(X_svm[y_svm == 1, 0], X_svm[y_svm == 1, 1],
               c="red", edgecolors="k", alpha=0.7, label="Class +1", s=40)

    # Highlight support vectors
    if svm_lin.success:
        sv_idx = svm_lin.result["support_vector_indices"]
        ax.scatter(X_svm[sv_idx, 0], X_svm[sv_idx, 1],
                   facecolors="none", edgecolors="lime", s=120, linewidths=2, label="Support Vectors")

    ax.set_title("Linear SVM — Separable Case", fontweight="bold", fontsize=12)
    ax.set_xlabel("Feature 1")
    ax.set_ylabel("Feature 2")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Kernel SVM (RBF)
    ax = axes[1]
    if svm_rbf.success:
        # Create a grid for RBF decision visualization
        x_min, x_max = X_nonsep[:, 0].min() - 1, X_nonsep[:, 0].max() + 1
        y_min, y_max = X_nonsep[:, 1].min() - 1, X_nonsep[:, 1].max() + 1
        xx, yy = np.meshgrid(np.linspace(x_min, x_max, 100),
                            np.linspace(y_min, y_max, 100))
        grid = np.column_stack([xx.ravel(), yy.ravel()])

        # RBF kernel between grid and support vectors
        sv_idx = svm_rbf.result["support_vector_indices"]
        X_sv = X_nonsep[sv_idx]
        alpha_sv = np.array(svm_rbf.result["alpha"])[sv_idx]
        y_sv = y_nonsep[sv_idx]
        gamma = 0.5

        sq_dists = (np.sum(grid ** 2, axis=1).reshape(-1, 1) +
                    np.sum(X_sv ** 2, axis=1).reshape(1, -1) -
                    2 * grid @ X_sv.T)
        K_grid = np.exp(-gamma * sq_dists)
        decision = K_grid @ (alpha_sv * y_sv) + svm_rbf.result["bias"]
        Z = decision.reshape(xx.shape)

        ax.contourf(xx, yy, Z, levels=[-10, 0, 10], colors=["#ffcccc", "#ccccff"], alpha=0.5)
        ax.contour(xx, yy, Z, levels=[0], colors="black", linewidths=2)

    ax.scatter(X_nonsep[y_nonsep == -1, 0], X_nonsep[y_nonsep == -1, 1],
               c="blue", edgecolors="k", alpha=0.7, label="Class -1", s=40)
    ax.scatter(X_nonsep[y_nonsep == 1, 0], X_nonsep[y_nonsep == 1, 1],
               c="red", edgecolors="k", alpha=0.7, label="Class +1", s=40)

    if svm_rbf.success:
        ax.scatter(X_nonsep[sv_idx, 0], X_nonsep[sv_idx, 1],
                   facecolors="none", edgecolors="lime", s=120, linewidths=2, label="Support Vectors")

    ax.set_title("Kernel SVM (RBF) — Non-separable Case", fontweight="bold", fontsize=12)
    ax.set_xlabel("Feature 1")
    ax.set_ylabel("Feature 2")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "ml_svm.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path}")

    # --- Plot 4: K-Means Clustering + Elbow ---
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # K-Means clustering
    ax = axes[0]
    if km.success:
        labels = np.array(km.result["labels"])
        centroids = np.array(km.result["centroids"])
        colors = plt.cm.tab10(np.linspace(0, 1, 10))
        for c in range(3):
            mask = labels == c
            ax.scatter(X_km[mask, 0], X_km[mask, 1],
                       c=[colors[c]], alpha=0.6, s=30, label=f"Cluster {c}")
        ax.scatter(centroids[:, 0], centroids[:, 1],
                   c="red", marker="X", s=200, edgecolors="black", linewidths=2, label="Centroids")

        # Draw centroid history
        if "centroid_history" in km.result:
            for hist in km.result["centroid_history"]:
                hist_arr = np.array(hist)
                if len(hist_arr) > 1:
                    for c in range(min(3, hist_arr.shape[0])):
                        ax.plot(hist_arr[:2, 0], hist_arr[:2, 1], "k--", alpha=0.2, linewidth=0.5)

    ax.set_title("K-Means Clustering (k=3)", fontweight="bold", fontsize=12)
    ax.set_xlabel("Feature 1")
    ax.set_ylabel("Feature 2")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Elbow method
    ax = axes[1]
    if elbow.success:
        ax.plot(elbow.result["k_values"], elbow.result["inertias"], "bo-", linewidth=2, markersize=8)
        ax.set_xlabel("Number of clusters (k)")
        ax.set_ylabel("Inertia (WCSS)")
        ax.set_title("Elbow Method for Optimal k", fontweight="bold", fontsize=12)
        ax.grid(True, alpha=0.3)
        # Annotate
        for k_val, inertia in zip(elbow.result["k_values"], elbow.result["inertias"]):
            ax.annotate(f"{inertia:.0f}", (k_val, inertia), textcoords="offset points",
                       xytext=(0, 10), ha="center", fontsize=8)

    plt.tight_layout()
    path = OUTPUT_DIR / "ml_kmeans.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path}")

    # --- Plot 5: Backpropagation Visualization ---
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Neural network diagram (text-based)
    ax = axes[0]
    ax.axis("off")
    if nn_grad.success:
        sizes = nn_grad.result["layer_sizes"]
        text = "Neural Network: Backpropagation\n\n"
        text += f"Architecture: {sizes[0]} → {sizes[1]} → {sizes[2]}\n\n"
        text += "Forward Pass:\n"
        for i, a in enumerate(nn_grad.result["forward_activations"]):
            text += f"  a[{i}] = {[f'{v:.3f}' for v in a]}\n"
        text += f"\nOutput: {nn_grad.result['output']:.4f}\n"
        text += f"Target: {nn_grad.result['target']}\n"
        text += f"Loss (MSE): {nn_grad.result['loss']:.6f}\n\n"
        text += "Backward Pass (Gradients):\n"
        for i, (wg, bg) in enumerate(zip(nn_grad.result["weight_gradients"],
                                          nn_grad.result["bias_gradients"])):
            text += f"  ∇W[{i}]: {[[f'{v:.4f}' for v in row] for row in wg]}\n"
            text += f"  ∇b[{i}]: {[f'{v:.4f}' for v in bg]}\n"
        ax.text(0.05, 0.95, text, transform=ax.transAxes, fontsize=9,
                verticalalignment="top", fontfamily="monospace",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    # Symbolic backpropagation
    ax = axes[1]
    ax.axis("off")
    if bp_math.success:
        text = "Symbolic Backpropagation (Chain Rule)\n\n"
        text += f"f = {bp_math.result['expression']}\n\n"
        text += "Gradients:\n"
        for var, grad in bp_math.result["gradients"].items():
            text += f"  ∂f/∂{var} = {grad['simplified']}\n"
        text += "\nHessian Diagonal:\n"
        for var, h in bp_math.result["hessian_diagonal"].items():
            text += f"  ∂²f/∂{var}² = {h}\n"
        text += "\nSteps:\n"
        for step in bp_math.result["steps"]:
            text += f"  {step}\n"
        ax.text(0.05, 0.95, text, transform=ax.transAxes, fontsize=9,
                verticalalignment="top", fontfamily="monospace",
                bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.5))

    plt.tight_layout()
    path = OUTPUT_DIR / "ml_backpropagation.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path}")

    # --- Plot 6: Summary Dashboard ---
    fig = plt.figure(figsize=(20, 14))
    gs = fig.add_gridspec(3, 3, hspace=0.4, wspace=0.35)

    # GD convergence
    ax = fig.add_subplot(gs[0, 0])
    if gd_batch.success:
        ax.plot(gd_batch.result["losses"], linewidth=1.5, color="blue", label="Batch")
    if gd_sgd.success:
        ax.plot(gd_sgd.result["losses"], linewidth=0.5, alpha=0.7, color="orange", label="SGD")
    if gd_mb.success:
        ax.plot(gd_mb.result["losses"], linewidth=0.5, alpha=0.7, color="green", label="Mini-Batch")
    ax.set_title("Gradient Descent Convergence", fontsize=10, fontweight="bold")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Loss")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)
    ax.set_yscale("log")

    # Logistic regression
    ax = fig.add_subplot(gs[0, 1])
    if lr_model.success and db.success:
        xx = np.array(db.result["xx"])
        yy = np.array(db.result["yy"])
        Z = np.array(db.result["Z"])
        ax.contourf(xx, yy, Z, levels=20, cmap="RdBu", alpha=0.6)
        ax.contour(xx, yy, Z, levels=[0.5], colors="black", linewidths=1.5)
    ax.scatter(X_cls[y_cls == 0, 0], X_cls[y_cls == 0, 1], c="blue", alpha=0.5, s=15)
    ax.scatter(X_cls[y_cls == 1, 0], X_cls[y_cls == 1, 1], c="red", alpha=0.5, s=15)
    ax.set_title("Logistic Regression", fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # Linear SVM
    ax = fig.add_subplot(gs[0, 2])
    if svm_lin.success and svm_db.success:
        xx = np.array(svm_db.result["xx"])
        yy = np.array(svm_db.result["yy"])
        Z = np.array(svm_db.result["Z"])
        ax.contourf(xx, yy, Z, levels=[-10, 0, 10], colors=["#ffcccc", "#ccccff"], alpha=0.5)
    ax.scatter(X_svm[y_svm == -1, 0], X_svm[y_svm == -1, 1], c="blue", alpha=0.5, s=15)
    ax.scatter(X_svm[y_svm == 1, 0], X_svm[y_svm == 1, 1], c="red", alpha=0.5, s=15)
    ax.set_title("Linear SVM", fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # RBF SVM
    ax = fig.add_subplot(gs[1, 0])
    if svm_rbf.success:
        x_min, x_max = X_nonsep[:, 0].min() - 1, X_nonsep[:, 0].max() + 1
        y_min, y_max = X_nonsep[:, 1].min() - 1, X_nonsep[:, 1].max() + 1
        xx, yy = np.meshgrid(np.linspace(x_min, x_max, 80), np.linspace(y_min, y_max, 80))
        grid = np.column_stack([xx.ravel(), yy.ravel()])
        sv_idx = svm_rbf.result["support_vector_indices"]
        X_sv = X_nonsep[sv_idx]
        alpha_sv = np.array(svm_rbf.result["alpha"])[sv_idx]
        y_sv = y_nonsep[sv_idx]
        sq_dists = (np.sum(grid ** 2, axis=1).reshape(-1, 1) +
                    np.sum(X_sv ** 2, axis=1).reshape(1, -1) - 2 * grid @ X_sv.T)
        K_grid = np.exp(-0.5 * sq_dists)
        decision = K_grid @ (alpha_sv * y_sv) + svm_rbf.result["bias"]
        Z = decision.reshape(xx.shape)
        ax.contourf(xx, yy, Z, levels=[-10, 0, 10], colors=["#ffcccc", "#ccccff"], alpha=0.5)
    ax.scatter(X_nonsep[y_nonsep == -1, 0], X_nonsep[y_nonsep == -1, 1], c="blue", alpha=0.5, s=15)
    ax.scatter(X_nonsep[y_nonsep == 1, 0], X_nonsep[y_nonsep == 1, 1], c="red", alpha=0.5, s=15)
    ax.set_title("Kernel SVM (RBF)", fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # K-Means
    ax = fig.add_subplot(gs[1, 1])
    if km.success:
        labels = np.array(km.result["labels"])
        centroids = np.array(km.result["centroids"])
        for c in range(3):
            mask = labels == c
            ax.scatter(X_km[mask, 0], X_km[mask, 1], alpha=0.5, s=15, label=f"C{c}")
        ax.scatter(centroids[:, 0], centroids[:, 1], c="red", marker="X", s=100, edgecolors="black")
    ax.set_title("K-Means (k=3)", fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # Elbow
    ax = fig.add_subplot(gs[1, 2])
    if elbow.success:
        ax.plot(elbow.result["k_values"], elbow.result["inertias"], "bo-", linewidth=2)
    ax.set_title("Elbow Method", fontsize=10, fontweight="bold")
    ax.set_xlabel("k")
    ax.set_ylabel("Inertia")
    ax.grid(True, alpha=0.3)

    # Loss history (logistic)
    ax = fig.add_subplot(gs[2, 0])
    if lr_model.success:
        ax.plot(lr_model.result["loss_history"], linewidth=1, color="purple")
    ax.set_title("Logistic Regression Loss", fontsize=10, fontweight="bold")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Cross-Entropy Loss")
    ax.grid(True, alpha=0.3)

    # SVM loss
    ax = fig.add_subplot(gs[2, 1])
    if svm_lin.success:
        ax.plot(svm_lin.result["loss_history"], linewidth=1, color="darkred")
    ax.set_title("SVM Hinge Loss", fontsize=10, fontweight="bold")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Loss")
    ax.grid(True, alpha=0.3)

    # Backprop summary
    ax = fig.add_subplot(gs[2, 2])
    ax.axis("off")
    if nn_grad.success and bp_math.success:
        text = "Backpropagation Summary\n\n"
        text += f"NN: {nn_grad.result['layer_sizes'][0]}→{nn_grad.result['layer_sizes'][1]}→{nn_grad.result['layer_sizes'][2]}\n"
        text += f"Output: {nn_grad.result['output']:.4f}\n"
        text += f"Loss: {nn_grad.result['loss']:.6f}\n\n"
        text += "Symbolic Gradients:\n"
        for var, grad in bp_math.result["gradients"].items():
            text += f"∂f/∂{var} = {grad['simplified']}\n"
        ax.text(0.05, 0.95, text, transform=ax.transAxes, fontsize=8,
                verticalalignment="top", fontfamily="monospace",
                bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.7))

    fig.suptitle("Machine Learning Math Dashboard", fontsize=16, fontweight="bold", y=1.01)
    plt.tight_layout()
    path = OUTPUT_DIR / "ml_math_dashboard.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path}")

    print("\n" + "=" * 60)
    print("ML MATH DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
