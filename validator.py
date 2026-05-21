from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

from schemas import DOC_TYPES, ValidationIssue


REQUIRED_FIELDS = [
    "kb_id",
    "title",
    "doc_type",
    "domain",
    "business_modules",
    "source_doc",
    "source_version",
    "source_section",
    "owner",
    "confidentiality",
    "risk_level",
    "applicable_roles",
    "tags",
    "status",
]


def validate_dir(input_dir: Path) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    for path in sorted(input_dir.rglob("*.md")):
        issues.extend(validate_file(path))
    return issues


def validate_file(path: Path) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    try:
        metadata, body = _read_markdown(path)
    except Exception as exc:
        return [ValidationIssue(path, "error", f"无法读取 Markdown Front Matter: {exc}")]

    for field in REQUIRED_FIELDS:
        if field not in metadata:
            issues.append(ValidationIssue(path, "error", f"缺少必填字段: {field}"))

    if metadata.get("doc_type") not in DOC_TYPES:
        issues.append(ValidationIssue(path, "error", f"doc_type 不合法: {metadata.get('doc_type')}"))

    if metadata.get("status") == "active" and metadata.get("review_status") != "approved":
        issues.append(ValidationIssue(path, "warning", "active 条目建议先设置 review_status: approved"))

    if len(body) > 3000:
        issues.append(ValidationIssue(path, "warning", f"正文较长，建议继续拆分: {len(body)} 字符"))
    if len(body) < 200:
        issues.append(ValidationIssue(path, "warning", f"正文较短，可能信息不足: {len(body)} 字符"))

    headings = re.findall(r"^##\s+", body, re.M)
    if len(headings) < 3:
        issues.append(ValidationIssue(path, "warning", "二级标题过少，可能未遵照标准结构"))

    return issues


def _read_markdown(path: Path) -> Tuple[Dict, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not match:
        raise ValueError("缺少 YAML Front Matter")
    return yaml.safe_load(match.group(1)) or {}, match.group(2).strip()

