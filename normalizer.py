from __future__ import annotations

import hashlib
import json
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from app_config import get_llm_config
from schemas import DOC_TYPES, KnowledgeItem, ParsedBlock


DEFAULT_DOMAIN = "联合运维"
DEFAULT_OWNER = "联合运维知识库"
CURRENT_DIR = Path(__file__).resolve().parent
KB_SPEC_PATH = CURRENT_DIR / "prompts" / "联合运维知识库建立规范.md"
TOOLS_PATH = CURRENT_DIR / "input" / "function" / "tools.json"
LLM_MAX_RETRIES = 10


def normalize_block(block: ParsedBlock, status: str = "draft") -> List[KnowledgeItem]:
    if get_llm_config().enabled:
        items = _normalize_with_llm(block, status=status)
        if items:
            return items
        _abort_llm("model returned no valid knowledge items", block)
    return [_normalize_heuristically(block, status=status)]


def _normalize_with_llm(block: ParsedBlock, status: str) -> List[KnowledgeItem]:
    config = get_llm_config()
    if not (config.base_url and config.api_key and config.model):
        _abort_llm("missing base_url, api_key, or model", block)

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
        print(f"llm error: cannot load ZhipuAI SDK ({exc})")
        return []
    client = client_cls(api_key=config.api_key, base_url=config.base_url)

    compact_retry = False
    for attempt in range(1, LLM_MAX_RETRIES + 1):
        prompt = _compact_retry_prompt(base_prompt) if compact_retry else base_prompt
        try:
            print(
                "llm request: "
                f"provider=zhipu base_url={config.base_url} attempt={attempt}/{LLM_MAX_RETRIES}"
            )
            response = _create_zhipu_completion(client, config, prompt)
        except Exception as exc:
            elapsed = time.monotonic() - started_at
            print(
                "llm error: "
                f"{type(exc).__name__} attempt={attempt}/{LLM_MAX_RETRIES} "
                f"after {elapsed:.1f}s detail={exc}"
            )
            if attempt >= LLM_MAX_RETRIES:
                _abort_llm(f"request failed after {LLM_MAX_RETRIES} attempts: {type(exc).__name__}", block)
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
                _abort_llm("empty response content after 10 attempts", block)
            time.sleep(min(2 ** (attempt - 1), 30))
            continue

        parsed = _extract_json(content)
        if not parsed:
            compact_retry = compact_retry or _looks_truncated(content, finish_reason)
            print(
                "llm parse failed: response is not valid JSON "
                f"finish_reason={finish_reason or 'unknown'} "
                f"truncated={_looks_truncated(content, finish_reason)} "
                f"preview={_preview(content)}"
            )
            if attempt >= LLM_MAX_RETRIES:
                _abort_llm("response is not valid JSON after 10 attempts", block)
            time.sleep(min(2 ** (attempt - 1), 30))
            continue

        raw_items = _coerce_raw_items(parsed)
        if not isinstance(raw_items, list):
            compact_retry = compact_retry or _looks_truncated(content, finish_reason)
            print(
                "llm parse failed: JSON does not contain an items list "
                f"finish_reason={finish_reason or 'unknown'} "
                f"truncated={_looks_truncated(content, finish_reason)} "
                f"top_level={_json_shape(parsed)} preview={_preview(content)}"
            )
            if attempt >= LLM_MAX_RETRIES:
                _abort_llm("JSON does not contain an items list after 10 attempts", block)
            time.sleep(min(2 ** (attempt - 1), 30))
            continue

        items: List[KnowledgeItem] = []
        for idx, raw in enumerate(raw_items, start=1):
            if not isinstance(raw, dict):
                continue
            items.append(_item_from_dict(raw, block, idx, status))
        print(f"llm done: generated_items={len(items)} attempt={attempt}/{LLM_MAX_RETRIES}")
        if items:
            return items
        if attempt >= LLM_MAX_RETRIES:
            _abort_llm("items list contained no valid objects after 10 attempts", block)
        time.sleep(min(2 ** (attempt - 1), 30))

    _abort_llm("model call failed", block)


def _system_message() -> str:
    return (
        "你是严谨的运维知识库整理助手，只能依据输入原文生成结构化知识条目。"
        "你必须只返回一个 JSON object，根节点必须只有 items 字段，"
        "且 items 必须是数组。不要返回 Markdown、解释文字或其他根字段。"
    )


def _messages(prompt: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": _system_message()},
        {"role": "user", "content": prompt},
    ]


def _compact_retry_prompt(base_prompt: str) -> str:
    return (
        base_prompt
        + "\n\n重试补充要求：上一次输出疑似过长或结构不完整。"
        "本次必须只生成 1 个 item，保留规范要求的正文 1-9 节，但每节只写当前原文中最必要、最确定的信息。"
        "不要省略 JSON 外层 items，不要输出多个条目，不要输出解释文字。"
    )


def _create_zhipu_completion(client, config, prompt: str):
    return client.chat.completions.create(
        model=config.model,
        messages=_messages(prompt),
        stream=False,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        do_sample=False,
        response_format={"type": "json_object"},
        thinking={"type": "disabled", "clear_thinking": True},
    )


def _get_zhipu_client_class():
    try:
        from zai import ZaiClient

        return ZaiClient
    except (ImportError, AttributeError):
        pass

    try:
        from zai import ZhipuAiClient

        return ZhipuAiClient
    except (ImportError, AttributeError):
        pass

    from zhipuai import ZhipuAI

    return ZhipuAI


def _extract_response_content(response) -> str:
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        return str((message or {}).get("content") or "")

    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    if message is None and isinstance(choices[0], dict):
        message = choices[0].get("message")
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", "") or "")


def _extract_reasoning_content(response) -> str:
    message = _first_message(response)
    if isinstance(message, dict):
        return str(message.get("reasoning_content") or "")
    return str(getattr(message, "reasoning_content", "") or "")


def _finish_reason(response) -> str:
    choice = _first_choice(response)
    if isinstance(choice, dict):
        return str(choice.get("finish_reason") or "")
    return str(getattr(choice, "finish_reason", "") or "")


def _first_message(response):
    choice = _first_choice(response)
    if isinstance(choice, dict):
        return choice.get("message")
    return getattr(choice, "message", None)


def _first_choice(response):
    if isinstance(response, dict):
        choices = response.get("choices") or []
    else:
        choices = getattr(response, "choices", None) or []
    return choices[0] if choices else None


def _response_debug(response) -> str:
    return _preview(repr(response))


def _json_shape(value) -> str:
    if isinstance(value, dict):
        return f"object keys={list(value.keys())[:10]}"
    if isinstance(value, list):
        return f"array len={len(value)}"
    return type(value).__name__


def _coerce_raw_items(parsed):
    if isinstance(parsed, dict):
        items = parsed.get("items")
        if isinstance(items, list):
            return items

        for key in ("knowledge_items", "records", "data", "result", "results"):
            value = parsed.get(key)
            if isinstance(value, list):
                print(f"llm parse notice: using non-standard list field '{key}' as items")
                return value
            if isinstance(value, dict):
                nested = _coerce_raw_items(value)
                if isinstance(nested, list):
                    print(f"llm parse notice: using nested field '{key}' as items")
                    return nested

        if _looks_like_single_item(parsed):
            print("llm parse notice: wrapping single item object as items[0]")
            return [parsed]

    if isinstance(parsed, list):
        print("llm parse notice: wrapping root array as items")
        return parsed

    return None


def _looks_like_single_item(value: Dict) -> bool:
    required_signal = {"title", "body"}
    item_fields = {
        "title",
        "doc_type",
        "business_modules",
        "source_version",
        "risk_level",
        "applicable_roles",
        "tags",
        "body",
        "split_reason",
    }
    return required_signal.issubset(value.keys()) and len(item_fields.intersection(value.keys())) >= 4


def _looks_truncated(content: str, finish_reason: str) -> bool:
    if finish_reason == "length":
        return True
    stripped = content.strip()
    if not stripped:
        return False
    return stripped.count("{") > stripped.count("}") or stripped.count("[") > stripped.count("]")


def _abort_llm(message: str, block: ParsedBlock) -> None:
    print(
        "ALERT: llm draft failed; aborting. "
        f"reason={message} doc={block.source_doc} section={block.source_section}"
    )
    raise SystemExit(1)


def _build_prompt(block: ParsedBlock, status: str) -> str:
    spec = _read_kb_spec()
    return f"""
请将以下原始文档片段整理为标准知识库条目。

要求：
1. 严格参照《联合运维知识库建立规范》的元数据字段、正文 1-9 节结构、内容切分原则和质量校验要求生成。
2. 只依据原文理解业务场景、业务模块、角色、标签、风险等级和处置策略，不要依据示例或常见关键词进行套写。
3. 如果一个片段包含多个独立场景、规则、指标、处置策略，请拆成多个 items。
4. 每个 item 必须可独立检索、独立回答，颗粒度控制在 800 到 1500 中文字符左右；复杂表格可适当放宽。
5. 不要编造来源、阈值、角色、日期、版本；原文没有的信息留空、空数组或使用规范允许的通用值。
6. 涉及表格、阈值、比较符、单位、持续时间、笔数、适用对象时必须保留原始逻辑。
7. 输出严格 JSON 对象，不要 Markdown 代码围栏，不要解释文字，不要在 JSON 前后添加任何内容。
8. status 固定为 "{status}"。
9. JSON 根节点必须严格为一个对象：{{"items": [...]}}。禁止返回单个 item 对象、禁止返回纯数组、禁止返回 result/data/records/knowledge_items 等其他根字段。
10. 为避免输出被截断，优先生成 1 个覆盖本片段核心内容的综合 item；只有原文明确包含多个相互独立主题时，才拆分为多个 items。
11. “辅助上下文”只用于理解当前片段在全文中的位置、术语和前后关系；不要把辅助上下文中独有而当前原文没有的事实写成正文依据。
12. body 必须对齐目标知识库样式：YAML Front Matter 由程序生成，body 只输出 Markdown 正文；正文必须包含 # 标题，以及 ## 1. 适用范围、## 2. 规则原则、## 3. 标准条件、## 4. 处置要求、## 5. 补充参考场景、## 6. 关联函数、## 7. 模型回答要求、## 8. 检索提示、## 9. 来源依据。
13. 如果某类条目不适用某一节，也必须保留该节标题，并写“暂无”或“原文未明确说明”，不要删除章节。
14. “关联函数”只能从“可用工具列表”中选择。只有当工具 description/trigger/input_schema 与当前知识条目明确相关时，才按指定 YAML 格式写入；不确定时写“暂无”，等待人工兜底。

doc_type 只能取：
{", ".join(sorted(DOC_TYPES))}

唯一允许的 JSON 输出格式：
{{
  "items": [
    {{
      "title": "",
      "doc_type": "scenario",
      "category": "",
      "category_description": "",
      "category_keywords": [],
      "business_modules": [],
      "source_version": "",
      "risk_level": "low|medium|high|critical",
      "applicable_roles": [],
      "tags": [],
      "body": "Markdown 正文，必须严格包含 # 标题，以及 ## 1. 适用范围、## 2. 规则原则、## 3. 标准条件、## 4. 处置要求、## 5. 补充参考场景、## 6. 关联函数、## 7. 模型回答要求、## 8. 检索提示、## 9. 来源依据",
      "split_reason": "为什么这是独立条目"
    }}
  ]
}}

《联合运维知识库建立规范》：
{spec}

可用工具列表：
{_read_tool_spec()}

来源文档：{block.source_doc}
知识大类：{block.category or "未分类"}
大类说明：{block.category_description or "无"}
大类关键词：{", ".join(block.category_keywords) if block.category_keywords else "无"}
来源章节：{block.source_section}
来源页码：{",".join(map(str, block.pages)) if block.pages else ""}

辅助上下文：
{block.context or "无"}

原文：
{block.content}
""".strip()


@lru_cache(maxsize=1)
def _read_kb_spec() -> str:
    try:
        return KB_SPEC_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


@lru_cache(maxsize=1)
def _read_tool_spec() -> str:
    try:
        raw = json.loads(TOOLS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return "无"
    if not isinstance(raw, list) or not raw:
        return "无"
    chunks = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        chunks.append(_format_tool_for_prompt(item))
    return "\n\n".join(chunks) if chunks else "无"


def _format_tool_for_prompt(item: Dict) -> str:
    input_schema = item.get("input_schema") if isinstance(item.get("input_schema"), dict) else {}
    output_schema = item.get("output_schema") if isinstance(item.get("output_schema"), dict) else {}
    return "\n".join([
        f"- function_name: {item.get('name', '')}",
        f"  display_name: {item.get('display_name', '')}",
        "  function_type: read",
        f"  description: {item.get('description', '')}",
        f"  trigger: {item.get('trigger', '')}",
        "  risk_level: low",
        "  requires_confirmation: false",
        "  required_permissions: []",
        f"  input_schema: {json.dumps(input_schema.get('properties', {}), ensure_ascii=False)}",
        f"  output_schema: {json.dumps(output_schema.get('properties', {}), ensure_ascii=False)}",
    ])


def _extract_json(text: str):
    text = text.strip()
    text = _strip_code_fence(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for candidate in _json_candidates(text):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    fence = re.match(r"^```(?:json|JSON)?\s*(.*?)\s*```$", text, re.S)
    return fence.group(1).strip() if fence else text


def _json_candidates(text: str) -> List[str]:
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
    return text.strip()


def _normalize_heuristically(block: ParsedBlock, status: str) -> KnowledgeItem:
    title = _guess_title(block)
    doc_type = "biz"
    body = _build_body(title, block.content)
    return KnowledgeItem(
        kb_id=_kb_id(doc_type, title, block.source_doc, 1),
        title=title,
        doc_type=doc_type,
        domain=DEFAULT_DOMAIN,
        category=block.category or _guess_category(block),
        category_description=block.category_description or _guess_category_description(block),
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
        review_status="pending",
        source_trace=_source_trace(block),
        body=body,
    )


def _item_from_dict(raw: Dict, block: ParsedBlock, idx: int, status: str) -> KnowledgeItem:
    title = str(raw.get("title") or _guess_title(block)).strip()
    doc_type = str(raw.get("doc_type") or "biz").strip()
    if doc_type not in DOC_TYPES:
        doc_type = "biz"
    body = str(raw.get("body") or _build_body(title, block.content)).strip()
    if not body.startswith("# "):
        body = f"# {title}\n\n{body}"
    return KnowledgeItem(
        kb_id=_kb_id(doc_type, title, block.source_doc, idx),
        title=title,
        doc_type=doc_type,
        domain=DEFAULT_DOMAIN,
        category=str(raw.get("category") or block.category or _guess_category(block)).strip(),
        category_description=str(
            raw.get("category_description") or block.category_description or _guess_category_description(block)
        ).strip(),
        category_keywords=_as_list(raw.get("category_keywords")) or block.category_keywords or [
            str(raw.get("category") or block.category or _guess_category(block)).strip()
        ],
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
        review_status="pending",
        source_trace=_source_trace(block),
        body=body,
    )


def _as_list(value) -> List[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [v.strip() for v in re.split(r"[,，、]", value) if v.strip()]
    return []


def _guess_title(block: ParsedBlock) -> str:
    for line in block.content.splitlines():
        match = re.match(r"^#{1,4}\s+(.+)$", line.strip())
        if match:
            return match.group(1).strip()[:80]
    return block.source_section[:80] or "待整理知识条目"


def _guess_category(block: ParsedBlock) -> str:
    if block.category:
        return block.category
    title = block.source_doc.rsplit(".", 1)[0].strip()
    return title[:80] or "未分类"


def _guess_category_description(block: ParsedBlock) -> str:
    category = _guess_category(block)
    return f"本分类来源于《{category}》，用于承载该源文件生成的知识库条目。"


def _normalize_risk_level(value) -> str:
    risk_level = str(value or "low").strip().lower()
    return risk_level if risk_level in {"low", "medium", "high", "critical"} else "low"


def _guess_version(text: str) -> str:
    match = re.search(r"[vV]\s*(\d+(?:\.\d+)*)", text)
    return f"V{match.group(1)}" if match else ""


def _build_body(title: str, source_content: str) -> str:
    content = source_content.strip()
    content = re.sub(r"^#{1,4}\s+.+\n?", "", content, count=1).strip()
    return f"""# {title}

## 1. 适用范围

待人工审核确认。以下内容基于来源文档片段整理。

## 2. 规则原则

{content}

## 3. 标准条件

待人工审核补充或确认，涉及阈值、单位、持续时间、笔数和比较关系时应使用表格表达。

## 4. 处置要求

待人工审核补充或确认。

## 5. 补充参考场景

暂无。

## 6. 关联函数

暂无。

## 7. 模型回答要求

当用户咨询本条目相关问题时，模型应基于来源依据回答；缺少关键数据时，应说明需要补充的信息，不得主观推断。

## 8. 检索提示

1. “{title}的规则是什么？”
2. “{title}适用于哪些场景？”

## 9. 来源依据

基于来源章节归纳，需人工复核原文一致性。
""".strip()


def _kb_id(doc_type: str, title: str, source_doc: str, idx: int) -> str:
    digest = hashlib.md5(f"{source_doc}:{title}:{idx}".encode("utf-8")).hexdigest()[:10]
    return f"{doc_type}-offline-{digest}-v1"


def _source_trace(block: ParsedBlock) -> str:
    pages = ",".join(map(str, block.pages)) if block.pages else ""
    return f"section={block.source_section}; pages={pages}".strip("; ")
