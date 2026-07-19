#!/usr/bin/env python3
"""
POV #11: Langfuse Monitoring Integration for Hermes Agent
=========================================================
Tracing Hermes tool calls through Langfuse — open-source LLM observability.

Usage:
  # With Langfuse cloud (set env vars first):
  export LANGFUSE_PUBLIC_KEY="pk-..."
  export LANGFUSE_SECRET_KEY="sk-..."
  export LANGFUSE_HOST="https://cloud.langfuse.com"
  python3 demo.py

  # With self-hosted Langfuse:
  export LANGFUSE_PUBLIC_KEY="pk-..."
  export LANGFUSE_SECRET_KEY="sk-..."
  export LANGFUSE_HOST="http://localhost:3000"
  python3 demo.py

  # Without Langfuse (local file tracing fallback):
  python3 demo.py --local

Features:
  - Trace: full session (Hermes conversation)
  - Span: individual tool call (terminal, browser, web_search, etc.)
  - Generation: LLM API call (prompt → completion)
  - Score: token usage, latency, success/failure
  - Metadata: model name, tool name, session ID
"""

import os
import sys
import json
import time
import uuid
import functools
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, Dict

# ─── Langfuse client (lazy init) ────────────────────────────────────────────

_langfuse_client = None
_local_traces_dir = Path.home() / ".hermes" / "langfuse_traces"


def _get_langfuse():
    """Initialize Langfuse client if credentials are available."""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if public_key and secret_key:
        try:
            from langfuse import Langfuse
            _langfuse_client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
            print(f"✅ Langfuse connected: {host}")
            return _langfuse_client
        except Exception as e:
            print(f"⚠️  Langfuse init failed: {e}")
            return None
    return None


def _local_trace(trace_name: str, data: dict):
    """Fallback: write trace to local JSON file."""
    _local_traces_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    fname = f"{ts}_{trace_name.replace(' ', '_')}.json"
    fpath = _local_traces_dir / fname
    with open(fpath, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return str(fpath)


# ─── Hermes Tool Tracer ─────────────────────────────────────────────────────

class HermesTracer:
    """
    Wraps Langfuse tracing for Hermes Agent tool calls.

    Hierarchy:
      Trace (session) → Span (tool call) → Generation (LLM call)
    """

    def __init__(self, session_id: Optional[str] = None, user_id: str = "hermes-agent"):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.user_id = user_id
        self.trace_id = str(uuid.uuid4())
        self.trace_name = f"hermes-session-{self.session_id}"
        self.start_time = time.time()
        self.tool_calls = 0
        self.total_tokens = 0
        self.errors = 0

        lf = _get_langfuse()
        if lf:
            self.trace = lf.trace(
                id=self.trace_id,
                name=self.trace_name,
                user_id=self.user_id,
                session_id=self.session_id,
                metadata={
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "host": os.uname().nodename if hasattr(os, "uname") else "unknown",
                },
            )
        else:
            self.trace = None

    def tool_span(self, tool_name: str, input_data: Any = None):
        """Create a span for a tool call (context manager)."""
        return ToolSpan(self, tool_name, input_data)

    def generation(self, name: str, model: str, prompt: str, completion: str,
                   usage: Optional[dict] = None, latency_ms: float = 0):
        """Record an LLM generation."""
        self.tool_calls += 1
        tokens = (usage or {}).get("total_tokens", 0)
        self.total_tokens += tokens

        payload = {
            "name": name,
            "model": model,
            "input": prompt[:2000],
            "output": completion[:2000],
            "usage": usage or {},
            "latency_ms": latency_ms,
        }

        if self.trace:
            try:
                self.trace.generation(
                    name=name,
                    model=model,
                    input=prompt[:2000],
                    output=completion[:2000],
                    usage=usage,
                    metadata={"latency_ms": latency_ms},
                )
            except Exception as e:
                print(f"⚠️  Langfuse generation failed: {e}")

        return _local_trace(f"generation_{name}", payload)

    def score(self, name: str, value: float, comment: str = ""):
        """Attach a score to the trace."""
        if self.trace:
            try:
                self.trace.score(name=name, value=value, comment=comment)
            except Exception as e:
                print(f"⚠️  Langfuse score failed: {e}")

    def flush(self):
        """Flush all pending events to Langfuse."""
        lf = _get_langfuse()
        if lf:
            try:
                lf.flush()
                print("📤 Langfuse flushed")
            except Exception as e:
                print(f"⚠️  Langfuse flush failed: {e}")

    def summary(self) -> dict:
        """Return session summary."""
        elapsed = time.time() - self.start_time
        return {
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "duration_seconds": round(elapsed, 2),
            "tool_calls": self.tool_calls,
            "total_tokens": self.total_tokens,
            "errors": self.errors,
            "langfuse_connected": _get_langfuse() is not None,
        }


class ToolSpan:
    """Context manager for a single tool call span."""

    def __init__(self, tracer: HermesTracer, tool_name: str, input_data: Any = None):
        self.tracer = tracer
        self.tool_name = tool_name
        self.input_data = input_data
        self.span_id = str(uuid.uuid4())
        self.start = time.time()
        self.output = None
        self.error = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.time() - self.start) * 1000

        if exc_type:
            self.error = str(exc_val)
            self.tracer.errors += 1

        payload = {
            "span_id": self.span_id,
            "tool": self.tool_name,
            "input": str(self.input_data)[:2000] if self.input_data else None,
            "output": str(self.output)[:2000] if self.output else None,
            "error": self.error,
            "latency_ms": round(elapsed_ms, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self.tracer.trace:
            try:
                span = self.tracer.trace.span(
                    name=self.tool_name,
                    input=self.input_data,
                    output=self.output,
                    metadata={
                        "latency_ms": round(elapsed_ms, 2),
                        "error": self.error,
                    },
                )
                if self.error:
                    span.update(level="ERROR", status_message=self.error)
                span.end()
            except Exception as e:
                print(f"⚠️  Langfuse span failed: {e}")

        path = _local_trace(f"tool_{self.tool_name}", payload)
        status = "❌" if self.error else "✅"
        print(f"  {status} [{self.tool_name}] {elapsed_ms:.0f}ms → {path}")

        return False  # don't suppress exceptions


# ─── Demo: Simulate Hermes tool calls ───────────────────────────────────────

def simulate_hermes_session():
    """Simulate a Hermes Agent session with multiple tool calls."""
    print("=" * 60)
    print("🔍 Langfuse Monitoring — Hermes Agent Demo")
    print("=" * 60)

    tracer = HermesTracer(session_id="demo-" + str(uuid.uuid4())[:6])

    # --- Tool 1: web_search ---
    with tracer.tool_span("web_search", {"query": "Langfuse Python SDK tracing"}) as span:
        time.sleep(0.3)
        span.output = {"results": 5, "top_hit": "langfuse.com/docs"}

    # --- Tool 2: terminal ---
    with tracer.tool_span("terminal", {"command": "pip install langfuse"}) as span:
        time.sleep(0.5)
        span.output = {"exit_code": 0, "stdout": "Successfully installed langfuse-4.14.0"}

    # --- Tool 3: read_file ---
    with tracer.tool_span("read_file", {"path": "~/workspace/hermes-enhancements/README.md"}) as span:
        time.sleep(0.1)
        span.output = {"lines": 90, "size_bytes": 3717}

    # --- Tool 4: write_file ---
    with tracer.tool_span("write_file", {"path": "POV/11-langfuse-monitoring/demo.py"}) as span:
        time.sleep(0.2)
        span.output = {"written": True, "size_bytes": 8192}

    # --- Generation: LLM call ---
    prompt = "Zaimplementuj Langfuse monitoring dla Hermes Agent"
    completion = "Utworzono POV #11 z demo.py i README.md..."
    tracer.generation(
        name="hermes-chat",
        model="deepseek-v4-pro",
        prompt=prompt,
        completion=completion,
        usage={"prompt_tokens": 120, "completion_tokens": 45, "total_tokens": 165},
        latency_ms=1234,
    )

    # --- Score: session quality ---
    tracer.score("success_rate", 1.0, "All 4 tools succeeded")
    tracer.score("avg_latency_ms", 275, "Average tool latency")

    # --- Flush & summary ---
    tracer.flush()
    summary = tracer.summary()

    print("\n" + "=" * 60)
    print("📊 Session Summary")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k}: {v}")

    if not summary["langfuse_connected"]:
        print(f"\n💡 Local traces saved to: {_local_traces_dir}")
        print("   Set LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY to use Langfuse cloud.")

    return summary


# ─── Integration helper for real Hermes usage ────────────────────────────────

def trace_tool_call(tool_name: str, input_data: Any = None):
    """
    Decorator/context-manager helper for real Hermes tool calls.

    Usage in a Hermes plugin or skill:
        from demo import HermesTracer, trace_tool_call
        tracer = HermesTracer()
        with tracer.tool_span("web_search", query) as span:
            result = do_search(query)
            span.output = result
    """
    tracer = HermesTracer()
    return tracer.tool_span(tool_name, input_data)


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--local" in sys.argv:
        # Force local-only mode
        os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
        os.environ.pop("LANGFUSE_SECRET_KEY", None)
        print("📁 Local-only mode (no Langfuse server)\n")

    summary = simulate_hermes_session()

    # Record token usage via token monitor
    token_monitor = Path.home() / "workspace/hermes-enhancements/POV/04-token-monitor/ollama_token_monitor.py"
    if token_monitor.exists():
        import subprocess
        subprocess.run([
            "python3", str(token_monitor), "record",
            "POV #11 Langfuse demo prompt",
            "POV #11 Langfuse demo completion",
            "deepseek-v4-pro",
        ], capture_output=True)
        print("\n📊 Token monitor updated")
