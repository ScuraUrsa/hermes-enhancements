"""PC runner for the Hermes digest queue (Windows task "Hermes digest queue", every 10 min).

Takes the oldest job from prod's ~/.hermes/digest-queue/new (written by Hermes' digest_request.py), moves it
to running/, runs digest.py --notify, writes the result to done/<job>.json on prod. One job per run; the
task does not start a second copy while one is busy.

Also, once a day, checks that Claude Code on the dev VM is logged in (2026-10-23..11-06 it was logged out for
two weeks and nobody noticed): if not, it pushes a notification with the one-line login command.

  python digest_queue.py [--once-health]
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
PY = str(HERE / "venv" / "Scripts" / "python.exe")
KEY = r"D:\hermes\terraforge-stacks\local\generated\id_rsa"
PROD, DEV = "ubuntu@192.168.56.107", "ubuntu@192.168.56.108"
Q = "~/.hermes/digest-queue"
STATE = Path(r"D:\courses\youtube\queue_state.json")
LOGIN_CMD = ('ssh -t -i D:\\hermes\\terraforge-stacks\\local\\generated\\id_rsa ubuntu@192.168.56.108 '
             '"CLAUDE_CONFIG_DIR=~/.claude-code claude"  (then /login)')


def log(msg: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def ssh(host: str, cmd: str, timeout: int = 120, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["ssh", "-o", "ConnectTimeout=10", "-i", KEY, host, cmd], input=stdin, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def health(state: dict) -> None:
    today = time.strftime("%Y-%m-%d")
    if state.get("health_day") == today:
        return
    try:
        r = ssh(DEV, "CLAUDE_CONFIG_DIR=~/.claude-code timeout 90 claude -p 'say ok' 2>&1 | tail -1", timeout=150)
    except subprocess.TimeoutExpired:
        return
    if r.returncode == 255:  # dev asleep: try again next run
        return
    state["health_day"] = today
    out = r.stdout.strip()
    log(f"dev claude check: {out[:100]}")
    if "ok" not in out.lower():
        msg = f"Claude Code na dev VM nie działa ({out[:80]}). Zaloguj: {LOGIN_CMD}"
        py = ("import sys; sys.path.insert(0, '/home/ubuntu/.hermes/scripts/timeplane'); import tp_push; "
              f"tp_push.send('⚠️ Claude na dev wylogowany', {msg!r}, tag='dev-claude', min_gap=720)")
        ssh(PROD, f"cd ~/.hermes/scripts/timeplane && ~/.hermes/hermes-agent/venv/bin/python -c {json.dumps(py)}")


def main() -> int:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {}
    health(state)
    STATE.write_text(json.dumps(state), encoding="utf-8")
    if "--once-health" in sys.argv:
        return 0
    r = ssh(PROD, f"mkdir -p {Q}/new {Q}/running {Q}/done && ls {Q}/new/*.json 2>/dev/null | head -1")
    path = r.stdout.strip()
    if not path:
        return 0
    name = path.rsplit("/", 1)[-1]
    job = json.loads(ssh(PROD, f"cat {path}").stdout)
    ssh(PROD, f"mv {path} {Q}/running/{name}")
    log(f"job {job['job']}: {job['urls']} ({job['model']})")
    cmd = [PY, "-u", str(HERE / "digest.py"), *job["urls"], "--model", job["model"], "--max", str(job.get("max", 50)),
           "--notify", "--job", job["job"]]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=HERE)
    for line in p.stderr.strip().splitlines()[-15:]:
        log("  " + line[:200])
    try:
        result = json.loads(p.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        result = {"state": "error", "error": (p.stderr or "")[-500:]}
    job.update(state=result.get("state"), result=result, finished=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    if result.get("state") == "dev-unreachable":  # back to the queue, next run tries again
        ssh(PROD, f"cat > {Q}/new/{name} && rm -f {Q}/running/{name}", stdin=json.dumps(job, ensure_ascii=False, indent=1))
    else:
        ssh(PROD, f"cat > {Q}/done/{name} && rm -f {Q}/running/{name}", stdin=json.dumps(job, ensure_ascii=False, indent=1))
    log(f"job {job['job']}: {job['state']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
