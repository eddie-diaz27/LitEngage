"""Book Catalog Browser - Search and browse the book collection."""

import streamlit as st

st.set_page_config(page_title="Catalog - LitEngage", page_icon="📖", layout="wide")

from frontend.components.book_card import render_book_card
from frontend.utils.api_client import api

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
            for result in results:
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{result.get('title', 'Unknown')}**")
                        st.markdown(f"*by {result.get('author', 'Unknown')}*")
                        desc = result.get("description", "")
                        if desc:
                            st.markdown(desc[:200] + "..." if len(desc) > 200 else desc)
                    with col2:
                        rating = result.get("avg_rating")
                        if rating:
                            st.markdown(f"⭐ {rating:.1f}")
        else:
            st.info("No books found matching your search. Try different keywords.")
    except Exception as e:
        st.error(f"Search failed: {e}")

else:
    # ------------------------------------------------------------------
    # Browse catalog (paginated)
    # ------------------------------------------------------------------
    st.markdown("### Browse Catalog")

    # Pagination
    if "catalog_page" not in st.session_state:
        st.session_state.catalog_page = 0

    page_size = 12
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

        # Display books in a grid
        for i in range(0, len(books), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                idx = i + j
                if idx < len(books):
                    with col:
                        render_book_card(books[idx])

        # Pagination controls
        col_prev, col_info, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.session_state.catalog_page > 0:
                if st.button("← Previous"):
                    st.session_state.catalog_page -= 1
                    st.rerun()
        with col_info:
            total_pages = (total + page_size - 1) // page_size
            st.markdown(
                f"Page {st.session_state.catalog_page + 1} of {total_pages}"
            )
        with col_next:
            if skip + page_size < total:
                if st.button("Next →"):
                    st.session_state.catalog_page += 1
                    st.rerun()

    except Exception as e:
        st.error(f"Could not load books: {e}")
