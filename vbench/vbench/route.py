"""From results.jsonl to a leaderboard and the routing table the pipeline reads (routing.json).

Rule, per stage and video type: a model is good enough when its mean score is at least the stage's
floor AND within ``rel`` of the best model on that type, with few failures; among good-enough
models the one with the lowest API-equivalent cost per video wins (latency breaks ties).
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .bundle import VIDEO_TYPES
from .scoring import TALK, VISUAL_HEAVY

FLOORS = {"classify": 90.0, "vision": 65.0, "report": 70.0, "transcribe": 80.0}
FRAMES_PER_MIN = {"talk": 0.5, "visual": 3.0, "default": 1.5, "short": 4.0}


@dataclass
class Rule:
    rel: float = 0.92
    floors: dict[str, float] = field(default_factory=lambda: dict(FLOORS))
    max_fail_rate: float = 0.10
    min_n: int = 2


@dataclass
class Agg:
    ref: str
    stage: str
    scores: list[float] = field(default_factory=list)
    fails: int = 0
    costs: list[float | None] = field(default_factory=list)
    marginal: list[float | None] = field(default_factory=list)
    latency: list[float] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.scores)

    @property
    def mean(self) -> float:
        return statistics.fmean(self.scores) if self.scores else 0.0

    @property
    def sd(self) -> float:
        return statistics.pstdev(self.scores) if len(self.scores) > 1 else 0.0

    @property
    def fail_rate(self) -> float:
        return self.fails / self.n if self.n else 1.0

    @property
    def cost(self) -> float | None:
        known = [c for c in self.costs if c is not None]
        return statistics.fmean(known) if known and len(known) == len(self.costs) else None

    @property
    def lat(self) -> float:
        return statistics.fmean(self.latency) if self.latency else 0.0

    def summary(self) -> dict[str, Any]:
        return {"ref": self.ref, "n": self.n, "score": round(self.mean, 1), "sd": round(self.sd, 1),
                "fail_rate": round(self.fail_rate, 2),
                "equiv_usd_per_video": None if self.cost is None else round(self.cost, 5),
                "latency_sec": round(self.lat, 1)}


def load_rows(paths: list[Path]) -> list[dict]:
    rows = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            p = p / "results.jsonl"
        rows += [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    return rows


def aggregate(rows: list[dict]) -> dict[tuple[str, str], dict[str, Agg]]:
    """(stage, video_type or '*') -> ref -> Agg. ``video_url`` rows count as the report stage."""
    out: dict[tuple[str, str], dict[str, Agg]] = defaultdict(dict)
    for r in rows:
        stage = "report" if r["stage"] == "video_url" else r["stage"]
        for vt in (r.get("video_type") or "other", "*"):
            a = out[(stage, vt)].setdefault(r["ref"], Agg(r["ref"], r["stage"]))
            a.scores.append(float(r.get("score") or 0.0))
            a.fails += 0 if r.get("ok") and not r.get("gate") else 1
            a.costs.append(r.get("equiv_usd"))
            a.marginal.append(r.get("marginal_usd"))
            a.latency.append(float(r.get("latency_sec") or 0.0))
    return out


def choose(aggs: dict[str, Agg], stage: str, rule: Rule, extra_cost: dict[str, float] | None = None
           ) -> tuple[Agg | None, list[Agg], bool]:
    """Return (winner, eligible, low_confidence)."""
    cands = [a for a in aggs.values() if a.n]
    if not cands:
        return None, [], True
    best = max(a.mean for a in cands)
    bar = max(rule.floors.get(stage, 0.0), rule.rel * best)
    eligible = [a for a in cands if a.mean >= bar and a.fail_rate <= rule.max_fail_rate]
    low_conf = not eligible or any(a.n < rule.min_n for a in eligible)
    if not eligible:  # nothing clears the bar: take the best scorer, flagged
        return max(cands, key=lambda a: a.mean), [], True

    def eff_cost(a: Agg) -> float:
        c = a.cost if a.cost is not None else float("inf")
        return c + (extra_cost or {}).get(a.ref, 0.0)
    eligible.sort(key=lambda a: (eff_cost(a), a.lat))
    return eligible[0], eligible, low_conf


def fpm_for(vt: str) -> float:
    if vt == "short":
        return FRAMES_PER_MIN["short"]
    if vt in TALK:
        return FRAMES_PER_MIN["talk"]
    if vt in VISUAL_HEAVY:
        return FRAMES_PER_MIN["visual"]
    return FRAMES_PER_MIN["default"]


def build_routing(rows: list[dict], rule: Rule | None = None, source: str = "") -> dict[str, Any]:
    rule = rule or Rule()
    agg = aggregate(rows)
    url_refs = {r["ref"] for r in rows if r["stage"] == "video_url"}
    classify, _, cl_low = choose(agg.get(("classify", "*"), {}), "classify", rule)
    routing: dict[str, Any] = {
        "schema": "vbench_routing/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_run": source,
        "rule": {"rel": rule.rel, "floors": rule.floors, "max_fail_rate": rule.max_fail_rate, "min_n": rule.min_n,
                 "rank_by": "API-equivalent USD per video"},
    }

    def entry(vt: str) -> dict[str, Any]:
        key = "*" if vt == "default" else vt
        e: dict[str, Any] = {"classify": classify.ref if classify else None, "skip": False,
                             "frames_per_min": fpm_for(vt), "evidence": {}}
        if classify:
            e["evidence"]["classify"] = classify.summary()
        vis, vis_ok, v_low = choose(agg.get(("vision", key), {}), "vision", rule)
        vis_cost = (vis.cost or 0.0) * fpm_for(vt) / 2.0 if vis else 0.0  # vision was benchmarked at 2 frames/min
        # A video_url model replaces both vision and report; every other report model also pays for vision.
        rep_aggs = agg.get(("report", key), {})
        extra = {ref: (0.0 if ref in url_refs else vis_cost) for ref in rep_aggs}
        rep, _, r_low = choose(rep_aggs, "report", rule, extra)
        e["report"] = rep.ref if rep else None
        e["vision"] = None if (rep and rep.ref in url_refs) else (vis.ref if vis else None)
        # next good-enough vision model, used when the first is retired or failing
        e["vision_fallback"] = next((x.ref for x in vis_ok if vis and x.ref != vis.ref), None) if e["vision"] else None
        if vis and e["vision"]:
            e["evidence"]["vision"] = vis.summary()
        if rep:
            e["evidence"]["report"] = rep.summary()
        e["low_confidence"] = bool(cl_low or v_low or r_low)
        return e

    routing["default"] = entry("default")
    tr_rows = [r for r in rows if r["stage"] == "transcribe"]
    if tr_rows:  # speech-to-text is chosen per language, not per video type
        by_lang: dict[str, Any] = {}
        for lang in sorted({r.get("language") or "?" for r in tr_rows}) + ["*"]:
            sub = [dict(r, video_type=lang) for r in tr_rows if lang == "*" or (r.get("language") or "?") == lang]
            win, _, low = choose(aggregate(sub).get(("transcribe", "*"), {}), "transcribe", rule)
            if win:
                by_lang["default" if lang == "*" else lang] = {"ref": win.ref, "low_confidence": low,
                                                               "evidence": win.summary()}
        routing["transcribe"] = by_lang
    seen = {r.get("video_type") for r in rows}
    for vt in VIDEO_TYPES:
        if vt == "music_artistic":
            routing[vt] = {"classify": routing["default"]["classify"], "skip": True, "vision": None,
                           "report": None, "frames_per_min": 0, "evidence": {}, "low_confidence": False}
        elif vt in seen:
            routing[vt] = entry(vt)
    return routing


def leaderboard_md(rows: list[dict], routing: dict[str, Any]) -> str:
    agg = aggregate(rows)
    out = ["# vbench leaderboard", "",
           f"{len(rows)} runs, {len({r['video_id'] for r in rows})} videos. Scores 0-100 (judge: see DESIGN.md). "
           "Cost is API-equivalent USD per video for that stage; on Filip's subscriptions the marginal cost is $0.", ""]
    for stage in ("classify", "transcribe", "vision", "report"):
        rows_all = sorted(agg.get((stage, "*"), {}).values(), key=lambda a: -a.mean)
        if not rows_all:
            continue
        out += [f"## {stage}", "", "| model | n | score | sd | fail | $/video | s/video |", "|---|---|---|---|---|---|---|"]
        for a in rows_all:
            s = a.summary()
            cost = "?" if s["equiv_usd_per_video"] is None else f"{s['equiv_usd_per_video']:.4f}"
            out.append(f"| {a.ref} | {s['n']} | {s['score']} | {s['sd']} | {s['fail_rate']:.0%} | {cost} | "
                       f"{s['latency_sec']} |")
        out.append("")
        types = sorted({vt for (st, vt) in agg if st == stage and vt != "*"})
        if types:
            out += [f"### {stage} by video type (score / $ per video)", "",
                    "| model | " + " | ".join(types) + " |", "|---|" + "---|" * len(types)]
            for a in rows_all:
                cells = []
                for vt in types:
                    x = agg.get((stage, vt), {}).get(a.ref)
                    cells.append("" if not x else f"{x.mean:.0f} / {'?' if x.cost is None else f'{x.cost:.4f}'}")
                out.append(f"| {a.ref} | " + " | ".join(cells) + " |")
            out.append("")
    out += ["## Routing", "", "| video type | classify | vision | report | frames/min | note |", "|---|---|---|---|---|---|"]
    for vt, e in routing.items():
        if vt == "transcribe" or not isinstance(e, dict) or "report" not in e:
            continue
        note = "skip (listed only)" if e.get("skip") else ("low confidence" if e.get("low_confidence") else "")
        out.append(f"| {vt} | {e.get('classify')} | {e.get('vision')} | {e.get('report')} | {e.get('frames_per_min')} | {note} |")
    if routing.get("transcribe"):
        out += ["", "Speech-to-text when a video has no captions: " + ", ".join(
            f"{lang}: {v['ref']}" for lang, v in routing["transcribe"].items())]
    return "\n".join(out) + "\n"
