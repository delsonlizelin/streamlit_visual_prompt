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


if __name__ == "__main__":
    unittest.main()
