"""Chat API endpoints with LangGraph agent and guardrails integration."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.connection import get_db
from backend.database import crud
from backend.database.models import TokenUsage
from backend.schemas.chat import (
    ChatMessageDetail,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
)
from backend.schemas.admin import LibrarianChatRequest, LibrarianChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Gemini 2.5 Flash pricing (per 1M tokens)
TOKEN_COST_PER_MILLION = {
    "input": 0.15,
    "output": 0.60,
}


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost based on Gemini pricing."""
    cost = (prompt_tokens / 1_000_000) * TOKEN_COST_PER_MILLION["input"]
    cost += (completion_tokens / 1_000_000) * TOKEN_COST_PER_MILLION["output"]
    return round(cost, 6)


def _save_token_usage(db, student_id, request_type, result):
    """Save token usage record from agent result."""
    token_info = result.get("token_usage", {})
    prompt_tokens = token_info.get("prompt_tokens", 0)
    completion_tokens = token_info.get("completion_tokens", 0)

    usage = TokenUsage(
        student_id=student_id,
        request_type=request_type,
        model_used=result.get("model_used", settings.gemini_model),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=token_info.get("total_tokens", 0),
        estimated_cost_usd=_estimate_cost(prompt_tokens, completion_tokens),
        latency_ms=result.get("latency_ms", 0),
        tools_used=result.get("tools_used", []),
    )
    db.add(usage)
    db.commit()


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

    # Layer 1: Zero-cost profanity pre-filter (no tokens, sub-ms)
    from backend.services.profanity_filter import get_profanity_filter
    pf = get_profanity_filter()
    is_clean, rejection = pf.check_input(request.message, context="student")
    if not is_clean:
        crud.create_chat_message(db, session.id, "assistant", rejection)
        logger.info(
            "Profanity filter triggered (student)",
            extra={"student_id": request.student_id},
        )
        return ChatMessageResponse(
            message=rejection,
            session_id=session_id,
            guardrail_triggered=True,
        )

    # Layer 2: DeepTeam guardrail check (costs guard tokens, catches injection/off-topic)
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

    # Save token usage
    _save_token_usage(db, request.student_id, "chat", result)

    return ChatMessageResponse(
        message=response_message,
        session_id=session_id,
        guardrail_triggered=not is_safe,
    )


@router.post("/message/librarian", response_model=LibrarianChatResponse)
async def send_librarian_message(
    request: LibrarianChatRequest,
    db: Session = Depends(get_db),
):
    """Librarian chat endpoint - returns response with debug metadata."""
    from backend.services.agent import invoke_agent
    from backend.services.profanity_filter import get_profanity_filter

    session_id = request.session_id or str(uuid.uuid4())

    # Layer 1: Zero-cost profanity pre-filter (no tokens, sub-ms)
    pf = get_profanity_filter()
    is_clean, rejection = pf.check_input(request.message, context="librarian")
    if not is_clean:
        logger.info("Profanity filter triggered (librarian)")
        return LibrarianChatResponse(
            message=rejection,
            session_id=session_id,
            token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            latency_ms=0,
            tools_used=[],
            model_used="profanity_filter",
        )

    # Use a librarian-specific thread
    result = await invoke_agent(
        student_id="librarian",
        message=request.message,
        session_id=session_id,
        student_data={
            "reading_level": "high-school",
            "grade_level": 12,
        },
    )

    response_message = result.get("message", "")

    # Save token usage as librarian_analysis
    _save_token_usage(db, None, "librarian_analysis", result)

    token_info = result.get("token_usage", {})

    return LibrarianChatResponse(
        message=response_message,
        session_id=session_id,
        token_usage=token_info,
        latency_ms=result.get("latency_ms"),
        tools_used=result.get("tools_used"),
        model_used=result.get("model_used"),
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int, db: Session = Depends(get_db)):
    """Delete a chat session and its messages."""
    success = crud.delete_chat_session(db, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}
