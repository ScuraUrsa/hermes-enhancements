# Hermes Custom Plugin Development — Research (Lipiec 2026)

## Plugin system

Hermes ma system pluginów: `~/.hermes/plugins/<name>/plugin.py`

```python
# Minimalny plugin
from tools.registry import registry

def my_tool(param: str) -> str:
    return f"Result: {param}"

registry.register(
    name="my_tool",
    toolset="custom",
    schema={...},
    handler=lambda args, **kw: my_tool(args.get("param", "")),
)
```

## Co można zrobić z pluginem

- **Custom tools** — nowe narzędzia dla agenta
- **Lifecycle hooks** — before/after tool call
- **Slash commands** — nowe komendy w CLI
- **Skills** — reusable procedury
- **MCP servers** — integracja z zewnętrznymi serwerami

## Rekomendacja

### POV #10: Hermes Custom Plugin — Selenium Browser Tool
- Opakować POV #2 (Selenium) jako plugin Hermesa
- Zarejestrować narzędzia: browser_navigate, browser_click, browser_type, browser_snapshot
- Plugin ładuje się automatycznie przy starcie Hermesa
- **Impact: 8/10, Effort: 4/10**
