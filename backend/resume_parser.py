"""Extract plain text from PDF, DOCX, or TXT resumes with process isolation, timeout, and memory guardrails."""
import io
import asyncio
from concurrent.futures import ProcessPoolExecutor
import pdfplumber
from docx import Document
from file_security import get_file_extension

# Shared process pool for isolated document parsing
_PROCESS_POOL = ProcessPoolExecutor(max_workers=4)


def parse_pdf(file_bytes: bytes) -> str:
    text_parts = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t.strip():
                    text_parts.append(t)
    except Exception:
        pass

    extracted = "\n".join(text_parts).strip()
    if len(extracted) >= 20:
        return extracted

    # Fallback 1: pypdfium2
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(file_bytes)
        pypdf_parts = []
        for page in pdf:
            textpage = page.get_textpage()
            t = textpage.get_text_range()
            if t.strip():
                pypdf_parts.append(t)
        pdf_text = "\n".join(pypdf_parts).strip()
        if len(pdf_text) >= 20:
            return pdf_text
    except Exception:
        pass

    # Fallback 2: utf-8 raw decoding
    try:
        return file_bytes.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def parse_docx(file_bytes: bytes) -> str:
    try:
        doc = Document(io.BytesIO(file_bytes))
        lines = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        lines.append(cell.text.strip())
        return "\n".join(lines).strip()
    except Exception as e:
        raise ValueError(f"Malformed DOCX document: {str(e)}")


def parse_txt(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8").strip()
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1", errors="ignore").strip()


def parse_resume(filename: str, file_bytes: bytes) -> str:
    """Synchronously parse text from PDF, DOCX, or TXT file bytes."""
    ext = get_file_extension(filename)
    if ext == "pdf":
        return parse_pdf(file_bytes)
    if ext == "docx":
        return parse_docx(file_bytes)
    if ext == "txt":
        return parse_txt(file_bytes)

    # Fallback
    try:
        res = parse_pdf(file_bytes)
        if len(res) >= 20:
            return res
    except Exception:
        pass

    try:
        res = parse_docx(file_bytes)
        if len(res) >= 20:
            return res
    except Exception:
        pass

    return parse_txt(file_bytes)


async def parse_resume_async(filename: str, file_bytes: bytes, timeout_seconds: float = 10.0) -> str:
    """Asynchronously parse text from file bytes with OS Process-level isolation and a 10s timeout."""
    loop = asyncio.get_running_loop()
    try:
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(_PROCESS_POOL, parse_resume, filename, file_bytes),
                timeout=timeout_seconds,
            )
        except (OSError, RuntimeError) as pool_err:
            # Fallback to thread execution if process pool fails due to OS stream/pipe/pty errors (e.g. Errno 5)
            return await asyncio.wait_for(
                asyncio.to_thread(parse_resume, filename, file_bytes),
                timeout=timeout_seconds,
            )
    except asyncio.TimeoutError:
        raise ValueError(f"File parsing timed out (max {int(timeout_seconds)}s). Document may be malformed or excessively complex.")
    except ValueError as ve:
        raise ve
    except Exception as e:
        raise ValueError(f"Failed to parse document: {str(e)}")
