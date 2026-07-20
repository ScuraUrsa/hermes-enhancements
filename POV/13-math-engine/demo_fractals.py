"""
Fractals & Chaos Demo — Mandelbrot, Julia, Newton, L-Systems.

Demonstrates:
- Mandelbrot set with zoom
- Julia sets for different c values
- Newton fractal (complex root finding)
- L-systems (Koch snowflake, Sierpinski, Dragon curve)
- Burning Ship fractal
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def mandelbrot(width: int = 800, height: int = 600, max_iter: int = 200,
               xmin: float = -2.5, xmax: float = 1.0,
               ymin: float = -1.2, ymax: float = 1.2) -> np.ndarray:
    """Compute Mandelbrot set."""
    x = np.linspace(xmin, xmax, width)
    y = np.linspace(ymin, ymax, height)
    X, Y = np.meshgrid(x, y)
    C = X + 1j * Y
    Z = np.zeros_like(C, dtype=complex)
    mandel = np.zeros(C.shape, dtype=int)

    for i in range(max_iter):
        mask = np.abs(Z) <= 2
        Z[mask] = Z[mask] ** 2 + C[mask]
        mandel[mask & (np.abs(Z) > 2)] = i

    mandel[mandel == 0] = max_iter
    return mandel


def julia(c: complex, width: int = 600, height: int = 600,
          max_iter: int = 150, xmin: float = -1.5, xmax: float = 1.5,
          ymin: float = -1.5, ymax: float = 1.5) -> np.ndarray:
    """Compute Julia set for parameter c."""
    x = np.linspace(xmin, xmax, width)
    y = np.linspace(ymin, ymax, height)
    X, Y = np.meshgrid(x, y)
    Z = X + 1j * Y
    julia_set = np.zeros(Z.shape, dtype=int)

    for i in range(max_iter):
        mask = np.abs(Z) <= 2
        Z[mask] = Z[mask] ** 2 + c
        julia_set[mask & (np.abs(Z) > 2)] = i

    julia_set[julia_set == 0] = max_iter
    return julia_set


def newton_fractal(width: int = 600, height: int = 600,
                   max_iter: int = 50, tol: float = 1e-6) -> np.ndarray:
    """Newton fractal for f(z) = z^3 - 1."""
    x = np.linspace(-2, 2, width)
    y = np.linspace(-2, 2, height)
    X, Y = np.meshgrid(x, y)
    Z = X + 1j * Y

    # Roots of z^3 - 1
    roots = np.array([1, np.exp(2j * np.pi / 3), np.exp(4j * np.pi / 3)])
    fractal = np.zeros(Z.shape, dtype=int)

    for i in range(max_iter):
        mask = fractal == 0
        if not np.any(mask):
            break
        Z[mask] = Z[mask] - (Z[mask]**3 - 1) / (3 * Z[mask]**2)

        # Check convergence to each root
        for r_idx, root in enumerate(roots):
            converged = mask & (np.abs(Z - root) < tol)
            fractal[converged] = r_idx + 1

    return fractal


def burning_ship(width: int = 600, height: int = 600, max_iter: int = 150,
                 xmin: float = -2.0, xmax: float = 1.5,
                 ymin: float = -2.0, ymax: float = 1.0) -> np.ndarray:
    """Compute Burning Ship fractal."""
    x = np.linspace(xmin, xmax, width)
    y = np.linspace(ymin, ymax, height)
    X, Y = np.meshgrid(x, y)
    C = X + 1j * Y
    Z = np.zeros_like(C, dtype=complex)
    ship = np.zeros(C.shape, dtype=int)

    for i in range(max_iter):
        mask = np.abs(Z) <= 2
        Z_real = np.abs(Z[mask].real)
        Z_imag = np.abs(Z[mask].imag)
        Z[mask] = (Z_real + 1j * Z_imag) ** 2 + C[mask]
        ship[mask & (np.abs(Z) > 2)] = i

    ship[ship == 0] = max_iter
    return ship


def l_system(axiom: str, rules: dict, iterations: int) -> str:
    """Generate L-system string."""
    result = axiom
    for _ in range(iterations):
        result = "".join(rules.get(c, c) for c in result)
    return result


def draw_l_system(commands: str, angle: float = 90, step: float = 1.0) -> tuple:
    """Draw L-system using turtle graphics approach."""
    x, y = 0.0, 0.0
    direction = 0.0  # radians, 0 = right
    points = [(x, y)]
    stack = []

    for cmd in commands:
        if cmd == "F" or cmd == "G":
            x += step * np.cos(direction)
            y += step * np.sin(direction)
            points.append((x, y))
        elif cmd == "+":
            direction += np.radians(angle)
        elif cmd == "-":
            direction -= np.radians(angle)
        elif cmd == "[":
            stack.append((x, y, direction))
        elif cmd == "]":
            x, y, direction = stack.pop()
            points.append((np.nan, np.nan))  # Break line
            points.append((x, y))

    return points


def main():
    print("=" * 60)
    print("FRACTALS & CHAOS — Mandelbrot, Julia, Newton, L-Systems")
    print("=" * 60)

    # 1. Mandelbrot set
    print("\n--- 1. Mandelbrot Set ---")
    mandel = mandelbrot(width=600, height=450, max_iter=200)
    print(f"  Resolution: {mandel.shape}")
    print(f"  Min iterations to escape: {mandel[mandel < 200].min()}")
    print(f"  Points in set: {np.sum(mandel == 200)}")

    # 2. Julia sets
    print("\n--- 2. Julia Sets ---")
    c_values = [-0.7 + 0.27j, -0.4 + 0.6j, 0.285 + 0.01j, -0.8 + 0.156j]
    julia_sets = {}
    for c in c_values:
        js = julia(c, width=300, height=300, max_iter=100)
        julia_sets[str(c)] = js
        print(f"  c = {c}: {np.sum(js == 100)} points in set")

    # 3. Newton fractal
    print("\n--- 3. Newton Fractal (z³ - 1) ---")
    newton = newton_fractal(width=400, height=400, max_iter=30)
    for r in range(1, 4):
        print(f"  Root {r}: {np.sum(newton == r)} points")

    # 4. Burning Ship
    print("\n--- 4. Burning Ship Fractal ---")
    ship = burning_ship(width=400, height=400, max_iter=100)
    print(f"  Points in set: {np.sum(ship == 100)}")

    # 5. L-systems
    print("\n--- 5. L-Systems ---")
    l_systems_configs = {
        "Koch Snowflake": {
            "axiom": "F++F++F",
            "rules": {"F": "F-F++F-F"},
            "angle": 60,
            "iterations": 4,
        },
        "Sierpinski Triangle": {
            "axiom": "F-G-G",
            "rules": {"F": "F-G+F+G-F", "G": "GG"},
            "angle": 120,
            "iterations": 5,
        },
        "Dragon Curve": {
            "axiom": "FX",
            "rules": {"X": "X+YF+", "Y": "-FX-Y"},
            "angle": 90,
            "iterations": 12,
        },
        "Plant": {
            "axiom": "X",
            "rules": {"X": "F+[[X]-X]-F[-FX]+X", "F": "FF"},
            "angle": 25,
            "iterations": 5,
        },
    }

    l_system_results = {}
    for name, config in l_systems_configs.items():
        cmds = l_system(config["axiom"], config["rules"], config["iterations"])
        points = draw_l_system(cmds, config["angle"])
        l_system_results[name] = points
        print(f"  {name}: {len(cmds)} commands, {len(points)} points")

    # ---- PLOTS ----
    fig = plt.figure(figsize=(20, 16))

    # Mandelbrot
    ax1 = fig.add_subplot(3, 4, 1)
    ax1.imshow(mandel, extent=[-2.5, 1.0, -1.2, 1.2], cmap="hot", origin="lower")
    ax1.set_title("Mandelbrot Set", fontsize=10, fontweight="bold")
    ax1.axis("off")

    # Julia sets (4 panels)
    for idx, (c_str, js) in enumerate(julia_sets.items()):
        ax = fig.add_subplot(3, 4, 2 + idx)
        ax.imshow(js, extent=[-1.5, 1.5, -1.5, 1.5], cmap="hot", origin="lower")
        ax.set_title(f"Julia: c = {c_str}", fontsize=9)
        ax.axis("off")

    # Newton fractal
    ax6 = fig.add_subplot(3, 4, 6)
    colors = ["#000000", "#FF0000", "#00FF00", "#0000FF"]
    cmap_newton = matplotlib.colors.ListedColormap(colors)
    ax6.imshow(newton, extent=[-2, 2, -2, 2], cmap=cmap_newton, origin="lower")
    ax6.set_title("Newton Fractal (z³-1)", fontsize=10, fontweight="bold")
    ax6.axis("off")

    # Burning Ship
    ax7 = fig.add_subplot(3, 4, 7)
    ax7.imshow(ship, extent=[-2.0, 1.5, -2.0, 1.0], cmap="hot", origin="lower")
    ax7.set_title("Burning Ship", fontsize=10, fontweight="bold")
    ax7.axis("off")

    # L-systems (4 panels)
    l_positions = [(3, 4, 9), (3, 4, 10), (3, 4, 11), (3, 4, 12)]
    for (name, points), pos in zip(l_system_results.items(), l_positions):
        ax = fig.add_subplot(*pos)
        px, py = zip(*points)
        ax.plot(px, py, linewidth=0.5, color="green")
        ax.set_aspect("equal")
        ax.set_title(name, fontsize=9)
        ax.axis("off")

    # Zoomed Mandelbrot (interesting region)
    ax8 = fig.add_subplot(3, 4, 8)
    mandel_zoom = mandelbrot(width=400, height=400, max_iter=300,
                             xmin=-0.8, xmax=-0.7, ymin=0.2, ymax=0.3)
    ax8.imshow(mandel_zoom, extent=[-0.8, -0.7, 0.2, 0.3], cmap="hot", origin="lower")
    ax8.set_title("Mandelbrot Zoom", fontsize=10, fontweight="bold")
    ax8.axis("off")

    plt.tight_layout()
    path = OUTPUT_DIR / "fractals.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n✅ Chart saved: {path}")

    # Extra: high-res Mandelbrot standalone
    fig2, ax = plt.subplots(figsize=(12, 8))
    mandel_hr = mandelbrot(width=1200, height=800, max_iter=300)
    ax.imshow(mandel_hr, extent=[-2.5, 1.0, -1.2, 1.2], cmap="inferno", origin="lower")
    ax.set_title("Mandelbrot Set — High Resolution", fontsize=14, fontweight="bold")
    ax.axis("off")
    path2 = OUTPUT_DIR / "fractals_mandelbrot_hr.png"
    plt.savefig(path2, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"✅ High-res Mandelbrot: {path2}")


if __name__ == "__main__":
    main()
