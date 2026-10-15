"""On the VM: is the course report rebuild alive, and how far is it? Standard library only.

  python3 status.py [site] [--watch SEC] [--log PATH]
From the PC, without copying anything to the VM: double-click status.cmd, or in Git Bash
  ssh -i /d/hermes/terraforge-stacks/local/generated/id_rsa ubuntu@192.168.56.108 "python3 - --watch 60" < status.py

Shows: whether regen_reports.py runs (and its cron line, if scheduled), lessons per course with
a v2 report / waiting / without a new transcript, the rebuild speed over the last 24 h, the log
tail, and whether the last failure was the Claude usage limit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.home() / ".hermes" / "sitedigest"
LIMIT_RE = re.compile(r"limit|usage|quota|429|rate", re.I)


def processes(pattern: str) -> list[tuple[int, str, float]]:
    """(pid, command line, start epoch) of processes whose command line contains pattern."""
    out = []
    boot = time.time() - float(Path("/proc/uptime").read_text().split()[0])
    hz = os.sysconf("SC_CLK_TCK")
    for d in Path("/proc").iterdir():
        if not d.name.isdigit() or int(d.name) == os.getpid():
            continue
        try:
            cmd = (d / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
            if pattern in cmd and "status.py" not in cmd:
                start = boot + int((d / "stat").read_text().rsplit(")", 1)[1].split()[19]) / hz
                out.append((int(d.name), cmd, start))
        except OSError:
            continue
    return out


def cron_lines(pattern: str) -> list[str]:
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line for line in r.stdout.splitlines() if pattern in line and not line.lstrip().startswith("#")]


def ago(ts: float) -> str:
    s = int(time.time() - ts)
    if s < 120:
        return f"{s} s ago"
    if s < 7200:
        return f"{s // 60} min ago"
    if s < 172800:
        return f"{s // 3600} h ago"
    return f"{s // 86400} days ago"


def find_log(site_dir: Path, given: str | None) -> Path | None:
    cands = [Path(given)] if given else [site_dir / "regen.log", Path.home() / "regen.log", ROOT / "regen.log",
                                         *sorted(site_dir.glob("*regen*.log")), *sorted(Path.home().glob("*regen*.log"))]
    found = [p for p in cands if p.is_file()]
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def ready(pdir: Path, rec: dict) -> bool:
    """Same rule as regen_reports.ready: every local video has a re-transcribed (.asr2) VTT."""
    locs = [v[len("local:"):] for v in rec.get("videos") or [] if v.startswith("local:")]
    return bool(locs) and all(list((pdir / Path(v).parent).glob("*.vtt.asr2")) for v in locs)


def course_of(rec: dict) -> str:
    return (rec.get("course_url") or "?").rstrip("/").rsplit("/", 1)[-1]


def snapshot(site: str, log_arg: str | None) -> str:
    site_dir = ROOT / site
    lines = [f"Course report rebuild (v2)   {site}   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
    up = float(Path("/proc/uptime").read_text().split()[0])
    lines.append(f"VM up {int(up // 3600)} h {int(up % 3600 // 60)} min (since {datetime.fromtimestamp(time.time() - up):%d.%m %H:%M})")

    procs = processes("regen_reports.py")
    if procs:
        for pid, cmd, start in procs:
            lines.append(f"RUNNING  pid {pid}, started {datetime.fromtimestamp(start):%d.%m %H:%M} ({ago(start)})")
            lines.append(f"         {cmd[:150]}")
    else:
        lines.append("NOT RUNNING  (no regen_reports.py process)")
    for c in cron_lines("regen_reports"):
        lines.append(f"scheduled: {c[:150]}")
    lines.append("")

    try:
        pages = json.loads((site_dir / "map.json").read_text(encoding="utf-8"))["pages"]
    except (OSError, ValueError, KeyError) as exc:
        return "\n".join(lines + [f"cannot read {site_dir / 'map.json'}: {exc}"])
    per: dict[str, Counter] = {}
    done_times = []
    for rec in pages:
        if (rec.get("digest") or {}).get("status") not in ("done", "partial"):
            continue
        pdir = site_dir / "pages" / rec["key"]
        c = per.setdefault(course_of(rec), Counter())
        c["lessons"] += 1
        mark = pdir / "report.v2.done"
        if mark.is_file():
            c["v2"] += 1
            done_times.append(mark.stat().st_mtime)
        elif ready(pdir, rec):
            c["waiting"] += 1
        else:
            c["no_transcript"] += 1
    w = max([len(k) for k in per] + [6])
    lines.append(f"{'course':<{w}}  lessons  v2 done  waiting  no new transcript")
    tot = Counter()
    for k, c in sorted(per.items()):
        tot.update(c)
        lines.append(f"{k:<{w}}  {c['lessons']:7}  {c['v2']:7}  {c['waiting']:7}  {c['no_transcript']:7}")
    lines.append(f"{'total':<{w}}  {tot['lessons']:7}  {tot['v2']:7}  {tot['waiting']:7}  {tot['no_transcript']:7}")
    pct = 100 * tot["v2"] / max(tot["lessons"], 1)
    lines.append(f"[{'#' * int(pct // 4):<25}] {pct:.0f} %")
    last_day = [t for t in done_times if t > time.time() - 86400]
    if done_times:
        lines.append(f"last v2 report {ago(max(done_times))}; {len(last_day)} in the last 24 h"
                     + (f", at that pace about {tot['waiting'] / len(last_day):.1f} more days" if last_day and tot["waiting"] else ""))
    lines.append("")

    log = find_log(site_dir, log_arg)
    if not log:
        lines.append("log: not found (pass --log PATH)")
        return "\n".join(lines)
    text = log.read_text(encoding="utf-8", errors="replace").splitlines()
    ok = sum(" v2 " in t for t in text)
    fails = [t for t in text if " FAIL " in t]
    lines.append(f"log {log} (written {ago(log.stat().st_mtime)}): {ok} v2, {len(fails)} FAIL")
    if fails and LIMIT_RE.search(fails[-1]) and (not text or " FAIL " in text[-1] or "finished" in text[-1]):
        m = re.search(r"resets? [^\"',)]{3,40}", fails[-1])
        lines.append(f"!! last failure is the Claude usage limit{(': ' + m.group(0)) if m else ''}")
    lines += ["", "last lines:"] + [f"  {t[:160]}" for t in text[-8:]]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("site", nargs="?", default="akademiasaas-pl")
    ap.add_argument("--watch", type=int, default=0, metavar="SEC", help="refresh every SEC seconds")
    ap.add_argument("--log")
    a = ap.parse_args()
    while True:
        out = snapshot(a.site, a.log)
        if not a.watch:
            print(out)
            return 0
        print("\033[2J\033[H" + out + f"\n\nrefresh every {a.watch} s, Ctrl+C to quit", flush=True)
        try:
            time.sleep(a.watch)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
