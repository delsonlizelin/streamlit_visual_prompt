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

    def test_unsupported_summary_number_is_reported(self):
        document = document_with("目标将在 2028 年降至 2%。")
        report = lint_summary_document(document, "原文只说目标会逐步下降到 2%。")
        self.assertIn("unsupported-number", {issue.code for issue in report.issues})

    def test_number_normalization_accepts_commas_and_spacing(self):
        self.assertEqual(extract_numeric_tokens("共 1,200 人"), ("1200人",))
        document = document_with("参与者共有1200人。")
        report = lint_summary_document(document, "参与者共有 1,200 人。")
        self.assertNotIn("unsupported-number", {issue.code for issue in report.issues})


if __name__ == "__main__":
    unittest.main()
