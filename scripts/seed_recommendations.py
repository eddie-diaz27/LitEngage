"""Seed recommendations_log table with mock data for dashboard metrics.

Creates recommendation entries for the 15 main students (those with
UserAccounts) so the librarian dashboard shows non-zero metrics for
Recommendations (Week), Positive Feedback, and Negative Feedback.
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

from backend.database.connection import SessionLocal
from backend.database.models import (
    ReadingHistory,
    RecommendationLog,
    StudentReview,
    UserAccount,
)

EXPLANATIONS = [
    "Based on your interest in fantasy and adventure, here are some exciting picks!",
    "Since you enjoyed similar books, I think you'll love these recommendations.",
    "These books match your reading level and favorite genres perfectly.",
    "I found some great options that other students in your grade loved.",
    "Here are some popular titles that match your reading preferences.",
]


def seed_recommendations():
    db = SessionLocal()

    try:
        # Only seed for students with UserAccounts (the 15 main students)
        accounts = (
            db.query(UserAccount)
            .filter(UserAccount.role == "student", UserAccount.student_id.isnot(None))
            .all()
        )

        if not accounts:
            print("No student accounts found. Run create_user_accounts.py first.")
            sys.exit(1)

        # Check if already seeded
        existing = db.query(RecommendationLog).count()
        if existing > 0:
            print(f"Already have {existing} recommendation logs. Clearing for re-seed...")
            db.query(RecommendationLog).delete()
            db.commit()

        created = 0
        thumbs_up = 0
        thumbs_down = 0
        this_week = 0

        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)

        for account in accounts:
            sid = account.student_id

            # Get this student's reading history for book IDs
            history = (
                db.query(ReadingHistory)
                .filter(ReadingHistory.student_id == sid, ReadingHistory.status == "completed")
                .limit(20)
                .all()
            )
            if len(history) < 3:
                continue

            book_ids = [h.book_id for h in history]

            # Get average review rating for this student to determine feedback tendency
            avg_rating_result = (
                db.query(StudentReview)
                .filter(StudentReview.student_id == sid)
                .all()
            )
            avg_rating = (
                sum(r.rating for r in avg_rating_result) / len(avg_rating_result)
                if avg_rating_result else 4.0
            )

            # Create 2-4 recommendation entries
            num_recs = random.randint(2, 4)
            for i in range(num_recs):
                # Pick 2-3 books for this recommendation
                rec_books = random.sample(book_ids, min(3, len(book_ids)))

                # Determine feedback based on student's general satisfaction
                if avg_rating >= 4.0:
                    feedback = random.choices(
                        ["thumbs_up", "thumbs_down", None],
                        weights=[70, 5, 25],
                    )[0]
                elif avg_rating >= 3.0:
                    feedback = random.choices(
                        ["thumbs_up", "thumbs_down", None],
                        weights=[40, 20, 40],
                    )[0]
                else:
                    feedback = random.choices(
                        ["thumbs_up", "thumbs_down", None],
                        weights=[10, 50, 40],
                    )[0]

                # Spread dates: some recent (within 7 days), some older
                if i == 0 and random.random() < 0.7:
                    days_ago = random.randint(0, 6)  # Within this week
                else:
                    days_ago = random.randint(0, 30)

                created_at = now - timedelta(days=days_ago, hours=random.randint(0, 23))

                rec = RecommendationLog(
                    student_id=sid,
                    book_ids_json=rec_books,
                    explanation=random.choice(EXPLANATIONS),
                    model_used="gemini-2.0-flash-exp",
                    reading_level_filter=account.student.reading_level if account.student else None,
                    feedback=feedback,
                    created_at=created_at,
                )
                db.add(rec)
                created += 1

                if feedback == "thumbs_up":
                    thumbs_up += 1
                elif feedback == "thumbs_down":
                    thumbs_down += 1
                if created_at >= week_ago:
                    this_week += 1

        db.commit()

        print(f"\n--- Recommendation Logs Seeded ---")
        print(f"  Total entries: {created}")
        print(f"  This week: {this_week}")
        print(f"  Thumbs up: {thumbs_up}")
        print(f"  Thumbs down: {thumbs_down}")
        print(f"  No feedback: {created - thumbs_up - thumbs_down}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_recommendations()
