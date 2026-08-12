"""Composable presets for the Visual Prompt builder.

Task templates establish layout and communication goals. Visual modes then
override only aesthetic dimensions, so users can combine the two and continue
fine-tuning every field in the UI.
"""

from __future__ import annotations

from typing import Any


Preset = dict[str, Any]


TASK_TEMPLATES: dict[str, Preset] = {
    "自由创作": {
        "description": "不预设用途，让模型根据主体自行组织画面。",
        "values": {"input_mode": "A", "aspect_ratio": "F"},
    },
    "自然人物肖像": {
        "description": "真实、克制、不过度磨皮的人物照片或身份敏感改图。",
        "values": {
            "purpose": "A", "subject_type": "A", "priority": "A", "aspect_ratio": "C",
            "medium": "A", "realism_level": "A", "composition": "B", "camera_angle": "B",
            "subject_scale": "B", "detail_level": "A", "lighting": "A", "texture": "D",
            "mood": "B", "background_complexity": "C", "additional_elements": "A",
            "tuning_strength": "A", "avoid_items": ["A", "B", "E", "J"],
        },
    },
    "社交媒体海报": {
        "description": "主体抓眼、层级明确，并为标题或文案预留安全区域。",
        "values": {
            "purpose": "C", "priority": "E", "aspect_ratio": "E", "composition": "E",
            "subject_scale": "D", "detail_level": "C", "color_scheme": "A", "mood": "F",
            "background_complexity": "F", "additional_elements": "C", "tuning_strength": "C",
            "avoid_items": ["B", "E", "J"],
        },
    },
    "杂志封面": {
        "description": "编辑摄影与克制排版结合，适合封面、人物专访和专题头图。",
        "values": {
            "purpose": "C", "priority": "B", "aspect_ratio": "C", "medium": "A",
            "realism_level": "A", "composition": "E", "camera_angle": "B", "subject_scale": "B",
            "color_scheme": "B", "lighting": "B", "texture": "D", "mood": "A",
            "background_complexity": "B", "additional_elements": "C", "tuning_strength": "B",
            "avoid_items": ["B", "E", "J"],
        },
    },
    "知识信息图": {
        "description": "清楚的阅读顺序、数据层级、标注与可读文字，适合知识分享。",
        "values": {
            "purpose": "E", "subject_type": "F", "priority": "C", "aspect_ratio": "C",
            "medium": "E", "realism_level": "D", "composition": "D", "camera_angle": "E",
            "subject_scale": "D", "linework": "B", "shape_language": "B", "detail_level": "C",
            "color_scheme": "C", "lighting": "E", "texture": "A", "mood": "A",
            "background_complexity": "E", "additional_elements": "E", "tuning_strength": "C",
            "avoid_items": ["B", "E", "F", "J"],
        },
    },
    "学术海报 / 单页幻灯": {
        "description": "白底、精确数据、较少装饰，适合研究海报和演示文稿单页。",
        "values": {
            "purpose": "E", "priority": "C", "aspect_ratio": "D", "medium": "E",
            "realism_level": "D", "composition": "D", "camera_angle": "E", "linework": "B",
            "shape_language": "B", "detail_level": "B", "color_scheme": "C", "lighting": "E",
            "texture": "A", "mood": "A", "background_complexity": "E",
            "additional_elements": "E", "tuning_strength": "B", "avoid_items": ["E", "F", "J"],
        },
    },
    "手写学习笔记": {
        "description": "把知识整理成真实纸面笔记，强调标题、重点、箭头和自然书写层级。",
        "values": {
            "purpose": "E", "subject_type": "F", "priority": "C", "aspect_ratio": "C",
            "medium": "B", "realism_level": "C", "composition": "D", "camera_angle": "E",
            "subject_scale": "D", "linework": "D", "shape_language": "C", "detail_level": "B",
            "color_scheme": "C", "lighting": "A", "texture": "B", "mood": "B",
            "background_complexity": "E", "additional_elements": "E", "tuning_strength": "B",
            "avoid_items": ["B", "E", "J"],
        },
    },
    "产品电商主图": {
        "description": "干净背景、准确材质和轮廓，避免无关装饰与错误标签。",
        "values": {
            "purpose": "F", "subject_type": "C", "priority": "A", "aspect_ratio": "A",
            "medium": "A", "realism_level": "A", "composition": "A", "camera_angle": "B",
            "subject_scale": "D", "detail_level": "A", "lighting": "A", "mood": "A",
            "background_complexity": "A", "additional_elements": "A", "tuning_strength": "A",
            "avoid_items": ["B", "E", "F", "J"],
        },
    },
    "品牌标志概念": {
        "description": "原创、简洁、可缩放的标志概念，强调轮廓和负空间。",
        "values": {
            "purpose": "F", "subject_type": "F", "priority": "C", "aspect_ratio": "A",
            "medium": "E", "realism_level": "E", "composition": "A", "camera_angle": "E",
            "subject_scale": "D", "linework": "B", "shape_language": "B", "detail_level": "E",
            "color_scheme": "C", "lighting": "E", "texture": "A", "mood": "A",
            "background_complexity": "A", "additional_elements": "A", "tuning_strength": "D",
            "avoid_items": ["E", "H", "J"],
        },
    },
    "故事绘本场景": {
        "description": "主体和环境共同叙事，画面亲切，有清晰的情绪与动作。",
        "values": {
            "purpose": "D", "subject_type": "E", "priority": "D", "aspect_ratio": "B",
            "medium": "I", "realism_level": "C", "composition": "B", "camera_angle": "B",
            "subject_scale": "D", "linework": "D", "shape_language": "C", "detail_level": "B",
            "color_scheme": "B", "lighting": "A", "texture": "C", "mood": "B",
            "background_complexity": "D", "additional_elements": "A", "tuning_strength": "C",
            "avoid_items": ["B", "E", "I", "J"],
        },
    },
    "四格漫画": {
        "description": "把叙事拆成连续视觉节拍，保证角色、场景和阅读方向一致。",
        "values": {
            "purpose": "D", "subject_type": "B", "priority": "C", "aspect_ratio": "E",
            "medium": "C", "realism_level": "C", "composition": "D", "camera_angle": "A",
            "subject_scale": "D", "linework": "A", "shape_language": "D", "detail_level": "C",
            "color_scheme": "C", "lighting": "C", "texture": "A", "mood": "C",
            "background_complexity": "C", "additional_elements": "D", "tuning_strength": "C",
            "avoid_items": ["B", "E", "J"],
        },
    },
    "贴纸 / 表情包": {
        "description": "粗轮廓、夸张表情、小尺寸高可读，适合聊天和社交传播。",
        "values": {
            "purpose": "B", "subject_type": "A", "priority": "E", "aspect_ratio": "A",
            "medium": "C", "realism_level": "D", "composition": "A", "camera_angle": "A",
            "subject_scale": "B", "linework": "A", "shape_language": "D", "detail_level": "D",
            "color_scheme": "A", "lighting": "D", "texture": "A", "mood": "C",
            "background_complexity": "A", "additional_elements": "B", "tuning_strength": "D",
            "avoid_items": ["B", "E", "H", "J"],
        },
    },
    "角色设定表": {
        "description": "同一角色的全身、局部与多角度视图，强调身份和服装一致。",
        "values": {
            "purpose": "D", "subject_type": "A", "priority": "A", "aspect_ratio": "B",
            "medium": "B", "realism_level": "C", "composition": "D", "camera_angle": "E",
            "subject_scale": "C", "linework": "B", "detail_level": "A", "color_scheme": "C",
            "lighting": "C", "texture": "A", "mood": "A", "background_complexity": "B",
            "additional_elements": "F", "tuning_strength": "B", "avoid_items": ["B", "E", "I", "J"],
        },
    },
}


VISUAL_MODES: dict[str, Preset] = {
    "沿用用途模板": {"description": "不额外覆盖视觉语言。", "values": {}},
    "自然纪实摄影": {
        "description": "真实皮肤与材料、自然光、轻微胶片颗粒，不过度修饰。",
        "values": {"medium": "A", "realism_level": "A", "linework": "C", "shape_language": "C", "color_scheme": "B", "lighting": "A", "texture": "D"},
    },
    "电影剧照": {
        "description": "明确镜头与戏剧光影，保留环境叙事和电影色彩。",
        "values": {"medium": "A", "realism_level": "A", "composition": "C", "camera_angle": "D", "color_scheme": "C", "lighting": "B", "texture": "D", "background_complexity": "D"},
    },
    "极简编辑插画": {
        "description": "克制色板、简化形体与充足留白，适合文章头图。",
        "values": {"medium": "B", "realism_level": "D", "composition": "B", "linework": "C", "shape_language": "B", "detail_level": "D", "color_scheme": "C", "lighting": "E", "texture": "B", "background_complexity": "B"},
    },
    "现代主义海报": {
        "description": "大胆几何、强层级、有限色板与清楚的标题区域。",
        "values": {"medium": "E", "realism_level": "D", "composition": "E", "linework": "C", "shape_language": "B", "detail_level": "D", "color_scheme": "A", "lighting": "E", "texture": "A", "background_complexity": "F"},
    },
    "复古旅行海报": {
        "description": "简化地标形体、复古色板和旧式印刷质感。",
        "values": {"medium": "B", "realism_level": "C", "composition": "E", "linework": "B", "shape_language": "B", "detail_level": "C", "color_scheme": "E", "lighting": "C", "texture": "E"},
    },
    "水彩绘本": {
        "description": "柔和颜料晕染、纸张纹理和温暖叙事感。",
        "values": {"medium": "I", "realism_level": "C", "linework": "D", "shape_language": "C", "detail_level": "C", "color_scheme": "B", "lighting": "A", "texture": "C", "mood": "B"},
    },
    "手写笔记页": {
        "description": "真实纸张、自然手写、荧光笔重点与简洁的小图解。",
        "values": {"medium": "B", "realism_level": "C", "composition": "D", "camera_angle": "E", "linework": "D", "shape_language": "C", "detail_level": "B", "color_scheme": "C", "lighting": "A", "texture": "B", "background_complexity": "E", "additional_elements": "E"},
    },
    "清线动漫": {
        "description": "稳定线稿、赛璐璐阴影、清晰剪影和受控色彩。",
        "values": {"medium": "D", "realism_level": "C", "linework": "B", "shape_language": "D", "detail_level": "B", "color_scheme": "C", "lighting": "D", "texture": "A"},
    },
    "儿童涂色书": {
        "description": "白底、封闭粗线、无阴影与大块可上色区域。",
        "values": {"medium": "C", "realism_level": "D", "composition": "A", "linework": "A", "shape_language": "A", "detail_level": "D", "color_scheme": "D", "lighting": "E", "texture": "A", "background_complexity": "A"},
    },
    "美式漫画": {
        "description": "粗墨线、动态构图、高反差色彩和网点印刷感。",
        "values": {"medium": "C", "realism_level": "C", "composition": "C", "linework": "A", "shape_language": "D", "color_scheme": "A", "lighting": "B", "texture": "E"},
    },
    "像素艺术": {
        "description": "清晰像素簇、有限色板，不做模糊平滑处理。",
        "values": {"medium": "J", "realism_level": "D", "linework": "C", "shape_language": "B", "detail_level": "C", "color_scheme": "C", "lighting": "D", "texture": "A"},
    },
    "黏土 3D": {
        "description": "柔软黏土材质、圆润造型、微缩布景和柔光。",
        "values": {"medium": "G", "realism_level": "C", "linework": "C", "shape_language": "A", "detail_level": "C", "color_scheme": "B", "lighting": "A", "texture": "F"},
    },
    "纸艺立体模型": {
        "description": "分层纸张、切割边缘、手工阴影和微缩场景感。",
        "values": {"medium": "H", "realism_level": "C", "linework": "C", "shape_language": "B", "detail_level": "C", "color_scheme": "C", "lighting": "A", "texture": "B"},
    },
    "Risograph 独立印刷": {
        "description": "有限专色、颗粒、轻微套色偏移和纸面感。",
        "values": {"medium": "K", "realism_level": "D", "linework": "F", "shape_language": "B", "detail_level": "D", "color_scheme": "C", "lighting": "E", "texture": "E"},
    },
    "黑白版画": {
        "description": "强黑白关系、手工刀刻线条和高辨识剪影。",
        "values": {"medium": "K", "realism_level": "C", "linework": "F", "shape_language": "C", "detail_level": "C", "color_scheme": "D", "lighting": "B", "texture": "C"},
    },
    "技术蓝图": {
        "description": "正交或等距视图、技术线、网格、箭头和结构标注。",
        "values": {"medium": "F", "realism_level": "D", "composition": "D", "camera_angle": "E", "linework": "E", "shape_language": "B", "detail_level": "A", "color_scheme": "D", "lighting": "E", "texture": "G", "background_complexity": "E", "additional_elements": "E"},
    },
    "复古胶片": {
        "description": "自然曝光、低饱和年代色彩与克制胶片颗粒。",
        "values": {"medium": "A", "realism_level": "A", "linework": "C", "shape_language": "C", "color_scheme": "E", "lighting": "A", "texture": "D"},
    },
    "编辑拼贴": {
        "description": "照片切片、纸张、图形和文字层级构成的混合媒介。",
        "values": {"medium": "H", "realism_level": "C", "composition": "F", "linework": "D", "shape_language": "B", "detail_level": "C", "color_scheme": "C", "lighting": "C", "texture": "B", "background_complexity": "F"},
    },
    "赛博霓虹": {
        "description": "夜景、霓虹边缘光、深色环境和科技气氛。",
        "values": {"medium": "B", "realism_level": "C", "composition": "C", "shape_language": "B", "detail_level": "A", "color_scheme": "A", "lighting": "F", "texture": "A", "mood": "E", "background_complexity": "D"},
    },
}


def merged_values(task_name: str, visual_name: str) -> dict[str, str | list[str]]:
    """Return task values with the selected visual mode layered on top."""
    values: dict[str, str | list[str]] = dict(TASK_TEMPLATES[task_name]["values"])
    values.update(VISUAL_MODES[visual_name]["values"])
    return values
