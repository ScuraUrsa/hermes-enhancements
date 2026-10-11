from datetime import datetime, timezone

from ytdigest import discover


def test_iso_duration():
    assert discover._seconds("PT1H2M3S") == 3723 and discover._seconds("PT59S") == 59 and discover._seconds("P1DT1S") == 86401


def test_run_dedupes_and_stops_at_cutoff(cfg, monkeypatch, tmp_path):
    monkeypatch.setattr(discover, "token_for", lambda c, a: "t")
    monkeypatch.setattr(discover, "api_playlists", lambda t, liked: [("PL1", "Openclaw")])
    monkeypatch.setattr(discover, "_paged", lambda t, path, p: [{"contentDetails": {"videoId": "aaaaaaaaaaa"}}]
                        if path == "playlistItems" else [{"snippet": {"resourceId": {"channelId": "C2"}, "title": "Sub"}}])
    monkeypatch.setattr(discover, "video_channels", lambda t, ids: {"C1": "Saved chan", "C3": "Muzyka - Topic"})
    monkeypatch.setattr(discover, "uploads_since", lambda t, cids, cutoff, log=print: [
        {"video_id": "bbbbbbbbbbb", "published": "2026-09-01", "channel_id": "C1", "channel": "Saved chan", "title": "x"},
        {"video_id": "bbbbbbbbbbb", "published": "2026-09-01", "channel_id": "C1", "channel": "Saved chan", "title": "x"},
        {"video_id": "ccccccccccc", "published": "2026-08-01", "channel_id": "C2", "channel": "Sub", "title": "y"}])
    monkeypatch.setattr(discover, "durations", lambda t, ids: {"bbbbbbbbbbb": 600, "ccccccccccc": 30})
    res = discover.run(cfg, "fjkazmierczak", 730, tmp_path / "d.tsv", skip_shorts=True, log=lambda m: None)
    assert [r["video_id"] for r in res["rows"]] == ["bbbbbbbbbbb"]
    assert res["summary"]["channels"] == 2 and res["summary"]["shorts"] == 1  # Topic channel dropped
    assert (tmp_path / "d.tsv").read_text().count("\n") == 2
