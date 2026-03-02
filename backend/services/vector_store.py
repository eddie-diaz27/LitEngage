"""ChromaDB vector store interface for semantic book search."""

import logging
from typing import List, Optional

from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

from backend.config import settings

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Singleton service for semantic book search via ChromaDB."""

    def __init__(self):
        self._embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        self._vectorstore = Chroma(
            persist_directory=settings.chroma_persist_directory,
            embedding_function=self._embeddings,
            collection_name=settings.chroma_collection_name,
        )
        logger.info(
            f"VectorStoreService initialized with collection "
            f"'{settings.chroma_collection_name}'"
        )

    def search_books(
        self,
        query: str,
        reading_level: Optional[str] = None,
        genres: Optional[List[str]] = None,
        k: int = 10,
    ) -> List[dict]:
        """Search books using MMR (Maximal Marginal Relevance) for diversity.

        Args:
            query: Natural language search query.
            reading_level: Filter by reading level (e.g., "middle-school").
            genres: Optional genre filters (applied post-search).
            k: Number of results to return.

        Returns:
            List of book dicts with metadata.
        """
        filter_dict = {}
        if reading_level:
            filter_dict["reading_level"] = reading_level

        try:
            results = self._vectorstore.max_marginal_relevance_search(
                query=query,
                k=k,
                fetch_k=k * 3,
                lambda_mult=settings.vector_search_lambda,
                filter=filter_dict if filter_dict else None,
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

        # Enrich with author_name and review context from DB
        book_ids = [doc.metadata.get("book_id", "") for doc in results]
        author_names = self._lookup_author_names(book_ids)
        review_ctx = self._lookup_review_context(book_ids)

        books = []
        for doc in results:
            bid = doc.metadata.get("book_id", "")
            rc = review_ctx.get(bid, {})
            book = {
                "book_id": bid,
                "title": doc.metadata.get("title", "Unknown"),
                "author": author_names.get(bid) or doc.metadata.get("author", "Unknown"),
                "description": doc.page_content[:500],
                "avg_rating": rc.get("avg_rating") or doc.metadata.get("avg_rating", 0.0),
                "publication_year": doc.metadata.get("publication_year", 0),
                "reading_level": doc.metadata.get("reading_level", ""),
                "review_count": rc.get("review_count", 0),
            }
            books.append(book)

        logger.info(
            f"Search '{query[:50]}' returned {len(books)} results "
            f"(reading_level={reading_level})"
        )
        return books

    def _lookup_author_names(self, book_ids: List[str]) -> dict:
        """Look up author_name from DB for a list of book IDs."""
        if not book_ids:
            return {}
        try:
            from backend.database.connection import SessionLocal
            from backend.database.models import Book
            db = SessionLocal()
            try:
                books = db.query(Book.id, Book.author_name).filter(Book.id.in_(book_ids)).all()
                return {b.id: b.author_name for b in books if b.author_name}
            finally:
                db.close()
        except Exception:
            return {}

    def _lookup_review_context(self, book_ids: List[str]) -> dict:
        """Look up review count and avg student rating for books."""
        if not book_ids:
            return {}
        try:
            from sqlalchemy import func as sqlfunc
            from backend.database.connection import SessionLocal
            from backend.database.models import Book, StudentReview
            db = SessionLocal()
            try:
                # Get review stats
                stats = (
                    db.query(
                        StudentReview.book_id,
                        sqlfunc.count(StudentReview.id).label("cnt"),
                        sqlfunc.avg(StudentReview.rating).label("avg"),
                    )
                    .filter(
                        StudentReview.book_id.in_(book_ids),
                        StudentReview.is_approved == True,
                    )
                    .group_by(StudentReview.book_id)
                    .all()
                )
                # Also get current Book.avg_rating for fallback
                books = db.query(Book.id, Book.avg_rating).filter(Book.id.in_(book_ids)).all()
                book_ratings = {b.id: b.avg_rating for b in books}

                result = {}
                for s in stats:
                    result[s.book_id] = {
                        "review_count": s.cnt,
                        "avg_rating": round(float(s.avg), 2) if s.avg else book_ratings.get(s.book_id),
                    }
                # For books without reviews, use DB avg_rating
                for bid in book_ids:
                    if bid not in result:
                        result[bid] = {
                            "review_count": 0,
                            "avg_rating": book_ratings.get(bid),
                        }
                return result
            finally:
                db.close()
        except Exception:
            return {}

    def similarity_search(self, query: str, k: int = 5) -> List[dict]:
        """Simple similarity search without MMR or filters."""
        try:
            results = self._vectorstore.similarity_search(query=query, k=k)
            book_ids = [doc.metadata.get("book_id", "") for doc in results]
            author_names = self._lookup_author_names(book_ids)
            return [
                {
                    "book_id": doc.metadata.get("book_id", ""),
                    "title": doc.metadata.get("title", "Unknown"),
                    "author": author_names.get(doc.metadata.get("book_id", "")) or doc.metadata.get("author", "Unknown"),
                    "description": doc.page_content[:300],
                }
                for doc in results
            ]
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []


# Lazy singleton - initialized on first access
_vector_store_service: Optional[VectorStoreService] = None


def get_vector_store_service() -> VectorStoreService:
    """Get or create the singleton VectorStoreService."""
    global _vector_store_service
    if _vector_store_service is None:
        _vector_store_service = VectorStoreService()
    return _vector_store_service
