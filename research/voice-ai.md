# Voice AI — Research (Lipiec 2026)

## Stan rynku

### ElevenLabs
- **11.ai (alpha, Marzec 2026)** — voice assistant zarządzający workflow
- **Conversational AI platform** — emotion recognition, context-aware
- **32+ języków**, voice cloning, dubbing, sound effects
- **Voice Agents SDK** — budowanie własnych voice agentów
- **Cena**: Free tier dostępny, API płatne

### OpenAI Whisper + TTS
- **Whisper v3** — najlepszy open-source STT
- **GPT-4o voice** — real-time voice mode
- **TTS API** — HD voices, emotion control
- **Cena**: API płatne per token

### Alternatywy
- **Inworld AI** — najlepsza alternatywa dla ElevenLabs (real-time voice)
- **Groq Whisper** — najszybszy STT (free tier)
- **Mistral Voxtral** — competitive TTS
- **Edge TTS** — darmowy, używany przez Hermesa
- **NeuTTS** — lokalny, darmowy

## Standardowy pipeline Voice Agent

```
User voice → STT (Whisper/Groq) → LLM (GPT-4/Claude) → TTS (ElevenLabs/Edge) → User voice
```

Z optymalizacjami:
```
User voice → Groq Whisper (fast, free) → Hermes Agent → Edge TTS (free) → User voice
```

## Hermes Voice Stack obecnie

- **STT**: local faster-whisper, Groq Whisper, OpenAI Whisper, Mistral Voxtral
- **TTS**: Edge TTS (default), ElevenLabs, OpenAI, MiniMax, Mistral, NeuTTS
- **Gateway**: Telegram/Discord voice messages → auto-transkrypcja
- **Voice commands**: `/voice on` (voice-to-voice), `/voice tts` (always voice)

## Rekomendacje

### POV #2: ElevenLabs Conversational Agent + Hermes
- Zastąpić Edge TTS ElevenLabs dla jakości
- Dodać emotion detection
- Voice cloning dla spersonalizowanego głosu
- **Impact: 8/10, Effort: 4/10** (API key już jest w Bitwarden)

### POV #3: Real-time Voice Pipeline (Groq + Hermes + ElevenLabs)
- Groq Whisper dla STT (najszybszy, free tier)
- Hermes jako mózg
- ElevenLabs dla TTS (najlepsza jakość)
- WebSocket dla real-time komunikacji
- **Impact: 9/10, Effort: 6/10**

### Ulepszenia istniejącego stacka
- Dodać `ELEVENLABS_API_KEY` do `.env` (już jest w Bitwarden)
- Skonfigurować `tts.provider: elevenlabs`
- Przetestować jakość vs Edge TTS
