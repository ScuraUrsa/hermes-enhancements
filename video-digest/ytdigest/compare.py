"""Run the same videos through several models and compare cost, tokens, time and output.

  ytdigest compare --refs claude-code:sonnet,claude-code:haiku --file ten.txt [--notion-parent PAGE_ID]

Each model gets its own data dir (compare/<stamp>/<label>/), the same frames
setting and the same prompts; report and frame descriptions both use the model
under test. Nothing is written to the "Raporty wideo" database or to YouTube.
Output: results.json, comparison.md and, with --notion-parent, a Notion page
with the table and both reports per video side by side (as toggles).
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from . import fetch, pipeline, render


def _label(ref: str) -> str:
    return ref.split(":", 1)[-1].replace(":", "-").replace("/", "-")


def run(cfg: dict, urls: list[str], refs: list[str], log=print, out_dir: Path | None = None) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    out_dir = out_dir or Path(cfg["data_dir"]) / "compare" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for url in urls:
        vid = fetch.video_id(url)
        row = {"video_id": vid, "url": fetch.watch_url(vid), "runs": {}}
        for ref in refs:
            c = copy.deepcopy(cfg)
            c["data_dir"] = str(out_dir / _label(ref))
            c["topic_routes"] = {}
            c["processed_playlist"] = {"enabled": False}
            c["clean_auto_transcript"] = False
            log(f"[{vid}] === {ref}")
            res = pipeline.safe_process(url, c, tag="compare", write_notion=False, force_analyzer="frames",
                                        route_override={"report": ref, "vision": ref, "vision_strict": True}, log=log)
            rep_path = Path(c["data_dir"]) / "bundles" / vid / "report.json"
            rep = json.loads(rep_path.read_text(encoding="utf-8"))["report"] if rep_path.is_file() else {}
            row["title"] = row.get("title") or res.get("title")
            row["video_type"] = row.get("video_type") or res.get("video_type")
            u = (res.get("usage") or {}).get(ref, {})
            row["runs"][ref] = {
                "status": res.get("status"), "error": res.get("error"), "seconds": res.get("seconds"),
                "degraded": res.get("degraded"), "calls": u.get("calls", 0),
                "input_tokens": u.get("input_tokens", 0), "output_tokens": u.get("output_tokens", 0),
                "cache_read_tokens": u.get("cache_read_tokens", 0), "cache_write_tokens": u.get("cache_write_tokens", 0),
                "api_equiv_usd": u.get("api_equiv_usd", 0.0), "model_seconds": u.get("seconds", 0.0),
                "other_models_usd": round((res.get("cost_usd") or 0.0), 4),
                "report_chars": len(res.get("report_md") or ""), "key_points": len(rep.get("key_points") or []),
                "tags": len(rep.get("tags") or []), "frames_captioned": _captioned(Path(c["data_dir"]), vid),
                "report_md": str(Path(c["data_dir"]) / "bundles" / vid / "report.md"),
            }
        rows.append(row)
        _write(out_dir, refs, rows)  # keep partial results if a later video hangs
    return {"dir": str(out_dir), "rows": rows}


def _captioned(data_dir: Path, vid: str) -> str:
    p = data_dir / "bundles" / vid / "bundle.json"
    if not p.is_file():
        return "0/0"
    frames = json.loads(p.read_text(encoding="utf-8")).get("frames") or []
    return f"{sum(1 for f in frames if f.get('caption'))}/{len(frames)}"


def totals(rows: list[dict], refs: list[str]) -> dict:
    out = {}
    for ref in refs:
        rs = [r["runs"][ref] for r in rows if ref in r["runs"]]
        out[ref] = {k: round(sum(x.get(k) or 0 for x in rs), 4) for k in (
            "calls", "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "api_equiv_usd", "seconds")}
        out[ref]["ok"] = sum(1 for x in rs if x["status"] == "done" and not x.get("degraded"))
        out[ref]["videos"] = len(rs)
    return out


def markdown(rows: list[dict], refs: list[str]) -> str:
    cols = ["video", "type"] + [f"{_label(r)} {k}" for r in refs for k in ("tokens in/out/cache", "API-equiv $", "s", "frames")]
    lines = ["# Model comparison", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        cells = [f"[{(r.get('title') or r['video_id'])[:50]}]({r['url']})", r.get("video_type") or ""]
        for ref in refs:
            x = r["runs"].get(ref, {})
            cells += [f"{x.get('input_tokens', 0)}/{x.get('output_tokens', 0)}/{x.get('cache_read_tokens', 0) + x.get('cache_write_tokens', 0)}",
                      f"{x.get('api_equiv_usd', 0):.4f}", f"{x.get('seconds') or 0:.0f}",
                      x.get("frames_captioned", "") + (" ⚠" if x.get("status") != "done" or x.get("degraded") else "")]
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "## Totals", "", "```json", json.dumps(totals(rows, refs), indent=1), "```"]
    return "\n".join(lines)


def _write(out_dir: Path, refs: list[str], rows: list[dict]) -> None:
    (out_dir / "results.json").write_text(json.dumps({"refs": refs, "rows": rows, "totals": totals(rows, refs)},
                                                     ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "comparison.md").write_text(markdown(rows, refs), encoding="utf-8")


def publish_notion(result: dict, refs: list[str], parent_page_id: str, title: str) -> str:
    """One Notion page: totals, per-video table rows, and both reports as toggles."""
    from .notion import Notion

    nt = Notion("")
    page = nt._req("POST", "/pages", {"parent": {"page_id": parent_page_id},
                                      "properties": {"title": {"title": render.rt(title)}}})
    rows = result["rows"]
    nt.append(page["id"], [render.block("callout", render.rt("Totals: " + json.dumps(totals(rows, refs))),
                                        icon={"type": "emoji", "emoji": "📊"})])
    for r in rows:  # one append per video keeps each request under Notion's 1000-block limit
        blocks = []
        blocks.append(render.h2(f"{r.get('title') or r['video_id']} ({r.get('video_type')})"))
        blocks.append(render.block("paragraph", render.rt(r["url"], link=r["url"])))
        for ref in refs:
            x = r["runs"].get(ref, {})
            summary = (f"{ref}: in {x.get('input_tokens')} / out {x.get('output_tokens')} / cache "
                       f"{x.get('cache_read_tokens', 0) + x.get('cache_write_tokens', 0)} tokens, "
                       f"API-equiv ${x.get('api_equiv_usd', 0):.4f}, {x.get('seconds') or 0:.0f} s, "
                       f"frames {x.get('frames_captioned')}, status {x.get('status')}")
            md = Path(x["report_md"]).read_text(encoding="utf-8") if x.get("report_md") and Path(x["report_md"]).is_file() else ""
            kids = render.para(md[:60000]) or [render.block("paragraph", render.rt(x.get("error") or "no report"))]
            blocks.append(render.block("toggle", render.rt(summary), children=kids[:90]))
        nt.append(page["id"], blocks)
    return page.get("url") or nt.page_url(page["id"])
