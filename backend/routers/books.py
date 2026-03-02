"""Book catalog API endpoints."""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database import crud
from backend.database.models import Book, ReadingHistory, StudentReview
from backend.schemas.book import (
    BookCreate,
    BookResponse,
    BookSearchRequest,
    BookSearchResult,
    BookStats,
    BookSummary,
    BookUpdate,
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


@router.get("/trending")
async def get_trending_books(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Get trending books based on recent reading activity."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    popular = (
        db.query(
            ReadingHistory.book_id,
            func.count(ReadingHistory.id).label("read_count"),
        )
        .filter(ReadingHistory.started_at >= cutoff)
        .group_by(ReadingHistory.book_id)
        .order_by(func.count(ReadingHistory.id).desc())
        .limit(limit)
        .all()
    )

    results = []
    for book_id, count in popular:
        book = db.query(Book).filter(Book.id == book_id).first()
        if book:
            results.append({
                "book_id": book.id,
                "title": book.title,
                "author_name": book.author_name or book.author,
                "image_url": book.image_url,
                "avg_rating": book.avg_rating,
                "read_count": count,
            })

    # If no activity, return top-rated books as fallback
    if not results:
        top_books = (
            db.query(Book)
            .filter(Book.avg_rating != None)
            .order_by(Book.ratings_count.desc())
            .limit(limit)
            .all()
        )
        results = [
            {
                "book_id": b.id,
                "title": b.title,
                "author_name": b.author_name or b.author,
                "image_url": b.image_url,
                "avg_rating": b.avg_rating,
                "read_count": 0,
            }
            for b in top_books
        ]

    return results


@router.get("/title-search")
async def title_search(
    q: str = Query("", min_length=0, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Simple text search by title for librarian book management."""
    query = db.query(Book)
    if q.strip():
        query = query.filter(Book.title.ilike(f"%{q.strip()}%"))
    books = (
        query
        .order_by(Book.ratings_count.desc().nullslast())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": b.id,
            "title": b.title,
            "author": b.author,
            "author_name": b.author_name or b.author,
            "avg_rating": b.avg_rating,
            "ratings_count": b.ratings_count,
            "reading_level": b.reading_level,
            "genres_json": b.genres_json,
            "image_url": b.image_url,
            "description": (b.description or "")[:300],
        }
        for b in books
    ]


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(book_id: str, db: Session = Depends(get_db)):
    """Get full details for a specific book."""
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return BookResponse.model_validate(book)


@router.get("/{book_id}/stats", response_model=BookStats)
async def get_book_stats(book_id: str, db: Session = Depends(get_db)):
    """Get reading stats for a specific book."""
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    times_read = (
        db.query(func.count(ReadingHistory.id))
        .filter(
            ReadingHistory.book_id == book_id,
            ReadingHistory.status.in_(["completed", "reading"]),
        )
        .scalar()
    )

    avg_student_rating = (
        db.query(func.avg(StudentReview.rating))
        .filter(StudentReview.book_id == book_id, StudentReview.is_approved == True)
        .scalar()
    )

    review_count = (
        db.query(func.count(StudentReview.id))
        .filter(StudentReview.book_id == book_id, StudentReview.is_approved == True)
        .scalar()
    )

    return BookStats(
        book_id=book.id,
        title=book.title,
        times_read=times_read,
        avg_student_rating=round(avg_student_rating, 1) if avg_student_rating else None,
        review_count=review_count,
    )


@router.post("/search", response_model=list[BookSearchResult])
async def search_books(request: BookSearchRequest, db: Session = Depends(get_db)):
    """Semantic search for books using natural language queries."""
    vs = get_vector_store_service()
    results = vs.search_books(
        query=request.query,
        reading_level=request.reading_level,
        genres=request.genres,
        k=request.max_results,
    )

    search_results = []
    for r in results:
        # Look up author_name from DB if available
        book = db.query(Book).filter(Book.id == r["book_id"]).first()
        author_name = book.author_name if book and book.author_name else r.get("author", "Unknown")

        search_results.append(BookSearchResult(
            book_id=r["book_id"],
            title=r["title"],
            author=r["author"],
            author_name=author_name,
            description=r.get("description"),
            avg_rating=r.get("avg_rating"),
            image_url=book.image_url if book else None,
        ))

    return search_results


@router.post("/", response_model=BookResponse)
async def create_book(request: BookCreate, db: Session = Depends(get_db)):
    """Librarian: add a new book to the catalog."""
    book = Book(
        id=str(uuid.uuid4()),
        title=request.title,
        author=request.author,
        author_name=request.author_name or request.author,
        description=request.description,
        genres_json=request.genres_json,
        reading_level=request.reading_level,
        publication_year=request.publication_year,
        num_pages=request.num_pages,
        image_url=request.image_url,
        isbn=request.isbn,
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return BookResponse.model_validate(book)


@router.put("/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: str,
    request: BookUpdate,
    db: Session = Depends(get_db),
):
    """Librarian: update a book's details."""
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(book, key, value)

    db.commit()
    db.refresh(book)
    return BookResponse.model_validate(book)


@router.delete("/{book_id}")
async def delete_book(book_id: str, db: Session = Depends(get_db)):
    """Librarian: delete a book from the catalog."""
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    db.delete(book)
    db.commit()
    return {"status": "deleted", "book_id": book_id}
