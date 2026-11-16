# 13 · Modular "super app" (and maybe a custom OS)

**Status vs Hermes:** new. Hermes has its own plugin system (`hermes-desktop-plugins`, `research/hermes-plugins.md`), but nothing aims to replace everyday apps.
**Priority:** P5

## Goal and context
Filip's idea: one app replaces all apps, and every feature is an optional module. The next step would be to replace the desktop, or even ship it as a custom OS with very little code. He asked whether that would be faster and more stable than a modern OS plus separate apps. The chat compared it with microkernel vs monolithic kernel designs and with existing "mini-OS" super apps (Emacs, VS Code, WeChat).

Source: fjkazmierczak account, *OS app model comparison* (2025-08-25).

Also from the **kazmierczakfilipjan** account:
- *Nazwa dla IDP* (2025-08-17, a "Life Engineering Platform": an internal developer platform for the whole of life: time, health, diet, relationships, spirituality)
- *Custom desktop setup options* (2025-11-28, every directory as its own "desktop" with background and icon size; no special main desktop)
- *Build Notion Tutorial Help* (2026-01-13, building your own Notion)
- *AI System Name Ideas* (2026-03-06) and *Postacie samowystarczalne* (2026-03-09): naming for a self-sufficient "build your own fortress" open-source AI system (Robinson Crusoe, Wokulski, Bill from The Last of Us)

## Architecture
A custom OS would not be faster or more stable in practice. The cost is drivers, security and app compatibility. The workable version is a **super app on Linux**:
```
host OS (Linux) → shell app (core: module loader, permissions, IPC bus, shared data store, UI shell)
                  modules = sandboxed plugins (WASM components or separate processes) with manifest
                  (capabilities: net, files:<path>, notifications), shared data model (contacts, tasks, files)
```
Hermes already behaves partly like this: skills and plugins are modules, Matrix and the phone are UI shells, and Honcho is shared memory. The pragmatic step is to make **Hermes the integration hub** rather than build a new app platform.

## Implementation plan (exploratory)
1. Write a one-page spec: which 5 everyday apps would be modules (notes, tasks, calendar, files, chat) and which data they share.
2. Prototype the core in a weekend: a WASM component host (wasmtime) with a capability manifest, plus one module.
3. Decide whether to continue, or put the effort into Hermes plugins.

## Deployment plan
None until the prototype exists.

## Configuration / Cost
Learning project only. Hardware: none.

## Additions from the kazmierczakfilipjan account
- **Life Engineering Platform = Hermes + its data planes.** Most planned modules already have a home: calendar/time (timeplane, calendar recon), tasks (Kanban, user inbox), health and diet (HA, notes), decision log. The super app is a **single UI shell over Hermes data**, not a new backend. A Notion-like block editor is the hardest part. Reuse an open one (AFFiNE, AppFlowy, or Outline) as a module, don't build one.
- **Directory-as-desktop.** On Linux this is a file-manager/shell extension (per-directory `.directory` metadata or a GNOME extension). It is a small, separate experiment and a good first module for the shell.

## Open questions
What specific pain does it solve that Hermes plus existing apps don't? Without an answer, keep it parked.
