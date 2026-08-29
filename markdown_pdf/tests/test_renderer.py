import unittest

from longread_pdf.preflight import preflight_markdown
from longread_pdf.gpt_prompt import GPT_MARKDOWN_PROMPT
from longread_pdf.renderer import (
    RenderError,
    build_document,
    build_summary_document,
    normalize_markdown,
)
from summarizer.deepseek import SummaryDocument, SummaryItem, SummarySection


class RendererTests(unittest.TestCase):
    def test_gpt_prompt_contains_renderer_contract(self):
        self.assertIn("第一行必须是全文唯一的一级标题", GPT_MARKDOWN_PROMPT)
        self.assertIn("不要使用原始 HTML", GPT_MARKDOWN_PROMPT)
        self.assertIn("不要用三个反引号把整篇文章包起来", GPT_MARKDOWN_PROMPT)
        self.assertNotIn("填写主题", GPT_MARKDOWN_PROMPT)
        self.assertNotIn("推荐结构", GPT_MARKDOWN_PROMPT)

    def test_normalize_emphasis_moves_terminal_punctuation(self):
        normalized, changes = normalize_markdown("这是**重点。**")
        self.assertEqual(normalized, "这是**重点**。")
        self.assertEqual(changes, 1)

    def test_desktop_document_has_no_running_header_or_cover_footer(self):
        document = build_document("# 标题\n> 副标题\n\n## 第一章\n\n正文。", mode="desktop")
        self.assertIn('class="mode-desktop"', document.html)
        self.assertIn("size: A4", document.html)
        self.assertNotIn("data-running-title", document.html)
        self.assertNotIn('class="cover-meta"', document.html)
        self.assertNotIn("阅读版", document.html)
        self.assertIn("@top-left { content: none; }", document.html)

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

    def test_document_without_title_starts_directly_with_body(self):
        document = build_document("开场正文。\n\n## 第一章\n\n继续阅读。", mode="desktop")
        self.assertNotIn('class="cover"', document.html)
        self.assertNotIn('class="toc-page"', document.html)
        self.assertIn("开场正文。", document.html)
        self.assertIn('id="section-01"', document.html)

    def test_empty_h1_does_not_create_blank_cover(self):
        document = build_document("#\n\n正文从这里开始。", mode="mobile")
        self.assertNotIn('class="cover"', document.html)
        self.assertNotIn("<h1></h1>", document.html)
        self.assertIn("正文从这里开始。", document.html)

    def test_untitled_quote_stays_in_first_page_body(self):
        document = build_document("> 这段引用属于正文。\n\n后续正文。", mode="desktop")
        self.assertNotIn('class="cover"', document.html)
        self.assertIn("<blockquote>", document.html)
        self.assertIn("这段引用属于正文。", document.html)

    def test_titled_document_without_sections_does_not_create_blank_toc(self):
        document = build_document("# 标题\n\n只有正文。", mode="desktop")
        self.assertIn('class="cover"', document.html)
        self.assertNotIn('class="toc-page"', document.html)

    def test_summary_pdf_uses_compact_template_without_cover_or_toc(self):
        document = build_summary_document(
            "# 摘要标题\n\n## 核心内容\n\n- 第一条。",
            mode="tablet",
        )
        self.assertIn('class="summary-header"', document.html)
        self.assertIn('class="longread"', document.html)
        self.assertIn('class="summary-card"', document.html)
        self.assertIn('data-section="1"', document.html)
        self.assertNotIn('class="cover"', document.html)
        self.assertNotIn('class="toc-page"', document.html)

    def test_long_image_uses_continuous_mobile_layout(self):
        document = build_summary_document(
            "# 摘要标题\n\n正文。",
            mode="mobile",
            continuous=True,
        )
        self.assertIn("continuous-output", document.html)
        self.assertNotIn("读到这里，已经抓住全文主线", document.html)
        self.assertIn("overflow: hidden", document.html)
        self.assertIn('font-family: "Noto Sans SC"', document.html)
        self.assertIn("NotoSansSC-VariableFont_wght.ttf", document.html)

    def test_structured_summary_escapes_text_and_marks_valid_highlights(self):
        summary = SummaryDocument(
            title="结构化摘要 <测试>",
            byline="Kevin Warsh",
            lead=None,
            sections=(
                SummarySection(
                    heading="通胀判断是什么？",
                    items=(
                        SummaryItem(
                            text="通胀仍高于 2% 目标，但不应把观点写成事实。",
                            highlights=("高于 2% 目标", "并不存在"),
                        ),
                    ),
                ),
            ),
        )
        document = build_summary_document(summary, mode="mobile", continuous=True)
        self.assertIn("结构化摘要 &lt;测试&gt;", document.html)
        self.assertIn("Kevin Warsh", document.html)
        self.assertIn("<strong>高于 2% 目标</strong>", document.html)
        self.assertNotIn("<strong>并不存在</strong>", document.html)
        self.assertEqual(document.sections, 1)

    def test_long_image_rejects_desktop_mode(self):
        with self.assertRaisesRegex(RenderError, "只支持平板和手机"):
            build_summary_document("# 摘要", mode="desktop", continuous=True)

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
