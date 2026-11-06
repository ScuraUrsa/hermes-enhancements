"""The attack corpus (tests/attacks, built by make_attacks.py) must be caught and must not reach the model."""

import json
from pathlib import Path

import pytest

from mailguard.analyze import analyse, card

ATTACKS = Path(__file__).parent / "attacks"
INDEX = json.loads((ATTACKS / "index.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", INDEX, ids=[c["id"] for c in INDEX])
def test_attack_case(case):
    rep = analyse((ATTACKS / f"{case['id']}.eml").read_bytes())
    codes = {r["code"] for r in rep.reasons}
    missing = set(case["expect"]) - codes
    assert not missing, (missing, rep.reasons)
    if case["expect"]:
        assert rep.label != "ok", rep.reasons
    else:
        assert rep.label == "ok", rep.reasons
    text = card(rep, nonce="f00dfeed")
    for s in case["must_not_reach_model"]:
        assert s not in text
    assert "\U000e0000" <= max(text) is False or not any(0xE0000 <= ord(c) <= 0xE007F for c in text)
