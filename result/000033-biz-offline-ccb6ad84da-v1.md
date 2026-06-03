---
kb_id: biz-offline-ccb6ad84da-v1
title: 自由格式报文-场景六：账户侧业务状态查询的请求与应答报文结构
doc_type: biz
domain: 网联清算业务
category: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
category_keywords:
- 自由格式报文
- 场景六
- head
- body
- uops051
- sysId
- msgId
- sendDate
- YYYY
- signature
subcategory: B.10 自由格式报文-场景六
related_items:
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.9 自由格式报文-场景五
  关联说明: 与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.11 自由格式报文-场景七
  关联说明: 与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.8 自由格式报文-场景四
  关联说明: 与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.12 自由格式报文-场景八
  关联说明: 与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.7 自由格式报文-场景三
  关联说明: 与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组
  关联度: 高
business_modules:
- uops
source_doc: 互联互通机制规范.md
source_version: V1.3
source_section: B.10 自由格式报文-场景六
source_order: 33
source_pages: []
source_trace: section=B.10 自由格式报文-场景六
effective_date: ''
owner: 网联清算业务知识库
confidentiality: 内部
risk_level: low
applicable_roles: []
tags:
- 自由格式报文
- 场景六
- head
- sysId
- uops
- msgId
- uops051
- sendDate
- YYYY
- 需人工复核
status: draft
review_status: coverage_warning
---

# 自由格式报文-场景六：账户侧业务状态查询的请求与应答报文结构

知识分类：
大类标题：Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
小类标题：B.10 自由格式报文-场景六
关键词：自由格式报文、场景六、head、body、uops051、sysId、msgId、sendDate、YYYY、signature
关联信息：
[
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.9 自由格式报文-场景五",
    "关联说明": "与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.11 自由格式报文-场景七",
    "关联说明": "与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.8 自由格式报文-场景四",
    "关联说明": "与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.12 自由格式报文-场景八",
    "关联说明": "与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.7 自由格式报文-场景三",
    "关联说明": "与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组",
    "关联度": "高"
  }
]

## 1. 核心内容

> WARNING: LLM 多次重试后仍未通过来源事实覆盖校验，本条目已降为草稿，需人工复核。
> 来源文档：互联互通机制规范.md
> 来源章节：B.10 自由格式报文-场景六
> 待人工补齐或确认的来源事实：
> - "result": "yes或no"
本条目定义了《网络支付清算平台 联合运维互联互通技术规范》中自由格式报文的场景六（sceneId 为 "06"）的请求与应答报文结构。该场景主要用于基于指定的账户侧单位名称、金融编码及时间范围进行相关业务状态的查询与结果反馈。

### 请求报文结构
请求报文封装在 `request` 对象中，包含 `head`、`body` 和 `signature` 三个核心部分：

1. **报文头（head）**：
   - `sysId`：固定为 `"uops"`。
   - `msgId`：固定为 `"uops051.000.01"`。
   - `sendDate`：格式为 `"YYYY-MM-DD HH:mm:ss"`。
   - `senderInstId`：发起方机构标识。
   - `receiverInstId`：接收方机构标识。
   - `direction`：固定为 `"01"`。

2. **报文体（body）**：
   - `sceneId`：固定为 `"06"`，标识当前为场景六。
   - `content`：包含具体的查询条件参数，字段包括：
     - `instName`：账户侧单位名称。
     - `instId`：账户侧金融编码。
     - `startTime`：查询开始时间。
     - `endTime`：查询结束时间。

3. **数字签名（signature）**：`"签名内容"`。

### 应答报文结构
应答报文封装在 `response` 对象中，同样包含 `head`、`body` 和 `signature` 三个部分：

1. **报文头（head）**：
   - 包含与请求报文头一致的基础字段：`sysId`（`"uops"`）、`msgId`（`"uops051.000.01"`）、`sendDate`（`"YYYY-MM-DD HH:mm:ss"`）、`senderInstId`（发起方机构标识）、`receiverInstId`（接收方机构标识）、`direction`（`"01"`）。
   - `rspCd`：应答代码，示例值为 `"0000"`。
   - `rspMsg`：应答消息。

2. **报文体（body）**：
   - `result`：查询结果，取值为 `"yes或no"`。

3. **数字签名（signature）**：`"签名内容"`。

## 2. 适用边界

本报文结构仅适用于自由格式报文的场景六（sceneId 为 "06"）。该场景专门针对包含账户侧单位名称、账户侧金融编码以及指定查询时间区间（查询开始时间、查询结束时间）的查询请求，并返回明确的 yes 或 no 结果。其他业务场景的报文结构请参考对应场景的独立定义。

## 3. 使用要求

1. 发送请求时，必须严格遵循报文结构，确保 `sysId`、`msgId`、`sceneId` 和 `direction` 等固定值字段准确无误。
2. `sendDate` 字段必须符合 `YYYY-MM-DD HH:mm:ss` 格式要求。
3. 请求 content 中的 `startTime` 和 `endTime` 必须明确传入查询时间范围。
4. 接收应答报文时，需通过 `rspCd` 和 `rspMsg` 判断通讯与处理状态，并从 body 中的 `result` 字段提取实际的查询结论（yes 或 no）。

## 4. 关联能力

```yaml
function_name: "unit_uops_api_status"
display_name: "互联互通API接口情况查询"
function_type: "read"
description: "根据登陆用户所属org_code，查询当前机构接入的联合运维互联互通API场景，包括接入的API类型、接入时间"
risk_level: "low"
requires_confirmation: false
required_permissions: []
input_schema:
  org_code: "成员单位金融编码，例如C10010010010"
output_schema:
  switch_type: "API类型，例如normalSwitch、urgentSwitch"
  create_time: "接入时间，例如2026-01-01 13:00:00"
```

## 5. 来源依据

- 来源文档：互联互通机制规范.md
- 来源章节：B.10 自由格式报文-场景六
- 来源说明：基于来源章节归纳，需人工复核原文一致性。
