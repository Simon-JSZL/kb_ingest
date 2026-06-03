---
kb_id: biz-offline-b31bb6d1b3-v1
title: 生产运维信息发送报文结构及功能说明
doc_type: biz
domain: 网联清算业务
category: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
category_keywords:
- 生产运维信息发送报文
- head
- body
- signature
- sysId
- msgId
- senderInstId
- receiverInstId
- sendDate
- direction
subcategory: 生产运维信息发送报文
related_items:
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: 交易监控统计信息报文
  关联说明: 与当前小类共享核心语义：receiverInstId、senderInstId、direction；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: 生产运维信息查询报文
  关联说明: 与当前小类共享核心语义：receiverInstId、senderInstId、direction；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: 自由格式报文
  关联说明: 与当前小类共享核心语义：receiverInstId、senderInstId、direction；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.2 生产运维信息发送报文
  关联说明: 与当前小类共享核心语义：senderInstId、生产运维信息发送报文、sendDate
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.1 交易监控统计信息报文
  关联说明: 与当前小类共享核心语义：senderInstId、sendDate、msgId
  关联度: 高
business_modules:
- 网联平台
- 成员单位
source_doc: 互联互通机制规范.md
source_version: V1.3
source_section: 7.6 生产运维信息发送报文
source_order: 21
source_pages: []
source_trace: section=7.6 生产运维信息发送报文
effective_date: ''
owner: 网联清算业务知识库
confidentiality: 内部
risk_level: low
applicable_roles: []
tags:
- 生产运维信息发送报文
- request
- response
- infoNo
- instId
- reinstId
- startTime
- endTime
- rspCd
status: active
review_status: pending
---

# 生产运维信息发送报文

知识分类：
大类标题：Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
小类标题：生产运维信息发送报文
关键词：生产运维信息发送报文、head、body、signature、sysId、msgId、senderInstId、receiverInstId、sendDate、direction
关联信息：
[
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "交易监控统计信息报文",
    "关联说明": "与当前小类共享核心语义：receiverInstId、senderInstId、direction；来源结构处于同一章节组；章节位置接近",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "生产运维信息查询报文",
    "关联说明": "与当前小类共享核心语义：receiverInstId、senderInstId、direction；来源结构处于同一章节组；章节位置接近",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "自由格式报文",
    "关联说明": "与当前小类共享核心语义：receiverInstId、senderInstId、direction；来源结构处于同一章节组；章节位置接近",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.2 生产运维信息发送报文",
    "关联说明": "与当前小类共享核心语义：senderInstId、生产运维信息发送报文、sendDate",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.1 交易监控统计信息报文",
    "关联说明": "与当前小类共享核心语义：senderInstId、sendDate、msgId",
    "关联度": "高"
  }
]

## 1. 核心内容

生产运维信息发送报文用于成员单位和网联平台之间通过系统接口的方式，传递生产运维计划信息。

报文结构分为请求报文和应答报文。

**请求报文（request）**包含以下层级字段：
- head（报文头）：包含 sysId、msgId、sendDate、senderInstId、receiverInstId、direction。
- body（报文体）：包含 infoNo、instName、instId、reinstName、reinstId、startTime、endTime、reason、contactPerson、contactPhone。
- signature（数字签名域）。

**应答报文（response）**包含以下层级字段：
- head（报文头）：包含 sysId、msgId、sendDate、senderInstId、receiverInstId、direction、rspCd、rspMsg。
- body（报文体）：原文未明确说明包含的具体下级字段。
- signature（数字签名域）。

## 2. 适用边界

该报文适用于成员单位和网联平台之间的系统接口交互，专门用于传递生产运维计划信息。不适用于查询生产运维计划信息的场景（查询场景另有专门报文规范）。

## 3. 使用要求

原文未明确说明该报文发送的具体使用要求、操作顺序或禁止事项。报文交互应遵循系统接口传递生产运维计划信息的基本功能定义。

## 4. 关联能力

暂无。

## 5. 来源依据

- 来源文档：互联互通机制规范.md
- 来源章节：7.6 生产运维信息发送报文
- 来源说明：基于来源章节归纳，需人工复核原文一致性。
