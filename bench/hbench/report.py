"""Aggregate result JSONL files into a Markdown leaderboard."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path


def load(paths: list[Path]) -> list[dict]:
    rows = []
    for p in paths:
        for line in p.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _median(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return statistics.median(xs) if xs else None


def _fmt(x, nd=0):
    if x is None:
        return "-"
    return f"{x:,.{nd}f}"


def _usd(x):
    return "-" if x is None else f"${x:,.2f}"


def leaderboard(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("agent") in ("oracle", "noop"):
            continue
        groups[(r["agent"], r["provider"], r["model"])].append(r)
    out = []
    for (agent, provider, model), rs in groups.items():
        graded = [r for r in rs if r.get("solved") is not None]
        solved = sum(1 for r in graded if r["solved"])
        costs = [r.get("cost_usd") for r in graded if isinstance(r.get("cost_usd"), (int, float))]
        by_cat: dict[str, list[bool]] = defaultdict(list)
        for r in graded:
            by_cat[r.get("category", "?")].append(bool(r["solved"]))
        out.append(
            {
                "agent": agent,
                "provider": provider,
                "model": model,
                "attempts": len(graded),
                "harness_errors": len(rs) - len(graded),
                "solved": solved,
                "pass_rate": solved / len(graded) if graded else None,
                "median_sec": _median(r.get("duration_sec") for r in graded),
                "median_out_tokens": _median(r.get("output_tokens") for r in graded),
                "total_cost_usd": sum(costs) if costs else None,
                "cost_per_solve": (sum(costs) / solved) if costs and solved else None,
                "by_category": {c: f"{sum(v)}/{len(v)}" for c, v in sorted(by_cat.items())},
            }
        )
    out.sort(key=lambda x: (-(x["pass_rate"] or 0), x["median_sec"] or 1e9))
    return out


def markdown(rows: list[dict]) -> str:
    lb = leaderboard(rows)
    lines = [
        "| Framework | Provider | Model | Solved | Pass rate | Median time | Median out tokens | Cost | $/solve | By category |",  # noqa: E501
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in lb:
        lines.append(
            f"| {r['agent']} | {r['provider']} | {r['model']} | {r['solved']}/{r['attempts']}"
            f"{' (+' + str(r['harness_errors']) + ' err)' if r['harness_errors'] else ''} "
            f"| {_fmt((r['pass_rate'] or 0) * 100)}% | {_fmt(r['median_sec'])}s "
            f"| {_fmt(r['median_out_tokens'])} | {_usd(r['total_cost_usd'])} "
            f"| {_usd(r['cost_per_solve'])} "
            f"| {', '.join(f'{k} {v}' for k, v in r['by_category'].items())} |"
        )
    # Per-task grid
    tasks = sorted({r["task"] for r in rows})
    combos = sorted({(r["agent"], r["provider"], r["model"]) for r in rows})
    grid = defaultdict(list)
    for r in rows:
        grid[(r["task"], (r["agent"], r["provider"], r["model"]))].append(r.get("solved"))
    lines += ["", "| Task | " + " | ".join(f"{a}/{p}/{m}" for a, p, m in combos) + " |", "|---|" + "---|" * len(combos)]  # noqa: E501
    sym = {True: "✓", False: "✗", None: "!"}
    for t in tasks:
        cells = ["".join(sym[s] for s in grid.get((t, c), [])) or " " for c in combos]
        lines.append(f"| {t} | " + " | ".join(cells) + " |")
    lines += ["", "✓ solved · ✗ failed · ! harness error (not counted)"]
    return "\n".join(lines) + "\n"
