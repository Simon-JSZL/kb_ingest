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
    "category",
    "category_keywords",
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
    """校验目录下所有生成的 Markdown 文件。"""
    issues: List[ValidationIssue] = []
    paths = sorted(input_dir.rglob("*.md"))
    for path in paths:
        issues.extend(validate_file(path))
    issues.extend(_validate_taxonomy_spread(paths))
    return issues


def validate_file(path: Path) -> List[ValidationIssue]:
    """校验单个生成 Markdown 文件。"""
    issues: List[ValidationIssue] = []
    try:
        metadata, body = _read_markdown(path)
    except Exception as exc:
        return [ValidationIssue(path, "error", f"无法读取 Markdown Front Matter: {exc}")]

    for field in REQUIRED_FIELDS:
        if field not in metadata:
            issues.append(ValidationIssue(path, "error", f"缺少必填字段: {field}"))

    for field in ("source_order", "source_pages", "source_trace"):
        if field not in metadata:
            issues.append(ValidationIssue(path, "warning", f"缺少来源追踪字段: {field}"))

    for field in (
        "subcategory",
        "related_items",
    ):
        if field not in metadata:
            issues.append(ValidationIssue(path, "warning", f"缺少分类关系字段: {field}"))

    if metadata.get("doc_type") not in DOC_TYPES:
        issues.append(ValidationIssue(path, "error", f"doc_type 不合法: {metadata.get('doc_type')}"))

    if len(body) > 3000:
        issues.append(ValidationIssue(path, "warning", f"正文较长，建议继续拆分: {len(body)} 字符"))
    if len(body) < 200:
        issues.append(ValidationIssue(path, "warning", f"正文较短，可能信息不足: {len(body)} 字符"))

    headings = re.findall(r"^##\s+", body, re.M)
    if len(headings) < 5:
        issues.append(ValidationIssue(path, "warning", "二级标题少于 5 个，可能未遵照标准知识库结构"))

    for idx, title in enumerate((
        "核心内容",
        "适用边界",
        "使用要求",
        "关联能力",
        "来源依据",
    ), start=1):
        if not re.search(rf"^##\s+{idx}\.\s+.*{title}", body, re.M):
            issues.append(ValidationIssue(path, "warning", f"缺少或未对齐章节: ## {idx}. {title}"))

    issues.extend(_validate_section_content(path, body))
    issues.extend(_validate_key_tags_in_core_body(path, metadata, body))
    issues.extend(_validate_taxonomy_fields(path, metadata))
    return issues


def _read_markdown(path: Path) -> Tuple[Dict, str]:
    """读取 Markdown 的 YAML Front Matter 和正文。"""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not match:
        raise ValueError("缺少 YAML Front Matter")
    return yaml.safe_load(match.group(1)) or {}, match.group(2).strip()


def _validate_section_content(path: Path, body: str) -> List[ValidationIssue]:
    """检查核心章节是否存在空内容。"""
    issues: List[ValidationIssue] = []
    for idx, content in _numbered_sections(body).items():
        if idx in {4, 5}:
            continue
        if not content.strip():
            issues.append(ValidationIssue(path, "warning", f"章节内容为空: ## {idx}"))
    return issues


def _validate_key_tags_in_core_body(path: Path, metadata: Dict, body: str) -> List[ValidationIssue]:
    """检查关键缩写是否进入核心正文。"""
    core_body = _core_answer_body(body)
    issues: List[ValidationIssue] = []
    for tag in metadata.get("tags") or []:
        tag_text = str(tag).strip()
        if not _looks_like_acronym(tag_text):
            continue
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(tag_text)}(?![A-Za-z0-9])", core_body):
            continue
        issues.append(ValidationIssue(path, "warning", f"关键缩写未进入正文核心章节: {tag_text}"))
    return issues


def _numbered_sections(body: str) -> Dict[int, str]:
    """按二级编号标题切分正文。"""
    matches = list(re.finditer(r"^##\s+(\d+)\.\s+.*$", body, flags=re.M))
    sections: Dict[int, str] = {}
    for pos, match in enumerate(matches):
        start = match.end()
        end = matches[pos + 1].start() if pos + 1 < len(matches) else len(body)
        sections[int(match.group(1))] = body[start:end].strip()
    return sections


def _core_answer_body(body: str) -> str:
    """提取回答相关的核心正文区域。"""
    match = re.search(r"^##\s+4\.\s+关联能力\s*$", body, flags=re.M)
    return body[:match.start()] if match else body


def _looks_like_acronym(value: str) -> bool:
    """判断文本是否像需要保留的缩写。"""
    return bool(re.fullmatch(r"[A-Z][A-Z0-9]{1,12}", value))


def _validate_taxonomy_fields(path: Path, metadata: Dict) -> List[ValidationIssue]:
    """检查分类和关联字段的结构质量。"""
    issues: List[ValidationIssue] = []
    category = str(metadata.get("category") or "").strip()
    subcategory = str(metadata.get("subcategory") or "").strip()

    if subcategory and category and subcategory == category:
        issues.append(ValidationIssue(path, "warning", "小类与大类相同，分类层级可能未细化"))
    related_items = metadata.get("related_items") or []
    if related_items and not isinstance(related_items, list):
        issues.append(ValidationIssue(path, "warning", "related_items 应为列表"))
    for idx, item in enumerate(related_items if isinstance(related_items, list) else [], start=1):
        if not isinstance(item, dict):
            issues.append(ValidationIssue(path, "warning", f"related_items[{idx}] 应为对象"))
            continue
        for field in ("大类标题", "小类标题", "关联说明", "关联度"):
            if not str(item.get(field) or "").strip():
                issues.append(ValidationIssue(path, "warning", f"related_items[{idx}] 缺少字段: {field}"))
        if item.get("关联度") not in {"极高", "高", "一般", "低"}:
            issues.append(ValidationIssue(path, "warning", f"related_items[{idx}] 关联度不规范"))
    return issues


def _validate_taxonomy_spread(paths: List[Path]) -> List[ValidationIssue]:
    """检查一批文件的分类是否退化。"""
    if len(paths) < 3:
        return []
    metadata_list: List[Tuple[Path, Dict]] = []
    for path in paths:
        try:
            metadata, _ = _read_markdown(path)
        except Exception:
            continue
        metadata_list.append((path, metadata))
    if len(metadata_list) < 3:
        return []

    categories = {str(meta.get("category") or "").strip() for _, meta in metadata_list}
    subcategories = {str(meta.get("subcategory") or "").strip() for _, meta in metadata_list}
    keywords = {
        tuple(str(item).strip() for item in (meta.get("category_keywords") or []))
        for _, meta in metadata_list
    }
    issues: List[ValidationIssue] = []
    if len(categories - {""}) == 1 and len(subcategories - {""}) <= 1 and len(metadata_list) >= 5:
        issues.append(ValidationIssue(paths[0], "warning", "所有文件的大类/小类几乎一致，分类可能退化"))
    if len(keywords - {()}) == 1 and len(metadata_list) >= 5:
        issues.append(ValidationIssue(paths[0], "warning", "所有文件的 category_keywords 完全一致，关键词区分度不足"))
    return issues
