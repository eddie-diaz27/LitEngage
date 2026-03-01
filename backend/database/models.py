"""SQLAlchemy ORM models for the LitEngage database."""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
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

    reading_history = relationship("ReadingHistory", back_populates="student")
    chat_sessions = relationship("ChatSession", back_populates="student")


class Book(Base):
    __tablename__ = "books"

    id = Column(String, primary_key=True)  # book_id from dataset
    isbn = Column(String, unique=True, index=True, nullable=True)
    isbn13 = Column(String, nullable=True)
    title = Column(String, nullable=False, index=True)
    title_without_series = Column(String, nullable=True)
    author = Column(String, nullable=False, index=True)
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
