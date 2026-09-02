# Recraftr — PRD (formerly ResumeMatch AI)

## Original problem statement
Build a modern AI-powered web app called "ResumeMatch AI" that optimizes a user's resume for a given
job description. User uploads a resume (PDF/DOCX), inputs Job Title + Job Description, clicks
Analyze/Optimize. Backend parses the resume, compares to the JD, produces ATS score + breakdown +
gap analysis + missing skills + improvements + optimized resume. Dark mode UI, no gradients, solid
colors, subtle borders and shadows only.

## User choices
- LLM providers: **GPT 5.4** (default) + **Gemini 3 Flash** (togglable in UI)
- LLM key: **Emergent Universal LLM Key** (user will replace with own later)
- PDF download: **styled server-side PDF** (reportlab)
- Auth: **JWT email/password** (custom, with login/signup pages)
- History: **saved per user in MongoDB**

## Architecture
- Backend: FastAPI (Python), MongoDB (motor), JWT auth (bcrypt+pyjwt).
- LLM: emergentintegrations `LlmChat` (OpenAI + Gemini providers, JSON responses).
- Resume parsing: pdfplumber (PDF) + python-docx (DOCX).
- PDF generation: reportlab (Letter, Helvetica, ATS-friendly text-only layout).
- Frontend: React 19, react-router-dom, Shadcn UI, Tailwind, sonner toasts, axios.
- Storage: Mongo collections — `users`, `resumes`, `analyses`.

## API endpoints (all under `/api`)
- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- `POST /upload-resume` (multipart, JWT)
- `POST /analyze` (JSON, JWT)
- `POST /optimize` (JSON, JWT)
- `GET /history`, `GET /history/{id}`, `DELETE /history/{id}` (JWT)
- `POST /download-pdf` (JWT, returns PDF stream)

## What's implemented (2026-02)
- Full end-to-end flow: signup → upload → analyze → optimize → download PDF.
- **Live streaming** for analyze / optimize / cover-letter (SSE, real tokens visible in loading overlay).
- **Cover Letter tab** — generate + copy + download styled PDF (server-side reportlab).
- **Version Compare page** (/compare) — upload multiple resume versions to a library, score up to 5 against one JD, ranked table.
- Results dashboard with 7 tabs (Overview / Gap / Missing / Improvements / Optimized / Cover Letter / Diff).
- ATS score ring + colored breakdown cards + grouped missing-skills badges.
- Model toggle (GPT 5.4 / Gemini 3 Flash), aggressive optimization switch.
- History page with saved analyses (open / delete / continue).
- Styled resume + cover-letter PDF export via reportlab.
- Login/Signup with JWT stored in localStorage, protected routes.
- Rebranded to **Recraftr** throughout (header, auth pages, browser title).
- Design: dark palette (#0A0A0A / #141414 / #262626 borders, primary #2563EB),
  Outfit + IBM Plex Sans, no gradients, generous spacing.

## Test credentials
`/app/memory/test_credentials.md`

## Backlog / next actions
- P1 — Streaming AI responses for perceived speed.
- P1 — Per-analysis re-optimization with different aggressiveness without re-parsing.
- P2 — Multi-resume comparison + best-fit picker.
- P2 — Shareable read-only report link.
- P2 — Cover letter generator using the same JD+resume context.
