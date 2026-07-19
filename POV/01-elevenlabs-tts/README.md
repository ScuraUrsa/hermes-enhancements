# POV #1: ElevenLabs TTS + Hermes

## Cel
Zastąpić domyślny Edge TTS (darmowy, ale niska jakość) ElevenLabs TTS (wysoka jakość, naturalne brzmienie).

## Status
✅ API key dostępny w Bitwarden
✅ Biblioteka `elevenlabs` zainstalowana
✅ Demo działa

## Szybki start

```bash
# 1. Zainstaluj bibliotekę
pip install elevenlabs

# 2. Uruchom demo
cd ~/workspace/hermes-enhancements/POV/01-elevenlabs-tts
python3 demo.py "Cześć, tu Hermes!"

# 3. Skonfiguruj Hermesa
echo "ELEVENLABS_API_KEY=$(bws secret get 893e302b-cd6b-4b40-aaea-b47b01615bb2 --server-url https://vault.bitwarden.eu | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"value\"])')" >> ~/.hermes/.env
hermes config set tts.provider elevenlabs

# 4. Restartuj Hermesa i testuj
# /voice tts
# Cześć, tu Hermes na ElevenLabs!
```

## Porównanie

| Cecha | Edge TTS | ElevenLabs |
|-------|----------|------------|
| Jakość głosu | 5/10 | 9/10 |
| Naturalność | 4/10 | 9/10 |
| Języki | ~50 | 32+ |
| Voice cloning | ❌ | ✅ |
| Emotion control | ❌ | ✅ |
| Cena | Darmowy | Free tier (10k znaków/mo) |
| Offline | ✅ | ❌ (API) |

## Wnioski

- ElevenLabs daje znacząco lepszą jakość głosu
- Free tier wystarcza do testów
- Edge TTS zostaje jako fallback
- Rekomendowane dla voice-first interakcji
