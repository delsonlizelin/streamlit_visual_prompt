from __future__ import annotations

import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


APP_ROOT = Path(__file__).resolve().parent.parent


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

    def test_summary_page_exposes_current_prompt_copy_button(self) -> None:
        source = (APP_ROOT / "pages" / "2_文章摘要.py").read_text(encoding="utf-8")
        self.assertIn('"复制当前模式提示词"', source)
        self.assertIn("build_prompt_template", source)

    def test_summary_page_exposes_four_distinct_summary_modes(self) -> None:
        app = AppTest.from_file(
            APP_ROOT / "pages" / "2_文章摘要.py",
            default_timeout=10,
        ).run()
        mode_control = next(radio for radio in app.radio if radio.label == "摘要方式")
        self.assertEqual(
            mode_control.options,
            ["快速概览", "核心摘要（推荐）", "按章节梳理", "零基础讲解"],
        )
        mode_control.set_value("零基础讲解").run()
        self.assertEqual(mode_control.value, "零基础讲解")
        self.assertEqual(list(app.exception), [])

    def test_summary_page_keeps_all_source_methods_visible_in_one_control(self) -> None:
        source = (APP_ROOT / "pages" / "2_文章摘要.py").read_text(encoding="utf-8")
        self.assertIn('"paste": "粘贴文字"', source)
        self.assertIn('"upload": "上传文件"', source)
        self.assertIn('"url": "文章网址"', source)
        self.assertIn('"重新读取这个文件"', source)

    def test_download_names_do_not_include_output_mode(self) -> None:
        pdf_source = (APP_ROOT / "streamlit_app.py").read_text(encoding="utf-8")
        summary_source = (APP_ROOT / "pages" / "2_文章摘要.py").read_text(encoding="utf-8")
        self.assertIn(
            'filename = f"{safe_filename(st.session_state.pdf_output_name)}.pdf"',
            pdf_source,
        )
        self.assertNotIn("result.mode}.pdf", pdf_source)
        self.assertIn('file_name=f"{output_name}.summary.pdf"', summary_source)
        self.assertIn('file_name=f"{output_name}.summary.png"', summary_source)
        self.assertNotIn("summary.{export['mode']}", summary_source)


if __name__ == "__main__":
    unittest.main()
