# 28 · CI-fix agent loop for Azure DevOps (run → filtered logs → fix → push)

**Status vs Hermes:** partly exists. For GitHub: `gh_actions_watchdog.py` cron, CI doctor, skills `github-actions-triage` and `hermes-delivery-gate`. For Azure DevOps: only `crewai/tools/azure_pipeline_tool.py` in WOBI and the dormant `terraforge-pipeline`. Missing: the Azure DevOps loop, log filtering, and PR-comment ingestion.
**Priority:** P2

## Goal and context
At work Filip runs Azure Pipelines (Terraform, Packer, Ansible) and wanted a coding agent (Cursor, then Copilot, then Hermes/Claude Code) that:
- triggers a pipeline, waits for it to finish, reads only the relevant part of thousands of log lines, fixes the code and pushes again, for up to N cycles;
- takes the reviewers' comments from an Azure DevOps PR and applies the suggested changes with one command.

Source: kazmierczakfilipjan.
- *Azure Pipelines AI Loop*, *Azure Pipelines Debug Setup* (2026-01-19)
- *Cycle agent count w Coursorze* (2026-02-06)
- *Run Custom Agent Loop* (2026-04-08, an `azure-devops-ci-fixer` Copilot agent)
- *PR Feedback Automation* (2026-05-07)
- many single-error threads (*Azure pipeline terraform stage*, *Proxy Error in DevOps*, *Packer VNet Error*, …) that show the loop's real input

## Architecture
```
agent edits code → git push (branch) → az pipelines run --branch … (or REST)
   → poll run status → on failure: fetch timeline + logs of failed steps only
   → log filter (no LLM): keep ##[error], Terraform "Error:" blocks, Ansible "fatal:" + task name,
                          Packer "==> … error", last 40 lines of the failed step; dedupe; cap 4k tokens
   → agent fix (Claude Code / Copilot CLI) → push → repeat (max N=5, stop on same error twice)
PR feedback: az repos pr thread list → active threads with file+line → markdown task → agent applies → reply "done in <sha>"
```
The same filter rules can feed the GitHub Actions side (`github-actions-triage`).

## Implementation plan
1. `ado-logs` script: given a run id, print the filtered failure context. Test it on saved logs from past failures.
2. `ado-loop` script: push → run → wait → filter → call the agent with a fixed prompt → repeat. Stop rules and a summary at the end.
3. `ado-pr-feedback` script: export active PR threads as a task file for the agent.
4. Package all three as a Hermes skill and a Claude Code / Copilot custom agent, so the same loop works from the work laptop.

## Deployment plan
Scripts in hermes-enhancements `ado-tools/`. At work they run on the work machine with Filip's own `az` login. Nothing work-related goes to the Hermes VM unless the employer allows it.

## Configuration
Org/project/pipeline id, max cycles, filter patterns per tool, PAT or `az login` (never stored in the repo).

## Cost / hardware
Free; agent tokens per cycle only. The filter keeps each cycle at a few thousand tokens instead of the full log.

## Open questions
- Does the employer allow an agent to push to work repos and run pipelines? This decides where it runs.
- Is Copilot CLI (company licence) or Claude Code the agent at work?
