"""Two non-LLM agents that keep the task set honest.

* ``oracle`` applies the real fix (every file the fix commit changed except the
  hidden tests). A task the oracle fails is broken.
* ``noop`` changes nothing. A task the no-op passes doesn't discriminate.

``hbench validate`` runs both on every task.
"""

from __future__ import annotations

import time

from .. import workspace
from .base import Agent, AgentResult, RunContext


class Oracle(Agent):
    name = "oracle"
    binary = None
    provider_kinds = ("none",)

    def run(self, ctx: RunContext) -> AgentResult:
        start = time.monotonic()
        workspace.restore_from_fix(ctx.task, ctx.src, ctx.workspace, workspace.fix_files(ctx.task, ctx.src))
        return AgentResult(0, False, time.monotonic() - start, {"agent_status": "applied reference fix"})


class Noop(Agent):
    name = "noop"
    binary = None
    provider_kinds = ("none",)

    def run(self, ctx: RunContext) -> AgentResult:
        return AgentResult(0, False, 0.0, {"agent_status": "did nothing"})
