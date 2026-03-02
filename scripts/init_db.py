"""Initialize the database: create all tables and verify."""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect as sa_inspect

from backend.database.connection import Base, engine

# Import all models so they register with Base.metadata
from backend.database.models import (  # noqa: F401
    Achievement,
    Book,
    BookReview,
    ChatMessage,
    ChatSession,
    ReadingGoal,
    ReadingHistory,
    RecommendationLog,
    Student,
    StudentReview,
    TokenUsage,
    UserAccount,
)


def init_database():
    """Create all database tables."""
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)

    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    # Verify tables
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()

    print(f"\nDatabase initialized successfully!")
    print(f"Tables created ({len(tables)}):")
    for table in sorted(tables):
        columns = [col["name"] for col in inspector.get_columns(table)]
        print(f"  - {table}: {len(columns)} columns")

    expected = {
        "students",
        "books",
        "reading_history",
        "chat_sessions",
        "chat_messages",
        "recommendations_log",
        "book_reviews",
        "student_reviews",
        "user_accounts",
        "token_usage",
        "achievements",
        "reading_goals",
    }
    missing = expected - set(tables)
    if missing:
        print(f"\nWARNING: Missing tables: {missing}")
    else:
        print(f"\nAll {len(expected)} expected tables present.")


if __name__ == "__main__":
    init_database()
