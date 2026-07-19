# MCP Servers — Research (Lipiec 2026)

## Stan ekosystemu

- **9800+ serwerów** na mcpservers.org
- **Nowa specyfikacja MCP** (RC 2026-07-28): stateless core, Extensions framework, Tasks, streaming, triggers
- **MCP marketplace**: Smithery, SkillsMP, Skills.sh — agent-first skill marketplace
- **Bezpieczeństwo**: CVE patterns, exploit chains — MCP security to gorący temat w 2026

## Top 15 MCP Serwerów (dla Hermesa)

| # | Serwer | Kategoria | Impact dla Hermesa |
|---|--------|-----------|-------------------|
| 1 | **Filesystem** | System | Dostęp do plików przez MCP (Hermes już ma natywny) |
| 2 | **GitHub** | Dev | Zarządzanie repo, issues, PR przez MCP |
| 3 | **PostgreSQL** | Baza | Query i schema management |
| 4 | **Slack** | Komunikacja | Wiadomości, kanały, userzy |
| 5 | **Brave Search** | Web | Web search (Hermes już ma natywny) |
| 6 | **Playwright** | Browser | Pełna automatyzacja przeglądarki przez MCP |
| 7 | **Context7** | Docs | Aktualna dokumentacja bibliotek |
| 8 | **Notion** | Produktywność | Pages, databases, blocks |
| 9 | **Google Drive** | Storage | Pliki, foldery, search |
| 10 | **Stripe** | Płatności | Customers, payments, invoices |
| 11 | **Supabase** | BaaS | Database, auth, storage |
| 12 | **Pinecone** | Vector DB | Vector search i RAG |
| 13 | **Zapier** | Automatyzacja | 7000+ app integrations |
| 14 | **Vectara** | Search | Enterprise search + RAG |
| 15 | **Salesforce** | CRM | Enterprise data access |

## MCP + Hermes

Hermes ma natywny MCP client:
```bash
hermes mcp add NAME --url URL
hermes mcp add NAME --command CMD
hermes mcp list
hermes mcp test NAME
```

**Kluczowe MCP dla wzmocnienia Hermesa:**
1. **Playwright MCP** — daje Hermesowi pełną kontrolę nad przeglądarką (obecnie browser tool jest ograniczony)
2. **GitHub MCP** — natywne zarządzanie repo (uzupełnia gh CLI)
3. **PostgreSQL MCP** — bezpośredni dostęp do baz danych
4. **Slack MCP** — dodatkowy kanał komunikacji
5. **Notion MCP** — integracja z Notion (użytkownik używa)

## Rekomendacja

**POV #1: Playwright MCP + Hermes** — największy impact. Da Hermesowi pełną automatyzację przeglądarki (formularze, klikanie, scraping dynamicznych stron) zamiast obecnego ograniczonego browser tool.
