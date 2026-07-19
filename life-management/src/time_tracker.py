"""
Time Tracker Core — 5-minutowe bloki czasu.
Mierzysz każdą minutę swojego życia. Bez tego nie ma optymalizacji.

Usage:
    tracker = TimeTracker()
    block_id = tracker.start("work_deep", planned=True, energy=8)
    # ... pracujesz ...
    tracker.stop(block_id, focus=9, satisfaction=8)
    tracker.summary_today()
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from .schema import get_db, init_db

# Minimalna jednostka czasu: 5 minut
BLOCK_MINUTES = 5

CATEGORIES = [
    "work_deep", "work_shallow", "people", "health",
    "hobby", "learning", "admin", "rest", "waste", "transit", "other"
]

CATEGORY_LABELS = {
    "work_deep": "Głęboka praca",
    "work_shallow": "Płytka praca",
    "people": "Czas z ludźmi",
    "health": "Zdrowie",
    "hobby": "Hobby",
    "learning": "Nauka",
    "admin": "Administracja",
    "rest": "Odpoczynek",
    "waste": "Zmarnowany czas",
    "transit": "Transport",
    "other": "Inne",
}


class TimeTracker:
    """Core time tracking with 5-minute blocks."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.conn = sqlite3.connect(db_path)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.row_factory = sqlite3.Row
        else:
            self.conn = get_db()
        init_db()

    # ─── BLOCK MANAGEMENT ───────────────────────────────────

    def start(
        self,
        category: str,
        person_id: Optional[int] = None,
        planned: bool = False,
        energy: Optional[int] = None,
        notes: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> int:
        """Start a new time block. Returns block_id."""
        if category not in CATEGORIES:
            raise ValueError(f"Invalid category: {category}. Must be one of {CATEGORIES}")

        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """INSERT INTO time_blocks
               (start_time, category, person_id, planned, energy_level, notes, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (now, category, person_id, int(planned), energy, notes, tags),
        )
        self.conn.commit()
        return cursor.lastrowid

    def stop(
        self,
        block_id: int,
        focus: Optional[int] = None,
        satisfaction: Optional[int] = None,
        energy: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Stop a running time block. Returns block summary."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        block = self.conn.execute(
            "SELECT * FROM time_blocks WHERE id = ?", (block_id,)
        ).fetchone()

        if not block:
            raise ValueError(f"Block {block_id} not found")
        if block["end_time"] is not None:
            raise ValueError(f"Block {block_id} already stopped at {block['end_time']}")

        start = datetime.fromisoformat(block["start_time"])
        duration = int((now - start).total_seconds() / 60)

        # Round to nearest 5-minute block
        duration_blocks = max(1, round(duration / BLOCK_MINUTES))
        duration_minutes = duration_blocks * BLOCK_MINUTES

        updates = {"end_time": now_iso, "duration_minutes": duration_minutes}
        if focus is not None:
            updates["focus_level"] = focus
        if satisfaction is not None:
            updates["satisfaction"] = satisfaction
        if energy is not None:
            updates["energy_level"] = energy
        if notes is not None:
            existing = block["notes"] or ""
            updates["notes"] = f"{existing}\n{notes}".strip() if existing else notes

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [block_id]
        self.conn.execute(
            f"UPDATE time_blocks SET {set_clause} WHERE id = ?", values
        )
        self.conn.commit()

        return {
            "id": block_id,
            "category": block["category"],
            "start": block["start_time"],
            "end": now_iso,
            "duration_minutes": duration_minutes,
            "duration_blocks": duration_blocks,
            "focus": focus,
            "satisfaction": satisfaction,
        }

    def get_active_block(self) -> Optional[Dict[str, Any]]:
        """Get currently running block (if any)."""
        row = self.conn.execute(
            "SELECT * FROM time_blocks WHERE end_time IS NULL ORDER BY start_time DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def get_block(self, block_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific block by ID."""
        row = self.conn.execute(
            "SELECT * FROM time_blocks WHERE id = ?", (block_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_blocks(
        self,
        date: Optional[str] = None,
        category: Optional[str] = None,
        person_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get time blocks with optional filters."""
        query = "SELECT * FROM time_blocks WHERE 1=1"
        params: list = []

        if date:
            query += " AND date(start_time) = ?"
            params.append(date)
        if category:
            query += " AND category = ?"
            params.append(category)
        if person_id is not None:
            query += " AND person_id = ?"
            params.append(person_id)

        query += " ORDER BY start_time DESC LIMIT ?"
        params.append(limit)

        return [dict(row) for row in self.conn.execute(query, params).fetchall()]

    # ─── DAILY SUMMARY ──────────────────────────────────────

    def summary_today(self) -> Dict[str, Any]:
        """Get today's time breakdown."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        rows = self.conn.execute(
            """SELECT category, SUM(duration_minutes) as total
               FROM time_blocks
               WHERE date(start_time) = ? AND duration_minutes IS NOT NULL
               GROUP BY category""",
            (today,),
        ).fetchall()

        breakdown = {cat: 0 for cat in CATEGORIES}
        total = 0
        for row in rows:
            breakdown[row["category"]] = row["total"] or 0
            total += row["total"] or 0

        # Active block
        active = self.get_active_block()
        active_info = None
        if active:
            start = datetime.fromisoformat(active["start_time"])
            elapsed = int((datetime.now(timezone.utc) - start).total_seconds() / 60)
            active_info = {
                "id": active["id"],
                "category": active["category"],
                "elapsed_minutes": elapsed,
                "started": active["start_time"],
            }

        return {
            "date": today,
            "total_minutes": total,
            "total_hours": round(total / 60, 1),
            "breakdown": breakdown,
            "breakdown_labels": {k: CATEGORY_LABELS[k] for k in breakdown},
            "active_block": active_info,
            "block_count": len(rows),
        }

    def summary_range(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get time breakdown for a date range."""
        rows = self.conn.execute(
            """SELECT category, SUM(duration_minutes) as total, COUNT(*) as blocks
               FROM time_blocks
               WHERE date(start_time) BETWEEN ? AND ?
                 AND duration_minutes IS NOT NULL
               GROUP BY category""",
            (start_date, end_date),
        ).fetchall()

        breakdown = {cat: 0 for cat in CATEGORIES}
        total = 0
        for row in rows:
            breakdown[row["category"]] = row["total"] or 0
            total += row["total"] or 0

        return {
            "start": start_date,
            "end": end_date,
            "total_minutes": total,
            "total_hours": round(total / 60, 1),
            "breakdown": breakdown,
            "breakdown_labels": {k: CATEGORY_LABELS[k] for k in breakdown},
        }

    def summary_this_week(self) -> Dict[str, Any]:
        """Get this week's time breakdown (Mon-Sun)."""
        today = datetime.now(timezone.utc).date()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return self.summary_range(monday.isoformat(), sunday.isoformat())

    # ─── FOCUS SESSIONS ─────────────────────────────────────

    def start_focus(self, duration: int = 25, task: Optional[str] = None) -> int:
        """Start a Pomodoro-style focus session."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """INSERT INTO focus_sessions (start_time, planned_duration, task)
               VALUES (?, ?, ?)""",
            (now, duration, task),
        )
        self.conn.commit()
        return cursor.lastrowid

    def stop_focus(
        self,
        session_id: int,
        interruptions: int = 0,
        focus_level: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Stop a focus session."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        session = self.conn.execute(
            "SELECT * FROM focus_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not session:
            raise ValueError(f"Focus session {session_id} not found")

        start = datetime.fromisoformat(session["start_time"])
        duration = int((now - start).total_seconds() / 60)

        self.conn.execute(
            """UPDATE focus_sessions
               SET end_time = ?, duration_minutes = ?, completed = 1,
                   interruptions = ?, focus_level = ?, notes = ?
               WHERE id = ?""",
            (now_iso, duration, interruptions, focus_level, notes, session_id),
        )
        self.conn.commit()

        return {
            "id": session_id,
            "planned": session["planned_duration"],
            "actual": duration,
            "interruptions": interruptions,
            "focus": focus_level,
        }

    # ─── QUICK STATS ────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Quick stats: today, this week, streaks."""
        today = self.summary_today()
        week = self.summary_this_week()

        # Waste ratio
        waste_today = today["breakdown"].get("waste", 0)
        total_today = today["total_minutes"] or 1
        waste_ratio = round(waste_today / total_today * 100, 1)

        # Deep work ratio
        deep_today = today["breakdown"].get("work_deep", 0)
        deep_ratio = round(deep_today / total_today * 100, 1)

        # People time
        people_today = today["breakdown"].get("people", 0)

        return {
            "today": today,
            "week": week,
            "waste_ratio_pct": waste_ratio,
            "deep_work_ratio_pct": deep_ratio,
            "people_minutes_today": people_today,
        }

    def close(self):
        """Close database connection."""
        self.conn.close()


# ─── CONVENIENCE ───────────────────────────────────────────

def quick_start(category: str, **kwargs) -> int:
    """Quick start a block without creating a tracker instance."""
    tracker = TimeTracker()
    block_id = tracker.start(category, **kwargs)
    tracker.close()
    return block_id


def quick_stop(block_id: int, **kwargs) -> Dict[str, Any]:
    """Quick stop a block."""
    tracker = TimeTracker()
    result = tracker.stop(block_id, **kwargs)
    tracker.close()
    return result


def quick_status() -> Dict[str, Any]:
    """Quick status check."""
    tracker = TimeTracker()
    stats = tracker.stats()
    tracker.close()
    return stats
