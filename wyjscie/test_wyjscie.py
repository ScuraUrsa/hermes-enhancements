import json
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import wyjscie  # noqa: E402


def forecast(day="2026-10-31", temp=10.0, feels=None, precip=0.0, prob=0, code=3, clouds=80, wind=10,
             sunrise="06:40", sunset="16:20", gusts=20, drop=0.0):
    hourly = []
    for h in range(24):
        t = temp - drop * h / 23
        hourly.append({"time": f"{day}T{h:02d}:00", "temp": t, "feels": (feels if feels is not None else t),
                       "precip_mm": precip, "precip_prob": prob, "code": code, "clouds": clouds, "wind_kmh": wind})
    return {"hourly": hourly, "days": [{"date": day, "sunrise": sunrise, "sunset": sunset, "gusts_kmh": gusts}]}


def args(argv):
    import argparse
    ap_argv = ["plan", "--profil", "/nonexistent"] + argv
    p = argparse.ArgumentParser()
    p.add_argument("cmd")
    for opt in ("--od", "--do", "--gdzie", "--okazja", "--wyjazd", "--pogoda-json", "--garderoba-json", "--profil",
                "--trasa-json"):
        p.add_argument(opt)
    p.add_argument("--miejsce", default="")
    p.add_argument("--transport", default="")
    p.add_argument("--z-dzieckiem", action="store_true")
    p.add_argument("--dodaj", action="append", default=[])
    a = p.parse_args(ap_argv)
    a.start = wyjscie.parse_when(a.od)
    a.end = wyjscie.parse_when(a.do, a.start.date()) if a.do else a.start + timedelta(hours=2)
    a.miejsce = [m for m in a.miejsce.split(",") if m]
    a.transport = [t for t in a.transport.split(",") if t]
    return a


def items(out):
    return [x for _, xs in out["lista"] for x in xs]


def run(argv, wx, wardrobe=None, outfit=True):
    a = args(argv)
    return wyjscie.build(a, prof=wyjscie.load_profile("/nonexistent"), weather_data=wx, wardrobe=wardrobe,
                         with_outfit=outfit)


def test_parse_when():
    base = datetime(2026, 10, 25).date()
    assert wyjscie.parse_when("jutro 18:00", base) == datetime(2026, 10, 26, 18, 0)
    assert wyjscie.parse_when("31.10 18:30", base) == datetime(2026, 10, 31, 18, 30)
    assert wyjscie.parse_when("2026-11-02T09:15", base) == datetime(2026, 11, 2, 9, 15)
    assert wyjscie.parse_when("01.01 10:00", base).year == 2027
    with pytest.raises(ValueError):
        wyjscie.parse_when("kiedyś", base)


def test_always_items_and_no_child_items():
    out = run(["--od", "2026-10-31 12:00", "--do", "2026-10-31 13:00"], forecast(temp=15))
    got = items(out)
    assert "klucze" in got and "chusteczki higieniczne" in got
    assert not any("pieluch" in x for x in got)
    assert not any("ładowarka" in x for x in got)


def test_rain_umbrella_unless_windy():
    out = run(["--od", "2026-10-31 12:00", "--transport", "pieszo"], forecast(precip=1.0, prob=80))
    assert "parasol" in items(out)
    out = run(["--od", "2026-10-31 12:00", "--transport", "pieszo"], forecast(precip=1.0, prob=80, wind=45))
    got = items(out)
    assert "parasol" not in got and any("przeciwdeszczowa" in x for x in got)


def test_cold_dark_long_with_child():
    wx = forecast(temp=2, feels=-3, sunset="16:20")
    out = run(["--od", "2026-10-31 14:00", "--do", "2026-10-31 20:00", "--z-dzieckiem", "--transport", "taxi",
               "--miejsce", "sala_zabaw"], wx)
    got = items(out)
    flags = out["pogoda"]["flags"]
    assert {"zimno", "mroz", "ciemno"} <= set(flags)
    assert any("pieluchy" in x for x in got)
    assert any("fotelik" in x for x in got)
    assert any("skarpetki" in x for x in got)
    assert any("ładowarka" in x for x in got)
    assert any("czapka i rękawiczki dziecka" in x for x in got)
    assert out["szykuj_od"] == "13:30"  # 10 + 20 min z dzieckiem


def test_occasion_gift_and_hints():
    out = run(["--od", "2026-10-31 18:00", "--do", "2026-10-31 23:00", "--okazja", "urodziny",
               "--transport", "auto", "--wyjazd", "17:40"], forecast())
    assert any("prezent" in x for x in items(out))
    assert any("Prezent" in h for h in out["podpowiedzi"])
    assert any("Auto" in h for h in out["podpowiedzi"])
    assert out["wyjazd"] == "17:40" and out["szykuj_od"] == "17:30"


def test_extra_items_and_pool():
    out = run(["--od", "2026-10-31 10:00", "--miejsce", "basen", "--dodaj", "karnet"], forecast(temp=12))
    got = items(out)
    assert "karnet" in got and any("strój kąpielowy" in x for x in got)


def test_weather_missing():
    out = run(["--od", "2026-10-31 10:00"], {"_error": "prognoza sięga 16 dni"})
    assert out["pogoda"]["ok"] is False
    assert out["stroj"]["poziom"] == 3
    assert any("Pogoda" in h for h in out["podpowiedzi"])


WARDROBE = {"ok": True, "data": [
    {"item": "kurtka zimowa czarna", "place": "Korytarz > Szafa", "note": "typ:kurtka ciepło:5 styl:casual woda:tak kto:filip kolor:czarny"},
    {"item": "płaszcz wełniany", "place": "Sypialnia > Szafa", "note": "typ:płaszcz ciepło:4 styl:elegancki kto:filip kolor:granat"},
    {"item": "kurtka przejściowa", "place": "Korytarz > Szafa", "note": "typ:kurtka ciepło:3 styl:casual kto:filip"},
    {"item": "koszula biała", "place": "Sypialnia > Szafa", "note": "typ:koszula ciepło:2 styl:elegancki kto:filip"},
    {"item": "bluza szara", "place": "Sypialnia > Komoda", "note": "typ:bluza ciepło:3 styl:casual kto:filip stan:pranie"},
    {"item": "spodnie chino", "place": "Sypialnia > Szafa", "note": "typ:spodnie ciepło:3 styl:smart kto:filip"},
    {"item": "półbuty skórzane", "place": "Korytarz", "note": "typ:półbuty ciepło:3 styl:elegancki kto:filip"},
    {"item": "kurtka Teosia", "place": "Pokój Teosia > Szafa 1", "note": "typ:kurtka ciepło:4 styl:casual woda:tak kto:teos"},
    {"item": "skarpetki bez notatki", "place": "Sypialnia", "note": None},
]}


def test_wardrobe_parsing(tmp_path):
    f = tmp_path / "g.json"
    f.write_text(json.dumps(WARDROBE, ensure_ascii=False))
    wr = wyjscie.load_wardrobe(str(f))
    assert len(wr) == 8  # rzecz bez typu pominięta
    assert {x["slot"] for x in wr} == {"okrycie", "gora", "dol", "buty"}


def test_outfit_date_cold(tmp_path):
    f = tmp_path / "g.json"
    f.write_text(json.dumps(WARDROBE, ensure_ascii=False))
    wr = wyjscie.load_wardrobe(str(f))
    out = run(["--od", "2026-10-31 18:00", "--do", "2026-10-31 22:00", "--okazja", "randka"],
              forecast(temp=5, feels=3), wardrobe=wr)
    st = out["stroj"]
    assert st["poziom"] == 4
    assert st["sloty"]["okrycie"][0]["nazwa"] == "płaszcz wełniany"  # styl elegancki, ciepło 4
    assert st["sloty"]["gora"][0]["nazwa"] == "koszula biała"
    assert st["sloty"]["buty"][0]["nazwa"] == "półbuty skórzane"
    text = wyjscie.fmt(out)
    assert "płaszcz wełniany" in text and "Spakuj" in text


def test_outfit_skips_laundry_and_other_people(tmp_path):
    f = tmp_path / "g.json"
    f.write_text(json.dumps(WARDROBE, ensure_ascii=False))
    wr = wyjscie.load_wardrobe(str(f))
    out = run(["--od", "2026-10-31 11:00", "--okazja", "spacer", "--z-dzieckiem"], forecast(temp=9, precip=2, prob=90),
              wardrobe=wr)
    st = out["stroj"]
    names = [x["nazwa"] for xs in st["sloty"].values() for x in xs]
    assert "bluza szara" not in names and "kurtka Teosia" not in names
    assert st["sloty"]["okrycie"][0]["woda"] is True  # deszcz: wodoodporna
    assert out["stroj_dziecka"]["sloty"]["okrycie"][0]["nazwa"] == "kurtka Teosia"


def test_no_wardrobe_generic():
    out = run(["--od", "2026-10-31 11:00"], forecast(temp=25, clouds=10), wardrobe=[])
    assert out["stroj"]["poziom"] == 1
    assert "slonce" in out["pogoda"]["flags"] and "cieplo" in out["pogoda"]["flags"]
    assert "okulary przeciwsłoneczne" in items(out)
    assert "garderoba jeszcze nie spisana" in wyjscie.fmt(out)


def test_profile_overrides(tmp_path):
    p = tmp_path / "profil.json"
    p.write_text(json.dumps({"zawsze": ["okulary korekcyjne"], "pomijaj": ["chusteczki higieniczne"],
                             "dziecko": {"pieluchy": False}}, ensure_ascii=False))
    prof = wyjscie.load_profile(str(p))
    assert prof["dziecko"]["wozek"] is True and prof["dziecko"]["pieluchy"] is False
    a = args(["--od", "2026-10-31 10:00", "--z-dzieckiem"])
    out = wyjscie.build(a, prof=prof, weather_data=forecast(), wardrobe=[])
    got = items(out)
    assert "okulary korekcyjne" in got and "chusteczki higieniczne" not in got
    assert not any("pieluchy" in x for x in got)


def test_rules_file_valid():
    rules = wyjscie.load_rules()
    groups = {g for g, _ in rules["grupy"]}
    keys = {"pogoda", "okazja", "miejsce", "transport", "dziecko", "pieluchy", "wozek", "min_h", "wiatr"}
    for r in rules["rzeczy"]:
        assert r["grupa"] in groups, r
        for c in ("gdy", "chyba_ze"):
            assert set(r.get(c, {})) <= keys, r
        for f in r.get("gdy", {}).get("pogoda", []):
            assert f in wyjscie.FLAGS, r


def test_cli_slownik(capsys):
    assert wyjscie.main(["slownik"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert "basen" in d["miejsca"] and "randka" in d["okazje"]


def test_cli_offline(tmp_path, capsys):
    f = tmp_path / "wx.json"
    f.write_text(json.dumps(forecast()))
    g = tmp_path / "g.json"
    g.write_text("[]")
    rc = wyjscie.main(["plan", "--od", "2026-10-31 18:00", "--do", "23:00", "--okazja", "teatr",
                       "--pogoda-json", str(f), "--garderoba-json", str(g), "--profil", "/nonexistent"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Wyjście 31.10 18:00–23:00" in out and "Dress code" in out
    assert wyjscie.main(["plan", "--od", "kiedyś"]) == 2


ROUTE = {"tryb": "zaplanowane", "wyjdz_o": "18:20",
         "odcinki": [{"od": "dom", "do": "Teatr", "najlepsza": {"sposob": "tramwaj 8"},
                      "srodek_dla_wyjscia": {"pieszo_min": 12, "na_zewnatrz_min": 18, "bagaz": True}}],
         "powrot": {"sposob": "Bolt"}}


def test_route_contract(tmp_path):
    f = tmp_path / "trasa.json"
    f.write_text(json.dumps(ROUTE, ensure_ascii=False))
    out = run(["--od", "2026-10-31 19:00", "--do", "23:00", "--okazja", "teatr", "--trasa-json", str(f)],
              forecast(precip=1, prob=70, sunset="16:20"))
    assert out["wyjazd"] == "18:20"
    assert set(out["transport"]) == {"komunikacja", "taxi", "pieszo"}
    got = items(out)
    assert any("bilet / aplikacja" in x for x in got) and "parasol" in got
    assert any("odblask" in x for x in got)
    assert any("bagaż" in h for h in out["podpowiedzi"])


def test_transport_words():
    assert wyjscie.transport_word("Bolt") == "taxi"
    assert wyjscie.transport_word("SKM Gdańsk Śródmieście") == "komunikacja"
    assert wyjscie.transport_word("PKP Intercity") == "pociag"
    assert wyjscie.transport_word("hulajnoga Tier") == "hulajnoga"
    assert wyjscie.transport_word("auto") == "auto"
    assert wyjscie.transport_word("teleport") is None
