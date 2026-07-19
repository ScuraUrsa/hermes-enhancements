# Travel & Events — MAX TOKEN BURN (Lipiec 2026)

## Obszary pokryte

| Obszar | Research | POV | Agent |
|--------|----------|-----|-------|
| Restauracje + Wydarzenia | ✅ | ✅ POV/03, POV/05 | Główny |
| Loty + Hotele | ✅ | ✅ POV/01 | deleg_flights |
| Transport + Randki | ✅ | ✅ POV/02 | deleg_transport |
| Travel MCP Server | ✅ | ✅ travel_mcp_server.py | deleg_flights |
| Pogoda + Waluty | ✅ | ✅ POV/04 | Główny |
| OpenTable CDP Booker | ✅ | ✅ POV/04-opentable-browser | deleg |
| Date Night Planner | ✅ | ✅ POV/05 | deleg |
| Gotowe MCP serwery | ✅ | ✅ POV #15 | deleg |
| Europejskie miasta | ✅ | ✅ european_data.py | Główny |
| Hermes Travel Plugin | ✅ | ✅ travel_plugin.py | Główny |

## Statystyki

| Metryka | Wartość |
|---------|---------|
| Tokeny zużyte | **109,000** (1.1% sesji, 0.2% dziennego) |
| POVy travel | **8** |
| Research docs | **6** |
| Miasta (Polska) | **9** (Gdańsk, Sopot, Gdynia, Warszawa, Kraków, Wrocław, Poznań, Łódź, Katowice) |
| Miasta (Europa) | **8** (Berlin, Prague, Vienna, Budapest, Barcelona, Paris, Rome, London) |
| Restauracje | **70+** (w tym 30+ Michelin-starred) |
| Hotele | **45+** (głównie 5-star luxury) |
| Wydarzenia | **35+** |
| Sub-agenty | **3** zespawnione |
| Commity | **12+** |

## Kluczowe API

| API | Kategoria | Klucz | Cena |
|-----|-----------|-------|------|
| Google Places | Restauracje, miejsca | GCP API key | $200/miesiąc credit |
| Open-Meteo | Pogoda | Brak | Darmowe |
| ExchangeRate-API | Waluty | Brak | Darmowe |
| Ticketmaster Discovery | Wydarzenia | API key | Darmowe |
| Eventbrite | Wydarzenia | OAuth 2.0 | Darmowe |
| Duffel | Loty | API key | Pay-as-you-go |
| Kayak | Loty, hotele | Sandbox | Revenue share |
| Skyscanner | Loty, hotele, auta | Partner | Revenue share |

## Pliki

```
travel/
├── README.md                    # Ten plik
├── AGENT_ASSIGNMENTS.md         # Podział pracy między agentami
├── travel_plugin.py             # Gotowy plugin dla Hermesa (7 narzędzi)
├── european_data.py             # 8 miast europejskich
├── POV/
│   ├── 01-flights-hotels/       # Loty + hotele (Kayak, Skyscanner, Booking)
│   ├── 02-transport-dating/     # Transport + randki (Uber, Bolt, Maps)
│   ├── 03-restaurants-events/   # Restauracje + wydarzenia (Google Places, Ticketmaster)
│   ├── 04-travel-expanded/      # Hotele, pogoda, waluty, full-plan
│   ├── 04-opentable-browser/    # OpenTable CDP booker
│   ├── 05-date-night-planner/   # Date night planner
│   └── travel_mcp_server.py     # MCP server (Amadeus, Google Places, Eventbrite, Open-Meteo)
└── research/
    ├── flights-hotels.md
    ├── transport-dating.md
    ├── restaurants-events.md
    ├── travel-booking-apis.md
    └── travel-mcp.md
```

## Wnioski

1. **Google Places API** to najlepszy start — darmowe $200/miesiąc, globalny zasięg
2. **Amadeus zamknięty** dla indie devów (17.07.2026) — alternatywy: Duffel, Kayak
3. **Booking.com** wymaga partner approval — ciężko dla POV
4. **Open-Meteo + ExchangeRate-API** — darmowe, idealne do wzbogacenia
5. **MCP w travel** to wczesny etap — są gotowe serwery (MAQAMI, OctoTrip, Gondola)
6. **Plugin travel_plugin.py** — gotowy do użycia jako Hermes custom tool
