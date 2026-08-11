from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from longread_pdf import render_markdown


SOURCE = (PROJECT_DIR / "tests" / "fixtures" / "longread_regression.md").read_text(encoding="utf-8")


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
