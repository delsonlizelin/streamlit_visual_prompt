# Visual Prompt

一个模板优先的 Streamlit 生图提示词构建器。它不会直接调用 API 出图，而是把用途、视觉语言、构图和硬性约束整理成可直接复制给 ChatGPT Images 或 OpenAI Image API 的提示词。

## 当前设计

- 三条并列工作流：从零生成、修改一张图、融合多张参考图
- 改图流程优先询问“改什么、改哪里、保留什么”；原图描述仅在有歧义时填写
- 首页精选 7 组主流用途和 8 组主流视觉风格；长尾模板仍可通过“更多”开关访问
- 完整库含 13 组用途和 19 组可组合视觉模式
- 模板会预填全部相关选项，用户仍可逐项微调
- 微调按内容与用途、视觉风格、构图与版式、高级控制分层，默认收起
- 支持精确的画内文字、输出尺寸和质量意图
- 结果优先提供一键复制与下载；完整预览和 JSON 放入折叠区域
- 固定 Light 主题，并针对手机窄屏优化间距和触控高度

## 为什么重新设计

GPT Image 2 对用途、精确文字、多图参考、复杂版式和编辑边界的理解已经明显增强。新版本不再把大量“质量词”和负面词当作主流程，而是把提示词稳定地组织为：目标与用途 → 视觉方向 → 构图 → 精确文字 → 保留/排除约束 → 输出意图。

该工具只生成提示词，不需要 OpenAI API Key。

## 本地运行

```bash
cd /Users/delsonlizelin/CodingSpace/Projects/streamlit_proj/visual_prompt
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## 文件

- `app.py`：页面与提示词生成逻辑
- `presets.py`：用途模板和经典视觉模式
- `question_bank.py`：可微调选项数据
- `tests/`：预设和提示词测试
