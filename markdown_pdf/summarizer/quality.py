from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

from .deepseek import SummaryDocument


QualitySeverity = Literal["warning"]

_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?\s*"
    r"(?:%|％|bp|bps|个百分点|美元|元|万元|亿元|亿美元|万亿美元|"
    r"人|家|个|项|倍|个月|年|月|日)?",
    re.IGNORECASE,
)
_ENUMERATOR_RE = re.compile(
    r"(?:第[一二三四五六七八九十]+|[一二三四五六七八九十]+是|"
    r"(?:首先|其次|再次|最后))"
)
_PDF_PAGE_MARKER_RE = re.compile(r"(?m)^\[第[ \t]*\d+[ \t]*页\][ \t]*$")
# Value matching tolerates rewrites that keep the quantity: "$18,000" vs "1.8万美元",
# "20 million" vs "2000 万", "80,000 chips" vs "8万筹码", "2016" vs "2016年".
_VALUE_RE = re.compile(
    r"(?<![A-Za-z0-9.])(\d[\d,]*(?:\.\d+)?)\s*"
    r"(万亿|亿|万|千|百万|thousand|million|billion|trillion|mn|bn|k\b|K\b)?\s*(%|％)?",
    re.IGNORECASE,
)
_MULTIPLIERS = {
    "万亿": 1e12, "亿": 1e8, "万": 1e4, "千": 1e3, "百万": 1e6,
    "thousand": 1e3, "k": 1e3, "million": 1e6, "mn": 1e6,
    "billion": 1e9, "bn": 1e9, "trillion": 1e12,
}


@dataclass(frozen=True)
class SummaryQualityIssue:
    severity: QualitySeverity
    code: str
    message: str
    section: int | None = None
    item: int | None = None


@dataclass(frozen=True)
class SummaryQualityReport:
    issues: tuple[SummaryQualityIssue, ...]
    checked_items: int

    @property
    def passed(self) -> bool:
        return not self.issues


def _normalize_number(value: str) -> str:
    return (
        re.sub(r"[\s,]", "", value)
        .replace("％", "%")
        .replace("BPS", "bp")
        .replace("bps", "bp")
    )


def extract_numeric_tokens(value: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for match in _NUMBER_RE.finditer(value):
        token = _normalize_number(match.group(0))
        if token and token not in tokens:
            tokens.append(token)
    return tuple(tokens)


def _numeric_values(value: str) -> set[tuple[bool, float]]:
    """Return (is_percent, magnitude) pairs with units and thousands separators resolved."""
    values: set[tuple[bool, float]] = set()
    for match in _VALUE_RE.finditer(value):
        try:
            number = float(match.group(1).replace(",", ""))
        except ValueError:
            continue
        multiplier = _MULTIPLIERS.get((match.group(2) or "").lower(), 1.0)
        values.add((bool(match.group(3)), round(number * multiplier, 6)))
    return values


def _token_supported_by_value(token: str, source_values: set[tuple[bool, float]]) -> bool:
    candidates = _numeric_values(token)
    return bool(candidates) and candidates <= source_values


def _similarity_text(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]+", "", value).lower()


def _looks_compound(value: str) -> bool:
    # A composed sentence with one semicolon is normal prose; a label followed by three or
    # more semicolon-separated members is an unprocessed list.
    colon_list = bool(re.search(r"[：:].+[；;].+[；;].+", value))
    enumerators = len(_ENUMERATOR_RE.findall(value)) >= 3
    return colon_list or enumerators


def lint_summary_document(
    document: SummaryDocument,
    source_text: str | None = None,
) -> SummaryQualityReport:
    """Return conservative, observable warnings without pretending to judge truth."""
    issues: list[SummaryQualityIssue] = []
    all_items: list[tuple[int, int, str]] = []
    highlight_characters = 0
    body_characters = 0

    question_headings = sum(
        section.heading.rstrip().endswith(("?", "？")) for section in document.sections
    )
    if len(document.sections) >= 2 and question_headings > len(document.sections) / 2:
        issues.append(
            SummaryQualityIssue(
                severity="warning",
                code="question-heading-density",
                message="问句分区超过一半，建议确认标题是否机械套用了提问句式。",
            )
        )

    for section_index, section in enumerate(document.sections, start=1):
        if len(section.items) > 16:
            issues.append(
                SummaryQualityIssue(
                    severity="warning",
                    code="large-section",
                    message=f"第 {section_index} 节包含 {len(section.items)} 条，长图阅读可能过密。",
                    section=section_index,
                )
            )
        for item_index, item in enumerate(section.items, start=1):
            all_items.append((section_index, item_index, item.text))
            body_characters += len(item.text)
            highlight_characters += sum(len(value) for value in item.highlights)
            cjk_count = len(re.findall(r"[\u3400-\u9fff]", item.text))
            word_count = len(re.findall(r"\b[\w'-]+\b", item.text))
            if cjk_count > 160 or (cjk_count < 20 and word_count > 100):
                issues.append(
                    SummaryQualityIssue(
                        severity="warning",
                        code="long-item",
                        message=f"第 {section_index} 节第 {item_index} 条较长，手机阅读时可能需要拆成两个原子判断。",
                        section=section_index,
                        item=item_index,
                    )
                )
            if _looks_compound(item.text):
                issues.append(
                    SummaryQualityIssue(
                        severity="warning",
                        code="compound-item",
                        message=f"第 {section_index} 节第 {item_index} 条疑似包含多个独立结论，请核对是否需要在模型侧重写。",
                        section=section_index,
                        item=item_index,
                    )
                )

    if len(all_items) > 80:
        issues.append(
            SummaryQualityIssue(
                severity="warning",
                code="large-document",
                message=f"摘要共 {len(all_items)} 条，单张长图可能过长，建议缩短原文或降低详细程度。",
            )
        )

    if document.lead:
        lead_cjk = len(re.findall(r"[\u3400-\u9fff]", document.lead))
        lead_words = len(re.findall(r"\b[\w'-]+\b", document.lead))
        if lead_cjk > 160 or (lead_cjk < 20 and lead_words > 100):
            issues.append(
                SummaryQualityIssue(
                    severity="warning",
                    code="long-lead",
                    message="导语偏长，会在标题下形成大段文字；请压缩到两三句，把细节移到正文。",
                )
            )

    if document.lead and all_items:
        lead_text = _similarity_text(document.lead)
        first_item_text = _similarity_text(all_items[0][2])
        if len(lead_text) >= 12 and SequenceMatcher(None, lead_text, first_item_text).ratio() >= 0.88:
            issues.append(
                SummaryQualityIssue(
                    severity="warning",
                    code="lead-duplicate",
                    message="导语与第一条要点高度相似，请让导语概括全文判断，或删去重复的导语。",
                    section=1,
                    item=1,
                )
            )

    for index, (section_index, item_index, text) in enumerate(all_items):
        left = _similarity_text(text)
        if len(left) < 18:
            continue
        for other_section, other_item, other_text in all_items[index + 1 :]:
            right = _similarity_text(other_text)
            if len(right) < 18:
                continue
            if SequenceMatcher(None, left, right).ratio() >= 0.88:
                issues.append(
                    SummaryQualityIssue(
                        severity="warning",
                        code="duplicate-item",
                        message=(
                            f"第 {section_index} 节第 {item_index} 条与第 {other_section} 节"
                            f"第 {other_item} 条高度相似，建议删除重复信息。"
                        ),
                        section=section_index,
                        item=item_index,
                    )
                )

    if body_characters and highlight_characters / body_characters > 0.12:
        issues.append(
            SummaryQualityIssue(
                severity="warning",
                code="highlight-density",
                message="重点文字超过正文的 12%，橙色强调可能开始失去区分度。",
            )
        )

    if source_text:
        # PDF extraction inserts navigation markers; they are not source facts.
        clean_source = _PDF_PAGE_MARKER_RE.sub("", source_text)
        source_numbers = set(extract_numeric_tokens(clean_source))
        source_values = _numeric_values(clean_source)
        summary_text = "\n".join(
            [document.title, document.byline or "", document.lead or ""]
            + [
                value
                for section in document.sections
                for value in (section.heading, *(item.text for item in section.items))
            ]
        )
        # Re-read each summary number with its multiplier ("1.8万") so value matching sees
        # the quantity, not the bare digits that the literal token regex captured.
        summary_numbers = set(extract_numeric_tokens(summary_text))
        summary_quantities = {
            match.group(0).strip(): match for match in _VALUE_RE.finditer(summary_text)
        }
        unsupported = sorted(
            token
            for token in summary_numbers - source_numbers
            if not any(
                _token_supported_by_value(quantity, source_values)
                for quantity, match in summary_quantities.items()
                if _normalize_number(match.group(1)) == re.sub(r"[^\d.]", "", token)
            )
        )
        if unsupported:
            preview = "、".join(unsupported[:6])
            suffix = "等" if len(unsupported) > 6 else ""
            issues.append(
                SummaryQualityIssue(
                    severity="warning",
                    code="unsupported-number",
                    message=(
                        f"摘要中的数字 {preview}{suffix} 在原文中找不到相同写法或相同数值，"
                        "请核对是否被改写或误写。"
                    ),
                )
            )

    return SummaryQualityReport(issues=tuple(issues), checked_items=len(all_items))
