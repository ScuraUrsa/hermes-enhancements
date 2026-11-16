"""Model providers, read from ``providers.toml``.

A provider says *where* the model runs; an agent adapter (framework) turns it
into that framework's own environment variables. ``kind`` is one of:

* ``anthropic`` - Anthropic API (API key or Claude Code OAuth token)
* ``ollama``    - Ollama, local (``http://host:11434``) or Ollama Cloud
* ``github``    - GitHub-hosted Copilot models (Copilot CLI only)
* ``openai``    - any OpenAI-compatible endpoint (vLLM, LiteLLM, OpenRouter, ...)
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Provider:
    name: str
    kind: str
    base_url: str | None = None
    api_key_env: str | None = None
    context_tokens: int | None = None
    local: bool = False  # local models have no per-token cost; record hardware instead
    hardware: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env) if self.api_key_env else None


def load_providers(path: Path) -> dict[str, Provider]:
    data = tomllib.loads(path.read_text())
    out = {}
    for name, cfg in data.items():
        cfg = dict(cfg)
        out[name] = Provider(
            name=name,
            kind=cfg.pop("kind"),
            base_url=cfg.pop("base_url", None),
            api_key_env=cfg.pop("api_key_env", None),
            context_tokens=cfg.pop("context_tokens", None),
            local=bool(cfg.pop("local", False)),
            hardware=cfg.pop("hardware", None),
            extra=cfg,
        )
    return out
