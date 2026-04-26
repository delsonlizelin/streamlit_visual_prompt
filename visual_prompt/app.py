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


def option_display(option: dict[str, str]) -> str:
    return f"{option['code']}. {option['label']}"


def format_selected_options(selected_options: list[dict[str, str]]) -> str:
    if not selected_options:
        return "未选择"
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
        if selected:
            fragments = format_prompt_fragments(selected)
            if fragments:
                lines.append(f"Prompt Hints: {fragments}")
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
    by_id = {q["id"]: q for q in QUESTION_BANK}

    def pick_label(qid: str) -> str:
        selected = answers.get(qid, [])
        return selected[0]["label"] if selected else ""

    def pick_fragments(qid: str) -> str:
        return format_prompt_fragments(answers.get(qid, []))

    preserve_fragments = format_prompt_fragments(answers.get("preserve_items", []))
    avoid_fragments = format_prompt_fragments(answers.get("avoid_items", []))

    lines = [
        "[English Prompt Skeleton]",
        "Create an image with the following constraints:",
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
        f"- Preserve (if image-to-image): {preserve_fragments or 'none specified'}",
        f"- Avoid: {avoid_fragments or 'none specified'}",
        "",
        "User custom notes:",
        f"- Subject details: {custom_inputs.get('subject_details') or 'N/A'}",
        f"- Usage notes: {custom_inputs.get('usage_notes') or 'N/A'}",
        f"- Custom preserve: {custom_inputs.get('custom_preserve') or 'N/A'}",
        f"- Custom avoid: {custom_inputs.get('custom_avoid') or 'N/A'}",
        f"- Additional notes: {custom_inputs.get('custom_notes') or 'N/A'}",
        "",
        "Write one concise production-ready prompt in English, then provide a shorter variant optimized for image-to-image tools.",
    ]

    # Avoid unused warning in static checks while keeping readable intent.
    _ = by_id
    return "\n".join(lines)


def build_cn_instruction(structured_brief: str) -> str:
    return (
        "请根据以下结构化需求，生成一段可用于 AI 生图或改图的英文提示词。\n"
        "要求：\n"
        "1. 不要只堆砌风格词；请把媒介、线条、形状、色彩、光影、构图、保留项和排除项整合为清晰描述。\n"
        "2. 先输出标准英文提示词，再输出一个更短版本。\n"
        "3. 如果有冲突约束，请以 Priority 字段为最高优先级。\n\n"
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
        "tuning_knobs": TUNING_KNOBS,
        "outputs": {
            "structured_brief": structured_brief,
            "english_prompt_skeleton": en_skeleton,
            "cn_gpt_instruction": cn_instruction,
        },
    }


def render_question(question: dict[str, Any]) -> list[dict[str, str]]:
    options = question["options"]
    labels = [option_display(item) for item in options]
    label_to_option = {option_display(item): item for item in options}

    with st.container(border=True):
        st.markdown(f"**{question['title']}**")

        if question["type"] == "single":
            selected_label = st.selectbox(
                "请选择一个选项",
                options=[""] + labels,
                key=f"q_{question['id']}",
                format_func=lambda value: "请选择..." if value == "" else value,
            )
            chosen = [label_to_option[selected_label]] if selected_label else []
        else:
            selected_labels = st.multiselect(
                "可多选",
                options=labels,
                key=f"q_{question['id']}",
            )
            chosen = [label_to_option[label] for label in selected_labels]

        with st.expander("查看选项解释", expanded=False):
            for item in options:
                st.markdown(
                    f"- **{option_display(item)}**：{item['description']}  \n"
                    f"  术语：{item['glossary']}"
                )

        if chosen:
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
        missing_required = [
            question["title"]
            for question in QUESTION_BANK
            if question["type"] == "single" and not answers.get(question["id"])
        ]

        if missing_required:
            st.error("还有必选题未完成，请先补齐：")
            for item in missing_required:
                st.write(f"- {item}")
        else:
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
