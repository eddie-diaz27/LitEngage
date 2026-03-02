"""Auto-recommendation service.

Generates personalized book recommendations for a student by
loading their profile + reading history and invoking the agent
with a preset prompt.  Includes an in-memory cache so the dashboard
loads instantly after the first generation.
"""

import logging
import re
import time

from backend.config import settings
from backend.database.connection import SessionLocal
from backend.database import crud
from backend.database.models import Book, TokenUsage

logger = logging.getLogger(__name__)

# Simple in-memory cache: {student_id: {"result": dict, "ts": float}}
_rec_cache: dict[str, dict] = {}
_CACHE_TTL_SECONDS = 60 * 30  # 30 minutes


async def generate_auto_recommendations(
    student_id: str, count: int = 3, *, force_refresh: bool = False,
) -> dict:
    """Generate auto-recommendations for a student.

    Args:
        student_id: The student's ID.
        count: Number of recommendations to generate (default 3).
        force_refresh: If True, bypass the cache.

    Returns:
        Dict with 'recommendations' list and token usage info.
    """
    # Check cache first (unless force refresh)
    if not force_refresh and student_id in _rec_cache:
        cached = _rec_cache[student_id]
        if time.time() - cached["ts"] < _CACHE_TTL_SECONDS:
            logger.info(f"Returning cached recommendations for {student_id}")
            return cached["result"]

    from backend.services.agent import invoke_agent

    db = SessionLocal()
    try:
        student = crud.get_student(db, student_id)
        if not student:
            return {"recommendations": [], "error": "Student not found"}

        # Build a rich prompt with student context
        history = crud.get_reading_history(db, student_id, 20)
        read_titles = [
            entry.book.title for entry in history
            if entry.book and entry.status in ("completed", "reading")
        ]
        wishlist_titles = [
            entry.book.title for entry in history
            if entry.book and entry.status == "wishlist"
        ]

        # Extract genres from books they've read for better context
        read_genres: set[str] = set()
        for entry in history:
            if entry.book and entry.book.genres_json:
                read_genres.update(entry.book.genres_json[:3])

        prefs = student.preferences_json or {}
        fav_genres = prefs.get("favorite_genres", [])
        # Merge explicit favorites with genres from reading history
        all_genres = list(dict.fromkeys(fav_genres + sorted(read_genres)))

        prompt_parts = [
            f"Recommend exactly {count} books for me. Be concise and complete.",
            f"I'm in grade {student.grade_level} with a {student.reading_level} reading level.",
        ]
        if all_genres:
            prompt_parts.append(f"I enjoy these genres: {', '.join(all_genres[:8])}.")
        if read_titles:
            prompt_parts.append(f"I've already read: {', '.join(read_titles[:10])}. Do NOT recommend these.")
        if wishlist_titles:
            prompt_parts.append(f"I'm interested in: {', '.join(wishlist_titles[:5])}.")

        prompt_parts.append(
            f"Use the search_books tool to find real books from the catalog. "
            f"Then respond with ONLY the {count} recommendations in this exact format "
            f"(no intro, no outro, just the books):\n\n"
            f"**1. Book Title** by Author Name\n"
            f"One sentence why I'd enjoy it.\n\n"
            f"**2. Book Title** by Author Name\n"
            f"One sentence why I'd enjoy it.\n\n"
            f"**3. Book Title** by Author Name\n"
            f"One sentence why I'd enjoy it."
        )

        prompt = " ".join(prompt_parts)

        # Use a unique session for auto-recommendations
        session_id = f"auto_rec_{student_id}"

        result = await invoke_agent(
            student_id=student_id,
            message=prompt,
            session_id=session_id,
            student_data={
                "reading_level": student.reading_level,
                "grade_level": student.grade_level,
                "preferences_json": student.preferences_json,
            },
        )

        # Save token usage
        token_info = result.get("token_usage", {})
        prompt_tokens = token_info.get("prompt_tokens", 0)
        completion_tokens = token_info.get("completion_tokens", 0)

        cost = (prompt_tokens / 1_000_000) * 0.15 + (completion_tokens / 1_000_000) * 0.60

        usage = TokenUsage(
            student_id=student_id,
            request_type="auto_recommendation",
            model_used=result.get("model_used", settings.gemini_model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=token_info.get("total_tokens", 0),
            estimated_cost_usd=round(cost, 6),
            latency_ms=result.get("latency_ms", 0),
            tools_used=result.get("tools_used", []),
        )
        db.add(usage)
        db.commit()

        response = {
            "message": result.get("message", ""),
            "session_id": session_id,
            "token_usage": token_info,
            "latency_ms": result.get("latency_ms"),
        }

        # Cache the result
        _rec_cache[student_id] = {"result": response, "ts": time.time()}

        return response

    finally:
        db.close()
