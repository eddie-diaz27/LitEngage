"""LitEngage - Library Reading Companion - Main entry point with role-based navigation."""

import os
import sys

# Add frontend directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

st.set_page_config(
    page_title="LitEngage",
    page_icon=":material/menu_book:",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.auth import get_current_user, logout, show_login_page
from utils.api_client import api

# ---------------------------------------------------------------------------
# Define all st.Page objects at module level so home_page can reference them
# ---------------------------------------------------------------------------
student_dashboard = st.Page(
    "pages/1_Student_Dashboard.py", title="Student Dashboard", icon=":material/dashboard:"
)
book_catalog = st.Page(
    "pages/2_Book_Catalog.py", title="Book Catalog", icon=":material/menu_book:"
)
student_chat = st.Page(
    "pages/3_Student_Chat.py", title="Student Chat", icon=":material/chat:"
)
librarian_dashboard = st.Page(
    "pages/4_Librarian_Dashboard.py", title="Librarian Dashboard", icon=":material/analytics:"
)
book_management = st.Page(
    "pages/5_Book_Management.py", title="Book Management", icon=":material/edit_note:"
)
librarian_chat = st.Page(
    "pages/6_Librarian_Chat.py", title="Librarian Chat", icon=":material/chat:"
)


def home_page():
    """Home / landing page content."""
    user = get_current_user()

    if user:
        with st.sidebar:
            st.markdown(f"**{user['display_name']}**")
            st.caption(f"Role: {user['role'].title()}")
            if st.button("Logout"):
                logout()
                st.rerun()

        st.title("LitEngage")
        st.subheader("Your Library Reading Companion")
        st.markdown("---")

        if user["role"] == "student":
            st.markdown(
                "Welcome back! Navigate using the sidebar or the buttons below."
            )
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("### Dashboard")
                st.markdown("See your reading progress, streak, and personalized recommendations.")
                if st.button("Go to Dashboard", type="primary", use_container_width=True):
                    st.switch_page(student_dashboard)
            with col2:
                st.markdown("### Book Catalog")
                st.markdown("Browse and search our collection. Add books to your reading list.")
                if st.button("Browse Books", use_container_width=True):
                    st.switch_page(book_catalog)
            with col3:
                st.markdown("### AI Librarian")
                st.markdown("Chat with our AI to get personalized book recommendations.")
                if st.button("Start Chatting", use_container_width=True):
                    st.switch_page(student_chat)

        elif user["role"] == "librarian":
            st.markdown(
                "Welcome back! Navigate using the sidebar or the buttons below."
            )
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("### Dashboard")
                st.markdown("View analytics, alerts, student oversight, and cost tracking.")
                if st.button("Go to Dashboard", type="primary", use_container_width=True):
                    st.switch_page(librarian_dashboard)
            with col2:
                st.markdown("### Book Management")
                st.markdown("Add, edit, or remove books. Moderate student reviews.")
                if st.button("Manage Books", use_container_width=True):
                    st.switch_page(book_management)
            with col3:
                st.markdown("### Analysis Chat")
                st.markdown("Ask questions about reading trends and student engagement.")
                if st.button("Start Analysis", use_container_width=True):
                    st.switch_page(librarian_chat)

        # Quick stats
        st.markdown("---")
        try:
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

    else:
        st.title("LitEngage")
        st.subheader("Your Library Reading Companion")
        st.markdown("---")
        st.markdown(
            "Welcome to LitEngage! Get personalized book recommendations "
            "powered by AI, tailored to your reading level and interests."
        )
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            show_login_page()
        with col2:
            st.markdown("### Quick Start")
            st.markdown(
                "**Student?** Log in to get personalized book recommendations, "
                "track your reading progress, and earn badges!\n\n"
                "**Librarian?** Log in to monitor student engagement, manage the "
                "book catalog, and view analytics."
            )
            st.markdown("---")
            st.caption("Demo credentials:")
            st.code("Student: student / student123\nLibrarian: librarian / librarian123")


# ---------------------------------------------------------------------------
# Role-based navigation
# ---------------------------------------------------------------------------
user = get_current_user()

home = st.Page(home_page, title="Home", icon=":material/home:")

if user and user.get("role") == "student":
    pg = st.navigation([home, student_dashboard, book_catalog, student_chat])
elif user and user.get("role") == "librarian":
    pg = st.navigation([home, librarian_dashboard, book_management, librarian_chat])
else:
    pg = st.navigation([home])

pg.run()
