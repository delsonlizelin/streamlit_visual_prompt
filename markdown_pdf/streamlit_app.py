from __future__ import annotations

import hashlib
import re

import streamlit as st

from longread_pdf import RenderError, render_markdown


SAMPLE = """# 一份适合长时间阅读的 Markdown
> 简洁、稳定，支持中英文长文。

## 从这里开始

上传 `.md` 文件，或者直接在左侧粘贴文字。第一行 H1 会成为封面标题，紧随其后的引用会成为封面副标题。

正文支持**重点**、*斜体*、列表、链接、引用、代码和简单表格。

## Two reading modes

Desktop mode uses an A4 page and a quiet running header. Mobile mode uses a 9:16 page, larger type, shorter lines, and no running header.

> 好的排版不需要抢走文字本身的注意力。
"""


st.set_page_config(page_title="Markdown PDF", page_icon="📄", layout="wide")
st.markdown(
    """
    <style>
      :root { --ink: #252525; --muted: #6f6f6f; --rule: #dedede; }
      .stApp { color: var(--ink); }
      [data-testid="stHeader"] { background: rgba(255,255,255,.92); }
      .block-container { max-width: 1240px; padding-top: 2.2rem; padding-bottom: 4rem; }
      h1 { letter-spacing: -.025em; }
      .intro { max-width: 720px; color: var(--muted); font-size: 1.02rem; line-height: 1.7; margin-bottom: 1.4rem; }
      .mode-note { color: var(--muted); font-size: .88rem; line-height: 1.55; }
      [data-testid="stFileUploader"] { border: 1px solid var(--rule); border-radius: .45rem; padding: .35rem .65rem; }
      [data-testid="stMetric"] { border-top: 1px solid var(--rule); padding-top: .65rem; }
      .stButton button, .stDownloadButton button { border-radius: .35rem; }
      footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", value).strip(" ._")
    return (cleaned or "longread")[:100]


@st.cache_data(show_spinner=False, max_entries=8)
def generate(markdown_source: str, mode: str, short_title: str):
    return render_markdown(markdown_source, mode=mode, short_title=short_title)


if "markdown_source" not in st.session_state:
    st.session_state.markdown_source = SAMPLE

st.title("Markdown PDF")
st.markdown(
    '<p class="intro">把中英文 Markdown 排成克制、易读的长文 PDF。无需账号、无需 API；文稿只在当前 Streamlit 会话中处理。</p>',
    unsafe_allow_html=True,
)

uploaded = st.file_uploader("上传 Markdown", type=["md", "markdown", "txt"], max_upload_size=5)
if uploaded is not None:
    payload = uploaded.getvalue()
    digest = hashlib.sha256(payload).hexdigest()
    if st.session_state.get("uploaded_digest") != digest:
        try:
            st.session_state.markdown_source = payload.decode("utf-8-sig")
            st.session_state.uploaded_digest = digest
        except UnicodeDecodeError:
            st.error("文件不是 UTF-8 编码。请先转换编码后再上传。")

editor, settings = st.columns([1.55, 1], gap="large")
with editor:
    markdown_source = st.text_area(
        "Markdown 内容",
        key="markdown_source",
        height=560,
        help="第一行 H1 成为封面标题；紧随其后的引用成为封面副标题。",
    )

with settings:
    st.subheader("阅读方式")
    mode_label = st.radio(
        "输出模式",
        ["电脑端 · A4", "手机端 · 9:16"],
        horizontal=True,
        label_visibility="collapsed",
    )
    mode = "desktop" if mode_label.startswith("电脑端") else "mobile"
    st.markdown(
        '<p class="mode-note">电脑端保留静态页眉和约 40 个中文字的行宽；手机端使用更大字号、短行宽，并取消页眉。</p>',
        unsafe_allow_html=True,
    )
    short_title = st.text_input(
        "短页眉标题（可选）",
        max_chars=40,
        disabled=mode == "mobile",
        help="留空时会从封面标题自动截取。手机版不显示页眉。",
    )
    output_name = st.text_input("下载文件名", value="longread")
    st.markdown("&nbsp;", unsafe_allow_html=True)
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
        else:
            try:
                with st.spinner("正在排版和分页…"):
                    st.session_state.render_result = generate(markdown_source, mode, short_title)
                st.success("PDF 已生成。")
            except RenderError as error:
                st.error(str(error))
            except Exception:
                st.error("生成失败。请检查 Markdown 内容，或查看 Streamlit Cloud 日志。")

result = st.session_state.get("render_result")
if result:
    st.divider()
    title_col, action_col = st.columns([1.6, 1], gap="large")
    with title_col:
        st.subheader(result.title)
        metrics = st.columns(4)
        metrics[0].metric("页数", result.pages)
        metrics[1].metric("章节", result.sections)
        metrics[2].metric("模式", "A4" if result.mode == "desktop" else "9:16")
        metrics[3].metric("用时", f"{result.milliseconds / 1000:.1f}s")
    with action_col:
        filename = f"{safe_filename(output_name)}.{result.mode}.pdf"
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
        if result.blank_pages or result.overflows:
            st.warning("自动检查发现潜在版式问题，建议下载后复核。")

    st.subheader("预览")
    st.pdf(result.pdf, height=780)

with st.expander("支持范围与隐私"):
    st.markdown(
        """
        - 支持标题、段落、粗体、斜体、引用、列表、链接、图片、代码和简单表格。
        - 不适合复杂公式、宽表格或以图表为主的文档。
        - 不调用 DeepSeek、OpenAI 或其他模型 API；上传内容不会被发送给模型服务。
        - HTTPS 图片会在生成时从原地址载入；不需要远程请求时，请使用纯文本 Markdown。
        """
    )
