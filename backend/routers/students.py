"""Student profile API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database import crud
from backend.schemas.student import (
    ReadingHistoryResponse,
    StudentListResponse,
    StudentPreferencesUpdate,
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
    limit: int = 20,
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
                status=entry.status,
                rating=entry.rating,
                started_at=entry.started_at,
                completed_at=entry.completed_at,
            )
        )
    return results
