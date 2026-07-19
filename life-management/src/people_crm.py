"""
People CRM — zarządzanie relacjami z ~50 osobami.
Balans czasu, priorytety, last_contact, przypomnienia o kontakcie.

Usage:
    crm = PeopleCRM()
    crm.add_person("Mama", "family_close", priority=2, birthday="1965-03-15")
    crm.log_interaction(person_id=1, type="call", duration=15, quality=8)
    crm.get_neglected()  # osoby bez kontaktu dłużej niż threshold
    crm.balance_report()  # kto dostaje za mało / za dużo czasu
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any
from pathlib import Path

from .schema import get_db, init_db

CATEGORIES = [
    "family_close", "family_extended", "partner",
    "friends_close", "friends", "work", "mentor", "other"
]

CATEGORY_LABELS = {
    "family_close": "Rodzina bliższa",
    "family_extended": "Dalsza rodzina",
    "partner": "Partner/ka",
    "friends_close": "Bliscy znajomi",
    "friends": "Znajomi",
    "work": "Praca",
    "mentor": "Mentor",
    "other": "Inne",
}

CATEGORY_DEFAULT_FREQUENCY = {
    "family_close": 1,     # codziennie
    "partner": 1,           # codziennie
    "friends_close": 3,     # co 3 dni
    "family_extended": 7,   # co tydzień
    "friends": 14,          # co 2 tygodnie
    "work": 5,              # co ~tydzień roboczy
    "mentor": 30,           # co miesiąc
    "other": 30,
}

CATEGORY_DEFAULT_MINUTES = {
    "family_close": 120,    # 2h tygodniowo
    "partner": 300,         # 5h tygodniowo
    "friends_close": 90,    # 1.5h
    "family_extended": 60,  # 1h
    "friends": 45,          # 45min
    "work": 0,              # nie liczymy work jako "people time"
    "mentor": 30,
    "other": 30,
}


class PeopleCRM:
    """Manage your relationships — never forget to contact someone."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.conn = sqlite3.connect(db_path)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.row_factory = sqlite3.Row
        else:
            self.conn = get_db()
        init_db()

    # ─── CRUD ───────────────────────────────────────────────

    def add_person(
        self,
        name: str,
        category: str,
        priority: int = 5,
        birthday: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[str] = None,
        target_minutes_per_week: Optional[int] = None,
    ) -> int:
        """Add a person to your CRM. Returns person_id."""
        if category not in CATEGORIES:
            raise ValueError(f"Invalid category: {category}")

        if target_minutes_per_week is None:
            target_minutes_per_week = CATEGORY_DEFAULT_MINUTES.get(category, 60)

        contact_freq = CATEGORY_DEFAULT_FREQUENCY.get(category, 7)

        cursor = self.conn.execute(
            """INSERT INTO people
               (name, category, priority, birthday, phone, email, notes, tags,
                target_minutes_per_week, contact_frequency_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, category, priority, birthday, phone, email, notes, tags,
             target_minutes_per_week, contact_freq),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_person(self, person_id: int) -> Optional[Dict[str, Any]]:
        """Get a person by ID."""
        row = self.conn.execute(
            "SELECT * FROM people WHERE id = ?", (person_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_all_people(
        self,
        category: Optional[str] = None,
        order_by: str = "priority",
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get all people, optionally filtered."""
        query = "SELECT * FROM people WHERE 1=1"
        params: list = []

        if category:
            query += " AND category = ?"
            params.append(category)

        order_map = {
            "priority": "priority ASC, name ASC",
            "name": "name ASC",
            "last_contact": "last_contact ASC NULLS FIRST",
            "category": "category, priority ASC",
            "balance": "time_balance_score ASC",
        }
        order = order_map.get(order_by, "priority ASC, name ASC")
        query += f" ORDER BY {order}"

        return [dict(row) for row in self.conn.execute(query, params).fetchall()]

    def update_person(self, person_id: int, **kwargs) -> bool:
        """Update person fields."""
        allowed = {
            "name", "category", "priority", "birthday", "phone", "email",
            "notes", "tags", "target_minutes_per_week", "contact_frequency_days",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False

        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [person_id]

        self.conn.execute(
            f"UPDATE people SET {set_clause} WHERE id = ?", values
        )
        self.conn.commit()
        return True

    def delete_person(self, person_id: int) -> bool:
        """Delete a person (cascades to interactions and time_blocks)."""
        self.conn.execute("DELETE FROM people WHERE id = ?", (person_id,))
        self.conn.commit()
        return True

    # ─── INTERACTIONS ───────────────────────────────────────

    def log_interaction(
        self,
        person_id: int,
        interaction_type: str,
        duration_minutes: Optional[int] = None,
        quality: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> int:
        """Log an interaction with a person. Updates last_contact and stats."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        cursor = self.conn.execute(
            """INSERT INTO interactions
               (person_id, interaction_type, duration_minutes, quality, notes, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (person_id, interaction_type, duration_minutes, quality, notes, now_iso),
        )

        # Update person stats
        self.conn.execute(
            """UPDATE people
               SET last_contact = ?,
                   total_interactions = total_interactions + 1,
                   total_time_minutes = total_time_minutes + COALESCE(?, 0),
                   updated_at = ?
               WHERE id = ?""",
            (now_iso, duration_minutes or 0, now_iso, person_id),
        )

        self.conn.commit()
        return cursor.lastrowid

    def get_interactions(
        self,
        person_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent interactions."""
        query = """SELECT i.*, p.name as person_name
                   FROM interactions i
                   JOIN people p ON i.person_id = p.id"""
        params: list = []

        if person_id is not None:
            query += " WHERE i.person_id = ?"
            params.append(person_id)

        query += " ORDER BY i.timestamp DESC LIMIT ?"
        params.append(limit)

        return [dict(row) for row in self.conn.execute(query, params).fetchall()]

    # ─── NEGLECT DETECTION ──────────────────────────────────

    def get_neglected(self, days_threshold: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get people who haven't been contacted within their threshold.
        Returns list sorted by urgency (most neglected first)."""
        now = datetime.now(timezone.utc)

        people = self.get_all_people()
        neglected = []

        for p in people:
            threshold = days_threshold or p["contact_frequency_days"]
            last = p["last_contact"]

            if last is None:
                days_since = 999  # never contacted
            else:
                last_dt = datetime.fromisoformat(last)
                days_since = (now - last_dt).days

            if days_since > threshold:
                overdue = days_since - threshold
                neglected.append({
                    **p,
                    "days_since_contact": days_since,
                    "threshold_days": threshold,
                    "overdue_days": overdue,
                    "urgency": min(10, overdue),  # 1-10 scale
                })

        neglected.sort(key=lambda x: x["overdue_days"], reverse=True)
        return neglected

    def get_upcoming_birthdays(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Get people with birthdays in the next N days."""
        today = date.today()
        end = today + timedelta(days=days_ahead)

        people = self.conn.execute(
            "SELECT * FROM people WHERE birthday IS NOT NULL"
        ).fetchall()

        upcoming = []
        for p in people:
            bday_str = p["birthday"]
            try:
                bday = date.fromisoformat(bday_str)
            except (ValueError, TypeError):
                # Try YYYY-MM-DD or just MM-DD
                if bday_str and len(bday_str) >= 5:
                    try:
                        bday = date(today.year, int(bday_str[5:7]), int(bday_str[8:10]))
                    except (ValueError, IndexError):
                        continue
                else:
                    continue

            # This year's birthday
            this_year_bday = date(today.year, bday.month, bday.day)
            if this_year_bday < today:
                this_year_bday = date(today.year + 1, bday.month, bday.day)

            days_until = (this_year_bday - today).days
            if days_until <= days_ahead:
                age = today.year - bday.year if bday.year else None
                upcoming.append({
                    **dict(p),
                    "days_until": days_until,
                    "birthday_date": this_year_bday.isoformat(),
                    "age": age,
                })

        upcoming.sort(key=lambda x: x["days_until"])
        return upcoming

    # ─── TIME BALANCE ───────────────────────────────────────

    def calculate_balance(self) -> List[Dict[str, Any]]:
        """Calculate time balance for all people.
        Returns list with balance scores: negative = neglected, positive = over-served."""
        now = datetime.now(timezone.utc)
        week_ago = (now - timedelta(days=7)).isoformat()

        people = self.get_all_people()
        results = []

        for p in people:
            # Get this week's time with this person
            row = self.conn.execute(
                """SELECT COALESCE(SUM(duration_minutes), 0) as total
                   FROM time_blocks
                   WHERE person_id = ? AND start_time >= ?""",
                (p["id"], week_ago),
            ).fetchone()

            actual = row["total"] if row else 0
            target = p["target_minutes_per_week"] or 60

            if target > 0:
                ratio = actual / target
                # Map ratio to -1..1 scale
                # ratio=0 → -1.0 (completely neglected)
                # ratio=1.0 → 0.0 (perfect balance)
                # ratio=2.0 → 1.0 (over-served)
                if ratio <= 1.0:
                    score = -1.0 + ratio  # -1.0 to 0.0
                else:
                    score = min(1.0, (ratio - 1.0))  # 0.0 to 1.0
            else:
                score = 0.0

            # Update stored score
            self.conn.execute(
                "UPDATE people SET time_balance_score = ? WHERE id = ?",
                (round(score, 2), p["id"]),
            )

            results.append({
                **p,
                "actual_minutes_this_week": actual,
                "target_minutes_per_week": target,
                "balance_score": round(score, 2),
                "status": (
                    "🔴 Zaniedbany" if score < -0.5
                    else "🟡 Poniżej" if score < -0.1
                    else "🟢 OK" if score <= 0.3
                    else "🔵 Nadmiar"
                ),
            })

        self.conn.commit()
        results.sort(key=lambda x: x["balance_score"])
        return results

    def balance_report(self) -> Dict[str, Any]:
        """Generate a full balance report."""
        balances = self.calculate_balance()
        neglected = self.get_neglected()
        birthdays = self.get_upcoming_birthdays()

        # Category breakdown
        cat_breakdown = {}
        for cat in CATEGORIES:
            cat_people = [b for b in balances if b["category"] == cat]
            if cat_people:
                avg_score = sum(b["balance_score"] for b in cat_people) / len(cat_people)
                total_actual = sum(b["actual_minutes_this_week"] for b in cat_people)
                total_target = sum(b["target_minutes_per_week"] for b in cat_people)
                cat_breakdown[cat] = {
                    "label": CATEGORY_LABELS[cat],
                    "count": len(cat_people),
                    "avg_balance": round(avg_score, 2),
                    "actual_minutes": total_actual,
                    "target_minutes": total_target,
                }

        return {
            "total_people": len(balances),
            "neglected_count": len(neglected),
            "neglected": neglected[:10],  # top 10 most neglected
            "upcoming_birthdays": birthdays,
            "category_breakdown": cat_breakdown,
            "all_balances": balances,
        }

    # ─── QUICK ACTIONS ──────────────────────────────────────

    def quick_contact(self, person_id: int, method: str = "message") -> int:
        """Log a quick contact (default: message, 5 min)."""
        return self.log_interaction(
            person_id=person_id,
            interaction_type=method,
            duration_minutes=5,
            quality=5,
            notes=f"Quick {method} check-in",
        )

    def who_to_contact_today(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get list of people you should contact today (most neglected first)."""
        neglected = self.get_neglected()
        return neglected[:limit]

    def import_sample_50(self) -> int:
        """Import a sample set of 50 people for testing.
        Returns number of people added."""
        sample_people = [
            # Family close (8)
            ("Mama", "family_close", 1, "1965-03-15"),
            ("Tata", "family_close", 1, "1963-07-22"),
            ("Brat", "family_close", 2, "1995-11-08"),
            ("Siostra", "family_close", 2, "1998-04-30"),
            ("Babcia Krysia", "family_close", 1, "1940-12-01"),
            ("Dziadek Janek", "family_close", 1, "1938-06-15"),
            ("Babcia Zosia", "family_close", 2, "1942-09-10"),
            ("Dziadek Tomek", "family_close", 2, "1939-02-28"),
            # Family extended (10)
            ("Ciocia Basia", "family_extended", 4, "1970-05-20"),
            ("Wujek Marek", "family_extended", 4, "1968-08-12"),
            ("Kuzyn Kuba", "family_extended", 5, "2000-01-15"),
            ("Kuzynka Ola", "family_extended", 5, "2002-07-03"),
            ("Ciocia Ewa", "family_extended", 5, "1972-11-25"),
            ("Wujek Piotr", "family_extended", 5, "1966-03-08"),
            ("Kuzynka Ania", "family_extended", 6, "1999-09-19"),
            ("Kuzyn Michał", "family_extended", 6, "1997-12-24"),
            ("Babcia cioteczna Hela", "family_extended", 7, "1935-04-11"),
            ("Dziadek cioteczny Stefan", "family_extended", 7, "1933-10-30"),
            # Partner (1)
            ("Partnerka", "partner", 1, "1996-06-14"),
            # Friends close (8)
            ("Przyjaciel 1", "friends_close", 3, "1995-02-10"),
            ("Przyjaciółka 1", "friends_close", 3, "1996-08-22"),
            ("Przyjaciel 2", "friends_close", 3, "1994-11-05"),
            ("Przyjaciółka 2", "friends_close", 3, "1997-03-18"),
            ("Przyjaciel 3", "friends_close", 4, "1995-07-30"),
            ("Przyjaciółka 3", "friends_close", 4, "1996-01-25"),
            ("Przyjaciel 4", "friends_close", 4, "1994-09-12"),
            ("Przyjaciółka 4", "friends_close", 4, "1997-05-08"),
            # Friends (10)
            ("Znajomy 1", "friends", 5, "1995-04-01"),
            ("Znajoma 1", "friends", 5, "1996-10-15"),
            ("Znajomy 2", "friends", 5, "1994-06-20"),
            ("Znajoma 2", "friends", 5, "1997-12-03"),
            ("Znajomy 3", "friends", 6, "1995-08-28"),
            ("Znajoma 3", "friends", 6, "1996-02-14"),
            ("Znajomy 4", "friends", 6, "1994-11-09"),
            ("Znajoma 4", "friends", 6, "1997-07-17"),
            ("Znajomy 5", "friends", 7, "1995-01-30"),
            ("Znajoma 5", "friends", 7, "1996-09-05"),
            # Work (8)
            ("Szef", "work", 3, "1980-03-20"),
            ("Kolega z zespołu 1", "work", 5, "1992-07-11"),
            ("Kolega z zespołu 2", "work", 5, "1993-11-28"),
            ("Koleżanka z zespołu 1", "work", 5, "1994-04-16"),
            ("PM", "work", 4, "1988-09-03"),
            ("Designer", "work", 5, "1991-06-22"),
            ("DevOps", "work", 5, "1990-12-07"),
            ("HR", "work", 6, "1987-02-18"),
            # Mentor (3)
            ("Mentor 1", "mentor", 4, "1975-05-25"),
            ("Mentor 2", "mentor", 5, "1978-08-14"),
            ("Coach", "mentor", 5, "1982-01-09"),
            # Other (2)
            ("Sąsiad Jan", "other", 7, "1960-10-10"),
            ("Lekarz rodzinny", "other", 6, "1970-03-05"),
        ]

        count = 0
        for name, cat, pri, bday in sample_people:
            try:
                self.add_person(
                    name=name,
                    category=cat,
                    priority=pri,
                    birthday=bday,
                    tags=f"sample,{cat}",
                )
                count += 1
            except Exception:
                pass

        self.conn.commit()
        return count

    def close(self):
        """Close database connection."""
        self.conn.close()
