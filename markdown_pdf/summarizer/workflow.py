"""The CLI's summary workflow, independent of who answers the model calls."""

from __future__ import annotations

from typing import Any, Mapping

from .deepseek import (
    SummarySteps,
    revision_request,
    summary_steps,
    verify_byline,
)
from .quality import lint_summary_document

ATTRIBUTION_FEEDBACK = "核对每条的主语、指控方与被指控方是否与原文一致。"


def summary_workflow(
    markdown_source: str,
    task: Mapping[str, Any],
    *,
    revise: bool = False,
    check_attribution: bool = False,
) -> SummarySteps:
    """Draft and compression passes, then the optional lint revision and attribution check.

    `task` holds build_messages' editorial keywords (mode, language, style, length,
    custom_instructions, material).
    """
    source = markdown_source.strip()  # lint and byline checks must see the text the prompt got
    document = yield from summary_steps(source, **task)
    if revise:
        report = lint_summary_document(document, source)
        if not report.passed:
            document = yield revision_request(
                source, document, [issue.message for issue in report.issues],
                step="quality", note=f"{len(report.issues)} lint issue(s)", **task,
            )
    if check_attribution:
        document = yield revision_request(
            source, document, [ATTRIBUTION_FEEDBACK],
            step="attribution", note="re-checking who said/accused what", **task,
        )
    return verify_byline(document, source, task.get("material"))

