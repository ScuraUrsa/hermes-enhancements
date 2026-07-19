# Travel MCP Servers — Research (Lipiec 2026)

## Istniejące MCP serwery travel

| Serwer | GitHub | Funkcje |
|--------|--------|---------|
| **travel-mcp-server** | gs-ysingh/travel-mcp-server | Flights, hotels, currency, weather |
| **mcp_travelassistant** | skarlekar/mcp_travelassistant | Suite of MCP servers: flights, hotels, restaurants, activities |
| **Google Travel Impact Model MCP** | Google | Carbon footprint for flights (official) |

## Integracja z Hermesem

```bash
# Klonuj i uruchom MCP server
git clone https://github.com/skarlekar/mcp_travelassistant.git
cd mcp_travelassistant
pip install -r requirements.txt

# Dodaj do Hermesa
hermes mcp add travel --command "python3 server.py"
```

## Wnioski

- MCP w travel to wczesny etap (2026) — kilka serwerów, głównie proof-of-concept
- Google oficjalnie wspiera MCP dla Travel Impact Model
- Najlepsza opcja: zbudować własny MCP server (jak travel_mcp_server.py w repo)
- Alternatywa: używać bezpośrednich API (Amadeus, Skyscanner, Booking) jako custom tools
