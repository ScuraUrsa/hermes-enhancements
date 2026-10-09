"""Notion writer for the "Raporty wideo" database (API 2025-09-03, data sources).

One row per video, found again by the "Video ID" property so re-runs update
the same page. The page body is replaced on each run. Key frames are uploaded
with the File Upload API and shown in "Co było widać".
"""

from __future__ import annotations

import mimetypes
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from . import render

API = "https://api.notion.com/v1"
VERSION = "2025-09-03"

STATUS = {"queued": "W kolejce", "processing": "Przetwarzanie", "done": "Gotowe",
          "artistic": "Artystyczne", "failed": "Błąd", "skipped": "Pominięte"}
SOURCE = {"youtube_manual": "napisy YouTube", "youtube_auto": "napisy auto", "whisper_local": "Whisper lokalnie",
          "whisper_groq": "Whisper Groq", "parakeet_local": "Parakeet lokalnie", "none": "brak"}
TIER = {0: "T0 bez LLM", 1: "T1 tani", 2: "T2 średni", 3: "T3 mocny"}


class NotionError(RuntimeError):
    pass


class Notion:
    def __init__(self, data_source_id: str, token: str | None = None, session=None):
        import requests

        self.ds = data_source_id
        self.token = token or os.environ.get("NOTION_API_KEY") or os.environ.get("NOTION_TOKEN")
        if not self.token:
            raise NotionError("NOTION_API_KEY not set")
        self.http = session or requests.Session()

    def _req(self, method: str, path: str, json_body=None, **kw):
        headers = {"Authorization": f"Bearer {self.token}", "Notion-Version": VERSION}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        url = path if path.startswith("http") else f"{API}{path}"
        for attempt in range(5):
            r = self.http.request(method, url, headers=headers, json=json_body, timeout=60, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(float(r.headers.get("Retry-After") or 2 * (attempt + 1)))
                continue
            if r.status_code >= 400:
                raise NotionError(f"{method} {path} -> {r.status_code}: {r.text[:400]}")
            time.sleep(0.35)  # stay under 3 requests/second
            return r.json() if r.content else {}
        raise NotionError(f"{method} {path}: gave up after retries")

    # -- rows -----------------------------------------------------------------
    def find(self, vid: str) -> str | None:
        body = {"filter": {"property": "Video ID", "rich_text": {"equals": vid}}, "page_size": 1}
        res = self._req("POST", f"/data_sources/{self.ds}/query", body).get("results") or []
        return res[0]["id"] if res else None

    def upsert(self, vid: str, props: dict) -> str:
        page_id = self.find(vid)
        if page_id:
            self._req("PATCH", f"/pages/{page_id}", {"properties": props})
            return page_id
        page = self._req("POST", "/pages", {"parent": {"type": "data_source_id", "data_source_id": self.ds}, "properties": props})
        return page["id"]

    def page_url(self, page_id: str) -> str:
        return f"https://www.notion.so/{page_id.replace('-', '')}"

    # -- body -----------------------------------------------------------------
    def clear(self, page_id: str) -> None:
        cursor = None
        while True:
            q = f"/blocks/{page_id}/children?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
            res = self._req("GET", q)
            for b in res.get("results", []):
                self._req("DELETE", f"/blocks/{b['id']}")
            if not res.get("has_more"):
                return
            cursor = res.get("next_cursor")

    def append(self, block_id: str, blocks: list[dict]) -> list[dict]:
        created = []
        for i in range(0, len(blocks), 100):
            res = self._req("PATCH", f"/blocks/{block_id}/children", {"children": blocks[i : i + 100]})
            created += res.get("results", [])
        return created

    def upload(self, path: Path) -> str:
        """Single-part file upload (< 20 MB); returns the file_upload id."""
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        up = self._req("POST", "/file_uploads", {"filename": path.name, "content_type": mime})
        with path.open("rb") as fh:
            r = self.http.post(
                up.get("upload_url") or f"{API}/file_uploads/{up['id']}/send",
                headers={"Authorization": f"Bearer {self.token}", "Notion-Version": VERSION},
                files={"file": (path.name, fh, mime)}, timeout=120,
            )
        if r.status_code >= 400:
            raise NotionError(f"file upload {path.name} -> {r.status_code}: {r.text[:300]}")
        return up["id"]


def properties(bundle: dict, report: dict, run: dict, status: str) -> dict:
    def text(v: str) -> dict:
        return {"rich_text": [{"text": {"content": (v or "")[:1900]}}]}

    def sel(v: str | None) -> dict:
        return {"select": {"name": v[:100]} if v else None}

    lang = (report.get("language") or bundle.get("language") or "")[:2]
    props = {
        "Tytuł": {"title": [{"text": {"content": (bundle.get("title") or bundle["video_id"])[:1900]}}]},
        "Video ID": text(bundle["video_id"]),
        "Link": {"url": bundle["url"]},
        "Kanał": text(bundle.get("channel") or ""),
        "Status": sel(STATUS[status]),
        "Typ wideo": sel(report.get("video_type")),
        "Tagi": {"multi_select": [{"name": t[:100]} for t in report.get("tags", [])[:20]]},
        "Jedno zdanie": text(report.get("one_line") or ""),
        "Język": sel(lang if lang in ("pl", "en") else ("inny" if lang else None)),
        "Czas trwania (min)": {"number": round((bundle.get("duration_sec") or 0) / 60, 1)},
        "Playlista": {"multi_select": [{"name": p[:100].replace(",", " ")} for p in bundle.get("playlists", [])[:10]]},
        "Konto": sel(bundle.get("account") or "ręcznie"),
        "Źródło transkryptu": sel(SOURCE.get(bundle["transcript"]["source"], bundle["transcript"]["source"])),
        "Analiza obrazu": {"checkbox": bool(run.get("visual"))},
        "Model": text(", ".join(run.get("models") or [])),
        "Poziom modelu": sel(TIER.get(run.get("tier", 1))),
        "Koszt USD": {"number": round(run.get("cost_usd", 0), 4)},
        "Pewność": {"number": round(float(report.get("confidence") or 0), 2)},
        "Przetworzono": {"date": {"start": datetime.now(timezone.utc).isoformat(timespec="seconds")}},
    }
    if bundle.get("published_at"):
        props["Opublikowano"] = {"date": {"start": bundle["published_at"]}}
    return props


def write_report(notion: Notion, bundle_dir: Path, bundle: dict, report: dict, run: dict, cfg: dict) -> str:
    status = "artistic" if report.get("is_artistic") else "done"
    page_id = notion.upsert(bundle["video_id"], properties(bundle, report, run, status))
    lang = cfg["report_language"]
    uploads: list[tuple[str, dict]] = []
    if cfg.get("notion_upload_frames") and not report.get("is_artistic"):
        useful = [f for f in bundle.get("frames", []) if f.get("path") and f.get("caption") and f.get("adds_information") is not False]
        useful = useful[: cfg.get("notion_max_frame_images", 6)]
        for f in useful:
            try:
                uploads.append((notion.upload(bundle_dir / f["path"]), f))
            except Exception:  # images are a bonus; the report must still land
                continue
    notion.clear(page_id)
    created = notion.append(page_id, render.notion_blocks(bundle, report, run, lang, uploads))
    if not report.get("is_artistic"):
        toggle = next((b for b in reversed(created) if b.get("type") == "heading_2"
                       and b["heading_2"].get("is_toggleable")), None)
        if toggle:
            notion.append(toggle["id"], render.transcript_blocks(bundle, lang))
    return notion.page_url(page_id)


def mark(notion: Notion, vid: str, url: str, title: str, status: str, note: str = "", account: str | None = None) -> str:
    """Create or update a bare row (queued / failed) without a report."""
    props = {
        "Tytuł": {"title": [{"text": {"content": (title or vid)[:1900]}}]},
        "Video ID": {"rich_text": [{"text": {"content": vid}}]},
        "Link": {"url": url},
        "Status": {"select": {"name": STATUS[status]}},
    }
    if note:
        props["Jedno zdanie"] = {"rich_text": [{"text": {"content": note[:1900]}}]}
    if account:
        props["Konto"] = {"select": {"name": account}}
    return notion.page_url(notion.upsert(vid, props))
