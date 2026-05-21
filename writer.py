from __future__ import annotations

import re
from pathlib import Path

import yaml

from schemas import KnowledgeItem


def write_item(item: KnowledgeItem, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{_safe_filename(item.kb_id)}.md"
    path.write_text(render_markdown(item), encoding="utf-8")
    return path


def render_markdown(item: KnowledgeItem) -> str:
    metadata = yaml.safe_dump(
        item.metadata(),
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip()
    return f"---\n{metadata}\n---\n\n{item.body.strip()}\n"


def _safe_filename(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "kb-item"

