from __future__ import annotations

import hashlib
import re

import streamlit as st

from longread_pdf import RenderError, render_summary_long_image, render_summary_pdf
from summarizer import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    MAX_SOURCE_CHARACTERS,
    SummaryError,
    summarize_markdown,
)
from ui_components import clipboard_button, page_navigation


SAMPLE = """# 一份等待摘要的长文

## 背景

把 Markdown 粘贴到这里，选择摘要方式后生成结果。

## 结论

摘要会保留重要数字、日期、名称、限制条件和否定表达。
"""


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", value).strip(" ._")
    return (cleaned or "summary")[:100]


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
st.markdown(
    """
    <style>
      :root { --ink: #252525; --muted: #6f6f6f; --rule: #dedede; }
      .stApp { color: var(--ink); }
      [data-testid="stHeader"] { background: rgba(255,255,255,.92); }
      .block-container { max-width: 1240px; padding-top: 2.2rem; padding-bottom: 4rem; }
      h1 { letter-spacing: -.025em; }
      .intro { max-width: 760px; color: var(--muted); font-size: 1.02rem; line-height: 1.7; margin-bottom: 1.4rem; }
      .stButton button, .stDownloadButton button { border-radius: .35rem; }
      footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)
page_navigation()

if "summary_markdown_source" not in st.session_state:
    st.session_state.summary_markdown_source = SAMPLE

api_key = secret_value("DEEPSEEK_API_KEY")
model = secret_value("DEEPSEEK_MODEL", DEFAULT_MODEL)
base_url = secret_value("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)

st.title("文章摘要")
st.markdown(
    '<p class="intro">上传或粘贴 Markdown，生成简短、标准或分章节摘要。PDF 转换页面不受 API 配置影响。</p>',
    unsafe_allow_html=True,
)

if not api_key:
    st.info("尚未配置 DeepSeek API Key。页面可以编辑，但生成按钮暂不可用。")

uploaded = st.file_uploader("上传 Markdown", type=["md", "markdown", "txt"], max_upload_size=5)
if uploaded is not None:
    payload = uploaded.getvalue()
    digest = hashlib.sha256(payload).hexdigest()
    if st.session_state.get("summary_uploaded_digest") != digest:
        try:
            st.session_state.summary_markdown_source = payload.decode("utf-8-sig")
            st.session_state.summary_uploaded_digest = digest
        except UnicodeDecodeError:
            st.error("文件不是 UTF-8 编码。请先转换编码后再上传。")

editor, settings = st.columns([1.55, 1], gap="large")
with editor:
    markdown_source = st.text_area(
        "Markdown 内容",
        key="summary_markdown_source",
        height=560,
    )

with settings:
    st.subheader("摘要方式")
    mode_options = {
        "简短摘要": "brief",
        "标准摘要": "standard",
        "分章节摘要": "section",
    }
    mode_label = st.radio("摘要模式", list(mode_options), label_visibility="collapsed")
    language_options = {
        "跟随原文": "source",
        "简体中文": "zh",
        "English": "en",
    }
    language_label = st.selectbox("输出语言", list(language_options))
    output_name = st.text_input("下载文件名", value="summary")
    consent = st.checkbox("我知道正文将发送到 DeepSeek API 进行摘要。")

    generate_clicked = st.button(
        "生成摘要",
        type="primary",
        icon=":material/summarize:",
        width="stretch",
        disabled=not api_key,
    )

    if generate_clicked:
        if not markdown_source.strip():
            st.error("请先输入 Markdown 内容。")
        elif len(markdown_source) > MAX_SOURCE_CHARACTERS:
            st.error(f"文稿超过 {MAX_SOURCE_CHARACTERS // 10_000} 万字符，请拆分后再摘要。")
        elif not consent:
            st.error("请先确认正文将发送到 DeepSeek API。")
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
                    st.session_state.pop("summary_export", None)
                st.success("摘要已生成。")
            except SummaryError as error:
                st.error(str(error))
            except Exception:
                st.error("摘要生成失败，请查看 Streamlit Cloud 日志。")

result = st.session_state.get("summary_result")
if result:
    st.divider()
    st.subheader("摘要结果")
    metrics = st.columns(3)
    metrics[0].metric("模型", result.model)
    metrics[1].metric("输出 Tokens", result.completion_tokens or "—")
    metrics[2].metric("用时", f"{result.milliseconds / 1000:.1f}s")

    copy_col, markdown_col, pdf_page_col = st.columns(3, gap="medium")
    with copy_col:
        clipboard_button(result.summary, "复制摘要", key="summary-result")
    with markdown_col:
        st.download_button(
            "下载 Markdown",
            data=result.summary.encode("utf-8"),
            file_name=f"{safe_filename(output_name)}.md",
            mime="text/markdown",
            type="primary",
            icon=":material/download:",
            width="stretch",
            on_click="ignore",
        )
    with pdf_page_col:
        if st.button(
            "发送到 Markdown PDF",
            icon=":material/arrow_forward:",
            width="stretch",
        ):
            st.session_state.markdown_source = result.summary
            st.session_state.pop("render_result", None)
            st.switch_page("streamlit_app.py")

    st.markdown(result.summary)

    st.divider()
    st.subheader("导出 PDF 或长图")
    st.caption("直接生成紧凑摘要 PDF，或使用 Tablet / Mobile 阅读版式生成一张连续 PNG 长图。")
    export_kind_label = st.radio(
        "导出格式",
        ["PDF", "长图 PNG"],
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
    summary_digest = hashlib.sha256(result.summary.encode("utf-8")).hexdigest()

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
            st.success("导出文件已生成。")
        except RenderError as error:
            st.error(str(error))
        except Exception:
            st.error("导出失败，请查看 Streamlit Cloud 日志。")

    export = st.session_state.get("summary_export")
    expected_kind = "pdf" if export_kind_label == "PDF" else "image"
    if (
        export
        and export["digest"] == summary_digest
        and export["kind"] == expected_kind
        and export["mode"] == export_mode
    ):
        artifact = export["artifact"]
        if expected_kind == "pdf":
            st.caption(f"{artifact.pages} 页 · {artifact.milliseconds / 1000:.1f} 秒")
            st.download_button(
                "下载 PDF",
                data=artifact.pdf,
                file_name=f"{safe_filename(output_name)}.summary.{export_mode}.pdf",
                mime="application/pdf",
                type="primary",
                icon=":material/download:",
                width="stretch",
                on_click="ignore",
            )
            st.pdf(artifact.pdf, height=720)
        else:
            st.caption(
                f"{artifact.width} × {artifact.height} px · "
                f"{artifact.milliseconds / 1000:.1f} 秒"
            )
            st.download_button(
                "下载 PNG 长图",
                data=artifact.png,
                file_name=f"{safe_filename(output_name)}.summary.{export_mode}.png",
                mime="image/png",
                type="primary",
                icon=":material/download:",
                width="stretch",
                on_click="ignore",
            )
            st.image(artifact.png, caption=f"{export_mode_label}预览", width="stretch")

with st.expander("API 与隐私"):
    st.markdown(
        f"""
        - 当前模型：`{model}`。
        - 只有点击“生成摘要”后，正文才会发送到 DeepSeek。
        - API Key 只从 Streamlit Secrets 读取，不会显示在页面、日志或下载文件中。
        - 单篇文稿上限为 {MAX_SOURCE_CHARACTERS // 10_000} 万字符。
        """
    )
