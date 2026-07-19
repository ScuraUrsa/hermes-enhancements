# Travel & Booking — Research Notes

## MCP Servers (gotowe do użycia)

### 1. skarlekar/mcp_travelassistant ⭐52 — NAJLEPSZE
- **6 serwerów MCP**: Flight Search, Hotel Search, Event Search, Geocoder, Weather, Finance
- **Python 3.8+**, MIT license
- **API**: SerpAPI (flights/hotels), OpenWeatherMap, ExchangeRate-API
- **Działa z Claude Desktop** — można podłączyć do Hermesa przez MCP
- **Przykład**: Banff/Jasper trip — full itinerary z budżetem $5000
- **GitHub**: https://github.com/skarlekar/mcp_travelassistant
- **Ostatni commit**: czerwiec 2025 (nieaktywne, ale działa)

### 2. gs-ysingh/travel-mcp-server ⭐14
- **TypeScript/Node.js**, ISC license
- **5 narzędzi**: search_flights, search_accommodation, get_exchange_rate, get_weather_forecast, calculate_trip_budget
- **API**: Amadeus/Skyscanner, Booking.com/Airbnb, Fixer.io, OpenWeatherMap, Google Places
- **Mniej dojrzałe** — tylko 1 commit, szkielet projektu
- **GitHub**: https://github.com/gs-ysingh/travel-mcp-server

## Flight APIs

| API | Typ | Cena | Najlepsze do |
|-----|-----|------|-------------|
| **Amadeus** | GDS (pełne API) | Usage-based, 90% zniżki przy bookingach | Globalna agregacja, loty+hotele |
| **Kiwi.com Tequila** | Metasearch | Darmowe na start | Multi-city, elastyczne trasy |
| **Skyscanner** | Metasearch | Partner-based (kontrakt) | Metasearch UX, filtry |
| **Travelpayouts** | Affiliate | Commission-based | Monetyzacja, price trends |
| **SerpAPI** (Google Flights) | Scraping | ~$50/mies | Gdy nie ma oficjalnego API |

**Rekomendacja**: Amadeus (testowy klucz darmowy) + Kiwi.com jako backup.

## Hotel APIs

| API | Typ | Cena | Pokrycie |
|-----|-----|------|---------|
| **Booking.com** | Affiliate + Demand | Commission-based | 3M+ properties, 229 krajów |
| **Expedia Rapid** | Partner | Kontrakt | Duży ekosystem |
| **Amadeus Hotels** | GDS | Usage-based | Zintegrowane z lotami |

**Rekomendacja**: Booking.com Affiliate (najłatwiejszy start) lub Amadeus (jeśli już używamy do lotów).

## Restaurant APIs

| API | Typ | Cena |
|-----|-----|------|
| **OpenTable** | REST API | Darmowe (affiliate) |
| **TheFork** | B2B API | Partner-based |
| **Google Places** | REST API | $0.017-0.040/request, $200/mies free |

**Rekomendacja**: Google Places API (najszersze pokrycie, darmowy tier) + OpenTable (rezerwacje).

## Event APIs

| API | Typ | Cena |
|-----|-----|------|
| **Eventbrite** | OAuth 2.0 REST | Darmowy API key |
| **Ticketmaster Discovery** | REST API | Darmowe tier (5k req/dzień) |
| **Meetup** | GraphQL API | $ (po akwizycji ograniczony) |

**Rekomendacja**: Eventbrite (najłatwiejszy) + Ticketmaster (największa baza).

## Google Places API — kluczowe endpointy

- **Nearby Search**: restauracje, bary, atrakcje w promieniu
- **Place Details**: godziny otwarcia, recenzje, zdjęcia, ceny
- **Text Search**: "romantic restaurant Gdańsk"
- **Photos**: zdjęcia miejsc

**Cennik (2026)**: 
- Nearby Search: $0.032/request
- Place Details: $0.017/request  
- Photos: $0.007/request
- **$200/month free credit** = ~6000 Place Details requests

## Strategia integracji z Hermesem

### Opcja A: MCP Travel Assistant (najszybsza)
1. Sklonować `skarlekar/mcp_travelassistant`
2. Skonfigurować API keys (SerpAPI, OpenWeatherMap)
3. Dodać jako MCP server w Hermesie
4. Hermes automatycznie dostaje narzędzia: search_flights, search_hotels, search_events...

### Opcja B: Własny MCP server (najlepsza kontrola)
1. Napisać Python MCP server z narzędziami:
   - `search_flights(origin, destination, date)` → Amadeus/Kiwi
   - `search_hotels(location, checkin, checkout)` → Booking.com
   - `search_restaurants(location, cuisine, price)` → Google Places
   - `search_events(location, date, category)` → Eventbrite/Ticketmaster
   - `get_weather(location, date)` → OpenWeatherMap
   - `get_exchange_rate(from, to)` → darmowe API
2. Podłączyć jako MCP server w Hermesie

### Opcja C: Custom tools w Pythonie (najprostsza)
1. Napisać skrypty Python jako custom tools
2. Hermes wywołuje je przez terminal tool
3. Nie wymaga MCP — działa od razu

## Rekomendacja

**POV #1**: Sklonować `skarlekar/mcp_travelassistant` + podłączyć do Hermesa. Impact: 9/10, Effort: 3/10.

**POV #2**: Dodać Google Places API do wyszukiwania restauracji i miejsc na randki. Impact: 8/10, Effort: 2/10.

**POV #3**: Dodać Eventbrite API do wyszukiwania wydarzeń. Impact: 7/10, Effort: 2/10.
