---
kb_id: biz-offline-65cb5c4f40-v1
title: 交易监控统计信息报文
doc_type: biz
domain: 网联清算业务
category: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
category_keywords:
- 交易监控统计信息报文
- head
- sysId
- msgId
- sendDate
- senderInstId
- receiverInstId
- direction
- body
- signature
subcategory: 交易监控统计信息报文
related_items:
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: 生产运维信息发送报文
  关联说明: 与当前小类共享核心语义：receiverInstId、senderInstId、direction；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: 生产运维信息查询报文
  关联说明: 与当前小类共享核心语义：receiverInstId、senderInstId、direction；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: 自由格式报文
  关联说明: 与当前小类共享核心语义：receiverInstId、senderInstId、direction；来源结构处于同一章节组
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.1 交易监控统计信息报文
  关联说明: 与当前小类共享核心语义：senderInstId、交易监控统计信息报文、sendDate
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.2 生产运维信息发送报文
  关联说明: 与当前小类共享核心语义：senderInstId、sendDate、msgId
  关联度: 高
business_modules: []
source_doc: 互联互通机制规范.md
source_version: ''
source_section: 7.5 交易监控统计信息报文
source_order: 20
source_pages: []
source_trace: section=7.5 交易监控统计信息报文
effective_date: ''
owner: 网联清算业务知识库
confidentiality: 内部
risk_level: low
applicable_roles: []
tags:
- 交易监控统计信息报文
- 实时/准实时
- 监控数据
status: active
review_status: pending
---

# 交易监控统计信息报文

知识分类：
大类标题：Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
小类标题：交易监控统计信息报文
关键词：交易监控统计信息报文、head、sysId、msgId、sendDate、senderInstId、receiverInstId、direction、body、signature
关联信息：
[
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "生产运维信息发送报文",
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
    "关联说明": "与当前小类共享核心语义：receiverInstId、senderInstId、direction；来源结构处于同一章节组",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.1 交易监控统计信息报文",
    "关联说明": "与当前小类共享核心语义：senderInstId、交易监控统计信息报文、sendDate",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.2 生产运维信息发送报文",
    "关联说明": "与当前小类共享核心语义：senderInstId、sendDate、msgId",
    "关联度": "高"
  }
]

## 1. 核心内容

成员单位和网联平台之间通过系统接口的方式，实时/准实时相互传输监控数据。

**报文结构**

**请求报文**
- request
  - head
    - sysId
    - msgId
    - sendDate
    - senderInstId
    - receiverInstId
    - direction
  - body
    - mTrxCtgyCd
    - mAccTpCd
    - succCnt
    - succAmt
    - failCnt
    - failAmt
    - rate
  - signature

**应答报文**
- response
  - head
    - sysId
    - msgId
    - sendDate
    - senderInstId
    - receiverInstId
    - direction
    - rspCd
    - rspMsg
  - body
  - signature

## 2. 适用边界

原文未明确说明。

## 3. 使用要求

原文未明确说明。

## 4. 关联能力

暂无。

## 5. 来源依据

- 来源文档：互联互通机制规范.md
- 来源章节：7.5 交易监控统计信息报文
- 来源说明：基于来源章节归纳，需人工复核原文一致性。
