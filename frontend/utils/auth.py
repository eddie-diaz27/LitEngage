"""Simple authentication / role selection for MVP."""

import streamlit as st


def check_role_selected() -> bool:
    """Check if the user has selected a role."""
    return "role" in st.session_state


def get_current_role() -> str:
    """Get the currently selected role."""
    return st.session_state.get("role", "")


def set_role(role: str):
    """Set the user's role."""
    st.session_state["role"] = role


def logout():
    """Clear the session state."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
