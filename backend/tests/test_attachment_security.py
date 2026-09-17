import io
import zipfile

import pytest

from app.attachment_security import detect_mime, safe_filename


def test_safe_filename_removes_paths_and_unsafe_characters():
    assert safe_filename("../../Quarterly report (final).pdf") == "Quarterly report (final).pdf"
    assert safe_filename("team<>notes.md") == "team_notes.md"


def test_safe_filename_rejects_active_content_extensions():
    with pytest.raises(ValueError, match="not allowed"):
        safe_filename("payload.svg")
    with pytest.raises(ValueError, match="not allowed"):
        safe_filename("index.html")


def test_detect_mime_uses_content_not_claimed_type():
    assert detect_mime(b"%PDF-1.7\nexample", "report.pdf") == "application/pdf"
    with pytest.raises(ValueError, match="does not match"):
        detect_mime(b"%PDF-1.7\nexample", "report.png")


def test_detect_mime_rejects_html_even_when_named_text():
    with pytest.raises(ValueError, match="Unsupported"):
        detect_mime(b"<!doctype html><script>alert(1)</script>", "notes.txt")


def test_detect_mime_validates_json_content():
    assert detect_mime(b'{"ok": true}', "data.json") == "text/plain"
    with pytest.raises(ValueError, match="Invalid JSON"):
        detect_mime(b"not-json", "data.json")


def test_detects_office_open_xml_by_archive_structure():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")

    assert (
        detect_mime(stream.getvalue(), "document.docx")
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
