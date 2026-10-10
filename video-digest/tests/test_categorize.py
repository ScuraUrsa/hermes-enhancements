import json

from ytdigest import categorize


def test_categories(tmp_path):
    rows = [
        {"video_id": "a1", "title": "Claude Code agents and MCP servers", "channel": "X", "seconds": 900, "published": "2026-09-01"},
        {"video_id": "a2", "title": "Docker i Kubernetes od zera", "channel": "DevPL", "seconds": 1800, "published": "2026-08-01"},
        {"video_id": "a3", "title": "Jak radzić sobie z lękiem i depresją", "channel": "Psych", "seconds": 1200},
        {"video_id": "a4", "title": "Wybory prezydenckie: debata", "channel": "News", "seconds": 3600},
        {"video_id": "a5", "title": "Band - Song (Official Video)", "channel": "Band", "seconds": 200, "is_music": True},
        {"video_id": "a6", "title": "wow", "channel": "S", "seconds": 30},
        {"video_id": "d1", "title": "Python tutorial part 1", "channel": "DevPL", "seconds": 600},
        {"video_id": "d2", "title": "Python FastAPI backend", "channel": "DevPL", "seconds": 600},
        {"video_id": "d3", "title": "Episode 42", "channel": "DevPL", "seconds": 600},  # vague: channel decides
        {"video_id": "o1", "title": "Mój dzień", "channel": "Vlog", "seconds": 600},
    ]
    f = tmp_path / "in.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows))
    s = categorize.run(f, tmp_path / "out")
    got = {json.loads(l)["video_id"]: json.loads(l)["topic"] for l in (tmp_path / "out" / "categorized.jsonl").read_text().splitlines()}
    assert got["a1"] == "AI" and got["a2"] == "Software" and got["a3"] == "Psychology" and got["a4"] == "Politics"
    assert got["a5"] == "Music & Art" and got["a6"] == "Shorts" and got["d3"] == "Software" and got["o1"] == "Other"
    assert s["_ai_software"]["videos"] == 5
    assert (tmp_path / "out" / "ai_software.txt").read_text().splitlines()[0] == "a1"
