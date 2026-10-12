#!/usr/bin/env python3
"""No-agent Hermes cron job: remind Filip to rotate the passwords agents generated for him.

Prints a short Polish message (Hermes delivers whatever a no-agent job prints) or nothing when
nothing is due. Needs an unlocked Bitwarden session: ``BW_SESSION`` in the environment, or
``~/.hermes/autonomy/identity-vault/bw_session`` (0600) written by Filip's unlock helper.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("HIDENTITY_PATH", str(Path(__file__).resolve().parents[2])))

from hidentity import accounts  # noqa: E402
from hidentity.bw import Bw, BwLocked  # noqa: E402


def main() -> int:
    session = os.environ.get("BW_SESSION")
    token_file = Path.home() / ".hermes" / "autonomy" / "identity-vault" / "bw_session"
    if not session and token_file.exists():
        session = token_file.read_text().strip() or None
    try:
        due = accounts.rotation_due(Bw(session=session))
    except BwLocked:
        print("🔐 Bitwarden jest zablokowany, nie mogę sprawdzić haseł do zmiany. Odblokuj (bw unlock) i zapisz sesję.")
        return 0
    if not due:
        return 0
    lines = ["🔑 Hasła wygenerowane przez agentów do zmiany w Bitwarden:"]
    for d in due:
        site = (d.get("uris") or ["?"])[0]
        lines.append(f"- {d['name']} ({site}, login {d.get('username') or '?'}), termin minął {d['rotate_by']}")
    lines.append("Po zmianie: `hidentity mark-rotated <id>` albo zmień hasło w Bitwarden (wykryję to po dacie zmiany).")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
