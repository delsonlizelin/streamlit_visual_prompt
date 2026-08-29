from __future__ import annotations

import hashlib
import importlib
import re

import streamlit as st

import ui_components
from input_documents import InputDocumentError, extract_uploaded_document
from longread_pdf import GPT_MARKDOWN_PROMPT, RenderError, preflight_markdown, render_markdown
from ui_components import clipboard_button, page_navigation


SAMPLE = """# 一份适合长时间阅读的 Markdown
> 简洁、稳定，支持中英文长文。

## 从这里开始

上传 `.md` 文件，或者直接在左侧粘贴文字。第一行 H1 会成为封面标题，紧随其后的引用会成为封面副标题。

正文支持**重点**、*斜体*、列表、链接、引用、代码和简单表格。

## Three reading modes

Desktop mode uses an A4 page. Tablet mode follows the iPad mini portrait ratio. Mobile mode uses a 9:16 page, larger type, and shorter lines.

> 好的排版不需要抢走文字本身的注意力。
"""


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", value).strip(" ._")
    return (cleaned or "longread")[:100]


@st.cache_data(show_spinner=False, max_entries=8)
def generate(markdown_source: str, mode: str):
    return render_markdown(markdown_source, mode=mode)


@st.cache_data(show_spinner=False, max_entries=24)
def analyze(markdown_source: str):
    return preflight_markdown(markdown_source)


st.set_page_config(page_title="Markdown PDF", page_icon="📄", layout="wide")
# A Cloud hot reload can briefly retain the previous component module revision.
if not hasattr(ui_components, "page_shell_styles"):
    try:
        importlib.reload(ui_components)
    except ImportError:
        pass
page_shell_styles = getattr(ui_components, "page_shell_styles", lambda: None)
compatible_file_uploader = getattr(
    ui_components,
    "compatible_file_uploader",
    st.file_uploader,
)
page_shell_styles()
page_navigation("pdf")

if "markdown_source" not in st.session_state:
    st.session_state.markdown_source = SAMPLE
if "pdf_output_name" not in st.session_state:
    st.session_state.pdf_output_name = "longread"

st.title("Markdown PDF")
st.markdown(
    '<p class="intro">把 Markdown 排成安静、耐读的长文 PDF。无需账号和 API，文稿只在当前会话中处理。</p>',
    unsafe_allow_html=True,
)

result = st.session_state.get("render_result")
if result:
    st.success("PDF 已生成，可以直接下载。", icon=":material/check_circle:")
    filename = f"{safe_filename(st.session_state.pdf_output_name)}.pdf"
    st.download_button(
        "下载 PDF",
        data=result.pdf,
        file_name=filename,
        mime="application/pdf",
        type="primary",
        icon=":material/download:",
        width="stretch",
        on_click="ignore",
    )
    st.subheader(result.title)
    metrics = st.columns(4)
    metrics[0].metric("页数", result.pages)
    metrics[1].metric("章节", result.sections)
    mode_names = {"desktop": "A4", "tablet": "iPad mini", "mobile": "9:16"}
    metrics[2].metric("模式", mode_names[result.mode])
    metrics[3].metric("用时", f"{result.milliseconds / 1000:.1f}s")
    if result.blank_pages or result.overflows:
        st.warning("自动检查发现潜在版式问题，建议下载后复核。")
    with st.expander("预览 PDF", icon=":material/preview:"):
        st.pdf(result.pdf, height=760)

source_digest = hashlib.sha256(st.session_state.markdown_source.encode("utf-8")).hexdigest()
if result and st.session_state.get("render_source_digest") != source_digest:
    st.info("原文已经修改；上方下载仍是上一次生成的版本。请重新生成以更新 PDF。")

input_panel = (
    st.expander("编辑原文或重新生成", icon=":material/edit:")
    if result
    else st.container()
)
with input_panel:
    clipboard_button(
        GPT_MARKDOWN_PROMPT,
        "复制 GPT Markdown 格式要求",
        key="gpt-markdown-prompt",
    )

    uploaded = compatible_file_uploader(
        "上传 Markdown 或 TXT",
        type=["md", "markdown", "txt"],
        max_upload_size=5,
    )
    if uploaded is not None:
        payload = uploaded.getvalue()
        digest = hashlib.sha256(payload).hexdigest()
        if st.session_state.get("uploaded_digest") != digest:
            try:
                document = extract_uploaded_document(uploaded.name, payload)
                st.session_state.markdown_source = document.text
                st.session_state.pdf_output_name = document.stem
                st.session_state.uploaded_digest = digest
                st.session_state.pop("render_result", None)
                st.session_state.pop("render_source_digest", None)
                st.rerun()
            except InputDocumentError as error:
                st.error(str(error))

    editor, settings = st.columns([1.55, 1], gap="large")
    with editor:
        markdown_source = st.text_area(
            "Markdown 内容",
            key="markdown_source",
            height=520,
            help="第一行 H1 成为封面标题；紧随其后的引用成为封面副标题。",
        )

    with settings:
        st.subheader("阅读方式")
        mode_options = {
            "电脑端 · A4": "desktop",
            "平板端 · iPad mini": "tablet",
            "手机端 · 9:16": "mobile",
        }
        mode_label = st.radio(
            "输出模式",
            list(mode_options),
            horizontal=True,
            label_visibility="collapsed",
            key="pdf_mode_label",
        )
        mode = mode_options[mode_label]
        st.markdown(
            '<p class="mode-note">电脑端适合大屏与打印；平板端匹配 iPad mini 竖屏比例；手机端采用更大字号和更短行宽。</p>',
            unsafe_allow_html=True,
        )
        output_name = st.text_input("下载文件名", key="pdf_output_name")

        report = analyze(markdown_source)
        if not report.issues:
            st.success("导出前检查通过。", icon=":material/check_circle:")
        else:
            summary = f"{report.errors} 个错误 · {report.warnings} 个提醒 · {report.notices} 个提示"
            if report.errors:
                st.error(summary, icon=":material/error:")
            elif report.warnings:
                st.warning(summary, icon=":material/warning:")
            else:
                st.info(summary, icon=":material/info:")
            with st.expander("查看兼容性检查"):
                icons = {"error": "🔴", "warning": "🟠", "notice": "🔵"}
                for issue in report.issues:
                    location = f" · 第 {issue.line} 行" if issue.line else ""
                    st.markdown(f"{icons[issue.severity]} **{issue.title}**{location}  \n{issue.message}")

        render_clicked = st.button(
            "生成 PDF",
            type="primary",
            icon=":material/picture_as_pdf:",
            width="stretch",
        )

        if render_clicked:
            if not markdown_source.strip():
                st.error("请先输入 Markdown 内容。")
            elif len(markdown_source) > 750_000:
                st.error("文稿超过 75 万字符。请拆成多个文件后再生成。")
            elif report.errors:
                st.error("请先修复导出前检查中的红色项目，再生成 PDF。")
            else:
                try:
                    with st.spinner("正在排版和分页…"):
                        st.session_state.render_result = generate(markdown_source, mode)
                        st.session_state.render_source_digest = hashlib.sha256(
                            markdown_source.encode("utf-8")
                        ).hexdigest()
                    st.rerun()
                except RenderError as error:
                    st.error(str(error))
                except Exception:
                    st.error("生成失败。请检查 Markdown 内容，或查看 Streamlit Cloud 日志。")

with st.expander("支持范围与隐私"):
    st.markdown(
        """
        - 支持标题、段落、粗体、斜体、引用、列表、链接、图片、代码和简单表格。
        - 导出前检查会提示长链接、宽表格、本地图片、公式、Mermaid、原始 HTML 和标题层级问题。
        - 不适合复杂公式、宽表格或以图表为主的文档。
        - 不调用 DeepSeek、OpenAI 或其他模型 API；上传内容不会被发送给模型服务。
        - HTTPS 图片会在生成时从原地址载入；不需要远程请求时，请使用纯文本 Markdown。
        """
    )
