"""Which pages to digest, digesting them in course order, and the course overview."""

from __future__ import annotations

import json
import time
from pathlib import Path

from ytdigest import gate, llm, routing

from . import crawl, lesson, notion_out

SYSTEM = ("You write the overview of a whole online course from the reports of its lessons, so the reader "
          "knows what the course teaches, how it is organised and what is worth applying. Answer with one JSON object only.")


def wanted(rec: dict, include_index: bool = False) -> bool:
    if rec.get("status") != "mapped":
        return False
    if rec.get("kind") == "index" and not include_index:
        return False
    return bool(rec.get("videos") or rec.get("docs") or (rec.get("text_chars") or 0) >= 300)


def pending(m: dict, redo: bool = False, include_index: bool = False) -> list[dict]:
    return [p for p in m["pages"] if wanted(p, include_index)
            and (redo or (p.get("digest") or {}).get("status") not in ("done", "partial"))]


def digest_site(cfg: dict, site: str, *, keys: list[str] | None = None, limit: int | None = None, model: str | None = None,
                write_notion: bool = True, redo: bool = False, include_index: bool = False, idle_only: bool = False,
                deadline: float | None = None, tag: str = "manual", log=print) -> list[dict]:
    m = crawl.load_map(cfg, site)
    if not m:
        raise SystemExit(f"no map for '{site}': run `sitedigest map URL` first")
    todo = [p for p in m["pages"] if p["key"] in keys or p["url"] in keys] if keys else pending(m, redo, include_index)
    results = []
    for rec in todo[: limit or None]:
        if deadline and time.time() > deadline:
            log("time limit reached")
            break
        if idle_only:
            ok, why = gate.check(cfg)
            if not ok:
                log("gate closed: " + "; ".join(w for w in why if w.startswith("NO")))
                break
        try:
            res = lesson.digest(cfg, site, rec, model=model, write_notion=write_notion, tag=tag, log=log)
        except Exception as exc:
            res = {"key": rec["key"], "status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:400]}"}
            log(f"[{rec['key']}] failed: {res['error']}")
        with crawl.map_lock(cfg, site):  # parallel workers / the harvest sync may write too
            m2 = crawl.load_map(cfg, site) or m  # the map may have been extended meanwhile
            for p in m2["pages"]:
                if p["key"] == rec["key"]:
                    p["digest"] = res
            crawl.save_map(cfg, site, m2)
        results.append(res)
    return results


def overview(cfg: dict, site: str, *, model: str | None = None, title: str | None = None, write_notion: bool = True,
             log=print) -> dict:
    m = crawl.load_map(cfg, site)
    lessons = []
    for p in m["pages"]:
        d = p.get("digest") or {}
        rp = crawl.page_dir(cfg, site, p["key"]) / "report.json"
        if d.get("status") not in ("done", "partial") or not rp.is_file():
            continue
        rep = json.loads(rp.read_text(encoding="utf-8"))["report"]
        lessons.append({"key": p["key"], "title": p.get("title"), "section": p.get("section"), "url": p["url"],
                        "notion_url": d.get("notion_url"), "one_line": rep.get("one_line"), "key_points": rep.get("key_points", [])[:6],
                        "tags": rep.get("tags", []), "difficulty": rep.get("difficulty"), "videos": d.get("videos", 0),
                        "files": d.get("files", 0), "cost_usd": d.get("cost_usd", 0)})
    if not lessons:
        raise SystemExit(f"no digested lessons for '{site}' yet")
    ref = model or cfg["site"].get("report_model") or routing.load(cfg)["default"]["report"]
    client = llm.Client(cfg, ledger=Path(cfg["data_dir"]) / "spend.jsonl", tag="manual")
    body = "\n".join(f"- [{x['section'] or '-'}] {x['title']}: {x['one_line']} | " + "; ".join(x["key_points"]) for x in lessons)
    lang = "Polish" if cfg["report_language"] == "pl" else "English"
    user = (f"Course site: {site} ({m['start_url']}). {len(lessons)} lesson reports in course order:\n{body[:120000]}\n\n"
            f"Write in {lang}. Return JSON with: one_line, about (who it is for, 2-4 sentences), text_summary (what the "
            "course teaches, module by module, 2-5 paragraphs), key_points[] (8-15 most valuable takeaways), "
            "life_applications[] (3-6), action_items[] (3-8, a practical plan), tags[] (6-12 lowercase), gaps[] "
            "(what the course leaves out or gets wrong, if anything), confidence.")
    rep = client.json(ref, SYSTEM, user, max_tokens=6000)
    course = {"title": title or m["pages"][0].get("title") or site, "start_url": m["start_url"], "report": rep,
              "run": {"models": client.usage.models, "cost_usd": client.usage.cost_usd}}
    if write_notion:
        course["notion_url"] = notion_out.write_course(cfg, site, course, lessons)
        log(f"course overview: {course['notion_url']}")
    (crawl.map_path(cfg, site).parent / "course.json").write_text(json.dumps(course, ensure_ascii=False, indent=1), encoding="utf-8")
    return course


def sites(cfg: dict) -> list[str]:
    root = Path(cfg["site"]["root"])
    return sorted(p.parent.name for p in root.glob("*/map.json"))
