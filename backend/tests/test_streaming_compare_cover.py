"""Recraftr iteration 2 - SSE streaming, cover letter (+PDF), resume library and /api/compare tests.

We drive the real backend at REACT_APP_BACKEND_URL via /api. All streaming endpoints
require Authorization: Bearer <token>. We assert:
  * Content-Type: text/event-stream
  * >=1 delta event received AND deltas grow over time (not one big blob)
  * A final 'done' event contains the expected schema
  * Non-streaming /analyze + /optimize + /download-pdf still work (compat)
  * /api/resumes list + delete
  * /api/compare validation + happy path with 2 resumes
"""
import io
import json
import time
import uuid
import requests
import pytest

from .conftest import (
    API,
    SAMPLE_JOB_TITLE,
    SAMPLE_JOB_DESCRIPTION,
    make_sample_pdf,
)


# ---------- helpers ----------
def _sse_iter(resp, max_seconds=180):
    """Yield decoded SSE events (dicts). Time-bounded."""
    started = time.time()
    buf = ""
    for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
        if chunk is None:
            continue
        buf += chunk if isinstance(chunk, str) else chunk.decode("utf-8", "ignore")
        while "\n\n" in buf:
            frame, buf = buf.split("\n\n", 1)
            line = frame.strip()
            if line.startswith("data:"):
                line = line[len("data:"):].strip()
            if not line:
                continue
            try:
                yield json.loads(line), time.time() - started
            except json.JSONDecodeError:
                continue
        if time.time() - started > max_seconds:
            break


def _post_stream(url, headers, payload):
    return requests.post(
        url,
        headers={**headers, "Accept": "text/event-stream"},
        json=payload,
        stream=True,
        timeout=180,
    )


@pytest.fixture
def resume_id(demo_headers):
    files = {"file": ("stream_test.pdf", make_sample_pdf(), "application/pdf")}
    r = requests.post(f"{API}/upload-resume", headers=demo_headers, files=files, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["resume_id"]


# ============================================================================
# SSE: analyze-stream + optimize-stream + cover-letter (grouped so xdist
# loadscope keeps them on the same worker and shares state via pytest globals).
# ============================================================================
class TestStreamingEndToEnd:
    def test_1_analyze_stream_emits_deltas_and_done(self, demo_headers, resume_id):
        url = f"{API}/analyze-stream"
        payload = {
            "resume_id": resume_id,
            "job_title": SAMPLE_JOB_TITLE,
            "job_description": SAMPLE_JOB_DESCRIPTION,
            "model": "gpt-5.4",
        }
        resp = _post_stream(url, demo_headers, payload)
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "text/event-stream" in ct, f"content-type not SSE: {ct}"

        delta_texts = []
        delta_times = []
        done_event = None
        error_event = None
        for ev, t in _sse_iter(resp, max_seconds=180):
            if ev.get("type") == "delta":
                delta_texts.append(ev.get("text", ""))
                delta_times.append(t)
            elif ev.get("type") == "done":
                done_event = ev
                break
            elif ev.get("type") == "error":
                error_event = ev
                break

        assert error_event is None, f"stream errored: {error_event}"
        assert done_event is not None, "no done event received"
        assert len(delta_texts) >= 3, f"expected multiple delta chunks, got {len(delta_texts)}"
        # incremental: not all deltas arriving at basically the same instant
        first_last_gap = delta_times[-1] - delta_times[0] if len(delta_times) > 1 else 0
        assert first_last_gap > 0.05, (
            f"deltas were batched (all arrived within {first_last_gap:.3f}s), "
            "streaming not incremental"
        )
        # done schema
        assert "analysis_id" in done_event
        result = done_event.get("result") or {}
        assert isinstance(result.get("ats_score"), int)
        assert 0 <= result["ats_score"] <= 100
        for k in ("keyword_match", "skills_match", "experience_match"):
            assert isinstance(result.get("breakdown", {}).get(k), int)
        assert isinstance(result.get("gap_analysis"), list)
        assert isinstance(result.get("missing_skills"), dict)
        assert isinstance(result.get("improvements"), list)

        # Persistence: GET /history/{analysis_id} must return this analysis
        aid = done_event["analysis_id"]
        det = requests.get(f"{API}/history/{aid}", headers=demo_headers, timeout=15)
        assert det.status_code == 200
        assert det.json().get("analysis", {}).get("ats_score") == result["ats_score"]
        # save for optimize + cover letter tests below
        pytest.stream_analysis_id = aid


# ============================================================================
# SSE: optimize-stream
# ============================================================================
    def test_2_optimize_stream_emits_deltas_and_done(self, demo_headers):
        aid = getattr(pytest, "stream_analysis_id", None)
        if not aid:
            pytest.skip("analyze-stream didn't produce an analysis_id")
        url = f"{API}/optimize-stream"
        resp = _post_stream(url, demo_headers, {"analysis_id": aid, "aggressive": False})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        deltas = 0
        done = None
        err = None
        for ev, _t in _sse_iter(resp, max_seconds=180):
            if ev.get("type") == "delta":
                deltas += 1
            elif ev.get("type") == "done":
                done = ev
                break
            elif ev.get("type") == "error":
                err = ev
                break

        assert err is None, f"stream errored: {err}"
        assert done is not None, "no done event received"
        assert deltas >= 3, f"expected multiple deltas, got {deltas}"
        assert done.get("analysis_id") == aid
        original = done.get("original_resume_text") or ""
        assert isinstance(original, str) and len(original) > 50
        result = done.get("result") or {}
        opt = result.get("optimized_resume") or ""
        assert isinstance(opt, str) and len(opt) > 200
        upper = opt.upper()
        assert any(h in upper for h in ("SUMMARY", "SKILLS", "EXPERIENCE", "EDUCATION"))
        assert isinstance(result.get("predicted_ats_score"), int)
        # Persistence check
        det = requests.get(f"{API}/history/{aid}", headers=demo_headers, timeout=15).json()
        assert det.get("optimization") and det["optimization"].get("optimized_resume")
        assert det.get("original_resume_text")


# ============================================================================
# SSE: cover-letter-stream + PDF
# ============================================================================
    def test_3_cover_letter_stream(self, demo_headers):
        aid = getattr(pytest, "stream_analysis_id", None)
        if not aid:
            pytest.skip("analyze-stream didn't produce an analysis_id")
        url = f"{API}/cover-letter-stream"
        resp = _post_stream(url, demo_headers, {"analysis_id": aid})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        deltas = 0
        done = None
        err = None
        for ev, _t in _sse_iter(resp, max_seconds=180):
            if ev.get("type") == "delta":
                deltas += 1
            elif ev.get("type") == "done":
                done = ev
                break
            elif ev.get("type") == "error":
                err = ev
                break
        assert err is None, f"stream errored: {err}"
        assert done is not None
        assert deltas >= 3, f"expected many deltas, got {deltas}"
        letter = done.get("cover_letter") or ""
        assert isinstance(letter, str) and len(letter) > 150, "cover letter suspiciously short"
        # persistence
        det = requests.get(f"{API}/history/{aid}", headers=demo_headers, timeout=15).json()
        assert det.get("cover_letter") == letter
        pytest.cover_letter_text = letter

    def test_4_cover_letter_pdf(self, demo_headers):
        letter = getattr(pytest, "cover_letter_text", None) or (
            "Dear Hiring Manager,\n\nI am writing to express my strong interest in the "
            "Senior Frontend Engineer role at your company. With 7+ years of building React "
            "applications, I would bring immediate value.\n\nSincerely,\nJane Doe"
        )
        r = requests.post(
            f"{API}/cover-letter-pdf",
            headers=demo_headers,
            json={
                "cover_letter": letter,
                "candidate_name": "Jane Doe",
                "job_title": SAMPLE_JOB_TITLE,
                "filename": "cover-letter",
            },
            timeout=30,
        )
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        body = r.content
        assert len(body) > 500
        assert body[:4] == b"%PDF"

    def test_5_cover_letter_pdf_rejects_empty(self, demo_headers):
        r = requests.post(
            f"{API}/cover-letter-pdf",
            headers=demo_headers,
            json={"cover_letter": ""},
            timeout=15,
        )
        assert r.status_code == 400


# ============================================================================
# /api/resumes library
# ============================================================================
class TestResumeLibrary:
    def test_list_resumes(self, demo_headers):
        r = requests.get(f"{API}/resumes", headers=demo_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data.get("items"), list)
        assert len(data["items"]) >= 1
        first = data["items"][0]
        for k in ("id", "filename", "created_at"):
            assert k in first
        assert "_id" not in first
        assert "text" not in first  # must not leak full text

    def test_delete_resume(self, demo_headers):
        # upload a throwaway then delete
        files = {"file": ("todelete.pdf", make_sample_pdf(), "application/pdf")}
        up = requests.post(f"{API}/upload-resume", headers=demo_headers, files=files, timeout=30)
        assert up.status_code == 200
        rid = up.json()["resume_id"]
        d = requests.delete(f"{API}/resumes/{rid}", headers=demo_headers, timeout=15)
        assert d.status_code == 200
        # deleting again -> 404
        d2 = requests.delete(f"{API}/resumes/{rid}", headers=demo_headers, timeout=15)
        assert d2.status_code == 404

    def test_list_requires_auth(self):
        r = requests.get(f"{API}/resumes", timeout=15)
        assert r.status_code == 401


# ============================================================================
# /api/compare
# ============================================================================
class TestCompare:
    def _upload(self, demo_headers, name):
        files = {"file": (name, make_sample_pdf(), "application/pdf")}
        r = requests.post(f"{API}/upload-resume", headers=demo_headers, files=files, timeout=30)
        assert r.status_code == 200
        return r.json()["resume_id"]

    def test_compare_rejects_short_jd(self, demo_headers, resume_id):
        r = requests.post(
            f"{API}/compare",
            headers=demo_headers,
            json={"resume_ids": [resume_id], "job_title": "X", "job_description": "too short"},
            timeout=15,
        )
        assert r.status_code == 400

    def test_compare_rejects_too_many_resumes(self, demo_headers, resume_id):
        r = requests.post(
            f"{API}/compare",
            headers=demo_headers,
            json={
                "resume_ids": [resume_id] * 6,
                "job_title": SAMPLE_JOB_TITLE,
                "job_description": SAMPLE_JOB_DESCRIPTION,
            },
            timeout=15,
        )
        assert r.status_code == 400

    def test_compare_two_resumes_returns_sorted_results(self, demo_headers, resume_id):
        # need at least 2 resumes -> upload a second one
        rid2 = self._upload(demo_headers, "compare_b.pdf")
        r = requests.post(
            f"{API}/compare",
            headers=demo_headers,
            json={
                "resume_ids": [resume_id, rid2],
                "job_title": SAMPLE_JOB_TITLE,
                "job_description": SAMPLE_JOB_DESCRIPTION,
            },
            timeout=240,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data.get("results"), list) and len(data["results"]) == 2
        # sorted desc by ats_score
        scores = [x.get("ats_score") or 0 for x in data["results"]]
        assert scores == sorted(scores, reverse=True), f"not sorted desc: {scores}"
        for row in data["results"]:
            assert "resume_id" in row
            if "error" in row:
                continue
            assert isinstance(row.get("ats_score"), int)
            assert "breakdown" in row
            assert "missing_skills" in row
            assert isinstance(row.get("top_improvements", []), list)
        # cleanup
        requests.delete(f"{API}/resumes/{rid2}", headers=demo_headers, timeout=15)
