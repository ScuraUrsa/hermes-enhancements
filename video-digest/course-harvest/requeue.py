"""On the VM: send lessons back to the digest pool (e.g. after a mind-map screenshot
was added). Marks their digest as 'requeued' under the map lock; the pool picks them up.

  python3 requeue.py --course-url-part od-developera-do-foundera-3.0 --with-file shot.jpg
"""
import argparse
import fcntl
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--course-url-part", required=True)
ap.add_argument("--with-file", default="", help="only lessons whose page folder has this file")
a = ap.parse_args()
n = 0
with open("map.lock", "w") as lk:
    fcntl.flock(lk, fcntl.LOCK_EX)
    m = json.loads(Path("map.json").read_text(encoding="utf-8"))
    for p in m["pages"]:
        if a.course_url_part not in p.get("course_url", ""):
            continue
        if a.with_file and not (Path("pages") / p["key"] / a.with_file).is_file():
            continue
        d = p.get("digest") or {}
        if d.get("status") in ("done", "partial"):
            p["digest"] = {**d, "status": "requeued", "previous": d.get("status")}
            n += 1
    Path("map.json.requeue.tmp").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    Path("map.json.requeue.tmp").replace("map.json")
    fcntl.flock(lk, fcntl.LOCK_UN)
print(f"requeued {n} lessons")
