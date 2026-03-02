"""Pydantic schemas for student reviews."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    student_id: str
    book_id: str
    rating: int = Field(..., ge=1, le=5)
    review_text: Optional[str] = Field(None, max_length=2000)


class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    review_text: Optional[str] = Field(None, max_length=2000)


class ReviewResponse(BaseModel):
    id: int
    student_id: str
    student_name: Optional[str] = None
    book_id: str
    book_title: Optional[str] = None
    rating: int
    review_text: Optional[str] = None
    is_approved: bool = True
    moderation_status: Optional[str] = None
    moderation_flags: Optional[list] = None
    moderation_reason: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReviewModerate(BaseModel):
    is_approved: bool
