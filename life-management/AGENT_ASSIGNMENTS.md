# Life Management System — Agent Assignments

Każdy agent wpisuje swój obszar poniżej. **Nie dublujemy się.**
Wspólne repo: `ScuraUrsa/hermes-enhancements/life-management/`

| Agent ID | Obszar | Status |
|----------|--------|--------|
| **GŁÓWNY** (Coder, deepseek-v4-pro) | **Time Tracker Core + People CRM + Hermes Integration** — 5-min bloki, baza 50 osób, balance time, raporty, habit tracker, event manager, cron jobs, dashboard, seed data | ✅ Done |
| deleg_e332cb3f (sub-agent #1) | **Health & Wellness** — pill schedule, meal tracker (kalorie/makro), water tracker, exercise tracker, sleep tracker | ✅ Done (health.py + test_health.py, 63 tests) |
| deleg_e332cb3f (sub-agent #2) | **Mind & Habits** — intrusive thought analysis (triggers, CBT), snacking trigger→response, focus/pomodoro, daily goals, weekly review | ✅ Done (mind.py) |

## Zasady
1. Wpisz swój obszar przed rozpoczęciem pracy
2. Nie wchodź w obszar innego agenta
3. Commituj do `life-management/` w repo `ScuraUrsa/hermes-enhancements`
4. Używaj `ollama_token_monitor.py record` po każdym API callu

## Architektura
```
life-management/
├── AGENT_ASSIGNMENTS.md       # Ten plik
├── README.md                  # Dokumentacja
├── life_cli.py                # Core engine (GŁÓWNY) — TimeTracker, PeopleManager, EventManager, HabitTracker, ReportGenerator
├── health.py                  # Health & Wellness (sub-agent #1) — pills, meals, water, exercise, sleep
├── mind.py                    # Mind & Habits (sub-agent #2) — thoughts, snacking, focus, goals, journal
├── hermes_integration.py      # Hermes Integration (GŁÓWNY) — cron jobs, notifications, dashboard, seed data
├── dashboard.html             # Wygenerowany dashboard
├── test_life_cli.py           # 27 testów core engine
├── test_health.py             # Testy health module
├── core/                      # SQLAlchemy models (inny agent)
├── src/                       # Alternatywna implementacja (inny agent)
└── data/                      # Bazy SQLite
```

## Stan — ALL DONE ✅
- ✅ Time Tracker (5-min bloki, 12 kategorii)
- ✅ People CRM (50 osób, 6 kategorii, balans czasu, overdue detection)
- ✅ Event Manager (wydarzenia, recurring, reminders)
- ✅ Habit Tracker (pills, thoughts, snacking, exercise, water, focus)
- ✅ Report Generator (daily brief, weekly deep dive)
- ✅ Health & Wellness (pill schedule, meals, water, exercise, sleep)
- ✅ Mind & Habits (CBT patterns, trigger analysis, pomodoro, daily goals, weekly review)
- ✅ Hermes Integration (8 cron jobs, notification bridge, dashboard, seed data)
- ✅ 27+ testów jednostkowych
- ✅ Hermes skill: `productivity/life-management`
