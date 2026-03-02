"""Librarian Dashboard - Analytics, alerts, student oversight, circulation, and cost tracking."""

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

st.title("📋 Librarian Dashboard")

# ------------------------------------------------------------------
# Top row metrics
# ------------------------------------------------------------------
try:
    analytics = api.get_analytics()
except Exception:
    analytics = {}

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Total Books", f"{analytics.get('total_books', 0):,}")
with c2:
    st.metric("Total Students", analytics.get("total_students", 0))
with c3:
    st.metric("Recommendations (Week)", analytics.get("recommendations_this_week", 0))
with c4:
    st.metric("Positive Feedback", analytics.get("thumbs_up", 0))
with c5:
    st.metric("Negative Feedback", analytics.get("thumbs_down", 0))

# ------------------------------------------------------------------
# Second row: Circulation & Moderation metrics
# ------------------------------------------------------------------
try:
    loan_summary = api.get_loan_summary()
except Exception:
    loan_summary = {}

try:
    flagged_reviews = api.get_flagged_reviews(limit=100)
except Exception:
    flagged_reviews = []

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Active Loans", loan_summary.get("total_active_loans", 0))
with m2:
    overdue_count = loan_summary.get("overdue_count", 0)
    st.metric("Overdue Books", overdue_count, delta=f"-{overdue_count}" if overdue_count else None, delta_color="inverse")
with m3:
    st.metric("Due This Week", loan_summary.get("due_this_week_count", 0))
with m4:
    st.metric("Flagged Reviews", len(flagged_reviews), delta=f"-{len(flagged_reviews)}" if flagged_reviews else None, delta_color="inverse")

st.markdown("---")

# ------------------------------------------------------------------
# Alerts panel
# ------------------------------------------------------------------
try:
    alerts = api.get_alerts()
except Exception:
    alerts = []

if alerts:
    with st.expander(f"Alerts ({len(alerts)})", expanded=True):
        for alert in alerts:
            severity = alert.get("severity", "info")
            message = alert.get("message", "")
            if severity == "warning":
                st.warning(message)
            elif severity == "success":
                st.success(message)
            else:
                st.info(message)

# ------------------------------------------------------------------
# Tabbed sections
# ------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Book Trends", "Student Oversight", "Circulation", "Recent Recommendations", "Cost Tracking"]
)

# ---- Tab 1: Book Trends ----
with tab1:
    col_genres, col_trending = st.columns(2)

    with col_genres:
        st.markdown("#### Genre Distribution")
        try:
            genres = api.get_genre_stats()
            if genres:
                for g in genres[:15]:
                    pct = g.get("percentage", 0)
                    st.markdown(f"**{g['genre']}** — {g['count']} books ({pct}%)")
                    st.progress(min(pct / 100, 1.0))
            else:
                st.info("No genre data available.")
        except Exception:
            st.warning("Could not load genre stats.")

    with col_trending:
        st.markdown("#### Trending Books (30 days)")
        try:
            trends = api.get_trends()
            if trends:
                for i, t in enumerate(trends[:10], 1):
                    author = t.get("author_name") or t.get("author", "Unknown")
                    rating = t.get("avg_rating")
                    rating_str = f" | Rating: {rating:.1f}" if rating else ""
                    st.markdown(
                        f"**{i}. {t['title']}** by {author} — "
                        f"{t['read_count']} reads{rating_str}"
                    )
            else:
                st.info("No reading activity yet.")
        except Exception:
            st.warning("Could not load trends.")

# ---- Tab 2: Student Oversight ----
with tab2:
    st.markdown("#### Student Overview")
    try:
        students = api.get_students()
        if students:
            for s in students:
                sid = s["id"]
                with st.expander(f"{s['name']} — Grade {s['grade_level']} ({s['reading_level']})"):
                    try:
                        profile = api.get_student_profile(sid)
                        pc1, pc2, pc3, pc4 = st.columns(4)
                        with pc1:
                            st.metric("Books Read", profile.get("books_completed", 0))
                        with pc2:
                            st.metric("Reviews", profile.get("review_count", 0))
                        with pc3:
                            streak = profile.get("streak", {})
                            st.metric("Streak", streak.get("current_streak", 0))
                        with pc4:
                            last_active = s.get("last_active", "Never")
                            if last_active and last_active != "Never":
                                st.metric("Last Active", str(last_active)[:10])
                            else:
                                st.metric("Last Active", "Never")

                        # Reading history
                        history = profile.get("reading_history", [])
                        if history:
                            st.markdown("**Recent Activity:**")
                            for h in history[:5]:
                                status = h.get("status", "unknown")
                                title = h.get("book_title") or h.get("title", "Unknown")
                                st.caption(f"- {title} [{status}]")
                    except Exception:
                        st.caption("Could not load profile.")
        else:
            st.info("No students registered yet.")
    except Exception:
        st.warning("Could not load student list.")

    # Leaderboard
    st.markdown("---")
    st.markdown("#### Leaderboard")
    try:
        leaderboard = api.get_leaderboard()
        if leaderboard:
            header_cols = st.columns([0.5, 2, 1, 1, 1, 1])
            with header_cols[0]:
                st.markdown("**#**")
            with header_cols[1]:
                st.markdown("**Student**")
            with header_cols[2]:
                st.markdown("**Score**")
            with header_cols[3]:
                st.markdown("**Books**")
            with header_cols[4]:
                st.markdown("**Reviews**")
            with header_cols[5]:
                st.markdown("**Streak**")

            for entry in leaderboard:
                cols = st.columns([0.5, 2, 1, 1, 1, 1])
                with cols[0]:
                    st.markdown(str(entry.get("rank", "-")))
                with cols[1]:
                    st.markdown(entry.get("student_name", "Unknown"))
                with cols[2]:
                    st.markdown(f"{entry.get('score', 0):.1f}")
                with cols[3]:
                    st.markdown(str(entry.get("books_completed", 0)))
                with cols[4]:
                    st.markdown(str(entry.get("review_count", 0)))
                with cols[5]:
                    st.markdown(str(entry.get("current_streak", 0)))
        else:
            st.info("No leaderboard data.")
    except Exception:
        st.warning("Could not load leaderboard.")

# ---- Tab 3: Circulation ----
with tab3:
    st.markdown("#### Book Circulation")

    # Summary cards
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        st.metric("Active Loans", loan_summary.get("total_active_loans", 0))
    with sc2:
        st.metric("Overdue", loan_summary.get("overdue_count", 0))
    with sc3:
        st.metric("Due Today", loan_summary.get("due_today_count", 0))
    with sc4:
        st.metric("Due This Week", loan_summary.get("due_this_week_count", 0))

    # Overdue list
    overdue_loans = loan_summary.get("overdue_loans", [])
    if overdue_loans:
        st.markdown("---")
        st.markdown("#### Overdue Books")
        for loan in overdue_loans:
            with st.container(border=True):
                lc1, lc2, lc3 = st.columns([3, 1, 1])
                with lc1:
                    st.markdown(f"**{loan.get('book_title', 'Unknown')}**")
                    st.caption(f"Student: {loan.get('student_name', 'Unknown')}")
                with lc2:
                    days = loan.get("days_overdue", 0)
                    st.markdown(f"**{days} day(s) overdue**")
                    st.caption(f"Due: {str(loan.get('due_date', ''))[:10]}")
                with lc3:
                    loan_id = loan.get("id")
                    if st.button("Mark Returned", key=f"return_{loan_id}"):
                        try:
                            api.return_loan(loan_id)
                            st.success("Book returned!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")

    # Quick checkout
    st.markdown("---")
    st.markdown("#### Quick Checkout")
    with st.form("quick_checkout"):
        try:
            all_students = api.get_students()
        except Exception:
            all_students = []

        student_options = {s["name"]: s["id"] for s in all_students} if all_students else {}
        selected_student = st.selectbox("Student", options=list(student_options.keys()) if student_options else ["No students"])

        book_search = st.text_input("Search book by title", key="checkout_book_search")

        checkout_days = st.number_input("Loan period (days)", min_value=1, max_value=90, value=14)

        if st.form_submit_button("Checkout Book", type="primary"):
            if selected_student in student_options and book_search:
                try:
                    books = api.title_search_books(q=book_search, limit=1)
                    if books:
                        result = api.checkout_book(
                            student_id=student_options[selected_student],
                            book_id=books[0]["id"],
                            due_days=checkout_days,
                        )
                        st.success(
                            f"Checked out '{books[0]['title']}' to {selected_student}. "
                            f"Due: {str(result.get('due_date', ''))[:10]}"
                        )
                    else:
                        st.warning("No book found with that title.")
                except Exception as e:
                    st.error(f"Checkout failed: {e}")
            else:
                st.warning("Please select a student and enter a book title.")

    # Active loans
    st.markdown("---")
    st.markdown("#### All Active Loans")
    try:
        active_loans = api.get_active_loans(limit=50)
    except Exception:
        active_loans = []

    if active_loans:
        for loan in active_loans:
            is_overdue = loan.get("is_overdue", False)
            border_color = "border-left: 3px solid red;" if is_overdue else ""
            with st.container(border=True):
                lc1, lc2, lc3, lc4 = st.columns([3, 1.5, 1, 1])
                with lc1:
                    prefix = "**[OVERDUE]** " if is_overdue else ""
                    st.markdown(f"{prefix}**{loan.get('book_title', 'Unknown')}**")
                    st.caption(f"Student: {loan.get('student_name', 'Unknown')}")
                with lc2:
                    st.caption(f"Checked out: {str(loan.get('checked_out_at', ''))[:10]}")
                    st.caption(f"Due: {str(loan.get('due_date', ''))[:10]}")
                with lc3:
                    renewed = loan.get("renewed_count", 0)
                    st.caption(f"Renewed: {renewed}x")
                with lc4:
                    loan_id = loan.get("id")
                    if st.button("Return", key=f"ret_active_{loan_id}"):
                        try:
                            api.return_loan(loan_id)
                            st.success("Returned!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
    else:
        st.info("No active loans.")

# ---- Tab 4: Recent Recommendations ----
with tab4:
    st.markdown("#### Recent Recommendations")
    try:
        recs = api.get_recent_recommendations(limit=20)
    except Exception:
        recs = []

    if recs:
        for rec in recs:
            with st.container(border=True):
                rc1, rc2, rc3 = st.columns([2, 4, 1])
                with rc1:
                    st.markdown(f"**Student:** {rec.get('student_id', 'N/A')[:8]}...")
                    st.caption(f"Model: {rec.get('model_used', 'N/A')}")
                with rc2:
                    book_ids = rec.get("book_ids_json") or []
                    st.markdown(f"**Books:** {', '.join(str(b) for b in book_ids[:3])}")
                    explanation = rec.get("explanation", "")
                    if explanation:
                        st.markdown(explanation[:200])
                with rc3:
                    feedback = rec.get("feedback")
                    if feedback == "thumbs_up":
                        st.markdown("Positive")
                    elif feedback == "thumbs_down":
                        st.markdown("Negative")
                    else:
                        st.markdown("No feedback")
                    created = rec.get("created_at", "")
                    if created:
                        st.caption(str(created)[:10])
    else:
        st.info("No recommendations yet. Students need to start chatting!")

# ---- Tab 5: Cost Tracking ----
with tab5:
    st.markdown("#### LLM Token Usage & Cost Tracking")

    days = st.selectbox("Time period", [7, 14, 30, 60, 90], index=2)

    try:
        usage = api.get_token_usage(days=days)
    except Exception:
        usage = {}

    if usage:
        uc1, uc2, uc3, uc4 = st.columns(4)
        with uc1:
            st.metric("Total Requests", usage.get("total_requests", 0))
        with uc2:
            st.metric("Total Tokens", f"{usage.get('total_tokens', 0):,}")
        with uc3:
            st.metric("Total Cost", f"${usage.get('total_cost_usd', 0):.4f}")
        with uc4:
            st.metric("Avg Latency", f"{usage.get('avg_latency_ms', 0):.0f}ms")

        # By request type
        by_type = usage.get("by_type", {})
        if by_type:
            st.markdown("**By Request Type:**")
            for rtype, data in by_type.items():
                st.markdown(
                    f"- **{rtype}**: {data['requests']} requests, "
                    f"{data['tokens']:,} tokens, ${data['cost']:.4f}"
                )

        # By student
        by_student = usage.get("by_student", [])
        if by_student:
            st.markdown("**Top Students by Token Usage:**")
            for entry in by_student[:10]:
                sid = entry.get("student_id", "system")
                st.markdown(
                    f"- **{sid[:8]}...**: {entry['requests']} requests, "
                    f"{entry['tokens']:,} tokens, ${entry['cost']:.4f}"
                )
    else:
        st.info("No token usage data yet. Usage is tracked when students chat with the AI.")
