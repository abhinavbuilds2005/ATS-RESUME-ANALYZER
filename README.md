---
title: ATS Resume Analyzer
emoji: 📄
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
---

# AI-Powered ATS Resume Scorer & Analyzer

A high-performance web application that analyzes resumes, checks formatting and structural compliance, matches technical skills against job descriptions (JDs), validates claimed skills against experience entries, and provides actionable optimization feedback.

Built with **FastAPI** serving a modern **HTML5 / CSS / JavaScript** single-page application (SPA), powered by **spaCy** for linguistic NLP parsing, **Sentence Transformers** for chunk-based semantic similarity, and **Groq (Llama 3)** for LLM-assisted resume feedback with automatic rule-based fallbacks.

---

## Key Features

- **Document Parsing & Validation:**
  - Secure PDF and genuine DOCX parser (detects password-protected PDFs, scanned image-only PDFs, corrupted archives, and limits resumes to 25 pages / 5 MB).
- **Custom ATS-Readiness Scoring (0–100):**
  - **Formatting & Structure (20%):** Validates standard sections, bullet points, and section layout.
  - **Keywords & Technical Skills (25%):** Comprehensive punctuation-safe skill matching (supports `C++`, `C#`, `.NET`, `Node.js`, `React.js`, `CI/CD`, etc.).
  - **Content Quality & Impact (25%):** Action verbs, quantified metrics/achievements, and text quality analysis.
  - **Skill Validation (15%):** Cross-references declared skills against projects and work experience descriptions via semantic embeddings.
  - **ATS Parseability & Privacy (15%):** Flags complex multi-column glyphs and excessive PII (full street addresses, postal/PIN codes) while safely allowing city/state entries.
  - *Disclaimer:* The score produced is a custom heuristic ATS-readiness metric designed to optimize resume structure and keywords; it is not an official score issued by any proprietary ATS vendor.
- **Chunk-Based Semantic Similarity:**
  - Employs rolling chunked embeddings across the entire document to eliminate 5,000-character truncation loss.
- **Curated Job Description Gap Analysis:**
  - Filters out generic recruiter phrases ("software engineer", "scalable applications", "cross-functional teams") to focus solely on true technical skill gaps.
- **Resilient AI Pipeline:**
  - If the Groq API key is missing or the external API is unreachable, the system automatically falls back to deterministic NLP extraction (`llm_status: "fallback"`) with zero user interruption.
- **Enterprise Security & Privacy:**
  - Supabase JWT validation (supporting RS256/ES256 via JWKS and HS256 via secret) isolating user history to prevent Insecure Direct Object References (IDOR).
  - Sanitized filenames and Jinja2 autoescaping across all generated HTML and PDF reports.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend API** | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+) |
| **Frontend UI** | Modern HTML5, Vanilla JavaScript, Tailwind CSS (served as static files) |
| **NLP & Parsing** | [spaCy](https://spacy.io/) (`en_core_web_md`), `pypdf`, `python-docx` |
| **Semantic Similarity** | [Sentence Transformers](https://www.sbert.net/) (`all-MiniLM-L6-v2`) |
| **LLM Insights** | [Groq](https://groq.com/) (`llama-3.1-8b-instant`) with deterministic fallback |
| **Database & Auth** | [Supabase](https://supabase.com/) (PostgreSQL + JWT Authentication) |
| **PDF Generation** | [WeasyPrint](https://weasyprint.org/) with fallback to [xhtml2pdf](https://xhtml2pdf.readthedocs.io/) |

---

## Repository Structure

```
ai-resume-ats/
├── backend/
│   ├── api/                  # FastAPI routers and JWT auth dependencies
│   ├── core/                 # App configuration and score weightings
│   ├── database/             # Supabase async client and history queries
│   ├── models/               # Pydantic request/response schemas
│   ├── services/             # Parser, scorer, matcher, Groq LLM, and PDF export
│   ├── templates/            # Jinja2 HTML templates for PDF reports
│   ├── utils/                # Skill dictionary, regex patterns, and matching helpers
│   └── main.py               # FastAPI application entrypoint & static mount
├── frontend/
│   ├── assets/               # Icons and static brand assets
│   ├── css/                  # Custom styling overrides
│   ├── js/                   # Frontend SPA application logic (app.js)
│   └── index.html            # Single-page application interface
├── tests/                    # Comprehensive pytest test suite
├── Dockerfile                # Multi-stage production container build
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
└── README.md
```

---

## Installation & Setup

### 1. Prerequisites
- Python 3.10, 3.11, 3.12, or 3.13
- Git

### 2. Clone the Repository & Create Virtual Environment
```bash
git clone <repo-url>
cd ai-resume-ats-main
python -m venv venv

# On Linux/macOS:
source venv/bin/activate

# On Windows:
.\venv\Scripts\activate
```

### 3. Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_md
```

*System dependencies for WeasyPrint (Linux):*
```bash
# Debian / Ubuntu
sudo apt update && sudo apt install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your configuration:
```env
# Application
PROJECT_NAME="AI ATS Resume Analyzer"
ENVIRONMENT="development"
DEBUG=True

# Groq LLM (Optional - automatic fallback if unset)
GROQ_API_KEY="your_groq_api_key_here"

# Supabase Auth & Database (Optional for guest analysis; required for history)
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="your_supabase_service_role_key"
SUPABASE_ANON_KEY="your_supabase_anon_key"
SUPABASE_JWT_SECRET="your_supabase_jwt_secret"
```

> **Security Note:** Never commit `.env` to version control. `.env*` files are ignored by git.

---

## Running the Application

Start the FastAPI server:
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- **Web Application:** Visit `http://localhost:8000/` in your browser.
- **Interactive API Documentation:** Visit `http://localhost:8000/docs` (Swagger UI).
- **Health Check Endpoint:** `http://localhost:8000/api/v1/health`.

---

## Running Automated Tests

Run the full pytest suite:
```bash
python -m pytest tests/ -v
```

To run individual test modules:
```bash
# Skill matching (punctuation skills: C++, C#, .NET, Node.js, etc.)
python -m pytest tests/test_skill_matching.py -v

# Resume parsing & document validation (magic bytes, scanned detection, page limits)
python -m pytest tests/test_resume_parser.py -v

# Authentication & IDOR isolation
python -m pytest tests/test_backend_auth.py -v

# Job description matching & chunked similarity
python -m pytest tests/test_jd_matcher.py -v

# ATS scoring & text quality analysis
python -m pytest tests/test_ats_scorer.py tests/test_grammar_analysis.py -v

# Report & PDF generation
python -m pytest tests/test_report_generator.py -v
```

---

## Docker Deployment

Build and run using Docker:
```bash
docker build -t ai-resume-ats .
docker run -p 8000:8000 --env-file .env ai-resume-ats
```
The Dockerfile pre-downloads both the spaCy linguistic model and the Sentence Transformer embeddings to guarantee zero runtime download latency.
