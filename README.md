# LitEngage — AI-Powered School Library Reading Companion

LitEngage is a conversational AI system that acts as a personalized school librarian, recommending books to students based on their reading history, preferences, and grade-appropriate reading levels. It combines semantic book search, an agentic LLM workflow, real-time content moderation, and a librarian oversight dashboard into a single full-stack application.

## Features

### Student Experience
- **AI Chat** — Natural-language conversations powered by a LangGraph agent backed by Google Gemini 2.5 Flash. Students describe what they're in the mood for, and the agent searches 5,000+ curated books via ChromaDB semantic similarity.
- **Personalized Recommendations** — Takes reading history, grade level, and stated preferences into account. Uses MMR (Maximal Marginal Relevance) for diversity so students aren't recommended the same genre repeatedly.
- **Book Catalog** — Browse, search, and filter the full catalog. View ratings, descriptions, genres, and community reviews.
- **Student Dashboard** — Reading progress, streaks, goals, badges, and a leaderboard to encourage engagement.
- **Reviews** — Students write reviews that are auto-moderated by AI before appearing publicly.

### Librarian Tools
- **Librarian Chat** — An AI assistant with database tools that can answer questions like "Which students haven't read anything this month?" or "Are there overdue books?"
- **Content Moderation** — Three-layer safety stack: zero-cost profanity filter (better-profanity) catches obvious violations instantly, DeepTeam guardrails handle nuanced input/output safety, and the LangGraph agent provides final-layer reasoning. Review moderation uses Gemini to flag toxicity, spoilers, off-topic content, and age-inappropriate themes.
- **Book Circulation** — Checkout, return, and renew books. Tracks overdue items with alerts on the dashboard.
- **Analytics Dashboard** — Metrics for book trends, student engagement, circulation health, recommendation quality, and LLM token cost tracking.
- **Book Management** — Add, edit, and delete catalog entries. Manage review approvals with AI-assisted flag indicators.

### Safety and Compliance
- **COPPA/FERPA compliant** — No PII sent to the LLM. Student IDs are anonymous UUIDs. Role-based access control separates student and librarian capabilities.
- **Zero-cost content filtering** — Profanity is caught before any API call, costing zero tokens and sub-millisecond latency.
- **DeepTeam guardrails** — Prompt injection detection, topical enforcement, toxicity filtering, and privacy guards on every LLM interaction.
- **AI review moderation** — Automated scanning for bullying, spoilers, off-topic content, and age-inappropriate themes with librarian override.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Google Gemini 2.5 Flash |
| Agent Framework | LangGraph (with tool-calling, checkpointing) |
| Backend | FastAPI + SQLAlchemy + Pydantic |
| Frontend | Streamlit (multi-page app) |
| Database | SQLite |
| Vector Store | ChromaDB + sentence-transformers/all-MiniLM-L6-v2 |
| Guardrails | DeepTeam + better-profanity |
| Observability | LangSmith (optional) |

## Project Structure

```
LitEngage/
├── backend/
│   ├── main.py                  # FastAPI application entry point
│   ├── config.py                # Pydantic settings from .env
│   ├── routers/
│   │   ├── admin.py             # Analytics, alerts, token usage
│   │   ├── auth.py              # Login / role-based auth
│   │   ├── books.py             # Book catalog CRUD + search
│   │   ├── chat.py              # Student & librarian chat endpoints
│   │   ├── gamification.py      # Streaks, goals, badges, leaderboard
│   │   ├── loans.py             # Book checkout / return / renew
│   │   ├── recommendations.py   # Recommendation log + feedback
│   │   ├── reviews.py           # Student reviews + AI moderation
│   │   └── students.py          # Student profiles + reading history
│   ├── services/
│   │   ├── agent.py             # LangGraph agent with 6 tools
│   │   ├── gemini_client.py     # Gemini LLM wrapper
│   │   ├── guardrails.py        # DeepTeam safety layer
│   │   ├── moderation.py        # AI review scanning via Gemini
│   │   ├── profanity_filter.py  # Zero-cost profanity pre-check
│   │   ├── vector_store.py      # ChromaDB semantic search
│   │   └── recommendation_engine.py
│   ├── database/
│   │   ├── connection.py        # SQLAlchemy engine setup
│   │   ├── models.py            # ORM models (Books, Students, Loans, Reviews, ...)
│   │   └── crud.py              # Database operations
│   └── schemas/                 # Pydantic request/response models
├── frontend/
│   ├── Home.py                  # Streamlit entry point with role routing
│   ├── pages/
│   │   ├── 1_Student_Dashboard.py
│   │   ├── 2_Book_Catalog.py
│   │   ├── 3_Student_Chat.py
│   │   ├── 4_Librarian_Dashboard.py
│   │   ├── 5_Book_Management.py
│   │   └── 6_Librarian_Chat.py
│   └── utils/
│       ├── api_client.py        # httpx client for FastAPI
│       └── auth.py              # Session-based auth
├── scripts/                     # Database setup, seeding, and migration scripts
├── data/                        # SQLite DB, ChromaDB, raw datasets (gitignored)
├── .env.example                 # Environment variable template
├── requirements.txt
└── CLAUDE.md                    # Detailed architecture reference
```

## Getting Started

### Prerequisites

- Python 3.11+
- A Google Gemini API key ([get one here](https://aistudio.google.com/app/apikey))

### 1. Clone and set up the environment

```bash
git clone <repo-url> && cd LitEngage
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:
- `GOOGLE_API_KEY` — your Gemini API key
- `SECRET_KEY` — generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`

### 3. Download the dataset

Download the **Young Adult** dataset files from the [UCSD Book Graph](https://cseweb.ucsd.edu/~jmcauley/datasets/goodreads.html):

- `goodreads_books_young_adult.json`
- `goodreads_interactions_young_adult.json`
- `goodreads_reviews_young_adult.json`

Place all three in `data/raw/`.

### 4. Initialize the database and load data

```bash
# Create tables
python scripts/init_db.py

# Load and filter books (5K+ curated from 93K)
python scripts/load_books.py

# Generate ChromaDB embeddings (~10-20 min)
python scripts/generate_embeddings.py

# Create student accounts
python scripts/create_sample_students.py
python scripts/create_additional_students.py
python scripts/create_user_accounts.py

# Seed demo data
python scripts/seed_reading_history.py
python scripts/seed_student_reviews.py
python scripts/seed_recommendations.py
python scripts/seed_loans.py
python scripts/seed_emma_progress.py

# Run migrations (adds moderation + loan columns)
python scripts/migrate_add_columns.py
python scripts/migrate_add_loans_and_moderation.py
```

### 5. Start the application

Open two terminals:

```bash
# Terminal 1 — FastAPI backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — Streamlit frontend
streamlit run frontend/Home.py
```

Open http://localhost:8501 in your browser.

### Demo accounts

| Username | Password | Role |
|----------|----------|------|
| `student` | `student123` | Student (Emma Watson) |
| `librarian` | `librarian123` | Librarian |

## Demo: Review Moderation

A script is included to inject realistic problematic reviews for demonstrating the AI moderation pipeline:

```bash
# Inject 8 problematic reviews (toxicity, spoilers, off-topic, etc.)
python scripts/demo_problematic_reviews.py

# Then in the Streamlit UI:
# 1. Log in as librarian
# 2. Go to Book Management > Review Moderation tab
# 3. Click "Scan All Pending" to trigger AI moderation
# 4. Watch reviews get flagged with specific categories and AI reasoning

# Revert to original reviews when done
python scripts/demo_problematic_reviews.py --revert
```

## Architecture

### Content Safety Stack

```
User message
    |
[Layer 1] better-profanity (zero cost, sub-ms)
    |--- Caught --> pre-formatted rejection, ZERO tokens
    |--- Clean ---|
                  v
[Layer 2] DeepTeam guards (prompt injection, topical, toxicity)
    |--- Caught --> pre-formatted rejection, skips agent
    |--- Clean ---|
                  v
[Layer 3] LangGraph agent (full Gemini call with tools)
    |
[Layer 4] Output guards (toxicity, privacy, hallucination)
```

### LangGraph Agent

The agent has access to 6 tools:
- `search_books` — Semantic search via ChromaDB with reading-level filters
- `get_reading_history` — Student's past books and ratings
- `get_book_details` — Full metadata for a specific book
- `save_preference` — Record student preferences for future recommendations
- `scan_reviews` — Query review moderation status (librarian only)
- `check_loans` — Query loan/circulation data (librarian only)

### Review Moderation Pipeline

1. **Profanity pre-check** — Instant rejection if profane language detected (zero cost)
2. **AI scan** — Gemini classifies for toxicity, spoilers, off-topic, and age-inappropriate content
3. **Librarian review** — AI flags are advisory; the librarian makes the final approve/reject decision

## API Documentation

With the backend running, visit http://localhost:8000/docs for the interactive Swagger UI.

Key endpoint groups:
- `/api/chat/` — Student and librarian chat
- `/api/books/` — Catalog search and management
- `/api/students/` — Student profiles and reading history
- `/api/reviews/` — Review CRUD + moderation
- `/api/loans/` — Book circulation (checkout, return, renew)
- `/api/admin/` — Analytics, alerts, token usage
- `/api/gamification/` — Streaks, goals, badges, leaderboard

## Configuration

All configuration is managed through `.env`. See [.env.example](.env.example) for the full list of options including:

- Gemini model selection and temperature
- DeepTeam guardrail toggles and strictness
- ChromaDB embedding model and search parameters
- Rate limiting and caching
- COPPA/FERPA compliance modes
- LangSmith observability

## License

This project was built for educational purposes as part of the MSDS program at the University of San Francisco.
