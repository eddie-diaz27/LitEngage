# CLAUDE.md - Library Engagement Agent Codebase Guide

## Project Overview

**School Library Book Recommendation Agent** - An AI-powered conversational system that mimics a helpful librarian, providing personalized book recommendations to students based on their reading history, preferences, and appropriate reading levels.

**Tech Stack:**
- **LLM:** Google Gemini 2.5 Flash (configurable)
- **Framework:** LangGraph for agentic workflows
- **Frontend:** Streamlit (multi-page app)
- **Backend:** FastAPI with Pydantic
- **Database:** SQLite for local development
- **Vector Store:** ChromaDB for semantic book search
- **Embeddings:** sentence-transformers/all-MiniLM-L6-v2
- **Guardrails:** DeepTeam for safety and compliance
- **Deployment:** GCP Cloud Run (planned)

---

## Architecture Overview

### High-Level Flow
```
Student → Streamlit UI → FastAPI Backend → LangGraph Agent → Gemini LLM
                                        ↓
                              ChromaDB (book embeddings)
                                        ↓
                              SQLite (students, books, history)
```

### Three-Layer Architecture

1. **Presentation Layer (Streamlit)**
   - `frontend/Home.py` - Main entry point
   - `frontend/pages/Student_Chat.py` - Student conversation interface
   - `frontend/pages/Librarian_Dashboard.py` - Admin/monitoring view
   - `frontend/pages/Book_Catalog.py` - Browse books
   - Thin client - only UI rendering, calls FastAPI for all logic

2. **Business Logic Layer (FastAPI)**
   - `backend/main.py` - FastAPI application
   - `backend/routers/` - API endpoint definitions
   - `backend/services/` - Core business logic (LangGraph agent, recommendations)
   - `backend/database/` - SQLAlchemy models and DB connection
   - Handles all LLM calls, guardrails, database operations

3. **Data Layer**
   - SQLite database (`data/library.db`)
   - ChromaDB vector store (`data/chroma_books_db/`)
   - Book dataset files (`data/raw/`, `data/processed/`)

---

## Project Structure

```
school-library-recommender/
├── backend/
│   ├── main.py                         # FastAPI app entry point
│   ├── config.py                       # Pydantic settings from .env
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── chat.py                     # Chat endpoints
│   │   ├── recommendations.py          # Recommendation endpoints
│   │   ├── students.py                 # Student profile management
│   │   └── books.py                    # Book catalog endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── agent.py                    # LangGraph agent definition
│   │   ├── gemini_client.py            # Gemini LLM wrapper
│   │   ├── guardrails.py               # DeepTeam guardrails setup
│   │   ├── embeddings.py               # Embedding generation
│   │   ├── vector_store.py             # ChromaDB interface
│   │   └── recommendation_engine.py    # Core recommendation logic
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py               # SQLAlchemy engine setup
│   │   ├── models.py                   # SQLAlchemy ORM models
│   │   └── crud.py                     # Database operations
│   └── schemas/
│       ├── __init__.py
│       ├── chat.py                     # Chat request/response models
│       ├── student.py                  # Student schemas
│       ├── book.py                     # Book schemas
│       └── recommendation.py           # Recommendation schemas
├── frontend/
│   ├── Home.py                         # Streamlit entry (landing page)
│   ├── pages/
│   │   ├── 1_Student_Chat.py           # Main chat interface
│   │   ├── 2_Librarian_Dashboard.py    # Admin dashboard
│   │   └── 3_Book_Catalog.py           # Browse books
│   ├── components/
│   │   ├── __init__.py
│   │   ├── chat_interface.py           # Reusable chat UI components
│   │   └── book_card.py                # Book display component
│   └── utils/
│       ├── __init__.py
│       ├── api_client.py               # httpx client for FastAPI
│       └── auth.py                     # Streamlit authentication
├── data/
│   ├── raw/                            # Downloaded datasets
│   │   ├── goodreads_books.json        # UCSD Book Graph
│   │   └── goodreads_interactions.csv
│   ├── processed/                      # Cleaned/enriched data
│   │   └── school_catalog.json
│   ├── library.db                      # SQLite database
│   └── chroma_books_db/                # ChromaDB vector store
├── scripts/
│   ├── init_db.py                      # Create database schema
│   ├── load_books.py                   # Load book dataset into DB
│   ├── generate_embeddings.py          # Create ChromaDB embeddings
│   ├── create_sample_students.py       # Generate mock student accounts
│   └── seed_reading_history.py         # Populate sample interactions
├── tests/
│   ├── test_agent.py
│   ├── test_recommendations.py
│   └── test_guardrails.py
├── .env.example                        # Environment variables template
├── .env                                # Actual config (DO NOT COMMIT)
├── .gitignore
├── requirements.txt
├── README.md
├── CLAUDE.md                           # This file
└── docker-compose.yml                  # Local development setup

```

---

## Core Components Deep Dive

### 1. LangGraph Agent (`backend/services/agent.py`)

**Purpose:** Orchestrates the conversation flow, tool usage, and recommendation generation.

**State Schema:**
```python
class BookAgentState(TypedDict):
    messages: Annotated[List, add_messages]  # Conversation history
    user_preferences: Optional[dict]          # Extracted preferences
    recommendations: Optional[list]           # Current recommendations
    student_id: str                           # Student identifier
    reading_history: Optional[list]           # Past books read
    search_results: Optional[list]            # Current book candidates
```

**Graph Nodes:**
1. `agent_node` - LLM with tools (search_books, get_reading_history, save_preference)
2. `tool_node` - Executes tool calls
3. `guardrail_node` - DeepTeam safety checks
4. `librarian_review_node` - Human-in-the-loop (optional interrupt)

**Tools Available:**
- `search_books(query, reading_level, genres)` - Semantic search in ChromaDB
- `get_book_details(book_id)` - Full book metadata
- `get_reading_history(student_id)` - Past interactions
- `save_recommendation(student_id, book_ids, explanation)` - Log recommendation

**Persistence:**
- Checkpointer: `SqliteSaver` (stores in `data/library.db`)
- Store: `InMemoryStore` (for development) or `PostgresStore` (production)
- Thread ID: `f"student_{student_id}_{session_id}"`

### 2. Guardrails System (`backend/services/guardrails.py`)

**Input Guardrails:**
- `PromptInjectionGuard()` - Detects jailbreak attempts
- `TopicalGuard(allowed_topics=["books", "reading", "library", ...])` - Keeps on topic

**Output Guardrails:**
- `ToxicityGuard()` - Blocks harmful content
- `PrivacyGuard()` - Prevents PII exposure
- `HallucinationGuard()` - Flags fabricated information

**Fallback Messages:**
- Input breach: "I can only help with book recommendations and library questions!"
- Output breach: "Let me try rephrasing that recommendation..."
- After 3 retries: "I'm having trouble with that request. Would you like me to suggest something different?"

### 3. Database Models (`backend/database/models.py`)

**Tables:**
```python
# Students: id, name, grade_level, reading_level, preferences_json, created_at
# Books: id, isbn, title, author, description, genres_json, reading_level, age_appropriate, themes_json, publication_year, avg_rating
# ReadingHistory: id, student_id, book_id, status (reading/completed/wishlist), rating, started_at, completed_at
# ChatSessions: id, student_id, thread_id, created_at, last_message_at
# ChatMessages: id, session_id, role, content, timestamp
# RecommendationsLog: id, student_id, book_ids_json, explanation, model_used, feedback, created_at
# BookReviews: id, review_id, user_id, book_id, rating, review_text, date_added, sentiment, themes_extracted_json
```

### 4. Vector Store (`backend/services/vector_store.py`)

**Embedding Strategy:**
- Document text: `"{title} by {author}. {description} Genres: {genres}. Themes: {themes}."`
- Metadata: `{book_id, reading_level, age_range, publication_year, genres}`
- Model: `sentence-transformers/all-MiniLM-L6-v2` (384 dims, CPU-friendly)

**Search Strategy:**
```python
# 1. Filter by reading level and age
# 2. Semantic similarity search (MMR for diversity)
# 3. Re-rank by collaborative filtering signals if available
vectorstore.max_marginal_relevance_search(
    query=student_query,
    k=10,
    fetch_k=30,
    lambda_mult=0.7,  # 70% relevance, 30% diversity
    filter={"reading_level": student_reading_level}
)
```

---

## Key Workflows

### Student Recommendation Flow

1. **Student opens chat** → Streamlit calls `/api/chat/sessions` (POST) to create session
2. **Student asks** "Can you recommend an adventure book?" 
3. **Streamlit** → POST `/api/chat/message` with message and student_id
4. **FastAPI backend:**
   - Input guardrails check (DeepTeam)
   - Invoke LangGraph agent with message
   - Agent reasons: "Need to search for adventure books at this student's reading level"
   - Agent calls `search_books` tool
   - Tool queries ChromaDB with filters
   - Agent evaluates results, picks top 3
   - Agent generates explanation
   - Output guardrails check
   - Save to RecommendationsLog
5. **Response streamed** back to Streamlit
6. **Student sees** 3 books with friendly explanations
7. **Student provides feedback** → POST `/api/recommendations/{rec_id}/feedback`

### Librarian Dashboard Flow

1. **Librarian logs in** → `streamlit-authenticator` checks credentials
2. **Dashboard loads** → GET `/api/analytics/overview`
   - Total recommendations this week
   - Most popular genres
   - Student engagement metrics
3. **Librarian reviews** recent recommendations → GET `/api/recommendations/recent`
4. **Librarian can:**
   - Override recommendations
   - Add books to catalog
   - View individual student reading profiles (FERPA-compliant)

---

## Configuration Management

**Environment Variables (`.env`):**
```
# Gemini API
GOOGLE_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash-exp  # or gemini-2.0-pro

# DeepTeam
DEEPTEAM_API_KEY=your_key_here  # if using hosted service
DEEPTEAM_MODEL=gemini-2.0-flash-exp

# Database
DATABASE_URL=sqlite:///./data/library.db

# ChromaDB
CHROMA_PERSIST_DIRECTORY=./data/chroma_books_db

# FastAPI
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:8501,http://localhost:3000

# Streamlit
STREAMLIT_SERVER_PORT=8501
BACKEND_API_URL=http://localhost:8000

# LangSmith (optional monitoring)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=library-agent

# Security
SECRET_KEY=generate_random_secret_key_here
```

**Loading config:** Use `pydantic-settings` in `backend/config.py`

---

## Development Workflow

### Initial Setup
```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy environment template
cp .env.example .env
# Edit .env with your API keys

# 4. Download dataset (see Dataset section below)
# Place in data/raw/

# 5. Initialize database
python scripts/init_db.py

# 6. Load books
python scripts/load_books.py

# 7. Generate embeddings
python scripts/generate_embeddings.py

# 8. Create sample students
python scripts/create_sample_students.py
```

### Running Locally
```bash
# Terminal 1 - Start FastAPI backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 - Start Streamlit frontend
streamlit run frontend/Home.py
```

### Testing
```bash
pytest tests/ -v --cov=backend
```

---

## Dataset Information

**Primary Source: UCSD Goodreads Young Adult Dataset (ALL THREE COMPONENTS)**

Download from: https://cseweb.ucsd.edu/~jmcauley/datasets/goodreads.html

**Three dataset files (all required):**

1. **goodreads_books_young_adult.json** (~93K books, ~500-800 MB uncompressed)
   - Complete book metadata: titles, authors, descriptions, ratings, genres, publication info
   - Rich fields: popular_shelves (user-generated tags), similar_books, series info
   
2. **goodreads_interactions_young_adult.json** (~35M interactions, ~4-6 GB uncompressed)
   - User-book interactions: ratings (1-5), is_read status, dates
   - Enables collaborative filtering: "students who liked X also liked Y"
   
3. **goodreads_reviews_young_adult.json** (~2.4M reviews, ~2-3 GB uncompressed)
   - Detailed text reviews with ratings
   - Sentiment analysis, theme extraction, understanding why students like/dislike books

**Preprocessing Strategy (3-Stage Filtering to 5-10K Books):**

The data loading process (`scripts/load_books.py`) implements three-stage filtering:

**Stage 1: Filter Books**
- Load all 93K books from newline-delimited JSON
- Apply quality filters:
  * `ratings_count >= 200` (well-known, popular books)
  * `average_rating >= 3.8` (high quality threshold)
  * `publication_year >= 1990` (modern + recent classics)
  * `language_code == 'eng'` (English only)
  * `description` exists and non-empty (required for embeddings)
- Sort by `ratings_count` descending (most popular first)
- Take top 5,000-10,000 books
- Extract genres from `popular_shelves` (top 5 shelf names become genres)
- Extract primary author from `authors` list
- Store selected `book_id`s in a set for next stages
- Insert into Books table

**Stage 2: Filter Interactions**
- Read interactions JSON line-by-line (memory efficient for 35M records)
- Keep only interactions where `book_id` is in selected books set
- Parse date strings to datetime objects
- Map anonymized `user_id`s to synthetic student profiles
- Result: ~500K-2M filtered interactions (manageable size)
- Used for collaborative filtering algorithms

**Stage 3: Filter Reviews**
- Read reviews JSON line-by-line
- Keep only reviews where `book_id` is in selected books set
- Keep only reviews with non-empty `review_text`
- Result: ~100K-400K filtered reviews
- Store in BookReviews table for future sentiment analysis

**Dataset Schema:**

Books JSON (newline-delimited):
- book_id, isbn, isbn13, title, authors (list), description
- average_rating, ratings_count, text_reviews_count
- popular_shelves (list of {name, count}), similar_books (list of IDs)
- publication_year/month/day, publisher, format, num_pages
- language_code, country_code, image_url, link

Interactions JSON (newline-delimited):
- user_id, book_id, is_read, rating (1-5), is_reviewed
- date_added, date_updated

Reviews JSON (newline-delimited):
- user_id, book_id, review_id, rating (1-5), review_text
- date_added, date_updated, n_votes, n_comments
- started_at, read_at

**Processing Pipeline:**

1. Run `scripts/load_books.py`:
   - Filters and loads 5-10K books into Books table
   - Filters and stores interactions for collaborative filtering
   - Filters and stores reviews for sentiment analysis

2. Run `scripts/generate_embeddings.py`:
   - Creates embeddings for 5-10K books (10-20 minutes)
   - Populates ChromaDB collection

3. Run `scripts/create_sample_students.py`:
   - Creates mock student accounts from filtered interactions data

This filtered subset provides:
- High-quality, popular books students will recognize
- Sufficient interaction data for collaborative filtering
- Review data for understanding book appeal
- Fast development iteration (embeddings, queries, testing)
- Can scale to full dataset later without code changes

---

## Safety and Compliance

### COPPA Compliance
- **No PII to Gemini API:** Only reading preferences, grade level (never names, emails)
- **Student IDs:** Use anonymous UUIDs, not real student identifiers
- **Parental consent:** School acts as consent provider under educational exception

### FERPA Compliance
- **Data minimization:** Only store necessary educational records
- **Access control:** Role-based auth (student vs librarian)
- **Audit logging:** Track all recommendations and searches

### DeepTeam Guardrails
- **Always active** on every LLM interaction
- **Logs all breaches** for review
- **Automatic fallbacks** prevent unsafe responses from reaching students

---

## Monitoring and Observability

**LangSmith Integration:**
- Trace every agent invocation
- Track tool usage patterns
- Monitor latency and token usage
- Debug failed recommendations

**Custom Metrics:**
- Recommendations per student per week
- Feedback scores (thumbs up/down)
- Guardrail breach rate
- Most recommended books/genres
- Reading level distribution

**Dashboards:**
- Streamlit librarian dashboard shows weekly trends
- LangSmith shows LLM performance
- FastAPI `/metrics` endpoint (optional Prometheus)

---

## Deployment Checklist

**Pre-Production:**
- [ ] Environment variables secured (use Secret Manager)
- [ ] Database backed up daily
- [ ] HTTPS/TLS enabled
- [ ] Rate limiting configured
- [ ] Error monitoring (Sentry or Cloud Error Reporting)
- [ ] COPPA/FERPA compliance documented
- [ ] Librarian training completed

**GCP Cloud Run:**
- [ ] Dockerfile created
- [ ] Cloud Build configured
- [ ] Cloud SQL for production database (or managed SQLite)
- [ ] Cloud Storage for dataset backups
- [ ] IAM roles configured (least privilege)
- [ ] Billing alerts set ($10, $25, $50)

---

## Common Tasks for AI Code Assistant

### Adding a new book field
1. Update `backend/database/models.py` - add column to Books model
2. Create Alembic migration: `alembic revision --autogenerate -m "add_field"`
3. Update `backend/schemas/book.py` - add field to Pydantic model
4. Update embedding generation in `backend/services/embeddings.py`
5. Regenerate embeddings: `python scripts/generate_embeddings.py --force`

### Adding a new guardrail
1. Import guard in `backend/services/guardrails.py`
2. Add to `input_guards` or `output_guards` list
3. Update fallback messages if needed
4. Test with `pytest tests/test_guardrails.py`

### Adding a new tool for the agent
1. Define tool function in `backend/services/agent.py`
2. Add `@tool` decorator with clear description
3. Bind tool to LLM in agent node
4. Update state schema if tool needs new state fields
5. Add integration test

### Changing the LLM model
1. Update `GEMINI_MODEL` in `.env`
2. Restart FastAPI backend
3. Monitor LangSmith for quality changes
4. Update cost estimates in documentation

---

## Troubleshooting

**Agent not calling tools:**
- Check tool descriptions are clear and specific
- Verify tools are bound to LLM in agent node
- Check LangSmith trace to see LLM's reasoning

**Guardrails too strict:**
- Adjust thresholds in guard initialization
- Use `sample_rate` parameter to reduce checks
- Review logs to identify false positives

**Slow recommendations:**
- Enable semantic caching (Redis or GPTCache)
- Reduce `fetch_k` in vector search
- Use Gemini Flash instead of Pro
- Profile with LangSmith to find bottleneck

**ChromaDB errors:**
- Ensure `data/chroma_books_db/` exists and is writable
- Check embedding dimensions match (384 for all-MiniLM-L6-v2)
- Regenerate embeddings if model changed

---

## Current Status

**✅ Completed:**
- Project structure defined
- Requirements.txt created
- Environment template created
- Architecture documented

**🚧 In Progress:**
- Initial database schema
- Basic LangGraph agent
- FastAPI backend structure
- Streamlit frontend scaffold

**📋 TODO:**
- Load UCSD book dataset
- Generate ChromaDB embeddings
- Implement DeepTeam guardrails
- Create sample students
- End-to-end testing
- Librarian dashboard
- Deployment configuration

---

## Quick Reference Commands

```bash
# Start development environment
make dev              # or manually start FastAPI + Streamlit

# Database operations
python scripts/init_db.py           # Create tables
python scripts/load_books.py        # Import books
python scripts/generate_embeddings.py  # Create vectors

# Testing
pytest tests/                       # Run all tests
pytest tests/test_agent.py -v      # Test agent specifically

# Linting and formatting
black backend/ frontend/            # Format code
ruff check backend/                 # Lint code

# Production
docker-compose up                   # Full stack locally
gcloud run deploy                   # Deploy to Cloud Run
```

---

## Need Help?

**Documentation:**
- LangGraph: https://langchain-ai.github.io/langgraph/
- Gemini API: https://ai.google.dev/docs
- DeepTeam: https://www.trydeepteam.com/docs
- Streamlit: https://docs.streamlit.io

**AI Assistant Instructions:**
- For code generation: Reference this file for project structure
- For new features: Update relevant sections above
- For debugging: Check Troubleshooting section first
- Always maintain COPPA/FERPA compliance in any student-facing code
