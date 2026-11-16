"""Attachment triage: real file type, active content, archives, optional ClamAV, and safe image re-encoding.

Nothing is opened with the program the file is meant for. Bytes are only inspected. Converting a document
to a safe form (CDR: render to pixels, rebuild a PDF) is done by Dangerzone in a sandbox on lab-w01, not
here (plan phase 3); this module decides which files need it.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import socket
import struct
import zipfile
from dataclasses import dataclass, field

# Extensions Windows/Android/macOS will execute or that run code when opened.
EXECUTABLE_EXT = {
    "exe", "scr", "com", "pif", "bat", "cmd", "msi", "msix", "msp", "cpl", "dll", "hta", "js", "jse", "vbs", "vbe",
    "wsf", "wsh", "ps1", "psm1", "lnk", "url", "reg", "inf", "jar", "apk", "app", "dmg", "pkg", "sh", "iso", "img",
    "vhd", "vhdx", "appx", "appxbundle", "chm", "scf", "xll", "library-ms", "search-ms", "settingcontent-ms", "one",
}
MACRO_EXT = {"docm", "dotm", "xlsm", "xltm", "xlam", "pptm", "potm", "ppam", "ppsm", "sldm", "xls", "doc", "ppt"}
ARCHIVE_EXT = {"zip", "rar", "7z", "gz", "tgz", "tar", "bz2", "xz", "cab", "arj", "ace", "lzh", "z"}
MARKUP_EXT = {"html", "htm", "shtml", "xhtml", "svg", "mht", "mhtml", "xml"}

_MAGIC = [
    (0, b"MZ", "pe"), (0, b"\x7fELF", "elf"), (0, b"PK\x03\x04", "zip"), (0, b"PK\x05\x06", "zip"),
    (0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole"), (0, b"%PDF", "pdf"), (0, b"Rar!\x1a\x07", "rar"),
    (0, b"7z\xbc\xaf\x27\x1c", "7z"), (0, b"\x1f\x8b", "gzip"), (0, b"{\\rtf", "rtf"),
    (0, b"L\x00\x00\x00\x01\x14\x02\x00", "lnk"), (0, b"\x89PNG\r\n\x1a\n", "png"), (0, b"\xff\xd8\xff", "jpeg"),
    (0, b"GIF8", "gif"), (0, b"RIFF", "riff"), (0, b"MSCF", "cab"), (0, b"\xca\xfe\xba\xbe", "macho"),
    (0, b"\xcf\xfa\xed\xfe", "macho"), (0x8001, b"CD001", "iso"), (0, b"BZh", "bzip2"), (0, b"\xfd7zXZ\x00", "xz"),
]
_EXT_FOR_KIND = {
    "pdf": {"pdf"}, "png": {"png"}, "jpeg": {"jpg", "jpeg", "jfif"}, "gif": {"gif"}, "riff": {"webp", "wav", "avi"},
    "zip": {"zip", "docx", "xlsx", "pptx", "odt", "ods", "odp", "epub", "jar", "apk", "docm", "xlsm", "pptm", "dotx",
            "xltx", "potx", "vsdx", "kmz", "xps", "oxps", "appx", "msix", "3mf", "pkpass", "numbers", "pages", "key"},
    "ole": {"doc", "xls", "ppt", "msg", "msi", "vsd", "pub", "dot", "xlt", "pot"},
    "rtf": {"rtf", "doc"}, "gzip": {"gz", "tgz"}, "rar": {"rar"}, "7z": {"7z"}, "cab": {"cab"}, "iso": {"iso", "img"},
    "bzip2": {"bz2"}, "xz": {"xz"},
}
_PDF_ACTIVE = (b"/JavaScript", b"/JS", b"/OpenAction", b"/AA", b"/Launch", b"/EmbeddedFile", b"/RichMedia",
               b"/XFA", b"/SubmitForm", b"/URI")


@dataclass
class AttachmentReport:
    id: str
    filename: str
    declared_type: str
    size: int
    sha256: str
    kind: str                     # detected from bytes
    flags: list[tuple[int, str, str]] = field(default_factory=list)
    needs_cdr: bool = False       # open only after Dangerzone conversion
    clamav: str = ""              # "", "OK", "<signature> FOUND", "error: ..."

    @property
    def score(self) -> int:
        return sum(w for w, _, _ in self.flags)


def detect_kind(data: bytes) -> str:
    for off, sig, kind in _MAGIC:
        if data[off: off + len(sig)] == sig:
            return kind
    head = data[:1024].lstrip().lower()
    if head.startswith((b"<!doctype html", b"<html", b"<head", b"<body", b"<script", b"<form", b"<meta")):
        return "html"
    if head.startswith(b"<?xml") or head.startswith(b"<svg"):
        return "svg" if b"<svg" in data[:4096].lower() else "xml"
    try:
        data[:4096].decode("utf-8")
        return "text"
    except UnicodeDecodeError:
        return "binary"


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _zip_flags(data: bytes, rep: AttachmentReport) -> None:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, ValueError, OSError):
        rep.flags.append((10, "zip_broken", "Archiwum ZIP jest uszkodzone (częsty trik na skanery)."))
        return
    names = zf.namelist()
    if any(i.flag_bits & 0x1 for i in zf.infolist()):
        rep.flags.append((35, "zip_encrypted", "Archiwum zaszyfrowane hasłem: antywirus nie zajrzy do środka (hasło "
                                               "zwykle jest w treści maila)."))
    if any(n.lower().endswith(("vbaproject.bin", "vbadata.xml")) for n in names):
        rep.flags.append((40, "office_macro", "Dokument Office zawiera makra VBA."))
    if any(n.lower().startswith(("word/", "xl/", "ppt/")) and n.lower().endswith(".bin") and "activex" in n.lower()
           for n in names):
        rep.flags.append((25, "office_activex", "Dokument Office zawiera kontrolki ActiveX."))
    total = sum(i.file_size for i in zf.infolist())
    if total > 500 * 1024 * 1024 or (len(data) and total / max(len(data), 1) > 200):
        rep.flags.append((30, "zip_bomb", "Archiwum rozpakowuje się do ogromnego rozmiaru (zip bomb)."))
    is_package = "[Content_Types].xml" in names or "mimetype" in names   # OOXML / ODF / EPUB
    if not is_package:
        inner_exec = [n for n in names if _ext(n) in EXECUTABLE_EXT]
        if inner_exec:
            rep.flags.append((50, "archive_executable",
                              f"W archiwum są pliki wykonywalne: {', '.join(inner_exec[:3])}."))
        if any(_ext(n) in ARCHIVE_EXT for n in names):
            rep.flags.append((10, "nested_archive", "Archiwum w archiwum."))
        if any(_ext(n) in MARKUP_EXT for n in names):
            rep.flags.append((20, "archive_html", "W archiwum jest plik HTML/SVG (częsta fałszywa strona logowania)."))


def _ole_flags(data: bytes, rep: AttachmentReport) -> None:
    if b"V\x00B\x00A\x00" in data or b"_VBA_PROJECT" in data or b"Macros" in data:
        rep.flags.append((40, "office_macro", "Stary dokument Office (OLE) z makrami VBA."))
    if b"Equation.3" in data or b"Equation Native" in data:
        rep.flags.append((40, "ole_equation", "Obiekt Equation Editor (znany exploit CVE-2017-11882)."))


def _pdf_flags(data: bytes, rep: AttachmentReport) -> None:
    found = sorted({k.decode().lstrip("/") for k in _PDF_ACTIVE if re.search(re.escape(k) + rb"[\s/<(\[]", data)})
    active = [k for k in found if k != "URI"]
    if active:
        w = 40 if {"JavaScript", "JS", "Launch"} & set(active) else 20
        rep.flags.append((w, "pdf_active", f"PDF z aktywną zawartością: {', '.join(active)}."))
    if b"/Encrypt" in data:
        rep.flags.append((10, "pdf_encrypted", "PDF zaszyfrowany (skanery widzą mniej)."))


def _markup_flags(data: bytes, rep: AttachmentReport) -> None:
    low = data[:2_000_000].lower()
    if b"<form" in low and (b"password" in low or b"has\xc5\x82o" in low or b"login" in low):
        rep.flags.append((50, "html_credential_form", "Załącznik HTML z formularzem logowania (phishing offline)."))
    elif b"<script" in low or b"onload=" in low or b"javascript:" in low:
        rep.flags.append((30, "markup_script", "Załącznik HTML/SVG uruchamia skrypty po otwarciu."))
    if b"window.location" in low or b"http-equiv=\"refresh\"" in low or b"location.href" in low:
        rep.flags.append((20, "markup_redirect", "Załącznik przekierowuje przeglądarkę na stronę w sieci."))
    if b"atob(" in low or b"unescape(" in low or b"fromcharcode" in low:
        rep.flags.append((20, "markup_obfuscated", "Zaciemniony kod w załączniku HTML/SVG."))


def clamd_scan(data: bytes, address: str | None = None, timeout: float = 30.0) -> str:
    """Scan bytes with clamd INSTREAM. ``address``: ``unix:/run/clamav/clamd.ctl`` or ``tcp:host:3310``.
    Returns "" when no address is configured (ClamAV optional), else clamd's verdict line."""
    address = address or os.environ.get("MAILGUARD_CLAMD", "")
    if not address:
        return ""
    try:
        if address.startswith("unix:"):
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(address[5:])
        else:
            host, port = address.removeprefix("tcp:").rsplit(":", 1)
            s = socket.create_connection((host, int(port)), timeout=timeout)
        with s:
            s.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), 1 << 16):
                chunk = data[i: i + (1 << 16)]
                s.sendall(struct.pack("!L", len(chunk)) + chunk)
            s.sendall(struct.pack("!L", 0))
            reply = b""
            while not reply.endswith(b"\0"):
                part = s.recv(4096)
                if not part:
                    break
                reply += part
        verdict = reply.rstrip(b"\0").decode(errors="replace")
        return verdict.split(":", 1)[-1].strip()   # "OK" or "Eicar-Signature FOUND"
    except OSError as e:
        return f"error: {e}"


def analyse_attachment(filename: str, declared_type: str, data: bytes, idx: int) -> AttachmentReport:
    filename = filename or "(bez nazwy)"
    rep = AttachmentReport(id=f"A{idx}", filename=filename, declared_type=declared_type, size=len(data),
                           sha256=hashlib.sha256(data).hexdigest(), kind=detect_kind(data))
    ext = _ext(filename)
    parts = filename.lower().split(".")
    if len(parts) >= 3 and parts[-1] in EXECUTABLE_EXT | MACRO_EXT and len(parts[-2]) <= 5:
        rep.flags.append((30, "double_extension",
                          f"Podwójne rozszerzenie ({'.'.join(parts[-2:])}) ukrywa prawdziwy typ."))
    if re.search("[‪-‮⁦-⁩]", filename):
        rep.flags.append((50, "rtlo_filename", "Nazwa pliku zawiera znak odwracający kierunek tekstu (RLO), żeby "
                                               "ukryć rozszerzenie."))
    if ext in EXECUTABLE_EXT or rep.kind in ("pe", "elf", "macho", "lnk"):
        rep.flags.append((70, "executable", f"Plik wykonywalny ({ext or rep.kind}). Nigdy nie uruchamiać."))
    expected = _EXT_FOR_KIND.get(rep.kind)
    if expected is not None and ext and ext not in expected and ext not in ARCHIVE_EXT | {"txt"}:
        rep.flags.append((35, "type_mismatch", f"Rozszerzenie .{ext} nie pasuje do zawartości ({rep.kind})."))
    if rep.kind == "zip":
        _zip_flags(data, rep)
    elif rep.kind == "ole":
        _ole_flags(data, rep)
    elif rep.kind == "pdf":
        _pdf_flags(data, rep)
    elif rep.kind in ("html", "svg", "xml") or ext in MARKUP_EXT:
        _markup_flags(data, rep)
    elif rep.kind == "iso":
        rep.flags.append((50, "disk_image", "Obraz dysku (ISO/IMG): sposób na przemycenie programów obok ochrony "
                                            "systemu."))
    elif rep.kind in ("rar", "7z", "gzip", "cab", "bzip2", "xz"):
        rep.flags.append((10, "archive_uninspected", f"Archiwum {rep.kind}: zawartość nie została sprawdzona."))
    rep.clamav = clamd_scan(data)
    if rep.clamav.endswith("FOUND"):
        rep.flags.append((100, "clamav", f"ClamAV: {rep.clamav}."))
    office = ext in {"doc", "docx", "docm", "xls", "xlsx", "xlsm", "ppt", "pptx", "pptm", "odt", "ods", "odp", "rtf"}
    rep.needs_cdr = rep.kind in ("pdf", "ole", "rtf") or office or rep.score >= 20
    return rep


# --- images -------------------------------------------------------------------------------------------------
MAX_PIXELS = 40_000_000


def sanitize_image(data: bytes, max_pixels: int = MAX_PIXELS) -> bytes:
    """Decode and re-encode an image as PNG: drops metadata (EXIF/GPS), trailing payloads, polyglot tricks.
    Needs Pillow (``pip install mailguard[images]``). Raises ValueError for anything that is not a clean image."""
    try:
        from PIL import Image
    except ImportError as e:  # pragma: no cover - optional dependency
        raise ValueError("Pillow nie jest zainstalowany (mailguard[images])") from e
    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in ("PNG", "JPEG", "GIF", "WEBP", "BMP"):
                raise ValueError(f"nieobsługiwany format obrazu: {im.format}")
            im.seek(0)
            frame = im.convert("RGBA") if im.mode in ("P", "LA", "RGBA") else im.convert("RGB")
            out = io.BytesIO()
            frame.save(out, format="PNG", optimize=True)
            return out.getvalue()
    except (OSError, Image.DecompressionBombError, SyntaxError) as e:
        raise ValueError(f"uszkodzony albo niebezpieczny obraz: {e}") from e
