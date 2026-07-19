"""
Life Management Reports — połączone raporty z Time Tracker + People CRM.
Weekly summary, daily briefing, balance alerts.

Usage:
    reporter = Reporter()
    reporter.daily_briefing()
    reporter.weekly_summary()
    reporter.balance_alert()
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any
from pathlib import Path

from .schema import get_db, init_db
from .time_tracker import TimeTracker, CATEGORY_LABELS as TIME_LABELS
from .people_crm import PeopleCRM, CATEGORY_LABELS as PEOPLE_LABELS


class Reporter:
    """Generate reports combining time tracking and people management."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.conn = sqlite3.connect(db_path)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.row_factory = sqlite3.Row
        else:
            self.conn = get_db()
        init_db()
        self.tracker = TimeTracker(db_path) if db_path else TimeTracker()
        self.crm = PeopleCRM(db_path) if db_path else PeopleCRM()

    # ─── DAILY BRIEFING ─────────────────────────────────────

    def daily_briefing(self) -> Dict[str, Any]:
        """Generate a morning/evening briefing."""
        today = date.today().isoformat()
        now = datetime.now(timezone.utc)

        # Time summary
        time_summary = self.tracker.summary_today()

        # People to contact today
        to_contact = self.crm.who_to_contact_today(limit=5)

        # Upcoming birthdays (next 7 days)
        birthdays = self.crm.get_upcoming_birthdays(days_ahead=7)

        # Active habits (from habit_log)
        habits_today = self._get_habits_today(today)

        # Health today
        health = self._get_health_today(today)

        # Focus sessions today
        focus = self._get_focus_today(today)

        # Waste alert
        waste_minutes = time_summary["breakdown"].get("waste", 0)
        waste_alert = waste_minutes > 60  # alert if > 1h wasted

        return {
            "date": today,
            "time": {
                "total_hours": time_summary["total_hours"],
                "breakdown": time_summary["breakdown_labels"],
                "active_block": time_summary["active_block"],
                "waste_alert": waste_alert,
                "waste_minutes": waste_minutes,
            },
            "people": {
                "to_contact_today": to_contact,
                "upcoming_birthdays": birthdays,
                "total_people": len(self.crm.get_all_people()),
            },
            "health": health,
            "habits": habits_today,
            "focus": focus,
            "alerts": self._generate_alerts(time_summary, to_contact, health),
        }

    # ─── WEEKLY SUMMARY ─────────────────────────────────────

    def weekly_summary(self) -> Dict[str, Any]:
        """Generate a comprehensive weekly summary."""
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)

        monday_str = monday.isoformat()
        sunday_str = sunday.isoformat()

        # Time breakdown
        time_summary = self.tracker.summary_range(monday_str, sunday_str)

        # People balance
        people_balance = self.crm.balance_report()

        # Health averages
        health = self._get_health_range(monday_str, sunday_str)

        # Habits completion
        habits = self._get_habits_range(monday_str, sunday_str)

        # Focus sessions
        focus = self._get_focus_range(monday_str, sunday_str)

        # Save to weekly_summary table
        self._save_weekly_summary(
            monday_str, time_summary, people_balance, health, habits, focus
        )

        return {
            "week": f"{monday_str} → {sunday_str}",
            "time": time_summary,
            "people": {
                "total": people_balance["total_people"],
                "neglected": people_balance["neglected_count"],
                "neglected_list": people_balance["neglected"][:5],
                "category_breakdown": people_balance["category_breakdown"],
            },
            "health": health,
            "habits": habits,
            "focus": focus,
            "alerts": self._generate_weekly_alerts(
                time_summary, people_balance, health, habits
            ),
        }

    # ─── BALANCE ALERT ──────────────────────────────────────

    def balance_alert(self) -> Dict[str, Any]:
        """Quick balance check — who needs attention RIGHT NOW."""
        neglected = self.crm.get_neglected()
        balances = self.crm.calculate_balance()

        critical = [b for b in balances if b["balance_score"] < -0.7]
        warning = [b for b in balances if -0.7 <= b["balance_score"] < -0.3]

        return {
            "critical": critical,  # severely neglected
            "warning": warning,    # below target
            "neglected_days": neglected[:5],
            "total_people": len(balances),
            "healthy_count": len(balances) - len(critical) - len(warning),
        }

    # ─── HEALTH ─────────────────────────────────────────────

    def _get_health_today(self, today: str) -> Dict[str, Any]:
        """Get today's health log."""
        row = self.conn.execute(
            "SELECT * FROM health_log WHERE date = ?", (today,)
        ).fetchone()
        if not row:
            return {"has_data": False, "message": "Brak wpisu zdrowotnego na dziś"}

        d = dict(row)
        return {
            "has_data": True,
            "pills_taken": bool(d["pills_taken"]),
            "sleep_hours": d["sleep_hours"],
            "sleep_quality": d["sleep_quality"],
            "water_ml": d["water_ml"],
            "meals_count": d["meals_count"],
            "snacking_episodes": d["snacking_episodes"],
            "exercise_minutes": d["exercise_minutes"],
            "mood": d["mood"],
            "energy": d["energy"],
            "stress": d["stress"],
            "intrusive_thoughts": d["intrusive_thoughts_count"],
        }

    def _get_health_range(self, start: str, end: str) -> Dict[str, Any]:
        """Get health averages for a date range."""
        row = self.conn.execute(
            """SELECT
                COUNT(*) as days,
                AVG(sleep_hours) as avg_sleep,
                AVG(sleep_quality) as avg_sleep_quality,
                AVG(water_ml) as avg_water,
                AVG(mood) as avg_mood,
                AVG(energy) as avg_energy,
                AVG(stress) as avg_stress,
                SUM(exercise_minutes) as total_exercise,
                SUM(snacking_episodes) as total_snacking,
                SUM(intrusive_thoughts_count) as total_intrusive,
                AVG(CASE WHEN pills_taken = 1 THEN 1.0 ELSE 0.0 END) as pills_adherence
               FROM health_log
               WHERE date BETWEEN ? AND ?""",
            (start, end),
        ).fetchone()

        row_dict = dict(row) if row else None
        if not row_dict or row_dict["days"] == 0:
            return {"has_data": False, "days": 0}

        return {
            "has_data": True,
            "days": row_dict["days"],
            "avg_sleep_hours": round(row_dict["avg_sleep"], 1) if row_dict["avg_sleep"] else None,
            "avg_sleep_quality": round(row_dict["avg_sleep_quality"], 1) if row_dict["avg_sleep_quality"] else None,
            "avg_water_ml": round(row_dict["avg_water"]) if row_dict["avg_water"] else None,
            "avg_mood": round(row_dict["avg_mood"], 1) if row_dict["avg_mood"] else None,
            "avg_energy": round(row_dict["avg_energy"], 1) if row_dict["avg_energy"] else None,
            "avg_stress": round(row_dict["avg_stress"], 1) if row_dict["avg_stress"] else None,
            "total_exercise_minutes": row_dict["total_exercise"] or 0,
            "total_snacking": row_dict["total_snacking"] or 0,
            "total_intrusive_thoughts": row_dict["total_intrusive"] or 0,
            "pills_adherence_pct": round((row_dict["pills_adherence"] or 0) * 100, 1),
        }

    # ─── HABITS ─────────────────────────────────────────────

    def _get_habits_today(self, today: str) -> Dict[str, Any]:
        """Get today's habit completion."""
        habits = self.conn.execute(
            "SELECT * FROM habits WHERE active = 1"
        ).fetchall()

        result = []
        completed = 0
        total = 0

        for h in habits:
            log = self.conn.execute(
                "SELECT * FROM habit_log WHERE habit_id = ? AND date = ?",
                (h["id"], today),
            ).fetchone()

            total += 1
            is_done = bool(log and log["completed"])
            if is_done:
                completed += 1

            result.append({
                "id": h["id"],
                "name": h["name"],
                "category": h["category"],
                "completed": is_done,
                "streak": h["streak_current"],
                "best_streak": h["streak_best"],
            })

        return {
            "habits": result,
            "completed": completed,
            "total": total,
            "rate_pct": round(completed / max(total, 1) * 100, 1),
        }

    def _get_habits_range(self, start: str, end: str) -> Dict[str, Any]:
        """Get habit completion for a date range."""
        habits = self.conn.execute(
            "SELECT * FROM habits WHERE active = 1"
        ).fetchall()

        result = []
        for h in habits:
            row = self.conn.execute(
                """SELECT COUNT(*) as total_days,
                          SUM(completed) as completed_days
                   FROM habit_log
                   WHERE habit_id = ? AND date BETWEEN ? AND ?""",
                (h["id"], start, end),
            ).fetchone()

            total_days = row["total_days"] or 0
            completed_days = row["completed_days"] or 0
            rate = round(completed_days / max(total_days, 1) * 100, 1)

            result.append({
                "id": h["id"],
                "name": h["name"],
                "category": h["category"],
                "completed_days": completed_days,
                "total_days": total_days,
                "rate_pct": rate,
                "streak": h["streak_current"],
            })

        total_completed = sum(r["completed_days"] for r in result)
        total_possible = sum(r["total_days"] for r in result)

        return {
            "habits": result,
            "overall_rate_pct": round(total_completed / max(total_possible, 1) * 100, 1),
        }

    # ─── FOCUS ──────────────────────────────────────────────

    def _get_focus_today(self, today: str) -> Dict[str, Any]:
        """Get today's focus sessions."""
        rows = self.conn.execute(
            """SELECT * FROM focus_sessions
               WHERE date(start_time) = ?
               ORDER BY start_time DESC""",
            (today,),
        ).fetchall()

        sessions = [dict(r) for r in rows]
        completed = [s for s in sessions if s["completed"]]
        total_focus = sum(s["duration_minutes"] or 0 for s in completed)

        return {
            "sessions": sessions,
            "completed_count": len(completed),
            "total_focus_minutes": total_focus,
            "avg_focus": round(
                sum(s["focus_level"] or 0 for s in completed) / max(len(completed), 1), 1
            ),
        }

    def _get_focus_range(self, start: str, end: str) -> Dict[str, Any]:
        """Get focus stats for a date range."""
        row = self.conn.execute(
            """SELECT
                COUNT(*) as total_sessions,
                SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed,
                SUM(duration_minutes) as total_minutes,
                AVG(focus_level) as avg_focus,
                AVG(interruptions) as avg_interruptions
               FROM focus_sessions
               WHERE date(start_time) BETWEEN ? AND ?""",
            (start, end),
        ).fetchone()

        if not row:
            return {"has_data": False}

        return {
            "has_data": True,
            "total_sessions": row["total_sessions"],
            "completed": row["completed"] or 0,
            "total_focus_minutes": row["total_minutes"] or 0,
            "avg_focus": round(row["avg_focus"], 1) if row["avg_focus"] else None,
            "avg_interruptions": round(row["avg_interruptions"], 1) if row["avg_interruptions"] else None,
        }

    # ─── ALERTS ─────────────────────────────────────────────

    def _generate_alerts(
        self,
        time_summary: Dict,
        to_contact: List,
        health: Dict,
    ) -> List[Dict[str, str]]:
        """Generate daily alerts."""
        alerts = []

        # Waste alert
        waste = time_summary["breakdown"].get("waste", 0)
        if waste > 60:
            alerts.append({
                "level": "warning",
                "message": f"⚠️ {waste} min zmarnowanego czasu dzisiaj",
            })

        # No deep work
        deep = time_summary["breakdown"].get("work_deep", 0)
        if deep < 25 and time_summary["total_minutes"] > 120:
            alerts.append({
                "level": "warning",
                "message": "⚠️ Brak sesji głębokiej pracy (minimum 25 min)",
            })

        # People neglected
        if len(to_contact) > 3:
            alerts.append({
                "level": "critical",
                "message": f"🔴 {len(to_contact)} osób wymaga kontaktu!",
            })

        # Pills not taken
        if health.get("has_data") and not health.get("pills_taken"):
            alerts.append({
                "level": "critical",
                "message": "🔴 Tabletki nie wzięte!",
            })

        # Low sleep
        if health.get("has_data") and health.get("sleep_hours", 0) < 6:
            alerts.append({
                "level": "warning",
                "message": f"⚠️ Tylko {health['sleep_hours']}h snu",
            })

        # High snacking
        if health.get("has_data") and health.get("snacking_episodes", 0) > 3:
            alerts.append({
                "level": "warning",
                "message": f"⚠️ {health['snacking_episodes']} epizodów podjadania",
            })

        # Intrusive thoughts
        if health.get("has_data") and health.get("intrusive_thoughts", 0) > 5:
            alerts.append({
                "level": "warning",
                "message": f"⚠️ {health['intrusive_thoughts']} natarczywych myśli",
            })

        return alerts

    def _generate_weekly_alerts(
        self,
        time: Dict,
        people: Dict,
        health: Dict,
        habits: Dict,
    ) -> List[Dict[str, str]]:
        """Generate weekly alerts."""
        alerts = []

        # Waste > 10% of waking hours
        total = time["total_minutes"]
        waste = time["breakdown"].get("waste", 0)
        if total > 0 and waste / total > 0.10:
            alerts.append({
                "level": "warning",
                "message": f"⚠️ {round(waste/total*100)}% czasu zmarnowane w tym tygodniu",
            })

        # Deep work < 15%
        deep = time["breakdown"].get("work_deep", 0)
        if total > 0 and deep / total < 0.15:
            alerts.append({
                "level": "warning",
                "message": f"⚠️ Tylko {round(deep/total*100)}% głębokiej pracy",
            })

        # Neglected people
        if people["neglected_count"] > 5:
            alerts.append({
                "level": "critical",
                "message": f"🔴 {people['neglected_count']} osób zaniedbanych!",
            })

        # Low pills adherence
        if health.get("has_data") and health.get("pills_adherence_pct", 100) < 80:
            alerts.append({
                "level": "critical",
                "message": f"🔴 Adherencja do tabletek: {health['pills_adherence_pct']}%",
            })

        # Low sleep
        if health.get("has_data") and health.get("avg_sleep_hours", 8) < 6.5:
            alerts.append({
                "level": "warning",
                "message": f"⚠️ Średnio {health['avg_sleep_hours']}h snu",
            })

        # Low habits
        if habits.get("overall_rate_pct", 100) < 60:
            alerts.append({
                "level": "warning",
                "message": f"⚠️ Tylko {habits['overall_rate_pct']}% nawyków wykonanych",
            })

        return alerts

    # ─── SAVE ───────────────────────────────────────────────

    def _save_weekly_summary(
        self,
        week_start: str,
        time: Dict,
        people: Dict,
        health: Dict,
        habits: Dict,
        focus: Dict,
    ):
        """Save weekly summary to database."""
        self.conn.execute(
            """INSERT OR REPLACE INTO weekly_summary
               (week_start, work_deep_minutes, work_shallow_minutes,
                people_minutes, health_minutes, hobby_minutes,
                learning_minutes, admin_minutes, rest_minutes,
                waste_minutes, transit_minutes,
                people_contacted, people_neglected,
                avg_sleep_hours, avg_mood, avg_energy,
                total_exercise_minutes, pills_adherence,
                habits_completion_rate, avg_focus_level,
                total_intrusive_thoughts, snacking_episodes_total)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                week_start,
                time["breakdown"].get("work_deep", 0),
                time["breakdown"].get("work_shallow", 0),
                time["breakdown"].get("people", 0),
                time["breakdown"].get("health", 0),
                time["breakdown"].get("hobby", 0),
                time["breakdown"].get("learning", 0),
                time["breakdown"].get("admin", 0),
                time["breakdown"].get("rest", 0),
                time["breakdown"].get("waste", 0),
                time["breakdown"].get("transit", 0),
                people["total_people"] - people["neglected_count"],
                people["neglected_count"],
                health.get("avg_sleep_hours"),
                health.get("avg_mood"),
                health.get("avg_energy"),
                health.get("total_exercise_minutes", 0),
                health.get("pills_adherence_pct", 0) / 100 if health.get("pills_adherence_pct") else None,
                habits.get("overall_rate_pct", 0) / 100 if habits.get("overall_rate_pct") else None,
                focus.get("avg_focus"),
                health.get("total_intrusive_thoughts", 0),
                health.get("total_snacking", 0),
            ),
        )
        self.conn.commit()

    def close(self):
        """Close all connections."""
        self.tracker.close()
        self.crm.close()
        self.conn.close()
