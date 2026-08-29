from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from longread_pdf import render_markdown


SOURCE = (PROJECT_DIR / "tests" / "fixtures" / "longread_regression.md").read_text(encoding="utf-8")
UNTITLED_SOURCE = """> 没有一级标题时，这段引用也应该保留在第一页正文里。

没有一级标题时，这一段应该直接出现在第一页。

## 正文小节

这是用于验证无标题 fallback 的第二段正文。
"""


if __name__ == "__main__":
    output_dir = PROJECT_DIR / ".smoke-output"
    output_dir.mkdir(exist_ok=True)
    for mode in ("desktop", "tablet", "mobile"):
        result = render_markdown(SOURCE, mode=mode)
        target = output_dir / f"smoke.{mode}.pdf"
        target.write_bytes(result.pdf)
        print(
            f"{mode}: {result.pages} pages, "
            f"{len(result.overflows)} overflows, {len(result.blank_pages)} blank pages -> {target}"
        )
        if result.overflows or result.blank_pages:
            raise SystemExit(f"{mode} failed layout QA")

    untitled = render_markdown(UNTITLED_SOURCE, mode="desktop")
    untitled_target = output_dir / "smoke.untitled.pdf"
    untitled_target.write_bytes(untitled.pdf)
    print(
        f"untitled: {untitled.pages} pages, "
        f"{len(untitled.blank_pages)} blank pages -> {untitled_target}"
    )
    if untitled.pages != 1 or untitled.blank_pages or untitled.overflows:
        raise SystemExit("untitled markdown did not start directly with body content")
