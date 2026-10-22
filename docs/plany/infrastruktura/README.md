# Kolektyw infrastruktury Hermesa

> **Źródło prawdy: repo [hermes-workspace/infra](https://github.com/ScuraUrsa/hermes-workspace/tree/claude/project-thread-5906j7/infra)** (gałąź `claude/project-thread-5906j7`, po merge'u
> `master`). Tam są opisy hostów zmierzone przez SSH 22.10 (`hosts/lab-ws01.md` = laptop MSI GL75 i7-9750H
> 32 GB, `hosts/lab-w01.md` = worker lab-ubuntu), pojemność, `naming.md` (komputery `lab-w01`/`lab-ws01`,
> VM nazwane od usługi, np. `hermes-prod-1`, `k3s-dev-1`) i `onboarding.md`. Prowadzi je wątek
> [Homelab z Proxmox i k3s](#cmsg_015HTwbUuT8LqRHP4MjSVwTE6NZbGr5kwwTWS6sAHenMqH).
> Zmierzone 22.10: **żaden stos monitoringu nie działa.**
>
> Ten plik zostaje tylko jako wskaźnik dla wątków Claude i lista kontrolna „czy się zmieści” (sekcja na dole).
> Liczby niżej to stara wersja z dokumentacji (09–20.10); przy rozbieżności wygrywa repo.

<details><summary>Stara wersja z dokumentacji (archiwum)</summary>

## 1. Mapa

```
Laptop DESKTOP-F1DF138 (Windows, 32 GB RAM, VirtualBox, D:\hermes)
├── hermes-host-daemon :9143 (z VM: 192.168.56.1:9143)  tworzy VM, repliki, cutover za zgodą Filipa
├── sieć host-only 192.168.56.0/24
│   ├── PROD  192.168.56.107  tożsamość unity-orchestrator, Tailscale hermes-vm-1 / 100.66.185.39
│   ├── DEV   192.168.56.108  hermes-dev
│   └── STAGE 192.168.56.110  budowany na żądanie (pipeline jeszcze nie działa)
└── Tailscale: telefon, laptop, prod, lab-ubuntu

Worker lab-ubuntu (osobny PC w LAN, Tailscale 100.113.115.91)
└── backup borg → Hetzner Storage Box u696488, repo /borg/lab-ubuntu
```

## 2. Maszyny

| Maszyna | Sprzęt | Rola | Wolne zasoby | Uwagi | Źródło |
|---|---|---|---|---|---|
| **Laptop DESKTOP-F1DF138** | 32 GB RAM, GPU GTX 1650 Ti 4 GB, Windows | host VirtualBox dla prod/dev(/stage), host daemon, workspace `D:\hermes`, benchmarki llama.cpp | ok. 10 GB RAM wolnego na kolejne VM (szacunek z planu K12) | Nie może spać (inaczej staje prod). Druga maszyna-laptop przewidziana przez rolę WOBI `laptop_host` (sieć 192.168.57.0/24). | [02-architecture](../../hermes-context/docs/02-architecture.md), [plan K12](../research/2026-10-22-kubernetes-ha.md) — do weryfikacji |
| **PROD** (unity-orchestrator) | VM 8 GB RAM + swap 4 GB | rozmowa z Filipem, gateway, cron Filipa, Honcho, HA + Whisper + Piper, Matrix, timeplane, Syncthing, backup, llama-router (cheap-route) | ok. 3,5 GB RAM i 36 GB dysku (20.10); llama-server zajmuje ok. 4,1 GB RSS | Najciaśniejsza maszyna. Każda nowa usługa na prod wymaga sprawdzenia RAM. | [unified-inbox/plan.md](../../unified-inbox/plan.md) (20.10), [free-web-proxy/plan.md](../../free-web-proxy/plan.md) (16.10) — do weryfikacji |
| **DEV** (hermes-dev) | VM (rozmiar do weryfikacji, ok. 6 GB wg planu K12) | kanban, workery, repozytoria i worktree, Claude Code, cron autonomii | do weryfikacji | Brak Tailscale (wg 02-architecture). | [02-architecture](../../hermes-context/docs/02-architecture.md) — do weryfikacji |
| **STAGE** | budowany na żądanie | kandydat na prod, testy zgodności | — | Pipeline zablokowany (klient OAuth Tailscale). | [prod-stage-dev-design.md](../../prod-stage-dev-design.md) |
| **lab-ubuntu** | Intel i7-950 (4c/8t, bez AVX), 12 GB DDR3 (sloty pełne, max 24 GB), GTX 1070 8 GB, WD Black 3 TB (zdrowy) + Seagate 500 GB (do wycofania), 2× 1 Gb/s (działa 100 Mb/s) | worker homelab, backup borg; docelowo węzeł GPU (llama.cpp CUDA), k3s dev, NAS, Jellyfin | dyski: ok. 2,3 TB zajęte, z tego 2,1 TB to gry do usunięcia; RAM/CPU do weryfikacji | **System działa z pendrive'a live** (restart kasuje konfigurację), sterownik nouveau (brak CUDA), 120–160 W na biegu jałowym, Wake-on-LAN włączony. Uptime 1 d 16 h (22.10 10:30). Na dyskach: Win7 RC 7100 (Seagate), Win7 na WD (GPT, nie startuje na tym BIOS-ie). Naprawa: [T171](https://app.notion.com/p/lab-ubuntu-SSD-Cat6-cable-cooling-BIOS-and-Ubuntu-install-3ffee453d19e81a9a71feb2901bb0a38). | [Diagnostyka lab-ubuntu](https://claude.ai/artifact/C83TRNyf8jZz3NdUut2mhe), [Dyski lab-ubuntu](https://claude.ai/artifact/73YbWVedhitNSs3Mk1arWz) (20.10); na prod `~/.hermes/homelab/node.json`, `inventory.yml` |

## 3. Usługi i porty (wg dokumentacji)

| Usługa | Gdzie | Adres | Uwagi |
|---|---|---|---|
| Hermes gateway + API (OpenAI-compatible) | prod | 127.0.0.1:8642 | używa go HA Assist |
| Honcho (api, deriver, postgres, redis, telemetry-sink) | prod | :8100 | dev czyta read-only |
| Home Assistant + wyoming-whisper + wyoming-piper | prod | http://100.66.185.39:8123 (Tailscale) | |
| Matrix (Continuwuity 26.9.1) | prod | 127.0.0.1:8008, `tailscale serve` :443 | jedyny pokój: DM z Filipem |
| Notification bridge | prod | :8655 | 0 klientów (08.10), do wycofania |
| timeplane-intake | prod | (port do weryfikacji) | przyciski HA, telefon |
| llama-router (cheap-route, Qwen3.5-4B Q4_K_M) | prod | 127.0.0.1:8082 `/health` | |
| Ollama (tylko embeddingi Honcho) | prod | lokalnie | wyjątek od reguły llama.cpp |
| Syncthing (Obsidian) | prod | — | |
| kanban-api | dev | :8787 | prod ma klienta i snapshot co minutę |
| hermes-host-daemon | laptop | 192.168.56.1:9143 | `POST /v1/upgrades`, cutover |

## 4. Monitoring i observability, które już istnieją

| Co | Gdzie | Link / plik | Stan |
|---|---|---|---|
| Backup lab-ubuntu: ostatnie archiwum `ubuntu-osobiste-2026-10-20`, zakończone 21.10 02:43 bez błędów, 110 962 pliki, 113,4 GB danych, 69 GB na boxie | Hetzner Storage Box u696488 | repo `/borg/lab-ubuntu` | ok (22.10 10:30, wątek Homelab) |
| Status backupu prod (format 3, rclone crypt → Google Drive, 7 kopii) | prod | `~/.hermes/autonomy/backup_status.json` | do weryfikacji |
| security_watch (trivy + CISA KEV, integralność co godzinę) | prod | `alerts.jsonl`, cron `security-watch-relay` | działa wg WOBI (commit „rollback CVE” z 21.10) |
| feature_checks (30 testów wszystkiego nad Hermesem, prod vs kopia) | prod / replika | rola WOBI `feature_checks` | do weryfikacji |
| Dashboard „od prompta do efektu” (sesje → PR → koszt) | dev/prod | wątek [Dashboard od prompta do efektu](#cmsg_015HTwbUuT8LqRHP4MjSVwTEBk9YF182CHsgUjW4v9Fvhv), rola `trace_dashboard` (WOBI #41) | adres do weryfikacji |
| Budżet i limity (budget.py, quota_governor) | prod | `~/.hermes/autonomy/quota.json` | |
| Watchdog GitHub Actions, CI doctor | dev | cron | |
| Radar technologiczny (digest w Notion) | prod | [📡 Radar Hermesa](https://app.notion.com/p/3feee453d19e81dda610e263946f3e25) | czeka na merge K01 |
| Metryki, logi, alerty (Prometheus/Grafana/Loki…) | — | — | **brak**, plan w K11 |

## 5. Dokumentacja vs stan faktyczny

Znane rozbieżności (do uzupełnienia po spisie na żywo):

| Dokument mówi | Stan faktyczny | Źródło |
|---|---|---|
| prod ma 8 GB RAM | 15–16.10 prod miał przez chwilę 4 GB, potem z powrotem 8 GB (polityka hosta `replica.memory_mb: 8192`) | [free-web-proxy/plan.md](../../free-web-proxy/plan.md) |
| Matrix „not in WOBI yet” (02-architecture) | WOBI `iac/final` ma rolę `matrix` | `ScuraUrsa/WOBI` iac/final |
| WOBI wdrażany z `iac/final` | PR radaru [WOBI #57](https://github.com/ScuraUrsa/WOBI/pull/57) celuje w `master` | GitHub |

## 6. Rozbudowa: onboarding nowych węzłów

Procedura onboardingu, nazewnictwo (`n01`, `lab-n01`, `n01-ci-01`), adresacja /29 i warunki dla runnerów CI na n01: [onboarding-i-nazewnictwo.md](onboarding-i-nazewnictwo.md).

Inne zasoby: Google Drive kazmierczakfilipjan ma 77,7 GiB wolnego (22.10, cel backupu prod).

</details>

## Lista kontrolna: jak oceniać „czy się zmieści”

1. Która maszyna? Domyślnie: rozmowa z Filipem i jego dane → prod; praca, kod, eksperymenty → dev; GPU,
   duże dyski, k3s dev → lab-ubuntu (po T171); nic publicznie, tylko Tailscale.
2. RAM: zostaw na prod co najmniej 1,5 GB wolnego i nie licz na swap. Podaj RSS nowej usługi.
3. Dysk: backup prod idzie na Google Drive (limit kont), więc duże dane wykluczaj z backupu albo kieruj na
   lab-ubuntu (WD 3 TB) z borg na Hetzner.
4. CPU/GPU: lab-ubuntu nie ma AVX, więc modele tylko na GPU; laptop GTX 1650 Ti 4 GB.
5. Wpływ: inne usługi na tej maszynie, czas backupu, limity Ollama Cloud i Claude, prąd (lab-ubuntu).
6. Utrzymanie: kto pilnuje usługi (agent z K40) i skąd czyta jej stan.
