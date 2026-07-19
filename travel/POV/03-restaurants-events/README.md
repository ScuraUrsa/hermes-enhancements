# POV: Restaurant & Event Finder for Hermes

## Cel
Dać Hermesowi możliwość wyszukiwania restauracji, wydarzeń i planowania randek w Trójmieście.

## Status
✅ Demo działa (mock data + Google Places API ready)
✅ 3 komendy: restaurants, events, date-night
✅ 10 restauracji + 8 wydarzeń w mock data
⚠️  Wymaga GOOGLE_PLACES_API_KEY do live API

## Szybki start

```bash
cd ~/workspace/hermes-enhancements/travel/POV/03-restaurants-events

# Restauracje
python3 demo.py restaurants Gdańsk włoska
python3 demo.py restaurants Sopot sushi

# Wydarzenia
python3 demo.py events Gdańsk 2026-07-25

# Randka
python3 demo.py date-night "Gdańsk Śródmieście"
```

## API

| API | Klucz | Status |
|-----|-------|--------|
| Google Places | `GOOGLE_PLACES_API_KEY` | Mock ready, live ready |
| Eventbrite | `EVENTBRITE_API_KEY` | Mock ready |
| Ticketmaster | `TICKETMASTER_API_KEY` | Mock ready |

## Integracja z Hermesem

```bash
# Dodaj klucz
echo "GOOGLE_PLACES_API_KEY=..." >> ~/.hermes/.env

# Zarejestruj jako custom tool
# Plugin: ~/.hermes/plugins/restaurant_finder/plugin.py
```

## Mock data

- 10 restauracji w Gdańsku (polska, włoska, japońska, meksykańska, steki, wegańska, fine dining, wine bar)
- 8 wydarzeń (koncerty, festiwale, teatr, kino, stand-up, rejsy, degustacje)
- Date-night planner: restauracja + wydarzenie + bar
