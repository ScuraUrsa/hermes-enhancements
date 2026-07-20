"""
Game Theory Demo — Nash Equilibrium, Prisoner's Dilemma, Mixed Strategies.

Demonstrates:
- Normal-form games: payoff matrices, Nash equilibria
- Prisoner's Dilemma, Battle of Sexes, Chicken, Matching Pennies
- Mixed strategy Nash equilibrium (linear programming)
- Evolutionary game theory (replicator dynamics)
- Extensive-form games (simple)
- Shapley value for cooperative games
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import optimize

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Classic games
# ---------------------------------------------------------------------------

GAMES = {
    "prisoners_dilemma": {
        "name": "Prisoner's Dilemma",
        "description": "Two suspects: cooperate (stay silent) or defect (betray).",
        "payoff_player1": [[-1, -5], [0, -3]],  # Row player
        "payoff_player2": [[-1, 0], [-5, -3]],   # Col player
        "strategies": ["Cooperate", "Defect"],
    },
    "battle_of_sexes": {
        "name": "Battle of the Sexes",
        "description": "Couple chooses between Boxing and Ballet.",
        "payoff_player1": [[3, 0], [0, 2]],
        "payoff_player2": [[2, 0], [0, 3]],
        "strategies": ["Boxing", "Ballet"],
    },
    "chicken": {
        "name": "Chicken",
        "description": "Two drivers heading toward each other.",
        "payoff_player1": [[0, -1], [1, -10]],
        "payoff_player2": [[0, 1], [-1, -10]],
        "strategies": ["Swerve", "Straight"],
    },
    "matching_pennies": {
        "name": "Matching Pennies",
        "description": "Each player shows Heads or Tails.",
        "payoff_player1": [[1, -1], [-1, 1]],
        "payoff_player2": [[-1, 1], [1, -1]],
        "strategies": ["Heads", "Tails"],
    },
    "stag_hunt": {
        "name": "Stag Hunt",
        "description": "Hunt stag together or rabbit alone.",
        "payoff_player1": [[4, 0], [2, 2]],
        "payoff_player2": [[4, 2], [0, 2]],
        "strategies": ["Stag", "Hare"],
    },
}


def find_pure_nash(p1: list[list[float]], p2: list[list[float]]) -> list[tuple[int, int]]:
    """Find all pure-strategy Nash equilibria."""
    nash = []
    n_rows = len(p1)
    n_cols = len(p1[0])

    for i in range(n_rows):
        for j in range(n_cols):
            # Check if player 1 can improve by deviating
            p1_best = True
            for i2 in range(n_rows):
                if p1[i2][j] > p1[i][j]:
                    p1_best = False
                    break
            # Check if player 2 can improve by deviating
            p2_best = True
            for j2 in range(n_cols):
                if p2[i][j2] > p2[i][j]:
                    p2_best = False
                    break
            if p1_best and p2_best:
                nash.append((i, j))

    return nash


def find_mixed_nash(p1: list[list[float]], p2: list[list[float]]) -> dict:
    """Find mixed-strategy Nash equilibrium for 2x2 games using indifference principle."""
    n_rows = len(p1)
    n_cols = len(p1[0])

    if n_rows != 2 or n_cols != 2:
        return {"error": "Mixed strategy solver currently supports only 2x2 games"}

    # Player 1's mix (p, 1-p): makes Player 2 indifferent
    # p * p2[0][0] + (1-p) * p2[0][1] = p * p2[1][0] + (1-p) * p2[1][1]
    # p * (p2[0][0] - p2[0][1] - p2[1][0] + p2[1][1]) = p2[1][1] - p2[0][1]
    denom_p1 = p2[0][0] - p2[0][1] - p2[1][0] + p2[1][1]
    if abs(denom_p1) < 1e-10:
        p = 0.5  # Degenerate
    else:
        p = (p2[1][1] - p2[0][1]) / denom_p1
    p = max(0, min(1, p))

    # Player 2's mix (q, 1-q): makes Player 1 indifferent
    denom_p2 = p1[0][0] - p1[0][1] - p1[1][0] + p1[1][1]
    if abs(denom_p2) < 1e-10:
        q = 0.5
    else:
        q = (p1[1][1] - p1[1][0]) / denom_p2
    q = max(0, min(1, q))

    # Expected payoffs
    p1_expected = p * q * p1[0][0] + p * (1 - q) * p1[0][1] + (1 - p) * q * p1[1][0] + (1 - p) * (1 - q) * p1[1][1]
    p2_expected = p * q * p2[0][0] + p * (1 - q) * p2[0][1] + (1 - p) * q * p2[1][0] + (1 - p) * (1 - q) * p2[1][1]

    return {
        "player1_mix": [float(p), float(1 - p)],
        "player2_mix": [float(q), float(1 - q)],
        "player1_expected_payoff": float(p1_expected),
        "player2_expected_payoff": float(p2_expected),
    }


def replicator_dynamics(p1: list[list[float]], p2: list[list[float]],
                         n_steps: int = 200, n_trajectories: int = 20) -> dict:
    """Simulate replicator dynamics for 2x2 games."""
    rng = np.random.RandomState(42)

    trajectories = []
    for _ in range(n_trajectories):
        p = rng.uniform(0.05, 0.95)
        q = rng.uniform(0.05, 0.95)
        traj_p = [p]
        traj_q = [q]

        for _ in range(n_steps):
            # Expected payoffs
            payoff_p1_strat1 = q * p1[0][0] + (1 - q) * p1[0][1]
            payoff_p1_strat2 = q * p1[1][0] + (1 - q) * p1[1][1]
            avg_p1 = p * payoff_p1_strat1 + (1 - p) * payoff_p1_strat2

            payoff_p2_strat1 = p * p2[0][0] + (1 - p) * p2[1][0]
            payoff_p2_strat2 = p * p2[0][1] + (1 - p) * p2[1][1]
            avg_p2 = q * payoff_p2_strat1 + (1 - q) * payoff_p2_strat2

            # Replicator update
            if avg_p1 != 0:
                p = p * payoff_p1_strat1 / avg_p1
            if avg_p2 != 0:
                q = q * payoff_p2_strat1 / avg_p2

            p = max(0.001, min(0.999, p))
            q = max(0.001, min(0.999, q))

            traj_p.append(p)
            traj_q.append(q)

        trajectories.append({"p": traj_p, "q": traj_q})

    return {"trajectories": trajectories}


def shapley_value(coalition_values: dict) -> dict:
    """Compute Shapley value for cooperative game.

    coalition_values: dict mapping coalition (frozenset of player indices) to value.
    E.g., {frozenset({0}): 10, frozenset({1}): 20, frozenset({0,1}): 50}
    """
    import itertools
    import math as _math

    players = set()
    for coalition in coalition_values:
        players.update(coalition)
    n = len(players)
    players = sorted(players)

    shapley = {p: 0.0 for p in players}

    for player in players:
        others = [p for p in players if p != player]
        for r in range(len(others) + 1):
            for subset in itertools.combinations(others, r):
                coalition_without = frozenset(subset)
                coalition_with = frozenset(list(subset) + [player])

                val_without = coalition_values.get(coalition_without, 0)
                val_with = coalition_values.get(coalition_with, 0)

                weight = (_math.factorial(len(subset)) *
                          _math.factorial(n - len(subset) - 1) /
                          _math.factorial(n))

                shapley[player] += weight * (val_with - val_without)

    return {str(k): float(v) for k, v in shapley.items()}


def main():
    print("=" * 60)
    print("GAME THEORY — Nash, Mixed Strategies, Evolutionary Dynamics")
    print("=" * 60)

    # Analyze each classic game
    for game_id, game in GAMES.items():
        print(f"\n--- {game['name']} ---")
        print(f"  {game['description']}")
        print(f"  Strategies: {game['strategies']}")

        # Payoff matrix
        print(f"  Payoff matrix (P1, P2):")
        for i in range(len(game["payoff_player1"])):
            row = []
            for j in range(len(game["payoff_player1"][0])):
                row.append(f"({game['payoff_player1'][i][j]}, {game['payoff_player2'][i][j]})")
            print(f"    {game['strategies'][i]}: {row}")

        # Pure Nash
        pure = find_pure_nash(game["payoff_player1"], game["payoff_player2"])
        if pure:
            for i, j in pure:
                print(f"  Pure Nash: ({game['strategies'][i]}, {game['strategies'][j]})")
        else:
            print(f"  No pure Nash equilibrium")

        # Mixed Nash
        mixed = find_mixed_nash(game["payoff_player1"], game["payoff_player2"])
        if "error" not in mixed:
            print(f"  Mixed Nash: P1=({mixed['player1_mix'][0]:.2f}, {mixed['player1_mix'][1]:.2f}), "
                  f"P2=({mixed['player2_mix'][0]:.2f}, {mixed['player2_mix'][1]:.2f})")
            print(f"  Expected payoffs: P1={mixed['player1_expected_payoff']:.2f}, P2={mixed['player2_expected_payoff']:.2f}")

    # Replicator dynamics for Prisoner's Dilemma
    print("\n--- Replicator Dynamics: Prisoner's Dilemma ---")
    pd = GAMES["prisoners_dilemma"]
    repl = replicator_dynamics(pd["payoff_player1"], pd["payoff_player2"],
                               n_steps=200, n_trajectories=15)
    print(f"  Simulated {len(repl['trajectories'])} trajectories")

    # Shapley value example
    print("\n--- Shapley Value (Cooperative Game) ---")
    # Three companies: value of coalition
    coalition_values = {
        frozenset({0}): 10,
        frozenset({1}): 20,
        frozenset({2}): 15,
        frozenset({0, 1}): 50,
        frozenset({0, 2}): 40,
        frozenset({1, 2}): 45,
        frozenset({0, 1, 2}): 100,
    }
    shapley = shapley_value(coalition_values)
    print(f"  Coalition values: {', '.join(f'{{{k}}}={v}' for k, v in coalition_values.items())}")
    print(f"  Shapley values: {json.dumps(shapley, indent=2)}")

    # ---- PLOTS ----
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    # Plot payoff matrices for each game
    for idx, (game_id, game) in enumerate(GAMES.items()):
        if idx >= 5:
            break
        ax = axes[idx // 3][idx % 3]

        p1 = np.array(game["payoff_player1"])
        p2 = np.array(game["payoff_player2"])

        # Create annotated matrix
        cell_text = []
        for i in range(len(p1)):
            row = []
            for j in range(len(p1[0])):
                row.append(f"({p1[i, j]}, {p2[i, j]})")
            cell_text.append(row)

        table = ax.table(cellText=cell_text,
                         rowLabels=game["strategies"],
                         colLabels=game["strategies"],
                         cellLoc="center",
                         loc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.5)

        # Highlight Nash equilibria
        pure = find_pure_nash(game["payoff_player1"], game["payoff_player2"])
        for i, j in pure:
            table[i, j].set_facecolor("#90EE90")

        ax.set_title(game["name"], fontsize=10, fontweight="bold")
        ax.axis("off")

    # Replicator dynamics plot
    fig2, ax = plt.subplots(figsize=(10, 8))

    # Phase portrait for Prisoner's Dilemma
    p_grid = np.linspace(0, 1, 20)
    q_grid = np.linspace(0, 1, 20)
    P, Q = np.meshgrid(p_grid, q_grid)

    dp = np.zeros_like(P)
    dq = np.zeros_like(Q)

    for i in range(len(p_grid)):
        for j in range(len(q_grid)):
            p = P[i, j]
            q = Q[i, j]
            payoff_p1_s1 = q * pd["payoff_player1"][0][0] + (1 - q) * pd["payoff_player1"][0][1]
            payoff_p1_s2 = q * pd["payoff_player1"][1][0] + (1 - q) * pd["payoff_player1"][1][1]
            avg_p1 = p * payoff_p1_s1 + (1 - p) * payoff_p1_s2

            payoff_p2_s1 = p * pd["payoff_player2"][0][0] + (1 - p) * pd["payoff_player2"][1][0]
            payoff_p2_s2 = p * pd["payoff_player2"][0][1] + (1 - p) * pd["payoff_player2"][1][1]
            avg_p2 = q * payoff_p2_s1 + (1 - q) * payoff_p2_s2

            if avg_p1 != 0:
                dp[i, j] = p * (payoff_p1_s1 - avg_p1)
            if avg_p2 != 0:
                dq[i, j] = q * (payoff_p2_s1 - avg_p2)

    ax.streamplot(P, Q, dp, dq, density=1.5, color="gray")

    # Plot trajectories
    colors = plt.cm.viridis(np.linspace(0, 1, len(repl["trajectories"])))
    for idx, traj in enumerate(repl["trajectories"]):
        ax.plot(traj["p"], traj["q"], linewidth=1, alpha=0.7, color=colors[idx])
        ax.scatter(traj["p"][0], traj["q"][0], s=20, color=colors[idx], marker="o")
        ax.scatter(traj["p"][-1], traj["q"][-1], s=30, color=colors[idx], marker="s")

    # Mark Nash equilibrium
    pure = find_pure_nash(pd["payoff_player1"], pd["payoff_player2"])
    for i, j in pure:
        ax.scatter(i, j, s=200, color="red", marker="*", zorder=10,
                   edgecolors="black", linewidth=1)

    ax.set_xlabel("P(Player 1: Cooperate)", fontsize=11)
    ax.set_ylabel("P(Player 2: Cooperate)", fontsize=11)
    ax.set_title("Replicator Dynamics: Prisoner's Dilemma\n○ = start, □ = end, ★ = Nash", fontsize=12)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = OUTPUT_DIR / "game_theory_replicator.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n✅ Replicator dynamics chart: {path}")

    # Payoff matrices chart
    path2 = OUTPUT_DIR / "game_theory_payoff_matrices.png"
    plt.figure(1)
    plt.savefig(path2, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Payoff matrices chart: {path2}")


if __name__ == "__main__":
    main()
