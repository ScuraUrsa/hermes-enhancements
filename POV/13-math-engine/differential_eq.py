"""
Differential Equations Module — ODE Solvers, Phase Portraits, Bifurcations.

All computations use NumPy/SciPy/SymPy — LLM NEVER does math.
Provides numerical ODE solvers (Euler, RK4, solve_ivp), phase portrait
generation, and specialized systems (Lotka-Volterra, pendulum, oscillator).

Usage:
    from differential_eq import DifferentialEquations
    de = DifferentialEquations()
    sol = de.solve_ode_euler(f, y0, t_span, h=0.01)
    X, Y, U, V = de.phase_portrait(f, x_range, y_range)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import scipy.integrate
import scipy.optimize


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class DEResult:
    """Structured result from differential equation operations."""
    success: bool
    result: Any = None
    error: str = ""
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Differential Equations Engine
# ---------------------------------------------------------------------------

class DifferentialEquations:
    """Numerical ODE solvers, phase portraits, and dynamical systems."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ---- ODE Solvers ----

    @staticmethod
    def solve_ode_euler(
        f: Callable[[float, np.ndarray], np.ndarray],
        y0: np.ndarray,
        t_span: tuple[float, float],
        h: float = 0.01,
    ) -> DEResult:
        """Forward Euler method for ODE: dy/dt = f(t, y).

        Args:
            f: function f(t, y) returning dy/dt
            y0: initial state vector
            t_span: (t_start, t_end)
            h: step size

        Returns:
            t array, y array (shape: n_steps × n_dims)
        """
        try:
            t0, tf = t_span
            n_steps = int((tf - t0) / h) + 1
            t = np.linspace(t0, tf, n_steps)
            y = np.zeros((n_steps, len(y0)))
            y[0] = y0

            for i in range(n_steps - 1):
                y[i + 1] = y[i] + h * np.array(f(t[i], y[i]))

            return DEResult(
                success=True,
                result={"t": t.tolist(), "y": y.tolist()},
                metadata={"method": "euler", "h": h, "n_steps": n_steps},
            )
        except Exception as e:
            return DEResult(success=False, error=str(e))

    @staticmethod
    def solve_ode_rk4(
        f: Callable[[float, np.ndarray], np.ndarray],
        y0: np.ndarray,
        t_span: tuple[float, float],
        h: float = 0.01,
    ) -> DEResult:
        """Classical Runge-Kutta 4th order method.

        Args:
            f: function f(t, y) returning dy/dt
            y0: initial state vector
            t_span: (t_start, t_end)
            h: step size

        Returns:
            t array, y array (shape: n_steps × n_dims)
        """
        try:
            t0, tf = t_span
            n_steps = int((tf - t0) / h) + 1
            t = np.linspace(t0, tf, n_steps)
            y = np.zeros((n_steps, len(y0)))
            y[0] = y0

            for i in range(n_steps - 1):
                ti = t[i]
                yi = y[i]
                k1 = np.array(f(ti, yi))
                k2 = np.array(f(ti + h / 2, yi + h * k1 / 2))
                k3 = np.array(f(ti + h / 2, yi + h * k2 / 2))
                k4 = np.array(f(ti + h, yi + h * k3))
                y[i + 1] = yi + (h / 6) * (k1 + 2 * k2 + 2 * k3 + k4)

            return DEResult(
                success=True,
                result={"t": t.tolist(), "y": y.tolist()},
                metadata={"method": "rk4", "h": h, "n_steps": n_steps},
            )
        except Exception as e:
            return DEResult(success=False, error=str(e))

    @staticmethod
    def solve_ode_scipy(
        f: Callable[[float, np.ndarray], np.ndarray],
        y0: np.ndarray,
        t_span: tuple[float, float],
        num_points: int = 200,
        method: str = "RK45",
    ) -> DEResult:
        """Solve ODE using scipy.integrate.solve_ivp (adaptive).

        Args:
            f: function f(t, y) returning dy/dt
            y0: initial state vector
            t_span: (t_start, t_end)
            num_points: number of evaluation points
            method: 'RK45', 'DOP853', 'Radau', 'BDF', 'LSODA'

        Returns:
            t array, y array
        """
        try:
            t_eval = np.linspace(t_span[0], t_span[1], num_points)
            sol = scipy.integrate.solve_ivp(
                f, t_span, y0, t_eval=t_eval, method=method,
                rtol=1e-8, atol=1e-8,
            )
            return DEResult(
                success=sol.success,
                result={"t": sol.t.tolist(), "y": sol.y.tolist()},
                metadata={"method": method, "num_points": num_points,
                          "nfev": getattr(sol, "nfev", None)},
            )
        except Exception as e:
            return DEResult(success=False, error=str(e))

    # ---- Phase Portraits ----

    @staticmethod
    def phase_portrait(
        f: Callable[[float, np.ndarray], np.ndarray],
        x_range: tuple[float, float],
        y_range: tuple[float, float],
        resolution: int = 30,
    ) -> DEResult:
        """Compute vector field for 2D phase portrait.

        Args:
            f: function f(t, [x, y]) returning [dx/dt, dy/dt]
            x_range: (x_min, x_max)
            y_range: (y_min, y_max)
            resolution: grid resolution

        Returns:
            X, Y meshgrids, U, V (normalized vector field components)
        """
        try:
            x = np.linspace(x_range[0], x_range[1], resolution)
            y = np.linspace(y_range[0], y_range[1], resolution)
            X, Y = np.meshgrid(x, y)

            U = np.zeros_like(X)
            V = np.zeros_like(Y)

            for i in range(resolution):
                for j in range(resolution):
                    deriv = f(0, [X[i, j], Y[i, j]])
                    U[i, j] = deriv[0]
                    V[i, j] = deriv[1]

            # Normalize for visualization
            magnitude = np.sqrt(U**2 + V**2)
            magnitude[magnitude == 0] = 1
            U = U / magnitude
            V = V / magnitude

            return DEResult(
                success=True,
                result={"X": X.tolist(), "Y": Y.tolist(),
                        "U": U.tolist(), "V": V.tolist()},
                metadata={"x_range": x_range, "y_range": y_range,
                          "resolution": resolution},
            )
        except Exception as e:
            return DEResult(success=False, error=str(e))

    @staticmethod
    def nullclines(
        f: Callable[[float, np.ndarray], np.ndarray],
        x_range: tuple[float, float],
        y_range: tuple[float, float],
        resolution: int = 200,
    ) -> DEResult:
        """Compute nullclines for 2D system: where dx/dt=0 or dy/dt=0.

        Returns x-nullcline (dx/dt=0) and y-nullcline (dy/dt=0) as contour data.
        """
        try:
            x = np.linspace(x_range[0], x_range[1], resolution)
            y = np.linspace(y_range[0], y_range[1], resolution)
            X, Y = np.meshgrid(x, y)

            DX = np.zeros_like(X)
            DY = np.zeros_like(Y)

            for i in range(resolution):
                for j in range(resolution):
                    deriv = f(0, [X[i, j], Y[i, j]])
                    DX[i, j] = deriv[0]
                    DY[i, j] = deriv[1]

            return DEResult(
                success=True,
                result={"X": X.tolist(), "Y": Y.tolist(),
                        "DX": DX.tolist(), "DY": DY.tolist()},
                metadata={"x_range": x_range, "y_range": y_range},
            )
        except Exception as e:
            return DEResult(success=False, error=str(e))

    # ---- Jacobian & Stability ----

    @staticmethod
    def jacobian_eigenvalues(
        f: Callable[[float, np.ndarray], np.ndarray],
        point: tuple[float, float],
        eps: float = 1e-6,
    ) -> DEResult:
        """Numerically compute eigenvalues of Jacobian at a fixed point.

        Uses finite differences to approximate the Jacobian, then computes
        eigenvalues to determine stability.

        Args:
            f: function f(t, [x, y]) returning [dx/dt, dy/dt]
            point: (x, y) fixed point
            eps: finite difference step

        Returns:
            eigenvalues (complex), stability classification
        """
        try:
            x0, y0 = point
            f0 = np.array(f(0, [x0, y0]))

            f_dx = np.array(f(0, [x0 + eps, y0]))
            f_dy = np.array(f(0, [x0, y0 + eps]))

            J = np.column_stack([(f_dx - f0) / eps, (f_dy - f0) / eps])
            eigenvals = np.linalg.eigvals(J)

            # Stability classification
            real_parts = eigenvals.real
            if np.all(real_parts < -1e-10):
                stability = "stable_node" if np.all(np.isreal(eigenvals)) else "stable_spiral"
            elif np.all(real_parts > 1e-10):
                stability = "unstable_node" if np.all(np.isreal(eigenvals)) else "unstable_spiral"
            elif np.all(np.abs(real_parts) < 1e-10):
                stability = "center"
            else:
                stability = "saddle"

            return DEResult(
                success=True,
                result={
                    "eigenvalues": [complex(v.real, v.imag) for v in eigenvals],
                    "stability": stability,
                    "jacobian": J.tolist(),
                },
                metadata={"point": point},
            )
        except Exception as e:
            return DEResult(success=False, error=str(e))

    # ---- Specialized Systems ----

    @staticmethod
    def lotka_volterra(
        t: float, state: np.ndarray,
        alpha: float = 1.0, beta: float = 0.1,
        gamma: float = 1.5, delta: float = 0.075,
    ) -> list[float]:
        """Lotka-Volterra predator-prey model.

        dx/dt = α·x - β·x·y  (prey)
        dy/dt = δ·x·y - γ·y  (predator)

        Equilibrium: (γ/δ, α/β)
        """
        x, y = state
        dx = alpha * x - beta * x * y
        dy = delta * x * y - gamma * y
        return [dx, dy]

    @staticmethod
    def pendulum(
        t: float, state: np.ndarray,
        g: float = 9.81, L: float = 1.0, b: float = 0.1,
    ) -> list[float]:
        """Damped pendulum.

        dθ/dt = ω
        dω/dt = -(g/L)·sin(θ) - b·ω

        Args:
            g: gravitational acceleration
            L: pendulum length
            b: damping coefficient
        """
        theta, omega = state
        dtheta = omega
        domega = -(g / L) * np.sin(theta) - b * omega
        return [dtheta, domega]

    @staticmethod
    def harmonic_oscillator(
        t: float, state: np.ndarray,
        omega0: float = 1.0, zeta: float = 0.0,
    ) -> list[float]:
        """Damped harmonic oscillator: x'' + 2ζω₀x' + ω₀²x = 0.

        Converted to first-order system:
        dx/dt = v
        dv/dt = -ω₀²·x - 2ζω₀·v

        Args:
            omega0: natural frequency
            zeta: damping ratio (0=undamped, <1=underdamped, 1=critically damped, >1=overdamped)
        """
        x, v = state
        dx = v
        dv = -(omega0 ** 2) * x - 2 * zeta * omega0 * v
        return [dx, dv]

    @staticmethod
    def van_der_pol(
        t: float, state: np.ndarray, mu: float = 1.0,
    ) -> list[float]:
        """Van der Pol oscillator: x'' - μ(1-x²)x' + x = 0.

        dx/dt = y
        dy/dt = μ(1-x²)y - x
        """
        x, y = state
        dx = y
        dy = mu * (1 - x**2) * y - x
        return [dx, dy]

    @staticmethod
    def lorenz(
        t: float, state: np.ndarray,
        sigma: float = 10.0, rho: float = 28.0, beta: float = 8.0 / 3.0,
    ) -> list[float]:
        """Lorenz attractor (chaotic system).

        dx/dt = σ(y - x)
        dy/dt = x(ρ - z) - y
        dz/dt = xy - βz
        """
        x, y, z = state
        dx = sigma * (y - x)
        dy = x * (rho - z) - y
        dz = x * y - beta * z
        return [dx, dy, dz]

    # ---- Bifurcation ----

    @staticmethod
    def bifurcation_diagram(
        f: Callable,
        param_range: tuple[float, float],
        param_name: str = "mu",
        y0: tuple[float, ...] = (2.0, 0.0),
        t_transient: float = 100.0,
        t_sample: float = 100.0,
        n_params: int = 200,
        sample_every: int = 5,
    ) -> DEResult:
        """Generate bifurcation diagram by varying a parameter.

        For each parameter value, integrates the ODE, discards transient,
        and samples the steady-state behavior.

        Args:
            f: function f(t, state, **{param_name: value})
            param_range: (param_min, param_max)
            param_name: name of the parameter to vary
            y0: initial state
            t_transient: time to discard as transient
            t_sample: time to sample after transient
            n_params: number of parameter values
            sample_every: sample every N-th point

        Returns:
            list of {param, x, y} points
        """
        try:
            params = np.linspace(param_range[0], param_range[1], n_params)
            results = []

            for p in params:
                def f_param(t, state):
                    kwargs = {param_name: p}
                    return f(t, state, **kwargs)

                sol = scipy.integrate.solve_ivp(
                    f_param, [0, t_transient + t_sample], list(y0),
                    max_step=0.1, rtol=1e-8, atol=1e-8,
                )

                n = len(sol.t)
                start = int(n * t_transient / (t_transient + t_sample))
                for i in range(start, n, sample_every):
                    results.append({
                        "param": float(p),
                        "x": float(sol.y[0, i]),
                        "y": float(sol.y[1, i]) if sol.y.shape[0] > 1 else 0.0,
                    })

            return DEResult(
                success=True,
                result=results,
                metadata={"param_name": param_name, "n_params": n_params,
                          "n_points": len(results)},
            )
        except Exception as e:
            return DEResult(success=False, error=str(e))

    @staticmethod
    def logistic_map_bifurcation(
        r_range: tuple[float, float] = (2.5, 4.0),
        n_r: int = 300,
        n_transient: int = 200,
        n_sample: int = 100,
    ) -> DEResult:
        """Generate bifurcation diagram for the logistic map: x_{n+1} = r·x_n·(1-x_n).

        Classic example of period-doubling route to chaos.
        """
        try:
            r_values = np.linspace(r_range[0], r_range[1], n_r)
            results = []

            for r in r_values:
                x = 0.5
                for _ in range(n_transient):
                    x = r * x * (1 - x)
                for _ in range(n_sample):
                    x = r * x * (1 - x)
                    results.append({"r": float(r), "x": float(x)})

            return DEResult(
                success=True,
                result=results,
                metadata={"r_range": r_range, "n_r": n_r, "n_points": len(results)},
            )
        except Exception as e:
            return DEResult(success=False, error=str(e))

    # ---- Utility ----

    @staticmethod
    def find_equilibria_2d(
        f: Callable[[float, np.ndarray], np.ndarray],
        x_range: tuple[float, float],
        y_range: tuple[float, float],
        n_guesses: int = 20,
    ) -> DEResult:
        """Find equilibrium points of a 2D system using root-finding.

        Tries multiple initial guesses within the range.
        """
        try:
            def g(vars):
                x, y = vars
                deriv = f(0, [x, y])
                return [deriv[0], deriv[1]]

            rng = np.random.RandomState(42)
            equilibria = []
            seen = set()

            for _ in range(n_guesses):
                guess = [
                    rng.uniform(x_range[0], x_range[1]),
                    rng.uniform(y_range[0], y_range[1]),
                ]
                try:
                    sol = scipy.optimize.fsolve(g, guess, maxfev=1000, xtol=1e-8)
                    key = (round(sol[0], 4), round(sol[1], 4))
                    if key not in seen:
                        # Verify it's actually an equilibrium
                        deriv = f(0, sol)
                        if np.linalg.norm(deriv) < 1e-6:
                            seen.add(key)
                            equilibria.append({"x": float(sol[0]), "y": float(sol[1])})
                except Exception:
                    pass

            return DEResult(
                success=True,
                result=equilibria,
                metadata={"n_found": len(equilibria)},
            )
        except Exception as e:
            return DEResult(success=False, error=str(e))
