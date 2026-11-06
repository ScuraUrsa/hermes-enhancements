from .base import Agent, AgentResult, RunContext, UnsupportedProvider
from .claude_code import ClaudeCode
from .copilot_cli import CopilotCli
from .reference import Noop, Oracle
from .zed import Zed

AGENTS: dict[str, type[Agent]] = {a.name: a for a in (ClaudeCode, CopilotCli, Zed, Oracle, Noop)}

__all__ = ["AGENTS", "Agent", "AgentResult", "RunContext", "UnsupportedProvider"]
