"""Deterministic analysis engine for Recraftr.

Provides fast, local Python keyword matching, section parsing, metric computation,
and initial gap analysis without LLM calls.
"""
import re
from typing import Dict, Any, List, Set

STOP_WORDS: Set[str] = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he",
    "in", "is", "it", "its", "of", "on", "that", "the", "to", "was", "were", "will",
    "with", "the", "this", "but", "they", "have", "had", "what", "when", "where",
    "who", "which", "why", "how", "all", "any", "both", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "can", "should", "now", "our", "my", "your",
    "we", "you", "or", "job", "role", "looking", "hiring", "team", "work", "experience",
    "years", "candidate", "must", "required", "plus", "strong", "ability"
}

ACTION_VERBS: Set[str] = {
    "built", "created", "developed", "engineered", "designed", "architected",
    "implemented", "scaled", "improved", "increased", "reduced", "led", "managed",
    "spearheaded", "optimized", "launched", "automated", "delivered", "deployed",
    "migrated", "collaborated", "mentored", "drove", "boosted", "expanded"
}


def _tokenize(text: str) -> List[str]:
    """Tokenize text into lowercased clean words."""
    words = re.findall(r"\b[a-zA-Z0-9\+\#\.\-]+\b", text.lower())
    return [w for w in words if len(w) > 1 and w not in STOP_WORDS]


def _extract_keywords(text: str, max_keywords: int = 25) -> List[str]:
    """Extract top distinct technical and professional terms."""
    tokens = _tokenize(text)
    freq: Dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    sorted_keywords = sorted(freq.keys(), key=lambda k: freq[k], reverse=True)
    return sorted_keywords[:max_keywords]


def parse_sections(resume_text: str) -> Dict[str, List[str]]:
    """Parse resume into key sections."""
    lines = [ln.strip() for ln in resume_text.splitlines() if ln.strip()]
    sections: Dict[str, List[str]] = {
        "skills": [],
        "experience": [],
        "education": [],
        "projects": []
    }
    current_sec = "experience"

    for line in lines:
        upper = line.upper()
        if "SKILL" in upper or "TECHNOLOGIES" in upper or "TOOLS" in upper:
            current_sec = "skills"
            continue
        elif "EXPERIENCE" in upper or "EMPLOYMENT" in upper or "WORK HISTORY" in upper:
            current_sec = "experience"
            continue
        elif "EDUCATION" in upper or "ACADEMIC" in upper:
            current_sec = "education"
            continue
        elif "PROJECT" in upper:
            current_sec = "projects"
            continue
        
        if current_sec in sections and len(line) > 2:
            sections[current_sec].append(line)

    return sections


def analyze_deterministic(resume_text: str, job_title: str, job_description: str) -> Dict[str, Any]:
    """Run fast deterministic analysis on resume + job description."""
    resume_tokens = set(_tokenize(resume_text))
    jd_tokens = set(_tokenize(job_description))
    title_tokens = set(_tokenize(job_title))

    jd_keywords = _extract_keywords(job_description, max_keywords=20)
    
    # Matching logic
    exact_matches = [kw for kw in jd_keywords if kw in resume_tokens]
    missing_keywords = [kw for kw in jd_keywords if kw not in resume_tokens]

    keyword_score = int((len(exact_matches) / max(len(jd_keywords), 1)) * 100)
    
    title_matches = [t for t in title_tokens if t in resume_tokens]
    title_score = int((len(title_matches) / max(len(title_tokens), 1)) * 100) if title_tokens else 80

    skills_score = min(100, int(keyword_score * 0.7 + 30))
    experience_score = min(100, int(title_score * 0.5 + keyword_score * 0.5))
    overall_score = int(keyword_score * 0.4 + skills_score * 0.3 + experience_score * 0.3)

    sections = parse_sections(resume_text)

    # Gap analysis
    gap_rows = []
    for kw in jd_keywords[:10]:
        if kw in resume_tokens:
            gap_rows.append({"requirement": kw.capitalize(), "match": "Exact", "evidence": f"Found in resume ('{kw}')"})
        else:
            gap_rows.append({"requirement": kw.capitalize(), "match": "Missing", "evidence": "Not found in resume"})

    # Action verbs & metric density
    resume_lower = resume_text.lower()
    verbs_found = [v for v in ACTION_VERBS if v in resume_lower]
    bullets = [ln for ln in resume_text.splitlines() if ln.strip().startswith("-") or ln.strip().startswith("•")]
    bullets_with_numbers = [b for b in bullets if re.search(r"\b\d+|\%|\$\b", b)]
    metric_density = int((len(bullets_with_numbers) / max(len(bullets), 1)) * 100) if bullets else 0

    return {
        "ats_score": overall_score,
        "breakdown": {
            "keyword_match": keyword_score,
            "skills_match": skills_score,
            "experience_match": experience_score
        },
        "resume_sections": sections,
        "job_requirements": {
            "required_skills": jd_keywords[:8],
            "keywords": jd_keywords[8:16],
            "responsibilities": [f"Demonstrate experience with {kw}" for kw in jd_keywords[:5]]
        },
        "gap_analysis": gap_rows,
        "missing_skills": {
            "high": missing_keywords[:3],
            "medium": missing_keywords[3:6],
            "optional": missing_keywords[6:9]
        },
        "deterministic_metrics": {
            "word_count": len(resume_text.split()),
            "bullet_count": len(bullets),
            "metric_density_pct": metric_density,
            "action_verbs_used": verbs_found
        }
    }
