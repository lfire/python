---
title: 阶段导览 · 资深进阶
description: 具备源码级理解、极致性能调优与架构演进能力
---

<StageHeader stage='阶段十一 · 资深进阶与源码' level='★★★★☆' time='8 讲' goal='具备源码级理解、极致性能调优与架构演进能力' prereq='上一阶段' />

# 阶段导览 · 资深进阶

> 具备源码级理解、极致性能调优与架构演进能力。本阶段共 8 讲，覆盖 CPython 源码、内存分配器与 GC、导入与事件循环源码、 specializing interpreter、架构与成长。建议按顺序推进：每讲都先建立直觉、再跑通示例、最后看工程边界，讲与讲之间的依赖关系在下面的地图里一目了然。

## 这个阶段解决什么问题

CPython 源码、内存分配器与 GC、导入与事件循环源码、 specializing interpreter、架构与成长。阶段划分不是按知识点罗列，而是按「学完能交付什么」倒推：前一阶段的输出正好是这一阶段的前置，跳过某一段往往会在后面某讲突然卡住，届时再回来补齐比按顺序学更费时。

<ConceptDiagram type='flow4' title='阶段十一 · 资深进阶与源码 · 知识主线' labels='源码|优化|架构|演进' caption='具备源码级理解、极致性能调优与架构演进能力' />

<Callout type="tip" title="怎么用这一阶段" text='先读导览确定出口能力，再逐讲打卡；遇到卡点优先回到对应讲的最小示例，而不是直接翻答案。共 8 讲，合计约 375 分钟。' />

## 阶段能力出口

<CheckList id='L11-goals' title='阶段十一 · 资深进阶与源码 · 能力自检' :items='["能独立完成本阶段 8 讲中的全部随堂检测", "能说清 CPython 源码、内存分配器与 GC、导入与事件循环源码、 specializing interpreter、架构与成长 各自解决什么问题", "能把本阶段结论接到真实项目并说明代价"]' />

## 讲次地图

| 讲次 | 标题 | 难度 | 建议时长 | 学完能做什么 |
| --- | --- | --- | --- | --- |
| 114 | [CPython 源码：对象、帧与求值循环](/advanced/cpython-source) | ★★★★★ | 50 分钟 | 能沿着源码读懂一条语句的执行 |
| 115 | [内存分配器 pymalloc 与 GC 源码](/advanced/allocator) | ★★★★★ | 45 分钟 | 定位并解决苛刻场景下的内存问题 |
| 116 | [导入系统源码与 import hook](/advanced/import-source) | ★★★★★ | 40 分钟 | 掌握启动期扩展能力与其代价 |
| 117 | [asyncio 事件循环与 Task 源码](/advanced/asyncio-source) | ★★★★★ | 45 分钟 | 读懂取消、超时与回调的真实路径 |
| 118 | [GIL 源码、自适应解释器与无 GIL 路线](/advanced/gil-source) | ★★★★★ | 50 分钟 | 理解性能演进方向并做技术判断 |
| 119 | [极致优化：从剖析到 C 扩展的十倍案例](/advanced/optimization) | ★★★★★ | 55 分钟 | 按层次系统性地压低延迟 |
| 120 | [架构设计：领域分层、演进与重构](/advanced/architecture) | ★★★★★ | 50 分钟 | 为长期演进的系统做结构决策 |
| 121 | [资深能力图谱、技术选型与持续精进](/advanced/senior-path) | ★★★★★ | 40 分钟 | 建立可自我更新的技术判断框架 |

## 学习节奏建议

<StepBox title='资深进阶 · 前五讲推进节奏' :steps='[{"title": "第 1 步：CPython 源码：对象、帧与", "body": "能沿着源码读懂一条语句的执行", "tip": "预计 50 分钟，做完随手打卡"}, {"title": "第 2 步：内存分配器 pymalloc 与", "body": "定位并解决苛刻场景下的内存问题", "tip": "预计 45 分钟，做完随手打卡"}, {"title": "第 3 步：导入系统源码与 import h", "body": "掌握启动期扩展能力与其代价", "tip": "预计 40 分钟，做完随手打卡"}, {"title": "第 4 步：asyncio 事件循环与 Ta", "body": "读懂取消、超时与回调的真实路径", "tip": "预计 45 分钟，做完随手打卡"}, {"title": "第 5 步：GIL 源码、自适应解释器与无 ", "body": "理解性能演进方向并做技术判断", "tip": "预计 50 分钟，做完随手打卡"}]' />

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先看导览与概念图", "tone": "blue"}, {"title": "逐讲推进", "desc": "跑示例代码并做完随堂检测", "tone": "green"}, {"title": "边界复盘", "desc": "整理易错点与工程代价", "tone": "orange"}, {"title": "进入下一阶段", "desc": "带着出口能力继续", "tone": "purple"}]' direction="horizontal" title='阶段学习闭环' />

## 阶段进度

<ProgressTracker />

[下一阶段：阶段十二 · 工程实战](/projects/)
