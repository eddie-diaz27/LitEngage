"""Gamification API endpoints - leaderboard, badges, streaks, goals."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import (
    Achievement,
    ReadingGoal,
    ReadingHistory,
    Student,
    StudentReview,
)
from backend.schemas.gamification import (
    BadgeResponse,
    LeaderboardEntry,
    ReadingGoalCreate,
    ReadingGoalResponse,
    StreakResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gamification", tags=["gamification"])

# Badge definitions: badge_type -> {levels: [{threshold, name}]}
BADGE_DEFS = {
    "bookworm": {
        "metric": "books_completed",
        "levels": [
            {"threshold": 5, "name": "Bookworm Bronze"},
            {"threshold": 10, "name": "Bookworm Silver"},
            {"threshold": 25, "name": "Bookworm Gold"},
        ],
    },
    "genre_explorer": {
        "metric": "genres_read",
        "levels": [
            {"threshold": 3, "name": "Genre Explorer Bronze"},
            {"threshold": 5, "name": "Genre Explorer Silver"},
            {"threshold": 8, "name": "Genre Explorer Gold"},
        ],
    },
    "review_star": {
        "metric": "reviews_written",
        "levels": [
            {"threshold": 3, "name": "Review Star Bronze"},
            {"threshold": 10, "name": "Review Star Silver"},
            {"threshold": 25, "name": "Review Star Gold"},
        ],
    },
    "streak_master": {
        "metric": "current_streak",
        "levels": [
            {"threshold": 7, "name": "Streak Master Bronze"},
            {"threshold": 14, "name": "Streak Master Silver"},
            {"threshold": 30, "name": "Streak Master Gold"},
        ],
    },
    "goal_achiever": {
        "metric": "goals_met",
        "levels": [
            {"threshold": 1, "name": "Goal Achiever Bronze"},
            {"threshold": 3, "name": "Goal Achiever Silver"},
            {"threshold": 6, "name": "Goal Achiever Gold"},
        ],
    },
}


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(limit: int = 20, db: Session = Depends(get_db)):
    """Get the student leaderboard ranked by composite score.

    Score = (books_completed/max)*50 + (reviews/max)*30 + (streak/max)*20
    """
    students = db.query(Student).all()
    if not students:
        return []

    entries = []
    for s in students:
        books_completed = (
            db.query(func.count(ReadingHistory.id))
            .filter(
                ReadingHistory.student_id == s.id,
                ReadingHistory.status == "completed",
            )
            .scalar()
        )
        review_count = (
            db.query(func.count(StudentReview.id))
            .filter(StudentReview.student_id == s.id)
            .scalar()
        )
        entries.append({
            "student_id": s.id,
            "name": s.name,
            "books_completed": books_completed,
            "review_count": review_count,
            "current_streak": s.current_streak or 0,
        })

    # Compute max values for normalization
    max_books = max((e["books_completed"] for e in entries), default=1) or 1
    max_reviews = max((e["review_count"] for e in entries), default=1) or 1
    max_streak = max((e["current_streak"] for e in entries), default=1) or 1

    for e in entries:
        e["score"] = round(
            (e["books_completed"] / max_books) * 50
            + (e["review_count"] / max_reviews) * 30
            + (e["current_streak"] / max_streak) * 20,
            1,
        )

    entries.sort(key=lambda x: x["score"], reverse=True)

    result = []
    for rank, e in enumerate(entries[:limit], 1):
        result.append(LeaderboardEntry(rank=rank, **e))

    return result


@router.get("/student/{student_id}/badges", response_model=list[BadgeResponse])
async def get_badges(student_id: str, db: Session = Depends(get_db)):
    """Get all badges earned by a student."""
    badges = (
        db.query(Achievement)
        .filter(Achievement.student_id == student_id)
        .order_by(Achievement.earned_at.desc())
        .all()
    )
    return [BadgeResponse.model_validate(b) for b in badges]


@router.get("/student/{student_id}/streak", response_model=StreakResponse)
async def get_streak(student_id: str, db: Session = Depends(get_db)):
    """Get a student's current and longest reading streak."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return StreakResponse(
        current_streak=student.current_streak or 0,
        longest_streak=student.longest_streak or 0,
        streak_last_date=student.streak_last_date,
    )


@router.get("/student/{student_id}/goal", response_model=ReadingGoalResponse)
async def get_current_goal(student_id: str, db: Session = Depends(get_db)):
    """Get the student's current month reading goal."""
    now = datetime.utcnow()
    goal = (
        db.query(ReadingGoal)
        .filter(
            ReadingGoal.student_id == student_id,
            ReadingGoal.month == now.month,
            ReadingGoal.year == now.year,
        )
        .first()
    )
    if not goal:
        # Return a default goal
        return ReadingGoalResponse(
            id=0,
            month=now.month,
            year=now.year,
            target_books=3,
            books_completed=0,
            progress_pct=0.0,
        )

    pct = round((goal.books_completed / goal.target_books) * 100, 1) if goal.target_books > 0 else 0
    return ReadingGoalResponse(
        id=goal.id,
        month=goal.month,
        year=goal.year,
        target_books=goal.target_books,
        books_completed=goal.books_completed,
        progress_pct=pct,
    )


@router.post("/student/{student_id}/goal", response_model=ReadingGoalResponse)
async def set_goal(
    student_id: str,
    request: ReadingGoalCreate,
    db: Session = Depends(get_db),
):
    """Set or update the student's monthly reading goal."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    now = datetime.utcnow()
    goal = (
        db.query(ReadingGoal)
        .filter(
            ReadingGoal.student_id == student_id,
            ReadingGoal.month == now.month,
            ReadingGoal.year == now.year,
        )
        .first()
    )

    if goal:
        goal.target_books = request.target_books
    else:
        goal = ReadingGoal(
            student_id=student_id,
            month=now.month,
            year=now.year,
            target_books=request.target_books,
        )
        db.add(goal)

    db.commit()
    db.refresh(goal)

    pct = round((goal.books_completed / goal.target_books) * 100, 1) if goal.target_books > 0 else 0
    return ReadingGoalResponse(
        id=goal.id,
        month=goal.month,
        year=goal.year,
        target_books=goal.target_books,
        books_completed=goal.books_completed,
        progress_pct=pct,
    )


@router.post("/student/{student_id}/check-badges")
async def check_badges(student_id: str, db: Session = Depends(get_db)):
    """Check and award any newly earned badges for a student."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    books_completed = (
        db.query(func.count(ReadingHistory.id))
        .filter(
            ReadingHistory.student_id == student_id,
            ReadingHistory.status == "completed",
        )
        .scalar()
    )

    review_count = (
        db.query(func.count(StudentReview.id))
        .filter(StudentReview.student_id == student_id)
        .scalar()
    )

    # Count distinct genres from completed books
    completed_books = (
        db.query(ReadingHistory)
        .filter(
            ReadingHistory.student_id == student_id,
            ReadingHistory.status == "completed",
        )
        .all()
    )
    genres_seen = set()
    for rh in completed_books:
        if rh.book and rh.book.genres_json:
            genres_seen.update(rh.book.genres_json)

    # Count goals met
    goals_met = (
        db.query(func.count(ReadingGoal.id))
        .filter(
            ReadingGoal.student_id == student_id,
            ReadingGoal.books_completed >= ReadingGoal.target_books,
        )
        .scalar()
    )

    metrics = {
        "books_completed": books_completed,
        "genres_read": len(genres_seen),
        "reviews_written": review_count,
        "current_streak": student.current_streak or 0,
        "goals_met": goals_met,
    }

    new_badges = []
    for badge_type, badge_def in BADGE_DEFS.items():
        metric_val = metrics.get(badge_def["metric"], 0)
        for level_idx, level in enumerate(badge_def["levels"], 1):
            if metric_val >= level["threshold"]:
                # Check if already earned
                existing = (
                    db.query(Achievement)
                    .filter(
                        Achievement.student_id == student_id,
                        Achievement.badge_type == badge_type,
                        Achievement.badge_level == level_idx,
                    )
                    .first()
                )
                if not existing:
                    badge = Achievement(
                        student_id=student_id,
                        badge_type=badge_type,
                        badge_name=level["name"],
                        badge_level=level_idx,
                    )
                    db.add(badge)
                    new_badges.append(level["name"])

    db.commit()

    return {"new_badges": new_badges, "total_checked": len(BADGE_DEFS)}
