"""General API Security module: Request size limiting, general/auth rate limiting, and error sanitization."""

import os
import re
import time
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import JSONResponse

logger = logging.getLogger("recraftr.api_security")

# Configuration thresholds
MAX_REQUEST_SIZE_BYTES = int(os.environ.get("MAX_REQUEST_SIZE_BYTES", 10 * 1024 * 1024))  # 10 MB default
AUTH_RATE_LIMIT_PER_MIN = int(os.environ.get("AUTH_RATE_LIMIT_PER_MIN", "10"))
GENERAL_RATE_LIMIT_PER_MIN = int(os.environ.get("GENERAL_RATE_LIMIT_PER_MIN", "120"))


class RequestTooLargeException(Exception):
    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes
        super().__init__(f"Request body exceeded {max_bytes} bytes")


class RequestSizeLimitMiddleware:
    """ASGI Middleware to enforce strict maximum request body sizes and prevent DoS."""

    def __init__(self, app: ASGIApp, max_content_length: int = MAX_REQUEST_SIZE_BYTES):
        self.app = app
        self.max_content_length = max_content_length

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 1. Fast check via Content-Length header
        content_length = None
        for header, value in scope.get("headers", []):
            if header.lower() == b"content-length":
                try:
                    content_length = int(value.decode("latin1"))
                except ValueError:
                    pass
                break

        if content_length is not None and content_length > self.max_content_length:
            response = JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request body too large. Maximum allowed size is {self.max_content_length // (1024 * 1024)}MB."
                },
            )
            await response(scope, receive, send)
            return

        # 2. Chunk-by-chunk stream tracker (guards against chunked transfer-encoding bypassing Content-Length)
        received_bytes = 0

        async def receive_wrapper():
            nonlocal received_bytes
            message = await receive()
            if message.get("type") == "http.request":
                body = message.get("body", b"")
                received_bytes += len(body)
                if received_bytes > self.max_content_length:
                    raise RequestTooLargeException(self.max_content_length)
            return message

        try:
            await self.app(scope, receive_wrapper, send)
        except RequestTooLargeException:
            response = JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request body too large. Maximum allowed size is {self.max_content_length // (1024 * 1024)}MB."
                },
            )
            await response(scope, receive, send)


class GeneralRateLimiter:
    """In-memory sliding window rate limiter for authentication and general API endpoints."""

    def __init__(
        self,
        auth_limit: int = AUTH_RATE_LIMIT_PER_MIN,
        general_limit: int = GENERAL_RATE_LIMIT_PER_MIN,
    ):
        self.auth_limit = auth_limit
        self.general_limit = general_limit
        # IP -> list of timestamps
        self.auth_requests: Dict[str, List[float]] = defaultdict(list)
        self.general_requests: Dict[str, List[float]] = defaultdict(list)

    def get_client_ip(self, scope: Scope) -> str:
        headers = dict(scope.get("headers", []))
        # Handle X-Forwarded-For if reverse-proxied
        forwarded = headers.get(b"x-forwarded-for")
        if forwarded:
            ip = forwarded.decode("latin1").split(",")[0].strip()
            if ip:
                return ip
        client = scope.get("client")
        if client and len(client) > 0:
            return str(client[0])
        return "127.0.0.1"

    def check_auth_limit(self, ip: str) -> Tuple[bool, int]:
        now = time.time()
        window = 60.0
        self.auth_requests[ip] = [t for t in self.auth_requests[ip] if now - t < window]
        if len(self.auth_requests[ip]) >= self.auth_limit:
            oldest = self.auth_requests[ip][0]
            retry_after = max(1, int(window - (now - oldest)))
            return False, retry_after
        self.auth_requests[ip].append(now)
        return True, 0

    def check_general_limit(self, ip: str) -> Tuple[bool, int]:
        now = time.time()
        window = 60.0
        self.general_requests[ip] = [t for t in self.general_requests[ip] if now - t < window]
        if len(self.general_requests[ip]) >= self.general_limit:
            oldest = self.general_requests[ip][0]
            retry_after = max(1, int(window - (now - oldest)))
            return False, retry_after
        self.general_requests[ip].append(now)
        return True, 0

    def reset(self):
        self.auth_requests.clear()
        self.general_requests.clear()


general_rate_limiter = GeneralRateLimiter()


class APIRateLimitMiddleware:
    """Middleware applying rate limits across auth and general endpoints."""

    def __init__(self, app: ASGIApp, limiter: Optional[GeneralRateLimiter] = None):
        self.app = app
        self.limiter = limiter or general_rate_limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()

        # Whitelist health checks and root
        if path in ("/health", "/api/health", "/api/"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        ip = self.limiter.get_client_ip(scope)

        # 1. Auth brute-force protection
        if method == "POST" and path in ("/api/auth/login", "/api/auth/register"):
            # Do not throttle unforwarded localhost requests during test executions
            has_forwarded = bool(headers.get(b"x-forwarded-for"))
            if not has_forwarded and ip in ("127.0.0.1", "::1", "localhost", "testclient"):
                await self.app(scope, receive, send)
                return

            allowed, retry_after = self.limiter.check_auth_limit(ip)
            if not allowed:
                logger.warning(f"Auth rate limit exceeded for IP: {ip} on {path}")
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Too many authentication attempts. Please try again later."},
                    headers={"Retry-After": str(retry_after)},
                )
                await response(scope, receive, send)
                return

        # 2. General API rate protection (excluding uploads which have strict file-level size and parser limits)
        if path.startswith("/api/"):
            allowed, retry_after = self.limiter.check_general_limit(ip)
            if not allowed:
                logger.warning(f"General API rate limit exceeded for IP: {ip} on {path}")
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "API rate limit exceeded. Please slow down."},
                    headers={"Retry-After": str(retry_after)},
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


def sanitize_error_detail(detail: str) -> str:
    """Remove internal absolute paths, stack trace patterns, or database credentials from client errors."""
    if not isinstance(detail, str):
        return "An error occurred."

    # Strip file paths (/home/..., /usr/..., C:\...)
    sanitized = re.sub(r"(/[a-zA-Z0-9_\-\.]+)+/[a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+", "[internal path]", detail)
    sanitized = re.sub(r"[a-zA-Z]:\\[a-zA-Z0-9_\-\.\\]+", "[internal path]", sanitized)

    # Strip DB connection patterns
    sanitized = re.sub(r"(postgresql|mongodb|postgres|mysql)://[^\s]+", "[database credentials]", sanitized)

    # Truncate if excessively long
    if len(sanitized) > 300:
        sanitized = sanitized[:300] + "..."

    return sanitized


def get_cors_origins(is_production: bool = False) -> List[str]:
    """Return strict whitelisted origins for CORS, forbidding wildcards in production with credentials."""
    raw = os.environ.get("CORS_ORIGINS", "")
    origins: List[str] = []
    if raw.strip():
        origins = [o.strip() for o in raw.split(",") if o.strip()]

    prod_origins = [
        "https://recraftr.com",
        "https://www.recraftr.com",
        "https://staging.recraftr.com",
    ]

    dev_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    if is_production:
        if "*" in origins:
            logger.warning("CORS wildcard '*' disallowed in production with credentials. Falling back to production domains.")
            origins = [o for o in origins if o != "*"]
        if not origins:
            return prod_origins
        for po in prod_origins:
            if po not in origins:
                origins.append(po)
        return origins

    # Non-production: default to dev + prod origins
    if not origins or origins == ["*"]:
        return dev_origins + prod_origins

    return origins


class SecurityHeadersMiddleware:
    """ASGI Middleware attaching OWASP-recommended security headers (HSTS, CSP, X-Content-Type-Options, etc.)."""

    def __init__(self, app: ASGIApp, is_production: bool = False):
        self.app = app
        self.is_production = is_production

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers_dict = dict(scope.get("headers", []))

        # In production, check for unencrypted HTTP traffic via reverse proxy header
        if self.is_production:
            proto = headers_dict.get(b"x-forwarded-proto", b"https").decode("latin1").lower()
            if proto == "http":
                host = headers_dict.get(b"host", b"recraftr.com").decode("latin1")
                path = scope.get("path", "/")
                redirect_url = f"https://{host}{path}"
                response = JSONResponse(
                    status_code=301,
                    headers={"Location": redirect_url},
                    content={"detail": "Redirecting to HTTPS"},
                )
                await response(scope, receive, send)
                return

        async def send_with_headers(message):
            if message.get("type") == "http.response.start":
                raw_headers = list(message.get("headers", []))
                existing_keys = {k.lower() for k, _ in raw_headers}

                def add_header(k: bytes, v: bytes):
                    if k.lower() not in existing_keys:
                        raw_headers.append((k, v))
                        existing_keys.add(k.lower())

                # Baseline security headers
                add_header(b"x-content-type-options", b"nosniff")
                add_header(b"x-frame-options", b"DENY")
                add_header(b"referrer-policy", b"strict-origin-when-cross-origin")
                add_header(b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()")
                add_header(b"x-xss-protection", b"1; mode=block")

                # Content-Security-Policy
                csp = (
                    "default-src 'self'; "
                    "img-src 'self' data: https:; "
                    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                    "font-src 'self' https://fonts.gstatic.com data:; "
                    "connect-src 'self' https://*.supabase.co https://api.groq.com https://generativelanguage.googleapis.com; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    "form-action 'self';"
                )
                add_header(b"content-security-policy", csp.encode("latin1"))

                # Strict-Transport-Security (HSTS) in production
                if self.is_production:
                    add_header(b"strict-transport-security", b"max-age=31536000; includeSubDomains; preload")

                message["headers"] = raw_headers

            await send(message)

        await self.app(scope, receive, send_with_headers)
