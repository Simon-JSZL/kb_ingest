---
kb_id: biz-offline-abe5181bec-v1
title: 生产运维信息查询报文结构及查询规则
doc_type: biz
domain: 网联清算业务
category: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
category_keywords:
- 查询开始时间
- 生产运维信息查询报文
- startTime
- 查询结束时间
- infoNo
- endTime
- head
- sysId
- msgId
- sendDate
subcategory: 生产运维信息查询报文
related_items:
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: 生产运维信息发送报文
  关联说明: 与当前小类共享核心语义：receiverInstId、senderInstId、direction；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: 交易监控统计信息报文
  关联说明: 与当前小类共享核心语义：receiverInstId、senderInstId、direction；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: 自由格式报文
  关联说明: 与当前小类共享核心语义：receiverInstId、senderInstId、direction；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.4 生产运维信息查询报文(计划时间段查询)
  关联说明: 与当前小类共享核心语义：生产运维信息查询报文、sendDate、msgId
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.3 生产运维信息查询报文(运维信息编号查询)
  关联说明: 与当前小类共享核心语义：生产运维信息查询报文、sendDate、msgId
  关联度: 高
business_modules:
- 网联平台
- 成员单位
source_doc: 互联互通机制规范.md
source_version: V1.3
source_section: 7.7 生产运维信息查询报文
source_order: 22
source_pages: []
source_trace: section=7.7 生产运维信息查询报文
effective_date: ''
owner: 网联清算业务知识库
confidentiality: 内部
risk_level: medium
applicable_roles: []
tags:
- 生产运维信息查询报文
- '7.7'
- 查询规则
- 报文结构
status: active
review_status: pending
---

# 生产运维信息查询报文结构及查询规则

知识分类：
大类标题：Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
小类标题：生产运维信息查询报文
关键词：查询开始时间、生产运维信息查询报文、startTime、查询结束时间、infoNo、endTime、head、sysId、msgId、sendDate
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
    "小类标题": "交易监控统计信息报文",
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
    "小类标题": "B.4 生产运维信息查询报文(计划时间段查询)",
    "关联说明": "与当前小类共享核心语义：生产运维信息查询报文、sendDate、msgId",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.3 生产运维信息查询报文(运维信息编号查询)",
    "关联说明": "与当前小类共享核心语义：生产运维信息查询报文、sendDate、msgId",
    "关联度": "高"
  }
]

## 1. 核心内容

生产运维信息查询报文用于成员单位和网联平台之间通过系统接口的方式，查询生产运维计划信息。

**请求报文结构**：
- request
  - head
    - sysId
    - msgId
    - sendDate
    - senderInstId
    - receiverInstId
    - direction
  - body
    - startTime
    - endTime
    - infoNo
  - signature

**应答报文结构**：
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
    - infoNo
    - instName
    - instId
    - reinstName
    - reinstId
    - startTime
    - endTime
    - reason
    - contactPerson
    - contactPhone
  - signature

**报文说明及查询规则**：
1. 查询报文适用范围：作为接收方，查询通知到自己方的相关生产运维信息。
2. 时间限制规则：“查询开始时间”不得超过1年（距离当前时间），“查询开始时间”和“查询结束时间”间隔不得超过3天。

## 2. 适用边界

- 适用对象：成员单位和网联平台。
- 适用场景：作为接收方，查询通知到自己方的相关生产运维信息。
- 时间范围限制：“查询开始时间”不得超过1年（距离当前时间），“查询开始时间”和“查询结束时间”间隔不得超过3天。

## 3. 使用要求

- 发起查询前，必须校验“查询开始时间”距离当前时间是否超过1年，若超过则不得发起查询。
- 发起查询前，必须校验“查询开始时间”和“查询结束时间”的间隔是否超过3天，若超过则不得发起查询。
- 查询方必须处于接收方角色，仅可查询通知到自己方的相关生产运维信息。

## 4. 关联能力

暂无。

## 5. 来源依据

- 来源文档：互联互通机制规范.md
- 来源章节：7.7 生产运维信息查询报文
- 来源说明：基于来源章节归纳，需人工复核原文一致性。
