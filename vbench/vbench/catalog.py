"""providers.toml as one object: providers, API-equivalent prices and per-model limits."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .providers import (DEFAULT_PROVIDERS, Completion, Model, ProviderConfig, base_ref, get_model, load_providers,
                        split_ref)


@dataclass
class Price:
    input: float  # USD per million tokens
    output: float
    basis: str = ""


@dataclass
class Cost:
    equiv_usd: float | None  # list price on a pay-per-token API
    marginal_usd: float | None  # what Filip actually pays for this call (0 on a subscription)


@dataclass
class Catalog:
    providers: dict[str, ProviderConfig]
    prices: dict[str, Price] = field(default_factory=dict)
    models: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "Catalog":
        path = Path(path or DEFAULT_PROVIDERS)
        data = tomllib.loads(path.read_text())
        prices = {k: Price(float(v["input"]), float(v["output"]), v.get("basis", "")) for k, v in
                  (data.get("prices") or {}).items()}
        return cls(load_providers(path), prices, dict(data.get("models") or {}))

    def model(self, ref: str) -> Model:
        return get_model(ref, self.providers)

    def context_tokens(self, ref: str, default: int = 128_000) -> int:
        return int(self.models.get(base_ref(ref), {}).get("context", default))

    def unavailable(self, refs: list[str]) -> dict[str, str]:
        """Refs whose provider says the model is not served (retired or misspelled). Providers that
        can't be asked (no key, not OpenAI-compatible, offline) are skipped, not flagged."""
        from .providers import list_live_models
        live: dict[str, set[str] | None] = {}
        out = {}
        for ref in refs:
            pname, model = split_ref(ref)
            if pname not in self.providers:
                continue
            if pname not in live:
                live[pname] = list_live_models(self.providers[pname])
            ids = live[pname]
            if ids is not None and model not in ids:
                out[ref] = f"{pname} does not serve {model}"
        return out

    def has_vision(self, ref: str) -> bool | None:
        v = self.models.get(base_ref(ref), {}).get("vision")
        return None if v is None else bool(v)

    def cost(self, ref: str, c: Completion) -> Cost:
        billing = self.providers[split_ref(ref)[0]].billing
        equiv: float | None
        if c.reported_cost_usd is not None:
            equiv = float(c.reported_cost_usd)
        elif base_ref(ref) in self.prices and c.input_tokens is not None:
            p = self.prices[base_ref(ref)]
            equiv = (c.input_tokens * p.input + (c.output_tokens or 0) * p.output) / 1e6
        else:
            equiv = None
        marginal = 0.0 if billing in ("subscription", "local") else equiv
        return Cost(equiv, marginal)


def prices_from_models_dev(cache: Path, mapping: dict[str, str]) -> dict[str, Price]:
    """Refresh prices from a models.dev dump. ``mapping`` is ref -> "provider/model-id" in that dump."""
    d = json.loads(Path(cache).read_text())
    out = {}
    for ref, src in mapping.items():
        prov, _, mid = src.partition("/")
        m = (d.get(prov) or {}).get("models", {}).get(mid)
        if m and (m.get("cost") or {}).get("input") is not None:
            out[ref] = Price(float(m["cost"]["input"]), float(m["cost"].get("output") or 0), f"models.dev {src}")
    return out
