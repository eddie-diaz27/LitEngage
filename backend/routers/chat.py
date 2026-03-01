"""Chat API endpoints with LangGraph agent and guardrails integration."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database import crud
from backend.schemas.chat import (
    ChatMessageDetail,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    request: ChatSessionCreate,
    db: Session = Depends(get_db),
):
    """Create a new chat session for a student."""
    student = crud.get_student(db, request.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    session_id = str(uuid.uuid4())
    thread_id = f"student_{request.student_id}_{session_id}"

    session = crud.create_chat_session(db, request.student_id, thread_id)
    return ChatSessionResponse(
        id=session.id,
        student_id=session.student_id,
        thread_id=session.thread_id,
        created_at=session.created_at,
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(session_id: int, db: Session = Depends(get_db)):
    """Get a chat session with its message history."""
    session = crud.get_chat_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = [
        ChatMessageDetail(
            role=msg.role,
            content=msg.content,
            timestamp=msg.timestamp,
        )
        for msg in session.messages
    ]

    return ChatSessionResponse(
        id=session.id,
        student_id=session.student_id,
        thread_id=session.thread_id,
        created_at=session.created_at,
        last_message_at=session.last_message_at,
        messages=messages,
    )


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    db: Session = Depends(get_db),
):
    """Send a message and get a response from the recommendation agent."""
    from backend.services.agent import invoke_agent
    from backend.services.guardrails import get_guardrail_service

    # Validate student exists
    student = crud.get_student(db, request.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get or create session
    session_id = request.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        thread_id = f"student_{request.student_id}_{session_id}"
        session = crud.create_chat_session(db, request.student_id, thread_id)
    else:
        thread_id = f"student_{request.student_id}_{session_id}"
        session = crud.get_chat_session_by_thread(db, thread_id)
        if not session:
            session = crud.create_chat_session(db, request.student_id, thread_id)

    # Save user message to DB
    crud.create_chat_message(db, session.id, "user", request.message)

    # Input guardrail check
    guardrails = get_guardrail_service()
    is_safe, fallback, details = await guardrails.check_input(request.message)

    if not is_safe:
        # Save guardrail response to DB
        crud.create_chat_message(db, session.id, "assistant", fallback)
        logger.info(
            "Input guardrail triggered",
            extra={
                "student_id": request.student_id,
                "breach": details,
            },
        )
        return ChatMessageResponse(
            message=fallback,
            session_id=session_id,
            guardrail_triggered=True,
        )

    # Invoke the LangGraph agent
    student_data = {
        "reading_level": student.reading_level,
        "grade_level": student.grade_level,
        "preferences_json": student.preferences_json,
    }

    result = await invoke_agent(
        student_id=request.student_id,
        message=request.message,
        session_id=session_id,
        student_data=student_data,
    )

    response_message = result.get("message", "")

    # Output guardrail check
    is_safe, fallback, details = await guardrails.check_output(
        request.message, response_message
    )

    if not is_safe:
        response_message = fallback
        logger.info(
            "Output guardrail triggered",
            extra={
                "student_id": request.student_id,
                "breach": details,
            },
        )

    # Save assistant response to DB
    crud.create_chat_message(db, session.id, "assistant", response_message)

    return ChatMessageResponse(
        message=response_message,
        session_id=session_id,
        guardrail_triggered=not is_safe,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int, db: Session = Depends(get_db)):
    """Delete a chat session and its messages."""
    success = crud.delete_chat_session(db, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}
