# POV #2: Selenium Browser Automation + Hermes

## Cel
Dać Hermesowi pełną kontrolę nad przeglądarką przez Selenium WebDriver.

## Status
✅ Selenium + Chrome działają
✅ Demo: nawigacja, formularze, snapshot
⚠️  Playwright MCP wymaga Node.js + sudo (niedostępne na tej VM)

## Szybki start

```bash
# 1. Zainstaluj zależności
pip install selenium webdriver-manager

# 2. Uruchom demo
cd ~/workspace/hermes-enhancements/POV/02-browser-automation
python3 demo.py
```

## Co działa

- Nawigacja do URL (lokalne i zdalne)
- Wypełnianie formularzy (input, textarea)
- Klikanie elementów
- Accessibility snapshot (jak Hermes browser_snapshot)
- Headless mode (działa bez GUI)

## Integracja z Hermesem

### Opcja A: Custom plugin (Python)
```python
# ~/.hermes/plugins/browser_selenium/plugin.py
# Zarejestruj narzędzia: navigate, click, type, snapshot
```

### Opcja B: Playwright MCP (lepsza, ale wymaga Node.js)
```bash
npm install -g @playwright/mcp
hermes mcp add playwright --command "npx @playwright/mcp"
```

## Porównanie z wbudowanym browser tool

| Cecha | Hermes browser | Selenium | Playwright MCP |
|-------|---------------|----------|----------------|
| Instalacja | Wbudowany | pip install | npm install |
| Self-healing | ❌ | ❌ | ✅ (Healer agent) |
| Multi-step | Ograniczony | ✅ | ✅ |
| Formularze | Podstawowe | ✅ | ✅ |
| File upload | ❌ | ✅ | ✅ |
| CAPTCHA | ❌ | ❌ | ❌ |

## Wnioski

- Selenium działa na Python 3.10 (browser-use wymaga 3.11+)
- Playwright MCP to lepsza opcja długoterminowa (self-healing, AI agenty)
- Do czasu instalacji Node.js, Selenium jest solidnym rozwiązaniem
