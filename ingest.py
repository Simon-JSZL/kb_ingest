#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import List
from uuid import uuid4

import yaml

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from app_config import get_draft_config
from normalizer import fallback_failed_block, normalize_block
from parser import iter_input_files, parse_document
from schemas import ParsedBlock
from splitter import split_blocks
from validator import validate_dir
from writer import write_item


IGNORED_EXISTING_FILES = {".gitkeep", ".DS_Store"}
PROGRESS_FILENAME = ".draft_progress.json"


def cmd_parse(args) -> int:
    """执行解析子命令。"""
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
    """执行草稿生成子命令。"""
    input_path = Path(args.input)
    output_dir = Path(args.output)

    existing = _list_effective_files(output_dir)
    progress_path = output_dir / PROGRESS_FILENAME
    resume_state = None
    if existing:
        action = _choose_existing_result_action(output_dir, existing)
        if action == "exit":
            print("aborted. existing files were kept.")
            return 0
        if action == "rebuild":
            _clear_generated_files(output_dir)
        elif action == "retry":
            return _retry_failed_files(output_dir, status=args.status)
        elif action == "resume":
            resume_state = _load_progress(progress_path)
            if not resume_state:
                print(f"aborted. no usable checkpoint found at {progress_path}.")
                return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    run_timestamp = (
        str(resume_state.get("run_timestamp"))
        if resume_state
        else _make_timestamp()
    )
    run_trace_id = (
        str(resume_state.get("run_trace_id"))
        if resume_state
        else uuid4().hex[:8]
    )
    total_items = int(resume_state.get("total_items", 0)) if resume_state else 0
    source_order = int(resume_state.get("source_order", 0)) if resume_state else 0
    draft_config = get_draft_config()
    max_chars = args.max_chars or draft_config.max_chars
    files = iter_input_files(input_path)
    start_file_index = int(resume_state.get("file_index", 0)) if resume_state else 0
    start_block_index = int(resume_state.get("block_index", 0)) if resume_state else 0

    for file_index, path in enumerate(files):
        if file_index < start_file_index:
            continue
        parsed = parse_document(path)
        blocks = split_blocks(parsed.blocks, max_chars=max_chars)
        blocks = _attach_block_context(
            blocks,
            context_chars=draft_config.context_chars,
            outline_max_sections=draft_config.outline_max_sections,
        )
        block_start = start_block_index if file_index == start_file_index else 0
        for block_index, block in enumerate(blocks):
            if block_index < block_start:
                continue
            _save_progress(
                progress_path,
                input_path=input_path,
                output_dir=output_dir,
                files=files,
                run_timestamp=run_timestamp,
                run_trace_id=run_trace_id,
                source_order=source_order,
                total_items=total_items,
                file_index=file_index,
                block_index=block_index,
                status="running",
            )
            try:
                items = normalize_block(block, status=args.status)
            except SystemExit as exc:
                print(f"WARNING: block failed with SystemExit({exc.code}); writing failed fallback")
                items = fallback_failed_block(block, status=args.status)
            except Exception as exc:
                print(f"WARNING: block failed with {type(exc).__name__}: {exc}; writing failed fallback")
                items = fallback_failed_block(block, status=args.status)
            if not items:
                items = fallback_failed_block(block, status=args.status)
            source_order, written = _write_items(
                items,
                output_dir,
                block,
                source_order=source_order,
                run_timestamp=run_timestamp,
                run_trace_id=run_trace_id,
            )
            total_items += written
            _save_progress(
                progress_path,
                input_path=input_path,
                output_dir=output_dir,
                files=files,
                run_timestamp=run_timestamp,
                run_trace_id=run_trace_id,
                source_order=source_order,
                total_items=total_items,
                file_index=file_index,
                block_index=block_index + 1,
                status="running",
            )
        print(f"drafted: {path} blocks={len(blocks)}")
        start_block_index = 0
    if progress_path.exists():
        progress_path.unlink()
    print(f"done. files={len(files)} draft_items={total_items} output={output_dir}")
    return 0


def _list_effective_files(path: Path) -> list[Path]:
    """列出目录下需要考虑的已有文件。"""
    if not path.exists():
        return []
    return sorted(
        p for p in path.rglob("*")
        if p.is_file() and p.name not in IGNORED_EXISTING_FILES
    )


def _write_items(
    items,
    output_dir: Path,
    block: ParsedBlock,
    *,
    source_order: int,
    run_timestamp: str,
    run_trace_id: str,
) -> tuple[int, int]:
    written = 0
    for item in items:
        source_order += 1
        item.source_order = source_order
        item.source_pages = sorted(set(block.pages))
        item.source_trace = _source_trace(block)
        write_item(
            item,
            output_dir,
            source_title=Path(block.source_doc).stem,
            timestamp=run_timestamp,
            trace_id=run_trace_id,
        )
        written += 1
    return source_order, written


def _retry_failed_files(output_dir: Path, status: str) -> int:
    failed_files = [path for path in _list_effective_files(output_dir) if "failed" in path.stem.lower()]
    if not failed_files:
        print("done. failed_files=0 retried=0")
        return 0

    run_timestamp = _make_timestamp()
    run_trace_id = uuid4().hex[:8]
    retried = 0
    succeeded = 0
    still_failed = 0
    for path in failed_files:
        block = _block_from_failed_file(path)
        if not block:
            print(f"WARNING: skipped failed file without chunk source: {path}")
            continue
        try:
            items = normalize_block(block, status=status)
        except SystemExit as exc:
            print(f"WARNING: retry failed with SystemExit({exc.code}); keeping failed fallback: {path}")
            items = fallback_failed_block(block, status=status)
        except Exception as exc:
            print(f"WARNING: retry failed with {type(exc).__name__}: {exc}; keeping failed fallback: {path}")
            items = fallback_failed_block(block, status=status)
        if not items:
            items = fallback_failed_block(block, status=status)

        source_order = max(int(block.order or 0) - 1, 0)
        _, written = _write_items(
            items,
            output_dir,
            block,
            source_order=source_order,
            run_timestamp=run_timestamp,
            run_trace_id=run_trace_id,
        )
        if written:
            path.unlink()
        retried += 1
        if any(item.review_status == "failed" for item in items):
            still_failed += 1
        else:
            succeeded += 1
    print(f"done. failed_files={len(failed_files)} retried={retried} succeeded={succeeded} still_failed={still_failed}")
    return 0


def _block_from_failed_file(path: Path) -> ParsedBlock | None:
    text = path.read_text(encoding="utf-8")
    metadata = _front_matter(text)
    source = _failed_chunk_source(text)
    if not source:
        return None
    return ParsedBlock(
        source_doc=str(metadata.get("source_doc") or path.stem),
        source_section=str(metadata.get("source_section") or ""),
        content=source,
        pages=[int(page) for page in metadata.get("source_pages") or [] if str(page).isdigit()],
        order=int(metadata.get("source_order") or 0),
        category=str(metadata.get("category") or ""),
        category_keywords=[str(item) for item in metadata.get("category_keywords") or []],
        source_doc_description=str(metadata.get("source_doc_description") or ""),
        subcategory=str(metadata.get("subcategory") or ""),
        category_path=[str(item) for item in metadata.get("category_path") or []],
        related_categories=[str(item) for item in metadata.get("related_categories") or []],
        relation_notes=[str(item) for item in metadata.get("relation_notes") or []],
        related_items=metadata.get("related_items") or [],
    )


def _front_matter(text: str) -> dict:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    data = yaml.safe_load(text[4:end]) or {}
    return data if isinstance(data, dict) else {}


def _failed_chunk_source(text: str) -> str:
    marker = "## failed_chunk_source"
    start = text.find(marker)
    if start < 0:
        return ""
    source = text[start + len(marker):].strip()
    if source.startswith("```"):
        first_line = source.find("\n")
        if first_line >= 0:
            source = source[first_line + 1:]
        if source.endswith("```"):
            source = source[:-3]
    return source.strip()


def _choose_existing_result_action(output_dir: Path, existing: list[Path]) -> str:
    """询问用户如何处理已有生成结果。"""
    print(f"found {len(existing)} existing file(s) in {output_dir}.")
    print("Choose how to continue:")
    print("1. delete and rebuild")
    print("2. resume from checkpoint")
    print("3. retry failed files")
    print("4. exit")
    answer = input("Select [1/2/3/4]: ").strip().lower().translate(
        str.maketrans({"１": "1", "２": "2", "３": "3", "４": "4"})
    )
    if answer.startswith("1") or answer in {"d", "delete", "rebuild", "r"}:
        return "rebuild"
    if answer.startswith("2") or answer in {"resume", "continue", "c"}:
        return "resume"
    if answer.startswith("3") or answer in {"retry", "failed", "f"}:
        return "retry"
    return "exit"


def _load_progress(path: Path) -> dict | None:
    """读取断点续传状态。"""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WARNING: failed to read checkpoint: {exc}")
        return None
    if not isinstance(data, dict):
        return None
    return data


def _save_progress(
    path: Path,
    *,
    input_path: Path,
    output_dir: Path,
    files: list[Path],
    run_timestamp: str,
    run_trace_id: str,
    source_order: int,
    total_items: int,
    file_index: int,
    block_index: int,
    status: str,
    error: str = "",
) -> None:
    """保存 draft 断点续传状态。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    current_file = files[file_index] if 0 <= file_index < len(files) else None
    payload = {
        "version": 1,
        "status": status,
        "error": error,
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "run_timestamp": run_timestamp,
        "run_trace_id": run_trace_id,
        "source_order": source_order,
        "total_items": total_items,
        "file_index": file_index,
        "block_index": block_index,
        "current_file": str(current_file) if current_file else "",
        "current_file_name": current_file.name if current_file else "",
        "files": [str(path) for path in files],
        "updated_at": _make_timestamp(),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _make_timestamp() -> str:
    """生成用于文件名和断点记录的本地时间戳。"""
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _clear_generated_files(*dirs: Path) -> None:
    """删除指定目录下的已有生成文件。"""
    for directory in dirs:
        for path in _list_effective_files(directory):
            path.unlink()
            print(f"deleted: {path}")


def _attach_block_context(
    blocks: List[ParsedBlock],
    context_chars: int,
    outline_max_sections: int,
) -> List[ParsedBlock]:
    """为片段附加目录和邻近片段上下文。"""
    if context_chars <= 0:
        return blocks

    outline = _document_outline(blocks, outline_max_sections)
    output: List[ParsedBlock] = []
    for idx, block in enumerate(blocks):
        parts = []
        if outline:
            parts.append(f"文档章节目录：\n{outline}")
        if block.category or block.subcategory or block.category_keywords:
            parts.append(
                "知识分类：\n"
                f"大类标题：{block.category}\n"
                f"小类标题：{block.subcategory}\n"
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
        output.append(replace(
            block,
            context="\n\n".join(parts),
        ))
    return output


def _document_outline(blocks: List[ParsedBlock], max_sections: int) -> str:
    """生成文档片段目录摘要。"""
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
    """压缩上下文文本到指定长度。"""
    compact = " ".join(text.split())
    if limit <= 0 or len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "..."


def _source_trace(block: ParsedBlock) -> str:
    """生成来源章节和页码追踪信息。"""
    parts = [f"section={block.source_section}"]
    if block.pages:
        parts.append(f"pages={','.join(map(str, sorted(set(block.pages))))}")
    return "; ".join(parts)


def cmd_validate(args) -> int:
    """执行校验子命令。"""
    issues = validate_dir(Path(args.input))
    for issue in issues:
        print(f"{issue.level}: {issue.path}: {issue.message}")
    print(f"done. issues={len(issues)}")
    return 1 if any(i.level == "error" for i in issues) else 0


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
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
    """命令行入口。"""
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
