"""What on a page is a video, a document or an image, and how to download it.

Videos go through yt-dlp, which knows the players course platforms embed
(Vimeo, Wistia, YouTube, Loom, Vidyard, Bunny, Mux, JW Player, Brightcove,
Kajabi, plain HLS/DASH/MP4). Private embeds usually only play when the request
carries the lesson page as Referer, so every download sends it. DRM-protected
streams (Widevine) are recorded as such and skipped: the lesson is still
digested from its text, documents and captions.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

VIDEO_HOSTS = re.compile(
    r"(youtube\.com/(embed|watch)|youtu\.be/|player\.vimeo\.com/video|vimeo\.com/\d+|"
    r"fast\.wistia\.(net|com)/(embed|medias)|wistia\.com/medias|\.wistia\.com/|loom\.com/(share|embed)|"
    r"play\.vidyard\.com|iframe\.mediadelivery\.net|video\.bunnycdn|stream\.mux\.com|"
    r"cdn\.jwplayer\.com|content\.jwplatform\.com|players\.brightcove\.net|"
    r"vz-[\w-]+\.b-cdn\.net|kajabi-storefronts|hotmart\.com/.*/video|vdocipher\.com|"
    r"dailymotion\.com/(embed|video)|streamable\.com|vooplayer|spotlightr\.com|"
    r"descript\.com/embed|tella\.tv|scribehow\.com/embed)",
    re.I)
MEDIA_EXT = re.compile(r"\.(mp4|m4v|webm|mov|mkv|m3u8|mpd|mp3|m4a|wav|ogg)(\?|$)", re.I)
DOC_EXT = re.compile(r"\.(pdf|docx?|pptx?|xlsx?|csv|txt|md|rtf|odt|odp|ods|epub|zip|json|ipynb|py|js|sql|ya?ml)(\?|$)", re.I)
IMAGE_EXT = re.compile(r"\.(png|jpe?g|gif|webp|svg)(\?|$)", re.I)
# HLS/DASH sub-playlists and segments seen on the network: not videos of their own
SEGMENT = re.compile(r"(\.ts|\.m4s|\.aac|/seg-|/segment|/chunk|/frag|init\.mp4|_\d+\.m3u8|/(video|audio)/\d+/)", re.I)


# Course handouts are often shared Google Docs/Drive or Dropbox links: fetch their export.
SHARED_DOC = [
    (re.compile(r"docs\.google\.com/document/d/([\w-]+)"), "https://docs.google.com/document/d/{}/export?format=docx"),
    (re.compile(r"docs\.google\.com/presentation/d/([\w-]+)"), "https://docs.google.com/presentation/d/{}/export/pptx"),
    (re.compile(r"docs\.google\.com/spreadsheets/d/([\w-]+)"), "https://docs.google.com/spreadsheets/d/{}/export?format=xlsx"),
    (re.compile(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:export=download&)?id=)([\w-]+)"),
     "https://drive.google.com/uc?export=download&id={}"),
]


def captions_for(video: Path, languages: list[str] | None = None) -> list[Path]:
    """Caption files next to a downloaded video: `<stem>.vtt` or `<stem>.<lang>.vtt`
    (yt-dlp, Whisper on the PC), preferred languages first."""
    import glob

    stem = glob.escape(video.stem)
    found = [f for f in video.parent.glob(f"{stem}*.vtt")
             if f.name == f"{video.stem}.vtt" or (f.name.startswith(f"{video.stem}.") and f.name.count(".") == video.stem.count(".") + 2)]
    langs = languages or []
    return sorted(found, key=lambda f: (next((i for i, l in enumerate(langs) if f.name.endswith(f".{l}.vtt")), 99), f.name))


def download_url(url: str) -> str:
    """The URL that returns the file itself (shared Google files -> export, Dropbox -> dl=1)."""
    for rx, tpl in SHARED_DOC:
        m = rx.search(url)
        if m:
            return tpl.format(m.group(1))
    if "dropbox.com/" in url:
        return re.sub(r"([?&])dl=0", r"\1dl=1", url) if "dl=0" in url else url + ("&" if "?" in url else "?") + "dl=1"
    return url


def classify(url: str) -> str | None:
    if not url or url.startswith(("blob:", "data:", "javascript:", "mailto:", "tel:")):
        return None
    if VIDEO_HOSTS.search(url):
        return "video"
    if any(rx.search(url) for rx, _ in SHARED_DOC) or re.search(r"dropbox\.com/(s|scl)/", url):
        return "doc"
    path = urlparse(url).path
    if MEDIA_EXT.search(path):
        return None if SEGMENT.search(path) else "video"
    if DOC_EXT.search(path):
        return "doc"
    if IMAGE_EXT.search(path):
        return "image"
    return None


def wistia_embed(media_id: str) -> str:
    return f"https://fast.wistia.net/embed/iframe/{media_id}"


def page_videos(found: dict, base_url: str) -> list[str]:
    """Pick the videos of one page from what the crawler saw, best source first:
    known players (iframes, data attributes), then <video> sources, and only if
    neither exists, manifests caught on the network (master playlists, not segments)."""
    embeds, direct, network = [], [], []
    for u in found.get("iframes", []) + found.get("embeds", []):
        u = urljoin(base_url, u)
        if classify(u) == "video":
            embeds.append(u)
    for u in found.get("videos", []):
        u = urljoin(base_url, u)
        if classify(u) == "video" or MEDIA_EXT.search(urlparse(u).path):
            direct.append(u)
    for u in found.get("network", []):
        if classify(u) == "video" and not SEGMENT.search(urlparse(u).path):
            network.append(u)
    picked = embeds + direct
    if not picked:
        by_host: dict[str, str] = {}
        for u in network:  # first manifest per host is normally the master playlist
            by_host.setdefault(urlparse(u).netloc, u)
        picked = list(by_host.values())
    seen, out = set(), []
    for u in picked:
        key = u.split("#")[0]
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def download_video(url: str, out_dir: Path, *, referer: str, cookies: str | None, max_height: int = 480,
                   languages: list[str] | None = None, stem: str = "video") -> dict:
    """Returns {path, title, duration, subtitles: Path|None, drm: bool, error: str|None}."""
    from ytdigest import fetch

    out_dir.mkdir(parents=True, exist_ok=True)
    origin = f"{urlparse(referer).scheme}://{urlparse(referer).netloc}"
    langs = languages or ["pl", "en"]
    opts = {
        "format": f"bv*[height<={max_height}]+ba/b[height<={max_height}]/bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / f"{stem}.%(ext)s"),
        "http_headers": {"Referer": referer, "Origin": origin},
        "writesubtitles": True, "writeautomaticsub": True, "subtitleslangs": [f"{l}.*" for l in langs] + langs,
        "subtitlesformat": "vtt/best", "ignoreerrors": False, "noplaylist": True,
        "allow_unplayable_formats": False,
    }
    res = {"path": None, "title": None, "duration": None, "subtitles": None, "drm": False, "error": None}
    try:
        with fetch._ydl(opts, cookies) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as exc:
        msg = str(exc)
        res["drm"] = "drm" in msg.lower()
        res["error"] = msg[:400]
        return res
    if info.get("_type") == "playlist":  # a player page listing several videos: take the first
        info = (info.get("entries") or [{}])[0] or {}
    res["title"] = info.get("title")
    res["duration"] = info.get("duration")
    files = sorted(out_dir.glob(f"{stem}.*"))
    vids = [p for p in files if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov", ".m4v", ".mp3", ".m4a")]
    subs = [p for p in files if p.suffix.lower() == ".vtt"]
    res["path"] = vids[0] if vids else None
    if subs:  # prefer the configured language order
        subs.sort(key=lambda p: next((i for i, l in enumerate(langs) if f".{l}" in p.name), 99))
        res["subtitles"] = subs[0]
    if not res["path"]:
        res["error"] = "yt-dlp finished without a media file"
    return res


def _filename(url: str, headers) -> str:
    cd = headers.get("Content-Disposition") or ""
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd) or re.search(r'filename="?([^";]+)"?', cd)
    name = unquote(m.group(1)) if m else unquote(Path(urlparse(url).path).name) or "file"
    return re.sub(r"[^\w.\- ()ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+", "_", name)[:120]


def download_doc(http, url: str, out_dir: Path, *, referer: str, max_mb: int = 200) -> dict:
    """Returns {path, name, bytes, content_type, error}. Follows redirects (signed S3 links)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {"path": None, "name": None, "bytes": 0, "content_type": None, "error": None}
    try:
        with http.get(download_url(url), headers={"Referer": referer}, stream=True, timeout=120, allow_redirects=True) as r:
            if r.status_code >= 400:
                res["error"] = f"HTTP {r.status_code}"
                return res
            ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip()
            res["content_type"] = ctype
            if ctype == "text/html" and not url.lower().split("?")[0].endswith((".html", ".htm")):
                res["error"] = "got an HTML page instead of a file (login wall or viewer page)"
                return res
            name = _filename(r.url, r.headers)
            path = out_dir / name
            size = 0
            with path.open("wb") as fh:
                for chunk in r.iter_content(1 << 16):
                    size += len(chunk)
                    if size > max_mb * 1024 * 1024:
                        fh.close()
                        path.unlink(missing_ok=True)
                        res["error"] = f"larger than {max_mb} MB"
                        return res
                    fh.write(chunk)
            res.update(path=path, name=name, bytes=size)
    except Exception as exc:
        res["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return res
