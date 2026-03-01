"""Generate ChromaDB embeddings for all books in the database."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_chroma import Chroma
from tqdm import tqdm

from backend.config import settings
from backend.database.connection import SessionLocal
from backend.database.models import Book

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_book_document(book: Book) -> Document:
    """Convert a Book ORM record to a LangChain Document for embedding."""
    content = f"{book.title}"
    if book.author and book.author != "Unknown":
        content += f" by {book.author}"
    content += ". "

    if book.description:
        content += f"{book.description} "

    if book.genres_json:
        genres_str = ", ".join(book.genres_json[:5])
        content += f"Genres: {genres_str}."

    metadata = {
        "book_id": book.id,
        "title": book.title,
        "author": book.author or "Unknown",
        "reading_level": book.reading_level or "middle-school",
        "publication_year": book.publication_year or 0,
        "avg_rating": book.avg_rating or 0.0,
    }

    return Document(page_content=content, metadata=metadata)


def generate_embeddings():
    """Generate embeddings for all books and store in ChromaDB."""
    db = SessionLocal()

    try:
        books = db.query(Book).all()
        if not books:
            logger.error("No books found in database. Run load_books.py first.")
            sys.exit(1)

        logger.info(f"Found {len(books)} books in database")

        # Create documents
        documents = []
        for book in tqdm(books, desc="Creating documents"):
            doc = create_book_document(book)
            documents.append(doc)

        logger.info(f"Created {len(documents)} documents")

        # Initialize embedding model
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

        # Create ChromaDB collection
        persist_dir = settings.chroma_persist_directory
        os.makedirs(persist_dir, exist_ok=True)

        logger.info(f"Generating embeddings and storing in {persist_dir}")
        logger.info("This may take 10-20 minutes for ~7,500 books...")

        # Process in batches to show progress
        batch_size = 500
        vectorstore = None

        for i in tqdm(range(0, len(documents), batch_size), desc="Embedding batches"):
            batch = documents[i : i + batch_size]

            if vectorstore is None:
                vectorstore = Chroma.from_documents(
                    documents=batch,
                    embedding=embeddings,
                    persist_directory=persist_dir,
                    collection_name=settings.chroma_collection_name,
                )
            else:
                vectorstore.add_documents(batch)

        # Verify
        collection = vectorstore._collection
        count = collection.count()
        logger.info(f"ChromaDB collection '{settings.chroma_collection_name}' has {count} documents")

        # Quick test search
        test_results = vectorstore.similarity_search("adventure fantasy magic", k=3)
        print("\nTest search for 'adventure fantasy magic':")
        for doc in test_results:
            print(f"  - {doc.metadata['title']} (rating: {doc.metadata['avg_rating']})")

        print(f"\nEmbeddings generated successfully! {count} documents in ChromaDB.")

    finally:
        db.close()


if __name__ == "__main__":
    generate_embeddings()
