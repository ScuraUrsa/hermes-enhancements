"""hbench command line.

hbench list                              tasks and their categories
hbench doctor                            which frameworks / providers are usable here
hbench validate [-t PATTERN]             oracle must pass, no-op must fail, per task
hbench run -a AGENT -p PROVIDER -m MODEL [-t PATTERN] [-n REPEATS]
hbench matrix matrix.toml                run a full framework x provider x model grid
hbench report results/*.jsonl            Markdown leaderboard
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

from . import report, runner
from .agents import AGENTS
from .providers import load_providers
from .tasks import load_tasks, select

ROOT = Path(__file__).resolve().parent.parent


def _tasks(args):
    return select(load_tasks(Path(args.tasks_dir)), args.task)


def cmd_list(args) -> int:
    for t in _tasks(args):
        print(f"{t.id:40} {t.category:9} {t.difficulty:7} {t.visibility:8} {t.repo}@{t.fix_commit[:8]}")
    return 0


def cmd_doctor(args) -> int:
    for name, cls in AGENTS.items():
        if cls.binary:
            path = shutil.which(cls.binary)
            print(f"framework {name:12} {'OK ' + path if path else 'missing (' + cls.binary + ')'}")
    for name, p in load_providers(Path(args.providers)).items():
        status = "configured"
        if p.api_key_env and not p.api_key:
            status = f"missing ${p.api_key_env}"
        if p.kind == "ollama" and p.local:
            try:
                with urllib.request.urlopen(f"{p.base_url}/api/tags", timeout=3) as r:
                    models = [m["name"] for m in json.load(r).get("models", [])]
                status = f"reachable, models: {', '.join(models) or '(none pulled)'}"
            except OSError as e:
                status = f"unreachable ({e})"
        print(f"provider  {name:12} {p.kind:9} {status}")
    print(f"HBENCH_REPOS={os.environ.get('HBENCH_REPOS', '(unset: repos are cloned from GitHub)')}")
    return 0


def cmd_validate(args) -> int:
    out = Path(args.out)
    bad = 0
    for t in _tasks(args):
        o = runner.run_attempt(t, "oracle", runner.NO_PROVIDER, "-", out, keep_workspace=args.keep)
        n = runner.run_attempt(t, "noop", runner.NO_PROVIDER, "-", out, keep_workspace=args.keep)
        ok = o.get("solved") is True and n.get("solved") is False
        bad += not ok
        print(
            f"{'OK ' if ok else 'BAD'} {t.id:40} oracle={o.get('solved')} noop={n.get('solved')} "
            f"{o.get('error') or n.get('error') or ''}"
        )
        if not ok:
            print(f"    see {o['outdir']} and {n['outdir']}")
    return 1 if bad else 0


def cmd_run(args) -> int:
    providers = load_providers(Path(args.providers))
    provider = runner.NO_PROVIDER if args.agent in ("oracle", "noop") else providers[args.provider]
    options = json.loads(args.options) if args.options else {}
    results = Path(args.out) / "adhoc.jsonl"
    for t in _tasks(args):
        for i in range(args.repeats):
            rec = runner.run_attempt(
                t, args.agent, provider, args.model, Path(args.out), options, keep_workspace=args.keep
            )
            rec["repeat"] = i
            runner.append_jsonl(results, rec)
            print(
                f"{t.id:40} solved={rec.get('solved')} {rec.get('duration_sec', '-')}s "
                f"{rec.get('error', '')}  -> {rec['outdir']}"
            )
    return 0


def cmd_matrix(args) -> int:
    path = runner.run_matrix(
        Path(args.matrix), load_tasks(Path(args.tasks_dir)), load_providers(Path(args.providers)), Path(args.out)
    )
    print(f"results: {path}")
    print(report.markdown(report.load([path])))
    return 0


def cmd_report(args) -> int:
    rows = report.load([Path(p) for p in args.files])
    print(json.dumps(report.leaderboard(rows), indent=2) if args.json else report.markdown(rows))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="hbench", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--tasks-dir", default=str(ROOT / "tasks"))
    ap.add_argument("--providers", default=str(ROOT / "providers.toml"))
    ap.add_argument("--out", default=str(ROOT / "results"))
    sub = ap.add_subparsers(required=True)

    def task_arg(p):
        p.add_argument("-t", "--task", action="append", help="id glob or tag:NAME (repeatable)")

    p = sub.add_parser("list")
    task_arg(p)
    p.set_defaults(func=cmd_list)
    p = sub.add_parser("doctor")
    p.set_defaults(func=cmd_doctor)
    p = sub.add_parser("validate")
    task_arg(p)
    p.add_argument("--keep", action="store_true", help="keep workspaces for inspection")
    p.set_defaults(func=cmd_validate)
    p = sub.add_parser("run")
    task_arg(p)
    p.add_argument("-a", "--agent", required=True, choices=sorted(AGENTS))
    p.add_argument("-p", "--provider", default="none")
    p.add_argument("-m", "--model", default="-")
    p.add_argument("-n", "--repeats", type=int, default=1)
    p.add_argument("-o", "--options", help='JSON, e.g. {"max_turns": 60, "timeout": 900}')
    p.add_argument("--keep", action="store_true")
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("matrix")
    p.add_argument("matrix")
    p.set_defaults(func=cmd_matrix)
    p = sub.add_parser("report")
    p.add_argument("files", nargs="+")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_report)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
