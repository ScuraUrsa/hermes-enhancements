"""digest: one command for "Hermes, opracuj ten film / playlistę / kanał" (Filip, 2026-11-07: "robimy").

  python digest.py URL [URL ...] [--model claude-code:sonnet|claude-code:haiku] [--max 50] [--no-wait]
                   [--notify] [--job ID]

Same path as the Akademia SaaS courses (proven on 1100+ lessons):
  1. PC: yt-dlp lists the videos (video, playlist or channel URL), downloads each at 480p (ffmpeg merge,
     deno for YouTube's JS), writes text.md (title, channel, date, description, chapters, link);
  2. PC: transcript = the video's own human subtitles (pl/en) when YouTube has them, else faster-whisper on
     the GPU with the glossary (language detected);
  3. dev VM: sync, sitedigest pool (Sonnet by default: transcript + key frames + description -> report);
  4. Notion "Kursy: lekcje" (Strona = youtube, Sekcja = channel or playlist); a playlist or channel also gets
     an overview. The Notion key goes from prod's Bitwarden straight into the push on dev, in memory.
Dev sleeps at night for the prod upgrade (prod_guard): steps 3-4 wait for it (up to --max-wait hours).
Prints a JSON result (Notion links) on the last line. Site folder: D:/courses/youtube (sitedigest format).
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
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
SITE = "youtube"
OUT = Path(r"D:\courses") / SITE
PKG = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WinGet" / "Packages"
FFMPEG = next(PKG.glob("Gyan.FFmpeg_*/ffmpeg-*/bin"), None)
DENO = next(PKG.glob("DenoLand.Deno_*/deno.exe"), None)
YTDLP = str(HERE / "venv" / "Scripts" / "yt-dlp.exe")
BASH = r"D:\Git\bin\bash.exe"
KEY = r"D:\hermes\terraforge-stacks\local\generated\id_rsa"
PROD, DEV = "ubuntu@192.168.56.107", "ubuntu@192.168.56.108"
VM_SITE = f"~/.hermes/sitedigest/{SITE}"
VM_TOOLS = "~/.hermes/sitedigest/tools"


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, file=sys.stderr, flush=True)


def ytdlp(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = [YTDLP, "--no-warnings"]
    if FFMPEG:
        cmd += ["--ffmpeg-location", str(FFMPEG)]
    if DENO:
        cmd += ["--js-runtimes", f"deno:{DENO}"]
    return subprocess.run(cmd + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace", check=check)


def key_for(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def ssh(host: str, cmd: str, timeout: int = 600, stdin=None) -> subprocess.CompletedProcess:
    return subprocess.run(["ssh", "-o", "ConnectTimeout=10", "-i", KEY, host, cmd], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, stdin=stdin)


def dev_up() -> bool:
    try:
        return ssh(DEV, "true", timeout=30).returncode == 0
    except subprocess.TimeoutExpired:
        return False


# -- 1. list and download ---------------------------------------------------------------------------------

def expand(url: str, limit: int) -> tuple[dict, list[str]]:
    """Collection info (title/url) and the watch URLs of a video, playlist or channel URL."""
    r = ytdlp("--flat-playlist", "-J", "--playlist-end", str(limit), url)
    info = json.loads(r.stdout)
    if info.get("_type") in ("playlist", "multi_video"):
        entries = [e for e in info.get("entries") or [] if e]
        # a channel URL lists tabs (Videos, Shorts, Live) as nested playlists: take the videos tab
        if entries and entries[0].get("_type") == "playlist":
            vids = next((e for e in entries if "videos" in (e.get("url") or "").lower()), entries[0])
            return expand(vids["url"], limit)
        urls = [f"https://www.youtube.com/watch?v={e['id']}" for e in entries if e.get("id")][:limit]
        title = info.get("title") or info.get("channel") or url
        return {"title": f"YouTube: {title}", "url": info.get("webpage_url") or url}, urls
    return {"title": "YouTube: pojedyncze filmy", "url": "https://www.youtube.com/"}, [info.get("webpage_url") or url]


def fetch(url: str, coll: dict, order: int) -> dict:
    key = key_for(url)
    pdir = OUT / "pages" / key
    pre = pdir / "prefetch"
    pre.mkdir(parents=True, exist_ok=True)
    meta = json.loads(ytdlp("-J", "--skip-download", url).stdout)
    if not list(pre.glob("video.mp4")):
        log(f"download {meta.get('title', url)[:60]} ({int(meta.get('duration') or 0) // 60} min)")
        ytdlp("-f", "bv*[height<=480]+ba/b[height<=480]/b", "--merge-output-format", "mp4",
              "-o", str(pre / "video.%(ext)s"), url)
    lang = (meta.get("language") or "").split("-")[0]
    subs = meta.get("subtitles") or {}  # human subtitles only (automatic captions are a separate field)
    want = [l for l in ([lang] if lang else []) + ["pl", "en"] if l in subs]
    if want and not list(pre.glob("*.vtt")):
        ytdlp("--skip-download", "--write-subs", "--sub-langs", want[0], "--sub-format", "vtt", "-o", str(pre / "video"), url,
              check=False)
        for f in pre.glob("video.*.vtt"):
            (pre / f"{f.name}.asr2").write_text(json.dumps({"source": "youtube human subtitles"}), encoding="utf-8")
    chapters = "\n".join(f"- {int(c['start_time']) // 60}:{int(c['start_time']) % 60:02d} {c['title']}"
                         for c in meta.get("chapters") or [])
    up = meta.get("upload_date") or ""
    text = (f"# {meta.get('title')}\n\nKanał: {meta.get('channel') or meta.get('uploader')} ({meta.get('channel_url', '')})\n"
            f"Data: {up[:4]}-{up[4:6]}-{up[6:]}\nDługość: {int(meta.get('duration') or 0) // 60} min\nLink: {url}\n\n"
            f"## Opis\n\n{meta.get('description') or ''}\n" + (f"\n## Rozdziały\n\n{chapters}\n" if chapters else ""))
    (pdir / "text.md").write_text(text, encoding="utf-8")
    channel = meta.get("channel") or meta.get("uploader") or "YouTube"
    return {"key": key, "url": url, "final_url": url, "status": "mapped", "kind": "lesson",
            "title": meta.get("title") or url, "link_text": meta.get("title") or url,
            "section": f"{coll['title']} / {channel}", "crumbs": [coll["title"], channel], "order": order,
            "depth": 1, "parent": None, "course": coll["title"], "course_url": coll["url"], "module": channel,
            "lesson_type": "video", "length_sec": meta.get("duration"), "videos": ["local:prefetch/video.mp4"],
            "docs": [], "images": [], "downloaded": True, "youtube_id": meta.get("id"),
            "mapped_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


# -- 2. transcripts on the GPU ----------------------------------------------------------------------------

def transcribe(pages: list[dict]) -> None:
    todo = [p for p in pages if not list((OUT / "pages" / p["key"] / "prefetch").glob("*.vtt"))]
    if not todo:
        return
    sys.path.insert(0, str(HERE))
    import transcribe_pc as T

    T._add_cuda_dlls()
    import av

    _open = av.open
    av.open = lambda *x, **kw: _open(*x, **{k: v for k, v in kw.items() if k != "metadata_errors"})
    from faster_whisper import WhisperModel

    model = WhisperModel(str(HERE / "models" / "faster-whisper-large-v3-turbo"), device="cuda", compute_type="int8_float16")
    for p in todo:
        pre = OUT / "pages" / p["key"] / "prefetch"
        cfg = T.asr_settings(OUT, p["course_url"])  # asr/default.json: the general glossary
        t0 = time.time()
        segs, info = model.transcribe(str(pre / "video.mp4"), language=None, vad_filter=True, beam_size=5,
                                      condition_on_previous_text=False, hotwords=cfg.get("hotwords") or None)
        lines = ["WEBVTT", ""]
        for s in segs:
            text = T.apply_fixes(s.text.strip(), cfg)
            if text:
                lines += [f"{T.ts(s.start)} --> {T.ts(s.end)}", text, ""]
        vtt = pre / f"video.{info.language}.vtt"
        vtt.write_text("\n".join(lines), encoding="utf-8")
        T.marker(vtt).write_text(json.dumps({"hotwords": cfg.get("hotwords"), "at": time.time()}), encoding="utf-8")
        log(f"transcript {p['title'][:50]}: {info.language}, {info.duration / 60:.0f} min in {time.time() - t0:.0f} s")


# -- 3./4. dev VM and Notion ------------------------------------------------------------------------------

def vm_map() -> dict:
    r = ssh(DEV, f"cat {VM_SITE}/map.json", timeout=120)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {"pages": []}


def push_notion(courses: set[str], overview: bool) -> None:
    get_key = ("export BWS_ACCESS_TOKEN=$(cat ~/.bws_token); bws secret list --server-url https://vault.bitwarden.eu -o json"
               " | python3 -c \"import sys,json; print([s['value'] for s in json.load(sys.stdin)"
               " if s['key']=='NOTION_API_KEY'][0])\"")
    parts = " ".join(f"--course-url-part {shlex.quote(c)}" for c in courses)
    push = (f"read -r NOTION_API_KEY || true; export NOTION_API_KEY; cd {VM_TOOLS} && P=~/.hermes/ytdigest/venv/bin/python && "
            f"$P push_notion.py {SITE} --lessons-only --only-new {parts} 2>&1 | tail -4"
            + (f" && $P push_notion.py {SITE} --overview-only {parts} 2>&1 | tail -3" if overview else ""))
    p1 = subprocess.Popen(["ssh", "-i", KEY, PROD, get_key], stdout=subprocess.PIPE)
    r = subprocess.run(["ssh", "-i", KEY, DEV, push], stdin=p1.stdout, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=4 * 3600)
    p1.wait()
    for line in (r.stdout + r.stderr).strip().splitlines()[-6:]:
        log("notion: " + line[:160])


def notify(title: str, message: str, url: str | None) -> None:
    py = ("import sys; sys.path.insert(0, '/home/ubuntu/.hermes/scripts/timeplane'); import tp_push; "
          f"print(tp_push.send({title!r}, {message!r}, tag='digest', min_gap=0, url={url!r}))")
    r = ssh(PROD, f"cd ~/.hermes/scripts/timeplane && ~/.hermes/hermes-agent/venv/bin/python -c {json.dumps(py)}")
    log(f"notify: {(r.stdout + r.stderr).strip()[-120:]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--model", default="claude-code:sonnet")
    ap.add_argument("--max", type=int, default=50, help="max videos per playlist/channel")
    ap.add_argument("--no-wait", action="store_true", help="stop after the PC part (download + transcript + sync)")
    ap.add_argument("--max-wait", type=float, default=36, help="hours to wait for the dev VM and the digests")
    ap.add_argument("--notify", action="store_true", help="push notification to Filip's phone/Matrix when done")
    ap.add_argument("--job", default="", help="queue job id (digest_queue.py)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    mf = OUT / "map.json"
    m = json.loads(mf.read_text(encoding="utf-8")) if mf.is_file() else \
        {"site": SITE, "start_url": "https://www.youtube.com/", "platform": "youtube", "pages": []}

    # 1. list + download + text
    pages, courses, overview = [], set(), False
    for url in a.urls:
        coll, urls = expand(url, a.max)
        overview |= len(urls) > 1
        courses.add(coll["url"])
        log(f"{coll['title']}: {len(urls)} video(s)")
        for i, u in enumerate(urls, 1):
            try:
                pages.append(fetch(u, coll, len(m["pages"]) + i))
            except subprocess.CalledProcessError as exc:
                log(f"skip {u}: {(exc.stderr or '')[-200:]}")
    known = {p["key"]: p for p in m["pages"]}
    for p in pages:
        known[p["key"]] = {**known.get(p["key"], {}), **p}
    m["pages"] = list(known.values())
    m["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mf.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")

    # 2. transcripts
    transcribe(pages)
    keys = {p["key"] for p in pages}
    result = {"job": a.job, "videos": len(keys), "lessons": {}, "overview": None, "state": "pc-done"}
    if a.no_wait or not keys:
        print(json.dumps(result, ensure_ascii=False))
        return 0

    # 3. dev: sync + pool, wait for the digests
    deadline = time.time() + a.max_wait * 3600
    while not dev_up():
        if time.time() > deadline:
            result["state"] = "dev-unreachable"
            print(json.dumps(result, ensure_ascii=False))
            return 2
        log("dev VM asleep (prod_guard / nightly prod upgrade), waiting")
        time.sleep(600)
    ssh(DEV, f"mkdir -p {VM_TOOLS}")
    subprocess.run(["scp", "-q", "-i", KEY, str(HERE / "push_notion.py"), str(HERE / "fill_notion_urls.py"),
                    f"{DEV}:.hermes/sitedigest/tools/"], check=True)
    env = {**os.environ, "ONCE": "1"}
    subprocess.run([BASH, "/d/hermes/course-harvest/pipeline_loop.sh", SITE, "192.168.56.108", "2", a.model],
                   env=env, capture_output=True, timeout=3600)
    while True:
        vm = {p["key"]: p for p in vm_map()["pages"] if p["key"] in keys}
        st = {k: (p.get("digest") or {}).get("status") for k, p in vm.items()}
        done = [k for k, s in st.items() if s in ("done", "partial", "failed")]
        log(f"digests: {len(done)}/{len(keys)}")
        if len(done) == len(keys) or time.time() > deadline:
            break
        if not dev_up():
            time.sleep(600)
            continue
        subprocess.run([BASH, "/d/hermes/course-harvest/pipeline_loop.sh", SITE, "192.168.56.108", "2", a.model],
                       env=env, capture_output=True, timeout=3600)  # resync + restart the pool if dev slept
        time.sleep(120)

    # 4. Notion
    push_notion(courses, overview)
    vm = {p["key"]: p for p in vm_map()["pages"] if p["key"] in keys}
    for k, p in vm.items():
        d = p.get("digest") or {}
        result["lessons"][p["title"]] = {"status": d.get("status"), "notion": d.get("notion_url"), "youtube": p["url"]}
    over = ssh(DEV, f"cat {VM_SITE}/course-*.json 2>/dev/null | python3 -c \"import sys,json,re; "
                    f"print(' '.join(re.findall(r'https://www.notion.so/[0-9a-f]+', sys.stdin.read())))\"").stdout.split()
    result["overview"] = over[-1] if overview and over else None
    ok = sum(1 for v in result["lessons"].values() if v["notion"])
    result["state"] = "done" if ok == len(keys) else "partial"
    if a.notify:
        first = result["overview"] or next((v["notion"] for v in result["lessons"].values() if v["notion"]), None)
        titles = ", ".join(list(result["lessons"])[:3])
        notify("🎬 Raport z filmów gotowy", f"{ok}/{len(keys)} w Notion: {titles}"[:300], first)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
