# Travel & Events — Research Summary (Lipiec 2026)

## Obszary pokryte

| Obszar | Research | POV | Agent |
|--------|----------|-----|-------|
| Restauracje + Wydarzenia | ✅ | ✅ POV/03 | Główny |
| Loty + Hotele | ✅ | ✅ POV/01 | deleg_flights |
| Transport + Randki | ✅ | ✅ POV/02 | deleg_transport |
| Travel MCP Server | ✅ | ✅ travel_mcp_server.py | deleg_flights |
| Pogoda + Waluty | ✅ | — | Główny |

## Kluczowe API (dostępne bez partner approval)

| API | Kategoria | Klucz | Cena |
|-----|-----------|-------|------|
| Google Places | Restauracje, miejsca | GCP API key | $200/miesiąc credit |
| Open-Meteo | Pogoda | Brak (free) | Darmowe |
| ExchangeRate-API | Waluty | Brak (free tier) | Darmowe |
| Ticketmaster Discovery | Wydarzenia | API key | Darmowe (rate-limited) |
| Eventbrite | Wydarzenia | OAuth 2.0 | Darmowe |
| Duffel | Loty | API key | Pay-as-you-go |
| Kayak | Loty, hotele | Sandbox | Revenue share |
| Skyscanner | Loty, hotele, auta | Partner | Revenue share |

## API wymagające partner approval

| API | Kategoria | Uwagi |
|-----|-----------|-------|
| Amadeus | Loty, hotele (GDS) | Self-service ZAMKNIĘTE 17.07.2026 |
| Booking.com | Hotele | Demand API — partner only |
| OpenTable | Restauracje | Partner API — application |
| TheFork | Restauracje (Europa) | B2B API — partner |
| Resy | Restauracje (USA) | Gen AI API (2026) |

## MCP w travel

- **travel-mcp-server** (gs-ysingh): flights, hotels, currency, weather
- **mcp_travelassistant** (skarlekar): suite of MCP servers
- **Google Travel Impact Model MCP**: carbon footprint (official)
- Własny: `travel_mcp_server.py` w repo

## Wnioski

1. **Google Places API** to najlepszy start — darmowe $200/miesiąc, globalny zasięg
2. **Amadeus zamknięty** dla indie devów — trzeba szukać alternatyw (Duffel, Kayak)
3. **Booking.com** wymaga partner approval — ciężko dla POV
4. **Open-Meteo** + **ExchangeRate-API** — darmowe, idealne do wzbogacenia POV
5. **MCP w travel** to wczesny etap — warto zbudować własny
