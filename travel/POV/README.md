# POV: Travel MCP Server for Hermes

## Co to jest

Własny MCP server w Pythonie dający Hermesowi 5 narzędzi do planowania podróży:

| Narzędzie | API | Co robi |
|-----------|-----|---------|
| `search_flights` | Amadeus | Szuka lotów między lotniskami |
| `search_restaurants` | Google Places | Szuka restauracji z ocenami, cenami, zdjęciami |
| `search_venues` | Google Places | Szuka barów, klubów, kawiarni, parków, muzeów |
| `search_events` | Eventbrite | Szuka wydarzeń (koncerty, festiwale, warsztaty) |
| `get_weather` | OpenWeatherMap | Prognoza pogody na 1-5 dni |

## Instalacja

```bash
# 1. Zainstaluj zależności (tylko stdlib — nic nie trzeba!)
# Kod używa wyłącznie urllib + json z Pythona 3.10+

# 2. Ustaw API keys
export AMADEUS_API_KEY="twój_klucz"
export AMADEUS_API_SECRET="twój_sekret"
export GOOGLE_PLACES_API_KEY="twój_klucz"
export EVENTBRITE_API_KEY="twój_klucz"
export OPENWEATHERMAP_API_KEY="twój_klucz"
```

## Test

```bash
# Pokaż dostępne narzędzia
python3 travel_mcp_server.py

# Wyszukaj loty GDN → WAW
echo '{"method":"tools/call","params":{"name":"search_flights","arguments":{"origin":"GDN","destination":"WAW","departure_date":"2026-08-01"}}}' | python3 travel_mcp_server.py

# Wyszukaj restauracje w Gdańsku
echo '{"method":"tools/call","params":{"name":"search_restaurants","arguments":{"location":"Gdańsk, Poland","cuisine":"italian","min_rating":4.5}}}' | python3 travel_mcp_server.py

# Wyszukaj bary w Gdańsku
echo '{"method":"tools/call","params":{"name":"search_venues","arguments":{"location":"Gdańsk, Poland","venue_type":"bar"}}}' | python3 travel_mcp_server.py

# Wyszukaj wydarzenia
echo '{"method":"tools/call","params":{"name":"search_events","arguments":{"location":"Gdańsk","start_date":"2026-08-01","end_date":"2026-08-31"}}}' | python3 travel_mcp_server.py

# Pogoda
echo '{"method":"tools/call","params":{"name":"get_weather","arguments":{"city":"Gdańsk","days":3}}}' | python3 travel_mcp_server.py
```

## Integracja z Hermesem

### Opcja 1: Jako custom tool (najprostsza)

Dodaj do `~/.hermes/tools/travel.py`:

```python
import subprocess, json, sys

def search_flights(origin, destination, departure_date, return_date=None, adults=1):
    result = subprocess.run(
        ["python3", "~/workspace/hermes-enhancements/travel/POV/travel_mcp_server.py"],
        input=json.dumps({
            "method": "tools/call",
            "params": {
                "name": "search_flights",
                "arguments": {
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                    "return_date": return_date,
                    "adults": adults,
                }
            }
        }),
        capture_output=True, text=True, timeout=30,
    )
    return json.loads(result.stdout)
```

### Opcja 2: Jako MCP server (pełna integracja)

```bash
hermes mcp add travel --command "python3 ~/workspace/hermes-enhancements/travel/POV/travel_mcp_server.py"
```

## API Keys — jak zdobyć

| API | Rejestracja | Darmowy tier | Link |
|-----|------------|-------------|------|
| Amadeus | 5 min | Tak (test env) | https://developers.amadeus.com/ |
| Google Places | 5 min | $200/mies free | https://console.cloud.google.com/ |
| Eventbrite | 2 min | Tak | https://www.eventbrite.com/platform/ |
| OpenWeatherMap | 2 min | 1000 req/dzień | https://openweathermap.org/api |

## Przykład użycia przez Hermesa

```
User: "Znajdź loty z Gdańska do Barcelony na weekend 15-17 sierpnia,
      restauracje z dobrymi ocenami i wydarzenia w tym terminie."

Hermes:
1. search_flights("GDN", "BCN", "2026-08-15", "2026-08-17")
2. search_restaurants("Barcelona, Spain", cuisine="spanish", min_rating=4.5)
3. search_events("Barcelona", "2026-08-15", "2026-08-17")
4. get_weather("Barcelona", days=3)
→ Pełny plan podróży z cenami, ocenami i pogodą
```

## Status

✅ Kod działa (zero zależności — tylko Python stdlib)
✅ 5 narzędzi zdefiniowanych
✅ Obsługa błędów (timeout, brak API key, invalid JSON)
⬜ API keys do zdobycia (wymagają rejestracji)
⬜ Testy integracyjne z Hermesem
