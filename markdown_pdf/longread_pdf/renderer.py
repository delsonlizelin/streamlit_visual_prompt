from __future__ import annotations

import html as html_lib
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import bleach
import markdown as markdown_lib
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


ASSET_DIR = Path(__file__).resolve().parent / "assets"
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


def _extract_front(source: str, fallback_title: str = "未命名长文") -> tuple[str, list[str], str]:
    lines = source.split("\n")
    title_index = next((index for index, line in enumerate(lines) if re.match(r"^#\s+", line)), -1)
    title = re.sub(r"^#\s+", "", lines[title_index]).strip() if title_index >= 0 else fallback_title
    body = lines.copy()
    cursor = 0
    if title_index >= 0:
        body.pop(title_index)
        cursor = title_index
    while cursor < len(body) and not body[cursor].strip():
        cursor += 1
    deck_start = cursor
    deck: list[str] = []
    while cursor < len(body) and re.match(r"^>\s?", body[cursor]):
        deck.append(re.sub(r"^>\s?", "", body[cursor]).rstrip().strip())
        cursor += 1
    if deck:
        del body[deck_start:cursor]
    return title, deck, "\n".join(body)


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


def _detect_language(source: str) -> str:
    cjk = len(re.findall(r"[\u3400-\u9fff]", source))
    latin = len(re.findall(r"[A-Za-z]", source))
    return "zh-CN" if cjk >= latin * 0.35 else "en"


def _short_running_title(title: str) -> str:
    compact = re.sub(r"\s+", " ", title).strip()
    return compact if len(compact) <= 26 else f"{compact[:25]}…"


def _css_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", " ").replace("\n", " ")


def _inline_markdown(value: str) -> str:
    rendered = markdown_lib.markdown(_parser_compatible(value), extensions=["extra"], output_format="html5")
    rendered = bleach.clean(rendered, tags={"p", "strong", "em", "a", "code"}, attributes={"a": ["href", "title"]}, strip=True)
    return re.sub(r"^<p>|</p>$", "", rendered.strip())


def _fill(source: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        source = source.replace("{{" + key + "}}", value)
    return source


def build_document(markdown_source: str, mode: str = "desktop", short_title: str = "") -> DocumentBuild:
    if mode not in ALLOWED_MODES:
        raise RenderError(f"未知模式：{mode}")
    if not markdown_source.strip():
        raise RenderError("Markdown 内容不能为空。")

    normalized, changed_lines = normalize_markdown(markdown_source)
    title, deck, body = _extract_front(normalized)
    article_html, toc = _render_article(body)
    running_title = short_title.strip() or _short_running_title(title)
    profile = MODE_PROFILES[mode]

    css = _fill((ASSET_DIR / "longread.css").read_text(encoding="utf-8"), {
        "PAGE_SIZE_CSS": profile["page_size"],
        "PAGE_WIDTH_CSS": profile["page_width"],
        "PAGE_HEIGHT_CSS": profile["page_height"],
        "PAGE_MARGIN_CSS": profile["page_margin"],
        "TOC_MARGIN_CSS": profile["toc_margin"],
        "RUNNING_HEADER_CONTENT_CSS": f'"{_css_string(running_title)}"' if mode == "desktop" else "none",
        "BOTTOM_LEFT_CONTENT_CSS": profile["bottom_left"],
        "BOTTOM_CENTER_CONTENT_CSS": profile["bottom_center"],
    })
    deck_html = "\n".join(f"<p>{_inline_markdown(line)}</p>" for line in deck) if deck else "<p>适合专注阅读的长文版本</p>"
    toc_html = "\n".join(
        f'<li><a href="#{identifier}">{html_lib.escape(label)}</a></li>' for identifier, label in toc
    )
    template = (ASSET_DIR / "template.html").read_text(encoding="utf-8")
    document = _fill(template, {
        "LANG": _detect_language(normalized),
        "BASE_URL": "",
        "MODE": mode,
        "TITLE": html_lib.escape(title),
        "SHORT_TITLE": html_lib.escape(running_title),
        "DATE": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y年%-m月%-d日"),
        "DECK": deck_html,
        "TOC": toc_html,
        "CONTENT": article_html,
        "CSS": css,
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


def render_markdown(markdown_source: str, mode: str = "desktop", short_title: str = "") -> RenderResult:
    build = build_document(markdown_source, mode=mode, short_title=short_title)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="markdown-pdf-") as temp_dir:
        html_path = Path(temp_dir) / "document.html"
        html_path.write_text(build.html, encoding="utf-8")
        html_uri = html_path.as_uri()
        try:
            with sync_playwright() as playwright:
                launch_options: dict[str, Any] = {
                    "headless": True,
                    "args": ["--no-sandbox", "--disable-dev-shm-usage"],
                }
                executable = _chromium_path()
                if executable:
                    launch_options["executable_path"] = executable
                browser = playwright.chromium.launch(**launch_options)
                try:
                    page = browser.new_page()

                    def route_request(route: Any) -> None:
                        url = route.request.url
                        if url == html_uri or url.startswith(("data:", "https://")):
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
