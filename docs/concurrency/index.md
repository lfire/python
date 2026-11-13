---
title: 阶段导览 · 并发与异步
description: 写出正确、可诊断、可扩展的并发程序
---

<StageHeader stage='阶段六 · 并发与异步' level='★★★☆☆' time='11 讲' goal='写出正确、可诊断、可扩展的并发程序' prereq='上一阶段' />

# 阶段导览 · 并发与异步

> 写出正确、可诊断、可扩展的并发程序。本阶段共 11 讲，覆盖 线程与同步、进程与 IPC、IO 多路复用、生成器协程、asyncio 与并发模式。建议按顺序推进：每讲都先建立直觉、再跑通示例、最后看工程边界，讲与讲之间的依赖关系在下面的地图里一目了然。

## 这个阶段解决什么问题

线程与同步、进程与 IPC、IO 多路复用、生成器协程、asyncio 与并发模式。阶段划分不是按知识点罗列，而是按「学完能交付什么」倒推：前一阶段的输出正好是这一阶段的前置，跳过某一段往往会在后面某讲突然卡住，届时再回来补齐比按顺序学更费时。

<ConceptDiagram type='flow4' title='阶段六 · 并发与异步 · 知识主线' labels='任务|事件循环|IO|结果' caption='写出正确、可诊断、可扩展的并发程序' />

<Callout type="tip" title="怎么用这一阶段" text='先读导览确定出口能力，再逐讲打卡；遇到卡点优先回到对应讲的最小示例，而不是直接翻答案。共 11 讲，合计约 430 分钟。' />

## 阶段能力出口

<CheckList id='L6-goals' title='阶段六 · 并发与异步 · 能力自检' :items='["能独立完成本阶段 11 讲中的全部随堂检测", "能说清 线程与同步、进程与 IPC、IO 多路复用、生成器协程、asyncio 与并发模式 各自解决什么问题", "能把本阶段结论接到真实项目并说明代价"]' />

## 讲次地图

| 讲次 | 标题 | 难度 | 建议时长 | 学完能做什么 |
| --- | --- | --- | --- | --- |
| 060 | [并发、并行与 IO 模型全景](/concurrency/concurrency-intro) | ★★☆☆☆ | 30 分钟 | 为不同负载选对并发模型 |
| 061 | [threading：线程生命周期与共享状态](/concurrency/threading) | ★★★☆☆ | 35 分钟 | 能安全地在线程间传递数据 |
| 062 | [线程同步：Lock、Condition、Semaphore、Event](/concurrency/sync-primitives) | ★★★☆☆ | 40 分钟 | 用正确的原语表达协作关系 |
| 063 | [线程池与 Future 模式](/concurrency/threadpool) | ★★★☆☆ | 35 分钟 | 管理并发度、结果收集与失败传播 |
| 064 | [multiprocessing：进程、Pool 与共享内存](/concurrency/multiprocessing) | ★★★★☆ | 40 分钟 | 绕过 GIL 处理 CPU 密集任务 |
| 065 | [进程间通信：Queue、Pipe 与信号](/concurrency/ipc) | ★★★☆☆ | 30 分钟 | 构建可停止、可监控的多进程程序 |
| 066 | [IO 多路复用：select / poll / epoll](/concurrency/io-multiplex) | ★★★★☆ | 40 分钟 | 理解事件循环在系统调用层的样子 |
| 067 | [生成器协程：send、yield from 与调度器](/concurrency/generator-coroutine) | ★★★★☆ | 40 分钟 | 从语言机制推出 async/await 的由来 |
| 068 | [async / await 与协程对象](/concurrency/async-await) | ★★★☆☆ | 35 分钟 | 正确创建并驱动协程 |
| 069 | [asyncio 深入：Task、Future 与事件循环](/concurrency/asyncio) | ★★★★☆ | 45 分钟 | 掌握任务生命周期与取消语义 |
| 070 | [阶段综合：并发爬虫四级演进](/concurrency/capstone) | ★★★★☆ | 60 分钟 | 把单机脚本演进到可限流的分布式抓取 |

## 学习节奏建议

<StepBox title='并发与异步 · 前五讲推进节奏' :steps='[{"title": "第 1 步：并发、并行与 IO 模型全景", "body": "为不同负载选对并发模型", "tip": "预计 30 分钟，做完随手打卡"}, {"title": "第 2 步：threading：线程生命周期", "body": "能安全地在线程间传递数据", "tip": "预计 35 分钟，做完随手打卡"}, {"title": "第 3 步：线程同步：Lock、Condit", "body": "用正确的原语表达协作关系", "tip": "预计 40 分钟，做完随手打卡"}, {"title": "第 4 步：线程池与 Future 模式", "body": "管理并发度、结果收集与失败传播", "tip": "预计 35 分钟，做完随手打卡"}, {"title": "第 5 步：multiprocessing：", "body": "绕过 GIL 处理 CPU 密集任务", "tip": "预计 40 分钟，做完随手打卡"}]' />

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先看导览与概念图", "tone": "blue"}, {"title": "逐讲推进", "desc": "跑示例代码并做完随堂检测", "tone": "green"}, {"title": "边界复盘", "desc": "整理易错点与工程代价", "tone": "orange"}, {"title": "进入下一阶段", "desc": "带着出口能力继续", "tone": "purple"}]' direction="horizontal" title='阶段学习闭环' />

## 阶段进度

<ProgressTracker />

[下一阶段：阶段七 · 工程化与质量](/engineering/)
