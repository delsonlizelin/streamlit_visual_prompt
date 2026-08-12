# Markdown PDF

一个轻量的双页面 Streamlit 应用：把中文、英文或双语 Markdown 转成适合长时间阅读的 PDF，或从 Markdown、TXT、普通文本型 PDF 生成忠实、可下载的文章摘要。两个页面使用顶部的单一按钮切换，不依赖侧边栏；页面为 Streamlit Cloud 固定工具栏保留安全区域，并针对手机窄屏调整编辑器、选项、指标和触控按钮。

PDF 页面提供三种确定性版式：

- **电脑端**：A4、11.2 pt 正文、静态宋体页眉、左下页码。
- **平板端**：132 × 201 mm、12.1 pt 正文，匹配 iPad mini 竖屏比例、无页眉、居中页码。
- **手机端**：9:16、12.8 pt 正文、短行宽、无页眉、居中页码。

裸 URL 会使用专门的折行与弱化样式，避免长路径、查询参数和 DOI 越过窄页面边界；带可读标题的普通链接保持正文样式。

## 从 GPT 网页会话生成 Markdown

页面顶部提供“复制 GPT Markdown 格式要求”按钮。按钮只复制渲染器的格式约束，不显示提示词正文，也不包含主题、风格或写作要求；可以直接附加到用户自己的 GPT 提示词中。

提示词要求模型只生成一个 H1，以 H2/H3 组织正文，使用渲染器支持的标准 Markdown，并排除 HTML、YAML front matter、公式、Mermaid、脚注、本地图片和整篇外层代码围栏。生成结果仍会经过页面现有的导出前检查。

## 导出前检查

编辑器会在生成前运行本地兼容性检查，提示：

- 未闭合代码围栏、缺少或重复 H1、标题层级跳跃；
- Mermaid、LaTeX 公式、原始 HTML 和不安全链接；
- 本地图片、缺失替代文本、宽表格和长 URL。

检查不调用模型，也不会修改原始 Markdown。未闭合代码围栏或不安全链接等红色错误会阻止导出，其余提醒允许继续生成。PDF 生成后还会检查空白页，以及正文中的链接、段落、列表、代码、表格、图片和引用是否越过页面内容边界。

## 文章摘要

独立的“文章摘要”页面支持上传或粘贴 Markdown，并提供：

- 上传 Markdown、UTF-8 TXT 和普通文本型 PDF，或直接粘贴内容；
- 快速概览、核心摘要、分章节摘要三种方式；
- 跟随原文、简体中文、English 三种输出语言；
- 一键复制、下载 Markdown，或把摘要直接发送到 Markdown PDF 页面；
- 生成 Desktop、Tablet、Mobile 三种紧凑摘要 PDF；
- 生成 Tablet 或 Mobile 的 3× 连续高清 PNG 长图；
- 保留重要数字、日期、名称、限制条件、因果关系和否定表达；
- 把文档与系统指令分隔，降低文稿中提示词注入内容的影响。
- 一键复制当前实际使用的摘要系统提示词，便于在其他对话中复用。

上传文件后，下载文件名默认继承原文件名；直接粘贴时仍使用 `summary` 或 `longread`。生成完成后，页面按“下载 → 预览 → 编辑”的顺序展示，不需要先越过大编辑框；PDF 或长图的下载按钮会同时出现在页面顶部和导出区域。摘要页首版只使用 DeepSeek Chat Completions API。请求使用 JSON 输出，单篇上限为 30 万字符；未配置 Key 时页面仍能打开和编辑，但生成按钮会禁用。点击生成即表示同意把当前输入发送到 DeepSeek，不再提供重复确认框。

提示词要求中性、直接和高信息密度：快速概览为 3–5 句无列表短文；核心摘要提供一个明确结论和 3–5 个不重复要点；分章节摘要每节限制 1–2 个要点。只有原文存在实质性限制时才添加“限制与例外”，也不会把作者观点、推测写成已证实事实。输出只使用当前 PDF 渲染器稳定支持的 Markdown；原文没有明确结论时，模型不得替作者补出结论。

PDF 使用没有封面和目录的紧凑摘要模板。长图沿用 Tablet / Mobile 的字体、行宽与段落节奏，把分页改成一张连续图片；如果摘要长到超过 Chromium 的稳定单图高度，页面会提示改用 PDF 或 Markdown。

## API 与隐私

PDF 转换和上传 PDF 的文字提取完全在 Streamlit 应用的运行环境中完成，不调用 DeepSeek、OpenAI 或其他模型服务。只有点击摘要页的“生成摘要”后，正文才会发送到 DeepSeek。

本地开发时，复制示例文件并填写自己的 Key：

```bash
cd markdown_pdf
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

```toml
DEEPSEEK_API_KEY = "your-key"
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
```

`.streamlit/secrets.toml` 已被 Git 忽略。不要把真实 Key 写进代码、提交到仓库或粘贴到公开日志。

应用启动时会自动读取 Key，但只有点击“生成摘要”才会调用 DeepSeek 和消耗额度。

## 依赖

Python 依赖写在 `requirements.txt`：

- `streamlit[pdf]`：界面、上传、PDF 预览与下载；
- `Markdown`：Markdown 解析；
- `bleach`：清理上传内容中的不安全 HTML；
- `pypdf`：从普通文本型 PDF 提取带页面顺序的可编辑文本；
- `playwright`：控制 Chromium 生成带 CSS 分页的 PDF。

摘要请求使用 Python 标准库发送，没有引入 DeepSeek SDK 或额外 AI 框架。

仓库根目录的 `packages.txt` 会让 Streamlit Community Cloud 安装：

- `chromium`：PDF 渲染引擎；
- `fonts-noto-cjk`：云端中文字体；
- `fonts-liberation`：英文字体后备。

Paged.js 已作为本地静态资源放在 `longread_pdf/assets/`，运行时不需要 Node.js，也不会从 CDN 下载脚本。

## 本地运行

建议使用 Python 3.12：

```bash
cd markdown_pdf
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

macOS 会自动寻找 `/Applications/Google Chrome.app`。Linux 默认寻找 `chromium`。也可以通过 `CHROMIUM_PATH` 指定浏览器可执行文件。

## 部署到 Streamlit Community Cloud

1. 把仓库推送到 GitHub。
2. 在 Streamlit Community Cloud 中新建应用。
3. 选择这个仓库与分支，入口文件填写 `markdown_pdf/streamlit_app.py`。
4. Python 版本选择 3.12，然后部署。
5. 如果需要摘要，在应用的 **Settings → Secrets** 中填写与上方相同的三项配置，然后重启应用。

只使用 PDF 功能时，不需要配置任何 API Key。

## 支持范围

支持普通标题、段落、强调、引用、列表、链接、HTTPS 图片、代码和简单表格。复杂公式、宽表格、Mermaid 或学术论文型排版不在第一版范围内；导出前检查会明确提示这些内容。

## 测试

```bash
python -m unittest discover -s tests -v
python scripts/smoke_test.py
python scripts/summary_export_smoke_test.py
```

第一组冒烟测试会用同一份中英文回归文稿生成 A4、Tablet 和 9:16 三份长文 PDF。第二组会生成三种紧凑摘要 PDF、Tablet / Mobile 两张高清长图，并把生成的 PDF 重新导入以验证文字提取；检测到空白页、正文溢出、解析失败或异常图片尺寸时会失败。

## 后续版本

PDF 与摘要保持为两个独立页面，但摘要可以一键送入 PDF 编辑器。复杂的 AI 格式润色、多模型切换、账号和历史记录暂不加入；是否继续开发以真实使用反馈为准。详细边界见 [`ROADMAP.md`](ROADMAP.md)。
