"""
Geometry + Fractals + 3D Visualization Engine.
===============================================
LLM NIGDY nie liczy — wszystkie obliczenia przez NumPy/SciPy/SymPy.

Moduły:
- Fractals: Mandelbrot set, Julia sets, Newton fractals, Sierpinski, Koch snowflake
- 3D Surfaces: parametric surfaces, implicit surfaces, vector fields
- Geometry: Voronoi diagrams, Delaunay triangulation, convex hulls, polygon operations
- Topology visualization: winding numbers, homotopy animations

Usage:
    from geometry_fractals import FractalEngine
    fe = FractalEngine()
    fe.mandelbrot(width=800, height=600, max_iter=100)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
from scipy.spatial import Voronoi, Delaunay, ConvexHull, KDTree
from scipy.spatial.distance import cdist
import sympy as sp

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


@dataclass
class GeoResult:
    success: bool
    result: Any = None
    image_path: str = ""
    error: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# FRACTALS
# ═══════════════════════════════════════════════════════════════════════════════

class FractalEngine:
    """Mandelbrot, Julia, Newton fractals, L-systems."""

    @staticmethod
    def mandelbrot(width: int = 800, height: int = 600,
                   x_range: tuple = (-2.5, 1.0), y_range: tuple = (-1.2, 1.2),
                   max_iter: int = 100, smooth: bool = True) -> GeoResult:
        """Generate Mandelbrot set image."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        x = np.linspace(x_range[0], x_range[1], width)
        y = np.linspace(y_range[0], y_range[1], height)
        X, Y = np.meshgrid(x, y)
        C = X + 1j * Y
        Z = np.zeros_like(C, dtype=complex)
        M = np.zeros(C.shape, dtype=float)

        for n in range(max_iter):
            mask = np.abs(Z) <= 2
            Z[mask] = Z[mask] ** 2 + C[mask]
            M[mask] = n

        if smooth:
            # Smooth coloring: log2 of escape iteration
            mask = np.abs(Z) > 2
            M[mask] = M[mask] - np.log2(np.log(np.abs(Z[mask])) / np.log(2))

        fig, ax = plt.subplots(figsize=(10, 8))
        im = ax.imshow(M, extent=[x_range[0], x_range[1], y_range[0], y_range[1]],
                       cmap='hot', origin='lower', aspect='equal')
        ax.set_title(f"Mandelbrot Set (max_iter={max_iter})")
        plt.colorbar(im, ax=ax, label='Iterations')
        path = str(OUTPUT_DIR / "mandelbrot.png")
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        return GeoResult(True, image_path=path)

    @staticmethod
    def julia(c: complex = complex(-0.7, 0.27), width: int = 600, height: int = 600,
              max_iter: int = 100) -> GeoResult:
        """Generate Julia set for given complex parameter c."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        x = np.linspace(-1.5, 1.5, width)
        y = np.linspace(-1.5, 1.5, height)
        X, Y = np.meshgrid(x, y)
        Z = X + 1j * Y
        M = np.zeros(Z.shape, dtype=float)

        for n in range(max_iter):
            mask = np.abs(Z) <= 2
            Z[mask] = Z[mask] ** 2 + c
            M[mask] = n

        mask = np.abs(Z) > 2
        M[mask] = M[mask] - np.log2(np.log(np.abs(Z[mask])) / np.log(2))

        fig, ax = plt.subplots(figsize=(8, 8))
        ax.imshow(M, extent=[-1.5, 1.5, -1.5, 1.5], cmap='twilight_shifted',
                  origin='lower', aspect='equal')
        ax.set_title(f"Julia Set — c = {c.real:.2f} + {c.imag:.2f}i")
        path = str(OUTPUT_DIR / f"julia_{c.real:.2f}_{c.imag:.2f}.png")
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        return GeoResult(True, image_path=path)

    @staticmethod
    def newton_fractal(polynomial: str = "z**3 - 1", width: int = 600,
                       height: int = 600, max_iter: int = 50) -> GeoResult:
        """Newton fractal: which root does Newton's method converge to?"""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Parse polynomial
        z = sp.Symbol('z')
        try:
            f = sp.sympify(polynomial)
            fprime = sp.diff(f, z)
            f_func = sp.lambdify(z, f, 'numpy')
            fp_func = sp.lambdify(z, fprime, 'numpy')
            roots = [complex(r.evalf()) for r in sp.nroots(f, n=15)]
        except Exception as e:
            return GeoResult(False, error=f"Parse error: {e}")

        x = np.linspace(-2, 2, width)
        y = np.linspace(-2, 2, height)
        X, Y = np.meshgrid(x, y)
        Z = X + 1j * Y
        M = np.full(Z.shape, -1, dtype=int)

        for n in range(max_iter):
            mask = M == -1
            if not mask.any():
                break
            try:
                fz = f_func(Z[mask])
                fpz = fp_func(Z[mask])
                Z[mask] = Z[mask] - np.divide(fz, fpz, out=np.zeros_like(fz), where=fpz != 0)
            except Exception:
                break

        # Assign to nearest root
        for i, root in enumerate(roots):
            dist = np.abs(Z - root)
            mask = (dist < 0.001) & (M == -1)
            M[mask] = i

        colors = plt.cm.Set1(np.linspace(0, 1, len(roots)))
        img = np.zeros((height, width, 3))
        for i in range(len(roots)):
            img[M == i] = colors[i][:3]
        img[M == -1] = [0, 0, 0]

        fig, ax = plt.subplots(figsize=(8, 8))
        ax.imshow(img, extent=[-2, 2, -2, 2], origin='lower', aspect='equal')
        ax.set_title(f"Newton Fractal: {polynomial}")
        path = str(OUTPUT_DIR / "newton_fractal.png")
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        return GeoResult(True, result={"roots": [str(r) for r in roots]}, image_path=path)

    @staticmethod
    def sierpinski(depth: int = 5, size: float = 1.0) -> GeoResult:
        """Sierpinski triangle via chaos game."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        vertices = np.array([[0, 0], [size, 0], [size / 2, size * np.sqrt(3) / 2]])
        n_points = 50000
        points = np.zeros((n_points, 2))
        points[0] = vertices[0]

        for i in range(1, n_points):
            v = vertices[np.random.randint(0, 3)]
            points[i] = (points[i - 1] + v) / 2

        fig, ax = plt.subplots(figsize=(8, 7))
        ax.scatter(points[:, 0], points[:, 1], s=0.1, c='black', alpha=0.5)
        ax.set_aspect('equal')
        ax.set_title(f"Sierpiński Triangle (depth={depth}, {n_points} points)")
        ax.axis('off')
        path = str(OUTPUT_DIR / "sierpinski.png")
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        return GeoResult(True, image_path=path)

    @staticmethod
    def koch_snowflake(depth: int = 4) -> GeoResult:
        """Koch snowflake via L-system recursion."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        def koch_curve(points, depth):
            if depth == 0:
                return points
            new_points = []
            for i in range(len(points) - 1):
                p1 = np.array(points[i])
                p2 = np.array(points[i + 1])
                v = p2 - p1
                a = p1 + v / 3
                b = p1 + v * 2 / 3
                # Rotate by 60 degrees
                rot = np.array([[0.5, -np.sqrt(3) / 2], [np.sqrt(3) / 2, 0.5]])
                tip = a + rot @ (v / 3)
                new_points.extend([p1.tolist(), a.tolist(), tip.tolist(), b.tolist()])
            new_points.append(points[-1])
            return koch_curve(new_points, depth - 1)

        # Equilateral triangle
        h = np.sqrt(3) / 2
        triangle = [[0, 0], [0.5, h], [1, 0], [0, 0]]
        curve = koch_curve(triangle, depth)
        curve = np.array(curve)

        fig, ax = plt.subplots(figsize=(8, 7))
        ax.plot(curve[:, 0], curve[:, 1], 'b-', linewidth=0.5)
        ax.set_aspect('equal')
        ax.set_title(f"Koch Snowflake (depth={depth})")
        ax.axis('off')
        path = str(OUTPUT_DIR / "koch_snowflake.png")
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        return GeoResult(True, image_path=path)


# ═══════════════════════════════════════════════════════════════════════════════
# 3D SURFACES & VECTOR FIELDS
# ═══════════════════════════════════════════════════════════════════════════════

class SurfaceEngine:
    """3D parametric surfaces, implicit surfaces, vector fields."""

    @staticmethod
    def parametric_surface(func_x: str, func_y: str, func_z: str,
                           u_range: tuple = (0, 2 * np.pi),
                           v_range: tuple = (0, np.pi),
                           resolution: int = 100) -> GeoResult:
        """Plot a parametric surface: x(u,v), y(u,v), z(u,v)."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D

        u = np.linspace(u_range[0], u_range[1], resolution)
        v = np.linspace(v_range[0], v_range[1], resolution)
        U, V = np.meshgrid(u, v)

        # Parse functions
        u_sym, v_sym = sp.Symbol('u'), sp.Symbol('v')
        try:
            fx = sp.lambdify((u_sym, v_sym), sp.sympify(func_x), 'numpy')
            fy = sp.lambdify((u_sym, v_sym), sp.sympify(func_y), 'numpy')
            fz = sp.lambdify((u_sym, v_sym), sp.sympify(func_z), 'numpy')
            X = fx(U, V)
            Y = fy(U, V)
            Z = fz(U, V)
        except Exception as e:
            return GeoResult(False, error=f"Function parse error: {e}")

        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        ax.plot_surface(X, Y, Z, cmap='viridis', alpha=0.85, edgecolor='none')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        ax.set_title(f"Parametric Surface: ({func_x}, {func_y}, {func_z})")
        path = str(OUTPUT_DIR / "parametric_surface.png")
        plt.savefig(path, dpi=120, bbox_inches='tight')
        plt.close()
        return GeoResult(True, image_path=path)

    @staticmethod
    def vector_field_3d(fx: str, fy: str, fz: str,
                        x_range: tuple = (-2, 2), y_range: tuple = (-2, 2),
                        z_range: tuple = (-2, 2), n_points: int = 10) -> GeoResult:
        """3D vector field plot."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        x_sym, y_sym, z_sym = sp.Symbol('x'), sp.Symbol('y'), sp.Symbol('z')
        try:
            ffx = sp.lambdify((x_sym, y_sym, z_sym), sp.sympify(fx), 'numpy')
            ffy = sp.lambdify((x_sym, y_sym, z_sym), sp.sympify(fy), 'numpy')
            ffz = sp.lambdify((x_sym, y_sym, z_sym), sp.sympify(fz), 'numpy')
        except Exception as e:
            return GeoResult(False, error=str(e))

        x = np.linspace(x_range[0], x_range[1], n_points)
        y = np.linspace(y_range[0], y_range[1], n_points)
        z = np.linspace(z_range[0], z_range[1], n_points)
        X, Y, Z = np.meshgrid(x, y, z)

        U = ffx(X, Y, Z)
        V = ffy(X, Y, Z)
        W = ffz(X, Y, Z)

        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        ax.quiver(X, Y, Z, U, V, W, length=0.3, normalize=True, alpha=0.7)
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        ax.set_title(f"Vector Field: ({fx}, {fy}, {fz})")
        path = str(OUTPUT_DIR / "vector_field_3d.png")
        plt.savefig(path, dpi=120, bbox_inches='tight')
        plt.close()
        return GeoResult(True, image_path=path)

    @staticmethod
    def implicit_surface(equation: str, x_range: tuple = (-2, 2),
                         y_range: tuple = (-2, 2), z_range: tuple = (-2, 2),
                         resolution: int = 50) -> GeoResult:
        """Plot implicit surface f(x,y,z) = 0 using marching cubes."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from skimage import measure

        x = np.linspace(x_range[0], x_range[1], resolution)
        y = np.linspace(y_range[0], y_range[1], resolution)
        z = np.linspace(z_range[0], z_range[1], resolution)
        X, Y, Z = np.meshgrid(x, y, z, indexing='ij')

        x_sym, y_sym, z_sym = sp.Symbol('x'), sp.Symbol('y'), sp.Symbol('z')
        try:
            f = sp.lambdify((x_sym, y_sym, z_sym), sp.sympify(equation), 'numpy')
            V = f(X, Y, Z)
        except Exception as e:
            return GeoResult(False, error=str(e))

        try:
            verts, faces, _, _ = measure.marching_cubes(V, level=0, spacing=(
                (x_range[1] - x_range[0]) / resolution,
                (y_range[1] - y_range[0]) / resolution,
                (z_range[1] - z_range[0]) / resolution,
            ))
            verts[:, 0] += x_range[0]
            verts[:, 1] += y_range[0]
            verts[:, 2] += z_range[0]
        except Exception as e:
            return GeoResult(False, error=f"Marching cubes failed: {e}")

        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        ax.plot_trisurf(verts[:, 0], verts[:, 1], faces, verts[:, 2],
                        cmap='plasma', alpha=0.8, edgecolor='none')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        ax.set_title(f"Implicit Surface: {equation} = 0")
        path = str(OUTPUT_DIR / "implicit_surface.png")
        plt.savefig(path, dpi=120, bbox_inches='tight')
        plt.close()
        return GeoResult(True, image_path=path)


# ═══════════════════════════════════════════════════════════════════════════════
# GEOMETRY
# ═══════════════════════════════════════════════════════════════════════════════

class GeometryEngine:
    """Voronoi, Delaunay, convex hulls, spatial operations."""

    @staticmethod
    def voronoi(points: list[tuple[float, float]], plot: bool = True) -> GeoResult:
        """Voronoi diagram for 2D points."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        pts = np.array(points)
        try:
            vor = Voronoi(pts)
        except Exception as e:
            return GeoResult(False, error=str(e))

        if plot:
            from scipy.spatial import voronoi_plot_2d
            fig, ax = plt.subplots(figsize=(8, 8))
            voronoi_plot_2d(vor, ax=ax, show_vertices=True, line_colors='blue',
                           line_width=1, point_size=15)
            ax.scatter(pts[:, 0], pts[:, 1], c='red', s=50, zorder=5)
            for i, (x, y) in enumerate(pts):
                ax.annotate(str(i), (x, y), xytext=(5, 5), textcoords='offset points')
            ax.set_aspect('equal')
            ax.set_title(f"Voronoi Diagram ({len(points)} points)")
            path = str(OUTPUT_DIR / "voronoi.png")
            plt.savefig(path, dpi=120, bbox_inches='tight')
            plt.close()

        return GeoResult(True,
            result={"n_points": len(points), "n_regions": len(vor.regions),
                    "n_vertices": len(vor.vertices)},
            image_path=path if plot else "")

    @staticmethod
    def delaunay(points: list[tuple[float, float]]) -> GeoResult:
        """Delaunay triangulation."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        pts = np.array(points)
        try:
            tri = Delaunay(pts)
        except Exception as e:
            return GeoResult(False, error=str(e))

        fig, ax = plt.subplots(figsize=(8, 8))
        ax.triplot(pts[:, 0], pts[:, 1], tri.simplices, 'b-', linewidth=0.5)
        ax.scatter(pts[:, 0], pts[:, 1], c='red', s=30, zorder=5)
        ax.set_aspect('equal')
        ax.set_title(f"Delaunay Triangulation ({len(points)} points, {len(tri.simplices)} triangles)")
        path = str(OUTPUT_DIR / "delaunay.png")
        plt.savefig(path, dpi=120, bbox_inches='tight')
        plt.close()
        return GeoResult(True,
            result={"n_triangles": len(tri.simplices)},
            image_path=path)

    @staticmethod
    def convex_hull(points: list[tuple[float, float]]) -> GeoResult:
        """Convex hull of 2D points."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        pts = np.array(points)
        try:
            hull = ConvexHull(pts)
        except Exception as e:
            return GeoResult(False, error=str(e))

        fig, ax = plt.subplots(figsize=(8, 8))
        ax.scatter(pts[:, 0], pts[:, 1], c='blue', s=30, alpha=0.5, label='Points')
        for simplex in hull.simplices:
            ax.plot(pts[simplex, 0], pts[simplex, 1], 'r-', linewidth=2)
        ax.plot(pts[hull.vertices, 0], pts[hull.vertices, 1], 'ro', markersize=8, label='Hull vertices')
        ax.set_aspect('equal')
        ax.set_title(f"Convex Hull (area={hull.volume:.2f}, {len(hull.vertices)} vertices)")
        ax.legend()
        path = str(OUTPUT_DIR / "convex_hull.png")
        plt.savefig(path, dpi=120, bbox_inches='tight')
        plt.close()
        return GeoResult(True,
            result={"area": float(hull.volume), "n_vertices": len(hull.vertices),
                    "vertices": hull.vertices.tolist()},
            image_path=path)

    @staticmethod
    def polygon_area(vertices: list[tuple[float, float]]) -> GeoResult:
        """Shoelace formula for polygon area."""
        v = np.array(vertices)
        x, y = v[:, 0], v[:, 1]
        area = 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
        return GeoResult(True, result={"area": float(area)})

    @staticmethod
    def point_in_polygon(point: tuple[float, float],
                         polygon: list[tuple[float, float]]) -> GeoResult:
        """Ray casting algorithm: is point inside polygon?"""
        from matplotlib.path import Path as MplPath
        path = MplPath(np.array(polygon))
        inside = path.contains_points([point])[0]
        return GeoResult(True, result={"inside": bool(inside)})


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO APP
# ═══════════════════════════════════════════════════════════════════════════════

def run_demo():
    """Run all demos and generate visualizations."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fe = FractalEngine()
    se = SurfaceEngine()
    ge = GeometryEngine()

    print("=" * 60)
    print("GEOMETRY + FRACTALS + 3D — DEMO")
    print("=" * 60)

    # ── Fractals ──
    print("\n🎨 Fractals...")
    r = fe.mandelbrot(400, 300, max_iter=80)
    print(f"  Mandelbrot: {r.image_path}")

    r = fe.julia(complex(-0.7, 0.27), 300, 300, max_iter=60)
    print(f"  Julia: {r.image_path}")

    r = fe.newton_fractal("z**3 - 1", 300, 300, max_iter=30)
    if r.success:
        print(f"  Newton: {r.image_path} — roots: {r.result['roots']}")

    r = fe.sierpinski(depth=5)
    print(f"  Sierpinski: {r.image_path}")

    r = fe.koch_snowflake(depth=4)
    print(f"  Koch: {r.image_path}")

    # ── 3D Surfaces ──
    print("\n🌐 3D Surfaces...")
    r = se.parametric_surface(
        "cos(u)*sin(v)", "sin(u)*sin(v)", "cos(v)",
        resolution=60,
    )
    print(f"  Sphere: {r.image_path}")

    r = se.vector_field_3d("-y", "x", "z", n_points=8)
    print(f"  Vector field: {r.image_path}")

    # ── Geometry ──
    print("\n📐 Geometry...")
    np.random.seed(42)
    points = np.random.uniform(0, 10, (20, 2)).tolist()
    r = ge.voronoi(points)
    print(f"  Voronoi: {r.image_path} — {r.result['n_regions']} regions")

    r = ge.delaunay(points)
    print(f"  Delaunay: {r.image_path} — {r.result['n_triangles']} triangles")

    r = ge.convex_hull(points)
    print(f"  Convex Hull: {r.image_path} — area={r.result['area']:.2f}")

    r = ge.polygon_area([(0, 0), (4, 0), (4, 3), (0, 3)])
    print(f"  Polygon area: {r.result['area']} (expected 12)")

    r = ge.point_in_polygon((2, 1.5), [(0, 0), (4, 0), (4, 3), (0, 3)])
    print(f"  Point in polygon: {r.result['inside']} (expected True)")

    print("\n✅ ALL GEOMETRY + FRACTALS DEMOS COMPLETE")


if __name__ == "__main__":
    run_demo()
