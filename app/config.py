from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    # Keep real environment variables authoritative over .env values.
    load_dotenv(override=False)
    # Also load from repository root explicitly in case process CWD differs.
    repo_env = Path(__file__).resolve().parents[1] / ".env"
    if repo_env.exists():
        load_dotenv(dotenv_path=repo_env, override=False)


def _normalize_runtime_env() -> None:
    """
    Strip surrounding whitespace/CR from selected env vars that are consumed by
    SDKs directly (not via Settings), e.g. GOOGLE_API_KEY.
    """
    if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY", "")

    keys = [
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "GOOGLE_GENAI_USE_VERTEXAI",
        "ANKOR_API_BASE_URL",
        "LIVE_MODEL",
        "APP_NAME",
    ]
    for key in keys:
        value = os.getenv(key)
        if value is not None:
            os.environ[key] = value.strip()


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip()
    if normalized == "":
        return default
    return normalized


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip()
    if normalized == "":
        return default
    try:
        return float(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid float for {name}: {value}") from exc


@dataclass(frozen=True)
class Settings:
    app_name: str
    live_model: str
    use_vertex_ai: bool
    google_cloud_project: Optional[str]
    google_cloud_location: Optional[str]
    ankor_api_base_url: str
    http_timeout_s: float
    manual_activity_signals: bool
    expose_tool_events: bool


def load_settings() -> Settings:
    _load_dotenv()
    _normalize_runtime_env()
    return Settings(
        app_name=_get_env("APP_NAME", "ankor-voice-agent"),
        live_model=_get_env("LIVE_MODEL", "gemini-live-2.5-flash-native-audio"),
        use_vertex_ai=_get_bool("GOOGLE_GENAI_USE_VERTEXAI", True),
        google_cloud_project=_get_env("GOOGLE_CLOUD_PROJECT"),
        google_cloud_location=_get_env("GOOGLE_CLOUD_LOCATION", "us-central1"),
        ankor_api_base_url=_get_env(
            "ANKOR_API_BASE_URL",
            "https://hjimvofwrmvwuonkyryl.supabase.co/functions/v1/api",
        ),
        http_timeout_s=_get_float("HTTP_TIMEOUT_S", 20.0),
        manual_activity_signals=_get_bool("MANUAL_ACTIVITY_SIGNALS", False),
        expose_tool_events=_get_bool("EXPOSE_TOOL_EVENTS", False),
    )


settings = load_settings()
