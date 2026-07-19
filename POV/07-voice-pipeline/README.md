# POV #7: Real-time Voice Pipeline

**WebSocket server do real-time voice: STT → Hermes → TTS**

## Architektura

```
Klient (przeglądarka / app)
    │
    ▼ WebSocket (ws://localhost:8765)
    │
┌───────────────────────────────┐
│  Voice Pipeline Server        │
│                               │
│  1. Audio (WAV bytes) ──► faster-whisper STT ──► tekst
│  2. Tekst ──► Hermes Agent (deepseek-v4-pro) ──► odpowiedź
│  3. Odpowiedź ──► ElevenLabs TTS ──► audio MP3
│                               │
│  4. Audio MP3 ──► klient      │
└───────────────────────────────┘
```

## Wymagania

```bash
pip install websockets faster-whisper elevenlabs
```

- **faster-whisper**: lokalny STT (offline, bez API key)
- **ElevenLabs**: TTS (wymaga API key — pobierany z Bitwarden)
- **websockets**: WebSocket server

## Szybki start

### 1. Test offline (bez WebSocket)

```bash
# Mock mode — testuje flow bez zewnętrznych API
python3 demo.py --test --mock

# Pełny test — z ElevenLabs TTS i faster-whisper
python3 demo.py --test
```

### 2. Uruchom serwer

```bash
# Mock mode (bez STT/TTS — tylko echo)
python3 demo.py --mock

# Pełny tryb (STT + TTS)
python3 demo.py

# Custom port
python3 demo.py --port 9000
```

### 3. Klient testowy

Otwórz `client.html` w przeglądarce (generowany automatycznie przy starcie serwera).

Możesz też testować przez CLI:

```bash
# Zainstaluj websocket klienta
pip install websocket-client

# Wyślij tekst
python3 -c "
import websocket, json
ws = websocket.create_connection('ws://localhost:8765')
ws.send(json.dumps({'text': 'Cześć, jak się masz?'}))
print(ws.recv())
ws.close()
"
```

## API WebSocket

### Klient → Serwer

| Format | Opis |
|--------|------|
| `bytes` (WAV) | Audio do transkrypcji (STT) |
| `{"text": "..."}` | Tekst do przetworzenia przez Hermesa |

### Serwer → Klient

| Format | Opis |
|--------|------|
| `{"type": "audio_ready", "text": "...", "input": "...", "audio_size": N}` | Metadane przed audio |
| `bytes` (MP3) | Audio z TTS |
| `{"type": "text", "text": "...", "input": "..."}` | Odpowiedź tekstowa (mock mode) |

## Konfiguracja

### ElevenLabs API Key

Klucz jest pobierany automatycznie z Bitwarden (`ELEVENLABS_API_KEY`).
Możesz też ustawić ręcznie:

```bash
export ELEVENLABS_API_KEY="sk_..."
```

### Model STT

Domyślnie `base` — zmień w `demo.py`:

```python
WHISPER_MODEL = "tiny"   # najszybszy, najmniejszy
WHISPER_MODEL = "base"   # dobry balans
WHISPER_MODEL = "small"  # lepsza jakość
WHISPER_MODEL = "medium" # bardzo dobra jakość
WHISPER_MODEL = "large-v3" # najlepsza jakość (wolny)
```

### Głos TTS

Domyślnie `George` (męski, naturalny). Zmień w `demo.py`:

```python
ELEVENLABS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George
# Inne popularne:
# "21m00Tcm4TlvDq8ikWAM"  # Rachel (żeński, amerykański)
# "AZnzlk1XvdvUeBnXmlld"  # Domi (żeński, brytyjski)
```

## Pliki

| Plik | Opis |
|------|------|
| `demo.py` | Serwer WebSocket + pipeline STT→Hermes→TTS |
| `client.html` | Klient testowy w przeglądarce (generowany auto) |
| `README.md` | Ten plik |

## Status

- [x] WebSocket server (asyncio + websockets)
- [x] STT: faster-whisper (lokalny, offline)
- [x] TTS: ElevenLabs (przez Bitwarden)
- [x] Hermes Agent proxy (deepseek-v4-pro)
- [x] Mock mode (testowanie bez API)
- [x] Klient HTML (nagrywanie + odtwarzanie)
- [x] Test offline
- [ ] Groq Whisper STT (brak API key — fallback: faster-whisper)
- [ ] Streaming audio (chunked TTS)
- [ ] Voice Activity Detection (VAD)

## Uwagi

- **Groq Whisper**: nie mamy API keya do Groq — używamy lokalnego `faster-whisper` jako fallback. Działa offline, bez limitu.
- **ElevenLabs**: free tier ma limit ~10k znaków/miesiąc. Używaj oszczędnie.
- **faster-whisper**: pierwsze uruchomienie pobiera model (~140MB dla `base`).
