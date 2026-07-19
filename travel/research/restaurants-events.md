# Restauracje + Rezerwacje + Wydarzenia — Research (Lipiec 2026)

## Platformy restauracyjne

| Platforma | Zasięg | API | Typ API | Klucz |
|-----------|--------|-----|---------|-------|
| **OpenTable** | Globalny | ✅ | Partner (B2B) + Consumer | Application required |
| **TheFork** | Europa (60k+) | ✅ | B2B REST | API key (partner) |
| **Resy** | USA, global | ✅ (2026) | Gen AI API | AmEx ecosystem |
| **Tock** | USA, premium | ✅ | REST + webhooks | Łączy się z Resy |
| **Google Places** | Globalny | ✅ | Nearby Search, Place Details | GCP API key |
| **TripAdvisor** | Globalny | ✅ | Content + Booking | API key |

## Platformy eventowe

| Platforma | Zasięg | API | Typ | Klucz |
|-----------|--------|-----|-----|-------|
| **Eventbrite** | Globalny | ✅ | OAuth 2.0 REST | API key + OAuth |
| **Ticketmaster** | Globalny (230k+) | ✅ | Discovery + Partner | API key |
| **Meetup** | Globalny | ✅ | REST | OAuth |
| **Facebook Events** | Globalny | ✅ | Graph API | App token |

## Kluczowe API — szczegóły

### Google Places API (najbardziej dostępne)
- **Nearby Search**: restauracje, bary, kawiarnie w promieniu
- **Place Details**: godziny otwarcia, rating, zdjęcia, recenzje, telefon, strona www
- **Text Search**: wyszukiwanie po nazwie, kuchni, atmosferze
- **Cena**: $17/1000 zapytań (Nearby), $25/1000 (Place Details)
- **Klucz**: GCP API key (darmowe $200/miesiąc credit)

### OpenTable
- **Consumer API**: dostępność stolików, rezerwacja
- **Partner API**: pełna integracja (wymaga application)
- **Ograniczenie**: wymaga partner approval

### TheFork (Europa)
- **B2B API**: `POST /v1/restaurants/{id}/reservations` — tworzenie rezerwacji
- **TripAdvisor integracja**: booking link przez TripAdvisor API
- **Zasięg**: Europa + Ameryka Łacińska + Australia

### Eventbrite
- **OAuth 2.0**: tworzenie eventów, zarządzanie biletami
- **Search API**: wyszukiwanie eventów po lokalizacji, kategorii, dacie
- **Webhooki**: powiadomienia o rezerwacjach

### Ticketmaster Discovery API
- **230k+ eventów**: koncerty, sport, teatr, family
- **Search**: po lokalizacji, dacie, gatunku, artyście
- **Pricing**: informacje o cenach biletów
- **Klucz**: darmowy API key (rate-limited)

## Rekomendacje dla Hermesa

### POV #1: Google Places — Restaurant Finder
- Wyszukiwanie restauracji w Gdańsku i okolicy
- Filtrowanie po: kuchni, cenie, ratingu, odległości
- Place Details: godziny otwarcia, telefon, strona
- **Impact: 9/10, Effort: 3/10** (wymaga GCP API key)

### POV #2: Eventbrite + Ticketmaster — Event Discovery
- Wyszukiwanie wydarzeń w Trójmieście
- Filtrowanie po dacie, kategorii, cenie
- Linki do biletów
- **Impact: 8/10, Effort: 4/10**

### POV #3: TheFork — Rezerwacja stolików
- Wyszukiwanie restauracji z dostępnymi stolikami
- Tworzenie rezerwacji przez API
- **Impact: 9/10, Effort: 6/10** (wymaga partner API)
