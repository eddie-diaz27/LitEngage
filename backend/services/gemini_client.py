"""Google Gemini LLM client wrapper for LangChain."""

import logging
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from backend.config import settings

logger = logging.getLogger(__name__)


def get_llm(
    with_tools: Optional[list] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> ChatGoogleGenerativeAI:
    """Create a ChatGoogleGenerativeAI instance.

    Args:
        with_tools: Optional list of tools to bind to the LLM.
        temperature: Override default temperature.
        max_tokens: Override default max tokens.

    Returns:
        Configured LLM instance.
    """
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=temperature or settings.gemini_temperature,
        max_output_tokens=max_tokens or settings.gemini_max_tokens,
        google_api_key=settings.google_api_key,
    )

    if with_tools:
        llm = llm.bind_tools(with_tools)
        logger.debug(f"LLM bound with {len(with_tools)} tools")

    return llm
