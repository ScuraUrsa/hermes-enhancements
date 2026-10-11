"""Map a logged-in website: every page in scope, in the order the site lists
them, with its module/section, text, screenshot, videos, documents and images.

Only GET navigation: nothing is clicked or submitted, and links that log out,
buy, delete, unenrol or mark lessons complete are never opened. Pages are
visited one at a time with a pause between them, like a person reading.

Output (resumable, re-run continues where it stopped):
  <root>/<site>/map.json                 every page and what was found on it
  <root>/<site>/pages/<key>/page.html    rendered HTML
                           /text.md      main content as Markdown
                           /shot.jpg     screenshot of the page (top 8000 px)
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from . import media, session

DANGER = re.compile(
    r"(log[-_]?out|sign[-_]?out|wyloguj|log[-_]?off|/delete|/destroy|/remove|unenrol|unenroll|unsubscribe|/cancel|"
    r"/checkout|/cart|/purchase|/buy|/billing|/payment|/upgrade|/orders?/|mark[-_]?(as[-_]?)?(complete|done)|"
    r"/complete(\?|$)|/reset|/settings|/password|/notifications|/messages/new|/comments?/new|/reply|"
    r"/vote|/like|/follow|/report-abuse|/oauth|/api/)", re.I)
TRACKING = re.compile(r"^(utm_\w+|fbclid|gclid|mc_cid|mc_eid|ref|ref_src|_hsenc|_hsmi|source)$", re.I)
LESSONISH = re.compile(r"(lesson|lecture|lekcj|module|modu[lł]|chapter|rozdzia|unit|step|posts?/|topic|video|class|session)", re.I)

EXTRACT_JS = r"""
() => {
  const abs = u => { try { return new URL(u, location.href).href } catch (e) { return null } };
  const txt = el => (el && (el.innerText || el.textContent) || '').replace(/\s+/g, ' ').trim();
  const HEAD = 'h1,h2,h3,h4,h5,h6,summary,[class*="section-title"],[class*="sectionTitle"],[class*="module-title"],' +
               '[class*="chapter-title"],[class*="heading"],[class*="title"]';
  function sectionOf(a) {
    let child = a, el = a.parentElement;
    for (let depth = 0; el && el !== document.body && depth < 7; depth++, child = el, el = el.parentElement) {
      let best = null;
      for (const h of el.querySelectorAll(':scope > ' + HEAD.split(',').join(', :scope > ') + ', :scope > * > h1, :scope > * > h2, :scope > * > h3, :scope > * > h4')) {
        if (h.contains(a)) continue;
        if (h.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING) best = h;
      }
      if (best) { const t = txt(best); if (t && t.length <= 160) return t; }
    }
    return '';
  }
  function md(root) {
    const out = [];
    const walk = (n, list) => {
      if (n.nodeType === 3) { out.push(n.textContent.replace(/\s+/g, ' ')); return; }
      if (n.nodeType !== 1) return;
      const tag = n.tagName.toLowerCase();
      if (['script','style','noscript','svg','nav','footer','header','button','form','iframe','video'].includes(tag)) return;
      const st = getComputedStyle(n); if (st.display === 'none' || st.visibility === 'hidden') return;
      if (/^h[1-6]$/.test(tag)) { out.push('\n\n' + '#'.repeat(+tag[1]) + ' ' + txt(n) + '\n\n'); return; }
      if (tag === 'pre') { out.push('\n```\n' + n.innerText + '\n```\n'); return; }
      if (tag === 'img') { const alt = n.getAttribute('alt'); if (alt) out.push(` [obraz: ${alt}] `); return; }
      if (tag === 'a') { const t = txt(n), h = abs(n.getAttribute('href') || ''); out.push(h && t && !h.startsWith('javascript') ? `[${t}](${h})` : t); return; }
      if (tag === 'li') out.push('\n- ');
      if (tag === 'tr') out.push('\n| ');
      if (['p','div','section','article','br','table','ul','ol','blockquote'].includes(tag)) out.push('\n');
      for (const c of n.childNodes) walk(c);
      if (tag === 'td' || tag === 'th') out.push(' | ');
      if (['p','div','section','blockquote'].includes(tag)) out.push('\n');
    };
    walk(root);
    return out.join('').replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  }
  const cands = [...document.querySelectorAll('main, article, [role=main], #content, .content, [class*="lesson-content"], ' +
                 '[class*="lecture-content"], [class*="post-body"], [class*="course-content"], [class*="entry-content"]')];
  let main = cands.sort((a, b) => txt(b).length - txt(a).length)[0];
  if (!main || txt(main).length < 200) main = document.body;
  const links = [...document.querySelectorAll('a[href]')].map(a => ({href: abs(a.getAttribute('href')), text: txt(a).slice(0, 200),
                  section: sectionOf(a)})).filter(l => l.href);
  // single-page apps often navigate from cards/rows carrying the target in a data attribute
  for (const el of document.querySelectorAll('[data-href], [data-url], [data-link], [data-to]')) {
    const h = abs(el.getAttribute('data-href') || el.getAttribute('data-url') || el.getAttribute('data-link') || el.getAttribute('data-to'));
    if (h) links.push({href: h, text: txt(el).slice(0, 200), section: sectionOf(el)});
  }
  const iframes = [...document.querySelectorAll('iframe')].map(f => abs(f.getAttribute('src') || f.getAttribute('data-src') || '')).filter(Boolean);
  const videos = [];
  for (const v of document.querySelectorAll('video, audio')) {
    for (const s of [v.currentSrc, v.getAttribute('src'), ...[...v.querySelectorAll('source')].map(s => s.getAttribute('src'))])
      if (s) videos.push(abs(s));
  }
  const embeds = [];
  for (const el of document.querySelectorAll('[class*="wistia_async_"], [data-wistia-id], [data-video-id][data-provider="wistia"]')) {
    const m = (el.className.baseVal === undefined ? el.className : '').match(/wistia_async_(\w+)/);
    const id = m ? m[1] : (el.getAttribute('data-wistia-id') || el.getAttribute('data-video-id'));
    if (id) embeds.push('https://fast.wistia.net/embed/iframe/' + id);
  }
  for (const el of document.querySelectorAll('[data-vimeo-id], [data-vimeo-url]')) {
    const id = el.getAttribute('data-vimeo-id'); embeds.push(id ? 'https://player.vimeo.com/video/' + id : abs(el.getAttribute('data-vimeo-url')));
  }
  for (const el of document.querySelectorAll('[data-video-url], [data-src*="m3u8"], [data-hls]'))
    embeds.push(abs(el.getAttribute('data-video-url') || el.getAttribute('data-src') || el.getAttribute('data-hls')));
  const images = [...main.querySelectorAll('img')].filter(i => i.naturalWidth >= 300 && i.naturalHeight >= 200)
                  .map(i => ({src: abs(i.currentSrc || i.src), alt: i.alt || '', w: i.naturalWidth, h: i.naturalHeight}));
  const crumbs = [...document.querySelectorAll('nav[aria-label*="read" i] li, .breadcrumb li, [class*="breadcrumb"] a')].map(txt).filter(Boolean);
  return {title: document.title, h1: txt(document.querySelector('h1')), crumbs, text: md(main), links, iframes,
          videos, embeds: embeds.filter(Boolean), images, height: document.documentElement.scrollHeight};
}
"""


def key_for(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def normalise(url: str) -> str:
    p = urlparse(url)
    query = urlencode(sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not TRACKING.match(k)))
    path = re.sub(r"/{2,}", "/", p.path) or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", query, ""))


class Scope:
    def __init__(self, start_url: str, include: str | None = None, exclude: str | None = None, hosts: list[str] | None = None):
        self.hosts = {urlparse(start_url).netloc.lower(), *(h.lower() for h in hosts or [])}
        self.include = re.compile(include) if include else None
        self.exclude = re.compile(exclude) if exclude else None

    def __call__(self, url: str) -> bool:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or p.netloc.lower() not in self.hosts:
            return False
        if DANGER.search(url) or media.classify(url):
            return False
        if self.include and not self.include.search(url):
            return False
        return not (self.exclude and self.exclude.search(url))


def map_path(cfg: dict, site: str) -> Path:
    return session.site_dir(cfg, site) / "map.json"


def load_map(cfg: dict, site: str) -> dict | None:
    p = map_path(cfg, site)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def save_map(cfg: dict, site: str, m: dict) -> None:
    m["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    p = map_path(cfg, site)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def page_dir(cfg: dict, site: str, key: str) -> Path:
    d = session.site_dir(cfg, site) / "pages" / key
    d.mkdir(parents=True, exist_ok=True)
    return d


def _kind(rec: dict, in_scope_links: int) -> str:
    if rec["videos"]:
        return "lesson"
    if in_scope_links >= 15 and rec["text_chars"] < 1500:
        return "index"
    if in_scope_links >= 3 and rec.get("link_share", 0) > 0.5:  # a table of contents: mostly links
        return "index"
    if LESSONISH.search(urlparse(rec["url"]).path):
        return "lesson"
    return "page"


def _new_page(url: str, parent: str | None, depth: int, section: str, link_text: str) -> dict:
    return {"key": key_for(url), "url": url, "parent": parent, "depth": depth, "section": section,
            "link_text": link_text, "status": "queued"}


def run(cfg: dict, site: str, start_url: str, *, include: str | None = None, exclude: str | None = None,
        hosts: list[str] | None = None, max_pages: int | None = None, max_depth: int = 6, refresh: bool = False,
        headless: bool = True, log=print, sleep=time.sleep) -> dict:
    """Map the site; returns the map (also saved to map.json after every page)."""
    from playwright.sync_api import sync_playwright

    scfg = cfg["site"]
    max_pages = max_pages or scfg["max_pages"]
    start = normalise(start_url)
    m = None if refresh else load_map(cfg, site)
    if not m or m.get("start_url") != start:
        m = {"site": site, "start_url": start, "include": include, "exclude": exclude, "hosts": hosts or [],
             "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "pages": [_new_page(start, None, 0, "", "")]}
    scope = Scope(start, m.get("include"), m.get("exclude"), m.get("hosts"))
    known = {p["url"] for p in m["pages"]}
    done = sum(1 for p in m["pages"] if p["status"] != "queued")
    lo, hi = scfg["delay_sec"]

    with sync_playwright() as pw:
        browser = session.launch(pw, headless=headless)
        ctx = session.new_context(browser, cfg, site)
        page = ctx.new_page()
        network: list[str] = []

        def on_response(resp):
            ctype = (resp.headers or {}).get("content-type", "")
            if ctype.startswith(("video/", "audio/")) or "mpegurl" in ctype or "dash+xml" in ctype or media.classify(resp.url) == "video":
                network.append(resp.url)

        page.on("response", on_response)
        try:
            for rec in m["pages"]:  # the list grows while we walk it: breadth-first in site order
                if rec["status"] != "queued":
                    continue
                if done >= max_pages:
                    log(f"stopped at --max-pages {max_pages}; run map again to continue")
                    break
                network.clear()
                try:
                    _visit(page, rec, cfg, site, network, log)
                except session.SessionExpired:
                    rec["status"] = "queued"
                    save_map(cfg, site, m)
                    raise
                except Exception as exc:
                    rec["status"] = "error"
                    rec["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
                    log(f"  ! {rec['url']}: {rec['error']}")
                done += 1
                if rec["status"] == "mapped" and rec["depth"] < max_depth:
                    in_scope = 0
                    for link in rec.pop("_links", []):
                        u = normalise(link["href"])
                        if not scope(u):
                            continue
                        in_scope += 1
                        if u not in known:
                            known.add(u)
                            m["pages"].append(_new_page(u, rec["key"], rec["depth"] + 1, link.get("section") or "", link.get("text") or ""))
                    rec["kind"] = _kind(rec, in_scope)
                rec.pop("_links", None)
                save_map(cfg, site, m)
                sleep(random.uniform(lo, hi))
        finally:
            session.save_state(cfg, site, ctx.storage_state())  # keep refreshed cookies
            browser.close()
    _number(m)
    save_map(cfg, site, m)
    return m


def _visit(page, rec: dict, cfg: dict, site: str, network: list[str], log) -> None:
    timeout = cfg["site"]["page_timeout_sec"] * 1000
    log(f"[{rec['key']}] {rec['url']}")
    try:
        resp = page.goto(rec["url"], wait_until="networkidle", timeout=timeout)
    except Exception:  # pages that never go idle (chat widgets, analytics): settle for load
        resp = page.goto(rec["url"], wait_until="load", timeout=timeout)
    final = page.url
    if session.looks_logged_out(rec["url"], final):
        raise session.SessionExpired(f"{rec['url']} redirected to the login page; run `sitedigest login` again")
    if resp is not None and resp.status >= 400:
        rec["status"] = "error"
        rec["error"] = f"HTTP {resp.status}"
        return
    for _ in range(12):  # scroll so lazy content and players load
        page.mouse.wheel(0, 1600)
        page.wait_for_timeout(250)
    page.wait_for_timeout(800)
    data = page.evaluate(EXTRACT_JS)
    d = page_dir(cfg, site, rec["key"])
    (d / "page.html").write_text(page.content(), encoding="utf-8")
    (d / "text.md").write_text(data["text"], encoding="utf-8")
    try:
        h = min(int(data.get("height") or 900), 8000)
        page.screenshot(path=str(d / "shot.jpg"), type="jpeg", quality=70, full_page=True,
                        clip={"x": 0, "y": 0, "width": 1366, "height": h})
    except Exception as exc:
        log(f"  screenshot skipped: {str(exc)[:120]}")
    found = {"iframes": data["iframes"], "videos": data["videos"], "embeds": data["embeds"], "network": list(network)}
    docs, seen = [], set()
    for link in data["links"]:
        u = link["href"].split("#")[0]
        if media.classify(u) == "doc" and u not in seen:
            seen.add(u)
            docs.append({"url": u, "text": link["text"]})
    rec.update({
        "final_url": final, "status": "mapped", "title": data["h1"] or data["title"], "page_title": data["title"],
        "crumbs": data["crumbs"][:8], "text_chars": len(data["text"]),
        "link_share": round(sum(len(x) for x in re.findall(r"\[[^\]]*\]\([^)]*\)", data["text"])) / max(len(data["text"]), 1), 2),
        "videos": media.page_videos(found, final), "docs": docs, "images": data["images"][:20],
        "mapped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "_links": data["links"],
    })
    (d / "found.json").write_text(json.dumps({**found, "links": data["links"]}, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"  {rec['title'][:80]!r}: {rec['text_chars']} chars, {len(rec['videos'])} video, {len(docs)} files")


def fetch_pages(cfg: dict, site: str, recs: list[dict], fetch_one, *, headless: bool = True, log=print,
                sleep=time.sleep) -> list[dict]:
    """Open each page again (fresh signed player links), then call fetch_one(rec) right away."""
    from playwright.sync_api import sync_playwright

    lo, hi = cfg["site"]["delay_sec"]
    out = []
    with sync_playwright() as pw:
        browser = session.launch(pw, headless=headless)
        ctx = session.new_context(browser, cfg, site)
        page = ctx.new_page()
        network: list[str] = []
        page.on("response", lambda r: network.append(r.url) if media.classify(r.url) == "video" else None)
        try:
            for rec in recs:
                network.clear()
                _visit(page, rec, cfg, site, network, log)
                rec.pop("_links", None)
                session.save_state(cfg, site, ctx.storage_state())  # cookies.txt for yt-dlp, current
                out.append({"key": rec["key"], **fetch_one(rec)})
                sleep(random.uniform(lo, hi))
        finally:
            session.save_state(cfg, site, ctx.storage_state())
            browser.close()
    return out


def _number(m: dict) -> None:
    """Course order: the order lessons were found in (site navigation order), and
    the module = the section heading the link sat under, inherited by children."""
    by_key = {p["key"]: p for p in m["pages"]}
    for i, p in enumerate(m["pages"], 1):
        p["order"] = i
        if not p.get("section") and p.get("parent") in by_key:
            p["section"] = by_key[p["parent"]].get("section") or ""
        if not p.get("section") and p.get("crumbs"):
            p["section"] = p["crumbs"][-2] if len(p["crumbs"]) > 1 else p["crumbs"][0]


def outline(m: dict) -> str:
    """Human-readable map: sections with their pages, and what each page holds."""
    lines = [f"# {m['site']}: {m['start_url']}", ""]
    counts = {"pages": 0, "videos": 0, "docs": 0, "errors": 0}
    current = None
    for p in m["pages"]:
        if p["status"] == "error":
            counts["errors"] += 1
        if p["status"] != "mapped":
            continue
        counts["pages"] += 1
        counts["videos"] += len(p.get("videos") or [])
        counts["docs"] += len(p.get("docs") or [])
        if (p.get("section") or "") != current:
            current = p.get("section") or ""
            lines.append(f"\n## {current or '(bez sekcji)'}")
        extra = []
        if p.get("videos"):
            extra.append(f"{len(p['videos'])} wideo")
        if p.get("docs"):
            extra.append(f"{len(p['docs'])} plików")
        lines.append(f"- [{p.get('kind', 'page')}] {p.get('title') or p['url']} ({', '.join(extra) or 'tekst'}) {p['url']}")
    queued = sum(1 for p in m["pages"] if p["status"] == "queued")
    lines.insert(1, f"{counts['pages']} stron, {counts['videos']} wideo, {counts['docs']} plików, "
                    f"{counts['errors']} błędów, {queued} jeszcze nieodwiedzonych")
    return "\n".join(lines) + "\n"
