"""On the VM: merge the PC harvester's map (map.pc.json) into sitedigest's map.json.
PC fields win (title, section, videos, docs, downloaded), the VM keeps 'digest'.
Pages whose video or transcript is not on the VM yet stay 'awaiting_download', so
digest workers only pick lessons that are complete here. Runs under sitedigest's
map lock, so it never overwrites results that parallel workers are writing."""
import fcntl
import json
from pathlib import Path

with open("map.lock", "w") as lk:
    fcntl.flock(lk, fcntl.LOCK_EX)
    pc = json.loads(Path("map.pc.json").read_text(encoding="utf-8"))
    old = json.loads(Path("map.json").read_text(encoding="utf-8")) if Path("map.json").is_file() else {"pages": []}
    digests = {p["key"]: p["digest"] for p in old["pages"] if p.get("digest")}
    ready = 0
    for p in pc["pages"]:
        local = [v for v in p.get("videos") or [] if v.startswith("local:")]
        # the video and its transcript (VTT from the PC GPU) must both be here
        # (a video pruned after its digest counts as present: prefetch/.pruned)
        have = all(((Path("pages") / p["key"] / v[len("local:"):]).is_file()
                    or (Path("pages") / p["key"] / v[len("local:"):]).parent.joinpath(".pruned").is_file())
                   and any((Path("pages") / p["key"] / v[len("local:"):]).parent.glob("*.vtt")) for v in local)
        ok = p.get("downloaded") and have and (Path("pages") / p["key"] / "text.md").is_file()
        p["status"] = "mapped" if ok else "awaiting_download"
        ready += bool(ok)
        if p["key"] in digests:
            p["digest"] = digests[p["key"]]
    Path("map.json.merge.tmp").write_text(json.dumps(pc, ensure_ascii=False, indent=1), encoding="utf-8")
    Path("map.json.merge.tmp").replace("map.json")
    fcntl.flock(lk, fcntl.LOCK_UN)
done = sum(1 for p in pc["pages"] if (p.get("digest") or {}).get("status") in ("done", "partial"))
print(f"map merged: {len(pc['pages'])} lessons, {ready} ready on the VM, {done} digested")
