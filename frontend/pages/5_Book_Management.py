"""Book Management - Add, edit, delete books and moderate reviews."""

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

if user["role"] != "librarian":
    st.error("Only librarians can access this page.")
    st.stop()

with st.sidebar:
    st.markdown(f"**{user['display_name']}**")
    st.caption(f"Role: {user['role'].title()}")
    if st.button("Logout"):
        logout()
        st.rerun()

st.title("📕 Book Management")

tab_add, tab_edit, tab_reviews = st.tabs(["Add Book", "Edit / Delete Book", "Review Moderation"])

# ------------------------------------------------------------------
# Tab 1: Add Book
# ------------------------------------------------------------------
with tab_add:
    st.markdown("#### Add a New Book")

    with st.form("add_book_form"):
        ab_title = st.text_input("Title *")
        ab_author = st.text_input("Author *")
        ab_desc = st.text_area("Description")
        ab_col1, ab_col2 = st.columns(2)
        with ab_col1:
            ab_level = st.selectbox(
                "Reading Level",
                ["elementary", "middle-school", "high-school"],
                index=1,
            )
            ab_year = st.number_input("Publication Year", min_value=1900, max_value=2026, value=2020)
        with ab_col2:
            ab_pages = st.number_input("Number of Pages", min_value=1, max_value=5000, value=200)
            ab_isbn = st.text_input("ISBN (optional)")

        ab_genres = st.text_input("Genres (comma separated)", placeholder="Fantasy, Adventure, Young Adult")
        ab_image = st.text_input("Cover Image URL (optional)")

        if st.form_submit_button("Add Book", type="primary"):
            if not ab_title or not ab_author:
                st.error("Title and Author are required.")
            else:
                genres_list = [g.strip() for g in ab_genres.split(",") if g.strip()] if ab_genres else None
                try:
                    result = api.create_book({
                        "title": ab_title,
                        "author": ab_author,
                        "author_name": ab_author,
                        "description": ab_desc or None,
                        "genres_json": genres_list,
                        "reading_level": ab_level,
                        "publication_year": ab_year,
                        "num_pages": ab_pages,
                        "image_url": ab_image or None,
                        "isbn": ab_isbn or None,
                    })
                    st.success(f"Book '{ab_title}' added successfully! (ID: {result.get('id', 'N/A')})")
                except Exception as e:
                    st.error(f"Failed to add book: {e}")

# ------------------------------------------------------------------
# Tab 2: Edit / Delete Book (Catalog-style layout)
# ------------------------------------------------------------------
with tab_edit:
    search_query = st.text_input(
        "Filter by title",
        key="edit_search",
        placeholder="Type to filter... (leave empty to see top books by popularity)",
    )

    # Always fetch books — empty query returns top 20 by popularity
    try:
        results = api.title_search_books(q=search_query, limit=20)
    except Exception:
        results = []

    if results:
        st.caption(f"Showing {len(results)} book(s)")

        for i, book in enumerate(results):
            book_id = book.get("id", "")
            title = book.get("title", "Unknown")
            author = book.get("author_name") or book.get("author", "Unknown")
            desc = book.get("description", "")
            rating = book.get("avg_rating")
            image = book.get("image_url")
            genres = book.get("genres_json") or []
            level = book.get("reading_level", "")

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
                    if level:
                        st.caption(level.title())

                # Expandable edit form
                with st.expander("Edit / Delete"):
                    with st.form(key=f"edit_form_{i}_{book_id}"):
                        ed_title = st.text_input("Title", value=title, key=f"ed_title_{i}")
                        ed_author = st.text_input("Author", value=author, key=f"ed_author_{i}")
                        ed_desc = st.text_area(
                            "Description",
                            value=desc,
                            key=f"ed_desc_{i}",
                        )
                        ed_col1, ed_col2 = st.columns(2)
                        with ed_col1:
                            ed_level = st.selectbox(
                                "Reading Level",
                                ["elementary", "middle-school", "high-school"],
                                index=["elementary", "middle-school", "high-school"].index(level)
                                if level in ["elementary", "middle-school", "high-school"]
                                else 1,
                                key=f"ed_level_{i}",
                            )
                        with ed_col2:
                            ed_genres = st.text_input(
                                "Genres (comma separated)",
                                value=", ".join(genres),
                                key=f"ed_genres_{i}",
                            )
                        ed_image = st.text_input(
                            "Cover Image URL",
                            value=image or "",
                            key=f"ed_image_{i}",
                        )

                        ec1, ec2 = st.columns(2)
                        with ec1:
                            save_clicked = st.form_submit_button("Save Changes", type="primary")
                        with ec2:
                            delete_clicked = st.form_submit_button("Delete Book")

                        if save_clicked:
                            genres_list = (
                                [g.strip() for g in ed_genres.split(",") if g.strip()]
                                if ed_genres
                                else None
                            )
                            try:
                                api.update_book(book_id, {
                                    "title": ed_title,
                                    "author": ed_author,
                                    "author_name": ed_author,
                                    "description": ed_desc or None,
                                    "genres_json": genres_list,
                                    "reading_level": ed_level,
                                    "image_url": ed_image or None,
                                })
                                st.success(f"Book '{ed_title}' updated!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to update: {e}")

                        if delete_clicked:
                            try:
                                api.delete_book(book_id)
                                st.success(f"Book '{title}' deleted.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to delete: {e}")
    else:
        st.info("No books found. Try a different search term.")

# ------------------------------------------------------------------
# Tab 3: Review Moderation
# ------------------------------------------------------------------
with tab_reviews:
    st.markdown("#### Student Review Moderation")
    st.caption("AI-assisted moderation flags potential issues. You make the final decision.")

    # Summary metrics
    try:
        all_reviews = api.get_recent_reviews(limit=200, include_hidden=True)
    except Exception:
        all_reviews = []

    flagged = [r for r in all_reviews if r.get("moderation_status") == "flagged"]
    pending = [r for r in all_reviews if r.get("moderation_status") == "pending"]
    hidden = [r for r in all_reviews if not r.get("is_approved", True)]
    approved = [r for r in all_reviews if r.get("is_approved", True)]

    rm1, rm2, rm3, rm4 = st.columns(4)
    with rm1:
        st.metric("Flagged", len(flagged))
    with rm2:
        st.metric("Pending Scan", len(pending))
    with rm3:
        st.metric("Hidden", len(hidden))
    with rm4:
        if st.button("Scan All Pending"):
            try:
                result = api.trigger_review_scan()
                st.success(f"Scanned {result.get('scanned', 0)} reviews. Flagged: {result.get('flagged', 0)}")
                st.rerun()
            except Exception as e:
                st.error(f"Scan failed: {e}")

    # Flagged reviews first
    if flagged:
        st.markdown("---")
        st.markdown(f"**AI-Flagged Reviews ({len(flagged)})**")
        for rev in flagged:
            with st.container(border=True):
                mc1, mc2, mc3 = st.columns([3, 1.5, 1])
                with mc1:
                    st.markdown(
                        f"**{rev.get('student_name', 'Unknown')}** reviewed "
                        f"*{rev.get('book_title', 'Unknown')}*"
                    )
                    if rev.get("review_text"):
                        st.caption(rev["review_text"][:300])
                    # Show moderation info
                    flags = rev.get("moderation_flags") or []
                    reason = rev.get("moderation_reason", "")
                    if flags:
                        flag_pills = " ".join(
                            f"**`{f}`**" for f in flags
                        )
                        st.markdown(f"Flags: {flag_pills}")
                    if reason:
                        st.caption(f"AI reason: {reason}")
                with mc2:
                    stars = rev.get("rating", 0)
                    st.markdown(f"{'⭐' * stars} ({stars}/5)")
                    status = "Hidden" if not rev.get("is_approved") else "Visible"
                    st.caption(status)
                with mc3:
                    review_id = rev.get("id")
                    if not rev.get("is_approved"):
                        if st.button("Approve", key=f"approve_flagged_{review_id}"):
                            try:
                                api.moderate_review(review_id, is_approved=True)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")
                    else:
                        if st.button("Hide", key=f"hide_flagged_{review_id}"):
                            try:
                                api.moderate_review(review_id, is_approved=False)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")

    # Hidden (non-flagged) reviews
    hidden_non_flagged = [r for r in hidden if r.get("moderation_status") != "flagged"]
    if hidden_non_flagged:
        st.markdown("---")
        st.markdown(f"**Hidden Reviews ({len(hidden_non_flagged)})**")
        for rev in hidden_non_flagged:
            with st.container(border=True):
                mc1, mc2, mc3 = st.columns([3, 1, 1])
                with mc1:
                    st.markdown(
                        f"**{rev.get('student_name', 'Unknown')}** reviewed "
                        f"*{rev.get('book_title', 'Unknown')}*"
                    )
                    if rev.get("review_text"):
                        st.caption(rev["review_text"][:300])
                with mc2:
                    stars = rev.get("rating", 0)
                    st.markdown(f"{'⭐' * stars} ({stars}/5)")
                with mc3:
                    review_id = rev.get("id")
                    if st.button("Approve", key=f"approve_hidden_{review_id}"):
                        try:
                            api.moderate_review(review_id, is_approved=True)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")

    # Approved reviews
    if approved:
        st.markdown("---")
        st.markdown(f"**Approved Reviews** ({len(approved)} shown)")
        for rev in approved:
            if rev.get("moderation_status") == "flagged":
                continue  # Already shown above
            with st.container(border=True):
                mc1, mc2, mc3 = st.columns([3, 1, 1])
                with mc1:
                    st.markdown(
                        f"**{rev.get('student_name', 'Unknown')}** reviewed "
                        f"*{rev.get('book_title', 'Unknown')}*"
                    )
                    if rev.get("review_text"):
                        st.caption(rev["review_text"][:300])
                with mc2:
                    stars = rev.get("rating", 0)
                    st.markdown(f"{'⭐' * stars} ({stars}/5)")
                    mod_status = rev.get("moderation_status", "")
                    if mod_status == "clean":
                        st.caption("AI: Clean")
                    elif mod_status == "pending":
                        st.caption("AI: Pending")
                with mc3:
                    review_id = rev.get("id")
                    if st.button("Hide", key=f"hide_approved_{review_id}"):
                        try:
                            api.moderate_review(review_id, is_approved=False)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")

    if not all_reviews:
        st.info("No student reviews found.")
