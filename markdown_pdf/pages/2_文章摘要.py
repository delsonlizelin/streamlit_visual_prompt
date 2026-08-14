from __future__ import annotations

import hashlib
import importlib
import re

import streamlit as st

import ui_components
from input_documents import InputDocumentError, extract_uploaded_document
from longread_pdf import RenderError, render_summary_long_image, render_summary_pdf
from summarizer import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    MAX_SOURCE_CHARACTERS,
    SYSTEM_PROMPT,
    SummaryError,
    summarize_markdown,
)
from ui_components import clipboard_button, page_navigation


SAMPLE = """# 一份等待摘要的长文

## 背景

把 Markdown、TXT 或普通文本型 PDF 上传到这里，也可以直接粘贴文字。

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


st.set_page_config(page_title="文章摘要", page_icon="📝", layout="wide")
# A Cloud hot reload can briefly retain the previous component module revision.
if not hasattr(ui_components, "page_shell_styles"):
    try:
        importlib.reload(ui_components)
    except ImportError:
        pass
page_shell_styles = getattr(ui_components, "page_shell_styles", lambda: None)
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
    '<p class="intro">上传 Markdown、TXT 或普通文本型 PDF，生成结构清楚、可以直接下载和分享的摘要。</p>',
    unsafe_allow_html=True,
)
clipboard_button(
    SYSTEM_PROMPT,
    "复制摘要系统提示词",
    key="summary-system-prompt",
)

if not api_key:
    st.info("尚未配置 DeepSeek API Key。页面可以编辑，但生成按钮暂不可用。")

result = st.session_state.get("summary_result")
summary_digest = (
    hashlib.sha256(result.summary.encode("utf-8")).hexdigest() if result else ""
)
export = st.session_state.get("summary_export")
valid_export = bool(export and export.get("digest") == summary_digest)

if result:
    st.success("摘要已生成，下载入口已放在最前面。", icon=":material/check_circle:")
    st.download_button(
        "下载 Markdown",
        data=result.summary.encode("utf-8"),
        file_name=f"{safe_filename(st.session_state.summary_output_name)}.md",
        mime="text/markdown",
        type="primary",
        icon=":material/download:",
        width="stretch",
        on_click="ignore",
    )

    if valid_export:
        export_download_button(export, key="summary-export-download-top")

    copy_col, pdf_page_col = st.columns(2, gap="medium")
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

    metrics = st.columns(3)
    metrics[0].metric("模型", result.model)
    metrics[1].metric("输出 Tokens", result.completion_tokens or "—")
    metrics[2].metric("用时", f"{result.milliseconds / 1000:.1f}s")

    with st.expander("预览摘要", icon=":material/preview:"):
        st.markdown(result.summary)

    st.subheader("生成 PDF 或长图")
    st.caption("选择格式后生成；生成完成的下载按钮会自动出现在页面顶部。")
    export_kind_label = st.radio(
        "导出格式",
        ["PDF", "高清长图 PNG"],
        horizontal=True,
        key="summary_export_kind",
    )
    if export_kind_label == "PDF":
        export_mode_options = {
            "电脑端 · A4": "desktop",
            "平板端 · iPad mini": "tablet",
            "手机端 · 9:16": "mobile",
        }
    else:
        export_mode_options = {
            "平板长图": "tablet",
            "手机长图": "mobile",
        }
    export_mode_label = st.radio(
        "阅读模式",
        list(export_mode_options),
        horizontal=True,
        key=f"summary_export_mode_{export_kind_label}",
    )
    export_mode = export_mode_options[export_mode_label]

    if st.button(
        "生成导出文件",
        type="primary",
        icon=":material/ios_share:",
        width="stretch",
    ):
        try:
            with st.spinner("正在排版导出文件…"):
                if export_kind_label == "PDF":
                    artifact = build_summary_pdf(result.summary, export_mode)
                    kind = "pdf"
                else:
                    artifact = build_summary_long_image(result.summary, export_mode)
                    kind = "image"
                st.session_state.summary_export = {
                    "digest": summary_digest,
                    "kind": kind,
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
        st.success(
            "导出文件已生成，可直接下载；下方预览只用于检查效果。",
            icon=":material/check_circle:",
        )
        export_download_button(export, key="summary-export-download-inline")
        with st.expander("预览最近生成的导出文件", icon=":material/preview:"):
            if export["kind"] == "pdf":
                st.caption(f"{artifact.pages} 页 · {artifact.milliseconds / 1000:.1f} 秒")
                st.pdf(artifact.pdf, height=700)
            else:
                st.caption(
                    f"{artifact.width} × {artifact.height} px · "
                    f"{artifact.milliseconds / 1000:.1f} 秒"
                )
                st.image(artifact.png, caption="长图预览", width="stretch")

current_source_digest = hashlib.sha256(
    st.session_state.summary_markdown_source.encode("utf-8")
).hexdigest()
if result and st.session_state.get("summary_source_digest") != current_source_digest:
    st.info(
        "当前正文与生成摘要时的原文不同。上方摘要和导出文件不会自动更新；"
        "如果你改了正文，请重新生成摘要。仅修改下载文件名不需要重新生成。"
    )

input_panel = (
    st.expander("编辑输入或重新生成", icon=":material/edit:")
    if result
    else st.container()
)
with input_panel:
    uploaded = st.file_uploader(
        "上传 Markdown、TXT 或 PDF",
        type=["md", "markdown", "txt", "pdf"],
        max_upload_size=20,
    )
    if uploaded is not None:
        payload = uploaded.getvalue()
        digest = hashlib.sha256(payload).hexdigest()
        if st.session_state.get("summary_uploaded_digest") != digest:
            try:
                with st.spinner("正在读取文件…"):
                    document = extract_uploaded_document(uploaded.name, payload)
                st.session_state.summary_markdown_source = document.text
                st.session_state.summary_output_name = document.stem
                st.session_state.summary_uploaded_digest = digest
                st.session_state.summary_input_meta = {
                    "kind": document.kind,
                    "pages": document.pages,
                    "characters": len(document.text),
                }
                st.session_state.pop("summary_result", None)
                st.session_state.pop("summary_export", None)
                st.session_state.pop("summary_source_digest", None)
                st.rerun()
            except InputDocumentError as error:
                st.error(str(error))

    input_meta = st.session_state.get("summary_input_meta")
    if input_meta:
        page_note = f" · {input_meta['pages']} 页" if input_meta["pages"] else ""
        st.caption(
            f"已读取 {input_meta['kind']}{page_note} · "
            f"{input_meta['characters']:,} 字符"
        )

    editor, settings = st.columns([1.55, 1], gap="large")
    with editor:
        markdown_source = st.text_area(
            "输入内容",
            key="summary_markdown_source",
            height=500,
            help="PDF 会先提取为可编辑文本；扫描版 PDF 需要先进行 OCR。",
        )

    with settings:
        st.subheader("摘要方式")
        mode_options = {
            "快速概览": "brief",
            "核心摘要": "standard",
            "分章节摘要": "section",
        }
        mode_label = st.radio(
            "摘要模式",
            list(mode_options),
            label_visibility="collapsed",
            key="summary_mode_label",
        )
        language_options = {
            "跟随原文": "source",
            "简体中文": "zh",
            "English": "en",
        }
        language_label = st.selectbox(
            "输出语言",
            list(language_options),
            key="summary_language_label",
        )
        output_name = st.text_input("下载文件名", key="summary_output_name")
        st.caption("点击生成即表示允许把当前输入发送到 DeepSeek；无需重复确认。")

        generate_clicked = st.button(
            "生成摘要",
            type="primary",
            icon=":material/summarize:",
            width="stretch",
            disabled=not api_key,
        )

        if generate_clicked:
            if not markdown_source.strip():
                st.error("请先输入内容。")
            elif len(markdown_source) > MAX_SOURCE_CHARACTERS:
                st.error(f"文稿超过 {MAX_SOURCE_CHARACTERS // 10_000} 万字符，请拆分后再摘要。")
            else:
                try:
                    with st.spinner("正在生成摘要…"):
                        st.session_state.summary_result = summarize_markdown(
                            markdown_source,
                            mode=mode_options[mode_label],
                            language=language_options[language_label],
                            api_key=api_key,
                            model=model,
                            base_url=base_url,
                        )
                        st.session_state.summary_source_digest = hashlib.sha256(
                            markdown_source.encode("utf-8")
                        ).hexdigest()
                        st.session_state.pop("summary_export", None)
                    st.rerun()
                except SummaryError as error:
                    st.error(str(error))
                except Exception:
                    st.error("摘要生成失败，请查看 Streamlit Cloud 日志。")

with st.expander("输入、API 与隐私"):
    st.markdown(
        f"""
        - 支持 Markdown、UTF-8 TXT 和普通文本型 PDF；扫描件或图片型 PDF 需要先做 OCR。
        - 当前模型：`{model}`。
        - 只有点击“生成摘要”后，输入内容才会发送到 DeepSeek。
        - API Key 只从 Streamlit Secrets 读取，不会显示在页面、日志或下载文件中。
        - 单篇文稿上限为 {MAX_SOURCE_CHARACTERS // 10_000} 万字符，PDF 上限为 500 页。
        """
    )
