"""Deterministic Markdown-to-PDF rendering for long-form reading."""

from .gpt_prompt import GPT_MARKDOWN_PROMPT
from .preflight import PreflightIssue, PreflightReport, preflight_markdown
from .renderer import RenderError, RenderResult, build_document, render_markdown

__all__ = [
    "PreflightIssue",
    "PreflightReport",
    "GPT_MARKDOWN_PROMPT",
    "RenderError",
    "RenderResult",
    "build_document",
    "preflight_markdown",
    "render_markdown",
]
