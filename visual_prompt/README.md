# AI Image Prompt Style Builder

一个基于 Streamlit 的视觉风格决策问卷工具。它不直接生成图片，而是把用户选择转成可复制的结构化需求文本，供 GPT / ChatGPT 图像生成 / Midjourney / Stable Diffusion 等工具继续使用。

## 功能

- 22 道数据驱动题目（单选 + 多选）
- 每个选项包含说明、术语解释和提示词片段
- 输出四类结果：
  - 结构化需求清单
  - 英文提示词骨架
  - 中文 GPT 指令
  - JSON 结果
- 支持下载 `.txt` / `.json`

## 目录结构

- `app.py`：Streamlit 主应用
- `question_bank.py`：题库与可微调项定义
- `requirements.txt`：依赖

## 本地运行

```bash
cd /Users/delsonlizelin/CodingSpace/Projects/streamlit_proj/visual_prompt
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud 部署

1. 推送本目录到 GitHub 仓库
2. 在 Streamlit Cloud 选择该仓库和 `app.py`
3. 确认依赖文件为 `requirements.txt`
4. 部署完成后即可分享链接
