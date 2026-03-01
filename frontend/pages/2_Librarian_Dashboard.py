"""Librarian Dashboard - Analytics and monitoring."""

import streamlit as st

st.set_page_config(page_title="Dashboard - LitEngage", page_icon="📋", layout="wide")

from frontend.utils.api_client import api

st.title("📋 Librarian Dashboard")

# ------------------------------------------------------------------
# Analytics overview
# ------------------------------------------------------------------
try:
    analytics = api.get_analytics()
except Exception as e:
    st.error(f"Could not load analytics. Is the backend running? ({e})")
    st.stop()

st.markdown("### Overview")
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Total Books", f"{analytics.get('total_books', 0):,}")
with c2:
    st.metric("Total Students", analytics.get("total_students", 0))
with c3:
    st.metric("Recommendations (Week)", analytics.get("recommendations_this_week", 0))
with c4:
    st.metric("👍 Positive", analytics.get("thumbs_up", 0))
with c5:
    st.metric("👎 Negative", analytics.get("thumbs_down", 0))

st.markdown("---")

# ------------------------------------------------------------------
# Recent recommendations
# ------------------------------------------------------------------
st.markdown("### Recent Recommendations")

try:
    recs = api.get_recent_recommendations(limit=20)
except Exception:
    recs = []

if recs:
    for rec in recs:
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 4, 1])
            with col1:
                st.markdown(f"**Student:** {rec.get('student_id', 'N/A')[:8]}...")
                st.caption(f"Model: {rec.get('model_used', 'N/A')}")
            with col2:
                book_ids = rec.get("book_ids_json") or []
                st.markdown(f"**Books:** {', '.join(book_ids[:3])}")
                explanation = rec.get("explanation", "")
                if explanation:
                    st.markdown(explanation[:200])
            with col3:
                feedback = rec.get("feedback")
                if feedback == "thumbs_up":
                    st.markdown("👍")
                elif feedback == "thumbs_down":
                    st.markdown("👎")
                else:
                    st.markdown("—")
                created = rec.get("created_at", "")
                if created:
                    st.caption(created[:10])
else:
    st.info("No recommendations yet. Students need to start chatting!")

st.markdown("---")

# ------------------------------------------------------------------
# Student list
# ------------------------------------------------------------------
st.markdown("### Registered Students")
try:
    students = api.get_students()
    if students:
        for s in students:
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.markdown(f"**{s['name']}**")
            with col2:
                st.markdown(f"Grade {s['grade_level']}")
            with col3:
                st.markdown(s["reading_level"])
    else:
        st.info("No students registered yet.")
except Exception:
    st.warning("Could not load student list.")
