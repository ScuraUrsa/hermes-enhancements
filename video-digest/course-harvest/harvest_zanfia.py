"""Harvest a Zanfia course platform (e.g. akademiasaas.pl) on Filip's PC.

Why on the PC: the login is an emailed code, stored by Firebase in the browser
profile. Filip logs in once in the window this script opens; the session never
leaves this machine. Only lesson text and media go to the VM, where sitedigest
(hermes-enhancements/video-digest) analyses them.

Output is a sitedigest site folder:
  <out>/map.json                        pages in course order (sitedigest map format)
  <out>/pages/<key>/text.md             lesson title, module, description, page text
  <out>/pages/<key>/prefetch/video.mp4  the lesson video (Bunny Stream, signed link
                                        taken right before the download)
  <out>/products.json                   every product in the library with its URL
Videos are referenced as "local:prefetch/video.mp4"; external videos (YouTube,
Vimeo) keep their URL and are fetched on the VM.

Only GET navigation and opening the module lists; nothing is submitted, no lesson
is marked complete. Licence: the platform's regulamin § 6 allows saving the
content on the buyer's own devices for personal use.

  python harvest_zanfia.py map      --site-url https://akademiasaas.pl/app/library
  python harvest_zanfia.py download --course od-developera-do-foundera-3.0 [--limit N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(r"D:\courses")
PROFILE = ROOT / ".profile-zanfia"

LESSONS_JS = r"""
async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (const b of [...document.querySelectorAll('nav button[aria-expanded="false"], nav button[data-headlessui-state=""]')]) {
    b.click(); await sleep(120);
  }
  await sleep(800);
  const out = [];
  for (const li of document.querySelectorAll('li[data-testid=lesson-list-item]')) {
    const k = Object.keys(li).find(k => k.startsWith('__reactFiber'));
    let f = li[k], lesson = null;
    for (let i = 0; i < 5 && f; i++) { if (f.memoizedProps && f.memoizedProps.lesson) { lesson = f.memoizedProps.lesson; break } f = f.return }
    if (!lesson) continue;
    const ul = li.closest('ul');
    const btn = ul && ul.id ? document.querySelector(`[aria-controls="${ul.id}"]`) : null;
    const module = btn ? (btn.innerText || '').split('\n')[0].trim() : '';
    const v = lesson.video;
    out.push({id: lesson.id, title: lesson.title, type: lesson.type, length: lesson.length || null,
              moduleId: lesson.moduleId, module, description: typeof lesson.description === 'string' ? lesson.description : '',
              external: (lesson.type === 'externalVideo' && v) ? (typeof v === 'string' ? v : (v.url || v.link || v.src || null)) : null});
  }
  const title = (document.querySelector('nav') || document.body).innerText.split('\n').find(l => l.trim().length > 3) || document.title;
  return {lessons: out, course_title: title.trim()};
}
"""

PAGE_TEXT_JS = r"""
() => {
  const main = document.querySelector('main') || document.body;
  const links = [...main.querySelectorAll('a[href]')].map(a => ({href: a.href, text: (a.innerText || '').trim()}))
    .filter(l => /^https?:/.test(l.href));
  return {text: (main.innerText || '').trim(), links};
}
"""


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def site_name(url: str) -> str:
    host = urlparse(url).hostname or "site"
    host = re.sub(r"^(www|app|members|courses?|learn|academy)\.", "", host)
    return re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")


def key_for(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def open_browser(pw, headless: bool = False):
    PROFILE.mkdir(parents=True, exist_ok=True)
    return pw.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=headless,
                                                 viewport={"width": 1366, "height": 900}, locale="pl-PL")


def ensure_logged_in(page, library_url: str) -> None:
    page.goto(library_url, wait_until="domcontentloaded")
    for i in range(720):  # up to 60 min for Filip to log in (email code / magic link)
        page.wait_for_timeout(5000)
        try:
            ok = "/app/" in page.url and page.locator("text=Moje produkty").count() > 0
        except Exception:  # page navigating during the login flow
            ok = False
        if ok:
            log("logged in")
            if "/app/library" not in page.url:
                page.goto(library_url, wait_until="domcontentloaded")
            return
        if i % 60 == 0:
            log(f"waiting for login ({i // 12} min): log in in the opened Chrome window (email code), then leave it open; now at {page.url.split('?')[0]}")
    raise SystemExit("not logged in after 60 minutes")


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def map_products(page, library_url: str) -> list[dict]:
    """Open every product card in the library (one per card title) and note where it leads."""
    page.goto(library_url, wait_until="domcontentloaded")
    page.wait_for_selector("text=Moje produkty", timeout=60000)
    page.wait_for_timeout(2500)
    titles = page.evaluate("() => [...new Set([...document.querySelectorAll('[role=button] h3')].map(h => h.innerText.trim()))]")
    products, seen = [], set()
    for i, t in enumerate(titles, 1):
        page.goto(library_url, wait_until="domcontentloaded")
        page.wait_for_selector("text=Moje produkty", timeout=60000)
        page.wait_for_timeout(2000)
        info = page.evaluate("""(t) => { const h = [...document.querySelectorAll('[role=button] h3')].find(h => h.innerText.trim() === t);
            if (!h) return null; const card = h.closest('[role=button]');
            const lines = (card.innerText||'').split('\\n').map(s => s.trim()).filter(Boolean); card.click(); return {lines}; }""", t)
        if not info:
            continue
        page.wait_for_timeout(2500)
        kinds = ("Kurs", "Baza wiedzy", "Społeczność")
        kind = next((l for l in info["lines"] if l in kinds), "")
        url = page.url.split("?")[0]
        log(f"product {i}/{len(titles)}: {kind} | {t} -> {url}")
        if url in seen or url.rstrip("/").endswith("/library"):
            continue
        seen.add(url)
        products.append({"title": t, "kind": kind, "url": url, "card": info["lines"][:4]})
    return products


def course_lessons(page, course_url: str) -> dict:
    page.goto(course_url, wait_until="domcontentloaded")
    try:
        page.wait_for_selector("li[data-testid=lesson-list-item]", timeout=60000)
    except Exception:
        pass
    page.wait_for_timeout(2500)
    return page.evaluate(LESSONS_JS)


def build_map(site: str, start_url: str, products: list[dict], courses: dict[str, dict]) -> dict:
    pages, order = [], 0
    for p in products:
        data = courses.get(p["url"])
        if not data:
            continue
        for l in data["lessons"]:
            order += 1
            url = f"{p['url']}?lesson={l['id']}"
            pages.append({
                "key": key_for(url), "url": url, "final_url": url, "status": "mapped", "kind": "lesson",
                "title": l["title"], "link_text": l["title"], "section": f"{p['title']} / {l['module']}".strip(" /"),
                "crumbs": [p["title"], l["module"]], "order": order, "depth": 1, "parent": None,
                "course": p["title"], "course_url": p["url"], "module": l["module"], "lesson_id": l["id"],
                "lesson_type": l["type"], "length_sec": l["length"], "text_chars": len(l.get("description") or ""),
                "videos": [l["external"]] if l.get("external") else [], "docs": [], "images": [],
                "mapped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
    return {"site": site, "start_url": start_url, "platform": "zanfia", "pages": pages,
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def cmd_map(a) -> None:
    site = site_name(a.site_url)
    out = ROOT / site
    with sync_playwright() as pw:
        ctx = open_browser(pw)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        ensure_logged_in(page, a.site_url)
        products = map_products(page, a.site_url)
        save_json(out / "products.json", products)
        courses = {}
        for p in products:
            if "/courses/" not in p["url"]:
                log(f"skip (not a course page, map later): {p['kind']} {p['title']} {p['url']}")
                continue
            data = course_lessons(page, p["url"])
            courses[p["url"]] = data
            secs = sum(int(l["length"] or 0) for l in data["lessons"])
            log(f"course {p['title']}: {len(data['lessons'])} lessons, {secs / 3600:.1f} h, "
                f"{len({l['moduleId'] for l in data['lessons']})} modules")
            time.sleep(random.uniform(1.5, 3.0))
        save_json(out / "courses.json", courses)
        m = build_map(site, a.site_url, products, courses)
        old = out / "map.json"
        if old.is_file():  # keep download state of an earlier run
            prev = {p["key"]: p for p in json.loads(old.read_text(encoding="utf-8"))["pages"]}
            for p in m["pages"]:
                for k in ("videos", "downloaded", "download_error", "digest"):
                    if k in prev.get(p["key"], {}) and (k != "videos" or prev[p["key"]].get("downloaded")):
                        p[k] = prev[p["key"]][k]
        save_json(old, m)
        log(f"map: {len(m['pages'])} lessons in {len(courses)} courses -> {old}")
        ctx.close()


def download_bunny(src: str, dest_dir: Path, referer: str) -> tuple[Path | None, str | None]:
    import yt_dlp

    dest_dir.mkdir(parents=True, exist_ok=True)
    origin = f"{urlparse(referer).scheme}://{urlparse(referer).netloc}"
    opts = {"format": "bv*[height<=480]+ba/b[height<=480]/b", "outtmpl": str(dest_dir / "video.%(ext)s"),
            "http_headers": {"Referer": referer, "Origin": origin}, "quiet": True, "no_warnings": True,
            "noprogress": True, "concurrent_fragment_downloads": 4, "retries": 5, "fragment_retries": 10}
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([src])
    except Exception as exc:
        msg = re.sub(r"token=[^&\s]+", "token=***", str(exc))
        return None, msg[:300]
    files = [p for p in dest_dir.glob("video.*") if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".ts", ".m4a")]
    return (files[0], None) if files else (None, "no file")


def cmd_download(a) -> None:
    """One browser walks the lessons and reads each signed player link; up to
    --parallel yt-dlp downloads run at the same time (a link starts downloading
    right away, while it is still valid)."""
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

    site = site_name(a.site_url)
    out = ROOT / site
    mp = out / "map.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    todo = [p for p in m["pages"] if (not a.course or a.course in p["course_url"]) and not p.get("downloaded")]
    if a.limit:
        todo = todo[: a.limit]
    log(f"{len(todo)} lessons to fetch, {a.parallel} downloads at a time")
    descs = {l["id"]: l.get("description", "") for c in json.loads((out / "courses.json").read_text(encoding="utf-8")).values()
             for l in c.get("lessons", [])}
    pending: dict = {}
    done_n = 0

    def finish(fut) -> None:
        nonlocal done_n
        rec, pdir = pending.pop(fut)
        path, err = fut.result()
        if path:
            rec["videos"] = [f"local:prefetch/{path.name}"]
            rec["downloaded"] = True
            rec.pop("download_error", None)
        else:
            rec["download_error"] = err
        done_n += 1
        mb = path.stat().st_size / 1e6 if path else 0
        log(f"{done_n}/{len(todo)} {rec['module'][:30]} | {rec['title'][:50]} | "
            f"{'ok' if path else 'FAIL ' + str(err)[:80]} {mb:.0f} MB")
        save_json(mp, m)

    with sync_playwright() as pw, ThreadPoolExecutor(max_workers=a.parallel) as pool:
        ctx = open_browser(pw)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        ensure_logged_in(page, a.site_url)
        for rec in todo:
            while len(pending) >= a.parallel:  # keep links fresh: only start when a slot is free
                for f in wait(list(pending), return_when=FIRST_COMPLETED).done:
                    finish(f)
            pdir = out / "pages" / rec["key"]
            pdir.mkdir(parents=True, exist_ok=True)
            page.goto(rec["url"], wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            body = page.evaluate(PAGE_TEXT_JS)
            desc = descs.get(rec["lesson_id"], "")
            text = (f"# {rec['title']}\n\nKurs: {rec['course']}\nModuł: {rec['module']}\n\n"
                    f"## Opis lekcji\n\n{desc}\n\n## Strona lekcji\n\n{body['text']}\n")
            if body["links"]:
                text += "\n## Linki na stronie lekcji\n\n" + "\n".join(
                    f"- {l['text'] or l['href']}: {l['href']}" for l in body["links"]) + "\n"
            (pdir / "text.md").write_text(text, encoding="utf-8")
            rec["text_chars"] = len(text)
            docs = [l for l in body["links"] if re.search(r"\.(pdf|docx?|pptx?|xlsx?|zip|csv)(\?|$)|firebasestorage|drive\.google|docs\.google|dropbox", l["href"], re.I)]
            rec["docs"] = [{"url": l["href"], "text": l["text"]} for l in docs]
            if rec["lesson_type"] == "video":
                src = None
                for _ in range(60):  # up to 45 s for slow players
                    src = page.evaluate("() => { const f = document.querySelector('iframe[src*=\"mediadelivery.net\"]'); return f ? f.src : null }")
                    if src:
                        break
                    page.wait_for_timeout(750)
                if not src:
                    rec["download_error"] = "no Bunny player found"
                    log(f"{rec['title'][:50]}: no Bunny player found")
                    save_json(mp, m)
                else:
                    pending[pool.submit(download_bunny, src, pdir / "prefetch", rec["url"])] = (rec, pdir)
            else:  # external video or article: fetched on the VM by URL / text only
                rec["downloaded"] = True
                save_json(mp, m)
            for f in [f for f in list(pending) if f.done()]:
                finish(f)
            time.sleep(random.uniform(1.0, 2.5))
        while pending:
            for f in wait(list(pending), return_when=FIRST_COMPLETED).done:
                finish(f)
        ctx.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["map", "download", "login"])
    ap.add_argument("--site-url", default="https://akademiasaas.pl/app/library")
    ap.add_argument("--course", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--parallel", type=int, default=3, help="video downloads at the same time")
    a = ap.parse_args()
    if a.cmd == "login":
        with sync_playwright() as pw:
            ctx = open_browser(pw)
            ensure_logged_in(ctx.pages[0] if ctx.pages else ctx.new_page(), a.site_url)
            ctx.close()
    elif a.cmd == "map":
        cmd_map(a)
    else:
        cmd_download(a)


if __name__ == "__main__":
    sys.exit(main())
