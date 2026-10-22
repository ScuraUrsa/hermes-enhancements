# Kolejka planów Hermesa

Stan na **2026-10-22**. Jedna kolejka ze wszystkich planów i researchy w projekcie. Konwencja i etapy:
[README.md](README.md). Infrastruktura do oceny „czy się zmieści”: [hermes-workspace/infra](https://github.com/ScuraUrsa/hermes-workspace/tree/claude/project-thread-5906j7/infra) + lista kontrolna w [infrastruktura/README.md](infrastruktura/README.md).

Kolejność: fala 0 odblokowuje resztę, fala 1 to fundament (wiedza o infrastrukturze, monitoring, kontekst
dla agentów), fala 2 to autonomia i agenci utrzymania, fala 3 to funkcje dla Filipa. W fali kolejność
wierszy = kolejność pracy. Kto: **F** Filip, **CC** Claude Code / wątek, **H** Hermes.

Etapy pozycji są przepisane ze źródeł z podanych dat. Jeśli coś się zmieniło, popraw wiersz.

## Fala 0: odblokowanie (decyzje i drobne kroki Filipa)

| ID | Temat | Etap | P | Następny krok | Kto | Źródło |
|---|---|---|---|---|---|---|
| K01 | Radar technologiczny F0 (codzienny digest 33 źródeł w Notion) | czeka na Filipa | P1 | Merge [WOBI #57](https://github.com/ScuraUrsa/WOBI/pull/57) ([T151](https://app.notion.com/p/Przejrzyj-i-zmerguj-PR-Radar-Hermesa-F0-WOBI-57-3feee453d19e8168a6e5c6ee73d4f5ec)). Uwaga: PR celuje w `master`, a prod jest wdrażany z `iac/final`, więc przed merge trzeba zmienić bazę PR na `iac/final`. | F, CC | [radar-technologiczny-plan.md](../mega-dev/radar-technologiczny-plan.md) |
| K02 | `vision.md` Hermesa (1 strona: czym ma być, czego nie robi, co teraz najważniejsze) | czeka na Filipa | P1 | Filip pisze ok. 30 min (może podyktować, wątek zrobi szkic z tej kolejki) | F | [mega.dev pkt 1](../mega-dev/autonomous-product-development-dla-hermesa.md) |
| K03 | lab-ubuntu jako trwały worker: SSD na system, kabel Cat6, AHCI, sterownik NVIDIA 580 + CUDA 12 | czeka na Filipa (zakup ~150 zł) | P1 | Zadanie [T171](https://app.notion.com/p/lab-ubuntu-SSD-Cat6-cable-cooling-BIOS-and-Ubuntu-install-3ffee453d19e81a9a71feb2901bb0a38): zakup SSD i kabla, potem instalacja Ubuntu Server 24.04 + bootstrap. Dziś system działa z pendrive'a live, restart kasuje konfigurację. | F, CC | [T171](https://app.notion.com/p/lab-ubuntu-SSD-Cat6-cable-cooling-BIOS-and-Ubuntu-install-3ffee453d19e81a9a71feb2901bb0a38), [Diagnostyka lab-ubuntu](https://claude.ai/artifact/C83TRNyf8jZz3NdUut2mhe), wątek [Homelab z Proxmox i k3s](#cmsg_015HTwbUuT8LqRHP4MjSVwTE6NZbGr5kwwTWS6sAHenMqH) |
| K04 | Rotacja wyciekłych sekretów (GitHub PAT, token BWS w historii git) | do weryfikacji | P1 | Sprawdzić, co już zrotowane (08-status z 11.10 i notatki z 08.10) | F | [08-status](../hermes-context/docs/08-status-and-open-issues.md), [notes 08.10](../notes/hermes-todo-2026-10-08.md) |
| K05 | Klucz Gemini API dla cheap-route (darmowy kanał free_web) | czeka na Filipa | P2 | [T85](https://app.notion.com/p/Klucz-Gemini-API-dla-cheap-route-darmowy-kana-3faee453d19e81daaec8faaf9e480438) | F | [free-web-proxy/plan.md](../free-web-proxy/plan.md) |

## Fala 1: fundament

| ID | Temat | Etap | P | Następny krok | Kto | Źródło |
|---|---|---|---|---|---|---|
| K10 | **Kolektyw infrastruktury**: hosty zmierzone przez SSH, pojemność, nazewnictwo, onboarding | w budowie (gałąź do merge'u) | P1 | Merge gałęzi `claude/project-thread-5906j7` w hermes-workspace; potem odświeżanie przez agenta (K40) i doc-gardener (K45) | CC, F | [hermes-workspace/infra](https://github.com/ScuraUrsa/hermes-workspace/tree/claude/project-thread-5906j7/infra), wątek [Homelab z Proxmox i k3s](#cmsg_015HTwbUuT8LqRHP4MjSVwTE6NZbGr5kwwTWS6sAHenMqH) |
| K11 | **Observability i monitoring**: Prometheus + Loki + Grafana + Alertmanager w k3s na lab-w01, Alloy (OTel) na każdym hoście, alerty do Matrix + e-mail, Healthchecks.io jako strażnik; Tempo w fazie 4; Zabbix/Checkmk/Thanos odrzucone na teraz. Ok. 2–2,5 GB RAM i 30 GB SSD na lab-w01; na laptopie i dev VM się nie mieści. Faza 6: agent `sre` (część K40) | czeka na Filipa | P1 | Faza 0 od razu (Healthchecks.io dla backupów, smartd); faza 1 po K03/T171 i K12 faza 1; Alloy na prod po K18; faza 2 po K15. 4 decyzje w §7 planu. Scala pomysł ChatGPT [20](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/20-observability-stack.md) i mega.dev pkt 7 | CC, F | [research/2026-10-22-observability.md](research/2026-10-22-observability.md), wątek [Observability i monitoring](#cmsg_015HTwbUuT8LqRHP4MjSVwTETrhDe1eE4jFYniz1T8aLpM) |
| K12 | **Kubernetes z wysoką niezawodnością**: k3s (wbudowany etcd) bezpośrednio na lab-w01, Flux (Argo CD od 24 GB RAM), Longhorn, CloudNativePG; k3d + Tilt tylko do dev; HA dopiero przy 3 zawsze włączonych węzłach. Na laptopie lab-ws01 węzeł k3s się nie zmieści. | czeka na Filipa | P2 | Plan: [research/2026-10-22-kubernetes-ha.md](research/2026-10-22-kubernetes-ha.md). Fazy 1–2 na lab-w01 (12 GB, na styk) po K03; runnery CI jako pody ARC zamiast osobnej VM (do uzgodnienia z wątkiem Homelab); faza 4 (prod do klastra) wymaga K19; decyzja o sprzęcie HA (rekomendacja: 3 używane mini PC). Faza 7: agenci utrzymania klastra (część K40). Pojemność do przeliczenia z K10. Scala pomysły ChatGPT [19](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/19-homelab-virtualization.md), [18](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/18-k8s-security-learning-path.md), [27](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/27-agent-sandboxes.md); powiązane: wątek [Self-hosted runnery GitHub Actions](#cmsg_015HTwbUuT8LqRHP4MjSVwTE2t1PGnsX9mNggLhRUFVrKw) (ARC w klastrze). | F, CC | wątek [Kubernetes z wysoką niezawodnością](#cmsg_015HTwbUuT8LqRHP4MjSVwTEJaa12sZHCMts4UqkWnzffs) |
| K13 | Styleguide + `vision.md` wstrzykiwane do każdej sesji (`cc_run.py`, `CLAUDE.md.j2`) | plan | P1 | PR w WOBI/crewai-orchestrator po K02 | CC | [mega.dev pkt 1](../mega-dev/autonomous-product-development-dla-hermesa.md) |
| K14 | Specy per funkcja z etapem i `lessons.md`, spięte z `features/registry.yaml` | plan | P1 | Szkielet `specs/` z 2–3 funkcjami (timeplane, voice, backup); ta kolejka jest jego zalążkiem | CC | [mega.dev pkt 2](../mega-dev/autonomous-product-development-dla-hermesa.md) |
| K15 | Upgrade Hermesa v0.20.0 → aktualny upstream przez replikę i testy zgodności | w budowie (feature_checks w WOBI) | P1 | Pierwszy upgrade przez pętlę: replika, 30 feature checks, cutover za zgodą | CC, F | [cutover-and-self-upgrade-plan.md](../cutover-and-self-upgrade-plan.md) §4, radar F2 |
| K16 | Stage jako pipeline (budowa ze `stage` refs, testy, „przetestuj”) | plan, zablokowane | P2 | Potrzebny klient OAuth Tailscale | F, CC | [prod-stage-dev-design.md](../prod-stage-dev-design.md) |
| K17 | Onboarding nowych węzłów homelab i konwencja nazw (lab-w01/lab-ws01, VM od usługi), runnery CI | plan | P2 | Po K03; powiązane z K12 i wątkiem [Self-hosted runnery GitHub Actions](#cmsg_015HTwbUuT8LqRHP4MjSVwTE2t1PGnsX9mNggLhRUFVrKw) | CC | [hermes-workspace/infra](https://github.com/ScuraUrsa/hermes-workspace/tree/claude/project-thread-5906j7/infra) (`onboarding.md`, `naming.md`) |
| K18 | Przenieść llama-router (cheap-route, Qwen3.5-4B) z prod na GPU lab-w01: zwalnia ok. 4,1 GB RAM na prod | plan | P1 | Po K03 (sterownik NVIDIA + CUDA na lab-w01); najszybszy zysk pamięci na prod | CC | [plan K12 §6](research/2026-10-22-kubernetes-ha.md), [free-web-proxy/plan.md](../free-web-proxy/plan.md) |
| K19 | RAM lab-w01 do 24 GB (6 × 4 GB DDR3, ok. 100 zł) | czeka na Filipa (zakup) | P2 | Odblokowuje fazę 4 planu K12 i Argo CD | F | [Diagnostyka lab-ubuntu](https://claude.ai/artifact/C83TRNyf8jZz3NdUut2mhe), [plan K12](research/2026-10-22-kubernetes-ha.md) |

## Fala 2: autonomia i agenci utrzymania

| ID | Temat | Etap | P | Następny krok | Kto | Źródło |
|---|---|---|---|---|---|---|
| K40 | **Agenci Hermesa do utrzymania i obsługi** (prośba Filipa 22.10): wspólny plan profili z faz utrzymania: `sre` z K11 (czyta alerty Alertmanagera, diagnozuje, naprawia z listy dozwolonych) oraz `k8s-operator`, `k8s-upgrader`, `backup-warden`, `capacity-planner`, `security-auditor` z K12; do tego odświeżanie kolektywu infrastruktury (K10) i dzienny raport | plan (fazy w K11 §6 i K12 §4 faza 7) | P1 | Scalić w jeden plan profili (ile profili, uprawnienia, budżet, bramka Filipa dla prod); start: 2 tygodnie tylko diagnozy | CC | [observability](research/2026-10-22-observability.md), [kubernetes-ha](research/2026-10-22-kubernetes-ha.md), [README pkt 4](README.md) |
| K41 | Profil `coordinator` i praca w falach (spec → 3–5 kart z testem akceptacji → review → jedno podsumowanie) | plan | P1 | Pilot na jednej funkcji | CC, H | [mega.dev pkt 3](../mega-dev/autonomous-product-development-dla-hermesa.md) |
| K42 | Radar F1–F3: ocena LLM, karty propozycji, POC po zgodzie, rejestr decyzji, warunki powrotu | plan | P1 | Po 7 dniach K01 | CC | [radar-technologiczny-plan.md](../mega-dev/radar-technologiczny-plan.md); scala pomysł [04](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/04-self-learning-tool-researcher.md) |
| K43 | Klaster „oszczędzanie tokenów”: repo zasad kodowania dla AI ([03](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/03-ai-coding-rules-repo.md)), zamiana powtarzalnej pracy LLM na kod ([17](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/17-llm-to-algorithm-distillation.md)), mały lokalny klasyfikator ([16](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/16-local-classifier-model.md)) | plan | P1 | Karty kanban z dokumentami jako spec | H, CC | [chatgpt-ideas](https://github.com/ScuraUrsa/hermes-enhancements/tree/master/docs/chatgpt-ideas) |
| K44 | `hermes-events`: wyzwalacze zdarzeniowe (journald, backup, token Google, mail z etykietą, HA, Notion) → karta kanbana | plan | P2 | Ujednolicić CI doctor / inbox w jedno źródło zdarzeń; wejście dla K40 | CC | [mega.dev pkt 5](../mega-dev/autonomous-product-development-dla-hermesa.md), [grok-bot-parity](../grok-bot-parity/plan.md) |
| K45 | Doc-gardener: nocne porównanie dokumentacji i specy z kodem, PR z poprawkami | plan | P2 | Razem z K10 (ten sam mechanizm porównania) | CC | [mega.dev pkt 6](../mega-dev/autonomous-product-development-dla-hermesa.md) |
| K46 | Whitelista pracy bez nadzoru (martwy kod, czerwone CI, testy stage, regresje UI) | plan | P2 | Wpis w polityce plannera | CC | [mega.dev pkt 8](../mega-dev/autonomous-product-development-dla-hermesa.md) |
| K47 | `ask_filip` + approvals „smart” (wysyłka, płatność, hasła, CAPTCHA) | plan | P2 | Grok parity faza 1 | CC, H | [grok-bot-parity](../grok-bot-parity/plan.md) |
| K48 | Pętla CI-fix i rozszerzenia pracy kodowej: CI-fix Azure DevOps ([28](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/28-ci-fix-agent-loop.md)), graf wiedzy o kodzie ([24](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/24-code-knowledge-graph.md)), agent demo po PR ([29](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/29-pr-demo-presentation-agent.md)), back-endy Copilot/Claude ([40](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/40-copilot-claude-coding-backends.md)) | plan | P2–P3 | Po K12 (sandboxy) | CC | chatgpt-ideas |

## Fala 3: funkcje dla Filipa

| ID | Temat | Etap | P | Następny krok | Kto | Źródło |
|---|---|---|---|---|---|---|
| K60 | Jedno wejście przez Matrix w stylu Grok Bota (sprawdza board, deleguje, plan nocny) | plan | P2 | Po K41 | CC, H | [mega.dev pkt 4](../mega-dev/autonomous-product-development-dla-hermesa.md) |
| K61 | Jedna skrzynka na wszystkie czaty (mostki mautrix + hermes-inbox + ekran w AetherShell) | w budowie (krok 1) | P2 | Rola `matrix_bridges` SMS + WhatsApp | CC, F | [unified-inbox/plan.md](../unified-inbox/plan.md) |
| K62 | Szybki zapis linków → analiza (endpoint `/save`, Termux, bookmarklet) | czeka na Filipa | P2 | Decyzja o Etapie 1 | F | [link-capture](../link-capture/research-2026-10-15.md) |
| K63 | Teach a Task → skill → skrypt; computer use ([23](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/23-computer-use-automation.md)) | w budowie (PR #2 hermes-gui-automation) | P2 | Test E2E na odblokowanym PC | F, CC | [grok-bot-parity](../grok-bot-parity/plan.md) |
| K64 | cheap-route E3/E4 (kanał webowy, tydzień pomiaru) | wstrzymane | P3 | Po K05 | CC | [free-web-proxy/plan.md](../free-web-proxy/plan.md) |
| K65 | Agent finansowy: paper trading, raport, backtest; kursy XTB | w budowie (paper) | P2 | Wybór brokera przez Filipa | F, CC | [agent-autonomiczny.md](../finanse/agent-autonomiczny.md), [kursy-xtb/plan.md](../finanse/kursy-xtb/plan.md) |
| K66 | Odciążenie telefonu: Android sterowany przez agenta ([21](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/21-phone-offload-homelab-android.md)) | plan | P2 | — | CC | chatgpt-ideas |
| K67 | Bezpieczeństwo rodziny bez haseł: klucze FIDO2 + Bitwarden ([31](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/31-family-passwordless-security.md)) | plan | P2 | Decyzja i zakup kluczy | F | chatgpt-ideas |
| K68 | Odkurzacz bez chmury (Valetudo + HA) ([06](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/06-robot-vacuum-valetudo.md)) | czeka na Filipa | P2 | Wątek [Roborock w Home Assistant](#cmsg_015HTwbUuT8LqRHP4MjSVwTEMLpBEESW1CKTxGrPoBV8FB) | F | chatgpt-ideas |
| K69 | Monitorowanie snu (Colmi R02 + Gadgetbridge + MCP „sleep”) | czeka na Filipa (zakup) | P3 | Decyzja | F | [sleep-tracking](../sleep-tracking/research-2026-10-15.md) |
| K70 | Skille CV (RenderCV) oraz Office/PDF (Stirling-PDF, LibreOffice) | research gotowy | P3 | Instalacja skilli; Stirling-PDF po sprawdzeniu w K10, czy się zmieści | CC | [cv](../cv/research-2026-10-20.md), [office-pdf](../office-pdf/skille-office-pdf-2026-10-20.md) |
| K71 | Workstation as code ([01](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/01-workstation-as-code.md)) + fabryka obrazów runnerów ([02](https://github.com/ScuraUrsa/hermes-enhancements/blob/master/docs/chatgpt-ideas/02-ci-runner-image-factory.md)) | plan | P2–P3 | Razem (ta sama rola Ansible i Packer) | CC | chatgpt-ideas |

## Backlog (P3–P5, bez kolejności)

Z [chatgpt-ideas](https://github.com/ScuraUrsa/hermes-enhancements/tree/master/docs/chatgpt-ideas) (numery dokumentów):
09 zdalny pulpit i wspólny komputer · 10 serwer multimediów (Jellyfin; lab-ubuntu ma NVENC) · 22 głosowy towarzysz
· 25 planer kosztów LLM (rozstrzyga 41 i 08) · 35 warsztat maker · 41 tani rig GPU · 05 · 07 · 08 · 11 · 14 · 26 Open WebUI
· 32 · 33 · 36 darmowy węzeł Oracle (backup off-site) · 39 gaming PC z Windows 10 · 12 · 13 · 15 · 30 · 38.
Gotowe: 34 (Matrix), 37 (eksport ChatGPT).

Z mega.dev (P3): notatka głosowa → spec, weryfikacja wizualna (Playwright na stage), prymitywy add-onów
(Integration/Secret/Event/Value/Capability), strona dokumentacji na tailnecie.

## Jak dopisać

Patrz [README.md](README.md): nowy plik w `research/`, nowy wiersz z kolejnym wolnym ID w odpowiedniej fali
(fala 0: K01–K09, fala 1: K10–K39, fala 2: K40–K59, fala 3: K60–K99, nowe tematy bez fali: K100+).
