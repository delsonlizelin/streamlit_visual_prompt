from __future__ import annotations

import base64
import json
import re

import streamlit as st


_AUTO_ARTICLE_URL_INPUT = st.components.v2.component(
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


_NATIVE_IMAGE_SHARE = st.components.v2.component(
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
    result = _AUTO_ARTICLE_URL_INPUT(
        data={"value": value},
        default={"url": value},
        key=key,
        on_url_change=lambda: None,
    )
    return str(result.url or "").strip()


def native_image_share(png: bytes, filename: str, *, key: str) -> None:
    """Show the native file share action when the browser supports Web Share."""
    _NATIVE_IMAGE_SHARE(
        data={
            "base64": base64.b64encode(png).decode("ascii"),
            "filename": filename,
            "title": "文章摘要长图",
        },
        key=key,
    )


def page_shell_styles() -> None:
    """Apply the shared desktop and mobile shell without covering content."""
    st.markdown(
        """
        <style>
          :root {
            color-scheme: light;
            --ink: #252525;
            --muted: #62686b;
            --rule: #d9dee1;
          }
          .stApp { color: var(--ink); }
          [data-testid="stAppViewContainer"],
          [data-testid="stAppViewContainer"] > div:has(> [data-testid="stHeader"]),
          [data-testid="stHeader"] {
            background-color: inherit !important;
          }
          [data-testid="stHeader"] {
            border-bottom: 1px solid color-mix(in srgb, currentColor 9%, transparent);
          }
          .block-container {
            max-width: 1240px;
            padding-top: calc(5.75rem + env(safe-area-inset-top));
            padding-bottom: 4rem;
          }
          h1 { letter-spacing: -.025em; }
          .intro {
            max-width: 780px;
            color: var(--muted);
            font-size: 1.02rem;
            line-height: 1.7;
            margin-bottom: 1.2rem;
          }
          .mode-note { color: var(--muted); font-size: .88rem; line-height: 1.55; }
          [data-testid="stFileUploader"] {
            border: 1px solid var(--rule);
            border-radius: .45rem;
            padding: .35rem .65rem;
          }
          [data-testid="stMetric"] { border-top: 1px solid var(--rule); padding-top: .65rem; }
          .stButton button, .stDownloadButton button { border-radius: .35rem; }
          footer { visibility: hidden; }

          @media (max-width: 768px) {
            .block-container {
              padding-top: calc(5.25rem + env(safe-area-inset-top));
              padding-right: 1rem;
              padding-bottom: 3rem;
              padding-left: 1rem;
            }
            h1 {
              margin-top: .35rem;
              font-size: clamp(2rem, 10vw, 2.5rem);
              line-height: 1.15;
            }
            h2 { font-size: 1.45rem; line-height: 1.25; }
            h3 { font-size: 1.18rem; line-height: 1.3; }
            .intro {
              margin-bottom: .85rem;
              font-size: .96rem;
              line-height: 1.65;
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
              border: 1px solid var(--rule);
              border-radius: .4rem;
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
            "切换到文章摘要",
            icon=":material/summarize:",
            key="open_summary_page",
        ):
            st.switch_page("pages/2_文章摘要.py")
    elif current == "summary":
        if st.button(
            "返回 Markdown PDF",
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
    st.iframe(
        f"""
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
            border: 1px solid #d8d8d8;
            border-radius: 6px;
            background: #fff;
            color: #252525;
            font: 500 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            cursor: pointer;
          }}
          button:hover {{ border-color: #9a9a9a; }}
        </style>
        """,
        width="content",
        height=42,
    )
