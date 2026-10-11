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
    # per model ref: calls, tokens (incl. prompt cache), wall seconds and, for the
    # Claude Code CLI, what the same tokens would cost on the API (subscription = $0)
    by_model: dict = field(default_factory=dict)

    def add(self, model: str, i: int, o: int, cost: float, *, cache_read: int = 0, cache_write: int = 0,
            api_equiv_usd: float = 0.0, seconds: float = 0.0) -> None:
        self.calls += 1
        self.input_tokens += i
        self.output_tokens += o
        self.cost_usd = round(self.cost_usd + cost, 6)
        if model not in self.models:
            self.models.append(model)
        d = self.by_model.setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0,
                                             "cache_write_tokens": 0, "cost_usd": 0.0, "api_equiv_usd": 0.0, "seconds": 0.0})
        d["calls"] += 1
        d["input_tokens"] += i
        d["output_tokens"] += o
        d["cache_read_tokens"] += cache_read
        d["cache_write_tokens"] += cache_write
        d["cost_usd"] = round(d["cost_usd"] + cost, 6)
        d["api_equiv_usd"] = round(d["api_equiv_usd"] + api_equiv_usd, 6)
        d["seconds"] = round(d["seconds"] + seconds, 1)


def split_ref(ref: str) -> tuple[str, str]:
    """'ollama-cloud:gpt-oss:120b' -> ('ollama-cloud', 'gpt-oss:120b'); '@k=v' options are dropped."""
    provider, _, model = ref.split("@", 1)[0].partition(":")
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


def ref_options(ref: str) -> dict:
    """'gemini-video:gemini-2.5-flash-lite@fps=0.2' -> {'fps': '0.2'}"""
    _, _, opts = ref.partition("@")
    return dict(kv.split("=", 1) for kv in opts.split("@") if "=" in kv)


def parse_json(text: str) -> dict:
    """Models wrap JSON in prose or fences now and then; take the outermost object."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
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
        if provider == "gemini-video":
            raise LLMError("gemini-video refs are handled by the gemini_url analyzer")
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
        t0 = time.time()
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
            self._record(f"{provider}:{model}", model, i, o, seconds=round(time.time() - t0, 1))
            return (data["choices"][0]["message"].get("content") or "").strip()
        raise LLMError(f"{provider}:{model} kept failing: {last}")

    def _claude_code(self, alias, system, user, images) -> str:
        """Claude Code CLI on the VM (Filip's subscription). Images are passed as
        file paths the CLI reads itself."""
        import tempfile

        prompt = f"{system}\n\n{user}"
        cmd = ["claude", "-p", "--model", alias, "--output-format", "json"]
        if images:
            prompt += "\n\nImages to look at (read each file):\n" + "\n".join(str(Path(p).resolve()) for p in images)
            cmd += ["--allowedTools", "Read"]
            for d in sorted({str(Path(p).resolve().parent) for p in images}):
                cmd += ["--add-dir", d]  # the CLI only reads inside its working dirs
        # Subscription login only: an API key in the env would bill the API instead.
        env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        t0 = time.time()
        with tempfile.TemporaryDirectory(prefix="ytdigest-cc-") as cwd:  # no project CLAUDE.md/hooks
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=1800, check=False,
                               env=env, cwd=cwd)
        if r.returncode != 0:  # a usage limit arrives as JSON on stdout: keep its text for the pool
            try:
                msg = str(json.loads(r.stdout).get("result") or "")
            except (ValueError, AttributeError):
                msg = r.stdout or ""
            raise LLMError(f"claude-code exit {r.returncode}: {(msg + ' ' + (r.stderr or '')).strip()[:300]}")
        out = json.loads(r.stdout)
        if out.get("is_error"):
            raise LLMError(f"claude-code:{alias} -> {str(out.get('result'))[:300]}")
        u = out.get("usage") or {}
        i, o = int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0)
        cr, cw = int(u.get("cache_read_input_tokens") or 0), int(u.get("cache_creation_input_tokens") or 0)
        equiv = float(out.get("total_cost_usd") or 0.0)
        ref = f"claude-code:{alias}"
        self.usage.add(ref, i, o, 0.0, cache_read=cr, cache_write=cw, api_equiv_usd=equiv,
                       seconds=round(time.time() - t0, 1))
        self._ledger(ref, 0.0, i, o, extra={"cache_read": cr, "cache_write": cw, "api_equiv_usd": equiv})
        return (out.get("result") or "").strip()

    def _record(self, ref: str, model: str, i: int, o: int, seconds: float = 0.0) -> None:
        cost = price(self.cfg, model, i, o)
        self.usage.add(ref, i, o, cost, seconds=seconds)
        self._ledger(ref, cost, i, o)

    def _ledger(self, ref: str, cost: float, i: int = 0, o: int = 0, extra: dict | None = None) -> None:
        if not self.ledger:
            return
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "tag": self.tag, "model": ref,
               "input_tokens": i, "output_tokens": o, "cost_usd": round(cost, 6), **(extra or {})}
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


_MODEL_CACHE: dict[str, set[str] | None] = {}


def available_models(cfg: dict, provider: str) -> set[str] | None:
    """Model names the provider lists right now (OpenAI-compatible GET /models), or None
    when the list can't be fetched; callers then keep their refs as they are."""
    if provider in _MODEL_CACHE:
        return _MODEL_CACHE[provider]
    import requests

    names = None
    pcfg = (cfg.get("providers") or {}).get(provider)
    if pcfg:
        key = os.environ.get(pcfg.get("key_env") or "", "")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        try:
            r = requests.get(pcfg["base_url"].rstrip("/") + "/models", headers=headers, timeout=20)
            if r.ok:
                names = {m.get("id") for m in r.json().get("data") or [] if m.get("id")} or None
        except Exception:
            names = None
    _MODEL_CACHE[provider] = names
    return names


def live_refs(cfg: dict, refs: list[str], candidates: list[str] = ()) -> list[str]:
    """refs (then candidates) in order, minus models their provider no longer lists."""
    out = []
    for ref in [*refs, *candidates]:
        if not ref or ref in out:
            continue
        provider, model = split_ref(ref)
        names = available_models(cfg, provider) if provider.startswith("ollama-cloud") else None
        if names is None or model in names:
            out.append(ref)
    return out
