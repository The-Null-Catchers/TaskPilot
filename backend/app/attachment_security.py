import io
import json
import re
import unicodedata
import zipfile
from pathlib import Path

DANGEROUS_EXTENSIONS = {
    ".app",
    ".bat",
    ".cmd",
    ".com",
    ".dll",
    ".exe",
    ".hta",
    ".html",
    ".htm",
    ".jar",
    ".js",
    ".mjs",
    ".msi",
    ".ps1",
    ".scr",
    ".sh",
    ".svg",
    ".vbs",
}

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/plain",
}

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._()\- ]+")


def safe_filename(filename: str | None) -> str:
    value = unicodedata.normalize("NFKC", Path(filename or "attachment").name).strip()
    value = value.replace("\x00", "")
    value = _SAFE_CHARS.sub("_", value)
    value = re.sub(r"\s+", " ", value).strip(" .") or "attachment"
    suffix = Path(value).suffix.lower()
    if suffix in DANGEROUS_EXTENSIONS:
        raise ValueError("File type is not allowed")
    if len(value) > 160:
        stem = Path(value).stem[: max(1, 160 - len(suffix))].rstrip(" ._") or "attachment"
        value = f"{stem}{suffix}"
    return value


def _office_mime(data: bytes) -> str | None:
    if not data.startswith(b"PK"):
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, OSError):
        return None
    if "[Content_Types].xml" not in names:
        return None
    if any(name.startswith("word/") for name in names):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if any(name.startswith("xl/") for name in names):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if any(name.startswith("ppt/") for name in names):
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return None


def _looks_like_safe_text(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    prefix = text.lstrip().lower()[:256]
    if prefix.startswith(("<html", "<!doctype html", "<svg", "<?xml")):
        return False
    if "<script" in prefix:
        return False
    controls = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")
    return controls <= max(2, len(text) // 1000)


def detect_mime(data: bytes, safe_name: str) -> str:
    if not data:
        raise ValueError("Empty files are not allowed")
    if data.startswith(b"%PDF-"):
        mime = "application/pdf"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif data.startswith((b"GIF87a", b"GIF89a")):
        mime = "image/gif"
    elif len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        mime = _office_mime(data) or ("text/plain" if _looks_like_safe_text(data) else "")
    if mime not in ALLOWED_MIME_TYPES:
        raise ValueError("Unsupported or unsafe file content")

    suffix = Path(safe_name).suffix.lower()
    expected = {
        ".pdf": {"application/pdf"},
        ".png": {"image/png"},
        ".jpg": {"image/jpeg"},
        ".jpeg": {"image/jpeg"},
        ".gif": {"image/gif"},
        ".webp": {"image/webp"},
        ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
        ".txt": {"text/plain"},
        ".md": {"text/plain"},
        ".csv": {"text/plain"},
        ".json": {"text/plain"},
    }
    if suffix and suffix in expected and mime not in expected[suffix]:
        raise ValueError("File extension does not match file content")
    if suffix and suffix not in expected:
        raise ValueError("File extension is not allowed")
    if not suffix and mime != "text/plain":
        raise ValueError("A recognized file extension is required")
    if suffix == ".json" and mime == "text/plain":
        try:
            json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON attachment") from exc
    return mime
