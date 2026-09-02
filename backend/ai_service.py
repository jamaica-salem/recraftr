"""LLM integration: streaming analyze/optimize/cover-letter."""
import os
import json
import re
import uuid
from typing import Any, Dict, AsyncGenerator
from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

EMERGENT_LLM_KEY = os.environ['EMERGENT_LLM_KEY']

MODELS = {
    "gpt-5.4": ("openai", "gpt-5.4"),
    "gemini-3-flash": ("gemini", "gemini-3-flash-preview"),
}
DEFAULT_MODEL = "gpt-5.4"


def _new_chat(system: str, model_key: str) -> LlmChat:
    provider, model = MODELS.get(model_key, MODELS[DEFAULT_MODEL])
    return LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"rc-{uuid.uuid4()}",
        system_message=system,
    ).with_model(provider, model)


def _extract_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else None
    if not candidate:
        start = text.find("{")
        end = text.rfind("}")
        candidate = text[start:end + 1] if start != -1 and end != -1 else text
    try:
        return json.loads(candidate)
    except Exception:
        return {}


# ---------------- Prompts ----------------
ANALYZE_SYSTEM = """You are an elite ATS (Applicant Tracking System) analyzer and career coach.
You compare a candidate's resume against a job description and produce a rigorous, structured analysis.
You always respond with a single valid JSON object matching the requested schema. No extra prose."""

ANALYZE_PROMPT = """Analyze the following resume against the job.

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description}

RESUME:
{resume_text}

Return ONLY a JSON object with this exact schema:
{{
  "ats_score": <integer 0-100>,
  "breakdown": {{
    "keyword_match": <integer 0-100>,
    "skills_match": <integer 0-100>,
    "experience_match": <integer 0-100>
  }},
  "resume_sections": {{
    "skills": [<string>], "experience": [<string>], "education": [<string>], "projects": [<string>]
  }},
  "job_requirements": {{
    "required_skills": [<string>], "keywords": [<string>], "responsibilities": [<string>]
  }},
  "gap_analysis": [
    {{"requirement": "<string>", "match": "Exact"|"Partial"|"Missing", "evidence": "<short quote or 'Not found'>"}}
  ],
  "missing_skills": {{ "high": [<string>], "medium": [<string>], "optional": [<string>] }},
  "improvements": [<string>]
}}

Be strict but fair. Include 6-12 gap rows and 5-10 improvements."""


OPTIMIZE_SYSTEM = """You are an elite resume writer specializing in ATS optimization.
You rewrite resumes to score 95+ on ATS systems while remaining truthful, professional, and realistic.
Never fabricate experience or credentials — only reframe, quantify, and inject relevant keywords naturally.
You return a single valid JSON object. No extra prose."""

OPTIMIZE_PROMPT = """Rewrite this resume to maximize alignment with the job below.

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description}

CURRENT RESUME:
{resume_text}

AGGRESSIVE MODE: {aggressive}

Guidelines:
- Preserve all factual claims (companies, dates, degrees). Do NOT invent experience.
- Rewrite bullets with strong action verbs and measurable impact when reasonable.
- Naturally weave in missing keywords/skills from the JD where the candidate plausibly has them.
- Keep formatting ATS-friendly: plain text, no tables, no columns.
- Sections: SUMMARY, SKILLS, EXPERIENCE, EDUCATION, PROJECTS (only relevant).
- Under EXPERIENCE, each role: "Job Title | Company | Dates" then "- " bullets.

Return ONLY a JSON object:
{{
  "optimized_resume": "<full plain-text resume, \\n line breaks>",
  "predicted_ats_score": <integer 0-100>,
  "changes_summary": [<string>]
}}"""


COVER_SYSTEM = """You are an elite cover letter writer.
Write personalized, professional cover letters that feel human, specific, and confident.
Never fabricate — only reference facts from the resume. Return a single JSON object. No extra prose."""

COVER_PROMPT = """Write a tailored cover letter for the candidate targeting this role.

JOB TITLE: {job_title}
JOB DESCRIPTION:
{job_description}

RESUME:
{resume_text}

Guidelines:
- 280-380 words, 3-4 short paragraphs.
- Open with a concrete hook tied to the role or company (no "I am writing to apply").
- Middle paragraphs weave 2-3 specific accomplishments from the resume, mapped to the job's needs.
- Close with a confident call-to-action.
- Warm, professional tone. First person. No cliches. No bullet lists.
- Do NOT invent facts. Only use the resume.

Return ONLY:
{{
  "cover_letter": "<full cover letter text with real line breaks between paragraphs>"
}}"""


# ---------------- Non-streaming (kept for compare and fallback) ----------------
async def analyze_resume(resume_text: str, job_title: str, job_description: str, model_key: str = DEFAULT_MODEL) -> Dict[str, Any]:
    chat = _new_chat(ANALYZE_SYSTEM, model_key)
    prompt = ANALYZE_PROMPT.format(job_title=job_title, job_description=job_description, resume_text=resume_text[:12000])
    resp = await chat.send_message(UserMessage(text=prompt))
    return _extract_json(resp if isinstance(resp, str) else str(resp))


async def optimize_resume(resume_text: str, job_title: str, job_description: str, aggressive: bool = False, model_key: str = DEFAULT_MODEL) -> Dict[str, Any]:
    chat = _new_chat(OPTIMIZE_SYSTEM, model_key)
    prompt = OPTIMIZE_PROMPT.format(
        job_title=job_title, job_description=job_description,
        resume_text=resume_text[:12000], aggressive="true" if aggressive else "false",
    )
    resp = await chat.send_message(UserMessage(text=prompt))
    return _extract_json(resp if isinstance(resp, str) else str(resp))


# ---------------- Streaming helpers ----------------
async def _run_stream(chat: LlmChat, prompt: str) -> AsyncGenerator[Dict[str, Any], None]:
    buf = ""
    try:
        async for ev in chat.stream_message(UserMessage(text=prompt)):
            if isinstance(ev, TextDelta):
                buf += ev.content
                yield {"type": "delta", "text": ev.content}
            elif isinstance(ev, StreamDone):
                break
    except Exception as e:
        # Fallback to non-streaming
        try:
            resp = await chat.send_message(UserMessage(text=prompt))
            buf = resp if isinstance(resp, str) else str(resp)
            yield {"type": "delta", "text": buf}
        except Exception as ee:
            yield {"type": "error", "error": f"{e} / {ee}"}
            return
    yield {"type": "result", "raw": buf, "parsed": _extract_json(buf)}


async def analyze_stream(resume_text: str, job_title: str, job_description: str, model_key: str = DEFAULT_MODEL) -> AsyncGenerator[Dict[str, Any], None]:
    chat = _new_chat(ANALYZE_SYSTEM, model_key)
    prompt = ANALYZE_PROMPT.format(job_title=job_title, job_description=job_description, resume_text=resume_text[:12000])
    async for ev in _run_stream(chat, prompt):
        yield ev


async def optimize_stream(resume_text: str, job_title: str, job_description: str, aggressive: bool, model_key: str = DEFAULT_MODEL) -> AsyncGenerator[Dict[str, Any], None]:
    chat = _new_chat(OPTIMIZE_SYSTEM, model_key)
    prompt = OPTIMIZE_PROMPT.format(
        job_title=job_title, job_description=job_description,
        resume_text=resume_text[:12000], aggressive="true" if aggressive else "false",
    )
    async for ev in _run_stream(chat, prompt):
        yield ev


async def cover_letter_stream(resume_text: str, job_title: str, job_description: str, model_key: str = DEFAULT_MODEL) -> AsyncGenerator[Dict[str, Any], None]:
    chat = _new_chat(COVER_SYSTEM, model_key)
    prompt = COVER_PROMPT.format(job_title=job_title, job_description=job_description, resume_text=resume_text[:12000])
    async for ev in _run_stream(chat, prompt):
        yield ev
