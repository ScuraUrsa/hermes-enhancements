# Transport lokalny + Mapy + Randki — Research (Lipiec 2026)

## Platformy transportowe

| Platforma | Zasięg | API | Typ API | Klucz | Cena |
|-----------|--------|-----|---------|-------|------|
| **Uber** | Globalny (70+ krajów) | ✅ | REST v1.2, OAuth 2.0 | Client ID + Secret | Darmowe (rate-limited) |
| **Bolt** | Europa + Afryka (45+ krajów) | ❌ | Brak publicznego API | — | — |
| **FreeNow** | Europa | ✅ | REST (partner) | API key | Partner-only |
| **Lyft** | USA, Kanada | ✅ | REST, OAuth 2.0 | Client ID + Secret | Darmowe |

## Platformy mapowe i transportu publicznego

| Platforma | Zasięg | API | Typ | Klucz | Cena |
|-----------|--------|-----|-----|-------|------|
| **Google Maps Platform** | Globalny | ✅ | Routes API, Places API, Distance Matrix | GCP API key | $200/miesiąc credit, potem pay-as-you-go |
| **jakdojade** | Polska (główne miasta) | ⚠️ | API niepubliczne, reverse-engineered | — | Darmowe (nieoficjalne) |
| **OpenStreetMap** | Globalny | ✅ | Overpass API, Nominatim | Brak | Darmowe |
| **Mapbox** | Globalny | ✅ | Directions, Matrix, Geocoding | API key | Darmowe 100k req/miesiąc |

## Platformy miejsc i recenzji

| Platforma | Zasięg | API | Typ | Klucz | Cena |
|-----------|--------|-----|-----|-------|------|
| **TripAdvisor Content API** | Globalny (8M+ lokacji) | ✅ | REST | API key | Płatny (trial: 10k/dzień) |
| **Yelp Places API** | USA + wybrane kraje | ✅ | REST v3 (Fusion) | API key | Trial: 5k/30 dni, potem od $7.99/1k calls |
| **Google Places API (New)** | Globalny | ✅ | Nearby Search, Text Search, Place Details | GCP API key | $200/miesiąc credit, potem $17-32/1k |

---

## Kluczowe API — szczegóły

### 1. Uber Riders API (v1.2)

**Base URL**: `https://api.uber.com/v1.2`

**Autentykacja**: OAuth 2.0 (Bearer token) lub Server Token (deprecated)

**Kluczowe endpointy**:

| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/products?latitude=X&longitude=Y` | Lista dostępnych produktów (uberX, Black, itp.) |
| GET | `/estimates/price?start_latitude=X&start_longitude=Y&end_latitude=A&end_longitude=B` | Szacunkowa cena przejazdu |
| GET | `/estimates/time?start_latitude=X&start_longitude=Y` | Szacunkowy czas przyjazdu |
| POST | `/requests/estimate` | Dokładniejsza wycena (wymaga product_id) |
| POST | `/requests` | Zamówienie przejazdu (wymaga privileged scope) |
| GET | `/requests/{request_id}` | Status przejazdu |
| DELETE | `/requests/{request_id}` | Anulowanie przejazdu |
| GET | `/requests/{request_id}/map` | Link do mapy śledzenia |

**Rate limiting**: 500 req / 5 sekund na aplikację

**Scopes**:
- `profile` — dane użytkownika
- `history` — historia przejazdów
- `request` — zamawianie przejazdów (privileged, wymaga approval)
- `places` — zapisane miejsca

**Uwagi**:
- Server Token już nie jest wydawany — tylko OAuth 2.0
- Ride Request wymaga whitelistingu aplikacji
- Sandbox dostępny: `https://sandbox-api.uber.com/v1.2`
- **Dla Hermesa**: Estimates (cena + czas) są najbardziej dostępne bez approval

### 2. Bolt — BRAK publicznego API

**Status**: Bolt oficjalnie nie oferuje publicznego API (stan na lipiec 2026).

**Alternatywy**:
- `bolt-driver-api-sdk` (GitHub: syrex1013) — reverse-engineered SDK dla kierowców
- Web scraping (niezalecane, łamie ToS)
- **Rekomendacja**: Użyj Uber API jako głównego + FreeNow jako fallback dla Europy

### 3. Google Maps Platform (2025+)

**⚠️ WAŻNE**: Od marca 2025 Google zmieniło cennik i API. Directions API i Distance Matrix API przeszły na status Legacy. Nowe API to **Routes API**.

#### Routes API (nowe)

| Endpoint | Opis | Cena (per 1k) |
|----------|------|---------------|
| `POST routes.googleapis.com/directions/v2:computeRoutes` | Trasa między punktami | Basic $5, Advanced $10, Preferred $15 |
| `POST routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix` | Macierz odległości | Basic $5, Advanced $10, Preferred $15 |

**Kluczowe zmiany vs Legacy**:
- POST zamiast GET (parametry w body)
- `travelMode` zamiast `mode`
- `computeAlternativeRoutes` zamiast `alternatives`
- `languageCode` zamiast `language`
- Dodano `TWO_WHEELER` jako travel mode

#### Places API (New)

| SKU | Opis | Cena (per 1k) |
|-----|------|---------------|
| Nearby Search | Miejsca w promieniu | $25.60 (Pro), $19.20 (Advanced), $9.60 (Enterprise) |
| Text Search (ID Only) | Wyszukiwanie tekstowe | $0.38 |
| Place Details | Szczegóły miejsca | $25.60 (Pro) |
| Autocomplete | Podpowiedzi | $2.83 / sesja |

**$200/miesiąc darmowego creditu** (nowi użytkownicy dostają $300 trial)

**Place Types istotne dla randek**:
- `restaurant`, `cafe`, `bar`, `night_club`
- `park`, `movie_theater`, `art_gallery`, `museum`
- `bowling_alley`, `amusement_park`, `aquarium`

### 4. jakdojade (Polska)

**Status**: Brak oficjalnego publicznego API.

**Alternatywy**:
- `konhi/poland-public-transport-api` (GitHub) — community-maintained REST API dla Polski
- ZTM Gdańsk API: `ckan.multimediagdansk.pl` — otwarte dane GTFS
- **Rekomendacja**: Dla Trójmiasta użyj ZTM Gdańsk open data + GTFS

**ZTM Gdańsk Open Data**:
- URL: `https://ckan.multimediagdansk.pl`
- Format: GTFS (General Transit Feed Specification)
- Dostępne: rozkłady jazdy, przystanki, trasy
- Darmowe, otwarte dane

### 5. TripAdvisor Content API

**Base URL**: `https://api.content.tripadvisor.com/api/v1`

**⚠️ UWAGA**: TripAdvisor migruje do nowej platformy **Terra API** (`https://docs.terra.tripadvisor.com`)

**Endpointy (Content API)**:

| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/location/{id}/details` | Szczegóły lokacji (nazwa, adres, rating, URL) |
| GET | `/location/{id}/photos` | Zdjęcia lokacji |
| GET | `/location/{id}/reviews` | Recenzje (do 5) |
| GET | `/location/search?searchQuery=X` | Wyszukiwanie lokacji |
| GET | `/location/nearby_search?lat=X&lng=Y` | Lokacje w pobliżu |

**Limity**:
- Trial: 10,000 zapytań/dzień, 50 req/sekundę
- Do 5 recenzji i 5 zdjęć na lokację
- Płatny: pay-per-use, miesięczny budżet

**Kategorie istotne dla randek**:
- `restaurants`, `attractions`, `hotels`
- Filtrowanie po ratingu, kuchni, cenie

### 6. Yelp Places API (Fusion v3)

**Base URL**: `https://api.yelp.com/v3`

**Autentykacja**: API Key (Bearer token w headerze)

**Kluczowe endpointy**:

| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/businesses/search?term=X&location=Y&categories=Z` | Wyszukiwanie firm |
| GET | `/businesses/{id}` | Szczegóły firmy |
| GET | `/businesses/{id}/reviews` | Recenzje (do 3 excerptów) |
| GET | `/businesses/search/phone?phone=X` | Wyszukiwanie po telefonie |
| GET | `/events?location=X` | Wydarzenia |
| GET | `/autocomplete?text=X` | Autouzupełnianie |
| GET | `/categories` | Lista kategorii |

**Pricing (2025+)**:
- Trial: 5,000 API calls / 30 dni (NIE do produkcji)
- Starter: $7.99 / 1,000 calls
- Plus: $9.99 / 1,000 calls
- Enterprise: $14.99 / 1,000 calls
- Podstawowy plan: 30,000 calls/miesiąc, daily limit 5,000

**Kategorie Yelp dla randek**:
- `restaurants` (podkategorie: `french`, `italian`, `japanese`, `wine_bars`, `cocktailbars`)
- `nightlife`, `bars`, `coffee`
- `arts`, `museums`, `parks`
- `active` (bowling, mini_golf, hiking)

**Rate limiting**: 5,000 calls/dzień (paid), reset o północy UTC

---

## Rekomendacje dla Hermesa

### POV #1: Google Maps Routes + Places — Date Night Planner
- **Routes API**: trasa dojazdu na randkę (samochód, transport publiczny, rower)
- **Places API**: wyszukiwanie restauracji, barów, kawiarni w okolicy
- **Distance Matrix**: porównanie czasów dojazdu do różnych miejsc
- **Impact: 10/10, Effort: 4/10** (wymaga GCP API key, $200/miesiąc credit)

### POV #2: Uber — Transport na randkę
- Szacowanie ceny i czasu przejazdu Uberem
- Porównanie uberX vs Black vs Comfort
- Link do zamówienia w aplikacji Uber
- **Impact: 8/10, Effort: 3/10** (wymaga Uber Developer account)

### POV #3: Yelp + TripAdvisor — Date Venue Discovery
- Wyszukiwanie romantycznych restauracji i barów
- Filtrowanie po ratingu, cenie, kategorii
- Recenzje i zdjęcia
- **Impact: 9/10, Effort: 4/10** (Yelp trial: 5k calls, TripAdvisor: 10k/dzień)

### POV #4: ZTM Gdańsk + OSM — Transport publiczny na randkę
- Rozkłady jazdy autobusów i tramwajów w Trójmieście
- Trasy piesze i rowerowe (OSM)
- **Impact: 7/10 (tylko Trójmiasto), Effort: 5/10**

---

## Macierz decyzyjna

| API | Dostępność | Cena | Zasięg | Ocena dla Hermesa |
|-----|-----------|------|--------|-------------------|
| Google Maps Platform | ⭐⭐⭐⭐⭐ | $200 credit | Globalny | **10/10** — must-have |
| Uber API | ⭐⭐⭐⭐ | Darmowe | 70+ krajów | **8/10** — świetne do transportu |
| Yelp Places | ⭐⭐⭐ | Od $7.99/1k | USA+ | **7/10** — drogie, ale dobre dane |
| TripAdvisor | ⭐⭐⭐⭐ | Trial 10k/dzień | Globalny | **8/10** — dobre do miejsc |
| Bolt | ⭐ | Brak API | Europa | **2/10** — brak API |
| jakdojade | ⭐⭐ | Darmowe (nieoficjalne) | Polska | **5/10** — tylko Polska |
| ZTM Gdańsk | ⭐⭐⭐⭐ | Darmowe | Trójmiasto | **6/10** — lokalne, ale otwarte |

---

## Plan działania

1. **POV #1 (priorytet)**: Google Maps Platform — Date Night Router
   - Routes API: trasa + czas dojazdu
   - Places API: wyszukiwanie miejsc
   - Distance Matrix: porównanie opcji

2. **POV #2**: Uber + TripAdvisor — Full Date Stack
   - Uber: szacowanie ceny przejazdu
   - TripAdvisor: wyszukiwanie romantycznych miejsc

3. **POV #3**: Yelp + ZTM — Local Date Discovery
   - Yelp: recenzje i kategorie
   - ZTM: transport publiczny w Trójmieście

---

**Ostatnia aktualizacja**: 2026-07-19 20:15 CEST
**Autor**: deleg_sub_02 (Transport lokalny + Mapy + Randki)
