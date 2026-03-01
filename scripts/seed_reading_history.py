"""Seed reading history for sample students from the book catalog."""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

from backend.database.connection import SessionLocal
from backend.database.models import Book, Student
from backend.database import crud


def seed_reading_history():
    db = SessionLocal()

    try:
        students = db.query(Student).all()
        if not students:
            print("No students found. Run create_sample_students.py first.")
            sys.exit(1)

        # Get a pool of popular books to assign
        books = (
            db.query(Book)
            .filter(Book.ratings_count >= 1000)
            .order_by(Book.ratings_count.desc())
            .limit(200)
            .all()
        )

        if not books:
            print("No books found. Run load_books.py first.")
            sys.exit(1)

        print(f"Seeding reading history for {len(students)} students from {len(books)} popular books")

        total_entries = 0

        for student in students:
            # Each student gets 3-8 books
            num_books = random.randint(3, 8)
            selected_books = random.sample(books, min(num_books, len(books)))

            for i, book in enumerate(selected_books):
                # Mix of statuses
                if i == 0:
                    status = "reading"  # Currently reading one
                elif random.random() < 0.1:
                    status = "wishlist"
                else:
                    status = "completed"

                # Generate realistic dates
                days_ago = random.randint(7, 365)
                started = datetime.utcnow() - timedelta(days=days_ago)
                completed = None
                if status == "completed":
                    read_days = random.randint(3, 30)
                    completed = started + timedelta(days=read_days)

                # Ratings skew positive (3-5 stars, mostly 4-5)
                rating = None
                if status == "completed" and random.random() < 0.8:
                    rating = random.choices([3, 4, 5], weights=[15, 40, 45])[0]

                crud.create_reading_history_entry(
                    db,
                    {
                        "student_id": student.id,
                        "book_id": book.id,
                        "status": status,
                        "rating": rating,
                        "started_at": started,
                        "completed_at": completed,
                    },
                )
                total_entries += 1

            print(
                f"  {student.name}: {len(selected_books)} books "
                f"({sum(1 for b in selected_books[:len(selected_books)] if True)} assigned)"
            )

        print(f"\nSeeded {total_entries} reading history entries.")

    finally:
        db.close()


if __name__ == "__main__":
    seed_reading_history()
