# Travel & Events — Research: Restauracje, Rezerwacje, Wydarzenia

## Google Places API (New)

**Status**: ✅ Publiczny, darmowy tier $200/miesiąc kredytu
**Klucz**: Wymaga GCP API key (mamy projekty GCP: f.j.kazmierczak, koalamis6, praktyki.ftims)

### Endpointy

| Endpoint | Opis | Przykład |
|----------|------|----------|
| **Nearby Search (New)** | Szukaj miejsc w promieniu | `POST /v1/places:searchNearby` — restauracje w promieniu 1km |
| **Text Search (New)** | Szukaj po zapytaniu tekstowym | `POST /v1/places:searchText` — "najlepsza włoska restauracja Gdańsk" |
| **Place Details (New)** | Szczegóły miejsca | `GET /v1/places/{place_id}` — adres, telefon, godziny, recenzje, zdjęcia |
| **Place Photos (New)** | Zdjęcia miejsca | `GET /v1/{photo_name}/media` — max 4800x4800px |
| **Autocomplete (New)** | Podpowiedzi podczas pisania | `POST /v1/places:autocomplete` |

### Kluczowe parametry

- `includedTypes`: `["restaurant", "cafe", "bar", "night_club", "tourist_attraction", "park", "museum"]`
- `locationRestriction`: `{circle: {center: {lat, lng}, radius: 5000}}`
- `rankPreference`: `DISTANCE` lub `POPULARITY`
- `languageCode`: `"pl"` dla polskich wyników
- `maxResultCount`: 1-20

### AI-powered summaries (NOWOŚĆ 2026!)
Google Places API (New) zwraca AI-generowane podsumowania miejsc — agregacja recenzji, opis atmosfery, popularne dania.

### Cennik (New API)
- Nearby Search: $0.04/request (podstawowe pola), $0.06 (zaawansowane)
- Text Search: $0.05/request
- Place Details: $0.03-0.05/request
- Photos: $0.01/request
- **$200 darmowego kredytu miesięcznie** = ~4000-6000 requestów

---

## Eventbrite API

**Status**: ✅ Publiczny, darmowy klucz API
**URL**: https://www.eventbrite.com/platform/api
**Auth**: OAuth2 lub Private API key

### Endpointy

| Endpoint | Opis |
|----------|------|
| `GET /v3/events/search/` | Szukaj wydarzeń po lokalizacji, kategorii, dacie |
| `GET /v3/events/{id}/` | Szczegóły wydarzenia |
| `GET /v3/venues/{id}/` | Szczegóły miejsca |
| `GET /v3/categories/` | Lista kategorii |

### Przykład: Szukaj wydarzeń w Gdańsku
```
GET /v3/events/search/?location.address=Gdańsk&location.within=10km&categories=103
Authorization: Bearer {API_KEY}
```

### Kategorie
- 101: Business
- 102: Science & Tech
- 103: Music
- 104: Film & Media
- 105: Sports
- 106: Health
- 107: Food & Drink
- 108: Community
- 109: Arts
- 110: Fashion
- 113: Dating/Networking 👈

### Rate limits
- 1000 req/godzinę dla podstawowego tieru
- Darmowe

---

## Ticketmaster Discovery API

**Status**: ✅ Publiczny, darmowy klucz API
**URL**: https://developer.ticketmaster.com/
**Auth**: API key w query string `?apikey=`

### Endpointy

| Endpoint | Opis |
|----------|------|
| `GET /discovery/v2/events.json` | Szukaj wydarzeń |
| `GET /discovery/v2/events/{id}.json` | Szczegóły wydarzenia |
| `GET /discovery/v2/venues.json` | Szukaj miejsc |
| `GET /discovery/v2/attractions.json` | Szukaj artystów/atrakcji |
| `GET /discovery/v2/classifications.json` | Kategorie |

### Przykład: Koncerty w Polsce
```
GET /discovery/v2/events.json?countryCode=PL&classificationName=music&apikey={key}
```

### Rate limits
- 5000 req/dzień
- 5 req/sekundę
- Darmowe

---

## OpenTable

**Status**: ⚠️ Tylko API partnerskie (dla restauracji i integratorów B2B)
**Alternatywa**: Web scraping przez browser-use/Playwright

### Podejście scrapingowe
1. Otwórz `https://www.opentable.com/s?term={miasto}&dateTime={data}&covers={osoby}`
2. Sprawdź dostępne restauracje i sloty
3. Kliknij rezerwację → wypełnij formularz

### TheFork
Podobnie — brak publicznego API. Web scraping.

---

## Rekomendowane POV-y

### POV #1: Google Places API — Wyszukiwarka restauracji i atrakcji
- Hermes custom tool: `search_places(query, location, type)`
- Zwraca: nazwa, adres, ocena, cena, godziny otwarcia, zdjęcia, AI summary
- Wymaga: GCP API key (mamy projekty)

### POV #2: Eventbrite + Ticketmaster — Wyszukiwarka wydarzeń
- Hermes custom tool: `search_events(query, city, date_range, category)`
- Agreguje wyniki z obu API
- Zwraca: nazwa, data, miejsce, cena biletów, link

### POV #3: OpenTable Scraper — Rezerwacja stolików
- Browser automation przez Playwright/CDP
- Wyszukuje restauracje, sprawdza dostępność, rezerwuje
- Wymaga: działająca przeglądarka (mamy Chrome + CDP)
