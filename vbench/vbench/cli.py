"""vbench command line.

  vbench sample  playlists/*.json --classifier ollama-cloud:gpt-oss:20b -o sample.json
  vbench bundle  sample.json --root bundles [--cookies cookies.txt]
  vbench label   --bundles bundles --labels labels --model claude-code:opus
  vbench review  --labels labels -o labels/REVIEW.md
  vbench run     matrix.toml [--stage report] [--video ID]
  vbench route   results/latest -o routing.json --md LEADERBOARD.md
  vbench check   (validate providers.toml, labels and bundles; no model calls)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .bundle import iter_bundles
from .catalog import Catalog


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vbench", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--providers", type=Path, default=None, help="providers.toml (default: next to the package)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sample", help="pick a stratified sample from playlist dumps")
    s.add_argument("inputs", nargs="+", type=Path)
    s.add_argument("--classifier", default="ollama-cloud:gpt-oss:20b")
    s.add_argument("--per-type", type=int, default=3)
    s.add_argument("--artistic", type=int, default=2)
    s.add_argument("--max-minutes", type=float, default=120)
    s.add_argument("-o", "--out", type=Path, default=Path("sample.json"))

    s = sub.add_parser("bundle", help="download and prepare bundles for a sample (yt-dlp + ffmpeg)")
    s.add_argument("sample", type=Path, help="sample.json, or a single YouTube URL")
    s.add_argument("--root", type=Path, default=Path("bundles"))
    s.add_argument("--cookies", type=Path)
    s.add_argument("--account")

    s = sub.add_parser("label", help="draft answer keys with a strong reference model")
    s.add_argument("--bundles", type=Path, default=Path("bundles"))
    s.add_argument("--labels", type=Path, default=Path("labels"))
    s.add_argument("--model", default="claude-code:opus")
    s.add_argument("--overwrite", action="store_true")
    s.add_argument("--video", action="append")

    s = sub.add_parser("review", help="render answer keys as Markdown for checking by hand")
    s.add_argument("--labels", type=Path, default=Path("labels"))
    s.add_argument("-o", "--out", type=Path, default=None)

    s = sub.add_parser("run", help="run a benchmark matrix")
    s.add_argument("matrix", type=Path)
    s.add_argument("--stage", action="append", help="only these stages")
    s.add_argument("--video", action="append", help="only these video ids")
    s.add_argument("--workers", type=int)

    s = sub.add_parser("route", help="leaderboard + routing.json from results")
    s.add_argument("results", nargs="+", type=Path)
    s.add_argument("-o", "--out", type=Path, default=Path("routing.json"))
    s.add_argument("--md", type=Path, default=Path("LEADERBOARD.md"))
    s.add_argument("--rel", type=float, default=0.92, help="good enough = within this share of the best score")
    s.add_argument("--min-n", type=int, default=2)

    s = sub.add_parser("check", help="validate config, bundles and labels without calling models")
    s.add_argument("--bundles", type=Path, default=Path("bundles"))
    s.add_argument("--labels", type=Path, default=Path("labels"))
    s.add_argument("--matrix", type=Path)

    a = ap.parse_args(argv)
    cat = Catalog.load(a.providers)

    if a.cmd == "sample":
        from .sample import load_candidates, pre_classify, stratify
        items = load_candidates(a.inputs)
        print(f"{len(items)} candidate videos")
        pre_classify(cat, a.classifier, items)
        picked = stratify(items, a.per_type, a.artistic, max_minutes=a.max_minutes)
        a.out.write_text(json.dumps(picked, ensure_ascii=False, indent=1))
        counts: dict[str, int] = {}
        for e in picked:
            counts[e["guess_type"]] = counts.get(e["guess_type"], 0) + 1
        print(f"picked {len(picked)} -> {a.out}: {counts}")
        return 0

    if a.cmd == "bundle":
        from .build_bundle import build
        urls = [str(a.sample)] if str(a.sample).startswith("http") else [e["url"] for e in json.loads(a.sample.read_text())]
        failed = 0
        for u in urls:
            vid = u.rsplit("=", 1)[-1]
            if (a.root / vid / "bundle.json").exists():
                continue
            try:
                b = build(u, a.root, cookies=a.cookies, account=a.account)
                print(f"ok {b.video_id}: {b.transcript.source}, {len(b.transcript.segments)} segments, {len(b.frames)} frames")
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"FAILED {u}: {e}", file=sys.stderr)
        return 1 if failed else 0

    if a.cmd == "label":
        from .labels import draft, problems
        for b in iter_bundles(a.bundles):
            if a.video and b.video_id not in a.video:
                continue
            try:
                lab = draft(cat, a.model, b, a.labels, overwrite=a.overwrite)
                print(f"{b.video_id}: {lab.get('video_type')} kp={len(lab.get('key_points') or [])} "
                      f"vis={len(lab.get('visual_facts') or [])} {problems(lab) or ''}")
            except Exception as e:  # noqa: BLE001
                print(f"FAILED {b.video_id}: {e}", file=sys.stderr)
        return 0

    if a.cmd == "review":
        from .labels import render_markdown
        pages = [render_markdown(json.loads(p.read_text())) for p in sorted(a.labels.glob("*.json"))]
        text = "\n---\n\n".join(pages)
        if a.out:
            a.out.write_text(text)
            print(f"{len(pages)} keys -> {a.out}")
        else:
            print(text)
        return 0

    if a.cmd == "run":
        from .runner import Matrix, Runner
        m = Matrix.load(a.matrix)
        if a.stage:
            m.stages = {k: v for k, v in m.stages.items() if k in a.stage}
        if a.video:
            m.videos = a.video
        if a.workers:
            m.workers = a.workers
        Runner(m, cat).run()
        return 0

    if a.cmd == "route":
        from .route import Rule, build_routing, leaderboard_md, load_rows
        rows = load_rows(a.results)
        routing = build_routing(rows, Rule(rel=a.rel, min_n=a.min_n), source=", ".join(map(str, a.results)))
        a.out.write_text(json.dumps(routing, ensure_ascii=False, indent=1))
        a.md.write_text(leaderboard_md(rows, routing))
        print(f"{len(rows)} rows -> {a.out}, {a.md}")
        return 0

    if a.cmd == "check":
        from .labels import load_label, problems
        from .runner import Matrix
        bad = 0
        for b in iter_bundles(a.bundles) if a.bundles.exists() else []:
            missing = [f.path for f in b.frames if not b.frame_path(f).exists()]
            lab = load_label(a.labels, b.video_id)
            probs = (["no label"] if lab is None else problems(lab)) + ([f"{len(missing)} frame files missing"] if missing else [])
            if lab and not lab.get("reviewed"):
                probs.append("label not reviewed")
            print(f"{b.video_id}: {b.transcript.source}, {len(b.frames)} frames, {b.duration_min:.0f} min {probs or 'ok'}")
            bad += bool(probs)
        if a.matrix:
            m = Matrix.load(a.matrix)
            for stage, refs in [("judge", m.judges), *m.stages.items()]:
                if stage == "transcribe":
                    print(f"  {stage:10s} " + ", ".join(refs))
                    continue
                for ref in refs:
                    try:
                        mod = cat.model(ref)
                        key = mod.cfg.api_key_env
                        warn = f" (set {key})" if key and not mod.cfg.api_key else ""
                        price = "" if ref.split("@")[0] in cat.prices else " (no price: cost shows as ?)"
                        print(f"  {stage:10s} {ref}{warn}{price}")
                    except ValueError as e:
                        bad += 1
                        print(f"  {stage:10s} {ref}: {e}")
        return 1 if bad else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
