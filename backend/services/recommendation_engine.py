"""Recommendation logging and analytics."""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from backend.database import crud

logger = logging.getLogger(__name__)


def log_recommendation(
    db: Session,
    student_id: str,
    book_ids: list,
    explanation: str,
    model_used: str,
    reading_level: str = None,
    genres: list = None,
) -> int:
    """Log a recommendation to the database.

    Returns the recommendation log ID.
    """
    rec = crud.create_recommendation_log(
        db,
        {
            "student_id": student_id,
            "book_ids_json": book_ids,
            "explanation": explanation,
            "model_used": model_used,
            "reading_level_filter": reading_level,
            "genres_searched": genres,
            "created_at": datetime.utcnow(),
        },
    )
    logger.info(
        "Recommendation logged",
        extra={
            "rec_id": rec.id,
            "student_id": student_id,
            "books": book_ids,
        },
    )
    return rec.id
