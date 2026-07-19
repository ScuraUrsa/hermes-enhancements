# POV #13: Life Time Tracker — Core Engine

## Co to jest

Kompletny system zarządzania życiem przez CLI. Fundament pod wszystkie moduły life-management.

## Funkcje

### ⏱️ Time Tracker (bloki 5-minutowe)
- `start <kategoria> [osoba_id]` — rozpocznij blok czasu
- `stop [opis]` — zakończ blok
- `log <start> <end> <kat>` — ręcznie dodaj blok wstecz
- `today` — podsumowanie dnia
- `week` — raport tygodniowy

### 👥 People CRM (50 osób)
- `people-add <imię> <kategoria>` — dodaj osobę
- `people` — lista wszystkich osób
- `balance` — balans czasu spędzonego z każdą osobą (30 dni)
- `attention` — kto potrzebuje kontaktu (overdue + priorytet)
- `birthdays [dni]` — nadchodzące urodziny

### 📅 Event Manager
- `events [dni]` — nadchodzące wydarzenia
- Automatyczne przypomnienia (reminder_days_before)
- Recurring events (urodziny co roku)

### 💊 Habit Tracker
- `pill taken|skipped` — logowanie pigułek + streak
- `thought <intensywność>` — natarczywe myśli
- `snack <intensywność>` — podjadanie
- `habit <typ> <wartość>` — dowolny nawyk
- `habit-streak <typ>` — sprawdź serię

### 📊 Raporty
- `brief` — pełny daily brief (czas, wydarzenia, urodziny, kontakt, nawyki)
- `week` — deep dive tygodniowy

## Architektura

```
life-management/
├── AGENT_ASSIGNMENTS.md    # Koordynacja między agentami
├── life_cli.py             # CLI + cały core engine (SQLite)
├── test_life_cli.py        # 27 testów jednostkowych
├── README.md               # Ten plik
├── core/                   # SQLAlchemy models (inny agent)
│   ├── models.py
│   ├── services.py
│   └── seed.py
└── data/
    └── life_management.db # SQLite (tworzona automatycznie)
```

## Baza danych

SQLite z 4 tabelami:
- `people` — osoby (name, category, priority, birthday, contact_frequency_days, last_contact)
- `time_blocks` — bloki 5-minutowe (start_time, end_time, category, person_id, energy, focus)
- `events` — wydarzenia (title, event_date, event_type, recurring, reminder_days_before)
- `habit_log` — logi nawyków (timestamp, habit_type, value, intensity)

## Kategorie czasu

`praca`, `rodzina`, `znajomi`, `zdrowie`, `jedzenie`, `hobby`, `odpoczynek`, `nauka`, `administracja`, `transport`, `higiena`, `inne`

## Kategorie osób

`rodzina_blizsza`, `rodzina_dalsza`, `znajomi_bliscy`, `znajomi`, `wspolpracownicy`, `inni`

## Szybki start

```bash
# Dodaj osoby
python3 life_cli.py people-add "Mama" rodzina_blizsza
python3 life_cli.py people-add "Kumpel Marek" znajomi_bliscy

# Śledź czas
python3 life_cli.py start praca
python3 life_cli.py stop "Skończyłem kodować"

# Loguj nawyki
python3 life_cli.py pill taken
python3 life_cli.py thought 7

# Codzienny raport
python3 life_cli.py brief

# Sprawdź kogo zaniedbujesz
python3 life_cli.py attention
```

## Integracja z Hermesem

```bash
# Codzienny brief o 8:00
cronjob create --schedule "0 8 * * *" --prompt "Uruchom python3 ~/workspace/hermes-enhancements/life-management/life_cli.py brief i wyślij wynik"

# Przypomnienie o pigułkach o 9:00 i 21:00
cronjob create --schedule "0 9,21 * * *" --prompt "Przypomnij użytkownikowi o wzięciu pigułek. Uruchom python3 life_cli.py pill taken jeśli użytkownik potwierdzi."

# Tygodniowy raport w niedzielę o 20:00
cronjob create --schedule "0 20 * * 0" --prompt "Uruchom python3 ~/workspace/hermes-enhancements/life-management/life_cli.py week i wyślij wynik"
```

## Testy

```bash
python3 -m pytest test_life_cli.py -v
# 27 passed
```

## Status

✅ Core engine gotowy
✅ 27 testów przechodzi
✅ CLI w pełni funkcjonalne
⬜ Integracja z Hermes cron jobs
⬜ Dashboard webowy
⬜ Aplikacja mobilna
