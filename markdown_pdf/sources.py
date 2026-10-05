"""One source layer: pasted text, uploaded files, web/WeChat URLs and YouTube URLs.

Every path returns a `SourceDocument` whose `material` tells the summarizer what
kind of text it is reading (article, document or transcript) and where it came from.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Literal
from urllib.parse import urlsplit

from input_documents import InputDocumentError, extract_uploaded_document, filename_stem
from url_documents import UrlDocumentError, fetch_url_document, normalize_public_url

Kind = Literal["article", "document", "transcript"]
Origin = Literal["paste", "upload", "web", "wechat", "youtube", "bilibili"]
UrlType = Literal["youtube", "bilibili", "web"]

KIND_LABELS: dict[str, str] = {
    "article": "文章",
    "document": "文档",
    "transcript": "视频或音频字幕",
}
BILIBILI_HOSTS = ("bilibili.com", "b23.tv")
_TIMESTAMP_LINE_RE = re.compile(r"^\s*\[?\(?\d{1,2}:\d{2}(?::\d{2})?\]?\)?\s")


@dataclass(frozen=True)
class Material:
    kind: Kind
    origin: Origin
    language: str | None = None
    asr: bool = False
    speakers_labelled: bool = False
    duration_seconds: int | None = None
    author: str | None = None


@dataclass(frozen=True)
class SourceDocument:
    text: str
    title: str
    output_name: str
    material: Material
    characters: int
    url: str | None = None
    site: str | None = None
    pages: int = 0
    text_pages: int = 0
    notices: tuple[str, ...] = field(default_factory=tuple)


class SourceError(RuntimeError):
    """A user-facing source failure: `str(error)` says what happened, `hint` what to do."""

    def __init__(self, message: str, *, code: str = "source-failed", hint: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.hint = hint


def detect_language(text: str) -> str | None:
    sample = text[:20_000]
    cjk = len(re.findall(r"[㐀-鿿]", sample))
    latin = len(re.findall(r"[A-Za-z]", sample))
    if cjk + latin < 20:
        return None
    # One CJK character carries roughly as much text as a short Latin word.
    return "zh" if cjk * 4 >= latin else "en"


def looks_like_transcript(text: str) -> bool:
    """Timestamped lines, or many short unpunctuated caption fragments without headings."""
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 8:
        return False
    timestamped = sum(bool(_TIMESTAMP_LINE_RE.match(line)) for line in lines)
    if timestamped >= 5 and timestamped >= len(lines) * 0.3:
        return True
    headings = sum(line.lstrip().startswith("#") for line in lines)
    short = sum(len(line.strip()) <= 60 for line in lines)
    unpunctuated = sum(not re.search(r"[.!?。！？]$", line.strip()) for line in lines)
    return (
        len(lines) >= 40
        and headings <= 1
        and short >= len(lines) * 0.8
        and unpunctuated >= len(lines) * 0.5
    )


def material_task_config(material: Material | None) -> dict[str, Any] | None:
    """The small JSON object sent as task_config.material (unset fields omitted)."""
    if material is None:
        return None
    data = asdict(material)
    if material.kind != "transcript":
        data.pop("asr")
        data.pop("speakers_labelled")
    return {key: value for key, value in data.items() if value not in (None, "")}


def suggested_language(material: Material | None) -> Literal["source", "zh"]:
    """Chinese readers: non-Chinese transcripts default to Simplified Chinese summaries."""
    if material and material.kind == "transcript" and material.language not in (None, "zh"):
        return "zh"
    return "source"


def classify_url(value: str) -> UrlType:
    candidate = value.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    host = (urlsplit(candidate).hostname or "").lower().rstrip(".")
    from youtube_documents import is_youtube_host

    if is_youtube_host(host):
        return "youtube"
    if any(host == domain or host.endswith(f".{domain}") for domain in BILIBILI_HOSTS):
        return "bilibili"
    return "web"


def _heading_title(text: str) -> str | None:
    match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    return match.group(1).strip() if match else None


def _safe_name(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", value).strip(" ._")
    return (cleaned or "summary")[:100]


def load_text(text: str) -> SourceDocument:
    transcript = looks_like_transcript(text)
    title = _heading_title(text) or "summary"
    return SourceDocument(
        text=text,
        title=title,
        output_name=_safe_name(title),
        material=Material(
            kind="transcript" if transcript else "article",
            origin="paste",
            language=detect_language(text),
            asr=transcript,
        ),
        characters=len(text),
        notices=("看起来是字幕或转写稿",) if transcript else (),
    )


def load_upload(filename: str, data: bytes) -> SourceDocument:
    try:
        document = extract_uploaded_document(filename, data)
    except InputDocumentError as error:
        raise SourceError(str(error), code="upload-failed") from error
    transcript = document.kind != "PDF" and looks_like_transcript(document.text)
    kind: Kind = "transcript" if transcript else ("document" if document.kind == "PDF" else "article")
    return SourceDocument(
        text=document.text,
        title=_heading_title(document.text) or document.stem,
        output_name=document.stem,
        material=Material(
            kind=kind,
            origin="upload",
            language=detect_language(document.text),
            asr=transcript,
        ),
        characters=len(document.text),
        pages=document.pages,
        text_pages=document.text_pages,
        notices=("看起来是字幕或转写稿",) if transcript else (),
    )


def load_url(
    value: str,
    *,
    timeout: int = 20,
    youtube_enabled: bool = False,
    youtube_proxy_url: str | None = None,
) -> SourceDocument:
    try:
        url_type = classify_url(value)
        if url_type == "web":
            normalize_public_url(value)  # SSRF guard before any request
    except UrlDocumentError as error:
        raise SourceError(str(error), code="invalid-url") from error

    if url_type == "bilibili":
        raise SourceError(
            "暂不支持 Bilibili 网址。",
            code="bilibili-unsupported",
            hint="搬运视频可改用 YouTube 原链接，或把字幕文本粘贴到“粘贴文字”。",
        )
    if url_type == "youtube":
        return _load_youtube(value, timeout=timeout, enabled=youtube_enabled, proxy_url=youtube_proxy_url)

    try:
        document = fetch_url_document(value, timeout=timeout)
    except UrlDocumentError as error:
        raise SourceError(str(error), code="web-failed") from error
    host = (urlsplit(document.url).hostname or "").lower()
    return SourceDocument(
        text=document.text,
        title=document.title,
        output_name=_safe_name(document.title),
        material=Material(
            kind="article",
            origin="wechat" if host.endswith("mp.weixin.qq.com") else "web",
            language=detect_language(document.text),
        ),
        characters=document.characters,
        url=document.url,
        site=document.site,
    )


def _load_youtube(value: str, *, timeout: int, enabled: bool, proxy_url: str | None) -> SourceDocument:
    if not enabled:
        raise SourceError(
            "YouTube 字幕只在本机运行时读取。",
            code="youtube-local-only",
            hint="云端服务器常被 YouTube 拦截。可在 YouTube 打开“显示字幕记录”复制后粘贴，或在本机运行。",
        )
    from youtube_documents import YouTubeDocumentError, YouTubeSettings, fetch_youtube_transcript, language_label

    try:
        video = fetch_youtube_transcript(
            value, settings=YouTubeSettings(proxy_url=proxy_url), timeout=timeout
        )
    except YouTubeDocumentError as error:
        raise SourceError(str(error), code=error.code, hint=error.hint) from error
    language = video.language.split("-")[0] or None
    return SourceDocument(
        text=video.text,
        title=video.title,
        output_name=_safe_name(video.title),
        material=Material(
            kind="transcript",
            origin="youtube",
            language=language,
            asr=video.generated,
            speakers_labelled=False,
            duration_seconds=video.duration_seconds,
            author=video.channel,
        ),
        characters=len(video.text),
        url=video.url,
        site=f"YouTube · {video.channel}" if video.channel else "YouTube",
        notices=(language_label(video.language, generated=video.generated), "无说话人标注"),
    )
