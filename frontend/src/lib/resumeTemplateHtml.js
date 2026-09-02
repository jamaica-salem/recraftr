const SECTION_HEADERS = new Set([
  "SUMMARY",
  "SKILLS",
  "EXPERIENCE",
  "EDUCATION",
  "PROJECTS",
  "CERTIFICATIONS",
  "AWARDS",
]);

const PRESET_CONFIGS = {
  classic: {
    primaryColor: "#0A0A0A",
    secondaryColor: "#404040",
    bodyColor: "#171717",
    fontFamily: "Helvetica",
    headerAlign: "left",
    fontSizeBody: 10.5,
    margin: "32px 28px",
    hasDivider: false,
  },
  modern: {
    primaryColor: "#1E3A8A",
    secondaryColor: "#475569",
    bodyColor: "#0F172A",
    fontFamily: "Helvetica",
    headerAlign: "left",
    fontSizeBody: 10.0,
    margin: "28px 24px",
    hasDivider: true,
  },
  compact: {
    primaryColor: "#111827",
    secondaryColor: "#374151",
    bodyColor: "#1F2937",
    fontFamily: "Helvetica",
    headerAlign: "left",
    fontSizeBody: 9.2,
    margin: "20px 20px",
    hasDivider: false,
  },
  elegant: {
    primaryColor: "#1E293B",
    secondaryColor: "#475569",
    bodyColor: "#1E293B",
    fontFamily: "Times-Roman",
    headerAlign: "center",
    fontSizeBody: 10.5,
    margin: "36px 32px",
    hasDivider: true,
  },
};

function escapeHtml(str = "") {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function generateResumeHtmlPreview(
  text = "",
  type = "resume", // "resume" or "cover_letter"
  template = "modern",
  customStyles = {}
) {
  const base = { ...(PRESET_CONFIGS[template] || PRESET_CONFIGS.classic) };

  if (customStyles?.primary_color) base.primaryColor = customStyles.primary_color;
  if (customStyles?.font_family) base.fontFamily = customStyles.font_family;
  if (customStyles?.header_align) base.headerAlign = customStyles.header_align;

  const fontCss =
    base.fontFamily === "Times-Roman"
      ? "Georgia, 'Times New Roman', serif"
      : "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

  const lines = (text || "").split("\n").map((ln) => ln.trimRight());
  while (lines.length > 0 && !lines[0].trim()) lines.shift();

  let nameLine = "";
  let contactLines = [];
  let bodyStart = 0;

  for (let i = 0; i < Math.min(lines.length, 5); i++) {
    const s = lines[i].trim();
    if (!s) continue;
    const upper = s.toUpperCase();
    if (!nameLine && !SECTION_HEADERS.has(upper)) {
      nameLine = s;
      bodyStart = i + 1;
    } else if (!SECTION_HEADERS.has(upper) && contactLines.length < 2) {
      contactLines.push(s);
      bodyStart = i + 1;
    } else {
      break;
    }
  }

  const htmlParts = [];
  htmlParts.push(`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: #ffffff; }
  body {
    font-family: ${fontCss};
    color: ${base.bodyColor};
    padding: ${base.margin};
    line-height: 1.45;
    font-size: ${base.fontSizeBody}pt;
  }
  .header {
    text-align: ${base.headerAlign};
    margin-bottom: 16px;
    border-bottom: ${base.hasDivider ? `2px solid ${base.primaryColor}` : "none"};
    padding-bottom: ${base.hasDivider ? "10px" : "0"};
  }
  .name {
    font-size: 22px;
    font-weight: 700;
    color: ${base.primaryColor};
    margin: 0 0 4px 0;
    line-height: 1.2;
  }
  .contact {
    font-size: 13px;
    color: ${base.secondaryColor};
    margin: 0;
  }
  .section-title {
    font-size: 14px;
    font-weight: 700;
    color: ${base.primaryColor};
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 18px;
    margin-bottom: 6px;
    border-bottom: ${base.hasDivider ? `1px solid ${base.primaryColor}` : "none"};
    padding-bottom: ${base.hasDivider ? "3px" : "0"};
  }
  ul {
    margin: 4px 0 10px 18px;
    padding: 0;
  }
  li {
    margin-bottom: 3px;
    font-size: ${base.fontSizeBody}pt;
  }
  p {
    font-size: ${base.fontSizeBody}pt;
    margin: 4px 0;
  }
</style>
</head>
<body>
`);

  if (nameLine || contactLines.length > 0) {
    htmlParts.push('<div class="header">');
    if (nameLine) htmlParts.push(`  <h1 class="name">${escapeHtml(nameLine)}</h1>`);
    if (contactLines.length > 0) {
      htmlParts.push(`  <p class="contact">${escapeHtml(contactLines.join(" | "))}</p>`);
    }
    htmlParts.push("</div>");
  }

  let inList = false;
  for (let i = bodyStart; i < lines.length; i++) {
    const s = lines[i].trim();
    if (!s) {
      if (inList) {
        htmlParts.push("</ul>");
        inList = false;
      }
      continue;
    }
    const upper = s.toUpperCase().replace(/:$/, "");
    if (SECTION_HEADERS.has(upper)) {
      if (inList) {
        htmlParts.push("</ul>");
        inList = false;
      }
      htmlParts.push(`<div class="section-title">${escapeHtml(upper)}</div>`);
    } else if (/^[-\u2022*]\s*/.test(s)) {
      if (!inList) {
        htmlParts.push("<ul>");
        inList = true;
      }
      htmlParts.push(`  <li>${escapeHtml(s.replace(/^[-\u2022*]\s*/, ""))}</li>`);
    } else {
      if (inList) {
        htmlParts.push("</ul>");
        inList = false;
      }
      htmlParts.push(`<p>${escapeHtml(s)}</p>`);
    }
  }

  if (inList) htmlParts.push("</ul>");
  htmlParts.push("</body>\n</html>");

  return htmlParts.join("\n");
}
