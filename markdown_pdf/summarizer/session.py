"""Hand the model calls to the calling agent (for example Claude Code) instead of the API.

A job folder holds the inputs and one request/reply pair per model call:

    <stem>.session/
      job.json       task, workflow flags and output settings
      source.md      the source text, shared by every request
      request-1.md   the messages DeepSeek would get, with `source` pointing at source.md
      reply-1.json   the agent's answer: one JSON object in the system prompt's schema
      request-2.md   a compression or revision pass, when the workflow needs one

Requests are rebuilt by replaying the recorded replies through the same workflow the
API path runs. A reply counts only while its request file still matches the rebuilt
request, so rewriting an earlier reply discards the later, now stale, files.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from typing import Any

from .deepseek import SummaryDocument, SummaryError, SummaryRequest, parse_summary_reply
from .workflow import summary_workflow

JOB_FILE = "job.json"
SOURCE_FILE = "source.md"
SOURCE_POINTER = f"（全文见同目录 {SOURCE_FILE}）"


def render_request(request: SummaryRequest, number: int) -> str:
    """The request as readable Markdown: same messages, source lifted out, payload indented."""
    system, user = (message["content"] for message in request.messages)
    preamble, raw_payload = user.split("\n", 1)
    payload = json.loads(raw_payload)
    payload["source"] = SOURCE_POINTER
    title = f"# Request {number} · {request.step}" + (f" · {request.note}" if request.note else "")
    return "\n".join([
        title,
        "",
        f"Answer as the model: follow the system prompt and user message below, and save only the "
        f"JSON object to `reply-{number}.json`. `source` is the full text of `{SOURCE_FILE}` in this folder.",
        "",
        "## System prompt",
        "",
        system,
        "",
        "## User message",
        "",
        preamble,
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
    ])


@dataclass(frozen=True)
class SessionJob:
    directory: Path
    source: str
    task: dict[str, Any]
    flags: dict[str, bool]
    output: dict[str, Any]

    @classmethod
    def create(
        cls,
        directory: Path,
        *,
        source: str,
        task: dict[str, Any],
        flags: dict[str, bool],
        output: dict[str, Any],
    ) -> SessionJob:
        if (directory / JOB_FILE).exists():
            shutil.rmtree(directory)  # a new run replaces an earlier job for the same output
        elif directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
            raise SummaryError(f"{directory} exists and is not a summary job; pick another -n/-o.")
        directory.mkdir(parents=True, exist_ok=True)
        job = {"version": 1, "task": task, "flags": flags, "output": output}
        (directory / JOB_FILE).write_text(json.dumps(job, ensure_ascii=False, indent=2), "utf-8")
        (directory / SOURCE_FILE).write_text(source, "utf-8")
        return cls(directory, source, task, flags, output)

    @classmethod
    def load(cls, directory: Path) -> SessionJob:
        try:
            job = json.loads((directory / JOB_FILE).read_text("utf-8"))
            source = (directory / SOURCE_FILE).read_text("utf-8")
            if job["version"] != 1:
                raise ValueError(f"unsupported job version {job['version']}")
            return cls(directory, source, dict(job["task"]), dict(job["flags"]), dict(job["output"]))
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise SummaryError(f"{directory} is not a readable summary job: {error}") from error

    def request_path(self, number: int) -> Path:
        return self.directory / f"request-{number}.md"

    def reply_path(self, number: int) -> Path:
        return self.directory / f"reply-{number}.json"

    def advance(self) -> tuple[int, SummaryRequest] | SummaryDocument:
        """Write the next unanswered request and return it with its number, or the final document."""
        steps = summary_workflow(self.source, self.task, **self.flags)
        request, number = next(steps), 1
        while self.reply_path(number).exists() and self._issued(request, number):
            try:
                document = parse_summary_reply(self.reply_path(number).read_text("utf-8"))
            except SummaryError as error:
                raise SummaryError(f"{self.reply_path(number).name}: {error}") from error
            try:
                request = steps.send(document)
            except StopIteration as finished:
                return finished.value
            number += 1
        self._discard_from(number)
        self.request_path(number).write_text(render_request(request, number), "utf-8")
        return number, request

    def _issued(self, request: SummaryRequest, number: int) -> bool:
        path = self.request_path(number)
        return path.exists() and path.read_text("utf-8") == render_request(request, number)

    def _discard_from(self, number: int) -> None:
        for path in [*self.directory.glob("request-*.md"), *self.directory.glob("reply-*.json")]:
            suffix = path.stem.split("-", 1)[1]
            if suffix.isdigit() and int(suffix) >= number:
                path.unlink()
