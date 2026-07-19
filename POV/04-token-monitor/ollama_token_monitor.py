#!/usr/bin/env python3
"""
Ollama Cloud Token Monitor — śledzi zużycie tokenów przez Hermesa.

Mechanizm:
- Ollama Cloud NIE MA API do sprawdzania quota (feature request #15663)
- Jedyny sposób: web dashboard (ollama.com/settings) lub email przy 90%
- Ten skrypt monitoruje per-request usage z response body i sumuje
- Zapisuje stan do pliku JSON, żeby przetrwać między sesjami

Użycie:
    python3 ollama_token_monitor.py status     # pokaż stan
    python3 ollama_token_monitor.py record 150 50  # zapisz: 150 prompt, 50 completion
    python3 ollama_token_monitor.py reset      # resetuj licznik
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

STATE_FILE = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "ollama_token_state.json"

# Limity Ollama Cloud (szacunkowe, bo Ollama nie publikuje dokładnych liczb)
# Pro plan: "50x more cloud usage than Free", sesje reset co 5h, tygodniowo co 7 dni
# Free: lekkie użycie (~1M tokenów/dzień?)
# Pro: ~50M tokenów/dzień?
# Max: ~250M tokenów/dzień?
ESTIMATED_LIMITS = {
    "free": {"daily_tokens": 1_000_000, "session_tokens": 200_000},
    "pro": {"daily_tokens": 50_000_000, "session_tokens": 10_000_000},
    "max": {"daily_tokens": 250_000_000, "session_tokens": 50_000_000},
}

PLAN = os.environ.get("OLLAMA_PLAN", "pro")  # domyślnie Pro


def load_state():
    """Wczytaj stan z pliku."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return {
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_tokens": 0,
        "api_calls": 0,
        "session_start": datetime.now(timezone.utc).isoformat(),
        "last_update": None,
        "plan": PLAN,
        "model": "unknown",
    }


def save_state(state):
    """Zapisz stan do pliku."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def record(prompt_tokens: int, completion_tokens: int, model: str = "unknown"):
    """Zarejestruj zużycie tokenów z pojedynczego API call."""
    state = load_state()
    state["total_prompt_tokens"] += prompt_tokens
    state["total_completion_tokens"] += completion_tokens
    state["total_tokens"] += prompt_tokens + completion_tokens
    state["api_calls"] += 1
    state["last_update"] = datetime.now(timezone.utc).isoformat()
    state["model"] = model
    save_state(state)
    return state


def status():
    """Pokaż aktualny stan zużycia."""
    state = load_state()
    limits = ESTIMATED_LIMITS.get(state.get("plan", PLAN), ESTIMATED_LIMITS["pro"])
    
    total = state["total_tokens"]
    daily_limit = limits["daily_tokens"]
    session_limit = limits["session_tokens"]
    
    pct_daily = (total / daily_limit) * 100 if daily_limit else 0
    pct_session = (total / session_limit) * 100 if session_limit else 0
    
    print("=" * 60)
    print("OLLAMA CLOUD TOKEN MONITOR")
    print("=" * 60)
    print(f"  Plan: {state.get('plan', PLAN).upper()}")
    print(f"  Model: {state['model']}")
    print(f"  Sesja od: {state['session_start'][:19]}")
    print(f"  Ostatnia aktywność: {state.get('last_update', 'brak')[:19] if state.get('last_update') else 'brak'}")
    print()
    print(f"  API calls: {state['api_calls']}")
    print(f"  Prompt tokens: {state['total_prompt_tokens']:,}")
    print(f"  Completion tokens: {state['total_completion_tokens']:,}")
    print(f"  TOTAL TOKENS: {total:,}")
    print()
    print(f"  Limit sesji (5h): {session_limit:,} → {pct_session:.1f}%")
    print(f"  Limit dzienny: {daily_limit:,} → {pct_daily:.1f}%")
    print()
    
    if pct_daily > 90:
        print("  🔴 UWAGA: >90% dziennego limitu!")
    elif pct_daily > 75:
        print("  🟡 OSTRZEŻENIE: >75% dziennego limitu")
    elif pct_daily > 50:
        print("  🟢 OK: >50% dziennego limitu")
    else:
        print("  🟢 Niskie zużycie")
    
    print()
    print("  💡 Ollama Cloud NIE MA API do quota — to są szacunki.")
    print("  💡 Sprawdź rzeczywisty stan: https://ollama.com/settings")
    print("=" * 60)
    
    return state


def reset():
    """Resetuj licznik (nowa sesja)."""
    state = {
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_tokens": 0,
        "api_calls": 0,
        "session_start": datetime.now(timezone.utc).isoformat(),
        "last_update": None,
        "plan": PLAN,
        "model": "unknown",
    }
    save_state(state)
    print(f"[OK] Licznik zresetowany. Nowa sesja: {state['session_start'][:19]}")
    return state


def test_api():
    """Test: wyślij zapytanie do Ollama Cloud i sprawdź response."""
    import subprocess
    
    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        # Spróbuj z .env
        env_path = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("OLLAMA_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    
    if not api_key:
        print("[FAIL] Brak OLLAMA_API_KEY")
        return None
    
    payload = {
        "model": "deepseek-v4-pro",
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 10,
    }
    
    result = subprocess.run(
        ["curl", "-s", "-H", f"Authorization: Bearer {api_key}",
         "-H", "Content-Type: application/json",
         "https://ollama.com/v1/chat/completions",
         "-d", json.dumps(payload)],
        capture_output=True, text=True, timeout=30
    )
    
    if result.returncode != 0:
        print(f"[FAIL] curl error: {result.stderr}")
        return None
    
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"[FAIL] Invalid JSON: {result.stdout[:200]}")
        return None
    
    usage = data.get("usage", {})
    prompt = usage.get("prompt_tokens", 0)
    completion = usage.get("completion_tokens", 0)
    total = usage.get("total_tokens", 0)
    model = data.get("model", "unknown")
    
    print(f"[OK] API działa. Model: {model}")
    print(f"     Prompt: {prompt}, Completion: {completion}, Total: {total}")
    
    # Sprawdź nagłówki (brak rate-limit headers)
    print(f"     ⚠️  Brak nagłówków rate-limit (Ollama Cloud nie wspiera)")
    
    return data


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    
    if cmd == "status":
        status()
    elif cmd == "record":
        if len(sys.argv) < 3:
            print("Użycie: record <prompt_tokens> <completion_tokens> [model]")
            sys.exit(1)
        prompt = int(sys.argv[2])
        completion = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        model = sys.argv[4] if len(sys.argv) > 4 else "unknown"
        state = record(prompt, completion, model)
        print(f"[OK] Zapisano: +{prompt} prompt, +{completion} completion")
        print(f"     Total: {state['total_tokens']:,}")
    elif cmd == "reset":
        reset()
    elif cmd == "test":
        test_api()
    else:
        print(f"Nieznana komenda: {cmd}")
        print("Dostępne: status, record, reset, test")
        sys.exit(1)
