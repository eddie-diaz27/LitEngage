"""Librarian Analysis Chat - Chat with AI for data analysis and insights."""

import os
import sys
import uuid

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

    st.markdown("---")
    st.markdown("### Analysis Chat")
    if st.button("New Conversation"):
        st.session_state.pop("lib_session_id", None)
        st.session_state.pop("lib_messages", None)
        st.rerun()

    st.markdown("---")
    st.markdown("### Example Questions")
    st.markdown(
        "- Which students haven't read anything this month?\n"
        "- What genres are trending?\n"
        "- Recommend books for struggling readers\n"
        "- Summarize student engagement this week\n"
        "- Which books have the highest student ratings?"
    )

st.title("💬 Librarian Analysis Chat")
st.caption("Ask questions about reading trends, student engagement, and library analytics.")

# Initialize session (generate client-side — librarian doesn't need a student session)
if "lib_session_id" not in st.session_state:
    st.session_state.lib_session_id = str(uuid.uuid4())
    st.session_state.lib_messages = []

if "lib_messages" not in st.session_state:
    st.session_state.lib_messages = []

# Display chat history
for msg in st.session_state.lib_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("metadata"):
            meta = msg["metadata"]
            tokens = meta.get("total_tokens", 0)
            latency = meta.get("latency_ms", 0)
            cost = meta.get("estimated_cost", 0)
            tools = meta.get("tools_used", [])

            parts = []
            if tokens:
                parts.append(f"Tokens: {tokens:,}")
            if latency:
                parts.append(f"Latency: {latency / 1000:.1f}s")
            if cost:
                parts.append(f"Cost: ${cost:.4f}")
            if tools:
                parts.append(f"Tools: {', '.join(tools)}")

            if parts:
                st.caption(" | ".join(parts))

# Welcome message
if not st.session_state.lib_messages:
    with st.chat_message("assistant"):
        st.markdown(
            "Hello! I'm your analysis assistant. I can help you understand "
            "reading trends, identify students who need attention, and provide "
            "insights about your library. What would you like to know?"
        )

# Chat input
if prompt := st.chat_input("Ask about reading trends, student engagement..."):
    st.session_state.lib_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            try:
                response = api.send_librarian_message(
                    message=prompt,
                    session_id=st.session_state.lib_session_id,
                )
                ai_message = response.get("message", "Sorry, I couldn't process that.")
                st.markdown(ai_message)

                # Display metadata
                metadata = {}
                token_usage = response.get("token_usage", {})
                if token_usage:
                    metadata["total_tokens"] = token_usage.get("total_tokens", 0)
                latency = response.get("latency_ms")
                if latency:
                    metadata["latency_ms"] = latency
                cost = response.get("estimated_cost")
                if cost:
                    metadata["estimated_cost"] = cost
                tools = response.get("tools_used", [])
                if tools:
                    metadata["tools_used"] = tools

                if metadata:
                    parts = []
                    if metadata.get("total_tokens"):
                        parts.append(f"Tokens: {metadata['total_tokens']:,}")
                    if metadata.get("latency_ms"):
                        parts.append(f"Latency: {metadata['latency_ms'] / 1000:.1f}s")
                    if metadata.get("estimated_cost"):
                        parts.append(f"Cost: ${metadata['estimated_cost']:.4f}")
                    if metadata.get("tools_used"):
                        parts.append(f"Tools: {', '.join(metadata['tools_used'])}")
                    if parts:
                        st.caption(" | ".join(parts))

            except Exception as e:
                ai_message = f"Analysis failed. Please try again. ({e})"
                metadata = {}
                st.error(ai_message)

    st.session_state.lib_messages.append({
        "role": "assistant",
        "content": ai_message,
        "metadata": metadata,
    })
