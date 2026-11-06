# Delivery gate shows "(unknown card)" for every kanban task, and re-runs fail on an existing PR

Two defects in `scripts/delivery_gate.py`:

1. `kanban_task(task_id)` reads the Hermes kanban SQLite DB (`KANBAN_DB`). It hard-codes a column named
   `blocked_reason`, which newer Hermes versions renamed to `block_kind`. The query raises, a bare
   `except` swallows it, and every PR body and review task says "(unknown card)". `kanban_task` must
   work with both schemas: with the new one it returns the row with a `block_kind` key, with the legacy
   one a `blocked_reason` key (plus `title`, `status` and the other columns as before).
2. `open_pr(...)` is not idempotent. When `gh pr create` fails because "a pull request for branch ...
   already exists" (raised as `DeliveryError` from `_sh`), treat it as success: look the PR up again with
   `find_open_pr` and return it.
