"""Recommendation API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database import crud
from backend.schemas.recommendation import (
    AnalyticsResponse,
    FeedbackRequest,
    RecommendationLogResponse,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/recent", response_model=list[RecommendationLogResponse])
async def get_recent_recommendations(
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Get recent recommendations (for librarian dashboard)."""
    recs = crud.get_recent_recommendations(db, limit)
    return [RecommendationLogResponse.model_validate(r) for r in recs]


@router.post("/{rec_id}/feedback")
async def submit_feedback(
    rec_id: int,
    request: FeedbackRequest,
    db: Session = Depends(get_db),
):
    """Submit thumbs up/down feedback for a recommendation."""
    rec = crud.update_recommendation_feedback(db, rec_id, request.feedback)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return {"status": "ok", "feedback": request.feedback}


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(db: Session = Depends(get_db)):
    """Get recommendation analytics for the librarian dashboard."""
    analytics = crud.get_recommendation_analytics(db)

    total_books = crud.get_book_count(db)
    total_students = len(crud.get_students(db))

    return AnalyticsResponse(
        **analytics,
        total_books=total_books,
        total_students=total_students,
    )
