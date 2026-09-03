"""Security test suite for Recraftr file upload guardrails."""

import os
import pytest
import io
import zipfile
import asyncio
from file_security import (
    validate_upload_file,
    sanitize_filename,
    quarantine_file,
    FileValidationError,
)
from resume_parser import parse_resume, parse_resume_async


def test_filename_sanitization():
    # Path traversal attempts
    assert sanitize_filename("../../../etc/passwd.pdf") == "passwd.pdf"
    assert sanitize_filename("..\\..\\windows\\system32\\cmd.exe") == "cmd.exe"
    assert sanitize_filename("safe_resume_2026.pdf") == "safe_resume_2026.pdf"
    assert sanitize_filename("\x00dangerous.docx") == "dangerous.docx"


def test_extension_whitelisting():
    # Allowed formats
    valid_pdf_bytes = b"%PDF-1.4 sample PDF content with sufficient length for testing..."
    assert validate_upload_file("resume.pdf", "application/pdf", valid_pdf_bytes) == "resume.pdf"
    
    valid_txt_bytes = b"This is a sample plain text resume containing work history and skills."
    assert validate_upload_file("my_resume.txt", "text/plain", valid_txt_bytes) == "my_resume.txt"

    # Forbidden formats
    with pytest.raises(FileValidationError) as exc:
        validate_upload_file("malicious.exe", "application/x-msdownload", b"MZexecutable")
    assert "Forbidden file extension" in str(exc.value)

    with pytest.raises(FileValidationError) as exc:
        validate_upload_file("script.py", "text/x-python", b"import os; os.system('ls')")
    assert "Forbidden file extension" in str(exc.value)

    with pytest.raises(FileValidationError) as exc:
        validate_upload_file("archive.zip", "application/zip", b"PK\x03\x04file")
    assert "Forbidden file extension" in str(exc.value)


def test_magic_bytes_spoofing_detection():
    # File named .pdf but contains Windows PE executable magic bytes (MZ)
    fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff"
    with pytest.raises(FileValidationError) as exc:
        validate_upload_file("fake.pdf", "application/pdf", fake_pdf)
    assert "executable" in str(exc.value).lower()

    # File named .pdf but missing %PDF- header magic
    invalid_pdf = b"NOT_A_PDF_FILE_HEADER_DATA"
    with pytest.raises(FileValidationError) as exc:
        validate_upload_file("bad.pdf", "application/pdf", invalid_pdf)
    assert "magic bytes" in str(exc.value).lower()


def test_file_size_limit():
    # 6 MB byte stream (exceeds 5MB limit)
    large_bytes = b"%PDF-1.4" + (b"A" * (6 * 1024 * 1024))
    with pytest.raises(FileValidationError) as exc:
        validate_upload_file("large.pdf", "application/pdf", large_bytes)
    assert "maximum limit" in str(exc.value)


def test_docx_security_validation():
    # Build a valid docx zip container
    docx_buf = io.BytesIO()
    with zipfile.ZipFile(docx_buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", "<w:document><w:body><w:p><w:r><w:t>John Doe Resume</w:t></w:r></w:p></w:body></w:document>")
    valid_docx_bytes = docx_buf.getvalue()

    assert validate_upload_file("resume.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", valid_docx_bytes) == "resume.docx"

    # Malformed docx (claims to be docx but invalid zip)
    with pytest.raises(FileValidationError) as exc:
        validate_upload_file("corrupt.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"PK\x03\x04corrupted_zip")
    assert "Malformed document" in str(exc.value)

    # DOCX containing dangerous nested executable (.exe)
    malicious_docx_buf = io.BytesIO()
    with zipfile.ZipFile(malicious_docx_buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", "<w:document></w:document>")
        zf.writestr("word/payload.exe", b"MZbinarypayload")
    
    with pytest.raises(FileValidationError) as exc:
        validate_upload_file("trojan.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", malicious_docx_buf.getvalue())
    assert "executable" in str(exc.value).lower()


def test_quarantine_file_permissions_and_cleanup():
    sample_data = b"%PDF-1.4 test quarantine file bytes"
    file_path = None
    with quarantine_file(sample_data, "test.pdf") as q_path:
        file_path = q_path
        assert q_path.exists()
        # Verify 0o600 permissions (read/write only, non-executable)
        st_mode = os.stat(q_path).st_mode
        assert (st_mode & 0o111) == 0  # No execution permissions for user, group, or others
    
    # Verify file unlinked automatically upon exit
    assert not file_path.exists()


@pytest.mark.anyio
async def test_process_isolated_async_parser():
    txt_data = b"Jane Doe - Staff Software Engineer with 8 years of distributed systems experience."
    res = await parse_resume_async("resume.txt", txt_data, timeout_seconds=5.0)
    assert "Jane Doe" in res
