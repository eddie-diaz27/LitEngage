"""Migration: Add book_loans table and moderation columns to student_reviews.

Safely adds new tables/columns without destroying existing data.
Follows the pattern from migrate_add_columns.py.
"""

import os
import sys
import sqlite3

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

    print("Running loans & moderation migration...\n")

    # --- 1. Add moderation columns to student_reviews ---
    print("1. Adding moderation columns to 'student_reviews' table:")
    add_column_if_missing(cursor, "student_reviews", "moderation_status", "TEXT", "'pending'")
    add_column_if_missing(cursor, "student_reviews", "moderation_flags", "JSON")
    add_column_if_missing(cursor, "student_reviews", "moderation_reason", "TEXT")
    add_column_if_missing(cursor, "student_reviews", "moderated_at", "DATETIME")

    # Set existing reviews to 'clean' (they were manually managed before)
    cursor.execute("""
        UPDATE student_reviews
        SET moderation_status = 'clean'
        WHERE moderation_status IS NULL OR moderation_status = 'pending'
    """)
    updated = cursor.rowcount
    print(f"  Set {updated} existing reviews to 'clean' status")

    # --- 2. Create book_loans table ---
    print("\n2. Creating book_loans table:")
    create_table_if_missing(cursor, "book_loans", """
        CREATE TABLE book_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id VARCHAR NOT NULL REFERENCES students(id),
            book_id VARCHAR NOT NULL REFERENCES books(id),
            checked_out_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            due_date DATETIME NOT NULL,
            returned_at DATETIME,
            renewed_count INTEGER DEFAULT 0,
            notes TEXT,
            UNIQUE(student_id, book_id, checked_out_at)
        )
    """)

    # --- 3. Create indexes ---
    print("\n3. Creating indexes:")
    indexes = [
        ("idx_book_loans_student", "book_loans", "student_id"),
        ("idx_book_loans_book", "book_loans", "book_id"),
        ("idx_book_loans_due_date", "book_loans", "due_date"),
        ("idx_book_loans_returned", "book_loans", "returned_at"),
        ("idx_student_reviews_moderation", "student_reviews", "moderation_status"),
    ]

    for idx_name, table, column in indexes:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
            print(f"  Index: {idx_name}")
        except sqlite3.OperationalError:
            print(f"  Index already exists: {idx_name}")

    conn.commit()

    # --- 4. Verify ---
    print("\n4. Verification:")
    tables = get_existing_tables(cursor)
    print(f"  book_loans: {'OK' if 'book_loans' in tables else 'MISSING'}")

    review_cols = get_existing_columns(cursor, "student_reviews")
    for col in ["moderation_status", "moderation_flags", "moderation_reason", "moderated_at"]:
        print(f"  student_reviews.{col}: {'OK' if col in review_cols else 'MISSING'}")

    conn.close()
    print("\nMigration complete!")


if __name__ == "__main__":
    migrate()
