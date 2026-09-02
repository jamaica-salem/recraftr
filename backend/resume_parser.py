"""Extract plain text from PDF or DOCX resumes."""
import io
import pdfplumber
from docx import Document


def parse_pdf(file_bytes: bytes) -> str:
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            text_parts.append(t)
    return "\n".join(text_parts).strip()


def parse_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    lines = [p.text for p in doc.paragraphs if p.text.strip()]
    # Also grab tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    lines.append(cell.text.strip())
    return "\n".join(lines).strip()


def parse_resume(filename: str, file_bytes: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return parse_pdf(file_bytes)
    if name.endswith(".docx"):
        return parse_docx(file_bytes)
    # Fallback: try both, then raw decode
    try:
        return parse_pdf(file_bytes)
    except Exception:
        pass
    try:
        return parse_docx(file_bytes)
    except Exception:
        pass
    return file_bytes.decode("utf-8", errors="ignore")
