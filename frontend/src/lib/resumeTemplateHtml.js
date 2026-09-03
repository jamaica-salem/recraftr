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
  jamaica: {
    primaryColor: "#0A0A0A",
    secondaryColor: "#171717",
    bodyColor: "#171717",
    fontFamily: "Times-Roman",
    headerAlign: "center",
    fontSizeBody: 9.5,
    margin: "28px 24px",
    hasDivider: true,
    headerBorderDouble: true,
  },
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
  template = "jamaica",
  customStyles = {}
) {
  const base = { ...(PRESET_CONFIGS[template] || PRESET_CONFIGS.jamaica) };

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

  const isDoubleHeader = base.headerBorderDouble || (base.headerAlign === "center" && base.fontFamily === "Times-Roman");

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
    ${isDoubleHeader ? `border-top: 1px solid ${base.primaryColor}; border-bottom: 1px solid ${base.primaryColor}; padding: 6px 0;` : (base.hasDivider ? `border-bottom: 2px solid ${base.primaryColor}; padding-bottom: 10px;` : "")}
  }
  .name {
    font-size: 24px;
    font-weight: 700;
    color: ${base.primaryColor};
    margin: 0 0 6px 0;
    line-height: 1.2;
    letter-spacing: 0.5px;
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
    margin-top: 18px;
    margin-bottom: 4px;
    border-bottom: 1px solid ${base.primaryColor};
    padding-bottom: 2px;
  }
  .two-col {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-top: 4px;
    margin-bottom: 2px;
  }
  .two-col-left {
    font-size: ${base.fontSizeBody}pt;
    font-weight: 700;
  }
  .two-col-right {
    font-size: ${base.fontSizeBody}pt;
    font-style: italic;
    text-align: right;
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
    if (isDoubleHeader) {
      if (nameLine) htmlParts.push(`  <h1 class="name" style="text-align:center">${escapeHtml(nameLine)}</h1>`);
      htmlParts.push('<div class="header">');
      if (contactLines.length > 0) {
        htmlParts.push(`  <p class="contact">${escapeHtml(contactLines.join(" | "))}</p>`);
      }
      htmlParts.push("</div>");
    } else {
      htmlParts.push('<div class="header">');
      if (nameLine) htmlParts.push(`  <h1 class="name">${escapeHtml(nameLine)}</h1>`);
      if (contactLines.length > 0) {
        htmlParts.push(`  <p class="contact">${escapeHtml(contactLines.join(" | "))}</p>`);
      }
      htmlParts.push("</div>");
    }
  }

  let currentSection = "";
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
      currentSection = upper;
      const secTitle = base.fontFamily === "Times-Roman" ? upper.charAt(0) + upper.slice(1).toLowerCase() : upper;
      htmlParts.push(`<div class="section-title">${escapeHtml(secTitle)}</div>`);
      continue;
    }

    const isBullet = /^[-\u2022*]\s*/.test(s);
    const bulletText = isBullet ? s.replace(/^[-\u2022*]\s*/, "") : s;

    if (bulletText.includes("|") && !isBullet) {
      const parts = bulletText.split("|").map((p) => p.trim());
      if (parts.length >= 2) {
        if (inList) {
          htmlParts.push("</ul>");
          inList = false;
        }
        const leftText = parts.slice(0, -1).join(" | ");
        const rightText = parts[parts.length - 1];
        htmlParts.push(`<div class="two-col"><span class="two-col-left">${escapeHtml(leftText)}</span><span class="two-col-right">${escapeHtml(rightText)}</span></div>`);
        continue;
      }
    }

    if (isBullet && bulletText.includes("|")) {
      const parts = bulletText.split("|").map((p) => p.trim());
      if (parts.length >= 2) {
        if (inList) {
          htmlParts.push("</ul>");
          inList = false;
        }
        const leftText = "• " + parts.slice(0, -1).join(" | ");
        const rightText = parts[parts.length - 1];
        htmlParts.push(`<div class="two-col"><span style="font-size:${base.fontSizeBody}pt">${escapeHtml(leftText)}</span><span class="two-col-right">${escapeHtml(rightText)}</span></div>`);
        continue;
      }
    }

    if (isBullet) {
      if (!inList) {
        htmlParts.push("<ul>");
        inList = true;
      }
      htmlParts.push(`  <li>${escapeHtml(bulletText)}</li>`);
    } else {
      if (inList) {
        htmlParts.push("</ul>");
        inList = false;
      }
      if (s.includes(":") && currentSection === "SKILLS") {
        const idx = s.indexOf(":");
        const cat = s.substring(0, idx).trim();
        const rest = s.substring(idx + 1).trim();
        htmlParts.push(`<p><strong>${escapeHtml(cat)}:</strong> ${escapeHtml(rest)}</p>`);
      } else if (currentSection === "EDUCATION" && !s.toUpperCase().includes(s)) {
        htmlParts.push(`<p><em>${escapeHtml(s)}</em></p>`);
      } else {
        htmlParts.push(`<p>${escapeHtml(s)}</p>`);
      }
    }
  }

  if (inList) htmlParts.push("</ul>");
  htmlParts.push("</body>\n</html>");

  return htmlParts.join("\n");
}

