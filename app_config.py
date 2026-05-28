from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml


CURRENT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = CURRENT_DIR / "config" / "config.yaml"


@dataclass(frozen=True)
class LlmConfig:
    enabled: bool = False
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout_seconds: int = 120
    max_tokens: int = 4096
    temperature: float = 0.1


@dataclass(frozen=True)
class DraftConfig:
    max_chars: int = 3600
    context_chars: int = 800
    outline_max_sections: int = 40


@lru_cache(maxsize=1)
def get_llm_config() -> LlmConfig:
    raw = _read_config().get("llm", {})
    if not isinstance(raw, dict):
        raw = {}

    return LlmConfig(
        enabled=_env_bool("KB_LLM_ENABLED", _as_bool(raw.get("enabled"), False)),
        base_url=os.environ.get("KB_LLM_BASE_URL", str(raw.get("base_url") or "")),
        api_key=os.environ.get("KB_LLM_API_KEY", str(raw.get("api_key") or "")),
        model=os.environ.get("KB_LLM_MODEL", str(raw.get("model") or "")),
        timeout_seconds=_env_int("KB_LLM_TIMEOUT_SECONDS", raw.get("timeout_seconds"), 120),
        max_tokens=_env_int("KB_LLM_MAX_TOKENS", raw.get("max_tokens"), 4096),
        temperature=_env_float("KB_LLM_TEMPERATURE", raw.get("temperature"), 0.1),
    )


@lru_cache(maxsize=1)
def get_draft_config() -> DraftConfig:
    raw = _read_config().get("draft", {})
    if not isinstance(raw, dict):
        raw = {}

    return DraftConfig(
        max_chars=_env_int("KB_DRAFT_MAX_CHARS", raw.get("max_chars"), 3600),
        context_chars=_env_int("KB_DRAFT_CONTEXT_CHARS", raw.get("context_chars"), 800),
        outline_max_sections=_env_int("KB_DRAFT_OUTLINE_MAX_SECTIONS", raw.get("outline_max_sections"), 40),
    )


def _read_config() -> Dict[str, Any]:
    path = Path(os.environ.get("KB_INGEST_CONFIG", DEFAULT_CONFIG_PATH))
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return _as_bool(value, default)


def _env_int(name: str, value: Any, default: int) -> int:
    raw = os.environ.get(name, value)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, value: Any, default: float) -> float:
    raw = os.environ.get(name, value)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default
