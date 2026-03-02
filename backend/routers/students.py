"""Student profile API endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database import crud
from backend.database.models import (
    Achievement,
    Book,
    ReadingHistory,
    Student,
    StudentReview,
)
from backend.schemas.student import (
    ReadingHistoryCreate,
    ReadingHistoryResponse,
    ReadingHistoryUpdate,
    StudentListResponse,
    StudentPreferencesUpdate,
    StudentProfileResponse,
    StudentResponse,
)

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/", response_model=list[StudentListResponse])
async def list_students(db: Session = Depends(get_db)):
    """List all students (for student selector dropdown)."""
    students = crud.get_students(db)
    return [StudentListResponse.model_validate(s) for s in students]


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(student_id: str, db: Session = Depends(get_db)):
    """Get a student's profile."""
    student = crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return StudentResponse.model_validate(student)


@router.get("/{student_id}/profile", response_model=StudentProfileResponse)
async def get_student_profile(student_id: str, db: Session = Depends(get_db)):
    """Get a student's full profile with stats."""
    student = crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    books_completed = (
        db.query(func.count(ReadingHistory.id))
        .filter(ReadingHistory.student_id == student_id, ReadingHistory.status == "completed")
        .scalar()
    )
    books_reading = (
        db.query(func.count(ReadingHistory.id))
        .filter(ReadingHistory.student_id == student_id, ReadingHistory.status == "reading")
        .scalar()
    )
    books_wishlist = (
        db.query(func.count(ReadingHistory.id))
        .filter(ReadingHistory.student_id == student_id, ReadingHistory.status == "wishlist")
        .scalar()
    )
    review_count = (
        db.query(func.count(StudentReview.id))
        .filter(StudentReview.student_id == student_id)
        .scalar()
    )
    badge_count = (
        db.query(func.count(Achievement.id))
        .filter(Achievement.student_id == student_id)
        .scalar()
    )

    return StudentProfileResponse(
        id=student.id,
        name=student.name,
        grade_level=student.grade_level,
        reading_level=student.reading_level,
        preferences_json=student.preferences_json,
        current_streak=student.current_streak or 0,
        longest_streak=student.longest_streak or 0,
        books_completed=books_completed,
        books_reading=books_reading,
        books_wishlist=books_wishlist,
        review_count=review_count,
        badge_count=badge_count,
    )


@router.put("/{student_id}/preferences", response_model=StudentResponse)
async def update_preferences(
    student_id: str,
    update: StudentPreferencesUpdate,
    db: Session = Depends(get_db),
):
    """Update a student's reading preferences."""
    student = crud.update_student_preferences(
        db, student_id, update.preferences_json
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return StudentResponse.model_validate(student)


@router.get("/{student_id}/history", response_model=list[ReadingHistoryResponse])
async def get_reading_history(
    student_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get a student's reading history."""
    student = crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    history = crud.get_reading_history(db, student_id, limit)
    results = []
    for entry in history:
        book = entry.book
        results.append(
            ReadingHistoryResponse(
                id=entry.id,
                book_id=entry.book_id,
                book_title=book.title if book else None,
                book_author=book.author if book else None,
                book_author_name=book.author_name if book else None,
                book_image_url=book.image_url if book else None,
                book_genres=book.genres_json if book else None,
                book_avg_rating=book.avg_rating if book else None,
                status=entry.status,
                rating=entry.rating,
                started_at=entry.started_at,
                completed_at=entry.completed_at,
            )
        )
    return results


@router.post("/{student_id}/history", response_model=ReadingHistoryResponse)
async def add_to_reading_list(
    student_id: str,
    request: ReadingHistoryCreate,
    db: Session = Depends(get_db),
):
    """Add a book to a student's reading list."""
    student = crud.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    book = db.query(Book).filter(Book.id == request.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Check if already in history
    existing = (
        db.query(ReadingHistory)
        .filter(
            ReadingHistory.student_id == student_id,
            ReadingHistory.book_id == request.book_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Book already in reading list")

    now = datetime.utcnow()
    entry = ReadingHistory(
        student_id=student_id,
        book_id=request.book_id,
        status=request.status,
        started_at=now if request.status in ("reading", "completed") else None,
        completed_at=now if request.status == "completed" else None,
    )
    db.add(entry)

    # Update student last_active
    student.last_active = now
    db.commit()
    db.refresh(entry)

    return ReadingHistoryResponse(
        id=entry.id,
        book_id=entry.book_id,
        book_title=book.title,
        book_author=book.author,
        book_author_name=book.author_name,
        book_image_url=book.image_url,
        book_genres=book.genres_json,
        book_avg_rating=book.avg_rating,
        status=entry.status,
        rating=entry.rating,
        started_at=entry.started_at,
        completed_at=entry.completed_at,
    )


@router.put("/{student_id}/history/{entry_id}", response_model=ReadingHistoryResponse)
async def update_reading_status(
    student_id: str,
    entry_id: int,
    update: ReadingHistoryUpdate,
    db: Session = Depends(get_db),
):
    """Update a reading history entry's status or rating."""
    entry = (
        db.query(ReadingHistory)
        .filter(ReadingHistory.id == entry_id, ReadingHistory.student_id == student_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Reading history entry not found")

    now = datetime.utcnow()
    if update.status is not None:
        entry.status = update.status
        if update.status == "reading" and not entry.started_at:
            entry.started_at = now
        elif update.status == "completed":
            entry.completed_at = now
    if update.rating is not None:
        entry.rating = update.rating

    # Update student last_active
    student = crud.get_student(db, student_id)
    if student:
        student.last_active = now
    db.commit()
    db.refresh(entry)

    book = entry.book
    return ReadingHistoryResponse(
        id=entry.id,
        book_id=entry.book_id,
        book_title=book.title if book else None,
        book_author=book.author if book else None,
        book_author_name=book.author_name if book else None,
        book_image_url=book.image_url if book else None,
        book_genres=book.genres_json if book else None,
        book_avg_rating=book.avg_rating if book else None,
        status=entry.status,
        rating=entry.rating,
        started_at=entry.started_at,
        completed_at=entry.completed_at,
    )
