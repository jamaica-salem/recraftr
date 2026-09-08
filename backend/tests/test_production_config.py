"""Tests for Production Server and FastAPI Production Configuration.

Validates:
- Health and database readiness check endpoints.
- Production configuration files (systemd, nginx, logrotate, server setup, .env.production.example).
"""
import os
import stat
from pathlib import Path
import pytest
import requests

BASE_URL = "http://localhost:8000"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_health_endpoint():
    """Verify GET /health and GET /api/health return service ok."""
    resp = requests.get(f"{BASE_URL}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "Recraftr"
    assert "environment" in data

    api_resp = requests.get(f"{BASE_URL}/api/health")
    assert api_resp.status_code == 200
    assert api_resp.json()["status"] == "ok"


def test_readiness_probe_database_connectivity():
    """Verify GET /readiness and GET /api/readiness verify live database connectivity."""
    resp = requests.get(f"{BASE_URL}/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert data["service"] == "Recraftr"

    api_resp = requests.get(f"{BASE_URL}/api/readiness")
    assert api_resp.status_code == 200
    api_data = api_resp.json()
    assert api_data["status"] == "ready"
    assert api_data["database"] == "connected"


def test_nginx_production_configuration_integrity():
    """Validate deploy/nginx.conf contains required security and reverse proxy rules."""
    nginx_path = PROJECT_ROOT / "deploy" / "nginx.conf"
    assert nginx_path.exists(), "deploy/nginx.conf does not exist"

    content = nginx_path.read_text()
    assert "client_max_body_size 10M;" in content, "Nginx must enforce 10M body size ceiling"
    assert "proxy_buffering off;" in content, "Nginx must disable buffering for SSE streaming"
    assert "proxy_read_timeout 300s;" in content, "Nginx must allow adequate timeout for AI streaming"
    assert "return 301 https://$host$request_uri;" in content, "Nginx must redirect HTTP to HTTPS"
    assert "Strict-Transport-Security" in content, "Nginx must add HSTS header"
    assert "X-Content-Type-Options" in content, "Nginx must add nosniff header"
    assert "X-Frame-Options" in content, "Nginx must add clickjacking protection"
    assert "proxy_pass http://recraftr_backend;" in content, "Nginx must reverse proxy to backend upstream"


def test_systemd_service_configuration_integrity():
    """Validate deploy/recraftr-backend.service contains required systemd directives."""
    service_path = PROJECT_ROOT / "deploy" / "recraftr-backend.service"
    assert service_path.exists(), "deploy/recraftr-backend.service does not exist"

    content = service_path.read_text()
    assert "User=recraftr" in content, "Service must run under non-root recraftr user"
    assert "Restart=always" in content, "Service must automatically restart on failure"
    assert "LimitNOFILE=65535" in content, "Service must raise file descriptor limit for high concurrency"
    assert "--workers 4" in content, "Service must configure multiple Uvicorn workers"
    assert "--proxy-headers" in content, "Service must accept proxy headers from Nginx"
    assert "ProtectSystem=full" in content, "Service must employ Linux system hardening"


def test_logrotate_configuration_integrity():
    """Validate deploy/recraftr.logrotate contains daily log rotation and compression."""
    logrotate_path = PROJECT_ROOT / "deploy" / "recraftr.logrotate"
    assert logrotate_path.exists(), "deploy/recraftr.logrotate does not exist"

    content = logrotate_path.read_text()
    assert "/var/log/recraftr/*.log" in content
    assert "daily" in content
    assert "rotate 14" in content
    assert "compress" in content


def test_server_setup_script_integrity_and_permissions():
    """Validate deploy/setup_server.sh is executable and contains firewall and provisioning commands."""
    setup_path = PROJECT_ROOT / "deploy" / "setup_server.sh"
    assert setup_path.exists(), "deploy/setup_server.sh does not exist"

    # Check executable bit
    mode = setup_path.stat().st_mode
    assert bool(mode & stat.S_IXUSR), "deploy/setup_server.sh must be executable"

    content = setup_path.read_text()
    assert "ufw default deny incoming" in content
    assert "ufw allow 80/tcp" in content
    assert "ufw allow 443/tcp" in content
    assert "ufw deny 8000/tcp" in content, "Direct FastAPI port must be blocked from public traffic"
    assert "adduser --system" in content or "useradd" in content or "recraftr" in content
    assert "unattended-upgrades" in content, "Automatic security upgrades must be configured"


def test_production_env_template_integrity():
    """Validate backend/.env.production.example contains production defaults."""
    env_path = PROJECT_ROOT / "backend" / ".env.production.example"
    assert env_path.exists(), "backend/.env.production.example does not exist"

    content = env_path.read_text()
    assert "ENVIRONMENT=production" in content
    assert "DEBUG=False" in content
    assert "DATABASE_URL=postgresql+asyncpg://" in content
    assert "pooler.supabase.com" in content
    assert "ssl=require" in content
    assert "PAYMONGO_SECRET_KEY" in content
    assert "CORS_ORIGINS" in content
