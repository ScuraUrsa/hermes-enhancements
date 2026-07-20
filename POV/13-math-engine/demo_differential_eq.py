"""
Differential Equations Demo — ODE Solvers, Phase Portraits, Bifurcations.

Generates comprehensive plots to output/:
- Euler vs RK4 vs scipy comparison
- Phase portraits (pendulum, harmonic oscillator)
- Lotka-Volterra predator-prey
- Van der Pol limit cycles
- Bifurcation diagrams (logistic map, ODE parameter sweep)
- Stability analysis
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from differential_eq import DifferentialEquations

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

de = DifferentialEquations()


def demo_ode_solvers():
    """Compare Euler, RK4, and scipy on a simple ODE."""
    print("\n--- 1. ODE Solver Comparison ---")

    # dy/dt = -2y + sin(t), y(0) = 1
    # Exact solution: y(t) = (6/5)e^{-2t} + (2/5)sin(t) - (1/5)cos(t)
    def f(t, y):
        return [-2 * y[0] + np.sin(t)]

    y0 = [1.0]
    t_span = (0.0, 5.0)

    r_euler = de.solve_ode_euler(f, y0, t_span, h=0.05)
    r_rk4 = de.solve_ode_rk4(f, y0, t_span, h=0.05)
    r_scipy = de.solve_ode_scipy(f, y0, t_span, num_points=200)

    t_euler = np.array(r_euler.result["t"])
    y_euler = np.array(r_euler.result["y"])[:, 0]
    t_rk4 = np.array(r_rk4.result["t"])
    y_rk4 = np.array(r_rk4.result["y"])[:, 0]
    t_scipy = np.array(r_scipy.result["t"])
    y_scipy = np.array(r_scipy.result["y"])[0]

    # Exact
    t_exact = np.linspace(0, 5, 500)
    y_exact = (6/5) * np.exp(-2*t_exact) + (2/5)*np.sin(t_exact) - (1/5)*np.cos(t_exact)

    # Errors at final point
    err_euler = abs(y_euler[-1] - ((6/5)*np.exp(-10) + (2/5)*np.sin(5) - (1/5)*np.cos(5)))
    err_rk4 = abs(y_rk4[-1] - ((6/5)*np.exp(-10) + (2/5)*np.sin(5) - (1/5)*np.cos(5)))
    print(f"  Euler error at t=5: {err_euler:.2e}")
    print(f"  RK4 error at t=5:   {err_rk4:.2e}")

    return t_euler, y_euler, t_rk4, y_rk4, t_scipy, y_scipy, t_exact, y_exact


def demo_lotka_volterra():
    """Lotka-Volterra predator-prey with phase portrait."""
    print("\n--- 2. Lotka-Volterra (Predator-Prey) ---")

    y0 = [10.0, 5.0]
    t_span = (0.0, 50.0)

    r = de.solve_ode_scipy(de.lotka_volterra, y0, t_span, num_points=500)
    t = np.array(r.result["t"])
    y = np.array(r.result["y"])

    # Equilibrium
    alpha, beta, gamma, delta = 1.0, 0.1, 1.5, 0.075
    eq = (gamma / delta, alpha / beta)
    print(f"  Equilibrium: ({eq[0]:.1f}, {eq[1]:.1f})")

    # Stability
    stab = de.jacobian_eigenvalues(de.lotka_volterra, eq)
    print(f"  Stability: {stab.result['stability']}")
    print(f"  Eigenvalues: {[complex(v.real, v.imag) for v in stab.result['eigenvalues']]}")

    # Phase portrait
    pp = de.phase_portrait(de.lotka_volterra, (0, 40), (0, 30), resolution=25)

    return t, y, eq, pp, stab


def demo_pendulum():
    """Damped pendulum phase portrait and time series."""
    print("\n--- 3. Damped Pendulum ---")

    y0 = [np.pi / 2, 0.0]  # Start at 90 degrees
    t_span = (0.0, 20.0)

    r = de.solve_ode_scipy(de.pendulum, y0, t_span, num_points=300)
    t = np.array(r.result["t"])
    y = np.array(r.result["y"])

    print(f"  Final angle: {y[0, -1]:.3f} rad")
    print(f"  Final angular velocity: {y[1, -1]:.3f} rad/s")

    # Phase portrait
    pp = de.phase_portrait(de.pendulum, (-np.pi, np.pi), (-8, 8), resolution=25)

    # Stability at (0,0)
    stab = de.jacobian_eigenvalues(de.pendulum, (0.0, 0.0))
    print(f"  Stability at (0,0): {stab.result['stability']}")

    return t, y, pp, stab


def demo_harmonic_oscillator():
    """Harmonic oscillator with different damping ratios."""
    print("\n--- 4. Harmonic Oscillator ---")

    y0 = [1.0, 0.0]
    t_span = (0.0, 20.0)

    zeta_values = [0.0, 0.1, 0.5, 1.0, 2.0]
    solutions = {}

    for zeta in zeta_values:
        def f_ho(t, state):
            return de.harmonic_oscillator(t, state, omega0=1.0, zeta=zeta)

        r = de.solve_ode_scipy(f_ho, y0, t_span, num_points=300)
        t = np.array(r.result["t"])
        y = np.array(r.result["y"])
        solutions[zeta] = (t, y)

        label = {0.0: "undamped", 0.1: "underdamped", 0.5: "underdamped",
                 1.0: "critically damped", 2.0: "overdamped"}[zeta]
        print(f"  ζ={zeta} ({label}): final x={y[0, -1]:.4f}")

    return solutions


def demo_van_der_pol():
    """Van der Pol oscillator limit cycles."""
    print("\n--- 5. Van der Pol Oscillator ---")

    y0 = [2.0, 0.0]
    t_span = (0.0, 30.0)

    mu_values = [0.5, 1.0, 2.0, 5.0]
    solutions = {}

    for mu in mu_values:
        def f_vdp(t, state):
            return de.van_der_pol(t, state, mu=mu)

        r = de.solve_ode_scipy(f_vdp, y0, t_span, num_points=500)
        t = np.array(r.result["t"])
        y = np.array(r.result["y"])
        solutions[mu] = (t, y)
        print(f"  μ={mu}: limit cycle amplitude ≈ {np.max(np.abs(y[0])):.2f}")

    return solutions


def demo_bifurcation():
    """Bifurcation diagrams."""
    print("\n--- 6. Bifurcation Diagrams ---")

    # Logistic map
    r_log = de.logistic_map_bifurcation(r_range=(2.5, 4.0), n_r=400)
    print(f"  Logistic map: {r_log.metadata['n_points']} points")

    # Van der Pol bifurcation (varying mu)
    r_vdp = de.bifurcation_diagram(
        de.van_der_pol,
        param_range=(0.1, 5.0),
        param_name="mu",
        y0=(2.0, 0.0),
        t_transient=50.0,
        t_sample=50.0,
        n_params=50,
    )
    print(f"  Van der Pol bifurcation: {r_vdp.metadata['n_points']} points")

    return r_log, r_vdp


# ---- PLOTS ----

def main():
    print("=" * 60)
    print("DIFFERENTIAL EQUATIONS — Solvers, Phase Portraits, Bifurcations")
    print("=" * 60)

    # Run all demos
    t_euler, y_euler, t_rk4, y_rk4, t_scipy, y_scipy, t_exact, y_exact = demo_ode_solvers()
    t_lv, y_lv, eq_lv, pp_lv, stab_lv = demo_lotka_volterra()
    t_pend, y_pend, pp_pend, stab_pend = demo_pendulum()
    ho_solutions = demo_harmonic_oscillator()
    vdp_solutions = demo_van_der_pol()
    r_log, r_vdp = demo_bifurcation()

    # ---- FIGURE 1: Main ----
    fig = plt.figure(figsize=(20, 18))

    # 1. ODE solver comparison
    ax1 = fig.add_subplot(3, 4, 1)
    ax1.plot(t_exact, y_exact, "k-", linewidth=2, label="Exact")
    ax1.plot(t_euler, y_euler, "o-", color="red", markersize=2, linewidth=0.8, label="Euler (h=0.05)")
    ax1.plot(t_rk4, y_rk4, "s-", color="green", markersize=2, linewidth=0.8, label="RK4 (h=0.05)")
    ax1.plot(t_scipy, y_scipy, "-", color="blue", linewidth=1.5, label="scipy RK45")
    ax1.set_xlabel("t")
    ax1.set_ylabel("y")
    ax1.set_title("ODE Solver Comparison: dy/dt=-2y+sin(t)")
    ax1.legend(fontsize=6)
    ax1.grid(True, alpha=0.3)

    # 2. Lotka-Volterra time series
    ax2 = fig.add_subplot(3, 4, 2)
    ax2.plot(t_lv, y_lv[0], linewidth=1.5, label="Prey", color="blue")
    ax2.plot(t_lv, y_lv[1], linewidth=1.5, label="Predator", color="red")
    ax2.set_xlabel("Time")
    ax2.set_ylabel("Population")
    ax2.set_title("Lotka-Volterra: Time Series")
    ax2.legend(fontsize=7)
    ax2.grid(True, alpha=0.3)

    # 3. Lotka-Volterra phase portrait
    ax3 = fig.add_subplot(3, 4, 3)
    X = np.array(pp_lv.result["X"])
    Y = np.array(pp_lv.result["Y"])
    U = np.array(pp_lv.result["U"])
    V = np.array(pp_lv.result["V"])
    ax3.streamplot(X, Y, U, V, density=1.5, color="gray")
    ax3.plot(y_lv[0], y_lv[1], linewidth=2, color="red", label="Trajectory")
    ax3.scatter(eq_lv[0], eq_lv[1], s=100, color="green", marker="o", zorder=5,
                label=f"Eq ({eq_lv[0]:.0f},{eq_lv[1]:.0f})")
    ax3.set_xlabel("Prey")
    ax3.set_ylabel("Predator")
    ax3.set_title("Lotka-Volterra: Phase Portrait")
    ax3.legend(fontsize=7)
    ax3.grid(True, alpha=0.3)

    # 4. Pendulum time series
    ax4 = fig.add_subplot(3, 4, 4)
    ax4.plot(t_pend, y_pend[0], linewidth=1.5, label="θ (angle)", color="blue")
    ax4.plot(t_pend, y_pend[1], linewidth=1.5, label="ω (velocity)", color="red")
    ax4.set_xlabel("Time (s)")
    ax4.set_ylabel("Value")
    ax4.set_title("Damped Pendulum: Time Series")
    ax4.legend(fontsize=7)
    ax4.grid(True, alpha=0.3)

    # 5. Pendulum phase portrait
    ax5 = fig.add_subplot(3, 4, 5)
    Xp = np.array(pp_pend.result["X"])
    Yp = np.array(pp_pend.result["Y"])
    Up = np.array(pp_pend.result["U"])
    Vp = np.array(pp_pend.result["V"])
    ax5.streamplot(Xp, Yp, Up, Vp, density=1.5, color="gray")
    ax5.plot(y_pend[0], y_pend[1], linewidth=2, color="red")
    ax5.scatter(0, 0, s=100, color="green", marker="o", zorder=5, label="Stable eq")
    ax5.set_xlabel("θ (angle)")
    ax5.set_ylabel("ω (angular velocity)")
    ax5.set_title("Damped Pendulum: Phase Portrait")
    ax5.legend(fontsize=7)
    ax5.grid(True, alpha=0.3)

    # 6. Harmonic oscillator time series
    ax6 = fig.add_subplot(3, 4, 6)
    colors_ho = {0.0: "blue", 0.1: "green", 0.5: "orange", 1.0: "red", 2.0: "purple"}
    for zeta, (t, y) in ho_solutions.items():
        label = {0.0: "ζ=0", 0.1: "ζ=0.1", 0.5: "ζ=0.5", 1.0: "ζ=1", 2.0: "ζ=2"}[zeta]
        ax6.plot(t, y[0], linewidth=1.2, color=colors_ho[zeta], label=label)
    ax6.set_xlabel("t")
    ax6.set_ylabel("x(t)")
    ax6.set_title("Harmonic Oscillator: Damping")
    ax6.legend(fontsize=7)
    ax6.grid(True, alpha=0.3)

    # 7. Harmonic oscillator phase portrait
    ax7 = fig.add_subplot(3, 4, 7)
    for zeta, (t, y) in ho_solutions.items():
        ax7.plot(y[0], y[1], linewidth=1.2, color=colors_ho[zeta],
                 label=f"ζ={zeta}")
    ax7.set_xlabel("x")
    ax7.set_ylabel("v")
    ax7.set_title("Harmonic Oscillator: Phase")
    ax7.legend(fontsize=6)
    ax7.grid(True, alpha=0.3)

    # 8. Van der Pol limit cycles
    ax8 = fig.add_subplot(3, 4, 8)
    colors_vdp = {0.5: "blue", 1.0: "green", 2.0: "orange", 5.0: "red"}
    for mu, (t, y) in vdp_solutions.items():
        ax8.plot(y[0], y[1], linewidth=1.5, color=colors_vdp[mu], label=f"μ={mu}")
    ax8.set_xlabel("x")
    ax8.set_ylabel("y")
    ax8.set_title("Van der Pol: Limit Cycles")
    ax8.legend(fontsize=7)
    ax8.grid(True, alpha=0.3)

    # 9. Van der Pol time series
    ax9 = fig.add_subplot(3, 4, 9)
    for mu, (t, y) in vdp_solutions.items():
        ax9.plot(t, y[0], linewidth=1, color=colors_vdp[mu], label=f"μ={mu}", alpha=0.7)
    ax9.set_xlabel("t")
    ax9.set_ylabel("x(t)")
    ax9.set_title("Van der Pol: Time Series")
    ax9.legend(fontsize=7)
    ax9.grid(True, alpha=0.3)

    # 10. Logistic map bifurcation
    ax10 = fig.add_subplot(3, 4, 10)
    log_data = r_log.result
    r_vals = [d["r"] for d in log_data]
    x_vals = [d["x"] for d in log_data]
    ax10.scatter(r_vals, x_vals, s=0.3, color="black", alpha=0.4)
    ax10.set_xlabel("r")
    ax10.set_ylabel("x")
    ax10.set_title("Logistic Map Bifurcation")
    ax10.grid(True, alpha=0.3)

    # 11. Van der Pol bifurcation
    ax11 = fig.add_subplot(3, 4, 11)
    vdp_data = r_vdp.result
    p_vals = [d["param"] for d in vdp_data]
    xv_vals = [d["x"] for d in vdp_data]
    ax11.scatter(p_vals, xv_vals, s=0.5, color="#2196F3", alpha=0.5)
    ax11.set_xlabel("μ")
    ax11.set_ylabel("x (steady state)")
    ax11.set_title("Van der Pol Bifurcation")
    ax11.grid(True, alpha=0.3)

    # 12. Stability summary
    ax12 = fig.add_subplot(3, 4, 12)
    ax12.axis("off")
    stability_text = (
        "Stability Analysis:\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Lotka-Volterra eq ({eq_lv[0]:.0f},{eq_lv[1]:.0f}):\n"
        f"  {stab_lv.result['stability']}\n"
        f"  λ = {[f'{v.real:.3f}{v.imag:+.3f}j' for v in stab_lv.result['eigenvalues']]}\n\n"
        f"Pendulum eq (0,0):\n"
        f"  {stab_pend.result['stability']}\n"
        f"  λ = {[f'{v.real:.3f}{v.imag:+.3f}j' for v in stab_pend.result['eigenvalues']]}\n\n"
        "Harmonic Oscillator:\n"
        "  ζ=0: center (neutrally stable)\n"
        "  ζ<1: stable spiral (underdamped)\n"
        "  ζ=1: stable node (critically damped)\n"
        "  ζ>1: stable node (overdamped)"
    )
    ax12.text(0.05, 0.95, stability_text, transform=ax12.transAxes,
              fontsize=8, verticalalignment="top", fontfamily="monospace")

    plt.tight_layout()
    path = OUTPUT_DIR / "differential_eq_demo.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n✅ Chart saved: {path}")

    # ---- FIGURE 2: Euler vs RK4 error analysis ----
    fig2, axes2 = plt.subplots(1, 2, figsize=(14, 5))

    # Error vs step size
    def f_test(t, y):
        return [-2 * y[0] + np.sin(t)]

    y0_test = [1.0]
    t_span_test = (0.0, 2.0)
    t_ref = np.linspace(0, 2, 1000)
    y_ref = (6/5) * np.exp(-2*t_ref) + (2/5)*np.sin(t_ref) - (1/5)*np.cos(t_ref)

    h_values = [0.2, 0.1, 0.05, 0.025, 0.01]
    euler_errors = []
    rk4_errors = []

    for h in h_values:
        r_e = de.solve_ode_euler(f_test, y0_test, t_span_test, h=h)
        r_r = de.solve_ode_rk4(f_test, y0_test, t_span_test, h=h)
        y_e = np.array(r_e.result["y"])[:, 0]
        y_r = np.array(r_r.result["y"])[:, 0]
        # Interpolate reference to same t
        t_e = np.array(r_e.result["t"])
        y_ref_interp = np.interp(t_e, t_ref, y_ref)
        euler_errors.append(np.max(np.abs(y_e - y_ref_interp)))
        y_ref_interp_r = np.interp(np.array(r_r.result["t"]), t_ref, y_ref)
        rk4_errors.append(np.max(np.abs(y_r - y_ref_interp_r)))

    ax = axes2[0]
    ax.loglog(h_values, euler_errors, "o-", color="red", label="Euler (O(h))")
    ax.loglog(h_values, rk4_errors, "s-", color="green", label="RK4 (O(h⁴))")
    ax.loglog(h_values, [h**1 * 0.5 for h in h_values], "--", color="red", alpha=0.3, label="O(h)")
    ax.loglog(h_values, [h**4 * 10 for h in h_values], "--", color="green", alpha=0.3, label="O(h⁴)")
    ax.set_xlabel("Step size h")
    ax.set_ylabel("Max error")
    ax.set_title("Euler vs RK4: Convergence")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Energy in pendulum
    ax = axes2[1]
    g, L, b = 9.81, 1.0, 0.1
    energy = 0.5 * y_pend[1]**2 + (g/L) * (1 - np.cos(y_pend[0]))
    ax.plot(t_pend, energy, linewidth=1.5, color="#E91E63")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Energy (normalized)")
    ax.set_title("Damped Pendulum: Energy Decay")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path2 = OUTPUT_DIR / "differential_eq_analysis.png"
    plt.savefig(path2, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Chart saved: {path2}")

    print(f"\n✅ All differential equations charts saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
