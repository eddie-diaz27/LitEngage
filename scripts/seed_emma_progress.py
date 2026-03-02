"""Seed gamification progress for Emma Johnson (the demo student account).

Gives Emma a realistic reading profile with:
- A current reading streak
- Past monthly reading goals (some achieved)
- Badges earned via the check-badges logic
- A current month goal with partial progress
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

from backend.database.connection import SessionLocal
from backend.database.models import (
    Achievement,
    ReadingGoal,
    ReadingHistory,
    Student,
    StudentReview,
    UserAccount,
)


def seed_emma_progress():
    db = SessionLocal()

    try:
        # Find Emma's student account
        account = (
            db.query(UserAccount)
            .filter(UserAccount.username == "student")
            .first()
        )
        if not account or not account.student_id:
            print("Emma's account not found. Run create_user_accounts.py first.")
            sys.exit(1)

        sid = account.student_id
        student = db.query(Student).filter(Student.id == sid).first()
        print(f"Found Emma: {student.name} (id={sid[:8]}...)")

        # ---------------------------------------------------------------
        # 1. Set a realistic reading streak
        # ---------------------------------------------------------------
        student.current_streak = 12
        student.longest_streak = 18
        student.streak_last_date = datetime.utcnow() - timedelta(hours=6)
        student.last_active = datetime.utcnow() - timedelta(hours=1)
        print(f"  Streak: current=12 days, longest=18 days")

        # ---------------------------------------------------------------
        # 2. Clear existing goals and achievements for clean re-seed
        # ---------------------------------------------------------------
        db.query(ReadingGoal).filter(ReadingGoal.student_id == sid).delete()
        db.query(Achievement).filter(Achievement.student_id == sid).delete()
        db.commit()

        # ---------------------------------------------------------------
        # 3. Create reading goals for past months + current month
        # ---------------------------------------------------------------
        now = datetime.utcnow()

        # Count books completed per month from reading history
        completed = (
            db.query(ReadingHistory)
            .filter(
                ReadingHistory.student_id == sid,
                ReadingHistory.status == "completed",
                ReadingHistory.completed_at.isnot(None),
            )
            .all()
        )
        print(f"  Total completed books: {len(completed)}")

        # Group by month/year
        monthly_counts = {}
        for rh in completed:
            key = (rh.completed_at.year, rh.completed_at.month)
            monthly_counts[key] = monthly_counts.get(key, 0) + 1

        # Create goals for the 6 most recent months
        goals_created = 0
        goals_met = 0
        for months_ago in range(5, -1, -1):
            m = now.month - months_ago
            y = now.year
            while m <= 0:
                m += 12
                y -= 1

            actual = monthly_counts.get((y, m), 0)

            # Set achievable targets for past months
            if months_ago == 0:
                # Current month: set goal with partial progress
                target = 4
                books_done = min(actual, 2)  # Show partial progress
            elif months_ago <= 2:
                target = 3
                books_done = min(actual, target + 1)  # Met recent goals
            else:
                target = 3
                books_done = min(actual, target - 1) if months_ago == 5 else min(actual, target)

            goal = ReadingGoal(
                student_id=sid,
                month=m,
                year=y,
                target_books=target,
                books_completed=max(books_done, 1),
            )
            db.add(goal)
            goals_created += 1
            if goal.books_completed >= goal.target_books:
                goals_met += 1

        db.commit()
        print(f"  Reading goals created: {goals_created} ({goals_met} met)")

        # ---------------------------------------------------------------
        # 4. Award badges based on actual data
        # ---------------------------------------------------------------
        books_completed_count = len(completed)
        review_count = (
            db.query(StudentReview)
            .filter(StudentReview.student_id == sid)
            .count()
        )

        # Count distinct genres
        genres_seen = set()
        for rh in completed:
            if rh.book and rh.book.genres_json:
                genres_seen.update(rh.book.genres_json)

        badge_defs = {
            "bookworm": {
                "metric_val": books_completed_count,
                "levels": [
                    {"threshold": 5, "name": "Bookworm Bronze"},
                    {"threshold": 10, "name": "Bookworm Silver"},
                    {"threshold": 25, "name": "Bookworm Gold"},
                ],
            },
            "genre_explorer": {
                "metric_val": len(genres_seen),
                "levels": [
                    {"threshold": 3, "name": "Genre Explorer Bronze"},
                    {"threshold": 5, "name": "Genre Explorer Silver"},
                    {"threshold": 8, "name": "Genre Explorer Gold"},
                ],
            },
            "review_star": {
                "metric_val": review_count,
                "levels": [
                    {"threshold": 3, "name": "Review Star Bronze"},
                    {"threshold": 10, "name": "Review Star Silver"},
                    {"threshold": 25, "name": "Review Star Gold"},
                ],
            },
            "streak_master": {
                "metric_val": student.current_streak,
                "levels": [
                    {"threshold": 7, "name": "Streak Master Bronze"},
                    {"threshold": 14, "name": "Streak Master Silver"},
                    {"threshold": 30, "name": "Streak Master Gold"},
                ],
            },
            "goal_achiever": {
                "metric_val": goals_met,
                "levels": [
                    {"threshold": 1, "name": "Goal Achiever Bronze"},
                    {"threshold": 3, "name": "Goal Achiever Silver"},
                    {"threshold": 6, "name": "Goal Achiever Gold"},
                ],
            },
        }

        badges_awarded = []
        for badge_type, bdef in badge_defs.items():
            val = bdef["metric_val"]
            for level_idx, level in enumerate(bdef["levels"], 1):
                if val >= level["threshold"]:
                    badge = Achievement(
                        student_id=sid,
                        badge_type=badge_type,
                        badge_name=level["name"],
                        badge_level=level_idx,
                        earned_at=now - timedelta(days=(3 - level_idx) * 15 + 5),
                    )
                    db.add(badge)
                    badges_awarded.append(level["name"])

        db.commit()
        print(f"  Badges awarded: {len(badges_awarded)}")
        for b in badges_awarded:
            print(f"    - {b}")

        # ---------------------------------------------------------------
        # Summary
        # ---------------------------------------------------------------
        print(f"\n--- Emma's Profile Summary ---")
        print(f"  Books completed: {books_completed_count}")
        print(f"  Reviews written: {review_count}")
        print(f"  Genres explored: {len(genres_seen)}")
        print(f"  Current streak: {student.current_streak} days")
        print(f"  Longest streak: {student.longest_streak} days")
        print(f"  Reading goals: {goals_created} ({goals_met} met)")
        print(f"  Badges: {len(badges_awarded)}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_emma_progress()
