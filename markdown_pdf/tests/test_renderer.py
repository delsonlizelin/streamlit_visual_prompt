import unittest

from longread_pdf.preflight import preflight_markdown
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

    def test_tablet_document_uses_ipad_mini_ratio(self):
        document = build_document("# 标题\n\n## 第一章\n\n正文。", mode="tablet")
        self.assertIn('class="mode-tablet"', document.html)
        self.assertIn("size: 132mm 201mm", document.html)
        self.assertIn("font-size: 12.1pt", document.html)
        self.assertIn("content: none", document.html)

    def test_bare_url_gets_safe_wrapping_class(self):
        target = "https://example.com/a/very-long-path-without-a-readable-label"
        document = build_document(f"# 标题\n\n## 来源\n\n<{target}>", mode="mobile")
        self.assertIn('class="bare-url"', document.html)
        self.assertIn("overflow-wrap: anywhere", document.html)

    def test_human_readable_link_keeps_normal_link_style(self):
        document = build_document("# 标题\n\n## 来源\n\n[官方网站](https://example.com/long-path)")
        self.assertNotIn('class="bare-url"', document.html)

    def test_markdown_autolink_is_not_reported_as_raw_html(self):
        report = preflight_markdown("# 标题\n\n<https://example.com/a-long-path>")
        self.assertNotIn("raw-html", {issue.code for issue in report.issues})

    def test_raw_script_is_removed(self):
        document = build_document("# 标题\n\n## 正文\n\n<script>alert(1)</script>安全。")
        self.assertNotIn("<script", document.html)

    def test_preflight_reports_structural_and_narrow_page_risks(self):
        source = """# 标题

### 跳级标题

![本地图片](images/chart.png)

https://example.com/a/very/long/path/with/query?alpha=1234567890&beta=abcdefghijk

```mermaid
graph TD
```
"""
        report = preflight_markdown(source)
        codes = {issue.code for issue in report.issues}
        self.assertTrue({"heading-jump", "local-image", "long-url", "mermaid"} <= codes)

    def test_preflight_reports_unclosed_fence_as_error(self):
        report = preflight_markdown("# 标题\n\n```python\nprint('x')")
        self.assertEqual(report.errors, 1)
        self.assertEqual(report.issues[0].code, "unclosed-fence")


if __name__ == "__main__":
    unittest.main()
