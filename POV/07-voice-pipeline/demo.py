#!/usr/bin/env python3
"""
POV #7: Real-time Voice Pipeline
=================================
WebSocket server do real-time voice: STT → Hermes → TTS

Architektura:
  Klient (przeglądarka/aplikacja) → WebSocket → Serwer
    1. Klient wysyła audio (WAV bytes) → faster-whisper STT → tekst
    2. Tekst → Hermes Agent (deepseek-v4-pro) → odpowiedź
    3. Odpowiedź → ElevenLabs TTS → audio MP3 → klient

Wymagania:
  - pip install websockets faster-whisper elevenlabs
  - ELEVENLABS_API_KEY (z Bitwarden lub env)
  - faster-whisper model (auto-download przy pierwszym użyciu)

Użycie:
  python3 demo.py                    # start serwera (domyślnie port 8765)
  python3 demo.py --port 9000        # custom port
  python3 demo.py --mock             # mock mode (bez STT/TTS — tylko echo)
  python3 demo.py --test             # test offline (bez WebSocket)
"""

import asyncio
import json
import os
import sys
import time
import struct
import io
import wave
import subprocess
import argparse
from pathlib import Path

# ─── Konfiguracja ───────────────────────────────────────────────

DEFAULT_PORT = 8765
WHISPER_MODEL = "base"  # tiny/base/small/medium/large-v3
ELEVENLABS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George
ELEVENLABS_MODEL = "eleven_multilingual_v2"
ELEVENLABS_SECRET_ID = "893e302b-cd6b-4b40-aaea-b47b01615bb2"

# ─── API Key helpers ────────────────────────────────────────────

def get_elevenlabs_key():
    """Pobiera ElevenLabs API key z env lub Bitwarden."""
    key = os.environ.get("ELEVENLABS_API_KEY")
    if key:
        return key
    try:
        result = subprocess.run(
            ["bws", "secret", "get", ELEVENLABS_SECRET_ID,
             "--server-url", "https://vault.bitwarden.eu"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return json.loads(result.stdout)["value"]
    except Exception as e:
        print(f"[WARN] Bitwarden fallback failed: {e}", file=sys.stderr)
    return None


# ─── STT: faster-whisper ────────────────────────────────────────

class WhisperSTT:
    """Lokalny STT z faster-whisper (offline, bez API)."""

    def __init__(self, model_size=WHISPER_MODEL):
        self.model = None
        self.model_size = model_size

    def load(self):
        if self.model is None:
            from faster_whisper import WhisperModel
            print(f"[STT] Ładowanie modelu faster-whisper ({self.model_size})...")
            self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            print("[STT] Model gotowy.")
        return self.model

    def transcribe(self, audio_bytes: bytes) -> str:
        """Transkrybuje audio WAV bytes → tekst."""
        model = self.load()
        # Zapisz tymczasowo do pliku (faster-whisper wymaga pliku lub numpy array)
        tmp_path = "/tmp/hermes_stt_input.wav"
        Path(tmp_path).write_bytes(audio_bytes)

        segments, info = model.transcribe(tmp_path, beam_size=5, language="pl")
        text = " ".join(seg.text for seg in segments).strip()

        detected_lang = info.language
        prob = info.language_probability
        print(f"[STT] Transkrypcja: '{text}' (lang={detected_lang}, prob={prob:.2f})")
        return text


# ─── TTS: ElevenLabs ────────────────────────────────────────────

class ElevenLabsTTS:
    """ElevenLabs Text-to-Speech."""

    def __init__(self, api_key=None):
        self.api_key = api_key or get_elevenlabs_key()
        self.client = None

    def _get_client(self):
        if self.client is None and self.api_key:
            from elevenlabs import ElevenLabs
            self.client = ElevenLabs(api_key=self.api_key)
        return self.client

    def synthesize(self, text: str) -> bytes:
        """Generuje audio MP3 z tekstu → bytes."""
        client = self._get_client()
        if not client:
            raise RuntimeError("Brak ElevenLabs API key")

        print(f"[TTS] Generowanie audio dla: '{text[:80]}...'")
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=ELEVENLABS_VOICE_ID,
            model_id=ELEVENLABS_MODEL,
            output_format="mp3_44100_128",
        )
        audio_bytes = b"".join(audio)
        print(f"[TTS] Wygenerowano {len(audio_bytes)} bajtów audio")
        return audio_bytes


# ─── Hermes Agent (mock / real) ─────────────────────────────────

class HermesAgent:
    """Proxy do Hermes Agent — przetwarza tekst i zwraca odpowiedź."""

    def __init__(self, mock=False):
        self.mock = mock

    async def process(self, text: str) -> str:
        """Przetwarza tekst przez Hermesa i zwraca odpowiedź."""
        if self.mock:
            # Mock: echo z prefixem
            response = f"Hermes słyszy: '{text}'. To jest odpowiedź mock — podłącz prawdziwego agenta przez API."
            print(f"[HERMES] Mock response: '{response[:80]}...'")
            return response

        # Real: wywołanie Hermes Agent API (ollama-cloud / deepseek-v4-pro)
        # W produkcji: HTTP POST do endpointu Hermesa
        try:
            import urllib.request
            data = json.dumps({
                "model": "deepseek-v4-pro",
                "messages": [{"role": "user", "content": text}],
                "stream": False,
            }).encode()
            req = urllib.request.Request(
                "https://api.ollama.ai/v1/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {os.environ.get('OLLAMA_API_KEY', '')}"
                }
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                response = result["choices"][0]["message"]["content"]
                print(f"[HERMES] Response: '{response[:80]}...'")
                return response
        except Exception as e:
            print(f"[HERMES] API error: {e}, fallback to mock")
            return f"[Hermes fallback] Przetworzono: '{text}' — błąd API: {e}"


# ─── WebSocket Server ───────────────────────────────────────────

class VoicePipelineServer:
    """WebSocket server: audio → STT → Hermes → TTS → audio."""

    def __init__(self, mock=False, port=DEFAULT_PORT):
        self.mock = mock
        self.port = port
        self.stt = None if mock else WhisperSTT()
        self.tts = None if mock else ElevenLabsTTS()
        self.hermes = HermesAgent(mock=mock)

    async def handle_client(self, websocket):
        """Obsługa pojedynczego klienta WebSocket."""
        client_addr = websocket.remote_address
        print(f"\n[WS] Nowy klient: {client_addr}")

        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    # Audio bytes → STT
                    if self.mock:
                        text = f"[mock audio {len(message)} bytes]"
                        print(f"[WS] Odebrano audio: {len(message)} bajtów (mock)")
                    else:
                        print(f"[WS] Odebrano audio: {len(message)} bajtów")
                        text = self.stt.transcribe(message)

                    # STT → Hermes
                    response_text = await self.hermes.process(text)

                    # Hermes → TTS
                    if self.mock:
                        audio_out = f"[mock audio for: {response_text[:50]}]".encode()
                        await websocket.send(json.dumps({
                            "type": "text",
                            "text": response_text,
                            "input": text,
                        }))
                    else:
                        audio_out = self.tts.synthesize(response_text)
                        # Wyślij audio + metadane
                        await websocket.send(json.dumps({
                            "type": "audio_ready",
                            "text": response_text,
                            "input": text,
                            "audio_size": len(audio_out),
                        }))
                        await websocket.send(audio_out)

                elif isinstance(message, str):
                    # Text message (tryb tekstowy)
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        data = {"text": message}

                    text = data.get("text", message)
                    print(f"[WS] Tekst: '{text[:80]}...'")

                    response_text = await self.hermes.process(text)

                    if self.mock:
                        await websocket.send(json.dumps({
                            "type": "text",
                            "text": response_text,
                            "input": text,
                        }))
                    else:
                        audio_out = self.tts.synthesize(response_text)
                        await websocket.send(json.dumps({
                            "type": "audio_ready",
                            "text": response_text,
                            "input": text,
                            "audio_size": len(audio_out),
                        }))
                        await websocket.send(audio_out)

        except Exception as e:
            print(f"[WS] Błąd klienta {client_addr}: {e}")
        finally:
            print(f"[WS] Klient rozłączony: {client_addr}")

    async def start(self):
        """Uruchamia serwer WebSocket."""
        import websockets
        print(f"\n{'='*60}")
        print(f"POV #7: Voice Pipeline Server")
        print(f"{'='*60}")
        print(f"  Port: {self.port}")
        print(f"  STT:  {'mock' if self.mock else 'faster-whisper (' + WHISPER_MODEL + ')'}")
        print(f"  TTS:  {'mock' if self.mock else 'ElevenLabs (George)'}")
        print(f"  Hermes: {'mock' if self.mock else 'deepseek-v4-pro'}")
        print(f"{'='*60}")
        print(f"\nNasłuchuję na ws://0.0.0.0:{self.port}")
        print("Klient HTML: otwórz client.html w przeglądarce")
        print("Test CLI:   python3 demo.py --test")
        print()

        async with websockets.serve(self.handle_client, "0.0.0.0", self.port):
            await asyncio.Future()  # run forever


# ─── Test offline ────────────────────────────────────────────────

async def test_offline(mock=False):
    """Testuje pipeline bez WebSocket — bezpośrednie wywołania."""
    print(f"\n{'='*60}")
    print("TEST OFFLINE: Voice Pipeline")
    print(f"{'='*60}")

    hermes = HermesAgent(mock=mock)

    # Test 1: STT (jeśli nie mock)
    if not mock:
        print("\n--- Test STT (faster-whisper) ---")
        stt = WhisperSTT()
        # Generuj prosty WAV z ciszą (test tylko ładuje model)
        stt.load()
        print("[OK] STT model załadowany")

    # Test 2: TTS (jeśli nie mock)
    if not mock:
        print("\n--- Test TTS (ElevenLabs) ---")
        tts = ElevenLabsTTS()
        if tts.api_key:
            audio = tts.synthesize("Cześć! Tu Hermes. Testuję voice pipeline.")
            out_path = "/tmp/hermes_voice_pipeline_test.mp3"
            Path(out_path).write_bytes(audio)
            print(f"[OK] Audio zapisane: {out_path} ({len(audio)} bajtów)")
        else:
            print("[SKIP] Brak ElevenLabs API key")

    # Test 3: Hermes
    print("\n--- Test Hermes Agent ---")
    response = await hermes.process("Cześć, jak się masz?")
    print(f"[OK] Hermes odpowiedział: '{response[:100]}...'")

    # Test 4: Full pipeline (tekst → Hermes → TTS)
    if not mock:
        print("\n--- Test Full Pipeline (tekst → Hermes → TTS) ---")
        tts = ElevenLabsTTS()
        if tts.api_key:
            text = "Opowiedz krótko o sztucznej inteligencji."
            response = await hermes.process(text)
            audio = tts.synthesize(response)
            out_path = "/tmp/hermes_full_pipeline_test.mp3"
            Path(out_path).write_bytes(audio)
            print(f"[OK] Full pipeline: {out_path} ({len(audio)} bajtów)")
        else:
            print("[SKIP] Brak ElevenLabs API key")

    print(f"\n{'='*60}")
    print("TEST ZAKOŃCZONY")
    print(f"{'='*60}")


# ─── Client HTML generator ───────────────────────────────────────

def generate_client_html(port=DEFAULT_PORT):
    """Generuje plik client.html do testowania w przeglądarce."""
    html = f'''<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hermes Voice Pipeline — Client</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 600px; margin: 2rem auto; padding: 1rem; }}
  h1 {{ color: #6366f1; }}
  button {{ padding: 0.75rem 1.5rem; margin: 0.5rem; border: none; border-radius: 8px; cursor: pointer; font-size: 1rem; }}
  .record {{ background: #ef4444; color: white; }}
  .stop {{ background: #6b7280; color: white; }}
  .send {{ background: #6366f1; color: white; }}
  #status {{ padding: 1rem; margin: 1rem 0; border-radius: 8px; background: #f3f4f6; }}
  #log {{ background: #1f2937; color: #e5e7eb; padding: 1rem; border-radius: 8px; min-height: 200px; font-family: monospace; font-size: 0.85rem; white-space: pre-wrap; }}
  input {{ width: 100%; padding: 0.75rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 1rem; margin: 0.5rem 0; }}
  audio {{ width: 100%; margin: 0.5rem 0; }}
</style>
</head>
<body>
<h1>🎤 Hermes Voice Pipeline</h1>
<div id="status">🔌 Rozłączony</div>

<input type="text" id="textInput" placeholder="Wpisz tekst i wyślij..." />
<button class="send" onclick="sendText()">📤 Wyślij tekst</button>

<div style="margin: 1rem 0;">
  <button class="record" id="recordBtn" onclick="toggleRecord()">🎙️ Nagraj audio</button>
  <button class="stop" id="stopBtn" onclick="toggleRecord()" style="display:none">⏹️ Zatrzymaj</button>
</div>

<audio id="audioPlayer" controls style="display:none"></audio>
<div id="log">Oczekiwanie na połączenie...</div>

<script>
const WS_URL = 'ws://localhost:{port}';
let ws = null;
let mediaRecorder = null;
let audioChunks = [];

function log(msg) {{
  const el = document.getElementById('log');
  el.textContent += '\\n' + new Date().toLocaleTimeString() + ' ' + msg;
  el.scrollTop = el.scrollHeight;
}}

function connect() {{
  ws = new WebSocket(WS_URL);
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {{
    document.getElementById('status').textContent = '🟢 Połączony';
    log('Połączono z serwerem');
  }};

  ws.onmessage = (event) => {{
    if (typeof event.data === 'string') {{
      const msg = JSON.parse(event.data);
      if (msg.type === 'audio_ready') {{
        log('📥 Otrzymano audio: ' + msg.text.substring(0, 60) + '...');
      }} else if (msg.type === 'text') {{
        log('📝 Hermes: ' + msg.text);
      }}
    }} else {{
      // Audio bytes
      const blob = new Blob([event.data], {{ type: 'audio/mpeg' }});
      const url = URL.createObjectURL(blob);
      const player = document.getElementById('audioPlayer');
      player.src = url;
      player.style.display = 'block';
      player.play();
      log('🔊 Odtwarzam audio (' + event.data.byteLength + ' bajtów)');
    }}
  }};

  ws.onclose = () => {{
    document.getElementById('status').textContent = '🔌 Rozłączony';
    log('Rozłączono');
    setTimeout(connect, 3000);
  }};

  ws.onerror = (e) => {{
    log('❌ Błąd WebSocket');
  }};
}}

function sendText() {{
  const input = document.getElementById('textInput');
  const text = input.value.trim();
  if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({{ text: text }}));
  log('📤 Wysłano: ' + text);
  input.value = '';
}}

function toggleRecord() {{
  if (mediaRecorder && mediaRecorder.state === 'recording') {{
    mediaRecorder.stop();
    document.getElementById('recordBtn').style.display = 'inline-block';
    document.getElementById('stopBtn').style.display = 'none';
  }} else {{
    navigator.mediaDevices.getUserMedia({{ audio: true }}).then(stream => {{
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.onstop = () => {{
        const blob = new Blob(audioChunks, {{ type: 'audio/wav' }});
        blob.arrayBuffer().then(buf => {{
          if (ws && ws.readyState === WebSocket.OPEN) {{
            ws.send(buf);
            log('📤 Wysłano audio: ' + buf.byteLength + ' bajtów');
          }}
        }});
      }};
      mediaRecorder.start();
      document.getElementById('recordBtn').style.display = 'none';
      document.getElementById('stopBtn').style.display = 'inline-block';
      log('🎙️ Nagrywanie...');
    }}).catch(e => log('❌ Błąd mikrofonu: ' + e));
  }}
}}

document.getElementById('textInput').addEventListener('keypress', e => {{
  if (e.key === 'Enter') sendText();
}});

connect();
</script>
</body>
</html>'''
    path = Path(__file__).parent / "client.html"
    path.write_text(html)
    print(f"[INFO] Wygenerowano client.html (port {port})")


# ─── Main ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="POV #7: Voice Pipeline Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port (default: {DEFAULT_PORT})")
    parser.add_argument("--mock", action="store_true", help="Mock mode — bez STT/TTS, tylko echo")
    parser.add_argument("--test", action="store_true", help="Test offline — bez WebSocket")
    parser.add_argument("--client", action="store_true", help="Generuj client.html")
    args = parser.parse_args()

    if args.client:
        generate_client_html(args.port)
        return

    if args.test:
        asyncio.run(test_offline(mock=args.mock))
        return

    # Generuj client.html przy starcie
    generate_client_html(args.port)

    # Start serwera
    server = VoicePipelineServer(mock=args.mock, port=args.port)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\n[INFO] Serwer zatrzymany.")


if __name__ == "__main__":
    main()
