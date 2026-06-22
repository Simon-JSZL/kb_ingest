from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml


CURRENT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = CURRENT_DIR / "config" / "config.yaml"


@dataclass(frozen=True)
class LlmConfig:
    """LLM 调用配置。"""
    enabled: bool = False
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout_seconds: int = 120
    max_tokens: int = 4096
    temperature: float = 0.1


@dataclass(frozen=True)
class DraftConfig:
    """草稿生成阶段的切分和上下文配置。"""
    max_chars: int = 3600
    context_chars: int = 800
    outline_max_sections: int = 40


@lru_cache(maxsize=1)
def get_llm_config() -> LlmConfig:
    """读取 LLM 配置。"""
    raw = _read_config().get("llm", {})
    if not isinstance(raw, dict):
        raw = {}

    return LlmConfig(
        enabled=_as_bool(raw.get("enabled"), False),
        base_url=str(raw.get("base_url") or ""),
        api_key=str(raw.get("api_key") or ""),
        model=str(raw.get("model") or ""),
        timeout_seconds=_as_int(raw.get("timeout_seconds"), 120),
        max_tokens=_as_int(raw.get("max_tokens"), 4096),
        temperature=_as_float(raw.get("temperature"), 0.1),
    )


@lru_cache(maxsize=1)
def get_draft_config() -> DraftConfig:
    """读取草稿生成配置。"""
    raw = _read_config().get("draft", {})
    if not isinstance(raw, dict):
        raw = {}

    return DraftConfig(
        max_chars=_as_int(raw.get("max_chars"), 3600),
        context_chars=_as_int(raw.get("context_chars"), 800),
        outline_max_sections=_as_int(raw.get("outline_max_sections"), 40),
    )


def _read_config() -> Dict[str, Any]:
    """读取 YAML 配置文件并返回字典。"""
    if not DEFAULT_CONFIG_PATH.exists():
        return {}
    data = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _as_int(value: Any, default: int) -> int:
    """把配置值转换为整数。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    """把配置值转换为浮点数。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    """把配置值转换为布尔值。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default
