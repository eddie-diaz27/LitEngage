"""SQLAlchemy ORM models for the LitEngage database."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

from backend.database.connection import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(String, primary_key=True)  # UUID
    name = Column(String, nullable=False)
    grade_level = Column(Integer)  # 1-12
    reading_level = Column(String)  # early-reader, elementary, middle-school, high-school
    preferences_json = Column(JSON)  # {favorite_genres: [], disliked_themes: [], ...}
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime)
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    streak_last_date = Column(DateTime, nullable=True)

    reading_history = relationship("ReadingHistory", back_populates="student")
    chat_sessions = relationship("ChatSession", back_populates="student")
    student_reviews = relationship("StudentReview", back_populates="student")
    achievements = relationship("Achievement", back_populates="student")
    reading_goals = relationship("ReadingGoal", back_populates="student")


class Book(Base):
    __tablename__ = "books"

    id = Column(String, primary_key=True)  # book_id from dataset
    isbn = Column(String, unique=True, index=True, nullable=True)
    isbn13 = Column(String, nullable=True)
    title = Column(String, nullable=False, index=True)
    title_without_series = Column(String, nullable=True)
    author = Column(String, nullable=False, index=True)
    author_name = Column(String, nullable=True)  # Human-readable author name
    authors_json = Column(JSON)  # Full authors list [{author_id, role}]
    description = Column(Text, nullable=True)
    genres_json = Column(JSON)  # Extracted from popular_shelves
    popular_shelves_json = Column(JSON)  # Full popular_shelves data
    similar_books_json = Column(JSON)  # List of similar book_ids
    reading_level = Column(String, index=True, default="middle-school")
    age_appropriate = Column(String, default="12-18")
    publication_year = Column(Integer, index=True, nullable=True)
    publication_month = Column(Integer, nullable=True)
    publication_day = Column(Integer, nullable=True)
    publisher = Column(String, nullable=True)
    format = Column(String, nullable=True)  # Paperback, Hardcover, etc.
    num_pages = Column(Integer, nullable=True)
    language_code = Column(String, default="eng")
    country_code = Column(String, nullable=True)
    avg_rating = Column(Float, index=True, nullable=True)
    ratings_count = Column(Integer, index=True, nullable=True)
    text_reviews_count = Column(Integer, nullable=True)
    image_url = Column(String, nullable=True)
    goodreads_link = Column(String, nullable=True)
    series_json = Column(JSON)  # Series IDs
    created_at = Column(DateTime, default=datetime.utcnow)

    reviews = relationship("BookReview", back_populates="book")
    student_reviews = relationship("StudentReview", back_populates="book")


class ReadingHistory(Base):
    __tablename__ = "reading_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"), index=True)
    book_id = Column(String, ForeignKey("books.id"), index=True)
    status = Column(String)  # reading, completed, wishlist, abandoned
    rating = Column(Integer, nullable=True)  # 1-5
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    student = relationship("Student", back_populates="reading_history")
    book = relationship("Book")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"), index=True)
    thread_id = Column(String, unique=True, index=True)  # For LangGraph persistence
    created_at = Column(DateTime, default=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)

    student = relationship("Student", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), index=True)
    role = Column(String)  # user, assistant, system
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


class RecommendationLog(Base):
    __tablename__ = "recommendations_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"), index=True)
    book_ids_json = Column(JSON)  # List of recommended book IDs
    explanation = Column(Text, nullable=True)
    model_used = Column(String, nullable=True)
    reading_level_filter = Column(String, nullable=True)
    genres_searched = Column(JSON, nullable=True)
    feedback = Column(String, nullable=True)  # thumbs_up, thumbs_down
    created_at = Column(DateTime, default=datetime.utcnow)


class BookReview(Base):
    __tablename__ = "book_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(String, unique=True, index=True)
    user_id = Column(String, index=True)  # Anonymized user from dataset
    book_id = Column(String, ForeignKey("books.id"), index=True)
    rating = Column(Integer, nullable=True)  # 1-5
    review_text = Column(Text, nullable=True)
    date_added = Column(DateTime, nullable=True)
    date_updated = Column(DateTime, nullable=True)
    n_votes = Column(Integer, nullable=True)
    n_comments = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    sentiment = Column(String, nullable=True)  # positive, negative, neutral
    themes_extracted_json = Column(JSON, nullable=True)

    book = relationship("Book", back_populates="reviews")


# ---------------------------------------------------------------------------
# New tables for frontend overhaul
# ---------------------------------------------------------------------------


class StudentReview(Base):
    """Student-authored reviews (separate from Goodreads book_reviews)."""
    __tablename__ = "student_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"), index=True)
    book_id = Column(String, ForeignKey("books.id"), index=True)
    rating = Column(Integer, nullable=False)  # 1-5
    review_text = Column(Text, nullable=True)
    is_approved = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)

    # AI moderation fields
    moderation_status = Column(String, default="pending")  # pending, clean, flagged
    moderation_flags = Column(JSON, nullable=True)  # ["toxicity", "spoiler", ...]
    moderation_reason = Column(Text, nullable=True)  # AI explanation
    moderated_at = Column(DateTime, nullable=True)

    student = relationship("Student", back_populates="student_reviews")
    book = relationship("Book", back_populates="student_reviews")

    __table_args__ = (
        UniqueConstraint("student_id", "book_id", name="uq_student_book_review"),
    )


class BookLoan(Base):
    """Physical book loan tracking (checkout/return/renew)."""
    __tablename__ = "book_loans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"), index=True)
    book_id = Column(String, ForeignKey("books.id"), index=True)
    checked_out_at = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, nullable=False, index=True)
    returned_at = Column(DateTime, nullable=True, index=True)
    renewed_count = Column(Integer, default=0)
    notes = Column(Text, nullable=True)

    student = relationship("Student")
    book = relationship("Book")


class UserAccount(Base):
    """Authentication accounts for students and librarians."""
    __tablename__ = "user_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # "student" or "librarian"
    student_id = Column(String, ForeignKey("students.id"), nullable=True)
    display_name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student")


class TokenUsage(Base):
    """Per-request LLM token tracking and cost estimation."""
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=True, index=True)
    request_type = Column(String, nullable=False)  # chat, auto_recommendation, librarian_analysis
    model_used = Column(String, nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Integer, default=0)
    tools_used = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Achievement(Base):
    """Gamification badges earned by students."""
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"), index=True)
    badge_type = Column(String, nullable=False)  # bookworm, genre_explorer, review_star, streak_master, goal_achiever
    badge_name = Column(String, nullable=False)
    badge_level = Column(Integer, default=1)  # 1, 2, 3
    earned_at = Column(DateTime, default=datetime.utcnow)
    metadata_json = Column(JSON, nullable=True)

    student = relationship("Student", back_populates="achievements")

    __table_args__ = (
        UniqueConstraint("student_id", "badge_type", "badge_level", name="uq_student_badge"),
    )


class ReadingGoal(Base):
    """Monthly reading targets for students."""
    __tablename__ = "reading_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"), index=True)
    month = Column(Integer, nullable=False)  # 1-12
    year = Column(Integer, nullable=False)
    target_books = Column(Integer, nullable=False, default=3)
    books_completed = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="reading_goals")

    __table_args__ = (
        UniqueConstraint("student_id", "month", "year", name="uq_student_month_goal"),
    )
