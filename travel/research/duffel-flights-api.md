# Duffel API — Flights Search & Booking (Lipiec 2026)

## Overview

Duffel to **jedyne dostępne bez partner approval** API do wyszukiwania i rezerwacji lotów.
- Self-service: rejestracja w 1 minutę, test access token od razu
- Python SDK: `pip install duffel-api`
- 300+ linii lotniczych
- Pay-as-you-go (prowizja od bookingów)

## Flow

```
1. Offer Request → wyszukaj loty (origin, destination, date, passengers)
2. Offer → wybierz konkretną ofertę
3. Order → zarezerwuj (pasażerowie, płatność)
4. Order → zarządzaj (zmiana, anulowanie)
```

## Przykład (Python)

```python
from duffel_api import Duffel

client = Duffel(access_token="duffel_test_...")

# 1. Search
offer_request = client.offer_requests.create(
    slices=[
        {"origin": "GDN", "destination": "WAW", "departure_date": "2026-08-01"},
    ],
    passengers=[{"type": "adult"}, {"type": "adult"}],
    cabin_class="economy",
)

# 2. Get offers
offers = client.offers.list(offer_request_id=offer_request.id)
for offer in offers[:3]:
    print(f"{offer.id}: {offer.total_amount} {offer.total_currency}")

# 3. Book
order = client.orders.create(
    selected_offers=[offers[0].id],
    passengers=[
        {"type": "adult", "title": "mr", "given_name": "Filip", "family_name": "Kazmierczak", "born_on": "1990-01-01", "gender": "m"},
    ],
)
```

## Integracja z Hermesem

```bash
pip install duffel-api
export DUFFEL_ACCESS_TOKEN="duffel_test_..."

# Dodaj jako custom tool
# Plugin: ~/.hermes/plugins/duffel_flights/plugin.py
```

## Ograniczenia

- Wymaga test access token (darmowy, ale rate-limited)
- Produkcja wymaga weryfikacji konta
- Prowizja od bookingów (nie od search)
- Nie wszystkie linie lotnicze dostępne
