"""The report template, rendered two ways: Notion blocks and Markdown.

Layout follows Filip's wording: "Here is the report from this film. This film
was about this and that, the text was about that and the video about that. You
can use this in your life in this and that. Here are propositions and tags and
the whole transcript and the link to the video and suggested related things."
"""

from __future__ import annotations

HEADINGS = {
    "pl": {
        "intro": "Raport z filmu",
        "about": "O czym jest ten film",
        "text": "Co zostało powiedziane",
        "visual": "Co było widać",
        "points": "Najważniejsze punkty",
        "life": "Jak możesz to wykorzystać w swoim życiu",
        "actions": "Propozycje działań",
        "chapters": "Rozdziały",
        "quotes": "Cytaty",
        "related": "Powiązane tematy do sprawdzenia",
        "meta": "Tagi i metadane",
        "video": "Film",
        "transcript": "Pełny transkrypt",
        "artistic": "Treść artystyczna: tylko zapisana na liście, bez analizy.",
        "no_transcript": "Brak transkryptu dla tego filmu.",
        "vision_failed": "Uwaga: analiza obrazu nie powiodła się, ten raport opiera się tylko na transkrypcie.",
        "tags": "Tagi", "channel": "Kanał", "duration": "Czas trwania", "published": "Opublikowano",
        "type": "Typ", "source": "Źródło transkryptu", "model": "Modele", "cost": "Koszt",
    },
    "en": {
        "intro": "Report from this video",
        "about": "What this video is about",
        "text": "What was said",
        "visual": "What was shown",
        "points": "Key points",
        "life": "How you can use this in your life",
        "actions": "Suggested actions",
        "chapters": "Chapters",
        "quotes": "Quotes",
        "related": "Related things to explore",
        "meta": "Tags and metadata",
        "video": "Video",
        "transcript": "Full transcript",
        "artistic": "Artistic content: listed only, not analysed.",
        "vision_failed": "Note: frame analysis failed, so this report is based on the transcript only.",
        "no_transcript": "No transcript available for this video.",
        "tags": "Tags", "channel": "Channel", "duration": "Duration", "published": "Published",
        "type": "Type", "source": "Transcript source", "model": "Models", "cost": "Cost",
    },
}

MAX_TEXT = 1900  # Notion rich_text limit is 2000 characters per object


def mmss(t: float) -> str:
    t = int(t or 0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def at(url: str, t: float) -> str:
    return f"{url}&t={int(t or 0)}s" if "?" in url else f"{url}?t={int(t or 0)}s"


# -- Notion block helpers -------------------------------------------------------

def rt(text: str, link: str | None = None, bold: bool = False) -> list[dict]:
    out = []
    for i in range(0, max(len(text), 1), MAX_TEXT):
        piece = {"type": "text", "text": {"content": text[i : i + MAX_TEXT]}}
        if link:
            piece["text"]["link"] = {"url": link}
        if bold:
            piece["annotations"] = {"bold": True}
        out.append(piece)
    return out


def block(kind: str, rich: list[dict], **extra) -> dict:
    return {"object": "block", "type": kind, kind: {"rich_text": rich, **extra}}


def h2(text: str) -> dict:
    return block("heading_2", rt(text))


def para(text: str) -> list[dict]:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    return [block("paragraph", rt(p)) for p in paragraphs]


def bullets(items: list[str], kind: str = "bulleted_list_item") -> list[dict]:
    if kind == "to_do":
        return [block("to_do", rt(i), checked=False) for i in items]
    return [block(kind, rt(i)) for i in items]


def image_block(upload_id: str, caption: str) -> dict:
    return {
        "object": "block", "type": "image",
        "image": {"type": "file_upload", "file_upload": {"id": upload_id}, "caption": rt(caption[:MAX_TEXT])},
    }


def _meta_lines(bundle: dict, report: dict, run: dict, H: dict) -> list[str]:
    return [
        f"{H['tags']}: " + (", ".join(f"#{t}" for t in report.get("tags", [])) or "—"),
        f"{H['channel']}: {bundle.get('channel')}",
        f"{H['duration']}: {mmss(bundle.get('duration_sec') or 0)}",
        f"{H['published']}: {bundle.get('published_at') or '—'}",
        f"{H['type']}: {report.get('video_type')}",
        f"{H['source']}: {bundle['transcript']['source']}",
        f"{H['model']}: {', '.join(run.get('models') or []) or '—'}",
        f"{H['cost']}: ${run.get('cost_usd', 0):.4f}",
    ]


def notion_blocks(bundle: dict, report: dict, run: dict, lang: str, frame_uploads: list[tuple[str, dict]] | None = None) -> list[dict]:
    """Body of the report page. The transcript toggle is returned empty; its
    paragraphs are appended separately (Notion caps 100 children per request)."""
    H = HEADINGS.get(lang, HEADINGS["pl"])
    url = bundle["url"]
    out: list[dict] = []
    if report.get("is_artistic"):
        out.append(block("callout", rt(H["artistic"] + (" " + report.get("about", "") if report.get("about") else "")),
                         icon={"type": "emoji", "emoji": "🎵"}))
        out.append(block("paragraph", rt(url, link=url)))
        out.append({"object": "block", "type": "video", "video": {"type": "external", "external": {"url": url}}})
        return out

    out.append(block("callout", rt(f"{H['intro']}: ", bold=True) + rt(report.get("one_line") or ""),
                     icon={"type": "emoji", "emoji": "📌"}))
    out += [h2(H["about"])] + para(report.get("about") or "—")
    out += [h2(H["text"])] + para(report.get("text_summary") or "—")
    out += [h2(H["visual"])]
    if run.get("degraded") == "vision":
        out.append(block("callout", rt(H["vision_failed"]), icon={"type": "emoji", "emoji": "⚠️"}))
    out += para(report.get("visual_summary") or "—")
    for upload_id, frame in frame_uploads or []:
        out.append(image_block(upload_id, f"{mmss(frame['t'])} {frame.get('caption') or ''}".strip()))
    if not frame_uploads:
        for f in bundle.get("frames") or []:
            if f.get("caption"):
                out.append(block("bulleted_list_item", rt(mmss(f["t"]), link=at(url, f["t"])) + rt(f"  {f['caption']}")))
    if report.get("key_points"):
        out += [h2(H["points"])] + bullets(report["key_points"])
    if report.get("life_applications"):
        out += [h2(H["life"])] + bullets(report["life_applications"])
    if report.get("action_items"):
        out += [h2(H["actions"])] + bullets(report["action_items"], "to_do")
    if report.get("chapters"):
        out.append(h2(H["chapters"]))
        for c in report["chapters"]:
            out.append(block("bulleted_list_item", rt(mmss(c["t"]), link=at(url, c["t"])) + rt(f"  {c.get('title', '')}")))
    if report.get("notable_quotes"):
        out.append(h2(H["quotes"]))
        for q in report["notable_quotes"]:
            out.append(block("quote", rt(f"„{q['quote']}” ") + rt(f"({mmss(q.get('t', 0))})", link=at(url, q.get("t", 0)))))
    if report.get("related_suggestions"):
        out += [h2(H["related"])] + bullets(report["related_suggestions"])
    out += [h2(H["meta"])] + bullets(_meta_lines(bundle, report, run, H))
    out.append(h2(H["video"]))
    out.append(block("paragraph", rt(bundle.get("title") or url, link=url)))
    out.append({"object": "block", "type": "video", "video": {"type": "external", "external": {"url": url}}})
    out.append(block("heading_2", rt(H["transcript"]), is_toggleable=True))
    return out


def transcript_blocks(bundle: dict, lang: str, every: float = 60.0) -> list[dict]:
    """Transcript as paragraphs of about a minute each, each starting with a
    clickable timestamp."""
    H = HEADINGS.get(lang, HEADINGS["pl"])
    segs = bundle["transcript"]["segments"]
    if not segs:
        return [block("paragraph", rt(H["no_transcript"]))]
    url = bundle["url"]
    out, buf, start = [], [], segs[0]["start"]
    for s in segs:
        if buf and s["start"] - start >= every:
            out.append(block("paragraph", rt(mmss(start), link=at(url, start)) + rt(" " + " ".join(buf))))
            buf, start = [], s["start"]
        buf.append(s["text"])
    if buf:
        out.append(block("paragraph", rt(mmss(start), link=at(url, start)) + rt(" " + " ".join(buf))))
    return out


def markdown(bundle: dict, report: dict, run: dict, lang: str, notion_url: str | None = None) -> str:
    """Same template as Markdown, for chat replies and the local report.md."""
    H = HEADINGS.get(lang, HEADINGS["pl"])
    url = bundle["url"]
    lines = [f"# {bundle.get('title')}", ""]
    if report.get("is_artistic"):
        lines += [f"🎵 {H['artistic']} {report.get('about', '')}", "", url]
        return "\n".join(lines)
    lines += [f"**{H['intro']}:** {report.get('one_line', '')}", ""]
    if notion_url:
        lines += [f"Notion: {notion_url}", ""]
    for key, field in (("about", "about"), ("text", "text_summary"), ("visual", "visual_summary")):
        lines += [f"## {H[key]}"]
        if key == "visual" and run.get("degraded") == "vision":
            lines += [f"> ⚠️ {H['vision_failed']}", ""]
        lines += [report.get(field) or "—", ""]
    for key, field, mark in (("points", "key_points", "-"), ("life", "life_applications", "-"),
                             ("actions", "action_items", "- [ ]"), ("related", "related_suggestions", "-")):
        if report.get(field):
            lines += [f"## {H[key]}"] + [f"{mark} {x}" for x in report[field]] + [""]
    if report.get("chapters"):
        lines += [f"## {H['chapters']}"] + [f"- [{mmss(c['t'])}]({at(url, c['t'])}) {c.get('title', '')}" for c in report["chapters"]] + [""]
    if report.get("notable_quotes"):
        lines += [f"## {H['quotes']}"] + [f"> „{q['quote']}” ({mmss(q.get('t', 0))})" for q in report["notable_quotes"]] + [""]
    lines += [f"## {H['meta']}"] + [f"- {m}" for m in _meta_lines(bundle, report, run, H)] + ["", f"## {H['video']}", url, ""]
    return "\n".join(lines)
