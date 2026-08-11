# Markdown PDF

把中文、英文或双语 Markdown 转成适合长时间阅读的 PDF。应用提供三种确定性版式：

- **电脑端**：A4、11.2 pt 正文、静态宋体页眉、左下页码。
- **平板端**：132 × 201 mm、12.1 pt 正文，匹配 iPad mini 竖屏比例、无页眉、居中页码。
- **手机端**：9:16、12.8 pt 正文、短行宽、无页眉、居中页码。

裸 URL 会使用专门的折行与弱化样式，避免长路径、查询参数和 DOI 越过窄页面边界；带可读标题的普通链接保持正文样式。

## 导出前检查

编辑器会在生成前运行本地兼容性检查，提示：

- 未闭合代码围栏、缺少或重复 H1、标题层级跳跃；
- Mermaid、LaTeX 公式、原始 HTML 和不安全链接；
- 本地图片、缺失替代文本、宽表格和长 URL。

检查不调用模型，也不会修改原始 Markdown。未闭合代码围栏或不安全链接等红色错误会阻止导出，其余提醒允许继续生成。PDF 生成后还会检查空白页，以及正文中的链接、段落、列表、代码、表格、图片和引用是否越过页面内容边界。

## 不需要模型 API

转换过程完全在 Streamlit 应用的运行环境中完成，不调用 DeepSeek、OpenAI 或其他模型服务。只有在未来增加“自动摘要、自动起标题、内容润色”等 AI 功能时，才需要可选的模型 API 密钥。

## 依赖

Python 依赖写在 `requirements.txt`：

- `streamlit[pdf]`：界面、上传、PDF 预览与下载；
- `Markdown`：Markdown 解析；
- `bleach`：清理上传内容中的不安全 HTML；
- `playwright`：控制 Chromium 生成带 CSS 分页的 PDF。

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

不需要在 Secrets 中配置任何 API key。

## 支持范围

支持普通标题、段落、强调、引用、列表、链接、HTTPS 图片、代码和简单表格。复杂公式、宽表格、Mermaid 或学术论文型排版不在第一版范围内；导出前检查会明确提示这些内容。

## 测试

```bash
python -m unittest discover -s tests -v
python scripts/smoke_test.py
```

冒烟测试会用同一份中英文回归文稿生成 A4、Tablet 和 9:16 三份 PDF，并在检测到空白页或正文溢出时失败。

## 后续版本

下一阶段会在现有转换器之外增加一个独立的“格式调整与摘要”工作区：先诊断 Markdown 与当前渲染器不兼容的写法，再以可审阅差异的方式修复；摘要功能则提供不同长度、要点和结构化输出。详细约束见 [`ROADMAP.md`](ROADMAP.md)。AI 功能需要可选的模型 API，但基础 PDF 转换始终保持无 API 可用。
