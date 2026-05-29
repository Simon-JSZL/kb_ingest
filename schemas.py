from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


DOC_TYPES = {
    "biz",
    "scenario",
    "sop",
    "metric",
    "severity",
    "change",
    "function",
    "evaluation",
}


@dataclass
class ParsedBlock:
    source_doc: str
    source_section: str
    content: str
    pages: List[int] = field(default_factory=list)
    order: int = 0
    context: str = ""
    category: str = ""
    category_description: str = ""
    category_keywords: List[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    source_path: Path
    source_doc: str
    markdown: str
    blocks: List[ParsedBlock]


@dataclass
class KnowledgeItem:
    kb_id: str
    title: str
    doc_type: str
    domain: str
    category: str
    category_description: str
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
    review_status: str = "pending"
    source_trace: str = ""

    def metadata(self) -> Dict:
        return {
            "kb_id": self.kb_id,
            "title": self.title,
            "doc_type": self.doc_type,
            "domain": self.domain,
            "category": self.category,
            "category_description": self.category_description,
            "category_keywords": self.category_keywords,
            "business_modules": self.business_modules,
            "source_doc": self.source_doc,
            "source_version": self.source_version,
            "source_section": self.source_section,
            "effective_date": self.effective_date,
            "owner": self.owner,
            "confidentiality": self.confidentiality,
            "risk_level": self.risk_level,
            "applicable_roles": self.applicable_roles,
            "tags": self.tags,
            "status": self.status,
        }


@dataclass
class ValidationIssue:
    path: Path
    level: str
    message: str
