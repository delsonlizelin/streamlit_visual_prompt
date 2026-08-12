from __future__ import annotations

import sys
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from app import build_ready_prompt, default_answers  # noqa: E402
from presets import (  # noqa: E402
    MAIN_TASK_NAMES,
    MAIN_VISUAL_NAMES,
    TASK_TEMPLATES,
    VISUAL_MODES,
    merged_values,
)
from question_bank import QUESTION_BANK  # noqa: E402


class PresetTests(unittest.TestCase):
    def test_all_preset_codes_exist_in_question_bank(self) -> None:
        valid = {
            question["id"]: {item["code"] for item in question["options"]}
            for question in QUESTION_BANK
        }
        for collection in (TASK_TEMPLATES, VISUAL_MODES):
            for preset_name, preset in collection.items():
                for question_id, value in preset["values"].items():
                    self.assertIn(question_id, valid, preset_name)
                    codes = value if isinstance(value, list) else [value]
                    self.assertTrue(set(codes).issubset(valid[question_id]), preset_name)

    def test_visual_mode_overrides_task_without_erasing_unrelated_values(self) -> None:
        values = merged_values("知识信息图", "现代主义海报")
        self.assertEqual(values["purpose"], "E")
        self.assertEqual(values["medium"], "E")
        self.assertEqual(values["composition"], "E")
        self.assertEqual(values["additional_elements"], "E")

    def test_library_has_multiple_task_and_visual_choices(self) -> None:
        self.assertGreaterEqual(len(TASK_TEMPLATES), 10)
        self.assertGreaterEqual(len(VISUAL_MODES), 15)
        self.assertLess(len(MAIN_TASK_NAMES), len(TASK_TEMPLATES))
        self.assertLess(len(MAIN_VISUAL_NAMES), len(VISUAL_MODES))


class PromptTests(unittest.TestCase):
    def test_prompt_has_maintainable_sections_and_exact_text(self) -> None:
        answers = default_answers()
        answers.update(merged_values("知识信息图", "极简编辑插画"))
        prompt = build_ready_prompt(
            answers,
            {
                "subject_details": "解释潮汐形成原理",
                "usage_notes": "手机阅读",
                "exact_text": "潮汐如何形成？",
                "custom_preserve": "",
                "custom_avoid": "不要装饰边框",
                "custom_notes": "",
            },
            {"target": "ChatGPT Images（推荐）", "size": "1024x1536", "quality": "medium"},
        )
        self.assertIn("GOAL AND USE", prompt)
        self.assertIn("VISUAL DIRECTION", prompt)
        self.assertIn("TEXT IN IMAGE", prompt)
        self.assertIn('"潮汐如何形成？"', prompt)
        self.assertIn("requested output size 1024x1536", prompt)

    def test_empty_exact_text_forbids_accidental_text(self) -> None:
        prompt = build_ready_prompt(
            default_answers(),
            {
                "subject_details": "a red chair",
                "usage_notes": "",
                "exact_text": "",
                "custom_preserve": "",
                "custom_avoid": "",
                "custom_notes": "",
            },
            {"target": "通用生图工具", "size": "auto", "quality": "low"},
        )
        self.assertIn("Do not add words, captions, logos, signatures, or watermarks", prompt)

    def test_edit_prompt_prioritizes_change_area_and_preservation(self) -> None:
        answers = default_answers()
        answers["input_mode"] = "B"
        answers["preserve_items"] = ["B", "C"]
        prompt = build_ready_prompt(
            answers,
            {
                "edit_request": "把白天改成下雪的冬日晚景",
                "edit_area": "整张图的天气和光线",
                "source_description": "街道中站着一个人",
                "custom_preserve": "建筑结构",
            },
            {"target": "ChatGPT Images（推荐）", "size": "auto", "quality": "medium"},
        )
        self.assertTrue(prompt.startswith("Edit the supplied image"))
        self.assertIn("EDIT PLAN", prompt)
        self.assertIn("整张图的天气和光线", prompt)
        self.assertIn("建筑结构", prompt)
        self.assertIn("keep all unrelated details stable", prompt)

    def test_multi_reference_prompt_records_reference_roles(self) -> None:
        answers = default_answers()
        answers["input_mode"] = "C"
        prompt = build_ready_prompt(
            answers,
            {"edit_request": "合成产品场景", "reference_roles": "图1提供产品，图2提供场景"},
            {"target": "通用生图工具", "size": "auto", "quality": "low"},
        )
        self.assertIn("combining the supplied reference images", prompt)
        self.assertIn("图1提供产品，图2提供场景", prompt)


if __name__ == "__main__":
    unittest.main()
