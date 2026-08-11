"""Deterministic Markdown-to-PDF rendering for long-form reading."""

from .gpt_prompt import GPT_MARKDOWN_PROMPT
from .preflight import PreflightIssue, PreflightReport, preflight_markdown
from .renderer import (
    LongImageResult,
    RenderError,
    RenderResult,
    build_document,
    build_summary_document,
    render_markdown,
    render_summary_long_image,
    render_summary_pdf,
)

__all__ = [
    "PreflightIssue",
    "PreflightReport",
    "GPT_MARKDOWN_PROMPT",
    "LongImageResult",
    "RenderError",
    "RenderResult",
    "build_document",
    "build_summary_document",
    "preflight_markdown",
    "render_markdown",
    "render_summary_long_image",
    "render_summary_pdf",
]
