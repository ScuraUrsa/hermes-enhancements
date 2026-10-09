"""process(): one video from link to Notion page.

  1. probe metadata (yt-dlp, no download)
  2. metadata music rule -> artistic: list in Notion, stop (no cost)
  3. transcript (captions -> Groq Whisper -> Parakeet -> local Whisper -> auto)
  4. analyse:
       gemini_url: Gemini reads the URL (speech + frames) and writes the report
       frames:     keyframes + vision model + text model (fallback path)
  5. write bundle.json, report.json, report.md and the Notion page
"""

from __future__ import annotations

import json
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path

from . import classify, fetch, frames, gemini, llm, notion, render, report, routing, transcript, vision


def _cookies(cfg: dict, account: str | None) -> str | None:
    tpl = cfg.get("cookies_file") or ""
    path = tpl.format(account=account or "default")
    if Path(path).is_file():
        return path
    fallback = tpl.format(account="default")
    return fallback if Path(fallback).is_file() else None


def make_bundle(info: dict, account: str | None, playlists: list[str]) -> dict:
    up = info.get("upload_date")
    published = f"{up[:4]}-{up[4:6]}-{up[6:8]}" if up and len(up) == 8 else None
    return {
        "schema": "video_bundle/v1",
        "video_id": info["id"],
        "url": fetch.watch_url(info["id"]),
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "duration_sec": info.get("duration"),
        "published_at": published,
        "language": (info.get("language") or "").split("-")[0] or None,
        "description": info.get("description") or "",
        "yt_tags": info.get("tags") or [],
        "yt_categories": info.get("categories") or [],
        "yt_chapters": [{"t": c.get("start_time", 0), "title": c.get("title", "")} for c in info.get("chapters") or []],
        "playlists": playlists,
        "account": account or "ręcznie",
        "transcript": {"source": "none", "language": None, "segments": []},
        "frames": [],
        "audio": {"music_ratio": None, "speech_ratio": None},
        "prep": {},
    }


def _save(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def process(url: str, cfg: dict, *, account: str | None = None, playlists: list[str] | None = None,
            tag: str = "manual", write_notion: bool = True, force_analyzer: str | None = None, log=print) -> dict:
    """Returns {video_id, status, notion_url, report_md, cost_usd, models, error?}."""
    data_dir = Path(cfg["data_dir"])
    client = llm.Client(cfg, ledger=data_dir / "spend.jsonl", tag=tag)
    table = routing.load(cfg)
    vid = fetch.video_id(url)
    bundle_dir = data_dir / "bundles" / vid
    work = data_dir / "work" / vid
    bundle_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    cookies = _cookies(cfg, account)
    run = {"models": [], "cost_usd": 0.0, "visual": False, "tier": 1, "started": datetime.now(timezone.utc).isoformat()}

    log(f"[{vid}] metadata")
    info = fetch.probe(fetch.watch_url(vid), cookies)
    bundle = make_bundle(info, account, playlists or [])
    nt = notion.Notion(cfg["notion_data_source_id"]) if write_notion else None

    # 2. artistic before anything costs money
    cls = classify.rule_based(info)
    if cls and cls["is_artistic"]:
        log(f"[{vid}] artistic ({cls['reason']}), listing only")
        return _finish(nt, cfg, bundle_dir, bundle, report.artistic_stub(bundle, cls["reason"]), run, client, "artistic", log)

    # 3. transcript
    log(f"[{vid}] transcript")
    audio_cache: dict = {}

    def audio_getter():
        if "p" not in audio_cache:
            audio_cache["p"] = fetch.download_audio(bundle["url"], work, cookies)
        return audio_cache["p"]

    tcfg = {**cfg, "whisper_groq_model": table.get("_transcribe_groq_model") or cfg["whisper_groq_model"]}
    tr = transcript.get(info, tcfg, work, cookies, audio_getter)
    bundle["transcript"] = tr
    bundle["language"] = bundle["language"] or tr.get("language")
    bundle["audio"]["speech_ratio"] = transcript.speech_ratio(tr["segments"], bundle["duration_sec"] or 0)
    head = transcript.plain_text(tr["segments"])[:3000]
    log(f"[{vid}] transcript source={tr['source']} segments={len(tr['segments'])}")

    # 4. classify (cheap model) unless the rule was already sure
    if not cls:
        try:
            cls = classify.with_model(client, table["default"]["classify"], info, head, bundle["audio"]["speech_ratio"], tr["source"])
        except Exception as exc:
            log(f"[{vid}] classify failed ({exc}); using 'other'")
            cls = {"video_type": "other", "is_artistic": False, "confidence": 0.3, "reason": "classifier failed"}
    if cls["is_artistic"]:
        log(f"[{vid}] artistic ({cls['reason']}), listing only")
        return _finish(nt, cfg, bundle_dir, bundle, report.artistic_stub(bundle, cls["reason"]), run, client, "artistic", log)
    vtype = cls["video_type"]
    route = routing.route(table, vtype)
    if route.get("skip"):
        return _finish(nt, cfg, bundle_dir, bundle, report.artistic_stub(bundle, f"skipped by routing ({vtype})"),
                       run, client, "artistic", log)

    # 5. analyse
    analyzer = force_analyzer or route.get("analyzer", "gemini_url")
    rep = None
    if analyzer == "gemini_url":
        model = llm.split_ref(route["url_model"])[1]
        try:
            log(f"[{vid}] analyse: Gemini reads the URL ({model}, {route['url_fps']} fps)")
            rep, described = gemini.analyse(client, model, bundle, cfg, route["url_fps"], head)
            bundle["frames"] = [{"t": float(f["t"]), "path": None, "reason": "model", "ocr_text": None,
                                 "caption": f.get("caption")} for f in described]
            run["visual"] = True
            if rep.get("is_artistic"):
                return _finish(nt, cfg, bundle_dir, bundle, report.artistic_stub(bundle, "Gemini: artistic"),
                               run, client, "artistic", log)
        except Exception as exc:
            log(f"[{vid}] Gemini URL path failed ({str(exc)[:200]}); falling back to frames")
            rep = None
    if rep is None:
        frames_per_min = route.get("frames_per_min", cfg["frames_per_min"])
        if frames_per_min > 0 and bundle["duration_sec"]:
            log(f"[{vid}] frames ({frames_per_min}/min)")
            try:
                video = fetch.download_video(bundle["url"], work, cfg["video_max_height"], cookies)
                fcfg = {**cfg, "frames_per_min": frames_per_min}
                bundle["frames"] = frames.extract_frames(video, bundle_dir, bundle["duration_sec"], bundle["yt_chapters"], fcfg)
                bundle["prep"] = {"frames_per_min": frames_per_min, "scene_threshold": cfg["scene_threshold"]}
                if bundle["frames"]:
                    _describe_frames(client, route, cfg, bundle_dir, bundle, tr["segments"], run, log)
            except Exception as exc:
                log(f"[{vid}] visual analysis skipped: {str(exc)[:200]}")
        log(f"[{vid}] report ({route['report']})")
        rep = report.build(client, route["report"], bundle, cfg, vtype)
    return _finish(nt, cfg, bundle_dir, bundle, rep, run, client, "done", log, work)


def _describe_frames(client, route: dict, cfg: dict, bundle_dir: Path, bundle: dict, segments, run: dict, log) -> None:
    """Caption the key frames; if the routed vision model fails on every frame, try the
    fallback model once, and if that fails too mark the run degraded instead of
    pretending the report saw the picture."""
    refs = [route["vision"]]
    fb = route.get("vision_fallback") or cfg.get("vision_fallback") or routing.VISION_FALLBACK
    if fb and fb not in refs:
        refs.append(fb)
    for ref in refs:
        for f in bundle["frames"]:
            f.pop("error", None)
        vision.describe(client, ref, bundle_dir, bundle["frames"], segments, cfg["report_language"],
                        title=bundle.get("title") or "")
        if any(f.get("caption") for f in bundle["frames"]):
            run["visual"] = True
            run["vision_model"] = ref
            return
        err = next((f.get("error") for f in bundle["frames"] if f.get("error")), "no captions returned")
        log(f"[{bundle['video_id']}] vision {ref} failed on all frames: {err[:200]}")
    run["visual"] = False
    run["degraded"] = "vision"
    log(f"[{bundle['video_id']}] WARNING visual analysis failed for all frames; report is transcript-only")


def _finish(nt, cfg, bundle_dir: Path, bundle: dict, rep: dict, run: dict, client, status: str, log, work: Path | None = None) -> dict:
    run["models"] = client.usage.models
    run["cost_usd"] = client.usage.cost_usd
    run["tier"] = 0 if not client.usage.calls else 1
    _save(bundle_dir / "bundle.json", bundle)
    _save(bundle_dir / "report.json", {"report": rep, "run": run})
    md = render.markdown(bundle, rep, run, cfg["report_language"])
    url = None
    if nt:
        log(f"[{bundle['video_id']}] Notion")
        url = notion.write_report(nt, bundle_dir, bundle, rep, run, cfg)
        md = render.markdown(bundle, rep, run, cfg["report_language"], url)
    (bundle_dir / "report.md").write_text(md, encoding="utf-8")
    if work and not cfg.get("keep_media"):
        shutil.rmtree(work, ignore_errors=True)
    log(f"[{bundle['video_id']}] {status}, ${run['cost_usd']:.4f}" + (f", {url}" if url else ""))
    return {"video_id": bundle["video_id"], "title": bundle.get("title"), "status": status, "notion_url": url,
            "report_md": md, "cost_usd": run["cost_usd"], "models": run["models"], "one_line": rep.get("one_line"),
            "degraded": run.get("degraded")}


def safe_process(url: str, cfg: dict, **kw) -> dict:
    """process() that never raises; failures come back as status 'failed'."""
    try:
        return process(url, cfg, **kw)
    except Exception as exc:
        return {"video_id": _vid_or(url), "status": "failed", "error": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc()[-2000:], "cost_usd": 0.0}


def _vid_or(url: str) -> str:
    try:
        return fetch.video_id(url)
    except ValueError:
        return url
