"""On the VM: keep the first Notion version of regenerated lessons for comparison.
Renames each old lesson row to "[v1] <title>" and changes its key to "<key>-v1", so the next
push_notion.py run creates a fresh row for the v2 report instead of overwriting it.
Old URLs are kept in the map as digest.notion_url_v1. Course overview rows the same way
(--overviews). Needs NOTION_API_KEY.

  python archive_notion_v1.py SITE [--course-url-part X] [--overviews] [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import sys

import requests

from sitedigest import config, crawl

API = "https://api.notion.com/v1"


def _h() -> dict:
    return {"Authorization": f"Bearer {os.environ['NOTION_API_KEY']}", "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"}


def page_id(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1].rsplit("-", 1)[-1].split("?")[0]


def rename(pid: str, dry: bool) -> str | None:
    """Prefix the title with [v1] and suffix the key with -v1; returns the new title (None if done before)."""
    p = requests.get(f"{API}/pages/{pid}", headers=_h(), timeout=30).json()
    props = p["properties"]
    title = "".join(t["plain_text"] for t in props["Nazwa"]["title"])
    key = "".join(t["plain_text"] for t in props["Klucz"]["rich_text"])
    if title.startswith("[v1]") or key.endswith("-v1"):
        return None
    if not dry:
        r = requests.patch(f"{API}/pages/{pid}", headers=_h(), timeout=30, json={"properties": {
            "Nazwa": {"title": [{"text": {"content": f"[v1] {title}"[:1900]}}]},
            "Klucz": {"rich_text": [{"text": {"content": f"{key}-v1"}}]}}})
        r.raise_for_status()
    return f"[v1] {title}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("--course-url-part", action="append", default=[])
    ap.add_argument("--overviews", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = config.load()
    m = crawl.load_map(cfg, a.site)
    done: dict[str, str] = {}
    for p in m["pages"]:
        d = p.get("digest") or {}
        if not d.get("notion_url") or d.get("notion_url_v1"):
            continue
        if a.course_url_part and not any(c in p.get("course_url", "") for c in a.course_url_part):
            continue
        if not (crawl.page_dir(cfg, a.site, p["key"]) / "report.v2.done").is_file():
            continue
        try:
            rename(page_id(d["notion_url"]), a.dry_run)
            done[p["key"]] = d["notion_url"]
        except Exception as exc:
            print(f"  {p['key']} {p.get('title', '')[:50]}: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
    print(f"lesson rows kept as [v1]: {len(done)}", flush=True)
    if a.overviews:
        site_dir = crawl.map_path(cfg, a.site).parent
        for f in site_dir.glob("course-*.json"):
            import json
            c = json.loads(f.read_text(encoding="utf-8"))
            if c.get("notion_url") and not c.get("notion_url_v1"):
                print(f"  overview {f.name}: {rename(page_id(c['notion_url']), a.dry_run)}", flush=True)
                if not a.dry_run:
                    c["notion_url_v1"] = c.pop("notion_url")
                    f.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    if done and not a.dry_run:
        with crawl.map_lock(cfg, a.site):
            m2 = crawl.load_map(cfg, a.site)
            for p in m2["pages"]:
                if p["key"] in done:
                    p["digest"]["notion_url_v1"] = done[p["key"]]
                    p["digest"].pop("notion_url", None)
            crawl.save_map(cfg, a.site, m2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
