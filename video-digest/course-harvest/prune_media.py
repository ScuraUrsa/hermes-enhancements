"""On the VM: delete the video copies of lessons that are fully digested (the originals stay
on the PC; transcripts, frames' captions and reports stay here). Leaves a prefetch/.pruned
marker so sync_to_vm.sh does not copy the video back. Lessons that are queued again
(e.g. 'requeued' for a mind map) keep their video.

  python3 prune_media.py [--dry-run]
"""
import argparse
import fcntl
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()
with open("map.lock", "w") as lk:
    fcntl.flock(lk, fcntl.LOCK_SH)
    m = json.loads(Path("map.json").read_text(encoding="utf-8"))
    fcntl.flock(lk, fcntl.LOCK_UN)
freed = n = 0
for p in m["pages"]:
    if (p.get("digest") or {}).get("status") not in ("done", "partial"):
        continue
    pdir = Path("pages") / p["key"]
    # extracted frames (100-500 jpg per lesson) are only needed until the frames are described
    for fr in pdir.glob("video*/frames"):
        for f in fr.glob("*.jpg"):
            freed += f.stat().st_size
            if not a.dry_run:
                f.unlink()
    pre = pdir / "prefetch"
    vids = [f for f in pre.glob("video.*") if f.suffix.lower() in (".mp4", ".mkv", ".webm", ".ts", ".m4a")] if pre.is_dir() else []
    if not vids:
        continue
    for f in vids:
        freed += f.stat().st_size
        if not a.dry_run:
            f.unlink()
    if not a.dry_run:
        (pre / ".pruned").write_text("video deleted after digest; original on the PC\n")
    n += 1
print(f"{'would free' if a.dry_run else 'freed'} {freed / 1e9:.1f} GB from {n} lessons")
