"""
Tests for linear_algebra.py module.

Covers: eigenvalues, SVD, LU/QR, matrix operations, least squares, PCA.
"""

import numpy as np
import pytest
from linear_algebra import LinearAlgebra, LAResult

la = LinearAlgebra()


# ---- Fixtures ----

@pytest.fixture
def sym_matrix():
    return np.array([[4, 1, 1],
                      [1, 3, 2],
                      [1, 2, 5]], dtype=float)


@pytest.fixture
def nonsym_matrix():
    return np.array([[0, 1],
                      [-2, -3]], dtype=float)


@pytest.fixture
def random_5x3():
    return la.random_matrix(5, 3, seed=42)


@pytest.fixture
def square_3x3():
    return np.array([[3, 2, -1],
                      [2, -2, 4],
                      [-1, 0.5, -1]], dtype=float)


@pytest.fixture
def pca_data():
    rng = np.random.RandomState(42)
    mean = [5, 10, 15]
    cov = [[3.0, 2.0, 1.0],
           [2.0, 4.0, 1.5],
           [1.0, 1.5, 2.0]]
    return rng.multivariate_normal(mean, cov, 200)


# ---- Matrix Creation ----

def test_from_list():
    A = la.from_list([[1, 2], [3, 4]])
    assert A.shape == (2, 2)
    assert A[0, 0] == 1


def test_random_matrix():
    A = la.random_matrix(4, 3, seed=42)
    assert A.shape == (4, 3)
    B = la.random_matrix(4, 3, seed=42)
    assert np.allclose(A, B)  # deterministic with seed


def test_hilbert_matrix():
    H = la.hilbert_matrix(4)
    assert H.shape == (4, 4)
    assert np.allclose(H, H.T)  # symmetric


# ---- Basic Operations ----

def test_determinant(sym_matrix):
    r = la.determinant(sym_matrix)
    assert r.success
    assert abs(r.result - 36.0) < 1e-10  # det of this specific matrix


def test_determinant_nonsquare(random_5x3):
    r = la.determinant(random_5x3)
    assert not r.success


def test_inverse(sym_matrix):
    r = la.inverse(sym_matrix)
    assert r.success
    inv = np.array(r.result)
    assert np.allclose(sym_matrix @ inv, np.eye(3), atol=1e-10)


def test_inverse_singular():
    A = np.array([[1, 2], [2, 4]], dtype=float)
    r = la.inverse(A)
    assert not r.success


def test_rank(sym_matrix):
    r = la.rank(sym_matrix)
    assert r.success
    assert r.result == 3


def test_rank_deficient():
    A = np.array([[1, 2, 3],
                   [2, 4, 6],
                   [3, 6, 9]], dtype=float)
    r = la.rank(A)
    assert r.success
    assert r.result == 1


def test_condition_number(sym_matrix):
    r = la.condition_number(sym_matrix)
    assert r.success
    assert r.result >= 1.0


def test_trace(sym_matrix):
    r = la.trace(sym_matrix)
    assert r.success
    assert abs(r.result - 12.0) < 1e-10  # 4+3+5


def test_norm(sym_matrix):
    r = la.norm(sym_matrix, ord="fro")
    assert r.success
    assert r.result > 0


# ---- Eigenvalues ----

def test_eigen_symmetric(sym_matrix):
    r = la.eigen_symmetric(sym_matrix)
    assert r.success
    evals = np.array(r.result["eigenvalues"])
    evecs = np.array(r.result["eigenvectors"])
    assert len(evals) == 3
    # Check that eigenvalues are real
    assert np.all(np.isreal(evals))
    # Check trace = sum of eigenvalues
    assert abs(np.sum(evals) - np.trace(sym_matrix)) < 1e-10


def test_eigen_nonsymmetric(nonsym_matrix):
    r = la.eigen(nonsym_matrix)
    assert r.success
    evals = np.array(r.result["eigenvalues"])
    assert len(evals) == 2
    # Product of eigenvalues = determinant
    det = np.linalg.det(nonsym_matrix)
    assert abs(np.prod(evals) - det) < 1e-10


def test_eigen_nonsquare(random_5x3):
    r = la.eigen(random_5x3)
    assert not r.success


# ---- SVD ----

def test_svd(random_5x3):
    r = la.svd(random_5x3)
    assert r.success
    U = np.array(r.result["U"])
    S = np.array(r.result["S"])
    Vt = np.array(r.result["Vt"])
    # Check shapes
    assert U.shape == (5, 5) or U.shape[1] == 5  # full_matrices=False gives (5,3)
    assert len(S) == 3
    assert Vt.shape == (3, 3)
    # Check reconstruction
    if U.shape[1] == 3:  # full_matrices=False
        recon = U @ np.diag(S) @ Vt
        assert np.allclose(recon, random_5x3, atol=1e-10)


def test_svd_full_matrices(random_5x3):
    r = la.svd(random_5x3, full_matrices=True)
    assert r.success
    U = np.array(r.result["U"])
    assert U.shape == (5, 5)


# ---- Decompositions ----

def test_lu_decomposition(square_3x3):
    r = la.lu_decomposition(square_3x3)
    assert r.success
    P = np.array(r.result["P"])
    L = np.array(r.result["L"])
    U = np.array(r.result["U"])
    recon = P @ L @ U
    assert np.allclose(recon, square_3x3, atol=1e-10)


def test_qr_decomposition(square_3x3):
    r = la.qr_decomposition(square_3x3)
    assert r.success
    Q = np.array(r.result["Q"])
    R = np.array(r.result["R"])
    recon = Q @ R
    assert np.allclose(recon, square_3x3, atol=1e-10)
    # Q should be orthogonal
    assert np.allclose(Q.T @ Q, np.eye(3), atol=1e-10)


def test_cholesky(sym_matrix):
    r = la.cholesky(sym_matrix)
    assert r.success
    L = np.array(r.result["L"])
    recon = L @ L.T
    assert np.allclose(recon, sym_matrix, atol=1e-10)


def test_cholesky_non_spd():
    A = np.array([[1, 2], [2, 1]], dtype=float)  # Not positive definite
    r = la.cholesky(A)
    assert not r.success


# ---- Solving Linear Systems ----

def test_solve(square_3x3):
    b = np.array([1, -2, 0], dtype=float)
    r = la.solve(square_3x3, b)
    assert r.success
    x = np.array(r.result["x"])
    assert np.allclose(square_3x3 @ x, b, atol=1e-10)
    assert r.result["residual"] < 1e-10


def test_solve_singular():
    A = np.array([[1, 2], [2, 4]], dtype=float)
    b = np.array([1, 2], dtype=float)
    r = la.solve(A, b)
    assert not r.success


# ---- Least Squares ----

def test_least_squares():
    rng = np.random.RandomState(42)
    n = 50
    x = np.linspace(-3, 3, n)
    y_true = 2 + 3 * x - 1.5 * x**2
    y = y_true + rng.normal(0, 0.5, n)
    A = np.column_stack([np.ones(n), x, x**2])

    r = la.least_squares(A, y)
    assert r.success
    coeffs = np.array(r.result["x"])
    # Should be close to [2, 3, -1.5]
    assert abs(coeffs[0] - 2) < 0.5
    assert abs(coeffs[1] - 3) < 0.5
    assert abs(coeffs[2] + 1.5) < 0.5


def test_least_squares_normal():
    rng = np.random.RandomState(42)
    n = 30
    x = np.linspace(0, 5, n)
    y = 1 + 2 * x + rng.normal(0, 0.3, n)
    A = np.column_stack([np.ones(n), x])

    r = la.solve_least_squares_normal(A, y)
    assert r.success
    coeffs = np.array(r.result["x"])
    assert abs(coeffs[0] - 1) < 0.5
    assert abs(coeffs[1] - 2) < 0.3


# ---- PCA ----

def test_pca_basic(pca_data):
    r = la.pca(pca_data, n_components=2)
    assert r.success
    projected = np.array(r.result["projected_data"])
    assert projected.shape == (200, 2)
    components = np.array(r.result["components"])
    assert components.shape == (2, 3)
    evr = r.result["explained_variance_ratio"]
    assert len(evr) == 2
    assert 0.99 < sum(evr) <= 1.0  # should explain most variance


def test_pca_no_standardize(pca_data):
    r = la.pca(pca_data, n_components=2, standardize=False)
    assert r.success
    projected = np.array(r.result["projected_data"])
    assert projected.shape == (200, 2)


def test_pca_all_components(pca_data):
    r = la.pca(pca_data, n_components=3)
    assert r.success
    projected = np.array(r.result["projected_data"])
    assert projected.shape == (200, 3)
    evr = r.result["explained_variance_ratio"]
    assert abs(sum(evr) - 1.0) < 1e-10


def test_pca_orthogonal_components(pca_data):
    r = la.pca(pca_data, n_components=3)
    components = np.array(r.result["components"])
    # Components should be orthonormal
    gram = components @ components.T
    assert np.allclose(gram, np.eye(3), atol=1e-10)


# ---- Symbolic ----

def test_symbolic_matrix():
    r = la.symbolic_matrix("[[a, b], [c, d]]")
    assert r.success


def test_symbolic_eigen():
    r = la.symbolic_eigen("[[1, 2], [2, 1]]")
    assert r.success
    assert "eigenvalues" in r.result
    assert "eigenvectors" in r.result


def test_symbolic_charpoly():
    r = la.symbolic_charpoly("[[1, 2], [3, 4]]")
    assert r.success


# ---- Matrix Info ----

def test_matrix_info(sym_matrix):
    r = la.matrix_info(sym_matrix)
    assert r.success
    assert r.result["shape"] == (3, 3)
    assert r.result["rank"] == 3
    assert r.result["is_symmetric"] is True
    assert r.result["is_positive_definite"] is True


def test_matrix_info_nonsymmetric(nonsym_matrix):
    r = la.matrix_info(nonsym_matrix)
    assert r.success
    assert r.result["is_symmetric"] is False
