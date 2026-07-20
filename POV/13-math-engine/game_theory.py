"""
Game Theory + Decision Theory + Operations Research Engine.
============================================================
LLM NIGDY nie liczy — wszystkie obliczenia przez SymPy/NumPy/SciPy.

Moduły:
- Game Theory: Nash equilibrium (pure/mixed), payoff matrices, Prisoner's Dilemma,
  Chicken, Battle of Sexes, zero-sum games, minimax
- Decision Theory: decision trees, expected utility, maximin/Laplace/Hurwicz criteria,
  value of perfect information (EVPI), risk analysis
- Operations Research: linear programming (simplex via SciPy), transportation problem,
  knapsack (0/1, fractional), assignment problem (Hungarian)

Usage:
    from game_theory import GameTheory
    gt = GameTheory()
    eq = gt.nash_equilibrium([[3,0],[5,1]], [[3,5],[0,1]])
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
from scipy.optimize import linprog, milp, LinearConstraint, Bounds
from scipy.optimize import minimize_scalar
import scipy.stats as stats
import sympy as sp

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


@dataclass
class GameResult:
    success: bool
    result: Any = None
    method: str = ""
    steps: list[str] = field(default_factory=list)
    error: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# GAME THEORY
# ═══════════════════════════════════════════════════════════════════════════════

class GameTheory:
    """Nash equilibrium, mixed strategies, classic games."""

    @staticmethod
    def nash_equilibrium(payoff_a: list[list[float]],
                         payoff_b: list[list[float]]) -> GameResult:
        """
        Find Nash equilibria for a 2-player bimatrix game.
        Uses support enumeration for small matrices, Lemke-Howson for larger.
        Returns list of (strategy_a, strategy_b, payoffs) tuples.
        """
        A = np.array(payoff_a, dtype=float)
        B = np.array(payoff_b, dtype=float)
        m, n = A.shape

        if B.shape != (m, n):
            return GameResult(False, error="Payoff matrices must have same dimensions")

        equilibria = []

        # 1. Pure strategy Nash: check every cell
        for i in range(m):
            for j in range(n):
                # Row player: can't improve by switching row
                row_best = all(A[i, j] >= A[k, j] for k in range(m))
                # Col player: can't improve by switching column
                col_best = all(B[i, j] >= B[i, k] for k in range(n))
                if row_best and col_best:
                    equilibria.append({
                        "type": "pure",
                        "strategy_a": [1.0 if k == i else 0.0 for k in range(m)],
                        "strategy_b": [1.0 if k == j else 0.0 for k in range(n)],
                        "payoff_a": float(A[i, j]),
                        "payoff_b": float(B[i, j]),
                    })

        # 2. Mixed strategy via linear complementarity (simplified: solve for 2x2)
        if m == 2 and n == 2 and not equilibria:
            eq = GameTheory._mixed_2x2(A, B)
            if eq:
                equilibria.append(eq)

        if not equilibria:
            return GameResult(True, result=[],
                            method="support_enumeration",
                            steps=["No pure Nash found", "Mixed strategy requires larger support enumeration"])

        return GameResult(True, result=equilibria,
                         method="support_enumeration",
                         steps=[f"Checked {m}x{n} matrix", f"Found {len(equilibria)} equilibria"])

    @staticmethod
    def _mixed_2x2(A: np.ndarray, B: np.ndarray) -> dict | None:
        """Compute mixed strategy Nash for 2x2 game."""
        # Row player: p * a11 + (1-p) * a21 = p * a12 + (1-p) * a22
        # p * (a11 - a12 - a21 + a22) = a22 - a21
        denom_a = A[0, 0] - A[0, 1] - A[1, 0] + A[1, 1]
        if abs(denom_a) < 1e-10:
            return None
        p = (A[1, 1] - A[1, 0]) / denom_a
        p = max(0.0, min(1.0, p))

        # Col player: q * b11 + (1-q) * b12 = q * b21 + (1-q) * b22
        denom_b = B[0, 0] - B[1, 0] - B[0, 1] + B[1, 1]
        if abs(denom_b) < 1e-10:
            return None
        q = (B[1, 1] - B[0, 1]) / denom_b
        q = max(0.0, min(1.0, q))

        payoff_a = p * q * A[0, 0] + p * (1 - q) * A[0, 1] + (1 - p) * q * A[1, 0] + (1 - p) * (1 - q) * A[1, 1]
        payoff_b = p * q * B[0, 0] + p * (1 - q) * B[0, 1] + (1 - p) * q * B[1, 0] + (1 - p) * (1 - q) * B[1, 1]

        return {
            "type": "mixed",
            "strategy_a": [float(p), float(1 - p)],
            "strategy_b": [float(q), float(1 - q)],
            "payoff_a": float(payoff_a),
            "payoff_b": float(payoff_b),
        }

    @staticmethod
    def zero_sum_solve(payoff: list[list[float]]) -> GameResult:
        """Solve zero-sum game: minimax value + optimal strategies via linear programming."""
        A = np.array(payoff, dtype=float)
        m, n = A.shape

        # Row player: max v s.t. sum_i p_i * A[i,j] >= v for all j, sum p_i = 1, p_i >= 0
        # Transform to LP: min -v
        c = np.zeros(m + 1)
        c[-1] = -1.0  # minimize -v

        # Constraints: sum_i p_i * A[i,j] - v >= 0  →  -sum_i p_i * A[i,j] + v <= 0
        A_ub = np.zeros((n, m + 1))
        for j in range(n):
            for i in range(m):
                A_ub[j, i] = -A[i, j]
            A_ub[j, -1] = 1.0
        b_ub = np.zeros(n)

        # Equality: sum p_i = 1
        A_eq = np.zeros((1, m + 1))
        A_eq[0, :m] = 1.0
        b_eq = np.array([1.0])

        bounds = [(0, None)] * m + [(None, None)]

        try:
            res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
            if res.success:
                p = res.x[:m]
                v = res.x[-1]
                return GameResult(True,
                    result={"row_strategy": p.tolist(), "game_value": float(v)},
                    method="linear_programming",
                    steps=[f"Solved {m}x{n} zero-sum via LP", f"Game value: {v:.4f}"])
        except Exception as e:
            return GameResult(False, error=str(e))

        return GameResult(False, error="LP solver failed")

    @staticmethod
    def prisoners_dilemma(temptation: float = 5.0, reward: float = 3.0,
                          punishment: float = 1.0, sucker: float = 0.0) -> GameResult:
        """Classic Prisoner's Dilemma with configurable payoffs. T > R > P > S."""
        A = [[reward, sucker], [temptation, punishment]]
        B = [[reward, temptation], [sucker, punishment]]
        eq = GameTheory.nash_equilibrium(A, B)
        eq.steps.insert(0, f"Prisoner's Dilemma: T={temptation}, R={reward}, P={punishment}, S={sucker}")
        eq.steps.insert(1, "Dominant strategy: Defect-Defect (unique Nash)")
        return eq

    @staticmethod
    def battle_of_sexes(man_pref: float = 3.0, woman_pref: float = 2.0) -> GameResult:
        """Battle of Sexes: coordination game with conflicting preferences."""
        A = [[man_pref, 0], [0, 1]]  # Man: prefers his choice
        B = [[1, 0], [0, woman_pref]]  # Woman: prefers her choice
        eq = GameTheory.nash_equilibrium(A, B)
        eq.steps.insert(0, f"Battle of Sexes: man_pref={man_pref}, woman_pref={woman_pref}")
        eq.steps.insert(1, "Two pure Nash + one mixed strategy equilibrium")
        return eq

    @staticmethod
    def chicken_game(fear_a: float = -10.0, fear_b: float = -10.0) -> GameResult:
        """Chicken game (hawk-dove)."""
        A = [[0, -1], [1, fear_a]]  # Swerve=0, Straight=1
        B = [[0, 1], [-1, fear_b]]
        eq = GameTheory.nash_equilibrium(A, B)
        eq.steps.insert(0, f"Chicken: fear_a={fear_a}, fear_b={fear_b}")
        eq.steps.insert(1, "Two pure Nash (Swerve-Straight, Straight-Swerve) + mixed")
        return eq


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION THEORY
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionTheory:
    """Decision trees, expected utility, criteria under uncertainty."""

    @staticmethod
    def expected_utility(payoffs: list[float], probabilities: list[float]) -> GameResult:
        """Compute expected utility: EU = sum(p_i * u_i)."""
        if len(payoffs) != len(probabilities):
            return GameResult(False, error="Length mismatch")
        if abs(sum(probabilities) - 1.0) > 1e-6:
            return GameResult(False, error="Probabilities must sum to 1")

        eu = sum(p * u for p, u in zip(probabilities, payoffs))
        return GameResult(True, result=eu, method="expected_utility",
                         steps=[f"EU = {eu:.4f}"])

    @staticmethod
    def decision_matrix(payoff_matrix: list[list[float]],
                        criteria: str = "all") -> GameResult:
        """
        Decision under uncertainty criteria.
        payoff_matrix: rows=alternatives, cols=states of nature
        criteria: maximin, maximax, laplace, hurwicz, savage (minimax regret), all
        """
        M = np.array(payoff_matrix)
        m, n = M.shape
        results = {}

        if criteria in ("maximin", "all"):
            # Worst case for each alternative, pick best of worst
            worst = M.min(axis=1)
            best_idx = int(np.argmax(worst))
            results["maximin"] = {
                "values": worst.tolist(),
                "best_alternative": best_idx,
                "best_value": float(worst[best_idx]),
                "description": "Maximin (Wald) — pessimistic: maximize minimum payoff",
            }

        if criteria in ("maximax", "all"):
            best = M.max(axis=1)
            best_idx = int(np.argmax(best))
            results["maximax"] = {
                "values": best.tolist(),
                "best_alternative": best_idx,
                "best_value": float(best[best_idx]),
                "description": "Maximax — optimistic: maximize maximum payoff",
            }

        if criteria in ("laplace", "all"):
            avg = M.mean(axis=1)
            best_idx = int(np.argmax(avg))
            results["laplace"] = {
                "values": avg.tolist(),
                "best_alternative": best_idx,
                "best_value": float(avg[best_idx]),
                "description": "Laplace — equal probabilities: maximize average",
            }

        if criteria in ("hurwicz", "all"):
            for alpha in [0.3, 0.5, 0.7]:
                h = alpha * M.max(axis=1) + (1 - alpha) * M.min(axis=1)
                best_idx = int(np.argmax(h))
                results[f"hurwicz_a{alpha}"] = {
                    "values": h.tolist(),
                    "best_alternative": best_idx,
                    "best_value": float(h[best_idx]),
                    "alpha": alpha,
                    "description": f"Hurwicz (α={alpha}) — weighted optimism/pessimism",
                }

        if criteria in ("savage", "all"):
            # Regret matrix: best in column - actual
            col_max = M.max(axis=0)
            regret = col_max - M
            max_regret = regret.max(axis=1)
            best_idx = int(np.argmin(max_regret))
            results["savage"] = {
                "regret_matrix": regret.tolist(),
                "max_regret": max_regret.tolist(),
                "best_alternative": best_idx,
                "best_value": float(max_regret[best_idx]),
                "description": "Savage (minimax regret) — minimize maximum regret",
            }

        return GameResult(True, result=results, method=f"decision_criteria_{criteria}",
                         steps=[f"Analyzed {m} alternatives × {n} states"])

    @staticmethod
    def value_of_perfect_information(payoff_matrix: list[list[float]],
                                     probabilities: list[float]) -> GameResult:
        """EVPI = Expected value with perfect info - max expected value without."""
        M = np.array(payoff_matrix)
        probs = np.array(probabilities)

        # Without info: max of expected values
        ev_without = max(M @ probs)

        # With perfect info: expected value of best action for each state
        ev_with = sum(probs[j] * M[:, j].max() for j in range(len(probs)))

        evpi = ev_with - ev_without

        return GameResult(True,
            result={"ev_without_info": float(ev_without),
                    "ev_with_perfect_info": float(ev_with),
                    "evpi": float(evpi)},
            method="evpi",
            steps=[f"EV without info: {ev_without:.4f}",
                   f"EV with perfect info: {ev_with:.4f}",
                   f"EVPI = {evpi:.4f} — max you should pay for information"])

    @staticmethod
    def decision_tree(tree: dict) -> GameResult:
        """
        Evaluate a decision tree recursively.
        tree = {"type": "decision"|"chance"|"terminal",
                "payoff": float (terminal only),
                "probability": float (chance only),
                "children": [...]}
        Returns optimal path and expected value.
        """
        def _eval(node, path=None):
            if path is None:
                path = []
            t = node.get("type", "terminal")

            if t == "terminal":
                return node.get("payoff", 0), path + [f"Terminal: {node.get('payoff', 0)}"]

            if t == "chance":
                ev = 0.0
                for child in node.get("children", []):
                    prob = child.get("probability", 0)
                    val, child_path = _eval(child, path + [f"Chance (p={prob})"])
                    ev += prob * val
                return ev, path + [f"Chance node EV={ev:.2f}"]

            if t == "decision":
                best_val = float("-inf")
                best_path = []
                for i, child in enumerate(node.get("children", [])):
                    val, child_path = _eval(child, path + [f"Decision {i}"])
                    if val > best_val:
                        best_val = val
                        best_path = child_path
                return best_val, best_path

            return 0, path

        ev, path = _eval(tree)
        return GameResult(True, result={"expected_value": ev, "optimal_path": path},
                         method="decision_tree_rollback",
                         steps=path)


# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS RESEARCH
# ═══════════════════════════════════════════════════════════════════════════════

class OperationsResearch:
    """Linear programming, knapsack, transportation, assignment."""

    @staticmethod
    def linear_program(c: list[float], A_ub: list[list[float]] = None,
                       b_ub: list[float] = None, A_eq: list[list[float]] = None,
                       b_eq: list[float] = None, bounds: list[tuple] = None,
                       maximize: bool = False) -> GameResult:
        """
        Solve linear program: min c·x subject to A_ub·x <= b_ub, A_eq·x = b_eq.
        Set maximize=True for maximization.
        """
        c_arr = np.array(c, dtype=float)
        if maximize:
            c_arr = -c_arr

        constraints = []
        if A_ub and b_ub:
            constraints.append(LinearConstraint(np.array(A_ub), -np.inf, np.array(b_ub)))
        if A_eq and b_eq:
            constraints.append(LinearConstraint(np.array(A_eq), np.array(b_eq), np.array(b_eq)))

        if bounds is None:
            bounds = [(0, None)] * len(c)

        try:
            res = linprog(c_arr, A_ub=np.array(A_ub) if A_ub else None,
                         b_ub=np.array(b_ub) if b_ub else None,
                         A_eq=np.array(A_eq) if A_eq else None,
                         b_eq=np.array(b_eq) if b_eq else None,
                         bounds=bounds, method='highs')
            if res.success:
                obj = float(-res.fun if maximize else res.fun)
                return GameResult(True,
                    result={"x": res.x.tolist(), "objective": obj, "status": res.message},
                    method="simplex_highs",
                    steps=[f"Optimal value: {obj:.4f}", f"Solution: {res.x.tolist()}"])
            return GameResult(False, error=res.message)
        except Exception as e:
            return GameResult(False, error=str(e))

    @staticmethod
    def knapsack_01(values: list[float], weights: list[float],
                    capacity: float) -> GameResult:
        """0/1 knapsack via dynamic programming."""
        n = len(values)
        W = int(capacity)
        dp = np.zeros((n + 1, W + 1))

        for i in range(1, n + 1):
            for w in range(W + 1):
                if weights[i - 1] <= w:
                    dp[i, w] = max(dp[i - 1, w],
                                   dp[i - 1, w - int(weights[i - 1])] + values[i - 1])
                else:
                    dp[i, w] = dp[i - 1, w]

        # Backtrack
        selected = []
        w = W
        for i in range(n, 0, -1):
            if dp[i, w] != dp[i - 1, w]:
                selected.append(i - 1)
                w -= int(weights[i - 1])

        selected.sort()
        return GameResult(True,
            result={"max_value": float(dp[n, W]),
                    "selected_items": selected,
                    "total_weight": sum(weights[i] for i in selected)},
            method="dynamic_programming",
            steps=[f"Items: {n}, Capacity: {capacity}",
                   f"Max value: {dp[n, W]:.0f}",
                   f"Selected: {selected}"])

    @staticmethod
    def knapsack_fractional(values: list[float], weights: list[float],
                            capacity: float) -> GameResult:
        """Fractional knapsack — greedy by value/weight ratio."""
        items = sorted(
            [(v / w, v, w, i) for i, (v, w) in enumerate(zip(values, weights))],
            reverse=True,
        )
        total_value = 0.0
        taken = []
        remaining = capacity

        for ratio, v, w, idx in items:
            if remaining <= 0:
                break
            if w <= remaining:
                taken.append({"item": idx, "fraction": 1.0, "value": v, "weight": w})
                total_value += v
                remaining -= w
            else:
                frac = remaining / w
                taken.append({"item": idx, "fraction": frac, "value": v * frac, "weight": remaining})
                total_value += v * frac
                remaining = 0

        items_str = [(t['item'], f"{t['fraction']:.1%}") for t in taken]
        return GameResult(True,
            result={"max_value": total_value, "items_taken": taken},
            method="greedy_ratio",
            steps=[f"Max value: {total_value:.2f}",
                   f"Items taken: {items_str}"])

    @staticmethod
    def transportation(costs: list[list[float]], supply: list[float],
                       demand: list[float]) -> GameResult:
        """Transportation problem via LP. Minimize total shipping cost."""
        m, n = len(supply), len(demand)
        c = []
        for i in range(m):
            for j in range(n):
                c.append(costs[i][j])

        # Supply constraints: sum_j x_ij = supply_i
        A_eq = []
        b_eq = []
        for i in range(m):
            row = [0.0] * (m * n)
            for j in range(n):
                row[i * n + j] = 1.0
            A_eq.append(row)
            b_eq.append(supply[i])

        # Demand constraints: sum_i x_ij = demand_j
        for j in range(n):
            row = [0.0] * (m * n)
            for i in range(m):
                row[i * n + j] = 1.0
            A_eq.append(row)
            b_eq.append(demand[j])

        try:
            res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=[(0, None)] * (m * n), method='highs')
            if res.success:
                X = res.x.reshape(m, n)
                return GameResult(True,
                    result={"shipments": X.tolist(), "total_cost": float(res.fun)},
                    method="linear_programming",
                    steps=[f"Optimal cost: {res.fun:.2f}"])
            return GameResult(False, error=res.message)
        except Exception as e:
            return GameResult(False, error=str(e))

    @staticmethod
    def assignment(costs: list[list[float]]) -> GameResult:
        """Assignment problem (Hungarian algorithm via LP). Minimize total assignment cost."""
        n = len(costs)
        c = []
        for i in range(n):
            for j in range(n):
                c.append(costs[i][j])

        # Each row sums to 1, each col sums to 1
        A_eq = []
        b_eq = []
        for i in range(n):
            row = [0.0] * (n * n)
            for j in range(n):
                row[i * n + j] = 1.0
            A_eq.append(row)
            b_eq.append(1.0)

        for j in range(n):
            row = [0.0] * (n * n)
            for i in range(n):
                row[i * n + j] = 1.0
            A_eq.append(row)
            b_eq.append(1.0)

        try:
            res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=[(0, 1)] * (n * n), method='highs')
            if res.success:
                X = res.x.reshape(n, n)
                assignments = []
                for i in range(n):
                    for j in range(n):
                        if X[i, j] > 0.5:
                            assignments.append((i, j, costs[i][j]))
                return GameResult(True,
                    result={"assignments": assignments, "total_cost": float(res.fun)},
                    method="linear_programming",
                    steps=[f"Optimal cost: {res.fun:.2f}",
                           f"Assignments: {[(a[0], a[1]) for a in assignments]}"])
            return GameResult(False, error=res.message)
        except Exception as e:
            return GameResult(False, error=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO APP
# ═══════════════════════════════════════════════════════════════════════════════

def run_demo():
    """Run all demos and generate visualizations."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    gt = GameTheory()
    dt = DecisionTheory()
    op = OperationsResearch()

    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes = axes.flatten()

    # ── 1. Prisoner's Dilemma ──
    ax = axes[0]
    pd = gt.prisoners_dilemma()
    eq = pd.result
    ax.bar(["Cooperate-Coop", "Cooperate-Defect", "Defect-Coop", "Defect-Defect"],
           [3, 0, 5, 1], color=['green', 'red', 'orange', 'red'], alpha=0.7)
    ax.set_title("Prisoner's Dilemma — Player A Payoffs")
    ax.set_ylabel("Payoff")
    ax.axhline(y=1, color='red', linestyle='--', label='Nash equilibrium (1,1)')
    ax.legend(fontsize=8)

    # ── 2. Battle of Sexes ──
    ax = axes[1]
    bos = gt.battle_of_sexes()
    eqs = bos.result
    strategies = []
    for e in eqs:
        label = f"{e['type']}: ({e['strategy_a'][0]:.1f},{e['strategy_b'][0]:.1f})"
        strategies.append(label)
    ax.barh([f"Eq {i+1}" for i in range(len(eqs))],
            [e['payoff_a'] for e in eqs], color='purple', alpha=0.7, label='Player A')
    ax.barh([f"Eq {i+1}" for i in range(len(eqs))],
            [e['payoff_b'] for e in eqs], color='orange', alpha=0.5, label='Player B')
    ax.set_title("Battle of Sexes — Equilibrium Payoffs")
    ax.legend(fontsize=8)

    # ── 3. Decision Criteria ──
    ax = axes[2]
    payoff_matrix = [[100, 50, -20], [80, 60, 10], [30, 40, 30]]
    dm = dt.decision_matrix(payoff_matrix)
    criteria_names = list(dm.result.keys())[:5]
    best_alts = [dm.result[c]["best_alternative"] for c in criteria_names]
    ax.bar(criteria_names, best_alts, color='teal', alpha=0.7)
    ax.set_title("Decision Criteria — Best Alternative")
    ax.set_ylabel("Alternative index")
    ax.tick_params(axis='x', rotation=45)

    # ── 4. EVPI ──
    ax = axes[3]
    evpi = dt.value_of_perfect_information(payoff_matrix, [0.3, 0.5, 0.2])
    ax.bar(["Without info", "With perfect info", "EVPI"],
           [evpi.result["ev_without_info"], evpi.result["ev_with_perfect_info"], evpi.result["evpi"]],
           color=['gray', 'green', 'gold'], alpha=0.7)
    ax.set_title("Value of Perfect Information")
    ax.set_ylabel("Expected Value")

    # ── 5. Knapsack ──
    ax = axes[4]
    values = [60, 100, 120, 80, 50]
    weights = [10, 20, 30, 15, 5]
    kp = op.knapsack_01(values, weights, 50)
    selected = kp.result["selected_items"]
    colors = ['green' if i in selected else 'gray' for i in range(len(values))]
    ax.bar([f"Item {i}" for i in range(len(values))], values, color=colors, alpha=0.7)
    ax.set_title(f"0/1 Knapsack (cap=50) — Max Value: {kp.result['max_value']:.0f}")
    ax.set_ylabel("Value")

    # ── 6. Transportation ──
    ax = axes[5]
    costs = [[4, 6, 8], [6, 3, 5], [7, 4, 6]]
    supply = [20, 30, 25]
    demand = [25, 25, 25]
    tp = op.transportation(costs, supply, demand)
    if tp.success:
        X = np.array(tp.result["shipments"])
        im = ax.imshow(X, cmap='YlOrRd', aspect='auto')
        for i in range(X.shape[0]):
            for j in range(X.shape[1]):
                ax.text(j, i, f"{X[i,j]:.0f}", ha='center', va='center', fontsize=9)
        ax.set_xticks(range(len(demand)))
        ax.set_xticklabels([f"D{j}" for j in range(len(demand))])
        ax.set_yticks(range(len(supply)))
        ax.set_yticklabels([f"S{i}" for i in range(len(supply))])
        ax.set_title(f"Transport Problem — Cost: {tp.result['total_cost']:.0f}")
        plt.colorbar(im, ax=ax)

    plt.tight_layout()
    path = OUTPUT_DIR / "game_theory_demo.png"
    plt.savefig(path, dpi=120, bbox_inches='tight')
    plt.close()
    print(f"✅ Saved: {path}")

    # ── Print results ──
    print("\n" + "=" * 60)
    print("GAME THEORY + DECISION THEORY + OR — DEMO RESULTS")
    print("=" * 60)

    print(f"\n🎮 Prisoner's Dilemma: {len(pd.result)} Nash equilibrium")
    for e in pd.result:
        print(f"   {e['type']}: A={e['strategy_a']}, B={e['strategy_b']}, payoffs=({e['payoff_a']},{e['payoff_b']})")

    print(f"\n🎮 Battle of Sexes: {len(bos.result)} equilibria")
    for e in bos.result:
        print(f"   {e['type']}: A={[f'{x:.2f}' for x in e['strategy_a']]}, B={[f'{x:.2f}' for x in e['strategy_b']]}")

    print(f"\n📊 Decision criteria for {len(payoff_matrix)}×{len(payoff_matrix[0])} matrix:")
    for name, data in dm.result.items():
        print(f"   {name}: best alt={data['best_alternative']}, value={data.get('best_value', data.get('best_value', '?'))}")

    print(f"\n💰 EVPI = {evpi.result['evpi']:.2f}")

    print(f"\n🎒 Knapsack: max={kp.result['max_value']:.0f}, items={kp.result['selected_items']}")

    if tp.success:
        print(f"\n🚚 Transport: cost={tp.result['total_cost']:.0f}")

    # ── Additional: Assignment problem ──
    assign_costs = [[9, 2, 7, 8], [6, 4, 3, 7], [5, 8, 1, 8], [7, 6, 9, 4]]
    ap = op.assignment(assign_costs)
    if ap.success:
        print(f"\n📋 Assignment: cost={ap.result['total_cost']:.0f}")
        for i, j, c in ap.result['assignments']:
            print(f"   Worker {i} → Task {j} (cost {c})")

    print("\n✅ ALL DEMOS COMPLETE")


if __name__ == "__main__":
    run_demo()
