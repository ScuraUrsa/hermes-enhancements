# Home Assistant + Wyoming — Research (Lipiec 2026)

## Stan ekosystemu

### Home Assistant Voice
- **Year of Voice** (2023) → **Chapter 11** (Paź 2025): multilingual assistants
- **Voice Preview Edition** — hardware do voice control
- **Wyoming Protocol** — lightweight local API do łączenia komponentów voice
- **Assist** — wbudowany voice assistant

### Wyoming Protocol
- Lokalny, lekki protokół
- Łączy: STT (Whisper) ↔ Intent Recognition ↔ TTS (Piper)
- Działa na Raspberry Pi
- Python + Docker

### Pipeline HA Voice

```
Voice Hardware → Wyoming → Whisper STT → HA Assist (intent) → Piper TTS → Voice Hardware
```

Z AI:
```
Voice Hardware → Wyoming → Whisper STT → Hermes Agent (LLM) → Piper/Edge TTS → Voice Hardware
```

## Hermes + Home Assistant

### Integracja
- Hermes ma `homeassistant` toolset (off by default)
- `hermes tools enable homeassistant`
- Gateway adapter dla Home Assistant

### Potencjalna integracja
- Hermes jako "mózg" dla HA Voice
- HA Voice PE → Wyoming → Hermes (przez API) → HA actions
- Hermes może kontrolować smart home przez HA API

## Rekomendacja

### POV #9: Hermes jako HA Voice brain
- Podłączyć Hermesa do HA przez REST API
- HA Voice PE → Wyoming → Hermes → HA actions
- Hermes rozumie kontekst (memory), HA wykonuje akcje
- **Impact: 7/10, Effort: 6/10** (wymaga HA instancji)

**Uwaga**: Użytkownik nie ma obecnie HA instancji. To future-proof research.
