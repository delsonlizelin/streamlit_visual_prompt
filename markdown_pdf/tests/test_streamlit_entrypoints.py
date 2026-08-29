from __future__ import annotations

import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import streamlit
from streamlit.testing.v1 import AppTest

from summarizer import deepseek as summarizer_backend


APP_ROOT = Path(__file__).resolve().parent.parent
STREAMLIT_VERSION = tuple(int(part) for part in streamlit.__version__.split(".")[:2])


def no_op(*args: object, **kwargs: object) -> None:
    """Stand in for helpers provided by the previous component revision."""


class StreamlitEntrypointTests(unittest.TestCase):
    def test_pages_launch_with_stale_ui_components_module(self) -> None:
        entrypoints = [
            APP_ROOT / "streamlit_app.py",
            APP_ROOT / "pages" / "2_文章摘要.py",
        ]
        for entrypoint in entrypoints:
            with self.subTest(entrypoint=entrypoint.name):
                stale_components = ModuleType("ui_components")
                stale_components.clipboard_button = no_op
                stale_components.page_navigation = no_op
                with patch.dict("sys.modules", {"ui_components": stale_components}):
                    app = AppTest.from_file(entrypoint, default_timeout=10)
                    app.run()
                    self.assertEqual(list(app.exception), [])
                    self.assertTrue(hasattr(stale_components, "page_shell_styles"))

    def test_summary_page_ignores_stale_summarizer_re_exports(self) -> None:
        stale_summarizer = ModuleType("summarizer")
        stale_summarizer.__path__ = [str(APP_ROOT / "summarizer")]
        stale_summarizer.deepseek = summarizer_backend
        with patch.dict("sys.modules", {"summarizer": stale_summarizer}):
            app = AppTest.from_file(
                APP_ROOT / "pages" / "2_文章摘要.py",
                default_timeout=10,
            ).run()

        self.assertEqual(list(app.exception), [])

    def test_summary_page_reloads_stale_summarizer_backend(self) -> None:
        stale_backend = ModuleType("summarizer.deepseek")
        with patch.dict("sys.modules", {"summarizer.deepseek": stale_backend}):
            app = AppTest.from_file(
                APP_ROOT / "pages" / "2_文章摘要.py",
                default_timeout=10,
            ).run()

        self.assertEqual(list(app.exception), [])
        self.assertTrue(hasattr(stale_backend, "STYLE_LABELS"))

    def test_summary_page_exposes_current_prompt_copy_button(self) -> None:
        source = (APP_ROOT / "pages" / "2_文章摘要.py").read_text(encoding="utf-8")
        self.assertIn('"复制完整 Prompt"', source)
        self.assertIn("build_prompt_template", source)

    @unittest.skipIf(
        STREAMLIT_VERSION < (1, 60),
        "Streamlit 1.50 AppTest cannot replay pages containing v2 custom components.",
    )
    def test_summary_page_separates_structure_from_explanation_style(self) -> None:
        app = AppTest.from_file(
            APP_ROOT / "pages" / "2_文章摘要.py",
            default_timeout=10,
        ).run()
        mode_control = next(
            control
            for control in app.get("button_group")
            if control.label == "内容结构"
        )
        self.assertEqual(
            mode_control.options,
            ["核心摘要（推荐）", "按章节梳理"],
        )
        style_control = next(
            control
            for control in app.get("button_group")
            if control.label == "讲述方式"
        )
        self.assertEqual(style_control.options, ["直接摘要", "易懂解释"])
        style_control.set_value("易懂解释").run()
        self.assertEqual(style_control.value, "易懂解释")
        length_control = next(
            control
            for control in app.get("button_group")
            if control.label == "详细程度"
        )
        self.assertEqual(length_control.options, ["标准篇幅（推荐）", "详细展开"])
        length_control.set_value("详细展开").run()
        self.assertEqual(length_control.value, "详细展开")
        model_control = next(
            selectbox for selectbox in app.selectbox if selectbox.label == "摘要模型"
        )
        self.assertEqual(
            model_control.options,
            ["DeepSeek V4 Flash", "DeepSeek V4 Pro"],
        )
        model_control.set_value("DeepSeek V4 Pro").run()
        self.assertEqual(model_control.value, "DeepSeek V4 Pro")
        self.assertEqual(list(app.exception), [])

    @unittest.skipIf(
        STREAMLIT_VERSION < (1, 60),
        "Streamlit 1.50 AppTest cannot replay pages containing v2 custom components.",
    )
    def test_summary_page_accepts_optional_prompt_guidance(self) -> None:
        app = AppTest.from_file(
            APP_ROOT / "pages" / "2_文章摘要.py",
            default_timeout=10,
        ).run()
        prompt_input = next(
            area for area in app.text_area if area.label == "补充要求（可选）"
        )
        prompt_input.set_value("重点解释数据变化。保留全部行动建议。").run()

        self.assertEqual(prompt_input.value, "重点解释数据变化。保留全部行动建议。")
        self.assertEqual(list(app.exception), [])

    def test_summary_page_keeps_all_source_methods_visible_in_one_control(self) -> None:
        source = (APP_ROOT / "pages" / "2_文章摘要.py").read_text(encoding="utf-8")
        self.assertIn('"paste": "粘贴文字"', source)
        self.assertIn('"upload": "上传文件"', source)
        self.assertIn('"url": "文章网址"', source)
        self.assertIn("max_upload_size=100", source)
        self.assertIn('"重新读取这个文件"', source)
        self.assertIn("auto_article_url_input", source)
        self.assertNotIn('"读取网页正文"', source)

    def test_summary_page_exposes_mobile_first_image_actions(self) -> None:
        source = (APP_ROOT / "pages" / "2_文章摘要.py").read_text(encoding="utf-8")
        self.assertIn('artifact = build_summary_long_image(generated_result.document, "mobile")', source)
        self.assertIn("native_image_share", source)
        self.assertIn("长按图片存储", source)
        self.assertNotIn('"下载 Markdown"', source)
        self.assertNotIn('"发送到 Markdown PDF"', source)
        self.assertNotIn("build_summary_pdf", source)

    def test_summary_page_exposes_local_editor_and_quality_check(self) -> None:
        source = (APP_ROOT / "pages" / "2_文章摘要.py").read_text(encoding="utf-8")
        self.assertIn('"应用修改并重新排版"', source)
        self.assertIn("supplement_numeric_highlights=False", source)
        self.assertIn("lint_summary_document", source)

    def test_summary_choices_precede_the_primary_action(self) -> None:
        source = (APP_ROOT / "pages" / "2_文章摘要.py").read_text(encoding="utf-8")
        self.assertLess(source.index('key="summary_length_choice"'), source.index("generate_clicked = st.button"))

    def test_summary_image_render_avoids_hot_reload_cache_failures(self) -> None:
        source = (APP_ROOT / "pages" / "2_文章摘要.py").read_text(encoding="utf-8")
        function_start = source.index("def build_summary_long_image")
        decorator_window = source[max(0, function_start - 120) : function_start]
        self.assertNotIn("@st.cache_data", decorator_window)
        self.assertIn('LOGGER.exception("Unexpected long-image export failure")', source)
        self.assertIn('LOGGER.exception("Unexpected long-image retry failure")', source)

    def test_download_names_do_not_include_output_mode(self) -> None:
        pdf_source = (APP_ROOT / "streamlit_app.py").read_text(encoding="utf-8")
        summary_source = (APP_ROOT / "pages" / "2_文章摘要.py").read_text(encoding="utf-8")
        self.assertIn(
            'filename = f"{safe_filename(st.session_state.pdf_output_name)}.pdf"',
            pdf_source,
        )
        self.assertNotIn("result.mode}.pdf", pdf_source)
        self.assertIn('file_name=f"{output_name}.summary.png"', summary_source)
        self.assertNotIn(".summary.pdf", summary_source)


if __name__ == "__main__":
    unittest.main()
