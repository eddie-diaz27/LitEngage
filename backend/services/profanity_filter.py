"""Zero-cost profanity pre-filter using better-profanity.

Catches obvious profanity/swear words before any LLM calls,
saving tokens and providing instant rejection responses.
Uses string matching (no ML, no API calls) — sub-millisecond execution.
"""

import logging

from better_profanity import profanity

from backend.config import settings

logger = logging.getLogger(__name__)

# Pre-formatted rejection messages (zero tokens)
STUDENT_REJECTION = (
    "Let's keep our conversation school-friendly! "
    "I'm here to help you find great books to read. "
    "What kind of story are you in the mood for?"
)

LIBRARIAN_REJECTION = (
    "Please keep the conversation appropriate for a school environment. "
    "How can I help you with library management today?"
)

REVIEW_REJECTION = (
    "Your review contains language that isn't appropriate for our school library. "
    "Please revise your review and try again."
)


class ProfanityFilter:
    """Zero-cost profanity detection using better-profanity library."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._setup()

    def _setup(self):
        """Initialize the profanity filter with custom word list."""
        profanity.load_censor_words()

        # Add custom words from settings (CSV string)
        if settings.profanity_custom_words:
            custom = [
                w.strip()
                for w in settings.profanity_custom_words.split(",")
                if w.strip()
            ]
            if custom:
                profanity.add_censor_words(custom)
                logger.info(f"Added {len(custom)} custom profanity words")

        logger.info("Profanity filter initialized")

    def contains_profanity(self, text: str) -> bool:
        """Check if text contains profanity. Zero cost, sub-ms."""
        if not settings.enable_profanity_filter:
            return False
        return profanity.contains_profanity(text)

    def check_input(self, text: str, context: str = "student") -> tuple[bool, str | None]:
        """Check text for profanity.

        Args:
            text: The text to check.
            context: One of "student", "librarian", "review".

        Returns:
            (is_clean, rejection_message). If clean, rejection_message is None.
        """
        if not settings.enable_profanity_filter:
            return True, None

        if profanity.contains_profanity(text):
            rejection = {
                "student": STUDENT_REJECTION,
                "librarian": LIBRARIAN_REJECTION,
                "review": REVIEW_REJECTION,
            }.get(context, STUDENT_REJECTION)

            logger.info(
                "Profanity filter triggered",
                extra={"context": context, "text_length": len(text)},
            )
            return False, rejection

        return True, None

    def censor(self, text: str) -> str:
        """Censor profanity in text (replace with asterisks)."""
        return profanity.censor(text)


def get_profanity_filter() -> ProfanityFilter:
    """Get the singleton profanity filter instance."""
    return ProfanityFilter()
