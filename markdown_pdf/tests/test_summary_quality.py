from __future__ import annotations

import unittest

from summarizer.deepseek import SummaryDocument, SummaryItem, SummarySection
from summarizer.quality import extract_numeric_tokens, lint_summary_document


def document_with(*items: str, headings: tuple[str, ...] = ("判断",)) -> SummaryDocument:
    sections = tuple(
        SummarySection(
            heading=heading,
            items=tuple(SummaryItem(text=text) for text in items),
        )
        for heading in headings
    )
    return SummaryDocument(title="测试主题", byline=None, lead=None, sections=sections)


class SummaryQualityTests(unittest.TestCase):
    def test_clean_document_passes(self):
        report = lint_summary_document(
            document_with("通胀仍高于目标，但劳动力市场保持稳定。"),
            "原文说明通胀仍高于目标，但劳动力市场保持稳定。",
        )
        self.assertTrue(report.passed)
        self.assertEqual(report.checked_items, 1)

    def test_compound_item_is_reported_without_mutating_content(self):
        document = document_with("原则包括：数据必须及时；目标必须固定；沟通必须克制。")
        report = lint_summary_document(document)
        self.assertIn("compound-item", {issue.code for issue in report.issues})
        self.assertEqual(document.sections[0].items[0].text, "原则包括：数据必须及时；目标必须固定；沟通必须克制。")

    def test_duplicate_items_are_reported(self):
        document = document_with(
            "政策会继续依赖数据，并根据经济前景的变化调整。",
            "政策将继续依赖数据，并根据经济前景变化进行调整。",
        )
        report = lint_summary_document(document)
        self.assertIn("duplicate-item", {issue.code for issue in report.issues})

    def test_repeated_lead_and_first_item_are_reported(self):
        document = SummaryDocument(
            title="测试主题",
            byline=None,
            lead="项目只支持有限范围的试点，不承诺全面部署。",
            sections=(
                SummarySection(
                    "实施范围",
                    (SummaryItem("项目只支持有限范围的试点，不承诺全面部署。"),),
                ),
            ),
        )
        report = lint_summary_document(document)
        self.assertIn("lead-duplicate", {issue.code for issue in report.issues})

    def test_unsupported_summary_number_is_reported(self):
        document = document_with("目标将在 2028 年降至 2%。")
        report = lint_summary_document(document, "原文只说目标会逐步下降到 2%。")
        self.assertIn("unsupported-number", {issue.code for issue in report.issues})

    def test_pdf_page_markers_do_not_support_summary_numbers(self):
        document = document_with("政策分为 3 类。")
        report = lint_summary_document(document, "[第 3 页]\n\n原文只说政策有几类。")
        self.assertIn("unsupported-number", {issue.code for issue in report.issues})

    def test_number_normalization_accepts_commas_and_spacing(self):
        self.assertEqual(extract_numeric_tokens("共 1,200 人"), ("1200人",))
        document = document_with("参与者共有1200人。")
        report = lint_summary_document(document, "参与者共有 1,200 人。")
        self.assertNotIn("unsupported-number", {issue.code for issue in report.issues})

    def test_two_question_headings_are_reported(self):
        document = SummaryDocument(
            title="测试主题",
            byline=None,
            lead=None,
            sections=(
                SummarySection("发生了什么？", (SummaryItem("第一项具体判断。"),)),
                SummarySection("为什么重要？", (SummaryItem("第二项具体判断。"),)),
            ),
        )
        report = lint_summary_document(document)
        self.assertIn("question-heading-density", {issue.code for issue in report.issues})

    def test_highlight_density_warning_uses_actual_highlights(self):
        document = SummaryDocument(
            title="测试主题",
            byline=None,
            lead=None,
            sections=(
                SummarySection(
                    "判断",
                    (SummaryItem("关键结论改变判断。", ("关键结论", "改变判断")),),
                ),
            ),
        )
        report = lint_summary_document(document)
        self.assertIn("highlight-density", {issue.code for issue in report.issues})


if __name__ == "__main__":
    unittest.main()


class CrossLanguageNumberTests(unittest.TestCase):
    def unsupported(self, summary: str, source: str) -> bool:
        report = lint_summary_document(document_with(summary), source)
        return "unsupported-number" in {issue.code for issue in report.issues}

    def test_rewritten_quantities_are_accepted(self):
        cases = [
            ("CA 称 Britney 欠她 1.8万美元。", "Britney wasn't paying her $18,000."),
            ("欠款 18,000 美元。", "her $18,000"),
            ("这是 2016年 的旧事。", "back from 2016 when"),
            ("生涯奖金约 2000 万美元。", "like 20 million in cashes"),
            ("被指拿走 8万筹码。", "pocketing 80,000 chips"),
            ("营收达到 3.5 billion 美元。", "营收为 35 亿美元。"),
        ]
        for summary, source in cases:
            with self.subTest(summary=summary):
                self.assertFalse(self.unsupported(summary, source))

    def test_changed_quantities_are_still_reported(self):
        self.assertTrue(self.unsupported("欠她 1.9万美元。", "her $18,000"))
        self.assertTrue(self.unsupported("拿走 9万筹码。", "pocketing 80,000 chips"))


class LeadLengthTests(unittest.TestCase):
    def test_long_lead_is_reported(self):
        from summarizer.deepseek import SummaryDocument, SummaryItem, SummarySection

        def report(lead: str):
            document = SummaryDocument("标题", None, lead, (SummarySection("判断", (SummaryItem("条目内容。"),)),))
            return {issue.code for issue in lint_summary_document(document).issues}

        self.assertIn("long-lead", report("甲与乙因一笔欠款起争执，" * 15))
        self.assertNotIn("long-lead", report("甲与乙因一笔欠款起争执，目前仍在审查。"))
