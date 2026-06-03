from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


DOC_TYPES = {
    "biz",
    "function",
}


@dataclass
class ParsedBlock:
    """表示从来源文档中切出的一个待整理片段。"""
    source_doc: str
    source_section: str
    content: str
    pages: List[int] = field(default_factory=list)
    order: int = 0
    context: str = ""
    category: str = ""
    category_description: str = ""
    category_keywords: List[str] = field(default_factory=list)
    source_doc_description: str = ""
    subcategory: str = ""
    subcategory_description: str = ""
    category_path: List[str] = field(default_factory=list)
    related_categories: List[str] = field(default_factory=list)
    relation_notes: List[str] = field(default_factory=list)
    related_items: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """表示单个来源文档解析后的 Markdown 和片段列表。"""
    source_path: Path
    source_doc: str
    markdown: str
    blocks: List[ParsedBlock]


@dataclass
class KnowledgeItem:
    """表示最终写入知识库 Markdown 的结构化条目。"""
    kb_id: str
    title: str
    doc_type: str
    domain: str
    category: str
    category_keywords: List[str]
    business_modules: List[str]
    source_doc: str
    source_version: str
    source_section: str
    effective_date: str
    owner: str
    confidentiality: str
    risk_level: str
    applicable_roles: List[str]
    tags: List[str]
    status: str
    body: str
    source_doc_description: str = ""
    subcategory: str = ""
    category_path: List[str] = field(default_factory=list)
    related_categories: List[str] = field(default_factory=list)
    relation_notes: List[str] = field(default_factory=list)
    related_items: List[Dict[str, str]] = field(default_factory=list)
    source_order: int = 0
    source_pages: List[int] = field(default_factory=list)
    review_status: str = "pending"
    source_trace: str = ""

    def metadata(self) -> Dict:
        """生成写入 Front Matter 的元数据字典。"""
        return {
            "kb_id": self.kb_id,
            "title": self.title,
            "doc_type": self.doc_type,
            "domain": self.domain,
            "category": self.category,
            "category_keywords": self.category_keywords,
            "subcategory": self.subcategory,
            "related_items": self.related_items,
            "business_modules": self.business_modules,
            "source_doc": self.source_doc,
            "source_version": self.source_version,
            "source_section": self.source_section,
            "source_order": self.source_order,
            "source_pages": self.source_pages,
            "source_trace": self.source_trace,
            "effective_date": self.effective_date,
            "owner": self.owner,
            "confidentiality": self.confidentiality,
            "risk_level": self.risk_level,
            "applicable_roles": self.applicable_roles,
            "tags": self.tags,
            "status": self.status,
            "review_status": self.review_status,
        }


@dataclass
class ValidationIssue:
    """表示生成结果校验过程中的单条问题。"""
    path: Path
    level: str
    message: str
