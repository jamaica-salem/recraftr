"""Recraftr backend."""
import os
import uuid
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
import io
import time

from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pydantic import BaseModel

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from auth import (
    UserRegister, UserLogin,
    hash_password, verify_password, create_token, get_current_user, new_user_doc,
)
from db import get_db, Profile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from resume_parser import parse_resume, parse_resume_async
from file_security import validate_upload_file, FileValidationError
from ai_security import ai_rate_limiter, record_ai_telemetry
from ai_service import (
    analyze_resume, optimize_resume,
    analyze_stream, optimize_stream, auto_optimize_stream, cover_letter_stream, rewrite_bullet,
    DEFAULT_MODEL,
)
from pdf_generator import build_pdf, build_cover_letter_pdf, build_html
from jd_scraper import scrape_jd
import asyncio

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'recraftr')]

app = FastAPI(title="Recraftr")
api = APIRouter(prefix="/api")


# ---------------- Auth ----------------
@api.post("/auth/register")
async def register(payload: UserRegister, session: AsyncSession = Depends(get_db)):
    email_clean = payload.email.lower().strip()
    from auth import supabase_admin
    if supabase_admin:
        try:
            sp_res = supabase_admin.auth.admin.create_user({
                "email": email_clean,
                "password": payload.password,
                "email_confirm": True,
                "user_metadata": {"name": payload.name},
            })
            user_id = str(sp_res.user.id)
            token = create_token(user_id)
            return {"token": token, "user": {"id": user_id, "email": email_clean, "name": payload.name}}
        except Exception as exc:
            err_msg = str(exc).lower()
            if "already" in err_msg and "registered" in err_msg or "unique" in err_msg:
                raise HTTPException(status_code=400, detail="Email already registered")
            logging.error(f"Supabase user registration error: {exc}")

    existing = await db.users.find_one({"email": email_clean})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = new_user_doc(payload.email, payload.name, hash_password(payload.password))
    await db.users.insert_one(doc)
    token = create_token(doc["id"])
    return {"token": token, "user": {"id": doc["id"], "email": doc["email"], "name": doc["name"]}}


@api.post("/auth/login")
async def login(payload: UserLogin):
    email_clean = payload.email.lower().strip()
    from auth import SUPABASE_URL, SUPABASE_ANON_KEY
    if SUPABASE_URL and SUPABASE_ANON_KEY:
        try:
            from supabase import create_client
            client_anon = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            res = client_anon.auth.sign_in_with_password({"email": email_clean, "password": payload.password})
            if res and res.session and res.user:
                return {
                    "token": res.session.access_token,
                    "user": {
                        "id": str(res.user.id),
                        "email": res.user.email,
                        "name": res.user.user_metadata.get("name") or res.user.email.split("@")[0],
                    },
                }
        except Exception:
            pass

    user = await db.users.find_one({"email": email_clean})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(user["id"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}


@api.get("/auth/me")
async def me(
    user_id: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    # 1. Check PostgreSQL profiles table
    try:
        user_uuid = uuid.UUID(user_id)
        stmt = select(Profile).where(Profile.id == user_uuid)
        result = await session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile:
            return {
                "id": str(profile.id),
                "email": profile.email,
                "name": profile.name,
                "created_at": profile.created_at.isoformat() if profile.created_at else None,
            }
    except ValueError:
        pass
    except Exception as exc:
        logging.warning(f"Error querying postgres profile: {exc}")

    # 2. Check legacy MongoDB
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if user:
        return user

    # 3. If authenticated via Supabase but profile row missing, auto-create in PostgreSQL
    from auth import supabase_admin
    if supabase_admin:
        try:
            sp_user = supabase_admin.auth.admin.get_user_by_id(user_id)
            if sp_user and sp_user.user:
                email = sp_user.user.email
                name = sp_user.user.user_metadata.get("name") or (email.split("@")[0] if email else "User")
                new_profile = Profile(id=uuid.UUID(user_id), email=email, name=name)
                session.add(new_profile)
                await session.commit()
                return {
                    "id": user_id,
                    "email": email,
                    "name": name,
                    "created_at": sp_user.user.created_at,
                }
        except Exception as exc:
            logging.warning(f"Error auto-syncing profile: {exc}")

    raise HTTPException(status_code=404, detail="User not found")


# ---------------- Resume upload / library ----------------
class UploadResumeResponse(BaseModel):
    resume_id: str
    filename: str
    text_preview: str
    char_count: int


@api.post("/upload-resume", response_model=UploadResumeResponse)
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    contents = await file.read()
    
    # 1. Security & Format Pre-validation
    try:
        sanitized_filename = validate_upload_file(
            original_filename=file.filename or "",
            mime_type=file.content_type or "",
            file_bytes=contents,
        )
    except FileValidationError as fve:
        raise HTTPException(status_code=400, detail=str(fve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File validation error: {e}")

    # 2. Async Parser Execution with 10.0s Timeout Guardrail
    try:
        text = await parse_resume_async(sanitized_filename, contents, timeout_seconds=10.0)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse resume: {e}")

    if len(text.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="Could not extract text from the file. Please ensure it contains selectable text (not scanned images)."
        )

    resume_id = str(uuid.uuid4())
    await db.resumes.insert_one({
        "id": resume_id,
        "user_id": user_id,
        "filename": sanitized_filename,
        "text": text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return UploadResumeResponse(
        resume_id=resume_id, filename=sanitized_filename,
        text_preview=text[:400], char_count=len(text),
    )


@api.get("/resumes")
async def list_resumes(user_id: str = Depends(get_current_user)):
    rows = await db.resumes.find(
        {"user_id": user_id}, {"_id": 0, "text": 0}
    ).sort("created_at", -1).to_list(50)
    return {"items": rows}


@api.delete("/resumes/{resume_id}")
async def delete_resume(resume_id: str, user_id: str = Depends(get_current_user)):
    res = await db.resumes.delete_one({"id": resume_id, "user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"ok": True}


# ---------------- Non-streaming analyze/optimize (kept for compare) ----------------
class AnalyzeRequest(BaseModel):
    resume_id: Optional[str] = None
    resume_text: Optional[str] = None
    job_title: str
    job_description: str
    model: Optional[str] = DEFAULT_MODEL


@api.post("/analyze")
async def analyze(payload: AnalyzeRequest, user_id: str = Depends(get_current_user)):
    resume_text = payload.resume_text
    resume_filename = "optimized_resume.pdf"
    resume_id = payload.resume_id

    if payload.resume_id:
        resume = await db.resumes.find_one({"id": payload.resume_id, "user_id": user_id})
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        resume_text = resume["text"]
        resume_filename = resume.get("filename")

    if not resume_text or len(resume_text.strip()) < 20:
        raise HTTPException(status_code=400, detail="Resume text or resume_id is required")

    try:
        result = await analyze_resume(
            resume_text, payload.job_title, payload.job_description, payload.model or DEFAULT_MODEL
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {e}")
    if not result or "ats_score" not in result:
        raise HTTPException(status_code=502, detail="AI returned an invalid response")

    analysis_id = str(uuid.uuid4())
    await db.analyses.insert_one({
        "id": analysis_id, "user_id": user_id,
        "resume_id": resume_id or analysis_id, "resume_filename": resume_filename,
        "job_title": payload.job_title, "job_description": payload.job_description,
        "model": payload.model or DEFAULT_MODEL,
        "analysis": result, "optimization": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"analysis_id": analysis_id, **result}


class OptimizeRequest(BaseModel):
    analysis_id: str
    aggressive: bool = False


async def _get_resume_text(row: dict, user_id: str) -> str:
    resume_id = row.get("resume_id")
    if resume_id:
        resume = await db.resumes.find_one({"id": resume_id, "user_id": user_id})
        if resume and resume.get("text"):
            return resume["text"]
    if row.get("original_resume_text"):
        return row["original_resume_text"]
    analysis_text = (row.get("analysis") or {}).get("resume_text")
    if analysis_text:
        return analysis_text
    opt_text = (row.get("optimization") or {}).get("optimized_resume")
    if opt_text:
        return opt_text
    raise HTTPException(status_code=404, detail="Original resume text not found")


@api.post("/optimize")
async def optimize(payload: OptimizeRequest, user_id: str = Depends(get_current_user)):
    row = await db.analyses.find_one({"id": payload.analysis_id, "user_id": user_id})
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found")
    resume_text = await _get_resume_text(row, user_id)
    try:
        result = await optimize_resume(
            resume_text, row["job_title"], row["job_description"],
            aggressive=payload.aggressive, model_key=row.get("model", DEFAULT_MODEL),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI optimization failed: {e}")
    if not result or "optimized_resume" not in result:
        raise HTTPException(status_code=502, detail="AI returned an invalid response")

    await db.analyses.update_one(
        {"id": payload.analysis_id},
        {"$set": {
            "optimization": {**result, "aggressive": payload.aggressive},
            "original_resume_text": resume_text,
            "optimized_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"analysis_id": payload.analysis_id, "original_resume_text": resume_text, **result}


# ---------------- Streaming (SSE) ----------------
def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


async def check_ai_limits(request: Request, user_id: str, operation: str):
    client_ip = request.client.host if request and request.client else "127.0.0.1"
    allowed, msg = await ai_rate_limiter.check_rate_limits(user_id, client_ip, operation, db)
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)
    return client_ip


@api.post("/analyze-stream")
async def analyze_stream_endpoint(payload: AnalyzeRequest, request: Request, user_id: str = Depends(get_current_user)):
    client_ip = await check_ai_limits(request, user_id, "analyze")
    resume_text = payload.resume_text
    resume_filename = "optimized_resume.pdf"
    resume_id = payload.resume_id

    if payload.resume_id:
        resume = await db.resumes.find_one({"id": payload.resume_id, "user_id": user_id})
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        resume_text = resume["text"]
        resume_filename = resume.get("filename")

    if not resume_text or len(resume_text.strip()) < 20:
        raise HTTPException(status_code=400, detail="Resume text or resume_id is required")

    req_id = f"ai_req_{uuid.uuid4().hex[:12]}"
    start_time = time.time()

    async def gen():
        final = None
        provider = "gemini"
        model_name = payload.model or DEFAULT_MODEL
        try:
            async for ev in analyze_stream(resume_text, payload.job_title, payload.job_description, payload.model or DEFAULT_MODEL):
                if ev.get("type") == "delta":
                    yield _sse({"type": "delta", "text": ev["text"]})
                elif ev.get("type") == "error":
                    yield _sse({"type": "error", "error": ev["error"]}); return
                elif ev.get("type") == "result":
                    final = ev.get("parsed") or {}
                    provider = ev.get("provider", provider)
                    model_name = ev.get("model", model_name)
            if not final or "ats_score" not in final:
                yield _sse({"type": "error", "error": "AI returned an invalid response"}); return
            analysis_id = str(uuid.uuid4())
            await db.analyses.insert_one({
                "id": analysis_id, "user_id": user_id,
                "resume_id": resume_id or analysis_id, "resume_filename": resume_filename,
                "job_title": payload.job_title, "job_description": payload.job_description,
                "model": payload.model or DEFAULT_MODEL,
                "analysis": final, "optimization": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            latency_ms = (time.time() - start_time) * 1000
            await record_ai_telemetry(
                db, user_id, "analyze", provider, model_name,
                f"{payload.job_title} {payload.job_description} {resume_text}",
                json.dumps(final), latency_ms, status="success", request_id=req_id
            )
            yield _sse({"type": "done", "analysis_id": analysis_id, "request_id": req_id, "result": final})
        except Exception as e:
            yield _sse({"type": "error", "error": str(e)})

    resp_headers = {**SSE_HEADERS, "X-Request-ID": req_id}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=resp_headers)


@api.post("/optimize-stream")
async def optimize_stream_endpoint(payload: OptimizeRequest, request: Request, user_id: str = Depends(get_current_user)):
    client_ip = await check_ai_limits(request, user_id, "optimize")
    row = await db.analyses.find_one({"id": payload.analysis_id, "user_id": user_id})
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found")
    resume_text = await _get_resume_text(row, user_id)

    req_id = f"ai_req_{uuid.uuid4().hex[:12]}"
    start_time = time.time()

    async def gen():
        final = None
        provider = "gemini"
        model_name = row.get("model", DEFAULT_MODEL)
        try:
            async for ev in optimize_stream(
                resume_text, row["job_title"], row["job_description"],
                aggressive=payload.aggressive, model_key=row.get("model", DEFAULT_MODEL),
            ):
                if ev.get("type") == "delta":
                    yield _sse({"type": "delta", "text": ev["text"]})
                elif ev.get("type") == "error":
                    yield _sse({"type": "error", "error": ev["error"]}); return
                elif ev.get("type") == "result":
                    final = ev.get("parsed") or {}
                    provider = ev.get("provider", provider)
                    model_name = ev.get("model", model_name)
            if not final or "optimized_resume" not in final:
                yield _sse({"type": "error", "error": "AI returned an invalid response"}); return
            await db.analyses.update_one(
                {"id": payload.analysis_id},
                {"$set": {
                    "optimization": {**final, "aggressive": payload.aggressive},
                    "original_resume_text": resume_text,
                    "optimized_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            latency_ms = (time.time() - start_time) * 1000
            await record_ai_telemetry(
                db, user_id, "optimize", provider, model_name,
                f"{row['job_title']} {row['job_description']} {resume_text}",
                json.dumps(final), latency_ms, status="success", request_id=req_id
            )
            yield _sse({"type": "done", "analysis_id": payload.analysis_id, "request_id": req_id, "original_resume_text": resume_text, "result": final})
        except Exception as e:
            yield _sse({"type": "error", "error": str(e)})

    resp_headers = {**SSE_HEADERS, "X-Request-ID": req_id}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=resp_headers)


class AutoOptimizeRequest(BaseModel):
    analysis_id: str
    target_score: Optional[int] = 90


@api.post("/auto-optimize-stream")
async def auto_optimize_stream_endpoint(payload: AutoOptimizeRequest, request: Request, user_id: str = Depends(get_current_user)):
    client_ip = await check_ai_limits(request, user_id, "optimize")
    row = await db.analyses.find_one({"id": payload.analysis_id, "user_id": user_id})
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found")
    resume_text = await _get_resume_text(row, user_id)
    start_text = (row.get("optimization") or {}).get("optimized_resume") or resume_text

    req_id = f"ai_req_{uuid.uuid4().hex[:12]}"
    start_time = time.time()

    async def gen():
        final = None
        provider = "gemini"
        model_name = row.get("model", DEFAULT_MODEL)
        try:
            async for ev in auto_optimize_stream(
                start_text, row["job_title"], row["job_description"],
                target_score=payload.target_score or 90,
                model_key=row.get("model", DEFAULT_MODEL)
            ):
                if ev.get("type") in ("delta", "status", "pass_done"):
                    yield _sse(ev)
                elif ev.get("type") == "error":
                    yield _sse({"type": "error", "error": ev["error"]}); return
                elif ev.get("type") == "result":
                    final = ev.get("parsed") or {}
                    provider = ev.get("provider", provider)
                    model_name = ev.get("model", model_name)
            if not final or "optimized_resume" not in final:
                yield _sse({"type": "error", "error": "AI returned an invalid response"}); return

            await db.analyses.update_one(
                {"id": payload.analysis_id},
                {"$set": {
                    "optimization": {**final, "auto_boosted": True},
                    "original_resume_text": resume_text,
                    "optimized_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            latency_ms = (time.time() - start_time) * 1000
            await record_ai_telemetry(
                db, user_id, "optimize", provider, model_name,
                f"{row['job_title']} {row['job_description']} {start_text}",
                json.dumps(final), latency_ms, status="success", request_id=req_id
            )
            yield _sse({"type": "done", "analysis_id": payload.analysis_id, "request_id": req_id, "original_resume_text": resume_text, "result": final})
        except Exception as e:
            yield _sse({"type": "error", "error": str(e)})

    resp_headers = {**SSE_HEADERS, "X-Request-ID": req_id}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=resp_headers)


# ---------------- Cover letter (streaming + PDF) ----------------
class CoverLetterRequest(BaseModel):
    analysis_id: str


@api.post("/cover-letter-stream")
async def cover_letter_stream_endpoint(payload: CoverLetterRequest, request: Request, user_id: str = Depends(get_current_user)):
    client_ip = await check_ai_limits(request, user_id, "cover_letter")
    row = await db.analyses.find_one({"id": payload.analysis_id, "user_id": user_id})
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found")
    resume_text = await _get_resume_text(row, user_id)

    req_id = f"ai_req_{uuid.uuid4().hex[:12]}"
    start_time = time.time()

    async def gen():
        final = None
        provider = "gemini"
        model_name = row.get("model", DEFAULT_MODEL)
        try:
            async for ev in cover_letter_stream(
                resume_text, row["job_title"], row["job_description"], row.get("model", DEFAULT_MODEL)
            ):
                if ev.get("type") == "delta":
                    yield _sse({"type": "delta", "text": ev["text"]})
                elif ev.get("type") == "error":
                    yield _sse({"type": "error", "error": ev["error"]}); return
                elif ev.get("type") == "result":
                    final = ev.get("parsed") or {}
                    provider = ev.get("provider", provider)
                    model_name = ev.get("model", model_name)
            letter = (final or {}).get("cover_letter", "").strip()
            if not letter:
                yield _sse({"type": "error", "error": "AI returned an empty cover letter"}); return
            await db.analyses.update_one(
                {"id": payload.analysis_id},
                {"$set": {"cover_letter": letter, "cover_letter_at": datetime.now(timezone.utc).isoformat()}},
            )
            latency_ms = (time.time() - start_time) * 1000
            await record_ai_telemetry(
                db, user_id, "cover_letter", provider, model_name,
                f"{row['job_title']} {row['job_description']} {resume_text}",
                letter, latency_ms, status="success", request_id=req_id
            )
            yield _sse({"type": "done", "cover_letter": letter, "request_id": req_id})
        except Exception as e:
            yield _sse({"type": "error", "error": str(e)})

    resp_headers = {**SSE_HEADERS, "X-Request-ID": req_id}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=resp_headers)


# ---------------- History ----------------
@api.get("/history")
async def history(user_id: str = Depends(get_current_user)):
    rows = await db.analyses.find(
        {"user_id": user_id}, {"_id": 0, "job_description": 0}
    ).sort("created_at", -1).to_list(100)
    items = []
    for r in rows:
        a = r.get("analysis") or {}
        items.append({
            "id": r["id"],
            "job_title": r.get("job_title"),
            "resume_filename": r.get("resume_filename"),
            "ats_score": a.get("ats_score"),
            "optimized": bool(r.get("optimization")),
            "has_cover_letter": bool(r.get("cover_letter")),
            "created_at": r.get("created_at"),
        })
    return {"items": items}


@api.get("/history/{analysis_id}")
async def history_detail(analysis_id: str, user_id: str = Depends(get_current_user)):
    row = await db.analyses.find_one({"id": analysis_id, "user_id": user_id}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@api.delete("/history/{analysis_id}")
async def history_delete(analysis_id: str, user_id: str = Depends(get_current_user)):
    res = await db.analyses.delete_one({"id": analysis_id, "user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


# ---------------- Compare (multi-resume vs one JD) ----------------
class CompareRequest(BaseModel):
    resume_ids: List[str]
    job_title: str
    job_description: str
    model: Optional[str] = DEFAULT_MODEL


@api.post("/compare")
async def compare(payload: CompareRequest, user_id: str = Depends(get_current_user)):
    if not payload.resume_ids:
        raise HTTPException(status_code=400, detail="At least one resume is required")
    if len(payload.resume_ids) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 resumes per comparison")
    if len(payload.job_description.strip()) < 30:
        raise HTTPException(status_code=400, detail="Job description too short")

    # Fetch all resume docs concurrently
    resume_docs = await asyncio.gather(*[
        db.resumes.find_one({"id": rid, "user_id": user_id}) for rid in payload.resume_ids
    ])

    sem = asyncio.Semaphore(5)  # cap concurrent LLM calls

    async def score_one(rid: str, resume: Optional[dict]):
        if not resume:
            return {"resume_id": rid, "filename": None, "error": "Resume not found"}
        async with sem:
            try:
                r = await analyze_resume(
                    resume["text"], payload.job_title, payload.job_description,
                    payload.model or DEFAULT_MODEL,
                )
                return {
                    "resume_id": rid,
                    "filename": resume.get("filename"),
                    "ats_score": r.get("ats_score"),
                    "breakdown": r.get("breakdown"),
                    "missing_skills": r.get("missing_skills"),
                    "top_improvements": (r.get("improvements") or [])[:3],
                }
            except Exception as e:
                return {"resume_id": rid, "filename": resume.get("filename"), "error": str(e)}

    results = await asyncio.gather(*[
        score_one(rid, doc) for rid, doc in zip(payload.resume_ids, resume_docs)
    ])
    results = list(results)
    results.sort(key=lambda x: x.get("ats_score") or 0, reverse=True)
    return {"results": results}


# ---------------- JD scrape ----------------
class ScrapeJdRequest(BaseModel):
    url: str
    model: Optional[str] = DEFAULT_MODEL


@api.post("/scrape-jd")
async def scrape_jd_endpoint(payload: ScrapeJdRequest, user_id: str = Depends(get_current_user)):
    try:
        result = await scrape_jd(payload.url.strip(), payload.model or DEFAULT_MODEL)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to scrape: {e}")
    if not result.get("job_title") and not result.get("job_description"):
        raise HTTPException(status_code=400, detail="The page didn't look like a job posting")
    return result


# ---------------- PDF & HTML downloads ----------------
class PdfRequest(BaseModel):
    resume_text: str
    filename: Optional[str] = "resume-optimized"
    template: Optional[str] = "classic"
    custom_styles: Optional[dict] = None
    format: Optional[str] = "pdf"


@api.post("/download-pdf")
async def download_pdf(payload: PdfRequest, user_id: str = Depends(get_current_user)):
    if not payload.resume_text or len(payload.resume_text.strip()) < 20:
        raise HTTPException(status_code=400, detail="Resume text is empty")
    name = (payload.filename or "resume-optimized").replace('"', '').strip() or "resume-optimized"

    if (payload.format or "pdf").lower() == "html":
        html_str = build_html(payload.resume_text, template=payload.template, custom_styles=payload.custom_styles)
        return StreamingResponse(
            io.BytesIO(html_str.encode("utf-8")), media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{name}.html"'},
        )

    pdf_bytes = build_pdf(payload.resume_text, template=payload.template, custom_styles=payload.custom_styles)
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'},
    )


class CoverLetterPdfRequest(BaseModel):
    cover_letter: str
    candidate_name: Optional[str] = ""
    job_title: Optional[str] = ""
    filename: Optional[str] = "cover-letter"
    template: Optional[str] = "classic"
    custom_styles: Optional[dict] = None
    format: Optional[str] = "pdf"


@api.post("/cover-letter-pdf")
async def cover_letter_pdf(payload: CoverLetterPdfRequest, user_id: str = Depends(get_current_user)):
    if not payload.cover_letter or len(payload.cover_letter.strip()) < 20:
        raise HTTPException(status_code=400, detail="Cover letter is empty")
    user = await db.users.find_one({"id": user_id})
    name = payload.candidate_name or (user.get("name") if user else "")
    fname = (payload.filename or "cover-letter").replace('"', '').strip() or "cover-letter"

    if (payload.format or "pdf").lower() == "html":
        header_title = f"Cover Letter — {payload.job_title}" if payload.job_title else "Cover Letter"
        html_str = build_html(
            f"{name}\n{header_title}\n\n{payload.cover_letter}",
            template=payload.template, custom_styles=payload.custom_styles
        )
        return StreamingResponse(
            io.BytesIO(html_str.encode("utf-8")), media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{fname}.html"'},
        )

    pdf_bytes = build_cover_letter_pdf(
        payload.cover_letter, candidate_name=name or "", job_title=payload.job_title or "",
        template=payload.template, custom_styles=payload.custom_styles
    )
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'},
    )


# ---------------- Bullet Rewrite Endpoint ----------------
class RewriteBulletRequest(BaseModel):
    bullet_text: str
    instruction: str
    job_description: Optional[str] = ""
    model: Optional[str] = DEFAULT_MODEL


@api.post("/rewrite-bullet")
async def rewrite_bullet_endpoint(payload: RewriteBulletRequest, request: Request, user_id: str = Depends(get_current_user)):
    client_ip = await check_ai_limits(request, user_id, "rewrite_bullet")
    if not payload.bullet_text or len(payload.bullet_text.strip()) < 5:
        raise HTTPException(status_code=400, detail="Bullet text is empty or too short")
    if not payload.instruction or len(payload.instruction.strip()) < 2:
        raise HTTPException(status_code=400, detail="Instruction is required")
    start_time = time.time()
    req_id = f"ai_req_{uuid.uuid4().hex[:12]}"
    try:
        res = await rewrite_bullet(
            payload.bullet_text, payload.instruction, payload.job_description or "", payload.model or DEFAULT_MODEL
        )
        latency_ms = (time.time() - start_time) * 1000
        await record_ai_telemetry(
            db, user_id, "rewrite_bullet", "gemini", payload.model or DEFAULT_MODEL,
            f"{payload.instruction} {payload.bullet_text}",
            json.dumps(res), latency_ms, status="success", request_id=req_id
        )
        return {**res, "request_id": req_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bullet rewrite failed: {e}")


# ---------------- Job Tracker / Applications ----------------
class ApplicationCreate(BaseModel):
    job_title: str
    company_name: Optional[str] = "Target Company"
    location: Optional[str] = ""
    status: Optional[str] = "applied"
    ats_score: Optional[int] = None
    job_description: Optional[str] = ""
    optimized_resume: Optional[str] = ""
    cover_letter: Optional[str] = ""
    notes: Optional[str] = ""
    resume_filename: Optional[str] = ""


class ApplicationUpdate(BaseModel):
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    ats_score: Optional[int] = None
    notes: Optional[str] = None
    optimized_resume: Optional[str] = None
    cover_letter: Optional[str] = None


@api.get("/applications")
async def list_applications(user_id: str = Depends(get_current_user)):
    rows = await db.applications.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("updated_at", -1).to_list(200)
    return {"items": rows}


@api.post("/applications")
async def create_application(payload: ApplicationCreate, user_id: str = Depends(get_current_user)):
    if not payload.job_title or len(payload.job_title.strip()) < 2:
        raise HTTPException(status_code=400, detail="Job title is required")
    app_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": app_id,
        "user_id": user_id,
        "job_title": payload.job_title.strip(),
        "company_name": (payload.company_name or "Target Company").strip(),
        "location": (payload.location or "").strip(),
        "status": (payload.status or "applied").lower(),
        "ats_score": payload.ats_score,
        "job_description": payload.job_description or "",
        "optimized_resume": payload.optimized_resume or "",
        "cover_letter": payload.cover_letter or "",
        "notes": payload.notes or "",
        "resume_filename": payload.resume_filename or "",
        "created_at": now,
        "updated_at": now,
    }
    await db.applications.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.put("/applications/{app_id}")
async def update_application(app_id: str, payload: ApplicationUpdate, user_id: str = Depends(get_current_user)):
    existing = await db.applications.find_one({"id": app_id, "user_id": user_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Application not found")

    updates = {}
    if payload.job_title is not None: updates["job_title"] = payload.job_title.strip()
    if payload.company_name is not None: updates["company_name"] = payload.company_name.strip()
    if payload.location is not None: updates["location"] = payload.location.strip()
    if payload.status is not None: updates["status"] = payload.status.lower()
    if payload.ats_score is not None: updates["ats_score"] = payload.ats_score
    if payload.notes is not None: updates["notes"] = payload.notes
    if payload.optimized_resume is not None: updates["optimized_resume"] = payload.optimized_resume
    if payload.cover_letter is not None: updates["cover_letter"] = payload.cover_letter

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.applications.update_one({"id": app_id, "user_id": user_id}, {"$set": updates})
    updated_doc = await db.applications.find_one({"id": app_id, "user_id": user_id}, {"_id": 0})
    return updated_doc


@api.delete("/applications/{app_id}")
async def delete_application(app_id: str, user_id: str = Depends(get_current_user)):
    res = await db.applications.delete_one({"id": app_id, "user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"ok": True}


# ---------------- Health ----------------
@api.get("/")
async def root():
    return {"service": "Recraftr", "status": "ok"}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recraftr")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
