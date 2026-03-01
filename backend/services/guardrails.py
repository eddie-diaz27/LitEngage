"""DeepTeam guardrails service for input/output safety checks.

Calls guards directly (bypassing the Guardrails class which forces
an OpenAI model override) using DeepEval's native GeminiModel.

Guards:
- PromptInjectionGuard (input)
- TopicalGuard (input) - books/reading topics only
- ToxicityGuard (output)
- PrivacyGuard (output)
- HallucinationGuard (output)
"""

import logging
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)


def _create_gemini_model():
    """Create DeepEval's native GeminiModel for guard evaluation."""
    from deepeval.models.llms.gemini_model import GeminiModel

    return GeminiModel(
        model=settings.deepteam_model,
        api_key=settings.google_api_key,
        temperature=0,
    )


class GuardrailService:
    """Singleton guardrails service. Initialize once at app startup."""

    def __init__(self):
        self._initialized = False
        self._input_guards = []
        self._output_guards = []

    def _ensure_initialized(self):
        """Lazy initialization of guards (expensive to create)."""
        if self._initialized:
            return

        try:
            from deepteam.guardrails import (
                HallucinationGuard,
                PrivacyGuard,
                PromptInjectionGuard,
                TopicalGuard,
                ToxicityGuard,
            )

            model = _create_gemini_model()

            if settings.enable_prompt_injection_guard:
                self._input_guards.append(PromptInjectionGuard(model=model))

            if settings.enable_topical_guard:
                self._input_guards.append(
                    TopicalGuard(
                        allowed_topics=settings.allowed_topics_list,
                        model=model,
                    )
                )

            if settings.enable_toxicity_guard:
                self._output_guards.append(ToxicityGuard(model=model))

            if settings.enable_privacy_guard:
                self._output_guards.append(PrivacyGuard(model=model))

            if settings.enable_hallucination_guard:
                self._output_guards.append(HallucinationGuard(model=model))

            self._initialized = True
            logger.info(
                f"GuardrailService initialized with "
                f"{len(self._input_guards)} input guards and "
                f"{len(self._output_guards)} output guards"
            )

        except Exception as e:
            logger.error(f"Failed to initialize guardrails: {e}")
            self._initialized = True  # Don't retry on every request

    async def check_input(self, message: str) -> tuple:
        """Check input message against guardrails.

        Returns:
            Tuple of (is_safe: bool, fallback_message: str, details: list)
        """
        self._ensure_initialized()

        if not self._input_guards:
            return True, "", []

        breach_names = []
        try:
            for guard in self._input_guards:
                safety_level = await guard.a_guard_input(input=message)
                guard_name = type(guard).__name__.lower()

                if safety_level and safety_level.lower() != "safe":
                    reason = getattr(guard, "reason", "")
                    breach_names.append(guard_name)
                    logger.warning(
                        "Input guardrail breach",
                        extra={"guard": guard_name, "reason": reason},
                    )

            if not breach_names:
                return True, "", []

            # Return appropriate fallback
            for name in breach_names:
                if "injection" in name or "prompt" in name:
                    return (
                        False,
                        "I can only help with book recommendations and "
                        "library questions!",
                        breach_names,
                    )
                if "topical" in name or "topic" in name:
                    return (
                        False,
                        "Let's keep our conversation focused on books and "
                        "reading. How can I help you find a great book?",
                        breach_names,
                    )

            return (
                False,
                "I'm having trouble understanding that request. "
                "Could you rephrase it?",
                breach_names,
            )

        except Exception as e:
            logger.error(f"Input guardrail check failed: {e}")
            return True, "", []

    async def check_output(
        self, input_msg: str, output_msg: str
    ) -> tuple:
        """Check output message against guardrails.

        Returns:
            Tuple of (is_safe: bool, fallback_message: str, details: list)
        """
        self._ensure_initialized()

        if not self._output_guards:
            return True, "", []

        breach_names = []
        try:
            for guard in self._output_guards:
                safety_level = await guard.a_guard_output(
                    input=input_msg, output=output_msg
                )
                guard_name = type(guard).__name__.lower()

                if safety_level and safety_level.lower() != "safe":
                    reason = getattr(guard, "reason", "")
                    breach_names.append(guard_name)
                    logger.warning(
                        "Output guardrail breach",
                        extra={"guard": guard_name, "reason": reason},
                    )

            if not breach_names:
                return True, "", []

            return (
                False,
                "I apologize, but I need to rephrase my response. "
                "Could you try asking your question differently?",
                breach_names,
            )

        except Exception as e:
            logger.error(f"Output guardrail check failed: {e}")
            return True, "", []


# Lazy singleton
_guardrail_service: Optional[GuardrailService] = None


def get_guardrail_service() -> GuardrailService:
    """Get or create the singleton GuardrailService."""
    global _guardrail_service
    if _guardrail_service is None:
        _guardrail_service = GuardrailService()
    return _guardrail_service
