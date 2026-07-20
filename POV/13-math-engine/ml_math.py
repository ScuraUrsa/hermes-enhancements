"""
Machine Learning Math Module — Gradient Descent, Logistic Regression, SVM, K-Means, Backpropagation.

All algorithms implemented from scratch using NumPy/SciPy/SymPy.
LLM NEVER does math — all computations are numerical.

Usage:
    from ml_math import MLMath
    ml = MLMath()
    result = ml.gradient_descent(f, grad_f, x0)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from scipy import linalg, optimize, special

try:
    import sympy as sp
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class MLResult:
    """Structured result from ML math operations."""
    success: bool
    result: Any = None
    error: str = ""
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ML Math Engine
# ---------------------------------------------------------------------------

class MLMath:
    """ML math from scratch: gradient descent, logistic regression, SVM, k-means, backprop."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ==================================================================
    # GRADIENT DESCENT (batch, stochastic, mini-batch)
    # ==================================================================

    def gradient_descent(
        self,
        f: Callable[[np.ndarray], float],
        grad_f: Callable[[np.ndarray], np.ndarray],
        x0: np.ndarray,
        learning_rate: float = 0.01,
        max_iter: int = 1000,
        tol: float = 1e-6,
        method: str = "batch",
        batch_size: int = 32,
        data: Optional[tuple[np.ndarray, np.ndarray]] = None,
        loss_fn: Optional[Callable] = None,
        grad_loss_fn: Optional[Callable] = None,
    ) -> MLResult:
        """Gradient descent optimization.

        Supports three variants:
        - batch: full gradient on all data
        - stochastic: single random sample per iteration
        - mini-batch: random subset per iteration

        For batch mode, f and grad_f are used directly.
        For stochastic/mini-batch, provide data=(X, y) and loss/grad_loss functions.
        """
        try:
            x = x0.copy().astype(float)
            history = [x.copy()]
            losses = []

            if method == "batch":
                for i in range(max_iter):
                    g = np.asarray(grad_f(x), dtype=float)
                    if np.linalg.norm(g) < tol:
                        break
                    x = x - learning_rate * g
                    history.append(x.copy())
                    losses.append(float(f(x)))

            elif method in ("stochastic", "mini-batch"):
                if data is None or loss_fn is None or grad_loss_fn is None:
                    return MLResult(success=False, error="data, loss_fn, grad_loss_fn required for stochastic/mini-batch")
                X, y = data
                n_samples = len(X)
                for i in range(max_iter):
                    if method == "stochastic":
                        idx = np.random.randint(0, n_samples)
                        xi = X[idx:idx + 1]
                        yi = y[idx:idx + 1]
                    else:  # mini-batch
                        indices = np.random.choice(n_samples, min(batch_size, n_samples), replace=False)
                        xi = X[indices]
                        yi = y[indices]
                    g = np.asarray(grad_loss_fn(x, xi, yi), dtype=float)
                    if np.linalg.norm(g) < tol:
                        break
                    x = x - learning_rate * g
                    history.append(x.copy())
                    losses.append(float(loss_fn(x, X, y)))
            else:
                return MLResult(success=False, error=f"Unknown method: {method}")

            return MLResult(
                success=True,
                result={
                    "x_opt": x.tolist(),
                    "f_opt": float(f(x)) if method == "batch" else float(loss_fn(x, X, y)),
                    "iterations": len(history) - 1,
                    "history": [h.tolist() for h in history],
                    "losses": losses,
                },
                metadata={"method": method, "learning_rate": learning_rate, "tol": tol},
            )
        except Exception as e:
            return MLResult(success=False, error=str(e))

    # ==================================================================
    # LOGISTIC REGRESSION (from scratch)
    # ==================================================================

    @staticmethod
    def _sigmoid(z: np.ndarray) -> np.ndarray:
        """Numerically stable sigmoid."""
        z = np.clip(z, -500, 500)
        return 1.0 / (1.0 + np.exp(-z))

    def logistic_regression(
        self,
        X: np.ndarray,
        y: np.ndarray,
        learning_rate: float = 0.1,
        max_iter: int = 5000,
        tol: float = 1e-5,
        lambda_reg: float = 0.0,
        fit_intercept: bool = True,
    ) -> MLResult:
        """Logistic regression from scratch using gradient descent.

        Args:
            X: feature matrix (n_samples, n_features)
            y: binary labels (0 or 1)
            learning_rate: step size
            max_iter: maximum iterations
            tol: convergence tolerance
            lambda_reg: L2 regularization strength
            fit_intercept: whether to add bias term
        """
        try:
            X = np.asarray(X, dtype=float)
            y = np.asarray(y, dtype=float)
            n_samples, n_features = X.shape

            if fit_intercept:
                X = np.column_stack([np.ones(n_samples), X])
                n_features += 1

            # Initialize weights
            w = np.zeros(n_features)
            losses = []

            for i in range(max_iter):
                z = X @ w
                p = self._sigmoid(z)
                # Gradient: X.T @ (p - y) / n + lambda * w
                grad = X.T @ (p - y) / n_samples
                if lambda_reg > 0:
                    grad_reg = lambda_reg * w
                    grad_reg[0] = 0 if fit_intercept else grad_reg[0]  # Don't regularize bias
                    grad = grad + grad_reg

                w_new = w - learning_rate * grad

                # Check convergence
                if np.linalg.norm(w_new - w) < tol:
                    w = w_new
                    break
                w = w_new

                # Binary cross-entropy loss
                eps = 1e-15
                loss = -np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps))
                if lambda_reg > 0:
                    loss += 0.5 * lambda_reg * np.sum(w[1:] ** 2) if fit_intercept else 0.5 * lambda_reg * np.sum(w ** 2)
                losses.append(float(loss))

            # Predictions
            p_final = self._sigmoid(X @ w)
            y_pred = (p_final >= 0.5).astype(int)
            accuracy = float(np.mean(y_pred == y))

            return MLResult(
                success=True,
                result={
                    "weights": w.tolist(),
                    "intercept": float(w[0]) if fit_intercept else 0.0,
                    "coefficients": w[1:].tolist() if fit_intercept else w.tolist(),
                    "accuracy": accuracy,
                    "final_loss": losses[-1] if losses else None,
                    "iterations": len(losses),
                    "loss_history": losses,
                    "predictions": y_pred.tolist(),
                    "probabilities": p_final.tolist(),
                },
                metadata={
                    "n_samples": n_samples, "n_features": n_features - (1 if fit_intercept else 0),
                    "learning_rate": learning_rate, "lambda_reg": lambda_reg,
                },
            )
        except Exception as e:
            return MLResult(success=False, error=str(e))

    def logistic_decision_boundary(
        self, X: np.ndarray, y: np.ndarray, weights: np.ndarray,
        x_range: Optional[tuple] = None, n_grid: int = 200,
    ) -> MLResult:
        """Compute decision boundary grid for 2D visualization."""
        try:
            X = np.asarray(X, dtype=float)
            if X.shape[1] != 2:
                return MLResult(success=False, error="Decision boundary requires exactly 2 features")

            if x_range is None:
                x_min, x_max = X[:, 0].min() - 1, X[:, 0].max() + 1
                y_min, y_max = X[:, 1].min() - 1, X[:, 1].max() + 1
            else:
                x_min, x_max, y_min, y_max = x_range

            xx, yy = np.meshgrid(np.linspace(x_min, x_max, n_grid),
                                np.linspace(y_min, y_max, n_grid))
            grid = np.column_stack([np.ones(n_grid * n_grid), xx.ravel(), yy.ravel()])
            Z = self._sigmoid(grid @ weights).reshape(n_grid, n_grid)

            return MLResult(
                success=True,
                result={
                    "xx": xx.tolist(),
                    "yy": yy.tolist(),
                    "Z": Z.tolist(),
                    "x_range": [float(x_min), float(x_max), float(y_min), float(y_max)],
                },
            )
        except Exception as e:
            return MLResult(success=False, error=str(e))

    # ==================================================================
    # SVM (linear separable case + kernel trick)
    # ==================================================================

    def svm_linear(
        self, X: np.ndarray, y: np.ndarray, C: float = 1.0,
        learning_rate: float = 0.001, max_iter: int = 5000, tol: float = 1e-4,
    ) -> MLResult:
        """Linear SVM from scratch using subgradient descent (hinge loss).

        Args:
            X: feature matrix (n_samples, n_features)
            y: labels (-1 or +1)
            C: regularization parameter (smaller = stronger regularization)
            learning_rate: step size
            max_iter: maximum iterations
            tol: convergence tolerance
        """
        try:
            X = np.asarray(X, dtype=float)
            y = np.asarray(y, dtype=float)
            n_samples, n_features = X.shape

            # Add bias
            X_bias = np.column_stack([np.ones(n_samples), X])

            # Initialize weights
            w = np.zeros(n_features + 1)
            losses = []

            for i in range(max_iter):
                # Subgradient of hinge loss
                margins = y * (X_bias @ w)
                # Hinge loss gradient
                mask = margins < 1
                grad = -C * (X_bias[mask].T @ y[mask]) / n_samples
                grad = grad + w  # L2 regularization gradient
                grad[0] = grad[0] - w[0]  # Don't regularize bias

                w_new = w - learning_rate * grad

                if np.linalg.norm(w_new - w) < tol:
                    w = w_new
                    break
                w = w_new

                # Hinge loss
                hinge = np.maximum(0, 1 - margins)
                loss = 0.5 * np.sum(w[1:] ** 2) + C * np.mean(hinge)
                losses.append(float(loss))

            # Predictions
            y_pred = np.sign(X_bias @ w)
            y_pred[y_pred == 0] = 1  # Map zero to positive
            accuracy = float(np.mean(y_pred == y))

            # Support vectors: points with margin <= 1
            margins_final = y * (X_bias @ w)
            support_vectors = margins_final <= 1.001

            return MLResult(
                success=True,
                result={
                    "weights": w.tolist(),
                    "intercept": float(w[0]),
                    "coefficients": w[1:].tolist(),
                    "accuracy": accuracy,
                    "final_loss": losses[-1] if losses else None,
                    "iterations": len(losses),
                    "loss_history": losses,
                    "predictions": y_pred.tolist(),
                    "support_vector_indices": np.where(support_vectors)[0].tolist(),
                    "n_support_vectors": int(np.sum(support_vectors)),
                },
                metadata={"C": C, "n_samples": n_samples, "n_features": n_features},
            )
        except Exception as e:
            return MLResult(success=False, error=str(e))

    def svm_kernel(
        self, X: np.ndarray, y: np.ndarray, kernel: str = "rbf",
        gamma: float = 1.0, C: float = 1.0, degree: int = 3,
    ) -> MLResult:
        """Kernel SVM using the kernel trick with simplified dual optimization.

        Uses a simple iterative approach to solve the dual problem.
        """
        try:
            X = np.asarray(X, dtype=float)
            y = np.asarray(y, dtype=float)
            n_samples, n_features = X.shape

            # Compute kernel matrix
            if kernel == "linear":
                K = X @ X.T
            elif kernel == "rbf":
                sq_dists = (
                    np.sum(X ** 2, axis=1).reshape(-1, 1) +
                    np.sum(X ** 2, axis=1).reshape(1, -1) -
                    2 * X @ X.T
                )
                K = np.exp(-gamma * sq_dists)
            elif kernel == "poly":
                K = (X @ X.T + 1) ** degree
            else:
                return MLResult(success=False, error=f"Unknown kernel: {kernel}")

            # Simplified SMO-like optimization
            alpha = np.zeros(n_samples)
            # Gradient of dual objective
            for _ in range(1000):
                grad = np.ones(n_samples) - (alpha * y) @ (K * y[:, None])
                # Pick most violating pair
                i = np.argmax(grad * (alpha < C - 1e-8))
                j = np.argmin(grad * (alpha > 1e-8))
                if grad[i] - grad[j] < 1e-4:
                    break
                # Update
                eta = K[i, i] + K[j, j] - 2 * K[i, j]
                if eta <= 0:
                    eta = 1e-12
                old_alpha_i = alpha[i]
                old_alpha_j = alpha[j]
                alpha[j] = old_alpha_j + y[j] * (grad[i] - grad[j]) / eta
                alpha[j] = np.clip(alpha[j], 0, C)
                alpha[i] = old_alpha_i + y[i] * y[j] * (old_alpha_j - alpha[j])

            # Support vectors
            sv_mask = alpha > 1e-5
            sv_indices = np.where(sv_mask)[0]

            # Compute bias
            if len(sv_indices) > 0:
                sv_K = K[sv_indices][:, sv_indices]
                sv_y = y[sv_indices]
                sv_alpha = alpha[sv_indices]
                bias = np.mean(sv_y - (sv_alpha * sv_y) @ sv_K)
            else:
                bias = 0.0

            # Predictions
            decision = (alpha * y) @ K + bias
            y_pred = np.sign(decision)
            y_pred[y_pred == 0] = 1  # Map zero to positive
            accuracy = float(np.mean(y_pred == y))

            return MLResult(
                success=True,
                result={
                    "bias": float(bias),
                    "alpha": alpha.tolist(),
                    "support_vector_indices": sv_indices.tolist(),
                    "n_support_vectors": int(np.sum(sv_mask)),
                    "accuracy": accuracy,
                    "predictions": y_pred.tolist(),
                    "decision_values": decision.tolist(),
                },
                metadata={"kernel": kernel, "gamma": gamma, "C": C, "degree": degree},
            )
        except Exception as e:
            return MLResult(success=False, error=str(e))

    def svm_decision_boundary(
        self, X: np.ndarray, y: np.ndarray, weights: np.ndarray,
        x_range: Optional[tuple] = None, n_grid: int = 200,
    ) -> MLResult:
        """Compute SVM decision boundary grid for 2D visualization."""
        try:
            X = np.asarray(X, dtype=float)
            if X.shape[1] != 2:
                return MLResult(success=False, error="Decision boundary requires exactly 2 features")

            if x_range is None:
                x_min, x_max = X[:, 0].min() - 1, X[:, 0].max() + 1
                y_min, y_max = X[:, 1].min() - 1, X[:, 1].max() + 1
            else:
                x_min, x_max, y_min, y_max = x_range

            xx, yy = np.meshgrid(np.linspace(x_min, x_max, n_grid),
                                np.linspace(y_min, y_max, n_grid))
            grid = np.column_stack([np.ones(n_grid * n_grid), xx.ravel(), yy.ravel()])
            Z = (grid @ weights).reshape(n_grid, n_grid)

            return MLResult(
                success=True,
                result={
                    "xx": xx.tolist(),
                    "yy": yy.tolist(),
                    "Z": Z.tolist(),
                    "x_range": [float(x_min), float(x_max), float(y_min), float(y_max)],
                },
            )
        except Exception as e:
            return MLResult(success=False, error=str(e))

    # ==================================================================
    # K-MEANS CLUSTERING (elbow method)
    # ==================================================================

    def kmeans(
        self, X: np.ndarray, k: int, max_iter: int = 300,
        tol: float = 1e-4, n_init: int = 10, seed: int = 42,
    ) -> MLResult:
        """K-means clustering from scratch with multiple restarts.

        Args:
            X: data matrix (n_samples, n_features)
            k: number of clusters
            max_iter: maximum iterations per run
            tol: convergence tolerance
            n_init: number of random initializations
            seed: random seed
        """
        try:
            X = np.asarray(X, dtype=float)
            n_samples, n_features = X.shape

            # Edge case: more clusters than samples
            if k > n_samples:
                k = n_samples

            rng = np.random.RandomState(seed)

            best_inertia = np.inf
            best_labels = None
            best_centroids = None
            best_history = None

            for init_idx in range(n_init):
                # Random initialization (k-means++)
                centroids = np.zeros((k, n_features))
                # First centroid: random point
                centroids[0] = X[rng.randint(n_samples)]
                for c in range(1, k):
                    dists = np.min(
                        [np.sum((X - centroids[j]) ** 2, axis=1) for j in range(c)],
                        axis=0,
                    )
                    total = np.sum(dists)
                    if total <= 0:
                        probs = np.ones(n_samples) / n_samples
                    else:
                        probs = dists / total
                    centroids[c] = X[rng.choice(n_samples, p=probs)]

                history = [centroids.copy()]
                for it in range(max_iter):
                    # Assign clusters
                    distances = np.zeros((n_samples, k))
                    for c in range(k):
                        distances[:, c] = np.sum((X - centroids[c]) ** 2, axis=1)
                    labels = np.argmin(distances, axis=1)

                    # Update centroids
                    new_centroids = np.zeros((k, n_features))
                    for c in range(k):
                        mask = labels == c
                        if np.sum(mask) > 0:
                            new_centroids[c] = np.mean(X[mask], axis=0)
                        else:
                            new_centroids[c] = X[rng.randint(n_samples)]

                    shift = np.linalg.norm(new_centroids - centroids)
                    centroids = new_centroids
                    history.append(centroids.copy())

                    if shift < tol:
                        break

                # Compute inertia
                inertia = 0.0
                for c in range(k):
                    mask = labels == c
                    if np.sum(mask) > 0:
                        inertia += np.sum(np.sum((X[mask] - centroids[c]) ** 2, axis=1))

                if inertia < best_inertia:
                    best_inertia = inertia
                    best_labels = labels
                    best_centroids = centroids
                    best_history = history

            return MLResult(
                success=True,
                result={
                    "labels": best_labels.tolist(),
                    "centroids": best_centroids.tolist(),
                    "inertia": float(best_inertia),
                    "iterations": len(best_history) - 1,
                    "centroid_history": [[c.tolist() for c in h] for h in best_history],
                },
                metadata={"k": k, "n_samples": n_samples, "n_features": n_features, "n_init": n_init},
            )
        except Exception as e:
            return MLResult(success=False, error=str(e))

    def kmeans_elbow(
        self, X: np.ndarray, k_range: tuple = (1, 11), **kwargs,
    ) -> MLResult:
        """Elbow method: run k-means for k in range and return inertias."""
        try:
            k_min, k_max = k_range
            inertias = []
            models = []

            for k in range(k_min, k_max):
                result = self.kmeans(X, k=k, **kwargs)
                if result.success:
                    inertias.append(result.result["inertia"])
                    models.append({
                        "k": k,
                        "inertia": result.result["inertia"],
                        "centroids": result.result["centroids"],
                    })

            return MLResult(
                success=True,
                result={
                    "k_values": list(range(k_min, k_max)),
                    "inertias": inertias,
                    "models": models,
                },
                metadata={"k_range": k_range},
            )
        except Exception as e:
            return MLResult(success=False, error=str(e))

    # ==================================================================
    # BACKPROPAGATION (chain rule derivation via SymPy)
    # ==================================================================

    def backpropagation_math(
        self, expr: str = "sigmoid(w1*x1 + w2*x2 + b)",
        variables: Optional[list[str]] = None,
    ) -> MLResult:
        """Derive backpropagation gradients symbolically using SymPy.

        Computes the chain rule for a given expression with respect to
        specified variables. Demonstrates the math behind backpropagation.

        Args:
            expr: expression string (e.g., 'sigmoid(w1*x1 + w2*x2 + b)')
            variables: list of variables to differentiate w.r.t.
        """
        try:
            if not SYMPY_AVAILABLE:
                return MLResult(success=False, error="SymPy required for symbolic backpropagation")

            if variables is None:
                variables = ["w1", "w2", "b"]

            # Define symbols
            syms = {v: sp.Symbol(v) for v in variables}
            syms["x1"] = sp.Symbol("x1")
            syms["x2"] = sp.Symbol("x2")

            # Define sigmoid
            def sigmoid(z):
                return 1 / (1 + sp.exp(-z))

            # Parse expression
            local_dict = {"sigmoid": sigmoid, **syms}
            f = eval(expr, {"__builtins__": {}}, local_dict)

            # Compute gradients
            gradients = {}
            steps = []
            steps.append(f"Expression: f = {sp.latex(f)}")

            for var in variables:
                grad = sp.diff(f, syms[var])
                grad_simplified = sp.simplify(grad)
                gradients[var] = {
                    "raw": str(grad),
                    "simplified": str(grad_simplified),
                    "latex": sp.latex(grad_simplified),
                }
                steps.append(f"∂f/∂{var} = {sp.latex(grad_simplified)}")

            # Also compute second-order (Hessian diagonal)
            hessian_diag = {}
            for var in variables:
                h = sp.diff(f, syms[var], 2)
                hessian_diag[var] = str(sp.simplify(h))

            return MLResult(
                success=True,
                result={
                    "expression": str(f),
                    "expression_latex": sp.latex(f),
                    "gradients": gradients,
                    "hessian_diagonal": hessian_diag,
                    "steps": steps,
                },
                metadata={"expr": expr, "variables": variables},
            )
        except Exception as e:
            return MLResult(success=False, error=str(e))

    def neural_network_gradients(
        self, layer_sizes: list[int] = None,
    ) -> MLResult:
        """Demonstrate backpropagation through a small neural network.

        Computes forward pass and backprop gradients for a 2-layer network
        with sigmoid activation, using NumPy.
        """
        try:
            if layer_sizes is None:
                layer_sizes = [2, 3, 1]  # input=2, hidden=3, output=1

            rng = np.random.RandomState(42)
            n_layers = len(layer_sizes) - 1

            # Initialize weights and biases
            weights = []
            biases = []
            for i in range(n_layers):
                w = rng.randn(layer_sizes[i + 1], layer_sizes[i]) * 0.1
                b = np.zeros((layer_sizes[i + 1], 1))
                weights.append(w)
                biases.append(b)

            # Sample input
            x = np.array([[0.5], [0.3]])

            # ---- Forward pass ----
            activations = [x]
            zs = []

            for i in range(n_layers):
                z = weights[i] @ activations[-1] + biases[i]
                zs.append(z)
                a = self._sigmoid(z)
                activations.append(a)

            # ---- Backward pass ----
            # Target: let's say we want output = 1.0
            y_target = np.array([[1.0]])

            # Output layer error: dC/da * da/dz = (a - y) * sigmoid'(z)
            delta = (activations[-1] - y_target) * (activations[-1] * (1 - activations[-1]))

            nabla_w = [None] * n_layers
            nabla_b = [None] * n_layers

            for i in range(n_layers - 1, -1, -1):
                nabla_w[i] = delta @ activations[i].T
                nabla_b[i] = delta
                if i > 0:
                    delta = (weights[i].T @ delta) * (activations[i] * (1 - activations[i]))

            return MLResult(
                success=True,
                result={
                    "layer_sizes": layer_sizes,
                    "input": x.flatten().tolist(),
                    "forward_activations": [a.flatten().tolist() for a in activations],
                    "forward_zs": [z.flatten().tolist() for z in zs],
                    "output": float(activations[-1][0, 0]),
                    "target": float(y_target[0, 0]),
                    "loss": float(0.5 * (activations[-1][0, 0] - y_target[0, 0]) ** 2),
                    "weight_gradients": [nw.tolist() for nw in nabla_w],
                    "bias_gradients": [nb.flatten().tolist() for nb in nabla_b],
                },
                metadata={"n_layers": n_layers, "activation": "sigmoid"},
            )
        except Exception as e:
            return MLResult(success=False, error=str(e))

    # ==================================================================
    # Utility: generate synthetic datasets
    # ==================================================================

    @staticmethod
    def make_classification(
        n_samples: int = 200, n_features: int = 2, separable: bool = True,
        seed: int = 42,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Generate synthetic binary classification dataset."""
        rng = np.random.RandomState(seed)
        if separable:
            # Two well-separated blobs
            X1 = rng.randn(n_samples // 2, n_features) + np.array([2, 2])
            X2 = rng.randn(n_samples // 2, n_features) + np.array([-2, -2])
            X = np.vstack([X1, X2])
            y = np.array([1] * (n_samples // 2) + [0] * (n_samples // 2))
        else:
            # Overlapping blobs
            X1 = rng.randn(n_samples // 2, n_features) + np.array([1, 1])
            X2 = rng.randn(n_samples // 2, n_features) + np.array([-1, -1])
            X = np.vstack([X1, X2])
            y = np.array([1] * (n_samples // 2) + [0] * (n_samples // 2))
        # Shuffle
        idx = rng.permutation(n_samples)
        return X[idx], y[idx]

    @staticmethod
    def make_blobs(
        n_samples: int = 300, n_features: int = 2, centers: int = 3,
        cluster_std: float = 1.0, seed: int = 42,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Generate isotropic Gaussian blobs for clustering."""
        rng = np.random.RandomState(seed)
        # Generate centers on a circle
        angles = np.linspace(0, 2 * np.pi, centers, endpoint=False)
        center_points = np.column_stack([np.cos(angles), np.sin(angles)]) * 5
        X = np.zeros((n_samples, n_features))
        y = np.zeros(n_samples, dtype=int)
        samples_per_center = n_samples // centers
        for i in range(centers):
            start = i * samples_per_center
            end = start + samples_per_center if i < centers - 1 else n_samples
            n_c = end - start
            X[start:end] = rng.randn(n_c, n_features) * cluster_std + center_points[i]
            y[start:end] = i
        idx = rng.permutation(n_samples)
        return X[idx], y[idx]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    ml = MLMath()

    if len(sys.argv) < 2:
        print("Usage: python ml_math.py <operation> [args...]")
        print("Operations: gd, logistic, svm_linear, svm_kernel, kmeans, elbow, backprop_math, nn_gradients")
        sys.exit(1)

    op = sys.argv[1]

    if op == "gd":
        # Minimize f(x) = (x-3)^2
        f = lambda x: float((x[0] - 3) ** 2)
        grad_f = lambda x: np.array([2 * (x[0] - 3)])
        r = ml.gradient_descent(f, grad_f, np.array([0.0]), learning_rate=0.1)
    elif op == "logistic":
        X, y = ml.make_classification(200)
        r = ml.logistic_regression(X, y)
    elif op == "svm_linear":
        X, y = ml.make_classification(200)
        y_svm = np.where(y == 0, -1, 1)
        r = ml.svm_linear(X, y_svm)
    elif op == "svm_kernel":
        X, y = ml.make_classification(200, separable=False)
        y_svm = np.where(y == 0, -1, 1)
        r = ml.svm_kernel(X, y_svm, kernel="rbf", gamma=0.5)
    elif op == "kmeans":
        X, _ = ml.make_blobs(300, centers=3)
        r = ml.kmeans(X, k=3)
    elif op == "elbow":
        X, _ = ml.make_blobs(300, centers=5)
        r = ml.kmeans_elbow(X, k_range=(1, 11))
    elif op == "backprop_math":
        r = ml.backpropagation_math()
    elif op == "nn_gradients":
        r = ml.neural_network_gradients()
    else:
        r = MLResult(success=False, error=f"Unknown operation: {op}")

    if isinstance(r, MLResult):
        print(json.dumps({"success": r.success, "result": r.result, "error": r.error, "metadata": r.metadata}, indent=2, default=str))
    else:
        print(json.dumps(r, indent=2, default=str))
