"""Pydantic schemas for book loan endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LoanCreate(BaseModel):
    student_id: str
    book_id: str
    due_days: int = Field(14, ge=1, le=90)


class LoanReturn(BaseModel):
    notes: Optional[str] = None


class LoanRenew(BaseModel):
    additional_days: int = Field(14, ge=1, le=30)
    notes: Optional[str] = None


class LoanResponse(BaseModel):
    id: int
    student_id: str
    student_name: Optional[str] = None
    book_id: str
    book_title: Optional[str] = None
    checked_out_at: datetime
    due_date: datetime
    returned_at: Optional[datetime] = None
    renewed_count: int = 0
    notes: Optional[str] = None
    is_overdue: bool = False
    days_overdue: int = 0

    model_config = {"from_attributes": True}


class LoanSummary(BaseModel):
    total_active_loans: int = 0
    overdue_count: int = 0
    due_today_count: int = 0
    due_this_week_count: int = 0
    overdue_loans: list[LoanResponse] = []
