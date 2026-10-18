# 13 · Modular "super app" (and maybe a custom OS)

**Status vs Hermes:** new. Hermes has its own plugin system (`hermes-desktop-plugins`, `research/hermes-plugins.md`), but nothing aims to replace everyday apps.
**Priority:** P5

## Goal and context
Filip's idea: one app replaces all apps, and every feature is an optional module. The next step would be to replace the desktop, or even ship it as a custom OS with very little code. He asked whether that would be faster and more stable than a modern OS plus separate apps. The chat compared it with microkernel vs monolithic kernel designs and with existing "mini-OS" super apps (Emacs, VS Code, WeChat).

Source: fjkazmierczak account, *OS app model comparison* (2025-08-25).

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

## Open questions
What specific pain does it solve that Hermes plus existing apps don't? Without an answer, keep it parked.
