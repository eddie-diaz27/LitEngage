# Dataset Strategy: UCSD Goodreads Young Adult (3-Component Approach)

## Overview

You've chosen to work with **all three components** of the UCSD Goodreads Young Adult dataset, filtered to **5-10K high-quality books**. This provides a rich, comprehensive foundation for building an intelligent book recommendation system.

---

## Dataset Components

### 1. Books Dataset (REQUIRED)
**File:** `goodreads_books_young_adult.json.gz`
- **Size:** 93,398 books (~200 MB compressed, ~500-800 MB uncompressed)
- **Format:** Newline-delimited JSON (one book per line)
- **Key fields:** book_id, title, authors, description, average_rating, ratings_count, popular_shelves, similar_books, publication info, image_url

**What it provides:**
- Complete book metadata for embeddings and search
- User-generated genre tags (from popular_shelves)
- Pre-computed similar books for recommendations
- Book covers for UI display
- Quality signals (ratings, review counts)

### 2. Interactions Dataset (REQUIRED)
**File:** `goodreads_interactions_young_adult.json.gz`
- **Size:** 34,919,254 interactions (~1-2 GB compressed, ~4-6 GB uncompressed)
- **Format:** Newline-delimited JSON (one interaction per line)
- **Key fields:** user_id, book_id, is_read, rating (1-5), date_added

**What it provides:**
- Collaborative filtering data: "Students who liked X also liked Y"
- Implicit preference signals (is_read = true even without rating)
- Temporal reading patterns (when books were added/read)
- User-book affinity matrix for recommendation algorithms
- Real student behavior patterns (anonymized)

### 3. Reviews Dataset (REQUIRED)
**File:** `goodreads_reviews_young_adult.json.gz`
- **Size:** 2,389,900 reviews (~800 MB compressed, ~2-3 GB uncompressed)
- **Format:** Newline-delimited JSON (one review per line)
- **Key fields:** user_id, book_id, review_id, rating, review_text, n_votes, started_at, read_at

**What it provides:**
- **Sentiment analysis:** Understand *why* students like/dislike books
- **Theme extraction:** Identify common themes from review text
- **Qualitative insights:** "Fast-paced," "slow start," "great characters," etc.
- **Reading time data:** started_at → read_at duration (reading speed)
- **Social proof:** n_votes (helpful reviews)

---

## Filtering Strategy: 93K → 5-10K Books

### Why Filter?

**Full dataset challenges:**
- 93K books × 384 embedding dimensions = massive memory footprint
- Hours to generate embeddings vs. 10-20 minutes for 5-10K
- 35M interactions are overwhelming for development/testing
- Slower iteration cycles during development

**Filtered subset benefits:**
- Fast embeddings generation (10-20 minutes)
- Manageable database size (1-2 GB total)
- Quick query responses (<100ms for vector search)
- Still enough data for robust recommendations
- Can expand to full dataset later without code changes

### Three-Stage Filtering Process

```
Stage 1: Filter Books (93K → 5-10K)
    ↓
Stage 2: Filter Interactions (35M → 500K-2M)
    ↓
Stage 3: Filter Reviews (2.4M → 100K-400K)
```

#### Stage 1: Select High-Quality Books

**Criteria:**
```python
ratings_count >= 200      # Well-known books (not obscure)
average_rating >= 3.8     # High quality (not mediocre)
publication_year >= 1990  # Modern + recent classics (not just old books)
language_code == 'eng'    # English only
description != None       # Required for embeddings
```

**Sorting & Selection:**
- Sort by `ratings_count` descending (most popular first)
- Take top 5,000-10,000 books
- Store selected `book_id`s in a set (Python) for stages 2 & 3

**Why these thresholds?**
- `ratings_count >= 200`: Ensures books have sufficient interaction data
- `average_rating >= 3.8`: Filters out poorly-received books (original mean ~3.9)
- `publication_year >= 1990`: Balances modern relevance with timeless classics
- Result: Popular, high-quality books students will recognize

#### Stage 2: Filter Interactions (Linked to Selected Books)

**Process:**
```python
selected_book_ids = set([...])  # From Stage 1

# Read interactions line-by-line (memory efficient)
for interaction in read_interactions_jsonl():
    if interaction['book_id'] in selected_book_ids:
        keep_interaction(interaction)
```

**Result:**
- From 34,919,254 interactions → ~500,000-2,000,000 interactions
- Only interactions for the 5-10K selected books
- Creates a coherent subset (all data aligns)

**Use cases:**
- Build user-item rating matrix for collaborative filtering
- Create synthetic student profiles from `user_id`s
- Analyze reading patterns (which books are read together)

#### Stage 3: Filter Reviews (Linked to Selected Books)

**Process:**
```python
selected_book_ids = set([...])  # Same set from Stage 1

# Read reviews line-by-line
for review in read_reviews_jsonl():
    if review['book_id'] in selected_book_ids and review['review_text']:
        keep_review(review)
```

**Result:**
- From 2,389,900 reviews → ~100,000-400,000 reviews
- Only reviews for selected books with actual text content
- High-quality review corpus for analysis

**Use cases:**
- Sentiment analysis (positive/negative/neutral)
- Theme extraction (friendship, adventure, romance, etc.)
- Understanding what makes books appealing to students
- Future: Generate book "vibes" or mood tags from reviews

---

## Implementation in `scripts/load_books.py`

**Recommended structure:**

```python
import json
from tqdm import tqdm

def load_and_filter_books(input_file, output_db, target_count=7500):
    """Stage 1: Filter books to top 5-10K high-quality subset."""
    
    # Load all books
    books = []
    with open(input_file, 'r') as f:
        for line in tqdm(f, desc="Loading books"):
            book = json.loads(line)
            
            # Apply filters
            if (int(book.get('ratings_count', 0)) >= 200 and
                float(book.get('average_rating', 0)) >= 3.8 and
                int(book.get('publication_year', 0)) >= 1990 and
                book.get('language_code') == 'eng' and
                book.get('description')):
                
                books.append(book)
    
    # Sort by popularity and take top N
    books.sort(key=lambda x: int(x['ratings_count']), reverse=True)
    selected_books = books[:target_count]
    
    # Extract book_ids for stages 2 & 3
    selected_book_ids = {book['book_id'] for book in selected_books}
    
    # Process and insert into database
    for book in selected_books:
        # Extract genres from popular_shelves
        genres = extract_top_genres(book['popular_shelves'], top_n=5)
        
        # Extract primary author
        primary_author = book['authors'][0]['author_id'] if book['authors'] else 'Unknown'
        
        # Insert into Books table
        db.insert_book({
            'id': book['book_id'],
            'title': book['title'],
            'author': primary_author,
            'description': book['description'],
            'genres_json': genres,
            'avg_rating': float(book['average_rating']),
            'ratings_count': int(book['ratings_count']),
            # ... other fields
        })
    
    return selected_book_ids


def load_and_filter_interactions(input_file, selected_book_ids, output_db):
    """Stage 2: Filter interactions to only selected books."""
    
    kept_count = 0
    with open(input_file, 'r') as f:
        for line in tqdm(f, desc="Filtering interactions"):
            interaction = json.loads(line)
            
            if interaction['book_id'] in selected_book_ids:
                # Store interaction for collaborative filtering
                db.insert_interaction(interaction)
                kept_count += 1
    
    print(f"Kept {kept_count:,} interactions for {len(selected_book_ids)} books")


def load_and_filter_reviews(input_file, selected_book_ids, output_db):
    """Stage 3: Filter reviews to only selected books."""
    
    kept_count = 0
    with open(input_file, 'r') as f:
        for line in tqdm(f, desc="Filtering reviews"):
            review = json.loads(line)
            
            if (review['book_id'] in selected_book_ids and 
                review.get('review_text', '').strip()):
                
                # Store review for sentiment analysis
                db.insert_review(review)
                kept_count += 1
    
    print(f"Kept {kept_count:,} reviews for {len(selected_book_ids)} books")


# Main execution
if __name__ == "__main__":
    # Stage 1
    selected_book_ids = load_and_filter_books(
        'data/raw/goodreads_books_young_adult.json',
        db,
        target_count=7500  # Adjust between 5000-10000
    )
    
    # Stage 2
    load_and_filter_interactions(
        'data/raw/goodreads_interactions_young_adult.json',
        selected_book_ids,
        db
    )
    
    # Stage 3
    load_and_filter_reviews(
        'data/raw/goodreads_reviews_young_adult.json',
        selected_book_ids,
        db
    )
```

---

## Database Schema Changes

**New table added: `book_reviews`**

```python
class BookReview(Base):
    __tablename__ = "book_reviews"
    
    id = Column(Integer, primary_key=True)
    review_id = Column(String, unique=True, index=True)
    user_id = Column(String, index=True)  # Anonymized
    book_id = Column(String, ForeignKey("books.id"), index=True)
    rating = Column(Integer)  # 1-5
    review_text = Column(Text)
    date_added = Column(DateTime)
    n_votes = Column(Integer)  # Helpfulness votes
    sentiment = Column(String)  # "positive", "negative", "neutral" (computed)
    themes_extracted_json = Column(JSON)  # For future theme extraction
    
    book = relationship("Book")
```

---

## Benefits of This Approach

### Immediate Benefits (MVP)
1. **Fast Development**: 5-10K books = quick embeddings, fast queries
2. **Quality Recommendations**: Only popular, well-rated books
3. **Collaborative Filtering**: Interaction data enables "students who liked X also liked Y"
4. **Rich Context**: Reviews explain *why* students like books

### Future Enhancements (Post-MVP)
1. **Sentiment Analysis**: Analyze review_text to understand book appeal
2. **Theme Extraction**: NLP on reviews to identify themes (friendship, adventure, etc.)
3. **Reading Time Analysis**: started_at → read_at duration for pacing insights
4. **Social Proof**: n_votes to highlight most helpful reviews
5. **Review-Based Search**: "Find books reviewers describe as 'fast-paced' or 'emotional'"

### Scalability
- Same code works for 5K or 93K books
- Just change `target_count` parameter
- Can expand to full dataset when ready
- No architectural changes needed

---

## Expected Dataset Sizes After Filtering

| Component | Original | Filtered | Reduction |
|-----------|----------|----------|-----------|
| Books | 93,398 | 5,000-10,000 | 89-95% |
| Interactions | 34,919,254 | 500K-2M | 94-98% |
| Reviews | 2,389,900 | 100K-400K | 83-96% |
| **Total Disk** | ~10-15 GB | ~1-2 GB | ~90% |

**Processing Times (approximate):**
- Loading books: ~2-3 minutes
- Filtering interactions: ~10-15 minutes (35M records)
- Filtering reviews: ~5-8 minutes (2.4M records)
- Generating embeddings: ~10-20 minutes (5-10K books)
- **Total:** ~30-45 minutes one-time setup

---

## Quality Validation Checklist

After running `scripts/load_books.py`, verify:

```sql
-- Check book count
SELECT COUNT(*) FROM books;  -- Should be 5,000-10,000

-- Check average rating (should be high)
SELECT AVG(avg_rating), MIN(avg_rating), MAX(avg_rating) FROM books;
-- Expected: AVG ~4.1-4.3, MIN >= 3.8, MAX ~5.0

-- Check rating counts (should be substantial)
SELECT AVG(ratings_count), MIN(ratings_count) FROM books;
-- Expected: AVG ~5,000-20,000, MIN >= 200

-- Check publication years (modern + classics)
SELECT MIN(publication_year), MAX(publication_year) FROM books;
-- Expected: MIN ~1990-1995, MAX ~2017

-- Check interactions count
SELECT COUNT(*) FROM reading_history;  -- Or interactions table
-- Expected: 500,000-2,000,000

-- Check reviews count
SELECT COUNT(*) FROM book_reviews WHERE review_text IS NOT NULL;
-- Expected: 100,000-400,000

-- Most popular books (sanity check - should be recognizable titles)
SELECT title, author, ratings_count, avg_rating 
FROM books 
ORDER BY ratings_count DESC 
LIMIT 10;
-- Should see popular YA books like Harry Potter, Hunger Games, Twilight, etc.
```

---

## Citation Requirements

When using this dataset, include these citations:

```
Mengting Wan, Julian McAuley. "Item Recommendation on Monotonic Behavior Chains." 
RecSys 2018.

Mengting Wan, Rishabh Misra, Ndapa Nakashole, Julian McAuley. 
"Fine-Grained Spoiler Detection from Large-Scale Review Corpora." ACL 2019.
```

---

## Next Steps

1. **Download all three datasets** (see SETUP_GUIDE.md)
2. **Decompress files** to `data/raw/`
3. **Implement `scripts/load_books.py`** with 3-stage filtering
4. **Run the script** and verify counts
5. **Generate embeddings** with `scripts/generate_embeddings.py`
6. **Create sample students** from interaction data
7. **Start building the agent!**

---

## Questions & Troubleshooting

**Q: Why 5-10K instead of using all 93K books?**
A: Development speed. Embeddings for 93K books take hours and consume GBs of RAM. 5-10K is the sweet spot for fast iteration while maintaining quality.

**Q: Can I change the filters (e.g., lower rating threshold)?**
A: Yes! Adjust the thresholds in `load_books.py`. Just ensure you still get high-quality books.

**Q: Should I filter interactions/reviews in the same script?**
A: Yes, it's most efficient. Load books first to get `selected_book_ids`, then stream-filter the larger files.

**Q: What if I want more than 10K books later?**
A: Just change `target_count` and re-run. The architecture supports it.

**Q: Do I need all three datasets for MVP?**
A: Books are essential. Interactions enable collaborative filtering (recommended). Reviews enable sentiment analysis (nice-to-have for MVP, powerful for later enhancements).

You chose wisely to download all three. This gives you maximum flexibility! 🎉
