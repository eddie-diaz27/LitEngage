"""Book catalog API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database import crud
from backend.schemas.book import (
    BookResponse,
    BookSearchRequest,
    BookSearchResult,
    BookSummary,
    PaginatedBooksResponse,
)
from backend.services.vector_store import get_vector_store_service

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/", response_model=PaginatedBooksResponse)
async def list_books(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    reading_level: Optional[str] = None,
    min_rating: Optional[float] = None,
    sort_by: str = Query("ratings_count", pattern="^(title|author|avg_rating|ratings_count|publication_year)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """List books with pagination and optional filters."""
    books, total = crud.get_books_paginated(
        db,
        skip=skip,
        limit=limit,
        reading_level=reading_level,
        min_rating=min_rating,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return PaginatedBooksResponse(
        books=[BookSummary.model_validate(b) for b in books],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(book_id: str, db: Session = Depends(get_db)):
    """Get full details for a specific book."""
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return BookResponse.model_validate(book)


@router.post("/search", response_model=list[BookSearchResult])
async def search_books(request: BookSearchRequest):
    """Semantic search for books using natural language queries."""
    vs = get_vector_store_service()
    results = vs.search_books(
        query=request.query,
        reading_level=request.reading_level,
        genres=request.genres,
        k=request.max_results,
    )
    return [
        BookSearchResult(
            book_id=r["book_id"],
            title=r["title"],
            author=r["author"],
            description=r.get("description"),
            avg_rating=r.get("avg_rating"),
        )
        for r in results
    ]
