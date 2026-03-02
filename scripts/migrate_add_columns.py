"""Migration script to add new tables and columns to existing database.

Safely adds new tables/columns without destroying existing data.
Uses raw ALTER TABLE since we're not using Alembic.
"""

import os
import sys
import sqlite3

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "library.db")


def get_existing_columns(cursor, table_name):
    """Get set of column names for a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def get_existing_tables(cursor):
    """Get set of existing table names."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cursor.fetchall()}


def add_column_if_missing(cursor, table, column, col_type, default=None):
    """Add a column to a table if it doesn't exist."""
    existing = get_existing_columns(cursor, table)
    if column not in existing:
        default_clause = f" DEFAULT {default}" if default is not None else ""
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}")
        print(f"  Added column: {table}.{column}")
    else:
        print(f"  Column already exists: {table}.{column}")


def create_table_if_missing(cursor, table_name, create_sql):
    """Create a table if it doesn't exist."""
    tables = get_existing_tables(cursor)
    if table_name not in tables:
        cursor.execute(create_sql)
        print(f"  Created table: {table_name}")
    else:
        print(f"  Table already exists: {table_name}")


def migrate():
    """Run all migrations."""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        print("Run scripts/init_db.py first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Running database migrations...\n")

    # --- Add new columns to existing tables ---
    print("1. Adding new columns to 'students' table:")
    add_column_if_missing(cursor, "students", "current_streak", "INTEGER", 0)
    add_column_if_missing(cursor, "students", "longest_streak", "INTEGER", 0)
    add_column_if_missing(cursor, "students", "streak_last_date", "DATETIME")

    print("\n2. Adding new columns to 'books' table:")
    add_column_if_missing(cursor, "books", "author_name", "TEXT")

    # --- Create new tables ---
    print("\n3. Creating new tables:")

    create_table_if_missing(cursor, "student_reviews", """
        CREATE TABLE student_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id VARCHAR NOT NULL REFERENCES students(id),
            book_id VARCHAR NOT NULL REFERENCES books(id),
            rating INTEGER NOT NULL,
            review_text TEXT,
            is_approved BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            UNIQUE(student_id, book_id)
        )
    """)

    create_table_if_missing(cursor, "user_accounts", """
        CREATE TABLE user_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR NOT NULL UNIQUE,
            hashed_password VARCHAR NOT NULL,
            role VARCHAR NOT NULL,
            student_id VARCHAR REFERENCES students(id),
            display_name VARCHAR NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            last_login DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    create_table_if_missing(cursor, "token_usage", """
        CREATE TABLE token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id VARCHAR REFERENCES students(id),
            request_type VARCHAR NOT NULL,
            model_used VARCHAR,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            estimated_cost_usd REAL DEFAULT 0.0,
            latency_ms INTEGER DEFAULT 0,
            tools_used JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    create_table_if_missing(cursor, "achievements", """
        CREATE TABLE achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id VARCHAR NOT NULL REFERENCES students(id),
            badge_type VARCHAR NOT NULL,
            badge_name VARCHAR NOT NULL,
            badge_level INTEGER DEFAULT 1,
            earned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            metadata_json JSON,
            UNIQUE(student_id, badge_type, badge_level)
        )
    """)

    create_table_if_missing(cursor, "reading_goals", """
        CREATE TABLE reading_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id VARCHAR NOT NULL REFERENCES students(id),
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            target_books INTEGER NOT NULL DEFAULT 3,
            books_completed INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, month, year)
        )
    """)

    # --- Create indexes ---
    print("\n4. Creating indexes:")
    indexes = [
        ("idx_student_reviews_student", "student_reviews", "student_id"),
        ("idx_student_reviews_book", "student_reviews", "book_id"),
        ("idx_user_accounts_username", "user_accounts", "username"),
        ("idx_token_usage_student", "token_usage", "student_id"),
        ("idx_token_usage_created", "token_usage", "created_at"),
        ("idx_achievements_student", "achievements", "student_id"),
        ("idx_reading_goals_student", "reading_goals", "student_id"),
    ]

    for idx_name, table, column in indexes:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
            print(f"  Index: {idx_name}")
        except sqlite3.OperationalError:
            print(f"  Index already exists: {idx_name}")

    conn.commit()

    # --- Verify ---
    print("\n5. Verification:")
    tables = get_existing_tables(cursor)
    expected_new = {"student_reviews", "user_accounts", "token_usage", "achievements", "reading_goals"}
    for t in sorted(expected_new):
        status = "OK" if t in tables else "MISSING"
        print(f"  {t}: {status}")

    conn.close()
    print("\nMigration complete!")


if __name__ == "__main__":
    migrate()
