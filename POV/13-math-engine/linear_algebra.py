"""
Linear Algebra Module — Eigenvalues, SVD, PCA, Least Squares, Matrix Decompositions.

All computations use NumPy/SciPy/SymPy — LLM NEVER does math.
Provides both numerical (NumPy/SciPy) and symbolic (SymPy) paths.

Usage:
    from linear_algebra import LinearAlgebra
    la = LinearAlgebra()
    evals, evecs = la.eigen(A)
    U, S, Vt = la.svd(A)
    pca_result = la.pca(data, n_components=2)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import scipy.linalg
import sympy as sp


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class LAResult:
    """Structured result from linear algebra operations."""
    success: bool
    result: Any = None
    error: str = ""
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Linear Algebra Engine
# ---------------------------------------------------------------------------

class LinearAlgebra:
    """Numerical and symbolic linear algebra operations."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Matrix Creation ----

    @staticmethod
    def from_list(data: list[list[float]]) -> np.ndarray:
        """Create numpy array from nested list."""
        return np.array(data, dtype=float)

    @staticmethod
    def random_matrix(m: int, n: int, seed: int = 42) -> np.ndarray:
        """Create random m×n matrix."""
        rng = np.random.RandomState(seed)
        return rng.randn(m, n)

    @staticmethod
    def hilbert_matrix(n: int) -> np.ndarray:
        """Create n×n Hilbert matrix (ill-conditioned)."""
        return scipy.linalg.hilbert(n)

    # ---- Basic Matrix Operations ----

    @staticmethod
    def determinant(A: np.ndarray) -> LAResult:
        """Compute determinant of square matrix."""
        try:
            if A.shape[0] != A.shape[1]:
                return LAResult(success=False, error="Matrix must be square")
            det = float(np.linalg.det(A))
            return LAResult(success=True, result=det, metadata={"shape": A.shape})
        except Exception as e:
            return LAResult(success=False, error=str(e))

    @staticmethod
    def inverse(A: np.ndarray) -> LAResult:
        """Compute matrix inverse."""
        try:
            if A.shape[0] != A.shape[1]:
                return LAResult(success=False, error="Matrix must be square")
            inv = np.linalg.inv(A)
            return LAResult(success=True, result=inv, metadata={"shape": A.shape})
        except np.linalg.LinAlgError as e:
            return LAResult(success=False, error=f"Singular matrix: {e}")
        except Exception as e:
            return LAResult(success=False, error=str(e))

    @staticmethod
    def rank(A: np.ndarray) -> LAResult:
        """Compute matrix rank."""
        try:
            r = int(np.linalg.matrix_rank(A))
            return LAResult(success=True, result=r, metadata={"shape": A.shape})
        except Exception as e:
            return LAResult(success=False, error=str(e))

    @staticmethod
    def condition_number(A: np.ndarray) -> LAResult:
        """Compute condition number (2-norm)."""
        try:
            cond = float(np.linalg.cond(A))
            return LAResult(success=True, result=cond, metadata={"shape": A.shape})
        except Exception as e:
            return LAResult(success=False, error=str(e))

    @staticmethod
    def trace(A: np.ndarray) -> LAResult:
        """Compute trace of matrix."""
        try:
            tr = float(np.trace(A))
            return LAResult(success=True, result=tr, metadata={"shape": A.shape})
        except Exception as e:
            return LAResult(success=False, error=str(e))

    @staticmethod
    def norm(A: np.ndarray, ord: str | int = "fro") -> LAResult:
        """Compute matrix norm. ord='fro' for Frobenius, 2 for spectral, etc."""
        try:
            n = float(np.linalg.norm(A, ord=ord))
            return LAResult(success=True, result=n, metadata={"shape": A.shape, "ord": str(ord)})
        except Exception as e:
            return LAResult(success=False, error=str(e))

    # ---- Eigenvalues & Eigenvectors ----

    @staticmethod
    def eigen(A: np.ndarray) -> LAResult:
        """Compute eigenvalues and eigenvectors of a square matrix.

        Returns eigenvalues (1D array) and eigenvectors (columns of matrix).
        """
        try:
            if A.shape[0] != A.shape[1]:
                return LAResult(success=False, error="Matrix must be square")
            eigenvalues, eigenvectors = np.linalg.eig(A)
            return LAResult(
                success=True,
                result={
                    "eigenvalues": eigenvalues.tolist(),
                    "eigenvectors": eigenvectors.tolist(),
                },
                metadata={"shape": A.shape},
            )
        except Exception as e:
            return LAResult(success=False, error=str(e))

    @staticmethod
    def eigen_symmetric(A: np.ndarray) -> LAResult:
        """Compute eigenvalues/vectors using eigh (for symmetric/Hermitian matrices)."""
        try:
            if A.shape[0] != A.shape[1]:
                return LAResult(success=False, error="Matrix must be square")
            eigenvalues, eigenvectors = np.linalg.eigh(A)
            return LAResult(
                success=True,
                result={
                    "eigenvalues": eigenvalues.tolist(),
                    "eigenvectors": eigenvectors.tolist(),
                },
                metadata={"shape": A.shape, "method": "eigh"},
            )
        except Exception as e:
            return LAResult(success=False, error=str(e))

    # ---- SVD ----

    @staticmethod
    def svd(A: np.ndarray, full_matrices: bool = False) -> LAResult:
        """Compute Singular Value Decomposition: A = U @ diag(S) @ Vt.

        Returns U, S (singular values), Vt.
        """
        try:
            U, S, Vt = np.linalg.svd(A, full_matrices=full_matrices)
            return LAResult(
                success=True,
                result={
                    "U": U.tolist(),
                    "S": S.tolist(),
                    "Vt": Vt.tolist(),
                },
                metadata={"shape": A.shape, "rank": int(np.sum(S > 1e-10))},
            )
        except Exception as e:
            return LAResult(success=False, error=str(e))

    # ---- Matrix Decompositions ----

    @staticmethod
    def lu_decomposition(A: np.ndarray) -> LAResult:
        """Compute LU decomposition: A = P @ L @ U."""
        try:
            P, L, U = scipy.linalg.lu(A)
            return LAResult(
                success=True,
                result={
                    "P": P.tolist(),
                    "L": L.tolist(),
                    "U": U.tolist(),
                },
                metadata={"shape": A.shape},
            )
        except Exception as e:
            return LAResult(success=False, error=str(e))

    @staticmethod
    def qr_decomposition(A: np.ndarray) -> LAResult:
        """Compute QR decomposition: A = Q @ R."""
        try:
            Q, R = np.linalg.qr(A)
            return LAResult(
                success=True,
                result={"Q": Q.tolist(), "R": R.tolist()},
                metadata={"shape": A.shape},
            )
        except Exception as e:
            return LAResult(success=False, error=str(e))

    @staticmethod
    def cholesky(A: np.ndarray) -> LAResult:
        """Compute Cholesky decomposition: A = L @ L.T (A must be SPD)."""
        try:
            L = np.linalg.cholesky(A)
            return LAResult(
                success=True,
                result={"L": L.tolist()},
                metadata={"shape": A.shape},
            )
        except np.linalg.LinAlgError as e:
            return LAResult(success=False, error=f"Matrix not positive definite: {e}")
        except Exception as e:
            return LAResult(success=False, error=str(e))

    # ---- Solving Linear Systems ----

    @staticmethod
    def solve(A: np.ndarray, b: np.ndarray) -> LAResult:
        """Solve linear system Ax = b."""
        try:
            x = np.linalg.solve(A, b)
            residual = np.linalg.norm(A @ x - b)
            return LAResult(
                success=True,
                result={"x": x.tolist(), "residual": float(residual)},
                metadata={"shape_A": A.shape, "shape_b": b.shape},
            )
        except np.linalg.LinAlgError as e:
            return LAResult(success=False, error=f"Singular/ill-conditioned: {e}")
        except Exception as e:
            return LAResult(success=False, error=str(e))

    @staticmethod
    def least_squares(A: np.ndarray, b: np.ndarray) -> LAResult:
        """Solve least squares: min ||Ax - b||₂.

        Uses np.linalg.lstsq for robust solution.
        """
        try:
            x, residuals, rank, singular_values = np.linalg.lstsq(A, b, rcond=None)
            residual_norm = float(np.linalg.norm(A @ x - b))
            return LAResult(
                success=True,
                result={
                    "x": x.tolist(),
                    "residual_norm": residual_norm,
                    "rank": int(rank),
                    "singular_values": singular_values.tolist(),
                },
                metadata={"shape_A": A.shape, "shape_b": b.shape},
            )
        except Exception as e:
            return LAResult(success=False, error=str(e))

    @staticmethod
    def solve_least_squares_normal(A: np.ndarray, b: np.ndarray) -> LAResult:
        """Solve least squares via normal equations: AᵀA x = Aᵀb.

        Educational — shows the normal equation approach.
        """
        try:
            AtA = A.T @ A
            Atb = A.T @ b
            x = np.linalg.solve(AtA, Atb)
            residual = float(np.linalg.norm(A @ x - b))
            return LAResult(
                success=True,
                result={"x": x.tolist(), "residual": residual},
                metadata={"shape_A": A.shape, "method": "normal_equations"},
            )
        except Exception as e:
            return LAResult(success=False, error=str(e))

    # ---- PCA ----

    @staticmethod
    def pca(data: np.ndarray, n_components: int = 2,
            standardize: bool = True) -> LAResult:
        """Principal Component Analysis via SVD.

        Steps:
        1. Center (and optionally standardize) the data
        2. Compute SVD of centered data
        3. Project onto top n_components

        Args:
            data: shape (n_samples, n_features)
            n_components: number of principal components
            standardize: if True, divide by std dev

        Returns:
            projected_data, components, explained_variance_ratio, singular_values
        """
        try:
            n_samples, n_features = data.shape

            # 1. Center
            mean = np.mean(data, axis=0)
            X = data - mean

            # 2. Standardize (optional)
            if standardize:
                std = np.std(X, axis=0)
                std[std == 0] = 1.0  # avoid division by zero
                X = X / std

            # 3. SVD: X = U @ diag(S) @ Vt
            U, S, Vt = np.linalg.svd(X, full_matrices=False)

            # 4. Explained variance
            total_var = np.sum(S ** 2)
            explained_variance_ratio = (S ** 2) / total_var

            # 5. Components = rows of Vt (first n_components)
            components = Vt[:n_components]

            # 6. Project data
            projected = X @ components.T

            return LAResult(
                success=True,
                result={
                    "projected_data": projected.tolist(),
                    "components": components.tolist(),
                    "explained_variance_ratio": explained_variance_ratio[:n_components].tolist(),
                    "singular_values": S.tolist(),
                    "mean": mean.tolist(),
                },
                metadata={
                    "n_samples": n_samples,
                    "n_features": n_features,
                    "n_components": n_components,
                    "standardized": standardize,
                },
            )
        except Exception as e:
            return LAResult(success=False, error=str(e))

    # ---- Symbolic Matrix Operations (SymPy) ----

    @staticmethod
    def symbolic_matrix(matrix_str: str) -> LAResult:
        """Parse a symbolic matrix from string. E.g. '[[a,b],[c,d]]'."""
        try:
            M = sp.Matrix(sp.sympify(matrix_str))
            return LAResult(
                success=True,
                result=str(M),
                metadata={"shape": (M.rows, M.cols)},
            )
        except Exception as e:
            return LAResult(success=False, error=str(e))

    @staticmethod
    def symbolic_eigen(matrix_str: str) -> LAResult:
        """Compute symbolic eigenvalues and eigenvectors."""
        try:
            M = sp.Matrix(sp.sympify(matrix_str))
            eigenvals = M.eigenvals()
            eigenvects = M.eigenvects()
            return LAResult(
                success=True,
                result={
                    "eigenvalues": {str(k): int(v) for k, v in eigenvals.items()},
                    "eigenvectors": [[str(ev[0]), int(ev[1]), [str(v) for v in ev[2]]]
                                     for ev in eigenvects],
                },
                metadata={"shape": (M.rows, M.cols)},
            )
        except Exception as e:
            return LAResult(success=False, error=str(e))

    @staticmethod
    def symbolic_charpoly(matrix_str: str) -> LAResult:
        """Compute characteristic polynomial of a symbolic matrix."""
        try:
            M = sp.Matrix(sp.sympify(matrix_str))
            lam = sp.symbols("lambda")
            cp = M.charpoly(lam)
            return LAResult(
                success=True,
                result=str(cp.as_expr()),
                metadata={"shape": (M.rows, M.cols)},
            )
        except Exception as e:
            return LAResult(success=False, error=str(e))

    # ---- Utility ----

    @staticmethod
    def matrix_info(A: np.ndarray) -> LAResult:
        """Get comprehensive info about a matrix."""
        try:
            m, n = A.shape
            info = {
                "shape": (m, n),
                "rank": int(np.linalg.matrix_rank(A)),
                "det": float(np.linalg.det(A)) if m == n else None,
                "trace": float(np.trace(A)) if m == n else None,
                "frobenius_norm": float(np.linalg.norm(A, "fro")),
                "condition_number": float(np.linalg.cond(A)) if m == n else None,
                "is_symmetric": bool(np.allclose(A, A.T)),
                "is_positive_definite": bool(np.all(np.linalg.eigvalsh(A) > 0)) if m == n and np.allclose(A, A.T) else None,
            }
            return LAResult(success=True, result=info)
        except Exception as e:
            return LAResult(success=False, error=str(e))
