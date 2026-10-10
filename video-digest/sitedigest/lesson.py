"""digest(): one mapped page (a lesson) -> report, with everything it holds.

  1. page text (Markdown from the crawl) and page screenshot (vision captions)
  2. documents linked from the page: downloaded, text extracted; image-only
     PDFs rendered and captioned
  3. videos: downloaded with the lesson page as Referer; transcript from the
     player's own captions, else the ytdigest Whisper chain on the audio;
     key frames + vision captions as for YouTube
  4. one report over all of it (notes first when it is long)
  5. lesson.json, report.json, report.md in the page folder; a Notion row

Model choice follows ytdigest: the routing table's cheap models by default, the
AI/software route (Claude via the subscription) when the lesson is about that,
or whatever `site.report_model` / --model says.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ytdigest import fetch, frames, llm, pipeline, report as ytreport, routing, topics, transcript

from . import crawl, docs, media, session

FIELDS = (
    "one_line, about, text_summary, visual_summary, key_points[], life_applications[], action_items[], tags[], "
    "notable_quotes[{source,t,quote}], resources[{title,url,note}], prerequisites[], difficulty, lesson_kind, "
    "related_suggestions[], confidence"
)

SYSTEM = (
    "You turn one lesson of an online course into a report so the reader can skip the lesson and still "
    "learn everything useful from it: the page text, the attached files, what was said in the videos and "
    "what was shown on screen. Only state what the material supports. Answer with one JSON object only."
)

NOTES_SYSTEM = "You take precise, dense notes from course material. Keep every claim, number, name, step, command and [mm:ss] mark."

IMAGE_SYSTEM = (
    "You describe images from an online course (page screenshots, slides, handouts, diagrams) for someone "
    "who will not see them. Transcribe readable text, describe charts, diagrams, code and UI concretely. "
    "Answer with one JSON object only."
)


def _lang(cfg: dict) -> str:
    return "Polish" if cfg["report_language"] == "pl" else "English"


# -- images -------------------------------------------------------------------------

def screenshot_tiles(shot: Path, out_dir: Path, max_tiles: int, height: int = 1300) -> list[Path]:
    """Cut the page screenshot into readable slices, skipping blank ones."""
    from PIL import Image, ImageStat

    if not shot.is_file() or max_tiles <= 0:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(shot).convert("RGB")
    tiles = []
    for i, top in enumerate(range(0, img.height, height)):
        if len(tiles) >= max_tiles:
            break
        tile = img.crop((0, top, img.width, min(img.height, top + height)))
        if tile.height < 200 or max(ImageStat.Stat(tile.convert("L")).stddev) < 8:
            continue  # empty background
        p = out_dir / f"tile{i:02d}.jpg"
        tile.save(p, quality=75)
        tiles.append(p)
    return tiles


def caption_images(client, ref: str, paths: list[Path], cfg: dict, context: str, batch: int = 4) -> list[dict]:
    """[{path, caption, text}] for each image; failures leave caption empty."""
    out = [{"path": p, "caption": "", "text": ""} for p in paths]
    for i in range(0, len(paths), batch):
        group = paths[i : i + batch]
        user = (f"Context: {context}\n{len(group)} image(s). For each, in {_lang(cfg)}, return "
                '{"images": [{"n": 1, "caption": "what it shows, 1-3 sentences", "text": "readable text, verbatim, or empty"}]}')
        try:
            res = client.json(ref, IMAGE_SYSTEM, user, images=group, max_tokens=3000)
        except Exception as exc:
            for o in out[i : i + batch]:
                o["error"] = str(exc)[:200]
            continue
        for item in res.get("images") or []:
            try:
                n = int(item.get("n", 0)) - 1
            except (TypeError, ValueError):
                continue
            if 0 <= n < len(group):
                out[i + n]["caption"] = str(item.get("caption") or "").strip()
                out[i + n]["text"] = str(item.get("text") or "").strip()
    return out


# -- videos ---------------------------------------------------------------------------

def _duration(path: Path) -> float | None:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip())
    except Exception:
        return None


def _audio(video: Path, work: Path) -> Path:
    out = work / "audio.mp3"
    if not out.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
                        "-b:a", "48k", str(out)], check=True, timeout=3600)
    return out


def do_video(client, cfg: dict, route: dict, url: str, n: int, pdir: Path, page_url: str, cookies: str | None,
             run: dict, log) -> dict:
    vdir = pdir / f"video{n:02d}"
    work = vdir / "work"
    v = {"n": n, "url": url, "title": None, "duration_sec": None, "status": "done", "error": None,
         "transcript": {"source": "none", "language": None, "segments": []}, "frames": []}
    dl = media.download_video(url, work, referer=page_url, cookies=cookies, max_height=cfg["video_max_height"],
                              languages=cfg["site"]["caption_languages"])
    if dl["error"]:
        v["status"] = "drm" if dl["drm"] else "download_failed"
        v["error"] = dl["error"]
        log(f"    video {n}: {v['status']}: {dl['error'][:160]}")
        return v
    v["title"] = dl["title"]
    v["duration_sec"] = dl["duration"] or _duration(dl["path"])
    if dl["subtitles"]:
        segs = fetch.parse_vtt(dl["subtitles"].read_text(encoding="utf-8", errors="replace"))
        if segs:
            v["transcript"] = {"source": "player_captions", "language": dl["subtitles"].name.split(".")[-2][:2], "segments": segs}
    if not v["transcript"]["segments"]:
        info = {"id": f"{pdir.name}-v{n}", "webpage_url": url, "duration": v["duration_sec"], "language": None}
        tr = transcript.get(info, cfg, work, None, lambda: _audio(dl["path"], work))
        v["transcript"] = tr
    log(f"    video {n}: {int(v['duration_sec'] or 0)} s, transcript {v['transcript']['source']} "
        f"({len(v['transcript']['segments'])} segments)")
    fpm = route.get("frames_per_min", cfg["frames_per_min"])
    if fpm > 0 and v["duration_sec"] and dl["path"].suffix.lower() not in (".mp3", ".m4a"):
        try:
            v["frames"] = frames.extract_frames(dl["path"], vdir, v["duration_sec"], [], {**cfg, "frames_per_min": fpm})
            if v["frames"]:
                vb = {"video_id": f"{pdir.name}-v{n}", "title": v["title"] or "", "frames": v["frames"]}
                vrun = {"visual": False}
                pipeline._describe_frames(client, route, cfg, vdir, vb, v["transcript"]["segments"], vrun, log)
                if vrun.get("degraded"):
                    run["degraded"] = "vision"
        except Exception as exc:
            log(f"    video {n}: frames skipped: {str(exc)[:160]}")
            run["degraded"] = "vision"
    if not cfg.get("keep_media"):
        shutil.rmtree(work, ignore_errors=True)
    return v


# -- documents -----------------------------------------------------------------------

def do_docs(client, cfg: dict, vision_ref: str, rec: dict, pdir: Path, http, log) -> list[dict]:
    out = []
    for i, d in enumerate(rec.get("docs") or [], 1):
        item = {"url": d["url"], "label": d.get("text") or "", "name": None, "path": None, "text": "", "pictures": [], "error": None}
        dl = media.download_doc(http, d["url"], pdir / "files", referer=rec.get("final_url") or rec["url"],
                                max_mb=cfg["site"]["max_doc_mb"])
        if dl["error"]:
            item["error"] = dl["error"]
            log(f"    file {i}: {d['url'][:100]}: {dl['error']}")
            out.append(item)
            continue
        item["name"], item["path"] = dl["name"], str(dl["path"].relative_to(pdir))
        item["text"] = docs.text_of(dl["path"])
        if docs.needs_pictures(dl["path"], item["text"]):
            pages = docs.render_pdf_pages(dl["path"], pdir / "files" / f"{dl['path'].stem}_pages", cfg["site"]["pdf_render_pages"])
            caps = caption_images(client, vision_ref, pages, cfg, f"pages of the course file {dl['name']}")
            item["pictures"] = [{"path": str(c["path"].relative_to(pdir)), "caption": c["caption"], "text": c["text"]} for c in caps]
        log(f"    file {i}: {dl['name']} ({dl['bytes'] // 1024} kB, {len(item['text'])} chars"
            + (f", {len(item['pictures'])} pages looked at" if item["pictures"] else "") + ")")
        out.append(item)
    return out


# -- report ---------------------------------------------------------------------------

def _condense(client, ref: str, label: str, text: str, limit: int, chunk: int) -> str:
    if len(text) <= limit:
        return text
    parts = [text[i : i + chunk] for i in range(0, len(text), chunk)]
    notes = [client.complete(ref, NOTES_SYSTEM, f"{label}, part {n} of {len(parts)}:\n\n{p}", max_tokens=2500)
             for n, p in enumerate(parts, 1)]
    return f"(notes taken from {label}, which was long)\n" + "\n\n".join(notes)


def _sources(client, ref: str, cfg: dict, lesson: dict) -> str:
    scfg = cfg["site"]
    chunk = cfg["chunk_chars"]
    blocks = [f"PAGE TEXT:\n{_condense(client, ref, 'the page text', lesson['page_text'], scfg['max_page_chars'], chunk) or '(empty)'}"]
    if lesson["screens"]:
        blocks.append("WHAT THE PAGE LOOKS LIKE (screenshot slices):\n" + "\n".join(
            f"- {s['caption']} {('| text: ' + s['text'][:500]) if s['text'] else ''}" for s in lesson["screens"] if s["caption"]))
    doc_text = []
    for d in lesson["docs"]:
        if d.get("error"):
            doc_text.append(f"FILE {d['url']}: not downloaded ({d['error']})")
            continue
        body = d["text"]
        if d["pictures"]:
            body += "\n" + "\n".join(f"[page {i}] {p['caption']} | {p['text'][:800]}" for i, p in enumerate(d["pictures"], 1))
        doc_text.append(f"FILE {d['name']} ({d['label']}):\n{body}")
    if doc_text:
        blocks.append(_condense(client, ref, "the lesson's files", "\n\n".join(doc_text), scfg["max_doc_chars"], chunk))
    for v in lesson["videos"]:
        head = f"VIDEO {v['n']} ({v.get('title') or v['url']}, {int(v.get('duration_sec') or 0)} s)"
        if v["status"] != "done":
            blocks.append(f"{head}: not available ({v['status']})")
            continue
        tl = ytreport._timeline(v["transcript"]["segments"])
        tl = _condense(client, ref, f"video {v['n']} transcript", tl, cfg["max_transcript_chars"], chunk)
        blocks.append(f"{head} transcript:\n{tl or '(no speech)'}\n\n{head} key frames:\n{ytreport._frames_text(v['frames'])}")
    return "\n\n".join(blocks)


def _instructions(cfg: dict) -> str:
    lang = _lang(cfg)
    return f"""Write every text field in {lang}. Return JSON with: {FIELDS}.
- one_line: one sentence, what the reader can do or understand after this lesson.
- about: 2-4 sentences, what the lesson covers and for whom.
- text_summary: what the lesson teaches, 1-4 short paragraphs, specific (steps, numbers, names, commands, arguments), from the page text, the files and the speech together.
- visual_summary: what the screen, slides, diagrams or files showed that the words did not; say plainly if nothing.
- key_points: 4-12 concrete takeaways.
- life_applications: 2-5 ways to use this in your own work or life.
- action_items: 0-6 concrete exercises or next steps the lesson asks for or implies.
- tags: 4-10 lowercase topic tags in {lang}.
- notable_quotes: up to 4 short verbatim quotes, source "video N" with t in seconds, or "page"/"file" with t null.
- resources: tools, templates, links and files the lesson points to, with URL when known.
- prerequisites: what you need to know or have before this lesson ([] if nothing).
- difficulty: "beginner", "intermediate" or "advanced".
- lesson_kind: one of video_lesson, reading, worksheet, quiz, overview, live_replay, resource_list, other.
- related_suggestions: 2-5 related topics, books, people or searches.
- confidence: 0.0-1.0, how complete the material was (missing videos or files lower it)."""


def normalise(rep: dict) -> dict:
    for k in ("key_points", "life_applications", "action_items", "tags", "related_suggestions", "prerequisites"):
        v = rep.get(k) or []
        rep[k] = [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else [str(v)]
    rep["tags"] = sorted({t.lower().lstrip("#").replace(",", " ")[:90] for t in rep["tags"]})
    for k in ("one_line", "about", "text_summary", "visual_summary", "difficulty", "lesson_kind"):
        rep[k] = str(rep.get(k) or "").strip()
    rep["resources"] = [r for r in rep.get("resources") or [] if isinstance(r, dict) and (r.get("title") or r.get("url"))]
    rep["notable_quotes"] = [q for q in rep.get("notable_quotes") or [] if isinstance(q, dict) and q.get("quote")]
    try:
        rep["confidence"] = float(rep.get("confidence") or 0.5)
    except (TypeError, ValueError):
        rep["confidence"] = 0.5
    return rep


def choose_route(cfg: dict, rec: dict, page_text: str, model: str | None) -> tuple[dict, str | None]:
    table = routing.load(cfg)
    has_video = bool(rec.get("videos"))
    route = dict(routing.route(table, "lecture_slides" if has_video else "default"))
    scfg = cfg["site"]
    if scfg.get("report_model"):
        route["report"] = scfg["report_model"]
    if scfg.get("vision_model"):
        route["vision"] = scfg["vision_model"]
    info = {"title": rec.get("title") or "", "tags": [], "channel": rec.get("section") or "", "description": page_text[:3000]}
    route, why = topics.apply(route, cfg, info, page_text[:3000], "site", None)
    if model:
        route = {**route, "report": model, "vision": model}
        why = "chosen for this run"
    return route, why


# -- one page -------------------------------------------------------------------------

def digest(cfg: dict, site: str, rec: dict, *, model: str | None = None, write_notion: bool = True,
           tag: str = "backlog", log=print) -> dict:
    """Returns {key, status, title, one_line, notion_url, cost_usd, ...}; also stored as rec['digest']."""
    from . import notion_out

    pdir = crawl.page_dir(cfg, site, rec["key"])
    client = llm.Client(cfg, ledger=Path(cfg["data_dir"]) / "spend.jsonl", tag=tag)
    started = datetime.now(timezone.utc)
    page_text = (pdir / "text.md").read_text(encoding="utf-8") if (pdir / "text.md").is_file() else ""
    route, why = choose_route(cfg, rec, page_text, model)
    run = {"started": started.isoformat(), "route_reason": why, "report_model": route["report"], "vision_model": route["vision"]}
    log(f"[{rec['key']}] {rec.get('title') or rec['url']} (report {route['report']}" + (f", {why}" if why else "") + ")")

    lesson = {"schema": "site_lesson/v1", "site": site, "key": rec["key"], "url": rec.get("final_url") or rec["url"],
              "title": rec.get("title") or rec.get("link_text") or rec["url"], "section": rec.get("section") or "",
              "order": rec.get("order"), "crumbs": rec.get("crumbs") or [], "page_text": page_text,
              "screens": [], "docs": [], "videos": []}

    tiles = screenshot_tiles(pdir / "shot.jpg", pdir / "tiles", cfg["site"]["screenshot_tiles"])
    if tiles:
        caps = caption_images(client, route["vision"], tiles, cfg, f"screenshot of the course page '{lesson['title']}'")
        lesson["screens"] = [{"path": str(c["path"].relative_to(pdir)), "caption": c["caption"], "text": c["text"]} for c in caps]

    http = session.requests_session(cfg, site)
    lesson["docs"] = do_docs(client, cfg, route["vision"], rec, pdir, http, log)

    cookies = str(session.cookies_path(cfg, site)) if session.cookies_path(cfg, site).is_file() else None
    for n, url in enumerate((rec.get("videos") or [])[: cfg["site"]["max_videos_per_page"]], 1):
        lesson["videos"].append(do_video(client, cfg, route, url, n, pdir, lesson["url"], cookies, run, log))

    user = f"Course site: {site}\nSection: {lesson['section']}\nLesson: {lesson['title']}\nURL: {lesson['url']}\n\n" \
           f"{_sources(client, route['report'], cfg, lesson)}\n\n{_instructions(cfg)}"
    rep = normalise(client.json(route["report"], SYSTEM, user, max_tokens=6000))
    if any(v["status"] != "done" for v in lesson["videos"]):
        rep["confidence"] = min(rep["confidence"], 0.6)

    run.update(models=client.usage.models, cost_usd=client.usage.cost_usd, usage=client.usage.by_model,
               seconds=round((datetime.now(timezone.utc) - started).total_seconds(), 1))
    status = "done" if all(v["status"] == "done" for v in lesson["videos"]) else "partial"
    (pdir / "lesson.json").write_text(json.dumps(lesson, ensure_ascii=False, indent=1), encoding="utf-8")
    (pdir / "report.json").write_text(json.dumps({"report": rep, "run": run}, ensure_ascii=False, indent=1), encoding="utf-8")
    url = None
    if write_notion:
        try:
            url = notion_out.write_lesson(cfg, pdir, lesson, rep, run, status)
        except Exception as exc:  # the report is saved locally; Notion can be re-sent later
            run["notion_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            log(f"[{rec['key']}] Notion skipped: {run['notion_error']}")
    (pdir / "report.md").write_text(notion_out.markdown(lesson, rep, run, url), encoding="utf-8")
    res = {"key": rec["key"], "status": status, "title": lesson["title"], "one_line": rep.get("one_line"),
           "notion_url": url, "cost_usd": run["cost_usd"], "seconds": run["seconds"], "models": run["models"],
           "videos": len(lesson["videos"]), "files": len(lesson["docs"]), "degraded": run.get("degraded"),
           "notion_error": run.get("notion_error"),
           "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    log(f"[{rec['key']}] {status}, ${run['cost_usd']:.4f}, {run['seconds']} s" + (f", {url}" if url else ""))
    return res
