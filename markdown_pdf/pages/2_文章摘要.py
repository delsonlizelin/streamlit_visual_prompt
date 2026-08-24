from __future__ import annotations

import hashlib
import importlib
import re

import streamlit as st

import ui_components
from input_documents import InputDocumentError, extract_uploaded_document
from longread_pdf import RenderError, render_summary_long_image, render_summary_pdf
from ui_components import clipboard_button, page_navigation
from url_documents import UrlDocumentError, fetch_url_document


SUMMARIZER_SYMBOLS = (
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "MAX_SOURCE_CHARACTERS",
    "MODE_CAPTIONS",
    "MODE_LABELS",
    "STYLE_CAPTIONS",
    "STYLE_LABELS",
    "SummaryError",
    "build_prompt_template",
    "summarize_markdown",
)
summarizer_backend = importlib.import_module("summarizer.deepseek")
if not all(hasattr(summarizer_backend, name) for name in SUMMARIZER_SYMBOLS):
    summarizer_backend = importlib.reload(summarizer_backend)

DEFAULT_BASE_URL = summarizer_backend.DEFAULT_BASE_URL
DEFAULT_MODEL = summarizer_backend.DEFAULT_MODEL
MAX_SOURCE_CHARACTERS = summarizer_backend.MAX_SOURCE_CHARACTERS
MODE_CAPTIONS = summarizer_backend.MODE_CAPTIONS
MODE_LABELS = summarizer_backend.MODE_LABELS
STYLE_CAPTIONS = summarizer_backend.STYLE_CAPTIONS
STYLE_LABELS = summarizer_backend.STYLE_LABELS
SummaryError = summarizer_backend.SummaryError
build_prompt_template = summarizer_backend.build_prompt_template
summarize_markdown = summarizer_backend.summarize_markdown


SAMPLE = """# 一份等待摘要的长文

## 背景

粘贴文字、上传 Markdown、TXT 或普通文本型 PDF，也可以读取公开文章网址。

## 结论

摘要会保留重要数字、日期、名称、限制条件和否定表达。
"""


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", value).strip(" ._")
    return (cleaned or "summary")[:100]


def export_download_button(export: dict, *, key: str) -> None:
    """Render a download button for the current PDF or long-image export."""
    artifact = export["artifact"]
    output_name = safe_filename(st.session_state.summary_output_name)
    if export["kind"] == "pdf":
        st.download_button(
            f"下载 {export['mode']} PDF",
            data=artifact.pdf,
            file_name=f"{output_name}.summary.pdf",
            mime="application/pdf",
            icon=":material/download:",
            width="stretch",
            on_click="ignore",
            key=key,
        )
    else:
        st.download_button(
            f"下载 {export['mode']} PNG 长图",
            data=artifact.png,
            file_name=f"{output_name}.summary.png",
            mime="image/png",
            icon=":material/download:",
            width="stretch",
            on_click="ignore",
            key=key,
        )


def secret_value(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
    except FileNotFoundError:
        return default
    return str(value) if value is not None else default


@st.cache_data(show_spinner=False, max_entries=8)
def build_summary_pdf(markdown_source: str, mode: str):
    return render_summary_pdf(markdown_source, mode=mode)


@st.cache_data(show_spinner=False, max_entries=8)
def build_summary_long_image(markdown_source: str, mode: str):
    return render_summary_long_image(markdown_source, mode=mode)


def clear_generated_content() -> None:
    """Drop outputs that no longer match a newly loaded source."""
    st.session_state.pop("summary_result", None)
    st.session_state.pop("summary_export", None)
    st.session_state.pop("summary_source_digest", None)


def use_source(*, text: str, output_name: str, meta: dict) -> None:
    st.session_state.summary_markdown_source = text
    st.session_state.summary_output_name = output_name
    st.session_state.summary_input_meta = meta
    clear_generated_content()


st.set_page_config(page_title="文章摘要", page_icon="📝", layout="wide")
# A Cloud hot reload can briefly retain the previous component module revision.
if not hasattr(ui_components, "page_shell_styles"):
    try:
        importlib.reload(ui_components)
    except ImportError:
        pass
page_shell_styles = getattr(ui_components, "page_shell_styles", lambda: None)
auto_article_url_input = getattr(
    ui_components,
    "auto_article_url_input",
    lambda value, key: st.text_input("文章网址", value=value, key=key),
)
native_image_share = getattr(
    ui_components,
    "native_image_share",
    lambda png, filename, key: None,
)
page_shell_styles()
page_navigation("summary")

if "summary_markdown_source" not in st.session_state:
    st.session_state.summary_markdown_source = SAMPLE
if "summary_output_name" not in st.session_state:
    st.session_state.summary_output_name = "summary"

api_key = secret_value("DEEPSEEK_API_KEY")
model = secret_value("DEEPSEEK_MODEL", DEFAULT_MODEL)
base_url = secret_value("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)

st.title("文章摘要")
st.markdown(
    '<p class="intro">粘贴文字、上传文档或输入文章网址。确认原文后，分别选择内容结构和讲述方式。</p>',
    unsafe_allow_html=True,
)
if not api_key:
    st.info("尚未配置 DeepSeek API Key。页面可以读取和编辑原文，但暂时不能生成摘要。")

st.subheader("添加原文")
source_labels = {
    "paste": "粘贴文字",
    "upload": "上传文件",
    "url": "文章网址",
}
source_method = st.segmented_control(
    "原文来源",
    list(source_labels),
    default="paste",
    format_func=source_labels.get,
    key="summary_source_method",
    width="stretch",
)

if source_method == "upload":
    uploaded = st.file_uploader(
        "选择 Markdown、TXT 或普通文本型 PDF",
        type=["md", "markdown", "txt", "pdf"],
        max_upload_size=100,
        key="summary_file_input",
        help="单个文件最多 100 MB。PDF 会先提取为可编辑文字；扫描件或图片型 PDF 需要先做 OCR。",
    )
    if uploaded is not None:
        payload = uploaded.getvalue()
        digest = hashlib.sha256(payload).hexdigest()
        reread = False
        if st.session_state.get("summary_uploaded_digest") == digest:
            reread = st.button(
                "重新读取这个文件",
                icon=":material/refresh:",
                help="丢弃编辑器中的改动，重新从当前文件提取原文。",
            )
        if st.session_state.get("summary_uploaded_digest") != digest or reread:
            try:
                with st.spinner("正在读取文件…"):
                    document = extract_uploaded_document(uploaded.name, payload)
                use_source(
                    text=document.text,
                    output_name=document.stem,
                    meta={
                        "kind": document.kind,
                        "pages": document.pages,
                        "characters": len(document.text),
                        "source": "upload",
                    },
                )
                st.session_state.summary_uploaded_digest = digest
                st.rerun()
            except InputDocumentError as error:
                st.error(str(error))

elif source_method == "url":
    stored_article_url = str(st.session_state.get("summary_article_url", ""))
    article_url = auto_article_url_input(
        stored_article_url,
        key="summary_article_url_input",
    )
    if article_url != stored_article_url:
        st.session_state.summary_article_url = article_url

    previous_attempt = st.session_state.get("summary_last_url_attempt")
    retry_url = bool(
        article_url
        and previous_attempt == article_url
        and st.button(
            "重新读取这个网址",
            icon=":material/refresh:",
            width="stretch",
        )
    )
    should_read_url = bool(article_url and (article_url != previous_attempt or retry_url))
    if should_read_url:
        st.session_state.summary_last_url_attempt = article_url
        try:
            with st.spinner("正在读取网页正文…"):
                document = fetch_url_document(article_url)
            use_source(
                text=document.text,
                output_name=safe_filename(document.title),
                meta={
                    "kind": "网页",
                    "pages": 0,
                    "characters": document.characters,
                    "source": "url",
                    "site": document.site,
                },
            )
            st.rerun()
        except UrlDocumentError as error:
            st.error(str(error))
    st.caption(
        "支持公开网页和微信公众号文章；粘贴完整网址后会自动读取。"
        "登录、验证码或访问频率限制仍可能导致失败。"
    )

input_meta = st.session_state.get("summary_input_meta")
if input_meta:
    page_note = f" · {input_meta['pages']} 页" if input_meta.get("pages") else ""
    site_note = f" · {input_meta['site']}" if input_meta.get("site") else ""
    st.caption(
        f"已读取 {input_meta['kind']}{page_note}{site_note} · "
        f"{input_meta['characters']:,} 字符"
    )

result = st.session_state.get("summary_result")
mode_order = ["standard", "section"]
mode_labels = [MODE_LABELS[mode] for mode in mode_order]
style_order = ["direct", "beginner"]
style_labels = [STYLE_LABELS[style] for style in style_order]
language_options = {
    "跟随原文": "source",
    "简体中文": "zh",
    "English": "en",
}

editor_col, options_col = st.columns([1.45, 1], gap="large")
with editor_col:
    markdown_source = st.text_area(
        "原文（可编辑）",
        key="summary_markdown_source",
        height=430,
        help="上传文件或读取网页后，正文会出现在这里；你可以修改后再生成。",
    )
    current_source_digest = hashlib.sha256(markdown_source.encode("utf-8")).hexdigest()
    source_is_stale = bool(
        result and st.session_state.get("summary_source_digest") != current_source_digest
    )
    if source_is_stale:
        st.warning("原文已经修改。当前结果仍是上一版；重新生成即可更新。")

with options_col:
    selected_mode_label = st.radio(
        "内容结构",
        mode_labels,
        index=0,
        captions=[MODE_CAPTIONS[mode] for mode in mode_order],
        key="summary_structure_choice",
    )
    selected_mode = mode_order[mode_labels.index(selected_mode_label)]
    selected_style_label = st.radio(
        "讲述方式",
        style_labels,
        index=0,
        captions=[STYLE_CAPTIONS[style] for style in style_order],
        key="summary_style_choice",
    )
    selected_style = style_order[style_labels.index(selected_style_label)]
    language_label = st.selectbox(
        "输出语言",
        list(language_options),
        key="summary_language_label",
    )
    st.text_input("下载文件名", key="summary_output_name")

    with st.expander("查看提示词与隐私"):
        st.caption("复制的是当前内容结构、讲述方式、语言和系统规则；正文位置使用占位符。")
        clipboard_button(
            build_prompt_template(
                mode=selected_mode,
                language=language_options[language_label],
                style=selected_style,
            ),
            "复制当前提示词",
            key="summary-prompt-template",
        )
        st.markdown(
            "只有点击“生成摘要”后，当前原文才会发送到 DeepSeek。"
            "API Key 不会显示或写入文件。"
        )
    generate_label = "重新生成摘要" if result else "生成摘要"
    generate_clicked = st.button(
        generate_label,
        type="primary",
        icon=":material/summarize:",
        width="stretch",
        disabled=not api_key,
    )
    st.caption(
        f"{model} · 上限 {MAX_SOURCE_CHARACTERS // 10_000} 万字符 · PDF 500 页"
    )

if generate_clicked:
    if not markdown_source.strip():
        st.error("请先添加原文。")
    elif len(markdown_source) > MAX_SOURCE_CHARACTERS:
        st.error(f"文稿超过 {MAX_SOURCE_CHARACTERS // 10_000} 万字符，请拆分后再摘要。")
    else:
        try:
            with st.spinner("正在生成摘要…"):
                st.session_state.summary_result = summarize_markdown(
                    markdown_source,
                    mode=selected_mode,
                    language=language_options[language_label],
                    style=selected_style,
                    api_key=api_key,
                    model=model,
                    base_url=base_url,
                )
                st.session_state.summary_source_digest = current_source_digest
                st.session_state.pop("summary_export", None)
            st.rerun()
        except SummaryError as error:
            st.error(str(error))
        except Exception:
            st.error("摘要生成失败，请查看 Streamlit Cloud 日志。")

if result:
    summary_digest = hashlib.sha256(result.summary.encode("utf-8")).hexdigest()
    export = st.session_state.get("summary_export")
    valid_export = bool(export and export.get("digest") == summary_digest)

    st.divider()
    st.subheader("摘要结果")
    if source_is_stale:
        st.info("下方结果基于上一版原文；重新生成前仍可复制或下载。")
    else:
        st.success("摘要已生成。", icon=":material/check_circle:")

    with st.container(border=True):
        st.markdown(result.summary)

    download_col, copy_col, pdf_page_col = st.columns(3, gap="medium")
    with download_col:
        st.download_button(
            "下载 Markdown",
            data=result.summary.encode("utf-8"),
            file_name=f"{safe_filename(st.session_state.summary_output_name)}.md",
            mime="text/markdown",
            icon=":material/download:",
            width="stretch",
            on_click="ignore",
        )
    with copy_col:
        clipboard_button(result.summary, "复制摘要", key="summary-result")
    with pdf_page_col:
        if st.button(
            "发送到 Markdown PDF",
            icon=":material/arrow_forward:",
            width="stretch",
        ):
            st.session_state.markdown_source = result.summary
            st.session_state.pdf_output_name = st.session_state.summary_output_name
            st.session_state.pop("render_result", None)
            st.session_state.pop("render_source_digest", None)
            st.switch_page("streamlit_app.py")

    st.caption(
        f"{result.model} · {result.completion_tokens or '—'} 输出 Tokens · "
        f"{result.milliseconds / 1000:.1f} 秒"
    )

    st.subheader("导出与分享")
    export_target_options = {
        "手机长图": ("image", "mobile"),
        "平板长图": ("image", "tablet"),
        "PDF": ("pdf", "mobile"),
    }
    export_target_label = st.segmented_control(
        "导出格式",
        list(export_target_options),
        default="手机长图",
        key="summary_export_target",
        width="stretch",
    )
    export_kind, export_mode = export_target_options[
        export_target_label or "手机长图"
    ]
    if export_kind == "pdf":
        export_mode_options = {
            "电脑端 · A4": "desktop",
            "平板端 · iPad mini": "tablet",
            "手机端 · 9:16": "mobile",
        }
        export_mode_label = st.radio(
            "PDF 阅读模式",
            list(export_mode_options),
            horizontal=True,
            key="summary_pdf_export_mode",
        )
        export_mode = export_mode_options[export_mode_label]

    generate_export_label = (
        "生成 PDF" if export_kind == "pdf" else f"生成{export_target_label}"
    )
    if st.button(
        generate_export_label,
        icon=":material/ios_share:",
        width="stretch",
    ):
        try:
            with st.spinner("正在排版导出文件…"):
                if export_kind == "pdf":
                    artifact = build_summary_pdf(result.summary, export_mode)
                else:
                    artifact = build_summary_long_image(result.summary, export_mode)
                st.session_state.summary_export = {
                    "digest": summary_digest,
                    "kind": export_kind,
                    "mode": export_mode,
                    "artifact": artifact,
                }
            st.rerun()
        except RenderError as error:
            st.error(str(error))
        except Exception:
            st.error("导出失败，请查看 Streamlit Cloud 日志。")

    if valid_export:
        artifact = export["artifact"]
        if export["kind"] == "image":
            output_name = safe_filename(st.session_state.summary_output_name)
            native_image_share(
                artifact.png,
                f"{output_name}.summary.png",
                key="summary-native-image-share",
            )
            export_download_button(export, key="summary-export-download-inline")
            st.caption(
                f"{artifact.width} × {artifact.height} px · "
                f"{artifact.milliseconds / 1000:.1f} 秒。"
                "iPhone 或 iPad 可点“分享长图”，也可以长按下方图片存储或分享。"
            )
            st.image(artifact.png, caption="长图预览", width="stretch")
        else:
            export_download_button(export, key="summary-export-download-inline")
            st.caption(f"{artifact.pages} 页 · {artifact.milliseconds / 1000:.1f} 秒")
            with st.expander("预览 PDF", icon=":material/preview:"):
                st.pdf(artifact.pdf, height=700)
