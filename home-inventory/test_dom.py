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


def test_batch_runs_and_verifies_each_line(run):
    code, out = run("batch",
                    'add masło --exp 30.10 --where "lodówka > półka 3"',
                    'add "ser żółty" --exp 25.10 --where "lodówka > półka 3"',
                    'dom add kefir --qty 2 --exp 19.10 --where "lodówka > półka 3"')
    assert code == 0, out
    assert out.count("✅") == 3 and "Wykonano 3 z 3." in out
    code, out = run("--json", "where", "kefir")
    assert json.loads(out)["data"][0]["qty"] == 2


def test_batch_reports_partial_failure(run):
    code, out = run("batch", 'add mąka --where "lodówka > półka 1"', 'add cukier --where "spiżarka"',
                    'map add "Sypialnia > Szafa" --shelves 2')
    assert code == 6
    assert "❌ 2/3" in out and "Wykonano 2 z 3." in out and "NIE zapisano" in out
    assert run("where", "mąka")[0] == 0 and run("where", "cukier")[0] == 3


def test_unquoted_multiword_names_and_paths(run):
    code, out = run("add", "ser", "żółty", "--exp", "20", "października", "--where", "lodówka", ">", "półka", "2")
    assert code == 0, out
    code, out = run("--json", "where", "ser", "żółty")
    d = json.loads(out)["data"][0]
    assert d["expires"] == "2026-10-20" and d["place"].startswith("Kuchnia → Lodówka → Półka 2")
    code, out = run("batch", "add jogurt grecki --where lodówka > półka 1", "map add Sypialnia > Szafa --shelves 3")
    assert code == 0 and "Wykonano 2 z 2." in out, out


def test_sector_written_into_where_is_peeled_off(run):
    code, out = run("add", "body Teosia", "--where", "pokój Teosia > szafa 1 > półka 2 > z lewej z przodu")
    assert code == 0, out
    code, out = run("where", "body Teosia")
    assert "Półka 2" in out and "po lewej, z przodu" in out
    code, out = run("move", "body Teosia", "--where", "komoda > szuflada 1 > prawo")
    assert code == 0 and "Szuflada 1" in out and "po prawej" in out


def test_shelf_count_written_as_last_segment(run):
    code, out = run("map", "add", "Sypialnia > Regał > 4 półki")
    assert code == 0 and "W środku (4)" in out and "półki" not in out.split("Ścieżka:")[1].split(".")[0].lower()
    code, out = run("map", "add", "Sypialnia > Komoda > z 3 szufladami")
    assert code == 0 and "W środku (3)" in out
    code, out = run("map", "add", "Gabinet > Regał biały z 5 półkami")
    assert code == 0 and "Regał biały" in out and "W środku (5)" in out


def test_clothes_get_their_category(run):
    run("add", "body Teosia z długim rękawem", "--where", "pokój Teosia > szafa 1 > półka 2")
    run("add", "skarpetki", "--where", "komoda > szuflada 1")
    code, out = run("list", "--cat", "ubrania")
    assert "body Teosia" in out and "skarpetki" in out


def test_round5_dates_unknown_place_and_shelf_count(run):
    assert dom.parse_date("jutra") == "2026-10-16"
    assert dom.parse_date("do jutra") == "2026-10-16"
    assert dom.parse_date("ważny do 20.10") == "2026-10-20"
    assert dom.parse_date("pojutrze") == "2026-10-17"
    code, out = run("add", "ryż", "--where", "spiżarnia")
    assert code == 5 and "Zapytaj Filipa" in out and "Podobne" not in out
    code, out = run("map", "add", "Kuchnia > Lodówka nowa > półki 3")
    assert code == 0 and "W środku (3)" in out
    code, out = run("map", "add", "Kuchnia > Lodówka nowa > Półka 4")  # a single shelf stays a place
    assert code == 0 and "Półka 4" in out


def test_clothes_attributes_in_note_and_tag(run):
    run("add", "płaszcz wełniany", "--cat", "ubrania", "--where", "pokój Teosia > szafa 1 > półka 1",
        "--note", "typ:płaszcz ciepło:4 kto:filip stan:czyste")
    code, out = run("set", "płaszcz wełniany", "--tag", "stan:pranie", "--tag", "kolor:granat")
    assert code == 0, out
    code, out = run("--json", "list", "--cat", "ubrania")
    d = json.loads(out)["data"][0]
    assert {"item", "place", "note"} <= d.keys()
    assert d["note"] == "typ:płaszcz ciepło:4 kto:filip stan:pranie kolor:granat"
    assert run("set", "płaszcz wełniany", "--tag", "zle")[0] == 2


def test_codes_for_qr_labels(run, tmp_path):
    code, out = run("code")
    assert code == 0 and "Żadne miejsce" in out
    code, out = run("--json", "code", "pokój Teosia > szafa 1", "--sub")
    assert code == 0, out
    data = json.loads(out)["data"]
    assert [d["code"] for d in data] == ["D001", "D002", "D003", "D004"]  # the wardrobe, then shelves 1-3
    assert data[0]["full_path"] == "Mieszkanie > Pokój Teosia > Szafa 1"
    code, out = run("code", "pokój Teosia > szafa 1 > półka 2")  # already has one: unchanged
    assert code == 0 and "Kody już były" in out and "D003" in out
    code, out = run("code", "kuchnia > lodówka")
    assert "D005" in out
    # #D003 works wherever a place is expected
    code, out = run("add", "body Teosia", "--where", "#D003", "--qty", "3")
    assert code == 0 and "Pokój Teosia → Szafa 1 → Półka 2" in out
    code, out = run("where", "#d003")
    assert code == 0 and "body Teosia" in out
    code, out = run("move", "body", "--where", "D-5")
    assert code == 0 and "Lodówka" in out
    assert run("add", "x", "--where", "#D099")[0] == 5
    code, out = run("map", "show", "pokój Teosia")
    assert "kod D001" in out
    run("move", "body", "--where", "#D003")
    assert run("map", "rm", "kuchnia > lodówka")[0] == 0  # D005 is gone ...
    code, out = run("code", "kuchnia > szafka pod zlewem")
    assert "D006" in out  # ... and not reused


def test_codes_column_added_to_an_old_db(tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(dom.SCHEMA)  # the pre-QR schema has no places.code
    old.execute("INSERT INTO places(parent_id, name, kind) VALUES (NULL, 'Mieszkanie', 'mieszkanie')")
    old.commit()
    old.close()
    monkeypatch.setenv("DOM_DB", str(path))
    code, out = dom.run(["code", "Mieszkanie"])
    assert code == 0 and "D001" in out
