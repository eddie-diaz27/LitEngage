"""LitEngage - Library Reading Companion - Home Page."""

import streamlit as st

st.set_page_config(
    page_title="LitEngage",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📚 LitEngage")
st.subheader("Your Library Reading Companion")

st.markdown("---")

st.markdown(
    "Welcome to LitEngage! Get personalized book recommendations "
    "powered by AI, tailored to your reading level and interests."
)

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🎒 I'm a Student")
    st.markdown(
        "Chat with our AI librarian to discover books you'll love. "
        "Get recommendations based on your interests and reading level."
    )
    if st.button("Start Reading Journey", type="primary", use_container_width=True):
        st.switch_page("pages/1_Student_Chat.py")

with col2:
    st.markdown("### 📋 I'm a Librarian")
    st.markdown(
        "Monitor recommendations, view analytics, and manage the book catalog."
    )
    if st.button("Go to Dashboard", use_container_width=True):
        st.switch_page("pages/2_Librarian_Dashboard.py")

st.markdown("---")

# Quick stats
try:
    from frontend.utils.api_client import api

    health = api.health_check()
    if health.get("status") == "healthy":
        analytics = api.get_analytics()
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Books in Catalog", f"{analytics.get('total_books', 0):,}")
        with c2:
            st.metric("Students", analytics.get("total_students", 0))
        with c3:
            st.metric(
                "Recommendations This Week",
                analytics.get("recommendations_this_week", 0),
            )
except Exception:
    st.info("Start the backend server to see live statistics.")

st.markdown("---")
st.caption("LitEngage - Making students love reading, one recommendation at a time.")
