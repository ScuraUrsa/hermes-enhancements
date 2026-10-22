# Observability, telemetria i monitoring dla Hermesa i homelabu

- **Data:** 2026-10-22
- **Wątek:** [Observability i monitoring](#cmsg_015HTwbUuT8LqRHP4MjSVwTETrhDe1eE4jFYniz1T8aLpM)
- **ID w kolejce:** K11
- **Etap:** czeka na Filipa (decyzje w §7; wdrożenie po K03/T171 i K12 faza 1)
- **Priorytet:** P1
- **Infrastruktura sprawdzona:** 2026-10-22, [hermes-workspace/infra](https://github.com/ScuraUrsa/hermes-workspace/tree/claude/project-thread-5906j7/infra)
- **Zależności:** K03 (T171), K12 faza 1 (k3s na lab-w01), K15 (upgrade Hermesa, dla fazy 2), K18 (Alloy na prod), K40 (faza 6)

Kontekst homelabu: wątek [Homelab z Proxmox i k3s](#cmsg_015HTwbUuT8LqRHP4MjSVwTE6NZbGr5kwwTWS6sAHenMqH), [raport sprzętu lab-ubuntu](https://claude.ai/artifact/C83TRNyf8jZz3NdUut2mhe).

## 1. Rekomendacja w skrócie

**Stack: Grafana + Prometheus + Loki + Tempo + Alertmanager, zbierane jednym agentem Grafana Alloy (dystrybucja OpenTelemetry Collectora) na każdym węźle.** Wszystko open source (AGPL/Apache), darmowe, najpopularniejsze w świecie Kubernetes i ma gotowe charty Helm pod k3s.

| Warstwa | Wybór | Dlaczego |
|---|---|---|
| Zbieranie (agent) | **Grafana Alloy** na każdym hoście / DaemonSet w k3s | Jeden agent na metryki, logi i trasy; przyjmuje OTLP; zastąpił Promtail (EOL 2026-03-02) i Grafana Agent |
| Standard telemetrii | **OpenTelemetry (OTLP)** | Hermes już umie wysyłać OTLP (od 2026-10-12 w upstreamie, patrz §3) |
| Metryki | **Prometheus** (1 instancja, retencja 30 dni) | Standard de facto, PromQL, kube-prometheus-stack |
| Logi | **Loki** (tryb monolityczny, dysk lokalny) | Tani w RAM, ten sam język etykiet co Prometheus |
| Trasy (traces) | **Tempo** (monolityczny) | Natywnie w Grafanie, łączy trasy z logami i metrykami; Jaeger v2 jako alternatywa |
| Wizualizacja | **Grafana** | Dashboardy dla wszystkiego powyżej + k3s, GPU, SMART, VM-ki |
| Alerty | **Alertmanager** → Matrix (osobny bot) + e-mail jako fallback + **Healthchecks.io** jako „dead man's switch” | Alert o tym, że monitoring sam padł |
| Uptime z zewnątrz | **Uptime Kuma** (lub Gatus) poza głównym hostem | Proste sprawdzanie „czy usługa odpowiada” i strona statusu |
| LLM / agent (opcjonalnie, później) | **Langfuse** (MIT, self-host) | Trasy promptów, tokeny, koszty per sesja; zastąpiłby część trace-dashboard |

**Czego nie bierzemy na start i dlaczego:**
- **Zabbix / Checkmk**: świetne do klasycznego monitoringu serwerów i sieci (SNMP, agenty, szablony), ale to drugi, równoległy świat obok Kubernetesa: własna baza SQL, własny agent, słabe wsparcie OTel (w Zabbix 8.0 OTel jest dopiero na roadmapie). Dla jednej osoby utrzymywanie dwóch systemów to podwójna praca. Wrócić do Checkmk Community tylko, gdyby pojawiło się dużo sprzętu sieciowego (switche, UPS przez SNMP); to i tak da się zrobić eksporterem SNMP w Prometheusie.
- **Thanos**: rozwiązuje długą retencję i wiele klastrów Prometheusa. Przy jednym klastrze i 30 dniach retencji to zbędna złożoność. Furtka: faza 5 (Thanos sidecar albo VictoriaMetrics), gdy będzie potrzeba trzymania metryk ponad rok.
- **Jaeger**: dobry, ale Tempo lepiej spina się z Grafaną i Loki. Jaeger v2 jest zbudowany na OTel Collectorze, więc zamiana później jest łatwa (Hermes wysyła OTLP, nie format Jaegera).

## 2. Co chcemy widzieć (zakres)

1. **Sprzęt i hosty**: CPU, RAM, dysk, temperatura (lab-ubuntu grzał się do 78 °C), **SMART dysków** (Seagate miał 141 przeniesionych sektorów i nikt o tym nie wiedział), sieć (link 100 Mb/s zamiast 1 Gb/s), GPU GTX 1070 (VRAM, temperatura, użycie przez llama.cpp).
2. **Wirtualizacja**: VirtualBox na laptopie (stan VM prod/dev), w przyszłości VM na lab-w01 (Proxmox odpadł: decyzja z 22.10 to k3s bezpośrednio na hoście lab-w01).
3. **k3s**: węzły, pody, restarty, PVC, certyfikaty, zdarzenia.
4. **Usługi Hermesa** na prod/dev/stage: `hermes-gateway` (żyje? platformy? cron spóźniony?), kanban API, Honcho (api/deriver/postgres/redis), Home Assistant + Whisper + Piper, notification bridge, timeplane intake, Syncthing, Matrix, Tailscale, trace-dashboard.
5. **Zadania okresowe**: nocny backup (`hermes-backup.timer`; był już cichy błąd 2026-10-10), backup borg na Storage Box, autonomy cron (planner, CI watchdog, pr-merge-watch), google-token-check.
6. **Koszty i LLM**: tokeny/koszt per provider (Ollama cloud, Claude), budżet self-work (przekroczony 2026-10-08), wywołania Honcho.
7. **Logi** wszystkich powyższych w jednym miejscu, z wyszukiwaniem.

## 3. Co już istnieje (żeby nie dublować)

| Element | Gdzie | Co z nim zrobić |
|---|---|---|
| **Eksport OTLP w Hermesie** (`monitoring.export.otlp`, metryki `hermes.gateway.up`, `hermes.platform.up`, cron heartbeat/overdue, trasy cyklu życia crona, logi błędów, bez treści) | upstream `hermes-agent`, plik `agent/monitoring/otlp_exporter.py`, dokumentacja `website/docs/developer-guide/gateway-monitoring.md`; dodany 2026-10-12 | **VM-ki działają na v0.20.0 (a6ede70), które tego jeszcze nie ma.** Wymaga upgrade'u Hermesa (fork PR #5 / replica przez stage). Do tego czasu: blackbox + logi journald |
| `hermes-host-daemon` `health_monitor.py` | `hermes-infra` | Zostaje do autonaprawy VM; może wystawić `/metrics` dla Prometheusa (mała zmiana) |
| trace-dashboard (prompt → sesje → PR, koszty) | WOBI rola `trace_dashboard`, `hermes-enhancements` | Zostaje; ewentualnie zastąpić Langfuse w fazie 5 |
| Honcho `telemetry-sink` | WOBI rola `honcho` | Zostaje (to telemetria Honcho, nie infrastruktury) |
| Notification bridge `:8655` | prod | 0 klientów, przewidziany do wycofania, więc **nie** jest kanałem alertów. Alerty idą do Matrix |
| `collect-nodes.py` (WOBI `bootstrap-usb/`), cron `quota-governor`, `gh-actions-watchdog`, `autonomy-budget-governor` | prod | Źródła danych dla eksportera-skryptu w fazie 2 |

## 4. Porównanie narzędzi

| Narzędzie | Do czego | Licencja / koszt | Plusy | Minusy dla nas | Werdykt |
|---|---|---|---|---|---|
| **Prometheus 3.x** | metryki, alerty (z Alertmanagerem) | Apache 2.0 | standard k8s, ogromny ekosystem eksporterów, natywny odbiór OTLP | sam nie trzyma długo danych, sam nie robi HA | **TAK** |
| **Grafana** | dashboardy, alerting | AGPL 3.0 | jeden widok na wszystko, tysiące gotowych dashboardów | — | **TAK** |
| **Loki 3.x** | logi | AGPL 3.0 | lekki (indeksuje tylko etykiety), LogQL jak PromQL; chart Helm przeniesiony do `grafana-community` (2026-03) | wyszukiwanie pełnotekstowe wolniejsze niż Elastic | **TAK** |
| **Tempo** | trasy | AGPL 3.0 | tani storage (pliki/S3), link trace↔log↔metryka w Grafanie | mniej wygodny UI wyszukiwania niż Jaeger | **TAK** |
| **Alloy** | agent zbierający | Apache 2.0 | jeden agent na wszystko, OTel w środku, konwerter z Promtail/Agent | własny język konfiguracji (River) | **TAK** |
| **OpenTelemetry** | standard + SDK + Collector | Apache 2.0 | niezależność od dostawcy; Hermes już go używa | sam nie przechowuje danych | **TAK** (jako protokół) |
| **Jaeger v2** | trasy | Apache 2.0 | dojrzały UI, oparty na OTel Collectorze | osobny UI i storage obok Grafany | alternatywa dla Tempo |
| **Thanos** | długa retencja i HA Prometheusa, S3 | Apache 2.0 | nieskończona retencja w S3, globalne zapytania | sidecar/store/compactor/querier: dużo części | później, jeśli potrzeba |
| **VictoriaMetrics** | zamiennik Prometheusa/Thanosa | Apache 2.0 | 3–7× mniej RAM i dysku, łatwa długa retencja | mniejsza społeczność, część funkcji klastrowych w wersji enterprise | plan B przy braku RAM |
| **Zabbix 7.0 LTS / 8.0 LTS** | klasyczny monitoring serwerów i sieci | AGPL 3.0 | wszystko w jednym, SNMP, autodiscovery, mapy | baza SQL, ciężki, słaby fit z k8s; OTel dopiero na roadmapie 8.0 | NIE (na teraz) |
| **Checkmk Community** (dawniej Raw, zmiana nazw 2026-03) | monitoring serwerów i sieci | GPL, wersja Community darmowa | świetne autowykrywanie, gotowe checki | ograniczenia vs Pro, osobny świat obok k8s | NIE (na teraz) |
| **Netdata** | monitoring hosta w czasie rzeczywistym | agent GPL, UI częściowo zamknięte | zero konfiguracji, piękne wykresy per sekunda | chmura/UI nie w pełni open source, dubluje Prometheusa | opcjonalnie do debugowania |
| **Uptime Kuma** | sprawdzanie dostępności, status page | MIT | 5 minut do działania, powiadomienia w 90+ kanałach | brak metryk wewnętrznych | **TAK** (zewnętrzny strażnik) |
| **Gatus** | jak wyżej, konfiguracja w YAML | Apache 2.0 | konfiguracja jako kod (pasuje do WOBI) | brak UI do edycji | alternatywa dla Kuma |
| **Beszel** | lekki monitoring hostów i Dockera | MIT | bardzo lekki, ładny | dubluje node-exportera | NIE |
| **SigNoz / OpenObserve** | wszystko w jednym na OTel (ClickHouse) | Apache/AGPL | jeden produkt zamiast czterech | ClickHouse ciężki na RAM, mniejszy ekosystem | NIE |
| **Langfuse** | obserwowalność LLM (prompty, tokeny, koszty) | MIT (self-host bez limitów) | standard dla agentów, przyjmuje OTLP | wymaga ClickHouse + Redis + S3 | faza 5, opcjonalnie |
| **Healthchecks.io** | dead man's switch dla cronów | BSD (self-host) lub darmowy plan SaaS | alarm, gdy coś *nie* zadzwoniło (backup, monitoring) | SaaS = zewnętrzna usługa | **TAK** (darmowy plan) |

## 5. Architektura docelowa

```
 lab-w01 (worker, zawsze włączony, k3s na hoście)            lab-ws01 (laptop, VirtualBox; śpi i podróżuje)
 ┌──────────────── namespace monitoring ────────────────┐    ┌──────────── VM prod / VM dev ────────────┐
 │ Prometheus (15–30 d) ── Alertmanager ──► Matrix bot   │    │ Alloy (host metrics, journald, docker)   │
 │ Loki (SingleBinary, PVC na SSD)       └► e-mail       │◄───│ Hermes gateway ──OTLP──► Alloy :4318      │
 │ Grafana (tailscale serve, tylko tailnet)              │ Tailscale (remote_write / Loki push / OTLP) │
 │ Alloy DaemonSet (k8s logs, kubelet, cAdvisor),        │    └──────────────────────────────────────────┘
 │ kube-state-metrics, nvidia_gpu_exporter, smartctl     │
 │ Tempo (dopiero faza 4)                                │    Healthchecks.io (SaaS, poza domem) ◄── ping z:
 └───────────────────────────────────────────────────────┘    Alertmanager Watchdog, hermes_backup.sh, borg
 Uptime Kuma / Gatus na prod VM: sprawdza Grafanę i lab-w01 z drugiej maszyny
```

Zasady:
- **Dostęp tylko przez Tailscale** (`tailscale serve`), jak trace-dashboard. Żadnych portów na 0.0.0.0.
- **Wszystko jako kod**: wartości Helm, dashboardy i reguły alertów w repo (GitOps przez Flux, zgodnie z planem K12); rola WOBI `alloy` dla VM-ek na laptopie.
- **Sekrety** (klucz Healthchecks, token bota Matrix) z Bitwardena, jak w innych rolach.
- **Bez treści**: Hermes eksportuje wyłącznie metadane (tak jest zaprojektowany jego eksporter); logi z promptami nie trafiają do Loki bez filtra redakcji w Alloy.
- **Bot Matrix osobnym kontem**, nigdy z `MATRIX_DEVICE_ID` gatewaya (znana pułapka: CLI unieważnia token gatewaya).
- **Laptop to nie serwer**: VM-ki znikają, gdy laptop śpi. Alert „prod niedostępny” ma krótkie okno ciszy i reguły inhibicji, żeby nie budzić Filipa za każdym zamknięciem klapy.

Budżet zasobów w wersji odchudzonej (5 hostów, retencja 15 dni metryki / 14 dni logi): Prometheus ok. 0,8–1,2 GB RAM / ~8 GB dysku, Loki ok. 0,4–0,6 GB / ~15 GB, Grafana ~0,2 GB, Alertmanager + kube-state-metrics + eksportery ~0,2 GB, Alloy ~0,1–0,15 GB na hosta. **Razem ok. 2–2,5 GB RAM i ~25–30 GB dysku na lab-w01** (Tempo dochodzi w fazie 4: +0,3 GB).

## 5a. Czy to się zmieści (stan zmierzony 2026-10-22 w [hermes-workspace/infra](https://github.com/ScuraUrsa/hermes-workspace/tree/claude/project-thread-5906j7/infra))

| Host | Zmierzone zasoby | Co tam już jest / będzie | Wpływ stacku | Mieści się? |
|---|---|---|---|---|
| **lab-ws01** (laptop MSI GL75, i7-9750H, 31,8 GB) | 12 GB oddane VM-kom, ok. 19 GB RAM wolne, **dyski pełne: C: 16 GB, D: 24 GB wolne** | VM prod (6 GB), dev (6 GB), stage na żądanie | żadnej nowej VM na monitoring: dysk nie pozwala | **NIE** na backendy |
| **prod VM** (4 vCPU, 6 GB RAM, 35 GB wolne) | llama-router zajmuje ok. 4,1 GB RSS, najciaśniejsza maszyna | gateway, Honcho, HA + Whisper + Piper, Matrix, timeplane, Syncthing | tylko Alloy (~0,1–0,15 GB) i Uptime Kuma (~0,1 GB) | **tak, ale dopiero po K18** (przeniesienie llama-router na GPU lab-w01 zwolni ok. 4 GB). Przed K18 tylko Healthchecks (0 RAM) |
| **dev VM** (4 vCPU, 6 GB RAM, **18 GB wolne**) | kanban, workery, Claude Code | — | tylko Alloy; backendy (3+ GB RAM, 25+ GB dysku) się nie mieszczą | **tylko Alloy** |
| **lab-w01** (i7-950 bez AVX, 12 GB RAM, GTX 1070, SSD po T171) | dziś system live z pendrive'a (restart kasuje wszystko) | po T171: k3s na hoście (~1 GB), llama.cpp na GPU (VRAM, ~1 GB RAM), runnery CI jako pody, część planu K12 | backendy ok. 2–2,5 GB RAM, 25–30 GB na SSD | **tak, po T171** (termin 25.10, k3s realnie 26–27.10). Przy 12 GB to ok. 20% RAM; przy pełnym planie K12 na styk, więc retencja krótka, a po RAM 24 GB (K19) można ją wydłużyć |

**Wnioski i zmiana względem pierwszej wersji planu:**
1. Backendy monitoringu stawiamy od razu na **lab-w01 w k3s** (faza 1 i 3 łączą się w jedną). Wariant z dev VM odpada (18 GB wolnego dysku, 6 GB RAM).
2. Do czasu T171 robimy tylko fazę 0 (Healthchecks, smartd), bo na lab-w01 nic nie przeżyje restartu.
3. Kolejność z kolejką: **K03/T171 → K12 faza 1 (k3s) → K11 faza 1**. K18 (llama-router na GPU) odblokowuje Alloy na prod.
4. Wpływ na resztę: backup nie rośnie (dane monitoringu są odtwarzalne i wykluczone z backupu, kopia tylko konfiguracji w git); limity Ollama/Claude nie są dotykane do fazy 6 (agent); prąd: lab-w01 i tak ma być zawsze włączony.
5. Ryzyko: monitoring i monitorowany klaster na jednej maszynie. Gdy lab-w01 padnie, padnie też Grafana. Dlatego strażnik z zewnątrz (Healthchecks.io z Watchdogiem Alertmanagera) i Uptime Kuma na prod.
6. Plan B przy braku RAM: **VictoriaMetrics single + VictoriaLogs** zamiast Prometheusa i Loki (ok. 2–3× mniej RAM, te same dashboardy Grafany, PromQL zgodny).

## 6. Plan wdrożenia (kolejka)

Każdy krok to osobne zadanie z kryterium „gotowe”. Kroki 1–2 nie czekają na k3s.

### Faza 0: szybkie wygrane, bez nowej infrastruktury (1 dzień)
1. **Dead man's switch dla backupów**: darmowe konto Healthchecks.io, ping na końcu `hermes_backup.sh`, borg na Storage Box i `pr-merge-watch`. Klucz w Bitwardenie.
   *Gotowe gdy:* brak nocnego backupu = mail/powiadomienie do Filipa następnego ranka.
2. **SMART i temperatury na lab-ubuntu**: `smartd` z mailem (od razu) i później `smartctl_exporter`.
   *Gotowe gdy:* wzrost przeniesionych sektorów lub temperatura > 80 °C wywołuje alert.

### Faza 1: stack w k3s na lab-w01 (po T171 i K12 faza 1, ok. 2–3 dni)
3. W repo GitOps (Flux, wg K12): `kube-prometheus-stack` (Prometheus Operator, Prometheus, Alertmanager, Grafana, kube-state-metrics, node-exporter) z retencją 15 d i limitami RAM, Loki (chart `grafana-community/loki`, SingleBinary, filesystem na SSD, retencja 14 d), Alloy jako DaemonSet. Alternatywnie chart `grafana/k8s-monitoring`, który składa Alloy za nas. Grafana przez `tailscale serve`.
4. Rola WOBI `alloy` na VM dev (od razu) i prod (po K18): metryki hosta (wbudowany node exporter), journald (unity `hermes-*`, `timeplane-intake`, `kanban-api`), logi Dockera (Honcho, HA, Matrix), cAdvisor. Wysyłka przez Tailscale do lab-w01 (remote_write / Loki push). Bufor na dysku, żeby po uśpieniu laptopa dane doszły.
5. Eksportery: `nvidia_gpu_exporter` na lab-w01 (GTX 1070; DCGM nie wspiera kart konsumenckich), `smartctl_exporter`, `blackbox_exporter` na HTTP: gateway API :8642, HA :8123, Honcho :8100, kanban API :8787, timeplane intake :8790, Matrix; stan unitów i timerów systemd.
6. Alerty startowe (pliki reguł w repo):
   - host niedostępny > 5 min (dla VM na laptopie: z inhibicją, gdy cały laptop śpi); dysk > 85 % (dev VM i laptop już są blisko!); SMART reallocated/pending > 0 lub rośnie; temperatura CPU > 80 °C / GPU > 85 °C;
   - unit `hermes-gateway`, `kanban-api`, kontener Honcho/HA/Matrix nie działa;
   - `hermes-backup` ostatni sukces > 26 h (plus Healthchecks z fazy 0);
   - endpoint z blackboxa nie odpowiada > 3 min; certyfikat wygasa < 14 dni;
   - `Watchdog` (zawsze płonie) → Healthchecks.io: cisza = monitoring padł.
7. Kanał alertów: Alertmanager → bot Matrix (np. `matrix-alertmanager-receiver`, osobne konto w Continuwuity, pokój „alerty”) + fallback e-mail z Gmaila. Grupowanie i cisza nocna (poza krytycznymi).
   *Gotowe gdy:* zatrzymanie `hermes-gateway` na prod daje wiadomość w Matrix w < 5 min, a wznowienie daje „resolved”; adres Grafany wpisany w [hermes-workspace/infra/README.md](https://github.com/ScuraUrsa/hermes-workspace/tree/claude/project-thread-5906j7/infra) w sekcji monitoringu.
8. Uptime Kuma (lub Gatus z konfiguracją w WOBI) na **prod VM** (po K18), sprawdza Grafanę i lab-w01 z drugiej maszyny.

### Faza 2: telemetria samego Hermesa (po upgrade'zie Hermesa z v0.20.0)
9. Po upgrade'zie (fork PR #5 / cutover przez stage) włączyć w `config.yaml`: `monitoring.gateway_health_export.enabled: true`, `monitoring.export.otlp.endpoint: http://127.0.0.1:4318/v1/traces` (lokalny Alloy), zainstalować extra `otlp`. Ustawić to w roli WOBI `hermes`.
10. Reguły z dokumentacji Hermesa: `hermes_gateway_up == 0`, `absent_over_time(hermes_gateway_up[5m])`, `hermes_platform_up == 0`, `hermes_cron_scheduler_heartbeat_age_seconds > 180`, `hermes_cron_jobs_overdue > 0`. Dashboard „Hermes gateway” (gateway, platformy, cron, aktywni agenci, kanban workers).
11. Metryki biznesowe z istniejących danych (eksporter-skrypt czytający `state.db`/`kanban.db`): karty kanbanu wg stanu, zablokowane > 24 h, wydany budżet self-work vs limit, tokeny/koszt per provider. Alerty na przekroczenie budżetu.
   *Gotowe gdy:* dashboard pokazuje stan Hermesa i budżetu bez logowania na VM.

### Faza 3: dojrzałość konfiguracji
12. Dashboardy, reguły i datasources jako ConfigMapy w repo; `flux reconcile` odtwarza cały monitoring od zera. Test: skasować namespace `monitoring` i sprawdzić, że wraca sam z dashboardami.
13. Gdy dojdą kolejne węzły (K12, 3 mini PC): Prometheus z PVC na Longhorn albo druga replika; wtedy wraca temat Thanos/VictoriaMetrics cluster.

### Faza 4: trasy end-to-end
14. Tempo (monolit, +0,3 GB RAM) w k3s. Trasy z usług własnych (timeplane intake, kanban API, contacts CRM) przez OTel SDK dla Pythona (auto-instrumentacja aiohttp/FastAPI) → Alloy → Tempo. Korelacja trace_id w logach.

### Faza 5: opcjonalnie, gdy będzie potrzeba
15. **Langfuse** (self-host) dla tras LLM: prompt → narzędzia → koszt per sesja i profil; porównanie z trace-dashboard i ewentualne zastąpienie.
16. **Długa retencja**: Thanos sidecar albo VictoriaMetrics + obiektowy storage (Garage/SeaweedFS na WD 3 TB w lab-w01; Hetzner Storage Box nie ma S3). Downsampling do roku.
17. **Monitoring sieci** (SNMP z routera/switcha/UPS) przez `snmp_exporter`; dopiero tu rozważyć Checkmk/Zabbix, jeśli sprzętu sieciowego będzie dużo.

### Faza 6: agenci Hermesa do utrzymania i obsługi monitoringu
18. **Profil `sre` (lub rozszerzenie `maintainer`)** z SOUL.md opisującym runbooki i zasady bezpieczeństwa. Narzędzia jako skille: `prom_query` (PromQL przez API Prometheusa), `loki_query` (LogQL), `alerts_list` / `silence_create` (API Alertmanagera), `grafana_snapshot` (link do panelu), plus istniejący SSH do VM.
19. **Obsługa alertów**: Alertmanager wysyła webhook także do Hermesa (kanban API lub nowy endpoint w gatewayu). Każdy alert = karta kanbanu dla profilu `sre` z linkiem do panelu. Agent: zbiera kontekst (metryki, logi z 15 min wokół, `systemctl status`), diagnozuje i:
    - **naprawia sam** tylko akcje z listy dozwolonych i odwracalnych: restart unitu/kontenera, czyszczenie cache/starych obrazów Dockera, ponowne uruchomienie backupu, `kubectl rollout restart`;
    - **zakłada kartę / PR** dla zmian w kodzie lub konfiguracji (np. próg alertu, poprawka roli WOBI) przez istniejący delivery gate;
    - **pyta Filipa** (zadanie w timeplane, zgodnie z regułą projektu) przy wszystkim nieodwracalnym: usuwanie danych, zmiany na produkcji poza listą, wymiana sprzętu (np. SMART rośnie → zadanie „kup dysk” z linkami).
    Każda akcja agenta trafia do Loki jako zdarzenie audytu i jako adnotacja w Grafanie.
20. **Codzienny raport zdrowia** (cron rano, dołączony do planu dnia timeplane): co płonęło, co agent naprawił, trendy (dysk zapełni się za N dni, rośnie SMART, koszty LLM vs budżet).
21. **Utrzymanie samego stacku**: cotygodniowy przegląd przez agenta: hałaśliwe alerty (do strojenia), zaległe wyciszenia, nowe wersje chartów Helm (PR z podbiciem wersji przez Renovate lub agenta), test odtworzenia Grafany z repo, zapełnienie PVC.
22. **Bezpiecznik**: limit napraw na godzinę (np. 3 restarty tej samej usługi → stop i eskalacja do Filipa), budżet tokenów agenta liczony w governorze, tryb „tylko diagnoza” na pierwsze 2 tygodnie.
    *Gotowe gdy:* zatrzymany kontener (np. Honcho deriver) zostaje wykryty, zrestartowany przez agenta i opisany w raporcie bez udziału Filipa, a próba usunięcia danych kończy się pytaniem do Filipa.

## 7. Decyzje dla Filipa

1. **Kanał alertów**: Matrix (osobny bot) + e-mail jako fallback. Rekomendacja: tak, bo notification bridge ma 0 klientów i idzie do wycofania.
2. **Healthchecks.io (darmowy SaaS) czy self-host**: rekomendacja SaaS, bo strażnik musi żyć poza domem.
3. **Gdzie backendy**: lab-w01 w k3s po T171 (rekomendacja; laptop ma pełne dyski, dev VM 18 GB wolnego) czy zamiast tego wydzielić je na osobny, tani sprzęt (np. jeden z planowanych mini PC z K12), żeby monitoring nie padał razem z klastrem.
4. **Agent `sre`**: od razu z autonaprawą z listy dozwolonych, czy 2 tygodnie tylko diagnozy (rekomendacja: najpierw diagnoza).

## 8. Źródła

- Hermes: `agent/monitoring/otlp_exporter.py`, `website/docs/developer-guide/gateway-monitoring.md` w [ScuraUrsa/hermes-agent](https://github.com/ScuraUrsa/hermes-agent) (eksport OTLP dodany 2026-10-12)
- [Promtail EOL 2026-03-02 i migracja do Alloy](https://blog.elest.io/promtail-is-dead-how-to-migrate-your-log-pipeline-to-grafana-alloy-before-it-breaks/), [Alloy: migracja z Promtail](https://grafana.com/docs/alloy/next/set-up/migrate/from-promtail/), [Loki 3.4: Promtail łączy się z Alloy](https://grafana.com/blog/grafana-loki-3-4-standardized-storage-config-sizing-guidance-and-promtail-merging-into-alloy/?pg=blog)
- [Loki: chart Helm przeniesiony do grafana-community](https://github.com/grafana/loki/issues/20705), [Loki monolithic Helm](https://grafana.com/docs/loki/latest/installation/helm/install-monolithic/)
- [Grafana k8s-monitoring Helm chart](https://grafana.com/docs/grafana-cloud/monitor-infrastructure/kubernetes-monitoring/configuration/helm-chart-config/helm-chart)
- [Zabbix 8.0: co się zmienia (OTel tylko na roadmapie)](https://everywan.com/en/blog/zabbix-8-0-what-actually-changes)
- [Nowe edycje Checkmk (Raw → Community, 2026-03)](https://checkmk.com/blog/meet-new-checkmk-lineup)
- [Jaeger vs Tempo](https://signoz.io/blog/jaeger-vs-tempo), [Tempo vs Jaeger (Last9)](https://last9.io/blog/grafana-tempo-vs-jaeger)
- [Narzędzia obserwowalności agentów AI 2026 (Langfuse MIT, przejęcia)](https://www.morphllm.com/ai-agent-observability-tools)
- [Najlepsze self-hosted narzędzia monitoringu 2026](https://selfhosting.sh/best/monitoring/), [Uptime Kuma vs Beszel](https://selfhosting.sh/compare/uptime-kuma-vs-beszel/), [Uptime Kuma vs Gatus](https://openalternative.co/compare/gatus/vs/uptime-kuma)
