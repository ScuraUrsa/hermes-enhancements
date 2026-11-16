# 24 · Code knowledge graph for agents (Graphify-style)

**Status vs Hermes:** new. Only research mentions exist (`research/coding-agents-comparison.md`). The nearest pieces are Obsidian (graph view of notes) and Honcho memory, neither of which models code.
**Priority:** P2

## Goal and context
Filip wants an "Obsidian graph, but for code": nodes are modules, functions, Ansible roles, Terraform resources and pipelines; edges are calls, imports, data flow and "deploys". Agents should query it instead of re-reading repos, and people should be able to look at it like a Lucidchart architecture diagram.

Source: kazmierczakfilipjan, *AI Code Graph Repos* (2026-08-10). It compared Graphify, Understand-Anything and codebase-memory-mcp, and how each could become a Lucidchart-like view grounded in real code.

## Architecture
```
repos (hermes-enhancements, WOBI, hermes-workspace, work repos)
  → indexer (tree-sitter parsers; for IaC: ansible role/include graph, terraform graph, pipeline yaml)
  → graph store (SQLite or Kùzu, file-based, rebuilt per commit)
  → MCP server "codegraph" : find_symbol, callers, dependents, path(a,b), summary(module)
       ▲ Claude Code / Hermes coder (loaded via the shared ~/.agents MCP config)
  → export: Mermaid/D2 diagrams per repo → rendered in README or Obsidian vault
```
Start from an existing project instead of building an indexer: try **codebase-memory-mcp** (MCP-first) and **Graphify** (graph + visual) on two repos and keep the better one.

## Implementation plan
1. POV (time-boxed, 1 day): run both tools on WOBI and hermes-enhancements. Measure index time, size, and whether answers to 10 fixed questions ("what deploys timeplane?", "who calls budget.py?") are right.
2. Wire the winner as an MCP server for Claude Code and the coder profile.
3. Add IaC edges the tools lack (Ansible role dependencies, `include_tasks`, Terraform module graph) as a small plugin.
4. Rebuild on push (git hook or Hermes cron). Export a Mermaid overview into each repo's docs.
5. Measure tokens per coding task before and after on a fixed task set (use `bench/hbench`).

## Deployment plan
A WOBI role installs the tool and the MCP registration. The index lives under `~/.cache/codegraph/<repo>`, outside git.

## Configuration
Repo list, languages, exclude globs, rebuild schedule.

## Cost / hardware
Free, local CPU. Indexing a few repos takes minutes and well under 1 GB.

## Open questions
- Can work repos be indexed on this VM, or only on the work machine?
- Is the visual side needed, or is the MCP query side enough?
