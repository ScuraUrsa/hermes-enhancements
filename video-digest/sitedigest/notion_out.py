"""Course reports in Notion: one database "Kursy: lekcje", one row per lesson
(found again by "Klucz", so re-runs update the same page) and one row per
course with the course overview. Also the Markdown twin of each report."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ytdigest import notion as ytnotion
from ytdigest.render import MAX_TEXT, block, bullets, h2, image_block, mmss, para, rt

STATUS = {"done": "Gotowe", "partial": "Częściowo", "failed": "Błąd", "queued": "W kolejce", "skipped": "Pominięte"}
KIND = {"lesson": "lekcja", "page": "strona", "index": "spis", "course": "kurs"}

H = {
    "pl": {"intro": "Raport z lekcji", "about": "O czym jest ta lekcja", "text": "Czego uczy", "visual": "Co było widać",
           "points": "Najważniejsze punkty", "life": "Jak możesz to wykorzystać", "actions": "Do zrobienia",
           "resources": "Materiały, narzędzia i linki", "files": "Pobrane pliki", "prereq": "Wymagania",
           "quotes": "Cytaty", "related": "Powiązane tematy", "sources": "Materiał źródłowy",
           "page_text": "Tekst strony", "video": "Wideo", "transcript": "transkrypcja", "file": "Plik",
           "missing": "niedostępne", "drm": "zabezpieczone DRM, pominięte (raport bez tego wideo)",
           "partial": "Uwaga: części materiału nie udało się pobrać; raport jest niepełny.",
           "course": "Przegląd kursu", "modules": "Moduły i lekcje", "level": "Poziom"},
    "en": {"intro": "Lesson report", "about": "What this lesson is about", "text": "What it teaches", "visual": "What was shown",
           "points": "Key points", "life": "How you can use this", "actions": "To do",
           "resources": "Materials, tools and links", "files": "Downloaded files", "prereq": "Prerequisites",
           "quotes": "Quotes", "related": "Related topics", "sources": "Source material",
           "page_text": "Page text", "video": "Video", "transcript": "transcript", "file": "File",
           "missing": "unavailable", "drm": "DRM-protected, skipped (report without this video)",
           "partial": "Note: part of the material could not be downloaded; this report is incomplete.",
           "course": "Course overview", "modules": "Modules and lessons", "level": "Level"},
}

SCHEMA = {
    "Nazwa": {"title": {}},
    "Klucz": {"rich_text": {}},
    "Strona": {"select": {}},
    "Sekcja": {"rich_text": {}},
    "Kolejność": {"number": {}},
    "Link": {"url": {}},
    "Status": {"select": {"options": [{"name": v} for v in STATUS.values()]}},
    "Rodzaj": {"select": {"options": [{"name": v} for v in KIND.values()]}},
    "Tagi": {"multi_select": {}},
    "Jedno zdanie": {"rich_text": {}},
    "Poziom": {"select": {}},
    "Filmy": {"number": {}},
    "Pliki": {"number": {}},
    "Minuty wideo": {"number": {}},
    "Model": {"rich_text": {}},
    "Koszt USD": {"number": {}},
    "Pewność": {"number": {}},
    "Przetworzono": {"date": {}},
}


class LessonNotion(ytnotion.Notion):
    KEY = "Klucz"

    def find(self, key: str) -> str | None:
        body = {"filter": {"property": self.KEY, "rich_text": {"equals": key}}, "page_size": 1}
        res = self._req("POST", f"/data_sources/{self.ds}/query", body).get("results") or []
        return res[0]["id"] if res else None


def setup(parent_page_id: str, title: str = "Kursy: lekcje", token: str | None = None) -> str:
    """Create the lessons database under a page; returns its data source id."""
    n = ytnotion.Notion("-", token=token)
    db = n._req("POST", "/databases", {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": title}}],
        "initial_data_source": {"properties": SCHEMA},
    })
    return (db.get("data_sources") or [{}])[0].get("id") or db["id"]


def _client(cfg: dict) -> LessonNotion:
    ds = cfg["site"].get("notion_data_source_id")
    if not ds:
        raise ytnotion.NotionError("site.notion_data_source_id not set: run `sitedigest notion-setup --parent PAGE_ID`")
    return LessonNotion(ds)


def _text(v: str) -> dict:
    return {"rich_text": [{"text": {"content": (v or "")[:1900]}}]}


def properties(lesson: dict, rep: dict, run: dict, status: str, kind: str = "lesson") -> dict:
    minutes = sum((v.get("duration_sec") or 0) for v in lesson.get("videos") or []) / 60
    props = {
        "Nazwa": {"title": [{"text": {"content": (lesson.get("title") or lesson["key"])[:1900]}}]},
        "Klucz": _text(lesson["key"]),
        "Strona": {"select": {"name": lesson["site"][:100]}},
        "Sekcja": _text(lesson.get("section") or ""),
        "Link": {"url": lesson["url"]},
        "Status": {"select": {"name": STATUS.get(status, status)}},
        "Rodzaj": {"select": {"name": KIND.get(kind, kind)}},
        "Tagi": {"multi_select": [{"name": t[:100]} for t in rep.get("tags", [])[:20]]},
        "Jedno zdanie": _text(rep.get("one_line") or ""),
        "Filmy": {"number": len(lesson.get("videos") or [])},
        "Pliki": {"number": len(lesson.get("docs") or [])},
        "Minuty wideo": {"number": round(minutes, 1)},
        "Model": _text(", ".join(run.get("models") or [])),
        "Koszt USD": {"number": round(run.get("cost_usd", 0), 4)},
        "Pewność": {"number": round(float(rep.get("confidence") or 0), 2)},
        "Przetworzono": {"date": {"start": datetime.now(timezone.utc).isoformat(timespec="seconds")}},
    }
    if lesson.get("order") is not None:
        props["Kolejność"] = {"number": lesson["order"]}
    if rep.get("difficulty"):
        props["Poziom"] = {"select": {"name": rep["difficulty"][:100]}}
    return props


def toggle(title: str, children: list[dict]) -> list[dict]:
    """Toggle blocks of at most 100 children each (Notion's nesting limit per request)."""
    out = []
    for i in range(0, max(len(children), 1), 100):
        part = children[i : i + 100] or [block("paragraph", rt("—"))]
        label = title if i == 0 else f"{title} ({i // 100 + 1})"
        out.append({"object": "block", "type": "toggle", "toggle": {"rich_text": rt(label[:MAX_TEXT]), "children": part}})
    return out


def _text_paragraphs(text: str, size: int = 1800) -> list[dict]:
    paras, buf = [], ""
    for line in (text or "").splitlines():
        if len(buf) + len(line) > size and buf:
            paras.append(buf)
            buf = ""
        buf += line + "\n"
    if buf.strip():
        paras.append(buf)
    return [block("paragraph", rt(p.strip()[:MAX_TEXT])) for p in paras if p.strip()]


def _transcript_paragraphs(segments: list[dict], every: float = 60.0) -> list[dict]:
    out, buf, start = [], [], None
    for s in segments:
        if start is None:
            start = s["start"]
        if buf and s["start"] - start >= every:
            out.append(block("paragraph", rt(f"{mmss(start)} " + " ".join(buf))))
            buf, start = [], s["start"]
        buf.append(s["text"])
    if buf:
        out.append(block("paragraph", rt(f"{mmss(start)} " + " ".join(buf))))
    return out


def blocks(lesson: dict, rep: dict, run: dict, lang: str, uploads: list[tuple[str, str]] | None = None) -> list[dict]:
    T = H.get(lang, H["pl"])
    crumb = " › ".join(x for x in [lesson["site"], lesson.get("section"), lesson.get("title")] if x)
    out = [block("callout", rt(f"{T['intro']}: {crumb}. ") + rt("Otwórz lekcję" if lang == "pl" else "Open the lesson", link=lesson["url"]),
                 icon={"type": "emoji", "emoji": "🎓"})]
    if any(v["status"] != "done" for v in lesson.get("videos") or []) or any(d.get("error") for d in lesson.get("docs") or []):
        out.append(block("callout", rt(T["partial"]), icon={"type": "emoji", "emoji": "⚠️"}))
    out += [h2(T["about"]), *para(rep.get("one_line") or ""), *para(rep.get("about") or "")]
    out += [h2(T["text"]), *para(rep.get("text_summary") or "")]
    out += [h2(T["visual"]), *para(rep.get("visual_summary") or "")]
    for upload_id, caption in uploads or []:
        out.append(image_block(upload_id, caption))
    out += [h2(T["points"]), *bullets(rep.get("key_points") or [])]
    out += [h2(T["life"]), *bullets(rep.get("life_applications") or [])]
    if rep.get("action_items"):
        out += [h2(T["actions"]), *bullets(rep["action_items"], "to_do")]
    res_items = []
    for r in rep.get("resources") or []:
        label = f"{r.get('title') or r.get('url')}" + (f": {r['note']}" if r.get("note") else "")
        res_items.append(block("bulleted_list_item", rt(label[:MAX_TEXT], link=r.get("url") if str(r.get("url", "")).startswith("http") else None)))
    if res_items:
        out += [h2(T["resources"]), *res_items]
    got = [d for d in lesson.get("docs") or []]
    if got:
        out.append(h2(T["files"]))
        for d in got:
            name = d.get("name") or d.get("label") or d["url"]
            note = f" ({d['error']})" if d.get("error") else ""
            out.append(block("bulleted_list_item", rt(f"{name}{note}"[:MAX_TEXT], link=d["url"])))
    if rep.get("prerequisites") or rep.get("difficulty"):
        out += [h2(T["prereq"]), *bullets(rep.get("prerequisites") or [])]
        if rep.get("difficulty"):
            out += para(f"{T['level']}: {rep['difficulty']}")
    if rep.get("notable_quotes"):
        q = []
        for x in rep["notable_quotes"]:
            when = f" ({x.get('source', '')}{', ' + mmss(x['t']) if isinstance(x.get('t'), (int, float)) else ''})"
            q.append(block("quote", rt(f"„{x['quote']}”{when}")))
        out += [h2(T["quotes"]), *q]
    if rep.get("related_suggestions"):
        out += [h2(T["related"]), *bullets(rep["related_suggestions"])]
    tags = ", ".join(rep.get("tags") or [])
    meta = f"Tagi: {tags}\nModele: {', '.join(run.get('models') or [])}\nKoszt: ${run.get('cost_usd', 0):.4f}, {run.get('seconds', 0)} s"
    out += [block("paragraph", rt(meta))]
    out.append(h2(T["sources"]))
    out += toggle(T["page_text"], _text_paragraphs(lesson.get("page_text") or ""))
    for v in lesson.get("videos") or []:
        title = f"{T['video']} {v['n']}: {v.get('title') or v['url']}"
        if v["status"] != "done":
            out.append(block("paragraph", rt(f"{title}: {T['drm'] if v['status'] == 'drm' else T['missing']} ({(v.get('error') or '')[:300]})")))
            continue
        out += toggle(f"{title} ({T['transcript']}: {v['transcript']['source']})", _transcript_paragraphs(v["transcript"]["segments"]))
    for d in lesson.get("docs") or []:
        if d.get("text"):
            out += toggle(f"{T['file']}: {d.get('name')}", _text_paragraphs(d["text"][:150000]))
    return out


def write_lesson(cfg: dict, pdir: Path, lesson: dict, rep: dict, run: dict, status: str) -> str:
    nt = _client(cfg)
    page_id = nt.upsert(lesson["key"], properties(lesson, rep, run, status))
    uploads: list[tuple[str, str]] = []
    pics = [(pdir / f"video{v['n']:02d}" / f["path"], f.get("caption") or "") for v in lesson.get("videos") or []
            for f in v.get("frames") or [] if f.get("caption") and f.get("adds_information") is not False]
    pics += [(pdir / s["path"], s["caption"]) for s in lesson.get("screens") or [] if s.get("caption")][:2]
    for path, caption in pics[: cfg.get("notion_max_frame_images", 6) + 2]:
        try:
            uploads.append((nt.upload(path), caption))
        except Exception:
            continue
    nt.clear(page_id)
    nt.append(page_id, blocks(lesson, rep, run, cfg["report_language"], uploads))
    return nt.page_url(page_id)


def markdown(lesson: dict, rep: dict, run: dict, notion_url: str | None = None) -> str:
    L = [f"# {lesson.get('title')}", "", f"{lesson['site']} › {lesson.get('section') or ''}", f"Lekcja: {lesson['url']}"]
    if notion_url:
        L.append(f"Notion: {notion_url}")
    L += ["", f"**{rep.get('one_line', '')}**", "", rep.get("about", ""), "", "## Czego uczy", rep.get("text_summary", ""),
          "", "## Co było widać", rep.get("visual_summary", ""), "", "## Najważniejsze punkty"]
    L += [f"- {x}" for x in rep.get("key_points") or []]
    L += ["", "## Jak możesz to wykorzystać", *[f"- {x}" for x in rep.get("life_applications") or []]]
    if rep.get("action_items"):
        L += ["", "## Do zrobienia", *[f"- [ ] {x}" for x in rep["action_items"]]]
    if rep.get("resources"):
        L += ["", "## Materiały, narzędzia i linki", *[f"- {r.get('title') or ''} {r.get('url') or ''} {r.get('note') or ''}".strip()
                                                          for r in rep["resources"]]]
    if lesson.get("docs"):
        L += ["", "## Pobrane pliki", *[f"- {d.get('name') or d['url']}: {d.get('path') or d.get('error')}" for d in lesson["docs"]]]
    if rep.get("prerequisites"):
        L += ["", "## Wymagania", *[f"- {x}" for x in rep["prerequisites"]]]
    if rep.get("related_suggestions"):
        L += ["", "## Powiązane tematy", *[f"- {x}" for x in rep["related_suggestions"]]]
    L += ["", f"Tagi: {', '.join(rep.get('tags') or [])}", f"Poziom: {rep.get('difficulty', '')}",
          f"Modele: {', '.join(run.get('models') or [])}, koszt ${run.get('cost_usd', 0):.4f}"]
    for v in lesson.get("videos") or []:
        L += ["", f"## Wideo {v['n']}: {v.get('title') or v['url']}"]
        if v["status"] != "done":
            L.append(f"({v['status']}: {v.get('error') or ''})")
            continue
        L += [f"[{mmss(s['start'])}] {s['text']}" for s in v["transcript"]["segments"]]
    L += ["", "## Tekst strony", "", lesson.get("page_text") or ""]
    return "\n".join(L) + "\n"


# -- course overview ----------------------------------------------------------------------

def write_course(cfg: dict, site: str, course: dict, lessons: list[dict]) -> str:
    """One row (Rodzaj = kurs) with the course overview and links to every lesson report."""
    nt = _client(cfg)
    T = H.get(cfg["report_language"], H["pl"])
    key = f"course-{site}"
    rep = course["report"]
    props = {
        "Nazwa": {"title": [{"text": {"content": f"{T['course']}: {course.get('title') or site}"[:1900]}}]},
        "Klucz": _text(key), "Strona": {"select": {"name": site[:100]}}, "Link": {"url": course["start_url"]},
        "Status": {"select": {"name": STATUS["done"]}}, "Rodzaj": {"select": {"name": KIND["course"]}},
        "Tagi": {"multi_select": [{"name": t[:100]} for t in rep.get("tags", [])[:20]]},
        "Jedno zdanie": _text(rep.get("one_line") or ""), "Kolejność": {"number": 0},
        "Filmy": {"number": sum(x.get("videos", 0) for x in lessons)}, "Pliki": {"number": sum(x.get("files", 0) for x in lessons)},
        "Model": _text(", ".join(course["run"].get("models") or [])),
        "Koszt USD": {"number": round(course["run"].get("cost_usd", 0) + sum(x.get("cost_usd") or 0 for x in lessons), 4)},
        "Przetworzono": {"date": {"start": datetime.now(timezone.utc).isoformat(timespec="seconds")}},
    }
    page_id = nt.upsert(key, props)
    out = [block("callout", rt(f"{T['course']}: {site}. ") + rt(course["start_url"], link=course["start_url"]), icon={"type": "emoji", "emoji": "📚"}),
           h2(T["about"]), *para(rep.get("one_line") or ""), *para(rep.get("about") or ""),
           h2(T["text"]), *para(rep.get("text_summary") or ""),
           h2(T["points"]), *bullets(rep.get("key_points") or []),
           h2(T["life"]), *bullets(rep.get("life_applications") or [])]
    if rep.get("action_items"):
        out += [h2(T["actions"]), *bullets(rep["action_items"], "to_do")]
    out.append(h2(T["modules"]))
    section = None
    for x in lessons:
        if x.get("section") != section:
            section = x.get("section")
            out.append(block("heading_3", rt(section or "—")))
        label = f"{x.get('title')}: {x.get('one_line') or ''}"[:MAX_TEXT]
        out.append(block("bulleted_list_item", rt(label, link=x.get("notion_url") or x.get("url"))))
    nt.clear(page_id)
    nt.append(page_id, out)
    return nt.page_url(page_id)
