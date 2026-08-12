"""Streamlit app: template-first visual prompt builder."""

from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime
from typing import Any

import streamlit as st

from presets import (
    MAIN_TASK_NAMES,
    MAIN_VISUAL_NAMES,
    TASK_TEMPLATES,
    VISUAL_MODES,
    merged_values,
)
from question_bank import QUESTION_BANK


APP_TITLE = "Visual Prompt"
APP_SUBTITLE = "先套用成熟视觉模板，再按需要微调；最终得到可直接交给 ChatGPT Images 的提示词。"
AUTO_CODE = "AUTO"

QUESTION_BY_ID = {question["id"]: question for question in QUESTION_BANK}
WORKFLOWS = {
    "从零生成": {"code": "A", "description": "描述想要的画面，从空白开始生成。"},
    "修改一张图": {"code": "B", "description": "上传原图后，明确要改什么，以及哪些内容不能变。"},
    "融合多张参考图": {"code": "C", "description": "分别说明每张参考图提供主体、风格、构图或产品素材。"},
}

CONTENT_QUESTION_IDS = ["purpose", "subject_type", "priority"]
VISUAL_QUESTION_IDS = ["medium", "realism_level", "color_scheme", "lighting", "mood"]
COMPOSITION_QUESTION_IDS = ["aspect_ratio", "composition", "subject_scale", "background_complexity", "additional_elements"]
ADVANCED_STYLE_IDS = ["camera_angle", "linework", "shape_language", "detail_level", "texture", "tuning_strength"]

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
    st.session_state.setdefault("workflow", "从零生成")
    st.session_state.setdefault("show_more_templates", False)
    st.session_state.setdefault("show_more_visuals", False)


def apply_presets() -> None:
    for question_id, value in default_answers().items():
        st.session_state[f"q_{question_id}"] = value
    values = merged_values(
        st.session_state.task_template,
        st.session_state.visual_mode,
    )
    for question_id, value in values.items():
        st.session_state[f"q_{question_id}"] = value
    st.session_state.q_input_mode = WORKFLOWS[st.session_state.workflow]["code"]
    st.session_state.output_size = ASPECT_RATIO_SIZES.get(str(values.get("aspect_ratio", "F")), "自动")
    st.session_state.generated_outputs = None


def reset_builder() -> None:
    for question_id, value in default_answers().items():
        st.session_state[f"q_{question_id}"] = value
    st.session_state.task_template = "自由创作"
    st.session_state.visual_mode = "沿用用途模板"
    st.session_state.output_size = "自动"
    st.session_state.workflow = "从零生成"
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


def render_question_grid(question_ids: list[str]) -> None:
    for index in range(0, len(question_ids), 2):
        columns = st.columns(2, gap="large")
        for column, question_id in zip(columns, question_ids[index:index + 2]):
            with column:
                render_question(question_id)


def visible_preset_names(main_names: list[str], presets: dict[str, Any], show_more: bool) -> list[str]:
    return list(presets) if show_more else main_names


def keep_preset_visible(key: str, names: list[str]) -> None:
    if st.session_state[key] not in names:
        st.session_state[key] = names[0]


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
    custom = {
        "subject_details": "",
        "usage_notes": "",
        "exact_text": "",
        "edit_request": "",
        "edit_area": "",
        "source_description": "",
        "reference_roles": "",
        "custom_preserve": "",
        "custom_avoid": "",
        "custom_notes": "",
        **custom,
    }
    text_request = custom["exact_text"].strip()
    workflow_code = str(answers["input_mode"])
    fragments = {
        qid: answer_fragments(answers, qid)
        for qid in QUESTION_BY_ID
    }
    opening = {
        "A": "Create one polished, production-ready image from the description below.",
        "B": "Edit the supplied image according to the instructions below.",
        "C": "Create one coherent image by combining the supplied reference images according to the role of each reference.",
    }.get(workflow_code, "Create one polished, production-ready image.")
    lines = [
        opening,
        "",
        "GOAL AND USE",
        f"- Intended use: {fragments['purpose'] or 'infer the most suitable presentation from the subject'}.",
        f"- Primary priority: {fragments['priority'] or 'balance clarity, visual coherence, and appeal'}.",
        f"- Subject / scene: {custom['subject_details'].strip() or 'Infer the visible subject from the supplied image references.'}",
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

    if workflow_code in {"B", "C"}:
        lines.extend([
            "",
            "EDIT PLAN",
            f"- Requested change: {custom['edit_request'].strip() or 'Apply only the explicitly requested visual transformation.'}",
            f"- Target area: {custom['edit_area'].strip() or 'the relevant area described in the requested change'}.",
        ])
        if custom["reference_roles"].strip():
            lines.append(f"- Reference roles: {custom['reference_roles'].strip()}")
        if custom["source_description"].strip():
            lines.append(f"- Optional source description: {custom['source_description'].strip()}")

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

    if workflow_code in {"B", "C"}:
        lines.extend([
            "- Treat each uploaded image as a reference with a specific role, not as permission to redesign everything.",
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
        f"{st.session_state.workflow} · {st.session_state.task_template} × {st.session_state.visual_mode}\n"
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

    st.title(APP_TITLE)
    st.markdown(f'<p class="intro">{APP_SUBTITLE}</p>', unsafe_allow_html=True)

    st.subheader("你想怎样开始？")
    workflow = st.segmented_control(
        "工作方式",
        options=list(WORKFLOWS),
        key="workflow",
        label_visibility="collapsed",
        width="stretch",
    ) or "从零生成"
    st.caption(WORKFLOWS[workflow]["description"])

    st.subheader("选择一个起点")
    task_names = visible_preset_names(MAIN_TASK_NAMES, TASK_TEMPLATES, st.session_state.show_more_templates)
    visual_names = visible_preset_names(MAIN_VISUAL_NAMES, VISUAL_MODES, st.session_state.show_more_visuals)
    keep_preset_visible("task_template", task_names)
    keep_preset_visible("visual_mode", visual_names)
    left, right = st.columns(2, gap="large")
    with left:
        st.selectbox("用途模板", task_names, key="task_template", help="预填常见的信息层级、构图和约束。")
        st.caption(TASK_TEMPLATES[st.session_state.task_template]["description"])
        st.toggle("更多专业用途", key="show_more_templates")
    with right:
        st.selectbox("视觉风格", visual_names, key="visual_mode", help="预填媒介、色彩、光影和材质。")
        st.caption(VISUAL_MODES[st.session_state.visual_mode]["description"])
        st.toggle("更多视觉风格", key="show_more_visuals")
    apply_col, reset_col = st.columns([3, 1])
    with apply_col:
        st.button("套用模板", type="primary", width="stretch", on_click=apply_presets)
    with reset_col:
        st.button("清空", width="stretch", on_click=reset_builder)

    st.subheader("核心需求")
    if workflow == "从零生成":
        subject_details = st.text_area(
            "主体与场景",
            key="subject_details",
            placeholder="例如：一位产品设计师在清晨的工作室整理纸质原型，桌面克制整洁……",
            height=110,
        )
        edit_request = ""
        edit_area = ""
        reference_roles = ""
        source_description = ""
    else:
        edit_request = st.text_area(
            "你希望修改什么？",
            key="edit_request",
            placeholder="例如：只把白天改成下雪的冬日晚景；人物、机位和建筑结构都不要改变。",
            height=110,
        )
        edit_left, edit_right = st.columns(2, gap="large")
        with edit_left:
            edit_area = st.text_input("修改区域（可选）", key="edit_area", placeholder="例如：人物外套、右上角背景、整张图的光线")
        with edit_right:
            source_description = st.text_input("原图简述（可选）", key="source_description", placeholder="模型能直接看图；只有歧义时才填写")
        if workflow == "融合多张参考图":
            reference_roles = st.text_area(
                "分别说明参考图的作用",
                key="reference_roles",
                placeholder="例如：图 1 提供人物身份；图 2 提供服装；图 3 提供场景和构图。",
                height=90,
            )
        else:
            reference_roles = ""
        subject_details = st.text_input(
            "成图主体或新场景（可选）",
            key="subject_details",
            placeholder="与原图一致可留空；只有替换场景或新增主体时填写。",
        )
        custom_preserve = st.text_input(
            "哪些内容绝对不能改变？",
            key="custom_preserve",
            placeholder="例如：人物身份、姿势、包装文字、机位和背景结构",
        )
    usage_notes = st.text_input("受众或使用场景（可选）", key="usage_notes", placeholder="例如：小红书知识卡片，手机端优先")
    exact_text = st.text_area(
        "必须出现在图片里的原文（可选）",
        key="exact_text",
        placeholder="逐字粘贴；留空时会明确要求图片里不要出现文字。",
        height=80,
    )

    st.subheader("按需要微调")
    st.caption("模板已经给出可用配置。多数情况下，只改一两个确实重要的项目即可。")
    with st.expander("内容与用途"):
        render_question_grid(CONTENT_QUESTION_IDS)
    with st.expander("视觉风格"):
        render_question_grid(VISUAL_QUESTION_IDS)
    with st.expander("构图与版式"):
        render_question_grid(COMPOSITION_QUESTION_IDS)
    with st.expander("高级控制"):
        render_question_grid(ADVANCED_STYLE_IDS)
        if workflow != "从零生成":
            render_question("preserve_items")
        render_question("avoid_items")
        if workflow == "从零生成":
            custom_preserve = st.text_input(
                "必须保持的特征（可选）",
                key="custom_preserve",
                placeholder="例如：人物脸型、品牌主色、产品轮廓",
            )
        custom_avoid = st.text_input("额外不要出现", key="custom_avoid", placeholder="例如：不要渐变、不要装饰边框")
        custom_notes = st.text_area("其他美术指导", key="custom_notes", placeholder="例如：更成熟、更克制，留白多一些")

    with st.expander("输出设置"):
        target_col, size_col, quality_col = st.columns(3, gap="large")
        with target_col:
            target = st.selectbox("使用位置", list(MODEL_TARGETS), key="model_target")
        with size_col:
            size_label = st.selectbox("输出尺寸", list(OUTPUT_SIZES), key="output_size")
        with quality_col:
            quality = st.select_slider("质量意图", options=["快速草稿", "平衡", "最终成品"], value="平衡", key="quality_intent")
        st.caption("GPT Image 2 支持灵活尺寸；2K 以上更适合作为最终输出，草稿阶段优先使用低质量设置。")

    if st.button("生成可复制提示词", type="primary", width="stretch", icon=":material/auto_awesome:"):
        st.session_state.q_input_mode = WORKFLOWS[workflow]["code"]
        answers = {question["id"]: st.session_state[f"q_{question['id']}"] for question in QUESTION_BANK}
        custom = {
            "subject_details": subject_details,
            "usage_notes": usage_notes,
            "exact_text": exact_text,
            "edit_request": edit_request,
            "edit_area": edit_area,
            "source_description": source_description,
            "reference_roles": reference_roles,
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
                "workflow": workflow,
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
