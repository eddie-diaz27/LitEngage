"""Seed student_reviews for ALL books using Goodreads review data.

Ensures every book in the catalog has at least 1 student review to justify
its rating. Popular books get more reviews. Also creates ReadingHistory
entries and recalculates Book.avg_rating from student reviews.
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

from sqlalchemy import func, text

from backend.database.connection import SessionLocal
from backend.database.models import (
    Book,
    BookReview,
    ReadingHistory,
    Student,
    StudentReview,
)

GENERIC_REVIEWS = [
    "Really enjoyed this book! The characters were relatable and the story kept me hooked.",
    "A great read. I'd recommend it to anyone who enjoys this genre.",
    "Interesting story with some unexpected twists. Couldn't put it down!",
    "Solid book with a compelling narrative. The author's writing style is engaging.",
    "I liked this one a lot. The pacing was good and the ending was satisfying.",
]


def _pick_goodreads_review(db, book_id: str, exclude_review_ids: set = None):
    """Find a quality Goodreads review for a book."""
    query = (
        db.query(BookReview)
        .filter(
            BookReview.book_id == book_id,
            BookReview.review_text.isnot(None),
            BookReview.review_text != "",
            BookReview.rating >= 3,
            func.length(BookReview.review_text) >= 30,
            func.length(BookReview.review_text) <= 2000,
        )
    )
    if exclude_review_ids:
        query = query.filter(BookReview.id.notin_(exclude_review_ids))

    review = query.order_by(BookReview.n_votes.desc().nullslast()).first()
    return review


def _target_reviews(book):
    """Determine how many reviews a book should get."""
    rc = book.ratings_count or 0
    if rc >= 5000:
        return random.randint(3, 5)
    elif rc >= 1000:
        return random.randint(2, 3)
    else:
        return random.randint(1, 2)


def seed_student_reviews():
    db = SessionLocal()

    try:
        students = db.query(Student).all()
        if not students:
            print("No students found. Run create scripts first.")
            sys.exit(1)

        student_ids = [s.id for s in students]
        print(f"Working with {len(student_ids)} students")

        # Clear existing seed data for a clean re-seed
        existing_sr = db.query(StudentReview).count()
        if existing_sr > 0:
            print(f"Clearing {existing_sr} existing student reviews...")
            db.query(StudentReview).delete()
            db.commit()

        # Build lookup of existing reading history to avoid duplicates
        existing_rh = set(
            (rh.student_id, rh.book_id)
            for rh in db.query(
                ReadingHistory.student_id, ReadingHistory.book_id
            ).all()
        )
        print(f"Existing reading history entries: {len(existing_rh)}")

        # Load all books
        all_books = db.query(Book).all()
        print(f"Total books to cover: {len(all_books)}")

        # Track per-student review counts to distribute evenly
        student_review_counts = {sid: 0 for sid in student_ids}
        reviews_created = 0
        history_created = 0
        books_covered = 0

        for idx, book in enumerate(all_books):
            target = _target_reviews(book)
            used_gr_ids = set()  # Avoid reusing same Goodreads review text

            # Pick students with fewest reviews to distribute evenly
            sorted_students = sorted(student_ids, key=lambda s: student_review_counts[s])

            assigned = 0
            for sid in sorted_students:
                if assigned >= target:
                    break

                # Skip if this student already reviewed this book
                if (sid, book.id) in existing_rh:
                    continue

                # Find a Goodreads review for this book
                gr_review = _pick_goodreads_review(db, book.id, exclude_review_ids=used_gr_ids)

                if gr_review:
                    rating = gr_review.rating or random.choices([3, 4, 5], weights=[15, 40, 45])[0]
                    review_text = gr_review.review_text[:500].strip()
                    used_gr_ids.add(gr_review.id)
                else:
                    # No Goodreads review available — use generic
                    rating = random.choices([3, 4, 5], weights=[15, 40, 45])[0]
                    review_text = random.choice(GENERIC_REVIEWS)

                # Create reading history entry if not exists
                if (sid, book.id) not in existing_rh:
                    days_ago = random.randint(14, 365)
                    started = datetime.utcnow() - timedelta(days=days_ago)
                    read_days = random.randint(3, 21)
                    completed = started + timedelta(days=read_days)

                    rh = ReadingHistory(
                        student_id=sid,
                        book_id=book.id,
                        status="completed",
                        rating=rating,
                        started_at=started,
                        completed_at=completed,
                    )
                    db.add(rh)
                    existing_rh.add((sid, book.id))
                    history_created += 1

                # Create student review
                review_date = datetime.utcnow() - timedelta(days=random.randint(1, 300))
                sr = StudentReview(
                    student_id=sid,
                    book_id=book.id,
                    rating=rating,
                    review_text=review_text,
                    is_approved=True,
                    created_at=review_date,
                )
                db.add(sr)
                reviews_created += 1
                student_review_counts[sid] += 1
                assigned += 1

            if assigned > 0:
                books_covered += 1

            # Commit in batches
            if (idx + 1) % 500 == 0:
                db.commit()
                print(f"  Processed {idx + 1}/{len(all_books)} books, {reviews_created} reviews so far...")

        db.commit()
        print(f"\nReviews created: {reviews_created}")
        print(f"Reading history entries created: {history_created}")
        print(f"Books with reviews: {books_covered}/{len(all_books)}")

        # -----------------------------------------------------------------
        # Recalculate avg_rating and ratings_count from student reviews
        # -----------------------------------------------------------------
        print("\nRecalculating book ratings from student reviews...")
        db.execute(text("""
            UPDATE books SET
                avg_rating = (
                    SELECT ROUND(AVG(rating), 2)
                    FROM student_reviews
                    WHERE student_reviews.book_id = books.id
                      AND student_reviews.is_approved = 1
                ),
                ratings_count = (
                    SELECT COUNT(*)
                    FROM student_reviews
                    WHERE student_reviews.book_id = books.id
                      AND student_reviews.is_approved = 1
                )
            WHERE id IN (SELECT DISTINCT book_id FROM student_reviews)
        """))
        db.commit()
        print("Ratings recalculated.")

        # -----------------------------------------------------------------
        # Summary
        # -----------------------------------------------------------------
        total_sr = db.query(StudentReview).count()
        books_with_reviews = db.query(func.count(func.distinct(StudentReview.book_id))).scalar()
        min_reviews = min(student_review_counts.values())
        max_reviews = max(student_review_counts.values())
        avg_reviews = sum(student_review_counts.values()) / len(student_review_counts)

        print(f"\n--- Summary ---")
        print(f"  Total student reviews: {total_sr}")
        print(f"  Books with reviews: {books_with_reviews}/{len(all_books)}")
        print(f"  Reviews per student: min={min_reviews}, max={max_reviews}, avg={avg_reviews:.1f}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_student_reviews()
