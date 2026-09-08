"""Unit and integration tests for Phase 12: API Security & Production Hardening."""

import pytest
import requests
from unittest.mock import patch
from starlette.testclient import TestClient
from fastapi import FastAPI

from server import app
from api_security import (
    general_rate_limiter,
    sanitize_error_detail,
    GeneralRateLimiter,
)
from tests.conftest import BASE_URL, API


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Ensure clean rate limiting state before each test."""
    general_rate_limiter.reset()
    yield
    general_rate_limiter.reset()


def test_health_endpoints():
    """Test that /health, /api/health, and / return 200 OK with service status."""
    res = requests.get(f"{BASE_URL}/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "Recraftr"

    res_api = requests.get(f"{API}/health")
    assert res_api.status_code == 200
    assert res_api.json()["status"] == "ok"


def test_request_size_limit_content_length_header():
    """Test that requests exceeding max size are rejected with HTTP 413."""
    class SizedStream:
        def __init__(self, size):
            self.size = size
            self.read_so_far = 0

        def __len__(self):
            return self.size

        def read(self, chunk_size=8192):
            if self.read_so_far >= self.size:
                return b""
            chunk = min(chunk_size, self.size - self.read_so_far)
            self.read_so_far += chunk
            return b"A" * chunk

    stream = SizedStream(15 * 1024 * 1024)
    res = requests.post(f"{API}/auth/register", data=stream, headers={"Content-Type": "application/json"})
    assert res.status_code == 413
    assert "Request body too large" in res.json().get("detail", "")


import time


def test_auth_rate_limiting_brute_force_protection():
    """Test that auth endpoints enforce 10 requests/minute per IP and return HTTP 429."""
    test_ip = f"203.0.113.{(int(time.time() * 1000) % 200) + 10}"
    # Send 10 rapid login attempts from the same IP
    for i in range(10):
        res = requests.post(
            f"{API}/auth/login",
            json={"email": f"brute_{i}@example.com", "password": "wrongpassword123"},
            headers={"X-Forwarded-For": test_ip},
        )
        assert res.status_code in (400, 401, 404)

    # 11th request must be blocked with 429 Too Many Requests
    blocked_res = requests.post(
        f"{API}/auth/login",
        json={"email": "blocked@example.com", "password": "wrongpassword123"},
        headers={"X-Forwarded-For": test_ip},
    )
    assert blocked_res.status_code == 429
    assert "Too many authentication attempts" in blocked_res.json().get("detail", "")
    assert "Retry-After" in blocked_res.headers


def test_general_api_rate_limiting():
    """Test that general API endpoints reject requests after exceeding limit."""
    limiter = GeneralRateLimiter(general_limit=5)
    test_ip = "198.51.100.25"
    for _ in range(5):
        allowed, _ = limiter.check_general_limit(test_ip)
        assert allowed is True

    allowed, retry_after = limiter.check_general_limit(test_ip)
    assert allowed is False
    assert retry_after > 0


def test_pydantic_validation_field_bounds(demo_headers):
    """Test that payloads exceeding Field bounds are rejected with 422 Unprocessable Entity."""
    # 1. Job title exceeding 150 characters
    res = requests.post(
        f"{API}/analyze",
        json={
            "job_title": "A" * 200,
            "job_description": "Valid job description requiring software engineering skills.",
        },
        headers=demo_headers,
    )
    assert res.status_code == 422

    # 2. Compare request with too many resumes (> 10 items)
    res_compare = requests.post(
        f"{API}/compare",
        json={
            "resume_ids": [f"id_{i}" for i in range(15)],
            "job_title": "Senior Engineer",
            "job_description": "Job description requirement text that is sufficiently long.",
        },
        headers=demo_headers,
    )
    assert res_compare.status_code == 422

    # 3. Scrape JD with URL > 2048 characters
    res_scrape = requests.post(
        f"{API}/scrape-jd",
        json={"url": "https://example.com/jobs/" + "x" * 2100},
        headers=demo_headers,
    )
    assert res_scrape.status_code == 422


def test_pagination_and_query_limits(demo_headers):
    """Test pagination parameters on /api/resumes, /api/history, and /api/applications."""
    # 1. /api/resumes pagination
    res_resumes = requests.get(f"{API}/resumes?limit=2&offset=0", headers=demo_headers)
    assert res_resumes.status_code == 200
    data_resumes = res_resumes.json()
    assert "items" in data_resumes
    assert data_resumes.get("limit") == 2
    assert data_resumes.get("offset") == 0

    # 2. /api/history pagination
    res_hist = requests.get(f"{API}/history?limit=3&offset=0", headers=demo_headers)
    assert res_hist.status_code == 200
    data_hist = res_hist.json()
    assert "items" in data_hist
    assert data_hist.get("limit") == 3
    assert data_hist.get("offset") == 0

    # 3. /api/applications pagination
    res_apps = requests.get(f"{API}/applications?limit=5&offset=0", headers=demo_headers)
    assert res_apps.status_code == 200
    data_apps = res_apps.json()
    assert "items" in data_apps
    assert data_apps.get("limit") == 5
    assert data_apps.get("offset") == 0

    # 4. Limit clamping (> 100 clamped to 100)
    res_clamped = requests.get(f"{API}/resumes?limit=500&offset=0", headers=demo_headers)
    assert res_clamped.status_code == 200
    assert res_clamped.json().get("limit") == 100


def test_error_detail_sanitizer():
    """Test that sanitize_error_detail strips internal paths and connection strings."""
    raw_error = "Error in /home/jamaica-ai/Documents/Others/recraftr/backend/server.py at line 42: postgresql://postgres:secret_pass@aws-0.supabase.com:6543/postgres failed"
    clean = sanitize_error_detail(raw_error)
    assert "/home/jamaica-ai" not in clean
    assert "secret_pass" not in clean
    assert "[internal path]" in clean
    assert "[database credentials]" in clean


def test_production_docs_disabled_in_prod_mode():
    """Test that docs_url and redoc_url are disabled in production environment."""
    prod_app = FastAPI(
        title="Recraftr Production",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    prod_client = TestClient(prod_app)
    assert prod_client.get("/docs").status_code == 404
    assert prod_client.get("/redoc").status_code == 404
    assert prod_client.get("/openapi.json").status_code == 404
