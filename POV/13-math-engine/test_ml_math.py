"""
Tests for Machine Learning Math Module.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from ml_math import MLMath, MLResult


@pytest.fixture
def ml():
    return MLMath(output_dir="/tmp/ml_test")


@pytest.fixture
def classification_data(ml):
    X, y = ml.make_classification(200, separable=True, seed=42)
    return X, y


@pytest.fixture
def nonsep_data(ml):
    X, y = ml.make_classification(200, separable=False, seed=42)
    return X, y


@pytest.fixture
def blob_data(ml):
    X, y = ml.make_blobs(300, centers=3, seed=42)
    return X, y


# ==================================================================
# Gradient Descent
# ==================================================================

class TestGradientDescent:
    """Tests for gradient descent variants."""

    def test_batch_gd_converges_to_minimum(self, ml):
        f = lambda w: float((w[0] - 3) ** 2 + (w[1] + 2) ** 2)
        grad_f = lambda w: np.array([2 * (w[0] - 3), 2 * (w[1] + 2)])
        result = ml.gradient_descent(f, grad_f, np.array([0.0, 0.0]),
                                     learning_rate=0.1, max_iter=500, method="batch")
        assert result.success
        x_opt = np.array(result.result["x_opt"])
        assert abs(x_opt[0] - 3.0) < 1e-4
        assert abs(x_opt[1] + 2.0) < 1e-4
        assert result.result["f_opt"] < 1e-8

    def test_batch_gd_history_recorded(self, ml):
        f = lambda w: float(w[0] ** 2)
        grad_f = lambda w: np.array([2 * w[0]])
        result = ml.gradient_descent(f, grad_f, np.array([5.0]),
                                     learning_rate=0.1, max_iter=100, method="batch")
        assert len(result.result["history"]) > 1
        assert len(result.result["losses"]) > 0

    def test_batch_gd_loss_decreases(self, ml):
        f = lambda w: float(w[0] ** 2 + w[1] ** 2)
        grad_f = lambda w: np.array([2 * w[0], 2 * w[1]])
        result = ml.gradient_descent(f, grad_f, np.array([5.0, 5.0]),
                                     learning_rate=0.1, max_iter=200, method="batch")
        losses = result.result["losses"]
        assert losses[-1] < losses[0]

    def test_stochastic_gd_works(self, ml):
        rng = np.random.RandomState(42)
        X = rng.randn(200, 1) * 2
        y = 3.0 * X.flatten() + 1.0 + rng.randn(200) * 0.5

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

        f_dummy = lambda w: 0.0
        grad_dummy = lambda w: np.zeros_like(w)

        result = ml.gradient_descent(
            f_dummy, grad_dummy, np.array([0.0, 0.0]),
            learning_rate=0.01, max_iter=500, method="stochastic",
            data=(X, y), loss_fn=loss_fn, grad_loss_fn=grad_loss_fn,
        )
        assert result.success
        # Should be close to true params [1.0, 3.0]
        w = result.result["x_opt"]
        assert abs(w[0] - 1.0) < 1.0  # intercept
        assert abs(w[1] - 3.0) < 1.0  # slope

    def test_mini_batch_gd_works(self, ml):
        rng = np.random.RandomState(42)
        X = rng.randn(200, 1) * 2
        y = 3.0 * X.flatten() + 1.0 + rng.randn(200) * 0.5

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

        f_dummy = lambda w: 0.0
        grad_dummy = lambda w: np.zeros_like(w)

        result = ml.gradient_descent(
            f_dummy, grad_dummy, np.array([0.0, 0.0]),
            learning_rate=0.01, max_iter=500, method="mini-batch",
            batch_size=32, data=(X, y), loss_fn=loss_fn, grad_loss_fn=grad_loss_fn,
        )
        assert result.success
        w = result.result["x_opt"]
        assert abs(w[0] - 1.0) < 1.0
        assert abs(w[1] - 3.0) < 1.0

    def test_gd_unknown_method_fails(self, ml):
        f = lambda w: float(w[0] ** 2)
        grad_f = lambda w: np.array([2 * w[0]])
        result = ml.gradient_descent(f, grad_f, np.array([1.0]), method="unknown")
        assert not result.success


# ==================================================================
# Logistic Regression
# ==================================================================

class TestLogisticRegression:
    """Tests for logistic regression from scratch."""

    def test_logistic_regression_success(self, ml, classification_data):
        X, y = classification_data
        result = ml.logistic_regression(X, y, learning_rate=0.1, max_iter=5000)
        assert result.success
        assert "weights" in result.result
        assert "accuracy" in result.result

    def test_logistic_regression_high_accuracy_separable(self, ml, classification_data):
        X, y = classification_data
        result = ml.logistic_regression(X, y, learning_rate=0.1, max_iter=5000)
        assert result.result["accuracy"] > 0.90

    def test_logistic_regression_weights_shape(self, ml, classification_data):
        X, y = classification_data
        result = ml.logistic_regression(X, y, fit_intercept=True)
        # weights = [bias, w1, w2]
        assert len(result.result["weights"]) == X.shape[1] + 1

    def test_logistic_regression_no_intercept(self, ml, classification_data):
        X, y = classification_data
        result = ml.logistic_regression(X, y, fit_intercept=False)
        assert len(result.result["weights"]) == X.shape[1]

    def test_logistic_regression_predictions_binary(self, ml, classification_data):
        X, y = classification_data
        result = ml.logistic_regression(X, y)
        preds = result.result["predictions"]
        assert all(p in (0, 1) for p in preds)

    def test_logistic_regression_probabilities_in_range(self, ml, classification_data):
        X, y = classification_data
        result = ml.logistic_regression(X, y)
        probs = result.result["probabilities"]
        assert all(0 <= p <= 1 for p in probs)

    def test_logistic_regression_loss_decreases(self, ml, classification_data):
        X, y = classification_data
        result = ml.logistic_regression(X, y, learning_rate=0.1, max_iter=5000)
        losses = result.result["loss_history"]
        assert len(losses) > 1
        assert losses[-1] < losses[0]

    def test_logistic_regression_with_regularization(self, ml, classification_data):
        X, y = classification_data
        r1 = ml.logistic_regression(X, y, lambda_reg=0.0)
        r2 = ml.logistic_regression(X, y, lambda_reg=1.0)
        assert r1.success and r2.success
        # Regularized weights should be smaller in magnitude
        w1_norm = np.linalg.norm(r1.result["coefficients"])
        w2_norm = np.linalg.norm(r2.result["coefficients"])
        assert w2_norm <= w1_norm * 1.1  # Allow some tolerance

    def test_decision_boundary_success(self, ml, classification_data):
        X, y = classification_data
        lr = ml.logistic_regression(X, y)
        db = ml.logistic_decision_boundary(X, y, np.array(lr.result["weights"]))
        assert db.success
        assert "xx" in db.result
        assert "yy" in db.result
        assert "Z" in db.result

    def test_decision_boundary_requires_2d(self, ml):
        X = np.random.randn(100, 3)
        y = np.random.randint(0, 2, 100)
        db = ml.logistic_decision_boundary(X, y, np.array([0.0, 1.0, 2.0, 3.0]))
        assert not db.success


# ==================================================================
# SVM
# ==================================================================

class TestSVMLinear:
    """Tests for linear SVM."""

    def test_svm_linear_success(self, ml, classification_data):
        X, y = classification_data
        y_svm = np.where(y == 0, -1, 1)
        result = ml.svm_linear(X, y_svm, C=1.0, learning_rate=0.001, max_iter=5000)
        assert result.success
        assert "weights" in result.result
        assert "accuracy" in result.result

    def test_svm_linear_high_accuracy_separable(self, ml, classification_data):
        X, y = classification_data
        y_svm = np.where(y == 0, -1, 1)
        result = ml.svm_linear(X, y_svm, C=1.0, learning_rate=0.001, max_iter=5000)
        assert result.result["accuracy"] > 0.90

    def test_svm_linear_predictions_are_signs(self, ml, classification_data):
        X, y = classification_data
        y_svm = np.where(y == 0, -1, 1)
        result = ml.svm_linear(X, y_svm)
        preds = result.result["predictions"]
        assert all(p in (-1, 1) for p in preds)

    def test_svm_linear_has_support_vectors(self, ml, classification_data):
        X, y = classification_data
        y_svm = np.where(y == 0, -1, 1)
        result = ml.svm_linear(X, y_svm)
        assert result.result["n_support_vectors"] > 0
        assert len(result.result["support_vector_indices"]) > 0

    def test_svm_linear_weights_shape(self, ml, classification_data):
        X, y = classification_data
        y_svm = np.where(y == 0, -1, 1)
        result = ml.svm_linear(X, y_svm)
        # weights = [bias, w1, w2]
        assert len(result.result["weights"]) == X.shape[1] + 1

    def test_svm_decision_boundary_success(self, ml, classification_data):
        X, y = classification_data
        y_svm = np.where(y == 0, -1, 1)
        svm = ml.svm_linear(X, y_svm)
        db = ml.svm_decision_boundary(X, y_svm, np.array(svm.result["weights"]))
        assert db.success


class TestSVMKernel:
    """Tests for kernel SVM."""

    def test_svm_kernel_rbf_success(self, ml, nonsep_data):
        X, y = nonsep_data
        y_svm = np.where(y == 0, -1, 1)
        result = ml.svm_kernel(X, y_svm, kernel="rbf", gamma=0.5, C=1.0)
        assert result.success
        assert "alpha" in result.result
        assert "accuracy" in result.result

    def test_svm_kernel_linear_success(self, ml, classification_data):
        X, y = classification_data
        y_svm = np.where(y == 0, -1, 1)
        result = ml.svm_kernel(X, y_svm, kernel="linear")
        assert result.success

    def test_svm_kernel_poly_success(self, ml, classification_data):
        X, y = classification_data
        y_svm = np.where(y == 0, -1, 1)
        result = ml.svm_kernel(X, y_svm, kernel="poly", degree=3)
        assert result.success

    def test_svm_kernel_has_support_vectors(self, ml, nonsep_data):
        X, y = nonsep_data
        y_svm = np.where(y == 0, -1, 1)
        result = ml.svm_kernel(X, y_svm, kernel="rbf", gamma=0.5)
        assert result.result["n_support_vectors"] > 0

    def test_svm_kernel_unknown_kernel_fails(self, ml, classification_data):
        X, y = classification_data
        y_svm = np.where(y == 0, -1, 1)
        result = ml.svm_kernel(X, y_svm, kernel="unknown")
        assert not result.success

    def test_svm_kernel_predictions_are_signs(self, ml, nonsep_data):
        X, y = nonsep_data
        y_svm = np.where(y == 0, -1, 1)
        result = ml.svm_kernel(X, y_svm, kernel="rbf", gamma=0.5)
        preds = result.result["predictions"]
        assert all(p in (-1, 1) for p in preds)


# ==================================================================
# K-Means
# ==================================================================

class TestKMeans:
    """Tests for k-means clustering."""

    def test_kmeans_success(self, ml, blob_data):
        X, _ = blob_data
        result = ml.kmeans(X, k=3, n_init=5, seed=42)
        assert result.success
        assert "labels" in result.result
        assert "centroids" in result.result

    def test_kmeans_correct_number_of_clusters(self, ml, blob_data):
        X, _ = blob_data
        result = ml.kmeans(X, k=5, n_init=5, seed=42)
        labels = np.array(result.result["labels"])
        assert len(np.unique(labels)) <= 5

    def test_kmeans_centroids_shape(self, ml, blob_data):
        X, _ = blob_data
        result = ml.kmeans(X, k=3, n_init=5, seed=42)
        centroids = np.array(result.result["centroids"])
        assert centroids.shape == (3, X.shape[1])

    def test_kmeans_labels_length(self, ml, blob_data):
        X, _ = blob_data
        result = ml.kmeans(X, k=3, n_init=5, seed=42)
        assert len(result.result["labels"]) == len(X)

    def test_kmeans_inertia_positive(self, ml, blob_data):
        X, _ = blob_data
        result = ml.kmeans(X, k=3, n_init=5, seed=42)
        assert result.result["inertia"] > 0

    def test_kmeans_reproducible(self, ml, blob_data):
        X, _ = blob_data
        r1 = ml.kmeans(X, k=3, n_init=1, seed=42)
        r2 = ml.kmeans(X, k=3, n_init=1, seed=42)
        np.testing.assert_array_equal(r1.result["labels"], r2.result["labels"])

    def test_kmeans_k1(self, ml, blob_data):
        X, _ = blob_data
        result = ml.kmeans(X, k=1, n_init=3, seed=42)
        assert result.success
        labels = np.array(result.result["labels"])
        assert np.all(labels == 0)


class TestElbow:
    """Tests for elbow method."""

    def test_elbow_success(self, ml, blob_data):
        X, _ = blob_data
        result = ml.kmeans_elbow(X, k_range=(1, 8), n_init=3, seed=42)
        assert result.success
        assert "k_values" in result.result
        assert "inertias" in result.result

    def test_elbow_inertias_decreasing(self, ml, blob_data):
        X, _ = blob_data
        result = ml.kmeans_elbow(X, k_range=(1, 8), n_init=3, seed=42)
        inertias = result.result["inertias"]
        for i in range(1, len(inertias)):
            assert inertias[i] <= inertias[i - 1]

    def test_elbow_correct_length(self, ml, blob_data):
        X, _ = blob_data
        result = ml.kmeans_elbow(X, k_range=(2, 7), n_init=3, seed=42)
        assert len(result.result["k_values"]) == 5
        assert len(result.result["inertias"]) == 5


# ==================================================================
# Backpropagation
# ==================================================================

class TestBackpropagation:
    """Tests for backpropagation math."""

    def test_backprop_math_success(self, ml):
        result = ml.backpropagation_math(
            expr="sigmoid(w1*x1 + w2*x2 + b)",
            variables=["w1", "w2", "b"],
        )
        assert result.success
        assert "gradients" in result.result
        assert "w1" in result.result["gradients"]
        assert "w2" in result.result["gradients"]
        assert "b" in result.result["gradients"]

    def test_backprop_math_has_steps(self, ml):
        result = ml.backpropagation_math()
        assert len(result.result["steps"]) > 0

    def test_backprop_math_hessian(self, ml):
        result = ml.backpropagation_math()
        assert "hessian_diagonal" in result.result
        assert "w1" in result.result["hessian_diagonal"]

    def test_backprop_math_custom_variables(self, ml):
        result = ml.backpropagation_math(
            expr="sigmoid(a*x + b)",
            variables=["a", "b"],
        )
        assert result.success
        assert "a" in result.result["gradients"]
        assert "b" in result.result["gradients"]

    def test_neural_network_gradients_success(self, ml):
        result = ml.neural_network_gradients(layer_sizes=[2, 3, 1])
        assert result.success
        assert "forward_activations" in result.result
        assert "weight_gradients" in result.result
        assert "bias_gradients" in result.result

    def test_neural_network_gradients_correct_shapes(self, ml):
        result = ml.neural_network_gradients(layer_sizes=[2, 4, 3, 1])
        # 3 layers: 2->4, 4->3, 3->1
        assert len(result.result["weight_gradients"]) == 3
        assert len(result.result["bias_gradients"]) == 3
        # Weight gradient shapes
        wg0 = np.array(result.result["weight_gradients"][0])
        assert wg0.shape == (4, 2)
        wg1 = np.array(result.result["weight_gradients"][1])
        assert wg1.shape == (3, 4)
        wg2 = np.array(result.result["weight_gradients"][2])
        assert wg2.shape == (1, 3)

    def test_neural_network_gradients_loss_positive(self, ml):
        result = ml.neural_network_gradients()
        assert result.result["loss"] > 0

    def test_neural_network_gradients_output_in_range(self, ml):
        result = ml.neural_network_gradients()
        assert 0 <= result.result["output"] <= 1


# ==================================================================
# Data Generation
# ==================================================================

class TestDataGeneration:
    """Tests for synthetic data generation."""

    def test_make_classification_separable(self, ml):
        X, y = ml.make_classification(200, separable=True, seed=42)
        assert X.shape == (200, 2)
        assert len(y) == 200
        assert set(y) == {0, 1}

    def test_make_classification_nonseparable(self, ml):
        X, y = ml.make_classification(200, separable=False, seed=42)
        assert X.shape == (200, 2)
        assert set(y) == {0, 1}

    def test_make_classification_reproducible(self, ml):
        X1, y1 = ml.make_classification(100, seed=42)
        X2, y2 = ml.make_classification(100, seed=42)
        np.testing.assert_array_equal(X1, X2)
        np.testing.assert_array_equal(y1, y2)

    def test_make_blobs(self, ml):
        X, y = ml.make_blobs(300, centers=3, seed=42)
        assert X.shape == (300, 2)
        assert len(y) == 300
        assert len(np.unique(y)) == 3

    def test_make_blobs_different_centers(self, ml):
        X, y = ml.make_blobs(300, centers=5, seed=42)
        assert len(np.unique(y)) == 5

    def test_make_blobs_reproducible(self, ml):
        X1, y1 = ml.make_blobs(100, seed=42)
        X2, y2 = ml.make_blobs(100, seed=42)
        np.testing.assert_array_equal(X1, X2)
        np.testing.assert_array_equal(y1, y2)


# ==================================================================
# MLResult
# ==================================================================

class TestMLResult:
    """Tests for MLResult dataclass."""

    def test_success_result(self):
        r = MLResult(success=True, result={"value": 42})
        assert r.success
        assert r.result["value"] == 42

    def test_error_result(self):
        r = MLResult(success=False, error="computation failed")
        assert not r.success
        assert r.error == "computation failed"

    def test_metadata(self):
        r = MLResult(success=True, result={}, metadata={"key": "val"})
        assert r.metadata["key"] == "val"


# ==================================================================
# Edge Cases
# ==================================================================

class TestEdgeCases:
    """Edge case and robustness tests."""

    def test_logistic_regression_small_dataset(self, ml):
        X = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]])
        y = np.array([0, 0, 1, 1])
        result = ml.logistic_regression(X, y, max_iter=5000)
        assert result.success

    def test_svm_linear_small_dataset(self, ml):
        X = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]])
        y = np.array([-1, -1, 1, 1])
        result = ml.svm_linear(X, y, max_iter=5000)
        assert result.success

    def test_kmeans_more_clusters_than_samples(self, ml):
        X = np.random.randn(5, 2)
        result = ml.kmeans(X, k=10, n_init=3, seed=42)
        assert result.success

    def test_gd_high_dimensional(self, ml):
        f = lambda w: float(np.sum(w ** 2))
        grad_f = lambda w: 2 * w
        x0 = np.ones(10)
        result = ml.gradient_descent(f, grad_f, x0, learning_rate=0.1, max_iter=500, method="batch")
        assert result.success
        assert result.result["f_opt"] < 1e-8
