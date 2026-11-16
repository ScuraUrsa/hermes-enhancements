#!/usr/bin/env python3
"""Benchmark the cheap-route evaluator against eval_set.jsonl.

Runs every question through the hard rules (rules.py) and, when they do not decide,
through a local llama-server (OpenAI-compatible /v1/chat/completions) with prompt.md as
the system prompt. Reports accuracy, the two numbers that matter (false free_web, which
leaks private context, and missed free_web, which only costs money), and latency.

usage: python bench_route.py [--url http://127.0.0.1:8081/v1] [--model x] [--runs 1]
                             [--threshold 0.8] [--no-rules] [--tag label] [--only q001,q002]
Writes raw/<tag>.jsonl (one row per question run) and prints a summary.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rules import hard_route  # noqa: E402

SYSTEM = open(os.path.join(HERE, "prompt.md"), encoding="utf-8").read()


def ask_model(url: str, model: str, text: str, timeout: float = 60.0) -> tuple[dict, float]:
    body = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
        "temperature": 0.0,
        "max_tokens": 120,
        "response_format": {"type": "json_object"},
    }
    t0 = time.time()
    r = requests.post(f"{url.rstrip('/')}/chat/completions", json=body, timeout=timeout)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"] or ""
    dt = time.time() - t0
    m = re.search(r"\{.*\}", content, re.S)
    try:
        parsed = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        parsed = {}
    return parsed, dt


def decide(parsed: dict, threshold: float) -> str:
    route = str(parsed.get("route", "hermes")).strip().lower()
    try:
        conf = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    return "free_web" if route == "free_web" and conf >= threshold else "hermes"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8081/v1")
    ap.add_argument("--model", default="local")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--threshold", type=float, default=0.8)
    ap.add_argument("--no-rules", action="store_true", help="skip rules.py, model decides everything")
    ap.add_argument("--only", default="")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    rows = [json.loads(line) for line in open(os.path.join(HERE, "eval_set.jsonl"), encoding="utf-8") if line.strip()]
    if args.only:
        keep = set(args.only.split(","))
        rows = [r for r in rows if r["id"] in keep]
    tag = args.tag or re.sub(r"[^a-z0-9]+", "-", args.model.lower()).strip("-") or "run"
    os.makedirs(os.path.join(HERE, "raw"), exist_ok=True)
    out = open(os.path.join(HERE, "raw", f"{tag}.jsonl"), "w", encoding="utf-8")

    total = correct = false_free = missed_free = 0
    by_rule = 0
    latencies: list[float] = []
    for run in range(args.runs):
        for row in rows:
            rule = None if args.no_rules else hard_route(row["text"])
            parsed, dt = ({}, 0.0)
            if rule is None:
                try:
                    parsed, dt = ask_model(args.url, args.model, row["text"])
                except Exception as exc:  # a dead server is a benchmark failure, not a route
                    parsed, dt = {"error": str(exc)}, 0.0
                got = decide(parsed, args.threshold)
                latencies.append(dt)
            else:
                got = rule
                by_rule += 1
            ok = got == row["label"]
            total += 1
            correct += ok
            if got == "free_web" and row["label"] == "hermes":
                false_free += 1
            if got == "hermes" and row["label"] == "free_web":
                missed_free += 1
            out.write(json.dumps({"run": run, **row, "got": got, "by_rule": rule is not None,
                                  "model": parsed, "latency_s": round(dt, 2)}, ensure_ascii=False) + "\n")
            mark = "PASS" if ok else ("LEAK" if got == "free_web" else "miss")
            src = "rule " if rule is not None else "model"
            print(f"[{run}] {row['id']} {mark:4} {src} {got:8} ({row['label']:8}) {dt:4.1f}s  {row['text'][:70]}")
    out.close()
    lat = sorted(latencies)
    p50 = lat[len(lat) // 2] if lat else 0.0
    print(f"\nSUMMARY {tag}: {correct}/{total} = {100 * correct // max(total, 1)}%  "
          f"false free_web (private leak) = {false_free}  missed free_web = {missed_free}  "
          f"decided by rules = {by_rule}  model p50 = {p50:.1f}s  max = {lat[-1] if lat else 0:.1f}s")
    return 0 if false_free == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
