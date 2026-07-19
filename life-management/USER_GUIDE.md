# 🧬 Life Management System — Przewodnik Użytkownika

Kompletny system do zarządzania każdą minutą życia. Śledzisz czas w 5-minutowych blokach, zarządzasz relacjami z ludźmi, monitorujesz zdrowie, nawyki i produktywność — wszystko z terminala, Telegrama lub dashboardu.

---

## 📦 Instalacja i pierwsze uruchomienie

### 1. Sklonuj repozytorium

```bash
cd ~/workspace
git clone git@github.com:ScuraUrsa/hermes-enhancements.git
cd hermes-enhancements/life-management
```

### 2. Wygeneruj dane startowe (seed)

```bash
# Dodaj 50 przykładowych osób + bloki czasu + wydarzenia
python3 hermes_integration.py seed
```

To polecenie:
- Tworzy bazę SQLite `data/life_management.db`
- Dodaje 50 osób w 5 kategoriach (rodzina bliższa, dalsza, znajomi bliscy, znajomi, współpracownicy)
- Generuje przykładowe bloki czasu z ostatnich 7 dni
- Dodaje wydarzenia (urodziny, deadline, wizyta u dentysty)
- Loguje przykładowe nawyki

### 3. Skonfiguruj cron jobs (automatyczne przypomnienia)

```bash
python3 -c "from hermes_integration import CronManager; CronManager.setup_all()"
```

To tworzy 8 automatycznych zadań:
- **08:00** — Daily brief (podsumowanie dnia, overdue kontakty, urodziny)
- **09:00** — Przypomnienie o porannych pigułkach
- **12:00** — Południowy check-in ("co robisz?")
- **21:00** — Przypomnienie o wieczornych pigułkach
- **22:00** — Wieczorny check-in (energia, focus, myśli, podjadanie)
- **Niedziela 20:00** — Raport tygodniowy
- **07:00** — Sprawdzenie urodzin na dziś i 7 dni

### 4. (Opcjonalnie) Uruchom Telegram bota

```bash
# Pobierz token z Bitwarden lub ustaw zmienną TELEGRAM_BOT_TOKEN
export TELEGRAM_BOT_TOKEN="twój_token"

# Uruchom bota (long polling)
python3 telegram_bot.py run
```

### 5. (Opcjonalnie) Uruchom web dashboard

```bash
python3 dashboard_server.py 8080
# Otwórz http://localhost:8080
```

---

## ⏱️ Śledzenie czasu

System działa na **5-minutowych blokach**. Każdy blok ma kategorię, opcjonalnie przypisaną osobę, poziom energii i focusu.

### Podstawowe komendy CLI

```bash
# Rozpocznij blok czasu
python3 life_cli.py start praca
python3 life_cli.py start hobby "Gitara"
python3 life_cli.py start rodzina 1    # 1 = ID osoby (Mama)

# Zakończ blok
python3 life_cli.py stop
python3 life_cli.py stop "Skończyłem kodować API"

# Ręcznie dodaj blok (wstecz)
python3 life_cli.py log "2026-07-19T08:00:00" "2026-07-19T09:00:00" praca

# Podsumowanie dnia
python3 life_cli.py today

# Raport tygodniowy
python3 life_cli.py week
```

### Kategorie czasu

| Kategoria | Opis | Przykład |
|-----------|------|----------|
| `praca` | Praca zawodowa | Kodowanie, meetingi, maile |
| `rodzina` | Czas z rodziną | Telefon do mamy, obiad z tatą |
| `znajomi` | Czas ze znajomymi | Kawa, spotkanie, impreza |
| `zdrowie` | Ćwiczenia, lekarz | Siłownia, bieganie, wizyta |
| `jedzenie` | Posiłki, gotowanie | Śniadanie, obiad, kolacja |
| `hobby` | Pasje, hobby | Gitara, czytanie, gry |
| `odpoczynek` | Sen, relaks | Drzemka, medytacja, Netflix |
| `nauka` | Nauka, kursy | Kurs online, czytanie książki |
| `administracja` | Zakupy, sprzątanie | Rachunki, porządki, zakupy |
| `transport` | Dojazdy | Samochód, autobus, rower |
| `higiena` | Higiena osobista | Prysznic, mycie zębów |
| `inne` | Wszystko pozostałe | — |

### Przez Telegram bota

```
/praca          — rozpocznij blok "praca"
/rodzina        — rozpocznij blok "rodzina"
/hobby Gitara   — rozpocznij blok "hobby" z opisem
/stop           — zakończ blok
/today          — podsumowanie dnia
/week           — raport tygodniowy
```

### Przez web dashboard

Dashboard (`http://localhost:8080`) ma zakładkę **⚡ Szybkie** z przyciskami do start/stop bloków i logowania nawyków jednym kliknięciem.

---

## 👥 People CRM — zarządzanie relacjami

System śledzi **50 osób** w 6 kategoriach. Dla każdej osoby zapisujesz: priorytet (1-10), urodziny, częstotliwość kontaktu, datę ostatniego kontaktu.

### Kategorie osób

| Kategoria | Przykłady | Domyślna częstotliwość |
|-----------|-----------|----------------------|
| `rodzina_blizsza` | Mama, Tata, rodzeństwo, partner | 3-7 dni |
| `rodzina_dalsza` | Kuzyni, wujkowie, dziadkowie | 14-30 dni |
| `znajomi_bliscy` | Najlepsi przyjaciele | 5-10 dni |
| `znajomi` | Reszta znajomych | 30-60 dni |
| `wspolpracownicy` | Ludzie z pracy | 1-7 dni |
| `inni` | Wszyscy pozostali | 90+ dni |

### Komendy CLI

```bash
# Lista wszystkich osób
python3 life_cli.py people

# Dodaj nową osobę
python3 life_cli.py people-add "Kumpel Marek" znajomi_bliscy

# Balans czasu z osobami (ostatnie 30 dni)
python3 life_cli.py balance

# Kto potrzebuje kontaktu (overdue)
python3 life_cli.py attention

# Nadchodzące urodziny
python3 life_cli.py birthdays 30    # w ciągu 30 dni
```

### Jak działa "overdue"?

System porównuje `days_since_contact` z `contact_frequency_days`. Jeśli minęło więcej dni niż wynosi częstotliwość — osoba jest **overdue** 🔴.

Przykład: Mama ma `contact_frequency_days = 3`. Jeśli nie dzwoniłeś od 5 dni → 🔴 overdue.

### Automatyczna aktualizacja kontaktu

Gdy używasz `start`/`stop` z `person_id`, system automatycznie aktualizuje `last_contact`:

```bash
python3 life_cli.py start rodzina 1   # 1 = ID Mamy
# ... rozmowa ...
python3 life_cli.py stop "Telefon do Mamy"
# → last_contact Mamy zaktualizowany automatycznie
```

---

## 💊 Logowanie nawyków

### Pigułki

```bash
# Szybkie logowanie
python3 life_cli.py pill taken
python3 life_cli.py pill skipped

# Sprawdź serię
python3 life_cli.py habit-streak pills
```

### Natarczywe myśli (intensywność 1-10)

```bash
python3 life_cli.py thought 7
```

Rozszerzona wersja (przez `mind.py`) dodaje analizę CBT:
- Typ zniekształcenia poznawczego (katastrofizacja, myślenie czarno-białe, czytanie w myślach...)
- Trigger (co wywołało myśl)
- Strategia radzenia sobie (mindfulness, przeformułowanie, odwrócenie uwagi...)
- Skuteczność strategii (1-10)

### Podjadanie (intensywność 1-10)

```bash
python3 life_cli.py snack 4
```

Rozszerzona wersja (`mind.py`) dodaje mapowanie trigger→response:
- Co wywołało (nuda, stres, smutek, zmęczenie...)
- Co zjadłeś i ile
- Jak się czułeś po (poczucie winy, zadowolenie, przejedzenie...)
- Co mogłeś zrobić zamiast

### Inne nawyki

```bash
# Woda
python3 life_cli.py habit water "250ml"

# Ćwiczenia
python3 life_cli.py habit exercise "30min siłownia"

# Focus session
python3 life_cli.py habit focus_session "25min deep work"

# Dowolny nawyk
python3 life_cli.py habit <typ> <wartość> [intensywność]
```

### Przez Telegram

```
/pill              — zaloguj pigułki (taken)
/thought 7         — natarczywa myśl 7/10
/snack 4           — podjadanie 4/10
/woda 250          — szklanka wody
/ćwiczenia 30      — 30 minut ćwiczeń
/sen 7.5           — 7.5h snu
```

---

## 📊 Raporty

### Daily Brief

```bash
python3 life_cli.py brief
```

Pokazuje:
- ⏱️ Podsumowanie czasu (kategorie + godziny)
- 🔔 Nadchodzące wydarzenia (dziś/jutro)
- 🎂 Urodziny w ciągu 7 dni
- 👥 Kto potrzebuje kontaktu (overdue)
- 💊 Logi nawyków na dziś

### Raport tygodniowy

```bash
python3 life_cli.py week
```

Pokazuje:
- 📊 Średnio godzin dziennie
- 📂 Rozkład kategorii z wizualnymi słupkami
- 👥 Top 5 osób z największą ilością czasu
- 🔴 Overdue kontakty
- 💊 Trendy nawykowe (częstotliwość + średnia intensywność)

### Przez Telegram

```
/brief     — daily brief
/today     — podsumowanie dnia
/week      — raport tygodniowy
/attention — kto potrzebuje kontaktu
/balance   — balans czasu z osobami
```

---

## 🎮 Gamifikacja

System nagradza Cię XP za regularne korzystanie. Im więcej używasz, tym wyższy poziom.

### Jak zdobywać XP

| Akcja | XP |
|-------|-----|
| Zalogowanie bloku czasu | +5 |
| Wzięcie pigułek | +10 (+2 za każdy dzień serii) |
| Ćwiczenia | +15 |
| Kontakt z osobą | +20 |
| Daily brief przeczytany | +5 |
| 100% pokrycia dnia | +50 |
| 7-dniowy streak pigułek | +100 |
| Tydzień bez overdue kontaktów | +200 |

### Poziomy

| Poziom | XP | Tytuł |
|--------|-----|-------|
| 1 | 0 | 🌱 Nowicjusz |
| 2 | 100 | 📗 Praktykant |
| 3 | 300 | 📘 Rzemieślnik |
| 4 | 600 | 📙 Adept |
| 5 | 1 000 | 📕 Mistrz |
| 6 | 2 000 | 💎 Ekspert |
| 7 | 3 500 | 👑 Weteran |
| 8 | 5 000 | 🌟 Arcymistrz |
| 9 | 8 000 | 🔥 Feniks |
| 10 | 12 000 | ⚡ Tytan |
| 11 | 20 000 | 🌌 Legenda |
| 12 | 35 000 | 🧬 Transcendencja |

### Achievementy (20+)

Przykładowe:
- 👣 **Pierwszy krok** — pierwszy blok czasu (+25 XP)
- 🔥 **Tydzień zdrowia** — 7 dni pigułek z rzędu (+100 XP)
- 💪 **Miesiąc zdrowia** — 30 dni pigułek (+500 XP)
- 🏆 **Żelazna dyscyplina** — 90 dni pigułek (+1500 XP)
- ✅ **Niezawodny** — tydzień bez overdue kontaktów (+200 XP)
- 📅 **Pełny dzień** — 100% pokrycia dnia (+100 XP)
- ⚖️ **Balans** — wszystkie 6 kategorii czasu w jednym dniu (+150 XP)

### Daily Questy (7)

Codzienne wyzwania z postępem:
- 📋 **Rejestrator** — zaloguj 5+ bloków (+30 XP)
- 💊 **Tabletkowy** — weź pigułki (+20 XP)
- 💪 **Aktywny** — zrób ćwiczenia (+30 XP)
- 👥 **Społecznik** — kontakt z 1+ osobą (+25 XP)
- 🚫 **Czysta dieta** — zero podjadania (+40 XP)
- 💧 **Nawodniony** — 2L wody (+20 XP)
- 🎯 **Skupiony** — 1+ sesja deep work (+25 XP)

### Weekly Challenge'y (7)

- 🔥 **Perfekcyjny tydzień** — pigułki 7/7 dni (+150 XP)
- 💪 **Tydzień ruchu** — ćwiczenia 5+ razy (+200 XP)
- 👥 **Społeczny tydzień** — kontakt z 10+ osobami (+250 XP)
- 📊 **Świadomy tydzień** — średnie pokrycie >80% (+300 XP)
- ✅ **Niezawodny tydzień** — zero overdue (+200 XP)
- 🎯 **Tydzień skupienia** — 10+ sesji deep work (+250 XP)
- ⚖️ **Balans tygodnia** — wszystkie kategorie czasu (+200 XP)

### Komendy gamifikacji

```bash
# Pełny status
python3 gamification.py status

# Aktualny poziom
python3 gamification.py level

# Lista achievementów
python3 gamification.py achievements

# Daily questy
python3 gamification.py quests

# Weekly challenge'y
python3 gamification.py challenges

# Auto-check (sprawdź i przyznaj nagrody)
python3 gamification.py check
```

---

## 🔗 Integracje

### Google Calendar

Synchronizuj bloki czasu z Google Calendar:

```bash
# Eksportuj bloki z ostatnich 7 dni do Google Calendar
python3 gcal_sync.py gcal-export 7

# Importuj eventy z Google Calendar
python3 gcal_sync.py gcal-import 30

# Dodaj urodziny jako recurring eventy
python3 gcal_sync.py gcal-sync-birthdays
```

Wymaga: service account JSON w `data/google_credentials.json` lub token OAuth w Bitwarden (`GOOGLE_CALENDAR_TOKEN`).

### Notion

Eksportuj dane do Notion:

```bash
# Eksportuj listę osób jako markdown
python3 gcal_sync.py notion-people

# Eksportuj raport tygodniowy jako markdown
python3 gcal_sync.py notion-weekly

# Wyślij do Notion
python3 gcal_sync.py notion-push "Raport tygodniowy"
```

Wymaga: `NOTION_API_KEY` w Bitwarden lub zmiennej środowiskowej.

### Telegram Bot

Pełna lista komend bota:

```
/praca /rodzina /znajomi /zdrowie /jedzenie
/hobby /odpoczynek /nauka /admin /transport
/stop — zakończ blok
/pill — zaloguj pigułki
/thought 7 — natarczywa myśl
/snack 4 — podjadanie
/woda 250 — szklanka wody
/ćwiczenia 30 — trening
/sen 7.5 — godziny snu
/brief — daily brief
/today — podsumowanie dnia
/week — raport tygodniowy
/attention — kto potrzebuje kontaktu
/balance — balans czasu z osobami
/birthdays — nadchodzące urodziny
/events — nadchodzące wydarzenia
/people — lista osób
```

### Hermes Voice Reminders

```bash
# Wygeneruj wszystkie przypomnienia (tekst)
python3 voice_reminders.py generate

# Wygeneruj i odtwórz przez TTS
python3 voice_reminders.py speak

# Daily brief głosowy
python3 voice_reminders.py brief
```

---

## 🏥 Moduł Health & Wellness

Rozszerzone śledzenie zdrowia przez `health.py`:

### Harmonogram pigułek

```python
from health import HealthDB, PillScheduler

db = HealthDB()
scheduler = PillScheduler(db)

# Dodaj harmonogram
scheduler.add_schedule(
    pill_name="Witamina D",
    time_of_day="09:00",
    days_of_week=[1,2,3,4,5,6,7],  # codziennie
    dosage="2000 IU"
)

# Zaloguj zażycie
scheduler.log_pill(schedule_id=1, status="taken")

# Sprawdź adherence (ostatnie 7 dni)
scheduler.get_adherence(schedule_id=1, days=7)
```

### Posiłki (kalorie, makro)

```python
from health import HealthDB, MealTracker

db = HealthDB()
meals = MealTracker(db)

meals.log_meal(
    meal_type="lunch",
    name="Kurczak z ryżem",
    calories=650,
    protein_g=45.0,
    carbs_g=60.0,
    fat_g=15.0
)
```

### Woda, ćwiczenia, sen

```python
from health import HealthDB, WaterTracker, ExerciseTracker, SleepTracker

db = HealthDB()
water = WaterTracker(db)
exercise = ExerciseTracker(db)
sleep = SleepTracker(db)

water.log_water(amount_ml=250)
exercise.log_exercise("running", duration_minutes=30, intensity=7)
sleep.log_sleep(bedtime="2026-07-19T23:00:00", wake_time="2026-07-20T07:00:00", quality=8)
```

---

## 🧠 Moduł Mind & Habits

Rozszerzona analiza przez `mind.py`:

### Analiza CBT natarczywych myśli

```python
from mind import MindDB, IntrusiveThoughtTracker

db = MindDB()
thoughts = IntrusiveThoughtTracker(db)

thoughts.log_thought(
    thought_content="Na pewno mnie zwolnią po tym błędzie",
    trigger="Krytyczna uwaga od szefa",
    cbt_pattern="catastrophizing",
    intensity=8,
    coping_strategy="cognitive_restructuring",
    coping_effectiveness=7,
    outcome="Uspokoiłem się po 10 minutach"
)

# Rozkład zniekształceń poznawczych
thoughts.get_cbt_pattern_breakdown(days=30)

# Najskuteczniejsze strategie
thoughts.get_coping_effectiveness_report(days=30)
```

### Mapowanie trigger→response podjadania

```python
from mind import MindDB, SnackingTracker

db = MindDB()
snacks = SnackingTracker(db)

snacks.log_snack(
    trigger_type="stress",
    trigger_detail="Deadline w pracy, napięcie od 2h",
    food_eaten="Cała paczka chipsów",
    amount="150g",
    intensity=8,
    feeling_after="guilty",
    alternative_action="5 minut ćwiczeń oddechowych"
)

# Rozkład triggerów
snacks.get_trigger_breakdown(days=30)
```

### Focus/Pomodoro

```python
from mind import MindDB, FocusTracker

db = MindDB()
focus = FocusTracker(db)

focus.start_session(
    duration_minutes=25,
    task_description="Refaktoryzacja API"
)

focus.end_session(
    session_id=1,
    distractions=["Slack notification", "Phone call"],
    productivity_score=7,
    focus_level=6
)
```

### Daily Goals (3 MITs)

```python
from mind import MindDB, GoalTracker

db = MindDB()
goals = GoalTracker(db)

goals.set_goal(goal_text="Dokończyć PR do review", priority_order=1)
goals.set_goal(goal_text="Odpowiedzieć na 5 maili", priority_order=2)
goals.set_goal(goal_text="30 min ćwiczeń", priority_order=3)

goals.complete_goal(goal_id=1)
```

### Weekly Review

```python
from mind import MindDB, ReviewTracker

db = MindDB()
reviews = ReviewTracker(db)

reviews.create_review(
    what_went_well="Skończyłem duży feature, 3 treningi",
    what_to_improve="Za mało snu, za dużo podjadania",
    lessons_learned="Planowanie dnia od 8:00 działa lepiej",
    gratitude="Wsparcie od zespołu, zdrowie rodziny",
    energy_avg=7,
    mood_avg=6,
    next_week_focus="Sen minimum 7h, zero podjadania po 20:00"
)
```

---

## 🗄️ Backup i bezpieczeństwo

### Backup bazy danych

```bash
# Kopia zapasowa
cp data/life_management.db data/life_management_backup_$(date +%Y%m%d).db

# Automatyczny backup przez cron
# Dodaj do crontab:
# 0 3 * * * cp ~/workspace/hermes-enhancements/life-management/data/life_management.db ~/backups/life_$(date +\%Y\%m\%d).db
```

### Eksport do Notion (markdown)

```bash
python3 gcal_sync.py notion-people > people_backup.md
python3 gcal_sync.py notion-weekly > weekly_backup.md
```

---

## 🔧 Rozwiązywanie problemów

### "Brak aktywnego bloku" przy `stop`

Oznacza, że nie ma otwartego bloku. Zacznij od `start`:

```bash
python3 life_cli.py start praca
python3 life_cli.py stop
```

### "Nie znam komendy" w Telegram bocie

Sprawdź listę komend przez `/help`. Bot akceptuje też polskie aliasy (`/pigułki`, `/myśl`, `/dziś`).

### Baza nie istnieje

```bash
# Jeśli dashboard nie widzi bazy:
python3 hermes_integration.py seed
```

### Google Calendar — błąd autoryzacji

1. Umieść service account JSON w `data/google_credentials.json`
2. Lub zapisz token OAuth w Bitwarden: `bws secret create GOOGLE_CALENDAR_TOKEN "twój_token"`

---

## 📋 Ściągawka komend CLI

```bash
# ⏱️ CZAS
python3 life_cli.py start <kategoria> [osoba_id]   # rozpocznij blok
python3 life_cli.py stop [opis]                     # zakończ blok
python3 life_cli.py log <start> <end> <kat>         # ręczny blok
python3 life_cli.py today                           # podsumowanie dnia
python3 life_cli.py week                            # raport tygodniowy
python3 life_cli.py brief                           # daily brief

# 👥 OSOBY
python3 life_cli.py people                          # lista osób
python3 life_cli.py people-add <imię> <kat>         # dodaj osobę
python3 life_cli.py balance                         # balans czasu
python3 life_cli.py attention                       # kto overdue
python3 life_cli.py birthdays [dni]                 # urodziny
python3 life_cli.py events [dni]                    # wydarzenia

# 💊 NAWYKI
python3 life_cli.py pill taken|skipped              # pigułki
python3 life_cli.py thought <1-10>                  # natarczywa myśl
python3 life_cli.py snack <1-10>                    # podjadanie
python3 life_cli.py habit <typ> <wartość> [int]     # dowolny nawyk
python3 life_cli.py habit-streak <typ>              # sprawdź serię

# 🎮 GAMIFIKACJA
python3 gamification.py status                      # pełny status
python3 gamification.py level                       # poziom
python3 gamification.py achievements                # achievementy
python3 gamification.py quests                      # daily questy
python3 gamification.py challenges                  # weekly challenge'y
python3 gamification.py check                       # auto-check nagród

# 🔗 INTEGRACJE
python3 gcal_sync.py gcal-export [dni]              # → Google Calendar
python3 gcal_sync.py gcal-import [dni]              # ← Google Calendar
python3 gcal_sync.py gcal-sync-birthdays            # urodziny → GC
python3 gcal_sync.py notion-people                  # osoby → markdown
python3 gcal_sync.py notion-weekly                  # raport → markdown

# 🤖 TELGRAM
python3 telegram_bot.py run [token]                 # uruchom bota
python3 telegram_bot.py test [token]                # test komend

# 🖥️ DASHBOARD
python3 dashboard_server.py [port]                  # uruchom dashboard

# 🔊 VOICE
python3 voice_reminders.py generate                 # teksty przypomnień
python3 voice_reminders.py speak                    # TTS
python3 voice_reminders.py brief                    # głosowy brief
```
