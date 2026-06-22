from __future__ import annotations

import unittest
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

import normalizer
from normalizer import (
    _build_prompt,
    _coverage_retry_prompt,
    _extract_response_content,
    _extract_json_with_diagnostics,
    _item_from_dict,
    _items_with_coverage_warning,
    _json_repair_retry_prompt,
    _normalize_with_llm,
    normalize_block,
    _postprocess_item,
    _read_tools,
    _significant_token_overlap,
    _source_fact_coverage_issues,
)
from schemas import KnowledgeItem, ParsedBlock
from writer import write_item


class LlmResponseCompatibilityTest(unittest.TestCase):
    def test_reads_tools_yaml_top_level_tools(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "tools.yaml"
            path.write_text(
                """
tools:
  - name: unit_uops_api_status
    display_name: 互联互通API接口情况查询
    input_schema:
      type: object
""".strip(),
                encoding="utf-8",
            )
            _read_tools.cache_clear()
            try:
                with patch.object(normalizer, "TOOLS_PATH", path):
                    self.assertEqual(_read_tools()[0]["name"], "unit_uops_api_status")
            finally:
                _read_tools.cache_clear()

    def test_extracts_segmented_message_content(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": '{"items": ['},
                            {"type": "text", "text": '{"title": "规则"}]}'},
                        ]
                    }
                }
            ]
        }

        self.assertEqual(_extract_response_content(response), '{"items": [\n{"title": "规则"}]}')

    def test_extracts_object_message_content(self):
        class ContentPart:
            text = '{"items": [{"title": "对象响应"}]}'

        class Message:
            content = [ContentPart()]

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        self.assertEqual(_extract_response_content(Response()), '{"items": [{"title": "对象响应"}]}')

    def test_extracts_tool_call_arguments_when_content_is_empty(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "arguments": '{"items": [{"title": "工具调用"}]}'
                                }
                            }
                        ],
                    }
                }
            ]
        }

        self.assertEqual(_extract_response_content(response), '{"items": [{"title": "工具调用"}]}')



class NormalizerPostprocessTest(unittest.TestCase):

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

    def test_llm_retry_carries_bad_response_into_next_round(self):
        config = SimpleNamespace(
            base_url="http://llm",
            api_key="key",
            model="glm",
            max_tokens=1000,
            temperature=0.1,
        )
        block = ParsedBlock(
            source_doc="doc.md",
            source_section="章节",
            content="异常交易需要人工复核。",
        )
        calls = []

        def fake_completion(_client, _config, messages):
            calls.append([dict(message) for message in messages])
            if len(calls) == 1:
                return {"choices": [{"message": {"content": '{"answer":"bad"}'}, "finish_reason": "stop"}]}
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"items":[{"title":"异常交易","body":"# 异常交易\\n\\n## 1. 核心内容\\n异常交易需要人工复核。"}]}'
                        },
                        "finish_reason": "stop",
                    }
                ]
            }

        with patch("normalizer.get_llm_config", return_value=config), \
            patch("normalizer._get_zhipu_client_class", return_value=lambda **_: object()), \
            patch("normalizer._create_zhipu_completion", side_effect=fake_completion), \
            patch("normalizer._source_fact_coverage_issues", return_value=[]), \
            patch("normalizer.time.sleep"):
            items = _normalize_with_llm(block, "draft")

        self.assertEqual(items[0].title, "异常交易")
        self.assertEqual(calls[1][2]["role"], "assistant")
        self.assertEqual(calls[1][2]["content"], '{"answer":"bad"}')
        self.assertIn("根节点必须严格为", calls[1][3]["content"])

    def test_llm_bad_shape_exhaustion_falls_back_without_abort(self):
        config = SimpleNamespace(
            base_url="http://llm",
            api_key="key",
            model="glm",
            max_tokens=1000,
            temperature=0.1,
        )
        block = ParsedBlock(
            source_doc="doc.md",
            source_section="章节",
            content="异常交易需要人工复核。",
        )

        with patch("normalizer.LLM_MAX_RETRIES", 1), \
            patch("normalizer.get_llm_config", return_value=config), \
            patch("normalizer._get_zhipu_client_class", return_value=lambda **_: object()), \
            patch(
                "normalizer._create_zhipu_completion",
                return_value={"choices": [{"message": {"content": '{"answer":"bad"}'}, "finish_reason": "stop"}]},
            ), \
            patch("normalizer.time.sleep"):
            self.assertEqual(_normalize_with_llm(block, "draft"), [])

    def test_llm_fallback_marks_failed_and_keeps_chunk_source(self):
        config = SimpleNamespace(enabled=True)
        block = ParsedBlock(
            source_doc="doc.md",
            source_section="章节",
            content="原始 chunk 内容",
        )

        with patch("normalizer.get_llm_config", return_value=config), \
            patch("normalizer._normalize_with_llm", return_value=[]):
            item = normalize_block(block, "active")[0]

        self.assertEqual(item.review_status, "failed")
        self.assertIn("WARNING: LLM 多次重试后仍未返回合格 JSON", item.body)
        self.assertIn("## failed_chunk_source", item.body)
        self.assertIn("原始 chunk 内容", item.body)

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
                "（以下简称“示例平台”），英文简称“EPCC”。"
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
                "（以下简称“示例平台”），英文简称“EPCC”。"
            ),
        )
        item = KnowledgeItem(
            kb_id="biz-test-v1",
            title="网络支付清算平台定义",
            doc_type="biz",
            domain="示例运维",
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
            "连接商业银行与非银行支付机构的非银行支付机构网络支付清算平台（以下简称“示例平台”），英文简称“EPCC”。"
        ])

    def test_source_fact_coverage_accepts_full_definition(self):
        block = ParsedBlock(
            source_doc="互联互通机制规范.md",
            source_section="3.1 网络支付清算平台 electronics payment clearing of China",
            content=(
                "#### 3.1 网络支付清算平台 electronics payment clearing of China\n\n"
                "连接商业银行与非银行支付机构的非银行支付机构网络支付清算平台"
                "（以下简称“示例平台”），英文简称“EPCC”。"
            ),
        )
        item = KnowledgeItem(
            kb_id="biz-test-v1",
            title="网络支付清算平台定义",
            doc_type="biz",
            domain="示例运维",
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

连接商业银行与非银行支付机构的非银行支付机构网络支付清算平台（以下简称“示例平台”），英文简称“EPCC”。

## 2. 适用边界

原文未明确说明。

## 3. 使用要求

原文未明确说明。
""",
        )

        self.assertEqual(_source_fact_coverage_issues(block, [item]), [])

    def test_coverage_retry_prompt_includes_source_context_and_previous_body(self):
        block = ParsedBlock(
            source_doc="制度.md",
            source_section="4.1 运行监控",
            content="当前片段要求监控异常交易笔数超过 30000 笔时升级处理。",
            context="上一节说明监控对象为大型单位。",
        )
        item = KnowledgeItem(
            kb_id="biz-test-v1",
            title="异常交易监控",
            doc_type="biz",
            domain="示例运维",
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
            tags=[],
            status="active",
            body="""# 异常交易监控

## 1. 核心内容

监控异常交易。

## 2. 适用边界

原文未明确说明。

## 3. 使用要求

原文未明确说明。
""",
        )

        prompt = _coverage_retry_prompt(block, ["异常交易笔数超过 30000 笔时升级处理。"], [item])

        self.assertIn("来源文档：制度.md", prompt)
        self.assertIn("来源章节：4.1 运行监控", prompt)
        self.assertIn("当前来源原文片段", prompt)
        self.assertIn("当前片段要求监控异常交易笔数超过 30000 笔时升级处理。", prompt)
        self.assertIn("上一节说明监控对象为大型单位。", prompt)
        self.assertIn("上一轮生成的核心正文", prompt)
        self.assertIn("监控异常交易。", prompt)

    def test_coverage_warning_releases_draft_with_manual_review_marker(self):
        block = ParsedBlock(
            source_doc="制度.md",
            source_section="4.1 运行监控",
            content="当前片段要求监控异常交易笔数超过 30000 笔时升级处理。",
        )
        item = KnowledgeItem(
            kb_id="biz-test-v1",
            title="异常交易监控",
            doc_type="biz",
            domain="示例运维",
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
            tags=[],
            status="active",
            body="""# 异常交易监控

## 1. 核心内容

监控异常交易。

## 2. 适用边界

原文未明确说明。

## 3. 使用要求

原文未明确说明。
""",
        )

        released = _items_with_coverage_warning(item_list := [item], block, ["异常交易笔数超过 30000 笔时升级处理。"])

        self.assertIs(released, item_list)
        self.assertEqual(item.status, "draft")
        self.assertEqual(item.review_status, "coverage_warning")
        self.assertIn("需人工复核", item.tags)
        self.assertIn("WARNING: LLM 多次重试后仍未通过来源事实覆盖校验", item.body)
        self.assertIn("异常交易笔数超过 30000 笔时升级处理。", item.body)



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

    def test_writes_matched_tool_from_tools_yaml_as_yaml_fence(self):
        block = ParsedBlock(
            source_doc="变更通知.md",
            source_section="成员机构变更报备查询",
            content="用户可查询某家机构近期变更、变更报备、计划变更、执行评价以及影响范围。",
            category="成员机构变更管理",
            category_description="覆盖成员机构变更通知查询。",
            category_keywords=["成员机构", "变更通知"],
        )
        item = _item_from_dict(
            {
                "title": "成员机构变更通知查询",
                "body": """# 成员机构变更通知查询

## 1. 核心内容

适用于查询成员机构近期变更、变更报备和执行评价。

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

        self.assertIn("```yaml\nfunction_name: \"query_member_change_announcements\"", processed.body)
        self.assertIn('display_name: "查询成员机构变更通知"', processed.body)
        self.assertIn("required_permissions: []", processed.body)
        self.assertIn('orgCode: "成员机构金融编码，通常由 resolve_member_org 工具获得。"', processed.body)
        self.assertIn("```", processed.body)

    def test_does_not_match_tool_from_broad_category_words_only(self):
        block = ParsedBlock(
            source_doc="互联互通.md",
            source_section="监控统计账户类型",
            content="本文说明监控统计账户类型字段 mAccTpCd 的含义，不涉及查询API接入情况、接入时间或某一场景是否接入。",
            category="网络支付清算平台 示例运维互联互通技术规范",
            category_description="覆盖互联互通技术规范。",
            category_keywords=["网络支付清算平台", "示例运维", "互联互通"],
        )
        item = _item_from_dict(
            {
                "title": "监控统计账户类型",
                "body": """# 监控统计账户类型

知识大类说明：
大类：网络支付清算平台 示例运维互联互通技术规范
说明：覆盖互联互通技术规范。
关键词：网络支付清算平台、示例运维、互联互通

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

    def test_write_item_prefixes_filename_with_source_title_timestamp_and_trace_id(self):
        item = KnowledgeItem(
            kb_id="biz-offline-abc-v1",
            title="标题",
            doc_type="biz",
            domain="示例运维",
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
            path = write_item(
                item,
                Path(tmp),
                source_title="制度",
                timestamp="20260610153045",
                trace_id="a1b2c3d4",
            )

        self.assertEqual(
            path.name,
            "制度-20260610153045-a1b2c3d4-000012-biz-offline-abc-v1.md",
        )

    def test_write_failed_item_marks_filename(self):
        item = KnowledgeItem(
            kb_id="biz-offline-abc-v1",
            title="标题",
            doc_type="biz",
            domain="示例运维",
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
            body="# 标题",
            source_order=12,
            review_status="failed",
        )

        with TemporaryDirectory() as tmp:
            path = write_item(
                item,
                Path(tmp),
                source_title="制度",
                timestamp="20260610153045",
                trace_id="a1b2c3d4",
            )

        self.assertIn("-failed-", path.name)


if __name__ == "__main__":
    unittest.main()
