"""Authentication utilities for Streamlit frontend."""

import streamlit as st

from utils.api_client import api


def get_current_user() -> dict:
    """Get the current logged-in user from session state."""
    return st.session_state.get("user")


def require_auth():
    """Require authentication. Shows login form if not authenticated."""
    if not get_current_user():
        show_login_page()
        st.stop()


def require_role(role: str):
    """Require a specific role. Shows error if wrong role."""
    user = get_current_user()
    if not user:
        show_login_page()
        st.stop()
    if user.get("role") != role:
        st.error(f"Access denied. This page requires the '{role}' role.")
        st.stop()


def show_login_page():
    """Render the login form."""
    st.markdown("### Log In")
    st.markdown("Enter your credentials to access LitEngage.")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In", type="primary", use_container_width=True)

    if submitted:
        if not username or not password:
            st.error("Please enter both username and password.")
            return

        try:
            result = api.login(username, password)
            st.session_state.user = result

            # Pre-fetch recommendations for students at login time
            if result.get("role") == "student" and result.get("student_id"):
                try:
                    recs = api.get_auto_recommendations(result["student_id"], count=3)
                    st.session_state.auto_recs = recs.get("message", "")
                except Exception:
                    st.session_state.auto_recs = None  # Will retry on dashboard

            st.rerun()
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg:
                st.error("Invalid username or password.")
            elif "403" in error_msg:
                st.error("Account is disabled.")
            else:
                st.error(f"Login failed: {error_msg}")


def logout():
    """Clear the session state and log out."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
