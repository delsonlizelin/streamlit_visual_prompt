from __future__ import annotations

import hashlib
import importlib
import re

import streamlit as st

import ui_components
from input_documents import InputDocumentError, extract_uploaded_document
from longread_pdf import RenderError, render_summary_long_image
from ui_components import clipboard_button, page_navigation
from url_documents import UrlDocumentError, fetch_url_document


SUMMARIZER_SYMBOLS = (
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "LENGTH_LABELS",
    "LENGTH_TARGETS",
    "MAX_CUSTOM_INSTRUCTION_CHARACTERS",
    "MAX_SOURCE_CHARACTERS",
    "MODE_LABELS",
    "STYLE_LABELS",
    "SummaryDocument",
    "SummaryError",
    "build_prompt_template",
    "summarize_markdown",
)
summarizer_backend = importlib.import_module("summarizer.deepseek")
if not all(hasattr(summarizer_backend, name) for name in SUMMARIZER_SYMBOLS):
    summarizer_backend = importlib.reload(summarizer_backend)

DEFAULT_BASE_URL = summarizer_backend.DEFAULT_BASE_URL
DEFAULT_MODEL = summarizer_backend.DEFAULT_MODEL
LENGTH_LABELS = summarizer_backend.LENGTH_LABELS
LENGTH_TARGETS = summarizer_backend.LENGTH_TARGETS
MAX_CUSTOM_INSTRUCTION_CHARACTERS = summarizer_backend.MAX_CUSTOM_INSTRUCTION_CHARACTERS
MAX_SOURCE_CHARACTERS = summarizer_backend.MAX_SOURCE_CHARACTERS
MODE_LABELS = summarizer_backend.MODE_LABELS
STYLE_LABELS = summarizer_backend.STYLE_LABELS
SummaryDocument = summarizer_backend.SummaryDocument
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


def long_image_download_button(export: dict, *, key: str) -> None:
    """Render the primary download action for the current long image."""
    artifact = export["artifact"]
    output_name = safe_filename(st.session_state.summary_output_name)
    st.download_button(
        "下载高清 PNG 长图",
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
def build_summary_long_image(document: SummaryDocument, mode: str):
    return render_summary_long_image(document, mode=mode)


def clear_generated_content() -> None:
    """Drop outputs that no longer match a newly loaded source."""
    st.session_state.pop("summary_result", None)
    st.session_state.pop("summary_export", None)
    st.session_state.pop("summary_export_error", None)
    st.session_state.pop("summary_source_digest", None)


def use_source(*, text: str, output_name: str, meta: dict) -> None:
    st.session_state.summary_markdown_source = text
    st.session_state.summary_output_name = output_name
    st.session_state.summary_input_meta = meta
    clear_generated_content()


def render_source_controls() -> None:
    st.markdown(
        '<div class="workbench-heading"><span>01</span><h2>添加原文</h2></div>',
        unsafe_allow_html=True,
    )
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
        uploaded = compatible_file_uploader(
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
        should_read_url = bool(
            article_url and (article_url != previous_attempt or retry_url)
        )
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


st.set_page_config(page_title="摘要长图", page_icon="📝", layout="wide")
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
compatible_file_uploader = getattr(
    ui_components,
    "compatible_file_uploader",
    st.file_uploader,
)
page_shell_styles()
page_navigation("summary")

if "summary_markdown_source" not in st.session_state:
    st.session_state.summary_markdown_source = SAMPLE
if "summary_output_name" not in st.session_state:
    st.session_state.summary_output_name = "summary"

api_key = secret_value("DEEPSEEK_API_KEY")
configured_model = secret_value("DEEPSEEK_MODEL", DEFAULT_MODEL)
base_url = secret_value("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)

st.title("把长文，变成一张读得完的图")
st.markdown(
    '<p class="intro">粘贴、上传或读取网页。保留结论、依据和必要边界，排成适合手机阅读和分享的高清长图。</p>',
    unsafe_allow_html=True,
)
if not api_key:
    st.info("尚未配置 DeepSeek API Key。页面可以读取和编辑原文，但暂时不能生成摘要长图。")

result = st.session_state.get("summary_result")
mode_order = ["standard", "section"]
mode_labels = [MODE_LABELS[mode] for mode in mode_order]
style_order = ["direct", "beginner"]
style_labels = [STYLE_LABELS[style] for style in style_order]
length_order = ["normal", "detailed"]
length_labels = [LENGTH_LABELS[length] for length in length_order]
language_options = {
    "跟随原文": "source",
    "简体中文": "zh",
    "English": "en",
}
model_options = {
    "DeepSeek V4 Flash": "deepseek-v4-flash",
    "DeepSeek V4 Pro": "deepseek-v4-pro",
}
if configured_model not in model_options.values():
    model_options[f"当前配置 · {configured_model}"] = configured_model

workspace_col, proof_col = st.columns([0.86, 1.14], gap="large")
with workspace_col:
    render_source_controls()
    st.markdown(
        '<div class="workbench-heading"><span>02</span><h2>编辑与提炼</h2></div>',
        unsafe_allow_html=True,
    )
    markdown_source = st.text_area(
        "原文（可编辑）",
        key="summary_markdown_source",
        height=280,
        help="上传文件或读取网页后，正文会出现在这里；你可以修改后再生成。",
    )
    current_source_digest = hashlib.sha256(markdown_source.encode("utf-8")).hexdigest()
    source_is_stale = bool(
        result and st.session_state.get("summary_source_digest") != current_source_digest
    )
    if source_is_stale:
        st.warning("原文已经修改。当前结果仍是上一版；重新生成即可更新。")
    generate_label = "重新生成长图" if result else "生成摘要长图"
    generate_clicked = st.button(
        generate_label,
        type="primary",
        icon=":material/summarize:",
        width="stretch",
        disabled=not api_key,
    )
    st.caption("使用下方当前方案生成；需要时再调整结构、讲述方式或详细程度。")

with workspace_col:
    selected_mode_label = st.segmented_control(
        "内容结构",
        mode_labels,
        default=mode_labels[0],
        key="summary_structure_choice",
        help="核心摘要会跨章节重组信息；按章节梳理会沿原文结构提炼。",
        width="stretch",
    )
    selected_mode = mode_order[mode_labels.index(selected_mode_label)]
    selected_style_label = st.segmented_control(
        "讲述方式",
        style_labels,
        default=style_labels[0],
        key="summary_style_choice",
        help="直接摘要保留术语和信息密度；零基础讲解会补背景、解释术语并展开逻辑。",
        width="stretch",
    )
    selected_style = style_order[style_labels.index(selected_style_label)]
    selected_length_label = st.segmented_control(
        "详细程度",
        length_labels,
        default=length_labels[0],
        key="summary_length_choice",
        help="详细展开会保留更多论据、数据、例子、限制和推理过程。",
        width="stretch",
    )
    selected_length = length_order[length_labels.index(selected_length_label)]
    chinese_target, english_target = LENGTH_TARGETS[
        (selected_mode, selected_style, selected_length)
    ]
    st.caption(
        f"当前方案：{selected_mode_label.replace('（推荐）', '')} · "
        f"{selected_style_label} · {selected_length_label.replace('（推荐）', '')}。"
        f"中文约 {chinese_target}；英文约 {english_target}。"
    )
    configured_model_index = list(model_options.values()).index(configured_model)
    with st.expander("更多设置 · 语言、模型与补充要求"):
        custom_instructions = st.text_area(
            "补充要求（可选）",
            key="summary_custom_instructions",
            height=112,
            max_chars=MAX_CUSTOM_INSTRUCTION_CHARACTERS,
            placeholder="例如：重点解释数据变化；保留所有行动建议；用更客观的语气。",
            help=(
                "补充要求会加入摘要 Prompt，用于指定关注重点、语气或展开方式；"
                "不能覆盖忠实性、内容结构和输出格式规则。"
            ),
        )
        language_col, model_col = st.columns(2, gap="medium")
        with language_col:
            language_label = st.selectbox(
                "输出语言",
                list(language_options),
                key="summary_language_label",
            )
        with model_col:
            model_label = st.selectbox(
                "摘要模型",
                list(model_options),
                index=configured_model_index,
                key="summary_model_label",
            )
        model = model_options[model_label]
        st.caption("V4 Pro 的 API 单价高于 V4 Flash；默认选择遵循部署配置。")
        st.text_input("下载文件名", key="summary_output_name")
        st.caption(
            "复制的是当前结构、讲述方式、详细程度、补充要求、语言和系统规则；"
            "正文位置使用占位符。"
        )
        clipboard_button(
            build_prompt_template(
                mode=selected_mode,
                language=language_options[language_label],
                style=selected_style,
                length=selected_length,
                custom_instructions=custom_instructions,
            ),
            "复制完整 Prompt",
            key="summary-prompt-template",
        )
        st.markdown(
            "只有点击“生成摘要长图”后，当前原文才会发送到 DeepSeek。"
            "API Key 不会显示或写入文件。"
        )
    st.caption(
        f"{language_label} · {model_label} · 原文上限 "
        f"{MAX_SOURCE_CHARACTERS // 10_000} 万字符"
    )

if generate_clicked:
    if not markdown_source.strip():
        st.error("请先添加原文。")
    elif len(markdown_source) > MAX_SOURCE_CHARACTERS:
        st.error(f"文稿超过 {MAX_SOURCE_CHARACTERS // 10_000} 万字符，请拆分后再摘要。")
    else:
        try:
            with st.spinner("正在提炼重点并排版长图…"):
                generated_result = summarize_markdown(
                    markdown_source,
                    mode=selected_mode,
                    language=language_options[language_label],
                    style=selected_style,
                    length=selected_length,
                    custom_instructions=custom_instructions,
                    api_key=api_key,
                    model=model,
                    base_url=base_url,
                )
                summary_digest = hashlib.sha256(
                    generated_result.document.to_json().encode("utf-8")
                ).hexdigest()
                st.session_state.summary_result = generated_result
                st.session_state.summary_source_digest = current_source_digest
                st.session_state.pop("summary_export", None)
                st.session_state.pop("summary_export_error", None)
                try:
                    artifact = build_summary_long_image(generated_result.document, "mobile")
                except RenderError as error:
                    # Preserve the paid model result so layout can be retried locally.
                    st.session_state.summary_export_error = str(error)
                else:
                    st.session_state.summary_export = {
                        "digest": summary_digest,
                        "mode": "mobile",
                        "artifact": artifact,
                    }
            st.rerun()
        except SummaryError as error:
            st.error(str(error))
        except Exception:
            st.error("长图生成失败，请查看 Streamlit Cloud 日志。")

with proof_col:
    st.markdown(
        '<div class="workbench-heading"><span>03</span><h2>结果预览</h2></div>',
        unsafe_allow_html=True,
    )
    if not result:
        st.markdown(
            """
            <section class="summary-empty" aria-label="尚未生成摘要">
              <div class="summary-empty-rule" aria-hidden="true"></div>
              <h3>长图会在这里成形</h3>
              <p>生成后直接预览完整长图。分区数量和篇幅跟随原文，不套固定模板。</p>
            </section>
            """,
            unsafe_allow_html=True,
        )
    else:
        summary_digest = hashlib.sha256(result.document.to_json().encode("utf-8")).hexdigest()
        export = st.session_state.get("summary_export")
        valid_export = bool(export and export.get("digest") == summary_digest)

        if source_is_stale:
            st.info("原文已经修改；这里仍是上一版长图。重新生成即可更新。")
        elif valid_export:
            st.success("内容与版式已经完成，可以保存或分享。", icon=":material/check_circle:")

        if not valid_export:
            export_error = st.session_state.get("summary_export_error")
            if export_error:
                st.error(f"摘要已经保留，但长图排版失败：{export_error}")
            else:
                st.warning("摘要内容已经生成，但长图还没有排版完成。")
            if st.button(
                "重新排版长图",
                icon=":material/refresh:",
                width="stretch",
            ):
                try:
                    with st.spinner("正在排版长图…"):
                        artifact = build_summary_long_image(result.document, "mobile")
                        st.session_state.summary_export = {
                            "digest": summary_digest,
                            "mode": "mobile",
                            "artifact": artifact,
                        }
                        st.session_state.pop("summary_export_error", None)
                    st.rerun()
                except RenderError as error:
                    st.error(str(error))
                except Exception:
                    st.error("长图排版失败，请查看 Streamlit Cloud 日志。")
        else:
            artifact = export["artifact"]
            output_name = safe_filename(st.session_state.summary_output_name)
            action_col, download_col = st.columns(2, gap="medium")
            with action_col:
                native_image_share(
                    artifact.png,
                    f"{output_name}.summary.png",
                    key="summary-native-image-share",
                )
            with download_col:
                long_image_download_button(export, key="summary-export-download-inline")
            st.caption(
                f"{artifact.width} × {artifact.height} px · "
                "iPhone 或 iPad 可点“分享长图”，也可以长按图片存储。"
            )
            st.image(artifact.png, width="stretch")

        with st.expander("生成信息"):
            st.caption(
                f"{result.model} · {result.completion_tokens or '—'} 输出 Tokens · "
                f"{result.milliseconds / 1000:.1f} 秒"
            )
