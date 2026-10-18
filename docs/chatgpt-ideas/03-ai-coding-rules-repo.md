# 03 · AI coding-rules meta-repo (rules from books and videos, enforced in review)

**Status vs Hermes:** partly exists.
- WOBI `roles/coding_agents/files/skills/authoring-rules` explains how to write AGENTS.md/CLAUDE.md rules.
- Skill `productivity/ocr-and-documents` does PDF→markdown with marker.
- `video-digest` (ytdigest, course-harvest) turns videos into transcripts and reports.

Missing: an extracted, sourced rule set, and enforcement of those rules at PR time (Rego/OPA or similar).

**Priority:** P1

## Goal and context
Filip wants a meta-repository of small, linkable coding rules per language and technology (Python, C++, Java, Go, Terraform, Ansible…), extracted by an AI from books he owns and from video courses (YouTube, Humble Bundle). It has three purposes:
1. Agents load only the relevant rules before coding, which saves tokens.
2. Every rule cites its source: book or file, location, and the short passage it came from.
3. PR review checks the rules automatically (Rego was the first idea).

The idea first came up in 2025 as "store best practices as Rego policies".

Source: fjkazmierczak account.
- *AI Self-Learning Framework* (2025-03-18, the Rego part)
- *Idea helperów w programowaniu* (2025-08-06, a taxonomy of code categories)
- *Tworzenie zasad kodowania AI* (2026-08-05)

## Architecture
```
sources/ (private, NOT in git: PDFs, videos)
   │ marker (PDF→md)  /  ytdigest + frame sampling (video→transcript+keyframes)
   ▼
chunks/  (≈10–20 pages, ~10% overlap, chunk id = file#page-range)
   │ extraction prompt (Hermes coder profile or Claude Code, batch)
   ▼
rules/<lang>/<topic>/<RULE-ID>.md  frontmatter: id, title, severity, applies_to (globs),
                                   source {file, locator, quote ≤ 1–2 sentences}, check: {kind, ref}
   │ dedupe/merge pass (embedding similarity → human review)
   ▼
index: rules.json  → (a) agent loader: picks rules by file glob/tech → AGENTS.md include
                      (b) enforcement:  kind=lint  → ruff/golangci/tflint/ansible-lint config
                                        kind=policy→ conftest/OPA Rego on structured files (HCL/YAML/JSON)
                                        kind=review→ LLM reviewer checklist (only what tools can't check)
```
Key design point: Rego only fits **structured** inputs (Terraform plan JSON, K8s/Ansible YAML). For general code style, generate linter configs, and send the remainder to an LLM review checklist. This matches the "replace AI work with algorithms" principle in [17](17-llm-to-algorithm-distillation.md).

## Implementation plan
1. Create a repo `ScuraUrsa/coding-rules` (private): rule schema (JSON Schema), `rules/`, and a `tools/` CLI (`rules extract|dedupe|index|select`).
2. Ingestion: reuse marker from the `ocr-and-documents` skill and the transcripts from `video-digest`. Add keyframe OCR for code shown on screen.
3. Extraction prompt with a strict output schema. Every rule must carry a source and a short quote, or it is rejected.
4. Pilot on one book plus one language (Python), aiming for about 50 rules. Filip reviews them.
5. Enforcement: a GitHub Action `rules-check` in one repo (ruff config plus conftest for Terraform/Ansible), with an LLM review comment only for `kind=review` rules.
6. Agent side: `rules select --paths <changed files>` emits a compact markdown include for Claude Code and Hermes coder prompts.

## Deployment plan
Run as a batch job on the Hermes dev VM (Kanban task per book). Book and video files stay in private storage, never in git. CI runs on the existing self-hosted runners.

## Configuration
`rules.config.yaml` (sources dir, chunk size and overlap, model per step), the rule schema and the severity levels.

## Cost / hardware
- marker on CPU is slow (minutes per book) but free.
- Extraction tokens: roughly 0.5–1.5M tokens per 400-page book. Use Ollama Cloud or Claude Code within the existing quotas.
- If you use local models for dedupe embeddings, run them through llama.cpp (`llama-server --embedding`), not local Ollama.

## Open questions
- Copyright: keep quotes very short and the repo private. Is that acceptable for every source?
- Should rules feed the existing `authoring-rules` skill, or replace it?

## Notes
Polish/English: write the rules in English and keep the original-language quote in `source.quote`.
