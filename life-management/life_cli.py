#!/usr/bin/env python3
"""
Life Management System — Core Engine
=====================================
Fundament systemu zarządzania życiem:
- Time Tracker (bloki 5-minutowe)
- People CRM (50 osób, kategorie, balans czasu)
- Event Manager (urodziny, ważne daty, przypomnienia)
- Report Generator (gdzie ucieka czas, z kim spędzam)

Wszystkie dane w SQLite: life_management.db
"""

from __future__ import annotations

import sqlite3
import json
import os
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional, Literal
from pathlib import Path
from contextlib import contextmanager

# ── Constants ───────────────────────────────────────────────────────────────

BLOCK_MINUTES: int = 5
BLOCKS_PER_HOUR: int = 12
BLOCKS_PER_DAY: int = 288  # 24h * 12

PersonCategory = Literal[
    "rodzina_blizsza",   # partner, dzieci, rodzice, rodzeństwo
    "rodzina_dalsza",    # kuzyni, wujkowie, dziadkowie
    "znajomi_bliscy",    # najlepsi przyjaciele
    "znajomi",           # reszta znajomych
    "wspolpracownicy",   # ludzie z pracy
    "inni",              # wszyscy pozostali
]

TimeCategory = Literal[
    "praca",
    "rodzina",
    "znajomi",
    "zdrowie",       # ćwiczenia, lekarz
    "jedzenie",      # posiłki, gotowanie
    "hobby",
    "odpoczynek",    # sen, relaks
    "nauka",
    "administracja", # zakupy, sprzątanie, rachunki
    "transport",
    "higiena",
    "inne",
]

# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class Person:
    """Osoba w systemie."""
    id: Optional[int] = None
    name: str = ""
    category: PersonCategory = "znajomi"
    priority: int = 5          # 1-10, jak ważna jest ta osoba
    birthday: Optional[str] = None  # ISO date: "1990-05-15"
    phone: str = ""
    email: str = ""
    notes: str = ""
    last_contact: Optional[str] = None  # ISO datetime
    contact_frequency_days: int = 14   # co ile dni powinienem mieć kontakt
    created_at: str = ""
    updated_at: str = ""


@dataclass
class TimeBlock:
    """Jeden blok 5-minutowy."""
    id: Optional[int] = None
    start_time: str = ""        # ISO datetime
    end_time: str = ""          # ISO datetime
    category: TimeCategory = "inne"
    person_id: Optional[int] = None  # NULL = solo activity
    description: str = ""
    energy_level: int = 5       # 1-10
    focus_level: int = 5        # 1-10
    was_planned: bool = False   # czy to było zaplanowane
    tags: str = ""              # JSON array of strings
    created_at: str = ""


@dataclass
class Event:
    """Ważne wydarzenie (urodziny, rocznica, deadline)."""
    id: Optional[int] = None
    title: str = ""
    event_date: str = ""        # ISO date
    event_type: Literal["urodziny", "rocznica", "deadline", "spotkanie", "zdrowie", "inne"] = "inne"
    person_id: Optional[int] = None
    recurring: bool = False     # czy powtarza się co roku
    reminder_days_before: int = 3
    notes: str = ""
    notified: bool = False
    created_at: str = ""


@dataclass
class HabitLog:
    """Log nawyków (pigułki, ćwiczenia, myśli, podjadanie)."""
    id: Optional[int] = None
    timestamp: str = ""
    habit_type: Literal["pills", "exercise", "intrusive_thought", "snacking", "focus_session", "meal", "water"] = "pills"
    value: str = ""             # "taken"/"skipped", "30min", "occurred", itp.
    intensity: int = 5          # 1-10 (dla myśli, podjadania)
    notes: str = ""
    created_at: str = ""


# ── Database Manager ─────────────────────────────────────────────────────────

class LifeDB:
    """Zarządza połączeniem z SQLite i tworzy tabele."""

    def __init__(self, db_path: str = ""):
        if not db_path:
            db_path = str(Path(__file__).parent / "data" / "life_management.db")
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_tables(self) -> None:
        """Tworzy wszystkie tabele jeśli nie istnieją."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS people (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'znajomi',
                    priority INTEGER NOT NULL DEFAULT 5 CHECK(priority BETWEEN 1 AND 10),
                    birthday TEXT,
                    phone TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    last_contact TEXT,
                    contact_frequency_days INTEGER NOT NULL DEFAULT 14,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS time_blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'inne',
                    person_id INTEGER,
                    description TEXT DEFAULT '',
                    energy_level INTEGER NOT NULL DEFAULT 5 CHECK(energy_level BETWEEN 1 AND 10),
                    focus_level INTEGER NOT NULL DEFAULT 5 CHECK(focus_level BETWEEN 1 AND 10),
                    was_planned INTEGER NOT NULL DEFAULT 0,
                    tags TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    event_type TEXT NOT NULL DEFAULT 'inne',
                    person_id INTEGER,
                    recurring INTEGER NOT NULL DEFAULT 0,
                    reminder_days_before INTEGER NOT NULL DEFAULT 3,
                    notes TEXT DEFAULT '',
                    notified INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS habit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    habit_type TEXT NOT NULL,
                    value TEXT DEFAULT '',
                    intensity INTEGER DEFAULT 5 CHECK(intensity BETWEEN 1 AND 10),
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_time_blocks_start ON time_blocks(start_time);
                CREATE INDEX IF NOT EXISTS idx_time_blocks_category ON time_blocks(category);
                CREATE INDEX IF NOT EXISTS idx_time_blocks_person ON time_blocks(person_id);
                CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date);
                CREATE INDEX IF NOT EXISTS idx_events_person ON events(person_id);
                CREATE INDEX IF NOT EXISTS idx_habit_log_timestamp ON habit_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_habit_log_type ON habit_log(habit_type);
                CREATE INDEX IF NOT EXISTS idx_people_category ON people(category);
            """)

    def execute(self, sql: str, params: tuple = ()) -> list[dict]:
        """Wykonaj SELECT i zwróć listę dictów."""
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def execute_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Wykonaj SELECT i zwróć jeden wiersz lub None."""
        rows = self.execute(sql, params)
        return rows[0] if rows else None

    def insert(self, table: str, data: dict) -> int:
        """Wstaw wiersz i zwróć ID."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        with self._conn() as conn:
            cursor = conn.execute(
                f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                tuple(data.values()),
            )
            return cursor.lastrowid

    def update(self, table: str, data: dict, where: str, params: tuple = ()) -> None:
        """Zaktualizuj wiersz."""
        sets = ", ".join([f"{k} = ?" for k in data])
        with self._conn() as conn:
            conn.execute(
                f"UPDATE {table} SET {sets} WHERE {where}",
                tuple(data.values()) + params,
            )

    def delete(self, table: str, where: str, params: tuple = ()) -> None:
        """Usuń wiersz."""
        with self._conn() as conn:
            conn.execute(f"DELETE FROM {table} WHERE {where}", params)


# ── Time Tracker ─────────────────────────────────────────────────────────────

class TimeTracker:
    """Śledzenie czasu w blokach 5-minutowych."""

    def __init__(self, db: LifeDB):
        self.db = db
        self._current_block_start: Optional[datetime] = None
        self._current_category: TimeCategory = "inne"
        self._current_person_id: Optional[int] = None

    def start_block(
        self,
        category: TimeCategory = "inne",
        person_id: Optional[int] = None,
        description: str = "",
        energy: int = 5,
        focus: int = 5,
        planned: bool = False,
        tags: Optional[list[str]] = None,
    ) -> TimeBlock:
        """Rozpocznij nowy blok czasu. Automatycznie zamyka poprzedni."""
        if self._current_block_start is not None:
            self.stop_block()

        now = datetime.now()
        self._current_block_start = now
        self._current_category = category
        self._current_person_id = person_id

        block = TimeBlock(
            start_time=now.isoformat(),
            end_time="",  # wypełnione przy stop_block
            category=category,
            person_id=person_id,
            description=description,
            energy_level=energy,
            focus_level=focus,
            was_planned=planned,
            tags=json.dumps(tags or []),
            created_at=now.isoformat(),
        )
        return block

    def stop_block(self, description: str = "") -> Optional[TimeBlock]:
        """Zamknij aktualny blok i zapisz do bazy."""
        if self._current_block_start is None:
            return None

        now = datetime.now()
        start = self._current_block_start
        duration = now - start

        # Zaokrąglij do pełnych bloków 5-minutowych
        total_minutes = int(duration.total_seconds() / 60)
        blocks_count = max(1, round(total_minutes / BLOCK_MINUTES))
        rounded_minutes = blocks_count * BLOCK_MINUTES
        end_time = start + timedelta(minutes=rounded_minutes)

        block = TimeBlock(
            start_time=start.isoformat(),
            end_time=end_time.isoformat(),
            category=self._current_category,
            person_id=self._current_person_id,
            description=description,
            energy_level=5,
            focus_level=5,
            was_planned=False,
            tags="[]",
            created_at=now.isoformat(),
        )

        block_id = self.db.insert("time_blocks", {
            "start_time": block.start_time,
            "end_time": block.end_time,
            "category": block.category,
            "person_id": block.person_id,
            "description": block.description,
            "energy_level": block.energy_level,
            "focus_level": block.focus_level,
            "was_planned": int(block.was_planned),
            "tags": block.tags,
            "created_at": block.created_at,
        })
        block.id = block_id

        # Aktualizuj last_contact dla osoby
        if self._current_person_id:
            self.db.update(
                "people",
                {"last_contact": now.isoformat(), "updated_at": now.isoformat()},
                "id = ?",
                (self._current_person_id,),
            )

        self._current_block_start = None
        self._current_category = "inne"
        self._current_person_id = None

        return block

    def log_manual_block(
        self,
        start_time: str,
        end_time: str,
        category: TimeCategory = "inne",
        person_id: Optional[int] = None,
        description: str = "",
        energy: int = 5,
        focus: int = 5,
        planned: bool = False,
        tags: Optional[list[str]] = None,
    ) -> TimeBlock:
        """Ręcznie dodaj blok czasu (np. wstecz)."""
        block = TimeBlock(
            start_time=start_time,
            end_time=end_time,
            category=category,
            person_id=person_id,
            description=description,
            energy_level=energy,
            focus_level=focus,
            was_planned=planned,
            tags=json.dumps(tags or []),
            created_at=datetime.now().isoformat(),
        )
        block_id = self.db.insert("time_blocks", {
            "start_time": block.start_time,
            "end_time": block.end_time,
            "category": block.category,
            "person_id": block.person_id,
            "description": block.description,
            "energy_level": block.energy_level,
            "focus_level": block.focus_level,
            "was_planned": int(block.was_planned),
            "tags": block.tags,
            "created_at": block.created_at,
        })
        block.id = block_id

        # Aktualizuj last_contact dla osoby
        if person_id:
            self.db.update(
                "people",
                {"last_contact": block.start_time, "updated_at": datetime.now().isoformat()},
                "id = ?",
                (person_id,),
            )

        return block

    def get_blocks(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[TimeCategory] = None,
        person_id: Optional[int] = None,
    ) -> list[dict]:
        """Pobierz bloki czasu z filtrami."""
        conditions = ["1=1"]
        params: list = []

        if start_date:
            conditions.append("start_time >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("start_time <= ?")
            params.append(end_date)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if person_id is not None:
            conditions.append("person_id = ?")
            params.append(person_id)

        where = " AND ".join(conditions)
        return self.db.execute(
            f"SELECT * FROM time_blocks WHERE {where} ORDER BY start_time DESC",
            tuple(params),
        )

    def get_today_summary(self) -> dict:
        """Podsumowanie dzisiejszego dnia."""
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        blocks = self.db.execute(
            """SELECT category, 
               SUM((julianday(end_time) - julianday(start_time)) * 24 * 60) as total_minutes,
               COUNT(*) as block_count
               FROM time_blocks 
               WHERE start_time >= ? AND start_time < ?
               GROUP BY category
               ORDER BY total_minutes DESC""",
            (today, tomorrow),
        )

        total_minutes = sum(b["total_minutes"] for b in blocks)
        return {
            "date": today,
            "total_minutes": round(total_minutes),
            "total_hours": round(total_minutes / 60, 1),
            "blocks_tracked": sum(b["block_count"] for b in blocks),
            "by_category": {b["category"]: round(b["total_minutes"]) for b in blocks},
            "coverage_pct": round(min(100, total_minutes / 1440 * 100), 1),  # % of 24h
        }

    def get_weekly_report(self) -> dict:
        """Raport tygodniowy."""
        today = date.today()
        week_start = (today - timedelta(days=today.weekday())).isoformat()
        week_end = (today + timedelta(days=1)).isoformat()

        blocks = self.db.execute(
            """SELECT category, 
               SUM((julianday(end_time) - julianday(start_time)) * 24 * 60) as total_minutes
               FROM time_blocks 
               WHERE start_time >= ? AND start_time < ?
               GROUP BY category
               ORDER BY total_minutes DESC""",
            (week_start, week_end),
        )

        total_minutes = sum(b["total_minutes"] for b in blocks)
        return {
            "week_start": week_start,
            "week_end": week_end,
            "total_hours": round(total_minutes / 60, 1),
            "by_category": {b["category"]: round(b["total_minutes"] / 60, 1) for b in blocks},
            "daily_average_hours": round(total_minutes / 60 / 7, 1),
        }


# ── People Manager ───────────────────────────────────────────────────────────

class PeopleManager:
    """Zarządzanie 50 osobami — CRUD, balans czasu, priorytety."""

    def __init__(self, db: LifeDB):
        self.db = db

    def add_person(
        self,
        name: str,
        category: PersonCategory = "znajomi",
        priority: int = 5,
        birthday: Optional[str] = None,
        phone: str = "",
        email: str = "",
        notes: str = "",
        contact_frequency_days: int = 14,
    ) -> Person:
        """Dodaj nową osobę."""
        now = datetime.now().isoformat()
        person_id = self.db.insert("people", {
            "name": name,
            "category": category,
            "priority": priority,
            "birthday": birthday,
            "phone": phone,
            "email": email,
            "notes": notes,
            "contact_frequency_days": contact_frequency_days,
            "created_at": now,
            "updated_at": now,
        })
        return self.get_person(person_id)  # type: ignore[return-value]

    def get_person(self, person_id: int) -> Optional[Person]:
        """Pobierz osobę po ID."""
        row = self.db.execute_one("SELECT * FROM people WHERE id = ?", (person_id,))
        return Person(**row) if row else None

    def get_all_people(self, category: Optional[PersonCategory] = None) -> list[Person]:
        """Pobierz wszystkie osoby, opcjonalnie filtrując po kategorii."""
        if category:
            rows = self.db.execute(
                "SELECT * FROM people WHERE category = ? ORDER BY priority DESC, name",
                (category,),
            )
        else:
            rows = self.db.execute("SELECT * FROM people ORDER BY category, priority DESC, name")
        return [Person(**r) for r in rows]

    def update_person(self, person_id: int, **kwargs) -> Optional[Person]:
        """Zaktualizuj dane osoby."""
        kwargs["updated_at"] = datetime.now().isoformat()
        self.db.update("people", kwargs, "id = ?", (person_id,))
        return self.get_person(person_id)

    def delete_person(self, person_id: int) -> bool:
        """Usuń osobę."""
        self.db.delete("people", "id = ?", (person_id,))
        return True

    def get_balance_report(self) -> dict:
        """Raport balansu czasu spędzonego z każdą osobą."""
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()

        rows = self.db.execute("""
            SELECT 
                p.id, p.name, p.category, p.priority, p.last_contact, p.contact_frequency_days,
                COALESCE(SUM((julianday(tb.end_time) - julianday(tb.start_time)) * 24 * 60), 0) as minutes_last_30d
            FROM people p
            LEFT JOIN time_blocks tb ON tb.person_id = p.id 
                AND tb.start_time >= ?
            GROUP BY p.id
            ORDER BY p.category, p.priority DESC
        """, (thirty_days_ago,))

        people_balance = []
        for r in rows:
            days_since_contact = None
            if r["last_contact"]:
                last = datetime.fromisoformat(r["last_contact"])
                days_since_contact = (datetime.now() - last).days

            overdue = False
            if days_since_contact is not None and days_since_contact > r["contact_frequency_days"]:
                overdue = True

            people_balance.append({
                "id": r["id"],
                "name": r["name"],
                "category": r["category"],
                "priority": r["priority"],
                "minutes_last_30d": round(r["minutes_last_30d"]),
                "hours_last_30d": round(r["minutes_last_30d"] / 60, 1),
                "days_since_contact": days_since_contact,
                "contact_frequency_days": r["contact_frequency_days"],
                "overdue": overdue,
            })

        return {
            "total_people": len(people_balance),
            "overdue_count": sum(1 for p in people_balance if p["overdue"]),
            "people": people_balance,
        }

    def get_who_needs_attention(self, top_n: int = 10) -> list[dict]:
        """Kto najbardziej potrzebuje kontaktu (overdue + wysoki priorytet)."""
        balance = self.get_balance_report()
        people = balance["people"]

        # Sortuj: overdue first, then by priority desc, then by days since contact desc
        def sort_key(p: dict) -> tuple:
            overdue_score = 0 if p["overdue"] else 1
            days = p["days_since_contact"] or 999
            return (overdue_score, -p["priority"], -days)

        people.sort(key=sort_key)
        return people[:top_n]

    def get_upcoming_birthdays(self, days_ahead: int = 30) -> list[dict]:
        """Nadchodzące urodziny w ciągu N dni."""
        today = date.today()
        upcoming = []

        people = self.get_all_people()
        for p in people:
            if not p.birthday:
                continue
            try:
                bday = date.fromisoformat(p.birthday)
                # Urodziny w tym roku
                this_year_bday = date(today.year, bday.month, bday.day)
                if this_year_bday < today:
                    this_year_bday = date(today.year + 1, bday.month, bday.day)
                days_until = (this_year_bday - today).days
                if days_until <= days_ahead:
                    upcoming.append({
                        "person_id": p.id,
                        "name": p.name,
                        "birthday": p.birthday,
                        "days_until": days_until,
                        "age": today.year - bday.year,
                    })
            except (ValueError, TypeError):
                continue

        upcoming.sort(key=lambda x: x["days_until"])
        return upcoming


# ── Event Manager ────────────────────────────────────────────────────────────

class EventManager:
    """Zarządzanie wydarzeniami — urodziny, deadline'y, przypomnienia."""

    def __init__(self, db: LifeDB):
        self.db = db

    def add_event(
        self,
        title: str,
        event_date: str,
        event_type: str = "inne",
        person_id: Optional[int] = None,
        recurring: bool = False,
        reminder_days_before: int = 3,
        notes: str = "",
    ) -> Event:
        """Dodaj nowe wydarzenie."""
        now = datetime.now().isoformat()
        event_id = self.db.insert("events", {
            "title": title,
            "event_date": event_date,
            "event_type": event_type,
            "person_id": person_id,
            "recurring": int(recurring),
            "reminder_days_before": reminder_days_before,
            "notes": notes,
            "notified": 0,
            "created_at": now,
        })
        return self.get_event(event_id)  # type: ignore[return-value]

    def get_event(self, event_id: int) -> Optional[Event]:
        """Pobierz wydarzenie po ID."""
        row = self.db.execute_one("SELECT * FROM events WHERE id = ?", (event_id,))
        return Event(**row) if row else None

    def get_upcoming_events(self, days_ahead: int = 7) -> list[dict]:
        """Pobierz nadchodzące wydarzenia."""
        today = date.today().isoformat()
        end = (date.today() + timedelta(days=days_ahead)).isoformat()

        rows = self.db.execute("""
            SELECT e.*, p.name as person_name
            FROM events e
            LEFT JOIN people p ON e.person_id = p.id
            WHERE e.event_date >= ? AND e.event_date <= ?
            ORDER BY e.event_date
        """, (today, end))

        return [dict(r) for r in rows]

    def get_events_needing_reminder(self) -> list[dict]:
        """Wydarzenia które potrzebują przypomnienia (w ciągu reminder_days_before dni)."""
        today = date.today()

        rows = self.db.execute("""
            SELECT e.*, p.name as person_name
            FROM events e
            LEFT JOIN people p ON e.person_id = p.id
            WHERE e.notified = 0
            ORDER BY e.event_date
        """)

        needing = []
        for r in rows:
            event_date = date.fromisoformat(r["event_date"])
            days_until = (event_date - today).days
            if 0 <= days_until <= r["reminder_days_before"]:
                needing.append({**dict(r), "days_until": days_until})
        return needing

    def mark_notified(self, event_id: int) -> None:
        """Oznacz wydarzenie jako powiadomione."""
        self.db.update("events", {"notified": 1}, "id = ?", (event_id,))


# ── Habit Tracker ────────────────────────────────────────────────────────────

class HabitTracker:
    """Śledzenie nawyków — pigułki, ćwiczenia, myśli, podjadanie."""

    def __init__(self, db: LifeDB):
        self.db = db

    def log(
        self,
        habit_type: str,
        value: str = "",
        intensity: int = 5,
        notes: str = "",
    ) -> HabitLog:
        """Zaloguj nawyk."""
        now = datetime.now().isoformat()
        log_id = self.db.insert("habit_log", {
            "timestamp": now,
            "habit_type": habit_type,
            "value": value,
            "intensity": intensity,
            "notes": notes,
            "created_at": now,
        })
        return HabitLog(
            id=log_id,
            timestamp=now,
            habit_type=habit_type,
            value=value,
            intensity=intensity,
            notes=notes,
            created_at=now,
        )

    def get_today_habits(self) -> dict[str, list[dict]]:
        """Pobierz dzisiejsze logi nawyków pogrupowane po typie."""
        today = date.today().isoformat()
        rows = self.db.execute(
            "SELECT * FROM habit_log WHERE timestamp >= ? ORDER BY timestamp DESC",
            (today,),
        )

        by_type: dict[str, list[dict]] = {}
        for r in rows:
            ht = r["habit_type"]
            if ht not in by_type:
                by_type[ht] = []
            by_type[ht].append(dict(r))
        return by_type

    def get_streak(self, habit_type: str) -> int:
        """Policz dni z rzędu z danym nawykiem."""
        rows = self.db.execute(
            "SELECT DISTINCT date(timestamp) as d FROM habit_log WHERE habit_type = ? ORDER BY d DESC",
            (habit_type,),
        )
        dates = [r["d"] for r in rows]
        if not dates:
            return 0

        streak = 0
        today = date.today()
        expected = today

        for d_str in dates:
            d = date.fromisoformat(d_str)
            if d == expected:
                streak += 1
                expected = d - timedelta(days=1)
            elif d < expected:
                break

        return streak

    def get_weekly_habit_report(self) -> dict:
        """Raport tygodniowy nawyków."""
        week_ago = (date.today() - timedelta(days=7)).isoformat()

        rows = self.db.execute("""
            SELECT habit_type, COUNT(*) as count, 
                   AVG(intensity) as avg_intensity
            FROM habit_log 
            WHERE timestamp >= ?
            GROUP BY habit_type
        """, (week_ago,))

        return {
            "week_start": week_ago,
            "habits": {r["habit_type"]: {
                "count": r["count"],
                "avg_intensity": round(r["avg_intensity"], 1) if r["avg_intensity"] else 0,
            } for r in rows},
        }


# ── Report Generator ─────────────────────────────────────────────────────────

class ReportGenerator:
    """Generuje raporty — gdzie ucieka czas, z kim spędzam, trendy."""

    def __init__(self, db: LifeDB):
        self.db = db
        self.time_tracker = TimeTracker(db)
        self.people_manager = PeopleManager(db)
        self.event_manager = EventManager(db)
        self.habit_tracker = HabitTracker(db)

    def daily_brief(self) -> str:
        """Codzienny raport — co dziś, co jutro, kogo widzieć."""
        today = date.today()
        summary = self.time_tracker.get_today_summary()
        upcoming_events = self.event_manager.get_upcoming_events(days_ahead=1)
        birthdays = self.people_manager.get_upcoming_birthdays(days_ahead=7)
        who_needs = self.people_manager.get_who_needs_attention(top_n=5)
        habits = self.habit_tracker.get_today_habits()

        lines = [
            f"📅 {today.strftime('%A, %d.%m.%Y')}",
            "=" * 40,
            "",
            "⏱️ CZAS:",
            f"   Śledzone: {summary['total_hours']}h ({summary['coverage_pct']}% dnia)",
        ]

        for cat, mins in summary.get("by_category", {}).items():
            hours = mins / 60
            lines.append(f"   {cat}: {hours:.1f}h")

        lines.extend([
            "",
            "🔔 WYDARZENIA:",
        ])
        if upcoming_events:
            for e in upcoming_events:
                lines.append(f"   ⚠️ {e['title']} — {e['event_date']}")
        else:
            lines.append("   Brak na dziś/jutro")

        lines.extend([
            "",
            "🎂 URODZINY (7 dni):",
        ])
        if birthdays:
            for b in birthdays:
                lines.append(f"   🎈 {b['name']} — za {b['days_until']} dni ({b['age']} lat)")
        else:
            lines.append("   Brak w ciągu 7 dni")

        lines.extend([
            "",
            "👥 KONTAKT POTRZEBNY:",
        ])
        if who_needs:
            for p in who_needs:
                flag = "🔴" if p["overdue"] else "🟢"
                days = p["days_since_contact"] or "?"
                lines.append(f"   {flag} {p['name']} ({p['category']}) — ostatni kontakt: {days} dni temu")
        else:
            lines.append("   Wszyscy w normie ✅")

        lines.extend([
            "",
            "💊 NAWYKI:",
        ])
        if habits:
            for ht, logs in habits.items():
                lines.append(f"   {ht}: {len(logs)}x dziś")
        else:
            lines.append("   Brak logów na dziś")

        return "\n".join(lines)

    def weekly_deep_dive(self) -> str:
        """Głęboki raport tygodniowy."""
        time_report = self.time_tracker.get_weekly_report()
        balance = self.people_manager.get_balance_report()
        habit_report = self.habit_tracker.get_weekly_habit_report()

        lines = [
            "📊 RAPORT TYGODNIOWY",
            "=" * 40,
            "",
            f"⏱️ Średnio dziennie: {time_report['daily_average_hours']}h śledzonych",
            "",
            "📂 Kategorie:",
        ]
        for cat, hours in time_report.get("by_category", {}).items():
            bar = "█" * int(hours)
            lines.append(f"   {cat:15s} {bar} {hours}h")

        lines.extend([
            "",
            f"👥 OSOBY ({balance['total_people']}):",
            f"   🔴 Overdue: {balance['overdue_count']}",
        ])

        # Top 5 most time
        top_time = sorted(balance["people"], key=lambda x: -x["hours_last_30d"])[:5]
        if top_time:
            lines.append("   Najwięcej czasu (30d):")
            for p in top_time:
                if p["hours_last_30d"] > 0:
                    lines.append(f"      {p['name']}: {p['hours_last_30d']}h")

        lines.extend([
            "",
            "💊 NAWYKI (7d):",
        ])
        for ht, data in habit_report.get("habits", {}).items():
            lines.append(f"   {ht}: {data['count']}x (śr. intensywność: {data['avg_intensity']})")

        return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    """CLI do szybkiego logowania czasu i zarządzania."""
    import sys

    db = LifeDB()
    tracker = TimeTracker(db)
    people = PeopleManager(db)
    events = EventManager(db)
    habits = HabitTracker(db)
    reports = ReportGenerator(db)

    if len(sys.argv) < 2:
        print("Life Management System — CLI")
        print()
        print("Komendy:")
        print("  start <kategoria> [osoba_id]  — rozpocznij blok czasu")
        print("  stop [opis]                   — zakończ blok czasu")
        print("  log <start> <end> <kat>       — ręcznie dodaj blok (ISO format)")
        print("  today                         — podsumowanie dnia")
        print("  week                          — raport tygodniowy")
        print("  brief                         — daily brief (pełny raport)")
        print("  people                        — lista osób")
        print("  people-add <imię> <kat>       — dodaj osobę")
        print("  balance                       — balans czasu z osobami")
        print("  attention                     — kto potrzebuje kontaktu")
        print("  birthdays [dni]               — nadchodzące urodziny")
        print("  events [dni]                   — nadchodzące wydarzenia")
        print("  habit <typ> <wartość>         — zaloguj nawyk")
        print("  habit-streak <typ>            — sprawdź serię")
        print("  pill taken|skipped            — szybkie logowanie pigułek")
        print("  thought <intensywność>        — zaloguj natarczywą myśl")
        print("  snack <intensywność>          — zaloguj podjadanie")
        return

    cmd = sys.argv[1]

    if cmd == "start" and len(sys.argv) >= 3:
        category = sys.argv[2]
        person_id = int(sys.argv[3]) if len(sys.argv) >= 4 else None
        block = tracker.start_block(category=category, person_id=person_id)  # type: ignore[arg-type]
        person_name = ""
        if person_id:
            p = people.get_person(person_id)
            person_name = f" z {p.name}" if p else ""
        print(f"▶️  START: {category}{person_name} — {block.start_time}")

    elif cmd == "stop":
        desc = sys.argv[2] if len(sys.argv) >= 3 else ""
        block = tracker.stop_block(description=desc)
        if block:
            print(f"⏹️  STOP: {block.category} — {block.start_time} → {block.end_time}")
        else:
            print("❌ Brak aktywnego bloku")

    elif cmd == "today":
        summary = tracker.get_today_summary()
        print(f"📅 {summary['date']}")
        print(f"   Śledzone: {summary['total_hours']}h ({summary['coverage_pct']}% dnia)")
        for cat, mins in summary["by_category"].items():
            print(f"   {cat}: {mins/60:.1f}h")

    elif cmd == "week":
        print(reports.weekly_deep_dive())

    elif cmd == "brief":
        print(reports.daily_brief())

    elif cmd == "people":
        all_people = people.get_all_people()
        for p in all_people:
            print(f"  [{p.id}] {p.name} ({p.category}) — prio {p.priority}")

    elif cmd == "people-add" and len(sys.argv) >= 4:
        name = sys.argv[2]
        category = sys.argv[3]
        p = people.add_person(name=name, category=category)  # type: ignore[arg-type]
        print(f"✅ Dodano: {p.name} (ID: {p.id})")

    elif cmd == "balance":
        report = people.get_balance_report()
        for p in report["people"]:
            flag = "🔴" if p["overdue"] else "🟢"
            print(f"  {flag} {p['name']:20s} {p['hours_last_30d']:5.1f}h | ostatni: {p['days_since_contact']}d temu")

    elif cmd == "attention":
        needing = people.get_who_needs_attention(top_n=10)
        for p in needing:
            flag = "🔴" if p["overdue"] else "🟢"
            print(f"  {flag} {p['name']} ({p['category']}) — {p['days_since_contact']}d | prio {p['priority']}")

    elif cmd == "birthdays":
        days = int(sys.argv[2]) if len(sys.argv) >= 3 else 30
        upcoming = people.get_upcoming_birthdays(days_ahead=days)
        for b in upcoming:
            print(f"  🎂 {b['name']} — {b['birthday']} (za {b['days_until']} dni, {b['age']} lat)")

    elif cmd == "events":
        days = int(sys.argv[2]) if len(sys.argv) >= 3 else 7
        upcoming = events.get_upcoming_events(days_ahead=days)
        for e in upcoming:
            print(f"  📌 {e['event_date']} — {e['title']} ({e['event_type']})")

    elif cmd == "habit" and len(sys.argv) >= 4:
        ht = sys.argv[2]
        val = sys.argv[3]
        intensity = int(sys.argv[4]) if len(sys.argv) >= 5 else 5
        habits.log(habit_type=ht, value=val, intensity=intensity)
        print(f"✅ Zalogowano: {ht} = {val}")

    elif cmd == "pill":
        val = sys.argv[2] if len(sys.argv) >= 3 else "taken"
        habits.log(habit_type="pills", value=val)
        streak = habits.get_streak("pills")
        print(f"💊 Pigułki: {val} | Seria: {streak} dni")

    elif cmd == "thought" and len(sys.argv) >= 3:
        intensity = int(sys.argv[2])
        habits.log(habit_type="intrusive_thought", value="occurred", intensity=intensity)
        print(f"🧠 Natarczywa myśl: intensywność {intensity}/10")

    elif cmd == "snack" and len(sys.argv) >= 3:
        intensity = int(sys.argv[2])
        habits.log(habit_type="snacking", value="occurred", intensity=intensity)
        print(f"🍪 Podjadanie: intensywność {intensity}/10")

    elif cmd == "habit-streak" and len(sys.argv) >= 3:
        ht = sys.argv[2]
        streak = habits.get_streak(ht)
        print(f"🔥 Seria {ht}: {streak} dni")

    else:
        print(f"❌ Nieznana komenda: {cmd}")


if __name__ == "__main__":
    main()
