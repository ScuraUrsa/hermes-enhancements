#!/usr/bin/env python3
"""
Mind & Habits Module — Life Management System
==============================================
Rozszerza core engine o:
- Intrusive Thought Tracker (trigger analysis, CBT patterns, coping strategies)
- Snacking Trigger→Response Mapping (co wywołało, co zjadłeś, jak się czułeś)
- Focus/Pomodoro Tracker (deep work sessions, dystrakcje, productivity score)
- Daily Goals (3 MITs, completion check)
- Weekly Review (co poszło dobrze, co poprawić, lessons learned)

Importuje LifeDB z life_cli.py i dodaje nowe tabele + CLI komendy.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional, Literal
from pathlib import Path

from life_cli import LifeDB

# ── Constants ───────────────────────────────────────────────────────────────

CBT_PATTERNS = [
    "catastrophizing",        # katastrofizacja — "to będzie katastrofa"
    "black_and_white",        # myślenie czarno-białe — "albo perfekcyjnie, albo wcale"
    "mind_reading",           # czytanie w myślach — "na pewno myśli, że jestem głupi"
    "fortune_telling",        # wróżenie z fusów — "na pewno mi się nie uda"
    "emotional_reasoning",    # wnioskowanie emocjonalne — "czuję się źle, więc jest źle"
    "overgeneralization",     # nadmierna generalizacja — "zawsze wszystko psuję"
    "labeling",               # etykietowanie — "jestem beznadziejny"
    "should_statements",      # "powinienem", "muszę" — sztywne zasady
    "personalization",        # personalizacja — biorę winę na siebie bez powodu
    "magnification",          # wyolbrzymianie — robienie z muchy słonia
    "discounting_positive",   # pomijanie pozytywów — "to się nie liczy"
    "other",                  # inne
]

COPING_STRATEGIES = [
    "cognitive_restructuring",  # przeformułowanie myśli
    "mindfulness",              # uważność, obserwacja bez oceniania
    "distraction",              # odwrócenie uwagi
    "physical_activity",        # aktywność fizyczna
    "social_support",           # rozmowa z kimś
    "journaling",               # zapisanie myśli
    "breathing",                # ćwiczenia oddechowe
    "gratitude",                # wdzięczność
    "self_compassion",          # współczucie dla siebie
    "exposure",                 # konfrontacja z lękiem
    "other",                    # inne
]

SNACKING_TRIGGERS = [
    "boredom",       # nuda
    "stress",        # stres
    "sadness",       # smutek
    "anxiety",       # lęk
    "anger",         # złość
    "tiredness",     # zmęczenie
    "social",        # towarzystwo / presja społeczna
    "habit",         # nawyk / rutyna
    "hunger",        # prawdziwy głód
    "celebration",   # świętowanie
    "procrastination", # odwlekanie
    "other",         # inne
]

FEELING_AFTER = [
    "guilty",        # poczucie winy
    "satisfied",     # zadowolenie
    "neutral",       # neutralnie
    "regretful",     # żal
    "bloated",       # przejedzenie
    "energized",     # energia
    "tired",         # zmęczenie
    "ashamed",       # wstyd
    "happy",         # radość
    "other",         # inne
]

# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class IntrusiveThought:
    """Rozszerzony log natarczywej myśli z analizą CBT."""
    id: Optional[int] = None
    timestamp: str = ""
    thought_content: str = ""          # treść myśli
    trigger: str = ""                  # co wywołało myśl (sytuacja, miejsce, osoba)
    cbt_pattern: str = ""              # typ zniekształcenia poznawczego
    intensity: int = 5                 # 1-10
    coping_strategy: str = ""          # strategia radzenia sobie
    coping_effectiveness: int = 5      # 1-10 — jak skuteczna była strategia
    outcome: str = ""                  # co się stało potem, jak się czuję teraz
    notes: str = ""
    created_at: str = ""


@dataclass
class SnackingLog:
    """Rozszerzony log podjadania z mapowaniem trigger→response."""
    id: Optional[int] = None
    timestamp: str = ""
    trigger_type: str = ""             # co wywołało (nuda, stres, smutek...)
    trigger_detail: str = ""           # szczegółowy opis triggera
    food_eaten: str = ""               # co zjadłeś
    amount: str = ""                   # ile (np. "pół paczki", "2 batony")
    intensity: int = 5                 # 1-10 — jak silna była potrzeba
    feeling_after: str = ""            # jak się czułeś po
    alternative_action: str = ""       # co mogłeś zrobić zamiast
    notes: str = ""
    created_at: str = ""


@dataclass
class FocusSession:
    """Sesja deep work / Pomodoro."""
    id: Optional[int] = None
    start_time: str = ""
    end_time: str = ""
    duration_minutes: int = 25         # planowana długość
    actual_duration_minutes: int = 0   # rzeczywista długość
    task_description: str = ""         # nad czym pracowałeś
    distractions: str = ""             # JSON array: co przerwało
    distraction_count: int = 0         # liczba dystrakcji
    productivity_score: int = 5        # 1-10
    focus_level: int = 5               # 1-10
    completed: bool = False            # czy sesja zakończona sukcesem
    notes: str = ""
    created_at: str = ""


@dataclass
class DailyGoal:
    """Cel dzienny (MIT — Most Important Task)."""
    id: Optional[int] = None
    goal_date: str = ""                # data (ISO date)
    priority_order: int = 1            # 1, 2, 3 — kolejność priorytetu
    goal_text: str = ""                # treść celu
    completed: bool = False            # czy zrobione
    completed_at: Optional[str] = None # kiedy ukończono
    notes: str = ""
    created_at: str = ""


@dataclass
class WeeklyReview:
    """Cotygodniowy przegląd — refleksja."""
    id: Optional[int] = None
    week_start: str = ""               # poniedziałek (ISO date)
    week_end: str = ""                 # niedziela (ISO date)
    what_went_well: str = ""           # co poszło dobrze
    what_to_improve: str = ""          # co poprawić
    lessons_learned: str = ""          # czego się nauczyłem
    gratitude: str = ""                # za co jestem wdzięczny
    energy_avg: int = 5                # średni poziom energii 1-10
    mood_avg: int = 5                  # średni nastrój 1-10
    goals_completed: int = 0           # ile celów ukończono w tygodniu
    goals_total: int = 0               # ile celów było w tygodniu
    next_week_focus: str = ""          # na czym skupić się w przyszłym tygodniu
    created_at: str = ""


# ── Database Extension ───────────────────────────────────────────────────────

class MindDB(LifeDB):
    """Rozszerza LifeDB o tabele Mind & Habits."""

    def _init_tables(self) -> None:
        """Tworzy wszystkie tabele (core + mind)."""
        super()._init_tables()
        with self._conn() as conn:
            conn.executescript("""
                -- Rozszerzona tabela natarczywych myśli
                CREATE TABLE IF NOT EXISTS intrusive_thoughts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    thought_content TEXT DEFAULT '',
                    trigger TEXT DEFAULT '',
                    cbt_pattern TEXT DEFAULT '',
                    intensity INTEGER NOT NULL DEFAULT 5 CHECK(intensity BETWEEN 1 AND 10),
                    coping_strategy TEXT DEFAULT '',
                    coping_effectiveness INTEGER NOT NULL DEFAULT 5 CHECK(coping_effectiveness BETWEEN 1 AND 10),
                    outcome TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                -- Rozszerzona tabela podjadania
                CREATE TABLE IF NOT EXISTS snacking_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    trigger_type TEXT DEFAULT '',
                    trigger_detail TEXT DEFAULT '',
                    food_eaten TEXT DEFAULT '',
                    amount TEXT DEFAULT '',
                    intensity INTEGER NOT NULL DEFAULT 5 CHECK(intensity BETWEEN 1 AND 10),
                    feeling_after TEXT DEFAULT '',
                    alternative_action TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                -- Sesje focus / Pomodoro
                CREATE TABLE IF NOT EXISTS focus_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT DEFAULT '',
                    duration_minutes INTEGER NOT NULL DEFAULT 25,
                    actual_duration_minutes INTEGER NOT NULL DEFAULT 0,
                    task_description TEXT DEFAULT '',
                    distractions TEXT DEFAULT '[]',
                    distraction_count INTEGER NOT NULL DEFAULT 0,
                    productivity_score INTEGER NOT NULL DEFAULT 5 CHECK(productivity_score BETWEEN 1 AND 10),
                    focus_level INTEGER NOT NULL DEFAULT 5 CHECK(focus_level BETWEEN 1 AND 10),
                    completed INTEGER NOT NULL DEFAULT 0,
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                -- Cele dzienne
                CREATE TABLE IF NOT EXISTS daily_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_date TEXT NOT NULL,
                    priority_order INTEGER NOT NULL DEFAULT 1 CHECK(priority_order BETWEEN 1 AND 3),
                    goal_text TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    completed_at TEXT,
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                -- Cotygodniowe przeglądy
                CREATE TABLE IF NOT EXISTS weekly_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_start TEXT NOT NULL,
                    week_end TEXT NOT NULL,
                    what_went_well TEXT DEFAULT '',
                    what_to_improve TEXT DEFAULT '',
                    lessons_learned TEXT DEFAULT '',
                    gratitude TEXT DEFAULT '',
                    energy_avg INTEGER NOT NULL DEFAULT 5 CHECK(energy_avg BETWEEN 1 AND 10),
                    mood_avg INTEGER NOT NULL DEFAULT 5 CHECK(mood_avg BETWEEN 1 AND 10),
                    goals_completed INTEGER NOT NULL DEFAULT 0,
                    goals_total INTEGER NOT NULL DEFAULT 0,
                    next_week_focus TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_intrusive_thoughts_ts ON intrusive_thoughts(timestamp);
                CREATE INDEX IF NOT EXISTS idx_intrusive_thoughts_cbt ON intrusive_thoughts(cbt_pattern);
                CREATE INDEX IF NOT EXISTS idx_snacking_log_ts ON snacking_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_snacking_log_trigger ON snacking_log(trigger_type);
                CREATE INDEX IF NOT EXISTS idx_focus_sessions_start ON focus_sessions(start_time);
                CREATE INDEX IF NOT EXISTS idx_daily_goals_date ON daily_goals(goal_date);
                CREATE INDEX IF NOT EXISTS idx_weekly_reviews_start ON weekly_reviews(week_start);
            """)


# ── Intrusive Thought Tracker ────────────────────────────────────────────────

class IntrusiveThoughtTracker:
    """Analiza natarczywych myśli — triggery, CBT patterns, coping strategies."""

    def __init__(self, db: MindDB):
        self.db = db

    def log_thought(
        self,
        thought_content: str = "",
        trigger: str = "",
        cbt_pattern: str = "other",
        intensity: int = 5,
        coping_strategy: str = "",
        coping_effectiveness: int = 5,
        outcome: str = "",
        notes: str = "",
    ) -> IntrusiveThought:
        """Zaloguj natarczywą myśl z pełną analizą CBT."""
        now = datetime.now().isoformat()
        thought_id = self.db.insert("intrusive_thoughts", {
            "timestamp": now,
            "thought_content": thought_content,
            "trigger": trigger,
            "cbt_pattern": cbt_pattern,
            "intensity": intensity,
            "coping_strategy": coping_strategy,
            "coping_effectiveness": coping_effectiveness,
            "outcome": outcome,
            "notes": notes,
            "created_at": now,
        })
        # Również zaloguj w uproszczonej tabeli habit_log (kompatybilność z core)
        self.db.insert("habit_log", {
            "timestamp": now,
            "habit_type": "intrusive_thought",
            "value": "occurred",
            "intensity": intensity,
            "notes": f"CBT: {cbt_pattern} | Trigger: {trigger} | {notes}",
            "created_at": now,
        })
        return self.get_thought(thought_id)  # type: ignore[return-value]

    def get_thought(self, thought_id: int) -> Optional[IntrusiveThought]:
        """Pobierz myśl po ID."""
        row = self.db.execute_one(
            "SELECT * FROM intrusive_thoughts WHERE id = ?", (thought_id,)
        )
        return IntrusiveThought(**row) if row else None

    def get_thoughts(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        cbt_pattern: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Pobierz myśli z filtrami."""
        conditions = ["1=1"]
        params: list = []

        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)
        if cbt_pattern:
            conditions.append("cbt_pattern = ?")
            params.append(cbt_pattern)

        where = " AND ".join(conditions)
        return self.db.execute(
            f"SELECT * FROM intrusive_thoughts WHERE {where} ORDER BY timestamp DESC LIMIT ?",
            tuple(params) + (limit,),
        )

    def get_cbt_pattern_breakdown(self, days: int = 30) -> dict:
        """Rozkład zniekształceń poznawczych w ostatnich N dniach."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self.db.execute("""
            SELECT cbt_pattern, COUNT(*) as count, AVG(intensity) as avg_intensity,
                   AVG(coping_effectiveness) as avg_coping_effectiveness
            FROM intrusive_thoughts
            WHERE timestamp >= ?
            GROUP BY cbt_pattern
            ORDER BY count DESC
        """, (since,))
        return {
            "period_days": days,
            "total_thoughts": sum(r["count"] for r in rows),
            "patterns": {r["cbt_pattern"]: {
                "count": r["count"],
                "avg_intensity": round(r["avg_intensity"], 1) if r["avg_intensity"] else 0,
                "avg_coping_effectiveness": round(r["avg_coping_effectiveness"], 1) if r["avg_coping_effectiveness"] else 0,
            } for r in rows},
        }

    def get_top_triggers(self, days: int = 30, limit: int = 10) -> list[dict]:
        """Najczęstsze triggery natarczywych myśli."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        return self.db.execute("""
            SELECT trigger, COUNT(*) as count, AVG(intensity) as avg_intensity
            FROM intrusive_thoughts
            WHERE timestamp >= ? AND trigger != ''
            GROUP BY trigger
            ORDER BY count DESC
            LIMIT ?
        """, (since, limit))

    def get_coping_effectiveness_report(self, days: int = 30) -> dict:
        """Które strategie radzenia sobie są najskuteczniejsze."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self.db.execute("""
            SELECT coping_strategy, COUNT(*) as count,
                   AVG(coping_effectiveness) as avg_effectiveness,
                   AVG(intensity) as avg_initial_intensity
            FROM intrusive_thoughts
            WHERE timestamp >= ? AND coping_strategy != ''
            GROUP BY coping_strategy
            ORDER BY avg_effectiveness DESC
        """, (since,))
        return {
            "period_days": days,
            "strategies": {r["coping_strategy"]: {
                "count": r["count"],
                "avg_effectiveness": round(r["avg_effectiveness"], 1) if r["avg_effectiveness"] else 0,
                "avg_initial_intensity": round(r["avg_initial_intensity"], 1) if r["avg_initial_intensity"] else 0,
            } for r in rows},
        }


# ── Snacking Tracker ─────────────────────────────────────────────────────────

class SnackingTracker:
    """Mapowanie trigger→response dla podjadania."""

    def __init__(self, db: MindDB):
        self.db = db

    def log_snack(
        self,
        trigger_type: str = "other",
        trigger_detail: str = "",
        food_eaten: str = "",
        amount: str = "",
        intensity: int = 5,
        feeling_after: str = "neutral",
        alternative_action: str = "",
        notes: str = "",
    ) -> SnackingLog:
        """Zaloguj epizod podjadania z pełnym kontekstem."""
        now = datetime.now().isoformat()
        snack_id = self.db.insert("snacking_log", {
            "timestamp": now,
            "trigger_type": trigger_type,
            "trigger_detail": trigger_detail,
            "food_eaten": food_eaten,
            "amount": amount,
            "intensity": intensity,
            "feeling_after": feeling_after,
            "alternative_action": alternative_action,
            "notes": notes,
            "created_at": now,
        })
        # Kompatybilność z core habit_log
        self.db.insert("habit_log", {
            "timestamp": now,
            "habit_type": "snacking",
            "value": food_eaten or "occurred",
            "intensity": intensity,
            "notes": f"Trigger: {trigger_type} | After: {feeling_after} | {notes}",
            "created_at": now,
        })
        return self.get_snack(snack_id)  # type: ignore[return-value]

    def get_snack(self, snack_id: int) -> Optional[SnackingLog]:
        """Pobierz epizod podjadania po ID."""
        row = self.db.execute_one(
            "SELECT * FROM snacking_log WHERE id = ?", (snack_id,)
        )
        return SnackingLog(**row) if row else None

    def get_snacks(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        trigger_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Pobierz epizody podjadania z filtrami."""
        conditions = ["1=1"]
        params: list = []

        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)
        if trigger_type:
            conditions.append("trigger_type = ?")
            params.append(trigger_type)

        where = " AND ".join(conditions)
        return self.db.execute(
            f"SELECT * FROM snacking_log WHERE {where} ORDER BY timestamp DESC LIMIT ?",
            tuple(params) + (limit,),
        )

    def get_trigger_breakdown(self, days: int = 30) -> dict:
        """Rozkład triggerów podjadania."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self.db.execute("""
            SELECT trigger_type, COUNT(*) as count, AVG(intensity) as avg_intensity
            FROM snacking_log
            WHERE timestamp >= ?
            GROUP BY trigger_type
            ORDER BY count DESC
        """, (since,))
        return {
            "period_days": days,
            "total_episodes": sum(r["count"] for r in rows),
            "triggers": {r["trigger_type"]: {
                "count": r["count"],
                "avg_intensity": round(r["avg_intensity"], 1) if r["avg_intensity"] else 0,
            } for r in rows},
        }

    def get_feeling_after_breakdown(self, days: int = 30) -> dict:
        """Jak się czujesz po podjadaniu — rozkład."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self.db.execute("""
            SELECT feeling_after, COUNT(*) as count
            FROM snacking_log
            WHERE timestamp >= ? AND feeling_after != ''
            GROUP BY feeling_after
            ORDER BY count DESC
        """, (since,))
        return {
            "period_days": days,
            "feelings": {r["feeling_after"]: r["count"] for r in rows},
        }

    def get_trigger_response_map(self, days: int = 60) -> dict:
        """Mapa trigger → response: co jesz przy danym triggerze i jak się czujesz."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self.db.execute("""
            SELECT trigger_type, food_eaten, feeling_after, COUNT(*) as count
            FROM snacking_log
            WHERE timestamp >= ? AND trigger_type != ''
            GROUP BY trigger_type, food_eaten, feeling_after
            ORDER BY trigger_type, count DESC
        """, (since,))
        result: dict = {}
        for r in rows:
            tt = r["trigger_type"]
            if tt not in result:
                result[tt] = []
            result[tt].append({
                "food": r["food_eaten"],
                "feeling": r["feeling_after"],
                "count": r["count"],
            })
        return {"period_days": days, "trigger_response_map": result}


# ── Focus / Pomodoro Tracker ─────────────────────────────────────────────────

class FocusTracker:
    """Śledzenie sesji deep work / Pomodoro."""

    def __init__(self, db: MindDB):
        self.db = db
        self._current_session_start: Optional[datetime] = None
        self._current_task: str = ""
        self._current_duration: int = 25
        self._distractions: list[str] = []

    def start_session(
        self,
        task_description: str = "",
        duration_minutes: int = 25,
    ) -> FocusSession:
        """Rozpocznij sesję focus. Automatycznie kończy poprzednią."""
        if self._current_session_start is not None:
            self.end_session(completed=False)

        now = datetime.now()
        self._current_session_start = now
        self._current_task = task_description
        self._current_duration = duration_minutes
        self._distractions = []

        return FocusSession(
            start_time=now.isoformat(),
            duration_minutes=duration_minutes,
            task_description=task_description,
            created_at=now.isoformat(),
        )

    def log_distraction(self, what: str) -> None:
        """Zaloguj dystrakcję podczas aktywnej sesji."""
        if self._current_session_start is not None:
            self._distractions.append(what)

    def end_session(
        self,
        completed: bool = True,
        productivity_score: int = 5,
        focus_level: int = 5,
        notes: str = "",
    ) -> Optional[FocusSession]:
        """Zakończ sesję focus i zapisz do bazy."""
        if self._current_session_start is None:
            return None

        now = datetime.now()
        start = self._current_session_start
        actual_minutes = int((now - start).total_seconds() / 60)

        session = FocusSession(
            start_time=start.isoformat(),
            end_time=now.isoformat(),
            duration_minutes=self._current_duration,
            actual_duration_minutes=actual_minutes,
            task_description=self._current_task,
            distractions=json.dumps(self._distractions),
            distraction_count=len(self._distractions),
            productivity_score=productivity_score,
            focus_level=focus_level,
            completed=completed,
            notes=notes,
            created_at=now.isoformat(),
        )

        session_id = self.db.insert("focus_sessions", {
            "start_time": session.start_time,
            "end_time": session.end_time,
            "duration_minutes": session.duration_minutes,
            "actual_duration_minutes": session.actual_duration_minutes,
            "task_description": session.task_description,
            "distractions": session.distractions,
            "distraction_count": session.distraction_count,
            "productivity_score": session.productivity_score,
            "focus_level": session.focus_level,
            "completed": int(session.completed),
            "notes": session.notes,
            "created_at": session.created_at,
        })
        session.id = session_id

        # Kompatybilność z core habit_log
        self.db.insert("habit_log", {
            "timestamp": now.isoformat(),
            "habit_type": "focus_session",
            "value": f"{actual_minutes}min",
            "intensity": productivity_score,
            "notes": f"Task: {self._current_task} | Distractions: {len(self._distractions)} | {'✓' if completed else '✗'}",
            "created_at": now.isoformat(),
        })

        self._current_session_start = None
        self._current_task = ""
        self._current_duration = 25
        self._distractions = []

        return session

    def log_manual_session(
        self,
        start_time: str,
        end_time: str,
        task_description: str = "",
        duration_minutes: int = 25,
        distractions: Optional[list[str]] = None,
        productivity_score: int = 5,
        focus_level: int = 5,
        completed: bool = True,
        notes: str = "",
    ) -> FocusSession:
        """Ręcznie dodaj sesję focus (np. wstecz)."""
        dist_list = distractions or []
        actual_minutes = duration_minutes  # przy ręcznym wpisie zakładamy planowaną

        session = FocusSession(
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            actual_duration_minutes=actual_minutes,
            task_description=task_description,
            distractions=json.dumps(dist_list),
            distraction_count=len(dist_list),
            productivity_score=productivity_score,
            focus_level=focus_level,
            completed=completed,
            notes=notes,
            created_at=datetime.now().isoformat(),
        )

        session_id = self.db.insert("focus_sessions", {
            "start_time": session.start_time,
            "end_time": session.end_time,
            "duration_minutes": session.duration_minutes,
            "actual_duration_minutes": session.actual_duration_minutes,
            "task_description": session.task_description,
            "distractions": session.distractions,
            "distraction_count": session.distraction_count,
            "productivity_score": session.productivity_score,
            "focus_level": session.focus_level,
            "completed": int(session.completed),
            "notes": session.notes,
            "created_at": session.created_at,
        })
        session.id = session_id

        # Kompatybilność z core habit_log
        self.db.insert("habit_log", {
            "timestamp": datetime.now().isoformat(),
            "habit_type": "focus_session",
            "value": f"{actual_minutes}min",
            "intensity": productivity_score,
            "notes": f"Task: {task_description} | Distractions: {len(dist_list)} | {'✓' if completed else '✗'}",
            "created_at": datetime.now().isoformat(),
        })

        return session

    def get_sessions(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Pobierz sesje focus z filtrami."""
        conditions = ["1=1"]
        params: list = []

        if start_date:
            conditions.append("start_time >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("start_time <= ?")
            params.append(end_date)

        where = " AND ".join(conditions)
        return self.db.execute(
            f"SELECT * FROM focus_sessions WHERE {where} ORDER BY start_time DESC LIMIT ?",
            tuple(params) + (limit,),
        )

    def get_today_focus_summary(self) -> dict:
        """Podsumowanie dzisiejszych sesji focus."""
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        rows = self.db.execute("""
            SELECT COUNT(*) as session_count,
                   SUM(actual_duration_minutes) as total_minutes,
                   AVG(productivity_score) as avg_productivity,
                   AVG(focus_level) as avg_focus,
                   SUM(distraction_count) as total_distractions,
                   SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed_count
            FROM focus_sessions
            WHERE start_time >= ? AND start_time < ?
        """, (today, tomorrow))

        r = rows[0] if rows else {}
        return {
            "date": today,
            "session_count": r.get("session_count", 0) or 0,
            "total_minutes": r.get("total_minutes", 0) or 0,
            "total_hours": round((r.get("total_minutes", 0) or 0) / 60, 1),
            "avg_productivity": round(r.get("avg_productivity", 0) or 0, 1),
            "avg_focus": round(r.get("avg_focus", 0) or 0, 1),
            "total_distractions": r.get("total_distractions", 0) or 0,
            "completed_count": r.get("completed_count", 0) or 0,
        }

    def get_weekly_focus_report(self) -> dict:
        """Raport tygodniowy sesji focus."""
        today = date.today()
        week_start = (today - timedelta(days=today.weekday())).isoformat()
        week_end = (today + timedelta(days=1)).isoformat()

        rows = self.db.execute("""
            SELECT date(start_time) as day,
                   COUNT(*) as sessions,
                   SUM(actual_duration_minutes) as total_minutes,
                   AVG(productivity_score) as avg_productivity,
                   SUM(distraction_count) as distractions
            FROM focus_sessions
            WHERE start_time >= ? AND start_time < ?
            GROUP BY day
            ORDER BY day
        """, (week_start, week_end))

        daily = [{
            "day": r["day"],
            "sessions": r["sessions"],
            "total_minutes": r["total_minutes"],
            "avg_productivity": round(r["avg_productivity"], 1) if r["avg_productivity"] else 0,
            "distractions": r["distractions"],
        } for r in rows]

        total_minutes = sum(d["total_minutes"] for d in daily)
        return {
            "week_start": week_start,
            "week_end": week_end,
            "total_sessions": sum(d["sessions"] for d in daily),
            "total_hours": round(total_minutes / 60, 1),
            "avg_daily_hours": round(total_minutes / 60 / 7, 1),
            "daily": daily,
        }

    def get_top_distractions(self, days: int = 30, limit: int = 10) -> list[dict]:
        """Najczęstsze dystrakcje."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self.db.execute(
            "SELECT distractions FROM focus_sessions WHERE start_time >= ? AND distractions != '[]'",
            (since,),
        )

        dist_counter: dict[str, int] = {}
        for r in rows:
            try:
                dists = json.loads(r["distractions"])
                for d in dists:
                    dist_counter[d] = dist_counter.get(d, 0) + 1
            except (json.JSONDecodeError, TypeError):
                continue

        sorted_dists = sorted(dist_counter.items(), key=lambda x: -x[1])[:limit]
        return [{"distraction": d, "count": c} for d, c in sorted_dists]


# ── Daily Goals Manager ──────────────────────────────────────────────────────

class DailyGoalsManager:
    """Zarządzanie celami dziennymi (3 MITs)."""

    def __init__(self, db: MindDB):
        self.db = db

    def set_goals(self, goals: list[str], goal_date: Optional[str] = None) -> list[DailyGoal]:
        """Ustaw cele na dany dzień (max 3). Zastępuje istniejące cele na ten dzień."""
        if goal_date is None:
            goal_date = date.today().isoformat()

        # Usuń stare cele na ten dzień
        self.db.delete("daily_goals", "goal_date = ?", (goal_date,))

        now = datetime.now().isoformat()
        result = []
        for i, text in enumerate(goals[:3], start=1):
            goal_id = self.db.insert("daily_goals", {
                "goal_date": goal_date,
                "priority_order": i,
                "goal_text": text,
                "completed": 0,
                "notes": "",
                "created_at": now,
            })
            result.append(DailyGoal(
                id=goal_id,
                goal_date=goal_date,
                priority_order=i,
                goal_text=text,
                completed=False,
                created_at=now,
            ))
        return result

    def get_today_goals(self) -> list[DailyGoal]:
        """Pobierz dzisiejsze cele."""
        today = date.today().isoformat()
        rows = self.db.execute(
            "SELECT * FROM daily_goals WHERE goal_date = ? ORDER BY priority_order",
            (today,),
        )
        return [DailyGoal(**r) for r in rows]

    def get_goals_for_date(self, goal_date: str) -> list[DailyGoal]:
        """Pobierz cele na konkretną datę."""
        rows = self.db.execute(
            "SELECT * FROM daily_goals WHERE goal_date = ? ORDER BY priority_order",
            (goal_date,),
        )
        return [DailyGoal(**r) for r in rows]

    def complete_goal(self, goal_id: int) -> Optional[DailyGoal]:
        """Oznacz cel jako ukończony."""
        now = datetime.now().isoformat()
        self.db.update("daily_goals", {
            "completed": 1,
            "completed_at": now,
        }, "id = ?", (goal_id,))
        row = self.db.execute_one("SELECT * FROM daily_goals WHERE id = ?", (goal_id,))
        return DailyGoal(**row) if row else None

    def uncomplete_goal(self, goal_id: int) -> Optional[DailyGoal]:
        """Cofnij ukończenie celu."""
        self.db.update("daily_goals", {
            "completed": 0,
            "completed_at": None,
        }, "id = ?", (goal_id,))
        row = self.db.execute_one("SELECT * FROM daily_goals WHERE id = ?", (goal_id,))
        return DailyGoal(**row) if row else None

    def get_completion_stats(self, days: int = 30) -> dict:
        """Statystyki ukończenia celów."""
        since = (date.today() - timedelta(days=days)).isoformat()
        rows = self.db.execute("""
            SELECT goal_date,
                   COUNT(*) as total,
                   SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed
            FROM daily_goals
            WHERE goal_date >= ?
            GROUP BY goal_date
            ORDER BY goal_date DESC
        """, (since,))

        daily_stats = [{
            "date": r["goal_date"],
            "total": r["total"],
            "completed": r["completed"],
            "pct": round(r["completed"] / r["total"] * 100, 1) if r["total"] > 0 else 0,
        } for r in rows]

        total_goals = sum(d["total"] for d in daily_stats)
        total_completed = sum(d["completed"] for d in daily_stats)

        return {
            "period_days": days,
            "days_with_goals": len(daily_stats),
            "total_goals": total_goals,
            "total_completed": total_completed,
            "completion_rate": round(total_completed / total_goals * 100, 1) if total_goals > 0 else 0,
            "daily": daily_stats,
        }


# ── Weekly Review Manager ────────────────────────────────────────────────────

class WeeklyReviewManager:
    """Cotygodniowe przeglądy — refleksja i planowanie."""

    def __init__(self, db: MindDB):
        self.db = db

    def create_review(
        self,
        what_went_well: str = "",
        what_to_improve: str = "",
        lessons_learned: str = "",
        gratitude: str = "",
        energy_avg: int = 5,
        mood_avg: int = 5,
        next_week_focus: str = "",
        week_start: Optional[str] = None,
    ) -> WeeklyReview:
        """Stwórz cotygodniowy przegląd."""
        if week_start is None:
            today = date.today()
            week_start = (today - timedelta(days=today.weekday())).isoformat()
        week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()

        # Policz cele z tego tygodnia
        goal_stats = self.db.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed
            FROM daily_goals
            WHERE goal_date >= ? AND goal_date <= ?
        """, (week_start, week_end))
        gs = goal_stats[0] if goal_stats else {}

        now = datetime.now().isoformat()
        review_id = self.db.insert("weekly_reviews", {
            "week_start": week_start,
            "week_end": week_end,
            "what_went_well": what_went_well,
            "what_to_improve": what_to_improve,
            "lessons_learned": lessons_learned,
            "gratitude": gratitude,
            "energy_avg": energy_avg,
            "mood_avg": mood_avg,
            "goals_completed": gs.get("completed", 0) or 0,
            "goals_total": gs.get("total", 0) or 0,
            "next_week_focus": next_week_focus,
            "created_at": now,
        })
        return self.get_review(review_id)  # type: ignore[return-value]

    def get_review(self, review_id: int) -> Optional[WeeklyReview]:
        """Pobierz przegląd po ID."""
        row = self.db.execute_one(
            "SELECT * FROM weekly_reviews WHERE id = ?", (review_id,)
        )
        return WeeklyReview(**row) if row else None

    def get_review_for_week(self, week_start: str) -> Optional[WeeklyReview]:
        """Pobierz przegląd dla konkretnego tygodnia."""
        row = self.db.execute_one(
            "SELECT * FROM weekly_reviews WHERE week_start = ?", (week_start,)
        )
        return WeeklyReview(**row) if row else None

    def get_latest_review(self) -> Optional[WeeklyReview]:
        """Pobierz najnowszy przegląd."""
        row = self.db.execute_one(
            "SELECT * FROM weekly_reviews ORDER BY week_start DESC LIMIT 1"
        )
        return WeeklyReview(**row) if row else None

    def get_all_reviews(self, limit: int = 12) -> list[WeeklyReview]:
        """Pobierz wszystkie przeglądy."""
        rows = self.db.execute(
            "SELECT * FROM weekly_reviews ORDER BY week_start DESC LIMIT ?",
            (limit,),
        )
        return [WeeklyReview(**r) for r in rows]

    def update_review(self, review_id: int, **kwargs) -> Optional[WeeklyReview]:
        """Zaktualizuj przegląd."""
        self.db.update("weekly_reviews", kwargs, "id = ?", (review_id,))
        return self.get_review(review_id)

    def get_lessons_timeline(self, limit: int = 20) -> list[dict]:
        """Oś czasu lessons learned ze wszystkich przeglądów."""
        rows = self.db.execute("""
            SELECT week_start, lessons_learned
            FROM weekly_reviews
            WHERE lessons_learned != ''
            ORDER BY week_start DESC
            LIMIT ?
        """, (limit,))
        return [{"week_start": r["week_start"], "lessons": r["lessons_learned"]} for r in rows]


# ── Mind & Habits Report Generator ───────────────────────────────────────────

class MindReportGenerator:
    """Generuje raporty dla modułu Mind & Habits."""

    def __init__(self, db: MindDB):
        self.db = db
        self.thoughts = IntrusiveThoughtTracker(db)
        self.snacks = SnackingTracker(db)
        self.focus = FocusTracker(db)
        self.goals = DailyGoalsManager(db)
        self.reviews = WeeklyReviewManager(db)

    def mind_daily_brief(self) -> str:
        """Codzienny raport Mind & Habits."""
        today = date.today()
        focus_summary = self.focus.get_today_focus_summary()
        today_goals = self.goals.get_today_goals()
        today_thoughts = self.thoughts.get_thoughts(
            start_date=today.isoformat(),
            end_date=(today + timedelta(days=1)).isoformat(),
        )
        today_snacks = self.snacks.get_snacks(
            start_date=today.isoformat(),
            end_date=(today + timedelta(days=1)).isoformat(),
        )

        lines = [
            f"🧠 MIND & HABITS — {today.strftime('%A, %d.%m.%Y')}",
            "=" * 40,
            "",
            "🎯 CELE DNIA:",
        ]
        if today_goals:
            for g in today_goals:
                icon = "✅" if g.completed else "⬜"
                lines.append(f"   {icon} [{g.priority_order}] {g.goal_text}")
        else:
            lines.append("   ❌ Brak celów na dziś — ustaw je!")

        lines.extend([
            "",
            "⏲️ FOCUS:",
            f"   Sesji: {focus_summary['session_count']} | Czas: {focus_summary['total_hours']}h",
            f"   Produktywność: {focus_summary['avg_productivity']}/10 | Focus: {focus_summary['avg_focus']}/10",
            f"   Dystrakcji: {focus_summary['total_distractions']} | Ukończonych: {focus_summary['completed_count']}",
            "",
            "🧘 MYŚLI:",
            f"   Natarczywych myśli dziś: {len(today_thoughts)}",
        ])
        for t in today_thoughts[:3]:
            lines.append(f"   • {t['cbt_pattern']} (intensywność: {t['intensity']}) — {t['trigger'][:50]}")

        lines.extend([
            "",
            "🍪 PODJADANIE:",
            f"   Epizodów dziś: {len(today_snacks)}",
        ])
        for s in today_snacks[:3]:
            lines.append(f"   • Trigger: {s['trigger_type']} → {s['food_eaten']} → {s['feeling_after']}")

        return "\n".join(lines)

    def mind_weekly_report(self) -> str:
        """Raport tygodniowy Mind & Habits."""
        focus_report = self.focus.get_weekly_focus_report()
        cbt_breakdown = self.thoughts.get_cbt_pattern_breakdown(days=7)
        trigger_breakdown = self.snacks.get_trigger_breakdown(days=7)
        goal_stats = self.goals.get_completion_stats(days=7)
        latest_review = self.reviews.get_latest_review()

        lines = [
            "📊 MIND & HABITS — RAPORT TYGODNIOWY",
            "=" * 40,
            "",
            "⏲️ FOCUS:",
            f"   Sesji: {focus_report['total_sessions']} | Łącznie: {focus_report['total_hours']}h",
            f"   Średnio dziennie: {focus_report['avg_daily_hours']}h",
        ]
        for d in focus_report.get("daily", []):
            bar = "█" * min(d["sessions"], 10)
            lines.append(f"   {d['day']}: {bar} {d['sessions']} sesji ({d['total_minutes']}min)")

        lines.extend([
            "",
            "🎯 CELE:",
            f"   Ukończono: {goal_stats['total_completed']}/{goal_stats['total_goals']} ({goal_stats['completion_rate']}%)",
            "",
            "🧘 CBT PATTERNS:",
            f"   Myśli w tygodniu: {cbt_breakdown['total_thoughts']}",
        ])
        for pattern, data in cbt_breakdown.get("patterns", {}).items():
            lines.append(f"   • {pattern}: {data['count']}x (śr. intensywność: {data['avg_intensity']})")

        lines.extend([
            "",
            "🍪 PODJADANIE:",
            f"   Epizodów: {trigger_breakdown['total_episodes']}",
        ])
        for trigger, data in trigger_breakdown.get("triggers", {}).items():
            lines.append(f"   • {trigger}: {data['count']}x (śr. intensywność: {data['avg_intensity']})")

        if latest_review:
            lines.extend([
                "",
                "📝 OSTATNI WEEKLY REVIEW:",
                f"   Tydzień: {latest_review.week_start} → {latest_review.week_end}",
                f"   ✅ Co poszło dobrze: {latest_review.what_went_well[:100]}",
                f"   🔧 Do poprawy: {latest_review.what_to_improve[:100]}",
                f"   📚 Lessons: {latest_review.lessons_learned[:100]}",
            ])

        return "\n".join(lines)


# ── CLI Extension ────────────────────────────────────────────────────────────

def mind_cli_main():
    """CLI dla modułu Mind & Habits."""
    import sys

    db_path = os.environ.get("MIND_DB_PATH", "")
    db = MindDB(db_path) if db_path else MindDB()
    thoughts = IntrusiveThoughtTracker(db)
    snacks = SnackingTracker(db)
    focus = FocusTracker(db)
    goals = DailyGoalsManager(db)
    reviews = WeeklyReviewManager(db)
    reports = MindReportGenerator(db)

    if len(sys.argv) < 2:
        print("🧠 Mind & Habits — CLI")
        print()
        print("Komendy:")
        print("  thought-log <treść> <trigger> <cbt_pattern> [intensity]")
        print("  thought-list [dni] [cbt_pattern]")
        print("  thought-patterns [dni]")
        print("  thought-triggers [dni]")
        print("  thought-coping [dni]")
        print("  snack-log <trigger> <food> <feeling> [intensity]")
        print("  snack-list [dni] [trigger]")
        print("  snack-triggers [dni]")
        print("  snack-feelings [dni]")
        print("  snack-map [dni]")
        print("  focus-start <task> [duration_min]")
        print("  focus-distract <co>")
        print("  focus-end [productivity] [focus_level]")
        print("  focus-today")
        print("  focus-week")
        print("  focus-distractions [dni]")
        print("  goals-set <cel1> | <cel2> | <cel3>")
        print("  goals-today")
        print("  goals-done <id>")
        print("  goals-undone <id>")
        print("  goals-stats [dni]")
        print("  review-create")
        print("  review-latest")
        print("  review-list")
        print("  review-lessons")
        print("  mind-brief")
        print("  mind-week")
        return

    cmd = sys.argv[1]

    # ── Intrusive Thoughts ──
    if cmd == "thought-log" and len(sys.argv) >= 5:
        content = sys.argv[2]
        trigger = sys.argv[3]
        cbt = sys.argv[4]
        intensity = int(sys.argv[5]) if len(sys.argv) >= 6 else 5
        t = thoughts.log_thought(
            thought_content=content,
            trigger=trigger,
            cbt_pattern=cbt,
            intensity=intensity,
        )
        print(f"🧠 Zalogowano myśl [{t.id}]: {cbt} (intensywność: {intensity}/10)")

    elif cmd == "thought-list":
        days = int(sys.argv[2]) if len(sys.argv) >= 3 else 7
        cbt_filter = sys.argv[3] if len(sys.argv) >= 4 else None
        since = (datetime.now() - timedelta(days=days)).isoformat()
        items = thoughts.get_thoughts(start_date=since, cbt_pattern=cbt_filter)
        for t in items:
            print(f"  [{t['id']}] {t['timestamp'][:16]} | {t['cbt_pattern']} | {t['trigger'][:40]} | intensywność: {t['intensity']}")

    elif cmd == "thought-patterns":
        days = int(sys.argv[2]) if len(sys.argv) >= 3 else 30
        breakdown = thoughts.get_cbt_pattern_breakdown(days=days)
        print(f"🧠 CBT Patterns ({breakdown['period_days']}d) — {breakdown['total_thoughts']} myśli:")
        for pattern, data in breakdown["patterns"].items():
            print(f"  • {pattern}: {data['count']}x (śr. intensywność: {data['avg_intensity']}, coping: {data['avg_coping_effectiveness']}/10)")

    elif cmd == "thought-triggers":
        days = int(sys.argv[2]) if len(sys.argv) >= 3 else 30
        triggers = thoughts.get_top_triggers(days=days)
        print(f"🎯 Top triggery ({days}d):")
        for t in triggers:
            print(f"  • {t['trigger']}: {t['count']}x (śr. intensywność: {round(t['avg_intensity'], 1)})")

    elif cmd == "thought-coping":
        days = int(sys.argv[2]) if len(sys.argv) >= 3 else 30
        coping = thoughts.get_coping_effectiveness_report(days=days)
        print(f"🛡️ Skuteczność strategii ({days}d):")
        for strategy, data in coping["strategies"].items():
            print(f"  • {strategy}: skuteczność {data['avg_effectiveness']}/10 ({data['count']}x)")

    # ── Snacking ──
    elif cmd == "snack-log" and len(sys.argv) >= 5:
        trigger = sys.argv[2]
        food = sys.argv[3]
        feeling = sys.argv[4]
        intensity = int(sys.argv[5]) if len(sys.argv) >= 6 else 5
        s = snacks.log_snack(
            trigger_type=trigger,
            food_eaten=food,
            feeling_after=feeling,
            intensity=intensity,
        )
        print(f"🍪 Zalogowano podjadanie [{s.id}]: {trigger} → {food} → {feeling}")

    elif cmd == "snack-list":
        days = int(sys.argv[2]) if len(sys.argv) >= 3 else 7
        trigger_filter = sys.argv[3] if len(sys.argv) >= 4 else None
        since = (datetime.now() - timedelta(days=days)).isoformat()
        items = snacks.get_snacks(start_date=since, trigger_type=trigger_filter)
        for s in items:
            print(f"  [{s['id']}] {s['timestamp'][:16]} | {s['trigger_type']} → {s['food_eaten']} → {s['feeling_after']}")

    elif cmd == "snack-triggers":
        days = int(sys.argv[2]) if len(sys.argv) >= 3 else 30
        breakdown = snacks.get_trigger_breakdown(days=days)
        print(f"🍪 Triggery podjadania ({breakdown['period_days']}d) — {breakdown['total_episodes']} epizodów:")
        for trigger, data in breakdown["triggers"].items():
            print(f"  • {trigger}: {data['count']}x (śr. intensywność: {data['avg_intensity']})")

    elif cmd == "snack-feelings":
        days = int(sys.argv[2]) if len(sys.argv) >= 3 else 30
        feelings = snacks.get_feeling_after_breakdown(days=days)
        print(f"😶 Uczucia po podjadaniu ({days}d):")
        for feeling, count in feelings["feelings"].items():
            print(f"  • {feeling}: {count}x")

    elif cmd == "snack-map":
        days = int(sys.argv[2]) if len(sys.argv) >= 3 else 60
        tmap = snacks.get_trigger_response_map(days=days)
        print(f"🗺️ Trigger → Response Map ({days}d):")
        for trigger, responses in tmap["trigger_response_map"].items():
            print(f"  🔹 {trigger}:")
            for r in responses[:3]:
                print(f"     → {r['food']} → {r['feeling']} ({r['count']}x)")

    # ── Focus / Pomodoro ──
    elif cmd == "focus-start" and len(sys.argv) >= 3:
        task = sys.argv[2]
        duration = int(sys.argv[3]) if len(sys.argv) >= 4 else 25
        session = focus.start_session(task_description=task, duration_minutes=duration)
        print(f"⏲️ START FOCUS: {task} ({duration}min) — {session.start_time[:16]}")

    elif cmd == "focus-distract" and len(sys.argv) >= 3:
        what = sys.argv[2]
        focus.log_distraction(what)
        print(f"⚠️ Dystrakcja: {what}")

    elif cmd == "focus-end":
        productivity = int(sys.argv[2]) if len(sys.argv) >= 3 else 5
        focus_level = int(sys.argv[3]) if len(sys.argv) >= 4 else 5
        session = focus.end_session(productivity_score=productivity, focus_level=focus_level)
        if session:
            print(f"⏹️ END FOCUS: {session.task_description} — {session.actual_duration_minutes}min | prod: {productivity}/10 | focus: {focus_level}/10 | dystrakcji: {session.distraction_count}")
        else:
            print("❌ Brak aktywnej sesji focus")

    elif cmd == "focus-today":
        summary = focus.get_today_focus_summary()
        print(f"⏲️ Focus dziś: {summary['session_count']} sesji, {summary['total_hours']}h")
        print(f"   Produktywność: {summary['avg_productivity']}/10 | Focus: {summary['avg_focus']}/10")
        print(f"   Dystrakcji: {summary['total_distractions']} | Ukończonych: {summary['completed_count']}")

    elif cmd == "focus-week":
        report = focus.get_weekly_focus_report()
        print(f"⏲️ Focus — tydzień {report['week_start']} → {report['week_end']}")
        print(f"   Sesji: {report['total_sessions']} | Łącznie: {report['total_hours']}h | Śr. dziennie: {report['avg_daily_hours']}h")
        for d in report["daily"]:
            print(f"   {d['day']}: {d['sessions']} sesji ({d['total_minutes']}min) | prod: {d['avg_productivity']}")

    elif cmd == "focus-distractions":
        days = int(sys.argv[2]) if len(sys.argv) >= 3 else 30
        dists = focus.get_top_distractions(days=days)
        print(f"⚠️ Top dystrakcje ({days}d):")
        for d in dists:
            print(f"  • {d['distraction']}: {d['count']}x")

    # ── Daily Goals ──
    elif cmd == "goals-set" and len(sys.argv) >= 3:
        # Format: goals-set cel1 | cel2 | cel3
        goals_text = " ".join(sys.argv[2:])
        goal_list = [g.strip() for g in goals_text.split("|")]
        result = goals.set_goals(goal_list)
        print(f"🎯 Ustawiono {len(result)} cele na dziś:")
        for g in result:
            print(f"   [{g.id}] {g.goal_text}")

    elif cmd == "goals-today":
        today_goals = goals.get_today_goals()
        if today_goals:
            print("🎯 Dzisiejsze cele:")
            for g in today_goals:
                icon = "✅" if g.completed else "⬜"
                print(f"   {icon} [{g.id}] {g.goal_text}")
        else:
            print("❌ Brak celów na dziś")

    elif cmd == "goals-done" and len(sys.argv) >= 3:
        goal_id = int(sys.argv[2])
        g = goals.complete_goal(goal_id)
        if g:
            print(f"✅ Ukończono: {g.goal_text}")

    elif cmd == "goals-undone" and len(sys.argv) >= 3:
        goal_id = int(sys.argv[2])
        g = goals.uncomplete_goal(goal_id)
        if g:
            print(f"⬜ Cofnięto: {g.goal_text}")

    elif cmd == "goals-stats":
        days = int(sys.argv[2]) if len(sys.argv) >= 3 else 30
        stats = goals.get_completion_stats(days=days)
        print(f"🎯 Cele ({stats['period_days']}d):")
        print(f"   Ukończono: {stats['total_completed']}/{stats['total_goals']} ({stats['completion_rate']}%)")
        print(f"   Dni z celami: {stats['days_with_goals']}")

    # ── Weekly Review ──
    elif cmd == "review-create":
        print("📝 TWORZENIE WEEKLY REVIEW")
        print("(Wpisz 'done' w nowej linii aby zakończyć każdą sekcję)")
        print()

        sections = [
            ("what_went_well", "✅ Co poszło dobrze?"),
            ("what_to_improve", "🔧 Co poprawić?"),
            ("lessons_learned", "📚 Czego się nauczyłeś?"),
            ("gratitude", "🙏 Za co jesteś wdzięczny?"),
            ("next_week_focus", "🎯 Na czym skupić się w przyszłym tygodniu?"),
        ]

        data = {}
        for key, prompt in sections:
            print(f"{prompt}")
            lines = []
            while True:
                try:
                    line = input()
                except EOFError:
                    break
                if line.strip().lower() == "done":
                    break
                lines.append(line)
            data[key] = "\n".join(lines)

        try:
            energy = int(input("⚡ Średni poziom energii (1-10): ") or "5")
        except (EOFError, ValueError):
            energy = 5
        try:
            mood = int(input("😊 Średni nastrój (1-10): ") or "5")
        except (EOFError, ValueError):
            mood = 5

        review = reviews.create_review(
            what_went_well=data["what_went_well"],
            what_to_improve=data["what_to_improve"],
            lessons_learned=data["lessons_learned"],
            gratitude=data["gratitude"],
            energy_avg=energy,
            mood_avg=mood,
            next_week_focus=data["next_week_focus"],
        )
        print(f"\n✅ Weekly review zapisany! ({review.week_start} → {review.week_end})")

    elif cmd == "review-latest":
        review = reviews.get_latest_review()
        if review:
            print(f"📝 Weekly Review: {review.week_start} → {review.week_end}")
            print(f"   ✅ Co poszło dobrze: {review.what_went_well}")
            print(f"   🔧 Do poprawy: {review.what_to_improve}")
            print(f"   📚 Lessons: {review.lessons_learned}")
            print(f"   🙏 Wdzięczność: {review.gratitude}")
            print(f"   ⚡ Energia: {review.energy_avg}/10 | 😊 Nastrój: {review.mood_avg}/10")
            print(f"   🎯 Cele: {review.goals_completed}/{review.goals_total}")
            print(f"   🔜 Next week: {review.next_week_focus}")
        else:
            print("❌ Brak weekly review")

    elif cmd == "review-list":
        all_reviews = reviews.get_all_reviews(limit=12)
        for r in all_reviews:
            print(f"  📝 {r.week_start} → {r.week_end} | ⚡{r.energy_avg} 😊{r.mood_avg} | 🎯{r.goals_completed}/{r.goals_total}")

    elif cmd == "review-lessons":
        lessons = reviews.get_lessons_timeline(limit=20)
        for l in lessons:
            print(f"  📚 {l['week_start']}: {l['lessons'][:100]}")

    # ── Reports ──
    elif cmd == "mind-brief":
        print(reports.mind_daily_brief())

    elif cmd == "mind-week":
        print(reports.mind_weekly_report())

    else:
        print(f"❌ Nieznana komenda: {cmd}")
        print("Uruchom bez argumentów aby zobaczyć dostępne komendy.")


if __name__ == "__main__":
    mind_cli_main()
