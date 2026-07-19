# POV #15: Gotowe MCP Serwery Travel — Podłącz i używaj

## Cel
Nie budować własnych integracji — podłączyć istniejące, darmowe MCP serwery travel, które już działają.

## Status
✅ Research zakończony | ✅ MAQAMI przetestowany | ⬜ Podłączenie do Hermesa

## Znalezione MCP serwery

### 🔥 MAQAMI Travel — NAJLEPSZE
- **URL**: `https://mcp.maqami.co/mcp`
- **Auth**: ❌ Brak (bez API key!)
- **Transport**: Streamable HTTP (SSE)
- **Narzędzia**: 18
  - `post_hotels_rates` — szukaj hoteli (po mieście, współrzędnych, IATA, AI search)
  - `post_hotels_min_rates` — najtańsza cena per hotel
  - `post_rates_prebook` — rezerwacja krok 1
  - `post_rates_book` — rezerwacja krok 2 (potwierdzenie)
  - `post_flights_rates` — szukaj lotów (one-way, round-trip, multi-city)
  - `post_flights_verify` — potwierdź dostępność
  - `post_flights_prebooks` — rezerwacja lotu krok 1
  - `post_flights_bookings` — rezerwacja lotu krok 2
  - `get_data_flights_airports` — autocomplete lotnisk
  - `get_data_flights_airlines` — lista linii lotniczych
  - `get_data_hotels_price_index` — historia cen hoteli
  - + więcej
- **Pokrycie**: 249 krajów, hotele + loty
- **AI Search**: `aiSearch: "Romantic getaway with Italian vibes in London"`

### 🚗 OctoTrip — Wynajem aut
- **URL**: `https://mcp.octotrip.app/rental-cars/mcp`
- **Auth**: ❌ Brak
- **Transport**: Streamable HTTP
- **Narzędzia**: Wynajem aut, real-time ceny, kategorie (economy, compact, SUV)

### 🎫 ticketlens — Atrakcje i wycieczki
- **URL**: `https://github.com/ticketlens/ticketlens-experiences-mcp`
- **Auth**: API key (darmowy)
- **Narzędzia**: Wycieczki, bilety na atrakcje, sport

### 🏠 Airbnb MCP
- **URL**: `https://github.com/openbnb-org/mcp-server-airbnb`
- **Auth**: ❌ Brak
- **Narzędzia**: Szukaj listingów Airbnb

### 🍽️ TripAdvisor MCP
- **URL**: `https://github.com/pab1it0/tripadvisor-mcp`
- **Auth**: API key
- **Narzędzia**: Recenzje, zdjęcia, lokalizacje

### ✈️ Google Flights MCP
- **URL**: `https://github.com/opspawn/Google-Flights-MCP-Server`
- **Auth**: ❌ Brak (fast_flights library)
- **Narzędzia**: Szukaj lotów, najtańsze opcje

### 🌍 Wander Agent — 66 narzędzi
- **URL**: `https://github.com/VirajMishra1/wander-agent`
- **Auth**: ❌ Brak
- **Narzędzia**: Loty, hotele, wizy, pogoda, itinerary, waluty, punkty lojalnościowe

### 💰 Gondola — Ceny w punktach i gotówce
- **URL**: `https://mcp.gondola.ai/mcp`
- **Auth**: OAuth 2.1 (anonimowe wyszukiwanie działa bez)
- **Narzędzia**: Hotele, loty, rental cars z cenami w punktach i gotówce

## Podłączenie do Hermesa

### MAQAMI (hotele + loty)

```bash
# Dodaj MCP server do Hermesa
hermes mcp add maqami \
  --url "https://mcp.maqami.co/mcp" \
  --transport "streamable-http"
```

### OctoTrip (wynajem aut)

```bash
hermes mcp add octotrip \
  --url "https://mcp.octotrip.app/rental-cars/mcp" \
  --transport "streamable-http"
```

### Wszystkie naraz

```bash
hermes mcp add maqami --url "https://mcp.maqami.co/mcp" --transport "streamable-http"
hermes mcp add octotrip --url "https://mcp.octotrip.app/rental-cars/mcp" --transport "streamable-http"
hermes mcp add gondola --url "https://mcp.gondola.ai/mcp" --transport "streamable-http"
```

## Test MAQAMI

```bash
# Szukaj hoteli w Gdańsku przez MAQAMI
curl -s -X POST "https://mcp.maqami.co/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "post_hotels_rates",
      "arguments": {
        "cityName": "Gdansk",
        "countryCode": "PL",
        "checkin": "2026-08-01",
        "checkout": "2026-08-03",
        "currency": "PLN",
        "guestNationality": "PL",
        "occupancies": [{"adults": 2}],
        "maxRatesPerHotel": 1,
        "limit": 5
      }
    }
  }' | grep "^data:" | sed 's/^data: //' | python3 -m json.tool | head -80
```

## Dlaczego to jest lepsze niż własne integracje

| Aspekt | Własne API | Gotowe MCP |
|--------|-----------|------------|
| **Czas wdrożenia** | Dni/tygodnie | Minuty |
| **Utrzymanie** | Trzeba aktualizować | Serwer robi to za nas |
| **API keys** | Trzeba zdobyć dla każdego | MAQAMI/OctoTrip — brak |
| **Booking flow** | Trzeba zaimplementować | Prebook → Book gotowe |
| **Pokrycie** | 1-2 API | MAQAMI: 249 krajów |
| **AI search** | Nie | MAQAMI: `aiSearch` po natural language |

## Rekomendacja

1. **MAQAMI** jako główny silnik (hotele + loty, zero auth)
2. **OctoTrip** do wynajmu aut
3. **ticketlens** do atrakcji i biletów
4. Własne integracje (Google Places, Eventbrite) tylko tam gdzie MCP nie pokrywa

## Koszt
- MAQAMI: darmowe (sandbox/test mode)
- OctoTrip: darmowe
- ticketlens: darmowy tier
- **Łącznie: $0**
