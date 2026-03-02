"""Student Chat - Chat with the AI Librarian."""

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

student_id = user.get("student_id")
if not student_id:
    st.error("Only students can access the chat.")
    st.stop()

with st.sidebar:
    st.markdown(f"**{user['display_name']}**")
    st.caption(f"Role: {user['role'].title()}")
    if st.button("Logout"):
        logout()
        st.rerun()

    st.markdown("---")
    st.markdown("### Chat Controls")
    if st.button("New Conversation"):
        try:
            session = api.create_session(student_id)
            st.session_state.session_id = session["thread_id"]
            st.session_state.messages = []
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    st.markdown("---")
    st.markdown("### Tips")
    st.markdown(
        "- Ask for book recommendations by genre\n"
        "- Tell me what you've enjoyed reading\n"
        "- Ask about specific books\n"
        "- Say what themes interest you"
    )

st.title("💬 Chat with Your AI Librarian")
st.caption(f"Chatting as {user['display_name']}")

# Initialize session
if "session_id" not in st.session_state:
    try:
        session = api.create_session(student_id)
        st.session_state.session_id = session["thread_id"]
        st.session_state.messages = []
    except Exception as e:
        st.error(f"Could not create chat session: {e}")
        st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Welcome message if no history
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown(
            f"Hi {user['display_name'].split()[0]}! I'm your AI librarian. "
            "What are you in the mood for today? I can recommend books based on "
            "your interests, favorite genres, or what you've been reading lately."
        )

# Chat input
if prompt := st.chat_input("What kind of book are you looking for?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = api.send_message(
                    student_id,
                    st.session_state.session_id,
                    prompt,
                )
                ai_message = response.get("message", "Sorry, I couldn't process that.")
                st.markdown(ai_message)

                if response.get("guardrail_triggered"):
                    st.caption("This response was filtered for safety.")

            except Exception as e:
                ai_message = f"I'm having trouble connecting right now. Please try again. ({e})"
                st.error(ai_message)

    st.session_state.messages.append({"role": "assistant", "content": ai_message})
