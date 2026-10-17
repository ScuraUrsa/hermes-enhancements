"""Status of the slow v2 report rebuild (regen_reports.py via run_regen.sh). Runs on the dev VM.

  python3 regen_status.py            one screen
  python3 regen_status.py --watch    refresh every 30 s (Ctrl+C to quit)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SITE = Path.home() / ".hermes/sitedigest/akademiasaas-pl"
CAP = 300


def ago(ts: float) -> str:
    s = int(time.time() - ts)
    return f"{s // 3600} h {s % 3600 // 60} min" if s >= 3600 else f"{s // 60} min {s % 60} s"


def screen() -> str:
    out = []
    now = datetime.now(timezone.utc)
    pid = subprocess.run(["pgrep", "-f", "regen_reports.py akademiasaas-pl"], capture_output=True, text=True).stdout.split()
    log = (SITE / "regen.log").read_text(encoding="utf-8", errors="replace").splitlines() if (SITE / "regen.log").is_file() else []
    m = json.loads((SITE / "map.json").read_text(encoding="utf-8"))
    # the map can list a lesson twice under one key: count each lesson once
    by_key = {p["key"]: p for p in m["pages"] if (p.get("digest") or {}).get("status") in ("done", "partial")}
    # lessons without a video of their own keep their v1 report (nothing to regenerate)
    pages = [p for p in by_key.values() if any(v.startswith("local:") for v in p.get("videos") or [])]

    out.append(f"v2 REPORT REBUILD   {now:%Y-%m-%d %H:%M:%S} UTC   (dev VM {os.uname().nodename})")
    out.append("=" * 72)
    if (SITE / "regen.finished").is_file():
        out.append("STATE     FINISHED " + (SITE / "regen.finished").read_text().strip())
    elif pid:
        out.append(f"STATE     RUNNING (pid {', '.join(pid)})")
    else:
        out.append("STATE     NOT RUNNING right now (cron starts it again within 20 min)")

    # what it is doing: a lesson started after the last finished line, or a limit wait
    last_ok = next((l for l in reversed(log) if " v2 " in l), None)
    last_fail = next((l for l in reversed(log) if " FAIL " in l), None)
    v2_files = sorted((SITE / "pages").glob("*/report.v2.done"), key=lambda f: f.stat().st_mtime)
    cur_f = SITE / "regen.current"
    if pid:
        if cur_f.is_file():
            cur = json.loads(cur_f.read_text(encoding="utf-8"))
            out.append(f"NOW       {(cur.get('title') or cur['key'])[:55]}  ({(cur.get('course') or '')[:28]}), for {ago(cur['started'])}")
        if last_fail and log and log[-1] == last_fail and not log[-1].startswith("===") and "limit" in last_fail.lower():
            out.append("NOW       waiting for the Claude limit to reset: " + last_fail.split(": ", 2)[-1][:80])
        elif not cur_f.is_file() and v2_files and time.time() - v2_files[-1].stat().st_mtime < 70:
            out.append("NOW       1-minute pause between lessons")
    out.append("")

    out.append(f"{'COURSE':34s} {'v2 done':>8s} {'total':>6s} {'in Notion v2':>13s}")
    for course in sorted({p.get("course", "") for p in pages}):
        ps = [p for p in pages if p.get("course") == course]
        done = sum(1 for p in ps if (SITE / "pages" / p["key"] / "report.v2.done").is_file())
        notion = sum(1 for p in ps if p["digest"].get("notion_url_v1") and p["digest"].get("notion_url"))
        bar = "#" * round(20 * done / len(ps)) + "." * (20 - round(20 * done / len(ps)))
        out.append(f"{course[:34]:34s} {done:8d} {len(ps):6d} {notion:13d}   [{bar}]")
    total = len(pages)
    done_all = len(v2_files)
    today = sum(1 for f in v2_files if datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).date() == now.date())
    out.append("")
    out.append(f"TODAY     {today}/{CAP} lessons (daily cap; resets 00:00 UTC)")
    recent = [t for t in (f.stat().st_mtime for f in v2_files[-10:]) if time.time() - t < 12 * 3600]
    if len(recent) >= 2:
        per = (recent[-1] - recent[0]) / (len(recent) - 1)
        left = total - done_all
        days = max(left / CAP, left * per / 86400)
        out.append(f"PACE      last 10 lessons: one every {per / 60:.1f} min;  left: {left};  ETA ~{days:.1f} days (if the VM stays awake)")
    if v2_files:
        out.append(f"LAST DONE {ago(v2_files[-1].stat().st_mtime)} ago: {by_key.get(v2_files[-1].parent.name, {}).get('title', '?')[:55]}")
    start = max((i for i, l in enumerate(log) if l.startswith("===")), default=0)  # current run
    run_fails = [l for l in log[start:] if " FAIL " in l]
    out.append(f"ERRORS    {len(run_fails)} since this run started" + (f"; last: {run_fails[-1][:100]}" if run_fails else ""))
    out.append("")
    out.append("LOG (last 6)")
    out += ["  " + l[:110] for l in log[-6:]]
    return "\n".join(out)


def main() -> None:
    if "--watch" in sys.argv:
        try:
            while True:
                s = screen()
                print("\033[2J\033[H" + s + "\n\n(refresh every 30 s, Ctrl+C to quit)", flush=True)
                time.sleep(30)
        except KeyboardInterrupt:
            pass
    else:
        print(screen())


if __name__ == "__main__":
    main()
