from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError


MAX_PDF_PAGES = 500


class InputDocumentError(RuntimeError):
    """A user-facing uploaded-document parsing error."""


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    filename: str
    stem: str
    kind: str
    pages: int


def filename_stem(filename: str, fallback: str) -> str:
    stem = Path(filename).stem.strip()
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", stem).strip(" ._")
    return (cleaned or fallback)[:100]


def _decode_text(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise InputDocumentError("文本文件不是 UTF-8 编码，请先转换编码后再上传。") from error
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n{4,}", "\n\n\n", text).strip()


def _extract_pdf(data: bytes, stem: str) -> tuple[str, int]:
    try:
        reader = PdfReader(BytesIO(data), strict=False)
    except (PdfReadError, ValueError, TypeError) as error:
        raise InputDocumentError("无法读取这个 PDF，请确认文件没有损坏。") from error

    if reader.is_encrypted:
        try:
            unlocked = reader.decrypt("")
        except Exception as error:
            raise InputDocumentError("PDF 已加密，请先移除密码后再上传。") from error
        if not unlocked:
            raise InputDocumentError("PDF 已加密，请先移除密码后再上传。")

    page_count = len(reader.pages)
    if page_count == 0:
        raise InputDocumentError("PDF 没有可读取的页面。")
    if page_count > MAX_PDF_PAGES:
        raise InputDocumentError(f"PDF 超过 {MAX_PDF_PAGES} 页，请按章节拆分后再上传。")

    extracted_pages: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text(
                extraction_mode="layout",
                layout_mode_space_vertically=False,
            )
        except TypeError:
            text = page.extract_text()
        except Exception as error:
            raise InputDocumentError(f"无法解析 PDF 第 {page_number} 页。") from error
        cleaned = "\n".join(line.rstrip() for line in (text or "").splitlines()).strip()
        if cleaned:
            extracted_pages.append(f"[第 {page_number} 页]\n\n{cleaned}")

    if not extracted_pages:
        raise InputDocumentError("PDF 中没有可提取文字；扫描版或图片型 PDF 请先进行 OCR。")
    return f"# {stem}\n\n" + "\n\n---\n\n".join(extracted_pages), page_count


def extract_uploaded_document(filename: str, data: bytes) -> ExtractedDocument:
    suffix = Path(filename).suffix.lower()
    stem = filename_stem(filename, "document")
    if suffix == ".pdf":
        text, pages = _extract_pdf(data, stem)
        kind = "PDF"
    elif suffix in {".md", ".markdown", ".txt"}:
        text = _decode_text(data)
        pages = 0
        kind = "Markdown" if suffix in {".md", ".markdown"} else "TXT"
    else:
        raise InputDocumentError("仅支持 Markdown、TXT 和 PDF 文件。")

    if not text.strip():
        raise InputDocumentError("文件中没有可用文字。")
    return ExtractedDocument(text=text, filename=filename, stem=stem, kind=kind, pages=pages)
