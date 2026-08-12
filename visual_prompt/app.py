"""Streamlit app: template-first visual prompt builder."""

from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime
from typing import Any

import streamlit as st

from presets import TASK_TEMPLATES, VISUAL_MODES, merged_values
from question_bank import QUESTION_BANK


APP_TITLE = "Visual Prompt"
APP_SUBTITLE = "先套用成熟视觉模板，再按需要微调；最终得到可直接交给 ChatGPT Images 的提示词。"
AUTO_CODE = "AUTO"

QUESTION_BY_ID = {question["id"]: question for question in QUESTION_BANK}
CORE_QUESTION_IDS = [
    "input_mode", "purpose", "subject_type", "priority", "aspect_ratio",
    "medium", "realism_level", "composition", "subject_scale", "color_scheme",
    "lighting", "mood", "background_complexity", "additional_elements",
]
ADVANCED_QUESTION_IDS = [
    "camera_angle", "linework", "shape_language", "detail_level", "texture",
    "tuning_strength", "preserve_items", "avoid_items",
]

MODEL_TARGETS = {
    "ChatGPT Images（推荐）": "Write as a direct conversational image request for ChatGPT Images.",
    "OpenAI Image API / GPT Image 2": "Write as a production prompt for the OpenAI Image API using GPT Image 2.",
    "通用生图工具": "Write a model-neutral image prompt without vendor-specific parameter syntax.",
}

OUTPUT_SIZES = {
    "自动": "auto",
    "正方形 · 1024×1024": "1024x1024",
    "竖版 · 1024×1536": "1024x1536",
    "横版 · 1536×1024": "1536x1024",
    "2K 横版 · 2560×1440": "2560x1440",
    "2K 正方形 · 2048×2048": "2048x2048",
}

ASPECT_RATIO_SIZES = {
    "A": "正方形 · 1024×1024",
    "B": "横版 · 1536×1024",
    "C": "竖版 · 1024×1536",
    "D": "2K 横版 · 2560×1440",
    "E": "竖版 · 1024×1536",
    "F": "自动",
}

QUALITY_VALUES = {"快速草稿": "low", "平衡": "medium", "最终成品": "high"}


def option_for(question_id: str, code: str) -> dict[str, str] | None:
    return next((item for item in QUESTION_BY_ID[question_id]["options"] if item["code"] == code), None)


def selected_options(question_id: str, value: str | list[str]) -> list[dict[str, str]]:
    codes = value if isinstance(value, list) else [value]
    return [item for code in codes if code != AUTO_CODE if (item := option_for(question_id, code))]


def default_answers() -> dict[str, str | list[str]]:
    return {
        question["id"]: ([] if question["type"] == "multi" else AUTO_CODE)
        for question in QUESTION_BANK
    }


def ensure_state() -> None:
    defaults = default_answers()
    for question_id, value in defaults.items():
        st.session_state.setdefault(f"q_{question_id}", value)
    st.session_state.setdefault("task_template", "自由创作")
    st.session_state.setdefault("visual_mode", "沿用用途模板")
    st.session_state.setdefault("generated_outputs", None)
    st.session_state.setdefault("output_size", "自动")


def apply_presets() -> None:
    for question_id, value in default_answers().items():
        st.session_state[f"q_{question_id}"] = value
    values = merged_values(
        st.session_state.task_template,
        st.session_state.visual_mode,
    )
    for question_id, value in values.items():
        st.session_state[f"q_{question_id}"] = value
    st.session_state.output_size = ASPECT_RATIO_SIZES.get(str(values.get("aspect_ratio", "F")), "自动")
    st.session_state.generated_outputs = None


def reset_builder() -> None:
    for question_id, value in default_answers().items():
        st.session_state[f"q_{question_id}"] = value
    st.session_state.task_template = "自由创作"
    st.session_state.visual_mode = "沿用用途模板"
    st.session_state.output_size = "自动"
    st.session_state.generated_outputs = None


def clipboard_button(text: str, label: str, *, key: str) -> None:
    payload = json.dumps(text, ensure_ascii=False).replace("</", "<\\/")
    element_id = "copy-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    st.iframe(
        f"""
        <button id="{element_id}" type="button">{html.escape(label)}</button>
        <script>
        const button = document.getElementById({json.dumps(element_id)});
        const content = {payload};
        button.addEventListener("click", async () => {{
          await navigator.clipboard.writeText(content);
          button.textContent = "已复制";
          setTimeout(() => button.textContent = {json.dumps(label, ensure_ascii=False)}, 1400);
        }});
        </script>
        <style>
          html, body {{ margin: 0; background: transparent; font-family: system-ui, sans-serif; }}
          button {{ width: 100%; min-height: 42px; padding: 0 16px; border: 1px solid #345d6f;
            border-radius: 7px; background: #345d6f; color: white; font-weight: 650; cursor: pointer; }}
          button:hover {{ background: #294b5a; }}
        </style>
        """,
        height=44,
        width="stretch",
    )


def render_question(question_id: str) -> str | list[str]:
    question = QUESTION_BY_ID[question_id]
    options = question["options"]
    code_to_option = {item["code"]: item for item in options}

    if question["type"] == "multi":
        value = st.multiselect(
            question["title"],
            options=[item["code"] for item in options],
            format_func=lambda code: code_to_option[code]["label"],
            key=f"q_{question_id}",
        )
        if value:
            st.caption(" · ".join(code_to_option[code]["description"] for code in value))
        return value

    codes = [AUTO_CODE, *[item["code"] for item in options]]
    value = st.selectbox(
        question["title"],
        options=codes,
        format_func=lambda code: "自动判断" if code == AUTO_CODE else code_to_option[code]["label"],
        key=f"q_{question_id}",
    )
    if value != AUTO_CODE:
        st.caption(code_to_option[value]["description"])
    return value


def answer_label(answers: dict[str, str | list[str]], question_id: str) -> str:
    selected = selected_options(question_id, answers[question_id])
    return "；".join(item["label"] for item in selected) if selected else "由模型根据整体画面判断"


def answer_fragments(answers: dict[str, str | list[str]], question_id: str) -> str:
    selected = selected_options(question_id, answers[question_id])
    return ", ".join(item["prompt_fragment"] for item in selected)


def build_ready_prompt(
    answers: dict[str, str | list[str]],
    custom: dict[str, str],
    output: dict[str, str],
) -> str:
    text_request = custom["exact_text"].strip()
    fragments = {
        qid: answer_fragments(answers, qid)
        for qid in QUESTION_BY_ID
    }
    lines = [
        "Create one polished, production-ready image.",
        "",
        "GOAL AND USE",
        f"- Intended use: {fragments['purpose'] or 'infer the most suitable presentation from the subject'}.",
        f"- Primary priority: {fragments['priority'] or 'balance clarity, visual coherence, and appeal'}.",
        f"- Subject: {custom['subject_details'].strip() or 'Use the subject description supplied with this prompt.'}",
    ]
    if custom["usage_notes"].strip():
        lines.append(f"- Audience / context: {custom['usage_notes'].strip()}")

    lines.extend([
        "",
        "VISUAL DIRECTION",
        f"- Visual medium: {fragments['medium'] or 'choose the most fitting visual medium'}.",
        f"- Realism and detail: {', '.join(filter(None, [fragments['realism_level'], fragments['detail_level']])) or 'resolve naturally for the intended use'}.",
        f"- Line, shape, and surface: {', '.join(filter(None, [fragments['linework'], fragments['shape_language'], fragments['texture']])) or 'keep visually coherent'}.",
        f"- Color and lighting: {', '.join(filter(None, [fragments['color_scheme'], fragments['lighting']])) or 'choose a coherent palette and light direction'}.",
        f"- Mood: {fragments['mood'] or 'derive an appropriate mood from the subject'}.",
        "",
        "COMPOSITION",
        f"- Format: {fragments['aspect_ratio'] or 'choose the best aspect ratio'}; requested output size {output['size']}.",
        f"- Layout and viewpoint: {', '.join(filter(None, [fragments['composition'], fragments['camera_angle'], fragments['subject_scale']])) or 'use a clear focal hierarchy'}.",
        f"- Background: {fragments['background_complexity'] or 'support the subject without unnecessary clutter'}.",
        f"- Supporting elements: {fragments['additional_elements'] or 'add only elements that improve communication'}.",
    ])

    if text_request:
        lines.extend([
            "",
            "TEXT IN IMAGE",
            f"- Render this copy exactly once, verbatim, with no added or omitted characters: \"{text_request}\"",
            "- Use legible typography, correct Chinese characters, clean spacing, and strong contrast.",
        ])
    else:
        lines.extend(["", "TEXT IN IMAGE", "- Do not add words, captions, logos, signatures, or watermarks."])

    preserve = ", ".join(filter(None, [fragments["preserve_items"], custom["custom_preserve"].strip()]))
    avoid = ", ".join(filter(None, [fragments["avoid_items"], custom["custom_avoid"].strip()]))
    lines.extend([
        "",
        "CONSTRAINTS",
        f"- Preserve: {preserve or 'the core identity and visual logic of any supplied references'}.",
        f"- Avoid: {avoid or 'unrequested elements and visual clutter'}.",
        "- Keep anatomy, perspective, object relationships, and light direction coherent.",
    ])
    if custom["custom_notes"].strip():
        lines.append(f"- Additional direction: {custom['custom_notes'].strip()}")

    if answers["input_mode"] in {"B", "C"}:
        lines.extend([
            "- Treat each uploaded image as a reference, not as permission to redesign everything.",
            "- Change only what this prompt asks to change; keep all unrelated details stable.",
        ])

    lines.extend([
        "",
        "OUTPUT",
        f"- Target: {output['target']}.",
        f"- Quality intent: {output['quality']}.",
        "- Make tasteful decisions inside these constraints; do not merely stack visual effects.",
    ])
    return "\n".join(lines)


def build_summary(answers: dict[str, str | list[str]], custom: dict[str, str]) -> str:
    return (
        f"{st.session_state.task_template} × {st.session_state.visual_mode}\n"
        f"主体：{custom['subject_details'].strip() or '待补充'}\n"
        f"媒介：{answer_label(answers, 'medium')}\n"
        f"构图：{answer_label(answers, 'composition')} · {answer_label(answers, 'aspect_ratio')}\n"
        f"色彩与光影：{answer_label(answers, 'color_scheme')} · {answer_label(answers, 'lighting')}"
    )


def page_styles() -> None:
    st.markdown(
        """
        <style>
          :root { color-scheme: light; --ink:#252525; --muted:#62686b; --rule:#d9dee1; --accent:#345d6f; }
          .stApp { color: var(--ink); }
          .block-container { max-width: 1120px; padding-top: 2.4rem; padding-bottom: 5rem; }
          h1 { letter-spacing: -0.035em; margin-bottom: .25rem; }
          h2, h3 { letter-spacing: -0.018em; }
          .eyebrow { color: var(--accent); font-weight: 700; font-size:.82rem; letter-spacing:.08em; text-transform:uppercase; }
          .intro { color:var(--muted); font-size:1.08rem; max-width:760px; line-height:1.75; margin-bottom:1.4rem; }
          [data-testid="stVerticalBlockBorderWrapper"] { background:#fff; }
          [data-testid="stSelectbox"] label p, [data-testid="stTextInput"] label p,
          [data-testid="stTextArea"] label p, [data-testid="stMultiSelect"] label p { font-weight:650; }
          [data-testid="stCaptionContainer"] p { color:var(--muted); line-height:1.45; }
          @media (max-width: 700px) {
            .block-container { padding: 1.25rem 1rem 4rem; }
            h1 { font-size: 2.15rem !important; }
            .intro { font-size:1rem; line-height:1.65; }
            [data-testid="stHorizontalBlock"] { gap:.5rem; }
            button { min-height:44px; }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="◫", layout="wide", initial_sidebar_state="collapsed")
    page_styles()
    ensure_state()

    st.markdown('<div class="eyebrow">Template-first image prompting</div>', unsafe_allow_html=True)
    st.title(APP_TITLE)
    st.markdown(f'<p class="intro">{APP_SUBTITLE}</p>', unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("1. 选择起点")
        left, right = st.columns(2, gap="large")
        with left:
            st.selectbox(
                "用途模板",
                options=list(TASK_TEMPLATES),
                key="task_template",
                help="决定信息层级、构图和常见约束。",
            )
            st.caption(TASK_TEMPLATES[st.session_state.task_template]["description"])
        with right:
            st.selectbox(
                "经典视觉模式",
                options=list(VISUAL_MODES),
                key="visual_mode",
                help="叠加媒介、色彩、光影和材质；不会锁死后续选项。",
            )
            st.caption(VISUAL_MODES[st.session_state.visual_mode]["description"])
        apply_col, reset_col = st.columns([3, 1])
        with apply_col:
            st.button("套用并预填全部选项", type="primary", width="stretch", on_click=apply_presets)
        with reset_col:
            st.button("清空", width="stretch", on_click=reset_builder)

    st.subheader("2. 描述你要的画面")
    subject_details = st.text_area(
        "主体与场景",
        key="subject_details",
        placeholder="例如：一位产品设计师在清晨的工作室整理纸质原型，桌面克制整洁……",
        height=110,
    )
    usage_notes = st.text_input("受众或使用场景（可选）", key="usage_notes", placeholder="例如：小红书知识卡片，手机端优先")
    exact_text = st.text_area(
        "必须出现在图片里的原文（可选）",
        key="exact_text",
        placeholder="逐字粘贴；留空时会明确要求图片里不要出现文字。",
        height=80,
    )

    with st.expander("调整核心选项", expanded=True):
        for index in range(0, len(CORE_QUESTION_IDS), 2):
            columns = st.columns(2, gap="large")
            for column, question_id in zip(columns, CORE_QUESTION_IDS[index:index + 2]):
                with column:
                    render_question(question_id)

    with st.expander("高级微调", expanded=False):
        st.caption("模板已经预填了这些项目。只有确实需要时再改，避免提示词互相冲突。")
        for index in range(0, len(ADVANCED_QUESTION_IDS), 2):
            columns = st.columns(2, gap="large")
            for column, question_id in zip(columns, ADVANCED_QUESTION_IDS[index:index + 2]):
                with column:
                    render_question(question_id)
        custom_preserve = st.text_input("额外必须保留", key="custom_preserve", placeholder="例如：人物脸型、包装标签、原图机位")
        custom_avoid = st.text_input("额外不要出现", key="custom_avoid", placeholder="例如：不要渐变、不要装饰边框")
        custom_notes = st.text_area("其他美术指导", key="custom_notes", placeholder="例如：更成熟、更克制，留白多一些")

    with st.container(border=True):
        st.subheader("3. 输出设置")
        target_col, size_col, quality_col = st.columns(3, gap="large")
        with target_col:
            target = st.selectbox("使用位置", list(MODEL_TARGETS), key="model_target")
        with size_col:
            size_label = st.selectbox("输出尺寸", list(OUTPUT_SIZES), key="output_size")
        with quality_col:
            quality = st.select_slider("质量意图", options=["快速草稿", "平衡", "最终成品"], value="平衡", key="quality_intent")
        st.caption("GPT Image 2 支持灵活尺寸；2K 以上更适合作为最终输出，草稿阶段优先使用低质量设置。")

    if st.button("生成可复制提示词", type="primary", width="stretch", icon=":material/auto_awesome:"):
        answers = {question["id"]: st.session_state[f"q_{question['id']}"] for question in QUESTION_BANK}
        custom = {
            "subject_details": subject_details,
            "usage_notes": usage_notes,
            "exact_text": exact_text,
            "custom_preserve": st.session_state.get("custom_preserve", ""),
            "custom_avoid": st.session_state.get("custom_avoid", ""),
            "custom_notes": st.session_state.get("custom_notes", ""),
        }
        output = {"target": target, "size": OUTPUT_SIZES[size_label], "quality": QUALITY_VALUES[quality]}
        prompt = build_ready_prompt(answers, custom, output)
        payload = {
            "meta": {
                "app": APP_TITLE,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "task_template": st.session_state.task_template,
                "visual_mode": st.session_state.visual_mode,
            },
            "output": output,
            "answers": answers,
            "custom": custom,
            "prompt": prompt,
        }
        st.session_state.generated_outputs = {
            "prompt": prompt,
            "summary": build_summary(answers, custom),
            "payload": payload,
        }

    generated = st.session_state.generated_outputs
    if generated:
        st.divider()
        st.subheader("可直接使用")
        st.caption(generated["summary"])
        copy_col, download_col = st.columns(2, gap="medium")
        with copy_col:
            clipboard_button(generated["prompt"], "复制完整提示词", key="copy-ready-prompt")
        with download_col:
            st.download_button(
                "下载提示词 (.txt)",
                generated["prompt"],
                file_name="visual-prompt.txt",
                mime="text/plain",
                width="stretch",
                icon=":material/download:",
            )
        with st.expander("预览和编辑提示词"):
            st.code(generated["prompt"], language="text", wrap_lines=True)
        with st.expander("开发用 JSON"):
            json_text = json.dumps(generated["payload"], ensure_ascii=False, indent=2)
            st.download_button("下载 JSON", json_text, "visual-prompt.json", "application/json", width="stretch")
            st.code(json_text, language="json")


if __name__ == "__main__":
    main()
