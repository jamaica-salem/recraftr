# Recraftr — AI-Powered Resume Optimizer & Career Assistant

> Transform your resume to match any Job Description in seconds. Powered by real-time AI streaming, ATS score analytics, automated cover letter generation, multi-version comparison, and job application tracking.

---

## Key Features

- **Real-Time AI Streaming**: Experience live token-by-token streaming for resume analysis, optimization, and cover letter generation powered by Server-Sent Events (SSE).
- **ATS Compatibility Analytics**: Instant 0–100 ATS match score with granular breakdown across Keyword Match, Hard Skills, Soft Skills, Experience Fit, and Formatting.
- **Multi-LLM Support**: Seamlessly toggle between **OpenAI (GPT-4o/GPT-5)** and **Google Gemini (Gemini 3 Flash)** models.
- **Auto-Boost Score Engine**: Multi-pass iterative optimization that automatically rewrites and enhances your resume until it hits target ATS thresholds (e.g. 90%+).
- **Web Job Description Scraper**: Paste any job posting URL (LinkedIn, Indeed, career sites) to automatically extract job title and requirements.
- **Interactive Bullet Rewriter**: Fine-tune individual bullet points on-the-fly with custom AI instructions (e.g., *add metrics*, *emphasize leadership*, *concise*).
- **Tailored Cover Letters**: Instantly generate context-aware, ATS-optimized cover letters tailored to your candidate profile and target role.
- **Multi-Resume Version Compare**: Compare up to 5 resume variants against a single target job to identify the highest-scoring match.
- **Job Application Tracker**: Built-in Kanban & table manager to track application statuses, custom resumes, notes, and ATS match scores.
- **Multi-Format Export Engine**: Download styled, ATS-compliant PDF resumes and cover letters (with customizable templates: Classic, Modern, Minimal, Executive) or raw HTML.
- **Secure Authentication & Saved History**: Custom JWT authentication with MongoDB database for persistent history and saved analysis reports.

---

## Tech Stack

### **Frontend**
- **Framework**: React 19 (bootstrapped with CRA & CRACO)
- **Routing**: React Router v7
- **Styling**: Tailwind CSS & Shadcn UI / Radix UI primitives
- **Motion & Icons**: Framer Motion, Lucide Icons
- **Data & Charts**: Recharts, Axios, Sonner Toasts

### **Backend**
- **Framework**: FastAPI (Python 3.10+)
- **Database**: MongoDB (Async motor driver)
- **Security**: Custom JWT Auth (PyJWT, Passlib, Bcrypt)
- **AI Integrations**: LiteLLM / Emergent LlmChat (OpenAI & Google Gemini APIs)
- **Document Processing**: `pdfplumber` (PDF parsing), `python-docx` (DOCX parsing), `reportlab` (PDF rendering)
- **Web Scraping**: BeautifulSoup4 & HTTPX

---

## Project Structure

```text
recraftr/
├── backend/                  # FastAPI Backend Application
│   ├── server.py             # Main FastAPI routes & SSE streaming endpoints
│   ├── ai_service.py         # AI analysis, optimization & bullet rewriter logic
│   ├── pdf_generator.py      # ReportLab PDF & HTML document generation
│   ├── resume_parser.py      # PDF & DOCX text extraction
│   ├── jd_scraper.py         # Job description URL web scraper
│   ├── auth.py               # Password hashing & JWT token validation
│   ├── requirements.txt      # Python dependencies
│   └── .env                  # Backend environment variables
│
├── frontend/                 # React 19 Frontend SPA
│   ├── src/
│   │   ├── components/       # UI components & modals (Export, Upload, Bullet Editor)
│   │   ├── pages/            # Dashboard, Compare, Tracker, History, Auth
│   │   └── App.js            # App routing & context provider setup
│   ├── package.json          # Frontend dependencies & scripts
│   └── tailwind.config.js    # Tailwind configuration
│
└── README.md                 # Project documentation
```

---

## Getting Started

### Prerequisites

Ensure you have the following installed on your system:
- **Node.js** (v18.x or later) & **Yarn** / **npm**
- **Python** (v3.10 or later)
- **MongoDB** (Local instance running on `localhost:27017` or MongoDB Atlas URI)

---

### 1. Backend Setup

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Create or edit the `.env` file in `backend/`:
   ```env
   MONGO_URL=mongodb://localhost:27017
   DB_NAME=recraftr
   JWT_SECRET=your_super_secret_jwt_key
   GEMINI_API_KEY=your_gemini_api_key
   GROQ_API_KEY=your_groq_api_key
   CORS_ORIGINS=*
   ```

5. **Start the FastAPI server**:
   ```bash
   uvicorn server:app --reload --port 8000
   ```
   The backend API will run at `http://localhost:8000`. You can inspect interactive API documentation at `http://localhost:8000/docs`.

---

### 2. Frontend Setup

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```

2. **Configure Environment Variables**:
   Create or edit the `.env` file in `frontend/` (see `frontend/.env.example`):
   ```env
   REACT_APP_BACKEND_URL=http://localhost:8000
   PORT=3001
   ```

3. **Install dependencies**:
   ```bash
   npm install
   # or: yarn install
   ```

4. **Start the development server**:
   ```bash
   npm start
   # or: yarn start
   ```

4. **Access the App**:
   Open `http://localhost:3000` in your web browser.

---

## API Reference Overview

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/auth/register` | `POST` | Register a new user account |
| `/api/auth/login` | `POST` | Authenticate user & receive JWT token |
| `/api/auth/me` | `GET` | Get current logged-in user profile |
| `/api/upload-resume` | `POST` | Upload PDF/DOCX resume file & extract text |
| `/api/analyze-stream` | `POST` | Stream ATS score, breakdown & gap analysis (SSE) |
| `/api/optimize-stream` | `POST` | Stream optimized ATS resume content (SSE) |
| `/api/auto-optimize-stream` | `POST` | Multi-pass streaming auto-optimization to hit target score |
| `/api/rewrite-bullet` | `POST` | AI-driven rewrite for individual bullet points |
| `/api/cover-letter-stream` | `POST` | Stream tailored cover letter text (SSE) |
| `/api/compare` | `POST` | Compare ATS scores for up to 5 resumes against one JD |
| `/api/scrape-jd` | `POST` | Scrape job title and description from a URL |
| `/api/download-pdf` | `POST` | Download styled resume in PDF or HTML format |
| `/api/cover-letter-pdf` | `POST` | Download cover letter in PDF or HTML format |
| `/api/applications` | `GET/POST/PUT/DELETE` | Manage job applications in Job Tracker |

---

## License

This project is open-source and available under the [MIT License](LICENSE).
