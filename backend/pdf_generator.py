"""Generate styled ATS-friendly PDFs and HTML exports for resume and cover letter."""
import io
import re
from typing import Optional, Dict, Any
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

SECTION_HEADERS = {"SUMMARY", "SKILLS", "EXPERIENCE", "EDUCATION", "PROJECTS", "CERTIFICATIONS", "AWARDS"}

PRESET_CONFIGS = {
    "jamaica": {
        "primary_color": "#0A0A0A",
        "secondary_color": "#171717",
        "body_color": "#171717",
        "font_family": "Times-Roman",
        "header_align": "center",
        "font_size_name": 14.5,
        "font_size_body": 9.5,
        "leading_body": 13.0,
        "margin": 0.5,
        "has_divider": True,
        "header_border_double": True,
    },
    "classic": {
        "primary_color": "#0A0A0A",
        "secondary_color": "#404040",
        "body_color": "#171717",
        "font_family": "Helvetica",
        "header_align": "left",
        "font_size_name": 18.0,
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
        "font_size_name": 18.0,
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
        "font_size_name": 16.0,
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
        "font_size_name": 16.0,
        "font_size_body": 10.5,
        "leading_body": 14.5,
        "margin": 0.75,
        "has_divider": True,
    },
}


def _resolve_config(template_name: Optional[str] = "jamaica", custom_styles: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    t_name = (template_name or "jamaica").lower()
    base = dict(PRESET_CONFIGS.get(t_name, PRESET_CONFIGS["jamaica"]))
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
    if not text:
        return ""
    # Strip dangerous HTML tags & attributes before entity escaping
    clean = re.sub(r'<\s*(script|iframe|object|embed|style|meta|link)[^>]*>', '', str(text), flags=re.IGNORECASE)
    clean = re.sub(r'on\w+\s*=', 'on_disabled=', clean, flags=re.IGNORECASE)
    clean = re.sub(r'javascript\s*:', 'blocked:', clean, flags=re.IGNORECASE)
    return clean.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")


def linkify_contact(str_val: str) -> str:
    escaped = _escape(str_val)
    def repl(m):
        match = m.group(0)
        if "javascript:" in match.lower() or "data:" in match.lower():
            return match
        href = match if match.startswith("http") else f"https://{match}"
        return f'<a href="{href}" target="_blank" rel="noopener noreferrer" style="color:#003399;text-decoration:underline;">{match}</a>'
    return re.sub(r'(?:https?://)?(?:www\.|github\.com/|linkedin\.com/in/)[^\s|]+', repl, escaped)


def build_pdf(
    resume_text: str,
    template: Optional[str] = "jamaica",
    custom_styles: Optional[Dict[str, Any]] = None,
) -> bytes:
    cfg = _resolve_config(template, custom_styles)
    font_base = cfg["font_family"]
    if font_base == "Times-Roman":
        font_bold = "Times-Bold"
        font_italic = "Times-Italic"
    elif font_base == "Courier":
        font_bold = "Courier-Bold"
        font_italic = "Courier-Oblique"
    else:
        font_bold = "Helvetica-Bold"
        font_italic = "Helvetica-Oblique"

    align_code = TA_CENTER if cfg["header_align"] == "center" else TA_LEFT
    p_color = HexColor(cfg["primary_color"])
    s_color = HexColor(cfg["secondary_color"])
    b_color = HexColor(cfg["body_color"])

    name_sz = cfg.get("font_size_name", 15.0 if font_base == "Times-Roman" else 18.0)
    ss = getSampleStyleSheet()
    name_style = ParagraphStyle(
        "CustomName", parent=ss["Title"], fontName=font_bold,
        fontSize=name_sz, leading=name_sz + 3.5, textColor=p_color, spaceAfter=3, alignment=align_code
    )
    contact_style = ParagraphStyle(
        "CustomContact", parent=ss["Normal"], fontName=font_base,
        fontSize=9.5, leading=12.5, textColor=s_color, spaceAfter=1.5, alignment=align_code
    )
    section_style = ParagraphStyle(
        "CustomSection", parent=ss["Heading2"], fontName=font_bold,
        fontSize=12 if font_base == "Times-Roman" else 11.5,
        leading=15, textColor=p_color, spaceBefore=7, spaceAfter=2
    )
    body_style = ParagraphStyle(
        "CustomBody", parent=ss["Normal"], fontName=font_base,
        fontSize=cfg["font_size_body"], leading=cfg["leading_body"], textColor=b_color, spaceAfter=2
    )
    bold_body_style = ParagraphStyle("CustomBoldBody", parent=body_style, fontName=font_bold)
    italic_body_style = ParagraphStyle("CustomItalicBody", parent=body_style, fontName=font_italic)
    right_body_style = ParagraphStyle("CustomRightBody", parent=body_style, alignment=TA_RIGHT)
    right_italic_style = ParagraphStyle("CustomRightItalic", parent=italic_body_style, alignment=TA_RIGHT)
    bullet_style = ParagraphStyle(
        "CustomBullet", parent=body_style, leftIndent=14, bulletIndent=2, spaceAfter=1.5
    )

    buf = io.BytesIO()
    margin_pts = cfg["margin"] * inch
    usable_width = 8.5 * inch - 2 * margin_pts

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
        elif s.upper() not in SECTION_HEADERS and len(contact_lines) < 3:
            contact_lines.append(s)
            body_start = i + 1
        else:
            break

    is_double_header = cfg.get("header_border_double") or (cfg["header_align"] == "center" and font_base == "Times-Roman")

    if is_double_header:
        if name_line:
            story.append(Paragraph(_escape(name_line), name_style))
        story.append(HRFlowable(width="100%", thickness=0.8, color=p_color, spaceBefore=2, spaceAfter=3))
        for c_line in contact_lines:
            story.append(Paragraph(_escape(c_line), contact_style))
        story.append(HRFlowable(width="100%", thickness=0.8, color=p_color, spaceBefore=3, spaceAfter=8))
    else:
        if name_line:
            story.append(Paragraph(_escape(name_line), name_style))
        for c_line in contact_lines:
            story.append(Paragraph(_escape(c_line), contact_style))
        if cfg["has_divider"]:
            story.append(HRFlowable(width="100%", thickness=1.2, color=p_color, spaceBefore=2, spaceAfter=8))
        else:
            story.append(Spacer(1, 4))

    current_section = ""

    for ln in lines[body_start:]:
        s = ln.strip()
        if not s:
            story.append(Spacer(1, 2))
            continue
        upper = s.upper().rstrip(":")
        if upper in SECTION_HEADERS:
            current_section = upper
            sec_title = upper.title() if font_base == "Times-Roman" else upper
            story.append(Paragraph(_escape(sec_title), section_style))
            if cfg["has_divider"] or is_double_header:
                story.append(HRFlowable(width="100%", thickness=1.0, color=p_color, spaceBefore=1, spaceAfter=4))
            continue

        is_bullet = s.startswith(("-", "•", "*"))
        bullet_text = s.lstrip("-•* ").strip() if is_bullet else s

        # Check for pipe delimited line (two column entries)
        if "|" in bullet_text and not is_bullet:
            parts = [p.strip() for p in bullet_text.split("|")]
            if len(parts) >= 2:
                left_text = " | ".join(parts[:-1])
                right_text = parts[-1]

                # Style left & right parts based on section
                if left_text.replace(" ", "").replace("-", "").isupper() or current_section in ("EXPERIENCE", "EDUCATION"):
                    left_p = Paragraph(f"<b>{_escape(left_text)}</b>", body_style)
                    right_p = Paragraph(f"<i>{_escape(right_text)}</i>", right_body_style)
                    tbl = Table([[left_p, right_p]], colWidths=[usable_width - 150, 150])
                    tbl.setStyle(TableStyle([
                        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
                        ('LEFTPADDING', (0,0), (-1,-1), 0),
                        ('RIGHTPADDING', (0,0), (-1,-1), 0),
                        ('TOPPADDING', (0,0), (-1,-1), 0),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
                    ]))
                    story.append(tbl)
                    continue

        # Bullet with pipe (e.g. Certifications with date)
        if is_bullet and "|" in bullet_text:
            parts = [p.strip() for p in bullet_text.split("|")]
            if len(parts) >= 2:
                left_text = "• " + " | ".join(parts[:-1])
                right_text = parts[-1]
                left_p = Paragraph(_escape(left_text), body_style)
                right_p = Paragraph(_escape(right_text), right_body_style)
                tbl = Table([[left_p, right_p]], colWidths=[usable_width - 80, 80])
                tbl.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
                    ('LEFTPADDING', (0,0), (-1,-1), 14),
                    ('RIGHTPADDING', (0,0), (-1,-1), 0),
                    ('TOPPADDING', (0,0), (-1,-1), 0),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 1),
                ]))
                story.append(tbl)
                continue

        if is_bullet:
            story.append(Paragraph(_escape(bullet_text), bullet_style, bulletText="•"))
        else:
            if ":" in s and current_section == "SKILLS":
                cat, rest = s.split(":", 1)
                formatted = f"<b>{_escape(cat.strip())}:</b> {_escape(rest.strip())}"
                story.append(Paragraph(formatted, body_style))
            else:
                if current_section == "EDUCATION" and not s.isupper():
                    story.append(Paragraph(f"<i>{_escape(s)}</i>", body_style))
                else:
                    story.append(Paragraph(_escape(s), body_style))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def build_cover_letter_pdf(
    text: str,
    candidate_name: str = "",
    job_title: str = "",
    template: Optional[str] = "jamaica",
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
    template: Optional[str] = "jamaica",
    custom_styles: Optional[Dict[str, Any]] = None,
) -> str:
    """Generates styled standalone HTML resume matching the Jamaica Academic & preset templates."""
    cfg = _resolve_config(template, custom_styles)
    p_color = cfg["primary_color"]
    s_color = cfg["secondary_color"]
    b_color = cfg["body_color"]
    font_family = "Georgia, 'Times New Roman', serif" if cfg["font_family"] == "Times-Roman" else "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
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

    is_double_header = cfg.get("header_border_double") or (cfg["header_align"] == "center" and cfg["font_family"] == "Times-Roman")

    html_parts = []
    name_px = int(cfg.get("font_size_name", 15) * 1.1)
    html_parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_escape(name_line or 'Resume')}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: {font_family};
    color: {b_color};
    background-color: #ffffff;
    max-width: 800px;
    margin: 0 auto;
    padding: 32px 28px;
    line-height: 1.45;
  }}
  .name {{
    font-size: {name_px}px;
    font-weight: 700;
    color: {p_color};
    margin: 0 0 4px 0;
    text-align: {header_align};
    letter-spacing: 0.2px;
    line-height: 1.2;
  }}
  .header {{
    text-align: {header_align};
    margin-top: 4px;
    margin-bottom: 14px;
    { 'border-top: 1px solid ' + p_color + '; border-bottom: 1px solid ' + p_color + '; padding: 4px 0;' if is_double_header else ('border-bottom: 2px solid ' + p_color + '; padding-bottom: 10px;' if cfg['has_divider'] else '') }
  }}
  .contact {{
    font-size: 9.5pt;
    color: {s_color};
    margin: 1px 0;
    line-height: 1.35;
  }}
  .contact a {{
    color: #003399;
    text-decoration: underline;
  }}
  .section-title {{
    font-size: 12pt;
    font-weight: 700;
    color: {p_color};
    margin-top: 14px;
    margin-bottom: 4px;
    border-bottom: 1px solid {p_color};
    padding-bottom: 2px;
  }}
  .two-col {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-top: 4px;
    margin-bottom: 2px;
  }}
  .two-col-left {{
    font-size: {cfg['font_size_body']}pt;
    font-weight: 700;
  }}
  .two-col-right {{
    font-size: {cfg['font_size_body']}pt;
    font-style: normal;
    text-align: right;
  }}
  ul {{
    margin: 3px 0 8px 16px;
    padding: 0;
  }}
  li {{
    margin-bottom: 3px;
    font-size: {cfg['font_size_body']}pt;
    line-height: 1.35;
  }}
  p {{
    font-size: {cfg['font_size_body']}pt;
    margin: 3px 0;
    line-height: 1.35;
  }}
  @media print {{
    body {{ padding: 0; max-width: 100%; }}
  }}
</style>
</head>
<body>
""")

    if name_line or contact_lines:
        if name_line:
            html_parts.append(f'  <h1 class="name">{_escape(name_line)}</h1>')
        if contact_lines:
            html_parts.append('<div class="header">')
            for c_line in contact_lines:
                html_parts.append(f'  <p class="contact">{linkify_contact(c_line)}</p>')
            html_parts.append('</div>')

    current_section = ""
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
            current_section = upper
            sec_title = upper.title() if cfg["font_family"] == "Times-Roman" else upper
            html_parts.append(f'<div class="section-title">{_escape(sec_title)}</div>')
            continue

        is_bullet = s.startswith(("-", "•", "*"))
        bullet_text = s.lstrip("-•* ").strip() if is_bullet else s

        if "|" in bullet_text and not is_bullet:
            parts = [p.strip() for p in bullet_text.split("|")]
            if len(parts) >= 2:
                if in_list:
                    html_parts.append('</ul>')
                    in_list = False
                left_text = " | ".join(parts[:-1])
                right_text = parts[-1]
                html_parts.append(f'<div class="two-col"><span class="two-col-left">{_escape(left_text)}</span><span class="two-col-right">{_escape(right_text)}</span></div>')
                continue

        if is_bullet and "|" in bullet_text:
            parts = [p.strip() for p in bullet_text.split("|")]
            if len(parts) >= 2:
                if in_list:
                    html_parts.append('</ul>')
                    in_list = False
                left_text = "• " + " | ".join(parts[:-1])
                right_text = parts[-1]
                html_parts.append(f'<div class="two-col"><span style="font-size:{cfg["font_size_body"]}pt">{_escape(left_text)}</span><span class="two-col-right">{_escape(right_text)}</span></div>')
                continue

        if is_bullet:
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            html_parts.append(f'  <li>{_escape(bullet_text)}</li>')
        else:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            if ":" in s and current_section == "SKILLS":
                cat, rest = s.split(":", 1)
                html_parts.append(f'<p><strong>{_escape(cat.strip())}:</strong> {_escape(rest.strip())}</p>')
            elif current_section == "EDUCATION" and not s.isupper():
                html_parts.append(f'<p><em>{_escape(s)}</em></p>')
            else:
                html_parts.append(f'<p>{_escape(s)}</p>')

    if in_list:
        html_parts.append('</ul>')

    html_parts.append("</body>\n</html>")
    return "\n".join(html_parts)

