"""Book Catalog Browser - Search, browse, review, and add to reading list."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st

from utils.auth import get_current_user, logout
from utils.api_client import api

user = get_current_user()
if not user:
    st.warning("Please log in first.")
    st.stop()

student_id = user.get("student_id")

with st.sidebar:
    st.markdown(f"**{user['display_name']}**")
    st.caption(f"Role: {user['role'].title()}")
    if st.button("Logout"):
        logout()
        st.rerun()

st.title("📖 Book Catalog")

# ------------------------------------------------------------------
# Search and filters
# ------------------------------------------------------------------
col_search, col_level, col_rating = st.columns([3, 1, 1])

with col_search:
    search_query = st.text_input(
        "Search books",
        placeholder="e.g., adventure with magic, dystopian society...",
    )

with col_level:
    reading_level = st.selectbox(
        "Reading Level",
        ["All", "elementary", "middle-school", "high-school"],
    )

with col_rating:
    min_rating = st.slider("Min Rating", 0.0, 5.0, 0.0, 0.5)


def render_book_with_actions(book, idx_prefix=""):
    """Render a book card with add-to-list and review actions."""
    book_id = book.get("id") or book.get("book_id", "")
    title = book.get("title", "Unknown")
    author = book.get("author_name") or book.get("author", "Unknown")
    desc = book.get("description", "")
    rating = book.get("avg_rating")
    image = book.get("image_url")
    genres = book.get("genres_json") or book.get("genres") or []

    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 3, 1])
        with c1:
            if image and image.strip():
                st.image(image, width=90)
            else:
                st.markdown("📕")
        with c2:
            st.markdown(f"**{title}**")
            st.caption(f"by {author}")
            if genres:
                st.caption(" | ".join(genres[:4]))
            if desc:
                st.markdown(desc[:200] + ("..." if len(desc) > 200 else ""))
        with c3:
            if rating:
                stars = int(round(rating))
                st.markdown(f"{'⭐' * stars} {rating:.1f}")

            # Add to reading list
            if student_id and user["role"] == "student":
                if st.button("📚 Add to List", key=f"add_{idx_prefix}_{book_id}"):
                    try:
                        api.add_to_reading_list(student_id, book_id, "wishlist")
                        st.success("Added to your reading list!")
                    except Exception as e:
                        err = str(e)
                        if "409" in err:
                            st.info("Already in your reading list.")
                        else:
                            st.error(f"Failed: {e}")

        # Expandable reviews section
        with st.expander("Student Reviews"):
            try:
                reviews = api.get_book_reviews(book_id)
                if reviews:
                    for rev in reviews[:5]:
                        st.markdown(f"{'⭐' * rev.get('rating', 0)} — **{rev.get('student_name', 'Anonymous')}**")
                        if rev.get("review_text"):
                            st.caption(rev["review_text"][:200])
                        st.markdown("---")
                else:
                    st.caption("No reviews yet.")
            except Exception:
                st.caption("Could not load reviews.")

            # Write review form (only for students with the book in their history)
            if student_id and user["role"] == "student":
                with st.form(key=f"review_form_{idx_prefix}_{book_id}"):
                    st.markdown("**Write a Review**")
                    rev_rating = st.slider("Rating", 1, 5, 4, key=f"rev_rat_{idx_prefix}_{book_id}")
                    rev_text = st.text_area("Your review (optional)", key=f"rev_txt_{idx_prefix}_{book_id}")
                    if st.form_submit_button("Submit Review"):
                        try:
                            api.create_review(student_id, book_id, rev_rating, rev_text or None)
                            st.success("Review submitted!")
                            st.rerun()
                        except Exception as e:
                            err = str(e)
                            if "409" in err:
                                st.info("You already reviewed this book.")
                            elif "400" in err:
                                st.warning("You can only review books in your reading list.")
                            else:
                                st.error(f"Failed: {e}")


# ------------------------------------------------------------------
# Search results
# ------------------------------------------------------------------
if search_query:
    st.markdown(f"### Search Results for: *{search_query}*")
    try:
        level_filter = reading_level if reading_level != "All" else None
        results = api.search_books(
            query=search_query,
            reading_level=level_filter,
            max_results=12,
        )
        if results:
            for i, result in enumerate(results):
                render_book_with_actions(result, f"search_{i}")
        else:
            st.info("No books found matching your search. Try different keywords.")
    except Exception as e:
        st.error(f"Search failed: {e}")

else:
    # ------------------------------------------------------------------
    # Browse catalog (paginated)
    # ------------------------------------------------------------------
    st.markdown("### Browse Catalog")

    if "catalog_page" not in st.session_state:
        st.session_state.catalog_page = 0

    page_size = 10
    skip = st.session_state.catalog_page * page_size

    try:
        level_filter = reading_level if reading_level != "All" else None
        rating_filter = min_rating if min_rating > 0 else None

        data = api.get_books(
            skip=skip,
            limit=page_size,
            reading_level=level_filter,
            min_rating=rating_filter,
        )

        books = data.get("books", [])
        total = data.get("total", 0)

        st.caption(f"Showing {skip + 1}-{min(skip + page_size, total)} of {total:,} books")

        for i, book in enumerate(books):
            render_book_with_actions(book, f"browse_{i}")

        # Pagination
        col_prev, col_info, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.session_state.catalog_page > 0:
                if st.button("← Previous"):
                    st.session_state.catalog_page -= 1
                    st.rerun()
        with col_info:
            total_pages = max((total + page_size - 1) // page_size, 1)
            st.markdown(f"Page {st.session_state.catalog_page + 1} of {total_pages}")
        with col_next:
            if skip + page_size < total:
                if st.button("Next →"):
                    st.session_state.catalog_page += 1
                    st.rerun()

    except Exception as e:
        st.error(f"Could not load books: {e}")
