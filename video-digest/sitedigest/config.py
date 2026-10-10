"""Settings: the ytdigest config (models, Notion token, transcription, idle gate)
plus a `site:` section for crawling. Everything for one site lives under
<root>/<site>/."""

from __future__ import annotations

import os
from pathlib import Path

from ytdigest import config as ytconfig

DEFAULTS = {
    "root": str(ytconfig.HERMES_HOME / "sitedigest"),
    # Notion database for lessons ("Kursy: lekcje"); `sitedigest notion-setup` creates it
    "notion_data_source_id": "",
    "max_pages": 800,
    "delay_sec": [1.5, 3.5],          # pause between pages: polite, and keeps the account safe
    "page_timeout_sec": 45,
    "max_videos_per_page": 6,
    "max_doc_mb": 200,
    "max_page_chars": 14000,          # page text sent to the model
    "max_doc_chars": 40000,           # all documents of one page, before notes are taken
    "screenshot_tiles": 3,            # page screenshot slices captioned by the vision model
    "pdf_render_pages": 12,           # image-only PDFs: pages rendered and captioned
    "report_model": None,             # None = routing table default report model
    "vision_model": None,             # None = routing table default vision model
    "caption_languages": ["pl", "en"],
}


def load(path: str | Path | None = None) -> dict:
    cfg = ytconfig.load(path)
    site = {**DEFAULTS, **(cfg.get("site") or {})}
    if os.environ.get("SITEDIGEST_ROOT"):
        site["root"] = os.environ["SITEDIGEST_ROOT"]
    if os.environ.get("SITEDIGEST_NOTION_DATA_SOURCE"):
        site["notion_data_source_id"] = os.environ["SITEDIGEST_NOTION_DATA_SOURCE"]
    cfg["site"] = site
    Path(site["root"]).mkdir(parents=True, exist_ok=True)
    return cfg
