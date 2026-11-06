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
        assert rep.label != "ok" or rep.llm_risk != "niskie", rep.reasons
    else:
        assert rep.label == "ok" and rep.llm_risk == "niskie", rep.reasons
    if "prompt_injection" in case["expect"]:
        assert rep.llm_risk in ("średnie", "wysokie")
    if "hidden_text" in case["expect"] or "unicode_tags" in case["expect"]:
        assert rep.llm_risk == "wysokie"
    text = card(rep, nonce="f00dfeed")
    for s in case["must_not_reach_model"]:
        assert s not in text
    assert not any(0xE0000 <= ord(c) <= 0xE007F for c in text)
    assert f"ryzyko dla AI: {rep.llm_risk}" in text
