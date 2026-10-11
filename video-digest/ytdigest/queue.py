"""SQLite queue of videos. Priority 100 = Filip asked for it (runs now, not
gated); lower = backlog (runs only when the idle gate is open)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

USER_PRIORITY = 100
BACKLOG_PRIORITY = 10
MAX_ATTEMPTS = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  video_id TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  title TEXT,
  account TEXT,
  playlists TEXT DEFAULT '[]',
  priority INTEGER DEFAULT 10,
  status TEXT DEFAULT 'queued',      -- queued | processing | done | artistic | failed
  attempts INTEGER DEFAULT 0,
  last_error TEXT,
  notion_url TEXT,
  cost_usd REAL DEFAULT 0,
  added_at TEXT,
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS videos_pick ON videos(status, priority DESC, added_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Queue:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def add(self, vid: str, url: str, *, title: str | None = None, account: str | None = None,
            playlist: str | None = None, priority: int = BACKLOG_PRIORITY) -> bool:
        """Insert or merge. Returns True when the video is new. Never re-queues
        finished videos; raises the priority if Filip asks again."""
        row = self.db.execute("SELECT * FROM videos WHERE video_id=?", (vid,)).fetchone()
        if row is None:
            self.db.execute(
                "INSERT INTO videos(video_id,url,title,account,playlists,priority,added_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (vid, url, title, account, json.dumps([playlist] if playlist else []), priority, _now(), _now()),
            )
            self.db.commit()
            return True
        pls = json.loads(row["playlists"] or "[]")
        if playlist and playlist not in pls:
            pls.append(playlist)
        self.db.execute(
            "UPDATE videos SET playlists=?, priority=MAX(priority,?), title=COALESCE(title,?), account=COALESCE(account,?), updated_at=? WHERE video_id=?",
            (json.dumps(pls, ensure_ascii=False), priority, title, account, _now(), vid),
        )
        if priority >= USER_PRIORITY and row["status"] == "failed":
            self.db.execute("UPDATE videos SET status='queued', attempts=0 WHERE video_id=?", (vid,))
        self.db.commit()
        return False

    def next(self, min_priority: int = 0) -> sqlite3.Row | None:
        row = self.db.execute(
            "SELECT * FROM videos WHERE status='queued' AND priority>=? AND attempts<? "
            "ORDER BY priority DESC, added_at LIMIT 1",
            (min_priority, MAX_ATTEMPTS),
        ).fetchone()
        if row:
            self.db.execute("UPDATE videos SET status='processing', attempts=attempts+1, updated_at=? WHERE video_id=?",
                            (_now(), row["video_id"]))
            self.db.commit()
        return row

    def finish(self, vid: str, result: dict) -> None:
        status = result.get("status", "failed")
        if status == "failed":
            row = self.db.execute("SELECT attempts FROM videos WHERE video_id=?", (vid,)).fetchone()
            status = "failed" if row and row["attempts"] >= MAX_ATTEMPTS else "queued"
        self.db.execute(
            "UPDATE videos SET status=?, last_error=?, notion_url=COALESCE(?,notion_url), cost_usd=cost_usd+?, "
            "title=COALESCE(?,title), updated_at=? WHERE video_id=?",
            (status, result.get("error"), result.get("notion_url"), float(result.get("cost_usd") or 0),
             result.get("title"), _now(), vid),
        )
        self.db.commit()

    def release_stuck(self, older_than_minutes: int = 120) -> int:
        """Put back videos a crashed worker left in 'processing'."""
        cur = self.db.execute(
            "UPDATE videos SET status='queued' WHERE status='processing' AND updated_at < datetime('now', ?)",
            (f"-{older_than_minutes} minutes",),
        )
        self.db.commit()
        return cur.rowcount

    def stats(self) -> dict:
        rows = self.db.execute("SELECT status, COUNT(*) n, SUM(cost_usd) c FROM videos GROUP BY status").fetchall()
        return {r["status"]: {"count": r["n"], "cost_usd": round(r["c"] or 0, 4)} for r in rows}
