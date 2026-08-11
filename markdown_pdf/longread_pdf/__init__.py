"""Deterministic Markdown-to-PDF rendering for long-form reading."""

from .renderer import RenderError, RenderResult, build_document, render_markdown

__all__ = ["RenderError", "RenderResult", "build_document", "render_markdown"]
