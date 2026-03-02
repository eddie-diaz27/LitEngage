"""Pydantic schemas for book-related requests and responses."""

from typing import List, Optional

from pydantic import BaseModel, Field


class BookBase(BaseModel):
    title: str
    author: str
    author_name: Optional[str] = None
    description: Optional[str] = None
    genres_json: Optional[List[str]] = None
    reading_level: Optional[str] = None
    avg_rating: Optional[float] = None
    publication_year: Optional[int] = None
    image_url: Optional[str] = None


class BookResponse(BookBase):
    id: str
    isbn: Optional[str] = None
    isbn13: Optional[str] = None
    title_without_series: Optional[str] = None
    publisher: Optional[str] = None
    format: Optional[str] = None
    num_pages: Optional[int] = None
    ratings_count: Optional[int] = None
    text_reviews_count: Optional[int] = None
    age_appropriate: Optional[str] = None
    similar_books_json: Optional[List[str]] = None
    goodreads_link: Optional[str] = None

    model_config = {"from_attributes": True}


class BookSummary(BaseModel):
    """Compact book representation for lists."""

    id: str
    title: str
    author: str
    author_name: Optional[str] = None
    genres_json: Optional[List[str]] = None
    avg_rating: Optional[float] = None
    ratings_count: Optional[int] = None
    image_url: Optional[str] = None
    reading_level: Optional[str] = None

    model_config = {"from_attributes": True}


class BookSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    reading_level: Optional[str] = None
    genres: Optional[List[str]] = None
    max_results: int = Field(default=10, ge=1, le=50)


class BookSearchResult(BaseModel):
    book_id: str
    title: str
    author: str
    author_name: Optional[str] = None
    description: Optional[str] = None
    relevance_score: Optional[float] = None
    genres: Optional[List[str]] = None
    avg_rating: Optional[float] = None
    image_url: Optional[str] = None


class PaginatedBooksResponse(BaseModel):
    books: List[BookSummary]
    total: int
    skip: int
    limit: int


class BookCreate(BaseModel):
    """Schema for librarian creating a book."""
    title: str = Field(..., min_length=1)
    author: str = Field(..., min_length=1)
    author_name: Optional[str] = None
    description: Optional[str] = None
    genres_json: Optional[List[str]] = None
    reading_level: str = "middle-school"
    publication_year: Optional[int] = None
    num_pages: Optional[int] = None
    image_url: Optional[str] = None
    isbn: Optional[str] = None


class BookUpdate(BaseModel):
    """Schema for librarian updating a book."""
    title: Optional[str] = None
    author: Optional[str] = None
    author_name: Optional[str] = None
    description: Optional[str] = None
    genres_json: Optional[List[str]] = None
    reading_level: Optional[str] = None
    publication_year: Optional[int] = None
    num_pages: Optional[int] = None
    image_url: Optional[str] = None


class BookStats(BaseModel):
    book_id: str
    title: str
    times_read: int = 0
    avg_student_rating: Optional[float] = None
    review_count: int = 0
