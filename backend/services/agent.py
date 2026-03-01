"""LangGraph agent for book recommendations.

Defines the StateGraph, tools, nodes, and edges for the
conversational book recommendation agent.
"""

import logging
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
                "author": entry.book.author if entry.book else "Unknown",
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

    db = SessionLocal()
    try:
        book = crud.get_book(db, book_id)
        if not book:
            return {"error": f"Book with ID {book_id} not found"}
        return {
            "book_id": book.id,
            "title": book.title,
            "author": book.author,
            "description": (book.description or "")[:500],
            "genres": book.genres_json or [],
            "avg_rating": book.avg_rating,
            "ratings_count": book.ratings_count,
            "publication_year": book.publication_year,
            "num_pages": book.num_pages,
            "image_url": book.image_url,
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

AGENT_TOOLS = [search_books, get_reading_history, get_book_details, save_preference]


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

    try:
        result = await graph.ainvoke(initial_state, config=config)

        # Extract the last AI message (skip tool-call-only messages)
        ai_message = ""
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

        logger.info(
            "Agent invocation complete",
            extra={
                "student_id": student_id,
                "session_id": session_id,
                "message_length": len(message),
                "response_length": len(ai_message),
            },
        )

        return {
            "message": ai_message,
            "session_id": session_id,
        }

    except Exception as e:
        logger.error(f"Agent invocation failed: {e}", exc_info=True)
        return {
            "message": (
                "I'm sorry, I'm having trouble right now. "
                "Could you try asking again?"
            ),
            "session_id": session_id,
        }
