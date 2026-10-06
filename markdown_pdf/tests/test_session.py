from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from summarizer.deepseek import SummaryDocument, SummaryError, build_messages, parse_summary_reply, summary_steps
from summarizer.session import SOURCE_POINTER, SessionJob, render_request
from summarizer.workflow import summary_workflow

PROJECT_DIR = Path(__file__).resolve().parents[1]
SOURCE = "# 原文\n\n作者甲认为关键事实决定结论，并给出 3 个例子。"
TASK = dict(mode="standard", language="zh", style="direct", length="normal", custom_instructions="", material=None)
REPLY = {
    "title": "测试主题",
    "byline": "作者甲",
    "lead": None,
    "sections": [{"heading": "结论", "items": [{"text": "作者甲认为关键事实决定结论。", "highlights": []}]}],
}
LONG_REPLY = dict(REPLY, sections=[{"heading": "分区", "items": [{"text": "一" * 90, "highlights": []}] * 12}])


def replay(steps, replies):
    """Feed replies in order: the first unanswered request, or the final document."""
    request = next(steps)
    for reply in replies:
        try:
            request = steps.send(reply)
        except StopIteration as finished:
            return finished.value
    return request


def document(value: dict) -> SummaryDocument:
    return parse_summary_reply(json.dumps(value, ensure_ascii=False))


class SummaryStepsTests(unittest.TestCase):
    def test_first_request_is_exactly_the_api_prompt(self):
        request = next(summary_steps(SOURCE, **TASK))
        self.assertEqual(request.step, "summary")
        self.assertEqual(request.messages, build_messages(SOURCE, **TASK))

    def test_overshoot_asks_for_compression_then_finishes(self):
        steps = summary_steps(SOURCE, **TASK)
        next(steps)
        budget = steps.send(document(LONG_REPLY))
        self.assertEqual(budget.step, "budget")
        self.assertIn("篇幅超出", budget.messages[1]["content"])
        finished = replay(summary_steps(SOURCE, **TASK), [document(LONG_REPLY), document(REPLY)])
        self.assertEqual(finished.title, "测试主题")
        self.assertEqual(finished.byline, "作者甲")  # named in the source, so verify_byline keeps it

    def test_workflow_adds_attribution_check_and_drops_unsupported_byline(self):
        steps = summary_workflow(SOURCE, TASK, check_attribution=True)
        attribution = replay(steps, [document(REPLY)])
        self.assertEqual(attribution.step, "attribution")
        unsupported = dict(REPLY, byline="某频道")
        finished = replay(summary_workflow(SOURCE, TASK, check_attribution=True), [document(REPLY), document(unsupported)])
        self.assertIsNone(finished.byline)

    def test_workflow_revises_only_when_lint_finds_issues(self):
        numbers = dict(REPLY, sections=[{"heading": "结论", "items": [{"text": "作者甲给出 99 个例子。", "highlights": []}]}])
        self.assertIsInstance(replay(summary_workflow(SOURCE, TASK, revise=True), [document(REPLY)]), SummaryDocument)
        quality = replay(summary_workflow(SOURCE, TASK, revise=True), [document(numbers)])
        self.assertEqual(quality.step, "quality")


class SessionJobTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.job = SessionJob.create(
            self.folder / "x.session", source=SOURCE, task=TASK,
            flags=dict(revise=False, check_attribution=False),
            output=dict(out_dir=str(self.folder), stem="x", formats=["md"], image_mode="tablet"),
        )

    def test_request_lifts_source_out_but_keeps_everything_else(self):
        number, request = self.job.advance()
        self.assertEqual(number, 1)
        text = self.job.request_path(1).read_text("utf-8")
        self.assertIn(request.messages[0]["content"], text)
        self.assertNotIn("作者甲认为关键事实", text)
        rendered = json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])
        original = json.loads(request.messages[1]["content"].split("\n", 1)[1])
        self.assertEqual(rendered, dict(original, source=SOURCE_POINTER))
        self.assertEqual(text, render_request(request, 1))

    def test_replies_drive_the_job_to_a_document(self):
        self.job.advance()
        self.job.reply_path(1).write_text(json.dumps(LONG_REPLY, ensure_ascii=False), "utf-8")
        number, request = SessionJob.load(self.job.directory).advance()
        self.assertEqual((number, request.step), (2, "budget"))
        self.job.reply_path(2).write_text(f"```json\n{json.dumps(REPLY, ensure_ascii=False)}\n```", "utf-8")
        self.assertEqual(SessionJob.load(self.job.directory).advance().title, "测试主题")

    def test_rewriting_an_earlier_reply_discards_later_stale_files(self):
        job = SessionJob(self.job.directory, SOURCE, TASK, dict(revise=False, check_attribution=True), self.job.output)
        job.advance()
        job.reply_path(1).write_text(json.dumps(LONG_REPLY, ensure_ascii=False), "utf-8")
        self.assertEqual(job.advance()[1].step, "budget")
        job.reply_path(2).write_text(json.dumps(REPLY, ensure_ascii=False), "utf-8")
        job.reply_path(1).write_text(json.dumps(REPLY, ensure_ascii=False), "utf-8")  # now in budget
        number, request = job.advance()  # request 2 becomes the attribution check; the budget reply is stale
        self.assertEqual((number, request.step), (2, "attribution"))
        self.assertFalse(job.reply_path(2).exists())

    def test_bad_reply_names_its_file(self):
        self.job.advance()
        self.job.reply_path(1).write_text("{not json", "utf-8")
        with self.assertRaisesRegex(SummaryError, "reply-1.json"):
            self.job.advance()

    def test_broken_job_file_is_a_summary_error(self):
        (self.job.directory / "job.json").write_text("{}", "utf-8")
        with self.assertRaisesRegex(SummaryError, "not a readable summary job"):
            SessionJob.load(self.job.directory)

    def test_new_run_replaces_an_old_job_but_not_other_folders(self):
        self.job.reply_path(1).write_text("{}", "utf-8")
        again = SessionJob.create(self.job.directory, source=SOURCE, task=TASK, flags=self.job.flags, output=self.job.output)
        self.assertFalse(again.reply_path(1).exists())
        other = self.folder / "notes"
        other.mkdir()
        (other / "keep.txt").write_text("mine", "utf-8")
        with self.assertRaises(SummaryError):
            SessionJob.create(other, source=SOURCE, task=TASK, flags=self.job.flags, output=self.job.output)


class SessionCliTests(unittest.TestCase):
    def test_cli_round_trip_writes_outputs_and_removes_the_job(self):
        folder = Path(tempfile.mkdtemp()).resolve()
        (folder / "a.md").write_text(SOURCE, "utf-8")
        cli = [sys.executable, str(PROJECT_DIR / "summarize_cli.py")]
        started = subprocess.run([*cli, str(folder / "a.md"), "--engine", "session", "--mode", "standard",
                                  "--formats", "md", "-n", "a"], capture_output=True, text=True, check=True)
        job_dir = folder / "a.session"
        self.assertEqual(started.stdout.strip(), str(job_dir / "request-1.md"))
        (job_dir / "reply-1.json").write_text(json.dumps(REPLY, ensure_ascii=False), "utf-8")
        finished = subprocess.run([*cli, "--resume", str(job_dir)], capture_output=True, text=True, check=True)
        self.assertEqual(finished.stdout.strip(), str(folder / "a.summary.md"))
        self.assertIn("测试主题", (folder / "a.summary.md").read_text("utf-8"))
        self.assertFalse(job_dir.exists())


if __name__ == "__main__":
    unittest.main()
