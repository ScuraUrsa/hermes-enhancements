"""A tiny course platform for tests: login wall, course home with two modules,
lessons with a video, a PDF and a DOCX, plus links that must never be opened."""

from __future__ import annotations

import io
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = """<html><head><title>Kurs Demo</title></head><body>
<nav><a href="/courses/demo">Kurs Demo</a> <a href="/logout">Wyloguj</a> <a href="/cart">Koszyk</a></nav>
<main><h1>Kurs Demo: notatki</h1>
<section><h3>Moduł 1: Podstawy</h3><ul>
  <li><a href="/courses/demo/lessons/1-wstep">Lekcja 1: Wstęp</a></li>
  <li><a href="/courses/demo/lessons/2-zasady?utm_source=x">Lekcja 2: Zasady</a></li>
</ul></section>
<section><h3>Moduł 2: Praktyka</h3><ul>
  <li><a href="/courses/demo/lessons/3-cwiczenie">Lekcja 3: Ćwiczenie</a></li>
  <li><a href="/courses/demo/lessons/3-cwiczenie/mark_complete">Oznacz jako ukończone</a></li>
</ul></section></main></body></html>"""

LESSON = """<html><head><title>{title}</title></head><body>
<nav><a href="/courses/demo">Spis</a></nav>
<main><h1>{title}</h1>{body}</main></body></html>"""

LESSONS = {
    "1-wstep": ("Lekcja 1: Wstęp", "<p>" + "Notatki to system, nie zbiór plików. " * 20 + "</p>"
                '<video controls src="/media/l1.mp4"></video><p><a href="/files/handout.pdf">Pobierz handout (PDF)</a></p>'),
    "2-zasady": ("Lekcja 2: Zasady", "<h2>Trzy zasady</h2><ol><li>Jedna myśl na notatkę</li><li>Linkuj</li><li>Przeglądaj co tydzień</li></ol>"
                 "<p>" + "Zasady są proste, ale wymagają nawyku. " * 15 + "</p>"
                 '<iframe src="https://player.vimeo.com/video/123456789?h=abc"></iframe>'),
    "3-cwiczenie": ("Lekcja 3: Ćwiczenie", "<p>" + "Zrób ćwiczenie z arkusza. " * 20 + "</p>"
                    '<a href="/files/arkusz.docx">Arkusz ćwiczeń</a>'),
}


def docx_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml",
                   '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                   f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p><w:p><w:r><w:t>Krok 2: zapisz wnioski.</w:t></w:r></w:p></w:body></w:document>')
    return buf.getvalue()


def pdf_bytes(text: str) -> bytes:
    stream = f"BT /F1 18 Tf 50 750 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


class Site:
    def __init__(self, video: Path | None = None):
        self.video = video
        self.hits: list[str] = []
        site = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body=b"", ctype="text/html; charset=utf-8", headers=None):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                site.hits.append("POST " + self.path)
                self._send(302, headers={"Location": "/courses/demo", "Set-Cookie": "sess=ok; Path=/"})

            def do_GET(self):
                site.hits.append(self.path)
                path = self.path.split("?")[0]
                if path == "/login":
                    return self._send(200, b'<form method="post"><input type="email" name="email"><input type="password" name="pw"></form>')
                if "sess=ok" not in (self.headers.get("Cookie") or ""):
                    return self._send(302, headers={"Location": "/login"})
                if path == "/courses/demo":
                    return self._send(200, HOME.encode())
                if path.startswith("/courses/demo/lessons/"):
                    slug = path.rsplit("/", 1)[-1]
                    if slug in LESSONS:
                        t, b = LESSONS[slug]
                        return self._send(200, LESSON.format(title=t, body=b).encode())
                if path == "/files/handout.pdf":
                    return self._send(200, pdf_bytes("Handout: trzy zasady notatek"), "application/pdf")
                if path == "/files/arkusz.docx":
                    return self._send(200, docx_bytes("Krok 1: wypisz tematy."), "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                      {"Content-Disposition": 'attachment; filename="arkusz.docx"'})
                if path == "/media/l1.mp4" and site.video:
                    return self._send(200, site.video.read_bytes(), "video/mp4")
                return self._send(404, b"not found")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
