"""Shared fixtures for DeepEval agent evaluation tests.

Provides the Gemini-based evaluation judge model, sample student data,
and helpers for constructing LLMTestCase instances from agent outputs.

The GeminiModel instantiation pattern is reused from
backend/services/guardrails.py:22-30.
"""

import pytest

from tests.eval_test_cases import SYNTHETIC_TEST_CASES


# ---------------------------------------------------------------------------
# Evaluation Judge Model
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def eval_model():
    """Create a GeminiModel instance for use as the DeepEval evaluation judge.

    Reuses the same pattern as guardrails.py:22-30.  Session-scoped so
    the model is initialized once across all tests.
    """
    from deepeval.models.llms.gemini_model import GeminiModel
    from backend.config import settings

    return GeminiModel(
        model=settings.deepteam_model,
        api_key=settings.google_api_key,
        temperature=0,
    )


# ---------------------------------------------------------------------------
# Pre-computed Test Cases (synthetic tier — no live API calls)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sample_cases():
    """Return the dictionary of pre-computed synthetic test cases.

    Each case has: input, actual_output, retrieval_context, and expected_tools.
    These enable deterministic evaluation without invoking the live agent.
    """
    return SYNTHETIC_TEST_CASES


# ---------------------------------------------------------------------------
# Live Agent Helper (live tier — requires API key)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def invoke_agent_helper():
    """Return an async helper that invokes the real agent and returns
    structured output suitable for building LLMTestCase instances.

    Usage in live tests::

        result = await invoke_agent_helper("recommend adventure books")
        test_case = LLMTestCase(
            input=result["input"],
            actual_output=result["actual_output"],
            retrieval_context=result["retrieval_context"],
        )
    """
    from backend.services.agent import invoke_agent

    async def _invoke(message: str, student_id: str = "eval_student_001"):
        result = await invoke_agent(
            student_id=student_id,
            message=message,
            session_id=f"eval_{student_id}",
            student_data={
                "reading_level": "middle-school",
                "grade_level": 7,
                "preferences_json": {"favorite_genres": ["fantasy", "adventure"]},
            },
        )
        return {
            "input": message,
            "actual_output": result.get("message", ""),
            "retrieval_context": [],  # Populated by search_books tool results
            "tools_used": result.get("tools_used", []),
            "token_usage": result.get("token_usage", {}),
            "latency_ms": result.get("latency_ms", 0),
        }

    return _invoke
