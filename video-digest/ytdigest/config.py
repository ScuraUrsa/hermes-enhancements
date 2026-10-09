"""Configuration: defaults, overridden by a YAML/JSON file, then by environment.

Lookup order for the file: $YTDIGEST_CONFIG, ~/.hermes/ytdigest/config.yaml,
./config.yaml. Secrets never live in the file; they come from env (Hermes loads
them from Bitwarden into ~/.hermes/.env).
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

HOME = Path(os.path.expanduser("~"))
HERMES_HOME = Path(os.environ.get("HERMES_REAL_HOME", HOME)) / ".hermes"

DEFAULTS: dict[str, Any] = {
    # Where bundles, media and the queue live.
    "data_dir": str(HERMES_HOME / "ytdigest"),
    # Language of the report text and headings ("pl" or "en").
    "report_language": "pl",
    # Transcript policy, tried in order. "manual" = uploaded captions,
    # "auto" = YouTube auto-captions, "groq"/"local" = Whisper.
    "transcript_order": ["manual", "groq", "parakeet", "local", "auto"],
    "caption_languages": ["pl", "en"],
    "whisper_local_model": "small",
    "whisper_groq_model": "whisper-large-v3-turbo",
    # Local Whisper on the 8 GB VM is slow; skip it for long videos.
    "whisper_local_max_minutes": 40,
    # Frames
    "scene_threshold": 0.30,
    "frames_per_min": 2.0,
    "max_frames": 60,
    "frame_width": 768,
    "video_max_height": 480,
    # Keep downloaded media after processing (bundle + frames are always kept).
    "keep_media": False,
    # yt-dlp: cookies file (Netscape format) for Watch Later and for when the
    # VM's IP gets rate limited. Optional.
    "cookies_file": str(HERMES_HOME / "ytdigest" / "cookies" / "{account}.txt"),
    # Path to the benchmark's routing table (vbench/routing.json). Optional.
    "routing_file": "",
    # Report: transcript characters sent in one call before switching to map-reduce.
    "max_transcript_chars": 60000,
    "chunk_chars": 18000,
    # Notion
    "notion_data_source_id": "561ac2c0-89c5-4d5a-aa40-67ab0f248e9c",
    "notion_upload_frames": True,
    "notion_max_frame_images": 6,
    # Budget for unattended (backlog) work, on top of Hermes' own budget.py.
    "backlog_daily_cap_usd": 1.00,
    "backlog_est_cost_usd": 0.05,
    # Idle gate
    "idle_user_quiet_minutes": 20,
    "idle_max_load_per_cpu": 0.7,
    "idle_min_free_mem_mb": 1500,
    # Accounts processed by the backlog, in order (koalamis6 first: most playlists).
    "accounts": ["koalamis6", "fjkazmierczak", "kazmierczakfilipjan", "praktyki"],
    "google_accounts_dir": str(HERMES_HOME / "google-accounts"),
    # Playlists to skip by title (case-insensitive substring).
    "skip_playlists": [],
    # Model providers (OpenAI-compatible). Keys come from env.
    "providers": {
        "ollama-cloud": {"base_url": "https://ollama.com/v1", "key_env": "OLLAMA_API_KEY"},
        "groq": {"base_url": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY"},
        "openrouter": {"base_url": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY"},
        "gemini": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
            "key_env": "GEMINI_API_KEY",
        },
        "ollama-local": {"base_url": "http://127.0.0.1:11434/v1", "key_env": ""},
    },
    # USD per 1M tokens [input, output]; unknown models use "_default".
    # Ollama Cloud figures mirror ~/.hermes/autonomy/budget.json (2026-10-05).
    "prices_per_mtok": {
        "gpt-oss:120b": [0.15, 0.60],
        "gpt-oss:20b": [0.07, 0.30],
        "glm-5.3-flash": [0.15, 0.50],
        "deepseek-v4.1-flash": [0.30, 1.20],
        "deepseek-v4-pro": [1.32, 3.96],
        "qwen3-vl:235b-instruct": [0.30, 1.20],
        "gemini-flash-lite-latest": [0.10, 0.40],
        "gemini-flash-latest": [0.30, 2.50],
        "_default": [0.50, 1.50],
    },
}


def _deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _read_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on host
        raise RuntimeError(f"PyYAML is needed to read {path}") from exc
    return yaml.safe_load(text) or {}


def config_path() -> Path | None:
    env = os.environ.get("YTDIGEST_CONFIG")
    candidates = [Path(env)] if env else []
    candidates += [HERMES_HOME / "ytdigest" / "config.yaml", Path("config.yaml")]
    for p in candidates:
        if p.is_file():
            return p
    return None


def load(path: str | Path | None = None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    p = Path(path) if path else config_path()
    if p:
        cfg = _deep_merge(cfg, _read_file(p))
    if os.environ.get("YTDIGEST_DATA_DIR"):
        cfg["data_dir"] = os.environ["YTDIGEST_DATA_DIR"]
    if os.environ.get("YTDIGEST_NOTION_DATA_SOURCE"):
        cfg["notion_data_source_id"] = os.environ["YTDIGEST_NOTION_DATA_SOURCE"]
    if os.environ.get("YTDIGEST_ROUTING"):
        cfg["routing_file"] = os.environ["YTDIGEST_ROUTING"]
    Path(cfg["data_dir"]).mkdir(parents=True, exist_ok=True)
    return cfg
