# Hermes na Kubernetesie z wysoką niezawodnością: research i plan migracji

- **Data:** 2026-10-22
- **Wątek:** [Kubernetes z wysoką niezawodnością](#cmsg_015HTwbUuT8LqRHP4MjSVwTEJaa12sZHCMts4UqkWnzffs) (zlecone z [Homelab z Proxmox i k3s](#cmsg_015HTwbUuT8LqRHP4MjSVwTE6NZbGr5kwwTWS6sAHenMqH))
- **ID w kolejce:** K12 (fazy utrzymania: K40)
- **Etap:** czeka na Filipa (decyzja o sprzęcie do HA; fazy 0–1 mogą ruszyć po zadaniu T171)
- **Priorytet:** P2
- **Plan siostrzany:** telemetria / observability (osobny wątek)
- **Stan infrastruktury:** pomiary kolektywu `hermes-workspace/infra` z 2026-10-22 (sekcja 6); nazwy wg `infra/naming.md` (lab-ws01 = laptop, lab-w01 = lab-ubuntu)

## TL;DR

1. **Dystrybucja: k3s** (v1.37, wbudowany etcd, Traefik, Gateway API). Nie Talos: brak SSH utrudnia
   naprawy agentom Hermesa, które dziś pracują przez SSH + Ansible. Nie Proxmox pod k3s na obecnym
   sprzęcie: 12 GB RAM w lab-w01 (lab-ubuntu) nie udźwignie warstwy VM (Proxmox ma sens dopiero od 24 GB+ albo
   przy potrzebie VM z Windowsem).
2. **k3d + Tilt to narzędzia dev, nie produkcja.** k3d = ten sam k3s w Dockerze (na dev i w CI do testów
   manifestów), Tilt = pętla „zapisz plik → kontener w klastrze się przeładowuje” dla dodatków Hermesa.
3. **GitOps: Argo CD od 24 GB RAM / fazy 4, wcześniej Flux** (Argo CD: UI do akceptacji, ręczny sync prodowych aplikacji = dzisiejsza bramka „Filip
   zatwierdza cutover”). WOBI zostaje dla warstwy systemu (OS, sterowniki NVIDIA, instalacja k3s).
4. **Prawdziwe HA wymaga 3 zawsze włączonych węzłów control-plane.** Dziś ich nie ma: laptop (lab-ws01)
   nie ma już RAM ani dysku na nowe VM (16 + 24 GB wolnego dysku), a lab-w01 pobiera 120–160 W. Dlatego plan
   jest fazowy: najpierw dev na k3s na lab-w01 (zwalnia ~6 GB RAM i dysk VM na laptopie), llama-router
   z prod na GPU (zwalnia ~4 GB na prod), potem prod (wymaga 24 GB RAM w lab-w01), a HA po decyzji o sprzęcie (rekomendacja:
   3 używane mini PC, ok. 10 W każdy).
5. **Hermes sam w sobie jest jednoinstancyjny** (SQLite: `state.db`, `kanban.db`, gateway). HA dla niego
   oznacza szybki failover (pod przenosi się na inny węzeł z replikowanym wolumenem Longhorn w 1–6 min),
   a nie aktywne-aktywne. Postgres Honcho dostaje prawdziwe HA przez CloudNativePG.
6. **Nowa faza 7: agenci Hermesa do utrzymania klastra** (k8s-operator, upgrade, backup/DR, capacity),
   pracujący przez Git/PR i z bramką Filipa dla prod.

---

## 1. Stan obecny (punkt wyjścia)

Źródła: `hermes-context/docs/02-architecture.md`, `04-deployment.md`, `prod-stage-dev-design.md`,
[raport sprzętu lab-ubuntu](https://claude.ai/artifact/C83TRNyf8jZz3NdUut2mhe), WOBI `bootstrap-usb`
(branch `claude/project-thread-dzmkdd`).

| Maszyna | Zasoby | Co działa | Uwagi |
|---|---|---|---|
| **lab-ws01** — laptop MSI GL75 (Windows, VirtualBox) | i7-9750H, 32 GB RAM, GTX 1650 Ti 4 GB; C: 16 GB i D: 24 GB wolne (22.10) | VM prod 192.168.56.107 (6 GB / 4 vCPU, llama-router ~4,1 GB RSS wg 20.10), VM dev .108 (6 GB / 4 vCPU), host-daemon :9143 | **brak miejsca na nowe VM** (RAM i dysk) |
| **lab-w01** (dawniej lab-ubuntu) | i7-950 4c/8t bez AVX, 12 GB DDR3 (max 24), GTX 1070 8 GB, WD 3 TB, Seagate 500 GB (do wycofania), Tailscale 100.113.115.91, publiczne IP /29 | Ubuntu live z pendrive'a, backup borg → Storage Box | potrzebny SSD (system + etcd), kabel Cat6, AHCI, sterownik NVIDIA 580 |
| Hetzner Storage Box | 5 TB, SFTP/borg/SMB, FSN1 | kopie borg | **nie ma S3** |
| Google Drive (4 konta) | | nocny backup rclone crypt z prod | |

Pomiary z 22.10 z kolektywu infrastruktury (`hermes-workspace/infra`) i rachunek pojemności są w sekcji 6.
Stos monitoringu nie działa nigdzie (stan 22.10), więc bieżące zużycie trzeba mierzyć przez SSH do czasu K11.

Najważniejsze ograniczenia:
- Węzły nie są w jednej sieci L2 (host-only VirtualBox vs publiczne /29 w labie), więc **cała sieć
  klastra idzie po Tailscale**; VIP przez ARP (kube-vip, MetalLB L2) nie zadziała między nimi.
- Lab ma publiczny adres: porty k3s (6443, 10250, 2379–2380, 8472/51820) tylko z tailnetu (ufw).
- Lokalne modele **tylko llama.cpp** (reguła Filipa). Ollama na VM dziś obsługuje embeddingi Honcho
  (wyjątek legacy) — w klastrze zastępuje go `llama-server --embedding` (patrz faza 4).

---

## 2. Research: narzędzia

### 2.1 Dystrybucja Kubernetes

| | Za | Przeciw | Werdykt |
|---|---|---|---|
| **k3s** (SUSE/CNCF) | 1 binarka, ~0.5–1 GB RAM na serwer, wbudowany etcd HA, Traefik, ServiceLB, helm-controller, snapshoty etcd do S3, wsparcie dla Tailscale (`--vpn-auth`), 1.37 z etcd 3.7 i Gateway API w pakiecie | domyślny Traefik/ServiceLB trzeba świadomie zostawić albo wyłączyć | **wybór** |
| RKE2 | hardening CIS, ta sama rodzina co k3s | cięższy (~2 GB na serwer) | za ciężki na 12 GB |
| Talos Linux | niezmienny OS, API zamiast SSH, automatyczny rollback | brak powłoki i SSH, osobny `talosctl`, storage tylko przez CSI; agenci Hermesa nie mogą naprawiać węzłów tak jak dziś | dobry kandydat **później**, na mini PC |
| k0s | czysty upstream, 1 binarka | mniejsza społeczność homelab niż k3s | ok, brak przewagi |
| MicroK8s | snap, łatwe add-ony | snap, słabsze HA (dqlite) | nie |
| kubeadm | wzorcowy upstream | dużo ręcznej roboty | nie |

### 2.2 Lokalny klaster i pętla deweloperska

| Narzędzie | Do czego | Werdykt |
|---|---|---|
| **k3d** | k3s w kontenerach Dockera; klaster w kilka sekund, multi-node, lokalny registry | **dev VM + CI**: ten sam k3s co prod, testy manifestów i e2e |
| kind | k8s-in-Docker (upstream), standard CI projektów k8s | alternatywa w CI, ale inna dystrybucja niż prod |
| minikube | VM/Docker, add-ony | wolniejszy, bez przewagi |
| **Tilt** | `Tiltfile` (Starlark): build → deploy → live update plików do działającego kontenera, UI z logami | **pętla dev dla dodatków** (notification-bridge, timeplane-intake, contact-crm, inbox) |
| Skaffold (Google) | build/deploy pipeline, dobre profile CI | alternatywa, mniej wygodny live-update |
| DevSpace / Garden / Okteto | dev w zdalnym klastrze | niepotrzebne przy jednym deweloperze |
| mirrord / Telepresence | lokalny proces „podpięty” pod ruch klastra | przydatne do debugowania, opcjonalnie |

Wniosek: k3d i Tilt nie zwiększają niezawodności prod same w sobie. Dają powtarzalne środowisko dev,
które jest kopią prod, i szybkie testy zmian przed merge — to obniża liczbę awarii po wdrożeniu.

### 2.3 GitOps

| | Argo CD | Flux |
|---|---|---|
| UI | wbudowane, dobre do podglądu i akceptacji | brak (Headlamp/Capacitor jako dodatek) |
| RAM | ~0.7–1 GB | ~0.3 GB |
| Bramka prod | ręczny sync / sync windows per aplikacja | PR merge jako bramka |
| Środowiska podglądowe | ApplicationSet z generatorem PR | Flux + kustomize, mniej gotowe |
| Popularność | największa (CNCF graduated) | CNCF graduated |

**Wybór: Argo CD** — UI dla Filipa, ręczny sync dla prod pasuje do obecnego „cutover za zgodą”, a
ApplicationSet daje efemeryczny stage per PR. Flux byłby lepszy przy bardzo małym RAM; do rozważenia,
jeśli kolektyw infrastruktury pokaże, że 1 GB to za dużo.
Aktualizacje wersji: Renovate (WOBI już go ma).

### 2.4 Storage i dane

| Warstwa | Wybór | Dlaczego / alternatywy |
|---|---|---|
| Wolumeny blokowe | **Longhorn** (2 repliki, potem 3) | prosty, UI, kopie do S3 **albo SMB/CIFS** (Storage Box ma SMB). Rook-Ceph: za ciężki (min. 3 węzły, ~4 GB RAM/węzeł). OpenEBS LocalPV: bez replikacji. Na 1 węźle: `local-path` z k3s wystarczy |
| Postgres (Honcho) | **CloudNativePG**, 2 instancje + WAL do S3 (plugin Barman Cloud) | automatyczny failover, PITR. Zastępuje Postgres z docker compose |
| Redis (Honcho) | 1 instancja + AOF na Longhorn | cache/kolejka, HA niepotrzebne |
| SQLite Hermesa | StatefulSet 1 replika, wolumen RWO Longhorn | **nie NFS** (blokady SQLite) |
| Obiekty S3 (dla etcd/Velero/CNPG/Longhorn) | **Garage** na WD 3 TB (lekki, rozproszony S3) + kopia off-site borg/restic → Storage Box | MinIO community jest w trybie utrzymania; SeaweedFS też ok. Alternatywa płatna: Hetzner Object Storage |
| Kopie klastra | k3s `--etcd-s3` (co 6 h), **Velero** (obiekty + wolumeny przez kopię kopia) | odtworzenie całego klastra z zera z Gita + kopii |

Zasada 3-2-1: dane na wolumenach (Longhorn, 2 kopie) → Garage w labie → borg na Storage Box (zaszyfrowane)
+ dotychczasowy rclone crypt na Google Drive do czasu zakończenia migracji.

### 2.5 Sieć, dostęp, sekrety, GPU

| Obszar | Wybór |
|---|---|
| Sieć między węzłami | k3s z `--node-ip`/`--flannel-iface tailscale0` (albo `--vpn-auth=name=tailscale`); flannel wireguard-native |
| Dostęp z telefonu / tailnetu | **Tailscale Kubernetes Operator**: każdy Service/Ingress jako węzeł tailnetu z HTTPS (zastępuje `tailscale serve` dla Matrix, HA, Grafany); API klastra przez proxy operatora |
| Ingress wewnętrzny | Traefik z k3s (Gateway API) |
| Sekrety | **External Secrets Operator z providerem Bitwarden Secrets Manager** — te same nazwy sekretów co dziś (`lookup('bws_secret', …)`), token maszynowy jako jedyny sekret wstawiany ręcznie |
| Certyfikaty | Tailscale HTTPS; cert-manager tylko jeśli coś wyjdzie poza tailnet |
| GPU | sterownik NVIDIA 580 + CUDA 12 przez WOBI na węźle, **NVIDIA device plugin** (nie pełny GPU Operator: za ciężki, Pascal), `llama-server` (llama.cpp, CUDA) jako Deployment z `nodeSelector: gpu=gtx1070` |
| Polityki | Kyverno (lżejsze od OPA Gatekeeper): wymagane limity, zakaz `:latest`, zakaz hostPath poza wyjątkami |
| Usypianie labu | KEDA / „scale-to-zero” dla llama-server + Wake-on-LAN z innego węzła, jeśli lab nie będzie 24/7 |

### 2.6 Co z Proxmoxem

Proxmox HA też potrzebuje 3 węzłów (albo 2 + QDevice) i zjada RAM na hypervisor. Na lab-w01 (12 GB)
rekomenduję **k3s bezpośrednio na Ubuntu Server 24.04** (GPU bez passthrough, prościej dla agentów).
Proxmox wraca do gry, gdy będzie maszyna z 32 GB+ i potrzeba VM-ek (np. Windows, izolowane sandboksy),
wtedy węzeł k3s może być VM-ką na Proxmoxie bez zmian w reszcie planu.

---

## 3. Architektura docelowa

```
                Git (WOBI: OS/k3s/sterowniki · nowe repo hermes-gitops: wszystko w klastrze)
                       │ Renovate PR → review → merge
                       ▼
                    Argo CD ── auto-sync: dev, stage(efemeryczny) ── ręczny sync: prod
                       │
  ┌────────────────────┴───────────────── tailnet (Tailscale) ─────────────────────┐
  │ k3s-prod-1 (server)      k3s-prod-2 (server)       k3s-prod-3 (server)        │
  │ etcd · Longhorn          etcd · Longhorn           etcd · Longhorn            │
  │                                                                                 │
  │ lab-w01 (k3s agent, GPU): llama-server (czat lokalny, embeddingi, Whisper),     │
  │   Garage S3 na WD 3 TB, buildy/CI, workery kanban                               │
  └─────────────────────────────────────────────────────────────────────────────────┘
  Namespaces: hermes-prod · hermes-dev · hermes-stage-<pr> · honcho · home-automation · platform · observability
  Off-site: borg → Hetzner Storage Box · (przejściowo) rclone crypt → Google Drive
```

Mapowanie usług:

| Dziś (VM, systemd/docker) | W klastrze |
|---|---|
| hermes-gateway, cron, API :8642 | StatefulSet `hermes-gateway` (1 replika, PVC `~/.hermes`), Service + Tailscale |
| kanban-api (dev), workery kanban | `hermes-dev`: Deployment kanban-api + workery jako Jobs (git worktree na PVC) |
| honcho api/deriver | Deployment ×2 (api), ×1 (deriver) |
| honcho postgres / redis | CloudNativePG Cluster ×2 / Redis ×1 |
| ollama (embeddingi) | `llama-server --embedding` na GPU (ten sam model `qwen3-embedding-0.6B` w GGUF; **sprawdzić zgodność wektorów albo przeembeddować**) |
| Home Assistant + Whisper + Piper | StatefulSet z `hostNetwork` (wykrywanie urządzeń), Whisper na GPU |
| notification-bridge, timeplane-intake, contact-crm, Matrix (Continuwuity) | Deploymenty z Helm chartu `hermes-addon` (jeden wspólny chart) |
| Syncthing (Obsidian) | StatefulSet, PVC |
| hermes-backup.timer | CronJob + Velero/CNPG/etcd-s3 |
| host-daemon (cutover VM) | zastąpiony przez Argo CD + stage per PR; zostaje tylko do budowy VM-węzłów |

---

## 4. Plan migracji (fazy)

Każda faza kończy się czymś działającym i jest odwracalna. Fazy 0–4 **nie wymagają zakupów** poza SSD
i kablem, które są już w zadaniu T171.

### Faza 0 — Fundamenty (1–2 dni pracy agenta)
- Repo `hermes-gitops` (struktura: `clusters/<nazwa>/`, `apps/`, `platform/`, overlays `dev|stage|prod`).
- Chart `hermes-addon` + Dockerfile dla każdego dodatku; obrazy do GHCR (prywatne).
- `k3d` na dev VM: klaster `hermes-local` + Tiltfile dla 2 dodatków (notification-bridge, timeplane-intake).
- CI: `k3d` w GitHub Actions — lint (`kubeconform`, `kube-linter`), deploy do k3d, smoke test.
  (Uwaga: Actions na prywatnych repo blokuje limit wydatków — patrz otwarte problemy; ewentualnie runner
  self-hosted w klastrze przez Actions Runner Controller.)
- **Gotowe, gdy:** `tilt up` na dev uruchamia oba dodatki, a PR w `hermes-gitops` przechodzi CI.

### Faza 1 — Pierwszy węzeł k3s (`k3s-dev-1`) na lab-w01
- Wymaga: SSD, Ubuntu Server 24.04, AHCI, Cat6 (zadanie [T171](https://app.notion.com/p/lab-ubuntu-SSD-Cat6-cable-cooling-BIOS-and-Ubuntu-install-3ffee453d19e81a9a71feb2901bb0a38)).
- Nowa rola WOBI `k3s` (server/agent, `--cluster-init` od razu, żeby później dołożyć serwery bez
  przebudowy; Tailscale jako sieć; ufw), rola `nvidia` (sterownik 580, CUDA 12, container toolkit).
- Bootstrap Argo CD, ESO + Bitwarden, Tailscale Operator, `local-path`, Garage na WD 3 TB,
  NVIDIA device plugin, `llama-server` (embeddingi + llama-router Qwen3.5-4B przeniesiony z prod, co zwalnia ~4,1 GB RAM na hermes-prod-1). Przy 12 GB RAM: Flux zamiast Argo CD (sekcja 6.3).
- **Gotowe, gdy:** `kubectl get nodes` przez tailnet, Argo CD pokazuje wszystko „Synced/Healthy”,
  `llama-server` odpowiada z GPU.

### Faza 2 — Dev do klastra (najmniejsze ryzyko)
- `hermes-dev` namespace: kanban-api, workery kanban (Jobs), coding agents, repo/worktree na PVC.
- Prod (VM) przełącza `kanban_bridge` na adres w klastrze (Tailscale).
- Wyłączenie dev VM → **zwalnia 6 GB na laptopie**.
- **Gotowe, gdy:** tydzień zadań kanban przechodzi w klastrze bez regresji (porównanie z hbench).

### Faza 3 — Kopie i odtwarzanie (zanim cokolwiek z prod trafi do klastra)
- etcd-s3 → Garage, Velero → Garage, borg Garage → Storage Box, Longhorn (od fazy 5) → SMB Storage Box.
- **Test DR:** skasować klaster k3d/testowy i odtworzyć z Gita + kopii; zmierzyć czas (cel RTO < 2 h,
  RPO < 24 h dla danych Hermesa, < 5 min dla Postgresa).
- **Gotowe, gdy:** udokumentowane, udane odtworzenie z zera.

### Faza 4 — Prod do klastra (jeszcze bez HA)
- Kolejno, każda usługa z okresem równoległym: Honcho (CNPG, import dumpu; embeddingi z llama-server),
  dodatki, Matrix, Syncthing, Home Assistant, na końcu `hermes-gateway` z odtworzonym `~/.hermes`.
- Stage = ApplicationSet: PR do `hermes-gitops` → namespace `hermes-stage-<pr>` z odtworzoną kopią prod,
  bez platform czatu; Filip testuje przez Tailscale; merge + ręczny sync w Argo CD = cutover.
- VM prod zostaje wyłączona, ale nieusunięta, przez 2 tygodnie (rollback).
- **Uwaga:** w tej fazie lab-w01 jest pojedynczym punktem awarii **i musi działać 24/7** (~130 W,
  ok. 1 100 kWh/rok, szacunkowo ~1 100 zł/rok prądu). To argument za fazą 5 z mini PC.
- **Gotowe, gdy:** wszystkie testy kompatybilności z `prod-stage-dev-design.md` przechodzą w klastrze,
  a VM prod jest wyłączona.

### Faza 5 — Wysoka niezawodność (po decyzji o sprzęcie)
- 3 serwery k3s (etcd) w 3 maszynach. **Dwa serwery są gorsze niż jeden** (utrata jednego = brak kworum).
- Longhorn 3 repliki, CNPG 2–3 instancje, PodDisruptionBudgety, `topologySpreadConstraints`,
  priorytety (gateway, HA, Honcho > workery), limity zasobów wszędzie.
- Lab-ubuntu zostaje agentem GPU i może być usypiany (WoL + scale-to-zero llama-server).
- Ćwiczenia: co miesiąc wyłączenie losowego węzła (chaos „ręczny”, później Chaos Mesh / Litmus).
- **Gotowe, gdy:** wyłączenie dowolnego jednego węzła nie przerywa rozmowy z Hermesem na dłużej niż
  ~5 min (czas przeniesienia poda z wolumenem), a Home Assistant i Honcho wracają same.

### Faza 6 — Domknięcie
- Wycofanie host-daemona do roli „buduję VM-węzły”, archiwizacja ról WOBI zastąpionych przez klaster,
  aktualizacja `hermes-context/docs`, `features/registry.yaml` (wpisy: k3s, argocd, longhorn, cnpg…).
- Upgrade Hermesa z v0.20.0 przez stage per PR (dziś zablokowany przez brak pipeline’u stage).

### Faza 7 — Agenci Hermesa do utrzymania i obsługi klastra (nowa, na prośbę Filipa)

Cel: klaster utrzymuje się sam w rutynie, a Filip dostaje tylko decyzje. Agenci to profile Hermesa
(jak dziś `maintainer`, `architect`) z wąskimi uprawnieniami i własnymi skillami.

| Agent (profil) | Zakres | Uprawnienia | Wyzwalacz |
|---|---|---|---|
| `k8s-operator` | triage alertów (Alertmanager → webhook do Hermesa), diagnoza (`kubectl describe/logs/events`, k8sgpt), restart/rollout restart, skalowanie | ServiceAccount RBAC: odczyt wszystkiego, zapis tylko `pods/delete`, `deployments/scale`, `rollout restart` w swoich namespace’ach; **zero dostępu do Secretów** | alert, cron co 15 min |
| `k8s-upgrader` | przegląd PR-ów Renovate, czytanie changelogów, test na stage, upgrade k3s (system-upgrade-controller, po jednym węźle) | tylko Git (PR); merge/sync prod = Filip | cotygodniowo |
| `backup-warden` | sprawdza świeżość kopii (etcd, Velero, CNPG, borg), co miesiąc robi test odtworzenia do namespace’u `dr-test` i raport | zapis tylko w `dr-test`, odczyt statusu kopii | codziennie + co miesiąc |
| `capacity-planner` | z metryk (wątek observability) liczy zapas RAM/CPU/dysku/VRAM na węzłach, ocenia, czy nowa funkcja z planu się zmieści; aktualizuje kolektyw infrastruktury | tylko odczyt metryk | cotygodniowo + na żądanie researchera |
| `security-auditor` | kube-bench, Trivy Operator (CVE w obrazach), Kyverno raporty, rotacja tokenów | odczyt | cotygodniowo |

Zasady wspólne:
- Każda zmiana stanu klastra idzie przez **PR do `hermes-gitops`** (Argo CD wdraża), wyjątek: restart/skalowanie
  w ramach runbooka. Bez `kubectl apply` z ręki na prod.
- Runbooki jako skille (`skills/k8s/<problem>/SKILL.md`): pod w CrashLoop, węzeł NotReady, Longhorn degraded,
  CNPG failover, etcd bez kworum, dysk pełny, GPU niewidoczne.
- Budżet i kwoty: agenci liczą się do `budget.py`; diagnozy na tanim modelu, kod/PR przez Claude Code (`cc_run.py`).
- Raport: jeden dzienny skrót do Filipa tylko przy zmianach; pilne alerty natychmiast (ntfy/Matrix).
- Narzędzia: **k8sgpt** (z backendem lokalnym llama.cpp przez API zgodne z OpenAI), **kubectl-ai** (opcjonalnie),
  Headlamp jako UI tylko do odczytu, MCP server Kubernetesa dla agentów (tryb read-only domyślnie).
- **Gotowe, gdy:** przez 2 tygodnie wszystkie alerty z klasy „rutynowe” są zamykane bez Filipa, a test
  odtworzenia przechodzi automatycznie co miesiąc.

---

## 5. Decyzje dla Filipa

1. **Sprzęt do HA (faza 5)** — rekomendacja: **3 używane mini PC** (np. Lenovo M720q/M920q, Dell
   OptiPlex Micro; i5 8. gen., 16 GB, SSD), szacunkowo 600–900 zł/szt. z Allegro, ~10–15 W każdy
   (~35 W razem zamiast ~130 W labu 24/7; zwraca się w prądzie w ok. 1–1,5 roku — ceny szacunkowe, do
   sprawdzenia). Alternatywa bez zakupu: VM na laptopie + lab-w01 + mały VPS Hetzner jako trzeci
   członek etcd przez Tailscale (~5 €/mies.), ale lab musi wtedy działać 24/7, a laptop przestaje być
   „wyłączalny”. Trzecia opcja: zostać na jednym węźle i zdecydować po fazie 4.
2. **Argo CD vs Flux** — rekomendacja Argo CD (UI, bramka prod); zmiana później jest tania tylko do fazy 2.
3. **S3 lokalnie (Garage) czy Hetzner Object Storage** (~5 €/mies./TB) — rekomendacja Garage + borg
   na Storage Box, bo jest już opłacony.

## 6. Pojemność: czy się zmieści

Podstawa: kolektyw infrastruktury (`hermes-workspace/infra`, pomiary przez SSH 2026-10-22, przekazane przez
wątek „Centralna kolejka planów”) i dokumentacja. Nazwy wg `infra/naming.md`: laptop = **lab-ws01**,
worker lab-ubuntu = **lab-w01**, VM-ki od usługi (`hermes-prod-1`, `hermes-dev-1`, `k3s-dev-1`, …).
Liczby oznaczone „~” to szacunki; dokładne wartości RAM/dysku z `infra/hosts/*.md` trzeba wpisać, gdy plik
będzie dostępny w `/mnt/project-files` (z tego wątku nie mam dostępu do repo `hermes-workspace`).

### 6.1 Stan na 22.10

| Host | Zasoby | Zajęte | Wniosek |
|---|---|---|---|
| **lab-ws01** (laptop MSI GL75, i7-9750H, 32 GB, GTX 1650 Ti 4 GB) | C: **16 GB wolne**, D: **24 GB wolne** | VM prod 6 GB / 4 vCPU, VM dev 6 GB / 4 vCPU, Windows+Chrome ~18–22 GB | **brak miejsca na kolejne VM** — ani RAM, ani dysk (40 GB łącznie). Żaden węzeł k3s na laptopie. |
| **hermes-prod-1** (dziś `unity-orchestrator`, VM 6 GB / 4 vCPU wg pomiaru 22.10; dokumentacja mówi 8 GB) | wolny RAM do zmierzenia (20.10 przy 8 GB: ~3,5 GB), 36 GB dysku | gateway, Honcho, HA+Whisper+Piper, Matrix, Syncthing, **llama-router Qwen3.5-4B ~4,1 GB RSS na CPU** | najciaśniejsza maszyna; nic nowego na prod |
| **lab-w01** (i7-950, 12 GB DDR3, GTX 1070 8 GB, WD 3 TB) | po T171: SSD na system | dziś system live z pendrive'a, backup skończony | jedyne miejsce na k3s; plan wątku Homelab: KVM, **1 VM ≤ 6 GB / 4 vCPU**, NAT + Tailscale, pierwsza VM 26–27.10 |
| Monitoring | — | **żaden stos nie działa** | metryki do oceny pojemności będą dopiero po K11 (observability) |

### 6.2 Zużycie komponentów

| Komponent | RAM |
|---|---|
| k3s server (+etcd) | 0,6–1 GB |
| Argo CD | 0,7–1 GB (Flux: ~0,3 GB) |
| Longhorn | 0,3–0,5 GB / węzeł (na 1 węźle zamiast niego `local-path`: ~0) |
| ESO, Tailscale operator, device plugin, Kyverno, Velero | ~0,6 GB razem |
| Observability (K11) w wersji lekkiej (VictoriaMetrics + Alloy + Loki + Grafana) | 1–1,5 GB |
| Hermes dev (kanban-api + 1–2 workery + Claude Code) | 3–5 GB |
| Hermes prod (gateway + Honcho + CNPG + Redis + HA + dodatki, bez llama-router) | ~4–5 GB |
| llama-server na GTX 1070 (Qwen3.5-4B + embeddingi) | ~1–1,5 GB RAM + ~4–5 GB VRAM |

### 6.3 Rachunek per faza

- **Faza 1–2 na lab-w01 przy 12 GB, zgodnie z planem Homelab (VM `k3s-dev-1`, 6 GB):**
  w VM: k3s ~0,8 + Flux 0,3 (Argo CD 1 GB się nie zmieści) + dodatki 0,6 + dev 3–4 = **~5–6 GB → na styk**.
  Na hoście (poza VM): llama-server z GPU jako usługa systemd z roli WOBI, wystawiony do klastra jako
  Service bez selektora (GTX 1070 przez passthrough do VM na X58 jest niepewny — nie zakładam go). Host:
  ~1,5 GB system + 1,5 GB llama = 3 GB, razem z VM ~9 GB z 12. **Na runnery CI i observability (K11) brak
  miejsca** w tym samym czasie. Wniosek: przy 12 GB w fazie 1 GitOps = **Flux**, nie Argo CD (zmieniam
  rekomendację z 2.3 na czas jednego węzła).
- **Decyzja Filipa (2026-10-22, wątek Homelab): k3s bezpośrednio na hoście lab-w01, bez VM KVM.** Oszczędza
  ~1,5 GB narzutu VM i daje GPU w klastrze bez passthrough; runnery CI jako pody (ARC). Termin: po T171,
  realnie 26–27.10. Wariant z VM opisany wyżej przestaje obowiązywać.
- **Faza 2 zwalnia na lab-ws01 6 GB RAM i dysk VM dev** — to jest główna korzyść dla laptopa, który dziś
  ma tylko 40 GB wolnego dysku.
- **Faza 4 (prod do klastra) przy 12 GB: nie mieści się** (platforma ~2,5 + dev 3–4 + prod 4–5 + llama 1,5 +
  system 1,5 ≈ 13–15 GB). Warunek: **RAM 24 GB w lab-w01 (~100 zł)** albo osobny sprzęt z fazy 5.
  Przy 24 GB: ~15 GB zajęte + observability 1,5 GB → zapas ~7 GB, wtedy też Argo CD.
- **Przeniesienie llama-router z prod na GPU lab-w01** zwalnia ~4,1 GB RAM na hermes-prod-1 już w fazie 1
  (prod może wtedy wrócić do 5–6 GB albo przyjąć nowe usługi). To najszybszy zysk całego planu.
- **CPU:** i7-950 bez AVX — modele tylko na GPU; buildy obrazów w GitHub Actions/GHCR, nie na węźle.
- **Dysk:** etcd i wolumeny na SSD (nie WD HDD); WD 3 TB na Garage, modele GGUF, dane.
- **Prąd:** od fazy 4 lab-w01 musi działać 24/7 (~130 W, ~1 100 kWh/rok) — argument za fazą 5 z mini PC.
- **Wpływ na inne plany:** Jellyfin/Immich/NAS z raportu sprzętu i runnery CI konkurują o te same 12 GB;
  przed 24 GB RAM kolejność: llama-server → k3s dev → reszta.

## 7. Ryzyka

| Ryzyko | Mitygacja |
|---|---|
| Sieć klastra po Tailscale: awaria Tailscale = awaria klastra | wireguard bezpośredni (lub DERP) i tak; plan B: lokalny LAN, gdy węzły będą w jednym miejscu (mini PC) |
| SQLite Hermesa na wolumenie sieciowym | Longhorn RWO (blok), nigdy NFS; snapshot spójny przez `sqlite3 .backup` w CronJobie |
| Zmiana Ollama → llama.cpp dla embeddingów zmienia wektory | test zgodności, w razie różnicy pełny re-embedding w oknie serwisowym |
| Złożoność ponad potrzeby jednego użytkownika | fazy odwracalne; po fazie 2 ocena „czy warto dalej” |
| Stary sprzęt (X58, zasilacz z 2009) | lab jako agent, nie control-plane; HA na nowszym sprzęcie |
| GitHub Actions zablokowane na prywatnych repo | self-hosted runner (ARC) w klastrze |
| Wycieki sekretów z historii repo | ESO + Bitwarden, rotacja przed migracją (decyzja Filipa z 08-status) |

## 8. Źródła

- [K3s 1.37 release](https://docs.k3s.io/blog/2026/09/10/K3s-1.37-release), [K3s embedded etcd HA](https://oneuptime.com/blog/post/2026-03-20-k3s-embedded-ha-etcd/view)
- [k3s vs RKE2 vs Talos](https://wz-it.com/en/knowledge/kubernetes/k3s-vs-rke2-vs-talos/), [Talos na Proxmoxie — plusy i koszmary](https://darkstars.me/blog/20260225/)
- [Tilt: lokalny dev na Kubernetesie](https://oneuptime.com/blog/post/2026-01-19-kubernetes-tilt-local-development/view), [k3d + Tilt przykład](https://github.com/adavarski/k3d-tilt-development), [Flux + Tilt](https://oneuptime.com/blog/post/2026-03-06-use-flux-cd-tilt-local-development/markdown)
- [Argo CD vs Flux 2026](https://oneuptime.com/blog/post/2026-02-26-argocd-vs-fluxcd-2026/view), [turbogeek: GitOps 2026](https://www.turbogeek.co.uk/gitops-argocd-vs-flux-2026/)
- [Longhorn vs Rook-Ceph](https://wz-it.com/en/knowledge/kubernetes/longhorn-vs-rook-ceph/), [Ceph vs Longhorn](https://oneuptime.com/blog/post/2026-03-31-rook-compare-ceph-vs-longhorn-kubernetes/view)
- [CloudNativePG + S3](https://oneuptime.com/blog/post/2026-09-18-cloudnativepg-minio-s3-iam-ca-path-style/view), [Barman Cloud Plugin](https://cloudnative-pg.io/plugin-barman-cloud/docs/0.4.0/intro/)
- [Tailscale Kubernetes Operator](https://tailscale.com/docs/kubernetes), [ingress przez operatora](https://tailscale.com/kb/1439/kubernetes-operator-cluster-ingress)
- Wewnętrzne: `hermes-context/docs/02,04,08`, `prod-stage-dev-design.md`, [raport lab-ubuntu](https://claude.ai/artifact/C83TRNyf8jZz3NdUut2mhe), WOBI `bootstrap-usb/README.md`
