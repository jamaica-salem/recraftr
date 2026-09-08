"""Tests for Phase 13 (CORS) and Phase 14 (HTTPS & Security Headers)."""

import pytest
import requests
from starlette.testclient import TestClient
from fastapi import FastAPI
from starlette.responses import JSONResponse

from api_security import (
    SecurityHeadersMiddleware,
    get_cors_origins,
)
from tests.conftest import BASE_URL, API


def test_baseline_security_headers_present():
    """Verify OWASP-recommended security headers on live API responses."""
    res = requests.get(f"{BASE_URL}/health")
    assert res.status_code == 200

    headers = res.headers

    # 1. X-Content-Type-Options
    assert headers.get("X-Content-Type-Options") == "nosniff"

    # 2. X-Frame-Options (Clickjacking defense)
    assert headers.get("X-Frame-Options") == "DENY"

    # 3. Referrer-Policy
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    # 4. Permissions-Policy
    assert "camera=()" in headers.get("Permissions-Policy", "")
    assert "microphone=()" in headers.get("Permissions-Policy", "")
    assert "geolocation=()" in headers.get("Permissions-Policy", "")

    # 5. Content-Security-Policy
    csp = headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_cors_preflight_allowed_origin():
    """Verify that whitelisted origins receive proper CORS headers."""
    # http://localhost:3001 is a whitelisted dev origin
    headers = {
        "Origin": "http://localhost:3001",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization,content-type",
    }
    res = requests.options(f"{API}/resumes", headers=headers)
    assert res.status_code == 200
    assert res.headers.get("Access-Control-Allow-Origin") == "http://localhost:3001"
    assert res.headers.get("Access-Control-Allow-Credentials") == "true"
    assert "GET" in res.headers.get("Access-Control-Allow-Methods", "")


def test_cors_disallowed_origin_not_permitted():
    """Verify that unauthorized origins are not granted CORS access."""
    headers = {
        "Origin": "https://malicious-phishing-site.com",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    }
    res = requests.options(f"{API}/resumes", headers=headers)
    # The origin must NOT be echoed back, nor should wildcard be returned
    assert res.headers.get("Access-Control-Allow-Origin") != "https://malicious-phishing-site.com"
    assert res.headers.get("Access-Control-Allow-Origin") != "*"


def test_get_cors_origins_logic(monkeypatch):
    """Test get_cors_origins helper disallowing wildcards in production."""
    # 1. In development, includes local dev origins
    dev_origins = get_cors_origins(is_production=False)
    assert "http://localhost:3000" in dev_origins
    assert "http://localhost:3001" in dev_origins
    assert "https://recraftr.com" in dev_origins

    # 2. In production, strips wildcard if mistakenly set
    monkeypatch.setenv("CORS_ORIGINS", "*,https://custom-domain.com")
    prod_origins = get_cors_origins(is_production=True)
    assert "*" not in prod_origins
    assert "https://custom-domain.com" in prod_origins
    assert "https://recraftr.com" in prod_origins

    # 3. In production with no env, defaults to production domains
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    prod_defaults = get_cors_origins(is_production=True)
    assert "https://recraftr.com" in prod_defaults
    assert "https://www.recraftr.com" in prod_defaults
    assert "https://staging.recraftr.com" in prod_defaults
    assert "http://localhost:3000" not in prod_defaults


def test_production_hsts_and_https_redirect():
    """Verify HSTS and HTTPS redirection when SecurityHeadersMiddleware is in production mode."""
    test_app = FastAPI()

    @test_app.get("/test")
    def sample():
        return {"ok": True}

    test_app.add_middleware(SecurityHeadersMiddleware, is_production=True)
    client = TestClient(test_app)

    # 1. HSTS header present on secure request
    res = client.get("/test", headers={"X-Forwarded-Proto": "https"})
    assert res.status_code == 200
    assert "max-age=31536000" in res.headers.get("Strict-Transport-Security", "")
    assert "includeSubDomains" in res.headers.get("Strict-Transport-Security", "")

    # 2. HTTP -> HTTPS 301 redirect when unencrypted traffic arrives
    res_http = client.get("/test", headers={"X-Forwarded-Proto": "http", "Host": "recraftr.com"}, follow_redirects=False)
    assert res_http.status_code == 301
    assert res_http.headers.get("Location") == "https://recraftr.com/test"
