"""On the PC: free disk when D: runs low. Deletes the PC copy of a lesson video once its
transcript exists here and the VM already has the video (or digested and pruned it), i.e.
nothing on the PC needs it any more. The lesson can be downloaded again from the platform.
Lessons of --keep courses keep their originals. Uses the VM file list of the last
sync_to_vm.sh run (.vm_files.txt).

  python pc_prune.py [--site akademiasaas-pl] [--min-free-gb 25] [--keep od-developera-do-foundera-3.0 ...]
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(r"D:\courses")
VIDEO = (".mp4", ".mkv", ".webm", ".ts", ".m4a")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="akademiasaas-pl")
    ap.add_argument("--min-free-gb", type=float, default=25)
    ap.add_argument("--keep", nargs="*", default=["od-developera-do-foundera-3.0", "akademia-globalnego-startupu"])
    a = ap.parse_args()
    free = shutil.disk_usage(ROOT).free / 1e9
    if free >= a.min_free_gb:
        print(f"pc_prune: {free:.0f} GB free, nothing to do")
        return
    out = ROOT / a.site
    vm = set((out / ".vm_files.txt").read_text(encoding="utf-8").split()) if (out / ".vm_files.txt").is_file() else set()
    m = json.loads((out / ".map.snapshot.json").read_text(encoding="utf-8"))
    freed = n = 0
    for p in m["pages"]:
        if any(k in p.get("course_url", "") for k in a.keep):
            continue
        pre = out / "pages" / p["key"] / "prefetch"
        if not pre.is_dir() or not list(pre.glob("*.vtt")):
            continue
        for f in pre.iterdir():
            if f.suffix.lower() not in VIDEO:
                continue
            rel = f"pages/{p['key']}/prefetch/{f.name}"
            if rel in vm or f"pages/{p['key']}/prefetch/.pruned" in vm:
                freed += f.stat().st_size
                f.unlink()
                (pre / ".pc_pruned").write_text("video deleted on the PC after it reached the VM (disk space)\n")
                n += 1
    print(f"pc_prune: {free:.0f} GB free, deleted {n} videos, {freed / 1e9:.1f} GB")


if __name__ == "__main__":
    main()
