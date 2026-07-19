"""
Life Management System — Database Schema
Fundacja dla wszystkich modułów: Time Tracker, People CRM, Health, Mind, Events.
"""

import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path

DB_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DB_DIR / "life_management.db"


def get_db() -> sqlite3.Connection:
    """Get database connection with WAL mode and foreign keys."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> sqlite3.Connection:
    """Initialize all tables. Idempotent — safe to call multiple times."""
    conn = get_db()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


SCHEMA_SQL = """
-- ============================================================
-- PEOPLE — zarządzanie relacjami z ~50 osobami
-- ============================================================
CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN (
        'family_close',    -- rodzina bliższa (mieszka z tobą / codzienny kontakt)
        'family_extended', -- dalsza rodzina
        'partner',         -- partner/partnerka
        'friends_close',   -- bliscy znajomi
        'friends',         -- znajomi
        'work',            -- współpracownicy
        'mentor',          -- mentorzy, coachowie
        'other'
    )),
    priority INTEGER NOT NULL DEFAULT 5 CHECK(priority BETWEEN 1 AND 10),
    -- 1-3: must contact weekly, 4-6: biweekly, 7-8: monthly, 9-10: quarterly

    -- Contact tracking
    last_contact TEXT,           -- ISO 8601
    contact_frequency_days INTEGER DEFAULT 7,  -- co ile dni powinien być kontakt
    total_interactions INTEGER DEFAULT 0,
    total_time_minutes INTEGER DEFAULT 0,  -- łączny czas spędzony (minuty)

    -- Balance tracking (do balansowania czasu między ludźmi)
    time_balance_score REAL DEFAULT 0.0,  -- -1.0 (zaniedbany) do 1.0 (nadmiar)
    target_minutes_per_week INTEGER DEFAULT 60,

    -- Metadata
    birthday TEXT,               -- YYYY-MM-DD (rok opcjonalny)
    phone TEXT,
    email TEXT,
    notes TEXT,
    tags TEXT,                   -- comma-separated

    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_people_category ON people(category);
CREATE INDEX IF NOT EXISTS idx_people_last_contact ON people(last_contact);
CREATE INDEX IF NOT EXISTS idx_people_priority ON people(priority);


-- ============================================================
-- TIME BLOCKS — 5-minutowe bloki czasu
-- ============================================================
CREATE TABLE IF NOT EXISTS time_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,     -- ISO 8601
    end_time TEXT,                -- ISO 8601 (NULL = ongoing)
    duration_minutes INTEGER,    -- obliczane przy zakończeniu

    category TEXT NOT NULL CHECK(category IN (
        'work_deep',       -- głęboka praca
        'work_shallow',    -- płytka praca (maile, meetingi)
        'people',          -- czas z ludźmi
        'health',          -- ćwiczenia, sen, jedzenie
        'hobby',           -- hobby, pasje
        'learning',        -- nauka, kursy
        'admin',           -- administracja, rachunki
        'rest',            -- odpoczynek świadomy
        'waste',           -- zmarnowany czas (social media, scrollowanie)
        'transit',         -- transport
        'other'
    )),

    -- Opcjonalne powiązania
    person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
    habit_id INTEGER REFERENCES habits(id) ON DELETE SET NULL,

    -- Jakość / energia
    energy_level INTEGER CHECK(energy_level BETWEEN 1 AND 10),
    focus_level INTEGER CHECK(focus_level BETWEEN 1 AND 10),
    satisfaction INTEGER CHECK(satisfaction BETWEEN 1 AND 10),

    -- Czy blok był zaplanowany czy spontaniczny
    planned INTEGER NOT NULL DEFAULT 0,  -- 0=spontaneous, 1=planned

    notes TEXT,
    tags TEXT,

    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_time_blocks_start ON time_blocks(start_time);
CREATE INDEX IF NOT EXISTS idx_time_blocks_category ON time_blocks(category);
CREATE INDEX IF NOT EXISTS idx_time_blocks_person ON time_blocks(person_id);


-- ============================================================
-- EVENTS — urodziny, ważne daty, wydarzenia
-- ============================================================
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN (
        'birthday', 'anniversary', 'appointment', 'deadline',
        'meeting', 'social', 'health', 'other'
    )),
    person_id INTEGER REFERENCES people(id) ON DELETE CASCADE,

    start_time TEXT NOT NULL,     -- ISO 8601
    end_time TEXT,                -- NULL dla whole-day events
    all_day INTEGER NOT NULL DEFAULT 0,

    -- Recurrence (RFC 5545 style)
    recurring INTEGER NOT NULL DEFAULT 0,
    recurrence_rule TEXT,         -- np. 'FREQ=YEARLY' dla urodzin

    -- Reminders
    reminder_minutes_before INTEGER,  -- ile minut przed wydarzeniem przypomnieć
    reminder_sent INTEGER NOT NULL DEFAULT 0,

    priority INTEGER NOT NULL DEFAULT 5 CHECK(priority BETWEEN 1 AND 10),
    notes TEXT,
    location TEXT,

    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_time);
CREATE INDEX IF NOT EXISTS idx_events_person ON events(person_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);


-- ============================================================
-- HABITS — nawyki do śledzenia
-- ============================================================
CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN (
        'health',      -- pigułki, woda, ćwiczenia
        'mind',        -- medytacja, journaling
        'food',        -- odżywianie, niepodjadanie
        'productivity', -- focus, deep work
        'social',      -- kontakt z ludźmi
        'other'
    )),

    -- Schedule
    frequency TEXT NOT NULL DEFAULT 'daily',  -- daily, weekly, monthly, custom
    target_count INTEGER DEFAULT 1,           -- ile razy w okresie
    time_of_day TEXT,                          -- 'morning', 'afternoon', 'evening', 'any'

    -- Tracking
    streak_current INTEGER DEFAULT 0,
    streak_best INTEGER DEFAULT 0,
    total_completions INTEGER DEFAULT 0,

    -- Reminder
    reminder_enabled INTEGER NOT NULL DEFAULT 1,
    reminder_time TEXT,             -- '08:00', '20:00'

    active INTEGER NOT NULL DEFAULT 1,
    notes TEXT,

    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_habits_category ON habits(category);
CREATE INDEX IF NOT EXISTS idx_habits_active ON habits(active);


-- ============================================================
-- HABIT LOG — dzienne wykonania nawyków
-- ============================================================
CREATE TABLE IF NOT EXISTS habit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    date TEXT NOT NULL,            -- YYYY-MM-DD
    completed INTEGER NOT NULL DEFAULT 0,
    count INTEGER DEFAULT 1,       -- ile razy (dla multi-count habits)
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(habit_id, date)
);

CREATE INDEX IF NOT EXISTS idx_habit_log_date ON habit_log(date);
CREATE INDEX IF NOT EXISTS idx_habit_log_habit ON habit_log(habit_id);


-- ============================================================
-- HEALTH LOG — zdrowie, pigułki, sen, woda, jedzenie
-- ============================================================
CREATE TABLE IF NOT EXISTS health_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,            -- YYYY-MM-DD

    -- Pigułki / leki
    pills_taken INTEGER NOT NULL DEFAULT 0,  -- 0=no, 1=yes, -1=skipped
    pills_time TEXT,               -- '08:00'
    pills_notes TEXT,

    -- Sen
    sleep_hours REAL,
    sleep_quality INTEGER CHECK(sleep_quality BETWEEN 1 AND 10),
    sleep_start TEXT,              -- ISO 8601
    sleep_end TEXT,

    -- Woda
    water_ml INTEGER DEFAULT 0,

    -- Jedzenie
    meals_count INTEGER DEFAULT 0,
    snacking_episodes INTEGER DEFAULT 0,  -- epizody podjadania
    food_quality INTEGER CHECK(food_quality BETWEEN 1 AND 10),
    food_notes TEXT,

    -- Aktywność
    exercise_minutes INTEGER DEFAULT 0,
    exercise_type TEXT,
    steps INTEGER DEFAULT 0,

    -- Samopoczucie
    mood INTEGER CHECK(mood BETWEEN 1 AND 10),
    energy INTEGER CHECK(energy BETWEEN 1 AND 10),
    stress INTEGER CHECK(stress BETWEEN 1 AND 10),

    -- Natarczywe myśli
    intrusive_thoughts_count INTEGER DEFAULT 0,
    intrusive_thoughts_notes TEXT,

    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(date)
);


-- ============================================================
-- INTERACTIONS — log interakcji z ludźmi
-- ============================================================
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    interaction_type TEXT NOT NULL CHECK(interaction_type IN (
        'in_person', 'call', 'video', 'message', 'email', 'social_media', 'other'
    )),
    duration_minutes INTEGER,
    quality INTEGER CHECK(quality BETWEEN 1 AND 10),
    notes TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_interactions_person ON interactions(person_id);
CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp);


-- ============================================================
-- FOCUS SESSIONS — sesje skupienia (Pomodoro style)
-- ============================================================
CREATE TABLE IF NOT EXISTS focus_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_minutes INTEGER,
    planned_duration INTEGER NOT NULL DEFAULT 25,  -- domyślnie 25 min Pomodoro

    -- Czy sesja była udana
    completed INTEGER NOT NULL DEFAULT 0,
    interruptions INTEGER DEFAULT 0,
    focus_level INTEGER CHECK(focus_level BETWEEN 1 AND 10),

    -- Co było robione
    task TEXT,
    category TEXT DEFAULT 'work_deep',

    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_focus_sessions_start ON focus_sessions(start_time);


-- ============================================================
-- DAILY JOURNAL — szybki dziennik
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,     -- YYYY-MM-DD

    -- 3 rzeczy dobre
    gratitude_1 TEXT,
    gratitude_2 TEXT,
    gratitude_3 TEXT,

    -- Refleksja
    highlight TEXT,                -- najlepszy moment dnia
    challenge TEXT,                -- największe wyzwanie
    learned TEXT,                  -- czego się nauczyłem

    -- Cele na jutro
    tomorrow_goal_1 TEXT,
    tomorrow_goal_2 TEXT,
    tomorrow_goal_3 TEXT,

    -- Ocena dnia
    day_rating INTEGER CHECK(day_rating BETWEEN 1 AND 10),

    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);


-- ============================================================
-- WEEKLY SUMMARY — tygodniowe podsumowania
-- ============================================================
CREATE TABLE IF NOT EXISTS weekly_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT NOT NULL UNIQUE,  -- YYYY-MM-DD (poniedziałek)

    -- Time breakdown (minuty)
    work_deep_minutes INTEGER DEFAULT 0,
    work_shallow_minutes INTEGER DEFAULT 0,
    people_minutes INTEGER DEFAULT 0,
    health_minutes INTEGER DEFAULT 0,
    hobby_minutes INTEGER DEFAULT 0,
    learning_minutes INTEGER DEFAULT 0,
    admin_minutes INTEGER DEFAULT 0,
    rest_minutes INTEGER DEFAULT 0,
    waste_minutes INTEGER DEFAULT 0,
    transit_minutes INTEGER DEFAULT 0,

    -- People balance
    people_contacted INTEGER DEFAULT 0,
    people_neglected INTEGER DEFAULT 0,  -- osoby bez kontaktu > threshold

    -- Health
    avg_sleep_hours REAL,
    avg_mood REAL,
    avg_energy REAL,
    total_exercise_minutes INTEGER DEFAULT 0,
    pills_adherence REAL,          -- 0.0 do 1.0

    -- Habits
    habits_completion_rate REAL,   -- 0.0 do 1.0

    -- Mind
    avg_focus_level REAL,
    total_intrusive_thoughts INTEGER DEFAULT 0,
    snacking_episodes_total INTEGER DEFAULT 0,

    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


if __name__ == "__main__":
    conn = init_db()
    print(f"✅ Database initialized: {DB_PATH}")
    print(f"   Tables: {', '.join(t for t in ['people', 'time_blocks', 'events', 'habits', 'habit_log', 'health_log', 'interactions', 'focus_sessions', 'daily_journal', 'weekly_summary'])}")
    conn.close()
