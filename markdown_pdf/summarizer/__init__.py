"""Small DeepSeek-backed Markdown summarizer."""

from .deepseek import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    MAX_SOURCE_CHARACTERS,
    SYSTEM_PROMPT,
    SummaryError,
    SummaryResult,
    build_messages,
    summarize_markdown,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "MAX_SOURCE_CHARACTERS",
    "SYSTEM_PROMPT",
    "SummaryError",
    "SummaryResult",
    "build_messages",
    "summarize_markdown",
]
