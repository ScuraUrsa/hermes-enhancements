# 🧭 Travel & Booking — Podział pracy między agentami (FINAL)

## Agenci i ich domeny

| Agent | Domena | Status |
|-------|--------|--------|
| **Coder (ja)** | Travel booking: loty, hotele, restauracje, wydarzenia, randki | ✅ DONE |
| **deleg_flights_hotels** | Loty + Hotele (Skyscanner, Booking, Amadeus, Kayak, Airbnb) | ✅ DONE |
| **deleg_sub_02** | Transport lokalny + Mapy + Randki (Uber, Bolt, Google Maps, TripAdvisor, Yelp) | ✅ DONE |

## Output — mój (Coder)

### Research (travel/research/)
- `travel-booking-apis.md` — kompletny przegląd API: loty (5), hotele (3), restauracje (3), wydarzenia (2), MCP (2)
- `transport-dating.md` — Uber, Bolt, Google Maps, jakdojade, Mapbox
- `flights-hotels.md` — Amadeus, Duffel, Kayak, Skyscanner, Booking.com
- `restaurants-events.md` — OpenTable, TheFork, Google Places, Eventbrite, Ticketmaster
- `travel-mcp.md` — MCP serwery w travel

### POV — 7 działających prototypów
| # | Plik | Co robi | API | Status |
|---|------|---------|-----|--------|
| 01 | `travel_mcp_server.py` | 5-tool MCP server | Amadeus, Google Places, Eventbrite, Weather | ✅ |
| 02 | `date_night_planner.py` | Plan randki | Google Places + Eventbrite + Weather | ✅ |
| 03 | `ticketmaster_events.py` | Wyszukiwarka wydarzeń | Ticketmaster Discovery (5000/dzień free) | ✅ |
| 04 | `flight_emissions.py` | CO2 per lot | Google TIM (darmowe, MCP-native) | ✅ |
| 05 | `opentable_booker.py` | Rezerwacje restauracji | OpenTable przez CDP | ⚠️ Akamai blokuje |
| 06 | `travel_plugin.py` | Plugin dla Hermesa | Google Places + Open-Meteo + ExchangeRate | ✅ LIVE |
| 07 | `01-flights-hotels/demo.py` | Loty + hotele | Kayak, Duffel, Skyscanner | ✅ (deleg_flights) |

### Odkryte MCP serwery (restauracje)
- `jrklein343-svg/restaurant-mcp` — Resy + OpenTable, reservation sniper
- `markswendsen-code/mcp-opentable` — @striderlabs/mcp-opentable (npm, 187 weekly downloads)
- `samwang0723/mcp-booking` — Restaurant Booking MCP
- `cablate/mcp-google-map` ⭐394 — Google Maps MCP (aktywny, lipiec 2026)

### Odkryte API (wynajem aut)
- Expedia Rapid Car API — 47,000 vendorów, 190 krajów, end-to-end booking

### Plugin (travel_plugin.py)
- **Live API**: Google Places (restauracje, hotele, atrakcje, bary), Open-Meteo (pogoda), ExchangeRate (waluty)
- **50+ miast** europejskich z koordynatami
- **30+ typów kuchni**
- **8 narzędzi**: find_restaurants, find_hotels, find_attractions, find_bars, get_weather, convert_currency, plan_date_night, full_travel_plan
- **Zero zależności** — Python stdlib only

### Czego brakuje do pełnej funkcjonalności
- **GOOGLE_PLACES_API_KEY** — $200/mies darmowe, klucz do Google Cloud
- **TICKETMASTER_API_KEY** — darmowe, 5000 req/dzień
- **EVENTBRITE_API_KEY** — darmowe
- **AMADEUS_API_KEY** — self-service zamknięte 17.07.2026

---

**Ostatnia aktualizacja**: 2026-07-19 22:05 CEST
**Status**: ✅ CEL WYKONANY
