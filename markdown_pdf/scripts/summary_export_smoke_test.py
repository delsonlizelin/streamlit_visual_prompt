from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from longread_pdf import render_summary_long_image


SOURCE = """# 一份中英文摘要

## 核心内容

- 项目计划在 2026 年 9 月启动，第一阶段预算为 **120 万元**。
- The pilot covers 3 cities and must not collect personal health records.
- 如果试点准确率低于 95%，团队不会进入第二阶段。

## 结论

原文支持有限范围的试点，但没有承诺全面部署。更多信息见[项目说明](https://example.com/project/overview)。
"""


if __name__ == "__main__":
    output_dir = PROJECT_DIR / ".smoke-output"
    output_dir.mkdir(exist_ok=True)

    for mode in ("tablet", "mobile"):
        result = render_summary_long_image(SOURCE, mode=mode)
        target = output_dir / f"summary.{mode}.png"
        target.write_bytes(result.png)
        print(f"image {mode}: {result.width}×{result.height}px -> {target}")
        expected_width = {"tablet": 1488, "mobile": 1170}[mode]
        minimum_content_height = {"tablet": 900, "mobile": 900}[mode]
        if result.width != expected_width or result.height < minimum_content_height:
            raise SystemExit(f"summary image {mode} has unexpected dimensions")
