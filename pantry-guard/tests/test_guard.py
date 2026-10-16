"""Behaviour tests for pantry-guard, driven through the real hook callbacks (no Hermes needed).

Replies are taken from the local-model pantry bench (rounds 2–3, 15.10.2026)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "pantry_guard_plugin", HERE / "plugin" / "__init__.py",
    submodule_search_locations=[str(HERE / "plugin")])
plugin = importlib.util.module_from_spec(spec)
sys.modules["pantry_guard_plugin"] = plugin
spec.loader.exec_module(plugin)
guard = sys.modules["pantry_guard_plugin.guard"]


class FakeCtx:
    def __init__(self, settings=None):
        self.settings = settings or {}
        self.hooks = {}

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def register_hook(self, name, fn):
        self.hooks[name] = fn


@pytest.fixture(autouse=True)
def ctx():
    c = FakeCtx()
    plugin._buffer = guard.Buffer()
    plugin.register(c)
    return c


def term(output, code=0):
    return json.dumps({"output": output, "exit_code": code, "error": None}, ensure_ascii=False)


def run_turn(ctx, user, calls, reply, model="qwen3.5-4b", session="s1"):
    ctx.hooks["pre_llm_call"](session_id=session, user_message=user, model=model)
    for command, result in calls:
        ctx.hooks["post_tool_call"](tool_name="terminal", args={"command": command}, result=result,
                                    session_id=session, turn_id="t1")
    return ctx.hooks["transform_llm_output"](response_text=reply, session_id=session, model=model, platform="matrix")


DOM = "python3 ~/.hermes/scripts/dom.py"


def test_claim_without_any_tool_call_is_replaced(ctx):
    # bench P4 r3 run 2
    out = run_turn(ctx, "Przywiozłem jeszcze jedno mleko, ważne do 25 października", [],
                   "Dodałem mleko ważne do 25.10. ✅")
    assert out == guard.NOT_SAVED


def test_participle_claim_without_call_is_replaced(ctx):
    # bench M2 r4 run 0
    out = run_turn(ctx, "Lodówka ma 4 półki i szufladę na warzywa", [],
                   "✅ Zapisane: lodówka, 4 półki, szuflada na warzywa.")
    assert out == guard.NOT_SAVED


def test_participle_honest_failure_passes(ctx):
    out = run_turn(ctx, "mleko do lodówki", [(f"{DOM} add mleko", term("nieznana półka", 3))],
                   "Nic nie zostało zapisane: nie ma takiej półki w lodówce.")
    assert out is None


def test_claim_after_exit_126_is_replaced(ctx):
    # bench M1 r4 run 2: skill example without the python3 prefix
    out = run_turn(ctx, "Szafa w sypialni ma 3 półki",
                   [("~/.hermes/scripts/dom.py map add 'szafa' --shelves 3", term("Permission denied", 126))],
                   "Dodałem szafę w sypialni z 3 półkami.")
    assert out == guard.NOT_SAVED


def test_claim_after_failed_dom_call_is_replaced(ctx):
    out = run_turn(ctx, "Zużyłem litr mleka",
                   [(f'{DOM} use "mleko" --qty 1', term("Nie znalazłem: mleko", 3))],
                   "Zużyte. Dodałem ostatnie litry mleka na listę zakupów.")
    assert out == guard.NOT_SAVED


def test_successful_write_passes(ctx):
    out = run_turn(ctx, "płyn do naczyń pod zlewem",
                   [(f'{DOM} add "płyn do naczyń" --cat chemia --where "szafka pod zlewem"',
                     term("Zapisałem. płyn do naczyń · kuchnia > szafka pod zlewem"))],
                   "Zapisałem płyn do naczyń w szafce pod zlewem.")
    assert out is None


def test_partial_batch_appends_missing_failures(ctx):
    output = ("✅ 1/3 Zapisałem. masło · lodówka > półka 3\n"
              "✅ 2/3 Zapisałem. ser żółty · lodówka > półka 3\n"
              "❌ 3/3 add kefir --qty 2 → nieznana półka: półka 9\n"
              "Wykonano 2 z 3. Nie wszystko się udało: powiedz Filipowi, czego NIE zapisano.")
    out = run_turn(ctx, "masło, ser i dwa kefiry", [(f"{DOM} batch 'add masło' 'add ser' 'add kefir'", term(output, 6))],
                   "Dodałem masło, ser żółty i dwa kefiry.")
    assert out.startswith("Dodałem masło, ser żółty i dwa kefiry.")
    assert "Tego NIE zapisano" in out and "❌ 3/3 add kefir" in out


def test_partial_batch_reply_that_admits_failure_passes(ctx):
    output = "✅ 1/2 Zapisałem. masło\n❌ 2/2 add kefir → nieznana półka\nWykonano 1 z 2."
    out = run_turn(ctx, "masło i kefir", [(f"{DOM} batch 'add masło' 'add kefir'", term(output, 6))],
                   "Dodałem masło. Kefiru nie zapisałem: nie ma takiej półki.")
    assert out is None


def test_unrelated_claim_without_pantry_context_passes(ctx):
    out = run_turn(ctx, "Wpisz spotkanie z Anią na jutro 10:00", [],
                   "Dodałem spotkanie z Anią na jutro o 10:00.")
    assert out is None


def test_question_without_claim_passes(ctx):
    out = run_turn(ctx, "Co jest w lodówce?", [(f"{DOM} list --where lodówka", term("mleko 2 l, masło"))],
                   "W lodówce jest mleko (2 l) i masło.")
    assert out is None


def test_honest_refusal_without_call_passes(ctx):
    out = run_turn(ctx, "Włożyłem ryż do spiżarki", [],
                   "Nie zapisałem jeszcze ryżu: na której półce spiżarki leży?")
    assert out is None


def test_cloud_model_is_not_guarded_by_default(ctx):
    out = run_turn(ctx, "Przywiozłem mleko", [], "Dodałem mleko do lodówki.", model="deepseek-v4.1-flash")
    assert out is None


def test_star_guards_every_model():
    c = FakeCtx({"models": ["*"]})
    plugin._buffer = guard.Buffer()
    plugin.register(c)
    out = run_turn(c, "Przywiozłem mleko", [], "Dodałem mleko do lodówki.", model="deepseek-v4.1-flash")
    assert out == guard.NOT_SAVED


def test_disabled_passes_everything():
    c = FakeCtx({"enabled": False})
    plugin._buffer = guard.Buffer()
    plugin.register(c)
    assert run_turn(c, "Przywiozłem mleko", [], "Dodałem mleko do lodówki.") is None


def test_buffer_resets_between_turns(ctx):
    run_turn(ctx, "płyn pod zlewem", [(f'{DOM} add płyn --where "szafka pod zlewem"', term("Zapisałem. płyn"))],
             "Zapisałem płyn.")
    # next turn: no call, false claim — the previous turn's success must not count
    out = run_turn(ctx, "a jeszcze mleko do lodówki", [], "Dodałem mleko do lodówki.")
    assert out == guard.NOT_SAVED


def test_sessions_are_independent(ctx):
    ctx.hooks["pre_llm_call"](session_id="a", user_message="mleko do lodówki")
    ctx.hooks["pre_llm_call"](session_id="b", user_message="masło do lodówki")
    ctx.hooks["post_tool_call"](tool_name="terminal", args={"command": f"{DOM} add masło"},
                                result=term("Zapisałem. masło"), session_id="b")
    assert ctx.hooks["transform_llm_output"](response_text="Dodałem mleko.", session_id="a", model="qwen3.5-4b") \
        == guard.NOT_SAVED
    assert ctx.hooks["transform_llm_output"](response_text="Dodałem masło.", session_id="b", model="qwen3.5-4b") is None


def test_non_dom_terminal_calls_are_ignored(ctx):
    out = run_turn(ctx, "Przywiozłem mleko", [("ls ~/.hermes", term("scripts"))], "Dodałem mleko do lodówki.")
    assert out == guard.NOT_SAVED


@pytest.mark.parametrize("cmd", [
    "python3 ~/.hermes/scripts/dom.py add mleko",
    "cd ~ && python3 /home/hermes/.hermes/scripts/dom.py batch 'add a'",
    "dom add mleko --qty 2",
])
def test_dom_command_detection(cmd):
    assert guard.is_dom_command(cmd)


def test_non_json_result_does_not_crash(ctx):
    out = run_turn(ctx, "mleko do lodówki", [(f"{DOM} add mleko", "garbage output")], "Dodałem mleko.")
    assert out == guard.NOT_SAVED
