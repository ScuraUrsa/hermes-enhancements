# POV #13: Eventbrite + Ticketmaster — Wyszukiwarka wydarzeń

## Cel
Dać Hermesowi możliwość wyszukiwania wydarzeń, koncertów, festiwali, warsztatów i spotkań przez Eventbrite API i Ticketmaster Discovery API.

## Status
✅ Research zakończony | ⬜ Implementacja | ⬜ Testy

## Wymagania
- Eventbrite API key (darmowy, z developer.eventbrite.com)
- Ticketmaster API key (darmowy, z developer.ticketmaster.com)
- `pip install requests`

## API Reference

### Eventbrite
- Docs: https://www.eventbrite.com/platform/docs/introduction
- Search: `GET /v3/events/search/?location.address={city}&location.within={radius}km`
- Auth: `Authorization: Bearer {API_KEY}`

### Ticketmaster
- Docs: https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/
- Search: `GET /discovery/v2/events.json?countryCode=PL&apikey={key}`
- Auth: `?apikey={key}` w query string
- Limit: 5000 req/dzień, 5 req/sek

## Implementacja

### 1. Hermes Custom Tool: `search_events`

```python
# ~/workspace/hermes-enhancements/POV/13-eventbrite-ticketmaster/events_tool.py

import requests
import os
from datetime import datetime, timedelta
from typing import Optional

EVENTBRITE_KEY = os.environ.get("EVENTBRITE_API_KEY", "")
TICKETMASTER_KEY = os.environ.get("TICKETMASTER_API_KEY", "")

EVENTBRITE_CATEGORIES = {
    "muzyka": "103",
    "biznes": "101",
    "technologia": "102",
    "film": "104",
    "sport": "105",
    "zdrowie": "106",
    "jedzenie": "107",
    "społeczność": "108",
    "sztuka": "109",
    "moda": "110",
    "randki": "113",
    "imprezy": "199",
}

TICKETMASTER_CLASSIFICATIONS = {
    "muzyka": "music",
    "sport": "sports",
    "sztuka": "arts",
    "teatr": "theatre",
    "film": "film",
    "rodzina": "family",
}


def search_eventbrite(
    city: str = "Gdańsk",
    radius: int = 20,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_results: int = 20,
) -> list[dict]:
    """
    Szukaj wydarzeń na Eventbrite.
    
    Args:
        city: Miasto
        radius: Promień w km
        category: Kategoria (muzyka, biznes, randki, itp.)
        start_date: Data początkowa (YYYY-MM-DD)
        end_date: Data końcowa (YYYY-MM-DD)
        max_results: Maksymalna liczba wyników
    
    Returns:
        Lista wydarzeń
    """
    url = "https://www.eventbriteapi.com/v3/events/search/"
    params = {
        "location.address": city,
        "location.within": f"{radius}km",
        "expand": "venue,ticket_classes",
        "page_size": min(max_results, 50),
    }
    
    if category and category in EVENTBRITE_CATEGORIES:
        params["categories"] = EVENTBRITE_CATEGORIES[category]
    
    if start_date:
        params["start_date.range_start"] = f"{start_date}T00:00:00Z"
    if end_date:
        params["start_date.range_end"] = f"{end_date}T23:59:59Z"
    
    headers = {"Authorization": f"Bearer {EVENTBRITE_KEY}"}
    
    resp = requests.get(url, params=params, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    
    results = []
    for event in data.get("events", []):
        venue = event.get("venue", {}) or {}
        ticket_classes = event.get("ticket_classes", [])
        min_price = min(
            (tc.get("cost", {}).get("major_value", 0) or 0
             for tc in ticket_classes if tc.get("free") == False),
            default=0
        )
        is_free = any(tc.get("free") for tc in ticket_classes)
        
        results.append({
            "source": "eventbrite",
            "name": event.get("name", {}).get("text", "?"),
            "description": event.get("description", {}).get("text", "")[:300],
            "url": event.get("url", ""),
            "start": event.get("start", {}).get("local", ""),
            "end": event.get("end", {}).get("local", ""),
            "venue": venue.get("name", "?"),
            "address": venue.get("address", {}).get("localized_multi_line_address_display", ["?"])[0] if venue.get("address") else "?",
            "city": venue.get("address", {}).get("city", city) if venue.get("address") else city,
            "is_free": is_free,
            "min_price_pln": f"{min_price / 100:.2f} PLN" if min_price else "Free",
            "category": category or "all",
            "status": event.get("status", ""),
        })
    
    return results


def search_ticketmaster(
    city: str = "Gdańsk",
    country: str = "PL",
    classification: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_results: int = 20,
) -> list[dict]:
    """
    Szukaj wydarzeń na Ticketmaster.
    
    Args:
        city: Miasto
        country: Kod kraju (PL, US, GB, itp.)
        classification: Kategoria (music, sports, arts, itp.)
        start_date: Data początkowa (YYYY-MM-DD)
        end_date: Data końcowa (YYYY-MM-DD)
        max_results: Maksymalna liczba wyników
    
    Returns:
        Lista wydarzeń
    """
    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        "apikey": TICKETMASTER_KEY,
        "countryCode": country,
        "city": city,
        "size": min(max_results, 50),
        "sort": "date,asc",
    }
    
    if classification and classification in TICKETMASTER_CLASSIFICATIONS:
        params["classificationName"] = TICKETMASTER_CLASSIFICATIONS[classification]
    
    if start_date:
        params["startDateTime"] = f"{start_date}T00:00:00Z"
    if end_date:
        params["endDateTime"] = f"{end_date}T23:59:59Z"
    
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    
    results = []
    embedded = data.get("_embedded", {})
    for event in embedded.get("events", []):
        venue_list = event.get("_embedded", {}).get("venues", [{}])
        venue = venue_list[0] if venue_list else {}
        
        price_ranges = event.get("priceRanges", [])
        min_price = min((p.get("min", 0) for p in price_ranges), default=0)
        max_price = max((p.get("max", 0) for p in price_ranges), default=0)
        
        results.append({
            "source": "ticketmaster",
            "name": event.get("name", "?"),
            "url": event.get("url", ""),
            "start": event.get("dates", {}).get("start", {}).get("localDate", ""),
            "start_time": event.get("dates", {}).get("start", {}).get("localTime", ""),
            "venue": venue.get("name", "?"),
            "city": venue.get("city", {}).get("name", city),
            "address": venue.get("address", {}).get("line1", "?"),
            "min_price_pln": f"{min_price:.2f} {event.get('priceRanges', [{}])[0].get('currency', 'PLN')}" if price_ranges else "N/A",
            "max_price_pln": f"{max_price:.2f} {event.get('priceRanges', [{}])[0].get('currency', 'PLN')}" if price_ranges else "N/A",
            "category": event.get("classifications", [{}])[0].get("segment", {}).get("name", classification or "all"),
            "genre": event.get("classifications", [{}])[0].get("genre", {}).get("name", ""),
            "image": next((img["url"] for img in event.get("images", []) if img.get("width", 0) > 200), ""),
        })
    
    return results


def search_all_events(
    city: str = "Gdańsk",
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_results: int = 30,
) -> dict:
    """
    Agreguje wyniki z Eventbrite i Ticketmaster.
    
    Args:
        city: Miasto
        category: Kategoria (muzyka, sport, randki, itp.)
        start_date: Data początkowa
        end_date: Data końcowa
        max_results: Maksymalna liczba wyników
    
    Returns:
        {"eventbrite": [...], "ticketmaster": [...], "total": N}
    """
    eb_results = []
    tm_results = []
    
    # Mapuj kategorię na oba API
    eb_cat = category if category in EVENTBRITE_CATEGORIES else None
    tm_cat = category if category in TICKETMASTER_CLASSIFICATIONS else None
    
    try:
        eb_results = search_eventbrite(city, category=eb_cat, start_date=start_date, end_date=end_date, max_results=max_results//2)
    except Exception as e:
        print(f"Eventbrite error: {e}")
    
    try:
        tm_results = search_ticketmaster(city, classification=tm_cat, start_date=start_date, end_date=end_date, max_results=max_results//2)
    except Exception as e:
        print(f"Ticketmaster error: {e}")
    
    return {
        "eventbrite": eb_results,
        "ticketmaster": tm_results,
        "total": len(eb_results) + len(tm_results),
    }
```

### 2. Rejestracja jako Hermes Custom Tool

```python
# W ~/.hermes/plugins/events_plugin.py
from hermes_tools import register_tool
from POV_13_eventbrite_ticketmaster.events_tool import search_all_events

register_tool(
    name="search_events",
    description="Szukaj wydarzeń, koncertów, festiwali i spotkań w danym mieście. Agreguje Eventbrite + Ticketmaster.",
    function=search_all_events,
)
```

## Test

```bash
export EVENTBRITE_API_KEY="..."
export TICKETMASTER_API_KEY="..."

python3 -c "
from events_tool import search_all_events

# Wydarzenia w Gdańsku na najbliższy tydzień
from datetime import date
today = date.today().isoformat()
next_week = (date.today() + timedelta(days=7)).isoformat()

results = search_all_events('Gdańsk', start_date=today, end_date=next_week)
print(f'Znaleziono {results[\"total\"]} wydarzeń')

for e in results['eventbrite'][:3]:
    print(f'[EB] {e[\"name\"]} — {e[\"start\"]} — {e[\"min_price_pln\"]} — {e[\"venue\"]}')

for e in results['ticketmaster'][:3]:
    print(f'[TM] {e[\"name\"]} — {e[\"start\"]} — {e[\"min_price_pln\"]} — {e[\"venue\"]}')
"
```

## Koszt
- Oba API darmowe
- Eventbrite: 1000 req/h
- Ticketmaster: 5000 req/dzień

## Integracja z Hermesem
Po rejestracji Hermes może:
- "Jakie koncerty są w Gdańsku w ten weekend?"
- "Szukam wydarzeń networkingowych w Warszawie w przyszłym tygodniu"
- "Czy są jakieś darmowe wydarzenia w Trójmieście jutro?"
- "Znajdź warsztaty z AI w Polsce w tym miesiącu"
