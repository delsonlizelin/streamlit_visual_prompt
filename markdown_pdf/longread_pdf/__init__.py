"""Deterministic Markdown-to-PDF rendering for long-form reading."""

from .preflight import PreflightIssue, PreflightReport, preflight_markdown
from .renderer import RenderError, RenderResult, build_document, render_markdown

__all__ = [
    "PreflightIssue",
    "PreflightReport",
    "RenderError",
    "RenderResult",
    "build_document",
    "preflight_markdown",
    "render_markdown",
]
