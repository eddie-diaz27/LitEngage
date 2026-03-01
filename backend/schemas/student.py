"""Pydantic schemas for student-related requests and responses."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class StudentBase(BaseModel):
    name: str
    grade_level: int = Field(..., ge=1, le=12)
    reading_level: str
    preferences_json: Optional[dict] = None


class StudentCreate(StudentBase):
    pass


class StudentResponse(StudentBase):
    id: str
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StudentPreferencesUpdate(BaseModel):
    preferences_json: dict


class ReadingHistoryResponse(BaseModel):
    id: int
    book_id: str
    book_title: Optional[str] = None
    book_author: Optional[str] = None
    status: str
    rating: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class StudentListResponse(BaseModel):
    id: str
    name: str
    grade_level: int
    reading_level: str

    model_config = {"from_attributes": True}
