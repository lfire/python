---
title: 阶段导览 · 服务端与数据
description: 独立交付一个生产可用的服务与数据访问层
---

<StageHeader stage='阶段八 · 服务端与数据' level='★★★☆☆' time='11 讲' goal='独立交付一个生产可用的服务与数据访问层' prereq='上一阶段' />

# 阶段导览 · 服务端与数据

> 独立交付一个生产可用的服务与数据访问层。本阶段共 11 讲，覆盖 HTTP / ASGI、FastAPI / Flask / Django、ORM、Redis、MQ、认证、对象存储与可观测性。建议按顺序推进：每讲都先建立直觉、再跑通示例、最后看工程边界，讲与讲之间的依赖关系在下面的地图里一目了然。

## 这个阶段解决什么问题

HTTP / ASGI、FastAPI / Flask / Django、ORM、Redis、MQ、认证、对象存储与可观测性。阶段划分不是按知识点罗列，而是按「学完能交付什么」倒推：前一阶段的输出正好是这一阶段的前置，跳过某一段往往会在后面某讲突然卡住，届时再回来补齐比按顺序学更费时。

<ConceptDiagram type='hub4' title='阶段八 · 服务端与数据 · 知识主线' labels='客户端|路由|服务|存储' caption='独立交付一个生产可用的服务与数据访问层' />

<Callout type="tip" title="怎么用这一阶段" text='先读导览确定出口能力，再逐讲打卡；遇到卡点优先回到对应讲的最小示例，而不是直接翻答案。共 11 讲，合计约 440 分钟。' />

## 阶段能力出口

<CheckList id='L8-goals' title='阶段八 · 服务端与数据 · 能力自检' :items='["能独立完成本阶段 11 讲中的全部随堂检测", "能说清 HTTP / ASGI、FastAPI / Flask / Django、ORM、Redis、MQ、认证、对象存储与可观测性 各自解决什么问题", "能把本阶段结论接到真实项目并说明代价"]' />

## 讲次地图

| 讲次 | 标题 | 难度 | 建议时长 | 学完能做什么 |
| --- | --- | --- | --- | --- |
| 082 | [HTTP 协议与 WSGI / ASGI](/server/http-wsgi) | ★★★☆☆ | 35 分钟 | 理解框架之下发生了什么 |
| 083 | [FastAPI / Flask / Django 选型](/server/frameworks) | ★★☆☆☆ | 30 分钟 | 按团队与场景选框架而不是按热度 |
| 084 | [路由、依赖注入与请求校验](/server/routing) | ★★★☆☆ | 35 分钟 | 把入口层做成可测试、可复用的薄层 |
| 085 | [REST API 设计、OpenAPI 与幂等](/server/rest-api) | ★★★☆☆ | 35 分钟 | 设计出稳定、可演进的接口契约 |
| 086 | [WebSocket / SSE / 长轮询与实时推送](/server/websocket) | ★★★★☆ | 35 分钟 | 为实时场景选对通道并管理连接状态 |
| 087 | [SQLAlchemy、连接池、事务与迁移](/server/orm) | ★★★★☆ | 45 分钟 | 写出可控、可诊断的数据库访问层 |
| 088 | [Redis 缓存：穿透、击穿、雪崩与分布式锁](/server/redis) | ★★★★☆ | 40 分钟 | 设计正确且可降级的缓存层 |
| 089 | [消息队列：Celery / RabbitMQ / Kafka](/server/mq) | ★★★★☆ | 45 分钟 | 用异步任务解耦并保证可靠投递 |
| 090 | [认证授权：Session、JWT、OAuth2 与 RBAC](/server/auth) | ★★★★☆ | 40 分钟 | 设计可撤销、可审计的身份体系 |
| 091 | [文件、对象存储、搜索与 gRPC](/server/storage) | ★★★☆☆ | 40 分钟 | 补齐服务端的外部依赖版图 |
| 092 | [阶段综合：生产级短链服务](/server/capstone) | ★★★★☆ | 60 分钟 | 把服务端各层串成一个可上线系统 |

## 学习节奏建议

<StepBox title='服务端与数据 · 前五讲推进节奏' :steps='[{"title": "第 1 步：HTTP 协议与 WSGI / ", "body": "理解框架之下发生了什么", "tip": "预计 35 分钟，做完随手打卡"}, {"title": "第 2 步：FastAPI / Flask ", "body": "按团队与场景选框架而不是按热度", "tip": "预计 30 分钟，做完随手打卡"}, {"title": "第 3 步：路由、依赖注入与请求校验", "body": "把入口层做成可测试、可复用的薄层", "tip": "预计 35 分钟，做完随手打卡"}, {"title": "第 4 步：REST API 设计、Open", "body": "设计出稳定、可演进的接口契约", "tip": "预计 35 分钟，做完随手打卡"}, {"title": "第 5 步：WebSocket / SSE ", "body": "为实时场景选对通道并管理连接状态", "tip": "预计 35 分钟，做完随手打卡"}]' />

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先看导览与概念图", "tone": "blue"}, {"title": "逐讲推进", "desc": "跑示例代码并做完随堂检测", "tone": "green"}, {"title": "边界复盘", "desc": "整理易错点与工程代价", "tone": "orange"}, {"title": "进入下一阶段", "desc": "带着出口能力继续", "tone": "purple"}]' direction="horizontal" title='阶段学习闭环' />

## 阶段进度

<ProgressTracker />

[下一阶段：阶段九 · 数据科学与 AI 工程](/data-ai/)
