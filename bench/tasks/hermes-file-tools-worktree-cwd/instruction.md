# Relative file writes in a fresh worktree session land in the main checkout

In a worktree session (`hermes -w`), a relative `write_file` / `patch` issued before any terminal
command has run can silently land in the **main** checkout instead of the worktree. The live terminal
cwd registry is still empty at that point, and `TERMINAL_CWD` is often a sentinel such as `.`, which is
currently joined onto the process cwd. The existing divergence warning only fires once the live cwd is
known, so nothing warns either.

Fix `tools/file_tools.py`:

- Add `_configured_terminal_cwd()`, which returns the `TERMINAL_CWD` value as a `Path` only when it is a
  real absolute path. Sentinel values (`''`, `'.'`, `'./'`, `'auto'`, `'cwd'`) and any relative value
  count as unset and return `None`.
- Path resolution (`_resolve_base_dir`, used by `_resolve_path_for_task`) and the escape warning
  (`_path_resolution_warning`) must use the same authoritative workspace root: the live terminal cwd if
  one is registered, otherwise a valid absolute `TERMINAL_CWD`. A live cwd still wins over
  `TERMINAL_CWD`.
- So from the very first write, a relative path resolves inside the worktree, and a path escaping it is
  warned about, even with an empty registry.
