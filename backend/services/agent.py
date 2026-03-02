"""LangGraph agent for book recommendations.

Defines the StateGraph, tools, nodes, and edges for the
conversational book recommendation agent.
"""

import logging
import time
from typing import Annotated, List, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from backend.config import settings
from backend.services.gemini_client import get_llm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State Schema
# ---------------------------------------------------------------------------

class BookAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    student_id: str
    user_preferences: Optional[dict]
    reading_history: Optional[list]
    search_results: Optional[list]
    recommendations: Optional[list]
    metadata: Optional[dict]


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a friendly, knowledgeable school librarian helping students find books they'll love. Your goal is to:

1. Understand the student's reading preferences through conversation
2. Use tools to search the library catalog based on their interests, reading level, and past reading history
3. Recommend 2-3 books that match their preferences, with brief, engaging explanations
4. Encourage reading by highlighting what makes each book exciting or interesting

Important guidelines:
- ALWAYS use the search_books tool to find books - never make up book titles or details
- ALWAYS filter by the student's reading level - never recommend books above or below their level
- Check the student's reading history to avoid recommending books they've already read
- Keep explanations brief and enthusiastic (2-3 sentences per book)
- Encourage diversity - suggest books from different genres when appropriate
- If you can't find good matches, say so honestly and ask about alternative preferences

You can ONLY help with book recommendations and library questions. Politely redirect any off-topic queries.

Current student reading level: {reading_level}
Current student grade: {grade_level}
"""


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def search_books(
    query: str,
    reading_level: str = "middle-school",
    genres: Optional[List[str]] = None,
    max_results: int = 10,
) -> list:
    """Search the library book catalog using semantic similarity.

    Use this to find books matching a student's interests, reading level, and
    preferred genres.

    Args:
        query: Natural language description of what the student wants
            (e.g., "exciting adventure with magic and dragons")
        reading_level: The student's reading level. One of: early-reader,
            elementary, middle-school, high-school
        genres: Optional list of genre filters (e.g., ["fantasy", "adventure"])
        max_results: Number of books to return (default 10)

    Returns:
        List of matching books with title, author, description, and rating.
    """
    from backend.services.vector_store import get_vector_store_service

    vs = get_vector_store_service()
    results = vs.search_books(
        query=query,
        reading_level=reading_level,
        genres=genres,
        k=max_results,
    )
    logger.info(
        f"search_books: query='{query[:50]}', level={reading_level}, "
        f"results={len(results)}"
    )
    return results


@tool
def get_reading_history(student_id: str, limit: int = 20) -> list:
    """Get a student's reading history - books they have read, are currently
    reading, or have on their wishlist.

    Use this to understand what the student has already read and avoid
    recommending duplicates.

    Args:
        student_id: The student's unique identifier
        limit: Maximum number of history entries to return
    """
    from backend.database.connection import SessionLocal
    from backend.database import crud

    db = SessionLocal()
    try:
        history = crud.get_reading_history(db, student_id, limit)
        return [
            {
                "book_id": entry.book_id,
                "title": entry.book.title if entry.book else "Unknown",
                "author": (entry.book.author_name or entry.book.author) if entry.book else "Unknown",
                "status": entry.status,
                "rating": entry.rating,
            }
            for entry in history
        ]
    finally:
        db.close()


@tool
def get_book_details(book_id: str) -> dict:
    """Get complete details for a specific book by its ID.

    Use this when you need full information about a book, including
    description, genres, and rating.

    Args:
        book_id: The book's unique identifier
    """
    from backend.database.connection import SessionLocal
    from backend.database import crud

    from backend.database.models import StudentReview

    db = SessionLocal()
    try:
        book = crud.get_book(db, book_id)
        if not book:
            return {"error": f"Book with ID {book_id} not found"}

        # Fetch recent student reviews for context
        reviews = (
            db.query(StudentReview)
            .filter(
                StudentReview.book_id == book_id,
                StudentReview.is_approved == True,
            )
            .order_by(StudentReview.created_at.desc())
            .limit(3)
            .all()
        )

        return {
            "book_id": book.id,
            "title": book.title,
            "author": book.author_name or book.author,
            "description": (book.description or "")[:500],
            "genres": book.genres_json or [],
            "avg_rating": book.avg_rating,
            "ratings_count": book.ratings_count,
            "publication_year": book.publication_year,
            "num_pages": book.num_pages,
            "image_url": book.image_url,
            "review_count": len(reviews),
            "recent_reviews": [
                {"rating": r.rating, "snippet": (r.review_text or "")[:150]}
                for r in reviews
            ],
        }
    finally:
        db.close()


@tool
def save_preference(
    student_id: str, preference_type: str, value: str
) -> dict:
    """Save a student's reading preference for future recommendations.

    Args:
        student_id: The student's unique identifier
        preference_type: Type of preference. One of: favorite_genre,
            disliked_genre, favorite_theme, reading_pace
        value: The preference value (e.g., "fantasy", "slow-paced")
    """
    from backend.database.connection import SessionLocal
    from backend.database import crud

    db = SessionLocal()
    try:
        student = crud.get_student(db, student_id)
        if not student:
            return {"error": "Student not found"}

        prefs = student.preferences_json or {}
        key = f"{preference_type}s"  # e.g., "favorite_genres"
        if key not in prefs:
            prefs[key] = []

        if isinstance(prefs[key], list) and value not in prefs[key]:
            prefs[key].append(value)
        else:
            prefs[key] = value

        crud.update_student_preferences(db, student_id, prefs)
        return {"status": "saved", "preference_type": preference_type, "value": value}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# All tools list
# ---------------------------------------------------------------------------

@tool
def scan_reviews(status_filter: str = "flagged", limit: int = 10) -> list:
    """Query student reviews by moderation status.

    Use this to find reviews that need librarian attention — flagged by AI
    moderation, or still pending review.

    Args:
        status_filter: Filter by moderation status. One of: flagged, pending,
            clean, all. Default is "flagged" to show problematic reviews.
        limit: Maximum number of reviews to return (default 10).

    Returns:
        List of reviews with moderation details (flags, reason, student, book).
    """
    from backend.database.connection import SessionLocal
    from backend.database.models import StudentReview

    db = SessionLocal()
    try:
        query = db.query(StudentReview)
        if status_filter != "all":
            query = query.filter(StudentReview.moderation_status == status_filter)
        reviews = (
            query.order_by(StudentReview.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "review_id": r.id,
                "student_name": r.student.name if r.student else "Unknown",
                "book_title": r.book.title if r.book else "Unknown",
                "rating": r.rating,
                "review_text": (r.review_text or "")[:200],
                "moderation_status": r.moderation_status,
                "moderation_flags": r.moderation_flags or [],
                "moderation_reason": r.moderation_reason or "",
                "is_approved": r.is_approved,
            }
            for r in reviews
        ]
    finally:
        db.close()


@tool
def check_loans(query_type: str = "overdue", student_id: str = None) -> dict:
    """Check the status of book loans in the library.

    Use this to find overdue books, see active checkouts, or look up a
    specific student's loans.

    Args:
        query_type: Type of loan query. One of:
            - "overdue" — books past their due date (default)
            - "active" — all currently checked-out books
            - "summary" — counts of active, overdue, due today, due this week
            - "student" — loans for a specific student (requires student_id)
        student_id: Required when query_type is "student". The student's ID.

    Returns:
        Loan information depending on query_type.
    """
    from datetime import datetime, timedelta
    from backend.database.connection import SessionLocal
    from backend.database.models import BookLoan

    db = SessionLocal()
    try:
        now = datetime.utcnow()

        if query_type == "summary":
            active = db.query(BookLoan).filter(BookLoan.returned_at == None).all()
            overdue = [l for l in active if l.due_date < now]
            today_end = now.replace(hour=23, minute=59, second=59)
            due_today = [l for l in active if l.due_date <= today_end and l.due_date >= now]
            week_end = now + timedelta(days=7)
            due_this_week = [l for l in active if now <= l.due_date <= week_end]
            return {
                "total_active": len(active),
                "overdue": len(overdue),
                "due_today": len(due_today),
                "due_this_week": len(due_this_week),
            }

        if query_type == "student" and student_id:
            loans = (
                db.query(BookLoan)
                .filter(BookLoan.student_id == student_id, BookLoan.returned_at == None)
                .order_by(BookLoan.due_date.asc())
                .all()
            )
        elif query_type == "overdue":
            loans = (
                db.query(BookLoan)
                .filter(BookLoan.returned_at == None, BookLoan.due_date < now)
                .order_by(BookLoan.due_date.asc())
                .limit(20)
                .all()
            )
        else:  # active
            loans = (
                db.query(BookLoan)
                .filter(BookLoan.returned_at == None)
                .order_by(BookLoan.due_date.asc())
                .limit(20)
                .all()
            )

        return {
            "query_type": query_type,
            "count": len(loans),
            "loans": [
                {
                    "loan_id": l.id,
                    "student_name": l.student.name if l.student else "Unknown",
                    "book_title": l.book.title if l.book else "Unknown",
                    "checked_out": str(l.checked_out_at.date()) if l.checked_out_at else "",
                    "due_date": str(l.due_date.date()) if l.due_date else "",
                    "days_overdue": max(0, (now - l.due_date).days) if l.due_date < now else 0,
                    "renewed_count": l.renewed_count,
                }
                for l in loans
            ],
        }
    finally:
        db.close()


AGENT_TOOLS = [search_books, get_reading_history, get_book_details, save_preference, scan_reviews, check_loans]


# ---------------------------------------------------------------------------
# Graph Nodes
# ---------------------------------------------------------------------------

def agent_node(state: BookAgentState) -> dict:
    """Invoke the LLM with tools and student context."""
    prefs = state.get("user_preferences") or {}
    reading_level = prefs.get("reading_level", "middle-school")
    grade_level = prefs.get("grade_level", 8)

    system_msg = SystemMessage(
        content=SYSTEM_PROMPT.format(
            reading_level=reading_level,
            grade_level=grade_level,
        )
    )

    llm = get_llm(with_tools=AGENT_TOOLS)
    messages = [system_msg] + state["messages"]
    response = llm.invoke(messages)

    return {"messages": [response]}


def should_continue(state: BookAgentState) -> str:
    """Route based on whether the LLM wants to call tools."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"


# ---------------------------------------------------------------------------
# Graph Construction
# ---------------------------------------------------------------------------

def build_graph():
    """Build the LangGraph StateGraph for the book recommendation agent."""
    tool_node = ToolNode(AGENT_TOOLS)

    workflow = StateGraph(BookAgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END},
    )
    workflow.add_edge("tools", "agent")

    # Compile with in-memory persistence (conversation state within session)
    checkpointer = MemorySaver()
    compiled = workflow.compile(checkpointer=checkpointer)

    return compiled


# Lazy singleton
_graph = None


def get_graph():
    """Get or create the singleton agent graph."""
    global _graph
    if _graph is None:
        _graph = build_graph()
        logger.info("LangGraph agent initialized")
    return _graph


# ---------------------------------------------------------------------------
# Agent Invocation
# ---------------------------------------------------------------------------

async def invoke_agent(
    student_id: str,
    message: str,
    session_id: str,
    student_data: Optional[dict] = None,
) -> dict:
    """Invoke the agent with a student message.

    Args:
        student_id: Student's unique identifier.
        message: The student's message.
        session_id: Session identifier for thread persistence.
        student_data: Optional dict with reading_level, grade_level, preferences.

    Returns:
        Dict with 'message' (str) and optional 'recommendations' (list).
    """
    graph = get_graph()
    thread_id = f"student_{student_id}_{session_id}"
    config = {"configurable": {"thread_id": thread_id}}

    # Build user preferences from student data
    user_preferences = {}
    if student_data:
        user_preferences = {
            "reading_level": student_data.get("reading_level", "middle-school"),
            "grade_level": student_data.get("grade_level", 8),
            "preferences": student_data.get("preferences_json", {}),
        }

    initial_state = {
        "messages": [HumanMessage(content=message)],
        "student_id": student_id,
        "user_preferences": user_preferences,
    }

    start_time = time.time()

    try:
        result = await graph.ainvoke(initial_state, config=config)

        latency_ms = int((time.time() - start_time) * 1000)

        # Extract the last AI message and token usage info
        ai_message = ""
        total_prompt_tokens = 0
        total_completion_tokens = 0
        tools_used = []

        for msg in result["messages"]:
            if isinstance(msg, AIMessage):
                # Collect tool call names
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                        if tool_name and tool_name not in tools_used:
                            tools_used.append(tool_name)

                # Collect token usage from usage_metadata
                usage = getattr(msg, "usage_metadata", None)
                if usage:
                    total_prompt_tokens += usage.get("input_tokens", 0) if isinstance(usage, dict) else getattr(usage, "input_tokens", 0)
                    total_completion_tokens += usage.get("output_tokens", 0) if isinstance(usage, dict) else getattr(usage, "output_tokens", 0)

        # Extract the last AI message text (skip tool-call-only messages)
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage):
                content = msg.content
                # Handle list-type content (Gemini may return structured parts)
                if isinstance(content, list):
                    text_parts = [
                        p.get("text", "") if isinstance(p, dict) else str(p)
                        for p in content
                    ]
                    content = "\n".join(p for p in text_parts if p)
                if content and len(content) > 1:
                    ai_message = content
                    break

        total_tokens = total_prompt_tokens + total_completion_tokens

        logger.info(
            "Agent invocation complete",
            extra={
                "student_id": student_id,
                "session_id": session_id,
                "message_length": len(message),
                "response_length": len(ai_message),
                "latency_ms": latency_ms,
                "total_tokens": total_tokens,
                "tools_used": tools_used,
            },
        )

        return {
            "message": ai_message,
            "session_id": session_id,
            "token_usage": {
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens,
            },
            "latency_ms": latency_ms,
            "tools_used": tools_used,
            "model_used": settings.gemini_model,
        }

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Agent invocation failed: {e}", exc_info=True)
        return {
            "message": (
                "I'm sorry, I'm having trouble right now. "
                "Could you try asking again?"
            ),
            "session_id": session_id,
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "latency_ms": latency_ms,
            "tools_used": [],
            "model_used": settings.gemini_model,
        }
