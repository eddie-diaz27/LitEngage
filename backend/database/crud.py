"""Database CRUD operations for all models."""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database.models import (
    Book,
    BookReview,
    ChatMessage,
    ChatSession,
    ReadingHistory,
    RecommendationLog,
    Student,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------


def create_book(db: Session, book_data: dict) -> Book:
    book = Book(**book_data)
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def bulk_create_books(db: Session, books: List[dict], batch_size: int = 1000) -> int:
    """Insert books in batches. Returns total inserted count."""
    total = 0
    for i in range(0, len(books), batch_size):
        batch = books[i : i + batch_size]
        db.bulk_insert_mappings(Book, batch)
        db.commit()
        total += len(batch)
    return total


def get_book(db: Session, book_id: str) -> Optional[Book]:
    return db.query(Book).filter(Book.id == book_id).first()


def get_books_paginated(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    reading_level: Optional[str] = None,
    genre: Optional[str] = None,
    min_rating: Optional[float] = None,
    sort_by: str = "ratings_count",
    sort_order: str = "desc",
) -> tuple:
    """Return (books, total_count) with optional filters."""
    query = db.query(Book)

    if reading_level:
        query = query.filter(Book.reading_level == reading_level)
    if min_rating:
        query = query.filter(Book.avg_rating >= min_rating)

    total = query.count()

    sort_col = getattr(Book, sort_by, Book.ratings_count)
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    books = query.offset(skip).limit(limit).all()
    return books, total


def get_book_count(db: Session) -> int:
    return db.query(func.count(Book.id)).scalar()


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------


def create_student(db: Session, student_data: dict) -> Student:
    student = Student(**student_data)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def get_student(db: Session, student_id: str) -> Optional[Student]:
    return db.query(Student).filter(Student.id == student_id).first()


def get_students(db: Session) -> List[Student]:
    return db.query(Student).order_by(Student.name).all()


def update_student_preferences(
    db: Session, student_id: str, preferences: dict
) -> Optional[Student]:
    student = get_student(db, student_id)
    if not student:
        return None
    student.preferences_json = preferences
    student.last_active = datetime.utcnow()
    db.commit()
    db.refresh(student)
    return student


# ---------------------------------------------------------------------------
# Reading History
# ---------------------------------------------------------------------------


def create_reading_history_entry(db: Session, entry: dict) -> ReadingHistory:
    record = ReadingHistory(**entry)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_reading_history(
    db: Session, student_id: str, limit: int = 20
) -> List[ReadingHistory]:
    return (
        db.query(ReadingHistory)
        .filter(ReadingHistory.student_id == student_id)
        .order_by(ReadingHistory.completed_at.desc().nullslast())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Chat Sessions & Messages
# ---------------------------------------------------------------------------


def create_chat_session(db: Session, student_id: str, thread_id: str) -> ChatSession:
    session = ChatSession(
        student_id=student_id,
        thread_id=thread_id,
        created_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_chat_session(db: Session, session_id: int) -> Optional[ChatSession]:
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()


def get_chat_session_by_thread(db: Session, thread_id: str) -> Optional[ChatSession]:
    return db.query(ChatSession).filter(ChatSession.thread_id == thread_id).first()


def get_chat_sessions_by_student(
    db: Session, student_id: str
) -> List[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.student_id == student_id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )


def create_chat_message(
    db: Session, session_id: int, role: str, content: str
) -> ChatMessage:
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        timestamp=datetime.utcnow(),
    )
    db.add(message)
    # Also update the session's last_message_at
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session:
        session.last_message_at = datetime.utcnow()
    db.commit()
    db.refresh(message)
    return message


def delete_chat_session(db: Session, session_id: int) -> bool:
    session = get_chat_session(db, session_id)
    if not session:
        return False
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.delete(session)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def create_recommendation_log(db: Session, data: dict) -> RecommendationLog:
    log = RecommendationLog(**data)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def update_recommendation_feedback(
    db: Session, rec_id: int, feedback: str
) -> Optional[RecommendationLog]:
    rec = db.query(RecommendationLog).filter(RecommendationLog.id == rec_id).first()
    if not rec:
        return None
    rec.feedback = feedback
    db.commit()
    db.refresh(rec)
    return rec


def get_recent_recommendations(
    db: Session, limit: int = 20
) -> List[RecommendationLog]:
    return (
        db.query(RecommendationLog)
        .order_by(RecommendationLog.created_at.desc())
        .limit(limit)
        .all()
    )


def get_recommendation_analytics(db: Session) -> dict:
    """Aggregate recommendation metrics for the dashboard."""
    from datetime import timedelta

    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    total = db.query(func.count(RecommendationLog.id)).scalar()
    this_week = (
        db.query(func.count(RecommendationLog.id))
        .filter(RecommendationLog.created_at >= week_ago)
        .scalar()
    )
    thumbs_up = (
        db.query(func.count(RecommendationLog.id))
        .filter(RecommendationLog.feedback == "thumbs_up")
        .scalar()
    )
    thumbs_down = (
        db.query(func.count(RecommendationLog.id))
        .filter(RecommendationLog.feedback == "thumbs_down")
        .scalar()
    )
    active_students = (
        db.query(func.count(func.distinct(RecommendationLog.student_id)))
        .filter(RecommendationLog.created_at >= week_ago)
        .scalar()
    )

    return {
        "total_recommendations": total,
        "recommendations_this_week": this_week,
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "active_students_this_week": active_students,
    }


# ---------------------------------------------------------------------------
# Book Reviews
# ---------------------------------------------------------------------------


def bulk_create_reviews(
    db: Session, reviews: List[dict], batch_size: int = 1000
) -> int:
    """Insert reviews in batches. Returns total inserted count."""
    total = 0
    for i in range(0, len(reviews), batch_size):
        batch = reviews[i : i + batch_size]
        db.bulk_insert_mappings(BookReview, batch)
        db.commit()
        total += len(batch)
    return total


def get_review_count(db: Session) -> int:
    return db.query(func.count(BookReview.id)).scalar()
