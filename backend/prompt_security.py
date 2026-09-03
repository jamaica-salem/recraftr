"""Prompt Injection Defense, Untrusted Data Isolation, and Output Sanitization module."""

import re
import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("recraftr.prompt_security")

# Known prompt injection & system prompt exfiltration attack triggers
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above|system)\s+instructions", re.IGNORECASE),
    re.compile(r"reveal\s+(the\s+|your\s+)?system\s+prompt", re.IGNORECASE),
    re.compile(r"show\s+(me\s+)?(the\s+|your\s+)?system\s+prompt", re.IGNORECASE),
    re.compile(r"print\s+(the\s+|your\s+)?system\s+prompt", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*:", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(DAN|jailbroken|unrestricted)", re.IGNORECASE),
    re.compile(r"override\s+(system|safety)\s+(directives|rules)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
]

# Sensitive system prompt terms to scrub if leaked into model output
SYSTEM_LEAK_PATTERNS = [
    re.compile(r"You are ResumeMatch-QA", re.IGNORECASE),
    re.compile(r"MANDATORY SCORING RULES:", re.IGNORECASE),
    re.compile(r"CRITICAL SECURITY DIRECTIVE:", re.IGNORECASE),
    re.compile(r"<untrusted_candidate_resume>", re.IGNORECASE),
    re.compile(r"</untrusted_candidate_resume>", re.IGNORECASE),
    re.compile(r"<untrusted_job_description>", re.IGNORECASE),
    re.compile(r"</untrusted_job_description>", re.IGNORECASE),
]


def sanitize_user_input_text(text: Optional[str]) -> str:
    """Sanitizes user input by neutralizing prompt injection triggers and escaping XML data tags."""
    if not text:
        return ""
    
    clean = text
    
    # 1. Escape XML boundary tags to prevent tag breakout
    clean = clean.replace("<untrusted_candidate_resume>", "&lt;untrusted_candidate_resume&gt;")
    clean = clean.replace("</untrusted_candidate_resume>", "&lt;/untrusted_candidate_resume&gt;")
    clean = clean.replace("<untrusted_job_description>", "&lt;untrusted_job_description&gt;")
    clean = clean.replace("</untrusted_job_description>", "&lt;/untrusted_job_description&gt;")

    # 2. Neutralize injection triggers
    for pattern in INJECTION_PATTERNS:
        if pattern.search(clean):
            logger.warning("Prompt injection trigger detected and sanitized in user input.")
            clean = pattern.sub("[filtered_meta_directive]", clean)

    return clean


def wrap_untrusted_data(resume_text: str, job_description: str) -> Tuple[str, str]:
    """Wraps user-provided resume and job description inside isolated XML data blocks."""
    clean_resume = sanitize_user_input_text(resume_text)
    clean_jd = sanitize_user_input_text(job_description)

    wrapped_resume = f"<untrusted_candidate_resume>\n{clean_resume}\n</untrusted_candidate_resume>"
    wrapped_jd = f"<untrusted_job_description>\n{clean_jd}\n</untrusted_job_description>"
    return wrapped_resume, wrapped_jd


def sanitize_ai_output(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validates structured AI JSON output schema and scrubs leaked system prompt text."""
    if not isinstance(data, dict):
        return {}

    sanitized = dict(data)

    # 1. Validate & clamp ATS scores (0 to 100)
    if "ats_score" in sanitized:
        try:
            val = int(sanitized["ats_score"])
            sanitized["ats_score"] = max(0, min(100, val))
        except (ValueError, TypeError):
            sanitized["ats_score"] = 70

    if "predicted_ats_score" in sanitized:
        try:
            val = int(sanitized["predicted_ats_score"])
            sanitized["predicted_ats_score"] = max(0, min(100, val))
        except (ValueError, TypeError):
            sanitized["predicted_ats_score"] = 85

    # 2. Validate score category
    if "score_category" in sanitized:
        cat = str(sanitized["score_category"]).strip().title()
        if cat not in ("Strong", "Moderate", "Weak"):
            score = sanitized.get("ats_score", 70)
            cat = "Strong" if score >= 85 else ("Moderate" if score >= 60 else "Weak")
        sanitized["score_category"] = cat

    # 3. Scrub system prompt leakage from string fields
    for key, val in list(sanitized.items()):
        if isinstance(val, str):
            for leak_pattern in SYSTEM_LEAK_PATTERNS:
                if leak_pattern.search(val):
                    val = leak_pattern.sub("", val)
            sanitized[key] = val.strip()
        elif isinstance(val, list):
            clean_list = []
            for item in val:
                if isinstance(item, str):
                    for leak_pattern in SYSTEM_LEAK_PATTERNS:
                        if leak_pattern.search(item):
                            item = leak_pattern.sub("", item)
                    clean_list.append(item.strip())
                else:
                    clean_list.append(item)
            sanitized[key] = clean_list

    return sanitized
