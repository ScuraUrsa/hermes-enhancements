"""Capture public Whimsical mind maps linked from lessons: open the board, expand every
collapsed branch (the coloured count bubbles are drawn on a canvas, so they are found
in the screenshot and clicked), zoom to fit and save a screenshot.

The image becomes the lesson's page screenshot (pages/<key>/shot.jpg), which
sitedigest slices and describes with the vision model, so the map's content lands
in the lesson report. Only GET + clicks on the public, read-only board.

  python whimsical.py [--site akademiasaas-pl] [--course od-developera-do-foundera-3.0] [--redo]
"""

from __future__ import annotations

import argparse
import io
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(r"D:\courses")
W, H = 2400, 1600


def bubbles(png: bytes) -> list[tuple[int, int]]:
    """Centres of small filled colour circles (collapsed-branch counters)."""
    a = np.asarray(Image.open(io.BytesIO(png)).convert("RGB")).astype(int)
    sat = (a.max(axis=2) - a.min(axis=2)) > 90
    sat[:80, :] = False  # toolbar
    ys, xs = np.nonzero(sat)
    cells: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for y, x in zip(ys[::2], xs[::2]):
        cells.setdefault((y // 24, x // 24), []).append((y, x))
    out = []
    for pts in cells.values():
        if len(pts) < 60:
            continue
        p = np.array(pts)
        h = p[:, 0].max() - p[:, 0].min()
        w = p[:, 1].max() - p[:, 1].min()
        if 10 <= h <= 24 and 10 <= w <= 24 and abs(h - w) <= 5:
            cy, cx = p.mean(axis=0)
            if not any(abs(cx - ox) < 15 and abs(cy - oy) < 15 for ox, oy in out):
                out.append((int(cx), int(cy)))
    return out


def capture(page, url: str, out: Path) -> int:
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    clicked = 0
    for _ in range(8):
        pts = bubbles(page.screenshot(type="png"))
        if not pts:
            break
        for x, y in pts:
            page.mouse.click(x, y)
            page.wait_for_timeout(300)
            clicked += 1
        page.wait_for_timeout(1200)
        page.keyboard.press("Shift+1")  # zoom to fit after each round
        page.wait_for_timeout(1200)
    page.keyboard.press("Shift+1")
    page.wait_for_timeout(1500)
    page.screenshot(path=str(out), type="jpeg", quality=88)
    return clicked


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="akademiasaas-pl")
    ap.add_argument("--course", default="")
    ap.add_argument("--redo", action="store_true")
    a = ap.parse_args()
    site = ROOT / a.site
    m = json.loads((site / "map.json").read_text(encoding="utf-8"))
    todo = []
    for p in m["pages"]:
        if a.course and a.course not in p["course_url"]:
            continue
        tm = site / "pages" / p["key"] / "text.md"
        if not tm.is_file():
            continue
        urls = list(dict.fromkeys(re.findall(r"https://whimsical\.com/[\w\-/]+", tm.read_text(encoding="utf-8"))))
        if urls and (a.redo or not (site / "pages" / p["key"] / "shot.jpg").is_file()):
            todo.append((p, urls))
    print(f"{len(todo)} lessons with Whimsical maps", flush=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome", headless=True)
        page = b.new_page(viewport={"width": W, "height": H})
        for n, (p, urls) in enumerate(todo, 1):
            pdir = site / "pages" / p["key"]
            shots = []
            for i, u in enumerate(urls[:3]):
                f = pdir / f"whimsical{i + 1}.jpg"
                try:
                    c = capture(page, u, f)
                    shots.append(f)
                    print(f"{n}/{len(todo)} {p['title'][:50]} | map {i + 1}: {c} branches opened", flush=True)
                except Exception as exc:
                    print(f"{n}/{len(todo)} {p['title'][:50]} | map {i + 1} failed: {str(exc)[:120]}", flush=True)
            if shots:  # stack the maps into the page screenshot sitedigest describes
                ims = [Image.open(s) for s in shots]
                canvas = Image.new("RGB", (max(i.width for i in ims), sum(i.height for i in ims)), "white")
                y = 0
                for im in ims:
                    canvas.paste(im, (0, y))
                    y += im.height
                canvas.save(pdir / "shot.jpg", quality=88)
        b.close()


if __name__ == "__main__":
    main()
