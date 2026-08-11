import unittest

from longread_pdf.renderer import build_document, normalize_markdown


class RendererTests(unittest.TestCase):
    def test_normalize_emphasis_moves_terminal_punctuation(self):
        normalized, changes = normalize_markdown("这是**重点。**")
        self.assertEqual(normalized, "这是**重点**。")
        self.assertEqual(changes, 1)

    def test_desktop_document_has_serif_running_header(self):
        document = build_document("# 标题\n> 副标题\n\n## 第一章\n\n正文。", mode="desktop")
        self.assertIn('class="mode-desktop"', document.html)
        self.assertIn("size: A4", document.html)
        self.assertIn('content: "标题"', document.html)
        self.assertIn("font-family: var(--serif)", document.html)

    def test_mobile_document_suppresses_running_header(self):
        document = build_document("# 标题\n\n## 第一章\n\n正文。", mode="mobile")
        self.assertIn('class="mode-mobile"', document.html)
        self.assertIn("size: 108mm 192mm", document.html)
        self.assertIn("content: none", document.html)

    def test_raw_script_is_removed(self):
        document = build_document("# 标题\n\n## 正文\n\n<script>alert(1)</script>安全。")
        self.assertNotIn("<script", document.html)


if __name__ == "__main__":
    unittest.main()
