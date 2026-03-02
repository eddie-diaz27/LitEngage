"""Reusable book display components for Streamlit."""

import streamlit as st


def render_book_card(book: dict):
    """Render a book card with cover, title, author, genres, and rating."""
    with st.container(border=True):
        col1, col2 = st.columns([1, 3])
        with col1:
            image_url = book.get("image_url")
            if image_url and image_url.strip():
                st.image(image_url, width=100)
            else:
                st.markdown("**No Cover**")
        with col2:
            st.markdown(f"### {book.get('title', 'Unknown Title')}")
            author = book.get("author_name") or book.get("author", "Unknown")
            st.markdown(f"*by {author}*")

            genres = book.get("genres_json") or book.get("genres") or []
            if genres:
                genre_str = " | ".join(genres[:3])
                st.caption(genre_str)

            rating = book.get("avg_rating")
            ratings_count = book.get("ratings_count")
            if rating:
                stars = int(round(rating))
                star_display = "★" * stars + "☆" * (5 - stars)
                rating_text = f"{star_display} {rating:.1f}"
                if ratings_count:
                    rating_text += f" ({ratings_count:,} ratings)"
                st.markdown(rating_text)

            desc = book.get("description", "")
            if desc:
                st.markdown(desc[:200] + ("..." if len(desc) > 200 else ""))


def render_book_list_item(book: dict):
    """Render a compact book list item."""
    title = book.get("title", "Unknown")
    author = book.get("author_name") or book.get("author", "Unknown")
    rating = book.get("avg_rating", 0)

    col1, col2, col3 = st.columns([4, 2, 1])
    with col1:
        st.markdown(f"**{title}**")
    with col2:
        st.markdown(f"*{author}*")
    with col3:
        if rating:
            st.markdown(f"{rating:.1f} ★")
