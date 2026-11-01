#!/usr/bin/env python3
"""Where did the Ollama tokens go? Run on a Hermes VM: python3 ollama_usage.py [--since 2026-10-15] [--home ~/.hermes]

Reads state.db (main + profiles) and the kanban boards read-only, keeps the per-model usage rows that ran on
Ollama Cloud, and prints the split by profile, model, source, day, kanban task and the top sessions.
Cost is the API-equivalent from ~/.hermes/autonomy/budget.json prices_per_mtok [in, cached, out] (stdlib only).
"""
import argparse
import datetime as dt
import glob
import json
import os
import sqlite3
from collections import defaultdict

LOCAL_HINTS = ("127.0.0.1", "localhost", "llama.cpp", "llama-server", "llamacpp")


def ro(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def cols(con, table):
    return {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}


def num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def when(v):
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)) or str(v).replace(".", "", 1).isdigit():
        x = float(v)
        if x > 1e12:
            x /= 1000
        return dt.datetime.fromtimestamp(x, dt.timezone.utc)
    try:
        d = dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def is_ollama(model, hint):
    h = (hint or "").lower()
    if any(x in h for x in LOCAL_HINTS):
        return False
    if "ollama" in h:
        return True
    m = (model or "").lower()
    if any(x in m for x in ("claude", "gemini", "gpt-4", "gpt-5", "o3", "o4")):
        return False
    return ":cloud" in m or any(x in m for x in ("deepseek", "glm", "kimi", "qwen", "gpt-oss", "minimax"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default="~/.hermes")
    ap.add_argument("--since", default=None, help="UTC date, e.g. 2026-10-15")
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()
    home = os.path.expanduser(a.home)
    since = dt.datetime.fromisoformat(a.since).replace(tzinfo=dt.timezone.utc) if a.since else None

    prices = {}
    try:
        prices = json.load(open(os.path.join(home, "autonomy", "budget.json"))).get("prices_per_mtok", {})
    except (OSError, ValueError):
        pass

    def cost(model, i, cr, o):
        p = prices.get(model) or prices.get((model or "").split(":")[0]) or prices.get("_default") or [0, 0, 0]
        return (max(i - cr, 0) * p[0] + cr * p[1] + o * p[2]) / 1e6

    # kanban: session that created a task, and worker sessions of runs
    task_of = {}
    for kb in glob.glob(os.path.join(home, "kanban*.db")):
        try:
            con = ro(kb)
            if "tasks" in [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
                tc = cols(con, "tasks")
                if "session_id" in tc:
                    for r in con.execute("SELECT id, title, session_id FROM tasks"):
                        if r["session_id"]:
                            task_of[r["session_id"]] = f'{r["id"]} {r["title"]}'
            con.close()
        except sqlite3.Error:
            pass

    dbs = [("main", os.path.join(home, "state.db"))] + [
        (os.path.basename(os.path.dirname(p)), p) for p in sorted(glob.glob(os.path.join(home, "profiles", "*", "state.db")))]
    rows = []
    for profile, path in dbs:
        if not os.path.exists(path):
            continue
        con = ro(path)
        sc = cols(con, "sessions")
        start = next((c for c in ("started_at", "created_at", "start_time") if c in sc), None)
        src = next((c for c in ("source", "platform") if c in sc), None)
        par = next((c for c in ("parent_session_id", "parent_id") if c in sc), None)
        sess = {}
        for r in con.execute(f'SELECT id, title, {start or "NULL"} AS st, {src or "NULL"} AS src, '
                             f'{par or "NULL"} AS par, cwd FROM sessions' if "cwd" in sc else
                             f'SELECT id, title, {start or "NULL"} AS st, {src or "NULL"} AS src, '
                             f'{par or "NULL"} AS par, NULL AS cwd FROM sessions'):
            sess[r["id"]] = dict(r)
        mc = cols(con, "messages")
        first = {}
        if {"session_id", "role", "content"} <= mc:
            for r in con.execute("SELECT session_id, content FROM messages WHERE role='user' ORDER BY id"):
                first.setdefault(r["session_id"], (r["content"] or "")[:160].replace("\n", " "))
        if cols(con, "session_model_usage"):
            for r in con.execute("SELECT * FROM session_model_usage"):
                u = dict(r)
                hint = f"{u.get('billing_provider') or ''} {u.get('base_url') or ''}"
                if not is_ollama(u.get("model"), hint):
                    continue
                s = sess.get(u.get("session_id"), {})
                t = when(s.get("st"))
                if since and (t is None or t < since):
                    continue
                i, o = num(u.get("input_tokens")), num(u.get("output_tokens")) + num(u.get("reasoning_tokens"))
                cr = num(u.get("cache_read_tokens"))
                rows.append({
                    "profile": profile, "session": u.get("session_id"), "model": u.get("model") or "?",
                    "task": u.get("task") or "", "source": s.get("src") or "?", "title": s.get("title") or "",
                    "parent": s.get("par"), "day": t.date().isoformat() if t else "?",
                    "in": i, "cache": cr, "out": o, "usd": cost(u.get("model"), i, cr, o),
                    "first_user": first.get(u.get("session_id"), ""),
                    "kanban": task_of.get(u.get("session_id"), ""),
                })
        con.close()

    total = sum(r["usd"] for r in rows) or 1e-9
    tok = sum(r["in"] + r["out"] for r in rows)
    print(f"Ollama usage rows: {len(rows)}  tokens in+out: {tok/1e6:.1f}M  API-equivalent: ${total:.2f}"
          + (f"  since {a.since}" if a.since else ""))

    def table(name, key, n=15):
        agg = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, set()])
        for r in rows:
            k = key(r)
            g = agg[k]
            g[0] += r["usd"]; g[1] += r["in"]; g[2] += r["out"]; g[3] += r["cache"]; g[4].add(r["session"])
        print(f"\n## by {name}")
        for k, g in sorted(agg.items(), key=lambda kv: -kv[1][0])[:n]:
            print(f"{g[0]/total*100:5.1f}%  ${g[0]:8.2f}  in {g[1]/1e6:7.2f}M (cache {g[3]/1e6:6.2f}M)  "
                  f"out {g[2]/1e6:6.2f}M  sessions {len(g[4]):4d}  {k}")

    table("profile", lambda r: r["profile"])
    table("model", lambda r: r["model"])
    table("source", lambda r: r["source"])
    table("usage task", lambda r: r["task"] or "-")
    table("day", lambda r: r["day"], 40)
    table("kanban task", lambda r: r["kanban"] or "-", 20)
    table("session title", lambda r: f'{r["profile"]}/{r["source"]}: {r["title"][:70]}', 20)

    by_sess = defaultdict(lambda: {"usd": 0.0, "in": 0.0, "out": 0.0})
    meta = {}
    for r in rows:
        b = by_sess[r["session"]]
        b["usd"] += r["usd"]; b["in"] += r["in"]; b["out"] += r["out"]
        meta[r["session"]] = r
    print(f"\n## top {a.top} sessions")
    for sid, b in sorted(by_sess.items(), key=lambda kv: -kv[1]["usd"])[:a.top]:
        m = meta[sid]
        print(f'${b["usd"]:7.2f}  {b["in"]/1e6:6.2f}M in  {m["day"]}  {m["profile"]}/{m["source"]}  {sid}  '
              f'"{m["title"][:60]}"  kanban={m["kanban"][:50]!r}  prompt={m["first_user"][:120]!r}')


if __name__ == "__main__":
    main()
