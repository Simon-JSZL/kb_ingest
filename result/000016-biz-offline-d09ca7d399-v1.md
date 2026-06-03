---
kb_id: biz-offline-d09ca7d399-v1
title: 互联互通报文整体格式：请求与应答报文结构
doc_type: biz
domain: 网联清算业务
category: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
category_keywords:
- head
- body
- signature
- 报文格式
- 请求报文结构
- 应答报文结构
- request
- response
- 报文体
- 报文头
subcategory: 报文格式
related_items:
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: 交易监控统计信息报文
  关联说明: 与当前小类共享核心语义：signature、head、body；来源结构处于同一章节组
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: 生产运维信息发送报文
  关联说明: 与当前小类共享核心语义：signature、head、body；来源结构处于同一章节组
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: 数字签名域
  关联说明: 与当前小类共享核心语义：head、body；来源结构处于同一章节组
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: 生产运维信息查询报文
  关联说明: 与当前小类共享核心语义：head、body；来源结构处于同一章节组
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: 报文头
  关联说明: 与当前小类共享核心语义：head；来源结构处于同一章节组；章节位置接近
  关联度: 一般
business_modules:
- request
- response
- head
- body
- signature
source_doc: 互联互通机制规范.md
source_version: V1.3
source_section: 7.1 报文格式
source_order: 16
source_pages: []
source_trace: section=7.1 报文格式
effective_date: ''
owner: 网联清算业务知识库
confidentiality: 内部
risk_level: low
applicable_roles: []
tags:
- 报文格式
- 请求报文
- 应答报文
- request
- response
- head
- body
- signature
status: active
review_status: pending
---

# 互联互通报文整体格式：请求与应答报文结构

知识分类：
大类标题：Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
小类标题：报文格式
关键词：head、body、signature、报文格式、请求报文结构、应答报文结构、request、response、报文体、报文头
关联信息：
[
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "交易监控统计信息报文",
    "关联说明": "与当前小类共享核心语义：signature、head、body；来源结构处于同一章节组",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "生产运维信息发送报文",
    "关联说明": "与当前小类共享核心语义：signature、head、body；来源结构处于同一章节组",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "数字签名域",
    "关联说明": "与当前小类共享核心语义：head、body；来源结构处于同一章节组",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "生产运维信息查询报文",
    "关联说明": "与当前小类共享核心语义：head、body；来源结构处于同一章节组",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "报文头",
    "关联说明": "与当前小类共享核心语义：head；来源结构处于同一章节组；章节位置接近",
    "关联度": "一般"
  }
]

## 1. 核心内容

根据规范要求，网络支付清算平台联合运维互联互通的报文格式分为**请求报文结构**和**应答报文结构**两种类型。两种报文结构均包含三个核心组成部分：报文头（head）、报文体（body）和数字签名域（signature）。

**请求报文结构**的根节点为 `request`，其下包含：
- `head`（报文头）
- `body`（报文体）
- `signature`（数字签名域）

**应答报文结构**的根节点为 `response`，其下包含：
- `head`（报文头）
- `body`（报文体）
- `signature`（数字签名域）

## 2. 适用边界

本结构适用于网络支付清算平台联合运维互联互通场景下的所有请求报文与应答报文。关于报文头（head）、报文体（body）及数字签名域（signature）各部分内部的具体字段定义与格式约束，需参见后续相关章节的具体说明。

## 3. 使用要求

在组装或解析报文时，必须严格区分请求报文（request）与应答报文（response）的根节点。无论是请求还是应答，均必须完整包含 `head`、`body`、`signature` 三个子节点结构，不得缺失。

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
- 来源章节：7.1 报文格式
- 来源说明：基于来源章节归纳，需人工复核原文一致性。
