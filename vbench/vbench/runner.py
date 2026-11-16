"""Run a matrix (stages x models x videos x repeats), judge every output, append to results.jsonl.

Re-running the same matrix resumes: rows already in results.jsonl are skipped.
"""

from __future__ import annotations

import json
import re
import threading
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import scoring, stages
from .bundle import VideoBundle, iter_bundles
from .catalog import Catalog
from .labels import load_label
from .providers import ref_options
from .transcribe import score_transcribe, transcribe


@dataclass
class Matrix:
    bundles: Path
    labels: Path
    out: Path
    judges: list[str] = field(default_factory=lambda: ["claude-code:sonnet", "ollama-cloud:deepseek-v4-pro"])
    language: str = "pl"
    repeats: int = 1
    workers: int = 4
    frames_per_min: float = 2.0
    max_frames: int = 40
    report_frames: str = "reference"  # "reference" (from the label) or a vision model ref
    stages: dict[str, list[str]] = field(default_factory=dict)
    videos: list[str] | None = None

    @classmethod
    def load(cls, path: Path, base: Path | None = None) -> "Matrix":
        data = tomllib.loads(Path(path).read_text())
        base = Path(base or Path(path).parent)
        run = data.get("run", {})
        st = {k: list(v.get("models", [])) for k, v in (data.get("stages") or {}).items()}
        return cls(bundles=base / run.get("bundles", "bundles"), labels=base / run.get("labels", "labels"),
                   out=base / run.get("out", "results/latest"),
                   judges=list(run.get("judges") or ["claude-code:sonnet", "ollama-cloud:deepseek-v4-pro"]),
                   language=run.get("language", "pl"), repeats=int(run.get("repeats", 1)),
                   workers=int(run.get("workers", 4)), frames_per_min=float(run.get("frames_per_min", 2.0)),
                   max_frames=int(run.get("max_frames", 40)), report_frames=run.get("report_frames", "reference"),
                   stages=st, videos=run.get("videos"))


def safe(ref: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", ref)


def row_key(r: dict) -> tuple:
    return (r["video_id"], r["stage"], r["ref"], r.get("repeat", 0))


class Runner:
    def __init__(self, m: Matrix, cat: Catalog, log: Callable[[str], None] = print):
        self.m, self.cat, self.log = m, cat, log
        self.m.out.mkdir(parents=True, exist_ok=True)
        self.results = self.m.out / "results.jsonl"
        self._lock = threading.Lock()

    def done_keys(self) -> set[tuple]:
        if not self.results.exists():
            return set()
        return {row_key(json.loads(line)) for line in self.results.read_text().splitlines() if line.strip()}

    def _write(self, row: dict) -> None:
        with self._lock, self.results.open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _save_output(self, b: VideoBundle, stage: str, ref: str, rep: int, payload: Any) -> str:
        p = self.m.out / "outputs" / b.video_id / f"{stage}__{safe(ref)}__r{rep}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
        return str(p.relative_to(self.m.out))

    def jobs(self) -> list[tuple[VideoBundle, dict, str, str, int]]:
        bundles = iter_bundles(self.m.bundles)
        if self.m.videos:
            bundles = [b for b in bundles if b.video_id in set(self.m.videos)]
        done = self.done_keys()
        out = []
        for b in bundles:
            label = load_label(self.m.labels, b.video_id)
            if label is None:
                self.log(f"skip {b.video_id}: no label (run `vbench label` first)")
                continue
            for stage, refs in self.m.stages.items():
                if label.get("is_artistic") and stage not in ("classify", "transcribe"):
                    continue  # artistic videos are only classified, never summarised
                for ref in refs:
                    for rep in range(self.m.repeats):
                        if (b.video_id, stage, ref, rep) not in done:
                            out.append((b, label, stage, ref, rep))
        return out

    def run_one(self, b: VideoBundle, label: dict, stage: str, ref: str, rep: int) -> dict:
        base = {"video_id": b.video_id, "stage": stage, "ref": ref, "repeat": rep,
                "video_type": label.get("video_type"), "is_artistic": bool(label.get("is_artistic")),
                "duration_min": round(b.duration_min, 1), "transcript_source": b.transcript.source,
                "language": label.get("language") or b.language,
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        judged: dict[str, Any] = {}
        if stage == "classify":
            res = stages.classify(self.cat, ref, b)
            judged = scoring.score_classify(label, res.output)
        elif stage == "transcribe":
            res = transcribe(ref, b)
            judged = score_transcribe(res)
        elif stage == "vision":
            res = stages.vision(self.cat, ref, b, self.m.frames_per_min, self.m.max_frames)
            judged = self._judge(lambda j: scoring.judge_vision(self.cat, j, label, res.output) if res.output else (None, {}),
                                 lambda v: scoring.score_vision(label, res.output, v), bool(res.output))
        elif stage in ("report", "video_url"):
            if stage == "video_url":
                res = stages.video_url_report(self.cat, ref, b, self.m.language)
            else:
                frames = self._report_frames(b, label, ref)
                res = stages.report(self.cat, ref, b, label.get("video_type", "other"), frames, self.m.language)
            gradable = res.output is not None and not res.problems
            judged = self._judge(
                lambda j: scoring.judge_report(self.cat, j, label, res.output, b.transcript.text()) if gradable else (None, {}),
                lambda v: scoring.score_report(label, res.output, v, res.problems), gradable)
        else:
            raise ValueError(f"unknown stage {stage}")
        rd = res.to_dict()
        rd["output_file"] = self._save_output(b, stage, ref, rep, rd.pop("output"))
        verdicts = judged.pop("verdicts", None)
        if verdicts:
            self._save_output(b, stage + "_verdict", ref, rep, verdicts)
        row = {**base, **rd, **judged}
        self._write(row)
        return row

    def _judge(self, call: Callable[[str], tuple[dict | None, dict]], score: Callable[[dict | None], dict],
               gradable: bool = True) -> dict:
        """Grade with every judge (different model families, to cancel self-preference) and average."""
        per, verdicts, usage = {}, {}, {}
        for j in self.m.judges:
            v, u = call(j)
            s = score(v)
            per[j], verdicts[j] = s, v
            usage[j] = u
        ok = [s for j, s in per.items() if verdicts[j] is not None]
        if not ok and gradable:  # the judges failed, not the candidate: leave the row out so it is retried
            raise RuntimeError(f"every judge failed: {usage}")
        if not ok:  # gated: invalid output scores 0
            first = next(iter(per.values()))
            return {**first, "judges": per, "judge_usage": usage, "verdicts": verdicts}
        keys = {k for s in ok for k, v in s.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
        avg = {k: round(sum(s[k] for s in ok if s.get(k) is not None) / max(1, sum(1 for s in ok if s.get(k) is not None)), 3)
               for k in keys}
        spread = max(s["score"] for s in ok) - min(s["score"] for s in ok)
        return {**avg, "judge_spread": round(spread, 1), "judges": {j: s.get("score") for j, s in per.items()},
                "judge_usage": usage, "verdicts": verdicts}

    def _report_frames(self, b: VideoBundle, label: dict, ref: str = "") -> list[dict]:
        source = ref_options(ref).get("frames", self.m.report_frames)
        if source == "none":
            return []
        if source == "reference":
            return list(label.get("frame_captions") or [])
        p = self.m.out / "outputs" / b.video_id / f"vision__{safe(source)}__r0.json"
        if not p.exists():
            raise RuntimeError(f"report frames come from {source}, but its vision output for {b.video_id} is missing;"
                               " run the vision stage first")
        data = json.loads(p.read_text())
        return data if isinstance(data, list) else []

    def drop_unavailable(self) -> None:
        """Skip candidates the provider no longer serves, instead of scoring them 0 on every video."""
        refs = sorted({r for refs in self.m.stages.values() for r in refs})
        gone = self.cat.unavailable(refs + list(self.m.judges))
        for ref, why in gone.items():
            self.log(f"skip {ref}: {why}")
        if any(j in gone for j in self.m.judges):
            raise RuntimeError(f"a judge is unavailable: {[j for j in self.m.judges if j in gone]}")
        self.m.stages = {st: [r for r in refs if r not in gone] for st, refs in self.m.stages.items()}

    def run(self, check_live: bool = True) -> int:
        if check_live:
            self.drop_unavailable()
        jobs = self.jobs()
        self.log(f"{len(jobs)} runs to do -> {self.results}")
        n = 0
        with ThreadPoolExecutor(max_workers=self.m.workers) as ex:
            futs = {ex.submit(self.run_one, *j): j for j in jobs}
            for f in as_completed(futs):
                b, _, stage, ref, rep = futs[f]
                try:
                    r = f.result()
                    n += 1
                    self.log(f"[{n}/{len(jobs)}] {b.video_id} {stage:8s} {ref:40s} score={r.get('score')} "
                             f"equiv=${r.get('equiv_usd')} {r.get('error') or ''}")
                except Exception as e:  # keep the matrix going; the row is retried on the next run
                    self.log(f"FAILED {b.video_id} {stage} {ref}: {e!r}")
        return n
