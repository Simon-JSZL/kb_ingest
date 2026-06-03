---
kb_id: biz-offline-bfe346cd09-v1
title: 自由格式报文-场景二的请求与应答报文结构
doc_type: biz
domain: 网联清算业务
category: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
category_keywords:
- 自由格式报文
- head
- sysId
- msgId
- sendDate
- 场景二
- body
- direction
- uops
- uops051
subcategory: B.6 自由格式报文-场景二
related_items:
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.7 自由格式报文-场景三
  关联说明: 与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.5 自由格式报文-场景一
  关联说明: 与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.8 自由格式报文-场景四
  关联说明: 与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.9 自由格式报文-场景五
  关联说明: 与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.10 自由格式报文-场景六
  关联说明: 与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组
  关联度: 高
business_modules:
- uops
- JSON
source_doc: 互联互通机制规范.md
source_version: V1.3
source_section: B.6 自由格式报文-场景二
source_order: 29
source_pages: []
source_trace: section=B.6 自由格式报文-场景二
effective_date: ''
owner: 网联清算业务知识库
confidentiality: 内部
risk_level: low
applicable_roles: []
tags:
- 自由格式报文
- 场景二
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

# 自由格式报文-场景二的请求与应答报文结构

知识分类：
大类标题：Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
小类标题：B.6 自由格式报文-场景二
关键词：自由格式报文、head、sysId、msgId、sendDate、场景二、body、direction、uops、uops051
关联信息：
[
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.7 自由格式报文-场景三",
    "关联说明": "与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.5 自由格式报文-场景一",
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
    "小类标题": "B.9 自由格式报文-场景五",
    "关联说明": "与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.10 自由格式报文-场景六",
    "关联说明": "与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组",
    "关联度": "高"
  }
]

## 1. 核心内容

> WARNING: LLM 多次重试后仍未通过来源事实覆盖校验，本条目已降为草稿，需人工复核。
> 来源文档：互联互通机制规范.md
> 来源章节：B.6 自由格式报文-场景二
> 待人工补齐或确认的来源事实：
> - "msgId": "uops051.000.01",
> - "sendDate": "YYYY-MM-DD HH:mm:ss",
自由格式报文-场景二定义了用于特定运维信息交互的请求与应答报文的 JSON 数据结构。报文整体分为 `head`（报文头）、`body`（报文体）和 `signature`（签名内容）三个主要部分。

### 请求报文结构

请求报文的 `head` 部分包含以下字段：
- `sysId`：固定为 `uops`
- `msgId`：固定为 `uops051.000.01`
- `sendDate`：格式为 `YYYY-MM-DD HH:mm:ss`
- `senderInstId`：发起方机构标识
- `receiverInstId`：接收方机构标识
- `direction`：固定为 `01`

请求报文的 `body` 部分包含 `sceneId` 固定为 `02`，以及 `content` 对象，具体字段如下：
- `instName`：发起方单位名称
- `instId`：发起方金融编码
- `reinstName`：接收方单位名称
- `reinstId`：接收方金融编码
- `infoNo`：信息编号
- `startTime`：开始时间
- `endTime`：结束时间
- `reason`：原因

### 应答报文结构

应答报文的 `head` 部分除了包含与请求报文一致的基础字段（`sysId`、`msgId`、`sendDate`、`senderInstId`、`receiverInstId`、`direction`）外，还包含应答专属字段：
- `rspCd`：应答代码（示例值为 `0000`）
- `rspMsg`：应答消息

应答报文的 `body` 部分为空对象 `{}`。

## 2. 适用边界

本报文结构适用于网络支付清算平台联合运维互联互通技术规范下的自由格式报文场景二（`sceneId` 为 `02`，`direction` 为 `01`）的数据交互。其他场景或方向的报文结构请参考对应的具体规范定义。

## 3. 使用要求

- 发起请求时，必须严格按照 JSON 结构组装数据，确保 `sysId`、`msgId`、`sceneId` 和 `direction` 等固定值准确无误。
- 时间类字段（如 `sendDate`、`startTime`、`endTime`）必须遵循指定的格式标准。
- 报文必须包含 `signature` 字段以进行签名验证。
- 应答报文的 `body` 节点为空，解析时应答结果主要以 `head` 中的 `rspCd` 和 `rspMsg` 为准。

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
- 来源章节：B.6 自由格式报文-场景二
- 来源说明：基于来源章节归纳，需人工复核原文一致性。
