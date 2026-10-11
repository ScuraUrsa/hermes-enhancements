from types import SimpleNamespace

from ytdigest import cli
from ytdigest.queue import BACKLOG_PRIORITY


def test_add_from_file(cfg, tmp_path, capsys):
    f = tmp_path / "wl.txt"
    f.write_text("# Watch later\ndQw4w9WgXcQ\nhttps://www.youtube.com/watch?v=T3-uFayjJBI\n\nnot a video\ndQw4w9WgXcQ\n")
    a = SimpleNamespace(urls=[], file=str(f), account="fjkazmierczak", playlist="Do obejrzenia", now=False, backlog=False)
    assert cli.cmd_add(cfg, a) == 0
    assert "2 queued, 1 already known, 1 skipped" in capsys.readouterr().out
    row = cli._q(cfg).db.execute("SELECT * FROM videos WHERE video_id='T3-uFayjJBI'").fetchone()
    assert row["account"] == "fjkazmierczak" and "Do obejrzenia" in row["playlists"] and row["priority"] == BACKLOG_PRIORITY
