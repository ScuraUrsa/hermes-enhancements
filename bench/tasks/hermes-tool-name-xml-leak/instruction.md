# Tool calls fail when the provider leaks XML attribute fragments into the tool name

With one provider's Anthropic-compatible endpoint, the `tool_use.name` field sometimes arrives with raw
XML attribute fragments appended, for example:

    terminal" parameter="command" string="true
    execute_code" parameter="code" string="true
    session_search" parameter="session_id" string="true

No repair rule recovers these, so every such tool call is retried three times and the turn aborts.

`repair_tool_call` in `agent/agent_runtime_helpers.py` must recover the real tool name from such input
(`terminal`, `execute_code`, `session_search`), and the rest of the existing repair pipeline
(lower-casing, CamelCase to snake_case, stripping a `_tool` suffix, fuzzy matching) must still apply to
the cleaned name. Whitespace is not a separator: the existing repair of `write file` to `write_file`
must keep working.
