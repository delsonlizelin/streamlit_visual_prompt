from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


Severity = Literal["error", "warning", "notice"]


@dataclass(frozen=True)
class PreflightIssue:
    code: str
    severity: Severity
    title: str
    message: str
    line: int | None = None


@dataclass(frozen=True)
class PreflightReport:
    issues: tuple[PreflightIssue, ...]

    @property
    def errors(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    @property
    def warnings(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)

    @property
    def notices(self) -> int:
        return sum(issue.severity == "notice" for issue in self.issues)


def _pipe_columns(line: str) -> int:
    cells = [cell for cell in line.strip().strip("|").split("|")]
    return len(cells) if any(cell.strip() for cell in cells) else 0


def preflight_markdown(source: str) -> PreflightReport:
    """Run fast, deterministic checks before Chromium pagination."""
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    issues: list[PreflightIssue] = []
    headings: list[tuple[int, int]] = []
    fence: tuple[str, int, str] | None = None
    long_urls = 0

    for number, line in enumerate(lines, start=1):
        fence_match = re.match(r"^\s*(```+|~~~+)\s*([^\s`]*)", line)
        if fence_match:
            marker = fence_match.group(1)[0]
            language = fence_match.group(2).lower()
            if fence is None:
                fence = (marker, number, language)
                if language == "mermaid":
                    issues.append(PreflightIssue(
                        "mermaid", "warning", "Mermaid 不会渲染为图表",
                        "当前版本会把 Mermaid 保留为代码块。", number,
                    ))
            elif fence[0] == marker:
                fence = None
            continue
        if fence:
            continue

        heading = re.match(r"^(#{1,6})\s+", line)
        if heading:
            headings.append((number, len(heading.group(1))))

        if re.search(r"<(?!https?://|mailto:)\/?[A-Za-z][^>]*>", line, flags=re.I):
            issues.append(PreflightIssue(
                "raw-html", "warning", "检测到原始 HTML",
                "不在安全白名单中的标签或属性会在生成时移除。", number,
            ))

        if "$$" in line or re.search(r"\\[\[(].*?\\[\])]", line):
            issues.append(PreflightIssue(
                "math", "warning", "检测到公式语法",
                "当前长文模式不排版 LaTeX 公式，建议先转换为普通文本。", number,
            ))

        for image in re.finditer(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+[^)]*)?\)", line):
            alt, target = image.group(1).strip(), image.group(2).strip("<>")
            if not alt:
                issues.append(PreflightIssue(
                    "missing-image-alt", "notice", "图片缺少替代文本",
                    "补充简短说明有助于无障碍阅读和内容追踪。", number,
                ))
            if not re.match(r"^(?:https://|data:)", target, flags=re.I):
                issues.append(PreflightIssue(
                    "local-image", "warning", "图片地址无法在云端读取",
                    "请改用 HTTPS 图片，或在后续版本使用多文件上传。", number,
                ))

        if re.search(r"\]\(\s*(?:javascript|vbscript|file):", line, flags=re.I):
            issues.append(PreflightIssue(
                "unsafe-link", "error", "链接协议不安全",
                "该链接会被安全过滤器移除。", number,
            ))

        long_urls += sum(
            len(match.group(0).rstrip(".,;:!?)]}")) >= 46
            for match in re.finditer(r"https?://[^\s<>]+", line, flags=re.I)
        )

        if re.match(r"^\s*\|?.+\|.+\|?\s*$", line) and _pipe_columns(line) > 6:
            issues.append(PreflightIssue(
                "wide-table", "warning", "表格列数较多",
                "超过 6 列的表格在手机和平板页面上可能过窄。", number,
            ))

    if fence:
        issues.append(PreflightIssue(
            "unclosed-fence", "error", "代码围栏未闭合",
            "从这里开始的其余正文可能全部被当作代码。", fence[1],
        ))

    h1_lines = [line for line, level in headings if level == 1]
    if not h1_lines:
        issues.append(PreflightIssue(
            "missing-h1", "warning", "缺少一级标题",
            "将使用“未命名长文”作为封面标题。",
        ))
    elif len(h1_lines) > 1:
        issues.append(PreflightIssue(
            "multiple-h1", "warning", "存在多个一级标题",
            "只有第一个一级标题会作为封面标题。", h1_lines[1],
        ))

    previous_level: int | None = None
    for line, level in headings:
        if previous_level is not None and level > previous_level + 1:
            issues.append(PreflightIssue(
                "heading-jump", "notice", "标题层级发生跳跃",
                f"标题从 H{previous_level} 跳到了 H{level}。", line,
            ))
        previous_level = level

    if long_urls:
        issues.append(PreflightIssue(
            "long-url", "notice", f"检测到 {long_urls} 个长链接",
            "生成时会使用安全折行，并在窄页面上采用更克制的链接样式。",
        ))

    # Repeated line-level warnings are useful only once in the compact UI.
    compact: list[PreflightIssue] = []
    seen: set[str] = set()
    for issue in issues:
        if issue.code in seen and issue.code in {"raw-html", "math", "wide-table"}:
            continue
        compact.append(issue)
        seen.add(issue.code)
    return PreflightReport(tuple(compact))
