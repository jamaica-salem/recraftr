"""Recraftr iteration 3 - JD URL scrape + parallel /api/compare.

We verify:
  * POST /api/scrape-jd on a live Greenhouse URL returns {job_title, job_description}
    in <2s (no LLM cost) with a plausible >500 char description.
  * POST /api/scrape-jd rejects malformed URLs, non-job pages, and pages with no
    extractable content.
  * POST /api/scrape-jd requires Bearer auth.
  * POST /api/compare runs analyses CONCURRENTLY: with 3 identical resume_ids the
    wallclock latency should be closer to the slowest single /analyze call than
    to 3x it. We assert T3 < 1.6 * T1.
  * /api/compare still enforces the previous bounds (1..5 ids, min 30-char JD)
    and still returns results sorted by ats_score desc.
"""
import os
import time
import requests
import pytest

from .conftest import (
    API,
    SAMPLE_JOB_TITLE,
    SAMPLE_JOB_DESCRIPTION,
    make_sample_pdf,
)

GH_BOARD_API = "https://boards-api.greenhouse.io/v1/boards/discord/jobs"


def _live_greenhouse_url() -> str:
    """Pick a live Greenhouse job so the test doesn't rot when a role closes."""
    try:
        r = requests.get(GH_BOARD_API, timeout=15)
        r.raise_for_status()
        jobs = (r.json() or {}).get("jobs") or []
    except Exception as e:
        pytest.skip(f"Cannot reach Greenhouse public API: {e}")
    for j in jobs:
        url = j.get("absolute_url") or ""
        if "job-boards.greenhouse.io/discord/jobs/" in url:
            return url
    if jobs:
        jid = jobs[0].get("id")
        if jid:
            return f"https://job-boards.greenhouse.io/discord/jobs/{jid}"
    pytest.skip("No live Greenhouse jobs available on discord board")


# ================= /api/scrape-jd =================
class TestScrapeJd:
    def test_scrape_greenhouse_url_fast_and_no_llm(self, demo_headers):
        url = _live_greenhouse_url()
        t0 = time.time()
        r = requests.post(
            f"{API}/scrape-jd",
            headers=demo_headers,
            json={"url": url},
            timeout=30,
        )
        elapsed = time.time() - t0
        assert r.status_code == 200, f"scrape-jd failed: {r.status_code} {r.text}"
        data = r.json()
        title = (data.get("job_title") or "").strip()
        desc = (data.get("job_description") or "").strip()
        assert title, "job_title empty"
        assert len(desc) >= 500, f"description too short ({len(desc)} chars)"
        # Regression (iter3 bug): Greenhouse's `content` field is HTML-entity-encoded
        # HTML. After html.unescape + BeautifulSoup the output must be genuine
        # plaintext -- no leftover markup markers.
        forbidden = ["<div", "<p>", "<p ", "<strong", "<ul", "<li", "</"]
        leaks = {tok: desc.count(tok) for tok in forbidden if tok in desc}
        assert not leaks, (
            f"Greenhouse description still contains raw HTML markers "
            f"(html.unescape regression?): {leaks}. Preview: {desc[:300]!r}"
        )
        # Also assert no angle brackets at all -- a strong signal the entities were
        # properly decoded before the DOM parser ran.
        assert desc.count("<") == 0, (
            f"Description contains {desc.count('<')} '<' chars — expected 0."
        )
        # Greenhouse public API path should be well under 2s; give a little
        # slack for ingress + Cloudflare.
        assert elapsed < 5.0, f"scrape took {elapsed:.2f}s (should be <5s via Greenhouse API)"
        print(f"[scrape-jd] {title!r} - {len(desc)} chars in {elapsed:.2f}s (no HTML leak)")

    def test_scrape_requires_auth(self):
        r = requests.post(
            f"{API}/scrape-jd",
            json={"url": "https://example.com"},
            timeout=15,
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code}"

    def test_scrape_rejects_non_url(self, demo_headers):
        r = requests.post(
            f"{API}/scrape-jd",
            headers=demo_headers,
            json={"url": "not-a-real-url"},
            timeout=15,
        )
        assert r.status_code == 400
        assert "url" in r.text.lower() or "http" in r.text.lower()

    def test_scrape_rejects_non_job_page(self, demo_headers):
        # example.com renders "Example Domain" - not a job posting.
        r = requests.post(
            f"{API}/scrape-jd",
            headers=demo_headers,
            json={"url": "https://example.com"},
            timeout=30,
        )
        assert r.status_code == 400, f"expected 400 for non-job page, got {r.status_code}: {r.text}"

    def test_scrape_handles_dead_host(self, demo_headers):
        r = requests.post(
            f"{API}/scrape-jd",
            headers=demo_headers,
            json={"url": "https://this-host-does-not-exist-91827364.example"},
            timeout=30,
        )
        assert r.status_code == 400, f"expected 400 for dead host, got {r.status_code}"


# ================= /api/compare parallel proof =================
class TestCompareParallel:
    @pytest.fixture
    def resume_id_for_perf(self, demo_headers):
        files = {"file": ("perf_resume.pdf", make_sample_pdf(), "application/pdf")}
        r = requests.post(f"{API}/upload-resume", headers=demo_headers, files=files, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()["resume_id"]

    def test_compare_runs_in_parallel(self, demo_headers, resume_id_for_perf):
        """T3 (compare of 3 resumes) should be closer to T1 (single analyze) than 3*T1."""
        # Warmup + T1
        payload_one = {
            "resume_id": resume_id_for_perf,
            "job_title": SAMPLE_JOB_TITLE,
            "job_description": SAMPLE_JOB_DESCRIPTION,
            "model": "gpt-5.4",
        }
        t0 = time.time()
        r1 = requests.post(f"{API}/analyze", headers=demo_headers, json=payload_one, timeout=180)
        t1 = time.time() - t0
        assert r1.status_code == 200, r1.text
        print(f"[compare-perf] single /analyze: {t1:.2f}s")

        # T3: compare of 3 identical ids
        payload_three = {
            "resume_ids": [resume_id_for_perf, resume_id_for_perf, resume_id_for_perf],
            "job_title": SAMPLE_JOB_TITLE,
            "job_description": SAMPLE_JOB_DESCRIPTION,
            "model": "gpt-5.4",
        }
        t0 = time.time()
        r3 = requests.post(f"{API}/compare", headers=demo_headers, json=payload_three, timeout=240)
        t3 = time.time() - t0
        assert r3.status_code == 200, r3.text
        data = r3.json()
        assert isinstance(data.get("results"), list) and len(data["results"]) == 3
        for row in data["results"]:
            assert isinstance(row.get("ats_score"), int), f"row missing ats_score: {row}"

        # Sorted desc
        scores = [row["ats_score"] for row in data["results"]]
        assert scores == sorted(scores, reverse=True)

        print(f"[compare-perf] /compare x3: {t3:.2f}s   (t3/t1={t3/max(t1,0.01):.2f})")
        # Parallel: t3 should be well below 3*t1. Allow 1.6x t1 to accommodate
        # network + json overhead + the semaphore (cap=5, 3 in flight fits fine).
        assert t3 < 1.6 * t1, (
            f"compare wallclock ({t3:.2f}s) not <= 1.6 * single analyze ({t1:.2f}s); "
            "suggests serial execution rather than asyncio.gather"
        )

    def test_compare_still_enforces_bounds(self, demo_headers, resume_id_for_perf):
        # empty list
        r = requests.post(
            f"{API}/compare",
            headers=demo_headers,
            json={
                "resume_ids": [],
                "job_title": SAMPLE_JOB_TITLE,
                "job_description": SAMPLE_JOB_DESCRIPTION,
            },
            timeout=15,
        )
        assert r.status_code == 400
        # > 5
        r = requests.post(
            f"{API}/compare",
            headers=demo_headers,
            json={
                "resume_ids": [resume_id_for_perf] * 6,
                "job_title": SAMPLE_JOB_TITLE,
                "job_description": SAMPLE_JOB_DESCRIPTION,
            },
            timeout=15,
        )
        assert r.status_code == 400
        # short JD
        r = requests.post(
            f"{API}/compare",
            headers=demo_headers,
            json={
                "resume_ids": [resume_id_for_perf],
                "job_title": SAMPLE_JOB_TITLE,
                "job_description": "too short",
            },
            timeout=15,
        )
        assert r.status_code == 400
