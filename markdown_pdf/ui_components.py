from __future__ import annotations

import json
import re

import streamlit as st


def page_shell_styles() -> None:
    """Apply the shared desktop and mobile shell without covering content."""
    st.markdown(
        """
        <style>
          :root { --ink: #252525; --muted: #6f6f6f; --rule: #dedede; }
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
