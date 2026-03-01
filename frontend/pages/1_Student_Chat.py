"""Student Chat Interface - Chat with the AI Librarian."""

import streamlit as st

st.set_page_config(page_title="Chat - LitEngage", page_icon="💬", layout="wide")

from frontend.components.chat_interface import display_chat_history
from frontend.utils.api_client import api

st.title("💬 Chat with Your AI Librarian")

# ------------------------------------------------------------------
# Student selection
# ------------------------------------------------------------------
if "student_id" not in st.session_state:
    st.markdown("**Select your profile to start chatting:**")

    try:
        students = api.get_students()
    except Exception as e:
        st.error(f"Could not connect to the backend. Is the API running? ({e})")
        st.stop()

    if not students:
        st.warning("No student profiles found. Run create_sample_students.py first.")
        st.stop()

    student = st.selectbox(
        "Choose your profile",
        students,
        format_func=lambda s: f"{s['name']} (Grade {s['grade_level']}, {s['reading_level']})",
    )

    if st.button("Start Chatting", type="primary"):
        st.session_state.student_id = student["id"]
        st.session_state.student_name = student["name"]
        st.session_state.student_reading_level = student["reading_level"]
        st.session_state.student_grade = student["grade_level"]

        # Create a new chat session
        try:
            session = api.create_session(student["id"])
            st.session_state.session_id = session["thread_id"]
            st.session_state.session_db_id = session["id"]
            st.session_state.messages = []
        except Exception as e:
            st.error(f"Could not create session: {e}")
            st.stop()

        st.rerun()
    st.stop()

# ------------------------------------------------------------------
# Active chat interface
# ------------------------------------------------------------------
st.markdown(
    f"**Chatting as:** {st.session_state.student_name} "
    f"(Grade {st.session_state.student_grade}, "
    f"{st.session_state.student_reading_level})"
)

# Sidebar controls
with st.sidebar:
    st.markdown("### Chat Controls")
    if st.button("New Conversation"):
        try:
            session = api.create_session(st.session_state.student_id)
            st.session_state.session_id = session["thread_id"]
            st.session_state.session_db_id = session["id"]
            st.session_state.messages = []
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    if st.button("Switch Student"):
        for key in ["student_id", "student_name", "student_reading_level",
                     "student_grade", "session_id", "session_db_id", "messages"]:
            st.session_state.pop(key, None)
        st.rerun()

    st.markdown("---")
    st.markdown("### Tips")
    st.markdown(
        "- Ask for book recommendations by genre\n"
        "- Tell me what you've enjoyed reading\n"
        "- Ask about specific books\n"
        "- Say what themes interest you"
    )

# Display chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

display_chat_history(st.session_state.messages)

# Chat input
if prompt := st.chat_input("What kind of book are you looking for?"):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get AI response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = api.send_message(
                    st.session_state.student_id,
                    st.session_state.session_id,
                    prompt,
                )
                ai_message = response.get("message", "Sorry, I couldn't process that.")
                st.markdown(ai_message)

                if response.get("guardrail_triggered"):
                    st.caption("⚠️ This response was filtered for safety.")

            except Exception as e:
                ai_message = f"I'm having trouble connecting right now. Please try again. ({e})"
                st.error(ai_message)

    st.session_state.messages.append({"role": "assistant", "content": ai_message})
