# POV #01: Flights & Hotels API Integration

## Cel
Zbadać i zintegrować API do wyszukiwania lotów i hoteli: Kayak, Skyscanner, Booking.com, Duffel, Amadeus.

## Status
- ✅ Research zakończony → `travel/research/flights-hotels.md`
- ✅ Demo.py gotowe (symulacje + realne API)
- ⚠️ Amadeus Self-Service ZAMKNIĘTY (17.07.2026)
- ⚠️ Google Flights — brak API
- ⚠️ Airbnb — brak publicznego search API

## Szybki start

```bash
# 1. Zainstaluj zależności
pip install requests python-dotenv

# 2. Status wszystkich API
cd ~/workspace/hermes-enhancements/travel/POV/01-flights-hotels
python3 demo.py

# 3. Test Kayak Sandbox (symulacja)
python3 demo.py --kayak-flights WAW LON
python3 demo.py --kayak-hotels Paris

# 4. Test Duffel (real API — self-service!)
export DUFFEL_API_KEY="duffel_test_..."
python3 demo.py --duffel WAW LON

# 5. Porównanie wszystkich API
python3 demo.py --compare WAW LON
```

## Architektura API

```
┌─────────────────────────────────────────────────────────┐
│                   Travel API Layer                       │
├──────────────┬──────────────┬──────────────┬────────────┤
│   Kayak 🟡   │ Skyscanner 🟠│ Booking 🔴   │ Duffel 🟢  │
│   Sandbox    │   Partner    │  Affiliate   │ Self-svc   │
├──────────────┼──────────────┼──────────────┼────────────┤
│ Flights ✓    │ Flights ✓    │ Hotels ✓     │ Flights ✓  │
│ Hotels ✓     │ Hotels ✓     │ Cars ✓       │            │
│ Cars ✓       │ Cars ✓       │ Attractions ✓│            │
│              │              │ Flights ⏳    │            │
├──────────────┼──────────────┼──────────────┼────────────┤
│ Auth: API Key│ Auth: API Key│ Auth: OAuth  │ Auth: Bearer│
│ Sandbox: Free│ Partner App  │ Managed Aff. │ Instant Key │
└──────────────┴──────────────┴──────────────┴────────────┘
```

## Porównanie API

| Cecha | Kayak | Skyscanner | Booking.com | Duffel | Amadeus |
|-------|-------|-----------|-------------|--------|---------|
| **Loty** | ✅ Search + Insights | ✅ Live + Indicative | ⏳ Coming | ✅ Search | ✅ (Enterprise) |
| **Hotele** | ✅ Search + Static | ✅ Live + Content | ✅ Core | ❌ | ❌ |
| **Self-service** | ✅ (sandbox) | ❌ (partner) | ❌ (affiliate) | ✅ | ❌ (enterprise) |
| **Darmowy tier** | ✅ (sandbox) | ❌ | ❌ | ✅ (test) | ❌ |
| **Dokumentacja** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Cena** | Revenue share | Revenue share | 25-40% comm. | Pay-as-you-go | Enterprise |

## Kluczowe wnioski

### ✅ Działa (można realnie testować)
1. **Duffel** — self-service, REST API, 300+ linii lotniczych. Rejestracja na duffel.com, API key instant.
2. **Kayak Sandbox** — darmowy sandbox, Flights + Hotels + Cars. Wymaga formularza kontaktowego.

### ⚠️ Wymaga partnerstwa
3. **Skyscanner** — najlepszy all-in-one (loty + hotele + auta), ale wymaga zatwierdzonej aplikacji partnerskiej.
4. **Booking.com** — największy katalog hoteli (28M+), ale wymaga bycia Managed Affiliate Partner.

### ❌ Niedostępne
5. **Amadeus** — self-service portal ZAMKNIĘTY 17.07.2026. Tylko Enterprise.
6. **Google Flights** — QPX Express zamknięty w 2018. Brak publicznego API.
7. **Airbnb** — oficjalne API tylko dla hostów. Search tylko przez third-party scrapery.

## Rekomendowana ścieżka integracji

```
Faza 1 (teraz):     Duffel (loty) + Kayak Sandbox (hotele)
                    ↓
Faza 2 (docelowo):  Skyscanner (loty + hotele, all-in-one)
                    ↓
Faza 3 (full):      Booking.com (hotele, pełny katalog)
```

## Pliki

| Plik | Opis |
|------|------|
| `demo.py` | Główny skrypt demonstracyjny |
| `README.md` | Ten plik |
| `../../research/flights-hotels.md` | Pełny research API |

## Pitfalls

- **Amadeus Self-Service ZAMKNIĘTY** — nie próbuj się rejestrować
- **Google Flights** — brak API, scraping łamie ToS
- **Airbnb** — tylko host API, search API nie istnieje
- **Skyscanner** — wymaga zatwierdzonej aplikacji (nie instant)
- **Booking.com** — tylko Managed Affiliate Partner
- **Kayak** — sandbox darmowy, ale production wymaga umowy
