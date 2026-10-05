"""Read a YouTube video's captions as an editable, summarizable transcript.

The `youtube-transcript-api` package is imported lazily: it is a local-only
dependency, because YouTube blocks most datacenter IPs (Streamlit Cloud).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Iterable
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import Request, urlopen

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}
PREFERRED_LANGUAGES = ("zh-Hans", "zh-Hant", "zh-CN", "zh-TW", "zh", "en")
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_SOUND_TAG_RE = re.compile(r"\[(?:music|applause|laughter|音乐|掌声|笑声)\]", re.IGNORECASE)
_LANGUAGE_NAMES = {
    "en": "英文",
    "zh": "中文",
    "zh-Hans": "简体中文",
    "zh-CN": "简体中文",
    "zh-Hant": "繁体中文",
    "zh-TW": "繁体中文",
    "ja": "日文",
    "ko": "韩文",
    "fr": "法文",
    "de": "德文",
    "es": "西班牙文",
}


class YouTubeDocumentError(RuntimeError):
    """A user-facing failure with a short next step."""

    def __init__(self, message: str, *, code: str, hint: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.hint = hint


@dataclass(frozen=True)
class YouTubeSettings:
    proxy_url: str | None = None
    languages: tuple[str, ...] = PREFERRED_LANGUAGES


@dataclass(frozen=True)
class YouTubeTranscript:
    text: str
    title: str
    channel: str | None
    url: str
    video_id: str
    language: str
    generated: bool
    duration_seconds: int


def is_youtube_host(hostname: str | None) -> bool:
    return bool(hostname) and hostname.lower().rstrip(".") in YOUTUBE_HOSTS


def extract_video_id(url: str) -> str | None:
    """Accept watch, youtu.be, shorts, live and embed URLs; ignore playlist-only links."""
    candidate = url.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None
    if not is_youtube_host(parsed.hostname):
        return None
    host = parsed.hostname.lower().rstrip(".")
    segments = [part for part in parsed.path.split("/") if part]
    video_id = None
    if host == "youtu.be":
        video_id = segments[0] if segments else None
    elif segments[:1] == ["watch"]:
        video_id = (parse_qs(parsed.query).get("v") or [None])[0]
    elif len(segments) >= 2 and segments[0] in {"shorts", "live", "embed", "v"}:
        video_id = segments[1]
    return video_id if video_id and _VIDEO_ID_RE.match(video_id) else None


def canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def fetch_video_metadata(video_id: str, *, timeout: int = 10) -> tuple[str, str | None] | None:
    """Return (title, channel) from YouTube's public oEmbed endpoint; None on any failure."""
    endpoint = (
        "https://www.youtube.com/oembed?format=json&url="
        + quote(canonical_url(video_id), safe="")
    )
    try:
        with urlopen(Request(endpoint, headers={"User-Agent": "Mozilla/5.0"}), timeout=timeout) as response:
            data = json.loads(response.read(512 * 1024).decode("utf-8"))
    except Exception:
        return None
    title = str(data.get("title") or "").strip()
    channel = str(data.get("author_name") or "").strip() or None
    return (title, channel) if title else None


def language_label(code: str, *, generated: bool) -> str:
    name = _LANGUAGE_NAMES.get(code) or _LANGUAGE_NAMES.get(code.split("-")[0]) or code
    return f"{name}{'自动字幕' if generated else '字幕'}"


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def _clean_caption(text: str) -> str:
    return re.sub(r"\s+", " ", _SOUND_TAG_RE.sub(" ", text.replace("\n", " "))).strip()


def transcript_to_markdown(
    snippets: Iterable[Any],
    *,
    title: str,
    url: str,
    channel: str | None,
    language: str,
    generated: bool,
    min_paragraph_seconds: float = 45,
    max_paragraph_seconds: float = 75,
) -> tuple[str, int]:
    """Merge caption snippets into timestamped paragraphs; never invent headings."""
    paragraphs: list[str] = []
    current: list[str] = []
    started_at: float | None = None
    duration = 0.0
    cjk = language.startswith(("zh", "ja", "ko"))
    for snippet in snippets:
        text = _clean_caption(str(getattr(snippet, "text", "") or ""))
        start = float(getattr(snippet, "start", 0.0) or 0.0)
        duration = max(duration, start + float(getattr(snippet, "duration", 0.0) or 0.0))
        if not text:
            continue
        if started_at is None:
            started_at = start
        current.append(text)
        elapsed = start - started_at
        sentence_end = bool(re.search(r"[.!?。！？…」』\"]$", text))
        if elapsed >= max_paragraph_seconds or (elapsed >= min_paragraph_seconds and sentence_end):
            joined = ("" if cjk else " ").join(current)
            paragraphs.append(f"[{format_timestamp(started_at)}] {joined}")
            current, started_at = [], None
    if current and started_at is not None:
        joined = ("" if cjk else " ").join(current)
        paragraphs.append(f"[{format_timestamp(started_at)}] {joined}")

    source = f"[YouTube · {channel}]({url})" if channel else f"[YouTube]({url})"
    metadata = " · ".join(
        [f"来源：{source}", f"时长 {format_timestamp(duration)}", language_label(language, generated=generated)]
    )
    return f"# {title}\n\n{metadata}\n\n" + "\n\n".join(paragraphs), int(duration)


_BLOCKED = {"RequestBlocked", "IpBlocked", "PoTokenRequired", "FailedToCreateConsentCookie"}
_NO_CAPTIONS = {"TranscriptsDisabled", "NoTranscriptFound"}
_UNAVAILABLE = {"VideoUnavailable", "VideoUnplayable", "AgeRestricted", "InvalidVideoId"}


def _map_error(error: Exception) -> YouTubeDocumentError:
    names = {cls.__name__ for cls in type(error).__mro__}
    if names & _BLOCKED:
        return YouTubeDocumentError(
            "YouTube 拒绝了这次字幕请求（服务器或代理 IP 常被拦截）。",
            code="youtube-blocked",
            hint="稍后重试、换一个网络，或在 YouTube 打开“显示字幕记录”复制后粘贴。",
        )
    if names & _NO_CAPTIONS:
        return YouTubeDocumentError(
            "这个视频没有可用字幕。",
            code="youtube-no-captions",
            hint="可以把视频的字幕或文字稿粘贴到“粘贴文字”。",
        )
    if names & _UNAVAILABLE:
        return YouTubeDocumentError(
            "视频不可用、受年龄限制或需要登录，无法读取字幕。",
            code="youtube-unavailable",
            hint="请确认视频可以公开观看。",
        )
    return YouTubeDocumentError(
        "无法读取这个视频的字幕。",
        code="youtube-failed",
        hint="请检查网址，或改为粘贴字幕文本。",
    )


def _pick_transcript(transcripts: Any, languages: tuple[str, ...]) -> Any:
    """Prefer creator captions, then auto captions, in the preferred languages, then anything."""
    for finder in ("find_manually_created_transcript", "find_generated_transcript"):
        try:
            return getattr(transcripts, finder)(list(languages))
        except Exception:
            continue
    available = list(transcripts)
    if not available:
        raise YouTubeDocumentError(
            "这个视频没有可用字幕。",
            code="youtube-no-captions",
            hint="可以把视频的字幕或文字稿粘贴到“粘贴文字”。",
        )
    manual = [item for item in available if not getattr(item, "is_generated", True)]
    return (manual or available)[0]


def fetch_youtube_transcript(
    url: str,
    *,
    settings: YouTubeSettings | None = None,
    timeout: int = 20,
) -> YouTubeTranscript:
    settings = settings or YouTubeSettings()
    video_id = extract_video_id(url)
    if not video_id:
        raise YouTubeDocumentError(
            "无法从这个网址识别 YouTube 视频。",
            code="youtube-invalid-url",
            hint="请使用 youtube.com/watch?v=… 或 youtu.be/… 形式的单个视频网址。",
        )
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.proxies import GenericProxyConfig
    except ImportError as error:
        raise YouTubeDocumentError(
            "当前环境没有安装 YouTube 字幕组件。",
            code="youtube-missing-library",
            hint="本机运行时执行 pip install youtube-transcript-api。",
        ) from error

    proxy = (
        GenericProxyConfig(http_url=settings.proxy_url, https_url=settings.proxy_url)
        if settings.proxy_url
        else None
    )
    try:
        api = YouTubeTranscriptApi(proxy_config=proxy)
        transcript = _pick_transcript(api.list(video_id), settings.languages)
        fetched = transcript.fetch()
    except YouTubeDocumentError:
        raise
    except Exception as error:  # library errors are mapped to user-facing guidance
        raise _map_error(error) from error

    metadata = fetch_video_metadata(video_id, timeout=min(timeout, 10))
    title, channel = metadata if metadata else (f"YouTube 视频 {video_id}", None)
    language = str(getattr(fetched, "language_code", "") or getattr(transcript, "language_code", ""))
    generated = bool(getattr(fetched, "is_generated", getattr(transcript, "is_generated", True)))
    page_url = canonical_url(video_id)
    text, duration = transcript_to_markdown(
        getattr(fetched, "snippets", fetched),
        title=title,
        url=page_url,
        channel=channel,
        language=language,
        generated=generated,
    )
    return YouTubeTranscript(
        text=text,
        title=title,
        channel=channel,
        url=page_url,
        video_id=video_id,
        language=language,
        generated=generated,
        duration_seconds=duration,
    )
