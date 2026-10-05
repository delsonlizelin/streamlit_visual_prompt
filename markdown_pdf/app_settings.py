"""One settings resolver shared by the Streamlit page and the local CLI."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
import tomllib
from typing import Any, Mapping

from summarizer.deepseek import DEFAULT_BASE_URL, resolve_model

PROJECT_DIR = Path(__file__).resolve().parent
SETTING_NAMES = (
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_BASE_URL",
    "YOUTUBE_ENABLED",
    "YOUTUBE_PROXY_URL",
)


@dataclass(frozen=True)
class AppSettings:
    api_key: str
    model: str
    base_url: str
    youtube_enabled: bool
    youtube_proxy_url: str | None = None


def running_on_streamlit_cloud() -> bool:
    """Streamlit Community Cloud mounts the repository under /mount/src."""
    return str(PROJECT_DIR).startswith("/mount/src/")


def youtube_library_available() -> bool:
    return importlib.util.find_spec("youtube_transcript_api") is not None


def _flag(value: Any) -> bool | None:
    cleaned = str(value or "").strip().lower()
    if cleaned in {"1", "true", "yes", "on"}:
        return True
    if cleaned in {"0", "false", "no", "off"}:
        return False
    return None  # "auto" or unset


def resolve_settings(values: Mapping[str, Any]) -> AppSettings:
    """Normalize raw secrets/env values; unknown models fall back to the default."""
    youtube_flag = _flag(values.get("YOUTUBE_ENABLED"))
    if youtube_flag is None:
        # YouTube blocks most datacenter IPs, so the feature is local-only by default.
        youtube_flag = not running_on_streamlit_cloud()
    proxy = str(values.get("YOUTUBE_PROXY_URL") or "").strip() or None
    return AppSettings(
        api_key=str(values.get("DEEPSEEK_API_KEY") or "").strip(),
        model=resolve_model(str(values.get("DEEPSEEK_MODEL") or "")),
        base_url=str(values.get("DEEPSEEK_BASE_URL") or "").strip() or DEFAULT_BASE_URL,
        youtube_enabled=youtube_flag and youtube_library_available(),
        youtube_proxy_url=proxy,
    )


def load_local_settings(project_dir: Path = PROJECT_DIR) -> AppSettings:
    """CLI settings: `.streamlit/secrets.toml`, overridden by environment variables."""
    values: dict[str, Any] = {}
    secrets = project_dir / ".streamlit" / "secrets.toml"
    if secrets.is_file():
        values.update(tomllib.loads(secrets.read_text("utf-8")))
    for name in SETTING_NAMES:
        if os.environ.get(name):
            values[name] = os.environ[name]
    return resolve_settings(values)
