"""Model adapters. A model ref is ``<provider>:<model>``, e.g. ``ollama-cloud:gemma3:27b``
or ``claude-code:haiku``; the provider part is looked up in ``providers.toml``.

Kinds:
  openai_compat  Ollama Cloud / local Ollama / DeepSeek / OpenRouter / Groq / Gemini's OpenAI endpoint
  claude_code    ``claude -p`` on Filip's Claude subscription (CLAUDE_CODE_OAUTH_TOKEN) or an API key
  anthropic      Messages API with an API key (optional; the subscription route is the default)
  gemini_video   Gemini generateContent with the YouTube URL as video input (the "no pipeline" baseline)
  mock           deterministic fake for tests

Only the standard library is used so the harness runs on the Hermes VM without a venv.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import shutil
import subprocess
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_PROVIDERS = Path(__file__).resolve().parent.parent / "providers.toml"


@dataclass
class Completion:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_sec: float = 0.0
    reported_cost_usd: float | None = None  # what the provider itself says (Claude Code does)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderConfig:
    name: str
    kind: str
    base_url: str | None = None
    api_key_env: str | None = None
    billing: str = "api"  # api | subscription | local
    timeout_sec: int = 600
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env) if self.api_key_env else None


class ProviderError(RuntimeError):
    pass


def load_providers(path: Path | None = None) -> dict[str, ProviderConfig]:
    data = tomllib.loads(Path(path or DEFAULT_PROVIDERS).read_text())
    out = {}
    for name, cfg in (data.get("providers") or {}).items():
        cfg = dict(cfg)
        out[name] = ProviderConfig(
            name=name,
            kind=cfg.pop("kind"),
            base_url=cfg.pop("base_url", None),
            api_key_env=cfg.pop("api_key_env", None),
            billing=cfg.pop("billing", "api"),
            timeout_sec=int(cfg.pop("timeout_sec", 600)),
            extra=cfg,
        )
    return out


def split_ref(ref: str) -> tuple[str, str]:
    """``provider:model[@k=v,k=v]`` -> (provider, model). Options are read with ``ref_options``."""
    base = ref.split("@", 1)[0]
    provider, sep, model = base.partition(":")
    if not sep or not model:
        raise ValueError(f"model ref must be <provider>:<model>[@k=v,...], got {ref!r}")
    return provider, model


def base_ref(ref: str) -> str:
    return ref.split("@", 1)[0]


def ref_options(ref: str) -> dict[str, str]:
    """Per-candidate knobs, e.g. ``gemini-video:gemini-2.5-flash-lite@fps=0.2`` or ``...@frames=none``."""
    if "@" not in ref:
        return {}
    out = {}
    for kv in ref.split("@", 1)[1].split(","):
        k, _, v = kv.partition("=")
        if k.strip():
            out[k.strip()] = v.strip()
    return out


# --------------------------------------------------------------------------------------------
class Model:
    """One model on one provider."""

    def __init__(self, ref: str, cfg: ProviderConfig):
        self.ref = ref
        self.cfg = cfg
        self.model = split_ref(ref)[1]
        self.opts = ref_options(ref)

    def complete(self, system: str, user: str, images: list[Path] | None = None, *, json_mode: bool = False,
                 max_tokens: int = 4096, video_url: str | None = None) -> Completion:
        raise NotImplementedError

    supports_images = True
    supports_video_url = False


def _http_json(url: str, payload: dict, headers: dict[str, str], timeout: int) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **headers})
    attempts = 4
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read()[:500].decode(errors="replace")
            if e.code in (429, 500, 502, 503, 504) and i < attempts - 1:
                time.sleep(min(60, 4 * 2**i))
                continue
            raise ProviderError(f"HTTP {e.code} from {url}: {detail}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if i < attempts - 1:
                time.sleep(min(60, 4 * 2**i))
                continue
            raise ProviderError(f"{url}: {e}") from e
    raise ProviderError("unreachable")


def _data_url(path: Path) -> tuple[str, str]:
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    return mime, base64.b64encode(Path(path).read_bytes()).decode()


class OpenAICompat(Model):
    def complete(self, system, user, images=None, *, json_mode=False, max_tokens=4096, video_url=None):
        if video_url:
            raise ProviderError(f"{self.ref} cannot take a video URL")
        content: list[dict] | str
        if images:
            content = [{"type": "text", "text": user}]
            for p in images:
                mime, b64 = _data_url(p)
                content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        else:
            content = user
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
            "max_tokens": max_tokens,
            "temperature": self.cfg.extra.get("temperature", 0.2),
        }
        if json_mode and self.cfg.extra.get("json_mode", True):
            payload["response_format"] = {"type": "json_object"}
        headers = {}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        t0 = time.monotonic()
        r = _http_json(self.cfg.base_url.rstrip("/") + "/chat/completions", payload, headers, self.cfg.timeout_sec)
        dt = time.monotonic() - t0
        try:
            text = r["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError) as e:
            raise ProviderError(f"{self.ref}: unexpected response {str(r)[:300]}") from e
        u = r.get("usage") or {}
        return Completion(text, u.get("prompt_tokens"), u.get("completion_tokens"), dt,
                          meta={"finish_reason": r["choices"][0].get("finish_reason")})


class ClaudeCode(Model):
    """``claude -p`` headless. Images are given as file paths the model opens with its Read tool."""

    def complete(self, system, user, images=None, *, json_mode=False, max_tokens=4096, video_url=None):
        if video_url:
            raise ProviderError("claude-code cannot take a video URL")
        binary = self.cfg.extra.get("binary") or shutil.which("claude")
        if not binary:
            raise ProviderError("claude CLI not found on PATH")
        with tempfile.TemporaryDirectory(prefix="vbench-cc-") as tmp:
            tmpd = Path(tmp)
            prompt = user
            if images:
                img_dir = tmpd / "frames"
                img_dir.mkdir()
                names = []
                for i, p in enumerate(images):
                    dst = img_dir / f"{i:03d}{Path(p).suffix or '.jpg'}"
                    shutil.copyfile(p, dst)
                    names.append(str(dst))
                prompt += ("\n\nThe frames are image files. Open every one of them with the Read tool, in order, "
                           "before answering:\n" + "\n".join(names))
            cfg_dir = tmpd / "claude-config"
            cfg_dir.mkdir()
            env = {**os.environ, "CLAUDE_CONFIG_DIR": str(cfg_dir), "DISABLE_AUTOUPDATER": "1",
                   "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
            if self.cfg.api_key_env and os.environ.get(self.cfg.api_key_env):
                env["CLAUDE_CODE_OAUTH_TOKEN"] = os.environ[self.cfg.api_key_env]
            argv = [binary, "-p", "--output-format", "json", "--model", self.model,
                    "--system-prompt", system,  # replace Claude Code's own prompt: fairer cost, no coding persona "--max-turns", str(len(images or []) + 3),
                    "--allowedTools", "Read", "--permission-mode", "default"]
            effort = self.opts.get("effort") or self.cfg.extra.get("effort")
            if effort:
                argv += ["--effort", str(effort)]
            t0 = time.monotonic()
            try:
                cp = subprocess.run(argv, input=prompt, capture_output=True, text=True, cwd=tmpd, env=env,
                                    timeout=self.cfg.timeout_sec)
            except subprocess.TimeoutExpired as e:
                raise ProviderError(f"{self.ref}: timed out after {self.cfg.timeout_sec}s") from e
            dt = time.monotonic() - t0
        try:
            res = json.loads(cp.stdout)
        except json.JSONDecodeError as e:
            raise ProviderError(f"{self.ref}: exit {cp.returncode}: {cp.stderr[-400:] or cp.stdout[-400:]}") from e
        if res.get("is_error"):
            raise ProviderError(f"{self.ref}: {res.get('subtype')}: {str(res.get('result'))[:300]}")
        u = res.get("usage") or {}
        inp = sum(u.get(k) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        return Completion(res.get("result") or "", inp or None, u.get("output_tokens"), dt,
                          reported_cost_usd=res.get("total_cost_usd"), meta={"turns": res.get("num_turns")})


class AnthropicAPI(Model):
    """Messages API through the official SDK (``pip install anthropic``); used only with an API key."""

    def complete(self, system, user, images=None, *, json_mode=False, max_tokens=4096, video_url=None):
        if video_url:
            raise ProviderError("anthropic cannot take a video URL")
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover - optional dependency
            raise ProviderError("pip install anthropic to use the anthropic provider") from e
        client = anthropic.Anthropic(api_key=self.cfg.api_key) if self.cfg.api_key else anthropic.Anthropic()
        content: list[dict] = []
        for p in images or []:
            mime, b64 = _data_url(p)
            content.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}})
        content.append({"type": "text", "text": user})
        kwargs: dict[str, Any] = {}
        effort = self.opts.get("effort") or self.cfg.extra.get("effort")
        if effort:
            kwargs["output_config"] = {"effort": effort}
        t0 = time.monotonic()
        msg = client.messages.create(model=self.model, max_tokens=max(max_tokens, 8000), system=system,
                                     messages=[{"role": "user", "content": content}], **kwargs)
        dt = time.monotonic() - t0
        if msg.stop_reason == "refusal":
            raise ProviderError(f"{self.ref}: refusal")
        text = "".join(b.text for b in msg.content if b.type == "text")
        return Completion(text, msg.usage.input_tokens, msg.usage.output_tokens, dt)


class GeminiVideo(Model):
    """Gemini watching the YouTube URL itself: no transcript or frames needed. Baseline track."""

    supports_video_url = True

    def complete(self, system, user, images=None, *, json_mode=False, max_tokens=4096, video_url=None):
        parts: list[dict] = []
        if video_url:
            part: dict[str, Any] = {"file_data": {"file_uri": video_url, "mime_type": "video/*"}}
            if self.opts.get("fps"):
                part["video_metadata"] = {"fps": float(self.opts["fps"])}
            parts.append(part)
        for p in images or []:
            mime, b64 = _data_url(p)
            parts.append({"inline_data": {"mime_type": mime, "data": b64}})
        parts.append({"text": user})
        payload: dict[str, Any] = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2},
        }
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"
        res = self.opts.get("res") or self.cfg.extra.get("media_resolution")
        if res:
            payload["generationConfig"]["mediaResolution"] = (res if res.startswith("MEDIA_") else
                                                              f"MEDIA_RESOLUTION_{res.upper()}")
        base = (self.cfg.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        t0 = time.monotonic()
        r = _http_json(f"{base}/models/{self.model}:generateContent", payload,
                       {"x-goog-api-key": self.cfg.api_key or ""}, self.cfg.timeout_sec)
        dt = time.monotonic() - t0
        try:
            text = "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError) as e:
            raise ProviderError(f"{self.ref}: unexpected response {str(r)[:300]}") from e
        u = r.get("usageMetadata") or {}
        return Completion(text, u.get("promptTokenCount"), u.get("candidatesTokenCount"), dt)


class Mock(Model):
    """Deterministic fake. ``mock:echo`` answers from canned JSON keyed by the prompt's stage marker."""

    responses: dict[str, str] = {}

    def complete(self, system, user, images=None, *, json_mode=False, max_tokens=4096, video_url=None):
        for marker, text in self.responses.items():
            if marker in system or marker in user:
                return Completion(text, len(user) // 4, len(text) // 4, 0.01)
        return Completion("{}", len(user) // 4, 1, 0.01)


def list_live_models(cfg: ProviderConfig, timeout: int = 30) -> set[str] | None:
    """Model ids the provider serves right now (OpenAI-compatible ``GET /models``), or None if it
    can't be asked. Ollama Cloud retires models without notice (a retired one answers HTTP 410)."""
    if cfg.kind != "openai_compat" or not cfg.base_url:
        return None
    headers = {"Authorization": f"Bearer {cfg.api_key}"} if cfg.api_key else {}
    req = urllib.request.Request(cfg.base_url.rstrip("/") + "/models", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    return {m.get("id") for m in data.get("data") or [] if m.get("id")}


KINDS = {"openai_compat": OpenAICompat, "claude_code": ClaudeCode, "anthropic": AnthropicAPI,
         "gemini_video": GeminiVideo, "mock": Mock}


def get_model(ref: str, providers: dict[str, ProviderConfig]) -> Model:
    pname, _ = split_ref(ref)
    if pname not in providers:
        raise ValueError(f"unknown provider {pname!r} in {ref!r}; known: {sorted(providers)}")
    cfg = providers[pname]
    try:
        cls = KINDS[cfg.kind]
    except KeyError as e:
        raise ValueError(f"provider {pname}: unknown kind {cfg.kind!r}") from e
    return cls(ref, cfg)
