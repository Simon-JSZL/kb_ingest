from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from normalizer import (
    _build_prompt,
    _extract_json_with_diagnostics,
    _item_from_dict,
    _json_repair_retry_prompt,
    _postprocess_item,
    _significant_token_overlap,
    _source_fact_coverage_issues,
)
from schemas import KnowledgeItem, ParsedBlock
from writer import write_item


class NormalizerPostprocessTest(unittest.TestCase):
    def test_extract_json_repairs_unescaped_quotes_in_category_description(self):
        content = '''{
  "items": [
    {
      "title": "异常交易规则",
      "doc_type": "biz",
      "category": "异常交易",
      "category_description": "本分类覆盖"异常交易"、'"大额交易"'、"风险处置"等内容。",
      "category_keywords": ["异常交易"],
      "business_modules": [],
      "source_version": "",
      "risk_level": "low",
      "applicable_roles": [],
      "tags": [],
      "body": "# 异常交易规则\\n\\n## 1. 核心内容\\n\\n正文。\\n\\n## 2. 适用边界\\n\\n原文未明确说明。\\n\\n## 3. 使用要求\\n\\n原文未明确说明。\\n\\n## 4. 关联能力\\n\\n暂无。\\n\\n## 5. 来源依据\\n\\n基于原文回答。",
      "split_reason": "独立规则"
    }
  ]
}'''

        parsed = _extract_json_with_diagnostics(content).value

        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed["items"][0]["title"], "异常交易规则")
        self.assertIn('"异常交易"', parsed["items"][0]["category_description"])

    def test_json_repair_retry_prompt_reports_parse_error(self):
        content = '{"items": [{"title": "异常", "body": "正文",}]}'
        result = _extract_json_with_diagnostics(content)

        prompt = _json_repair_retry_prompt(result.error, content)

        self.assertIsNone(result.value)
        self.assertIn("line", result.error)
        self.assertIn("column", result.error)
        self.assertIn("只能返回修复后的 JSON object", prompt)
        self.assertIn('根节点必须严格为 {"items": [...]}', prompt)
        self.assertIn("所有字符串内部的英文双引号必须写成", prompt)

    def test_item_uses_clean_model_category_description(self):
        block = ParsedBlock(
            source_doc="制度.md",
            source_section="1. 异常处置",
            content="# 1. 异常处置\n\n正文。",
            category="异常处置规范",
            category_description="本分类对应来源文档《异常处置规范》，用于归集与异常处置相关的定义、规则、流程、指标和处置要求。",
            category_keywords=["异常处置"],
        )

        item = _item_from_dict(
            {
                "title": "异常处置要求",
                "category_description": "覆盖\"异常交易\"、'处置流程'、\"风险复核\"等内容。",
                "body": "# 异常处置要求\n\n## 1. 核心内容\n\n正文。",
            },
            block,
            1,
            "active",
        )

        self.assertEqual(item.category, "异常处置规范")
        self.assertEqual(item.subcategory, "异常处置规范")

    def test_item_falls_back_when_model_category_description_is_generic(self):
        block = ParsedBlock(
            source_doc="制度.md",
            source_section="1. 异常处置",
            content="# 1. 异常处置\n\n正文。",
            category="异常处置规范",
            category_description="本分类对应来源文档《异常处置规范》，用于归集与异常处置相关的定义、规则、流程、指标和处置要求。",
            category_keywords=["异常处置"],
        )

        item = _item_from_dict(
            {
                "title": "异常处置要求",
                "category_description": "说明",
                "body": "# 异常处置要求\n\n## 1. 核心内容\n\n正文。",
            },
            block,
            1,
            "active",
        )

        self.assertEqual(item.category, "异常处置规范")
        self.assertEqual(item.subcategory, "异常处置规范")

    def test_prompt_requires_definition_facts_in_core_body(self):
        block = ParsedBlock(
            source_doc="互联互通机制规范.md",
            source_section="3.1 网络支付清算平台 electronics payment clearing of China",
            content=(
                "#### 3.1 网络支付清算平台 electronics payment clearing of China\n\n"
                "连接商业银行与非银行支付机构的非银行支付机构网络支付清算平台"
                "（以下简称“网联平台”），英文简称“EPCC”。"
            ),
        )

        prompt = _build_prompt(block, "active")

        self.assertIn("定义句", prompt)
        self.assertIn("以下简称", prompt)
        self.assertIn("英文简称", prompt)
        self.assertIn("## 1 到 ## 3", prompt)
        self.assertIn("## 1. 核心内容", prompt)
        self.assertIn("全量覆盖", prompt)
        self.assertIn("EPCC", prompt)

    def test_source_fact_coverage_flags_compressed_definition(self):
        block = ParsedBlock(
            source_doc="互联互通机制规范.md",
            source_section="3.1 网络支付清算平台 electronics payment clearing of China",
            content=(
                "#### 3.1 网络支付清算平台 electronics payment clearing of China\n\n"
                "连接商业银行与非银行支付机构的非银行支付机构网络支付清算平台"
                "（以下简称“网联平台”），英文简称“EPCC”。"
            ),
        )
        item = KnowledgeItem(
            kb_id="biz-test-v1",
            title="网络支付清算平台定义",
            doc_type="biz",
            domain="联合运维",
            category="分类",
            category_keywords=[],
            business_modules=[],
            source_doc=block.source_doc,
            source_version="",
            source_section=block.source_section,
            effective_date="",
            owner="",
            confidentiality="内部",
            risk_level="low",
            applicable_roles=[],
            tags=["EPCC"],
            status="active",
            body="""# 网络支付清算平台定义

## 1. 核心内容

网络支付清算平台（electronics payment clearing of China），英文简称“EPCC”。

## 2. 适用边界

原文未明确说明。

## 3. 使用要求

原文未明确说明。

## 4. 关联能力

暂无。

## 5. 来源依据

- 来源文档：互联互通机制规范.md
""",
        )

        issues = _source_fact_coverage_issues(block, [item])

        self.assertEqual(issues, [
            "连接商业银行与非银行支付机构的非银行支付机构网络支付清算平台（以下简称“网联平台”），英文简称“EPCC”。"
        ])

    def test_source_fact_coverage_accepts_full_definition(self):
        block = ParsedBlock(
            source_doc="互联互通机制规范.md",
            source_section="3.1 网络支付清算平台 electronics payment clearing of China",
            content=(
                "#### 3.1 网络支付清算平台 electronics payment clearing of China\n\n"
                "连接商业银行与非银行支付机构的非银行支付机构网络支付清算平台"
                "（以下简称“网联平台”），英文简称“EPCC”。"
            ),
        )
        item = KnowledgeItem(
            kb_id="biz-test-v1",
            title="网络支付清算平台定义",
            doc_type="biz",
            domain="联合运维",
            category="分类",
            category_keywords=[],
            business_modules=[],
            source_doc=block.source_doc,
            source_version="",
            source_section=block.source_section,
            effective_date="",
            owner="",
            confidentiality="内部",
            risk_level="low",
            applicable_roles=[],
            tags=["EPCC"],
            status="active",
            body="""# 网络支付清算平台定义

## 1. 核心内容

连接商业银行与非银行支付机构的非银行支付机构网络支付清算平台（以下简称“网联平台”），英文简称“EPCC”。

## 2. 适用边界

原文未明确说明。

## 3. 使用要求

原文未明确说明。
""",
        )

        self.assertEqual(_source_fact_coverage_issues(block, [item]), [])

    def test_rewrites_hallucinated_function_when_source_is_unrelated(self):
        block = ParsedBlock(
            source_doc="规则.md",
            source_section="异常处置",
            content="# 异常处置\n\n原文只描述人工登记、复核和上报要求。",
            category="异常处置规范",
            category_description="覆盖人工处置流程。",
            category_keywords=["异常处置", "人工复核"],
        )
        item = _item_from_dict(
            {
                "title": "异常处置要求",
                "doc_type": "function",
                "body": """# 异常处置要求

## 1. 核心内容

适用于人工处置。

## 4. 关联能力

yaml
function_name: "unit_uops_api_status"
display_name: "互联互通API接口情况查询"

## 5. 来源依据

基于原文回答。
""",
            },
            block,
            1,
            "active",
        )

        processed = _postprocess_item(item, block)

        self.assertEqual(processed.doc_type, "biz")
        self.assertIn("## 4. 关联能力\n\n暂无。", processed.body)
        self.assertNotIn("unit_uops_api_status", processed.body)
        self.assertIn("知识分类：", processed.body)
        self.assertIn("大类标题：异常处置规范", processed.body)

    def test_writes_matched_function_as_yaml_fence(self):
        block = ParsedBlock(
            source_doc="互联互通.md",
            source_section="API接口查询",
            content="用户可查询自身接入联合运维互联互通API的具体情况，以及某一场景是否接入。",
            category="互联互通技术规范",
            category_description="覆盖API接入状态查询。",
            category_keywords=["互联互通", "API接入"],
        )
        item = _item_from_dict(
            {
                "title": "互联互通API接入查询",
                "body": """# 互联互通API接入查询

## 1. 核心内容

适用于查询互联互通API接入状态。

## 4. 关联能力

暂无。

## 5. 来源依据

基于原文回答。
""",
            },
            block,
            1,
            "active",
        )

        processed = _postprocess_item(item, block)

        self.assertIn("```yaml\nfunction_name: \"unit_uops_api_status\"", processed.body)
        self.assertIn('display_name: "互联互通API接口情况查询"', processed.body)
        self.assertIn("required_permissions: []", processed.body)
        self.assertIn('org_code: "成员单位金融编码，例如C10010010010"', processed.body)
        self.assertIn("```", processed.body)

    def test_does_not_match_tool_from_broad_category_words_only(self):
        block = ParsedBlock(
            source_doc="互联互通.md",
            source_section="监控统计账户类型",
            content="本文说明监控统计账户类型字段 mAccTpCd 的含义，不涉及查询API接入情况、接入时间或某一场景是否接入。",
            category="网络支付清算平台 联合运维互联互通技术规范",
            category_description="覆盖互联互通技术规范。",
            category_keywords=["网络支付清算平台", "联合运维", "互联互通"],
        )
        item = _item_from_dict(
            {
                "title": "监控统计账户类型",
                "body": """# 监控统计账户类型

知识大类说明：
大类：网络支付清算平台 联合运维互联互通技术规范
说明：覆盖互联互通技术规范。
关键词：网络支付清算平台、联合运维、互联互通

## 1. 核心内容

适用于理解 mAccTpCd 字段含义。

## 2. 适用边界

原文说明监控统计账户类型字段。

## 4. 关联能力

暂无。

## 5. 来源依据

基于原文字段说明回答。
""",
            },
            block,
            1,
            "active",
        )

        processed = _postprocess_item(item, block)

        self.assertIn("## 4. 关联能力\n\n暂无。", processed.body)
        self.assertNotIn("```yaml", processed.body)
        self.assertNotIn("unit_uops_api_status", processed.body)

    def test_significant_tool_overlap_filters_only_structural_noise(self):
        source_tokens = {"查询", "接口", "共享主题", "operation_001"}
        tool_tokens = {"查询", "接口", "共享主题", "operation_001"}

        overlap = _significant_token_overlap(source_tokens, tool_tokens)

        self.assertEqual(overlap, {"共享主题", "operation_001"})

    def test_rewrites_source_section_and_keeps_pages_out_of_body(self):
        block = ParsedBlock(
            source_doc="制度.md",
            source_section="4.1 运行监控",
            content="# 4.1 运行监控\n\n正文。",
            pages=[3, 4],
            order=7,
        )
        item = _item_from_dict(
            {
                "title": "运行监控",
                "body": """# 运行监控

## 1. 核心内容

第 3 页
适用于监控场景。

## 4. 关联能力

暂无。

## 5. 来源依据

来源页码：3
模型自写来源。
""",
            },
            block,
            1,
            "active",
        )

        processed = _postprocess_item(item, block)
        before_source, source = processed.body.split("## 5. 来源依据", 1)

        self.assertNotIn("第 3 页", before_source)
        self.assertNotIn("来源页码", before_source)
        self.assertIn("- 来源文档：制度.md", source)
        self.assertIn("- 来源章节：4.1 运行监控", source)
        self.assertIn("- 来源页码：3、4", source)
        self.assertEqual(processed.source_pages, [3, 4])
        self.assertEqual(processed.source_order, 7)

    def test_write_item_prefixes_filename_with_source_order(self):
        item = KnowledgeItem(
            kb_id="biz-offline-abc-v1",
            title="标题",
            doc_type="biz",
            domain="联合运维",
            category="分类",
            category_keywords=[],
            business_modules=[],
            source_doc="制度.md",
            source_version="",
            source_section="1",
            effective_date="",
            owner="",
            confidentiality="内部",
            risk_level="low",
            applicable_roles=[],
            tags=[],
            status="active",
            body="# 标题\n\n## 5. 来源依据\n\n- 来源文档：制度.md",
            source_order=12,
            source_pages=[5],
            source_trace="section=1; pages=5",
        )

        with TemporaryDirectory() as tmp:
            path = write_item(item, Path(tmp))

        self.assertEqual(path.name, "000012-biz-offline-abc-v1.md")


if __name__ == "__main__":
    unittest.main()
