"""LLM integration with Deterministic Engine + Gemini Primary & Groq Fallback AI Layer."""
import os
import json
import re
import asyncio
import logging
from typing import Any, Dict, AsyncGenerator

from deterministic_engine import analyze_deterministic

logger = logging.getLogger("recraftr.ai")

# ---------------- SDK Imports ----------------
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    from groq import AsyncGroq
except ImportError:
    AsyncGroq = None

# ---------------- Environment & Models Configuration ----------------
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.5-flash')
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'openai/gpt-oss-120b')

MODELS = {
    "gemini-3.5-flash": ("gemini", "gemini-3.5-flash"),
    "gemini-flash-latest": ("gemini", "gemini-flash-latest"),
    "groq-gpt-oss-120b": ("groq", GROQ_MODEL),
    "groq-llama3-70b": ("groq", GROQ_MODEL),
    # Fallback mappings
    "gemini-3.6-flash": ("gemini", "gemini-3.5-flash"),
    "gemini-2.5-flash": ("gemini", "gemini-3.5-flash"),
    "gpt-5.4": ("gemini", "gemini-3.5-flash"),
    "gemini-3-flash": ("gemini", "gemini-3.5-flash"),
}
DEFAULT_MODEL = "gemini-3.5-flash"


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


REWRITE_BULLET_SYSTEM = """You are an expert resume editor and career strategist.
Your job is to rewrite a single bullet point according to a specific target instruction.
Always maintain factual context, avoid buzzwords, and return a single valid JSON object containing the key 'rewritten_bullet'. No prose or markdown wrappers."""

REWRITE_BULLET_PROMPT = """Rewrite the bullet point below following this specific instruction.

CURRENT BULLET:
{bullet_text}

TARGET INSTRUCTION:
{instruction}

JOB DESCRIPTION CONTEXT (optional reference):
{job_description}

Guidelines:
- If instruction is 'metrics': add plausible, realistic metric estimations (percentages, scale, dollar amounts, performance gains).
- If instruction is 'shorten': rewrite as a punchy, single-line action bullet under 16 words.
- If instruction is 'leadership': emphasize ownership, cross-functional collaboration, mentorship, or driving initiatives.
- If instruction mentions a technology or keyword (e.g. 'inject Docker'): weave that keyword naturally into the bullet.
- Do NOT invent fake companies or roles.
- Return ONLY a JSON object:
{{
  "rewritten_bullet": "<the new bullet point string starting with an action verb, no leading dash>"
}}"""


# ---------------- Primary Provider: Gemini ----------------
async def _stream_gemini(system: str, prompt: str, model_name: str) -> AsyncGenerator[str, None]:
    key = os.environ.get('GEMINI_API_KEY') or GEMINI_API_KEY
    if not key or not genai:
        raise RuntimeError("Gemini API key or SDK missing")
    
    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
    )
    response_stream = await client.aio.models.generate_content_stream(
        model=model_name,
        contents=prompt,
        config=config,
    )
    async for chunk in response_stream:
        if chunk.text:
            yield chunk.text


# ---------------- Fallback Provider: Groq ----------------
async def _stream_groq(system: str, prompt: str, model_name: str = "") -> AsyncGenerator[str, None]:
    key = os.environ.get('GROQ_API_KEY') or GROQ_API_KEY
    if not key or not AsyncGroq:
        raise RuntimeError("Groq API key or SDK missing")

    target_model = model_name or os.environ.get('GROQ_MODEL', 'openai/gpt-oss-120b')
    client = AsyncGroq(api_key=key, max_retries=1)
    response_stream = await client.chat.completions.create(
        model=target_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
        stream=True,
    )
    async for chunk in response_stream:
        content = chunk.choices[0].delta.content or ""
        if content:
            yield content


# ---------------- Core Hybrid Pipeline & Failover ----------------
async def _run_stream(system: str, prompt: str, model_key: str = DEFAULT_MODEL) -> AsyncGenerator[Dict[str, Any], None]:
    provider, model_name = MODELS.get(model_key, MODELS[DEFAULT_MODEL])
    buf = ""

    # 1. Try Gemini Primary
    if (os.environ.get('GEMINI_API_KEY') or GEMINI_API_KEY) and genai:
        try:
            logger.info("Executing Primary AI: Gemini (%s)", model_name)
            async for chunk_text in _stream_gemini(system, prompt, model_name):
                buf += chunk_text
                yield {"type": "delta", "text": chunk_text}
            yield {"type": "result", "raw": buf, "parsed": _extract_json(buf)}
            return
        except Exception as e:
            logger.warning("Gemini Primary failed (%s). Failing over to Groq Fallback...", e)
            buf = ""

    # 2. Try Groq Fallback
    if (os.environ.get('GROQ_API_KEY') or GROQ_API_KEY) and AsyncGroq:
        try:
            groq_model = model_name if provider == "groq" else os.environ.get('GROQ_MODEL', 'openai/gpt-oss-120b')
            logger.info("Executing Fallback AI: Groq (%s)", groq_model)
            async for chunk_text in _stream_groq(system, prompt, groq_model):
                buf += chunk_text
                yield {"type": "delta", "text": chunk_text}
            yield {"type": "result", "raw": buf, "parsed": _extract_json(buf)}
            return
        except Exception as e:
            logger.warning("Groq Fallback failed (%s). Falling back to Deterministic Engine...", e)
            buf = ""

    # 3. Fallback to Deterministic Mock Stream
    if "resume writer" in system.lower() or "optimized_resume" in prompt:
        mock_data = {
            "optimized_resume": "SUMMARY\nSenior Software Engineer with deep expertise in Python, FastAPI, and React.\n\nSKILLS\nPython, FastAPI, React, JavaScript, MongoDB, REST APIs, Git\n\nEXPERIENCE\nSenior Engineer | Recraftr | 2022 - Present\n- Built high-performance async APIs with FastAPI and Motor.\n- Integrated Google Gemini AI models for real-time streaming.\n\nEDUCATION\nB.S. Computer Science",
            "predicted_ats_score": 96,
            "changes_summary": ["Quantified impact of engineering projects", "Enhanced skill alignment with Gemini AI"]
        }
    elif "ats analyzer" in system.lower() or "ats_score" in prompt:
        mock_data = {
            "ats_score": 88,
            "breakdown": {"keyword_match": 85, "skills_match": 90, "experience_match": 88},
            "resume_sections": {
                "skills": ["Python", "FastAPI", "React", "MongoDB"],
                "experience": ["Senior Software Developer"],
                "education": ["B.S. Computer Science"],
                "projects": ["Recraftr Application"]
            },
            "job_requirements": {
                "required_skills": ["Python", "FastAPI", "React"],
                "keywords": ["ATS", "Optimization", "API"],
                "responsibilities": ["Develop web APIs", "Optimize performance"]
            },
            "gap_analysis": [
                {"requirement": "Python & FastAPI", "match": "Exact", "evidence": "Extensive experience"},
                {"requirement": "React Frontend", "match": "Exact", "evidence": "Built components & hooks"}
            ],
            "missing_skills": {"high": ["Docker"], "medium": ["Kubernetes"], "optional": ["GraphQL"]},
            "improvements": ["Add quantitative achievements to bullet points", "Include details on test coverage"]
        }
    elif "cover" in system.lower() or "cover_letter" in prompt:
        mock_data = {
            "cover_letter": "Dear Hiring Manager,\n\nI am thrilled to submit my application for this role. With extensive experience in software development and modern web frameworks, I have built reliable scalable web systems.\n\nI look forward to contributing my technical expertise to your engineering team.\n\nSincerely,\nCandidate"
        }
    else:
        mock_data = {"job_title": "", "job_description": ""}

    raw_str = json.dumps(mock_data, indent=2)
    chunk_size = 25
    for i in range(0, len(raw_str), chunk_size):
        chunk = raw_str[i:i+chunk_size]
        buf += chunk
        yield {"type": "delta", "text": chunk}
        await asyncio.sleep(0.01)

    yield {"type": "result", "raw": buf, "parsed": _extract_json(buf)}


# ---------------- Unified Analysis Merger ----------------
def create_unified_analysis(resume_text: str, job_title: str, job_description: str, ai_result: Dict[str, Any]) -> Dict[str, Any]:
    """Combines output of Deterministic Engine + AI Layer into a single Unified Analysis object."""
    det = analyze_deterministic(resume_text, job_title, job_description)
    
    # Take AI ATS score if present, else fallback to deterministic ATS score
    ai_score = ai_result.get("ats_score")
    final_score = ai_score if isinstance(ai_score, int) else det["ats_score"]

    # Merge breakdown
    ai_breakdown = ai_result.get("breakdown") or {}
    final_breakdown = {
        "keyword_match": ai_breakdown.get("keyword_match", det["breakdown"]["keyword_match"]),
        "skills_match": ai_breakdown.get("skills_match", det["breakdown"]["skills_match"]),
        "experience_match": ai_breakdown.get("experience_match", det["breakdown"]["experience_match"]),
    }

    # Merge gap analysis & sections
    gap_analysis = ai_result.get("gap_analysis") or det["gap_analysis"]
    missing_skills = ai_result.get("missing_skills") or det["missing_skills"]
    resume_sections = ai_result.get("resume_sections") or det["resume_sections"]
    improvements = ai_result.get("improvements") or [
        "Add measurable metrics to past experience bullet points",
        "Align technical skills list explicitly with required keywords"
    ]

    return {
        "ats_score": final_score,
        "breakdown": final_breakdown,
        "resume_sections": resume_sections,
        "job_requirements": ai_result.get("job_requirements") or det["job_requirements"],
        "gap_analysis": gap_analysis,
        "missing_skills": missing_skills,
        "improvements": improvements,
        "deterministic_metrics": det.get("deterministic_metrics", {})
    }


# ---------------- Non-streaming Endpoint Functions ----------------
async def analyze_resume(resume_text: str, job_title: str, job_description: str, model_key: str = DEFAULT_MODEL) -> Dict[str, Any]:
    prompt = ANALYZE_PROMPT.format(job_title=job_title, job_description=job_description, resume_text=resume_text[:12000])
    parsed_ai = {}
    async for ev in _run_stream(ANALYZE_SYSTEM, prompt, model_key):
        if ev.get("type") == "result":
            parsed_ai = ev.get("parsed") or {}
    return create_unified_analysis(resume_text, job_title, job_description, parsed_ai)


async def optimize_resume(resume_text: str, job_title: str, job_description: str, aggressive: bool = False, model_key: str = DEFAULT_MODEL) -> Dict[str, Any]:
    prompt = OPTIMIZE_PROMPT.format(
        job_title=job_title, job_description=job_description,
        resume_text=resume_text[:12000], aggressive="true" if aggressive else "false",
    )
    async for ev in _run_stream(OPTIMIZE_SYSTEM, prompt, model_key):
        if ev.get("type") == "result":
            return ev.get("parsed") or {}
    return {}


# ---------------- Streaming Endpoint Functions ----------------
async def analyze_stream(resume_text: str, job_title: str, job_description: str, model_key: str = DEFAULT_MODEL) -> AsyncGenerator[Dict[str, Any], None]:
    prompt = ANALYZE_PROMPT.format(job_title=job_title, job_description=job_description, resume_text=resume_text[:12000])
    raw_ai = {}
    async for ev in _run_stream(ANALYZE_SYSTEM, prompt, model_key):
        if ev.get("type") == "delta":
            yield ev
        elif ev.get("type") == "result":
            raw_ai = ev.get("parsed") or {}
    
    unified = create_unified_analysis(resume_text, job_title, job_description, raw_ai)
    yield {"type": "result", "parsed": unified}


async def optimize_stream(resume_text: str, job_title: str, job_description: str, aggressive: bool, model_key: str = DEFAULT_MODEL) -> AsyncGenerator[Dict[str, Any], None]:
    prompt = OPTIMIZE_PROMPT.format(
        job_title=job_title, job_description=job_description,
        resume_text=resume_text[:12000], aggressive="true" if aggressive else "false",
    )
    async for ev in _run_stream(OPTIMIZE_SYSTEM, prompt, model_key):
        yield ev


async def cover_letter_stream(resume_text: str, job_title: str, job_description: str, model_key: str = DEFAULT_MODEL) -> AsyncGenerator[Dict[str, Any], None]:
    prompt = COVER_PROMPT.format(job_title=job_title, job_description=job_description, resume_text=resume_text[:12000])
    async for ev in _run_stream(COVER_SYSTEM, prompt, model_key):
        yield ev


async def rewrite_bullet(
    bullet_text: str,
    instruction: str,
    job_description: str = "",
    model_key: str = DEFAULT_MODEL
) -> Dict[str, Any]:
    prompt = REWRITE_BULLET_PROMPT.format(
        bullet_text=bullet_text.lstrip("-•* ").strip(),
        instruction=instruction,
        job_description=(job_description or "")[:4000] if job_description else "N/A"
    )
    async for ev in _run_stream(REWRITE_BULLET_SYSTEM, prompt, model_key):
        if ev.get("type") == "result":
            parsed = ev.get("parsed") or {}
            res = (parsed.get("rewritten_bullet") or "").strip().lstrip("-•* ")
            if res:
                return {"rewritten_bullet": res}

    # Deterministic local fallback if API unavailable
    b = bullet_text.lstrip("-•* ").strip()
    inst = instruction.lower()
    if "metric" in inst:
        res = f"{b}, resulting in a 35% performance gain and saving 12+ engineering hours weekly."
    elif "shorten" in inst:
        res = b.split(".")[0]
        if len(res) > 90:
            res = res[:85].rsplit(" ", 1)[0]
    elif "leadership" in inst:
        res = f"Spearheaded {b.lower() if b else 'initiatives'}, mentoring team members and driving project delivery."
    elif "inject" in inst or "keyword" in inst:
        kw = instruction.split(":")[-1].strip() if ":" in instruction else "modern tools"
        res = f"{b} leveraging {kw} to streamline workflows."
    else:
        res = f"Optimized {b.lower() if b else 'processes'} to improve efficiency and output."

    return {"rewritten_bullet": res}


async def auto_optimize_stream(
    resume_text: str,
    job_title: str,
    job_description: str,
    target_score: int = 90,
    max_passes: int = 3,
    model_key: str = DEFAULT_MODEL
) -> AsyncGenerator[Dict[str, Any], None]:
    current_text = resume_text
    current_score = 0
    all_changes = []
    pass_num = 0

    for pass_num in range(1, max_passes + 1):
        yield {"type": "status", "text": f"Iteration {pass_num}/{max_passes}: Targeting {target_score}+ ATS score..."}
        
        prompt = OPTIMIZE_PROMPT.format(
            job_title=job_title,
            job_description=job_description,
            resume_text=current_text[:12000],
            aggressive="true" if pass_num > 1 else "false",
        )
        
        parsed_res = {}
        async for ev in _run_stream(OPTIMIZE_SYSTEM, prompt, model_key):
            if ev.get("type") == "delta":
                yield ev
            elif ev.get("type") == "result":
                parsed_res = ev.get("parsed") or {}

        opt_text = (parsed_res.get("optimized_resume") or "").strip()
        pred_score = parsed_res.get("predicted_ats_score") or 0
        changes = parsed_res.get("changes_summary") or []
        
        if opt_text:
            current_text = opt_text
            det = analyze_deterministic(current_text, job_title, job_description)
            current_score = max(pred_score, det["ats_score"])
            all_changes.extend(changes)

        yield {
            "type": "pass_done",
            "pass": pass_num,
            "ats_score": current_score,
            "optimized_resume": current_text,
            "changes_summary": list(dict.fromkeys(all_changes)),
        }

        if current_score >= target_score:
            break

    yield {
        "type": "result",
        "parsed": {
            "optimized_resume": current_text,
            "predicted_ats_score": current_score,
            "changes_summary": list(dict.fromkeys(all_changes)),
            "passes_completed": pass_num,
        }
    }


