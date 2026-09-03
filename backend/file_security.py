"""File upload security verification module for Recraftr.

Enforces extension whitelisting, MIME validation, magic byte signature checks,
executable detection, zip bomb detection, path traversal prevention, file quarantine,
ClamAV malware scanning, and filename sanitization.
"""

import os
import re
import uuid
import zipfile
import io
import tempfile
import subprocess
import shutil
from pathlib import Path
from contextlib import contextmanager
from typing import Tuple

MAX_UPLOAD_SIZE_BYTES = int(os.environ.get("MAX_UPLOAD_SIZE_BYTES", 5 * 1024 * 1024))  # 5 MB default
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/x-plain",
    "application/octet-stream",  # Frequently sent by browsers; validated via magic bytes
}

# Known executable magic signatures to explicitly reject
EXECUTABLE_MAGIC_BYTES = [
    (b"MZ", "Windows Executable/DLL"),
    (b"\x7fELF", "Linux ELF Executable"),
    (b"\xca\xfe\xba\xbe", "Java Class / Mach-O Binary"),
    (b"\xfe\xed\xfa\xce", "Mach-O Binary"),
    (b"\xfe\xed\xfa\xcf", "Mach-O 64-bit Binary"),
    (b"Rar!\x1a\x07", "RAR Archive"),
    (b"7z\xbc\xaf\x27\x1c", "7-Zip Archive"),
]

DANGEROUS_ZIP_EXTENSIONS = {
    ".exe", ".dll", ".sh", ".bat", ".vbs", ".js", ".py", ".elf",
    ".jar", ".so", ".cmd", ".ps1", ".scr", ".com", ".htm", ".html", ".php"
}

# Max expanded size for DOCX zip contents (10 MB limit to prevent zip bombs)
MAX_DOCX_UNCOMPRESSED_SIZE = 10 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 100.0  # Max 100:1 ratio

QUARANTINE_DIR = Path(tempfile.gettempdir()) / "recraftr_quarantine"


class FileValidationError(ValueError):
    """Raised when an uploaded file fails security validation checks."""
    pass


def init_quarantine_dir() -> Path:
    """Ensure quarantine directory exists with 0o700 restricted permissions."""
    try:
        QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(QUARANTINE_DIR, 0o700)
    except Exception:
        pass
    return QUARANTINE_DIR


@contextmanager
def quarantine_file(file_bytes: bytes, filename: str = "upload.tmp"):
    """Context manager that writes file bytes to an isolated 0o600 non-executable quarantine path,
    yields the path, and guarantees immediate unlink/cleanup upon exit.
    """
    init_quarantine_dir()
    unique_id = uuid.uuid4().hex
    safe_name = sanitize_filename(filename)
    tmp_path = QUARANTINE_DIR / f"{unique_id}_{safe_name}"
    
    try:
        with open(tmp_path, "wb") as f:
            f.write(file_bytes)
        # Enforce read/write only, no execution
        os.chmod(tmp_path, 0o600)
        yield tmp_path
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def scan_with_clamav(file_path: Path) -> Tuple[bool, str]:
    """Scan quarantine file with clamscan/clamdscan CLI if installed.
    Returns (is_clean: bool, detail: str).
    """
    clam_binary = shutil.which("clamdscan") or shutil.which("clamscan")
    if not clam_binary:
        return True, "ClamAV scanner not installed on host; standard quarantine heuristics applied."
    
    try:
        res = subprocess.run(
            [clam_binary, "--no-summary", str(file_path)],
            capture_output=True,
            text=True,
            timeout=15.0,
        )
        if res.returncode == 0:
            return True, "Clean scan"
        elif res.returncode == 1:
            return False, f"Malware detected by ClamAV: {res.stdout.strip() or 'Infected file'}"
        else:
            return True, f"ClamAV scan warning (code {res.returncode}): {res.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "ClamAV malware scan timed out"
    except Exception as e:
        return True, f"ClamAV scan execution error: {e}"


def sanitize_filename(original_filename: str) -> str:
    """Sanitize original filename to prevent path traversal and header injection."""
    if not original_filename:
        return "resume.txt"
    
    # Strip any path component (e.g. ../../../etc/passwd -> passwd)
    filename = os.path.basename(original_filename)
    filename = filename.replace("\\", "/").split("/")[-1]
    
    # Strip null bytes and control chars
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
    
    # Replace non-printable / unsafe chars with underscore, allowing alphanumeric, dots, hyphens, underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_.\-]', '_', filename).strip(". ")
    
    if not sanitized:
        return "resume.txt"
    return sanitized[:150]


def get_file_extension(filename: str) -> str:
    """Extract lowercased extension without leading dot."""
    sanitized = sanitize_filename(filename)
    parts = sanitized.rsplit(".", 1)
    if len(parts) == 2:
        return parts[1].lower()
    return ""


def validate_file_signature(ext: str, file_bytes: bytes) -> Tuple[bool, str]:
    """Validate magic bytes signature matching the claimed file extension."""
    if not file_bytes:
        return False, "File is empty (0 bytes)"

    # Check against known executable signatures first
    for magic, desc in EXECUTABLE_MAGIC_BYTES:
        if file_bytes.startswith(magic):
            return False, f"File rejected: Contains executable or restricted archive signature ({desc})"

    if ext == "pdf":
        # PDF must start with %PDF- header magic
        if not file_bytes.startswith(b"%PDF-"):
            return False, "Invalid PDF signature: File does not start with %PDF- magic bytes"
        return True, "Valid PDF"

    elif ext == "docx":
        # DOCX files are OpenXML ZIP packages starting with PK\x03\x04
        if not file_bytes.startswith(b"PK\x03\x04"):
            return False, "Invalid DOCX signature: File does not start with PK zip magic bytes"
        
        # Deep inspection of DOCX zip container
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as zf:
                namelist = zf.namelist()
                
                # DOCX package must contain word/document.xml or [Content_Types].xml
                if not any(name in namelist for name in ("word/document.xml", "[Content_Types].xml")):
                    return False, "Invalid DOCX package: Missing Word document XML structures"
                
                total_uncompressed = 0
                total_compressed = len(file_bytes)
                
                for info in zf.infolist():
                    # Reject nested executables inside DOCX package
                    file_ext = os.path.splitext(info.filename)[1].lower()
                    if file_ext in DANGEROUS_ZIP_EXTENSIONS:
                        return False, f"Invalid DOCX package: Contains forbidden executable/script file '{info.filename}'"
                    
                    total_uncompressed += info.file_size
                
                if total_uncompressed > MAX_DOCX_UNCOMPRESSED_SIZE:
                    return False, "Invalid DOCX package: Excessively large decompressed size (zip bomb protection)"
                
                if total_compressed > 0 and (total_uncompressed / total_compressed) > MAX_DOCX_COMPRESSION_RATIO:
                    return False, "Invalid DOCX package: Suspicious compression ratio detected (zip bomb protection)"

        except zipfile.BadZipFile:
            return False, "Malformed document: File claims to be DOCX but is not a valid zip archive"
        except Exception as e:
            return False, f"Malformed document package: {str(e)}"
        
        return True, "Valid DOCX"

    elif ext == "txt":
        # Text file validation: ensure no binary null bytes or non-text control characters
        if b"\x00" in file_bytes:
            return False, "Invalid TXT file: Contains binary null bytes"
        try:
            file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                file_bytes.decode("latin-1")
            except Exception:
                return False, "Invalid TXT file: File is not valid plain text"
        return True, "Valid TXT"

    return False, f"Unsupported file extension '.{ext}'"


def validate_upload_file(original_filename: str, mime_type: str, file_bytes: bytes) -> str:
    """Perform full security validation check on an uploaded file.
    
    Returns sanitized filename if valid, or raises FileValidationError.
    """
    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        max_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise FileValidationError(f"File size exceeds maximum limit of {max_mb}MB")
    
    if len(file_bytes) == 0:
        raise FileValidationError("Uploaded file is empty (0 bytes)")

    sanitized_name = sanitize_filename(original_filename)
    ext = get_file_extension(sanitized_name)

    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(f"Forbidden file extension '.{ext}'. Only PDF, DOCX, and TXT files are allowed.")

    if mime_type and mime_type.lower() not in ALLOWED_MIME_TYPES:
        raise FileValidationError(f"Unsupported MIME type '{mime_type}'. Only PDF, DOCX, and TXT files are allowed.")

    is_valid_sig, sig_msg = validate_file_signature(ext, file_bytes)
    if not is_valid_sig:
        raise FileValidationError(sig_msg)

    # Perform quarantine & ClamAV malware scan
    with quarantine_file(file_bytes, sanitized_name) as q_path:
        is_clean, scan_msg = scan_with_clamav(q_path)
        if not is_clean:
            raise FileValidationError(f"Security Alert: Upload rejected. {scan_msg}")

    return sanitized_name
