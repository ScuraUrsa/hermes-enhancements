# Ideas from Filip's ChatGPT history (plans only)

Source: ChatGPT data exports dated 2026-10-18 from three accounts:

| Account | Conversations | Date range | Technical (approx.) | Covered in |
|---|---|---|---|---|
| fjkazmierczak | 90 | 2024-02 to 2026-10 | ~70 | first run: ideas 01–20 |
| kazmierczakfilipjan | 397 | 2023-01 to 2026-10 | ~260 | second run: most of new ideas 21–41, additions to 01–03, 05–09, 12–14, 16, 17, 19, 20 |
| koalamis6 | 46 | 2024-02 to 2026-10 | ~15 | second run: new ideas 21, 22, 31, additions to 03, 04, 07, 09, 14 |

Kanban task `chatgpt-ideas`.

These docs are **plans only**. Nothing here is implemented, installed or deployed. They contain summaries, not
conversation dumps, personal data or secrets.

## How this was built
1. **Technical filter.** Only conversations about software, hardware, infrastructure, AI/LLMs, home automation, devices and networking were used. Cooking, travel, health, law, finance, history and similar were skipped. Most technical chats were one-off work troubleshooting: Terraform, Ansible, Packer or Azure Pipelines errors. Those are not ideas in their own right, so they were folded into the idea they support (02, 18, 28) or dropped.
2. **Grouping.** One idea is one thing Filip wanted to build, buy, set up or learn. The first run gave 20 ideas. The second run (the other two accounts) added 21 new ideas. Where a conversation repeated an existing idea, it was merged into that doc as an "Also from the … account" source line plus an "Additions" section.
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

41 ideas: 20 from the first run, 21 new in the second run (21–41).

| # | Idea | Status vs Hermes | Priority | Doc |
|---|---|---|---|---|
| 03 | AI coding-rules meta-repo → knowledge compiler (rules, standards repo, repo factory) | partly: `authoring-rules` skill, marker OCR skill, video-digest | P1 | [03](03-ai-coding-rules-repo.md) |
| 17 | Turn recurring LLM work into deterministic code (cost boundary) | partly: `hermes-scripted-cron`, `teach-procedures`, rule-first triage | P1 | [17](17-llm-to-algorithm-distillation.md) |
| 01 | Workstation as code (WSL/laptop → image → remote dev desktop) | partly: `packer-images` (Hermes VM only), `laptop_host` role | P2 | [01](01-workstation-as-code.md) |
| 04 | Self-learning tool researcher (endless queue, sandbox, skills) | partly: 2026-08 research/POC series, roadmap C3, `technical-research-pov` | P2 | [04](04-self-learning-tool-researcher.md) |
| 06 | Better robot vacuum, cloud-free (Valetudo + HA + tidy-up help) | partly: Home Assistant + Polish voice on prod | P2 | [06](06-robot-vacuum-valetudo.md) |
| 16 | Small local classifier (Cloudflare Clef) for routing/labelling | partly: `cheap-route` llama.cpp router, `llm_triage`, `vbench` | P2 | [16](16-local-classifier-model.md) |
| 20 | Observability stack (metrics, logs, alerts to Matrix) | partly: trace-dashboard, Langfuse POV, host-daemon health design | P2 | [20](20-observability-stack.md) |
| 21 | Phone offload: agent-controlled Android, homelab Android, minimal phone | partly: `phone-control` skill, Termux/mosh, Remote Control | P2 | [21](21-phone-offload-homelab-android.md) |
| 23 | Computer-use automation: record once with AI, replay as a script | partly: `computer-use`, `teach-procedures`, `desktop` role | P2 | [23](23-computer-use-automation.md) |
| 24 | Code knowledge graph for agents (Graphify / codebase-memory-mcp) | new | P2 | [24](24-code-knowledge-graph.md) |
| 28 | CI-fix agent loop for Azure DevOps + PR-comment ingestion | partly: GitHub side (`github-actions-triage`, watchdog, CI doctor) | P2 | [28](28-ci-fix-agent-loop.md) |
| 31 | Passwordless family security (FIDO2 keys + Bitwarden) + compromise playbook | new (passkeys only mentioned in `identity-vault`) | P2 | [31](31-family-passwordless-security.md) |
| 02 | Self-hosted CI runner image factory (manifest, toolcache, checksums) | partly: WOBI `github_runner` role (runners done), Packer CI failing | P3 | [02](02-ci-runner-image-factory.md) |
| 09 | Remote desktop between home PCs, shared central PC, Pi thin client | partly: Tailscale + SSH/mosh only | P3 | [09](09-remote-access-shared-compute.md) |
| 10 | Private media server for friends (Jellyfin over tailnet) | new | P3 | [10](10-private-media-server.md) |
| 18 | Kubernetes security path (CKS) + hardened private EKS reference | new (K8s POC series ended 2026-10-06) | P3 | [18](18-k8s-security-learning-path.md) |
| 19 | Homelab virtualization (Proxmox), power management, DIY storage | new | P3 | [19](19-homelab-virtualization.md) |
| 22 | Ambient voice companion ("Hey Hermes", proactive, avatar) | partly: HA Assist → Hermes with Polish STT/TTS | P3 | [22](22-ambient-voice-companion.md) |
| 25 | LLM serving and cost planner (sizing, self-host vs API) | partly: Ollama Cloud + quota governor, local Qwen via llama.cpp, `cheap_route` | P3 | [25](25-llm-serving-cost-planner.md) |
| 27 | Disposable sandboxes for agents (containers / Firecracker / VMs) | partly: worktrees, `desktop` role, dev VM, host daemon | P3 | [27](27-agent-sandboxes.md) |
| 29 | Demo and presentation agent after a PR | new (`powerpoint`, `manim-video` skills exist) | P3 | [29](29-pr-demo-presentation-agent.md) |
| 35 | Home maker workshop (Prusa MK4S + MMU3, scanning, CNC, workbench) | new | P3 | [35](35-maker-workshop.md) |
| 40 | Copilot and Claude subscription as Hermes coding back ends | partly: `cc_run.py`, Copilot profiles, hbench; Copilot CLI not installed | P3 | [40](40-copilot-claude-coding-backends.md) |
| 41 | Budget multi-GPU LLM rig from used or repaired cards | new | P3 | [41](41-used-gpu-llm-rig.md) |
| 05 | Self-hosted general agent (OpenManus / OpenClaw / CrewAI alternative) | done: Hermes itself; only a browser-agent eval remains | P4 | [05](05-local-autonomous-agent.md) |
| 07 | Open-source robots (LeRobot SO-101, PAROL6, mini VR rover) | new | P4 | [07](07-open-source-robot.md) |
| 08 | Renting out homelab GPUs (Salad, Vast.ai, TensorDock) | new | P4 | [08](08-gpu-rental-homelab.md) |
| 11 | Web terminal with one-click sandbox provisioning | new | P4 | [11](11-web-terminal-onboarding.md) |
| 14 | Let someone log in as me without seeing passwords | partly: BWS for machine secrets only | P4 | [14](14-delegated-credential-access.md) |
| 26 | Open WebUI as a front-end for Hermes (decision doc) | partly: ran until 2026-10-06, now stopped; untracked bridge | P4 | [26](26-open-webui-front-end.md) |
| 32 | Hermes access to YouTube (transcribe, summarise, queue) | done (mostly): video-digest, youtube skills, roadmap C4 | P4 | [32](32-youtube-agent-access.md) |
| 33 | Low-friction household logging (drinks, shopping lists) | partly: `home-inventory`, Home Assistant | P4 | [33](33-household-auto-logging.md) |
| 36 | Free-tier cloud node (Oracle Ampere A1): game server + off-site backup | new | P4 | [36](36-free-tier-cloud-node.md) |
| 39 | Moving the gaming PC off Windows 10 | new (`steam-games` reads Steam data only) | P4 | [39](39-linux-gaming-pc.md) |
| 12 | Managed SaaS / DaaS business (Nextcloud, thin clients, credits) | new | P5 | [12](12-managed-saas-business.md) |
| 13 | Modular "super app" / Life Engineering Platform | new | P5 | [13](13-modular-super-app.md) |
| 15 | Personal values system as a checkable knowledge base | new | P5 | [15](15-formal-values-system.md) |
| 30 | Measuring the "logic value" of engineering work | new | P5 | [30](30-engineering-value-metric.md) |
| 34 | Secure messaging channel between Filip and his agent | done: Matrix (Continuwuity) over Tailscale | P5 | [34](34-agent-messaging-channel.md) |
| 37 | Back up ChatGPT history and turn it into plans | done: `chatgpt_export_watch.py` + this doc set | P5 | [37](37-chatgpt-export-ideas-pipeline.md) |
| 38 | Eye-tracking control on a Windows PC | new | P5 | [38](38-eye-tracking-pc-control.md) |

## Cross-links
- **The token-saving cluster.** 03 (rules), 16 (classifier) and 17 (distillation) all aim to replace repeated LLM reasoning with code or small models. Plan them together.
- **The hardware cluster.** 19 (a dedicated Proxmox host) is the platform that 06, 07, 08, 10 and 20 would run on. Decide on 19 before buying hardware for the others.
- **The image cluster.** 01 and 02 share the same Ansible "toolset" role and the Packer flow.
- **The agent-platform cluster.** 23 (computer use), 24 (code graph), 27 (sandboxes), 28 (CI loop), 29 (demo agent) and 40 (back ends) are all extensions of how Hermes runs coding work. 27 is the safety base for 23 and 28.
- **The model-cost cluster.** 25 (planner) decides whether 41 (GPU rig) or 08 (renting GPUs) makes sense at all. Today Ollama Cloud is the baseline to beat.
- **The phone and voice cluster.** 21 (phone), 22 (voice companion), 33 (household logging) and 38 (eye tracking) are input channels to the same Hermes.

## Next steps (suggested)
1. Filip reviews priorities and the open questions in each doc.
2. For each accepted idea, create a Kanban task with priority 100 and the doc as its spec.
