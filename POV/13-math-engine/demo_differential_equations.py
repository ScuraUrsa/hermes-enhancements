"""
Differential Equations Demo — ODE Systems, Phase Portraits, Bifurcations.

Demonstrates:
- Phase portraits for 2D ODE systems
- Lotka-Volterra (predator-prey)
- Lorenz attractor (chaos)
- Van der Pol oscillator
- Bifurcation diagrams
- Stability analysis (eigenvalues of Jacobian)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import integrate

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def lotka_volterra(t, state, alpha=1.0, beta=0.1, gamma=1.5, delta=0.075):
    """Lotka-Volterra predator-prey model.
    dx/dt = alpha*x - beta*x*y  (prey)
    dy/dt = delta*x*y - gamma*y  (predator)
    """
    x, y = state
    dx = alpha * x - beta * x * y
    dy = delta * x * y - gamma * y
    return [dx, dy]


def lorenz(t, state, sigma=10.0, rho=28.0, beta=8.0 / 3.0):
    """Lorenz attractor (chaotic system)."""
    x, y, z = state
    dx = sigma * (y - x)
    dy = x * (rho - z) - y
    dz = x * y - beta * z
    return [dx, dy, dz]


def van_der_pol(t, state, mu=1.0):
    """Van der Pol oscillator.
    dx/dt = y
    dy/dt = mu*(1 - x²)*y - x
    """
    x, y = state
    dx = y
    dy = mu * (1 - x**2) * y - x
    return [dx, dy]


def pendulum(t, state, g=9.81, L=1.0, b=0.1):
    """Damped pendulum.
    dθ/dt = ω
    dω/dt = -(g/L)*sin(θ) - b*ω
    """
    theta, omega = state
    dtheta = omega
    domega = -(g / L) * np.sin(theta) - b * omega
    return [dtheta, domega]


def compute_phase_portrait(f, x_range, y_range, resolution=30):
    """Compute vector field for phase portrait."""
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

    # Normalize
    magnitude = np.sqrt(U**2 + V**2)
    magnitude[magnitude == 0] = 1
    U = U / magnitude
    V = V / magnitude

    return X, Y, U, V


def jacobian_eigenvalues(f, point, eps=1e-6):
    """Numerically compute eigenvalues of Jacobian at a point."""
    x0, y0 = point
    f0 = np.array(f(0, [x0, y0]))

    # Finite differences
    f_dx = np.array(f(0, [x0 + eps, y0]))
    f_dy = np.array(f(0, [x0, y0 + eps]))

    J = np.column_stack([(f_dx - f0) / eps, (f_dy - f0) / eps])
    eigenvals = np.linalg.eigvals(J)

    return eigenvals


def bifurcation_diagram(f, param_range, param_name="mu",
                        x0=2.0, y0=0.0, transient=500, n_points=200):
    """Generate bifurcation diagram by varying a parameter."""
    params = np.linspace(param_range[0], param_range[1], n_points)
    results = []

    for p in params:
        # Create function with fixed parameter
        def f_param(t, state):
            kwargs = {param_name: p}
            return f(t, state, **kwargs)

        sol = integrate.solve_ivp(
            f_param, [0, 200], [x0, y0],
            max_step=0.1, rtol=1e-8, atol=1e-8,
        )

        # Take last portion (after transient)
        n = len(sol.t)
        start = max(0, n - transient)
        for i in range(start, n, 5):
            results.append({"param": float(p), "x": float(sol.y[0, i])})

    return results


def main():
    print("=" * 60)
    print("DIFFERENTIAL EQUATIONS — Phase Portraits, Chaos, Bifurcations")
    print("=" * 60)

    # 1. Lotka-Volterra
    print("\n--- 1. Lotka-Volterra (Predator-Prey) ---")
    sol_lv = integrate.solve_ivp(
        lotka_volterra, [0, 50], [10, 5],
        max_step=0.1, rtol=1e-8, atol=1e-8,
    )
    print(f"  Prey range: [{sol_lv.y[0].min():.1f}, {sol_lv.y[0].max():.1f}]")
    print(f"  Predator range: [{sol_lv.y[1].min():.1f}, {sol_lv.y[1].max():.1f}]")

    # Stability at equilibrium (gamma/delta, alpha/beta)
    eq = (1.5 / 0.075, 1.0 / 0.1)  # (20, 10)
    eigenvals = jacobian_eigenvalues(lotka_volterra, eq)
    print(f"  Equilibrium: ({eq[0]:.1f}, {eq[1]:.1f})")
    print(f"  Jacobian eigenvalues: {eigenvals[0]:.3f}, {eigenvals[1]:.3f}")
    print(f"  Stability: {'Center (neutrally stable)' if abs(eigenvals[0].real) < 1e-6 else 'Stable' if eigenvals[0].real < 0 else 'Unstable'}")

    # 2. Lorenz attractor
    print("\n--- 2. Lorenz Attractor (Chaos) ---")
    sol_lorenz = integrate.solve_ivp(
        lorenz, [0, 40], [1.0, 1.0, 1.0],
        max_step=0.01, rtol=1e-8, atol=1e-8,
    )
    print(f"  x range: [{sol_lorenz.y[0].min():.1f}, {sol_lorenz.y[0].max():.1f}]")
    print(f"  y range: [{sol_lorenz.y[1].min():.1f}, {sol_lorenz.y[1].max():.1f}]")
    print(f"  z range: [{sol_lorenz.y[2].min():.1f}, {sol_lorenz.y[2].max():.1f}]")

    # 3. Van der Pol
    print("\n--- 3. Van der Pol Oscillator ---")
    for mu in [0.5, 2.0, 5.0]:
        def vdp_mu(t, state):
            return van_der_pol(t, state, mu=mu)
        sol_vdp = integrate.solve_ivp(
            vdp_mu, [0, 30], [2.0, 0.0],
            max_step=0.05, rtol=1e-8, atol=1e-8,
        )
        print(f"  μ={mu}: limit cycle amplitude ≈ {np.max(np.abs(sol_vdp.y[0])):.2f}")

    # 4. Pendulum
    print("\n--- 4. Damped Pendulum ---")
    sol_pend = integrate.solve_ivp(
        pendulum, [0, 20], [np.pi / 2, 0.0],
        max_step=0.05, rtol=1e-8, atol=1e-8,
    )
    print(f"  Final angle: {sol_pend.y[0, -1]:.3f} rad")
    print(f"  Final angular velocity: {sol_pend.y[1, -1]:.3f} rad/s")

    # ---- PLOTS ----
    fig = plt.figure(figsize=(18, 14))

    # Lotka-Volterra time series
    ax1 = fig.add_subplot(3, 3, 1)
    ax1.plot(sol_lv.t, sol_lv.y[0], linewidth=1.5, label="Prey", color="blue")
    ax1.plot(sol_lv.t, sol_lv.y[1], linewidth=1.5, label="Predator", color="red")
    ax1.set_xlabel("Time")
    ax1.set_ylabel("Population")
    ax1.set_title("Lotka-Volterra: Time Series")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Lotka-Volterra phase portrait
    ax2 = fig.add_subplot(3, 3, 2)
    X, Y, U, V = compute_phase_portrait(lotka_volterra, [0, 40], [0, 30], resolution=25)
    ax2.streamplot(X, Y, U, V, density=1.5, color="gray")
    ax2.plot(sol_lv.y[0], sol_lv.y[1], linewidth=2, color="red", label="Trajectory")
    ax2.scatter(eq[0], eq[1], s=100, color="green", marker="o", zorder=5,
                label=f"Equilibrium ({eq[0]:.0f}, {eq[1]:.0f})")
    ax2.set_xlabel("Prey")
    ax2.set_ylabel("Predator")
    ax2.set_title("Lotka-Volterra: Phase Portrait")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Lorenz 3D
    ax3 = fig.add_subplot(3, 3, 3, projection="3d")
    ax3.plot(sol_lorenz.y[0], sol_lorenz.y[1], sol_lorenz.y[2],
             linewidth=0.5, color="blue", alpha=0.8)
    ax3.set_xlabel("X")
    ax3.set_ylabel("Y")
    ax3.set_zlabel("Z")
    ax3.set_title("Lorenz Attractor (Chaos)")

    # Lorenz time series
    ax4 = fig.add_subplot(3, 3, 4)
    ax4.plot(sol_lorenz.t, sol_lorenz.y[0], linewidth=0.5, alpha=0.7, label="x", color="blue")
    ax4.plot(sol_lorenz.t, sol_lorenz.y[2], linewidth=0.5, alpha=0.7, label="z", color="red")
    ax4.set_xlabel("Time")
    ax4.set_ylabel("Value")
    ax4.set_title("Lorenz: x(t) and z(t)")
    ax4.legend(fontsize=8)
    ax4.grid(True, alpha=0.3)

    # Van der Pol phase portraits
    ax5 = fig.add_subplot(3, 3, 5)
    colors = {0.5: "blue", 2.0: "green", 5.0: "red"}
    for mu, color in colors.items():
        def vdp_mu(t, state):
            return van_der_pol(t, state, mu=mu)
        sol = integrate.solve_ivp(vdp_mu, [0, 30], [2.0, 0.0],
                                  max_step=0.05, rtol=1e-8, atol=1e-8)
        ax5.plot(sol.y[0], sol.y[1], linewidth=1.5, color=color, label=f"μ={mu}")
    ax5.set_xlabel("x")
    ax5.set_ylabel("y")
    ax5.set_title("Van der Pol: Limit Cycles")
    ax5.legend(fontsize=8)
    ax5.grid(True, alpha=0.3)

    # Pendulum phase portrait
    ax6 = fig.add_subplot(3, 3, 6)
    Xp, Yp, Up, Vp = compute_phase_portrait(pendulum, [-np.pi, np.pi], [-8, 8], resolution=25)
    ax6.streamplot(Xp, Yp, Up, Vp, density=1.5, color="gray")
    ax6.plot(sol_pend.y[0], sol_pend.y[1], linewidth=2, color="red")
    ax6.scatter(0, 0, s=100, color="green", marker="o", zorder=5, label="Stable equilibrium")
    ax6.set_xlabel("θ (angle)")
    ax6.set_ylabel("ω (angular velocity)")
    ax6.set_title("Damped Pendulum: Phase Portrait")
    ax6.legend(fontsize=8)
    ax6.grid(True, alpha=0.3)

    # Bifurcation diagram (logistic map as proxy)
    ax7 = fig.add_subplot(3, 3, 7)
    r_values = np.linspace(2.5, 4.0, 100)
    for r in r_values:
        x = 0.5
        for _ in range(100):
            x = r * x * (1 - x)
        for _ in range(50):
            x = r * x * (1 - x)
            ax7.scatter(r, x, s=0.5, color="black", alpha=0.3)
    ax7.set_xlabel("r")
    ax7.set_ylabel("x")
    ax7.set_title("Logistic Map Bifurcation Diagram")

    # Pendulum time series
    ax8 = fig.add_subplot(3, 3, 8)
    ax8.plot(sol_pend.t, sol_pend.y[0], linewidth=1.5, label="θ (angle)", color="blue")
    ax8.plot(sol_pend.t, sol_pend.y[1], linewidth=1.5, label="ω (velocity)", color="red")
    ax8.set_xlabel("Time (s)")
    ax8.set_ylabel("Value")
    ax8.set_title("Damped Pendulum: Time Series")
    ax8.legend(fontsize=8)
    ax8.grid(True, alpha=0.3)

    # Lorenz x-y projection
    ax9 = fig.add_subplot(3, 3, 9)
    ax9.plot(sol_lorenz.y[0], sol_lorenz.y[1], linewidth=0.5, color="purple", alpha=0.8)
    ax9.set_xlabel("X")
    ax9.set_ylabel("Y")
    ax9.set_title("Lorenz: X-Y Projection")
    ax9.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "differential_equations.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n✅ Chart saved: {path}")


if __name__ == "__main__":
    main()
