# Visual Prompt

一个模板优先的 Streamlit 生图提示词构建器。它不会直接调用 API 出图，而是把用途、视觉语言、构图和硬性约束整理成可直接复制给 ChatGPT Images 或 OpenAI Image API 的提示词。

## 当前设计

- 13 组用途模板：人物肖像、海报、杂志封面、信息图、学术单页、手写学习笔记、产品主图、标志概念、绘本、四格漫画、贴纸和角色设定等
- 19 组可组合视觉模式：纪实摄影、电影剧照、编辑插画、现代主义/旅行海报、水彩、手写笔记、动漫、美式漫画、涂色书、像素、黏土 3D、纸艺、Risograph、版画、蓝图、复古胶片、拼贴和赛博霓虹等
- 模板会预填全部相关选项，用户仍可逐项微调
- 常用选项默认展开，镜头、线条、材质、保留项和排除项收进高级微调
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
