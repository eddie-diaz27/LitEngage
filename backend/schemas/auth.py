"""Pydantic schemas for authentication."""

from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=100)


class LoginResponse(BaseModel):
    user_id: int
    username: str
    role: str
    student_id: Optional[str] = None
    display_name: str


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field(..., pattern="^(student|librarian)$")
    student_id: Optional[str] = None
    display_name: str = Field(..., min_length=1, max_length=100)
