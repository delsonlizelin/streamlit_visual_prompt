"""Streamlit app: AI Image Prompt Style Builder."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import streamlit as st

from question_bank import QUESTION_BANK, TUNING_KNOBS


APP_TITLE = "AI Image Prompt Style Builder"
APP_SUBTITLE = "通过选择题定义视觉风格，并生成可复制给 GPT 的结构化提示词需求"
SECTION_ORDER = ["基础设置", "风格定义", "画面控制"]

AUTO_SINGLE_OPTION = {
    "code": "AUTO",
    "label": "无所谓/自行发挥",
    "description": "不强行锁定该维度，由模型在整体一致性前提下自动决策。",
    "prompt_fragment": "leave this dimension flexible and let the model resolve it coherently",
    "glossary": "Auto mode: this dimension is intentionally left open for controlled model discretion.",
}

GLOBAL_PROMPT_PRINCIPLES_CN = [
    "字符与编码：默认按 UTF-8 语义处理；若画面包含文字，必须保证中文字符正确可读、无乱码、无伪文字。未明确要求文字时默认不生成文字。",
    "结构稳定性：手部和五官必须自然，禁止多指、断指、扭曲手势、诡异神情、空洞眼神或脸部结构异常。",
    "一致性：主体身份线索（发型、脸型、服装轮廓、主色关系）保持一致，不出现跨区域风格断裂。",
    "画面质量：禁止脏噪点、莫名水印、低清锯齿、光源冲突、背景杂乱和焦点缺失。",
    "版权与安全：禁止模仿在世艺术家风格、禁止复刻受版权保护角色与商标元素。",
]

GLOBAL_QUALITY_RULES_EN = [
    "maintain coherent anatomy and natural facial expression",
    "preserve identity cues when preservation is requested",
    "keep composition clean with a clear focal point",
    "maintain style consistency across subject and background",
    "if text is required, render Chinese characters correctly and legibly",
]

GLOBAL_NEGATIVE_RULES_EN = [
    "no uncanny hands, no extra fingers, no fused fingers, no broken wrists",
    "no uncanny face, no asymmetrical eyes, no distorted mouth geometry",
    "no gibberish text, no corrupted Chinese characters, no random watermark/signature",
    "no photofilter-overlay look, no muddy detail, no compression artifacts",
    "no cluttered background, no conflicting light direction, no accidental plastic 3D look unless requested",
    "no imitation of living artists or copyrighted IP characters",
]


def option_display(option: dict[str, str]) -> str:
    return f"{option['code']}. {option['label']}"


def option_long_description(option: dict[str, str]) -> str:
    return (
        f"{option['description']} {option['glossary']} "
        f"建议效果：{option['prompt_fragment']}。"
    )


def format_selected_options(selected_options: list[dict[str, str]]) -> str:
    if not selected_options:
        return "无所谓/自行发挥（此维度交给模型按整体一致性自动决定）"
    return "；".join(f"{item['label']}（{item['description']}）" for item in selected_options)


def format_prompt_fragments(selected_options: list[dict[str, str]]) -> str:
    fragments = [item["prompt_fragment"] for item in selected_options if item.get("prompt_fragment")]
    return ", ".join(fragments) if fragments else ""


def build_structured_brief(
    answers: dict[str, list[dict[str, str]]],
    custom_inputs: dict[str, str],
) -> str:
    lines: list[str] = ["[AI Image Prompt Brief]", ""]

    for question in QUESTION_BANK:
        field = question["output_field"]
        selected = answers.get(question["id"], [])
        lines.append(f"{field}:")
        lines.append(format_selected_options(selected))
        fragments = format_prompt_fragments(selected)
        if fragments:
            lines.append(f"Prompt Hints: {fragments}")
        lines.append("")

    lines.append("Global Principles (Always On):")
    for item in GLOBAL_PROMPT_PRINCIPLES_CN:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("Custom Inputs:")
    lines.append(f"Subject Details: {custom_inputs.get('subject_details') or '无'}")
    lines.append(f"Usage Notes: {custom_inputs.get('usage_notes') or '无'}")
    lines.append(f"Custom Preserve: {custom_inputs.get('custom_preserve') or '无'}")
    lines.append(f"Custom Avoid: {custom_inputs.get('custom_avoid') or '无'}")
    lines.append(f"Custom Notes: {custom_inputs.get('custom_notes') or '无'}")
    lines.append("")

    lines.append("可微调项:")
    for idx, knob in enumerate(TUNING_KNOBS, start=1):
        lines.append(f"{idx}. {knob['name']}（{knob['cn']}）：{knob['desc']}")

    return "\n".join(lines)


def build_english_prompt_skeleton(
    answers: dict[str, list[dict[str, str]]],
    custom_inputs: dict[str, str],
) -> str:
    def pick_label(qid: str) -> str:
        selected = answers.get(qid, [])
        return selected[0]["label"] if selected else "Auto / Model discretion"

    def pick_fragments(qid: str) -> str:
        fragments = format_prompt_fragments(answers.get(qid, []))
        return fragments or "model decides this dimension coherently"

    preserve_fragments = format_prompt_fragments(answers.get("preserve_items", []))
    avoid_fragments = format_prompt_fragments(answers.get("avoid_items", []))
    custom_avoid = custom_inputs.get("custom_avoid") or ""

    negative_rules = GLOBAL_NEGATIVE_RULES_EN.copy()
    if avoid_fragments:
        negative_rules.append(avoid_fragments)
    if custom_avoid:
        negative_rules.append(custom_avoid)

    lines = [
        "[English Prompt Skeleton]",
        "Create one high-quality image with the following constraints:",
        f"- Input mode: {pick_label('input_mode')} ({pick_fragments('input_mode')})",
        f"- Purpose: {pick_label('purpose')} ({pick_fragments('purpose')})",
        f"- Subject type: {pick_label('subject_type')} ({pick_fragments('subject_type')})",
        f"- Priority: {pick_label('priority')} ({pick_fragments('priority')})",
        f"- Aspect ratio: {pick_label('aspect_ratio')} ({pick_fragments('aspect_ratio')})",
        f"- Style family: {pick_label('medium')} ({pick_fragments('medium')})",
        f"- Realism level: {pick_label('realism_level')} ({pick_fragments('realism_level')})",
        f"- Composition: {pick_label('composition')} ({pick_fragments('composition')})",
        f"- Camera/view: {pick_label('camera_angle')} ({pick_fragments('camera_angle')})",
        f"- Subject scale: {pick_label('subject_scale')} ({pick_fragments('subject_scale')})",
        f"- Linework: {pick_label('linework')} ({pick_fragments('linework')})",
        f"- Shape language: {pick_label('shape_language')} ({pick_fragments('shape_language')})",
        f"- Detail level: {pick_label('detail_level')} ({pick_fragments('detail_level')})",
        f"- Color: {pick_label('color_scheme')} ({pick_fragments('color_scheme')})",
        f"- Lighting: {pick_label('lighting')} ({pick_fragments('lighting')})",
        f"- Texture: {pick_label('texture')} ({pick_fragments('texture')})",
        f"- Mood: {pick_label('mood')} ({pick_fragments('mood')})",
        f"- Background: {pick_label('background_complexity')} ({pick_fragments('background_complexity')})",
        f"- Additional elements: {pick_label('additional_elements')} ({pick_fragments('additional_elements')})",
        f"- Stylization strength: {pick_label('tuning_strength')} ({pick_fragments('tuning_strength')})",
        f"- Preserve (if image-to-image): {preserve_fragments or 'preserve only essential identity cues'}",
        "",
        "Always-on quality principles:",
    ]

    lines.extend(f"- {item}" for item in GLOBAL_QUALITY_RULES_EN)
    lines.append("")
    lines.append("Always-on negative constraints:")
    lines.extend(f"- {item}" for item in negative_rules)
    lines.append("")
    lines.append("User custom notes:")
    lines.append(f"- Subject details: {custom_inputs.get('subject_details') or 'N/A'}")
    lines.append(f"- Usage notes: {custom_inputs.get('usage_notes') or 'N/A'}")
    lines.append(f"- Custom preserve: {custom_inputs.get('custom_preserve') or 'N/A'}")
    lines.append(f"- Additional notes: {custom_inputs.get('custom_notes') or 'N/A'}")
    lines.append("")
    lines.append("Write one production-ready English prompt, then provide a shorter variant for image-to-image tools.")

    return "\n".join(lines)


def build_cn_instruction(structured_brief: str) -> str:
    return (
        "请根据以下结构化需求，生成一段可用于 AI 生图或改图的英文提示词。\n"
        "要求：\n"
        "1. 不要堆砌风格词；把媒介、线条、形状、色彩、光影、构图、保留项、排除项整合为清晰指令。\n"
        "2. 默认强制质量规则：手部和五官自然、不要诡异手、不要诡异神情、不要乱码/伪文字。\n"
        "3. 若涉及文字渲染，确保中文字符正确、可读、无错别字样式伪造；未明确要求文字则默认不生成文字。\n"
        "4. 先输出标准英文提示词，再输出一个简短版本。\n"
        "5. 如果有冲突约束，以 Priority 字段为最高优先级。\n\n"
        "需求如下：\n"
        f"{structured_brief}"
    )


def build_json_payload(
    answers: dict[str, list[dict[str, str]]],
    custom_inputs: dict[str, str],
    structured_brief: str,
    en_skeleton: str,
    cn_instruction: str,
) -> dict[str, Any]:
    answer_items = []
    for question in QUESTION_BANK:
        selected = answers.get(question["id"], [])
        answer_items.append(
            {
                "id": question["id"],
                "title": question["title"],
                "type": question["type"],
                "output_field": question["output_field"],
                "selected": selected,
            }
        )

    return {
        "meta": {
            "app": APP_TITLE,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "question_count": len(QUESTION_BANK),
        },
        "answers": answer_items,
        "custom_inputs": custom_inputs,
        "global_principles_cn": GLOBAL_PROMPT_PRINCIPLES_CN,
        "global_quality_rules_en": GLOBAL_QUALITY_RULES_EN,
        "global_negative_rules_en": GLOBAL_NEGATIVE_RULES_EN,
        "tuning_knobs": TUNING_KNOBS,
        "outputs": {
            "structured_brief": structured_brief,
            "english_prompt_skeleton": en_skeleton,
            "cn_gpt_instruction": cn_instruction,
        },
    }


def render_question(question: dict[str, Any]) -> list[dict[str, str]]:
    options = question["options"]

    with st.container(border=True):
        st.markdown(f"**{question['title']}**")

        if question["type"] == "single":
            ui_options = [AUTO_SINGLE_OPTION, *options]
            labels = [option_display(item) for item in ui_options]
            label_to_option = {option_display(item): item for item in ui_options}
            captions = [option_long_description(item) for item in ui_options]

            selected_label = st.radio(
                "单选（默认无所谓/自行发挥）",
                options=labels,
                captions=captions,
                index=0,
                key=f"q_{question['id']}",
            )
            chosen = [label_to_option[selected_label]]
        else:
            st.caption("可多选。若一个都不选，默认该维度为“无所谓/自行发挥”。")
            chosen: list[dict[str, str]] = []
            for item in options:
                label = f"**{option_display(item)}**  \n*{option_long_description(item)}*"
                checked = st.checkbox(label, key=f"q_{question['id']}_{item['code']}")
                if checked:
                    chosen.append(item)

            if not chosen:
                st.caption("当前：无所谓/自行发挥")

        st.caption(f"已选：{format_selected_options(chosen)}")

    return chosen


def build_questions_by_section() -> dict[str, list[dict[str, Any]]]:
    data: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_ORDER}
    for question in QUESTION_BANK:
        section = question["section"]
        if section not in data:
            data[section] = []
        data[section].append(question)
    return data


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🎨", layout="wide")

    st.markdown(
        """
        <style>
        div[data-testid="stRadio"] div[data-testid="stCaptionContainer"] p {
            font-style: italic;
            opacity: 0.92;
            line-height: 1.35;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title(APP_TITLE)
    st.caption(APP_SUBTITLE)
    st.write(
        "这个工具用于把模糊审美偏好转成结构化风格需求。"
        "它不会直接出图，而是给你可复制的需求文本，再交给 GPT / Midjourney / SD 等工具生成最终提示词。"
    )

    if "generated_outputs" not in st.session_state:
        st.session_state.generated_outputs = None

    questions_by_section = build_questions_by_section()

    with st.form("visual_prompt_form"):
        answers: dict[str, list[dict[str, str]]] = {}

        st.subheader("1) 基础设置")
        for question in questions_by_section.get("基础设置", []):
            answers[question["id"]] = render_question(question)

        st.subheader("2) 风格定义")
        for question in questions_by_section.get("风格定义", []):
            answers[question["id"]] = render_question(question)

        st.subheader("3) 画面控制")
        for question in questions_by_section.get("画面控制", []):
            answers[question["id"]] = render_question(question)

        st.subheader("补充输入")
        subject_details = st.text_input("主体补充（可选）", placeholder="例如：戴黑框眼镜、卷发、浅色风衣")
        usage_notes = st.text_input("用途补充（可选）", placeholder="例如：用于微信群头像，目标是小尺寸也清晰")
        custom_preserve = st.text_input("保留项补充（可选）", placeholder="例如：一定保留手势和衣服配色")
        custom_avoid = st.text_input("排除项补充（可选）", placeholder="例如：不要复杂背景，不要任何英文单词")
        custom_notes = st.text_area("其他备注（可选）", placeholder="例如：希望整体观感更成熟，不要幼态五官")

        submitted = st.form_submit_button("生成结构化结果", type="primary")

    if submitted:
        custom_inputs = {
            "subject_details": subject_details.strip(),
            "usage_notes": usage_notes.strip(),
            "custom_preserve": custom_preserve.strip(),
            "custom_avoid": custom_avoid.strip(),
            "custom_notes": custom_notes.strip(),
        }

        structured_brief = build_structured_brief(answers, custom_inputs)
        en_skeleton = build_english_prompt_skeleton(answers, custom_inputs)
        cn_instruction = build_cn_instruction(structured_brief)
        json_payload = build_json_payload(
            answers=answers,
            custom_inputs=custom_inputs,
            structured_brief=structured_brief,
            en_skeleton=en_skeleton,
            cn_instruction=cn_instruction,
        )

        st.session_state.generated_outputs = {
            "structured_brief": structured_brief,
            "en_skeleton": en_skeleton,
            "cn_instruction": cn_instruction,
            "json_payload": json_payload,
        }

    generated = st.session_state.generated_outputs
    if generated:
        st.subheader("4) 结果输出")
        tab1, tab2, tab3, tab4 = st.tabs([
            "结构化需求清单",
            "英文提示词骨架",
            "中文 GPT 指令",
            "JSON",
        ])

        with tab1:
            st.code(generated["structured_brief"], language="text")
            st.download_button(
                label="下载结构化结果 (.txt)",
                data=generated["structured_brief"],
                file_name="visual_prompt_brief.txt",
                mime="text/plain",
                key="download_brief",
            )

        with tab2:
            st.code(generated["en_skeleton"], language="text")
            st.download_button(
                label="下载英文骨架 (.txt)",
                data=generated["en_skeleton"],
                file_name="visual_prompt_en_skeleton.txt",
                mime="text/plain",
                key="download_en",
            )

        with tab3:
            st.code(generated["cn_instruction"], language="text")
            st.download_button(
                label="下载中文指令 (.txt)",
                data=generated["cn_instruction"],
                file_name="visual_prompt_cn_instruction.txt",
                mime="text/plain",
                key="download_cn",
            )

        with tab4:
            json_str = json.dumps(generated["json_payload"], ensure_ascii=False, indent=2)
            st.code(json_str, language="json")
            st.download_button(
                label="下载 JSON (.json)",
                data=json_str,
                file_name="visual_prompt_result.json",
                mime="application/json",
                key="download_json",
            )


if __name__ == "__main__":
    main()
