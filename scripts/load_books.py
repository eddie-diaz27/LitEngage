"""Three-stage data loading pipeline.

Stage 1: Filter 93K books -> ~7,500 high-quality YA books
Stage 2: Filter 35M interactions -> only for selected books
Stage 3: Filter 2.4M reviews -> only for selected books with text
"""

import json
import logging
import os
import sys
from datetime import datetime

from tqdm import tqdm

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import settings
from backend.database.connection import SessionLocal
from backend.database.models import Book, BookReview, ReadingHistory  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Shelf names that are NOT genres (organizational/format shelves)
EXCLUDED_SHELVES = {
    "to-read", "currently-reading", "favorites", "favourites",
    "books-i-own", "owned", "owned-books", "default", "library",
    "kindle", "ebook", "ebooks", "e-book", "e-books",
    "audiobook", "audiobooks", "audio", "my-books", "my-library",
    "wish-list", "to-buy", "i-own", "tbr", "have", "re-read",
    "dnf", "did-not-finish", "abandoned", "reviewed", "arc",
    "netgalley", "need-to-buy", "paperback", "hardcover",
    "young-adult", "ya", "ya-fiction", "teen", "teens",
    "fiction", "novels", "novel", "series",
}


def _safe_int(val, default=0):
    """Safely parse a string to int."""
    if not val:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_float(val, default=0.0):
    """Safely parse a string to float."""
    if not val:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def extract_genres(popular_shelves: list, top_n: int = 5) -> list:
    """Extract genre names from popular_shelves, filtering out non-genre tags."""
    genres = []
    for shelf in popular_shelves:
        name = shelf.get("name", "").lower().strip()
        if name and name not in EXCLUDED_SHELVES:
            genres.append(name)
        if len(genres) >= top_n:
            break
    return genres


def extract_primary_author(authors: list) -> str:
    """Extract the primary author_id from the authors list.

    The dataset only provides author_ids, not names.
    We store the ID and can enrich later via Open Library.
    """
    if not authors:
        return "Unknown"
    # First author without a translator/editor role is the primary
    for author in authors:
        role = author.get("role", "").lower()
        if not role or role == "":
            return author.get("author_id", "Unknown")
    return authors[0].get("author_id", "Unknown")


def _parse_goodreads_date(date_str: str):
    """Parse Goodreads date strings like 'Wed Mar 29 00:12:52 -0700 2017'."""
    if not date_str or not date_str.strip():
        return None
    try:
        # Remove timezone offset for simpler parsing
        parts = date_str.split()
        if len(parts) >= 6:
            # Remove the timezone part (e.g., -0700)
            clean = " ".join(parts[:4]) + " " + parts[-1]
            return datetime.strptime(clean, "%a %b %d %H:%M:%S %Y")
    except (ValueError, IndexError):
        pass
    return None


def stage1_filter_books(raw_dir: str, target_count: int = 7500) -> tuple:
    """Filter books to top N high-quality subset.

    Returns: (selected_book_ids set, list of book dicts for DB insertion)
    """
    books_file = os.path.join(raw_dir, "goodreads_books_young_adult.json")
    if not os.path.exists(books_file):
        logger.error(f"Books file not found: {books_file}")
        sys.exit(1)

    logger.info(f"Stage 1: Loading and filtering books from {books_file}")

    candidates = []
    total_read = 0

    with open(books_file, "r", encoding="utf-8") as f:
        for line in tqdm(f, desc="Reading books", total=93398):
            total_read += 1
            try:
                book = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            ratings_count = _safe_int(book.get("ratings_count"))
            avg_rating = _safe_float(book.get("average_rating"))
            pub_year = _safe_int(book.get("publication_year"))
            lang = book.get("language_code", "")
            description = (book.get("description") or "").strip()

            # Apply quality filters
            if (
                ratings_count >= 200
                and avg_rating >= 3.8
                and pub_year >= 1990
                and lang == "eng"
                and len(description) > 20
            ):
                candidates.append(book)

    logger.info(
        f"Read {total_read} books, {len(candidates)} passed filters"
    )

    # Sort by popularity and take top N
    candidates.sort(key=lambda x: _safe_int(x.get("ratings_count")), reverse=True)
    selected = candidates[:target_count]

    logger.info(f"Selected top {len(selected)} books by ratings_count")

    # Build book records for DB
    selected_ids = set()
    book_records = []

    for book in selected:
        book_id = book["book_id"]
        selected_ids.add(book_id)

        genres = extract_genres(book.get("popular_shelves", []))
        primary_author = extract_primary_author(book.get("authors", []))

        record = {
            "id": book_id,
            "isbn": book.get("isbn") or None,
            "isbn13": book.get("isbn13") or None,
            "title": book.get("title", "Unknown Title"),
            "title_without_series": book.get("title_without_series") or None,
            "author": primary_author,
            "authors_json": book.get("authors"),
            "description": book.get("description") or None,
            "genres_json": genres,
            "popular_shelves_json": book.get("popular_shelves"),
            "similar_books_json": book.get("similar_books"),
            "reading_level": "middle-school",  # Default for YA dataset
            "age_appropriate": "12-18",
            "publication_year": _safe_int(book.get("publication_year")) or None,
            "publication_month": _safe_int(book.get("publication_month")) or None,
            "publication_day": _safe_int(book.get("publication_day")) or None,
            "publisher": book.get("publisher") or None,
            "format": book.get("format") or None,
            "num_pages": _safe_int(book.get("num_pages")) or None,
            "language_code": book.get("language_code") or "eng",
            "country_code": book.get("country_code") or None,
            "avg_rating": _safe_float(book.get("average_rating")),
            "ratings_count": _safe_int(book.get("ratings_count")),
            "text_reviews_count": _safe_int(book.get("text_reviews_count")),
            "image_url": book.get("image_url") or None,
            "goodreads_link": book.get("link") or None,
            "series_json": book.get("series") or None,
        }
        book_records.append(record)

    # Print stats
    if selected:
        top = selected[0]
        bottom = selected[-1]
        logger.info(f"Top book: {top['title']} ({_safe_int(top.get('ratings_count'))} ratings)")
        logger.info(
            f"Bottom book: {bottom['title']} ({_safe_int(bottom.get('ratings_count'))} ratings)"
        )

    return selected_ids, book_records


def stage2_filter_interactions(
    raw_dir: str, selected_book_ids: set, processed_dir: str
) -> int:
    """Filter interactions to only selected books.

    Saves to a processed JSONL file for future collaborative filtering.
    These interactions use anonymous user_ids from the dataset (not our app
    students), so they can't go into reading_history which has FK constraints.
    """
    interactions_file = os.path.join(
        raw_dir, "goodreads_interactions_young_adult.json"
    )
    if not os.path.exists(interactions_file):
        logger.warning(f"Interactions file not found: {interactions_file}, skipping Stage 2")
        return 0

    logger.info(f"Stage 2: Filtering interactions from {interactions_file}")

    os.makedirs(processed_dir, exist_ok=True)
    output_file = os.path.join(processed_dir, "filtered_interactions.jsonl")

    kept = 0
    skipped = 0

    with open(interactions_file, "r", encoding="utf-8") as fin, \
         open(output_file, "w", encoding="utf-8") as fout:
        for line in tqdm(fin, desc="Filtering interactions", total=34919254):
            try:
                interaction = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            book_id = interaction.get("book_id")
            if book_id not in selected_book_ids:
                skipped += 1
                continue

            fout.write(line)
            kept += 1

    logger.info(f"Kept {kept:,} interactions, skipped {skipped:,}")
    logger.info(f"Saved to {output_file}")
    return kept


def stage3_filter_reviews(
    raw_dir: str, selected_book_ids: set, db_session
) -> int:
    """Filter reviews to only selected books with non-empty text."""
    reviews_file = os.path.join(raw_dir, "goodreads_reviews_young_adult.json")
    if not os.path.exists(reviews_file):
        logger.warning(f"Reviews file not found: {reviews_file}, skipping Stage 3")
        return 0

    logger.info(f"Stage 3: Filtering reviews from {reviews_file}")

    kept = 0
    skipped = 0
    batch = []
    batch_size = 5000

    with open(reviews_file, "r", encoding="utf-8") as f:
        for line in tqdm(f, desc="Filtering reviews", total=2389900):
            try:
                review = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            book_id = review.get("book_id")
            review_text = (review.get("review_text") or "").strip()

            if book_id not in selected_book_ids or not review_text:
                skipped += 1
                continue

            record = {
                "review_id": review.get("review_id", ""),
                "user_id": review.get("user_id", ""),
                "book_id": book_id,
                "rating": review.get("rating", 0) or None,
                "review_text": review_text,
                "date_added": _parse_goodreads_date(review.get("date_added", "")),
                "date_updated": _parse_goodreads_date(review.get("date_updated", "")),
                "n_votes": review.get("n_votes", 0),
                "n_comments": review.get("n_comments", 0),
                "started_at": _parse_goodreads_date(review.get("started_at", "")),
                "read_at": _parse_goodreads_date(review.get("read_at", "")),
            }
            batch.append(record)
            kept += 1

            if len(batch) >= batch_size:
                db_session.bulk_insert_mappings(BookReview, batch)
                db_session.commit()
                batch = []

    # Insert remaining
    if batch:
        db_session.bulk_insert_mappings(BookReview, batch)
        db_session.commit()

    logger.info(f"Kept {kept:,} reviews, skipped {skipped:,}")
    return kept


def main():
    raw_dir = settings.raw_data_dir
    target_count = settings.max_books_to_load or 7500

    logger.info(f"Starting data loading pipeline (target: {target_count} books)")
    logger.info(f"Raw data directory: {raw_dir}")

    db = SessionLocal()

    try:
        # Stage 1: Filter and load books
        selected_ids, book_records = stage1_filter_books(raw_dir, target_count)

        logger.info(f"Inserting {len(book_records)} books into database...")
        for i in range(0, len(book_records), 1000):
            batch = book_records[i : i + 1000]
            db.bulk_insert_mappings(Book, batch)
            db.commit()
        logger.info(f"Stage 1 complete: {len(book_records)} books loaded")

        # Stage 2: Filter interactions (save to processed file, not DB)
        interaction_count = stage2_filter_interactions(
            raw_dir, selected_ids, settings.processed_data_dir
        )
        logger.info(f"Stage 2 complete: {interaction_count:,} interactions saved")

        # Stage 3: Filter reviews
        review_count = stage3_filter_reviews(raw_dir, selected_ids, db)
        logger.info(f"Stage 3 complete: {review_count:,} reviews loaded")

        # Print summary
        print("\n" + "=" * 60)
        print("DATA LOADING SUMMARY")
        print("=" * 60)
        print(f"Books loaded:        {len(book_records):>10,}")
        print(f"Interactions loaded: {interaction_count:>10,}")
        print(f"Reviews loaded:      {review_count:>10,}")
        print("=" * 60)

    except Exception as e:
        logger.error(f"Error during data loading: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
