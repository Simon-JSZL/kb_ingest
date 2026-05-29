from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List

from schemas import ParsedBlock, ParsedDocument


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".md", ".markdown", ".txt"}


def iter_input_files(input_path: Path) -> List[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in SUPPORTED_EXTENSIONS else []
    files = [
        p for p in input_path.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files)


def parse_document(path: Path) -> ParsedDocument:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        markdown = _parse_pdf_text(path)
    elif suffix == ".docx":
        markdown = _parse_docx(path)
    elif suffix == ".doc":
        markdown = _parse_legacy_doc(path)
    elif suffix in {".md", ".markdown", ".txt"}:
        markdown = path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {path}")

    blocks = _markdown_to_blocks(path.name, markdown)
    category, category_description, category_keywords = _document_category_profile(path, markdown, blocks)
    blocks = [
        ParsedBlock(
            source_doc=block.source_doc,
            source_section=block.source_section,
            content=block.content,
            pages=block.pages,
            order=block.order,
            context=block.context,
            category=category,
            category_description=category_description,
            category_keywords=category_keywords,
        )
        for block in blocks
    ]
    return ParsedDocument(
        source_path=path,
        source_doc=path.name,
        markdown=markdown,
        blocks=blocks,
    )


def _parse_pdf_text(path: Path) -> str:
    """Extract embedded PDF text without OCR, layout models, or remote artifacts."""
    from docling_parse.pdf_parser import DoclingPdfParser
    from docling_parse.pdf_parsers import DecodePageConfig

    parser = DoclingPdfParser(loglevel="fatal")
    document = parser.load(path_or_stream=path)
    if document is None:
        raise RuntimeError(f"docling-parse could not load PDF: {path}")

    try:
        config = DecodePageConfig()
        config.keep_char_cells = True
        config.keep_shapes = False
        config.keep_bitmaps = False
        config.create_word_cells = False
        config.create_line_cells = True
        config.enforce_same_font = True

        lines: List[str] = []
        for page_no in range(1, document.number_of_pages() + 1):
            page = document.get_page(page_no, config=config)
            lines.extend(cell.text.strip() for cell in page.textline_cells if cell.text.strip())
        return _compact_pdf_lines(lines)
    finally:
        document.unload()


def _compact_pdf_lines(lines: List[str]) -> str:
    cleaned = [_normalize_pdf_line(line) for line in lines]
    cleaned = [line for line in cleaned if line and not _is_noise_line(line)]

    output: List[str] = []
    paragraph = ""
    for line in cleaned:
        heading = _heading_markdown(line)
        if heading:
            if paragraph:
                output.append(paragraph)
                paragraph = ""
            output.append(heading)
            continue

        if _should_keep_as_own_line(line):
            if paragraph:
                output.append(paragraph)
                paragraph = ""
            output.append(line)
            continue

        paragraph = _join_text(paragraph, line)

    if paragraph:
        output.append(paragraph)

    return _separate_embedded_headings("\n\n".join(output).strip())


def _normalize_pdf_line(line: str) -> str:
    line = line.replace("\u00a0", " ")
    line = line.replace("网联清算有限公司", "")
    line = re.sub(r"[ \t]+", " ", line)
    return line.strip()


def _is_noise_line(line: str) -> bool:
    if re.fullmatch(r"[-—–_·•\s]+", line):
        return True
    if re.fullmatch(r"\d{1,4}", line):
        return True
    if re.fullmatch(r"第\s*\d{1,4}\s*页(?:\s*/\s*共\s*\d{1,4}\s*页)?", line):
        return True
    if re.fullmatch(r"Page\s+\d{1,4}(?:\s+of\s+\d{1,4})?", line, re.I):
        return True
    if "目 录" in line or "目录" in line and "." * 3 in line:
        return True
    if line.count(".") >= 20:
        return True
    if re.search(r"[\x00-\x08\x0b-\x1f\x7f]", line):
        return True
    return False


def _heading_markdown(line: str) -> str:
    if line.startswith("#"):
        return line

    match = re.match(r"^(\d+(?:\.\d+){1,4})[、.．\s]*(.{2,100})$", line)
    if match:
        title = match.group(2).strip()
        if not re.match(r"^[\u4e00-\u9fffA-Za-z]", title):
            return ""
        depth = 2 + min(match.group(1).count("."), 2)
        return f"{'#' * depth} {line}"

    match = re.match(r"^(第[一二三四五六七八九十百千万]+[章节条])[、.．\s]*(.{2,100})$", line)
    if match:
        return f"## {line}"

    if re.match(r"^附\s*录\s*[A-ZＡ-Ｚ]\s*.{2,100}$", line):
        return f"## {line}"

    return ""


def _separate_embedded_headings(text: str) -> str:
    preface = text.find("前 言本指引")
    if preface > 0:
        text = text[preface:]

    def split_numeric(match: re.Match) -> str:
        start = match.start()
        prev = text[max(0, start - 8):start]
        if prev.endswith(("参见", "详见", "参考")) or re.search(r"[Vv]$", prev):
            return match.group(1)
        if not prev.endswith(("指引", "说明", "文件", "策略", "评价", "内容", "范围")):
            return match.group(1)
        return f"\n\n{match.group(1)}"

    text = re.sub(
        r"(?<![\d.])(\d+\.\d+(?:\.\d+){0,3})(?=[\u4e00-\u9fffA-Za-z])",
        split_numeric,
        text,
    )
    text = re.sub(
        r"(?<!\n)(附\s*录\s*[A-ZＡ-Ｚ])(?=[\u4e00-\u9fffA-Za-z])",
        r"\n\n\1",
        text,
    )
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _should_keep_as_own_line(line: str) -> bool:
    return bool(
        re.match(r"^([（(]?[一二三四五六七八九十]+[）)]?|[A-Za-z]|\d+)[、.．)]\s+", line)
        or re.search(r"\s{2,}", line)
        or "\t" in line
    )


def _join_text(current: str, line: str) -> str:
    if not current:
        return line
    if current.endswith(("。", "；", "：", ":", "？", "！", ".", ";", "?", "!")):
        return f"{current}\n{line}"
    if re.search(r"[A-Za-z0-9]$", current) and re.match(r"^[A-Za-z0-9]", line):
        return f"{current} {line}"
    return f"{current}{line}"


def _parse_docx(path: Path) -> str:
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, WordFormatOption

    converter = DocumentConverter(
        allowed_formats=[InputFormat.DOCX],
        format_options={InputFormat.DOCX: WordFormatOption()},
    )
    result = converter.convert(str(path))
    return result.document.export_to_markdown()


def _parse_legacy_doc(path: Path) -> str:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError(
            "Legacy .doc parsing needs LibreOffice headless conversion. "
            "Install LibreOffice and expose soffice in PATH, or convert the file to .docx first."
        )

    with tempfile.TemporaryDirectory(prefix="kb_ingest_doc_") as tmp:
        tmp_dir = Path(tmp)
        subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to",
                "docx",
                "--outdir",
                str(tmp_dir),
                str(path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        converted = tmp_dir / f"{path.stem}.docx"
        if not converted.exists():
            candidates = list(tmp_dir.glob("*.docx"))
            if not candidates:
                raise RuntimeError(f"LibreOffice did not produce docx for {path}")
            converted = candidates[0]
        return _parse_docx(converted)


def _markdown_to_blocks(source_doc: str, markdown: str) -> List[ParsedBlock]:
    normalized = _recover_headings(markdown)
    pieces = re.split(r"\n(?=#{1,4}\s+)", normalized)
    blocks: List[ParsedBlock] = []
    for idx, piece in enumerate(p.strip() for p in pieces if p.strip()):
        title = _first_heading(piece) or f"文档片段 {idx + 1}"
        pages = [int(n) for n in re.findall(r"第\s*(\d+)\s*页", title)]
        blocks.append(ParsedBlock(
            source_doc=source_doc,
            source_section=title,
            content=piece,
            pages=pages,
            order=idx,
        ))
    if not blocks and normalized.strip():
        blocks.append(ParsedBlock(source_doc=source_doc, source_section="全文", content=normalized.strip()))
    return blocks


def _document_category_profile(path: Path, markdown: str, blocks: List[ParsedBlock]) -> tuple[str, str, List[str]]:
    category = _document_category(path, markdown, blocks)
    headings = _document_headings(markdown, blocks)
    keywords = _category_keywords(category, headings)
    description = _category_description(category, headings)
    return category, description, keywords


def _document_category(path: Path, markdown: str, blocks: List[ParsedBlock]) -> str:
    for line in markdown.splitlines()[:80]:
        match = re.match(r"^#\s+(.+)$", line.strip())
        if match:
            return _clean_category(match.group(1))

    if blocks:
        first_section = blocks[0].source_section
        if first_section and not first_section.startswith("文档片段"):
            return _clean_category(first_section)

    return _clean_category(path.stem)


def _document_headings(markdown: str, blocks: List[ParsedBlock]) -> List[str]:
    headings: List[str] = []
    for line in markdown.splitlines():
        match = re.match(r"^#{1,4}\s+(.+)$", line.strip())
        if match and _is_useful_category_heading(match.group(1)):
            headings.append(_clean_category(match.group(1)))
    if not headings:
        headings = [
            _clean_category(block.source_section)
            for block in blocks[:12]
            if _is_useful_category_heading(block.source_section)
        ]
    return _unique_nonempty(headings)[:12]


def _category_description(category: str, headings: List[str]) -> str:
    useful = [h for h in headings if h and h != category][:8]
    if useful:
        return f"本分类来源于《{category}》，主要覆盖：{'；'.join(useful)}。"
    return f"本分类来源于《{category}》，用于承载该源文件所属业务场景、规则、指标、处置要求和相关知识条目。"


def _category_keywords(category: str, headings: List[str]) -> List[str]:
    seeds = [category] + headings
    keywords: List[str] = []
    for seed in seeds:
        for part in re.split(r"[\s,，、;；/／|｜（）()《》【】\\-]+", seed):
            part = _clean_category(part)
            if len(part) >= 2:
                keywords.append(part)
        if seed:
            keywords.append(seed)
    return _unique_nonempty(keywords)[:16]


def _is_useful_category_heading(value: str) -> bool:
    cleaned = _clean_category(value)
    if not cleaned:
        return False
    if re.fullmatch(r"(?:\d+|[A-ZＡ-Ｚ])(?:\.\d+)*", cleaned):
        return False
    if cleaned in {"目录", "前言", "范围", "术语和定义", "规范性引用文件", "未分类"}:
        return False
    if cleaned.startswith(("Q/", "ICS", "CCS")):
        return False
    if "\\" in cleaned or "fonttbl" in cleaned or "ansi" in cleaned:
        return False
    return True


def _unique_nonempty(values: List[str]) -> List[str]:
    seen = set()
    output = []
    for value in values:
        cleaned = _clean_category(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output


def _clean_category(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" #\t\r\n")
    value = re.sub(r"^(文档片段|全文)\s*\d*", "", value).strip()
    return value[:80] or "未分类"


def _recover_headings(markdown: str) -> str:
    lines = []
    heading_pattern = re.compile(r"^(\d+(?:\.\d+){1,4}|第[一二三四五六七八九十百]+[章节条]|附\s*录\s*[A-ZＡ-Ｚ])[\s、.．]*(.{2,80})$")
    for raw in markdown.splitlines():
        line = raw.strip()
        match = heading_pattern.match(line)
        if match and not line.startswith("#"):
            title = match.group(2).strip()
            if not re.match(r"^[\u4e00-\u9fffA-Za-z]", title):
                lines.append(raw)
                continue
            depth = 2 + min(match.group(1).count("."), 2)
            lines.append(f"{'#' * depth} {line}")
        else:
            lines.append(raw)
    return "\n".join(lines)


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        match = re.match(r"^#{1,4}\s+(.+)$", line.strip())
        if match:
            return match.group(1).strip()
    return ""
