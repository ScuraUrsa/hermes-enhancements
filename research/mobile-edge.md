# Mobile & Edge — Research (Lipiec 2026)

## Hermes Mobile

### Stan obecny
- **Desktop app**: Electron (macOS, Windows, Linux)
- **Gateway**: Telegram, Discord, WhatsApp, iMessage, Signal — dostęp z telefonu
- **Termux**: Android (oficjalnie wspierany)
- **iOS**: przez iMessage, Onepilot (third-party)
- **PR #52673**: Native mobile shell (Expo, iPhone + Android config)

### Rekomendacja
- Gateway to już "mobile app" — użytkownik ma Conduit + Bridge
- Native mobile shell (PR #52673) może dać lepsze UX
- **Impact: 5/10, Effort: 8/10** (gateway już działa)

## Edge AI (Raspberry Pi / Jetson)

### Stan rynku
- **Raspberry Pi 5**: tani ($60), słaby do LLM, dobry do lekkich agentów
- **Jetson Orin Nano**: $599, GPU acceleration, real-time LLM inference
- **Lokalne LLM**: quantized 4B modele na edge
- **Ollama**: działa na RPi 5 + AI HAT

### Hermes na edge
- Hermes działa na Linux (RPi = ARM Linux)
- Wymaga Pythona 3.10+
- Model: lokalny przez Ollama lub API przez sieć
- **Praktyczne**: Hermes na RPi 5 + Ollama (tiny model) + cloud fallback

### Rekomendacja
- **Impact: 4/10, Effort: 7/10** — ciekawy projekt, ale nie priorytet
- Gateway na telefonie już daje "mobile Hermes"
