from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from ipaddress import ip_address
import re
import socket
from typing import Callable
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_URL_BYTES = 25 * 1024 * 1024
MIN_ARTICLE_CHARACTERS = 120
DEFAULT_TIMEOUT = 20


class UrlDocumentError(RuntimeError):
    """A user-facing web-article extraction error."""


def _read_bounded_response(response, *, max_bytes: int = MAX_URL_BYTES) -> bytes:  # noqa: ANN001
    """Read one byte past the limit so oversized responses fail without growing forever."""
    payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        limit_mb = max(1, (max_bytes + 1024 * 1024 - 1) // (1024 * 1024))
        raise UrlDocumentError(
            f"网页响应超过 {limit_mb} MB，无法安全读取；"
            "请复制正文，或将文章下载为 PDF 后上传。"
        )
    return payload


@dataclass(frozen=True)
class ExtractedUrlDocument:
    text: str
    url: str
    title: str
    site: str
    characters: int


def _public_addresses(hostname: str) -> list[str]:
    try:
        records = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise UrlDocumentError("无法解析这个网址，请检查地址是否正确。") from error

    addresses = sorted({record[4][0] for record in records})
    if not addresses or any(not ip_address(address).is_global for address in addresses):
        raise UrlDocumentError("为了安全，网址不能指向本机或内网地址。")
    return addresses


def normalize_public_url(
    value: str,
    *,
    resolver: Callable[[str], list[str]] = _public_addresses,
) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise UrlDocumentError("请先输入文章网址。")
    if "://" not in cleaned:
        cleaned = f"https://{cleaned}"

    parsed = urlsplit(cleaned)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UrlDocumentError("只支持 http 或 https 网页地址。")
    if not parsed.hostname or parsed.username or parsed.password:
        raise UrlDocumentError("网址格式不正确。")
    try:
        parsed.port
    except ValueError as error:
        raise UrlDocumentError("网址端口不正确。") from error

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".local"):
        raise UrlDocumentError("为了安全，网址不能指向本机或内网地址。")
    resolver(hostname)

    netloc = hostname
    if parsed.port:
        netloc = f"{hostname}:{parsed.port}"
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, ""))


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        absolute = urljoin(req.full_url, newurl)
        safe_url = normalize_public_url(absolute)
        return super().redirect_request(req, fp, code, msg, headers, safe_url)


class _ArticleParser(HTMLParser):
    _ignored_tags = {"script", "style", "noscript", "svg", "nav", "form", "button"}
    _void_tags = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
    _block_tags = {
        "address",
        "article",
        "aside",
        "blockquote",
        "div",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "header",
        "li",
        "main",
        "p",
        "section",
        "td",
        "th",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.author = ""
        self.published = ""
        self.site = ""
        self._title_depth = 0
        self._author_depth = 0
        self._published_depth = 0
        self._ignored_depth = 0
        self._depth = 0
        self._open_tags: list[str] = []
        self._roots: dict[str, list[int]] = {
            "wechat": [],
            "article": [],
            "main": [],
            "body": [],
        }
        self._parts: dict[str, list[str]] = {name: [] for name in self._roots}

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key.lower(): (value or "") for key, value in attrs}

    def _append(self, value: str) -> None:
        if self._ignored_depth:
            return
        for name, starts in self._roots.items():
            if starts:
                self._parts[name].append(value)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in self._void_tags:
            self._open_tags.append(tag)
        self._depth = len(self._open_tags)
        attributes = self._attrs(attrs)
        element_id = attributes.get("id", "")

        if tag in self._ignored_tags:
            self._ignored_depth += 1
        if tag == "title":
            self._title_depth += 1
        if element_id in {"js_name", "profileBt"}:
            self._author_depth = self._depth
        if element_id in {"publish_time", "js_publish_time"}:
            self._published_depth = self._depth

        if element_id == "js_content":
            self._roots["wechat"].append(self._depth)
        if tag == "article":
            self._roots["article"].append(self._depth)
        if tag == "main":
            self._roots["main"].append(self._depth)
        if tag == "body":
            self._roots["body"].append(self._depth)

        if tag == "meta":
            key = (attributes.get("property") or attributes.get("name", "")).lower()
            content = attributes.get("content", "").strip()
            if key in {"og:title", "twitter:title"} and content:
                self.title = content
            elif key in {"author", "article:author"} and content:
                self.author = content
            elif key in {"article:published_time", "date", "pubdate"} and content:
                self.published = content
            elif key in {"og:site_name", "application-name"} and content:
                self.site = content

        if tag in {"h1", "h2", "h3", "h4"}:
            self._append("\n\n## ")
        elif tag == "li":
            self._append("\n- ")
        elif tag == "blockquote":
            self._append("\n\n> ")
        elif tag == "br":
            self._append("\n")
        elif tag in self._block_tags:
            self._append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._block_tags:
            self._append("\n\n")

        closing_index = next(
            (
                index
                for index in range(len(self._open_tags) - 1, -1, -1)
                if self._open_tags[index] == tag
            ),
            -1,
        )
        if closing_index < 0:
            # Real-world article HTML often contains unmatched presentational
            # closing tags. They must not move the capture depth or terminate
            # an enclosing article root early.
            return
        closing_depth = closing_index + 1

        for starts in self._roots.values():
            if starts and starts[-1] == closing_depth:
                starts.pop()
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
        if self._author_depth == closing_depth:
            self._author_depth = 0
        if self._published_depth == closing_depth:
            self._published_depth = 0
        if tag in self._ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1
        self._open_tags = self._open_tags[:closing_index]
        self._depth = len(self._open_tags)

    def handle_data(self, data: str) -> None:
        value = re.sub(r"\s+", " ", data).strip()
        if not value:
            return
        if self._title_depth and not self.title:
            self.title = value
        if self._author_depth and not self.author:
            self.author = value
        if self._published_depth and not self.published:
            self.published = value
        self._append(value + " ")

    @staticmethod
    def _clean(value: str) -> str:
        value = value.replace("\xa0", " ")
        value = re.sub(r"[ \t]+\n", "\n", value)
        value = re.sub(r"\n[ \t]+", "\n", value)
        value = re.sub(r"[ \t]{2,}", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        value = re.sub(r"(?m)^##\s*$", "", value)
        return value.strip(" \n-")

    def article_text(self) -> str:
        candidates = [
            self._clean("".join(self._parts[name]))
            for name in ("wechat", "article", "main", "body")
        ]
        for candidate in candidates:
            if len(candidate) >= MIN_ARTICLE_CHARACTERS:
                return candidate
        return max(candidates, key=len, default="")


def extract_article_html(html: str, *, url: str) -> ExtractedUrlDocument:
    parser = _ArticleParser()
    try:
        parser.feed(html)
    except Exception as error:
        raise UrlDocumentError("网页结构无法解析，请改为粘贴正文。") from error

    article = parser.article_text()
    hostname = (urlsplit(url).hostname or "网页").removeprefix("www.")
    if len(re.sub(r"\s+", "", article)) < MIN_ARTICLE_CHARACTERS:
        if hostname.endswith("mp.weixin.qq.com"):
            raise UrlDocumentError(
                "微信公众号没有返回可读取的正文，可能触发了登录或访问限制；请在微信中复制正文后粘贴。"
            )
        raise UrlDocumentError("网页正文太短或无法识别，请改为粘贴正文。")

    title = re.sub(r"\s+", " ", parser.title).strip() or "网页文章"
    site = re.sub(r"\s+", " ", parser.site).strip() or hostname
    metadata = [f"来源：[{site}]({url})"]
    if parser.author:
        author = re.sub(r"\s+", " ", parser.author).strip()
        metadata.append(f"作者：{author}")
    if parser.published:
        published = re.sub(r"\s+", " ", parser.published).strip()
        metadata.append(f"发布时间：{published}")
    text = f"# {title}\n\n" + " · ".join(metadata) + f"\n\n{article}"
    return ExtractedUrlDocument(
        text=text,
        url=url,
        title=title,
        site=site,
        characters=len(text),
    )


def fetch_url_document(value: str, *, timeout: int = DEFAULT_TIMEOUT) -> ExtractedUrlDocument:
    url = normalize_public_url(value)
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml;q=0.9",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
            ),
        },
    )
    opener = build_opener(_SafeRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            final_url = normalize_public_url(response.geturl())
            content_type = response.headers.get_content_type().lower()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise UrlDocumentError("这个网址不是可读取的网页文章。")
            payload = _read_bounded_response(response)
            charset = response.headers.get_content_charset() or "utf-8"
    except UrlDocumentError:
        raise
    except Exception as error:
        raise UrlDocumentError("无法读取这个网页；请检查网址，或改为粘贴正文。") from error

    try:
        html = payload.decode(charset, errors="strict")
    except (LookupError, UnicodeDecodeError):
        try:
            html = payload.decode("utf-8")
        except UnicodeDecodeError:
            html = payload.decode("gb18030", errors="replace")
    return extract_article_html(html, url=final_url)
