from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from normalizer import normalize_block
from parser import iter_input_files, parse_document
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
    approved_dir = Path(args.approved_dir)
    result_dir = Path(args.result_dir)

    existing = _list_effective_files(output_dir)
    if existing and not _confirm_overwrite(output_dir, approved_dir, result_dir, existing):
        print("aborted. existing files were kept.")
        return 0

    if existing:
        _clear_generated_files(output_dir, approved_dir, result_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    total_items = 0
    files = iter_input_files(input_path)
    for path in files:
        parsed = parse_document(path)
        blocks = split_blocks(parsed.blocks, max_chars=args.max_chars)
        for block in blocks:
            for item in normalize_block(block, status="draft"):
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
    approved_dir: Path,
    result_dir: Path,
    existing: list[Path],
) -> bool:
    print(f"found {len(existing)} existing file(s) in {output_dir}.")
    print("Continuing will delete existing generated files under:")
    print(f"- {output_dir}")
    print(f"- {approved_dir}")
    print(f"- {result_dir}")
    answer = input("Overwrite and continue? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def _clear_generated_files(*dirs: Path) -> None:
    for directory in dirs:
        for path in _list_effective_files(directory):
            path.unlink()
            print(f"deleted: {path}")


def cmd_validate(args) -> int:
    issues = validate_dir(Path(args.input))
    for issue in issues:
        print(f"{issue.level}: {issue.path}: {issue.message}")
    print(f"done. issues={len(issues)}")
    return 1 if any(i.level == "error" for i in issues) else 0


def cmd_promote(args) -> int:
    input_dir = Path(args.input)
    result_dir = Path(args.result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(input_dir.rglob("*.md")):
        target = result_dir / path.name
        shutil.copy2(path, target)
        count += 1
        print(f"promoted: {path} -> {target}")
    print(f"done. promoted={count}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline document-to-knowledge Markdown generator.")
    sub = parser.add_subparsers(dest="command", required=True)

    parse_cmd = sub.add_parser("parse", help="Parse input documents to intermediate Markdown.")
    parse_cmd.add_argument("--input", default=str(CURRENT_DIR / "input"))
    parse_cmd.add_argument("--output", default=str(CURRENT_DIR / "parsed"))
    parse_cmd.set_defaults(func=cmd_parse)

    draft_cmd = sub.add_parser("draft", help="Generate draft knowledge files.")
    draft_cmd.add_argument("--input", default=str(CURRENT_DIR / "input"))
    draft_cmd.add_argument("--output", default=str(CURRENT_DIR / "drafts"))
    draft_cmd.add_argument("--approved-dir", default=str(CURRENT_DIR / "approved"))
    draft_cmd.add_argument("--result-dir", default=str(CURRENT_DIR / "result"))
    draft_cmd.add_argument("--max-chars", type=int, default=8000)
    draft_cmd.set_defaults(func=cmd_draft)

    validate_cmd = sub.add_parser("validate", help="Validate generated Markdown files.")
    validate_cmd.add_argument("--input", default=str(CURRENT_DIR / "drafts"))
    validate_cmd.set_defaults(func=cmd_validate)

    promote_cmd = sub.add_parser("promote", help="Copy reviewed files to result.")
    promote_cmd.add_argument("--input", default=str(CURRENT_DIR / "approved"))
    promote_cmd.add_argument("--result-dir", default=str(CURRENT_DIR / "result"))
    promote_cmd.set_defaults(func=cmd_promote)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
