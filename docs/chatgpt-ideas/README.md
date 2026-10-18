# Ideas from Filip's ChatGPT history (plans only)

Source: the ChatGPT data export of the **fjkazmierczak** account, dated 2026-10-18 (90 conversations, 2024-02 to 2026-10).
Kanban task `chatgpt-ideas`.

These docs are **plans only**. Nothing here is implemented, installed or deployed. They contain summaries, not
conversation dumps, personal data or secrets.

## How this was built
1. **Technical filter.** About 70 of the 90 conversations are technical (software, infra, AI, devices, networking). The rest (cooking, music, law, military service, language, philosophy) were skipped. Most technical chats were one-off work troubleshooting: Terraform, Ansible or Azure Pipelines errors. Those are not ideas in their own right, so they were folded into the idea they support (02, 18) or dropped.
2. **Grouping.** One idea is one thing Filip wanted to build, buy, set up or learn. This gives 20 ideas.
3. **Dedupe.** Each idea was checked against `hermes-workspace/HERMES_MAP.md` (+ ARCHITECTURE, tasks), this repo,
   WOBI `iac/final`, `~/.hermes/skills` and `~/.hermes/autonomy/{roadmap,decision_log}.md`.
4. **Plans.** Local models run via llama.cpp only, never local Ollama. Ollama is used only for its cloud models.

**Status:**
- **new**: nothing in Hermes yet
- **partly**: building blocks exist (see each doc)
- **done**: already covered

**Priority:**
- **P1**: high value for Hermes now
- **P2**: worth planning soon
- **P3**: useful, no urgency
- **P4**: nice-to-have or decision-only
- **P5**: parked exploration

## Index

| # | Idea | Status vs Hermes | Priority | Doc |
|---|---|---|---|---|
| 03 | AI coding-rules meta-repo (rules from books/videos, checked in PR review) | partly: `authoring-rules` skill, marker OCR skill, video-digest | P1 | [03](03-ai-coding-rules-repo.md) |
| 17 | Turn recurring LLM work into deterministic code (cost boundary) | partly: `hermes-scripted-cron`, `teach-procedures`, rule-first triage | P1 | [17](17-llm-to-algorithm-distillation.md) |
| 01 | Workstation as code (WSL/laptop → image → remote dev desktop) | partly: `packer-images` (Hermes VM only), `laptop_host` role | P2 | [01](01-workstation-as-code.md) |
| 04 | Self-learning tool researcher (endless queue, sandbox, skills) | partly: 2026-08 research/POC series, roadmap C3, `technical-research-pov` | P2 | [04](04-self-learning-tool-researcher.md) |
| 06 | Better robot vacuum, cloud-free (Valetudo + HA + tidy-up help) | partly: Home Assistant + Polish voice on prod | P2 | [06](06-robot-vacuum-valetudo.md) |
| 16 | Small local classifier (Cloudflare Clef) for routing/labelling | partly: `cheap-route` llama.cpp router, `llm_triage`, `vbench` | P2 | [16](16-local-classifier-model.md) |
| 20 | Observability stack (metrics, logs, alerts to Matrix) | partly: trace-dashboard, Langfuse POV, host-daemon health design | P2 | [20](20-observability-stack.md) |
| 02 | Self-hosted CI runner image factory (manifest, toolcache, checksums) | partly: WOBI `github_runner` role (runners done), Packer CI failing | P3 | [02](02-ci-runner-image-factory.md) |
| 09 | Remote desktop between home PCs, shared central PC | partly: Tailscale + SSH/mosh only | P3 | [09](09-remote-access-shared-compute.md) |
| 10 | Private media server for friends (Jellyfin over tailnet) | new | P3 | [10](10-private-media-server.md) |
| 18 | Kubernetes security path (CKS) + hardened private EKS reference | new (K8s POC series ended 2026-10-06) | P3 | [18](18-k8s-security-learning-path.md) |
| 19 | Homelab virtualization (Proxmox instead of VirtualBox on Windows) | new | P3 | [19](19-homelab-virtualization.md) |
| 05 | Self-hosted general agent (OpenManus alternative) | done: Hermes itself; only a browser-agent eval remains | P4 | [05](05-local-autonomous-agent.md) |
| 07 | Open-source robot arm / humanoid (LeRobot SO-101 first) | new | P4 | [07](07-open-source-robot.md) |
| 08 | Renting out homelab GPUs (Salad, Vast.ai, TensorDock) | new | P4 | [08](08-gpu-rental-homelab.md) |
| 11 | Web terminal with one-click sandbox provisioning | new | P4 | [11](11-web-terminal-onboarding.md) |
| 14 | Let someone log in as me without seeing passwords | partly: BWS for machine secrets only | P4 | [14](14-delegated-credential-access.md) |
| 12 | Managed SaaS business (Nextcloud, DaaS, CSP, managed CI/CD) | new | P5 | [12](12-managed-saas-business.md) |
| 13 | Modular "super app" / custom OS | new | P5 | [13](13-modular-super-app.md) |
| 15 | Personal values system as a checkable knowledge base | new | P5 | [15](15-formal-values-system.md) |

## Cross-links
- **The token-saving cluster.** 03 (rules), 16 (classifier) and 17 (distillation) all aim to replace repeated LLM reasoning with code or small models. Plan them together.
- **The hardware cluster.** 19 (a dedicated Proxmox host) is the platform that 06, 07, 08, 10 and 20 would run on. Decide on 19 before buying hardware for the others.
- **The image cluster.** 01 and 02 share the same Ansible "toolset" role and the Packer flow.

## Next steps (suggested)
1. Filip reviews priorities and the open questions in each doc.
2. For each accepted idea, create a Kanban task with priority 100 and the doc as its spec.
