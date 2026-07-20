"""
Tests for differential_eq.py module.

Covers: Euler, RK4, scipy ODE solvers, phase portraits, specialized systems,
bifurcation diagrams, stability analysis.
"""

import numpy as np
import pytest
from differential_eq import DifferentialEquations, DEResult

de = DifferentialEquations()


# ---- Test ODE Solvers ----

def f_simple(t, y):
    """dy/dt = -y, exact solution: y(t) = y0 * exp(-t)"""
    return [-y[0]]


def f_2d(t, y):
    """Simple 2D system: dx/dt = y, dy/dt = -x (harmonic oscillator)"""
    return [y[1], -y[0]]


def test_euler_simple():
    r = de.solve_ode_euler(f_simple, [1.0], (0.0, 1.0), h=0.01)
    assert r.success
    t = np.array(r.result["t"])
    y = np.array(r.result["y"])[:, 0]
    # At t=1, exact is exp(-1) ≈ 0.3679
    assert abs(y[-1] - np.exp(-1)) < 0.02  # Euler with h=0.01 should be close


def test_euler_2d():
    r = de.solve_ode_euler(f_2d, [1.0, 0.0], (0.0, 2 * np.pi), h=0.01)
    assert r.success
    y = np.array(r.result["y"])
    # After one period, should return to (1, 0) approximately
    assert abs(y[-1, 0] - 1.0) < 0.5  # Euler drifts but should be in ballpark
    assert abs(y[-1, 1] - 0.0) < 0.5


def test_rk4_simple():
    r = de.solve_ode_rk4(f_simple, [1.0], (0.0, 1.0), h=0.01)
    assert r.success
    y = np.array(r.result["y"])[:, 0]
    assert abs(y[-1] - np.exp(-1)) < 1e-5  # RK4 should be very accurate


def test_rk4_2d():
    r = de.solve_ode_rk4(f_2d, [1.0, 0.0], (0.0, 2 * np.pi), h=0.01)
    assert r.success
    y = np.array(r.result["y"])
    # RK4 should preserve the orbit well
    assert abs(y[-1, 0] - 1.0) < 0.01
    assert abs(y[-1, 1] - 0.0) < 0.01


def test_scipy_solve():
    r = de.solve_ode_scipy(f_simple, [1.0], (0.0, 1.0), num_points=100)
    assert r.success
    y = np.array(r.result["y"])[0]
    assert abs(y[-1] - np.exp(-1)) < 1e-8


def test_scipy_solve_2d():
    r = de.solve_ode_scipy(f_2d, [1.0, 0.0], (0.0, 2 * np.pi), num_points=200)
    assert r.success
    y = np.array(r.result["y"])
    assert abs(y[0, -1] - 1.0) < 1e-6
    assert abs(y[1, -1] - 0.0) < 1e-6


def test_euler_vs_rk4_convergence():
    """RK4 should be more accurate than Euler for same step size."""
    h = 0.1
    r_e = de.solve_ode_euler(f_simple, [1.0], (0.0, 1.0), h=h)
    r_r = de.solve_ode_rk4(f_simple, [1.0], (0.0, 1.0), h=h)
    y_e = np.array(r_e.result["y"])[:, 0]
    y_r = np.array(r_r.result["y"])[:, 0]
    err_e = abs(y_e[-1] - np.exp(-1))
    err_r = abs(y_r[-1] - np.exp(-1))
    assert err_r < err_e  # RK4 should be better


# ---- Phase Portraits ----

def test_phase_portrait():
    r = de.phase_portrait(f_2d, (-2, 2), (-2, 2), resolution=20)
    assert r.success
    X = np.array(r.result["X"])
    Y = np.array(r.result["Y"])
    U = np.array(r.result["U"])
    V = np.array(r.result["V"])
    assert X.shape == (20, 20)
    assert Y.shape == (20, 20)
    # Vectors should be normalized
    magnitudes = np.sqrt(U**2 + V**2)
    assert np.allclose(magnitudes[magnitudes > 0], 1.0, atol=1e-10)


def test_nullclines():
    r = de.nullclines(f_2d, (-2, 2), (-2, 2), resolution=30)
    assert r.success
    DX = np.array(r.result["DX"])
    DY = np.array(r.result["DY"])
    assert DX.shape == (30, 30)


# ---- Jacobian & Stability ----

def test_jacobian_eigenvalues_center():
    """Harmonic oscillator at (0,0) should be a center."""
    r = de.jacobian_eigenvalues(f_2d, (0.0, 0.0))
    assert r.success
    assert r.result["stability"] == "center"
    evals = r.result["eigenvalues"]
    # Should be ±i
    assert abs(evals[0].real) < 1e-5
    assert abs(abs(evals[0].imag) - 1.0) < 1e-3


def test_jacobian_eigenvalues_saddle():
    """dx/dt = x, dy/dt = -y has saddle at (0,0)."""
    def f_saddle(t, y):
        return [y[0], -y[1]]

    r = de.jacobian_eigenvalues(f_saddle, (0.0, 0.0))
    assert r.success
    assert r.result["stability"] == "saddle"


# ---- Specialized Systems ----

def test_lotka_volterra():
    """Test Lotka-Volterra at equilibrium."""
    alpha, beta, gamma, delta = 1.0, 0.1, 1.5, 0.075
    eq = (gamma / delta, alpha / beta)
    deriv = de.lotka_volterra(0, eq, alpha, beta, gamma, delta)
    assert abs(deriv[0]) < 1e-10
    assert abs(deriv[1]) < 1e-10


def test_lotka_volterra_solve():
    r = de.solve_ode_scipy(de.lotka_volterra, [10.0, 5.0], (0.0, 20.0), num_points=200)
    assert r.success
    y = np.array(r.result["y"])
    assert y.shape[0] == 2  # 2D system
    assert y.shape[1] == 200


def test_pendulum():
    """Test pendulum at equilibrium."""
    deriv = de.pendulum(0, [0.0, 0.0])
    assert abs(deriv[0]) < 1e-10
    assert abs(deriv[1]) < 1e-10


def test_pendulum_solve():
    r = de.solve_ode_scipy(de.pendulum, [np.pi/4, 0.0], (0.0, 10.0), num_points=200)
    assert r.success
    y = np.array(r.result["y"])
    # Should decay toward 0
    assert abs(y[0, -1]) < abs(y[0, 0])


def test_harmonic_oscillator_undamped():
    """Undamped oscillator should conserve energy."""
    r = de.solve_ode_scipy(
        lambda t, s: de.harmonic_oscillator(t, s, omega0=1.0, zeta=0.0),
        [1.0, 0.0], (0.0, 2 * np.pi), num_points=200,
    )
    assert r.success
    y = np.array(r.result["y"])
    # Should return to (1, 0) after one period
    assert abs(y[0, -1] - 1.0) < 1e-6
    assert abs(y[1, -1] - 0.0) < 1e-6


def test_harmonic_oscillator_damped():
    """Damped oscillator should decay."""
    r = de.solve_ode_scipy(
        lambda t, s: de.harmonic_oscillator(t, s, omega0=1.0, zeta=0.2),
        [1.0, 0.0], (0.0, 10.0), num_points=200,
    )
    assert r.success
    y = np.array(r.result["y"])
    assert abs(y[0, -1]) < 0.5  # Should have decayed significantly


def test_van_der_pol():
    """Van der Pol should settle into a limit cycle."""
    r = de.solve_ode_scipy(
        lambda t, s: de.van_der_pol(t, s, mu=1.0),
        [2.0, 0.0], (0.0, 30.0), num_points=500,
    )
    assert r.success
    y = np.array(r.result["y"])
    # After transient, amplitude should be ~2
    last_quarter = y[0, -125:]
    amplitude = np.max(np.abs(last_quarter))
    assert 1.5 < amplitude < 3.0


def test_lorenz():
    """Lorenz system should produce bounded chaotic trajectory."""
    r = de.solve_ode_scipy(de.lorenz, [1.0, 1.0, 1.0], (0.0, 20.0), num_points=500)
    assert r.success
    y = np.array(r.result["y"])
    assert y.shape[0] == 3
    # Should be bounded
    assert np.all(np.abs(y) < 50)


# ---- Bifurcation ----

def test_logistic_map_bifurcation():
    r = de.logistic_map_bifurcation(r_range=(2.5, 4.0), n_r=50)
    assert r.success
    assert len(r.result) > 0
    # Check that we have data for multiple r values
    r_vals = set(d["r"] for d in r.result)
    assert len(r_vals) > 1


def test_bifurcation_diagram():
    """Bifurcation diagram for Van der Pol."""
    r = de.bifurcation_diagram(
        de.van_der_pol,
        param_range=(0.5, 2.0),
        param_name="mu",
        y0=(2.0, 0.0),
        t_transient=20.0,
        t_sample=20.0,
        n_params=10,
    )
    assert r.success
    assert len(r.result) > 0


# ---- Find Equilibria ----

def test_find_equilibria():
    r = de.find_equilibria_2d(f_2d, (-2, 2), (-2, 2), n_guesses=10)
    assert r.success
    # Should find (0,0) as equilibrium
    found_origin = any(
        abs(eq["x"]) < 1e-3 and abs(eq["y"]) < 1e-3
        for eq in r.result
    )
    assert found_origin


# ---- Edge Cases ----

def test_euler_zero_steps():
    r = de.solve_ode_euler(f_simple, [1.0], (0.0, 0.0), h=0.01)
    assert r.success
    t = np.array(r.result["t"])
    assert len(t) == 1


def test_scipy_different_methods():
    for method in ["RK45", "DOP853", "Radau", "BDF"]:
        r = de.solve_ode_scipy(f_simple, [1.0], (0.0, 1.0),
                               num_points=50, method=method)
        assert r.success, f"Method {method} failed"
