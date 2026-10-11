from ytdigest.queue import USER_PRIORITY, Queue


def test_queue_priorities_and_retries(tmp_path):
    q = Queue(tmp_path / "q.db")
    assert q.add("aaaaaaaaaaa", "u1", playlist="A")
    assert not q.add("aaaaaaaaaaa", "u1", playlist="B")
    q.add("bbbbbbbbbbb", "u2", priority=USER_PRIORITY)
    row = q.next()
    assert row["video_id"] == "bbbbbbbbbbb"
    q.finish("bbbbbbbbbbb", {"status": "done", "notion_url": "n", "cost_usd": 0.01})
    row = q.next()
    assert row["video_id"] == "aaaaaaaaaaa"
    q.finish("aaaaaaaaaaa", {"status": "failed", "error": "x"})
    assert q.stats()["queued"]["count"] == 1  # retried
    for _ in range(2):
        q.next()
        q.finish("aaaaaaaaaaa", {"status": "failed", "error": "x"})
    assert q.stats()["failed"]["count"] == 1
    assert q.next() is None
    import json
    pls = json.loads(q.db.execute("select playlists from videos where video_id='aaaaaaaaaaa'").fetchone()[0])
    assert pls == ["A", "B"]
