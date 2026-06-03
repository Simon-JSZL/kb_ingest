---
kb_id: biz-offline-dab45cebb4-v1
title: 自由格式报文-场景一
doc_type: biz
domain: 网联清算业务
category: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
category_keywords:
- 自由格式报文
- 场景一
- sendDate
- YYYY
- head
- sysId
- uops
- msgId
- uops051
- direction
subcategory: B.5 自由格式报文-场景一
related_items:
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.6 自由格式报文-场景二
  关联说明: 与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.7 自由格式报文-场景三
  关联说明: 与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近
  关联度: 高
- 大类标题: Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
  小类标题: B.8 自由格式报文-场景四
  关联说明: 与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组
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
- 自由格式报文
source_doc: 互联互通机制规范.md
source_version: V1.3
source_section: B.5 自由格式报文-场景一
source_order: 28
source_pages: []
source_trace: section=B.5 自由格式报文-场景一
effective_date: ''
owner: 网联清算业务知识库
confidentiality: 内部
risk_level: low
applicable_roles: []
tags:
- 自由格式报文
- 场景一
- head
- sysId
- uops
- msgId
- uops051
- sendDate
- YYYY
status: active
review_status: pending
---

# 自由格式报文-场景一

知识分类：
大类标题：Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3
小类标题：B.5 自由格式报文-场景一
关键词：自由格式报文、场景一、sendDate、YYYY、head、sysId、uops、msgId、uops051、direction
关联信息：
[
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.6 自由格式报文-场景二",
    "关联说明": "与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.7 自由格式报文-场景三",
    "关联说明": "与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组；章节位置接近",
    "关联度": "高"
  },
  {
    "大类标题": "Q/NUC 601-2023 网络支付清算平台 联合运维互联互通技术规范V1.3",
    "小类标题": "B.8 自由格式报文-场景四",
    "关联说明": "与当前小类共享核心语义：sendDate、uops051、自由格式报文；来源结构处于同一章节组",
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

**请求报文结构**

{
  "request": {
    "head": {
      "sysId": "uops",
      "msgId": "uops051.000.01",
      "sendDate": "YYYY-MM-DD HH:mm:ss",
      "senderInstId": "发起方机构标识",
      "receiverInstId": "接收方机构标识",
      "direction": "01"
    },
    "body": {
      "sceneId": "01",
      "content": {
        "trxCode": "交易代码",
        "trxType": "交易类型",
        "result": "熔断结果",
        "reason": "原因"
      }
    },
    "signature": "签名内容"
  }
}

**应答报文结构**

{
  "response": {
    "head": {
      "sysId": "uops",
      "msgId": "uops051.000.01",
      "sendDate": "YYYY-MM-DD HH:mm:ss",
      "senderInstId": "发起方机构标识",
      "receiverInstId": "接收方机构标识",
      "direction": "01",
      "rspCd": "0000",
      "rspMsg": "应答消息"
    },
    "body": {},
    "signature": "签名内容"
  }
}

## 2. 适用边界

适用于自由格式报文的场景一，用于传输交易代码、交易类型、熔断结果及原因等信息。

## 3. 使用要求

1. 请求报文中的 `sceneId` 必须设置为 "01"。
2. `sendDate` 格式必须为 "YYYY-MM-DD HH:mm:ss"。
3. `direction` 值为 "01"。
4. 报文必须包含签名内容。

## 4. 关联能力

暂无。

## 5. 来源依据

- 来源文档：互联互通机制规范.md
- 来源章节：B.5 自由格式报文-场景一
- 来源说明：基于来源章节归纳，需人工复核原文一致性。
