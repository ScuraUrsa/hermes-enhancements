# Browser Automation — Research (Lipiec 2026)

## Stan ekosystemu

### Playwright AI Ecosystem 2026
- **MCP server** — standardowy protokół dla AI-browser interakcji
- **3 wbudowane agenty**: Planner, Generator, Healer
- **Accessibility-tree-first** — nie screenshots, nie piksele
- **Self-healing** — auto-naprawa selektorów
- **Codegen z AI** — natural language → testy

### Warstwy ekosystemu Playwright AI

1. **Protocol layer**: Playwright MCP — kontrolowany dostęp do przeglądarki
2. **Agent layer**: Planner (eksploracja), Generator (tworzenie testów), Healer (samoleczenie)
3. **Authoring layer**: Codegen, CLI z AI Skills, IDE integrations
4. **Tooling layer**: TestDino, ZeroStep, Bug0, Octomind, AgentQL

### Browser Use (open-source)
- Python library do AI-driven browser automation
- Agent-based: "znajdź produkt, dodaj do koszyka, kup"
- Działa z każdym LLM (przez LangChain)
- 25k+ GitHub stars

### Porównanie narzędzi

| Tool | Typ | AI-native | Self-healing | Open source |
|------|-----|-----------|--------------|-------------|
| **Playwright MCP** | Protocol | ✅ | ✅ (Healer) | ✅ |
| **Browser Use** | Library | ✅ | ❌ | ✅ |
| **Selenium** | Framework | ❌ | ❌ | ✅ |
| **Puppeteer** | Library | ❌ | ❌ | ✅ |
| **Browserbase** | Platform | ✅ | ✅ | ❌ (SaaS) |
| **Camofox** | Platform | ✅ | ✅ | ❌ (SaaS) |

## Hermes + Browser

Hermes ma wbudowany `browser` toolset:
- `browser_navigate`, `browser_click`, `browser_type`, `browser_snapshot`
- Accessibility-tree-based (jak Playwright)
- Ograniczony do prostych interakcji

**Brakuje:**
- Self-healing selektorów
- Multi-step workflows
- Form filling z kontekstem
- File upload
- CAPTCHA handling
- Session persistence

## Rekomendacja

### POV #4: Playwright MCP + Hermes
- Zainstalować Playwright MCP server
- Podłączyć do Hermesa przez `hermes mcp add`
- Zastąpić/uzupełnić wbudowany browser tool
- Daje: self-healing, multi-step, lepsze snapshoty, Codegen

```bash
# Instalacja
npm install -g @playwright/mcp
hermes mcp add playwright --command "npx @playwright/mcp"
```

**Impact: 9/10, Effort: 3/10** (głównie instalacja npm)
