"""Student Dashboard - Gamification, reading history, recommendations, and leaderboard."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st

from utils.auth import get_current_user, logout
from utils.api_client import api

# Auth check
user = get_current_user()
if not user:
    st.warning("Please log in first.")
    st.stop()

if user["role"] != "student":
    st.error("This page is for students only.")
    st.stop()

student_id = user.get("student_id")

# Sidebar
with st.sidebar:
    st.markdown(f"**{user['display_name']}**")
    st.caption("Role: Student")
    if st.button("Logout"):
        logout()
        st.rerun()

st.title(f"Welcome back, {user['display_name'].split()[0]}!")

# ======================================================================
# ROW 1: Gamification stats (full width)
# ======================================================================
try:
    streak = api.get_streak(student_id)
    goal = api.get_reading_goal(student_id)
    badges = api.get_badges(student_id)

    g1, g2, g3, g4 = st.columns(4)
    with g1:
        st.metric("Streak", f"{streak.get('current_streak', 0)} days")
    with g2:
        st.metric("Badges Earned", len(badges))
    with g3:
        target = goal.get("target_books", 3)
        completed = goal.get("books_completed", 0)
        st.metric("Monthly Goal", f"{completed} / {target} books")
    with g4:
        progress = goal.get("progress_pct", 0)
        st.metric("Goal Progress", f"{progress:.0f}%")

    st.progress(min(progress / 100.0, 1.0))

    if badges:
        badge_names = [b["badge_name"] for b in badges[:8]]
        st.caption("Badges: " + "  |  ".join(badge_names))

except Exception:
    st.caption("Gamification data unavailable.")

st.markdown("---")

# ======================================================================
# ROW 2: Recommendations (left, wider) + Leaderboard (right)
# ======================================================================
rec_col, leader_col = st.columns([3, 2])

with rec_col:
    st.subheader("Top Picks For You")

    # Recommendations are pre-fetched at login; fallback to on-demand if missing
    if "auto_recs" not in st.session_state:
        st.session_state.auto_recs = None

    needs_refresh = st.session_state.get("auto_recs_refresh", False)

    if st.session_state.auto_recs is None or needs_refresh:
        try:
            with st.spinner("Generating personalized recommendations..."):
                result = api.get_auto_recommendations(
                    student_id, count=3, refresh=needs_refresh,
                )
                st.session_state.auto_recs = result.get("message", "No recommendations available.")
                st.session_state.auto_recs_refresh = False
        except Exception as e:
            st.session_state.auto_recs = f"Could not generate recommendations: {e}"
            st.session_state.auto_recs_refresh = False

    rec_text = st.session_state.auto_recs or ""
    if rec_text:
        st.markdown(rec_text)

    if st.button("Refresh Recommendations"):
        st.session_state.auto_recs = None
        st.session_state.auto_recs_refresh = True
        st.rerun()

with leader_col:
    st.subheader("Leaderboard")
    try:
        leaders = api.get_leaderboard(limit=10)
        if leaders:
            for entry in leaders:
                is_me = entry["student_id"] == student_id
                name = entry["name"].split()[0]
                rank = entry["rank"]
                books = entry["books_completed"]
                reviews = entry["review_count"]
                cur_streak = entry["current_streak"]

                line = f"**#{rank} {name}** — {books} books, {reviews} reviews, {cur_streak}d streak"
                if is_me:
                    st.markdown(f"> {line}")
                else:
                    st.markdown(line)
        else:
            st.info("No leaderboard data yet.")
    except Exception as e:
        st.warning(f"Could not load leaderboard: {e}")

st.markdown("---")

# ======================================================================
# ROW 3: Reading List (left, wider) + Trending Books (right)
# ======================================================================
reading_col, trending_col = st.columns([3, 2])

with reading_col:
    st.subheader("My Reading List")

    try:
        history = api.get_reading_history(student_id, limit=20)
        if history:
            for entry in history:
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        title = entry.get("book_title", "Unknown")
                        author = entry.get("book_author_name") or entry.get("book_author", "Unknown")
                        status = entry.get("status", "")
                        status_label = {
                            "completed": "Completed",
                            "reading": "Reading",
                            "wishlist": "Wishlist",
                            "abandoned": "Abandoned",
                        }
                        st.markdown(f"**{title}** by {author}")
                        rating = entry.get("rating")
                        rating_str = f" — {'*' * rating}" if rating else ""
                        st.caption(f"{status_label.get(status, status)}{rating_str}")
                    with c2:
                        if status == "reading":
                            if st.button("Mark Done", key=f"complete_{entry['id']}"):
                                try:
                                    api.update_reading_status(student_id, entry["id"], status="completed")
                                    st.rerun()
                                except Exception:
                                    pass
                        elif status == "wishlist":
                            if st.button("Start", key=f"start_{entry['id']}"):
                                try:
                                    api.update_reading_status(student_id, entry["id"], status="reading")
                                    st.rerun()
                                except Exception:
                                    pass
        else:
            st.info("No books in your reading list yet. Browse the catalog to add some!")
    except Exception as e:
        st.warning(f"Could not load reading history: {e}")

with trending_col:
    st.subheader("Trending Books")
    try:
        trending = api.get_trending_books(limit=5)
        if trending:
            for book in trending:
                title = book.get("title", "Unknown")
                author = book.get("author_name", "Unknown")
                reads = book.get("read_count", 0)
                rating = book.get("avg_rating")
                rating_str = f" — {rating:.1f}/5" if rating else ""
                st.markdown(f"**{title}**")
                st.caption(f"by {author} | {reads} reads{rating_str}")
        else:
            st.caption("No trending data available yet.")
    except Exception:
        st.caption("No trending data available.")
