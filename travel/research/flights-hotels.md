# Loty + Hotele — Research API (Lipiec 2026)

> **Autor**: deleg_flights_hotels (deepseek-v4-pro)  
> **Data**: 2026-07-19  
> **Status**: Research zakończony, POV w budowie

---

## ✈️ Platformy lotnicze

| Platforma | Zasięg | API | Typ | Dostęp | Cena |
|-----------|--------|-----|-----|--------|------|
| **Skyscanner** | Globalny (52 rynki, 30 języków) | ✅ | Partner REST (Flights Live Prices, Indicative Prices) | Aplikacja partnerska | Revenue share / commission |
| **Amadeus** | Globalny (największy GDS) | ✅ → ⚠️ | Enterprise REST (było Self-Service) | **Self-service ZAMKNIĘTE 17.07.2026** | Enterprise (kontakt) |
| **Google Flights** | Globalny | ❌ | QPX Express (zamknięty 2018) | Brak publicznego API | N/A |
| **Kayak** | Globalny (200+ krajów) | ✅ | Affiliate REST (Flights Search, Price Insights) | Sandbox (darmowy) + Partner | Revenue share |
| **Duffel** | Globalny | ✅ | REST (Flights Search, Booking) | Self-service, API key | Pay-as-you-go |
| **Kiwi.com** | Globalny | ✅ | REST (Flights Search, Multi-city) | Partner API | Revenue share |
| **TravelPayouts** | Globalny | ✅ | REST (Aviasales API) | Self-service, API key | CPA/CPC |

### Kluczowe wnioski — loty

1. **Amadeus — DRAMAT**: 17 lipca 2026 Amadeus zamknął swój self-service portal. To był najłatwiejszy sposób na dostęp do GDS (Global Distribution System). Teraz tylko Enterprise — trzeba kontaktować się z sales teamem. **To poważna blokada dla indie devów.**

2. **Google Flights — brak API**: QPX Express zamknięty w 2018. Google nie oferuje żadnego publicznego API do wyszukiwania lotów. Alternatywy: scraping (ryzykowne), lub inne API.

3. **Skyscanner — najlepsza opcja partnerska**: Pełne API (Live Prices + Indicative Prices + Geo + Culture + Carriers). Wymaga aplikacji partnerskiej, ale ma dedykowane wsparcie techniczne. Oferuje też hotele, auta.

4. **Kayak — sandbox dostępny**: Darmowy sandbox do testów. Flights Search API + Price Insights API. Trzeba wypełnić formularz kontaktowy.

5. **Duffel — najłatwiejszy start**: Self-service, REST API, dokumentacja publiczna. Obsługuje 300+ linii lotniczych. Pay-as-you-go.

---

## 🏨 Platformy hotelowe

| Platforma | Zasięg | API | Typ | Dostęp | Cena |
|-----------|--------|-----|-----|--------|------|
| **Booking.com** | Globalny (28M+ nieruchomości) | ✅ | Demand API (Affiliate) + Connectivity API | Managed Affiliate Partner | 25-40% commission share |
| **Airbnb** | Globalny (7M+ ofert) | ⚠️ | Oficjalne API tylko dla hostów | **Brak publicznego API dla search** | N/A |
| **Kayak Hotels** | Globalny (2M+ hoteli, 200+ krajów) | ✅ | Hotels Search API + Static Data Feeds | Sandbox (darmowy) + Partner | Revenue share |
| **Skyscanner Hotels** | Globalny | ✅ | Hotels Live Prices + Indicative + Content + Reviews | Aplikacja partnerska | Revenue share |
| **Expedia** | Globalny | ✅ | Partner API (EPS Rapid) | Partner application | Revenue share |
| **TripAdvisor** | Globalny | ✅ | Content API + Booking API | API key | Revenue share |

### Kluczowe wnioski — hotele

1. **Booking.com — najlepszy ekosystem**: Demand API v3 (najnowsza wersja) oferuje stays, car rentals, attractions, a wkrótce flights i taxis. 4 poziomy integracji: Content Only → Search & Redirect → Full Booking → Post-booking. Commission 25-40% w zależności od wolumenu.

2. **Airbnb — brak publicznego API**: Oficjalne API tylko dla hostów (zarządzanie ofertami). Dla wyszukiwania trzeba używać third-party scraperów (SearchAPI.io, RapidAPI, AirROI, AirDNA). To nieoficjalne i ryzykowne.

3. **Kayak Hotels — świetny sandbox**: Darmowy dostęp do sandboxa. Hotels Search API z filtrami (cena, gwiazdki, rating, udogodnienia, łańcuchy). Static Data Feeds z pełnym katalogiem hoteli.

4. **Skyscanner Hotels — kompletny pakiet**: Live Prices, Indicative Prices, Content (amenities, zdjęcia, polityki), Reviews. Wszystko w jednym ekosystemie z lotami.

---

## 🔑 Rekomendowana strategia integracji

### Tier 1: Najłatwiejszy start (self-service, darmowy sandbox)
- **Kayak** — Flights + Hotels Search API (sandbox za darmo)
- **Duffel** — Flights API (self-service, REST)
- **TravelPayouts** — Aviasales API (self-service)

### Tier 2: Partnerski (wymaga aplikacji, revenue share)
- **Skyscanner** — Flights + Hotels (najlepszy all-in-one)
- **Booking.com** — Hotels (największy katalog, Demand API v3)

### Tier 3: Enterprise (kontakt z sales)
- **Amadeus** — GDS (po zamknięciu self-service, tylko enterprise)

### Tier 4: Nieoficjalne/scraping (ryzykowne)
- **Airbnb** — przez SearchAPI.io, RapidAPI scrapery
- **Google Flights** — przez SerpAPI, scraping

---

## 📊 Porównanie kluczowych cech

| Cecha | Skyscanner | Kayak | Booking.com | Amadeus | Duffel |
|-------|-----------|-------|-------------|---------|--------|
| **Loty** | ✅ Live + Indicative | ✅ Search + Insights | ⏳ Coming soon | ✅ (Enterprise) | ✅ |
| **Hotele** | ✅ Live + Content | ✅ Search + Static | ✅ (core) | ❌ | ❌ |
| **Self-service** | ❌ (partner) | ✅ (sandbox) | ❌ (partner) | ❌ (enterprise) | ✅ |
| **Darmowy tier** | ❌ | ✅ (sandbox) | ❌ | ❌ | ✅ (test) |
| **Dokumentacja** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Języki** | 30 | Multi | 40+ | Multi | EN |
| **Waluty** | Multi | Multi | Multi | Multi | Multi |

---

## 🧪 Co testujemy w POV

1. **Kayak Sandbox** — Flights Search + Hotels Search (darmowy sandbox, najłatwiejszy start)
2. **Skyscanner** — struktura API (dokumentacja publiczna, symulacja)
3. **Booking.com** — struktura Demand API (dokumentacja publiczna, symulacja)
4. **Duffel** — Flights Search (self-service, można realnie testować)

---

## ⚠️ Pitfalls

- **Amadeus Self-Service ZAMKNIĘTY** — nie marnuj czasu na rejestrację
- **Google Flights** — brak API, tylko scraping (ryzykowne, łamie ToS)
- **Airbnb** — oficjalne API tylko dla hostów, third-party scrapery są nieoficjalne
- **Skyscanner** — wymaga zatwierdzonej aplikacji partnerskiej (nie instant)
- **Booking.com** — wymaga bycia Managed Affiliate Partner
- **Kayak** — sandbox jest darmowy, ale production wymaga umowy

---

## 📎 Źródła

- https://developers.skyscanner.net/docs/intro
- https://developers.amadeus.com/ (self-service decommissioned 17.07.2026)
- https://developers.booking.com/demand
- https://developers.kayak.com/
- https://affiliates.kayak.com/apis/hotels
- https://affiliates.kayak.com/apis/flights
- https://duffel.com/blog/google-flights-api
- https://www.phocuswire.com/amadeus-shut-down-self-service-apis-portal-developers
- https://www.searchapi.io/airbnb-api
- https://partnerships.booking.com/api-v3
