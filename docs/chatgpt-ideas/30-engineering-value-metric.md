# 30 · Measuring the "logic value" of engineering work

**Status vs Hermes:** new. `trace-dashboard` measures token cost, not the value of the change.
**Priority:** P5

## Goal and context
Filip wants a measure of the technical value of a change that is not lines of code, time spent or revenue. The measure would capture how much decision logic a PR adds, removes or moves (conditions, cases, functions, pipelines, automations), across maintenance, bug fixes, features, tech debt and tool migrations. He asked which academic definitions and theories already exist.

Source: kazmierczakfilipjan, *Measuring Engineering Logic* (2026-05-27).

## Architecture
A per-PR metric built from existing ideas:
```
diff → AST/IaC parse (tree-sitter; ansible/terraform/yaml pipelines as graphs)
  features: Δ cyclomatic/cognitive complexity, Δ decision points, Δ "essential" branches (tests that cover them),
            Δ automation (manual steps removed, from runbooks/pipelines), duplication removed, dependency graph change
  score  : "implemented decision complexity" = Σ new verified decisions − Σ removed accidental complexity
report : per-PR card + trend per repo; never used as a personal performance number
```
Related academic work to read first: Halstead metrics, McCabe and cognitive complexity, function points / COSMIC, Kolmogorov-complexity-based measures, the "essential vs accidental complexity" idea (Brooks), and DORA/SPACE for the delivery side.

## Implementation plan
1. Literature note (1 page) with the definitions above and why each falls short.
2. Prototype on hermes-enhancements history: compute the features per merged PR, compare with Filip's own ranking of 20 PRs.
3. Keep only features that correlate with his ranking. Publish as a CI comment.

## Deployment plan
A script plus a GitHub Action comment. No service.

## Configuration
Languages, weights, excluded paths (generated code, lockfiles).

## Cost / hardware
Free.

## Open questions
- What is it for: self-reflection, team reporting, or input to the token-saving work in [17](17-llm-to-algorithm-distillation.md)?
