"""AI-assisted review moderation using Gemini.

First checks with zero-cost profanity filter, then uses a structured
Gemini call for nuanced content analysis (bullying, spoilers, off-topic).
"""

import json
import logging
import re
from datetime import datetime

from sqlalchemy.orm import Session

from backend.config import settings
from backend.services.profanity_filter import get_profanity_filter

logger = logging.getLogger(__name__)

MODERATION_PROMPT = """You are a school library content moderator. A student in grade {grade_level} submitted a review for the book titled "{book_title}".

<review>
{review_text}
</review>

Classify the review for these issues:
- toxicity: bullying, harassment, hate speech, threats, personal attacks
- spoiler: major plot spoilers that ruin the reading experience
- off_topic: content completely unrelated to the book (social media, ads, personal chat)
- age_inappropriate: themes or language inappropriate for the grade level

Reply with EXACTLY one line of JSON. No explanation, no markdown fences.
If clean: {{"status":"clean","flags":[],"reason":""}}
If problematic: {{"status":"flagged","flags":["toxicity"],"reason":"short explanation"}}"""


def _parse_moderation_json(text: str) -> dict:
    """Extract a JSON object from an LLM response, tolerating common issues."""
    text = text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find a JSON object anywhere in the text
    match = re.search(r'\{[^{}]*"status"\s*:\s*"(?:clean|flagged)"[^{}]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: look for key signals in the raw text
    text_lower = text.lower()
    if '"flagged"' in text_lower or "'flagged'" in text_lower:
        # Try to extract flags
        flags = []
        for flag in ["toxicity", "spoiler", "off_topic", "age_inappropriate"]:
            if flag in text_lower:
                flags.append(flag)
        return {
            "status": "flagged",
            "flags": flags or ["unknown"],
            "reason": "AI flagged this review (response parsing fell back to text matching).",
        }

    if '"clean"' in text_lower or "'clean'" in text_lower:
        return {"status": "clean", "flags": [], "reason": ""}

    # Give up — return pending so it can be retried
    raise ValueError(f"Could not parse moderation response: {text[:200]}")


async def scan_review(
    review_text: str,
    book_title: str = "Unknown",
    student_grade: int = 8,
) -> dict:
    """Scan a single review for content issues.

    Returns:
        {"status": "clean"|"flagged", "flags": [...], "reason": "..."}
    """
    # Layer 1: Zero-cost profanity check
    pf = get_profanity_filter()
    if pf.contains_profanity(review_text):
        return {
            "status": "flagged",
            "flags": ["profanity"],
            "reason": "Review contains profane language.",
        }

    # Layer 2: AI moderation via Gemini
    try:
        from backend.services.gemini_client import get_llm

        llm = get_llm()
        # Escape the review text to avoid prompt injection / quote issues
        safe_review = review_text[:1000].replace('"', "'")
        prompt = MODERATION_PROMPT.format(
            grade_level=student_grade,
            book_title=book_title.replace('"', "'"),
            review_text=safe_review,
        )

        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        result = _parse_moderation_json(content)
        return {
            "status": result.get("status", "clean"),
            "flags": result.get("flags", []),
            "reason": result.get("reason", ""),
        }
    except Exception as e:
        logger.error(f"AI moderation failed: {e}")
        # Fail open — don't block reviews if AI is unavailable
        return {
            "status": "pending",
            "flags": [],
            "reason": f"Auto-scan failed: {str(e)[:100]}",
        }


async def scan_and_update_review(db: Session, review, book_title: str = None, student_grade: int = 8):
    """Scan a review and update its moderation fields in the database."""
    from backend.database.models import Book

    if not book_title and review.book_id:
        book = db.query(Book).filter(Book.id == review.book_id).first()
        book_title = book.title if book else "Unknown"

    result = await scan_review(
        review_text=review.review_text or "",
        book_title=book_title or "Unknown",
        student_grade=student_grade,
    )

    review.moderation_status = result["status"]
    review.moderation_flags = result["flags"]
    review.moderation_reason = result["reason"]
    review.moderated_at = datetime.utcnow()

    if result["status"] == "flagged":
        review.is_approved = False

    db.commit()
    return result


async def scan_pending_reviews(db: Session, limit: int = 50) -> list:
    """Batch scan pending reviews."""
    from backend.database.models import StudentReview

    pending = (
        db.query(StudentReview)
        .filter(StudentReview.moderation_status == "pending")
        .limit(limit)
        .all()
    )

    results = []
    for review in pending:
        result = await scan_and_update_review(db, review)
        results.append({
            "review_id": review.id,
            "student_id": review.student_id,
            "book_id": review.book_id,
            **result,
        })

    return results
