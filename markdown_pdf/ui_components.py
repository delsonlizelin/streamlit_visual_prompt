from __future__ import annotations

import json
import re

import streamlit as st


def page_navigation() -> None:
    """Render stable labels for the two lightweight app pages."""
    with st.sidebar:
        st.page_link(
            "streamlit_app.py",
            label="Markdown PDF",
            icon=":material/picture_as_pdf:",
        )
        st.page_link(
            "pages/2_文章摘要.py",
            label="文章摘要",
            icon=":material/summarize:",
        )


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
