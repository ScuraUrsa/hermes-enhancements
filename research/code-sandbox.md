# Code Execution Sandbox — Research (Lipiec 2026)

## Stan ekosystemu

### Platformy sandbox

| Platform | Architektura | Open Source | Max Session | Best For |
|----------|-------------|-------------|-------------|----------|
| **E2B** | Firecracker microVMs | ✅ | 24h | AI-first, enterprise |
| **Docker** | Containers | ✅ | ∞ | Self-hosted, flexible |
| **Modal** | Serverless containers | ❌ | Configurable | Scale-to-zero, GPU |
| **Daytona** | Dev environments | ✅ | ∞ | Dev environments |
| **Codex Sandbox** | Cloud VMs | ❌ | Task-based | Codex-native |

### E2B — "AI Agent Cloud"
- Firecracker microVMs (pełna izolacja)
- Python, JS, TS, R, Java
- 94% Fortune 100 używa
- Open-source SDK
- **Limit**: 24h max session
- **Cena**: Free tier + paid

### Docker — "Self-hosted sandbox"
- Pełna izolacja przez kontenery
- Nieograniczony czas sesji
- Wymaga własnej infrastruktury
- Hermes może używać Docker jako terminal backend

### Hermes obecnie

- **terminal backend**: local, docker, ssh, modal, daytona
- **execute_code**: sandboxed Python execution (wbudowany)
- **Brak**: Firecracker-level izolacji, E2B integracji

## Rekomendacja

### POV #10: Docker sandbox dla Hermesa
- Skonfigurować `terminal.backend: docker`
- Każda komenda Hermesa w izolowanym kontenerze
- Bezpieczne uruchamianie kodu
- **Impact: 8/10, Effort: 4/10** (Docker już jest na VM)

### POV #11: E2B + Hermes
- E2B SDK jako dodatkowy sandbox
- Pełna izolacja Firecracker microVM
- Lepsze niż Docker dla untrusted code
- **Impact: 7/10, Effort: 6/10** (wymaga E2B API key)
