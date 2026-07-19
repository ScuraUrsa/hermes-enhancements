# POV #10: Hermes Custom Plugin — Selenium Browser Tool

**Plugin Hermesa** opakowujący Selenium WebDriver jako narzędzia agenta.

## Zarejestrowane narzędzia

| Narzędzie | Opis |
|-----------|------|
| `browser_navigate(url)` | Nawiguj do URL, zwróć snapshot |
| `browser_click(selector)` | Kliknij element, zwróć snapshot |
| `browser_type(selector, text)` | Wpisz tekst w pole, zwróć snapshot |
| `browser_snapshot()` | Accessibility snapshot strony |
| `browser_screenshot()` | Screenshot jako base64 PNG |
| `browser_close()` | Zamknij przeglądarkę |

## Instalacja

```bash
# 1. Zainstaluj zależności
pip install selenium webdriver-manager

# 2. Skopiuj plugin do katalogu Hermesa
cp -r POV/10-hermes-selenium-plugin ~/.hermes/plugins/selenium_browser/

# 3. Zrestartuj Hermesa
# Plugin ładuje się automatycznie
```

## Test standalone

```bash
python3 -c "
from plugin import browser_navigate, browser_snapshot, browser_close
snap = browser_navigate('https://example.com')
print(snap['title'])
print(f'Interactive elements: {snap[\"total_interactive\"]}')
browser_close()
"
```

## Architektura

```
plugin.py
├── _get_driver()          # Lazy init Chrome (headless)
├── _get_snapshot()        # Accessibility tree + interactive elements
├── browser_navigate()     # driver.get(url)
├── browser_click()        # find_element + click
├── browser_type()         # find_element + send_keys
├── browser_snapshot()     # Tylko snapshot
├── browser_screenshot()   # base64 PNG
├── browser_close()        # driver.quit()
└── register_plugin()      # Auto-rejestracja w Hermes registry
```

## Integracja z Hermesem

Plugin używa `tools.registry` do rejestracji narzędzi. Gdy Hermes ładuje plugin, narzędzia stają się dostępne dla agenta:

```
Agent: "Otwórz https://example.com i sprawdź tytuł"
→ browser_navigate("https://example.com")
→ browser_snapshot()
→ Zwróć: {"title": "Example Domain", ...}
```

## Wymagania

- Python 3.8+
- Google Chrome
- `selenium`, `webdriver-manager`
- Hermes Agent (dla integracji pluginowej)

## Status

✅ Plugin działa standalone (bez Hermesa)
✅ Wszystkie 6 narzędzi zarejestrowanych
✅ Headless Chrome — nie wymaga GUI
✅ Auto-rejestracja przy imporcie
