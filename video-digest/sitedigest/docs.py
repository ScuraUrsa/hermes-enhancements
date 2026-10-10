"""Text out of downloaded course files, with only the standard library plus
pdftotext (poppler) or pypdf. Image-only PDFs (scanned handouts, exported
slides) are rendered to pictures so the vision model can read them."""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def _pdf(path: Path) -> str:
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"], capture_output=True, timeout=300)
        if r.returncode == 0:
            return r.stdout.decode("utf-8", "replace")
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    reader = PdfReader(str(path))
    return "\n\n".join(f"--- strona {i} ---\n{p.extract_text() or ''}" for i, p in enumerate(reader.pages, 1))


def _xml_text(data: bytes, tag_suffix: str) -> str:
    root = ET.fromstring(data)
    out, para = [], []
    for el in root.iter():
        name = el.tag.rsplit("}", 1)[-1]
        if name == tag_suffix and el.text:
            para.append(el.text)
        elif name == "p" and para:
            out.append("".join(para))
            para = []
    if para:
        out.append("".join(para))
    return "\n".join(out)


def _docx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        return _xml_text(z.read("word/document.xml"), "t")


def _pptx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)]
        names.sort(key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
        parts = []
        for n in names:
            num = re.search(r"(\d+)\.xml$", n).group(1)
            parts.append(f"--- slajd {num} ---\n{_xml_text(z.read(n), 't')}")
            notes = f"ppt/notesSlides/notesSlide{num}.xml"
            if notes in z.namelist():
                parts.append(f"(notatki prelegenta) {_xml_text(z.read(notes), 't')}")
        return "\n".join(parts)


def _xlsx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.iter():
                if si.tag.endswith("}si"):
                    strings.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
        return "\n".join(s for s in strings if s.strip())


def _odf(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("content.xml"))
    return "\n".join("".join(el.itertext()) for el in root.iter() if el.tag.rsplit("}", 1)[-1] in ("p", "h"))


def _html(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style|nav|footer|header)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<(br|/p|/div|/li|/h\d)>", "\n", raw)
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def _ipynb(path: Path) -> str:
    nb = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for c in nb.get("cells", []):
        src = "".join(c.get("source") or [])
        out.append(f"```python\n{src}\n```" if c.get("cell_type") == "code" else src)
    return "\n\n".join(out)


def _zip(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    return "Archiwum ZIP, pliki:\n" + "\n".join(f"- {n}" for n in names[:300])


READERS = {
    ".pdf": _pdf, ".docx": _docx, ".pptx": _pptx, ".xlsx": _xlsx, ".odt": _odf, ".odp": _odf, ".ods": _odf,
    ".html": _html, ".htm": _html, ".ipynb": _ipynb, ".zip": _zip,
}
PLAIN = {".txt", ".md", ".csv", ".json", ".py", ".js", ".sql", ".yaml", ".yml", ".rtf"}


def text_of(path: Path) -> str:
    ext = path.suffix.lower()
    try:
        if ext in READERS:
            text = READERS[ext](path)
        elif ext in PLAIN:
            text = path.read_text(encoding="utf-8", errors="replace")
        else:
            return ""
    except Exception as exc:
        return f"(nie udało się odczytać pliku: {type(exc).__name__}: {str(exc)[:200]})"
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def needs_pictures(path: Path, text: str) -> bool:
    """PDF with (almost) no text layer, or slides whose text is tiny: look at the pages."""
    if path.suffix.lower() != ".pdf":
        return False
    return len(re.sub(r"\s+|--- strona \d+ ---", "", text)) < 300


def render_pdf_pages(path: Path, out_dir: Path, max_pages: int = 12, dpi: int = 90) -> list[Path]:
    if not shutil.which("pdftoppm"):
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pdftoppm", "-jpeg", "-r", str(dpi), "-f", "1", "-l", str(max_pages), str(path), str(out_dir / "p")],
                   capture_output=True, timeout=300)
    return sorted(out_dir.glob("p-*.jpg"))
