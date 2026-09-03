"""Extract plain text from PDF or DOCX resumes."""
import io
import pdfplumber
from docx import Document


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
    return file_bytes.decode("utf-8", errors="ignore").strip()


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
    return file_bytes.decode("utf-8", errors="ignore").strip()

