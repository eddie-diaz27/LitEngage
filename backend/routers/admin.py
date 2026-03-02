"""Admin/librarian API endpoints - token tracking, alerts, analytics."""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import (
    Book,
    ReadingHistory,
    Student,
    StudentReview,
    TokenUsage,
)
from backend.schemas.admin import (
    AlertResponse,
    GenreDistribution,
    TokenUsageResponse,
    TokenUsageSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/token-usage", response_model=TokenUsageSummary)
async def get_token_usage(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Get token usage summary for the last N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    records = (
        db.query(TokenUsage)
        .filter(TokenUsage.created_at >= cutoff)
        .all()
    )

    total_requests = len(records)
    total_tokens = sum(r.total_tokens for r in records)
    total_cost = sum(r.estimated_cost_usd for r in records)
    avg_latency = sum(r.latency_ms for r in records) / total_requests if total_requests else 0

    # By type
    by_type = {}
    for r in records:
        t = r.request_type or "unknown"
        if t not in by_type:
            by_type[t] = {"requests": 0, "tokens": 0, "cost": 0.0}
        by_type[t]["requests"] += 1
        by_type[t]["tokens"] += r.total_tokens
        by_type[t]["cost"] += r.estimated_cost_usd

    # By student
    student_usage = {}
    for r in records:
        sid = r.student_id or "system"
        if sid not in student_usage:
            student_usage[sid] = {"student_id": sid, "requests": 0, "tokens": 0, "cost": 0.0}
        student_usage[sid]["requests"] += 1
        student_usage[sid]["tokens"] += r.total_tokens
        student_usage[sid]["cost"] += r.estimated_cost_usd

    by_student = sorted(student_usage.values(), key=lambda x: x["tokens"], reverse=True)

    return TokenUsageSummary(
        total_requests=total_requests,
        total_tokens=total_tokens,
        total_cost_usd=round(total_cost, 4),
        avg_latency_ms=round(avg_latency, 1),
        by_type=by_type,
        by_student=by_student,
    )


@router.get("/token-usage/student/{student_id}", response_model=list[TokenUsageResponse])
async def get_student_token_usage(
    student_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get token usage records for a specific student."""
    records = (
        db.query(TokenUsage)
        .filter(TokenUsage.student_id == student_id)
        .order_by(TokenUsage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [TokenUsageResponse.model_validate(r) for r in records]


@router.get("/alerts", response_model=list[AlertResponse])
async def get_alerts(db: Session = Depends(get_db)):
    """Generate automated alerts for the librarian."""
    alerts = []
    now = datetime.utcnow()

    # 1. Inactive students (no activity in 30 days)
    thirty_days_ago = now - timedelta(days=30)
    inactive = (
        db.query(Student)
        .filter(
            (Student.last_active == None) | (Student.last_active < thirty_days_ago)
        )
        .all()
    )
    if inactive:
        names = [s.name for s in inactive[:5]]
        more = f" and {len(inactive) - 5} more" if len(inactive) > 5 else ""
        alerts.append(AlertResponse(
            alert_type="inactive_student",
            message=f"{len(inactive)} students inactive for 30+ days: {', '.join(names)}{more}",
            severity="warning",
            data={"count": len(inactive), "student_ids": [s.id for s in inactive]},
        ))

    # 2. Students who completed their reading goal this month
    from backend.database.models import ReadingGoal
    completed_goals = (
        db.query(ReadingGoal)
        .join(Student)
        .filter(
            ReadingGoal.month == now.month,
            ReadingGoal.year == now.year,
            ReadingGoal.books_completed >= ReadingGoal.target_books,
        )
        .all()
    )
    for goal in completed_goals:
        alerts.append(AlertResponse(
            alert_type="goal_completed",
            message=f"{goal.student.name} completed their reading goal ({goal.books_completed}/{goal.target_books} books)!",
            severity="success",
            data={"student_id": goal.student_id},
        ))

    # 3. Low review activity
    total_reviews = db.query(func.count(StudentReview.id)).scalar()
    if total_reviews == 0:
        alerts.append(AlertResponse(
            alert_type="low_reviews",
            message="No student reviews yet. Encourage students to write reviews!",
            severity="info",
        ))

    # 4. Overdue books
    from backend.database.models import BookLoan
    overdue_loans = (
        db.query(BookLoan)
        .filter(
            BookLoan.returned_at == None,
            BookLoan.due_date < now,
        )
        .all()
    )
    if overdue_loans:
        details = []
        for l in overdue_loans[:5]:
            student_name = l.student.name if l.student else "Unknown"
            book_title = l.book.title if l.book else "Unknown"
            days = (now - l.due_date).days
            details.append(f"{student_name}: \"{book_title}\" ({days}d overdue)")
        more = f" and {len(overdue_loans) - 5} more" if len(overdue_loans) > 5 else ""
        alerts.append(AlertResponse(
            alert_type="overdue_books",
            message=f"{len(overdue_loans)} overdue book(s) need attention: {'; '.join(details)}{more}",
            severity="warning",
            data={"count": len(overdue_loans)},
        ))

    # 5. Flagged reviews awaiting librarian decision
    flagged_count = (
        db.query(func.count(StudentReview.id))
        .filter(StudentReview.moderation_status == "flagged")
        .scalar()
    )
    if flagged_count:
        alerts.append(AlertResponse(
            alert_type="flagged_reviews",
            message=f"{flagged_count} flagged review(s) awaiting your decision. Check the Review Moderation tab.",
            severity="warning",
            data={"count": flagged_count},
        ))

    return alerts


@router.get("/stats/genres", response_model=list[GenreDistribution])
async def get_genre_stats(db: Session = Depends(get_db)):
    """Get genre distribution across the book catalog."""
    books = db.query(Book).filter(Book.genres_json != None).all()
    genre_counts = {}
    total = 0
    for book in books:
        if book.genres_json:
            for genre in book.genres_json:
                genre_counts[genre] = genre_counts.get(genre, 0) + 1
                total += 1

    result = []
    for genre, count in sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
        result.append(GenreDistribution(
            genre=genre,
            count=count,
            percentage=round((count / total) * 100, 1) if total else 0,
        ))
    return result


@router.get("/stats/trends")
async def get_trends(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Get book popularity trends based on reading activity."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Most read books in period
    popular = (
        db.query(
            ReadingHistory.book_id,
            func.count(ReadingHistory.id).label("read_count"),
        )
        .filter(ReadingHistory.started_at >= cutoff)
        .group_by(ReadingHistory.book_id)
        .order_by(func.count(ReadingHistory.id).desc())
        .limit(10)
        .all()
    )

    results = []
    for book_id, count in popular:
        book = db.query(Book).filter(Book.id == book_id).first()
        if book:
            results.append({
                "book_id": book.id,
                "title": book.title,
                "author_name": book.author_name or book.author,
                "read_count": count,
                "avg_rating": book.avg_rating,
            })

    return results
