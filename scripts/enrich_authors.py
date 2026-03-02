"""Enrich books with human-readable author names.

Uses Open Library API to look up author names by matching book title.
Falls back to "Unknown Author" for unresolved books.
"""

import os
import sys
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import func

from backend.database.connection import SessionLocal
from backend.database.models import Book


def lookup_author(title: str, isbn: str = None) -> str:
    """Look up author name from Open Library API."""
    try:
        params = {"limit": 1}
        if isbn:
            params["isbn"] = isbn
        else:
            params["title"] = title

        resp = httpx.get(
            "https://openlibrary.org/search.json",
            params=params,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            docs = data.get("docs", [])
            if docs and docs[0].get("author_name"):
                return docs[0]["author_name"][0]
    except Exception:
        pass
    return None


def enrich_authors():
    db = SessionLocal()
    try:
        # Get books without author_name that have a numeric author ID
        books = (
            db.query(Book)
            .filter(
                (Book.author_name == None) | (Book.author_name == ""),
            )
            .order_by(Book.ratings_count.desc())
            .all()
        )

        total = len(books)
        print(f"Found {total} books needing author enrichment")

        if total == 0:
            print("All books already have author names!")
            return

        enriched = 0
        failed = 0
        batch_size = 50

        for i, book in enumerate(books):
            # Try to get author from authors_json first (some may have names)
            if book.authors_json:
                authors = book.authors_json if isinstance(book.authors_json, list) else json.loads(book.authors_json) if isinstance(book.authors_json, str) else []
                for a in authors:
                    if isinstance(a, dict) and a.get("name"):
                        book.author_name = a["name"]
                        enriched += 1
                        break
                if book.author_name:
                    if (i + 1) % 100 == 0:
                        db.commit()
                        print(f"  [{i+1}/{total}] From JSON: {enriched} enriched, {failed} failed")
                    continue

            # Try Open Library API
            author = lookup_author(book.title, book.isbn)
            if author:
                book.author_name = author
                enriched += 1
            else:
                # Fallback: use the numeric author field as-is (better than nothing)
                book.author_name = book.author if not book.author.isdigit() else "Unknown Author"
                failed += 1

            # Rate limiting: pause every batch_size requests
            if (i + 1) % batch_size == 0:
                db.commit()
                print(f"  [{i+1}/{total}] API: {enriched} enriched, {failed} failed")
                time.sleep(1)

        db.commit()
        print(f"\nEnrichment complete:")
        print(f"  Enriched: {enriched}/{total}")
        print(f"  Failed/Fallback: {failed}/{total}")

        # Show some examples
        samples = db.query(Book).filter(Book.author_name != None).limit(5).all()
        print("\nSample results:")
        for b in samples:
            print(f"  '{b.title}' by {b.author_name}")

    finally:
        db.close()


if __name__ == "__main__":
    print("Starting author name enrichment...\n")
    enrich_authors()
    print("\nDone!")
