from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml

from app_config import get_llm_config
from schemas import DOC_TYPES, KnowledgeItem, ParsedBlock


DEFAULT_DOMAIN = "通用业务"
DEFAULT_OWNER = "通用知识库"
CURRENT_DIR = Path(__file__).resolve().parent
KB_SPEC_PATH = CURRENT_DIR / "prompts" / "知识库建立规范.md"
TOOLS_PATH = CURRENT_DIR / "input" / "function" / "tools.yaml"
LLM_MAX_RETRIES = 10
COVERAGE_MAX_RETRIES = 3


@dataclass(frozen=True)
class JsonParseResult:
    """保存 JSON 解析结果和诊断错误信息。"""
    value: Any = None
    error: str = ""


def normalize_block(block: ParsedBlock, status: str = "draft") -> List[KnowledgeItem]:
    """把解析片段转换为一个或多个知识条目。"""
    if get_llm_config().enabled:
        items = _normalize_with_llm(block, status=status)
        if items:
            return [_postprocess_item(item, block) for item in items]
        print("WARNING: model returned no valid knowledge items; using heuristic fallback")
        return fallback_failed_block(block, status=status)
    return [_postprocess_item(_normalize_heuristically(block, status=status), block)]


def fallback_failed_block(block: ParsedBlock, status: str = "draft") -> List[KnowledgeItem]:
    """用离线规则生成 failed 兜底条目。"""
    item = _normalize_heuristically(block, status=status)
    return [_mark_llm_failed_item(_postprocess_item(item, block), block)]


def _normalize_with_llm(block: ParsedBlock, status: str) -> List[KnowledgeItem]:
    """调用 LLM 生成条目并处理重试。"""
    config = get_llm_config()
    if not (config.base_url and config.api_key and config.model):
        print("WARNING: missing base_url, api_key, or model; using heuristic fallback")
        return []

    base_prompt = _build_prompt(block, status)
    started_at = time.monotonic()
    print(
        "llm start: "
        f"doc={block.source_doc} section={block.source_section} "
        f"chars={len(block.content)} model={config.model}"
    )
    try:
        client_cls = _get_zhipu_client_class()
    except ImportError as exc:
        print(f"llm error: cannot load Z.AI SDK ({exc})")
        return []
    client = client_cls(api_key=config.api_key, base_url=config.base_url)

    coverage_retry_count = 0
    messages = _messages(base_prompt)
    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            print(
                "llm request: "
                f"provider=zhipu base_url={config.base_url} attempt={attempt}/{LLM_MAX_RETRIES}"
            )
            response = _create_zhipu_completion(client, config, messages)
        except Exception as exc:
            elapsed = time.monotonic() - started_at
            print(
                "llm error: "
                f"{type(exc).__name__} attempt={attempt}/{LLM_MAX_RETRIES} "
                f"after {elapsed:.1f}s detail={exc}"
            )
            if attempt >= LLM_MAX_RETRIES:
                print(f"WARNING: request failed after {LLM_MAX_RETRIES} attempts: {type(exc).__name__}; using heuristic fallback")
                return []
            time.sleep(min(2 ** (attempt - 1), 30))
            continue

        content = _extract_response_content(response)
        elapsed = time.monotonic() - started_at
        finish_reason = _finish_reason(response)
        print(
            "llm response: "
            f"{len(content)} chars in {elapsed:.1f}s attempt={attempt}/{LLM_MAX_RETRIES} "
            f"finish_reason={finish_reason or 'unknown'}"
        )
        if content:
            print(f"llm response content:\n{_preview(content)}")
        if not content.strip():
            reasoning = _extract_reasoning_content(response)
            print(
                "llm parse failed: empty response content "
                f"finish_reason={finish_reason} reasoning_chars={len(reasoning)} "
                f"response={_response_debug(response)}"
            )
            if attempt >= LLM_MAX_RETRIES:
                print(f"WARNING: empty response content after {LLM_MAX_RETRIES} attempts; using heuristic fallback")
                return []
            _append_retry_messages(
                messages,
                content,
                "重试补充要求：上一轮响应为空。请只返回一个 JSON object，根节点必须严格为 {\"items\": [...]}。",
            )
            time.sleep(min(2 ** (attempt - 1), 30))
            continue

        parse_result = _extract_json_with_diagnostics(content)
        parsed = parse_result.value
        if not parsed:
            retry_prompt = _json_repair_retry_prompt(parse_result.error, content)
            if _looks_truncated(content, finish_reason):
                retry_prompt += "\n上一轮响应疑似被截断，本轮请压缩表述但保持 {\"items\": [...]} 根结构。"
            print(
                "llm parse failed: response is not valid JSON "
                f"finish_reason={finish_reason or 'unknown'} "
                f"truncated={_looks_truncated(content, finish_reason)} "
                f"error={parse_result.error or 'unknown'} "
                f"preview={_preview(content)}"
            )
            if attempt >= LLM_MAX_RETRIES:
                print(f"WARNING: response is not valid JSON after {LLM_MAX_RETRIES} attempts; using heuristic fallback")
                return []
            _append_retry_messages(messages, content, retry_prompt)
            time.sleep(min(2 ** (attempt - 1), 30))
            continue

        raw_items = _coerce_raw_items(parsed)
        if not isinstance(raw_items, list):
            retry_prompt = _json_shape_retry_prompt(parsed)
            if _looks_truncated(content, finish_reason):
                retry_prompt += "\n上一轮响应疑似被截断，本轮请压缩表述但保持 {\"items\": [...]} 根结构。"
            print(
                "llm parse failed: JSON does not contain an items list "
                f"finish_reason={finish_reason or 'unknown'} "
                f"truncated={_looks_truncated(content, finish_reason)} "
                f"top_level={_json_shape(parsed)} preview={_preview(content)}"
            )
            if attempt >= LLM_MAX_RETRIES:
                print(f"WARNING: JSON does not contain an items list after {LLM_MAX_RETRIES} attempts; using heuristic fallback")
                return []
            _append_retry_messages(messages, content, retry_prompt)
            time.sleep(min(2 ** (attempt - 1), 30))
            continue

        items: List[KnowledgeItem] = []
        for idx, raw in enumerate(raw_items, start=1):
            if not isinstance(raw, dict):
                continue
            items.append(_item_from_dict(raw, block, idx, status))
        print(f"llm done: generated_items={len(items)} attempt={attempt}/{LLM_MAX_RETRIES}")
        if items:
            coverage_issues = _source_fact_coverage_issues(block, items)
            if coverage_issues:
                print(
                    "llm coverage failed: "
                    f"missing_facts={len(coverage_issues)} "
                    f"preview={_preview('；'.join(coverage_issues[:3]))}"
                )
                if coverage_retry_count >= COVERAGE_MAX_RETRIES or attempt >= LLM_MAX_RETRIES:
                    print(
                        "WARNING: source fact coverage failed after "
                        f"{coverage_retry_count} coverage retries; releasing draft for manual review"
                    )
                    return _items_with_coverage_warning(items, block, coverage_issues)
                coverage_retry_count += 1
                _append_retry_messages(
                    messages,
                    content,
                    _coverage_retry_prompt(block, coverage_issues, items),
                )
                time.sleep(min(2 ** (attempt - 1), 30))
                continue
            return items
        if attempt >= LLM_MAX_RETRIES:
            print(f"WARNING: items list contained no valid objects after {LLM_MAX_RETRIES} attempts; using heuristic fallback")
            return []
        _append_retry_messages(
            messages,
            content,
            "重试补充要求：上一轮 items 数组没有可用对象。请返回 {\"items\": [...]}，items 中每个元素都必须是知识库条目对象。",
        )
        time.sleep(min(2 ** (attempt - 1), 30))

    return []


def _system_message() -> str:
    """构造 LLM 系统提示。"""
    return (
        "你是严谨的运维知识库整理助手，只能依据输入原文生成结构化知识条目。"
        "你必须只返回一个 JSON object，根节点必须只有 items 字段，"
        "且 items 必须是数组。不要返回 Markdown、解释文字或其他根字段。"
    )


def _messages(prompt: str) -> List[Dict[str, str]]:
    """组装发送给 LLM 的消息列表。"""
    return [
        {"role": "system", "content": _system_message()},
        {"role": "user", "content": prompt},
    ]














def _coverage_retry_prompt(
    block: ParsedBlock,
    missing_facts: List[str],
    items: List[KnowledgeItem],
) -> str:
    """构造事实覆盖不足时的重试提示。"""
    lines = "\n".join(f"- {fact}" for fact in missing_facts[:8])
    source_excerpt = _preview(block.content)[:4000] or "无"
    context_excerpt = _preview(block.context)[:2000] or "无"
    current_core = _preview(
        "\n\n".join(_core_sections_for_coverage(item.body) for item in items)
    )[:3000] or "无"
    return (
        "重试补充要求：上一次输出遗漏了以下来源正文事实。"
        "请重新生成 JSON，并把这些事实写入 ## 1. 核心内容、## 2. 适用边界 或 ## 3. 使用要求。"
        "短定义句、简称句、阈值句和规则句应优先保留原句或等价完整表述，不要只概括关键词。\n"
        f"{lines}\n\n"
        f"来源文档：{block.source_doc}\n"
        f"来源章节：{block.source_section or '全文'}\n\n"
        "当前来源原文片段如下，请结合上下文判断缺失事实应补入哪个正文小节：\n"
        f"{source_excerpt}\n\n"
        "辅助上下文如下。辅助上下文只用于理解位置和术语，不要把其中独有事实写入正文：\n"
        f"{context_excerpt}\n\n"
        "上一轮生成的核心正文如下，请在此基础上补齐遗漏事实并保持 JSON 根结构不变：\n"
        f"{current_core}"
    )


def _json_repair_retry_prompt(error: str, previous_content: str) -> str:
    """构造 JSON 解析失败时的修复提示。"""
    return (
        "重试补充要求：上一次响应不是合法 JSON，应用层解析失败。"
        "本次只能返回修复后的 JSON object，不能返回 Markdown 代码围栏、解释文字或前后缀。"
        "不要改写业务内容，只修复 JSON 语法、转义和根结构。"
        "所有字符串内部的英文双引号必须写成 \\\"，换行必须写成 \\n。"
        "根节点必须严格为 {\"items\": [...]}。\n"
        f"解析错误：{error or 'unknown'}\n"
        f"上一轮输出片段：\n{_preview(previous_content)[:3000]}"
    )


def _json_shape_retry_prompt(parsed) -> str:
    """构造 JSON 根结构错误时的重试提示。"""
    return (
        "重试补充要求：上一次响应虽然是 JSON，但结构不符合要求。"
        "本次只能返回一个 JSON object，根节点必须严格为 {\"items\": [...]}。"
        "不要返回纯数组、单个 item、data/result/records/knowledge_items 等其他根字段；"
        "不要返回解释文字或 Markdown 代码围栏。"
        f"上一次 JSON 结构：{_json_shape(parsed)}"
    )


def _append_retry_messages(messages: List[Dict[str, str]], previous_content: str, feedback: str) -> None:
    """把坏返回和纠偏要求放进下一轮会话。"""
    messages.append({"role": "assistant", "content": previous_content or ""})
    messages.append({"role": "user", "content": feedback})


def _create_zhipu_completion(client, config, messages: List[Dict[str, str]]):
    """发起一次非流式模型补全请求。"""
    return client.chat.completions.create(
        model=config.model,
        messages=messages,
        stream=False,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        do_sample=False,
        response_format={"type": "json_object"},
        thinking={"type": "disabled", "clear_thinking": False},
    )


def _get_zhipu_client_class():
    """加载 Z.AI SDK 客户端类。"""
    try:
        from zai import ZhipuAiClient

        return ZhipuAiClient
    except (ImportError, AttributeError) as exc:
        raise ImportError(
            "missing Z.AI Python SDK. Install it with: python -m pip install zai-sdk==0.2.2"
        ) from exc


def _extract_response_content(response) -> str:
    """从模型响应中提取正文内容。"""
    message = _first_message(response)
    if message is None:
        return ""

    if isinstance(message, dict):
        content = _stringify_message_content(message.get("content"))
        if content:
            return content
        content = _extract_tool_call_content(message.get("function_call"))
        if content:
            return content
        content = _extract_tool_call_content(message.get("tool_calls"))
        if content:
            return content
        return _stringify_message_content(message.get("reasoning_content"))

    content = _stringify_message_content(getattr(message, "content", ""))
    if content:
        return content
    content = _extract_tool_call_content(getattr(message, "function_call", None))
    if content:
        return content
    content = _extract_tool_call_content(getattr(message, "tool_calls", None))
    if content:
        return content
    return _stringify_message_content(getattr(message, "reasoning_content", ""))


def _stringify_message_content(content) -> str:
    """兼容不同 SDK 返回的纯文本、分段文本和结构化 content。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [_stringify_message_content(part) for part in content]
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        for key in ("text", "content", "output_text", "json", "arguments"):
            value = content.get(key)
            text = _stringify_message_content(value)
            if text:
                return text
        try:
            return json.dumps(content, ensure_ascii=False)
        except TypeError:
            return str(content)

    for attr in ("text", "content", "output_text"):
        value = getattr(content, attr, None)
        text = _stringify_message_content(value)
        if text:
            return text
    return str(content)


def _extract_tool_call_content(tool_calls) -> str:
    """从工具/函数调用参数里兜底提取 JSON 文本。"""
    if not tool_calls:
        return ""
    calls = tool_calls if isinstance(tool_calls, list) else [tool_calls]
    for call in calls:
        function = call.get("function") if isinstance(call, dict) else getattr(call, "function", None)
        if function is None:
            function = call
        arguments = function.get("arguments") if isinstance(function, dict) else getattr(function, "arguments", None)
        text = _stringify_message_content(arguments)
        if text:
            return text
    return ""


def _extract_reasoning_content(response) -> str:
    """从模型响应中提取推理内容。"""
    message = _first_message(response)
    if isinstance(message, dict):
        return str(message.get("reasoning_content") or "")
    return str(getattr(message, "reasoning_content", "") or "")


def _finish_reason(response) -> str:
    """读取模型响应的结束原因。"""
    choice = _first_choice(response)
    if isinstance(choice, dict):
        return str(choice.get("finish_reason") or "")
    return str(getattr(choice, "finish_reason", "") or "")


def _first_message(response):
    """读取响应中的第一条消息。"""
    choice = _first_choice(response)
    if isinstance(choice, dict):
        return choice.get("message")
    return getattr(choice, "message", None)


def _first_choice(response):
    """读取响应中的第一条候选。"""
    if isinstance(response, dict):
        choices = response.get("choices") or []
    else:
        choices = getattr(response, "choices", None) or []
    return choices[0] if choices else None


def _response_debug(response) -> str:
    """生成响应对象的调试预览。"""
    return _preview(repr(response))


def _json_shape(value) -> str:
    """描述 JSON 顶层结构。"""
    if isinstance(value, dict):
        return f"object keys={list(value.keys())[:10]}"
    if isinstance(value, list):
        return f"array len={len(value)}"
    return type(value).__name__


def _mark_llm_failed_item(item: KnowledgeItem, block: ParsedBlock) -> KnowledgeItem:
    """标记 LLM 失败后的离线兜底条目。"""
    item.review_status = "failed"
    item.body = _append_failed_chunk_source(item.body, block.content)
    return item


def _append_failed_chunk_source(body: str, source: str) -> str:
    """在 failed 文件末尾保存原始 chunk。"""
    warning = (
        "## LLM 生成失败警告\n\n"
        "WARNING: LLM 多次重试后仍未返回合格 JSON，本文件由离线规则兜底生成，需人工核对。\n\n"
        "## failed_chunk_source\n\n"
        "```text\n"
        f"{source.strip()}\n"
        "```"
    )
    return f"{body.strip()}\n\n{warning}".strip()


def _coerce_raw_items(parsed):
    """只接受标准 {"items": [...]} 输出。"""
    if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
        return parsed["items"]
    return None






def _looks_truncated(content: str, finish_reason: str) -> bool:
    """判断响应是否疑似被截断。"""
    if finish_reason == "length":
        return True
    stripped = content.strip()
    if not stripped:
        return False
    return stripped.count("{") > stripped.count("}") or stripped.count("[") > stripped.count("]")


def _build_prompt(block: ParsedBlock, status: str) -> str:
    """构造片段生成知识条目的完整提示。"""
    spec = _read_kb_spec()
    return f"""
请将以下原始文档片段整理为标准知识库条目。

要求：
1. 严格参照《知识库建立规范》的元数据字段、正文 5 节结构、内容切分原则和质量校验要求生成。
2. 只依据原文理解知识点、对象、模块、角色、标签和风险等级，不要依据示例或常见关键词进行套写。
3. 如果一个片段包含多个独立定义、规则、流程、指标、接口或判定标准，请拆成多个 items。
4. 每个 item 必须可独立检索、独立回答，颗粒度控制在 800 到 1500 中文字符左右；复杂表格可适当放宽。
5. 不要编造来源、阈值、角色、日期、版本；原文没有的信息留空、空数组或使用规范允许的通用值。
6. 涉及表格、阈值、比较符、单位、持续时间、笔数、适用对象时必须保留原始逻辑。
7. 输出严格 JSON 对象，不要 Markdown 代码围栏，不要解释文字，不要在 JSON 前后添加任何内容。
8. status 固定为 "{status}"。
9. JSON 根节点必须严格为一个对象：{{"items": [...]}}。禁止返回单个 item 对象、禁止返回纯数组、禁止返回 result/data/records/knowledge_items 等其他根字段。
10. 为避免输出被截断，优先生成 1 个覆盖本片段核心内容的综合 item；只有原文明确包含多个相互独立主题时，才拆分为多个 items。
11. “辅助上下文”只用于理解当前片段在全文中的位置、术语和前后关系；不要把辅助上下文中独有而当前原文没有的事实写成正文依据。
12. body 必须对齐目标知识库样式：YAML Front Matter 由程序生成，body 只输出 Markdown 正文；正文必须包含 # 标题，以及 ## 1. 核心内容、## 2. 适用边界、## 3. 使用要求、## 4. 关联能力、## 5. 来源依据。
13. 如果某类条目不适用某一节，也必须保留该节标题，并写“暂无”或“原文未明确说明”，不要删除章节；但不要为了填满栏目编造业务事实。
14. 正文必须以原文为主，不要根据工具、示例或规范样例生成原文不存在的业务事实、接口事实或处置规则。
15. 除格式、页码、页眉页脚和目录噪声外，原文正文信息必须全量覆盖到知识条目正文中。可以调整结构和表达顺序，但不能省略原文中的限定语、主体对象、适用边界、简称、阈值、比较符、单位、时间、数量、例外条件和禁止要求。
16. 对术语、定义、缩写、简称、英文名称类片段，必须把原文中的定义句、被定义对象、全称、英文名、中文简称和英文简称写入 ## 1. 核心内容，不能只写在 title、tags、business_modules 或 ## 5. 来源依据 中。例如原文出现“以下简称”“英文简称”“称为”“是指”“定义为”时，正文核心章节必须保留完整定义句；短定义句优先直接引用原句。
17. 输出 JSON 前必须逐句自检：原文正文中的每个事实句，是否已经进入 body 的 ## 1 到 ## 3；若只出现在元数据或来源依据中，或被概括到丢失主体/边界/限定语，视为不合格，必须改写 body。
18. “关联能力”章节由程序根据原文和工具维护文件自动补写。你在 body 的 ## 4. 关联能力 下只写“暂无”，不要抄写、改写或扩展工具列表。
19. 不要在 ## 1 到 ## 4 的正文中写入页码、页眉、页脚或“来源页码”；来源页码由程序写入 ## 5. 来源依据。
20. category_keywords 必须围绕当前小类和正文核心内容抽取，按重要程度排序，不超过 10 个；大类级关键词不超过 3 个；不要输出全局背景词、文档编号、版本号或无人会检索的代号。
21. category 表示大类，subcategory 表示当前词条在大类下的具体小类或场景；related_items 表示当前词条与其他小类的结构化关联信息。
22. related_items 必须是对象数组，每个对象只包含“大类标题”“小类标题”“关联说明”“关联度”。关联说明必须结合位置、小类标题和关键词语义解释为什么相关，不要只写“同属大类”或“位置相邻”；关联度只能取“极高”“高”“一般”“低”。

doc_type 只能取：
{", ".join(sorted(DOC_TYPES))}

唯一允许的 JSON 输出格式：
{{
  "items": [
    {{
      "title": "",
      "doc_type": "biz",
      "category": "",
      "subcategory": "",
      "related_items": [],
      "category_keywords": [],
      "business_modules": [],
      "source_version": "",
      "risk_level": "low|medium|high|critical",
      "applicable_roles": [],
      "tags": [],
      "body": "Markdown 正文，必须严格包含 # 标题，以及 ## 1. 核心内容、## 2. 适用边界、## 3. 使用要求、## 4. 关联能力、## 5. 来源依据",
      "split_reason": "为什么这是独立条目"
    }}
  ]
}}

《知识库建立规范》：
{spec}

来源文档：{block.source_doc}
知识大类：{block.category or "未分类"}
文件总体说明：{block.source_doc_description or "无"}
知识小类：{block.subcategory or "无"}
同级相关小类：{", ".join(block.related_categories) if block.related_categories else "无"}
关联信息提示：{_related_items_prompt(block.related_items) if block.related_items else "无"}
大类关键词：{", ".join(block.category_keywords) if block.category_keywords else "无"}
来源章节：{block.source_section}

辅助上下文：
{block.context or "无"}

原文：
{block.content}
""".strip()


@lru_cache(maxsize=1)
def _read_kb_spec() -> str:
    """读取知识库建立规范。"""
    try:
        return KB_SPEC_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


@lru_cache(maxsize=1)
def _read_tools() -> List[Dict[str, Any]]:
    """读取本地工具维护文件。"""
    try:
        raw = yaml.safe_load(TOOLS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError):
        return []
    if isinstance(raw, dict):
        raw = raw.get("tools")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _extract_json_with_diagnostics(text: str) -> JsonParseResult:
    """提取 JSON 并保留失败诊断。"""
    text = _strip_code_fence(text.strip())
    errors: List[str] = []
    try:
        return JsonParseResult(value=json.loads(text))
    except json.JSONDecodeError as exc:
        errors.append(_json_error_message(exc, text))

    for candidate in _json_candidates(text):
        try:
            return JsonParseResult(value=json.loads(candidate))
        except json.JSONDecodeError as exc:
            errors.append(_json_error_message(exc, candidate))
    return JsonParseResult(error=errors[-1] if errors else "no JSON object or array found")




def _json_error_message(exc: json.JSONDecodeError, text: str) -> str:
    """格式化 JSON 解析错误位置。"""
    line = text.splitlines()[exc.lineno - 1] if 0 < exc.lineno <= len(text.splitlines()) else ""
    start = max(exc.colno - 41, 0)
    end = min(exc.colno + 40, len(line))
    pointer = " " * max(exc.colno - start - 1, 0) + "^"
    snippet = line[start:end]
    return (
        f"{exc.msg} at line {exc.lineno}, column {exc.colno}, char {exc.pos}. "
        f"near: {snippet}\n{pointer}"
    )


def _strip_code_fence(text: str) -> str:
    """移除包裹 JSON 的代码围栏。"""
    text = text.strip()
    fence = re.match(r"^```(?:json|JSON)?\s*(.*?)\s*```$", text, re.S)
    return fence.group(1).strip() if fence else text


def _json_candidates(text: str) -> List[str]:
    """从混合文本中枚举 JSON 候选片段。"""
    candidates: List[str] = []
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        while start != -1:
            end = text.rfind(closer)
            while end > start:
                candidates.append(text[start:end + 1])
                end = text.rfind(closer, 0, end)
            start = text.find(opener, start + 1)
    return candidates
















def _preview(text: str) -> str:
    """生成日志预览文本。"""
    return text.strip()


def _normalize_heuristically(block: ParsedBlock, status: str) -> KnowledgeItem:
    """在未启用 LLM 时生成保守条目。"""
    title = _guess_title(block)
    doc_type = "biz"
    body = _build_body(title, block.content)
    return KnowledgeItem(
        kb_id=_kb_id(doc_type, title, _kb_source_seed(block), 1),
        title=title,
        doc_type=doc_type,
        domain=DEFAULT_DOMAIN,
        category=block.category or _guess_category(block),
        category_keywords=block.category_keywords or [block.category or _guess_category(block)],
        business_modules=[],
        source_doc=block.source_doc,
        source_version=_guess_version(block.source_doc + " " + block.content),
        source_section=block.source_section,
        effective_date="",
        owner=DEFAULT_OWNER,
        confidentiality="内部",
        risk_level="low",
        applicable_roles=[],
        tags=[],
        status=status,
        source_order=block.order,
        source_pages=sorted(set(block.pages)),
        review_status="pending",
        source_trace=_source_trace(block),
        body=body,
        source_doc_description=block.source_doc_description,
        subcategory=block.subcategory or block.category or _guess_category(block),
        category_path=block.category_path or [block.category or _guess_category(block)],
        related_categories=block.related_categories,
        relation_notes=block.relation_notes,
        related_items=block.related_items,
    )


def _items_with_coverage_warning(
    items: List[KnowledgeItem],
    block: ParsedBlock,
    missing_facts: List[str],
) -> List[KnowledgeItem]:
    """把覆盖不足的 LLM 结果降级为需人工复核的草稿。"""
    for item in items:
        item.status = "draft"
        item.review_status = "coverage_warning"
        if "需人工复核" not in item.tags:
            item.tags.append("需人工复核")
        item.body = _body_with_coverage_warning(item.body, block, missing_facts)
    return items


def _body_with_coverage_warning(
    body: str,
    block: ParsedBlock,
    missing_facts: List[str],
) -> str:
    """在正文核心章节标注覆盖不足的来源事实。"""
    fact_lines = "\n".join(f"> - {fact}" for fact in missing_facts[:20])
    note = (
        "\n\n"
        "> WARNING: LLM 多次重试后仍未通过来源事实覆盖校验，本条目已降为草稿，需人工复核。\n"
        f"> 来源文档：{block.source_doc}\n"
        f"> 来源章节：{block.source_section or '全文'}\n"
        "> 待人工补齐或确认的来源事实：\n"
        f"{fact_lines}"
    )
    pattern = r"(^##\s+1\.\s+核心内容\s*$)"
    if re.search(pattern, body, flags=re.M):
        return re.sub(pattern, r"\1" + note, body, count=1, flags=re.M)
    return f"{body.rstrip()}\n\n## 人工复核提示{note}"


def _source_fact_coverage_issues(block: ParsedBlock, items: List[KnowledgeItem]) -> List[str]:
    """检查来源事实是否进入核心正文。"""
    facts = _source_fact_sentences(block.content)
    if not facts:
        return []

    covered_text = "\n".join(_core_sections_for_coverage(item.body) for item in items)
    covered_norm = _coverage_text(covered_text)
    missing = []
    for fact in facts:
        fact_norm = _coverage_text(fact)
        if not fact_norm or fact_norm in covered_norm:
            continue
        missing.append(fact)
    return missing


def _source_fact_sentences(text: str) -> List[str]:
    """从来源文本中抽取事实句。"""
    facts: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or _is_table_noise_line(line):
            continue
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^\d+[、.．)]\s*", "", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        for sentence in _split_fact_sentences(line):
            sentence = sentence.strip()
            if len(_coverage_text(sentence)) >= 12:
                facts.append(sentence)
    return _unique_fact_sentences(facts)


def _split_fact_sentences(line: str) -> List[str]:
    """按中文和英文标点切分事实句。"""
    parts = re.split(r"(?<=[。；;！？!?])\s*", line)
    return [part for part in parts if part.strip()] or [line]


def _is_table_noise_line(line: str) -> bool:
    """判断 Markdown 表格分隔行是否为噪声。"""
    if re.fullmatch(r"\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?", line):
        return True
    return False


def _unique_fact_sentences(values: List[str]) -> List[str]:
    """按覆盖文本去重事实句。"""
    seen = set()
    output = []
    for value in values:
        key = _coverage_text(value)
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def _core_sections_for_coverage(body: str) -> str:
    """提取用于事实覆盖检查的正文范围。"""
    body = _strip_category_summary(body)
    match = re.search(r"^##\s+4\.\s+关联能力\s*$", body, flags=re.M)
    if match:
        return body[:match.start()]
    match = re.search(r"^##\s+5\.\s+来源依据\s*$", body, flags=re.M)
    if match:
        return body[:match.start()]
    return body


def _coverage_text(text: str) -> str:
    """归一化文本以便事实覆盖比对。"""
    text = re.sub(r"^#{1,6}\s+.*$", "", text, flags=re.M)
    text = re.sub(r"[\s`*_#|>：:，,。；;！？!?、（）()【】\[\]《》“”\"'‘’.\-—–]+", "", text)
    return text.lower()


def _postprocess_item(item: KnowledgeItem, block: ParsedBlock) -> KnowledgeItem:
    """补写分类摘要、工具能力和来源依据。"""
    item.body = _with_category_summary(item.body, item)
    item.body = _rewrite_function_section(item.body, block, item)
    item.body = _rewrite_source_section(item.body, block)
    item.body = _strip_page_markers_outside_source_section(item.body)
    if item.doc_type == "function" and not _source_describes_function(block):
        item.doc_type = "biz"
        item.kb_id = re.sub(r"^function-", "biz-", item.kb_id)
    return item


def _with_category_summary(body: str, item: KnowledgeItem) -> str:
    """确保正文包含分类摘要。"""
    if "知识分类：" in body:
        return body

    lines = body.strip().splitlines()
    if not lines:
        return _category_summary(item)

    summary = _category_summary(item)
    if lines[0].startswith("# "):
        return "\n".join([lines[0], "", summary, "", *lines[1:]]).strip()
    return f"{summary}\n\n{body.strip()}"


def _category_summary(item: KnowledgeItem) -> str:
    """生成正文中的分类摘要块。"""
    keywords = "、".join(item.category_keywords)
    lines = [
        "知识分类：",
        f"大类标题：{item.category or '未分类'}",
        f"小类标题：{item.subcategory or '无'}",
        f"关键词：{keywords or '无'}",
    ]
    related_items = item.related_items or _related_items_from_legacy(
        item.category,
        item.related_categories,
        item.relation_notes,
    )
    if related_items:
        lines.append("关联信息：")
        lines.append(json.dumps(related_items, ensure_ascii=False, indent=2))
    return "\n".join(lines)


def _rewrite_function_section(body: str, block: ParsedBlock, item: KnowledgeItem) -> str:
    """重写正文的关联能力章节。"""
    replacement = _function_section_content(block, item)
    pattern = re.compile(
        r"(^##\s+4\.\s+关联能力\s*\n)(.*?)(?=^##\s+5\.\s+来源依据|\Z)",
        re.S | re.M,
    )
    match = pattern.search(body)
    if match:
        return pattern.sub(lambda m: f"{m.group(1).rstrip()}\n\n{replacement}\n\n", body, count=1).strip()

    return f"{body.rstrip()}\n\n## 4. 关联能力\n\n{replacement}".strip()


def _function_section_content(block: ParsedBlock, item: KnowledgeItem) -> str:
    """根据匹配工具生成关联能力内容。"""
    tools = _matched_tools(block, item)
    if not tools:
        return "暂无。"
    return "\n\n".join(f"```yaml\n{_tool_yaml(tool)}\n```" for tool in tools)


def _rewrite_source_section(body: str, block: ParsedBlock) -> str:
    """重写正文的来源依据章节。"""
    replacement = _source_section_content(block)
    pattern = re.compile(
        r"(^##\s+5\.\s+来源依据\s*\n)(.*?)(?=^##\s+\d+\.|\Z)",
        re.S | re.M,
    )
    match = pattern.search(body)
    if match:
        return pattern.sub(lambda m: f"{m.group(1).rstrip()}\n\n{replacement}\n", body, count=1).strip()
    return f"{body.rstrip()}\n\n## 5. 来源依据\n\n{replacement}".strip()


def _source_section_content(block: ParsedBlock) -> str:
    """生成标准来源依据内容。"""
    lines = [
        f"- 来源文档：{block.source_doc}",
        f"- 来源章节：{block.source_section or '全文'}",
    ]
    if block.pages:
        pages = "、".join(map(str, sorted(set(block.pages))))
        lines.append(f"- 来源页码：{pages}")
    lines.append("- 来源说明：基于来源章节归纳，需人工复核原文一致性。")
    return "\n".join(lines)


def _strip_page_markers_outside_source_section(body: str) -> str:
    """移除来源依据外的页码痕迹。"""
    match = re.search(r"^##\s+5\.\s+来源依据\s*$", body, flags=re.M)
    if not match:
        return _strip_page_marker_lines(body)
    before = body[:match.start()]
    after = body[match.start():]
    return f"{_strip_page_marker_lines(before).rstrip()}\n\n{after.lstrip()}".strip()


def _strip_page_marker_lines(text: str) -> str:
    """移除文本中的页码行。"""
    text = re.sub(r"(?m)^\s*(?:[-*]\s*)?来源页码[：:][^\n]*\n?", "", text)
    text = re.sub(r"(?m)^\s*(?:[-*]\s*)?页码[：:]\s*\d+(?:\s*[,，、]\s*\d+)*\s*\n?", "", text)
    text = re.sub(r"(?m)^\s*(?:[-*]\s*)?第\s*\d{1,4}\s*页(?:\s*/\s*共\s*\d{1,4}\s*页)?\s*\n?", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _matched_tools(block: ParsedBlock, item: KnowledgeItem) -> List[Dict[str, Any]]:
    """根据来源文本匹配可关联工具。"""
    source_text = _strip_negative_tool_sentences(_strip_category_summary(_strip_function_section("\n".join([
        block.source_section,
        block.content,
        item.title,
        item.body,
    ]))))
    source_tokens = _match_tokens(source_text)
    if not source_tokens:
        return []

    matches: List[tuple[int, Dict[str, Any]]] = []
    for tool in _read_tools():
        tool_text = _tool_match_text(tool)
        tool_tokens = _match_tokens(tool_text)
        significant_overlap = _significant_token_overlap(source_tokens, tool_tokens)
        if _has_literal_tool_signal(source_text, tool) or _has_tool_phrase_match(source_text, tool_text):
            matches.append((max(len(significant_overlap), 8), tool))
            continue
        if len(significant_overlap) >= 4:
            matches.append((len(significant_overlap), tool))

    return [tool for _, tool in sorted(matches, key=lambda value: value[0], reverse=True)[:3]]


def _tool_match_text(tool: Dict[str, Any]) -> str:
    """拼接工具描述和触发条件用于匹配。"""
    return " ".join([
        str(tool.get("description") or ""),
        str(tool.get("trigger") or ""),
    ])


def _significant_token_overlap(source_tokens: set[str], tool_tokens: set[str]) -> set[str]:
    """计算去除结构噪声后的 token 交集。"""
    structural_noise = {
        "api", "接口", "服务", "工具", "函数", "查询", "获取", "列表", "详情",
        "具体", "类型", "状态", "编码", "名称", "标识",
    }
    return {
        token for token in source_tokens.intersection(tool_tokens)
        if token not in structural_noise and (len(token) >= 4 or re.fullmatch(r"[a-z0-9_]{3,}", token))
    }


def _has_tool_phrase_match(source_text: str, tool_text: str) -> bool:
    """判断来源是否包含工具的完整触发短语。"""
    source = _compact_for_match(source_text)
    for phrase in _tool_phrases(tool_text):
        if phrase in source:
            return True
    return False


def _tool_phrases(tool_text: str) -> List[str]:
    """从工具文本中抽取可匹配短语。"""
    phrases: List[str] = []
    for part in re.split(r"[，,。；;、\s]+", tool_text.lower()):
        compact = _compact_for_match(part)
        if len(compact) < 8:
            continue
        if not _is_generic_tool_phrase(compact):
            phrases.append(compact)
    return phrases


def _is_generic_tool_phrase(text: str) -> bool:
    """过滤过短或泛化的工具短语。"""
    generic = {
        "查询", "获取", "列表", "详情", "信息", "数据", "状态", "类型",
        "根据", "当前", "用户", "所属", "用于", "支持", "返回",
    }
    return text in generic or len(text) < 8


def _compact_for_match(text: str) -> str:
    """压缩文本空白用于短语匹配。"""
    return re.sub(r"\s+", "", text.lower())


def _strip_function_section(text: str) -> str:
    """移除正文中已有的关联能力章节。"""
    return re.sub(
        r"^##\s+4\.\s+关联能力\s*\n.*?(?=^##\s+5\.\s+来源依据|\Z)",
        "",
        text,
        flags=re.S | re.M,
    )


def _strip_category_summary(text: str) -> str:
    """移除正文中的分类摘要块。"""
    for label in ("知识分类", "知识大类说明"):
        text = re.sub(
            rf"{label}：\s*\n.*?(?=\n{{2,}}|^##\s+|\Z)",
            "",
            text,
            flags=re.S | re.M,
        )
    return text


def _strip_negative_tool_sentences(text: str) -> str:
    """移除明确否定工具能力的句子。"""
    sentences = re.split(r"([。！？\n])", text)
    kept: List[str] = []
    for idx in range(0, len(sentences), 2):
        sentence = sentences[idx]
        delimiter = sentences[idx + 1] if idx + 1 < len(sentences) else ""
        if re.search(r"(不涉及|无需|不需要|不得|禁止|不包括).{0,24}(函数|接口|api|工具|能力|查询)", sentence, re.I):
            continue
        kept.append(sentence + delimiter)
    return "".join(kept)


def _match_tokens(text: str) -> set[str]:
    """从文本中提取工具匹配 token。"""
    normalized = text.lower()
    raw_tokens = re.findall(r"[a-z0-9_]{3,}|[\u4e00-\u9fff]{2,}", normalized)
    stopwords = {
        "查询", "情况", "当前", "根据", "用于", "辅助", "例如", "包括", "用户", "所属",
        "对象", "主体", "时间", "场景", "知识", "条目", "来源", "文档", "规则", "要求",
    }
    tokens: set[str] = set()
    for token in raw_tokens:
        if token in stopwords:
            continue
        tokens.add(token)
        if re.search(r"[\u4e00-\u9fff]", token) and len(token) > 4:
            tokens.update(token[idx:idx + 4] for idx in range(0, len(token) - 3))
    return tokens


def _has_literal_tool_signal(text: str, tool: Dict[str, Any]) -> bool:
    """判断来源是否直接出现工具名称。"""
    lowered = text.lower()
    for key in ("name", "display_name"):
        value = str(tool.get(key) or "").strip().lower()
        if value and value in lowered:
            return True
    return False


def _tool_yaml(tool: Dict[str, Any]) -> str:
    """把工具配置渲染为 YAML 片段。"""
    lines = [
        f"function_name: {_yaml_scalar(tool.get('name') or '')}",
        f"display_name: {_yaml_scalar(tool.get('display_name') or '')}",
        f"function_type: {_yaml_scalar(tool.get('function_type') or 'read')}",
        f"description: {_yaml_scalar(tool.get('description') or '')}",
        f"risk_level: {_yaml_scalar(tool.get('risk_level') or 'low')}",
        f"requires_confirmation: {_yaml_bool(tool.get('requires_confirmation', False))}",
        f"required_permissions: {_yaml_list(tool.get('required_permissions') or [])}",
    ]
    lines.extend(_schema_yaml("input_schema", tool.get("input_schema")))
    lines.extend(_schema_yaml("output_schema", tool.get("output_schema")))
    return "\n".join(lines)


def _schema_yaml(label: str, schema) -> List[str]:
    """把 schema properties 渲染为 YAML 行。"""
    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict) or not properties:
        return [f"{label}: {{}}"]
    lines = [f"{label}:"]
    for name, spec in properties.items():
        description = _schema_description(spec)
        lines.append(f"  {name}: {_yaml_scalar(description)}")
    return lines


def _schema_description(spec) -> str:
    """提取 schema 字段描述。"""
    if isinstance(spec, dict):
        return str(spec.get("description") or spec.get("title") or spec.get("type") or "")
    return str(spec or "")


def _yaml_scalar(value) -> str:
    """把值渲染为 YAML 字符串标量。"""
    return json.dumps(str(value), ensure_ascii=False)


def _yaml_bool(value) -> str:
    """把布尔值渲染为 YAML 布尔标量。"""
    return "true" if bool(value) else "false"


def _yaml_list(value) -> str:
    """把列表渲染为 YAML 行内列表。"""
    if not isinstance(value, list):
        return "[]"
    return "[" + ", ".join(_yaml_scalar(item) for item in value) + "]"


def _source_describes_function(block: ParsedBlock) -> bool:
    """判断来源是否本身在描述函数接口。"""
    text = f"{block.source_doc}\n{block.source_section}\n{block.content}".lower()
    return bool(re.search(r"function_name|input_schema|output_schema|函数名称|入参|出参", text))


def _item_from_dict(raw: Dict, block: ParsedBlock, idx: int, status: str) -> KnowledgeItem:
    """把模型原始字典转换为知识条目。"""
    title = str(raw.get("title") or _guess_title(block)).strip()
    doc_type = str(raw.get("doc_type") or "biz").strip()
    if doc_type not in DOC_TYPES:
        doc_type = "biz"
    category = str(raw.get("category") or block.category or _guess_category(block)).strip()
    subcategory = _clean_taxonomy_text(raw.get("subcategory") or block.subcategory or category)
    category_path = _as_list(raw.get("category_path")) or block.category_path or [category, subcategory]
    category_path = _unique_list([category, *category_path, subcategory])
    body = str(raw.get("body") or _build_body(title, block.content)).strip()
    if not body.startswith("# "):
        body = f"# {title}\n\n{body}"
    return KnowledgeItem(
        kb_id=_kb_id(doc_type, title, _kb_source_seed(block), idx),
        title=title,
        doc_type=doc_type,
        domain=DEFAULT_DOMAIN,
        category=category,
        category_keywords=_clean_category_keywords(raw.get("category_keywords"), block, body),
        business_modules=_as_list(raw.get("business_modules")),
        source_doc=block.source_doc,
        source_version=str(raw.get("source_version") or _guess_version(block.source_doc + " " + block.content)),
        source_section=block.source_section,
        effective_date="",
        owner=DEFAULT_OWNER,
        confidentiality="内部",
        risk_level=_normalize_risk_level(raw.get("risk_level")),
        applicable_roles=_as_list(raw.get("applicable_roles")),
        tags=_as_list(raw.get("tags")),
        status=status,
        source_order=block.order,
        source_pages=sorted(set(block.pages)),
        review_status="pending",
        source_trace=_source_trace(block),
        body=body,
        source_doc_description=_clean_description(
            raw.get("source_doc_description") or block.source_doc_description
        ),
        subcategory=subcategory,
        category_path=category_path,
        related_categories=_unique_list([*_as_list(raw.get("related_categories")), *block.related_categories])[:8],
        relation_notes=_clean_notes([*_as_list(raw.get("relation_notes")), *block.relation_notes])[:8],
        related_items=_merged_related_items(raw.get("related_items"), block, category),
    )


def _as_list(value) -> List[str]:
    """把字符串或列表归一化为字符串列表。"""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [v.strip() for v in re.split(r"[,，、]", value) if v.strip()]
    return []


def _unique_list(values: List[str]) -> List[str]:
    """清洗并去重字符串列表。"""
    seen = set()
    output = []
    for value in values:
        cleaned = _clean_taxonomy_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output


def _clean_category_keywords(raw_value, block: ParsedBlock, body: str) -> List[str]:
    """合并模型和来源关键词并清洗排序。"""
    values: List[str] = []
    values.extend(_as_list(raw_value))
    values.extend(block.category_keywords)
    title_tokens = _keyword_tokens(block.subcategory)
    values.extend(title_tokens)
    values.extend(title_tokens)
    values.extend(title_tokens)
    values.extend(_keyword_tokens(_core_sections_for_coverage(body)))
    values.extend(_keyword_tokens(block.content[:1200]))
    return _rank_keywords(values, block.category)[:10]


def _keyword_tokens(text: str) -> List[str]:
    """从文本中抽取关键词候选。"""
    return [
        token
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}|[\u4e00-\u9fff][\u4e00-\u9fffA-Za-z0-9]{1,18}", str(text or ""))
        if _clean_keyword(token)
    ]


def _rank_keywords(values: List[str], category: str) -> List[str]:
    """按频次、位置和大类占比排序关键词。"""
    counts: Dict[str, int] = {}
    first_pos: Dict[str, int] = {}
    category_tokens = {_clean_keyword(token) for token in _keyword_tokens(category)}
    category_tokens.discard("")
    for idx, value in enumerate(values):
        keyword = _clean_keyword(value)
        if not keyword:
            continue
        counts[keyword] = counts.get(keyword, 0) + 1
        first_pos.setdefault(keyword, idx)

    output: List[str] = []
    category_count = 0
    for keyword, _ in sorted(counts.items(), key=lambda item: (-item[1], first_pos[item[0]], -len(item[0]))):
        if keyword in category_tokens:
            if category_count >= 3:
                continue
            category_count += 1
        output.append(keyword)
        if len(output) >= 10:
            break
    return output


def _clean_keyword(value) -> str:
    """清洗关键词并过滤结构性噪声。"""
    text = _clean_taxonomy_text(value)
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
        "知识条目", "来源文档", "核心内容",
        "适用边界", "使用要求", "关联能力", "来源依据", "暂无", "原文未明确说明",
        "本分类", "当前小类", "小类标题",
    }


def _merged_related_items(raw_value, block: ParsedBlock, category: str) -> List[Dict[str, str]]:
    """合并并清洗结构化关联条目。"""
    values = [*_as_related_items(raw_value, category), *block.related_items]
    if not values and (block.related_categories or block.relation_notes):
        values = _related_items_from_legacy(
            category,
            block.related_categories,
            block.relation_notes,
        )
    return _dedupe_related_items(values)[:8]


def _as_related_items(value, default_category: str) -> List[Dict[str, str]]:
    """把模型输出归一化为关联条目列表。"""
    if not isinstance(value, list):
        return []
    items: List[Dict[str, str]] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        category = _clean_taxonomy_text(
            raw.get("大类标题") or raw.get("大类") or raw.get("category") or default_category
        )
        subcategory = _clean_taxonomy_text(
            raw.get("小类标题") or raw.get("小类") or raw.get("subcategory") or raw.get("title")
        )
        if not subcategory:
            continue
        info = _clean_relation_info(
            raw.get("关联说明") or raw.get("关联信息") or raw.get("说明") or raw.get("reason")
        )
        relevance = _clean_relevance(raw.get("关联度") or raw.get("relevance"))
        items.append({
            "大类标题": category or default_category,
            "小类标题": subcategory,
            "关联说明": info or "与当前小类存在结构、标题或核心语义上的关联，可作为补充参考。",
            "关联度": relevance,
        })
    return items


def _dedupe_related_items(values: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """按大类和小类去重关联条目。"""
    output: List[Dict[str, str]] = []
    seen = set()
    for value in values:
        category = _clean_taxonomy_text(value.get("大类标题"))
        subcategory = _clean_taxonomy_text(value.get("小类标题"))
        if not subcategory:
            continue
        key = (category, subcategory)
        if key in seen:
            continue
        seen.add(key)
        output.append({
            "大类标题": category,
            "小类标题": subcategory,
            "关联说明": _clean_relation_info(value.get("关联说明")),
            "关联度": _clean_relevance(value.get("关联度")),
        })
    return output


def _related_items_from_legacy(
    category: str,
    related_categories: List[str],
    relation_notes: List[str],
) -> List[Dict[str, str]]:
    """把旧版关联字段转换为结构化条目。"""
    values: List[Dict[str, str]] = []
    for idx, name in enumerate(related_categories[:6]):
        relevance = "高" if idx < 3 else "一般"
        note = relation_notes[idx] if idx < len(relation_notes) else ""
        values.append({
            "大类标题": category,
            "小类标题": name,
            "关联说明": _legacy_relation_info(note),
            "关联度": relevance,
        })
    return values


def _legacy_relation_info(note: str) -> str:
    """清洗旧版关联说明。"""
    cleaned = _clean_relation_info(note)
    if cleaned and "同属" not in cleaned[:20]:
        return cleaned
    return "与当前小类存在结构、标题或核心语义上的关联，可作为补充参考。"


def _related_items_prompt(items: List[Dict[str, str]]) -> str:
    """把关联条目压缩为提示文本。"""
    return json.dumps(items, ensure_ascii=False)


def _clean_relation_info(value) -> str:
    """清洗关联说明文本。"""
    text = _clean_description(value)
    text = re.sub(r"回答时应结合来源章节区分适用场景、交互对象和处理要求。?", "", text)
    text = re.sub(r"^[“”\"']?[^“”\"']{1,80}[“”\"']?与[“”\"']?[^“”\"']{1,80}[“”\"']?同属[“”\"']?[^“”\"']{1,120}[“”\"']?大类[，,]?", "", text)
    text = text.strip(" ：:，,。；;、")
    return text[:120]


def _clean_relevance(value) -> str:
    """归一化关联度枚举值。"""
    text = str(value or "").strip()
    if text in {"极高", "高", "一般", "低"}:
        return text
    if text in {"最高", "强", "较高"}:
        return "高"
    if text in {"中", "中等", "普通"}:
        return "一般"
    return "一般"


def _clean_taxonomy_text(value) -> str:
    """清洗分类层级文本。"""
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" ：:，,。；;、[]")
    return text[:80]


def _clean_description(value) -> str:
    """清洗说明类文本。"""
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    text = text.replace('"', "“").replace("'", "’")
    return text.strip(" ：:，,；;")[:180]


def _clean_notes(values: List[str]) -> List[str]:
    """清洗并去重说明列表。"""
    notes = []
    seen = set()
    for value in values:
        cleaned = _clean_description(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        notes.append(cleaned)
    return notes[:5]


def _guess_title(block: ParsedBlock) -> str:
    """从片段中推断条目标题。"""
    for line in block.content.splitlines():
        match = re.match(r"^#{1,4}\s+(.+)$", line.strip())
        if match:
            return match.group(1).strip()[:80]
    return block.source_section[:80] or "待整理知识条目"


def _guess_category(block: ParsedBlock) -> str:
    """从片段或来源文件推断分类。"""
    if block.category:
        return block.category
    title = block.source_doc.rsplit(".", 1)[0].strip()
    return title[:80] or "未分类"


def _normalize_risk_level(value) -> str:
    """归一化风险等级枚举值。"""
    risk_level = str(value or "low").strip().lower()
    return risk_level if risk_level in {"low", "medium", "high", "critical"} else "low"


def _guess_version(text: str) -> str:
    """从文本中提取版本号。"""
    match = re.search(r"[vV]\s*(\d+(?:\.\d+)*)", text)
    return f"V{match.group(1)}" if match else ""


def _build_body(title: str, source_content: str) -> str:
    """基于来源文本生成兜底正文。"""
    content = source_content.strip()
    content = re.sub(r"^#{1,4}\s+.+\n?", "", content, count=1).strip()
    return f"""# {title}

## 1. 核心内容

{content}

## 2. 适用边界

原文未明确说明。

## 3. 使用要求

当用户咨询本条目相关问题时，模型应基于来源依据回答；缺少关键数据时，应说明需要补充的信息，不得主观推断。

## 4. 关联能力

暂无。

## 5. 来源依据

基于来源章节归纳，需人工复核原文一致性。
""".strip()


def _kb_id(doc_type: str, title: str, source_doc: str, idx: int) -> str:
    """生成稳定的离线知识条目标识。"""
    digest = hashlib.md5(f"{source_doc}:{title}:{idx}".encode("utf-8")).hexdigest()[:10]
    return f"{doc_type}-offline-{digest}-v1"


def _kb_source_seed(block: ParsedBlock) -> str:
    """生成条目 ID 使用的来源种子。"""
    return f"{block.source_doc}:{block.source_section}:{block.order}"


def _source_trace(block: ParsedBlock) -> str:
    """生成来源章节和页码追踪信息。"""
    pages = ",".join(map(str, block.pages)) if block.pages else ""
    return f"section={block.source_section}; pages={pages}".strip("; ")
