import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import dom  # noqa: E402

MAP = """\
Mieszkanie
  Kuchnia
    Lodówka | lodowka
      Półka 1
      Półka 2
      Półka 3
      Szuflada na warzywa
    Szafka nad zlewem
      Półka 1
      Półka 2
    Szafka pod zlewem | chemia  # środki czystości
  Pokój Teosia | pokój syna
    Szafa 1
      Półka 1
      Półka 2
      Półka 3
    Komoda
      Szuflada 1
      Szuflada 2
"""


@pytest.fixture()
def run(tmp_path, monkeypatch):
    monkeypatch.setenv("DOM_DB", str(tmp_path / "dom.db"))
    monkeypatch.setenv("DOM_TODAY", "2026-10-15")
    mp = tmp_path / "mapa.txt"
    mp.write_text(MAP, encoding="utf-8")

    def _run(*argv):
        return dom.run(list(argv))

    code, out = _run("map", "import", str(mp))
    assert code == 0, out
    return _run


def test_parse_dates(monkeypatch):
    monkeypatch.setenv("DOM_TODAY", "2026-10-15")
    p = dom.parse_date
    assert p("2026-10-20") == "2026-10-20"
    assert p("20.10") == "2026-10-20"
    assert p("20.10.2026") == "2026-10-20"
    assert p("20.10.27") == "2027-10-20"
    assert p("10.2026") == "2026-10-31"
    assert p("20 października") == "2026-10-20"
    assert p("koniec listopada") == "2026-11-30"
    assert p("5 stycznia") == "2027-01-05"  # an old date rolls to next year
    assert p("01.03") == "2027-03-01"
    assert p("za 5 dni") == "2026-10-20"
    assert p("jutro") == "2026-10-16"
    assert p("2 tygodnie") == "2026-10-29"
    assert p("za miesiąc") == "2026-11-15"
    assert p("") is None
    with pytest.raises(dom.DomError) as e:
        p("kiedyś")
    assert e.value.code == 2


def test_map_import_and_shelf_order(run):
    code, out = run("map", "show", "Lodówka")
    assert code == 0
    assert "Półka 1 (1. półka od góry, 3. od dołu)" in out
    code, out = run("map", "show")
    assert "Pokój Teosia" in out and "aka pokój syna" in out
    # re-import is idempotent
    code, out = run("--json", "map", "import", "/dev/null")
    assert json.loads(out)["data"]["created"] == 0


def test_body_where_with_sector_and_typo(run):
    code, out = run("add", "body Teosia z długim rękawem", "--qty", "3", "--cat", "ubrania",
                    "--where", "pokój Teosia > szafa 1 > półka 2", "--side", "lewo", "--depth", "przód")
    assert code == 0, out
    code, out = run("where", "body Trosia z długim rękawem")  # dictation typo
    assert code == 0, out
    assert "Pokój Teosia → Szafa 1 → Półka 2 (2. półka od góry, 2. od dołu), po lewej, z przodu" in out


def test_shopping_then_meal_plan_then_use(run):
    assert run("add", "mleko", "--qty", "2", "--unit", "l", "--exp", "18.10", "--where", "lodówka > półka 1")[0] == 0
    assert run("add", "mleko", "--qty", "1", "--unit", "l", "--exp", "25.10")[0] == 0  # same usual place
    assert run("add", "jogurt naturalny", "--exp", "jutro", "--where", "lodowka/polka 2", "--side", "prawo")[0] == 0
    assert run("add", "płyn do naczyń", "--cat", "chemia", "--where", "szafka pod zlewem")[0] == 0
    assert run("add", "ser żółty", "--exp", "2026-10-12", "--where", "lodówka > szuflada na warzywa")[0] == 0

    code, out = run("--json", "where", "mleka")
    data = json.loads(out)["data"]
    assert [d["expires"] for d in data] == ["2026-10-18", "2026-10-25"]
    assert all(d["place"].startswith("Kuchnia → Lodówka → Półka 1") for d in data)

    code, out = run("plan")
    assert "jogurt naturalny" in out and "termin mija jutro" in out
    assert "mleko" in out and "2026" in out
    assert "Już po terminie" in out and "ser żółty" in out
    assert "płyn do naczyń" not in out  # chemicals are not meal hints

    # FEFO: using milk takes the batch that expires first
    code, out = run("use", "mleko", "--qty", "2")
    assert code == 0 and "Zostało 1 l" in out
    code, out = run("--json", "where", "mleko")
    assert [d["expires"] for d in json.loads(out)["data"]] == ["2026-10-25"]
    code, out = run("use", "mleko", "--all")
    assert "ostatnia sztuka" in out
    code, out = run("where", "mleko")
    assert code == 3 and "Zwykle leży: Kuchnia → Lodówka → Półka 1" in out


def test_list_place_remind_and_throw(run):
    run("add", "masło", "--exp", "16.10", "--where", "lodówka > półka 3")
    run("add", "dżem", "--exp", "2027-05-01", "--where", "lodówka > półka 3", "--depth", "tył")
    code, out = run("list", "--where", "lodówka")
    assert "masło" in out and "dżem" in out and "z tyłu" in out
    code, out = run("remind")
    assert out.startswith("🧺") and "masło" in out and "dżem" not in out
    run("throw", "masło", "--all")
    code, out = run("remind")
    assert code == 0 and out == ""


def test_ambiguous_and_unknown(run):
    run("add", "ser żółty", "--where", "lodówka > półka 1")
    run("add", "ser biały", "--where", "lodówka > półka 1")
    code, out = run("use", "ser")
    assert code == 4 and "ser biały" in out and "ser żółty" in out
    code, out = run("add", "mąka", "--where", "spiżarka")
    assert code == 5
    code, out = run("add", "cukier", "--where", "półka 1")  # several "Półka 1" in the flat
    assert code == 4


def test_open_shortens_expiry_and_move(run):
    run("add", "śmietana", "--exp", "2026-11-01", "--where", "lodówka > półka 2")
    code, out = run("--json", "set", "śmietana", "--opened", "--days-after-opening", "3")
    assert json.loads(out)["data"]["expires"] == "2026-10-18"
    code, out = run("move", "śmietana", "--where", "lodówka > półka 1", "--side", "środek")
    assert code == 0 and "Półka 1" in out and "pośrodku" in out
    code, out = run("history", "śmietana")
    assert "przeniesiono" in out and "dodano" in out


def test_map_rm_refuses_non_empty(run):
    run("add", "skarpetki", "--cat", "ubrania", "--where", "komoda > szuflada 1")
    assert run("map", "rm", "komoda")[0] == 1
    run("throw", "skarpetki", "--all")
    assert run("map", "rm", "komoda")[0] == 0


def test_where_falls_back_to_place_contents(run):
    run("add", "musztarda", "--where", "lodówka > półka 3")
    code, out = run("where", "lodówka > półka 3")
    assert code == 0 and "musztarda" in out


def test_map_add_with_shelves_in_one_call(run):
    code, out = run("map", "add", "Sypialnia > Szafa", "--shelves", "5")
    assert code == 0 and "W środku (5)" in out
    code, out = run("map", "add", "Pokój Teosia > Komoda nowa", "--drawers", "4")
    assert "W środku (4)" in out and "4. szuflada od góry, 1. od dołu" in out
