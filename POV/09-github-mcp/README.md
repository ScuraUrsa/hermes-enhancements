# POV #9: GitHub MCP Integration

**Klient GitHub API przez `gh` CLI** — zero zewnętrznych bibliotek, tylko standardowe `subprocess` + `json`.

## Funkcje

| Funkcja | Opis |
|---------|------|
| `list_issues(repo, state, limit)` | Lista issues |
| `create_issue(repo, title, body, labels)` | Tworzenie issue |
| `list_prs(repo, state, limit)` | Lista Pull Requestów |
| `repo_info(repo)` | Informacje o repozytorium |
| `search_issues(repo, query, limit)` | Szukanie issues |
| `list_labels(repo)` | Lista etykiet |

## Wymagania

- **Python 3.8+**
- **gh CLI** zalogowane: `gh auth login`
- Konto GitHub z dostępem do docelowego repo

## Instalacja

```bash
# 1. Zainstaluj gh CLI (jeśli nie masz)
# Ubuntu/Debian:
sudo apt install gh
# macOS:
brew install gh

# 2. Zaloguj się
gh auth login

# 3. Zweryfikuj
gh auth status
```

## Użycie

```bash
# Demo — pokazuje repo info, issues, PRy, etykiety
python3 demo.py

# Demo + utworzenie testowego issue
python3 demo.py --create-test

# Na innym repo
GITHUB_REPO="owner/repo" python3 demo.py
```

## Przykład w kodzie

```python
from demo import repo_info, list_issues, create_issue

# Info o repo
info = repo_info("ScuraUrsa/hermes-enhancements")
print(info["stargazerCount"])

# Lista issues
issues = list_issues("ScuraUrsa/hermes-enhancements", state="open")
for i in issues:
    print(f"#{i['number']}: {i['title']}")

# Utwórz issue
result = create_issue(
    repo="ScuraUrsa/hermes-enhancements",
    title="Nowy feature",
    body="Opis feature'a...",
    labels=["enhancement"]
)
```

## Architektura

```
demo.py
├── _gh(args, stdin)        # Wrapper na subprocess → gh CLI
├── list_issues()           # gh issue list --json
├── create_issue()          # gh issue create
├── list_prs()              # gh pr list --json
├── repo_info()             # gh repo view --json
├── search_issues()         # gh search issues
└── list_labels()           # gh label list --json
```

## Token Monitor

Każde wywołanie API przez `gh` CLI zużywa tokeny GitHub (nie Ollama). Monitoruj limity:

```bash
python3 ../04-token-monitor/ollama_token_monitor.py status
```

## Status

✅ Przetestowane na `ScuraUrsa/hermes-enhancements`
✅ gh CLI zalogowane jako ScuraUrsa
✅ Wszystkie operacje działają: list, create, search, labels
