#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from app_config import get_draft_config
from normalizer import normalize_block
from parser import iter_input_files, parse_document
from schemas import ParsedBlock
from splitter import split_blocks
from validator import validate_dir
from writer import write_item


IGNORED_EXISTING_FILES = {".gitkeep", ".DS_Store"}


def cmd_parse(args) -> int:
    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = iter_input_files(input_path)
    for path in files:
        parsed = parse_document(path)
        out = output_dir / f"{path.stem}.parsed.md"
        out.write_text(parsed.markdown, encoding="utf-8")
        print(f"parsed: {path} -> {out}")
    print(f"done. files={len(files)}")
    return 0


def cmd_draft(args) -> int:
    input_path = Path(args.input)
    output_dir = Path(args.output)

    existing = _list_effective_files(output_dir)
    if existing and not _confirm_overwrite(output_dir, existing):
        print("aborted. existing files were kept.")
        return 0

    if existing:
        _clear_generated_files(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    total_items = 0
    draft_config = get_draft_config()
    max_chars = args.max_chars or draft_config.max_chars
    files = iter_input_files(input_path)
    for path in files:
        parsed = parse_document(path)
        blocks = split_blocks(parsed.blocks, max_chars=max_chars)
        blocks = _attach_block_context(
            blocks,
            context_chars=draft_config.context_chars,
            outline_max_sections=draft_config.outline_max_sections,
        )
        for block in blocks:
            for item in normalize_block(block, status=args.status):
                write_item(item, output_dir)
                total_items += 1
        print(f"drafted: {path} blocks={len(blocks)}")
    print(f"done. files={len(files)} draft_items={total_items} output={output_dir}")
    return 0


def _list_effective_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(
        p for p in path.rglob("*")
        if p.is_file() and p.name not in IGNORED_EXISTING_FILES
    )


def _confirm_overwrite(
    output_dir: Path,
    existing: list[Path],
) -> bool:
    print(f"found {len(existing)} existing file(s) in {output_dir}.")
    print("Continuing will delete existing generated files under:")
    print(f"- {output_dir}")
    answer = input("Overwrite and continue? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def _clear_generated_files(*dirs: Path) -> None:
    for directory in dirs:
        for path in _list_effective_files(directory):
            path.unlink()
            print(f"deleted: {path}")


def _attach_block_context(
    blocks: List[ParsedBlock],
    context_chars: int,
    outline_max_sections: int,
) -> List[ParsedBlock]:
    if context_chars <= 0:
        return blocks

    outline = _document_outline(blocks, outline_max_sections)
    output: List[ParsedBlock] = []
    for idx, block in enumerate(blocks):
        parts = []
        if outline:
            parts.append(f"文档章节目录：\n{outline}")
        if block.category_description:
            parts.append(
                "知识大类说明：\n"
                f"大类：{block.category}\n"
                f"说明：{block.category_description}\n"
                f"关键词：{', '.join(block.category_keywords)}"
            )
        if idx > 0:
            parts.append(
                "上一片段摘要：\n"
                f"章节：{blocks[idx - 1].source_section}\n"
                f"{_compact_context_text(blocks[idx - 1].content, context_chars // 2)}"
            )
        if idx + 1 < len(blocks):
            parts.append(
                "下一片段摘要：\n"
                f"章节：{blocks[idx + 1].source_section}\n"
                f"{_compact_context_text(blocks[idx + 1].content, context_chars // 2)}"
            )
        output.append(ParsedBlock(
            source_doc=block.source_doc,
            source_section=block.source_section,
            content=block.content,
            pages=block.pages,
            order=block.order,
            context="\n\n".join(parts),
            category=block.category,
            category_description=block.category_description,
            category_keywords=block.category_keywords,
        ))
    return output


def _document_outline(blocks: List[ParsedBlock], max_sections: int) -> str:
    sections = []
    seen = set()
    for block in blocks:
        section = block.source_section.strip()
        if not section or section in seen:
            continue
        seen.add(section)
        sections.append(f"- {section}")
        if len(sections) >= max_sections:
            remaining = len(blocks) - len(sections)
            if remaining > 0:
                sections.append(f"- ... 其余 {remaining} 个片段")
            break
    return "\n".join(sections)


def _compact_context_text(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if limit <= 0 or len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "..."


def cmd_validate(args) -> int:
    issues = validate_dir(Path(args.input))
    for issue in issues:
        print(f"{issue.level}: {issue.path}: {issue.message}")
    print(f"done. issues={len(issues)}")
    return 1 if any(i.level == "error" for i in issues) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline document-to-knowledge Markdown generator.")
    sub = parser.add_subparsers(dest="command", required=True)

    parse_cmd = sub.add_parser("parse", help="Parse input documents to intermediate Markdown.")
    parse_cmd.add_argument("--input", default=str(CURRENT_DIR / "input"))
    parse_cmd.add_argument("--output", default=str(CURRENT_DIR / "parsed"))
    parse_cmd.set_defaults(func=cmd_parse)

    draft_cmd = sub.add_parser("draft", help="Generate draft knowledge files.")
    draft_cmd.add_argument("--input", default=str(CURRENT_DIR / "input"))
    draft_cmd.add_argument("--output", default=str(CURRENT_DIR / "result"))
    draft_cmd.add_argument("--status", default="active", choices=["draft", "active"])
    draft_cmd.add_argument("--max-chars", type=int, default=None)
    draft_cmd.set_defaults(func=cmd_draft)

    validate_cmd = sub.add_parser("validate", help="Validate generated Markdown files.")
    validate_cmd.add_argument("--input", default=str(CURRENT_DIR / "result"))
    validate_cmd.set_defaults(func=cmd_validate)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
