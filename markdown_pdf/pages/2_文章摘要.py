from __future__ import annotations

import hashlib
import importlib
import json
import logging
import re
from urllib.parse import urlsplit

import streamlit as st

from dataclasses import asdict

import ui_components
from longread_pdf import RenderError, render_summary_long_image
from summarizer.quality import lint_summary_document
from ui_components import clipboard_button, page_navigation


LOGGER = logging.getLogger(__name__)


SOURCE_SYMBOLS = (
    "KIND_LABELS",
    "Material",
    "SourceDocument",
    "SourceError",
    "load_text",
    "load_upload",
    "load_url",
    "material_task_config",
    "suggest_mode",
    "suggested_language",
)
sources_backend = importlib.import_module("sources")
if not all(hasattr(sources_backend, name) for name in SOURCE_SYMBOLS):
    sources_backend = importlib.reload(sources_backend)
KIND_LABELS = sources_backend.KIND_LABELS
Material = sources_backend.Material
SourceDocument = sources_backend.SourceDocument
SourceError = sources_backend.SourceError
load_text = sources_backend.load_text
load_upload = sources_backend.load_upload
load_url = sources_backend.load_url
material_task_config = sources_backend.material_task_config
suggest_mode = sources_backend.suggest_mode
suggested_language = sources_backend.suggested_language

app_settings = importlib.import_module("app_settings")
if not hasattr(app_settings, "resolve_settings"):
    app_settings = importlib.reload(app_settings)


SUMMARIZER_SYMBOLS = (
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "GENERATION_CAPTIONS",
    "GENERATION_LABELS",
    "LENGTH_LABELS",
    "LENGTH_CAPTIONS",
    "LENGTH_TARGETS",
    "MAX_CUSTOM_INSTRUCTION_CHARACTERS",
    "MAX_SOURCE_CHARACTERS",
    "MODE_LABELS",
    "MODE_CAPTIONS",
    "STYLE_LABELS",
    "STYLE_CAPTIONS",
    "SummaryDocument",
    "SummaryError",
    "SummaryResult",
    "build_prompt_template",
    "build_request_fingerprint",
    "parse_summary_document",
    "resolve_generation",
    "revise_summary_with_feedback",
    "summarize_markdown",
)
summarizer_backend = importlib.import_module("summarizer.deepseek")
if not all(hasattr(summarizer_backend, name) for name in SUMMARIZER_SYMBOLS):
    summarizer_backend = importlib.reload(summarizer_backend)

DEFAULT_BASE_URL = summarizer_backend.DEFAULT_BASE_URL
DEFAULT_MODEL = summarizer_backend.DEFAULT_MODEL
GENERATION_CAPTIONS = summarizer_backend.GENERATION_CAPTIONS
GENERATION_LABELS = summarizer_backend.GENERATION_LABELS
LENGTH_LABELS = summarizer_backend.LENGTH_LABELS
LENGTH_CAPTIONS = summarizer_backend.LENGTH_CAPTIONS
LENGTH_TARGETS = summarizer_backend.LENGTH_TARGETS
MAX_CUSTOM_INSTRUCTION_CHARACTERS = summarizer_backend.MAX_CUSTOM_INSTRUCTION_CHARACTERS
MAX_SOURCE_CHARACTERS = summarizer_backend.MAX_SOURCE_CHARACTERS
MODE_LABELS = summarizer_backend.MODE_LABELS
MODE_CAPTIONS = summarizer_backend.MODE_CAPTIONS
STYLE_LABELS = summarizer_backend.STYLE_LABELS
STYLE_CAPTIONS = summarizer_backend.STYLE_CAPTIONS
SummaryDocument = summarizer_backend.SummaryDocument
SummaryError = summarizer_backend.SummaryError
SummaryResult = summarizer_backend.SummaryResult
build_prompt_template = summarizer_backend.build_prompt_template
build_request_fingerprint = summarizer_backend.build_request_fingerprint
parse_summary_document = summarizer_backend.parse_summary_document
resolve_generation = summarizer_backend.resolve_generation
revise_summary_with_feedback = summarizer_backend.revise_summary_with_feedback
summarize_markdown = summarizer_backend.summarize_markdown


def looks_like_article_url(value: str) -> bool:
    """Recognize a URL pasted by itself without treating prose as a link."""
    cleaned = value.strip()
    if not cleaned or re.search(r"\s", cleaned):
        return False
    candidate = cleaned if "://" in cleaned else f"https://{cleaned}"
    try:
        parsed = urlsplit(candidate)
        return bool(
            parsed.scheme.lower() in {"http", "https"}
            and parsed.hostname
            and "." in parsed.hostname
            and not parsed.username
            and not parsed.password
        )
    except ValueError:
        return False


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", value).strip(" ._")
    return (cleaned or "summary")[:100]


def long_image_download_button(export: dict, *, key: str, stale: bool = False) -> None:
    """Render the primary download action for the current long image."""
    artifact = export["artifact"]
    output_name = safe_filename(st.session_state.summary_output_name)
    st.download_button(
        "下载上一版 PNG 长图" if stale else "下载高清 PNG 长图",
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


def build_summary_long_image(document: SummaryDocument, mode: str):
    """Render once per explicit action; session state already retains the PNG.

    Keeping this outside ``st.cache_data`` avoids hashing dynamically reloaded
    summary dataclasses during Streamlit Cloud hot updates.
    """
    return render_summary_long_image(document, mode=mode)


def clear_generated_content() -> None:
    """Drop outputs that no longer match a newly loaded source."""
    st.session_state.pop("summary_result", None)
    st.session_state.pop("summary_export", None)
    st.session_state.pop("summary_export_error", None)
    st.session_state.pop("summary_source_digest", None)
    st.session_state.pop("summary_request_fingerprint", None)
    st.session_state.pop("summary_model_original_json", None)
    st.session_state.pop("summary_editor_json", None)
    st.session_state.pop("summary_editor_pending_json", None)
    st.session_state.pop("summary_editor_seed_digest", None)
    st.session_state.pop("summary_revision_count", None)
    st.session_state.pop("summary_user_feedback", None)
    st.session_state.pop("summary_clear_user_feedback", None)


LANGUAGE_LABEL_FOR = {"source": "跟随原文", "zh": "简体中文", "en": "English"}


def apply_language_suggestion(material: Material) -> None:
    """Default non-Chinese transcripts to Chinese, without overriding a manual choice."""
    if not st.session_state.get("summary_language_manual"):
        st.session_state.summary_language_label = LANGUAGE_LABEL_FOR[suggested_language(material)]


def mark_language_manual() -> None:
    st.session_state.summary_language_manual = True


def mark_mode_manual() -> None:
    st.session_state.summary_mode_manual = True


def apply_mode_suggestion(text: str, material: Material) -> None:
    """Pre-select the mode that fits the material; never override the reader's own pick."""
    mode, reason = suggest_mode(text, material)
    st.session_state.summary_mode_suggestion = {"mode": mode, "reason": reason}
    if not st.session_state.get("summary_mode_manual"):
        st.session_state.summary_structure_choice = MODE_LABELS[mode]


def use_source(document: SourceDocument, *, source: str) -> None:
    st.session_state.summary_markdown_source = document.text
    st.session_state.summary_output_name = safe_filename(document.output_name)
    st.session_state.summary_input_meta = {
        "kind": KIND_LABELS[document.material.kind],
        "is_pdf": document.material.kind == "document" and document.pages > 0,
        "pages": document.pages,
        "text_pages": document.text_pages,
        "characters": document.characters,
        "source": source,
        "site": document.site,
        "notices": list(document.notices),
        "material": asdict(document.material),
        "digest": hashlib.sha256(document.text.encode("utf-8")).hexdigest(),
    }
    st.session_state.pop("summary_material_override", None)
    # A new source gets a fresh suggestion; a manual pick only holds for the source it was made on.
    st.session_state.pop("summary_mode_manual", None)
    apply_language_suggestion(document.material)
    apply_mode_suggestion(document.text, document.material)
    clear_generated_content()


def show_source_error(error: SourceError) -> None:
    st.error(str(error))
    if getattr(error, "hint", ""):
        st.caption(error.hint)


def progress_reporter(status, action: str):  # noqa: ANN001, ANN201
    """Turn streaming progress into a live status label."""

    def report(elapsed: float, reasoning_characters: int, content_characters: int) -> None:
        phase = "正在写摘要" if content_characters else ("正在思考" if reasoning_characters else "等待响应")
        status.update(label=f"{action} · {phase} · {elapsed:.0f} 秒")

    return report


def use_url(url: str) -> None:
    """Read a web, WeChat or YouTube URL; replace the editor only after it succeeds."""
    with st.spinner("正在读取…"):
        document = load_url(
            url,
            youtube_enabled=settings.youtube_enabled,
            youtube_proxy_url=settings.youtube_proxy_url,
        )
    use_source(document, source="url")
    st.session_state.summary_loaded_article_url = url
    st.session_state.summary_article_url = url
    st.session_state.summary_last_url_attempt = url


def apply_local_summary_document(document: SummaryDocument, previous_result: SummaryResult) -> None:
    """Store an edited document and render it without another model request."""
    edited_result = SummaryResult(
        document=document,
        model=previous_result.model,
        prompt_tokens=previous_result.prompt_tokens,
        completion_tokens=previous_result.completion_tokens,
        milliseconds=previous_result.milliseconds,
    )
    edited_digest = hashlib.sha256(document.to_json().encode("utf-8")).hexdigest()
    st.session_state.summary_result = edited_result
    st.session_state.summary_editor_seed_digest = edited_digest
    st.session_state.summary_editor_pending_json = json.dumps(
        document.to_dict(),
        ensure_ascii=False,
        indent=2,
    )
    st.session_state.pop("summary_export", None)
    st.session_state.pop("summary_export_error", None)
    artifact = build_summary_long_image(document, "tablet")
    st.session_state.summary_export = {
        "digest": edited_digest,
        "mode": "tablet",
        "artifact": artifact,
    }


def store_model_summary_result(
    result: SummaryResult,
    *,
    source_digest: str,
    request_fingerprint: str,
    is_revision: bool = False,
) -> None:
    """Store a model result and attempt its deterministic long-image render."""
    summary_digest = hashlib.sha256(result.document.to_json().encode("utf-8")).hexdigest()
    st.session_state.summary_result = result
    st.session_state.summary_source_digest = source_digest
    st.session_state.summary_request_fingerprint = request_fingerprint
    st.session_state.summary_model_original_json = json.dumps(
        result.document.to_dict(),
        ensure_ascii=False,
        indent=2,
    )
    if is_revision:
        st.session_state.summary_revision_count = (
            int(st.session_state.get("summary_revision_count", 0)) + 1
        )
    else:
        st.session_state.pop("summary_revision_count", None)
    st.session_state.pop("summary_export", None)
    st.session_state.pop("summary_export_error", None)
    try:
        artifact = build_summary_long_image(result.document, "tablet")
    except RenderError as error:
        # Preserve the paid model result so layout can be retried locally.
        st.session_state.summary_export_error = str(error)
    except Exception as error:
        LOGGER.exception("Unexpected long-image export failure")
        st.session_state.summary_export_error = (
            f"长图渲染发生意外错误（{type(error).__name__}）。"
            "摘要已经保留，请点击“重新排版长图”重试。"
        )
    else:
        st.session_state.summary_export = {
            "digest": summary_digest,
            "mode": "tablet",
            "artifact": artifact,
        }


def render_source_controls() -> None:
    st.markdown(
        '<div class="workbench-heading"><span>01</span><h2>添加原文</h2></div>',
        unsafe_allow_html=True,
    )
    source_labels = {
        "paste": "粘贴文字",
        "upload": "上传文件",
        "url": "网址",
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
                        document = load_upload(uploaded.name, payload)
                    use_source(document, source="upload")
                    st.session_state.summary_uploaded_digest = digest
                    st.rerun()
                except SourceError as error:
                    show_source_error(error)

    elif source_method == "url":
        stored_article_url = str(st.session_state.get("summary_article_url", ""))
        article_url = auto_article_url_input(
            stored_article_url,
            key="summary_article_url_input",
            label="网址",
            placeholder=(
                "公众号、网页或 YouTube 链接"
                if settings.youtube_enabled
                else "https://mp.weixin.qq.com/s/..."
            ),
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
                use_url(article_url)
                st.rerun()
            except SourceError as error:
                show_source_error(error)
        if (
            article_url != st.session_state.get("summary_loaded_article_url")
            or st.session_state.get("summary_input_meta", {}).get("source") != "url"
        ):
            st.warning("当前网址尚未成功读取；编辑器可能仍是上一篇原文。请重新读取或切换来源。")
        st.caption(
            (
                "支持公开网页、微信公众号文章和 YouTube 字幕；"
                if settings.youtube_enabled
                else "支持公开网页和微信公众号文章；"
            )
            + "粘贴完整网址后会自动读取。登录、验证码或访问频率限制仍可能导致失败。"
        )

    input_meta = st.session_state.get("summary_input_meta")
    if input_meta:
        page_note = f" · {input_meta['pages']} 页" if input_meta.get("pages") else ""
        site_note = f" · {input_meta['site']}" if input_meta.get("site") else ""
        source_edited = input_meta.get("digest") != hashlib.sha256(
            st.session_state.summary_markdown_source.encode("utf-8")
        ).hexdigest()
        edit_note = " · 已在编辑器修改" if source_edited else ""
        notice_note = "".join(f" · {notice}" for notice in input_meta.get("notices", []))
        st.caption(
            f"已读取 {input_meta['kind']}{page_note}{site_note}{notice_note} · "
            f"原文 {input_meta['characters']:,} 字符{edit_note}"
        )
        missing_pdf_pages = (
            input_meta.get("is_pdf", input_meta.get("kind") == "PDF")
            and input_meta.get("text_pages", input_meta.get("pages"))
            < input_meta.get("pages", 0)
        )
        if missing_pdf_pages:
            st.warning(
                f"PDF 共 {input_meta['pages']} 页，仅 {input_meta['text_pages']} 页提取出文字。"
                "请检查下方原文是否缺页；扫描页需先做 OCR，再生成摘要。"
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
    st.session_state.summary_markdown_source = ""
if "summary_output_name" not in st.session_state:
    st.session_state.summary_output_name = "summary"

settings = app_settings.resolve_settings(
    {name: secret_value(name) for name in app_settings.SETTING_NAMES}
)
api_key = settings.api_key
model = settings.model
base_url = settings.base_url

st.title("把长文，变成一张读得完的图")
st.markdown(
    '<p class="intro">添加长文，得到可直接保存与分享的手机摘要长图。</p>',
    unsafe_allow_html=True,
)
if not api_key:
    st.info("未配置 DeepSeek API Key；可编辑原文，但无法生成。")

result = st.session_state.get("summary_result")
mode_order = ["standard", "story", "howto", "section"]
mode_labels = [MODE_LABELS[mode] for mode in mode_order]
if st.session_state.get("summary_structure_choice") not in (None, *mode_labels):
    st.session_state.summary_structure_choice = mode_labels[0]
style_order = ["direct", "beginner"]
style_labels = [STYLE_LABELS[style] for style in style_order]
length_order = ["normal", "detailed"]
length_labels = [LENGTH_LABELS[length] for length in length_order]
language_options = {
    "跟随原文": "source",
    "简体中文": "zh",
    "English": "en",
}
generation_order = ["auto", "fast", "careful"]
generation_labels = [GENERATION_LABELS[choice] for choice in generation_order]
if st.session_state.get("summary_generation_label") not in (None, *generation_labels):
    st.session_state.summary_generation_label = generation_labels[0]
material_order = ["auto", "article", "document", "transcript"]

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
        placeholder="粘贴文章正文，或在上方上传文件、输入文章网址。",
        help="上传文件或读取网页后，正文会出现在这里；你可以修改后再生成。",
    )
    pasted_url_pending = bool(
        st.session_state.get("summary_source_method") == "paste"
        and looks_like_article_url(markdown_source)
    )
    if pasted_url_pending:
        st.info("检测到你粘贴的是网址。先读取内容，再生成摘要。")
        if st.button("读取这个网址", icon=":material/article:", width="stretch"):
            try:
                use_url(markdown_source.strip())
                st.rerun()
            except SourceError as error:
                show_source_error(error)
    url_source_pending = bool(
        st.session_state.get("summary_source_method") == "url"
        and (
            st.session_state.get("summary_article_url", "")
            != st.session_state.get("summary_loaded_article_url")
            or st.session_state.get("summary_input_meta", {}).get("source") != "url"
        )
    )
    input_source_pending = pasted_url_pending or url_source_pending
    st.caption(f"当前原文 · {len(markdown_source.strip()):,} 字符")
    loaded_meta = st.session_state.get("summary_input_meta") or {}
    if loaded_meta.get("material"):
        detected_material = Material(**loaded_meta["material"])
    else:
        detected_material = load_text(markdown_source).material
        pasted_digest = hashlib.sha256(markdown_source.encode("utf-8")).hexdigest()
        if markdown_source.strip() and st.session_state.get("summary_mode_suggest_digest") != pasted_digest:
            st.session_state.summary_mode_suggest_digest = pasted_digest
            apply_mode_suggestion(markdown_source, detected_material)
    current_source_digest = hashlib.sha256(markdown_source.encode("utf-8")).hexdigest()
    source_has_changed = bool(
        result and st.session_state.get("summary_source_digest") != current_source_digest
    )

with workspace_col:
    selected_mode_label = st.segmented_control(
        "摘要方式",
        mode_labels,
        default=mode_labels[0],
        key="summary_structure_choice",
        on_change=mark_mode_manual,
        help=(
            "先看结论：结论是什么；来龙去脉：发生了什么；上手步骤：怎么做；逐章梳理：每章讲什么。"
            "读取原文后会按材料自动建议一种。"
        ),
        width="stretch",
    )
    selected_mode = mode_order[mode_labels.index(selected_mode_label)]
    suggestion = st.session_state.get("summary_mode_suggestion") or {}
    suggestion_note = (
        f"已按材料建议（{suggestion['reason']}） · "
        if suggestion.get("mode") == selected_mode and suggestion.get("reason")
        else ""
    )
    st.caption(suggestion_note + MODE_CAPTIONS[selected_mode])
    selected_style_label = st.segmented_control(
        "讲述方式",
        style_labels,
        default=style_labels[0],
        key="summary_style_choice",
        help="直接摘要保留术语和信息密度；易懂解释只用更直白的语言展开原文已有背景与逻辑。",
        width="stretch",
    )
    selected_style = style_order[style_labels.index(selected_style_label)]
    st.caption(STYLE_CAPTIONS[selected_style])
    selected_length_label = st.segmented_control(
        "详细程度",
        length_labels,
        default=length_labels[0],
        key="summary_length_choice",
        help="详细展开会保留更多论据、数据、例子、限制和推理过程。",
        width="stretch",
    )
    selected_length = length_order[length_labels.index(selected_length_label)]
    st.caption(LENGTH_CAPTIONS[selected_length])
    chinese_target, english_target = LENGTH_TARGETS[
        (selected_mode, selected_style, selected_length)
    ]
    st.caption(
        f"篇幅参考 · 中文 {chinese_target} · English {english_target}"
    )
    generate_clicked = st.button(
        "重新生成摘要长图" if result else "生成摘要长图",
        type="primary",
        icon=":material/summarize:",
        width="stretch",
        disabled=(
            not api_key
            or not markdown_source.strip()
            or len(markdown_source) > MAX_SOURCE_CHARACTERS
            or pasted_url_pending
            or url_source_pending
        ),
    )
    if len(markdown_source) > MAX_SOURCE_CHARACTERS:
        st.warning(f"原文超过 {MAX_SOURCE_CHARACTERS // 10_000} 万字符，请拆分后再生成。")
    else:
        st.caption("点击后发送当前原文与方案到 DeepSeek。")
    material_override = st.session_state.get("summary_material_override", "auto")
    material_kind = (
        detected_material.kind if material_override in (None, "auto") else material_override
    )
    effective_material = Material(**{**asdict(detected_material), "kind": material_kind})
    generation_choice = generation_order[
        generation_labels.index(
            st.session_state.get("summary_generation_label", generation_labels[0])
        )
    ]
    thinking, reasoning_effort = resolve_generation(
        generation_choice,
        mode=selected_mode,
        material_kind=material_kind,
        source_characters=len(markdown_source.strip()),
    )
    resolved_generation = "仔细" if thinking else "快速"
    collapsed_language = str(st.session_state.get("summary_language_label", "跟随原文"))
    collapsed_generation = (
        f"自动 · {resolved_generation}" if generation_choice == "auto" else resolved_generation
    )
    with st.expander(f"其他设置 · {collapsed_language} · {collapsed_generation}"):
        custom_instructions = st.text_area(
            "补充要求（可选）",
            key="summary_custom_instructions",
            height=112,
            max_chars=MAX_CUSTOM_INSTRUCTION_CHARACTERS,
            placeholder="例如：重点解释数据变化；保留行动建议。",
            help=(
                "补充要求会加入摘要 Prompt，用于指定关注重点、语气或展开方式；"
                "不能覆盖忠实性、内容结构和输出格式规则。"
            ),
        )
        language_col, generation_col = st.columns(2, gap="medium")
        with language_col:
            language_label = st.selectbox(
                "输出语言",
                list(language_options),
                key="summary_language_label",
                on_change=mark_language_manual,
            )
        with generation_col:
            st.selectbox(
                "生成方式",
                generation_labels,
                key="summary_generation_label",
                help="快速不启用深度思考；仔细启用深度思考（DeepSeek V4.1 Flash），更慢但更稳。",
            )
        st.caption(GENERATION_CAPTIONS[generation_choice])
        st.selectbox(
            "材料类型",
            material_order,
            format_func=lambda kind: (
                f"自动识别 · {KIND_LABELS[detected_material.kind]}"
                if kind == "auto"
                else KIND_LABELS[kind]
            ),
            key="summary_material_override",
            help="字幕或转写稿会提示模型注意识别错误、缺少说话人标注，并逐句核对“谁说了什么”。",
        )
        st.text_input("下载文件名", key="summary_output_name")
        clipboard_button(
            build_prompt_template(
                markdown_source,
                mode=selected_mode,
                language=language_options[language_label],
                style=selected_style,
                length=selected_length,
                custom_instructions=custom_instructions,
                material=material_task_config(effective_material),
            ),
            "复制当前完整 Prompt",
            key="summary-prompt-template",
        )
        st.caption("复制内容包含当前原文、选项和完整生成规则。")
    current_request_fingerprint = build_request_fingerprint(
        markdown_source,
        mode=selected_mode,
        language=language_options[language_label],
        style=selected_style,
        length=selected_length,
        custom_instructions=custom_instructions,
        model=model,
        thinking=thinking,
        reasoning_effort=reasoning_effort,
        material=material_task_config(effective_material),
    )
    request_is_stale = bool(
        result
        and (
            input_source_pending
            or st.session_state.get("summary_request_fingerprint")
            != current_request_fingerprint
        )
    )

if generate_clicked:
    if pasted_url_pending or url_source_pending:
        st.error("请先读取文章正文，再生成摘要。")
    elif not markdown_source.strip():
        st.error("请先添加原文。")
    elif len(markdown_source) > MAX_SOURCE_CHARACTERS:
        st.error(f"文稿超过 {MAX_SOURCE_CHARACTERS // 10_000} 万字符，请拆分后再摘要。")
    else:
        try:
            action = "仔细提炼（约 1–2 分钟）" if thinking else "正在提炼"
            with st.status(action, expanded=False) as status:
                generated_result = summarize_markdown(
                    markdown_source,
                    mode=selected_mode,
                    language=language_options[language_label],
                    style=selected_style,
                    length=selected_length,
                    custom_instructions=custom_instructions,
                    material=material_task_config(effective_material),
                    api_key=api_key,
                    model=model,
                    thinking=thinking,
                    reasoning_effort=reasoning_effort,
                    base_url=base_url,
                    on_progress=progress_reporter(status, action),
                )
                status.update(label="正在排版长图…")
                store_model_summary_result(
                    generated_result,
                    source_digest=current_source_digest,
                    request_fingerprint=current_request_fingerprint,
                )
                st.session_state.summary_generation_note = (
                    f"思考 · {reasoning_effort}" if thinking else "快速 · 非思考"
                )
            st.rerun()
        except SummaryError as error:
            st.error(str(error))
        except Exception as error:
            LOGGER.exception("Unexpected summary generation failure")
            st.error(
                f"摘要生成发生意外错误（{type(error).__name__}）。"
                "详细堆栈已写入 Streamlit Cloud 日志。"
            )

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
              <h3>摘要会在这里出现</h3>
              <p>添加原文并选择提炼方式后，生成的长图可在这里预览、保存和分享。</p>
            </section>
            """,
            unsafe_allow_html=True,
        )
    else:
        summary_digest = hashlib.sha256(result.document.to_json().encode("utf-8")).hexdigest()
        export = st.session_state.get("summary_export")
        valid_export = bool(export and export.get("digest") == summary_digest)

        quality_report = lint_summary_document(
            result.document,
            None if source_has_changed else markdown_source,
        )
        if source_has_changed:
            st.info("当前显示上一版摘要：原文已修改，本次只检查摘要结构。重新生成后再分享新版长图。")
        elif input_source_pending:
            st.info("当前显示上一版摘要：新文章尚未成功读取。读取正文后再生成。")
        elif request_is_stale:
            st.info("当前显示上一版摘要：生成方案已改变。重新生成后再分享新版长图。")
        elif valid_export and quality_report.passed:
            st.success("长图已完成，自动检查未发现明显问题。", icon=":material/check_circle:")

        if not quality_report.passed:
            st.warning(f"自动检查发现 {len(quality_report.issues)} 项需要人工核对。")
            with st.expander("查看自动检查结果"):
                for issue in quality_report.issues:
                    st.markdown(f"- {issue.message}")
                if not source_has_changed:
                    st.caption(
                        "数字检查只看摘要数字能否在原文找到相同写法或相同数值（会换算万、亿、"
                        "million 等单位），不判断数字的上下文、主体或因果关系。"
                    )
            revise_clicked = st.button(
                "按检查结果修订",
                icon=":material/auto_fix_high:",
                width="stretch",
                disabled=bool(not api_key or source_has_changed or request_is_stale),
                key="summary-revise-from-quality",
            )
            if source_has_changed or request_is_stale:
                st.caption("原文或生成方案已改变，请先重新生成，再使用检查反馈修订。")
            elif not api_key:
                st.caption("配置 DeepSeek API Key 后可按检查结果修订。")
            else:
                st.caption(
                    "会将当前原文、摘要和上述反馈发送到 DeepSeek；"
                    "保留未被指出的有效内容。"
                )
            if revise_clicked:
                try:
                    with st.spinner("正在依据检查结果修订并排版…"):
                        revised_result = revise_summary_with_feedback(
                            markdown_source,
                            result.document,
                            tuple(
                                f"{issue.code}: {issue.message}"
                                for issue in quality_report.issues
                            ),
                            mode=selected_mode,
                            language=language_options[language_label],
                            style=selected_style,
                            length=selected_length,
                            custom_instructions=custom_instructions,
                            material=material_task_config(effective_material),
                            api_key=api_key,
                            model=model,
                            thinking=thinking,
                            reasoning_effort=reasoning_effort,
                            base_url=base_url,
                        )
                        store_model_summary_result(
                            revised_result,
                            source_digest=current_source_digest,
                            request_fingerprint=current_request_fingerprint,
                            is_revision=True,
                        )
                    st.rerun()
                except SummaryError as error:
                    st.error(f"修订失败：{error}")
                except Exception as error:
                    LOGGER.exception("Unexpected summary revision failure")
                    st.error(
                        f"摘要修订发生意外错误（{type(error).__name__}）。"
                        "详细堆栈已写入 Streamlit Cloud 日志。"
                    )
        if selected_mode == "story" or material_kind == "transcript":
            attribution_clicked = st.button(
                "核对归属（谁说、谁指控谁）",
                icon=":material/fact_check:",
                width="stretch",
                disabled=bool(not api_key or source_has_changed or request_is_stale),
                key="summary-check-attribution",
                help="让模型逐条回到原文核对主语、指控方与被指控方，只修改归属有问题的条目。",
            )
            if attribution_clicked:
                try:
                    action = "正在核对归属"
                    with st.status(action, expanded=False) as status:
                        revised_result = revise_summary_with_feedback(
                            markdown_source,
                            result.document,
                            ("核对每条的主语、指控方与被指控方是否与原文一致。",),
                            mode=selected_mode,
                            language=language_options[language_label],
                            style=selected_style,
                            length=selected_length,
                            custom_instructions=custom_instructions,
                            material=material_task_config(effective_material),
                            api_key=api_key,
                            model=model,
                            thinking=thinking,
                            reasoning_effort=reasoning_effort,
                            base_url=base_url,
                            feedback_kind="attribution",
                            on_progress=progress_reporter(status, action),
                        )
                        store_model_summary_result(
                            revised_result,
                            source_digest=current_source_digest,
                            request_fingerprint=current_request_fingerprint,
                            is_revision=True,
                        )
                    st.rerun()
                except SummaryError as error:
                    st.error(f"核对失败：{error}")
                except Exception as error:
                    LOGGER.exception("Unexpected attribution check failure")
                    st.error(
                        f"核对归属发生意外错误（{type(error).__name__}）。"
                        "详细堆栈已写入 Streamlit Cloud 日志。"
                    )
        if st.session_state.pop("summary_clear_user_feedback", False):
            st.session_state.summary_user_feedback = ""
        with st.expander("调整这份摘要", icon=":material/tune:"):
            user_feedback = st.text_area(
                "你希望怎么改？",
                key="summary_user_feedback",
                max_chars=500,
                height=100,
                placeholder="例如：结论再短一点；补充原文对数据来源的限制。",
            )
            st.caption("会将当前原文、摘要和这条要求发送到 DeepSeek，再生成一版完整摘要。")
            revise_from_user = st.button(
                "按我的要求修订",
                icon=":material/auto_fix_high:",
                width="stretch",
                disabled=bool(
                    not api_key
                    or source_has_changed
                    or request_is_stale
                    or not user_feedback.strip()
                ),
                key="summary-revise-from-user",
            )
            if source_has_changed or request_is_stale:
                st.caption("原文或生成方案已改变，请先重新生成，再修改这份摘要。")
            if revise_from_user:
                try:
                    with st.spinner("正在按你的要求修订并排版…"):
                        revised_result = revise_summary_with_feedback(
                            markdown_source,
                            result.document,
                            (user_feedback,),
                            mode=selected_mode,
                            language=language_options[language_label],
                            style=selected_style,
                            length=selected_length,
                            custom_instructions=custom_instructions,
                            material=material_task_config(effective_material),
                            api_key=api_key,
                            model=model,
                            thinking=thinking,
                            reasoning_effort=reasoning_effort,
                            base_url=base_url,
                            feedback_kind="user",
                        )
                        store_model_summary_result(
                            revised_result,
                            source_digest=current_source_digest,
                            request_fingerprint=current_request_fingerprint,
                            is_revision=True,
                        )
                        st.session_state.summary_clear_user_feedback = True
                    st.rerun()
                except SummaryError as error:
                    st.error(f"修订失败：{error}")
                except Exception as error:
                    LOGGER.exception("Unexpected user-directed summary revision failure")
                    st.error(
                        f"摘要修订发生意外错误（{type(error).__name__}）。"
                        "详细堆栈已写入 Streamlit Cloud 日志。"
                    )
        pending_editor_json = st.session_state.pop("summary_editor_pending_json", None)
        if pending_editor_json is not None:
            st.session_state.summary_editor_json = pending_editor_json
            st.session_state.summary_editor_seed_digest = summary_digest
        elif st.session_state.get("summary_editor_seed_digest") != summary_digest:
            st.session_state.summary_editor_json = json.dumps(
                result.document.to_dict(),
                ensure_ascii=False,
                indent=2,
            )
            st.session_state.summary_editor_seed_digest = summary_digest

        original_json = st.session_state.get("summary_model_original_json")
        with st.expander("手动编辑摘要"):
            st.caption("直接修改结构化内容；保存后只在本地重新排版。")
            with st.form("summary-local-editor"):
                edited_json = st.text_area(
                    "结构化摘要 JSON",
                    key="summary_editor_json",
                    height=360,
                    label_visibility="collapsed",
                )
                apply_col, restore_col = st.columns(2, gap="medium")
                with apply_col:
                    apply_edit = st.form_submit_button(
                        "应用修改并重新排版",
                        icon=":material/edit_document:",
                        width="stretch",
                    )
                with restore_col:
                    restore_original = st.form_submit_button(
                        "恢复模型原稿",
                        icon=":material/history:",
                        width="stretch",
                        disabled=not isinstance(original_json, str),
                    )
            if apply_edit or restore_original:
                try:
                    next_json = original_json if restore_original else edited_json
                    edited_payload = json.loads(str(next_json))
                    if not isinstance(edited_payload, dict):
                        raise SummaryError("编辑内容必须是一个 JSON 对象。")
                    edited_document = parse_summary_document(
                        edited_payload,
                        supplement_numeric_highlights=False,
                    )
                    with st.spinner("正在本地重新排版…"):
                        apply_local_summary_document(edited_document, result)
                    st.rerun()
                except (json.JSONDecodeError, SummaryError) as error:
                    st.error(f"无法应用修改：{error}")
                except RenderError as error:
                    st.session_state.summary_export_error = str(error)
                    st.error(f"文字修改已保留，但重新排版失败：{error}")
                except Exception as error:
                    LOGGER.exception("Unexpected local summary edit failure")
                    st.error(
                        f"本地编辑发生意外错误（{type(error).__name__}）。"
                        "详细堆栈已写入 Streamlit Cloud 日志。"
                    )

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
                        artifact = build_summary_long_image(result.document, "tablet")
                        st.session_state.summary_export = {
                            "digest": summary_digest,
                            "mode": "tablet",
                            "artifact": artifact,
                        }
                        st.session_state.pop("summary_export_error", None)
                    st.rerun()
                except RenderError as error:
                    st.error(str(error))
                except Exception as error:
                    LOGGER.exception("Unexpected long-image retry failure")
                    st.error(
                        f"长图排版发生意外错误（{type(error).__name__}）。"
                        "详细堆栈已写入 Streamlit Cloud 日志。"
                    )
        else:
            artifact = export["artifact"]
            output_name = safe_filename(st.session_state.summary_output_name)
            if request_is_stale:
                long_image_download_button(
                    export,
                    key="summary-export-download-inline",
                    stale=True,
                )
            else:
                action_col, download_col = st.columns(2, gap="medium")
                with action_col:
                    native_image_share(
                        artifact.png,
                        f"{output_name}.summary.png",
                        key="summary-native-image-share",
                    )
                with download_col:
                    long_image_download_button(export, key="summary-export-download-inline")
            st.download_button(
                "下载 Markdown",
                data=result.document.to_markdown().encode("utf-8"),
                file_name=f"{output_name}.summary.md",
                mime="text/markdown",
                icon=":material/description:",
                width="stretch",
                on_click="ignore",
                key="summary-export-markdown",
            )
            st.caption(
                f"{artifact.width} × {artifact.height} px · "
                + (
                    "这是上一版结果；可保留或下载，更新请重新生成。"
                    if request_is_stale
                    else "可分享、下载或长按保存。"
                )
            )
            st.image(artifact.png, width="stretch")

        with st.expander("生成信息"):
            revision_count = int(st.session_state.get("summary_revision_count", 0))
            revision_note = f" · 已修订 {revision_count} 次" if revision_count else ""
            generation_note = st.session_state.get("summary_generation_note")
            generation_note = f" · {generation_note}" if generation_note else ""
            st.caption(
                f"{result.model}{generation_note} · {result.completion_tokens or '—'} 输出 Tokens · "
                f"{result.milliseconds / 1000:.1f} 秒{revision_note}"
            )
