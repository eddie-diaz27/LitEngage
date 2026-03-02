"""Seed mock book loan data for development/demo purposes.

Creates a mix of active loans, overdue loans, and returned loans
across multiple students for the Librarian Dashboard.
"""

import os
import sys
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from backend.database.connection import SessionLocal
from backend.database.models import Book, BookLoan, Student


def seed_loans():
    db: Session = SessionLocal()

    try:
        students = db.query(Student).all()
        if not students:
            print("No students found. Run seed scripts first.")
            return

        # Get a pool of books
        books = db.query(Book).order_by(Book.ratings_count.desc()).limit(100).all()
        if not books:
            print("No books found. Run load_books.py first.")
            return

        # Clear existing loans
        existing = db.query(BookLoan).count()
        if existing > 0:
            db.query(BookLoan).delete()
            db.commit()
            print(f"Cleared {existing} existing loans.")

        now = datetime.utcnow()
        loans_created = 0

        # For each student, create some loans
        for student in students:
            sample_books = random.sample(books, min(8, len(books)))

            # 2-3 active loans (not overdue)
            for book in sample_books[:3]:
                checked_out = now - timedelta(days=random.randint(1, 10))
                due = checked_out + timedelta(days=14)
                loan = BookLoan(
                    student_id=student.id,
                    book_id=book.id,
                    checked_out_at=checked_out,
                    due_date=due,
                    returned_at=None,
                    renewed_count=0,
                )
                db.add(loan)
                loans_created += 1

            # 1 overdue loan per student
            overdue_book = sample_books[3]
            checked_out = now - timedelta(days=random.randint(20, 35))
            due = checked_out + timedelta(days=14)  # Due date already passed
            loan = BookLoan(
                student_id=student.id,
                book_id=overdue_book.id,
                checked_out_at=checked_out,
                due_date=due,
                returned_at=None,
                renewed_count=random.randint(0, 1),
            )
            db.add(loan)
            loans_created += 1

            # 2-3 returned loans (history)
            for book in sample_books[4:7]:
                checked_out = now - timedelta(days=random.randint(30, 90))
                due = checked_out + timedelta(days=14)
                returned = checked_out + timedelta(days=random.randint(7, 20))
                loan = BookLoan(
                    student_id=student.id,
                    book_id=book.id,
                    checked_out_at=checked_out,
                    due_date=due,
                    returned_at=returned,
                    renewed_count=0,
                )
                db.add(loan)
                loans_created += 1

        db.commit()

        # Report
        active = db.query(BookLoan).filter(BookLoan.returned_at == None).count()
        overdue = (
            db.query(BookLoan)
            .filter(BookLoan.returned_at == None, BookLoan.due_date < now)
            .count()
        )
        returned = db.query(BookLoan).filter(BookLoan.returned_at != None).count()

        print(f"\nSeeded {loans_created} loans:")
        print(f"  Active (not overdue): {active - overdue}")
        print(f"  Overdue: {overdue}")
        print(f"  Returned: {returned}")
        print(f"  Total: {loans_created}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_loans()
