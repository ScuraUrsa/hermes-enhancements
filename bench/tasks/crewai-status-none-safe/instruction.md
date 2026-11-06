# `delivery_gate.py status` crashes on a partially written item

Running `python scripts/delivery_gate.py status` (text output, not `--json`) crashes with

    TypeError: unsupported format string passed to NoneType.__format__

when the state file contains an item that has no risk or tasks yet, for example a freshly registered
item: `{"items": {"wt/t_a": {"status": "open", "pr": {"number": 7}}}}`.

The text view must never crash on a fresh or partial item. Print a placeholder for missing values; the
line must still show the branch name and `PR #7`.
