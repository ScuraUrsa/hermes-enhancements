"""One call interface for every model the routing table can name.

Model refs look like "<provider>:<model>", e.g. "ollama-cloud:gpt-oss:120b",
"groq:llama-3.3-70b-versatile", "gemini:gemini-2.5-flash-lite" or
"claude-code:haiku". Everything except claude-code is an OpenAI-compatible
/chat/completions endpoint. Every call is priced and appended to a spend
ledger so unattended work can be capped (Hermes' budget.py only sees Hermes
sessions, not these direct calls).
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


class LLMError(RuntimeError):
    pass


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    models: list[str] = field(default_factory=list)

    def add(self, model: str, i: int, o: int, cost: float) -> None:
        self.calls += 1
        self.input_tokens += i
        self.output_tokens += o
        self.cost_usd = round(self.cost_usd + cost, 6)
        if model not in self.models:
            self.models.append(model)


def split_ref(ref: str) -> tuple[str, str]:
    provider, _, model = ref.partition(":")
    if not model:
        raise LLMError(f"model ref needs 'provider:model', got {ref!r}")
    return provider, model


def price(cfg: dict, model: str, i: int, o: int) -> float:
    table = cfg.get("prices_per_mtok", {})
    pi, po = table.get(model) or table.get("_default", [0.5, 1.5])
    return (i * pi + o * po) / 1e6


def _image_part(path: Path) -> dict:
    data = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}}


def parse_json(text: str) -> dict:
    """Models wrap JSON in prose or fences now and then; take the outermost object."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise LLMError(f"no JSON object in model output: {text[:200]!r}")
    return json.loads(text[start : end + 1])


class Client:
    def __init__(self, cfg: dict, ledger: Path | None = None, tag: str = "manual"):
        self.cfg = cfg
        self.usage = Usage()
        self.ledger = ledger
        self.tag = tag  # "manual" (Filip asked) or "backlog" (idle work)

    # -- public -------------------------------------------------------------
    def json(self, ref: str, system: str, user: str, images: list[Path] | None = None, max_tokens: int = 4000) -> dict:
        text = self.complete(ref, system, user, images=images, json_mode=True, max_tokens=max_tokens)
        try:
            return parse_json(text)
        except (LLMError, json.JSONDecodeError):
            fix = self.complete(
                ref, "Return only valid JSON. No prose.", f"Fix this into valid JSON:\n{text[:20000]}",
                json_mode=True, max_tokens=max_tokens,
            )
            return parse_json(fix)

    def complete(self, ref: str, system: str, user: str, images: list[Path] | None = None,
                 json_mode: bool = False, max_tokens: int = 4000) -> str:
        provider, model = split_ref(ref)
        if provider == "claude-code":
            return self._claude_code(model, system, user, images)
        return self._openai_compat(provider, model, system, user, images or [], json_mode, max_tokens)

    # -- providers ----------------------------------------------------------
    def _openai_compat(self, provider, model, system, user, images, json_mode, max_tokens) -> str:
        import requests

        pcfg = self.cfg["providers"].get(provider)
        if not pcfg:
            raise LLMError(f"unknown provider {provider!r}")
        key = os.environ.get(pcfg.get("key_env") or "", "")
        if pcfg.get("key_env") and not key:
            raise LLMError(f"{pcfg['key_env']} not set for provider {provider}")
        content = [{"type": "text", "text": user}] + [_image_part(p) for p in images] if images else user
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        url = pcfg["base_url"].rstrip("/") + "/chat/completions"
        last = ""
        for attempt in range(4):
            r = requests.post(url, headers=headers, json=body, timeout=600)
            if r.status_code == 400 and "response_format" in body:
                body.pop("response_format")  # provider/model without JSON mode
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                last = f"{r.status_code}: {r.text[:200]}"
                time.sleep(min(60, 5 * 2**attempt))
                continue
            if r.status_code >= 400:
                raise LLMError(f"{provider}:{model} -> {r.status_code}: {r.text[:300]}")
            data = r.json()
            u = data.get("usage") or {}
            i, o = int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0)
            self._record(f"{provider}:{model}", model, i, o)
            return (data["choices"][0]["message"].get("content") or "").strip()
        raise LLMError(f"{provider}:{model} kept failing: {last}")

    def _claude_code(self, alias, system, user, images) -> str:
        """Claude Code CLI on the VM (Filip's subscription). Images are passed as
        file paths the CLI reads itself."""
        prompt = f"{system}\n\n{user}"
        cmd = ["claude", "-p", "--model", alias, "--output-format", "json"]
        if images:
            prompt += "\n\nImages to look at (read each file):\n" + "\n".join(str(p) for p in images)
            cmd += ["--allowedTools", "Read"]
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=1800, check=False)
        if r.returncode != 0:
            raise LLMError(f"claude-code exit {r.returncode}: {r.stderr[:300]}")
        out = json.loads(r.stdout)
        u = out.get("usage") or {}
        self.usage.add(f"claude-code:{alias}", int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0), 0.0)
        self._ledger(f"claude-code:{alias}", 0.0)
        return (out.get("result") or "").strip()

    def _record(self, ref: str, model: str, i: int, o: int) -> None:
        cost = price(self.cfg, model, i, o)
        self.usage.add(ref, i, o, cost)
        self._ledger(ref, cost, i, o)

    def _ledger(self, ref: str, cost: float, i: int = 0, o: int = 0) -> None:
        if not self.ledger:
            return
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "tag": self.tag, "model": ref,
               "input_tokens": i, "output_tokens": o, "cost_usd": round(cost, 6)}
        with self.ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")


def spent_today(ledger: Path, tag: str = "backlog") -> float:
    if not ledger.is_file():
        return 0.0
    today = datetime.now(timezone.utc).date().isoformat()
    total = 0.0
    for line in ledger.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("tag") == tag and str(rec.get("ts", "")).startswith(today):
            total += float(rec.get("cost_usd") or 0)
    return round(total, 4)
