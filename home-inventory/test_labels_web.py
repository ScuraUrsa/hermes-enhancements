import json
import os
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import dom  # noqa: E402
import dom_web  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DOM_DB", str(tmp_path / "dom.db"))
    monkeypatch.setenv("DOM_TODAY", "2026-10-31")
    assert dom.run(["map", "add", "Pokój Teosia > Szafa 1", "--shelves", "2"])[0] == 0
    assert dom.run(["code", "pokój Teosia > szafa 1", "--sub"])[0] == 0  # D001 szafa, D002/D003 półki
    assert dom.run(["add", "body Teosia", "--qty", "3", "--where", "#D003", "--side", "lewo", "--depth", "przód"])[0] == 0
    assert dom.run(["add", "kefir", "--exp", "01.11", "--where", "#D002"])[0] == 0
    return tmp_path


def test_place_view(db):
    con = dom.connect()
    status, v = dom_web.place_view(con, "D001")
    con.close()
    assert status == 200
    assert v["path"] == "Pokój Teosia → Szafa 1"
    assert [i["item"] for i in v["items"]] == ["kefir", "body Teosia"]  # earliest expiry first
    assert [k["code"] for k in v["inside"]] == ["D002", "D003"] and [k["items"] for k in v["inside"]] == [1, 1]


def test_http_pages(db):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dom_web.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        page = urllib.request.urlopen(base + "/dom/D003").read().decode()
        assert "body Teosia" in page and "po lewej z przodu" in page
        page = urllib.request.urlopen(base + "/D001").read().decode()  # tailscale serve may strip /dom
        assert "kefir" in page and "do 01.11" in page and 'href="/dom/D002"' in page
        assert json.loads(urllib.request.urlopen(base + "/dom/d-2.json").read())["code"] == "D002"
        assert "D003" in urllib.request.urlopen(base + "/dom/").read().decode()
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/dom/D099")
        assert e.value.code == 404
    finally:
        srv.shutdown()


def test_labels_and_cards(db, tmp_path):
    labels = pytest.importorskip("dom_labels")
    out = tmp_path / "n.html"
    assert labels.main(["labels", "--where", "pokój Teosia > szafa 1", "--out", str(out)]) == 0
    page = out.read_text(encoding="utf-8")
    assert page.count('class="cell"') == 3 and "D001" in page and "D003" in page and "<svg" in page
    assert labels.main(["labels", "D2", "--copies", "2", "--size", "50x30", "--out", str(out)]) == 0
    page = out.read_text(encoding="utf-8")
    assert page.count('class="cell"') == 2 and "width: 50.0mm" in page
    with pytest.raises(SystemExit):
        labels.main(["labels", "D009", "--out", str(out)])
    # --where without --assign does not hand out codes
    dom.run(["map", "add", "Kuchnia > Lodówka"])
    with pytest.raises(SystemExit):
        labels.main(["labels", "--where", "lodówka", "--out", str(out)])
    assert "Lodówka" not in dom.run(["code", "--list"])[1]
    assert labels.main(["card", "--name", "Jan Testowy", "--phone", "+48 600 000 000", "--email", "jan@example.com",
                        "--count", "4", "--out", str(out)]) == 0
    page = out.read_text(encoding="utf-8")
    assert page.count('class="cell card"') == 4 and "Jan Testowy" in page
