"""Generate styled ATS-friendly PDFs and HTML exports for resume and cover letter."""
import io
from typing import Optional, Dict, Any
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER

SECTION_HEADERS = {"SUMMARY", "SKILLS", "EXPERIENCE", "EDUCATION", "PROJECTS", "CERTIFICATIONS", "AWARDS"}

PRESET_CONFIGS = {
    "classic": {
        "primary_color": "#0A0A0A",
        "secondary_color": "#404040",
        "body_color": "#171717",
        "font_family": "Helvetica",
        "header_align": "left",
        "font_size_body": 10.5,
        "leading_body": 14,
        "margin": 0.7,
        "has_divider": False,
    },
    "modern": {
        "primary_color": "#1E3A8A", # Deep Navy
        "secondary_color": "#475569",
        "body_color": "#0F172A",
        "font_family": "Helvetica",
        "header_align": "left",
        "font_size_body": 10.0,
        "leading_body": 13.5,
        "margin": 0.6,
        "has_divider": True,
    },
    "compact": {
        "primary_color": "#111827",
        "secondary_color": "#374151",
        "body_color": "#1F2937",
        "font_family": "Helvetica",
        "header_align": "left",
        "font_size_body": 9.2,
        "leading_body": 12.0,
        "margin": 0.45,
        "has_divider": False,
    },
    "elegant": {
        "primary_color": "#1E293B",
        "secondary_color": "#475569",
        "body_color": "#1E293B",
        "font_family": "Times-Roman",
        "header_align": "center",
        "font_size_body": 10.5,
        "leading_body": 14.5,
        "margin": 0.75,
        "has_divider": True,
    },
}


def _resolve_config(template_name: Optional[str] = "classic", custom_styles: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    t_name = (template_name or "classic").lower()
    base = dict(PRESET_CONFIGS.get(t_name, PRESET_CONFIGS["classic"]))
    if custom_styles and isinstance(custom_styles, dict):
        if custom_styles.get("primary_color"):
            base["primary_color"] = custom_styles["primary_color"]
        if custom_styles.get("font_family"):
            fam = custom_styles["font_family"]
            if fam in ("Helvetica", "Times-Roman"):
                base["font_family"] = fam
        if custom_styles.get("header_align"):
            align = custom_styles["header_align"].lower()
            if align in ("left", "center"):
                base["header_align"] = align
    return base


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_pdf(
    resume_text: str,
    template: Optional[str] = "classic",
    custom_styles: Optional[Dict[str, Any]] = None,
) -> bytes:
    cfg = _resolve_config(template, custom_styles)
    font_base = cfg["font_family"]
    if font_base == "Times-Roman":
        font_bold = "Times-Bold"
    elif font_base == "Courier":
        font_bold = "Courier-Bold"
    else:
        font_bold = "Helvetica-Bold"

    align_code = TA_CENTER if cfg["header_align"] == "center" else TA_LEFT
    p_color = HexColor(cfg["primary_color"])
    s_color = HexColor(cfg["secondary_color"])
    b_color = HexColor(cfg["body_color"])

    ss = getSampleStyleSheet()
    name_style = ParagraphStyle(
        "CustomName", parent=ss["Title"], fontName=font_bold,
        fontSize=20 if cfg["font_size_body"] > 9.5 else 18,
        leading=24, textColor=p_color, spaceAfter=4, alignment=align_code
    )
    contact_style = ParagraphStyle(
        "CustomContact", parent=ss["Normal"], fontName=font_base,
        fontSize=9.5, leading=13, textColor=s_color, spaceAfter=10, alignment=align_code
    )
    section_style = ParagraphStyle(
        "CustomSection", parent=ss["Heading2"], fontName=font_bold,
        fontSize=12 if cfg["font_size_body"] > 9.5 else 11,
        leading=15, textColor=p_color, spaceBefore=8, spaceAfter=4
    )
    body_style = ParagraphStyle(
        "CustomBody", parent=ss["Normal"], fontName=font_base,
        fontSize=cfg["font_size_body"], leading=cfg["leading_body"], textColor=b_color, spaceAfter=2
    )
    bullet_style = ParagraphStyle(
        "CustomBullet", parent=body_style, leftIndent=14, bulletIndent=2, spaceAfter=1
    )

    buf = io.BytesIO()
    margin_pts = cfg["margin"] * inch
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=margin_pts, rightMargin=margin_pts,
        topMargin=margin_pts, bottomMargin=margin_pts,
        title="Resume"
    )
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
            name_line = s
            body_start = i + 1
        elif s.upper() not in SECTION_HEADERS and len(contact_lines) < 2:
            contact_lines.append(s)
            body_start = i + 1
        else:
            break

    if name_line:
        story.append(Paragraph(_escape(name_line), name_style))
    if contact_lines:
        story.append(Paragraph(_escape(" | ".join(contact_lines)), contact_style))

    if cfg["has_divider"]:
        story.append(HRFlowable(width="100%", thickness=1.5, color=p_color, spaceBefore=2, spaceAfter=8))
    else:
        story.append(Spacer(1, 4))

    for ln in lines[body_start:]:
        s = ln.strip()
        if not s:
            story.append(Spacer(1, 3))
            continue
        upper = s.upper().rstrip(":")
        if upper in SECTION_HEADERS:
            story.append(Paragraph(_escape(upper), section_style))
            if cfg["has_divider"]:
                story.append(HRFlowable(width="100%", thickness=0.75, color=p_color, spaceBefore=1, spaceAfter=4))
        elif s.startswith(("-", "•", "*")):
            story.append(Paragraph(_escape(s.lstrip("-•* ").strip()), bullet_style, bulletText="-"))
        else:
            story.append(Paragraph(_escape(s), body_style))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def build_cover_letter_pdf(
    text: str,
    candidate_name: str = "",
    job_title: str = "",
    template: Optional[str] = "classic",
    custom_styles: Optional[Dict[str, Any]] = None,
) -> bytes:
    cfg = _resolve_config(template, custom_styles)
    font_base = cfg["font_family"]
    if font_base == "Times-Roman":
        font_bold = "Times-Bold"
    elif font_base == "Courier":
        font_bold = "Courier-Bold"
    else:
        font_bold = "Helvetica-Bold"

    align_code = TA_CENTER if cfg["header_align"] == "center" else TA_LEFT
    p_color = HexColor(cfg["primary_color"])
    s_color = HexColor(cfg["secondary_color"])
    b_color = HexColor(cfg["body_color"])

    ss = getSampleStyleSheet()
    name_style = ParagraphStyle(
        "CLName", parent=ss["Title"], fontName=font_bold,
        fontSize=18, leading=22, textColor=p_color, spaceAfter=4, alignment=align_code
    )
    subtitle_style = ParagraphStyle(
        "CLSub", parent=ss["Normal"], fontName=font_base,
        fontSize=10.5, leading=14, textColor=s_color, spaceAfter=14, alignment=align_code
    )
    body_style = ParagraphStyle(
        "CLBody", parent=ss["Normal"], fontName=font_base,
        fontSize=cfg["font_size_body"] + 0.5, leading=cfg["leading_body"] + 2, textColor=b_color, spaceAfter=10
    )

    buf = io.BytesIO()
    margin_pts = cfg["margin"] * inch
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=margin_pts, rightMargin=margin_pts,
        topMargin=margin_pts, bottomMargin=margin_pts,
        title="Cover Letter"
    )
    story = []
    if candidate_name.strip():
        story.append(Paragraph(_escape(candidate_name.strip()), name_style))
    if job_title.strip():
        story.append(Paragraph(_escape(f"Cover letter — {job_title.strip()}"), subtitle_style))
    else:
        story.append(Spacer(1, 8))

    if cfg["has_divider"]:
        story.append(HRFlowable(width="100%", thickness=1.5, color=p_color, spaceBefore=0, spaceAfter=10))

    raw = (text or "").strip()
    paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
    for p in paragraphs:
        content = " ".join(seg.strip() for seg in p.splitlines() if seg.strip())
        if content:
            story.append(Paragraph(_escape(content), body_style))
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def build_html(
    resume_text: str,
    template: Optional[str] = "classic",
    custom_styles: Optional[Dict[str, Any]] = None,
) -> str:
    """Generates styled standalone HTML resume with embedded CSS matching the chosen template."""
    cfg = _resolve_config(template, custom_styles)
    p_color = cfg["primary_color"]
    s_color = cfg["secondary_color"]
    b_color = cfg["body_color"]
    font_family = "Georgia, serif" if cfg["font_family"] == "Times-Roman" else "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    header_align = cfg["header_align"]

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
            name_line = s
            body_start = i + 1
        elif s.upper() not in SECTION_HEADERS and len(contact_lines) < 2:
            contact_lines.append(s)
            body_start = i + 1
        else:
            break

    html_parts = []
    html_parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_escape(name_line or 'Resume')}</title>
<style>
  body {{
    font-family: {font_family};
    color: {b_color};
    background-color: #ffffff;
    max-width: 800px;
    margin: 0 auto;
    padding: 40px 24px;
    line-height: 1.5;
  }}
  .header {{
    text-align: {header_align};
    margin-bottom: 20px;
    border-bottom: { '2px solid ' + p_color if cfg['has_divider'] else 'none' };
    padding-bottom: { '12px' if cfg['has_divider'] else '0' };
  }}
  .name {{
    font-size: 26px;
    font-weight: 700;
    color: {p_color};
    margin: 0 0 6px 0;
  }}
  .contact {{
    font-size: 14px;
    color: {s_color};
    margin: 0;
  }}
  .section-title {{
    font-size: 16px;
    font-weight: 700;
    color: {p_color};
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 24px;
    margin-bottom: 6px;
    border-bottom: { '1px solid ' + p_color if cfg['has_divider'] else 'none' };
    padding-bottom: { '4px' if cfg['has_divider'] else '0' };
  }}
  ul {{
    margin: 4px 0 12px 20px;
    padding: 0;
  }}
  li {{
    margin-bottom: 4px;
    font-size: {cfg['font_size_body']}pt;
  }}
  p {{
    font-size: {cfg['font_size_body']}pt;
    margin: 4px 0;
  }}
  @media print {{
    body {{ padding: 0; max-width: 100%; }}
  }}
</style>
</head>
<body>
""")

    if name_line or contact_lines:
        html_parts.append('<div class="header">')
        if name_line:
            html_parts.append(f'  <h1 class="name">{_escape(name_line)}</h1>')
        if contact_lines:
            html_parts.append(f'  <p class="contact">{_escape(" | ".join(contact_lines))}</p>')
        html_parts.append('</div>')

    in_list = False
    for ln in lines[body_start:]:
        s = ln.strip()
        if not s:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            continue
        upper = s.upper().rstrip(":")
        if upper in SECTION_HEADERS:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<div class="section-title">{_escape(upper)}</div>')
        elif s.startswith(("-", "•", "*")):
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            html_parts.append(f'  <li>{_escape(s.lstrip("-•* ").strip())}</li>')
        else:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<p>{_escape(s)}</p>')

    if in_list:
        html_parts.append('</ul>')

    html_parts.append("</body>\n</html>")
    return "\n".join(html_parts)
