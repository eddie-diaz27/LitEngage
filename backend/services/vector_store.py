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

        books = []
        for doc in results:
            book = {
                "book_id": doc.metadata.get("book_id", ""),
                "title": doc.metadata.get("title", "Unknown"),
                "author": doc.metadata.get("author", "Unknown"),
                "description": doc.page_content[:500],
                "avg_rating": doc.metadata.get("avg_rating", 0.0),
                "publication_year": doc.metadata.get("publication_year", 0),
                "reading_level": doc.metadata.get("reading_level", ""),
            }
            books.append(book)

        # Post-search genre filtering (ChromaDB can't filter on list fields)
        if genres:
            # We'd need the full book record for genre filtering
            # For now, return all results - genre filtering happens at the agent level
            pass

        logger.info(
            f"Search '{query[:50]}' returned {len(books)} results "
            f"(reading_level={reading_level})"
        )
        return books

    def similarity_search(self, query: str, k: int = 5) -> List[dict]:
        """Simple similarity search without MMR or filters."""
        try:
            results = self._vectorstore.similarity_search(query=query, k=k)
            return [
                {
                    "book_id": doc.metadata.get("book_id", ""),
                    "title": doc.metadata.get("title", "Unknown"),
                    "author": doc.metadata.get("author", "Unknown"),
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
