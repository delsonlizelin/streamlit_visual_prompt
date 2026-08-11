from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from longread_pdf import render_markdown


SOURCE = """# Markdown PDF 冒烟测试
> 中文与 English 都应清晰显示。

## 第一章

这是一段用于验证分页、**强调**和中英文混排的文字。

> 引用应保持克制，并在页面内完整显示。
"""


if __name__ == "__main__":
    output_dir = PROJECT_DIR / ".smoke-output"
    output_dir.mkdir(exist_ok=True)
    for mode in ("desktop", "mobile"):
        result = render_markdown(SOURCE, mode=mode)
        target = output_dir / f"smoke.{mode}.pdf"
        target.write_bytes(result.pdf)
        print(f"{mode}: {result.pages} pages -> {target}")
