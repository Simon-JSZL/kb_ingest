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
    """列出支持解析的输入文件。"""
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in SUPPORTED_EXTENSIONS else []
    files = [
        p for p in input_path.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files, key=lambda path: (path.name.lower(), str(path).lower()))


def parse_document(path: Path) -> ParsedDocument:
    """解析来源文档并补充分类画像。"""
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
    category = _document_category(path, markdown, blocks)
    headings = _document_headings(markdown, blocks)
    category_description = _category_description(category, headings)
    category_keywords = _category_keywords(category, headings)
    source_doc_description = _source_doc_description(category, markdown, blocks)
    sibling_subcategories = _document_subcategory_index(blocks, category)
    blocks = [
        _with_category_profile(
            source_doc=block.source_doc,
            source_section=block.source_section,
            content=block.content,
            pages=block.pages,
            order=block.order,
            context=block.context,
            document_category=category,
            document_category_description=category_description,
            document_category_keywords=category_keywords,
            source_doc_description=source_doc_description,
            sibling_subcategories=sibling_subcategories,
        )
        for block in blocks
    ]
    return ParsedDocument(
        source_path=path,
        source_doc=path.name,
        markdown=markdown,
        blocks=blocks,
    )


def _with_category_profile(
    source_doc: str,
    source_section: str,
    content: str,
    pages: List[int],
    order: int,
    context: str,
    document_category: str,
    document_category_description: str,
    document_category_keywords: List[str],
    source_doc_description: str,
    sibling_subcategories: dict[str, List[str]],
) -> ParsedBlock:
    """为片段补充大类、小类和关联信息。"""
    subcategory = _block_subcategory(source_section, content)
    category = _clean_category(document_category) or "未分类"
    related_records = _related_subcategories(
        sibling_subcategories.get(category, []),
        source_section,
        subcategory,
        _keyword_profile(category, subcategory, content, document_category_keywords),
    )
    related = [item["小类标题"] for item in related_records]
    related_items = [{"大类标题": category, **item} for item in related_records]
    return ParsedBlock(
        source_doc=source_doc,
        source_section=source_section,
        content=content,
        pages=pages,
        order=order,
        context=context,
        category=category,
        category_description=_major_category_description(category, document_category_description),
        category_keywords=_keyword_profile(category, subcategory, content, document_category_keywords)[:10],
        source_doc_description=source_doc_description,
        subcategory=subcategory,
        subcategory_description=_subcategory_description(subcategory, category),
        category_path=[category, subcategory] if subcategory and subcategory != category else [category],
        related_categories=related,
        relation_notes=_relation_notes(category, subcategory, related),
        related_items=related_items,
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
    """把 PDF 行文本整理为段落和标题。"""
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
    """清理单行 PDF 文本的结构噪声。"""
    line = line.replace("\u00a0", " ")
    line = re.sub(r"[ \t]+", " ", line)
    return line.strip()


def _is_noise_line(line: str) -> bool:
    """判断行文本是否为页码或目录等噪声。"""
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
    """把识别出的章节行转换为 Markdown 标题。"""
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
    """拆出粘连在段落中的章节标题。"""
    preface = text.find("前 言本指引")
    if preface > 0:
        text = text[preface:]

    def split_numeric(match: re.Match) -> str:
        """处理嵌入式数字标题的拆分边界。"""
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
    """判断行文本是否应独立成段。"""
    return bool(
        re.match(r"^([（(]?[一二三四五六七八九十]+[）)]?|[A-Za-z]|\d+)[、.．)]\s+", line)
        or re.search(r"\s{2,}", line)
        or "\t" in line
    )


def _join_text(current: str, line: str) -> str:
    """按中英文边界拼接连续文本行。"""
    if not current:
        return line
    if current.endswith(("。", "；", "：", ":", "？", "！", ".", ";", "?", "!")):
        return f"{current}\n{line}"
    if re.search(r"[A-Za-z0-9]$", current) and re.match(r"^[A-Za-z0-9]", line):
        return f"{current} {line}"
    return f"{current}{line}"


def _parse_docx(path: Path) -> str:
    """把 DOCX 转换为 Markdown。"""
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, WordFormatOption

    converter = DocumentConverter(
        allowed_formats=[InputFormat.DOCX],
        format_options={InputFormat.DOCX: WordFormatOption()},
    )
    result = converter.convert(str(path))
    return result.document.export_to_markdown()


def _parse_legacy_doc(path: Path) -> str:
    """通过本地办公套件把 DOC 转换后解析。"""
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
    """把 Markdown 按标题切成解析片段。"""
    normalized = _recover_headings(_strip_standalone_page_markers(markdown))
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


def _strip_standalone_page_markers(markdown: str) -> str:
    """移除独立页码和页眉页脚噪声。"""
    kept = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if _is_noise_line(line):
            continue
        kept.append(raw)
    return "\n".join(kept)


def _source_doc_description(category: str, markdown: str, blocks: List[ParsedBlock]) -> str:
    """生成来源文档的整体说明。"""
    headings = _document_headings(markdown, blocks)
    useful = [heading for heading in headings if heading != category][:6]
    if useful:
        return f"本文件围绕《{category}》展开，主要覆盖{'、'.join(useful)}等主题。"
    return f"本文件围绕《{category}》展开，用于沉淀来源文档中的主要知识条目。"


def _document_subcategory_index(blocks: List[ParsedBlock], document_category: str) -> dict[str, List[tuple[str, str, List[str]]]]:
    """构建同一大类下的小类索引。"""
    output: dict[str, List[tuple[str, str, List[str]]]] = {}
    for block in blocks:
        subcategory = _block_subcategory(block.source_section, block.content)
        category = _clean_category(document_category) or "未分类"
        if not subcategory:
            continue
        output.setdefault(category, [])
        pair = (
            block.source_section,
            subcategory,
            _keyword_profile(category, subcategory, block.content, []),
        )
        if pair not in output[category]:
            output[category].append(pair)
    return output


def _related_subcategories(
    siblings: List[tuple[str, str, List[str]]],
    source_section: str,
    subcategory: str,
    current_keywords: List[str],
) -> List[dict[str, str]]:
    """根据结构距离和语义重叠推荐相关小类。"""
    if not siblings or not subcategory:
        return []

    current_key = _section_family_key(source_section)
    current_index = next(
        (
            idx
            for idx, (section, name, _) in enumerate(siblings)
            if name == subcategory and section == source_section
        ),
        -1,
    )
    if current_index < 0:
        current_index = next((idx for idx, (_, name, _) in enumerate(siblings) if name == subcategory), -1)

    current_set = set(current_keywords)
    candidates: List[tuple[float, int, str, List[str], int]] = []
    for idx, (section, name, keywords) in enumerate(siblings):
        if name == subcategory or not _is_useful_category_heading(name):
            continue
        distance = abs(idx - current_index) if current_index >= 0 else idx
        same_family = bool(current_key and _section_family_key(section) == current_key)
        overlap = sorted(current_set.intersection(keywords), key=len, reverse=True)
        title_overlap = sorted(set(_semantic_tokens(subcategory)).intersection(_semantic_tokens(name)), key=len, reverse=True)
        score = len(overlap) * 3.0 + len(title_overlap) * 2.0 + (2.0 if same_family else 0.0) - min(distance, 8) * 0.25
        candidates.append((score, distance, name, _unique_nonempty([*overlap, *title_overlap])[:3], 1 if same_family else 0))

    items: List[dict[str, str]] = []
    seen = set()
    for score, distance, name, reasons, same_family in sorted(candidates, reverse=True):
        if name in seen:
            continue
        seen.add(name)
        if score >= 5:
            relevance = "高"
        elif score >= 2 or distance <= 2:
            relevance = "一般"
        else:
            relevance = "低"
        items.append({
            "小类标题": name,
            "关联说明": _relation_info(name, reasons, distance, bool(same_family)),
            "关联度": relevance,
        })
        if len(items) >= 5:
            break
    return items


def _section_family_key(source_section: str) -> str:
    """提取章节的同组关系键。"""
    section = source_section.strip()
    match = re.match(r"^([A-ZＡ-Ｚ])\.\d+(?:\.\d+)*", section, flags=re.I)
    if match:
        return match.group(1).upper()

    match = re.match(r"^(\d+(?:\.\d+)*)", section)
    if not match:
        return ""
    parts = match.group(1).split(".")
    if len(parts) == 1:
        return parts[0]
    return ".".join(parts[:-1])


def _block_subcategory(source_section: str, content: str) -> str:
    """从章节标题或内容推断小类标题。"""
    title = _clean_heading_title(source_section)
    if not title or title.startswith("文档片段"):
        title = _first_heading(content) or title
    return _clean_category(title)[:80] or "未分类"


def _clean_heading_title(value: str) -> str:
    """清理章节编号并保留标题文本。"""
    value = _clean_category(value)
    value = re.sub(r"^\d+(?:\.\d+)*\s*[、.．]?\s*", "", value).strip()
    value = re.sub(r"^第[一二三四五六七八九十百]+[章节条]\s*[、.．]?\s*", "", value).strip()
    return value


def _major_category_description(category: str, fallback_description: str) -> str:
    """生成或复用大类说明。"""
    if category and fallback_description and category not in fallback_description:
        return f"本大类来源于文档结构中的“{category}”，用于承载该主题下的相关知识条目。"
    return fallback_description


def _subcategory_description(subcategory: str, category: str) -> str:
    """生成小类说明文本。"""
    if not subcategory or subcategory == category:
        return f"用于说明“{category}”主题下的具体内容、边界和使用提示。"
    return f"用于说明“{subcategory}”在“{category}”大类下的具体内容、边界和关联提示。"



def _relation_notes(category: str, subcategory: str, related: List[str]) -> List[str]:
    """生成旧版关联说明以兼容历史字段。"""
    if not related or not subcategory:
        return []
    return [
        f"“{subcategory}”与“{name}”同属“{category}”大类，回答时应结合来源章节区分适用场景、交互对象和处理要求。"
        for name in related[:3]
    ]


def _relation_info(name: str, reasons: List[str], distance: int, same_family: bool) -> str:
    """生成结构化关联说明。"""
    parts: List[str] = []
    if reasons:
        parts.append(f"与当前小类共享核心语义：{'、'.join(reasons[:3])}")
    if same_family:
        parts.append("来源结构处于同一章节组")
    if distance <= 2:
        parts.append("章节位置接近")
    if not parts:
        parts.append("与当前小类存在可参考的相近主题")
    return "；".join(parts) + "。"


def _keyword_profile(category: str, subcategory: str, content: str, document_keywords: List[str]) -> List[str]:
    """基于标题和正文生成关键词候选。"""
    values: List[str] = []
    title_tokens = _semantic_tokens(subcategory)
    values.extend(title_tokens)
    values.extend(title_tokens)
    values.extend(title_tokens)
    values.extend(_semantic_tokens(_core_content_text(content)))
    values.extend(_semantic_tokens(" ".join(document_keywords[:3])))
    return _rank_keywords(values, category)[:10]


def _core_content_text(content: str) -> str:
    """提取正文中适合抽关键词的核心文本。"""
    text = re.sub(r"^#{1,6}\s+.*$", "", content, flags=re.M)
    text = re.sub(r"\|.*?\|", " ", text)
    return text[:1600]


def _semantic_tokens(text: str) -> List[str]:
    """从文本中提取可检索语义 token。"""
    tokens: List[str] = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}|[\u4e00-\u9fff][\u4e00-\u9fffA-Za-z0-9]{1,18}", text):
        cleaned = _clean_keyword(token)
        if cleaned:
            tokens.append(cleaned)
    return tokens


def _rank_keywords(values: List[str], category: str) -> List[str]:
    """按频次、位置和大类占比排序关键词。"""
    counts: dict[str, int] = {}
    first_pos: dict[str, int] = {}
    category_tokens = set(_semantic_tokens(category))
    for idx, raw in enumerate(values):
        token = _clean_keyword(raw)
        if not token:
            continue
        counts[token] = counts.get(token, 0) + 1
        first_pos.setdefault(token, idx)

    output: List[str] = []
    category_count = 0
    for token, _ in sorted(counts.items(), key=lambda item: (-item[1], first_pos[item[0]], -len(item[0]))):
        if token in category_tokens:
            if category_count >= 3:
                continue
            category_count += 1
        output.append(token)
        if len(output) >= 10:
            break
    return output


def _clean_keyword(value: str) -> str:
    """清洗关键词并过滤结构性噪声。"""
    text = _clean_category(value)
    text = re.sub(r"^[A-Z]\.\d+(?:\.\d+)?", "", text).strip(" -_：:")
    if not text or len(text) < 2:
        return ""
    if text in _keyword_stopwords():
        return ""
    if re.fullmatch(r"\d+(?:\.\d+)*", text):
        return ""
    if re.search(r"Q\s*/\s*NUC|NUC|V\d+(?:\.\d+)*", text, re.I):
        return ""
    return text[:32]


def _keyword_stopwords() -> set[str]:
    """返回跨场景的结构性关键词停用词。"""
    return {
        "知识条目", "来源文档",
        "核心内容", "适用边界", "使用要求", "关联能力", "来源依据", "暂无",
        "原文未明确说明", "本分类", "当前小类", "小类标题",
    }


def _document_category(path: Path, markdown: str, blocks: List[ParsedBlock]) -> str:
    """从标题或文件名推断文档大类。"""
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
    """提取可用于分类的文档标题。"""
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
    """生成文档分类说明。"""
    useful = [h for h in headings if h and h != category][:8]
    if useful:
        return f"本分类对应来源文档《{category}》，用于归集与{'、'.join(useful[:4])}相关的知识条目。"
    return f"本分类对应来源文档《{category}》，用于归集该文档中的知识条目。"


def _category_keywords(category: str, headings: List[str]) -> List[str]:
    """从文档标题集合生成大类关键词。"""
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
    """过滤目录和编号类标题噪声。"""
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
    """去重并保留非空清洗结果。"""
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
    """清洗分类或标题文本。"""
    value = re.sub(r"\s+", " ", value).strip(" #\t\r\n")
    value = re.sub(r"^(文档片段|全文)\s*\d*", "", value).strip()
    return value[:80] or "未分类"


def _recover_headings(markdown: str) -> str:
    """从纯文本行中恢复 Markdown 标题。"""
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
    """返回文本中的第一个 Markdown 标题。"""
    for line in text.splitlines():
        match = re.match(r"^#{1,4}\s+(.+)$", line.strip())
        if match:
            return match.group(1).strip()
    return ""
