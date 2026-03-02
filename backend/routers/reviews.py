"""Student reviews API endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import Book, ReadingHistory, Student, StudentReview
from backend.schemas.review import (
    ReviewCreate,
    ReviewModerate,
    ReviewResponse,
    ReviewUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _recalculate_book_rating(db: Session, book_id: str):
    """Recalculate a book's avg_rating and ratings_count from student reviews."""
    result = (
        db.query(
            func.avg(StudentReview.rating),
            func.count(StudentReview.id),
        )
        .filter(
            StudentReview.book_id == book_id,
            StudentReview.is_approved == True,
        )
        .first()
    )
    book = db.query(Book).filter(Book.id == book_id).first()
    if book:
        book.avg_rating = round(float(result[0]), 2) if result[0] else 0
        book.ratings_count = result[1]
        db.commit()


def _review_to_response(review: StudentReview) -> ReviewResponse:
    """Convert a StudentReview ORM object to a response schema."""
    return ReviewResponse(
        id=review.id,
        student_id=review.student_id,
        student_name=review.student.name if review.student else None,
        book_id=review.book_id,
        book_title=review.book.title if review.book else None,
        rating=review.rating,
        review_text=review.review_text,
        is_approved=review.is_approved,
        moderation_status=review.moderation_status,
        moderation_flags=review.moderation_flags,
        moderation_reason=review.moderation_reason,
        created_at=review.created_at,
    )


@router.get("/recent", response_model=list[ReviewResponse])
async def get_recent_reviews(
    limit: int = 50,
    include_hidden: bool = True,
    db: Session = Depends(get_db),
):
    """Get recent reviews for librarian moderation. Returns all reviews sorted by date."""
    query = db.query(StudentReview)
    if not include_hidden:
        query = query.filter(StudentReview.is_approved == True)
    reviews = (
        query.order_by(StudentReview.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_review_to_response(r) for r in reviews]


@router.post("/", response_model=ReviewResponse)
async def create_review(request: ReviewCreate, db: Session = Depends(get_db)):
    """Create a student review. Student must have the book in their reading history."""
    # Zero-cost profanity pre-check on review text
    if request.review_text:
        from backend.services.profanity_filter import get_profanity_filter
        pf = get_profanity_filter()
        is_clean, rejection = pf.check_input(request.review_text, context="review")
        if not is_clean:
            raise HTTPException(status_code=400, detail=rejection)

    # Verify student exists
    student = db.query(Student).filter(Student.id == request.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Verify book exists
    book = db.query(Book).filter(Book.id == request.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Check if book is in student's reading history with valid status
    history = (
        db.query(ReadingHistory)
        .filter(
            ReadingHistory.student_id == request.student_id,
            ReadingHistory.book_id == request.book_id,
            ReadingHistory.status.in_(["completed", "reading"]),
        )
        .first()
    )
    if not history:
        raise HTTPException(
            status_code=400,
            detail="You can only review books you are reading or have completed",
        )

    # Check for existing review
    existing = (
        db.query(StudentReview)
        .filter(
            StudentReview.student_id == request.student_id,
            StudentReview.book_id == request.book_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="You have already reviewed this book")

    review = StudentReview(
        student_id=request.student_id,
        book_id=request.book_id,
        rating=request.rating,
        review_text=request.review_text,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    _recalculate_book_rating(db, request.book_id)

    # Auto-scan review with AI moderation (non-blocking — failure doesn't block creation)
    if review.review_text:
        try:
            from backend.services.moderation import scan_and_update_review
            grade = student.grade_level or 8
            await scan_and_update_review(db, review, book_title=book.title, student_grade=grade)
            db.refresh(review)
        except Exception as e:
            logger.warning(f"Auto-scan failed for review {review.id}: {e}")

    return _review_to_response(review)


@router.get("/flagged", response_model=list[ReviewResponse])
async def get_flagged_reviews(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get reviews flagged by AI moderation, awaiting librarian decision."""
    reviews = (
        db.query(StudentReview)
        .filter(StudentReview.moderation_status == "flagged")
        .order_by(StudentReview.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_review_to_response(r) for r in reviews]


@router.post("/scan-pending")
async def trigger_scan_pending(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Trigger AI moderation scan on all pending reviews."""
    from backend.services.moderation import scan_pending_reviews
    results = await scan_pending_reviews(db, limit=limit)
    flagged_count = sum(1 for r in results if r["status"] == "flagged")
    return {
        "scanned": len(results),
        "flagged": flagged_count,
        "clean": len(results) - flagged_count,
        "details": results,
    }


@router.get("/book/{book_id}", response_model=list[ReviewResponse])
async def get_book_reviews(book_id: str, db: Session = Depends(get_db)):
    """Get all approved reviews for a book."""
    reviews = (
        db.query(StudentReview)
        .filter(
            StudentReview.book_id == book_id,
            StudentReview.is_approved == True,
        )
        .order_by(StudentReview.created_at.desc())
        .all()
    )
    return [_review_to_response(r) for r in reviews]


@router.get("/student/{student_id}", response_model=list[ReviewResponse])
async def get_student_reviews(student_id: str, db: Session = Depends(get_db)):
    """Get all reviews by a student."""
    reviews = (
        db.query(StudentReview)
        .filter(StudentReview.student_id == student_id)
        .order_by(StudentReview.created_at.desc())
        .all()
    )
    return [_review_to_response(r) for r in reviews]


@router.put("/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: int,
    update: ReviewUpdate,
    db: Session = Depends(get_db),
):
    """Update a review."""
    review = db.query(StudentReview).filter(StudentReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if update.rating is not None:
        review.rating = update.rating
    if update.review_text is not None:
        review.review_text = update.review_text
    review.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(review)

    _recalculate_book_rating(db, review.book_id)

    return _review_to_response(review)


@router.delete("/{review_id}")
async def delete_review(review_id: int, db: Session = Depends(get_db)):
    """Delete a review."""
    review = db.query(StudentReview).filter(StudentReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    book_id = review.book_id
    db.delete(review)
    db.commit()

    _recalculate_book_rating(db, book_id)

    return {"status": "deleted"}


@router.put("/{review_id}/moderate", response_model=ReviewResponse)
async def moderate_review(
    review_id: int,
    action: ReviewModerate,
    db: Session = Depends(get_db),
):
    """Librarian: approve or hide a student review."""
    review = db.query(StudentReview).filter(StudentReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    review.is_approved = action.is_approved
    db.commit()
    db.refresh(review)

    _recalculate_book_rating(db, review.book_id)

    return _review_to_response(review)
