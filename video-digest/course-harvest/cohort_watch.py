"""Follow the ODDF: AI SaaS cohort (Akademia SaaS, from 2026-10-19) on the PC. Run by the Windows task
"Hermes cohort watch" twice a day (Filip, 2026-10-20: "zleć transkrypcje i opracowanie tego szkolenia
również i zaplanuj śledzenie na żywo warsztatów").

Each run:
  1. reads the community calendar and the cohort channels (announcements, LIVE workshops, workshop work,
     homework, questions) with the harvester's logged-in Chrome profile; new posts go to
     D:/courses/akademiasaas-pl/cohort/posts.md, the raw pages to cohort/pages/;
  2. every new upcoming event becomes a timeplane task for Filip (date, time, link), so he joins live;
  3. remaps the library (new cohort course, new recordings in "Nagrania LIVE"), downloads what is new,
     transcribes it on the GPU, syncs it to the dev VM and makes sure the Sonnet pool runs (one
     pipeline_loop.sh pass);
  4. sends lessons that are digested but not yet in Notion to "Kursy: lekcje".
State: cohort/state.json. Log: D:/courses/cohort-watch.log.

  python cohort_watch.py [--no-pipeline] [--no-notion] [--no-tasks]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).parent
SITE = Path(r"D:\courses\akademiasaas-pl")
OUT = SITE / "cohort"
PY = str(HERE / "venv" / "Scripts" / "python.exe")
BASH = r"D:\Git\bin\bash.exe"
KEY = r"D:\hermes\terraforge-stacks\local\generated\id_rsa"
PROD, DEV = "ubuntu@192.168.56.107", "ubuntu@192.168.56.108"
COMMUNITY = "https://akademiasaas.pl/app/community/spolecznosc"
CHANNELS = {  # name -> channel id (community "ODDF: AI SaaS" section + announcements)
    "Ogłoszenia": "cd7d9d27-c879-4084-8134-7f7c5915038e",
    "Warsztaty LIVE": "51327d8b-eb1e-4e6f-9212-ec4f89768565",
    "Prace z warsztatów": "6c9b02f4-c0b5-4916-9722-e838ca43d006",
    "Prace domowe": "c4b5fc50-9156-4e7f-bf40-a5125118fb85",
    "LIVE-y i spotkania": "d5d6e122-9040-4390-a1f2-e7845465989f",
}
MONTHS = {"sty": 1, "lut": 2, "mar": 3, "kwi": 4, "maj": 5, "cze": 6, "lip": 7, "sie": 8, "wrz": 9, "paź": 10,
          "lis": 11, "gru": 12}
THREAD = "Hermes_local: YouTube/course digest (kohorta ODDF: AI SaaS)"


def log(msg: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def run(cmd: list[str], timeout: int = 7200, **kw) -> str:
    log("$ " + " ".join(cmd)[:160])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, **kw)
    tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
    for line in tail:
        log("  " + line[:200])
    return r.stdout


def running(pattern: str) -> bool:
    """Is another process with this in its command line alive (e.g. the long transcriber or pipeline loop)?"""
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -match '%s' }"
          " | Measure-Object | Select-Object -ExpandProperty Count") % pattern
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=120)
    return r.stdout.strip() not in ("", "0")


def body_text(page) -> str:
    return page.evaluate("() => (document.querySelector('main') || document.body).innerText")


def scrape() -> dict:
    sys.path.insert(0, str(HERE))
    from playwright.sync_api import sync_playwright

    from harvest_zanfia import open_browser

    res = {"calendar": "", "channels": {}}
    with sync_playwright() as pw:
        ctx = open_browser(pw)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(f"{COMMUNITY}?tab=calendar", wait_until="domcontentloaded")
        page.wait_for_timeout(8000)
        res["calendar"] = body_text(page)
        for name, cid in CHANNELS.items():
            page.goto(f"{COMMUNITY}/{cid}", wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            res["channels"][name] = body_text(page)
        ctx.close()
    return res


def upcoming_events(calendar: str) -> list[dict]:
    """Events listed under NADCHODZĄCE: '<day> <month>' / title / 'HH:MM – HH:MM'."""
    m = re.search(r"NADCHODZĄCE\s*(.*?)\s*MINIONE WYDARZENIA", calendar, re.S)
    if not m:
        return []
    lines = [l.strip() for l in m.group(1).splitlines() if l.strip()]
    events, i = [], 0
    today = date.today()
    while i < len(lines):
        d = re.fullmatch(r"(\d{1,2}) (\w{3})\w*", lines[i])
        if d and d.group(2).lower() in MONTHS and i + 1 < len(lines):
            title = lines[i + 1]
            t = re.search(r"(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})", lines[i + 2]) if i + 2 < len(lines) else None
            month = MONTHS[d.group(2).lower()]
            year = today.year + (1 if month < today.month - 6 else 0)
            events.append({"date": f"{year}-{month:02d}-{int(d.group(1)):02d}", "title": title,
                           "start": t.group(1) if t else "", "end": t.group(2) if t else ""})
            i += 3 if t else 2
        else:
            i += 1
    return events


def channel_posts(text: str, name: str) -> list[str]:
    """Rough split of a channel page into posts (the text between the channel header and the sidebar)."""
    body = text.split(name, 2)[-1] if text.count(name) >= 2 else text
    body = body.split("🚀 AKADEMIA SAAS")[0]
    if "Brak wpisów" in body or "Dodaj pierwszy post" in body:
        return []
    parts = re.split(r"\n(?=[^\n]{2,60}\n(?:Lv\.\d+\n)?\d+ (?:minut|godzin|dzie|dni|tydz|tygod)\w*)", body)
    return [p.strip() for p in parts if len(p.strip()) > 40]


def filip_task(ev: dict) -> str:
    start = datetime.strptime(f"{ev['date']} {ev['start'] or '20:00'}", "%Y-%m-%d %H:%M")
    end = datetime.strptime(f"{ev['date']} {ev['end'] or '21:30'}", "%Y-%m-%d %H:%M") if ev["end"] else None
    minutes = max(30, min(480, int((end - start).total_seconds() // 60))) if end else 90
    steps = (f"Why: the ODDF: AI SaaS cohort runs live workshops; joining live lets you ask questions and do the workshop "
             f"work with the group. The recording is transcribed and digested automatically afterwards.\n"
             f"1. {ev['date']} at {ev['start'] or '?'} (Polish time) open the community calendar: {COMMUNITY}?tab=calendar "
             f"and join \"{ev['title']}\".\n"
             f"2. Workshop posts and work: {COMMUNITY}/{CHANNELS['Warsztaty LIVE']} and {COMMUNITY}/{CHANNELS['Prace z warsztatów']}\n"
             f"3. Afterwards nothing to do: cohort_watch.py picks up the recording and the report lands in Notion "
             f"\"Kursy: lekcje\" (https://www.notion.so/e44ec7c6c4fc4f92af0a8626144963d4).\n")
    tmp = OUT / "task_steps.md"
    tmp.write_text(steps, encoding="utf-8")
    subprocess.run(["scp", "-q", "-i", KEY, str(tmp), f"{PROD}:/tmp/cohort_steps.md"], check=True, timeout=120)
    cmd = ("~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/filip_task.py add "
           f"--title {shlex.quote('Warsztat LIVE (kohorta AI SaaS): ' + ev['title'])} --body-file /tmp/cohort_steps.md "
           f"--due {ev['date']} --min {minutes} --thread {shlex.quote(THREAD)} "
           f"--why {shlex.quote('Live workshop of the ODDF: AI SaaS cohort')} "
           f"--done-when {shlex.quote('You joined the workshop (or decided to watch the recording)')}; rm -f /tmp/cohort_steps.md")
    r = subprocess.run(["ssh", "-i", KEY, PROD, cmd], capture_output=True, text=True, encoding="utf-8", timeout=600)
    return (r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else ""


def notion_push() -> None:
    """Same flow as by hand: the key goes from prod's Bitwarden straight into the push process on dev, in memory."""
    get_key = ("export BWS_ACCESS_TOKEN=$(cat ~/.bws_token); bws secret list --server-url https://vault.bitwarden.eu -o json"
               " | python3 -c \"import sys,json; print([s['value'] for s in json.load(sys.stdin)"
               " if s['key']=='NOTION_API_KEY'][0], end='')\"")
    push = ("cd ~/.hermes/sitedigest/akademiasaas-pl && export NOTION_API_KEY=$(cat) && "
            "~/.hermes/ytdigest/venv/bin/python push_notion.py akademiasaas-pl --lessons-only --only-new 2>&1 | tail -20")
    p1 = subprocess.Popen(["ssh", "-i", KEY, PROD, get_key], stdout=subprocess.PIPE)
    r = subprocess.run(["ssh", "-i", KEY, DEV, push], stdin=p1.stdout, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=6 * 3600)
    p1.wait()
    for line in r.stdout.strip().splitlines()[-8:]:
        log("  notion: " + line[:200])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pipeline", action="store_true")
    ap.add_argument("--no-notion", action="store_true")
    ap.add_argument("--no-tasks", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pages").mkdir(exist_ok=True)
    sf = OUT / "state.json"
    state = json.loads(sf.read_text(encoding="utf-8")) if sf.is_file() else {"events": {}, "posts": []}

    # 1. calendar and channels
    try:
        res = scrape()
    except Exception as exc:
        log(f"scrape failed: {type(exc).__name__}: {str(exc)[:200]}")
        res = None
    if res:
        stamp = time.strftime("%Y%m%d-%H%M")
        (OUT / "pages" / f"{stamp}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        new_posts = []
        for name, text in res["channels"].items():
            for post in channel_posts(text, name):
                # hash the content only: "4 godziny temu", reaction counts etc. change between runs
                core = "\n".join(l for l in post.splitlines()
                                 if len(l.strip()) > 25 and not re.search(r"\b(temu|edytowano)\b|publikuje w|Dodaj nowy wpis", l))
                if not core:  # the empty post editor of a channel, not a post
                    continue
                h = hashlib.sha1((name + core).encode("utf-8")).hexdigest()[:16]
                if h not in state["posts"]:
                    state["posts"].append(h)
                    new_posts.append(f"## {name} (seen {time.strftime('%Y-%m-%d %H:%M')})\n\n{post}\n")
        if new_posts:
            with open(OUT / "posts.md", "a", encoding="utf-8") as f:
                f.write("\n".join(new_posts) + "\n")
        log(f"channels: {len(new_posts)} new posts")
        # 2. events -> timeplane tasks
        events = upcoming_events(res["calendar"])
        log(f"calendar: {len(events)} upcoming: " + "; ".join(f"{e['date']} {e['start']} {e['title']}" for e in events))
        for ev in events:
            k = f"{ev['date']} {ev['title']}"
            if k in state["events"]:
                continue
            out = "" if a.no_tasks else filip_task(ev)
            state["events"][k] = {**ev, "task": out, "seen": time.strftime("%Y-%m-%d %H:%M")}
            log(f"new event {k}: task {out[:120]}")
    sf.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    # 3. new lessons/recordings -> download, GPU transcript, VM pool
    if not a.no_pipeline:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        run([PY, "-u", str(HERE / "harvest_zanfia.py"), "map"], cwd=HERE, env=env, timeout=3600)
        run([PY, "-u", str(HERE / "harvest_zanfia.py"), "download", "--parallel", "3"], cwd=HERE, env=env, timeout=6 * 3600)
        # the long-running copies (remaining_*.cmd) do the same work: don't start a second one
        if running("transcribe_pc.py"):
            log("transcriber already running, it will pick up the new videos")
        else:
            run([PY, "-u", str(HERE / "transcribe_pc.py")], cwd=HERE, env=env, timeout=12 * 3600)
        if running("pipeline_loop.sh"):
            log("pipeline loop already running")
        else:
            run([BASH, "/d/hermes/course-harvest/pipeline_loop.sh", "akademiasaas-pl", "192.168.56.108", "4"],
                env={**env, "ONCE": "1"}, timeout=3600)
    # 4. Notion
    if not a.no_notion:
        try:
            notion_push()
        except Exception as exc:
            log(f"notion push failed: {type(exc).__name__}: {str(exc)[:200]}")
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
