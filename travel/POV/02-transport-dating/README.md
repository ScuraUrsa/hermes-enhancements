# POV #02: Transport lokalny + Mapy + Randki

**Date Night Planner** — integracja Google Maps, Uber, TripAdvisor i Yelp do planowania idealnej randki.

## 🎯 Cel

Stworzyć narzędzie, które dla zadanego adresu startowego i docelowego:
1. Oblicza trasę i czas dojazdu (Google Maps Routes API)
2. Znajduje romantyczne miejsca w pobliżu celu (Google Maps Places API)
3. Szacuje koszt przejazdu Uberem (Uber API)
4. Pobiera recenzje i zdjęcia miejsc (TripAdvisor Content API)
5. Wyszukuje lokale po kategorii i ratingu (Yelp Fusion API)

## 📦 Wymagania

- Python 3.9+
- Klucze API (patrz niżej)

## 🔑 Konfiguracja API

### Google Maps Platform
1. Wejdź na [Google Cloud Console](https://console.cloud.google.com/)
2. Utwórz projekt i włącz:
   - **Routes API** (`routes.googleapis.com`)
   - **Places API (New)** (`places.googleapis.com`)
   - **Geocoding API** (`maps.googleapis.com`)
3. Wygeneruj API key
4. Nowi użytkownicy dostają **$300 trial credit** (90 dni)
5. Potem **$200/miesiąc darmowego creditu**

```bash
export GOOGLE_MAPS_API_KEY="AIza..."
```

### Uber Developer
1. Wejdź na [Uber Developer Dashboard](https://developer.uber.com/dashboard/)
2. Utwórz aplikację (Rides API)
3. Skopiuj `Client ID` i `Client Secret`
4. Estimates (cena/czas) działają bez approval

```bash
export UBER_CLIENT_ID="..."
export UBER_CLIENT_SECRET="..."
```

### TripAdvisor Content API
1. Wejdź na [TripAdvisor Developer Portal](https://developer-tripadvisor.com/)
2. Zarejestruj się do Content API
3. Trial: **10,000 zapytań/dzień**, 50 req/sek

```bash
export TRIPADVISOR_API_KEY="..."
```

### Yelp Fusion API
1. Wejdź na [Yelp Developers](https://www.yelp.com/developers)
2. Utwórz aplikację
3. Trial: **5,000 zapytań / 30 dni**

```bash
export YELP_API_KEY="..."
```

## 🚀 Użycie

```bash
# Podstawowe — domyślne ustawienia (Gdańsk Wrzeszcz → Śródmieście)
python3 demo.py

# Z własnymi adresami
python3 demo.py --origin "Gdańsk Oliwa" --destination "Sopot Centrum"

# Romantyczna randka z wyższym budżetem
python3 demo.py --vibe romantic --budget 3 --mode DRIVE

# Aktywna randka — rowerem
python3 demo.py --vibe adventurous --mode BICYCLE

# Wynik jako JSON (do pipeline'ów)
python3 demo.py --json
```

## 📊 Przykładowy output

```
======================================================================
  💘 DATE NIGHT PLANNER — Twój plan randki
======================================================================

📍 Z: Gdańsk Wrzeszcz
📍 Do: Gdańsk Śródmieście
💰 Budżet: $$
🚗 Transport: DRIVE
💫 Nastrój: romantic

🗺️  TRASA
   Dystans: 5.2 km
   Czas: 12 min
   Opis: Aleja Grunwaldzka → Podwale Grodzkie

🚗 UBER — Szacunkowe ceny
   uberX: 18-24 PLN | ~8 min
   Uber Black: 35-45 PLN | ~8 min

🍽️  GOOGLE PLACES — Miejsca w pobliżu
   1. Restauracja Gdańska  ⭐⭐⭐⭐  $$
   2. Kawiarnia Drukarnia  ⭐⭐⭐⭐  $
   3. Bar Pod Łososiem  ⭐⭐⭐⭐  $$$

⭐ TRIPADVISOR — Polecane miejsca
   1. Restauracja Gdańska  ⭐4.5  (234 recenzji)
   2. Kawiarnia Drukarnia  ⭐4.3  (89 recenzji)

🌟 YELP — Najlepiej oceniane
   1. Restauracja Gdańska  ⭐⭐⭐⭐  [French, Wine Bars]  $$
======================================================================
```

## 🏗️ Architektura

```
demo.py
├── Config — zarządzanie kluczami API
├── GoogleMapsClient
│   ├── geocode() — adres → współrzędne
│   ├── compute_route() — trasa (Routes API, POST)
│   ├── nearby_places() — miejsca w promieniu (Places API New)
│   └── place_details() — szczegóły miejsca
├── UberClient
│   ├── get_products() — dostępne produkty
│   ├── price_estimate() — szacunkowa cena
│   └── time_estimate() — szacunkowy czas
├── TripAdvisorClient
│   ├── search_locations() — wyszukiwanie
│   ├── location_details() — szczegóły
│   └── location_reviews() — recenzje
├── YelpClient
│   ├── search_businesses() — wyszukiwanie firm
│   ├── business_details() — szczegóły
│   └── business_reviews() — recenzje
└── DateNightPlanner — orkiestracja wszystkich API
```

## 🎨 Warianty nastroju (vibe)

| Nastrój | Place Types | Yelp Categories | Opis |
|---------|-------------|-----------------|------|
| `romantic` | restaurant, cafe, bar, park, art_gallery | french, italian, wine_bars, cocktailbars | Romantyczna kolacja |
| `casual` | restaurant, cafe, bar, movie_theater, bowling_alley | restaurants, coffee, desserts | Luźne spotkanie |
| `fancy` | restaurant, bar, night_club, art_gallery, museum | restaurants, cocktailbars, japanese | Elegancka randka |
| `adventurous` | park, amusement_park, hiking_area, restaurant, cafe | restaurants, parks, active | Aktywna przygoda |

## 💰 Koszty API (szacunkowe)

| API | Darmowy limit | Koszt po przekroczeniu |
|-----|--------------|----------------------|
| Google Maps | $200/miesiąc credit | $5-25/1k zapytań |
| Uber | Darmowe (rate-limited) | — |
| TripAdvisor | 10k/dzień trial | Płatny (kontakt) |
| Yelp | 5k/30 dni trial | $7.99-14.99/1k zapytań |

## 🔮 Co dalej?

1. **Integracja z ZTM Gdańsk** — transport publiczny w Trójmieście
2. **OpenStreetMap fallback** — gdy Google Maps niedostępne
3. **Cache wyników** — Redis/memcached dla często wyszukiwanych tras
4. **Rekomendacje ML** — uczenie na podstawie historii randek
5. **Powiadomienia** — przypomnienia o rezerwacji, czas wyjścia

## 📁 Powiązane pliki

- `travel/research/transport-dating.md` — pełny research API
- `travel/AGENT_ASSIGNMENTS.md` — podział pracy między agentami
- `POV/04-token-monitor/ollama_token_monitor.py` — monitor zużycia tokenów

---

**Autor**: deleg_sub_02 (Transport lokalny + Mapy + Randki)
**Data**: 2026-07-19
**Model**: deepseek-v4-pro
