# POV #12: Google Places API — Wyszukiwarka restauracji i atrakcji

## Cel
Dać Hermesowi możliwość wyszukiwania restauracji, kawiarni, barów i atrakcji turystycznych przez Google Places API (New).

## Status
✅ Research zakończony | ⬜ Implementacja | ⬜ Testy

## Wymagania
- GCP API key z włączonym Places API (New)
- `pip install requests`

## API Reference
- Docs: https://developers.google.com/maps/documentation/places/web-service/op-overview
- Nearby Search: `POST https://places.googleapis.com/v1/places:searchNearby`
- Text Search: `POST https://places.googleapis.com/v1/places:searchText`
- Place Details: `GET https://places.googleapis.com/v1/places/{place_id}`
- Field mask: https://developers.google.com/maps/documentation/places/web-service/choose-fields

## Implementacja

### 1. Hermes Custom Tool: `google_places_search`

```python
# ~/workspace/hermes-enhancements/POV/12-google-places/places_tool.py

import requests
import os
from typing import Optional

GOOGLE_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
BASE_URL = "https://places.googleapis.com/v1"

PLACE_TYPES = {
    "restauracja": "restaurant",
    "kawiarnia": "cafe",
    "bar": "bar",
    "klub": "night_club",
    "atrakcja": "tourist_attraction",
    "park": "park",
    "muzeum": "museum",
    "galeria": "art_gallery",
    "teatr": "theater",
    "kino": "movie_theater",
    "spa": "spa",
    "siłownia": "gym",
}

def search_nearby(
    lat: float,
    lng: float,
    radius: int = 2000,
    place_type: str = "restaurant",
    max_results: int = 10,
    language: str = "pl",
) -> list[dict]:
    """
    Szukaj miejsc w pobliżu współrzędnych.
    
    Args:
        lat: Szerokość geograficzna
        lng: Długość geograficzna
        radius: Promień w metrach (max 50000)
        place_type: Typ miejsca (restaurant, cafe, bar, itp.)
        max_results: Maksymalna liczba wyników (1-20)
        language: Kod języka (pl, en)
    
    Returns:
        Lista miejsc z nazwą, adresem, oceną, typem
    """
    url = f"{BASE_URL}/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.priceLevel,places.types,places.id,places.googleMapsUri,places.regularOpeningHours,places.photos",
    }
    body = {
        "includedTypes": [PLACE_TYPES.get(place_type, place_type)],
        "maxResultCount": max_results,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius,
            }
        },
        "languageCode": language,
        "rankPreference": "POPULARITY",
    }
    
    resp = requests.post(url, json=body, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    
    results = []
    for place in data.get("places", []):
        results.append({
            "name": place.get("displayName", {}).get("text", "?"),
            "address": place.get("formattedAddress", "?"),
            "rating": place.get("rating", 0),
            "reviews_count": place.get("userRatingCount", 0),
            "price_level": place.get("priceLevel", "?"),
            "types": place.get("types", []),
            "place_id": place.get("id", ""),
            "maps_url": place.get("googleMapsUri", ""),
            "open_now": place.get("regularOpeningHours", {}).get("openNow", False),
            "has_photos": len(place.get("photos", [])) > 0,
        })
    
    return results


def search_text(
    query: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius: int = 5000,
    max_results: int = 10,
    language: str = "pl",
) -> list[dict]:
    """
    Szukaj miejsc po zapytaniu tekstowym.
    
    Args:
        query: Zapytanie (np. "najlepsza pizza Gdańsk Wrzeszcz")
        lat/lng: Opcjonalne współrzędne do zawężenia
        radius: Promień w metrach
        max_results: Maksymalna liczba wyników
        language: Kod języka
    
    Returns:
        Lista miejsc
    """
    url = f"{BASE_URL}/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.priceLevel,places.id,places.googleMapsUri,places.types,places.editorialSummary",
    }
    body = {
        "textQuery": query,
        "maxResultCount": max_results,
        "languageCode": language,
    }
    
    if lat is not None and lng is not None:
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius,
            }
        }
    
    resp = requests.post(url, json=body, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    
    results = []
    for place in data.get("places", []):
        summary = place.get("editorialSummary", {})
        results.append({
            "name": place.get("displayName", {}).get("text", "?"),
            "address": place.get("formattedAddress", "?"),
            "rating": place.get("rating", 0),
            "reviews_count": place.get("userRatingCount", 0),
            "price_level": place.get("priceLevel", "?"),
            "types": place.get("types", []),
            "place_id": place.get("id", ""),
            "maps_url": place.get("googleMapsUri", ""),
            "ai_summary": summary.get("text", "") if summary else "",
        })
    
    return results


def get_place_details(place_id: str, language: str = "pl") -> dict:
    """
    Pobierz szczegóły miejsca.
    
    Args:
        place_id: Google Place ID
        language: Kod języka
    
    Returns:
        Szczegóły miejsca (adres, telefon, strona, godziny, recenzje)
    """
    url = f"{BASE_URL}/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "displayName,formattedAddress,nationalPhoneNumber,websiteUri,regularOpeningHours,rating,userRatingCount,priceLevel,reviews,editorialSummary,googleMapsUri,photos,types,delivery,takeout,dineIn,servesBreakfast,servesLunch,servesDinner,servesBeer,servesWine,servesCocktails,outdoorSeating,liveMusic,goodForGroups,allowsDogs",
    }
    params = {"languageCode": language}
    
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    place = resp.json()
    
    reviews = []
    for r in place.get("reviews", [])[:5]:
        reviews.append({
            "author": r.get("authorAttribution", {}).get("displayName", "?"),
            "rating": r.get("rating", 0),
            "text": r.get("text", {}).get("text", "")[:500],
            "time": r.get("relativePublishTimeDescription", ""),
        })
    
    return {
        "name": place.get("displayName", {}).get("text", "?"),
        "address": place.get("formattedAddress", "?"),
        "phone": place.get("nationalPhoneNumber", ""),
        "website": place.get("websiteUri", ""),
        "maps_url": place.get("googleMapsUri", ""),
        "rating": place.get("rating", 0),
        "reviews_count": place.get("userRatingCount", 0),
        "price_level": place.get("priceLevel", "?"),
        "open_now": place.get("regularOpeningHours", {}).get("openNow", False),
        "weekday_hours": place.get("regularOpeningHours", {}).get("weekdayDescriptions", []),
        "ai_summary": place.get("editorialSummary", {}).get("text", ""),
        "reviews": reviews,
        "features": {
            "delivery": place.get("delivery", False),
            "takeout": place.get("takeout", False),
            "dine_in": place.get("dineIn", False),
            "outdoor_seating": place.get("outdoorSeating", False),
            "live_music": place.get("liveMusic", False),
            "good_for_groups": place.get("goodForGroups", False),
            "allows_dogs": place.get("allowsDogs", False),
            "serves_beer": place.get("servesBeer", False),
            "serves_wine": place.get("servesWine", False),
            "serves_cocktails": place.get("servesCocktails", False),
        },
        "has_photos": len(place.get("photos", [])) > 0,
    }
```

### 2. Rejestracja jako Hermes Custom Tool

```python
# W ~/.hermes/plugins/places_plugin.py
from hermes_tools import register_tool
from POV_12_google_places.places_tool import search_nearby, search_text, get_place_details

register_tool(
    name="search_restaurants",
    description="Szukaj restauracji i miejsc w okolicy przez Google Places API",
    function=search_nearby,
)

register_tool(
    name="search_places_text",
    description="Szukaj miejsc po zapytaniu tekstowym (np. 'najlepsza pizza Gdańsk')",
    function=search_text,
)

register_tool(
    name="get_place_info",
    description="Pobierz szczegółowe informacje o miejscu (adres, godziny, recenzje, menu)",
    function=get_place_details,
)
```

## Test

```bash
# Ustaw klucz
export GOOGLE_MAPS_API_KEY="..."

# Test: restauracje w centrum Gdańska
python3 -c "
from places_tool import search_nearby, get_place_details

# Gdańsk Główny: 54.3520, 18.6466
results = search_nearby(54.3520, 18.6466, radius=2000, place_type='restauracja', max_results=5)
for r in results:
    print(f'{r[\"name\"]} — {r[\"rating\"]}★ ({r[\"reviews_count\"]} opinii) — {r[\"price_level\"]}')

# Szczegóły pierwszego miejsca
if results:
    details = get_place_details(results[0]['place_id'])
    print(f'\\n{details[\"name\"]}')
    print(f'Tel: {details[\"phone\"]}')
    print(f'AI: {details[\"ai_summary\"][:200]}')
    for r in details['reviews'][:2]:
        print(f'  {r[\"author\"]}: {r[\"text\"][:100]}...')
"
```

## Koszt
- $200/miesiąc darmowego kredytu GCP
- ~4000-6000 requestów w ramach free tier
- Dla typowego użycia (50-100 zapytań dziennie) = $0

## Integracja z Hermesem
Po rejestracji jako custom tool, Hermes może:
- "Znajdź najlepsze restauracje włoskie w promieniu 2km od Dworca Głównego w Gdańsku"
- "Jakie są godziny otwarcia i recenzje restauracji X?"
- "Szukam miejsca na randkę — romantyczna restauracja z muzyką na żywo"
