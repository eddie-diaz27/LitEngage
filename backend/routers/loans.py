"""Book loan endpoints — checkout, return, renew, overdue tracking."""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.connection import get_db
from backend.database.models import Book, BookLoan, Student
from backend.schemas.loan import (
    LoanCreate,
    LoanRenew,
    LoanResponse,
    LoanReturn,
    LoanSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/loans", tags=["loans"])


def _loan_to_response(loan: BookLoan) -> LoanResponse:
    """Convert a BookLoan ORM object to response schema."""
    now = datetime.utcnow()
    is_overdue = loan.returned_at is None and loan.due_date < now
    days_overdue = max(0, (now - loan.due_date).days) if is_overdue else 0

    return LoanResponse(
        id=loan.id,
        student_id=loan.student_id,
        student_name=loan.student.name if loan.student else None,
        book_id=loan.book_id,
        book_title=loan.book.title if loan.book else None,
        checked_out_at=loan.checked_out_at,
        due_date=loan.due_date,
        returned_at=loan.returned_at,
        renewed_count=loan.renewed_count,
        notes=loan.notes,
        is_overdue=is_overdue,
        days_overdue=days_overdue,
    )


@router.post("/checkout", response_model=LoanResponse)
async def checkout_book(
    request: LoanCreate,
    db: Session = Depends(get_db),
):
    """Check out a book to a student."""
    student = db.query(Student).filter(Student.id == request.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    book = db.query(Book).filter(Book.id == request.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Check if this book is already checked out by this student
    existing = (
        db.query(BookLoan)
        .filter(
            BookLoan.student_id == request.student_id,
            BookLoan.book_id == request.book_id,
            BookLoan.returned_at == None,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="This book is already checked out to this student",
        )

    now = datetime.utcnow()
    loan = BookLoan(
        student_id=request.student_id,
        book_id=request.book_id,
        checked_out_at=now,
        due_date=now + timedelta(days=request.due_days),
    )
    db.add(loan)
    db.commit()
    db.refresh(loan)

    logger.info(f"Book {request.book_id} checked out to {request.student_id}")
    return _loan_to_response(loan)


@router.post("/{loan_id}/return", response_model=LoanResponse)
async def return_book(
    loan_id: int,
    request: LoanReturn = None,
    db: Session = Depends(get_db),
):
    """Return a checked-out book."""
    loan = db.query(BookLoan).filter(BookLoan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    if loan.returned_at is not None:
        raise HTTPException(status_code=400, detail="Book already returned")

    loan.returned_at = datetime.utcnow()
    if request and request.notes:
        loan.notes = request.notes
    db.commit()
    db.refresh(loan)

    logger.info(f"Book {loan.book_id} returned by {loan.student_id}")
    return _loan_to_response(loan)


@router.post("/{loan_id}/renew", response_model=LoanResponse)
async def renew_loan(
    loan_id: int,
    request: LoanRenew = None,
    db: Session = Depends(get_db),
):
    """Extend the due date of a loan."""
    loan = db.query(BookLoan).filter(BookLoan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    if loan.returned_at is not None:
        raise HTTPException(status_code=400, detail="Cannot renew a returned book")
    if loan.renewed_count >= settings.max_loan_renewals:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum renewals ({settings.max_loan_renewals}) reached",
        )

    additional_days = request.additional_days if request else settings.default_loan_days
    loan.due_date = loan.due_date + timedelta(days=additional_days)
    loan.renewed_count += 1
    if request and request.notes:
        loan.notes = request.notes
    db.commit()
    db.refresh(loan)

    logger.info(f"Loan {loan_id} renewed (count={loan.renewed_count})")
    return _loan_to_response(loan)


@router.get("/active", response_model=list[LoanResponse])
async def get_active_loans(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get all currently checked-out books."""
    loans = (
        db.query(BookLoan)
        .filter(BookLoan.returned_at == None)
        .order_by(BookLoan.due_date.asc())
        .limit(limit)
        .all()
    )
    return [_loan_to_response(l) for l in loans]


@router.get("/overdue", response_model=list[LoanResponse])
async def get_overdue_loans(db: Session = Depends(get_db)):
    """Get all overdue books."""
    now = datetime.utcnow()
    loans = (
        db.query(BookLoan)
        .filter(
            BookLoan.returned_at == None,
            BookLoan.due_date < now,
        )
        .order_by(BookLoan.due_date.asc())
        .all()
    )
    return [_loan_to_response(l) for l in loans]


@router.get("/summary", response_model=LoanSummary)
async def get_loan_summary(db: Session = Depends(get_db)):
    """Get loan summary counts for the dashboard."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    week_end = today_start + timedelta(days=7)

    active = (
        db.query(BookLoan)
        .filter(BookLoan.returned_at == None)
        .all()
    )

    overdue = [l for l in active if l.due_date < now]
    due_today = [l for l in active if today_start <= l.due_date < today_end]
    due_this_week = [l for l in active if today_start <= l.due_date < week_end]

    return LoanSummary(
        total_active_loans=len(active),
        overdue_count=len(overdue),
        due_today_count=len(due_today),
        due_this_week_count=len(due_this_week),
        overdue_loans=[_loan_to_response(l) for l in overdue[:10]],
    )


@router.get("/student/{student_id}", response_model=list[LoanResponse])
async def get_student_loans(
    student_id: str,
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Get a student's loan history."""
    query = db.query(BookLoan).filter(BookLoan.student_id == student_id)
    if active_only:
        query = query.filter(BookLoan.returned_at == None)
    loans = query.order_by(BookLoan.checked_out_at.desc()).all()
    return [_loan_to_response(l) for l in loans]
