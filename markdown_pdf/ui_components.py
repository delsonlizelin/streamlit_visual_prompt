from __future__ import annotations

import base64
import inspect
import json
import re

import streamlit as st


def _component_v2(*args, **kwargs):  # noqa: ANN002, ANN003
    """Create a v2 component when supported, otherwise enable a native fallback."""
    component_api = getattr(st.components, "v2", None)
    return component_api.component(*args, **kwargs) if component_api is not None else None


_AUTO_ARTICLE_URL_INPUT = _component_v2(
    "auto_article_url_input",
    html="""
      <label for="article-url">文章网址</label>
      <input id="article-url" type="url" inputmode="url"
             autocomplete="url" autocapitalize="none" spellcheck="false"
             placeholder="https://mp.weixin.qq.com/s/...">
      <p>粘贴完整网址后自动读取，无需回车。</p>
    """,
    css="""
      :host { display: block; }
      label {
        display: block;
        margin: 0 0 .45rem;
        color: var(--st-text-color);
        font: 400 .875rem/1.35 var(--st-font);
      }
      input {
        width: 100%;
        min-height: 42px;
        box-sizing: border-box;
        padding: .5rem .75rem;
        border: 1px solid var(--st-border-color);
        border-radius: var(--st-base-radius);
        background: var(--st-background-color);
        color: var(--st-text-color);
        font: 400 1rem/1.4 var(--st-font);
        outline: none;
      }
      input:focus {
        border-color: var(--st-primary-color);
        box-shadow: 0 0 0 1px var(--st-primary-color);
      }
      p {
        margin: .4rem 0 0;
        color: var(--st-text-color);
        opacity: .68;
        font: 400 .82rem/1.45 var(--st-font);
      }
      @media (pointer: coarse) { input { min-height: 44px; } }
    """,
    js="""
      export default function(component) {
        const { parentElement, data, setStateValue } = component;
        const input = parentElement.querySelector("input");
        const incoming = typeof data?.value === "string" ? data.value : "";
        if (document.activeElement !== input && input.value !== incoming) {
          input.value = incoming;
        }

        let timer;
        const publish = () => {
          const value = input.value.trim();
          if (!value) {
            if (incoming) setStateValue("url", "");
            return;
          }
          const looksLikeUrl = /^(https?:\\/\\/)?[^\\s/]+\\.[^\\s]+$/i.test(value);
          if (looksLikeUrl && value !== incoming) setStateValue("url", value);
        };
        const schedule = (delay) => {
          window.clearTimeout(timer);
          timer = window.setTimeout(publish, delay);
        };
        const onInput = () => schedule(800);
        const onPaste = () => schedule(60);
        input.addEventListener("input", onInput);
        input.addEventListener("paste", onPaste);
        return () => {
          window.clearTimeout(timer);
          input.removeEventListener("input", onInput);
          input.removeEventListener("paste", onPaste);
        };
      }
    """,
)


_NATIVE_IMAGE_SHARE = _component_v2(
    "native_image_share",
    html="""
      <button type="button" hidden>分享长图</button>
      <p role="status" aria-live="polite"></p>
    """,
    css="""
      :host { display: block; }
      button {
        width: 100%;
        min-height: 42px;
        padding: .5rem 1rem;
        border: 1px solid var(--st-border-color);
        border-radius: var(--st-base-radius);
        background: var(--st-background-color);
        color: var(--st-text-color);
        font: 500 .9rem/1.4 var(--st-font);
        cursor: pointer;
      }
      button:active { background: var(--st-secondary-background-color); }
      p {
        margin: .35rem 0 0;
        color: var(--st-text-color);
        opacity: .72;
        font: 400 .8rem/1.4 var(--st-font);
      }
      p:empty { display: none; }
      @media (pointer: coarse) { button { min-height: 44px; } }
    """,
    js="""
      export default function(component) {
        const { parentElement, data } = component;
        const button = parentElement.querySelector("button");
        const status = parentElement.querySelector('[role="status"]');
        const supported = typeof navigator.share === "function" &&
          typeof window.File === "function";
        button.hidden = !supported;

        const share = async () => {
          status.textContent = "";
          try {
            const binary = window.atob(data.base64);
            const bytes = new Uint8Array(binary.length);
            for (let index = 0; index < binary.length; index += 1) {
              bytes[index] = binary.charCodeAt(index);
            }
            const file = new File([bytes], data.filename, { type: "image/png" });
            if (navigator.canShare && !navigator.canShare({ files: [file] })) {
              throw new Error("file-sharing-unavailable");
            }
            await navigator.share({
              files: [file],
              title: data.title,
            });
          } catch (error) {
            if (error?.name !== "AbortError") {
              status.textContent = "无法调出分享菜单，请长按图片或使用下载按钮。";
            }
          }
        };
        button.addEventListener("click", share);
        return () => button.removeEventListener("click", share);
      }
    """,
)


def auto_article_url_input(value: str, *, key: str) -> str:
    """Return a complete pasted or typed URL without requiring Enter."""
    if _AUTO_ARTICLE_URL_INPUT is None:
        return st.text_input(
            "文章网址",
            value=value,
            placeholder="https://mp.weixin.qq.com/s/...",
            help="粘贴完整网址后按 Enter 读取。",
            key=key,
        ).strip()
    result = _AUTO_ARTICLE_URL_INPUT(
        data={"value": value},
        default={"url": value},
        key=key,
        on_url_change=lambda: None,
    )
    return str(result.url or "").strip()


def native_image_share(png: bytes, filename: str, *, key: str) -> None:
    """Show the native file share action when the browser supports Web Share."""
    if _NATIVE_IMAGE_SHARE is None:
        return
    _NATIVE_IMAGE_SHARE(
        data={
            "base64": base64.b64encode(png).decode("ascii"),
            "filename": filename,
            "title": "文章摘要长图",
        },
        key=key,
    )


def compatible_file_uploader(label: str, *, max_upload_size: int, **kwargs):  # noqa: ANN003
    """Use per-widget upload limits when the installed Streamlit supports them."""
    parameters = inspect.signature(st.file_uploader).parameters
    if "max_upload_size" in parameters:
        kwargs["max_upload_size"] = max_upload_size
    return st.file_uploader(label, **kwargs)


def page_shell_styles() -> None:
    """Apply a restrained editorial shell shared by both tools."""
    st.markdown(
        """
        <style>
          @font-face {
            font-family: "Noto Sans SC";
            src: url("/app/static/fonts/NotoSansSC-VariableFont_wght.ttf") format("truetype");
            font-style: normal;
            font-weight: 100 900;
            font-display: swap;
          }
          :root {
            color-scheme: light;
            --ink: #191b1e;
            --muted: #626971;
            --rule: #d9dde0;
            --paper: #f1f3f4;
            --surface: #ffffff;
            --accent: #b84316;
          }
          .stApp {
            color: var(--ink);
            background: var(--paper);
            font-family: "Noto Sans SC", "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", sans-serif;
          }
          [data-testid="stAppViewContainer"],
          [data-testid="stAppViewContainer"] > div:has(> [data-testid="stHeader"]),
          [data-testid="stHeader"] {
            background-color: inherit !important;
          }
          [data-testid="stHeader"] {
            border-bottom: 1px solid var(--rule);
          }
          .block-container {
            max-width: 1240px;
            padding-top: calc(4.1rem + env(safe-area-inset-top));
            padding-bottom: 5rem;
          }
          h1, h2, h3 {
            color: var(--ink);
            letter-spacing: -.025em;
            text-wrap: balance;
          }
          h1 {
            max-width: 900px;
            font-family: "Noto Sans SC", "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", sans-serif;
            font-size: clamp(2.3rem, 3.8vw, 3.8rem);
            font-weight: 760;
            line-height: 1.05;
          }
          h2 {
            margin-top: 2.8rem;
            margin-bottom: .75rem;
            font-weight: 680;
          }
          .intro {
            max-width: 680px;
            color: var(--muted);
            font-size: 1rem;
            line-height: 1.68;
            margin: .65rem 0 1.5rem;
          }
          .mode-note { color: var(--muted); font-size: .82rem; line-height: 1.55; }
          [data-testid="stFileUploader"] {
            border: 1px solid var(--rule);
            border-radius: .75rem;
            background: var(--surface);
            padding: .45rem .75rem;
          }
          [data-testid="stTextArea"] textarea,
          [data-testid="stTextInput"] input,
          [data-testid="stSelectbox"] > div > div {
            border-radius: .625rem;
            background: var(--surface);
          }
          [data-testid="stMetric"] {
            border-top: 1px solid var(--rule);
            padding-top: .75rem;
          }
          .stButton button, .stDownloadButton button {
            border-radius: .625rem;
            font-weight: 600;
            transition: border-color 140ms ease-out, background 140ms ease-out, color 140ms ease-out;
          }
          .stButton button[kind="primary"],
          .stDownloadButton button[kind="primary"] {
            border-color: var(--accent);
            background: var(--accent);
          }
          .stButton button[kind="primary"]:hover,
          .stDownloadButton button[kind="primary"]:hover {
            border-color: #92350f;
            background: #92350f;
          }
          .stButton button:focus-visible,
          .stDownloadButton button:focus-visible,
          [data-testid="stTextArea"] textarea:focus-visible,
          [data-testid="stTextInput"] input:focus-visible {
            outline: 3px solid color-mix(in srgb, var(--accent) 28%, transparent);
            outline-offset: 2px;
          }
          [data-testid="stAlert"] {
            border-radius: .75rem;
          }
          [data-testid="stExpander"] {
            border-color: var(--rule);
            border-radius: .75rem;
            background: var(--surface);
          }
          [data-testid="stImage"] img {
            border-radius: .75rem;
            box-shadow: 0 18px 48px rgba(25, 27, 30, .12);
          }
          .summary-empty {
            min-height: 560px;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            padding: clamp(2rem, 5vw, 4.5rem);
            border: 1px solid var(--rule);
            border-radius: .75rem;
            background: var(--surface);
          }
          .summary-empty-rule {
            margin-bottom: auto;
            width: 3.5rem;
            height: 2px;
            background: var(--accent);
          }
          .summary-empty h3 {
            margin: 0 0 .75rem;
            color: var(--ink);
            font-size: 1.35rem;
          }
          .summary-empty p {
            max-width: 34rem;
            margin: 0;
            color: var(--muted);
            font-size: 1rem;
            line-height: 1.7;
          }
          .workbench-heading {
            display: grid;
            grid-template-columns: 2rem minmax(0, 1fr);
            gap: .6rem;
            align-items: baseline;
            margin: 1.15rem 0 .65rem;
            border-top: 1px solid var(--rule);
            padding-top: .8rem;
          }
          .workbench-heading span {
            color: var(--accent);
            font-size: .82rem;
            font-weight: 760;
            font-variant-numeric: tabular-nums;
            letter-spacing: .05em;
          }
          .workbench-heading h2 {
            margin: 0;
            font-size: 1.35rem;
            line-height: 1.25;
          }
          div[data-testid="stButton"]:has(button[key="open_summary_page"]),
          div[data-testid="stButton"]:has(button[key="open_pdf_page"]) {
            width: fit-content;
          }
          footer { visibility: hidden; }

          @media (max-width: 768px) {
            .block-container {
              padding-top: calc(4.1rem + env(safe-area-inset-top));
              padding-right: 1rem;
              padding-bottom: 3rem;
              padding-left: 1rem;
            }
            h1 {
              margin-top: .5rem;
              line-height: 1.04;
            }
            h2 { font-size: 1.35rem; line-height: 1.25; }
            h3 { font-size: 1rem; line-height: 1.3; }
            .intro {
              margin-bottom: .65rem;
              font-size: 1rem;
              line-height: 1.65;
            }
            .summary-empty {
              min-height: 320px;
              padding: 1.5rem;
            }
            [data-testid="stFileUploader"] { padding: .2rem .35rem; }
            [data-testid="stTextArea"] textarea {
              min-height: 260px !important;
              height: 38vh !important;
              max-height: 360px !important;
            }
            [data-testid="stRadio"] div[role="radiogroup"] {
              flex-wrap: wrap;
              row-gap: .35rem;
            }
            .stButton button, .stDownloadButton button { min-height: 44px; }
            [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {
              flex-flow: row wrap !important;
              gap: .65rem !important;
            }
            [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"] {
              width: calc(50% - .325rem) !important;
              min-width: 0 !important;
              flex: 1 1 calc(50% - .325rem) !important;
            }
            [data-testid="stMetric"] {
              min-height: 82px;
              padding: .55rem .65rem;
              border: 0;
              border-top: 1px solid var(--rule);
              border-radius: 0;
            }
            [data-testid="stMetricValue"] { font-size: 1.35rem; }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_navigation(current: str) -> None:
    """Render one compact top-level control to the app's other page."""
    if current == "pdf":
        if st.button(
            "摘要长图",
            icon=":material/summarize:",
            key="open_summary_page",
        ):
            st.switch_page("pages/2_文章摘要.py")
    elif current == "summary":
        if st.button(
            "Markdown PDF",
            icon=":material/arrow_back:",
            key="open_pdf_page",
        ):
            st.switch_page("streamlit_app.py")
    else:
        raise ValueError(f"Unknown page: {current}")


def clipboard_button(value: str, label: str, *, key: str) -> None:
    """Render a small trusted iframe button that copies text to the clipboard."""
    element_id = "copy-" + re.sub(r"[^a-zA-Z0-9_-]+", "-", key).strip("-")
    value_json = json.dumps(value, ensure_ascii=False)
    label_json = json.dumps(label, ensure_ascii=False)
    markup = f"""
        <button id="{element_id}" type="button">{label}</button>
        <script>
          const button = document.getElementById({json.dumps(element_id)});
          const value = {value_json};
          const label = {label_json};
          async function copyValue() {{
            try {{
              await navigator.clipboard.writeText(value);
            }} catch (error) {{
              const area = document.createElement("textarea");
              area.value = value;
              area.style.position = "fixed";
              area.style.opacity = "0";
              document.body.appendChild(area);
              area.select();
              document.execCommand("copy");
              area.remove();
            }}
            button.textContent = "已复制";
            window.setTimeout(() => {{ button.textContent = label; }}, 1600);
          }}
          button.addEventListener("click", copyValue);
        </script>
        <style>
          body {{ margin: 0; background: transparent; }}
          button {{
            min-height: 38px;
            padding: 0 14px;
            border: 1px solid #d9dde0;
            border-radius: 10px;
            background: #fff;
            color: #191b1e;
            font: 500 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            cursor: pointer;
          }}
          button:hover {{ border-color: #626971; }}
        </style>
        """
    if hasattr(st, "iframe"):
        st.iframe(markup, width="content", height=42)
    else:
        st.components.v1.html(markup, height=42)
