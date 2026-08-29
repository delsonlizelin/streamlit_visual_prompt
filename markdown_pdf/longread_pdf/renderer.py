from __future__ import annotations

import html as html_lib
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import bleach
import markdown as markdown_lib
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright
from summarizer.deepseek import SummaryDocument, SummaryItem


ASSET_DIR = Path(__file__).resolve().parent / "assets"
PROJECT_DIR = ASSET_DIR.parent.parent
SUMMARY_FONT_PATH = PROJECT_DIR / "static" / "fonts" / "NotoSansSC-VariableFont_wght.ttf"
ALLOWED_MODES = {"desktop", "tablet", "mobile"}
MODE_PROFILES = {
    "desktop": {
        "page_size": "A4",
        "page_width": "210mm",
        "page_height": "297mm",
        "page_margin": "24mm 25mm 23mm",
        "toc_margin": "25mm 28mm 23mm",
        "bottom_left": "counter(page)",
        "bottom_center": "none",
    },
    "mobile": {
        "page_size": "108mm 192mm",
        "page_width": "108mm",
        "page_height": "192mm",
        "page_margin": "12mm 10mm 11mm",
        "toc_margin": "12mm 10mm 11mm",
        "bottom_left": "none",
        "bottom_center": "counter(page)",
    },
    "tablet": {
        "page_size": "132mm 201mm",
        "page_width": "132mm",
        "page_height": "201mm",
        "page_margin": "15mm 14mm 13mm",
        "toc_margin": "15mm 14mm 13mm",
        "bottom_left": "none",
        "bottom_center": "counter(page)",
    },
}
LONG_IMAGE_PROFILES = {
    "tablet": {"viewport_width": 500, "device_scale_factor": 3},
    "mobile": {"viewport_width": 409, "device_scale_factor": 3},
}
MAX_LONG_IMAGE_CSS_HEIGHT = 10_500

ALLOWED_TAGS = {
    "p", "h2", "h3", "h4", "h5", "h6", "blockquote", "strong", "em",
    "ul", "ol", "li", "a", "img", "hr", "br", "pre", "code", "table",
    "thead", "tbody", "tr", "th", "td", "figure", "figcaption",
}
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "class"],
    "img": ["src", "alt", "title", "width", "height"],
    "th": ["colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
}
ENCLOSING_PAIRS = {
    "“": "”", "‘": "’", "「": "」", "『": "』", "（": "）",
    "(": ")", "[": "]", "{": "}", "《": "》",
}


class RenderError(RuntimeError):
    """A user-facing rendering error."""


@dataclass(frozen=True)
class DocumentBuild:
    html: str
    title: str
    running_title: str
    sections: int
    normalized_emphasis_lines: int


@dataclass(frozen=True)
class RenderResult:
    pdf: bytes
    title: str
    running_title: str
    mode: str
    pages: int
    sections: int
    normalized_emphasis_lines: int
    blank_pages: tuple[int, ...]
    overflows: tuple[dict[str, Any], ...]
    milliseconds: int


@dataclass(frozen=True)
class LongImageResult:
    png: bytes
    title: str
    mode: str
    width: int
    height: int
    milliseconds: int


def _split_terminal_punctuation(value: str) -> tuple[str, str]:
    match = re.search(r"([，。！？；：、,.!?;:]+|…{1,2})$", value)
    if not match:
        return value, ""
    return value[: match.start()], match.group(0)


def _normalize_delimited(content: str, marker: str) -> str:
    leading = re.match(r"^\s*", content).group(0)
    trailing = re.search(r"\s*$", content).group(0)
    end = len(content) - len(trailing) if trailing else len(content)
    core = content[len(leading):end]
    if not core:
        return f"{marker}{content}{marker}"

    prefix = suffix = ""
    expected_close = ENCLOSING_PAIRS.get(core[0])
    if expected_close and core.endswith(expected_close):
        prefix, suffix = core[0], expected_close
        core = core[1:-1]

    core, punctuation = _split_terminal_punctuation(core)
    if not core:
        return f"{marker}{content}{marker}"
    return f"{leading}{prefix}{marker}{core}{marker}{suffix}{punctuation}{trailing}"


def _normalize_inline(segment: str) -> str:
    patterns = (
        (re.compile(r"\*\*([^*\n]+?)\*\*"), "**"),
        (re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)"), "*"),
        (re.compile(r"__([^_\n]+?)__"), "__"),
        (re.compile(r"(?<!_)_([^_\n]+?)_(?!_)"), "_"),
    )
    for pattern, marker in patterns:
        segment = pattern.sub(lambda match: _normalize_delimited(match.group(1), marker), segment)
    return segment


def normalize_markdown(source: str) -> tuple[str, int]:
    before = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    after: list[str] = []
    fence: str | None = None
    for line in before:
        fence_match = re.match(r"^\s*(```+|~~~+)", line)
        if fence_match:
            fence_char = fence_match.group(1)[0]
            fence = fence_char if fence is None else (None if fence == fence_char else fence)
            after.append(line)
            continue
        if fence:
            after.append(line)
            continue
        parts = re.split(r"(`+[^`]*?`+)", line)
        after.append("".join(part if index % 2 else _normalize_inline(part) for index, part in enumerate(parts)))
    return "\n".join(after), sum(left != right for left, right in zip(before, after))


def _parser_compatible(source: str) -> str:
    lines = source.split("\n")
    converted: list[str] = []
    fence: str | None = None
    for line in lines:
        fence_match = re.match(r"^\s*(```+|~~~+)", line)
        if fence_match:
            fence_char = fence_match.group(1)[0]
            fence = fence_char if fence is None else (None if fence == fence_char else fence)
            converted.append(line)
            continue
        if fence:
            converted.append(line)
            continue
        parts = re.split(r"(`+[^`]*?`+)", line)
        for index in range(0, len(parts), 2):
            parts[index] = re.sub(r"\*\*([^*\n]+?)\*\*", r"<strong>\1</strong>", parts[index])
            parts[index] = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", parts[index])
        converted.append("".join(parts))
    return "\n".join(converted)


def _extract_front(
    source: str,
    fallback_title: str = "未命名长文",
) -> tuple[str, list[str], str, bool]:
    lines = source.split("\n")
    title_index = next(
        (index for index, line in enumerate(lines) if re.match(r"^#\s+\S", line)),
        -1,
    )
    has_explicit_title = title_index >= 0
    title = (
        re.sub(r"^#\s+", "", lines[title_index]).strip()
        if has_explicit_title
        else fallback_title
    )
    body = lines.copy()
    cursor = 0
    if has_explicit_title:
        body.pop(title_index)
        cursor = title_index
    else:
        # A bare `#` is not a title and should not leave an empty heading in the body.
        body = [line for line in body if not re.match(r"^#\s*$", line)]
    while cursor < len(body) and not body[cursor].strip():
        cursor += 1
    deck_start = cursor
    deck: list[str] = []
    if has_explicit_title:
        while cursor < len(body) and re.match(r"^>\s?", body[cursor]):
            deck.append(re.sub(r"^>\s?", "", body[cursor]).rstrip().strip())
            cursor += 1
        if deck:
            del body[deck_start:cursor]
    return title, deck, "\n".join(body), has_explicit_title


def _plain_text(value: str) -> str:
    return html_lib.unescape(bleach.clean(value, tags=set(), strip=True)).strip()


def _render_article(source: str) -> tuple[str, list[tuple[str, str]]]:
    rendered = markdown_lib.markdown(
        _parser_compatible(source),
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )
    rendered = bleach.clean(
        rendered,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols={"http", "https", "mailto", "data"},
        strip=True,
    )

    toc: list[tuple[str, str]] = []
    h2_index = 0
    h3_index = 0

    def heading(match: re.Match[str]) -> str:
        nonlocal h2_index, h3_index
        level, inner = match.group(1), match.group(2)
        if level == "2":
            h2_index += 1
            h3_index = 0
            identifier = f"section-{h2_index:02d}"
            toc.append((identifier, _plain_text(inner)))
            return f'<h2 id="{identifier}">{inner}</h2>'
        h3_index += 1
        identifier = f"section-{h2_index:02d}-{h3_index:02d}"
        return f'<h3 id="{identifier}">{inner}</h3>'

    rendered = re.sub(r"<h([23])>([\s\S]*?)</h\1>", heading, rendered)

    def link_class(match: re.Match[str]) -> str:
        attributes, inner = match.group(1), match.group(2)
        href_match = re.search(r'\bhref="([^"]*)"', attributes)
        if not href_match:
            return match.group(0)
        href = html_lib.unescape(href_match.group(1)).strip()
        visible = _plain_text(inner)
        is_url = bool(re.match(r"^(?:https?://|www\.)", visible, flags=re.I))
        is_bare = is_url or visible.rstrip("/") == href.rstrip("/")
        if not is_bare or re.search(r'\bclass="', attributes):
            return match.group(0)
        return f'<a{attributes} class="bare-url">{inner}</a>'

    rendered = re.sub(r"<a([^>]*)>([\s\S]*?)</a>", link_class, rendered)

    def quote_class(match: re.Match[str]) -> str:
        inner = match.group(1)
        class_name = ' class="long-quote"' if len(_plain_text(inner)) > 650 else ""
        return f"<blockquote{class_name}>{inner}</blockquote>"

    return re.sub(r"<blockquote>([\s\S]*?)</blockquote>", quote_class, rendered), toc


def _wrap_summary_sections(article_html: str) -> str:
    """Group generated summary sections into a continuous, card-like reading flow."""
    starts = [match.start() for match in re.finditer(r'<h2\b', article_html)]
    if not starts:
        return f'<section class="summary-lead">{article_html}</section>'

    chunks: list[str] = []
    intro = article_html[: starts[0]].strip()
    if intro:
        chunks.append(f'<section class="summary-lead">{intro}</section>')
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(article_html)
        section = article_html[start:end].strip()
        chunks.append(
            f'<section class="summary-card" data-section="{index + 1}">{section}</section>'
        )
    return "\n".join(chunks)


def _highlight_summary_text(item: SummaryItem) -> str:
    """Escape one item and apply only validated, non-overlapping emphasis spans."""
    ranges: list[tuple[int, int]] = []
    for highlight in sorted(item.highlights, key=len, reverse=True):
        start = item.text.find(highlight)
        if start < 0:
            continue
        end = start + len(highlight)
        if any(start < existing_end and end > existing_start for existing_start, existing_end in ranges):
            continue
        ranges.append((start, end))
    ranges.sort()

    parts: list[str] = []
    cursor = 0
    for start, end in ranges:
        parts.append(html_lib.escape(item.text[cursor:start]))
        parts.append(f"<strong>{html_lib.escape(item.text[start:end])}</strong>")
        cursor = end
    parts.append(html_lib.escape(item.text[cursor:]))
    return "".join(parts)


def _render_structured_summary(document: SummaryDocument) -> str:
    parts: list[str] = []
    if document.lead:
        parts.append(
            '<section class="summary-lead" aria-label="全文结论">'
            f"<p>{html_lib.escape(document.lead)}</p></section>"
        )
    for index, section in enumerate(document.sections, start=1):
        items = "".join(f"<li>{_highlight_summary_text(item)}</li>" for item in section.items)
        parts.append(
            f'<section class="summary-card" data-section="{index}">'
            f"<h2>{html_lib.escape(section.heading)}</h2><ul>{items}</ul></section>"
        )
    return "\n".join(parts)


def _detect_language(source: str) -> str:
    cjk = len(re.findall(r"[\u3400-\u9fff]", source))
    latin = len(re.findall(r"[A-Za-z]", source))
    return "zh-CN" if cjk >= latin * 0.35 else "en"


def _short_running_title(title: str) -> str:
    compact = re.sub(r"\s+", " ", title).strip()
    return compact if len(compact) <= 26 else f"{compact[:25]}…"


def _inline_markdown(value: str) -> str:
    rendered = markdown_lib.markdown(_parser_compatible(value), extensions=["extra"], output_format="html5")
    rendered = bleach.clean(rendered, tags={"p", "strong", "em", "a", "code"}, attributes={"a": ["href", "title"]}, strip=True)
    return re.sub(r"^<p>|</p>$", "", rendered.strip())


def _fill(source: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        source = source.replace("{{" + key + "}}", value)
    return source


def _mode_css(mode: str) -> str:
    profile = MODE_PROFILES[mode]
    return _fill((ASSET_DIR / "longread.css").read_text(encoding="utf-8"), {
        "PAGE_SIZE_CSS": profile["page_size"],
        "PAGE_WIDTH_CSS": profile["page_width"],
        "PAGE_HEIGHT_CSS": profile["page_height"],
        "PAGE_MARGIN_CSS": profile["page_margin"],
        "TOC_MARGIN_CSS": profile["toc_margin"],
        "BOTTOM_LEFT_CONTENT_CSS": profile["bottom_left"],
        "BOTTOM_CENTER_CONTENT_CSS": profile["bottom_center"],
    })


def _summary_font_css() -> str:
    if not SUMMARY_FONT_PATH.is_file():
        return ""
    return (
        '@font-face {'
        'font-family: "Noto Sans SC";'
        f'src: url("{SUMMARY_FONT_PATH.as_uri()}") format("truetype");'
        'font-style: normal;'
        'font-weight: 100 900;'
        'font-display: block;'
        '}'
    )


def _is_allowed_render_url(url: str, html_uri: str) -> bool:
    return (
        url == html_uri
        or url == SUMMARY_FONT_PATH.as_uri()
        or url.startswith(("data:", "https://"))
    )


def build_document(markdown_source: str, mode: str = "desktop") -> DocumentBuild:
    if mode not in ALLOWED_MODES:
        raise RenderError(f"未知模式：{mode}")
    if not markdown_source.strip():
        raise RenderError("Markdown 内容不能为空。")

    normalized, changed_lines = normalize_markdown(markdown_source)
    title, deck, body, has_explicit_title = _extract_front(normalized)
    article_html, toc = _render_article(body)
    running_title = ""
    css = _mode_css(mode)
    deck_html = "\n".join(f"<p>{_inline_markdown(line)}</p>" for line in deck) if deck else "<p>适合专注阅读的长文版本</p>"
    front_parts: list[str] = []
    if has_explicit_title:
        front_parts.append(
            '<section class="cover" aria-label="封面">'
            '<div class="cover-content">'
            f'<h1>{html_lib.escape(title)}</h1>'
            f'<div class="cover-deck">{deck_html}</div>'
            '</div></section>'
        )
        if toc:
            toc_html = "\n".join(
                f'<li><a href="#{identifier}">{html_lib.escape(label)}</a></li>'
                for identifier, label in toc
            )
            front_parts.append(
                '<nav class="toc-page" aria-label="目录">'
                f'<h1>目录</h1><ol class="toc">{toc_html}</ol>'
                '</nav>'
            )
    template = (ASSET_DIR / "template.html").read_text(encoding="utf-8")
    document = _fill(template, {
        "LANG": _detect_language(normalized),
        "BASE_URL": "",
        "MODE": mode,
        "TITLE": html_lib.escape(title),
        "FRONT_MATTER": "\n".join(front_parts),
        "CONTENT": article_html,
        "CSS": css,
    })
    return DocumentBuild(document, title, running_title, len(toc), changed_lines)


def build_summary_document(
    summary_source: str | SummaryDocument,
    mode: str = "tablet",
    *,
    continuous: bool = False,
) -> DocumentBuild:
    if mode not in ALLOWED_MODES:
        raise RenderError(f"未知模式：{mode}")
    if continuous and mode not in LONG_IMAGE_PROFILES:
        raise RenderError("长图只支持平板和手机模式。")
    # Streamlit Cloud can hot-reload ``summarizer.deepseek`` while this module
    # still holds the previous SummaryDocument class object. Branch on the
    # stable primitive type instead of class identity so an equivalent document
    # from the reloaded module is not mistaken for Markdown and sent to .strip().
    if not isinstance(summary_source, str):
        required_fields = ("title", "byline", "lead", "sections", "to_json")
        if not all(hasattr(summary_source, field) for field in required_fields):
            raise RenderError("无法识别结构化摘要，请重新生成摘要后再试。")
        title = summary_source.title
        normalized = summary_source.to_json()
        changed_lines = 0
        article_html = _render_structured_summary(summary_source)
        toc = [(f"section-{index:02d}", section.heading) for index, section in enumerate(summary_source.sections, start=1)]
        summary_meta = (
            f'<p class="summary-meta">{html_lib.escape(summary_source.byline)}</p>'
            if summary_source.byline
            else ""
        )
    else:
        if not summary_source.strip():
            raise RenderError("摘要内容不能为空。")
        normalized, changed_lines = normalize_markdown(summary_source)
        title, _deck, body, _has_explicit_title = _extract_front(
            normalized,
            fallback_title="文章摘要",
        )
        article_html, toc = _render_article(body)
        article_html = _wrap_summary_sections(article_html)
        summary_meta = '<p class="summary-meta">由原文提炼</p>'
    running_title = _short_running_title(title)
    css_parts = [
        _mode_css(mode),
        _summary_font_css(),
        (ASSET_DIR / "summary.css").read_text(encoding="utf-8"),
    ]
    if continuous:
        css_parts.append((ASSET_DIR / "long_image.css").read_text(encoding="utf-8"))

    template = (ASSET_DIR / "summary_template.html").read_text(encoding="utf-8")
    document = _fill(template, {
        "LANG": _detect_language(normalized),
        "BASE_URL": "",
        "MODE": mode,
        "OUTPUT_CLASS": "continuous-output" if continuous else "paged-output",
        "TITLE": html_lib.escape(title),
        "SHORT_TITLE": html_lib.escape(running_title),
        "SUMMARY_META": summary_meta,
        "CONTENT": article_html,
        "CSS": "\n".join(css_parts),
    })
    return DocumentBuild(document, title, running_title, len(toc), changed_lines)


def _chromium_path() -> str | None:
    configured = os.environ.get("CHROMIUM_PATH")
    if configured and Path(configured).is_file():
        return configured
    for command in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        resolved = shutil.which(command)
        if resolved:
            return resolved
    mac_chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    return str(mac_chrome) if mac_chrome.is_file() else None


def _launch_options() -> dict[str, Any]:
    options: dict[str, Any] = {
        "headless": True,
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }
    executable = _chromium_path()
    if executable:
        options["executable_path"] = executable
    return options


def _render_paged_document(build: DocumentBuild, *, mode: str) -> RenderResult:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="markdown-pdf-") as temp_dir:
        html_path = Path(temp_dir) / "document.html"
        html_path.write_text(build.html, encoding="utf-8")
        html_uri = html_path.as_uri()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(**_launch_options())
                try:
                    page = browser.new_page()

                    def route_request(route: Any) -> None:
                        url = route.request.url
                        if _is_allowed_render_url(url, html_uri):
                            route.continue_()
                        else:
                            route.abort()

                    page.route("**/*", route_request)
                    page.goto(html_uri, wait_until="load")
                    page.evaluate("() => document.fonts.ready")
                    page.add_script_tag(content=(ASSET_DIR / "paged.polyfill.js").read_text(encoding="utf-8"))
                    page.wait_for_selector(".pagedjs_page", timeout=120_000)

                    last_count = -1
                    stable_checks = 0
                    deadline = time.monotonic() + 120
                    while stable_checks < 5 and time.monotonic() < deadline:
                        page.wait_for_timeout(200)
                        page_count = page.locator(".pagedjs_page").count()
                        stable_checks = stable_checks + 1 if page_count > 0 and page_count == last_count else 0
                        last_count = page_count
                    if stable_checks < 5:
                        raise RenderError("分页未能在两分钟内稳定完成。")

                    qa = page.evaluate(r"""
                        () => {
                          const pages = [...document.querySelectorAll('.pagedjs_page')];
                          const overflows = [];
                          const selector = [
                            'a', 'p', 'li', 'code', 'pre', 'table', 'th', 'td',
                            'figure', 'img', 'svg', 'blockquote'
                          ].join(', ');
                          document.querySelectorAll(`.pagedjs_page_content ${selector}`).forEach((element) => {
                            // Paged.js keeps a fragmented grid box for multi-page TOCs;
                            // its geometry spans fragments even though the visible rows fit.
                            // TOCs are covered by visual regression instead of this article check.
                            if (element.closest('.toc')) return;
                            const content = element.closest('.pagedjs_page_content');
                            const pageElement = element.closest('.pagedjs_page');
                            if (!content || !pageElement) return;
                            const contentRect = content.getBoundingClientRect();
                            const rects = [...element.getClientRects()];
                            let amount = 0;
                            rects.forEach((rect) => {
                              amount = Math.max(
                                amount,
                                rect.right - contentRect.right,
                                contentRect.left - rect.left
                              );
                            });
                            const scrollContainers = 'pre, table, figure, img, svg, blockquote';
                            if (element.matches(scrollContainers) && element.clientWidth > 0) {
                              amount = Math.max(amount, element.scrollWidth - element.clientWidth);
                            }
                            if (amount > 2) {
                              overflows.push({
                                page: pages.indexOf(pageElement) + 1,
                                tag: element.tagName.toLowerCase(),
                                overflow: Math.round(amount),
                                text: (element.textContent || element.getAttribute('alt') || '')
                                  .replace(/\s+/g, ' ').slice(0, 80),
                              });
                            }
                          });
                          return {
                            pages: pages.length,
                            blankPages: pages.map((item, index) => ({ index: index + 1, text: (item.innerText || '').trim() }))
                              .filter((item) => item.text.length < 8).map((item) => item.index),
                            overflows,
                          };
                        }
                    """)
                    pdf = page.pdf(print_background=True, prefer_css_page_size=True, tagged=True)
                finally:
                    browser.close()
        except RenderError:
            raise
        except PlaywrightError as error:
            raise RenderError(
                "无法启动 Chromium。请确认本机安装了 Chrome，或在 Streamlit Cloud 的 packages.txt 中安装 chromium。"
            ) from error

    return RenderResult(
        pdf=pdf,
        title=build.title,
        running_title=build.running_title,
        mode=mode,
        pages=int(qa["pages"]),
        sections=build.sections,
        normalized_emphasis_lines=build.normalized_emphasis_lines,
        blank_pages=tuple(qa["blankPages"]),
        overflows=tuple(qa["overflows"]),
        milliseconds=round((time.monotonic() - started) * 1000),
    )


def render_markdown(markdown_source: str, mode: str = "desktop") -> RenderResult:
    build = build_document(markdown_source, mode=mode)
    return _render_paged_document(build, mode=mode)


def render_summary_pdf(summary_source: str | SummaryDocument, mode: str = "tablet") -> RenderResult:
    build = build_summary_document(summary_source, mode=mode)
    return _render_paged_document(build, mode=mode)


def render_summary_long_image(summary_source: str | SummaryDocument, mode: str = "mobile") -> LongImageResult:
    if mode not in LONG_IMAGE_PROFILES:
        raise RenderError("长图只支持平板和手机模式。")

    build = build_summary_document(summary_source, mode=mode, continuous=True)
    profile = LONG_IMAGE_PROFILES[mode]
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="markdown-image-") as temp_dir:
        html_path = Path(temp_dir) / "summary.html"
        html_path.write_text(build.html, encoding="utf-8")
        html_uri = html_path.as_uri()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(**_launch_options())
                try:
                    page = browser.new_page(
                        viewport={"width": profile["viewport_width"], "height": 900},
                        device_scale_factor=profile["device_scale_factor"],
                    )

                    def route_request(route: Any) -> None:
                        url = route.request.url
                        if _is_allowed_render_url(url, html_uri):
                            route.continue_()
                        else:
                            route.abort()

                    page.route("**/*", route_request)
                    page.goto(html_uri, wait_until="load")
                    page.evaluate("() => document.fonts.ready")
                    page.evaluate(r"""
                        () => Promise.all([...document.images].map((image) => {
                          if (image.complete) return Promise.resolve();
                          return new Promise((resolve) => {
                            image.addEventListener('load', resolve, { once: true });
                            image.addEventListener('error', resolve, { once: true });
                          });
                        }))
                    """)
                    geometry = page.evaluate(r"""
                        () => ({
                          height: Math.ceil(document.documentElement.scrollHeight),
                          horizontalOverflow: Math.max(
                            0,
                            document.documentElement.scrollWidth - window.innerWidth
                          ),
                        })
                    """)
                    if int(geometry["horizontalOverflow"]) > 2:
                        raise RenderError("长图内容发生横向溢出，请检查摘要中的长链接或复杂内容。")
                    if int(geometry["height"]) > MAX_LONG_IMAGE_CSS_HEIGHT:
                        raise RenderError(
                            "摘要过长，无法稳定导出为单张长图；请缩短原文，"
                            "或改用标准篇幅后重试。"
                        )
                    png = page.locator("body").screenshot(type="png", animations="disabled")
                finally:
                    browser.close()
        except RenderError:
            raise
        except PlaywrightError as error:
            raise RenderError(
                "无法生成长图。请确认本机安装了 Chrome，或在 Streamlit Cloud 的 packages.txt 中安装 chromium。"
            ) from error

    if len(png) < 24 or png[:8] != b"\x89PNG\r\n\x1a\n":
        raise RenderError("Chromium 没有返回有效的 PNG 长图。")
    width = int.from_bytes(png[16:20], "big")
    height = int.from_bytes(png[20:24], "big")
    return LongImageResult(
        png=png,
        title=build.title,
        mode=mode,
        width=width,
        height=height,
        milliseconds=round((time.monotonic() - started) * 1000),
    )
