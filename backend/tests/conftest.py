"""Shared fixtures for ResumeMatch AI backend tests."""
import io
import os
import uuid
import pytest
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

# Registered demo user (see /app/memory/test_credentials.md)
DEMO_EMAIL = "test@resumematch.ai"
DEMO_PASSWORD = "testpass123"


SAMPLE_RESUME_TEXT = """Jane Doe
jane.doe@example.com | +1-555-0100 | San Francisco, CA | linkedin.com/in/janedoe

SUMMARY
Senior Frontend Engineer with 7 years of experience building responsive React web applications.
Passionate about performance, accessibility, design systems, and developer experience.

SKILLS
JavaScript, TypeScript, React, Redux, Next.js, HTML5, CSS3, Tailwind CSS, Jest, Cypress, Webpack, Node.js, GraphQL, REST APIs, Git

EXPERIENCE
Senior Frontend Engineer | Acme Corp | 2021 - Present
- Led migration of legacy Angular app to React + TypeScript, improving Lighthouse scores from 62 to 94.
- Built a reusable component library used across 8 product teams.
- Mentored 4 junior engineers and led weekly frontend guild meetings.

Frontend Engineer | Beta Startup | 2018 - 2021
- Shipped a new checkout flow that increased conversion by 18 percent.
- Introduced automated visual regression testing with Chromatic and Storybook.

EDUCATION
B.S. in Computer Science | State University | 2018

PROJECTS
Open-source contributor to popular React UI libraries and design tokens tooling.
"""

SAMPLE_JOB_TITLE = "Senior Frontend Engineer"
SAMPLE_JOB_DESCRIPTION = (
    "We are hiring a Senior Frontend Engineer to lead the development of our React based "
    "dashboard product. You must have deep expertise in React, TypeScript, and modern build "
    "tooling (Vite, Webpack). Experience with design systems, accessibility (WCAG), "
    "performance optimization, and testing (Jest, Cypress) is required. Familiarity with "
    "GraphQL, REST APIs, CI/CD pipelines, and mentoring junior engineers is a strong plus. "
    "Nice-to-have: Next.js, server-side rendering, and web performance profiling."
)


def make_sample_pdf(text: str = SAMPLE_RESUME_TEXT) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.setFont("Helvetica", 10)
    y = 750
    for line in text.splitlines():
        # simple wrapping
        while len(line) > 100:
            c.drawString(50, y, line[:100])
            line = line[100:]
            y -= 12
            if y < 50:
                c.showPage()
                c.setFont("Helvetica", 10)
                y = 750
        c.drawString(50, y, line)
        y -= 12
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = 750
    c.save()
    return buf.getvalue()


def make_sample_docx(text: str = SAMPLE_RESUME_TEXT) -> bytes:
    from docx import Document
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="session")
def api_base():
    return API


@pytest.fixture
def api_client():
    s = requests.Session()
    s.headers.update({"Accept": "application/json"})
    return s


def _login(session, email, password):
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    return r


@pytest.fixture(scope="session")
def demo_token():
    """Login (or auto-register) the shared demo user once for the session."""
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=15)
    if r.status_code == 200:
        return r.json()["token"]
    # If not registered yet, create it
    r = s.post(
        f"{API}/auth/register",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "name": "Demo User"},
        timeout=15,
    )
    if r.status_code == 200:
        return r.json()["token"]
    pytest.skip(f"Could not authenticate demo user: {r.status_code} {r.text}")


@pytest.fixture
def demo_headers(demo_token):
    return {"Authorization": f"Bearer {demo_token}"}


@pytest.fixture
def uploaded_resume(demo_headers):
    """Uploads a fresh PDF resume for the demo user and returns metadata."""
    pdf_bytes = make_sample_pdf()
    files = {"file": ("jane_doe_resume.pdf", pdf_bytes, "application/pdf")}
    r = requests.post(f"{API}/upload-resume", headers=demo_headers, files=files, timeout=30)
    assert r.status_code == 200, f"upload-resume failed: {r.status_code} {r.text}"
    return r.json()


def random_email(prefix="TEST_"):
    return f"{prefix}{uuid.uuid4().hex[:10]}@example.com"
