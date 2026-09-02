"""Generate styled ATS-friendly PDFs for resume and cover letter."""
import io
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT

SECTION_HEADERS = {"SUMMARY", "SKILLS", "EXPERIENCE", "EDUCATION", "PROJECTS", "CERTIFICATIONS", "AWARDS"}


def _resume_styles():
    ss = getSampleStyleSheet()
    return (
        ParagraphStyle("Name", parent=ss["Title"], fontName="Helvetica-Bold",
                       fontSize=20, leading=24, textColor=HexColor("#0A0A0A"), spaceAfter=6, alignment=TA_LEFT),
        ParagraphStyle("Contact", parent=ss["Normal"], fontName="Helvetica",
                       fontSize=10, leading=13, textColor=HexColor("#404040"), spaceAfter=12),
        ParagraphStyle("Section", parent=ss["Heading2"], fontName="Helvetica-Bold",
                       fontSize=12, leading=15, textColor=HexColor("#0A0A0A"), spaceBefore=10, spaceAfter=4),
        ParagraphStyle("Body", parent=ss["Normal"], fontName="Helvetica",
                       fontSize=10.5, leading=14, textColor=HexColor("#171717"), spaceAfter=2),
    )


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_pdf(resume_text: str) -> bytes:
    name_style, contact_style, section_style, body_style = _resume_styles()
    bullet_style = ParagraphStyle("Bullet", parent=body_style, leftIndent=14, bulletIndent=2, spaceAfter=1)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER,
                            leftMargin=0.7 * inch, rightMargin=0.7 * inch,
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                            title="Resume")
    story = []
    lines = [ln.rstrip() for ln in (resume_text or "").splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)

    name_line = ""
    contact_lines = []
    body_start = 0
    for i, ln in enumerate(lines[:5]):
        s = ln.strip()
        if not s:
            continue
        if not name_line and s.upper() not in SECTION_HEADERS:
            name_line = s; body_start = i + 1
        elif s.upper() not in SECTION_HEADERS and len(contact_lines) < 2:
            contact_lines.append(s); body_start = i + 1
        else:
            break

    if name_line:
        story.append(Paragraph(_escape(name_line), name_style))
    if contact_lines:
        story.append(Paragraph(_escape(" | ".join(contact_lines)), contact_style))

    for ln in lines[body_start:]:
        s = ln.strip()
        if not s:
            story.append(Spacer(1, 4)); continue
        upper = s.upper().rstrip(":")
        if upper in SECTION_HEADERS:
            story.append(Paragraph(_escape(upper), section_style))
        elif s.startswith(("-", "•", "*")):
            story.append(Paragraph(_escape(s.lstrip("-•* ").strip()), bullet_style, bulletText="•"))
        else:
            story.append(Paragraph(_escape(s), body_style))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def build_cover_letter_pdf(text: str, candidate_name: str = "", job_title: str = "") -> bytes:
    ss = getSampleStyleSheet()
    name_style = ParagraphStyle("CLName", parent=ss["Title"], fontName="Helvetica-Bold",
                                fontSize=18, leading=22, textColor=HexColor("#0A0A0A"),
                                spaceAfter=4, alignment=TA_LEFT)
    subtitle_style = ParagraphStyle("CLSub", parent=ss["Normal"], fontName="Helvetica",
                                    fontSize=10.5, leading=14, textColor=HexColor("#525252"), spaceAfter=18)
    body_style = ParagraphStyle("CLBody", parent=ss["Normal"], fontName="Helvetica",
                                fontSize=11, leading=16, textColor=HexColor("#171717"), spaceAfter=10)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER,
                            leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                            topMargin=0.8 * inch, bottomMargin=0.8 * inch,
                            title="Cover Letter")
    story = []
    if candidate_name.strip():
        story.append(Paragraph(_escape(candidate_name.strip()), name_style))
    if job_title.strip():
        story.append(Paragraph(_escape(f"Cover letter — {job_title.strip()}"), subtitle_style))
    else:
        story.append(Spacer(1, 8))

    # Split into paragraphs on blank lines; preserve intra-paragraph text.
    raw = (text or "").strip()
    paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
    for p in paragraphs:
        content = " ".join(seg.strip() for seg in p.splitlines() if seg.strip())
        if content:
            story.append(Paragraph(_escape(content), body_style))
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
