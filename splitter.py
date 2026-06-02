from __future__ import annotations

import re
from dataclasses import replace
from typing import List

from schemas import ParsedBlock


def split_blocks(blocks: List[ParsedBlock], max_chars: int = 8000) -> List[ParsedBlock]:
    """合并和切分解析片段以适配生成长度。"""
    result: List[ParsedBlock] = []
    for block in _merge_parent_child_blocks(blocks):
        result.extend(_split_one(block, max_chars=max_chars))
    return [b for b in result if len(b.content.strip()) >= 40]


def _merge_parent_child_blocks(blocks: List[ParsedBlock]) -> List[ParsedBlock]:
    """把短父章节与其子章节合并。"""
    merged: List[ParsedBlock] = []
    current: ParsedBlock | None = None
    current_prefix = ""

    for block in blocks:
        prefix = _section_prefix(block.source_section)
        if prefix and _is_parent_section(prefix, block.content):
            if current:
                merged.append(current)
            current = block
            current_prefix = prefix
            continue

        if current and current_prefix and _is_child_section(current_prefix, block.source_section):
            current = replace(
                current,
                content=f"{current.content.rstrip()}\n\n{block.content.strip()}",
                pages=sorted(set(current.pages + block.pages)),
            )
            continue

        if current:
            merged.append(current)
            current = None
            current_prefix = ""
        merged.append(block)

    if current:
        merged.append(current)
    return merged


def _section_prefix(title: str) -> str:
    """提取章节号的父级前缀。"""
    match = re.match(r"^(\d+\.\d+)(?!\.)", title.strip())
    return match.group(1) if match else ""


def _is_parent_section(prefix: str, content: str) -> bool:
    """判断片段是否像需要合并的父章节。"""
    return bool(prefix) and len(content.strip()) < 120


def _is_child_section(parent_prefix: str, title: str) -> bool:
    """判断章节是否属于指定父章节。"""
    return title.strip().startswith(f"{parent_prefix}.")


def _split_one(block: ParsedBlock, max_chars: int) -> List[ParsedBlock]:
    """按最大字符数切分单个片段。"""
    content = block.content.strip()
    if len(content) <= max_chars:
        return [block]

    candidates = _split_by_heading_window(content, max_chars)

    output: List[ParsedBlock] = []
    for idx, text in enumerate(candidates, start=1):
        text = text.strip()
        if not text:
            continue
        output.append(replace(
            block,
            source_section=f"{block.source_section} / 片段 {idx}",
            content=text,
            order=block.order * 100 + idx,
        ))
    return output


def _split_by_heading_window(text: str, max_chars: int) -> List[str]:
    """优先按标题窗口切分长文本。"""
    sections = [p.strip() for p in re.split(r"\n(?=#{2,4}\s+)", text) if p.strip()]
    if len(sections) <= 1:
        return _split_by_paragraph_window(text, max_chars)

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for section in sections:
        if current and current_len + len(section) > max_chars:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        if len(section) > max_chars:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            chunks.extend(_split_by_paragraph_window(section, max_chars))
            continue
        current.append(section)
        current_len += len(section)
    if current:
        chunks.append("\n\n".join(current))
    return chunks or [text]


def _split_by_paragraph_window(text: str, max_chars: int) -> List[str]:
    """按段落窗口切分长文本。"""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for paragraph in paragraphs:
        if current and current_len + len(paragraph) > max_chars:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += len(paragraph)
    if current:
        chunks.append("\n\n".join(current))
    return chunks or [text]
