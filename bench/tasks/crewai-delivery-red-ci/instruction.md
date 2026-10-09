# Delivery gate completes kanban cards even when the merged PR's CI is red

`scripts/delivery_gate.py reconcile` completes a card (kanban, Notion, notifications) as soon as its PR
is merged. A merge whose CI is red means the work is not finished, so the card must stay open and be
completed later by a follow-up PR that goes green.

Required behaviour:

- New config default `require_ci_green`, `True` by default, in `DEFAULTS`.
- In `_complete_item()`: when the PR is merged, `require_ci_green` is on and the PR's checks
  (`ci_status(cfg, number)`) are not all green (`ci_all_green`), do **not** complete anything. Set
  `item["status"] = "ci_red"` and `item["waiting"] = "ci_red_after_merge"`, and return a result with
  `merged=True`, `waiting="ci_red_after_merge"` and `ci` = a list of `{"name", "state"}` per check.
- `_complete_item(..., force=False)` gets a keyword argument `force`; `force=True` skips this check.
  `reconcile` gets a `--force` flag that passes it through (to override a known flaky check).
- `reconcile` must also process items whose status is `"ci_red"`, not only `"open"`, so a follow-up
  green PR can complete them.

Existing behaviour for green CI must not change.
