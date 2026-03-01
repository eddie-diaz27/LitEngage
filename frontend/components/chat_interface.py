"""Chat UI components for the student chat interface."""

import streamlit as st


def render_chat_message(role: str, content: str):
    """Render a single chat message."""
    with st.chat_message(role):
        st.markdown(content)


def display_chat_history(messages: list):
    """Display all messages in the chat history."""
    for msg in messages:
        render_chat_message(msg["role"], msg["content"])
