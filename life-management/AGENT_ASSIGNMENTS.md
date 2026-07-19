# Life Management System — Agent Assignments

Każdy agent wpisuje swój obszar poniżej. **Nie dublujemy się.**
Wspólne repo: `ScuraUrsa/hermes-enhancements/life-management/`

| Agent ID | Obszar | Status |
|----------|--------|--------|
| **GŁÓWNY** (Coder, deepseek-v4-pro) | **Time Tracker Core + People CRM + Hermes Integration + Gamification** — 5-min bloki, baza 50 osób, balance time, raporty, habit tracker, event manager, cron jobs, dashboard, seed data, XP/achievements/quests | ✅ Done |
| deleg_e332cb3f (sub-agent #1) | **Health & Wellness** — pill schedule, meal tracker (kalorie/makro), water tracker, exercise tracker, sleep tracker | ✅ Done (health.py + test_health.py, 63 tests) |
| deleg_e332cb3f (sub-agent #2) | **Mind & Habits** — intrusive thought analysis (triggers, CBT), snacking trigger→response, focus/pomodoro, daily goals, weekly review | ✅ Done (mind.py + test_mind.py, 60 tests) |
| deleg_7d6263f3 (sub-agent #3) | **Integration Tests** — testy integracyjne wszystkich modułów, raport | 🔄 W trakcie |
| deleg_7d6263f3 (sub-agent #4) | **Documentation** — USER_GUIDE.md, ARCHITECTURE.md, QUICKSTART.md | 🔄 W trakcie |

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
├── QUICKSTART.md              # 5-minutowy start (sub-agent #4)
├── USER_GUIDE.md              # Pełny user guide (sub-agent #4)
├── ARCHITECTURE.md            # Architektura techniczna (sub-agent #4)
├── INTEGRATION_TEST_REPORT.md # Raport testów (sub-agent #3)
├── life_cli.py                # Core engine (GŁÓWNY)
├── health.py                  # Health & Wellness (sub-agent #1)
├── mind.py                    # Mind & Habits (sub-agent #2)
├── hermes_integration.py      # Hermes Integration (GŁÓWNY)
├── gamification.py            # XP, achievements, quests (GŁÓWNY)
├── dashboard_server.py        # HTTP Dashboard (GŁÓWNY)
├── telegram_bot.py            # Telegram Bot (GŁÓWNY)
├── gcal_sync.py               # Google Calendar + Notion (GŁÓWNY)
├── voice_reminders.py         # TTS Reminders (GŁÓWNY)
├── dashboard.html             # Statyczny dashboard
├── test_life_cli.py           # 27 testów core engine
├── test_health.py             # 63 testy health
├── test_mind.py               # 60 testów mind
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
- ✅ Hermes Integration (5 cron jobs, notification bridge, dashboard, seed data)
- ✅ Telegram Bot (30+ komend, long polling)
- ✅ Dashboard Server (HTTP API + interaktywny web UI)
- ✅ Google Calendar Sync (export/import, birthday sync)
- ✅ Notion Backup (markdown export)
- ✅ Voice Reminders (TTS dla pigułek, urodzin, overdue)
- ✅ Gamification (XP, 12 poziomów, 20 achievementów, 7 daily quests, 7 weekly challenges)
- ✅ 150+ testów jednostkowych
- ✅ Hermes skill: `productivity/life-management`
