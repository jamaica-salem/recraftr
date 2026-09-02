"""End-to-end backend API tests for ResumeMatch AI.

Covers auth, resume upload, analyze (LLM), optimize (LLM), history and PDF download.
Uses REACT_APP_BACKEND_URL from env and follows the /api prefix rule.
"""
import os
import time
import uuid
import requests
import pytest

from .conftest import (
    API,
    DEMO_EMAIL,
    DEMO_PASSWORD,
    SAMPLE_JOB_TITLE,
    SAMPLE_JOB_DESCRIPTION,
    make_sample_pdf,
    make_sample_docx,
    random_email,
)


# ---------------- Health ----------------
class TestHealth:
    def test_root_ok(self, api_client):
        r = api_client.get(f"{API}/", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        assert data.get("service") == "Recraftr"


# ---------------- Auth ----------------
class TestAuth:
    def test_register_new_user_returns_token(self, api_client):
        email = random_email()
        r = api_client.post(
            f"{API}/auth/register",
            json={"email": email, "password": "secret123", "name": "Test User"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data.get("token"), str) and len(data["token"]) > 20
        # backend lowercases the email
        assert data["user"]["email"] == email.lower()
        assert data["user"]["name"] == "Test User"
        assert "id" in data["user"]

    def test_register_duplicate_email_returns_400(self, api_client):
        email = random_email()
        payload = {"email": email, "password": "secret123", "name": "Dup"}
        r1 = api_client.post(f"{API}/auth/register", json=payload, timeout=15)
        assert r1.status_code == 200
        r2 = api_client.post(f"{API}/auth/register", json=payload, timeout=15)
        assert r2.status_code == 400
        assert "already registered" in r2.text.lower()

    def test_login_success(self, api_client):
        r = api_client.post(
            f"{API}/auth/login",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["email"] == DEMO_EMAIL
        assert isinstance(data["token"], str)

    def test_login_wrong_password_returns_401(self, api_client):
        r = api_client.post(
            f"{API}/auth/login",
            json={"email": DEMO_EMAIL, "password": "wrongpassword"},
            timeout=15,
        )
        assert r.status_code == 401

    def test_me_requires_token(self, api_client):
        r = api_client.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401

    def test_me_with_valid_token(self, api_client, demo_headers):
        r = api_client.get(f"{API}/auth/me", headers=demo_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == DEMO_EMAIL
        assert "password_hash" not in data
        assert "_id" not in data


# ---------------- Resume upload ----------------
class TestResumeUpload:
    def test_upload_pdf_returns_parsed_preview(self, demo_headers):
        pdf_bytes = make_sample_pdf()
        files = {"file": ("resume.pdf", pdf_bytes, "application/pdf")}
        r = requests.post(f"{API}/upload-resume", headers=demo_headers, files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "resume_id" in data and len(data["resume_id"]) > 10
        assert data["filename"] == "resume.pdf"
        assert data["char_count"] > 100
        assert "Jane Doe" in data["text_preview"] or "Frontend" in data["text_preview"]

    def test_upload_docx_returns_parsed_preview(self, demo_headers):
        docx_bytes = make_sample_docx()
        files = {"file": ("resume.docx", docx_bytes,
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        r = requests.post(f"{API}/upload-resume", headers=demo_headers, files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["filename"] == "resume.docx"
        assert data["char_count"] > 100
        assert "Frontend" in data["text_preview"] or "Jane Doe" in data["text_preview"]

    def test_upload_requires_auth(self, api_client):
        files = {"file": ("resume.pdf", make_sample_pdf(), "application/pdf")}
        r = requests.post(f"{API}/upload-resume", files=files, timeout=15)
        assert r.status_code == 401


# ---------------- Analyze / Optimize (LLM) ----------------
class TestAnalyzeOptimizeLLM:
    """These tests exercise the real LLM path via emergentintegrations (GPT 5.4 by default)."""

    def test_analyze_returns_valid_schema(self, demo_headers, uploaded_resume):
        payload = {
            "resume_id": uploaded_resume["resume_id"],
            "job_title": SAMPLE_JOB_TITLE,
            "job_description": SAMPLE_JOB_DESCRIPTION,
            "model": "gpt-5.4",
        }
        r = requests.post(f"{API}/analyze", headers=demo_headers, json=payload, timeout=120)
        assert r.status_code == 200, f"analyze failed: {r.status_code} {r.text}"
        data = r.json()
        # analysis_id + core fields present
        assert "analysis_id" in data
        assert isinstance(data.get("ats_score"), int) and 0 <= data["ats_score"] <= 100
        bd = data.get("breakdown", {})
        for k in ("keyword_match", "skills_match", "experience_match"):
            assert isinstance(bd.get(k), int), f"breakdown.{k} missing/invalid"
            assert 0 <= bd[k] <= 100
        assert isinstance(data.get("gap_analysis"), list) and len(data["gap_analysis"]) >= 1
        ms = data.get("missing_skills", {})
        assert isinstance(ms.get("high"), list)
        assert isinstance(ms.get("medium"), list)
        assert isinstance(ms.get("optional"), list)
        assert isinstance(data.get("improvements"), list) and len(data["improvements"]) >= 1
        # save for optimize test
        pytest.analysis_id_for_optimize = data["analysis_id"]

    def test_optimize_uses_saved_analysis(self, demo_headers):
        aid = getattr(pytest, "analysis_id_for_optimize", None)
        if not aid:
            pytest.skip("analyze test did not produce an analysis_id")
        payload = {"analysis_id": aid, "aggressive": False}
        r = requests.post(f"{API}/optimize", headers=demo_headers, json=payload, timeout=120)
        assert r.status_code == 200, f"optimize failed: {r.status_code} {r.text}"
        data = r.json()
        assert data["analysis_id"] == aid
        opt = data.get("optimized_resume") or ""
        assert isinstance(opt, str) and len(opt) > 200, "optimized_resume too short"
        # It should be a resume-like text with section headers
        upper = opt.upper()
        assert any(h in upper for h in ("SUMMARY", "SKILLS", "EXPERIENCE", "EDUCATION")), (
            "Optimized resume missing standard section headers"
        )
        assert isinstance(data.get("predicted_ats_score"), int)
        assert 0 <= data["predicted_ats_score"] <= 100
        assert isinstance(data.get("original_resume_text"), str) and len(data["original_resume_text"]) > 50

    def test_analyze_rejects_unknown_resume_id(self, demo_headers):
        payload = {
            "resume_id": str(uuid.uuid4()),
            "job_title": SAMPLE_JOB_TITLE,
            "job_description": SAMPLE_JOB_DESCRIPTION,
        }
        r = requests.post(f"{API}/analyze", headers=demo_headers, json=payload, timeout=15)
        assert r.status_code == 404


# ---------------- History ----------------
class TestHistory:
    """History tests create their own analysis so they don't depend on TestAnalyze
    (which may run on a different xdist worker)."""

    def _seed_analysis(self, demo_headers):
        from .conftest import make_sample_pdf
        pdf_bytes = make_sample_pdf()
        files = {"file": ("history_seed.pdf", pdf_bytes, "application/pdf")}
        up = requests.post(f"{API}/upload-resume", headers=demo_headers, files=files, timeout=30)
        assert up.status_code == 200, up.text
        resume_id = up.json()["resume_id"]
        payload = {
            "resume_id": resume_id,
            "job_title": SAMPLE_JOB_TITLE,
            "job_description": SAMPLE_JOB_DESCRIPTION,
        }
        an = requests.post(f"{API}/analyze", headers=demo_headers, json=payload, timeout=120)
        assert an.status_code == 200, f"seed analyze failed: {an.status_code} {an.text}"
        return an.json()["analysis_id"]

    def test_history_lists_previous_analyses(self, demo_headers):
        seeded_id = self._seed_analysis(demo_headers)
        r = requests.get(f"{API}/history", headers=demo_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data.get("items"), list)
        assert len(data["items"]) >= 1
        ids = [it["id"] for it in data["items"]]
        assert seeded_id in ids
        first = data["items"][0]
        for k in ("id", "job_title", "ats_score", "optimized", "created_at"):
            assert k in first, f"history item missing {k}"

    def test_history_detail_and_delete(self, demo_headers):
        seeded_id = self._seed_analysis(demo_headers)
        # detail
        det = requests.get(f"{API}/history/{seeded_id}", headers=demo_headers, timeout=15)
        assert det.status_code == 200
        row = det.json()
        assert row["id"] == seeded_id
        assert row.get("analysis")
        assert "_id" not in row
        # delete
        d = requests.delete(f"{API}/history/{seeded_id}", headers=demo_headers, timeout=15)
        assert d.status_code == 200
        assert d.json().get("ok") is True
        # verify gone
        det2 = requests.get(f"{API}/history/{seeded_id}", headers=demo_headers, timeout=15)
        assert det2.status_code == 404


# ---------------- PDF download ----------------
class TestPdfDownload:
    def test_download_pdf_returns_pdf_bytes(self, demo_headers):
        text = (
            "Jane Doe\njane@example.com | 555-0100\n\n"
            "SUMMARY\nExperienced engineer with strong React skills.\n\n"
            "SKILLS\nReact, TypeScript, Node.js\n\n"
            "EXPERIENCE\nSenior Engineer | Acme | 2021 - Present\n"
            "- Built cool stuff\n"
        )
        r = requests.post(
            f"{API}/download-pdf",
            headers=demo_headers,
            json={"resume_text": text, "filename": "test-resume"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        body = r.content
        assert len(body) > 500
        assert body[:4] == b"%PDF", f"body does not start with %PDF: {body[:10]}"

    def test_download_pdf_rejects_empty(self, demo_headers):
        r = requests.post(
            f"{API}/download-pdf",
            headers=demo_headers,
            json={"resume_text": "", "filename": "empty"},
            timeout=15,
        )
        assert r.status_code == 400
