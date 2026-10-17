#!/usr/bin/env python3
"""Trace collector: Filip's prompt -> Claude threads / Hermes sessions -> commits and PRs -> result.

Reads (all read-only):
  * Hermes session databases (state.db of ~/.hermes and of every profile), on this VM and, when given,
    copies fetched from other VMs (--extra-hermes-home, e.g. a dev snapshot);
  * the kanban board (kanban.db or the kanban-dev.db snapshot on prod);
  * ~/.hermes/autonomy/claude_runs.jsonl (Claude Code runs started by cc_run.py);
  * claude_threads.json: the Claude project threads with their usage, exported by the project's
    Claude thread (orphan data branch of the private ScuraUrsa/hermes-default-workspace);
  * GitHub: pull requests and recent commits of the ScuraUrsa repositories.

Writes one file, trace.json, that web/index.html renders. Python 3.10+, standard library only.

Linking (see README.md, "How a change is tied to a prompt"):
  * Claude thread -> PR: the PR's head branch is the thread session's branch (claude/project-thread-*),
    or the PR body links the thread (thread=cmsg_...) or the session (session_...).
  * Claude thread -> commit: trailer "Claude-Session: .../session_<id>" or the commit is in such a PR.
  * Hermes chat -> subagent sessions: parent_session_id.
  * Hermes -> kanban task: task.created_by / the session that created it; task -> worker sessions by
    the task id in the session (cwd, title, kanban columns); task -> Claude Code runs by task_id.
  * kanban task -> PR / commit: branch wt/t_<id>, or "t_<id>" / "Kanban-Task: t_<id>" in the PR or commit.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

TASK_RE = re.compile(r"\bt_[0-9a-f]{8}\b")
SESSION_RE = re.compile(r"session_[0-9A-Za-z]{20,}")
THREAD_RE = re.compile(r"cmsg_[0-9A-Za-z]{20,}")
PROJECT_URL = "https://claude.ai/code/project/{project}?thread={thread}"
SESSION_URL = "https://claude.ai/code/{session}"
CHAT_SOURCES = {"cli", "telegram", "whatsapp", "discord", "slack", "signal", "matrix", "api_server",
                "api", "voice", "homeassistant", "email", "sms", "web"}


# ---------------------------------------------------------------------------------------------- utils
def iso(value) -> str | None:
    """Epoch seconds/ms or an ISO string -> ISO 8601 UTC (or None)."""
    if value in (None, "", 0):
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and re.fullmatch(r"\d+(\.\d+)?", value)):
        v = float(value)
        if v > 1e12:
            v /= 1000.0
        return dt.datetime.fromtimestamp(v, dt.timezone.utc).isoformat(timespec="seconds")
    s = str(value).strip().replace(" ", "T", 1)
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


def month_of(ts: str | None) -> str:
    return (ts or "")[:7] or "unknown"


def short(text, n=400) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


SECRET_RES = [
    re.compile(r"(ghp_|gho_|github_pat_|sk-ant-|sk-|xox[abpr]-|AKIA)[A-Za-z0-9_\-]{8,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}"),
    re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)"),
]


def redact(text: str) -> str:
    for r in SECRET_RES:
        text = r.sub("[redacted]", text or "")
    return text


def provider_of(model: str | None, hint: str | None = None) -> str:
    """anthropic | ollama | gemini | local | other, from the billing provider / base URL first, then the model."""
    m = (model or "").lower()
    h = (hint or "").lower()
    if any(k in h for k in ("127.0.0.1", "localhost", "llama.cpp", "llamacpp")):
        return "local"
    if "ollama" in h:
        return "ollama"
    if "anthropic" in h or "claude" in h:
        return "anthropic"
    if "gemini" in h or "googleapis" in h:
        return "gemini"
    if any(k in m for k in ("claude", "opus", "sonnet", "haiku", "fable")):
        return "anthropic"
    if "gemini" in m:
        return "gemini"
    if any(k in m for k in ("deepseek", "kimi", "glm", "gpt-oss", "minimax", "qwen3-coder")):
        return "ollama"
    if "gguf" in m or m in ("local", "qwen3.5-4b"):
        return "local"
    return "other"


def num(v, kind=int):
    try:
        return kind(float(v)) if v not in (None, "") else kind(0)
    except (TypeError, ValueError):
        return kind(0)


def tokens(inp=0, out=0, cr=0, cw=0) -> dict:
    return {"input": num(inp), "output": num(out), "cache_read": num(cr), "cache_write": num(cw)}


def tok_sum(t: dict) -> int:
    return sum(int(t.get(k, 0) or 0) for k in ("input", "output", "cache_read", "cache_write"))


# ---------------------------------------------------------------------------------------------- Hermes
def open_ro(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def cols(con, table) -> set[str]:
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


def first_col(available: set[str], *names) -> str | None:
    for n in names:
        if n in available:
            return n
    return None


def hermes_dbs(homes: list[str]) -> list[tuple[str, str, str]]:
    """(vm, profile, path) of every state.db under the given homes ("vm=path" or a plain path)."""
    out = []
    for h in homes:
        vm, _, path = h.partition("=") if "=" in h else ("prod", "", h)
        path = os.path.expanduser(path)
        root = os.path.join(path, "state.db")
        if os.path.exists(root):
            out.append((vm, "main", root))
        for p in sorted(glob.glob(os.path.join(path, "profiles", "*", "state.db"))):
            out.append((vm, Path(p).parent.name, p))
    return out


def read_hermes_sessions(dbs) -> list[dict]:
    seen = {}
    for vm, profile, path in dbs:
        try:
            con = open_ro(path)
        except sqlite3.Error as e:
            print(f"warn: {path}: {e}", file=sys.stderr)
            continue
        c = cols(con, "sessions")
        if not c:
            continue
        pick = {
            "id": first_col(c, "id", "session_id"),
            "source": first_col(c, "source", "platform"),
            "title": first_col(c, "title", "name"),
            "model": first_col(c, "model", "model_name"),
            "provider": first_col(c, "billing_provider", "provider", "model_provider"),
            "base_url": first_col(c, "billing_base_url", "base_url"),
            "started": first_col(c, "started_at", "created_at", "start_time"),
            "ended": first_col(c, "ended_at", "updated_at", "end_time"),
            "end_reason": first_col(c, "end_reason"),
            "parent": first_col(c, "parent_session_id", "parent_id"),
            "cwd": first_col(c, "cwd", "working_dir"),
            "in": first_col(c, "input_tokens", "prompt_tokens"),
            "out": first_col(c, "output_tokens", "completion_tokens"),
            "cr": first_col(c, "cache_read_tokens", "cache_read_input_tokens"),
            "cw": first_col(c, "cache_write_tokens", "cache_creation_tokens", "cache_creation_input_tokens"),
            "reasoning": first_col(c, "reasoning_tokens"),
            "cost": first_col(c, "actual_cost_usd", "estimated_cost_usd", "cost_usd"),
            "msgs": first_col(c, "message_count"),
            "tools": first_col(c, "tool_call_count"),
            "user_id": first_col(c, "user_id"),
        }
        sel = ", ".join(f'"{v}" AS "{k}"' if v else f'NULL AS "{k}"' for k, v in pick.items())
        mc = cols(con, "messages")
        sid_col = first_col(mc, "session_id")
        role_col = first_col(mc, "role")
        content_col = first_col(mc, "content", "text")
        order_col = first_col(mc, "id", "timestamp", "created_at")
        usage = defaultdict(list)
        uc = cols(con, "session_model_usage")
        if uc:
            for r in con.execute("SELECT * FROM session_model_usage"):
                u = dict(r)
                usage[u.get("session_id")].append({
                    "model": u.get("model") or "", "provider": provider_of(
                        u.get("model"), f"{u.get('billing_provider') or ''} {u.get('base_url') or ''}"),
                    "task": u.get("task") or "",
                    "tokens": tokens(num(u.get("input_tokens")), num(u.get("output_tokens")) + num(u.get("reasoning_tokens")),
                                     num(u.get("cache_read_tokens")), num(u.get("cache_write_tokens"))),
                    "reported_cost": num(u.get("actual_cost_usd") or u.get("estimated_cost_usd"), float)})
        for r in con.execute(f"SELECT {sel} FROM sessions"):
            d = dict(r)
            key = (d["id"])
            first_user = ""
            if sid_col and role_col and content_col:
                row = con.execute(
                    f"SELECT {content_col} FROM messages WHERE {sid_col}=? AND {role_col}='user' "
                    f"ORDER BY {order_col} LIMIT 1", (d["id"],)).fetchone()
                if row and row[0]:
                    first_user = row[0] if isinstance(row[0], str) else str(row[0])
            s = {
                "vm": vm, "profile": profile, "id": d["id"], "source": d["source"] or "",
                "title": d["title"] or "", "model": d["model"] or "",
                "provider": provider_of(d["model"], f"{d['provider'] or ''} {d['base_url'] or ''}"),
                "started": iso(d["started"]), "ended": iso(d["ended"]), "end_reason": d["end_reason"],
                "parent": d["parent"], "cwd": d["cwd"] or "",
                "tokens": tokens(num(d["in"]), num(d["out"]) + num(d["reasoning"]), num(d["cr"]), num(d["cw"])),
                "reported_cost": num(d["cost"], float),
                "messages": d["msgs"], "tool_calls": d["tools"],
                "first_user": redact(short(first_user, 1200)),
                "usage": usage.get(d["id"], []),
            }
            # The dev VM started as a clone of prod: the same session can be in both, keep the later copy.
            old = seen.get(key)
            if old is None or tok_sum(s["tokens"]) >= tok_sum(old["tokens"]):
                seen[key] = s
        con.close()
    return list(seen.values())


def read_kanban(paths: list[str]) -> tuple[dict, dict]:
    """tasks by id, runs by task id. Later paths win (dev's live board over prod's snapshot)."""
    tasks, runs = {}, defaultdict(list)
    for spec in paths:
        vm, _, path = spec.partition("=") if "=" in spec else ("dev", "", spec)
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            continue
        con = open_ro(path)
        tc = cols(con, "tasks")
        if not tc:
            continue
        for r in con.execute("SELECT * FROM tasks"):
            d = dict(r)
            tid = d.get("id")
            tasks[tid] = {
                "id": tid, "vm": vm, "title": d.get("title") or "", "status": d.get("status") or "",
                "assignee": d.get("assignee") or "", "created_by": d.get("created_by") or "",
                "created": iso(d.get("created_at")), "started": iso(d.get("started_at")),
                "completed": iso(d.get("completed_at")), "branch": d.get("branch_name") or "",
                "workspace": d.get("workspace_path") or "",
                "body": redact(short(d.get("body") or d.get("description") or "", 1200)),
                "result": redact(short(d.get("result") or "", 800)),
                "origin_session": d.get("session_id") or "",
                "session_ids": set(),
            }
        rt = next((t for t in ("runs", "task_runs") if cols(con, t)), None)
        if rt:
            for r in con.execute(f"SELECT * FROM {rt}"):
                d = dict(r)
                tid = d.get("task_id")
                if tid:
                    try:
                        meta = json.loads(d.get("metadata") or "{}")
                    except (TypeError, ValueError):
                        meta = {}
                    if isinstance(meta, dict) and meta.get("worker_session_id"):
                        d["worker_session_id"] = meta["worker_session_id"]
                    d["started_iso"], d["ended_iso"] = iso(d.get("started_at")), iso(d.get("ended_at"))
                    runs[tid].append({k: v for k, v in d.items() if not isinstance(v, bytes) and k != "metadata"})
        con.close()
    for tid in tasks:
        tasks[tid]["runs"] = runs.get(tid, [])
        for run in runs.get(tid, []):
            for k, v in run.items():
                if k in ("session_id", "worker_session_id") and isinstance(v, str) and v:
                    tasks[tid]["session_ids"].add(v)
    return tasks, runs


def read_claude_runs(paths: list[str]) -> list[dict]:
    out, seen = [], set()
    for spec in paths:
        vm, _, path = spec.partition("=") if "=" in spec else ("prod", "", spec)
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                key = r.get("session_id") or (r.get("ts"), r.get("cwd"))
                if key in seen:
                    continue
                seen.add(key)
                r.setdefault("vm", vm)
                out.append(r)
    return out


# ---------------------------------------------------------------------------------------------- GitHub
class GitHub:
    def __init__(self, token: str | None, cache_path: str):
        self.token = token
        self.cache_path = cache_path
        try:
            with open(cache_path, encoding="utf-8") as f:
                self.cache = json.load(f)
        except (OSError, ValueError):
            self.cache = {}
        self.calls = 0

    def save(self):
        tmp = self.cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.cache, f)
        os.replace(tmp, self.cache_path)

    def get(self, url: str, ttl: int = 900):
        hit = self.cache.get(url)
        if hit and time.time() - hit["t"] < ttl:
            return hit["v"]
        req = urllib.request.Request(url if url.startswith("http") else "https://api.github.com" + url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "hermes-trace-dashboard")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        if hit and hit.get("etag"):
            req.add_header("If-None-Match", hit["etag"])
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                v = json.load(resp)
                self.cache[url] = {"t": time.time(), "v": v, "etag": resp.headers.get("ETag")}
                return v
        except urllib.error.HTTPError as e:
            if e.code == 304 and hit:
                hit["t"] = time.time()
                return hit["v"]
            print(f"warn: GitHub {url}: HTTP {e.code}", file=sys.stderr)
            return hit["v"] if hit else None
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"warn: GitHub {url}: {e}", file=sys.stderr)
            return hit["v"] if hit else None

    def pages(self, url: str, ttl: int = 900, max_pages: int = 10):
        out = []
        sep = "&" if "?" in url else "?"
        for page in range(1, max_pages + 1):
            v = self.get(f"{url}{sep}per_page=100&page={page}", ttl)
            if not v:
                break
            out.extend(v)
            if len(v) < 100:
                break
        return out


def read_github(gh: GitHub, owner: str, since: str, only: list[str] | None = None) -> tuple[list, list]:
    if only:
        repos = [{"full_name": r if "/" in r else f"{owner}/{r}", "pushed_at": "9999"} for r in only]
    else:
        repos = [r for r in gh.pages("/user/repos?affiliation=owner", ttl=6 * 3600)
                 if r.get("owner", {}).get("login", "").lower() == owner.lower()] or \
            gh.pages(f"/users/{owner}/repos?type=owner", ttl=6 * 3600)
    prs, commits = [], []
    for repo in repos:
        name = repo["full_name"]
        if (repo.get("pushed_at") or "") < since:
            continue
        for p in gh.pages(f"/repos/{name}/pulls?state=all&sort=updated&direction=desc", max_pages=3):
            prs.append({
                "repo": name, "number": p["number"], "title": p.get("title") or "",
                "state": "merged" if p.get("merged_at") else p.get("state"), "draft": p.get("draft"),
                "head": (p.get("head") or {}).get("ref") or "", "base": (p.get("base") or {}).get("ref") or "",
                "created": p.get("created_at"), "merged": p.get("merged_at"), "closed": p.get("closed_at"),
                "url": p.get("html_url"), "body": p.get("body") or "", "author": (p.get("user") or {}).get("login"),
            })
        for c in gh.pages(f"/repos/{name}/commits?since={since}", max_pages=5):
            msg = (c.get("commit") or {}).get("message") or ""
            commits.append({
                "repo": name, "sha": c.get("sha"), "title": msg.splitlines()[0] if msg else "",
                "message": msg, "date": ((c.get("commit") or {}).get("committer") or {}).get("date"),
                "url": c.get("html_url"),
            })
    # Commits of the PRs that are tied to something are fetched later, on demand (pr_commits).
    return prs, commits


def pr_commits(gh: GitHub, pr: dict) -> list[dict]:
    ttl = 30 * 86400 if pr["state"] in ("merged", "closed") else 900
    out = []
    for c in gh.pages(f"/repos/{pr['repo']}/pulls/{pr['number']}/commits", ttl=ttl, max_pages=3):
        msg = (c.get("commit") or {}).get("message") or ""
        out.append({"repo": pr["repo"], "sha": c.get("sha"), "title": msg.splitlines()[0] if msg else "",
                    "message": msg, "date": ((c.get("commit") or {}).get("committer") or {}).get("date"),
                    "url": c.get("html_url")})
    return out


# ---------------------------------------------------------------------------------------------- costs
class Pricing:
    """Tokens -> USD. Per provider (pricing.json):
    reported  the source reports the cost itself (Claude Code / claude.ai: API list-price equivalent);
    per_model USD per million tokens by model, [input, cached input, output], from Hermes' own budget.json
              (prices_per_mtok, the table budget.py uses) or from pricing.json's fallback table;
    per_token flat USD per million tokens."""

    def __init__(self, cfg: dict, budget_path: str | None = None):
        self.cfg = cfg.get("providers", {})
        self.model_prices = dict(cfg.get("prices_per_mtok", {}))
        self.prices_source = "pricing.json"
        if budget_path and os.path.exists(os.path.expanduser(budget_path)):
            try:
                b = json.loads(Path(os.path.expanduser(budget_path)).read_text(encoding="utf-8"))
                if b.get("prices_per_mtok"):
                    self.model_prices.update(b["prices_per_mtok"])
                    self.prices_source = os.path.expanduser(budget_path)
            except (OSError, ValueError):
                pass

    def label(self, provider: str) -> str:
        return self.cfg.get(provider, {}).get("label", provider)

    def rate(self, model: str):
        m = (model or "").lower()
        if m in self.model_prices:
            return self.model_prices[m], m
        for k in sorted(self.model_prices, key=len, reverse=True):
            if k != "_default" and (k in m or m in k) and m:
                return self.model_prices[k], k
        return self.model_prices.get("_default"), "_default"

    def cost(self, provider: str, model: str, t: dict, reported: float | None) -> tuple[float, str]:
        p = self.cfg.get(provider) or self.cfg.get("other") or {}
        mode = p.get("mode", "per_token")
        if mode == "reported":
            return float(reported or 0), "koszt z Claude (cena API)"
        if mode == "per_model":
            r, key = self.rate(model)
            if not r:
                return 0.0, "brak ceny modelu"
            c = (t["input"] * r[0] + t["cache_read"] * r[1] + t["output"] * r[2] + t["cache_write"] * r[0]) / 1e6
            return c, f"cennik {key}: {r[0]}/{r[1]}/{r[2]} USD za 1M (wej./cache/wyj.)"
        if reported:
            return float(reported), "zgłoszony przez źródło"
        c = (t["input"] * p.get("input_per_mtok", 0) + t["output"] * p.get("output_per_mtok", 0)) / 1e6
        return c, ("bez opłat za tokeny" if c == 0 else "cena za token")


# ---------------------------------------------------------------------------------------------- build
def build(args) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    since = (now - dt.timedelta(days=args.days)).isoformat(timespec="seconds")
    pricing = Pricing(json.loads(Path(args.pricing).read_text(encoding="utf-8")), args.budget)

    sessions = read_hermes_sessions(hermes_dbs(args.hermes_home)) if args.hermes_home else []
    have = {x["id"]: x for x in sessions}
    for spec in args.hermes_json:
        vm, _, path = spec.partition("=") if "=" in spec else ("dev", "", spec)
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            continue
        try:
            dumped = json.loads(Path(path).read_text(encoding="utf-8"))
        except ValueError:
            print(f"warn: {path} is not JSON", file=sys.stderr)
            continue
        for x in dumped:
            x["vm"] = vm
            old = have.get(x["id"])
            if old is None or tok_sum(x["tokens"]) >= tok_sum(old["tokens"]):
                have[x["id"]] = x
    sessions = list(have.values())
    tasks, _ = read_kanban(args.kanban) if args.kanban else ({}, {})
    cruns = read_claude_runs(args.claude_runs) if args.claude_runs else []
    threads = {}
    if args.claude_threads and os.path.exists(args.claude_threads):
        threads = json.loads(Path(args.claude_threads).read_text(encoding="utf-8"))

    gh = GitHub(os.environ.get("GITHUB_TOKEN"), args.github_cache)
    prs, commits = read_github(gh, args.owner, since, args.repo) if not args.no_github else ([], [])

    # ---- steps: every unit of model work becomes a step with tokens and cost
    steps = {}

    def add_step(sid, **kw):
        kw.setdefault("tokens", tokens())
        kw["id"] = sid
        steps[sid] = kw
        return kw

    for s in sessions:
        if s["started"] and s["started"] < since:
            continue
        rows = s["usage"] or [{"model": s["model"], "provider": s["provider"], "task": "", "tokens": s["tokens"],
                               "reported_cost": s["reported_cost"]}]
        models, cost, basis = [], 0.0, []
        for u in rows:
            c, why = pricing.cost(u["provider"], u["model"], u["tokens"], u["reported_cost"])
            cost += c
            basis.append(why)
            models.append({"model": u["model"], "provider": u["provider"], "task": u["task"],
                           "tokens": u["tokens"], "cost_usd": round(c, 5)})
        main = max(rows, key=lambda u: tok_sum(u["tokens"]))
        tsum_ = tokens(*(sum(u["tokens"][k] for u in rows) for k in ("input", "output", "cache_read", "cache_write")))
        add_step(f"hs:{s['id']}", kind="hermes_session", title=s["title"] or short(s["first_user"], 80),
                 why=short(s["first_user"], 300), at=s["started"], end=s["ended"], provider=main["provider"],
                 model=", ".join(dict.fromkeys(u["model"] for u in rows if u["model"])) or s["model"],
                 tokens=tsum_ if s["usage"] else s["tokens"], fixed_cost=(cost, "; ".join(dict.fromkeys(basis))),
                 models=models,
                 where=f"Hermes {s['vm']} · profil {s['profile']} · {s['source']}",
                 meta={"source": s["source"], "parent": s["parent"], "cwd": s["cwd"], "vm": s["vm"],
                       "profile": s["profile"], "messages": s["messages"], "tool_calls": s["tool_calls"]})
    for r in cruns:
        if (r.get("ts") or "") < since:
            continue
        t = tokens(r.get("input_tokens"), r.get("output_tokens"), r.get("cache_read_tokens"),
                   r.get("cache_write_tokens") or r.get("cache_creation_tokens"))
        add_step(f"cc:{r.get('session_id') or r.get('ts')}", kind="claude_code_run",
                 title=("Sonda limitu Claude" if r.get("probe") else "Claude Code (cc_run.py)"),
                 why=(r.get("prompt_head") or r.get("purpose") or ("sprawdzenie, czy limit Claude jest dostępny"
                                                                   if r.get("probe") else "")),
                 at=iso(r.get("ts")), provider="anthropic", model=r.get("model") or "", tokens=t,
                 reported=float(r.get("cost_usd_equiv") or 0), where=f"Claude Code na {r.get('vm')} · {r.get('cwd')}",
                 meta={"task_id": r.get("task_id"), "cwd": r.get("cwd"), "probe": bool(r.get("probe")),
                       "is_error": r.get("is_error"), "hit_limit": r.get("hit_limit"), "turns": r.get("num_turns")})
    project = threads.get("project_id", "")
    for th in threads.get("threads", []):
        s = th.get("session") or {}
        u = s.get("usage") or {}
        add_step(f"ct:{th['thread_id']}", kind="claude_thread", title=th.get("title") or "",
                 why=short((th.get("first_user_message") or th.get("root") or {}).get("text", ""), 300),
                 at=th.get("created_at"), end=th.get("last_activity_at"), provider="anthropic",
                 model=(s.get("last_served_model") or s.get("model") or s.get("configured_model") or ""),
                 tokens=tokens(u.get("input_tokens"), u.get("output_tokens"), u.get("cache_read_tokens"),
                               u.get("cache_write_tokens")),
                 reported=float(u.get("cost_usd") or 0), where="Wątek w projekcie Claude",
                 link=PROJECT_URL.format(project=project, thread=th["thread_id"]),
                 meta={"session_id": th.get("session_id"), "branch": s.get("branch") or "",
                       "status": th.get("status_bucket"), "resolved": th.get("resolved")})
    coord_cost = sum(float((c.get("usage") or {}).get("cost_usd") or 0) for c in threads.get("coordinators", []))
    for c in threads.get("coordinators", []):
        u = c.get("usage") or {}
        add_step(f"co:{c.get('id')}", kind="claude_coordinator", title=c.get("title") or "Koordynator projektu",
                 why="Triaż wiadomości w czacie projektu i uruchamianie wątków", at=c.get("created_at"),
                 end=c.get("updated_at"), provider="anthropic",
                 model=c.get("last_served_model") or c.get("configured_model") or "",
                 tokens=tokens(u.get("input_tokens"), u.get("output_tokens"), u.get("cache_read_tokens"),
                               u.get("cache_write_tokens")), reported=float(u.get("cost_usd") or 0),
                 where="Koordynator projektu Claude", link=SESSION_URL.format(session=c.get("id")), meta={})

    for st in steps.values():
        fixed = st.pop("fixed_cost", None)
        st["cost_usd"], st["cost_basis"] = fixed or pricing.cost(st["provider"], st.get("model", ""), st["tokens"],
                                                                 st.pop("reported", None))
        st["provider_label"] = pricing.label(st["provider"])

    # ---- traces: one per original prompt
    traces = {}

    def trace(tid, **kw):
        if tid not in traces:
            traces[tid] = dict(id=tid, steps=[], changes=[], **kw)
        return traces[tid]

    owner_of = {}  # step id -> trace id

    # Claude threads: the thread root (Filip's message) is the prompt.
    branch_to_thread = {}
    session_to_thread = {}
    for th in threads.get("threads", []):
        root = th.get("first_user_message") or th.get("root") or {}
        t = trace(f"ct:{th['thread_id']}", origin="claude_project", title=th.get("title") or "",
                  prompt=redact(short(root.get("text", ""), 1500)),
                  author=root.get("author_name") or ("Claude (koordynator)" if root.get("author") == "agent" else ""),
                  at=root.get("sent_at") or th.get("created_at"), link=PROJECT_URL.format(project=project, thread=th["thread_id"]),
                  status=("done" if th.get("resolved") else {"completed": "done", "working": "in_progress",
                                                             "blocked": "waiting", "review_ready": "review"}.get(
                      th.get("status_bucket"), th.get("status_bucket") or "")),
                  finished=th.get("resolved_at"))
        t["steps"].append(f"ct:{th['thread_id']}")
        owner_of[f"ct:{th['thread_id']}"] = t["id"]
        b = (th.get("session") or {}).get("branch")
        if b:
            branch_to_thread[b] = t["id"]
        if th.get("session_id"):
            session_to_thread[th["session_id"]] = t["id"]
        thread_ids = th["thread_id"]
        session_to_thread[thread_ids] = t["id"]

    # Hermes: chat sessions without a parent are prompts; children follow parent_session_id.
    by_id = {s["id"]: s for s in sessions}

    def root_of(sid, depth=0):
        s = by_id.get(sid)
        if not s or not s["parent"] or depth > 20 or s["parent"] not in by_id:
            return sid
        return root_of(s["parent"], depth + 1)

    # Kanban worker sessions -> task: the run's worker_session_id, the task id in the session title or cwd,
    # else the run's profile and time window (task_runs has no session column).
    task_of_session = {}
    for tid, task in tasks.items():
        for sid in task["session_ids"]:
            task_of_session[sid] = tid
    for s in sessions:
        m = TASK_RE.search(" ".join([s["cwd"], s["title"]]))
        if m and s["id"] not in task_of_session and m.group(0) in tasks:
            task_of_session[s["id"]] = m.group(0)
    workers = defaultdict(list)
    for s in sessions:
        if s["source"] == "kanban" and s["id"] not in task_of_session and s["started"]:
            workers[s["profile"]].append(s)
    for tid, task in tasks.items():
        for run in task["runs"]:
            st, en = run.get("started_iso"), run.get("ended_iso") or run.get("started_iso")
            if not st:
                continue
            lo = (dt.datetime.fromisoformat(st) - dt.timedelta(seconds=120)).isoformat(timespec="seconds")
            for s in workers.get(run.get("profile") or task["assignee"], []):
                if s["id"] not in task_of_session and lo <= s["started"] <= en:
                    task_of_session[s["id"]] = tid

    def task_for(sid):
        return task_of_session.get(sid) or task_of_session.get(root_of(sid))

    for s in sessions:
        sid = f"hs:{s['id']}"
        if sid not in steps or task_for(s["id"]):
            continue  # kanban work is attached to its task below
        rid = root_of(s["id"])
        root = by_id[rid]
        if root["source"] == "cron":
            t = trace(f"cron:{root['title'] or 'cron'}", origin="hermes_cron",
                      title=f"Cron: {root['title'] or 'zadanie cykliczne'}",
                      prompt="Zadanie cykliczne Hermesa (cron), bez prompta od Ciebie.", author="Hermes cron",
                      at=root["started"], link=None, status="recurring", finished=None)
        elif root["source"] == "kanban":
            d = (root["started"] or "")[:10]
            t = trace(f"kbw:{d}", origin="hermes_autonomy", title=f"Sesje workerów kanban bez zadania ({d})",
                      prompt="Sesje workerów, których nie udało się przypisać do zadania kanban "
                             "(brak id zadania w tytule i brak przebiegu w tym oknie czasu).",
                      author="Hermes", at=root["started"], link=None, status="done", finished=None)
        else:
            t = trace(f"hs:{rid}", origin="hermes_chat",
                      title=root["title"] or short(root["first_user"], 80) or rid,
                      prompt=root["first_user"], author=("Filip" if root["source"] in CHAT_SOURCES else root["source"]),
                      at=root["started"], link=None, status=("done" if root["ended"] else "in_progress"),
                      finished=root["ended"], where=f"Hermes {root['vm']} · {root['source']}")
        if rid != s["id"]:
            steps[sid]["parent_step"] = f"hs:{rid}"
        t["steps"].append(sid)
        owner_of[sid] = t["id"]

    task_sessions = defaultdict(list)
    for s in sessions:
        tid = task_for(s["id"])
        if tid and f"hs:{s['id']}" in steps:
            task_sessions[tid].append(s)

    # Kanban tasks, oldest first: under the trace of the Hermes session that created them (tasks.session_id),
    # else a trace of their own (Filip's task, or autonomy: planner, watchdog, CI doctor...).
    FILIP = {"filip", "filip-via-hermes", "user"}
    for tid, task in sorted(tasks.items(), key=lambda kv: kv[1]["created"] or ""):
        if task["created"] and task["created"] < since:
            continue
        creator = task["created_by"]
        parent_trace = owner_of.get(f"hs:{task['origin_session']}") if task["origin_session"] else None
        if parent_trace is None:
            label = {"planner": "Autonomia (planner)", "filip": "Filip", "filip-via-hermes": "Filip przez Hermesa",
                     "gh-actions-watchdog": "CI watchdog", "ci-doctor": "CI doctor",
                     "auto-decomposer": "Auto-dekompozycja"}.get(creator, creator or "?")
            t = trace(f"kb:{tid}", origin=("kanban" if creator in FILIP else "hermes_autonomy"), title=task["title"],
                      prompt=task["body"] or task["title"], author=label, at=task["created"], link=None,
                      status={"done": "done", "archived": "done", "blocked": "waiting"}.get(task["status"], task["status"]),
                      finished=task["completed"])
        else:
            t = traces[parent_trace]
        kid = f"kb:{tid}"
        steps[kid] = dict(id=kid, kind="kanban_task", title=f"{tid} · {task['title']}", why=short(task["body"], 300),
                          at=task["created"], end=task["completed"], provider="none", provider_label="—",
                          model="", tokens=tokens(), cost_usd=0.0, cost_basis="",
                          where=f"Kanban · {task['assignee']} · utworzył {creator}",
                          meta={"status": task["status"], "assignee": task["assignee"], "branch": task["branch"],
                                "result": task["result"], "runs": len(task["runs"])})
        if parent_trace and task["origin_session"]:
            steps[kid]["parent_step"] = f"hs:{task['origin_session']}"
        t["steps"].append(kid)
        owner_of[kid] = t["id"]
        for s in task_sessions.get(tid, []):
            sid = f"hs:{s['id']}"
            if sid not in owner_of:
                steps[sid]["parent_step"] = kid
                t["steps"].append(sid)
                owner_of[sid] = t["id"]

    # Claude Code runs: by task_id, else by the task id in their cwd, else a "Claude Code" trace per day.
    for r in cruns:
        sid = f"cc:{r.get('session_id') or r.get('ts')}"
        if sid not in steps:
            continue
        m = TASK_RE.search(r.get("cwd") or "")
        tid = r.get("task_id") or (m.group(0) if m else None)
        if tid and f"kb:{tid}" in owner_of:
            steps[sid]["parent_step"] = f"kb:{tid}"
            traces[owner_of[f"kb:{tid}"]]["steps"].append(sid)
            owner_of[sid] = owner_of[f"kb:{tid}"]
            continue
        day = (iso(r.get("ts")) or "")[:10]
        if r.get("probe"):
            t = trace(f"probe:{day[:7]}", origin="hermes_autonomy", title=f"Sondy limitu Claude ({day[:7]})",
                      prompt="Automatyczne sprawdzanie, czy limit Claude się odnowił (quota governor).",
                      author="Hermes", at=day, link=None, status="recurring", finished=None)
        else:
            t = trace(f"ccday:{day}", origin="hermes_autonomy", title=f"Claude Code bez zadania kanban ({day})",
                      prompt="Uruchomienia cc_run.py, których nie da się przypisać do zadania.", author="Hermes",
                      at=day, link=None, status="done", finished=None)
        t["steps"].append(sid)
        owner_of[sid] = t["id"]

    # Coordinator sessions: shared overhead, its own trace.
    for c in threads.get("coordinators", []):
        sid = f"co:{c.get('id')}"
        t = trace("coordinator", origin="claude_project", title="Koordynacja projektu Claude (narzut wspólny)",
                  prompt="Sesje, które czytają czat projektu, odpowiadają na krótkie pytania i zakładają wątki. "
                         "To koszt wspólny dla wszystkich wątków.", author="Claude", at=c.get("created_at"),
                  link=None, status="recurring", finished=None)
        t["steps"].append(sid)
        owner_of[sid] = "coordinator"

    # ---- changes: PRs and commits tied to a trace
    def trace_for_text(text: str, what: str) -> tuple[str | None, str | None]:
        for m in THREAD_RE.findall(text or ""):
            if f"ct:{m}" in traces:
                return f"ct:{m}", f"link do wątku w {what}"
        for m in SESSION_RE.findall(text or ""):
            if m in session_to_thread:
                return session_to_thread[m], f"Claude-Session w {what}"
        for m in TASK_RE.findall(text or ""):
            if f"kb:{m}" in owner_of:
                return owner_of[f"kb:{m}"], f"id zadania {m} w {what}"
        return None, None

    seen_sha = set()
    for pr in prs:
        tid = branch_to_thread.get(pr["head"])
        via = "gałąź wątku" if tid else None
        if not tid:
            m = TASK_RE.search(pr["head"])
            if m and f"kb:{m.group(0)}" in owner_of:
                tid, via = owner_of[f"kb:{m.group(0)}"], "gałąź zadania kanban"
        if not tid:
            tid, via = trace_for_text(pr["title"] + "\n" + pr["body"], "opisie PR")
        if not tid:
            continue
        ch = {"kind": "pr", "repo": pr["repo"], "number": pr["number"], "title": pr["title"], "state": pr["state"],
              "draft": pr["draft"], "at": pr["created"], "merged": pr["merged"], "closed": pr["closed"],
              "url": pr["url"], "via": via, "commits": []}
        if not args.no_github:
            for c in pr_commits(gh, pr):
                seen_sha.add(c["sha"])
                ch["commits"].append({"sha": c["sha"][:7], "title": c["title"], "at": c["date"], "url": c["url"]})
        traces[tid]["changes"].append(ch)
    for c in commits:
        if c["sha"] in seen_sha:
            continue
        tid, via = trace_for_text(c["message"], "commicie")
        if not tid:
            continue
        traces[tid]["changes"].append({"kind": "commit", "repo": c["repo"], "sha": c["sha"][:7], "title": c["title"],
                                       "at": c["date"], "url": c["url"], "via": via})

    # ---- totals and finish state
    def parts(st):
        """A step's spend split by provider: a Hermes session can use several models (main + auxiliary)."""
        if st["provider"] == "none":
            return []
        if st.get("models"):
            return [m for m in st["models"] if m["provider"] != "none"]
        return [st]

    for t in traces.values():
        t["steps"] = sorted(dict.fromkeys(t["steps"]), key=lambda s: steps[s].get("at") or "")
        by_p = defaultdict(lambda: {"cost_usd": 0.0, "tokens": 0, "label": ""})
        for sid in t["steps"]:
            for part in parts(steps[sid]):
                by_p[part["provider"]]["cost_usd"] += part["cost_usd"]
                by_p[part["provider"]]["tokens"] += tok_sum(part["tokens"])
                by_p[part["provider"]]["label"] = pricing.label(part["provider"])
        t["by_provider"] = dict(by_p)
        t["cost_usd"] = round(sum(v["cost_usd"] for v in by_p.values()), 4)
        t["tokens"] = sum(v["tokens"] for v in by_p.values())
        t["changes"].sort(key=lambda c: c.get("at") or "")
        prs_ = [c for c in t["changes"] if c["kind"] == "pr"]
        t["result"] = {
            "prs": len(prs_), "merged": sum(1 for c in prs_ if c["state"] == "merged"),
            "open": sum(1 for c in prs_ if c["state"] == "open"),
            "commits": sum(len(c.get("commits", [])) for c in prs_) + sum(1 for c in t["changes"] if c["kind"] == "commit"),
        }
        merged = [c["merged"] for c in prs_ if c.get("merged")]
        if not t.get("finished") and merged and not t["result"]["open"]:
            t["finished"] = max(merged)
        t["last_activity"] = max([steps[s].get("end") or steps[s].get("at") or "" for s in t["steps"]] +
                                 [c.get("merged") or c.get("at") or "" for c in t["changes"]] + [t.get("at") or ""])

    gh.save()
    totals = defaultdict(lambda: {"cost_usd": 0.0, "tokens": 0, "label": ""})
    for st in steps.values():
        for part in parts(st):
            totals[part["provider"]]["cost_usd"] += part["cost_usd"]
            totals[part["provider"]]["tokens"] += tok_sum(part["tokens"])
            totals[part["provider"]]["label"] = pricing.label(part["provider"])
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "window_days": args.days,
        "sources": {"hermes_sessions": len(sessions), "kanban_tasks": len(tasks), "claude_code_runs": len(cruns),
                    "claude_threads": len(threads.get("threads", [])),
                    "claude_threads_exported_at": threads.get("exported_at"), "pull_requests": len(prs),
                    "commits_scanned": len(commits), "github_calls": gh.calls},
        "pricing": pricing.cfg, "model_prices": pricing.model_prices, "model_prices_source": pricing.prices_source,
        "totals": dict(totals),
        "coordinator_cost_usd": round(coord_cost, 4),
        "traces": sorted(traces.values(), key=lambda t: t.get("last_activity") or "", reverse=True),
        "steps": steps,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hermes-home", action="append", default=[],
                    help="Hermes home to read, as vm=path (repeatable), e.g. prod=~/.hermes dev=/var/tmp/dev-hermes")
    ap.add_argument("--hermes-json", action="append", default=[],
                    help="sessions dumped on another VM with --dump-hermes, as vm=path (repeatable)")
    ap.add_argument("--dump-hermes", action="store_true",
                    help="print the sessions of --hermes-home as JSON and exit (run this on another VM over SSH)")
    ap.add_argument("--kanban", action="append", default=[], help="kanban db as vm=path (repeatable, later wins)")
    ap.add_argument("--claude-runs", action="append", default=[], help="claude_runs.jsonl as vm=path (repeatable)")
    ap.add_argument("--claude-threads", help="claude_threads.json exported from the Claude project")
    ap.add_argument("--pricing", default=str(Path(__file__).with_name("pricing.json")))
    ap.add_argument("--budget", default="~/.hermes/autonomy/budget.json",
                    help="Hermes budget.json whose prices_per_mtok prices the Ollama models")
    ap.add_argument("--owner", default="ScuraUrsa")
    ap.add_argument("--repo", action="append", default=[],
                    help="only these repositories (owner/name or name; repeatable); default: every repo of --owner")
    ap.add_argument("--days", type=int, default=120, help="only work newer than this many days")
    ap.add_argument("--github-cache", default=os.path.expanduser("~/.cache/trace-dashboard-github.json"))
    ap.add_argument("--no-github", action="store_true")
    ap.add_argument("--out", help="where to write trace.json")
    args = ap.parse_args(argv)
    if args.dump_hermes:
        json.dump(read_hermes_sessions(hermes_dbs(args.hermes_home)), sys.stdout, ensure_ascii=False)
        return 0
    if not args.out:
        ap.error("--out is required")
    os.makedirs(os.path.dirname(os.path.abspath(args.github_cache)), exist_ok=True)
    data = build(args)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"), default=list)
    os.replace(tmp, args.out)
    s = data["sources"]
    print(f"trace.json: {len(data['traces'])} traces, {len(data['steps'])} steps; sources {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
