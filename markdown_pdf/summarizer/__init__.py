"""Small DeepSeek-backed Markdown summarizer."""

from .deepseek import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    MAX_SOURCE_CHARACTERS,
    MODE_CAPTIONS,
    MODE_INSTRUCTIONS,
    MODE_LABELS,
    SYSTEM_PROMPT,
    SummaryError,
    SummaryResult,
    build_messages,
    build_prompt_template,
    summarize_markdown,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "MAX_SOURCE_CHARACTERS",
    "MODE_CAPTIONS",
    "MODE_INSTRUCTIONS",
    "MODE_LABELS",
    "SYSTEM_PROMPT",
    "SummaryError",
    "SummaryResult",
    "build_messages",
    "build_prompt_template",
    "summarize_markdown",
]
