# POV #14: OpenTable Scraper — Rezerwacja stolików

## Cel
Dać Hermesowi możliwość wyszukiwania restauracji z wolnymi stolikami i dokonywania rezerwacji przez OpenTable (web scraping, bo brak publicznego API).

## Status
✅ Research zakończony | ⬜ Implementacja | ⬜ Testy

## Dlaczego scraping?
OpenTable nie ma publicznego API konsumenckiego — tylko B2B partnerskie. TheFork podobnie.
Alternatywy:
- **Browser automation** (Playwright/CDP) — działa, ale wolne
- **Reverse-engineer API** — OpenTable używa GraphQL wewnętrznie, można podsłuchać
- **Google Reserve** — Google Maps ma integrację rezerwacyjną, ale przez partnerów

## Wymagania
- Chrome/Chromium z CDP (localhost:9222) — już działa na VM
- `pip install websocket-client` — już jest
- Alternatywnie: Playwright (`pip install playwright`)

## Implementacja

### 1. OpenTable Scraper przez CDP

```python
# ~/workspace/hermes-enhancements/POV/14-opentable-scraper/opentable_tool.py

import json
import time
import urllib.request
from websocket import create_connection
from typing import Optional

def get_cdp_ws():
    """Znajdź WebSocket do Chrome CDP."""
    req = urllib.request.Request("http://localhost:9222/json")
    with urllib.request.urlopen(req) as resp:
        pages = json.loads(resp.read())
    # Szukaj strony OpenTable lub otwórz nową
    for p in pages:
        if "opentable.com" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    # Jeśli nie ma, otwórz nową
    for p in pages:
        if "sw.js" not in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    raise Exception("No CDP page available")


def send_cdp(ws, method, params=None):
    msg = {"id": 1, "method": method}
    if params:
        msg["params"] = params
    ws.send(json.dumps(msg))
    time.sleep(0.3)
    return json.loads(ws.recv())


def search_opentable(
    city: str = "Gdansk",
    date: str = "2026-07-20",
    time_str: str = "19:00",
    party_size: int = 2,
) -> list[dict]:
    """
    Szukaj dostępnych restauracji na OpenTable.
    
    Args:
        city: Miasto (po angielsku)
        date: Data (YYYY-MM-DD)
        time_str: Godzina (HH:MM)
        party_size: Liczba osób
    
    Returns:
        Lista restauracji z dostępnymi slotami
    """
    ws_url = get_cdp_ws()
    ws = create_connection(ws_url, origin="http://localhost:9222")
    
    # Nawiguj do OpenTable
    url = f"https://www.opentable.com/s?term={city}&dateTime={date}T{time_str}&covers={party_size}"
    send_cdp(ws, "Page.navigate", {"url": url})
    time.sleep(5)
    
    # Poczekaj na załadowanie wyników
    for attempt in range(5):
        result = send_cdp(ws, "Runtime.evaluate", {
            "expression": """
            (function() {
                var results = document.querySelectorAll('[data-test=\"restaurant-card\"]');
                return results.length;
            })()
            """
        })
        count = result.get("result", {}).get("result", {}).get("value", 0)
        if count > 0:
            break
        time.sleep(2)
    
    # Wyciągnij dane restauracji
    result = send_cdp(ws, "Runtime.evaluate", {
        "expression": """
        (function() {
            var cards = document.querySelectorAll('[data-test=\"restaurant-card\"]');
            var results = [];
            cards.forEach(function(card) {
                var name = card.querySelector('[data-test=\"restaurant-name\"]');
                var rating = card.querySelector('[data-test=\"rating\"]');
                var price = card.querySelector('[data-test=\"price\"]');
                var cuisine = card.querySelector('[data-test=\"cuisine\"]');
                var times = card.querySelectorAll('[data-test=\"time-slot\"]');
                
                var slots = [];
                times.forEach(function(t) { slots.push(t.textContent.trim()); });
                
                results.push({
                    name: name ? name.textContent.trim() : '',
                    rating: rating ? rating.textContent.trim() : '',
                    price: price ? price.textContent.trim() : '',
                    cuisine: cuisine ? cuisine.textContent.trim() : '',
                    available_slots: slots
                });
            });
            return JSON.stringify(results);
        })()
        """
    })
    
    ws.close()
    
    try:
        return json.loads(result.get("result", {}).get("result", {}).get("value", "[]"))
    except:
        return []


def get_restaurant_details_opentable(restaurant_name: str, city: str = "Gdansk") -> dict:
    """
    Pobierz szczegóły restauracji z OpenTable.
    
    Args:
        restaurant_name: Nazwa restauracji
        city: Miasto
    
    Returns:
        Szczegóły (adres, opis, zdjęcia, menu, opinie)
    """
    ws_url = get_cdp_ws()
    ws = create_connection(ws_url, origin="http://localhost:9222")
    
    # Szukaj restauracji
    search_url = f"https://www.opentable.com/s?term={restaurant_name}+{city}"
    send_cdp(ws, "Page.navigate", {"url": search_url})
    time.sleep(4)
    
    # Kliknij pierwszy wynik
    send_cdp(ws, "Runtime.evaluate", {
        "expression": """
        (function() {
            var card = document.querySelector('[data-test=\"restaurant-card\"]');
            if (card) { card.click(); return 'clicked'; }
            return 'not found';
        })()
        """
    })
    time.sleep(3)
    
    # Wyciągnij szczegóły
    result = send_cdp(ws, "Runtime.evaluate", {
        "expression": """
        (function() {
            var details = {};
            
            var name = document.querySelector('h1');
            if (name) details.name = name.textContent.trim();
            
            var address = document.querySelector('[data-test=\"address\"]');
            if (address) details.address = address.textContent.trim();
            
            var phone = document.querySelector('[data-test=\"phone\"]');
            if (phone) details.phone = phone.textContent.trim();
            
            var description = document.querySelector('[data-test=\"description\"]');
            if (description) details.description = description.textContent.trim().substring(0, 500);
            
            var rating = document.querySelector('[data-test=\"rating-value\"]');
            if (rating) details.rating = rating.textContent.trim();
            
            var reviews_count = document.querySelector('[data-test=\"reviews-count\"]');
            if (reviews_count) details.reviews_count = reviews_count.textContent.trim();
            
            var price = document.querySelector('[data-test=\"price-range\"]');
            if (price) details.price = price.textContent.trim();
            
            var cuisine = document.querySelector('[data-test=\"cuisine-type\"]');
            if (cuisine) details.cuisine = cuisine.textContent.trim();
            
            return JSON.stringify(details);
        })()
        """
    })
    
    ws.close()
    
    try:
        return json.loads(result.get("result", {}).get("result", {}).get("value", "{}"))
    except:
        return {}


def make_reservation_opentable(
    restaurant_url: str,
    date: str,
    time_str: str,
    party_size: int,
    email: str,
    phone: str,
    first_name: str,
    last_name: str,
) -> dict:
    """
    Dokonaj rezerwacji na OpenTable.
    
    UWAGA: Ta funkcja wymaga interakcji z formularzem — może wymagać
    ręcznej interwencji dla CAPTCHA lub potwierdzenia.
    
    Args:
        restaurant_url: URL restauracji na OpenTable
        date: Data (YYYY-MM-DD)
        time_str: Godzina (HH:MM)
        party_size: Liczba osób
        email: Email do rezerwacji
        phone: Telefon
        first_name: Imię
        last_name: Nazwisko
    
    Returns:
        {"success": True/False, "confirmation": "..."}
    """
    ws_url = get_cdp_ws()
    ws = create_connection(ws_url, origin="http://localhost:9222")
    
    # Nawiguj do strony restauracji
    send_cdp(ws, "Page.navigate", {"url": restaurant_url})
    time.sleep(4)
    
    # Kliknij "Find a table" / "Rezerwuj"
    send_cdp(ws, "Runtime.evaluate", {
        "expression": """
        (function() {
            var btn = document.querySelector('[data-test=\"find-table-button\"]');
            if (btn) { btn.click(); return 'clicked'; }
            return 'not found';
        })()
        """
    })
    time.sleep(3)
    
    # Wybierz datę, godzinę, liczbę osób
    # (selektory zależą od aktualnego UI OpenTable — mogą wymagać aktualizacji)
    
    # Wypełnij formularz
    send_cdp(ws, "Runtime.evaluate", {
        "expression": f"""
        (function() {{
            // Wypełnij dane
            var inputs = document.querySelectorAll('input');
            inputs.forEach(function(inp) {{
                var name = (inp.name || '').toLowerCase();
                var placeholder = (inp.placeholder || '').toLowerCase();
                if (name.includes('first') || placeholder.includes('first')) inp.value = '{first_name}';
                if (name.includes('last') || placeholder.includes('last')) inp.value = '{last_name}';
                if (name.includes('email') || placeholder.includes('email')) inp.value = '{email}';
                if (name.includes('phone') || placeholder.includes('phone')) inp.value = '{phone}';
            }});
            return 'filled';
        }})()
        """
    })
    
    # Kliknij "Complete reservation"
    send_cdp(ws, "Runtime.evaluate", {
        "expression": """
        (function() {
            var btn = document.querySelector('button[type=\"submit\"]');
            if (btn) { btn.click(); return 'clicked'; }
            return 'not found';
        })()
        """
    })
    time.sleep(3)
    
    # Sprawdź potwierdzenie
    result = send_cdp(ws, "Runtime.evaluate", {
        "expression": """
        (function() {
            var confirm = document.querySelector('[data-test=\"confirmation\"]');
            if (confirm) return JSON.stringify({success: true, confirmation: confirm.textContent.trim()});
            var error = document.querySelector('[data-test=\"error\"]');
            if (error) return JSON.stringify({success: false, error: error.textContent.trim()});
            return JSON.stringify({success: false, error: 'unknown'});
        })()
        """
    })
    
    ws.close()
    
    try:
        return json.loads(result.get("result", {}).get("result", {}).get("value", "{}"))
    except:
        return {"success": False, "error": "parse error"}
```

### 2. Alternatywa: Google Reserve (przez Places API)

Google Maps ma integrację z OpenTable, TheFork, Bookatable. Przez Places API można sprawdzić linki rezerwacyjne:

```python
# W get_place_details() dodajemy:
"reservable": place.get("reservable", False),
"booking_url": place.get("bookingUrl", ""),  # Deep link do rezerwacji
```

To działa bez scrapowania — Google przekierowuje do partnera rezerwacyjnego.

### 3. Rejestracja jako Hermes Custom Tool

```python
register_tool(
    name="search_opentable",
    description="Szukaj restauracji z dostępnymi stolikami na OpenTable",
    function=search_opentable,
)

register_tool(
    name="get_restaurant_details",
    description="Pobierz szczegóły restauracji z OpenTable (adres, opinie, menu)",
    function=get_restaurant_details_opentable,
)

register_tool(
    name="reserve_table",
    description="Zarezerwuj stolik przez OpenTable. UWAGA: wymaga potwierdzenia.",
    function=make_reservation_opentable,
)
```

## Test

```bash
python3 -c "
from opentable_tool import search_opentable

# Restauracje w Gdańsku na jutro, 19:00, 2 osoby
results = search_opentable('Gdansk', '2026-07-20', '19:00', 2)
for r in results[:5]:
    print(f'{r[\"name\"]} — {r[\"rating\"]} — {r[\"price\"]} — {r[\"cuisine\"]}')
    print(f'  Sloty: {r[\"available_slots\"][:3]}')
"
```

## Ograniczenia
- **CAPTCHA**: OpenTable może wymagać CAPTCHA przy rezerwacji
- **Selektory CSS**: Mogą się zmieniać — wymaga okresowej aktualizacji
- **Szybkość**: Każda operacja to 5-10s (nawigacja + rendering)
- **Sesja**: Wymaga działającego Chrome z CDP

## Rekomendacja
Dla MVP: użyj **Google Reserve** przez Places API (linki rezerwacyjne) zamiast pełnego scrapowania OpenTable. To prostsze, szybsze i nie wymaga utrzymywania selektorów CSS.
