from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from validator import validate_file


class ValidatorQualityTest(unittest.TestCase):
    def test_warns_when_acronym_only_appears_outside_core_sections(self):
        text = """---
kb_id: biz-offline-test-v1
title: 网络支付清算平台定义
doc_type: biz
domain: 联合运维
category: 互联互通技术规范
category_description: 说明
category_keywords: []
business_modules: []
source_doc: 互联互通机制规范.md
source_version: V1.3
source_section: 3.1 网络支付清算平台 electronics payment clearing of China
owner: 联合运维知识库
confidentiality: 内部
risk_level: low
applicable_roles: []
tags:
- EPCC
status: active
---

# 网络支付清算平台定义

## 1. 核心内容

适用于网络支付清算平台定义。

## 2. 适用边界

原文未明确说明

## 3. 使用要求

原文未明确说明

## 4. 关联能力

暂无

## 5. 来源依据

- 关键词：EPCC
- 来源文档：互联互通机制规范.md
"""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "item.md"
            path.write_text(text, encoding="utf-8")

            issues = validate_file(path)

        messages = [issue.message for issue in issues]
        self.assertIn("关键缩写未进入正文核心章节: EPCC", messages)

    def test_warns_when_core_section_is_blank(self):
        text = """---
kb_id: biz-offline-test-v1
title: 网络支付清算平台定义
doc_type: biz
domain: 联合运维
category: 互联互通技术规范
category_description: 说明
category_keywords: []
business_modules: []
source_doc: 互联互通机制规范.md
source_version: V1.3
source_section: 3.1 网络支付清算平台
owner: 联合运维知识库
confidentiality: 内部
risk_level: low
applicable_roles: []
tags: []
status: active
---

# 网络支付清算平台定义

## 1. 核心内容

适用于网络支付清算平台定义。

## 2. 适用边界

## 3. 使用要求

原文未明确说明

## 4. 关联能力

暂无

## 5. 来源依据

- 来源文档：互联互通机制规范.md
"""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "item.md"
            path.write_text(text, encoding="utf-8")

            issues = validate_file(path)

        messages = [issue.message for issue in issues]
        self.assertIn("章节内容为空: ## 2", messages)


if __name__ == "__main__":
    unittest.main()
